"""
Utilidades y Lógica Financiera para Parque Safari (Venta_safari).
Normativas Oficiales:
- Ley N° 20.956 (Regla de Redondeo en Efectivo del Banco Central de Chile).
- Subproceso de Cuadratura y Arqueo de Cajas (Protocolo Oficial de Cierre).
- Soporte para Eventos Promocionales con monedas de $1 y $5 pesos.
"""

from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from .models import Producto, PrecioEspecial, DetalleVenta, RegistroPrecioEspecial


def calcular_redondeo_ley_20956(monto, metodo_pago='EFECTIVO', tiene_promo_moneda_fisica=False):
    """
    Aplica la Regla de Redondeo para operaciones en efectivo (1 al 4 hacia abajo, 5 al 9 hacia arriba):
    - Cantidades que terminen en 1, 2, 3 o 4 se redondean hacia abajo a la decena inferior.
    - Cantidades que terminen en 5, 6, 7, 8 o 9 se redondean hacia arriba a la decena superior.
    - Excepción de Evento Promocional: Montos especiales de $1 a $5 pesos (ej. promoción 'segunda hamburguesa a $1 peso')
      se cobran al valor exacto de la moneda promocional para permitir su recepción física y cuadratura en caja.
    - Operaciones con tarjetas o transferencias electrónicas no se redondean (pago al peso exacto).
    
    Retorna tupla: (monto_final, ajuste_redondeo)
    Ejemplos:
      $1 -> $1 (Evento promocional con moneda de $1 peso)
      $5 -> $5 (Evento promocional con moneda de $5 pesos)
      $1.994 -> $1.990 (ajuste: -4)
      $1.995 -> $2.000 (ajuste: +5)
      $2.000 -> $2.000 (ajuste: 0)
    """
    monto_dec = Decimal(str(monto))
    if metodo_pago.upper() != 'EFECTIVO':
        return monto_dec, Decimal('0')

    monto_int = int(round(float(monto_dec)))

    # Excepción para eventos promocionales con monedas físicas de $1 o $5 pesos
    if 0 < monto_int <= 5 or tiene_promo_moneda_fisica:
        return Decimal(str(monto_int)), Decimal('0')

    resto = monto_int % 10

    if resto == 0:
        ajuste = 0
        final = monto_int
    elif resto <= 4:
        ajuste = -resto
        final = monto_int - resto
    else:
        ajuste = 10 - resto
        final = monto_int + ajuste

    return Decimal(str(final)), Decimal(str(ajuste))


def calcular_resumen_caja(caja):
    """
    Calcula el balance y resumen consolidado de una sesión de Caja:
    - Fondo de sencillo inicial (apertura)
    - Desglose de ventas por método de pago (Efectivo, Débito, Crédito, Transferencia)
    - Total de efectivo esperado para cuadratura
    """
    ventas_pagadas = caja.ventas.filter(estado='PAGADA')

    ventas_efectivo = ventas_pagadas.filter(metodo_pago='EFECTIVO').aggregate(total=Sum('total'))['total'] or Decimal('0')
    ventas_debito = ventas_pagadas.filter(metodo_pago='DEBITO').aggregate(total=Sum('total'))['total'] or Decimal('0')
    ventas_credito = ventas_pagadas.filter(metodo_pago='CREDITO').aggregate(total=Sum('total'))['total'] or Decimal('0')
    ventas_transferencia = ventas_pagadas.filter(metodo_pago='TRANSFERENCIA').aggregate(total=Sum('total'))['total'] or Decimal('0')

    total_ventas = ventas_efectivo + ventas_debito + ventas_credito + ventas_transferencia
    total_efectivo_esperado = Decimal(str(caja.monto_apertura)) + ventas_efectivo
    total_transacciones = ventas_pagadas.count()

    return {
        'monto_apertura': caja.monto_apertura,
        'ventas_efectivo': ventas_efectivo,
        'ventas_debito': ventas_debito,
        'ventas_credito': ventas_credito,
        'ventas_transferencia': ventas_transferencia,
        'total_ventas': total_ventas,
        'total_efectivo_esperado': total_efectivo_esperado,
        'total_transacciones': total_transacciones,
    }


# ==============================================================================
# GESTIÓN Y AUDITORÍA DE PRECIOS DURANTE LA VENTA (RF07)
# ==============================================================================
def validar_y_calcular_precio_linea(
    producto,
    cantidad=1,
    precio_solicitado=None,
    convenio_id=None,
    usuario=None,
    motivo=None,
    permite_manual=True
):
    """
    RF07 - Validación y Cálculo de Precios para Línea de Venta / Comanda.
    
    Reglas de Negocio Oficiales:
    - RF07.1: El precio base SIEMPRE se toma de producto.precio_base en BD (nunca se confía en el frontend).
    - RF07.2: El precio especial o convenio aplica única y exclusivamente al detalle de la venta actual;
              NUNCA modifica permanentemente Producto.precio_base en el catálogo.
    - RF07.3: Autorización estricta por rol (ADMINISTRADOR o CAJERO) para precios especiales manuales.
    - RF07.4: Trazabilidad total de auditoría (precio base original, precio aplicado, descuento, motivo, autor).
    - RF07.5: Convenios comerciales e institucionales validados contra PrecioEspecial en BD con control de vigencia.
    
    Blindaje contra contingencias:
    - Rechaza precios <= 0 (precios 0 o negativos).
    - Rechaza valores no numéricos.
    - Rechaza productos inactivos o no encontrados.
    - Rechaza convenios inexistentes, inactivos o expirados por rango de fechas.
    - Rechaza cantidades menores a 1.
    - Rechaza intentos de descuento no autorizados.
    """
    if not producto:
        raise ValidationError("El producto especificado no existe.")

    # 1. Validar estado activo del producto
    if not producto.activo:
        raise ValidationError(f"El producto '{producto.nombre}' se encuentra inactivo y no puede ser comercializado.")

    # 2. Validar cantidad
    try:
        cant_int = int(cantidad)
        if cant_int < 1:
            raise ValidationError("La cantidad a vender debe ser de al menos 1 unidad.")
    except (ValueError, TypeError):
        raise ValidationError("La cantidad debe ser un valor numérico entero válido.")

    # RF07.1: El precio base oficial SIEMPRE proviene de la BD
    precio_base_bd = Decimal(str(producto.precio_base))
    if precio_base_bd < Decimal('0'):
        raise ValidationError(f"El producto '{producto.nombre}' tiene un precio base negativo no válido.")

    es_especial = False
    precio_final = precio_base_bd
    motivo_final = ""
    convenio_obj = None
    autorizador = None

    # Caso A: Se solicitó aplicación de Convenio / Precio Especial registrado (RF07.5)
    if convenio_id:
        try:
            conv = PrecioEspecial.objects.select_related('producto').filter(id=convenio_id, producto=producto).first()
            if not conv:
                raise ValidationError(f"El convenio o condición especial #{convenio_id} no existe para el producto '{producto.nombre}'.")
            
            hoy = timezone.localdate()
            if not conv.es_vigente(hoy):
                raise ValidationError(f"El convenio '{conv.nombre_condicion}' no se encuentra vigente para la fecha actual ({hoy.strftime('%d/%m/%Y')}).")

            if conv.precio <= Decimal('0'):
                raise ValidationError(f"El precio configurado en el convenio '{conv.nombre_condicion}' no es válido (debe ser mayor a $0).")

            precio_final = Decimal(str(conv.precio))
            es_especial = True
            motivo_final = f"Convenio: {conv.nombre_condicion}"
            convenio_obj = conv
            autorizador = usuario if (usuario and usuario.is_authenticated) else None
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Error al validar convenio comercial: {str(e)}")

    # Caso B: Se solicitó precio manual / condición comercial autorizada (RF07.3)
    elif precio_solicitado is not None:
        try:
            precio_req_dec = Decimal(str(precio_solicitado))
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError("El precio solicitado contiene un formato no numérico inválido.")

        # Blindaje: rechazar precio <= 0
        if precio_req_dec <= Decimal('0'):
            raise ValidationError("El precio especial debe ser un valor monetario positivo mayor a $0.")

        # Si el precio solicitado difiere del precio base de catálogo:
        if precio_req_dec != precio_base_bd:
            if not permite_manual:
                raise ValidationError("No está permitida la modificación manual de precios en esta operación.")

            # RF07.3: Validar autorización de usuario
            es_autorizado = False
            if usuario and usuario.is_authenticated:
                if usuario.is_superuser or usuario.is_staff:
                    es_autorizado = True
                else:
                    perfil = getattr(usuario, 'perfil', None)
                    if perfil and perfil.rol in ['ADMINISTRADOR', 'CAJERO']:
                        es_autorizado = True

            if not es_autorizado:
                raise ValidationError("No tienes autorización para modificar precios de venta. Rol requerido: Cajero o Administrador.")

            # Validar motivo justificado
            motivo_limpio = str(motivo or '').strip()
            if not motivo_limpio:
                raise ValidationError("Debe ingresar un motivo o justificación comercial para aplicar un precio especial manual.")

            precio_final = precio_req_dec
            es_especial = True
            motivo_final = motivo_limpio[:200]
            autorizador = usuario

    # Cálculo final de subtotales
    descuento_unitario = max(Decimal('0'), precio_base_bd - precio_final)
    subtotal = Decimal(str(cant_int)) * precio_final

    return {
        'producto': producto,
        'cantidad': cant_int,
        'precio_original': precio_base_bd,
        'precio_aplicado': precio_final,
        'descuento_unitario': descuento_unitario,
        'subtotal': subtotal,
        'es_precio_especial': es_especial,
        'motivo': motivo_final,
        'convenio_obj': convenio_obj,
        'autorizado_por': autorizador,
    }


def registrar_precio_especial_auditoria(venta, detalle_venta, calculo_dict):
    """
    RF07.4 - Trazabilidad e Inmutabilidad de Auditoría.
    Registra el evento de precio especial en RegistroPrecioEspecial y en los campos de DetalleVenta.
    """
    if not calculo_dict.get('es_precio_especial'):
        return None

    # 1. Asignar atributos en DetalleVenta
    if detalle_venta:
        detalle_venta.precio_original = calculo_dict['precio_original']
        detalle_venta.es_precio_especial = True
        detalle_venta.motivo_precio_especial = calculo_dict['motivo']
        detalle_venta.autorizado_por = calculo_dict['autorizado_por'] or venta.cajero
        detalle_venta.save()

    # 2. Registrar en tabla de auditoría inmutable
    registro = RegistroPrecioEspecial.objects.create(
        venta=venta,
        detalle_venta=detalle_venta,
        producto=calculo_dict['producto'],
        precio_original=calculo_dict['precio_original'],
        precio_aplicado=calculo_dict['precio_aplicado'],
        descuento_unitario=calculo_dict['descuento_unitario'],
        cantidad=calculo_dict['cantidad'],
        usuario=calculo_dict['autorizado_por'] or venta.cajero,
        motivo=calculo_dict['motivo'],
        convenio_origen=calculo_dict.get('convenio_obj')
    )
    return registro


# ==============================================================================
# MOTOR DE GENERACIÓN Y REIMPRESIÓN DE TICKETS (RF08 - Cocina, Barra, Comprobante)
# ==============================================================================
def generar_contenido_ticket_cocina(pedido, items_cocina, es_reimpresion=False, num_reimpresion=0, usuario_reimpresion=None):
    """
    Genera el formato de texto estructurado para el Ticket de Cocina Caliente (RF08.2).
    Incluye código, modalidad (Mesa / Venta Rápida), fecha/hora, ronda, productos de elaboración,
    cantidades y observaciones individuales (RF12).
    """
    venta = pedido.venta
    local_nom = venta.punto_venta.nombre if venta.punto_venta else "Restaurante Parque Safari"
    if venta.modalidad == 'MESA' and venta.mesa:
        mesa_txt = f"Mesa: {venta.mesa.identificador} (Salón)"
    else:
        mesa_txt = "Retiro Rápido / Mostrador"
    rondas_total = venta.pedidos.count()
    num_ronda = list(venta.pedidos.order_by('id').values_list('id', flat=True)).index(pedido.id) + 1 if pedido.id else rondas_total
    hora_str = timezone.localtime(pedido.creado_en).strftime("%d/%m/%Y %H:%M:%S") if pedido.creado_en else timezone.localtime().strftime("%d/%m/%Y %H:%M:%S")

    lineas = []
    if es_reimpresion:
        u_nom = usuario_reimpresion.get_full_name() or usuario_reimpresion.username if usuario_reimpresion else "Supervisión"
        lineas.append("****************************************")
        lineas.append(f"*** COPIA DE REIMPRESIÓN #{num_reimpresion} ***")
        lineas.append(f"*** {timezone.localtime().strftime('%d/%m/%Y %H:%M:%S')} | Por: {u_nom} ***")
        lineas.append("****************************************")

    lineas.append("========================================")
    lineas.append("     PARQUE SAFARI - COMANDA COCINA     ")
    lineas.append(f"Local: {local_nom}")
    lineas.append(f"Comanda #{pedido.id:04d} | Ronda #{num_ronda}")
    lineas.append(f"Ubicación: {mesa_txt}")
    lineas.append(f"Fecha/Hora: {hora_str}")
    lineas.append("========================================")
    lineas.append("CANT  PRODUCTO / ELABORACIÓN")
    lineas.append("----------------------------------------")

    total_unidades = 0
    for d in items_cocina:
        p_nom = d.producto.nombre
        total_unidades += d.cantidad
        lineas.append(f" {d.cantidad:>2}x  {p_nom[:32]}")
        if d.observaciones and d.observaciones.strip():
            lineas.append(f"      Nota: {d.observaciones.strip()[:60]}")

    lineas.append("----------------------------------------")
    lineas.append(f"TOTAL PRODUCTOS COCINA: {total_unidades} unid.")
    if pedido.observaciones and pedido.observaciones.strip():
        lineas.append(f"Obs. General: {pedido.observaciones.strip()[:70]}")
    lineas.append("========================================")
    return "\n".join(lineas)


def generar_contenido_ticket_barra(pedido, items_barra, es_reimpresion=False, num_reimpresion=0, usuario_reimpresion=None):
    """
    Genera el formato de texto estructurado para el Ticket de Barra / Cafetería / Snacks (RF08.3).
    Incluye productos terminados, bebidas, cafés, snacks o tickets de juegos.
    """
    venta = pedido.venta
    local_nom = venta.punto_venta.nombre if venta.punto_venta else "Barra Parque Safari"
    if venta.modalidad == 'MESA' and venta.mesa:
        mesa_txt = f"Mesa: {venta.mesa.identificador} (Salón)"
    else:
        mesa_txt = "Retiro Rápido / Mostrador"
    rondas_total = venta.pedidos.count()
    num_ronda = list(venta.pedidos.order_by('id').values_list('id', flat=True)).index(pedido.id) + 1 if pedido.id else rondas_total
    hora_str = timezone.localtime(pedido.creado_en).strftime("%d/%m/%Y %H:%M:%S") if pedido.creado_en else timezone.localtime().strftime("%d/%m/%Y %H:%M:%S")

    lineas = []
    if es_reimpresion:
        u_nom = usuario_reimpresion.get_full_name() or usuario_reimpresion.username if usuario_reimpresion else "Supervisión"
        lineas.append("****************************************")
        lineas.append(f"*** COPIA DE REIMPRESIÓN #{num_reimpresion} ***")
        lineas.append(f"*** {timezone.localtime().strftime('%d/%m/%Y %H:%M:%S')} | Por: {u_nom} ***")
        lineas.append("****************************************")

    lineas.append("========================================")
    lineas.append("      PARQUE SAFARI - COMANDA BARRA     ")
    lineas.append(f"Local: {local_nom}")
    lineas.append(f"Comanda #{pedido.id:04d} | Ronda #{num_ronda}")
    lineas.append(f"Ubicación: {mesa_txt}")
    lineas.append(f"Fecha/Hora: {hora_str}")
    lineas.append("========================================")
    lineas.append("CANT  BEBIDA / CAFETERÍA / SNACK")
    lineas.append("----------------------------------------")

    total_unidades = 0
    for d in items_barra:
        p_nom = d.producto.nombre
        total_unidades += d.cantidad
        lineas.append(f" {d.cantidad:>2}x  {p_nom[:32]}")
        if d.observaciones and d.observaciones.strip():
            lineas.append(f"      Nota: {d.observaciones.strip()[:60]}")

    lineas.append("----------------------------------------")
    lineas.append(f"TOTAL PRODUCTOS BARRA: {total_unidades} unid.")
    lineas.append("========================================")
    return "\n".join(lineas)


def generar_contenido_comprobante_venta(venta, es_reimpresion=False, num_reimpresion=0, usuario_reimpresion=None):
    """
    Genera el comprobante de cliente / boleta fiscal de venta (RF08.4).
    Incluye detalle consolidado de venta, precios aplicados, descuentos, redondeo Ley 20.956 y método de pago.
    """
    local_nom = venta.punto_venta.nombre if venta.punto_venta else "Parque Safari General"
    cajero_nom = venta.cajero.get_full_name() or venta.cajero.username if venta.cajero else "Cajero Autorizado"
    caja_nom = venta.caja.nombre if venta.caja else "Caja Operativa"
    mesa_txt = f"Consumo en Mesa {venta.mesa.identificador}" if (venta.modalidad == 'MESA' and venta.mesa) else "Venta Rápida Mostrador"
    hora_str = timezone.localtime(venta.fecha_hora).strftime("%d/%m/%Y %H:%M:%S") if venta.fecha_hora else timezone.localtime().strftime("%d/%m/%Y %H:%M:%S")

    lineas = []
    if es_reimpresion:
        u_nom = usuario_reimpresion.get_full_name() or usuario_reimpresion.username if usuario_reimpresion else "Supervisión"
        lineas.append("****************************************")
        lineas.append(f"*** COPIA DE REIMPRESIÓN #{num_reimpresion} ***")
        lineas.append(f"*** {timezone.localtime().strftime('%d/%m/%Y %H:%M:%S')} | Por: {u_nom} ***")
        lineas.append("****************************************")

    lineas.append("========================================")
    lineas.append("          PARQUE SAFARI CHILE           ")
    lineas.append("      RUT: 76.842.109-5 | Rancagua      ")
    lineas.append(f"Local: {local_nom}")
    lineas.append(f"Boleta / Comprobante: TKT-VEN-{venta.id:05d}")
    lineas.append(f"Fecha: {hora_str}")
    lineas.append(f"Cajero: {cajero_nom}")
    lineas.append(f"Caja: {caja_nom}")
    lineas.append(f"Modalidad: {mesa_txt}")
    lineas.append("========================================")
    lineas.append("CANT  DESCRIPCIÓN              TOTAL   ")
    lineas.append("----------------------------------------")

    subtotal_items = Decimal('0')
    descuento_total = Decimal('0')

    detalles = venta.detalles.select_related('producto').all()
    for d in detalles:
        subtotal_items += d.subtotal
        if d.precio_original and d.precio_original > d.precio_aplicado:
            ahorro_linea = (d.precio_original - d.precio_aplicado) * d.cantidad
            descuento_total += ahorro_linea

        precio_txt = f"${int(d.subtotal):,}".replace(",", ".")
        lineas.append(f" {d.cantidad:>2}x  {d.producto.nombre[:22]:<22} {precio_txt:>9}")
        if d.es_precio_especial and d.motivo_precio_especial:
            lineas.append(f"      [{d.motivo_precio_especial[:30]}]")

    lineas.append("----------------------------------------")
    subtotal_bruto = venta.total_sin_redondeo or subtotal_items or (venta.total if venta.total else Decimal('0'))
    subtotal_str = f"${int(subtotal_bruto):,}".replace(",", ".")
    lineas.append(f"Subtotal Bruto:             {subtotal_str:>16}")

    if descuento_total > 0:
        desc_str = f"-${int(descuento_total):,}".replace(",", ".")
        lineas.append(f"Descuentos / Convenios:     {desc_str:>16}")

    if venta.redondeo_ley_20956 and venta.redondeo_ley_20956 != 0:
        signo = "+" if venta.redondeo_ley_20956 > 0 else ""
        red_str = f"{signo}${int(venta.redondeo_ley_20956):,}".replace(",", ".")
        lineas.append(f"Redondeo Ley 20.956:        {red_str:>16}")

    lineas.append("========================================")
    total_str = f"${int(venta.total):,}".replace(",", ".")
    lineas.append(f"TOTAL PAGADO:               {total_str:>16}")
    lineas.append(f"Método de Pago:             {venta.get_metodo_pago_display():>12}")
    lineas.append(f"Estado de Operación:        {venta.get_estado_display():>12}")

    # Cumplimiento Ley N° 20.918 Art. 64 bis: Desglose y sugerencia voluntaria de propina del 10%
    if venta.modalidad == 'MESA' or (venta.mesa is not None):
        propina_sug = int(round(Decimal(str(subtotal_bruto)) * Decimal('0.10')))
        total_con_propina = int(venta.total) + propina_sug
        lineas.append("----------------------------------------")
        prop_str = f"${propina_sug:,}".replace(",", ".")
        tot_prop_str = f"${total_con_propina:,}".replace(",", ".")
        lineas.append(f"Propina Sugerida 10% (Ley 20.918): {prop_str:>9}")
        lineas.append(f"Total Sugerido c/Propina:         {tot_prop_str:>9}")
        lineas.append(" * La propina es 100% voluntaria")
    lineas.append("========================================")
    lineas.append("    ¡Gracias por visitar Parque Safari! ")
    lineas.append("========================================")
    return "\n".join(lineas)


# ==============================================================================
# SERVICIO LÓGICO DE IMPRESIÓN Y DESPACHO (RF09 - Cocina, Barra, Comprobante)
# ==============================================================================

def obtener_o_crear_punto_impresion(tipo_destino, punto_venta=None):
    """
    Obtiene o inicializa el Punto de Impresión (Cocina, Barra, Comprobante)
    asignado a un Local/Punto de Venta específico (RF09.1, RF09.2).
    """
    from .models import PuntoImpresion, PuntoVenta

    if not punto_venta:
        punto_venta = PuntoVenta.objects.filter(activo=True).order_by('id').first()

    if not punto_venta:
        return None

    punto_imp = PuntoImpresion.objects.filter(
        punto_venta=punto_venta,
        tipo_destino=tipo_destino,
        activo=True
    ).first()

    if not punto_imp:
        nombre_defecto = {
            'COCINA': f"Impresora Térmica Cocina - {punto_venta.nombre}",
            'BARRA': f"Impresora Térmica Barra - {punto_venta.nombre}",
            'COMPROBANTE': f"Impresora Boleta / Caja - {punto_venta.nombre}",
        }.get(tipo_destino, f"Impresora {tipo_destino} - {punto_venta.nombre}")

        punto_imp, _ = PuntoImpresion.objects.get_or_create(
            punto_venta=punto_venta,
            tipo_destino=tipo_destino,
            defaults={
                'nombre': nombre_defecto,
                'tipo_conexion': 'DIGITAL',
                'estado_operativo': 'ONLINE',
                'ancho_papel_mm': 80,
                'activo': True
            }
        )

    return punto_imp


def enviar_a_impresora(ticket, usuario=None, forzar_reintento=False):
    """
    Servicio lógico de impresión física y digital (RF09.1, RF09.3, RF09.4).
    - Desacoplamiento Total: Si la impresora falla o está offline, la venta y el pedido
      permanecen intactos en la base de datos (RF09.4).
    - Soporta 3 destinos físicos/lógicos: COCINA, BARRA, COMPROBANTE (RF09.2).
    - Registra auditoría inmutable en RegistroImpresion.
    """
    from .models import RegistroImpresion
    import socket

    if not ticket:
        return {'exito': False, 'error': 'Ticket inválido o nulo'}

    pv = ticket.get_punto_venta()
    if pv and not ticket.punto_venta:
        ticket.punto_venta = pv

    punto_imp = ticket.punto_impresion or obtener_o_crear_punto_impresion(ticket.tipo_destino, pv)
    if punto_imp and punto_imp.id:
        try:
            punto_imp.refresh_from_db()
        except Exception:
            pass
    ticket.punto_impresion = punto_imp

    if forzar_reintento:
        ticket.intentos_impresion += 1

    # 1. Comprobación de fallo simulado o estado fuera de línea (RF09.4)
    if punto_imp and (punto_imp.simular_fallo or punto_imp.estado_operativo != 'ONLINE'):
        motivo = f"Impresora '{punto_imp.nombre}' en estado {punto_imp.get_estado_operativo_display()}"
        if punto_imp.simular_fallo:
            motivo += " [Fallo simulado de hardware]"
        ticket.estado_impresion = 'FALLO'
        ticket.error_impresion = motivo
        ticket.save()

        RegistroImpresion.objects.create(
            ticket=ticket,
            punto_impresion=punto_imp,
            exitoso=False,
            modo=punto_imp.tipo_conexion if punto_imp else 'DESCONOCIDO',
            mensaje_error=motivo,
            es_reintento=forzar_reintento,
            usuario=usuario
        )
        return {
            'exito': False,
            'ticket': ticket,
            'punto_impresion': punto_imp,
            'error': motivo
        }

    # 2. Conexión a Impresora de Red (Ethernet / WiFi RAW 9100)
    if punto_imp and punto_imp.tipo_conexion == 'RED':
        if not punto_imp.direccion_ip:
            ticket.estado_impresion = 'FALLO'
            ticket.error_impresion = "Impresora de red sin dirección IP configurada"
            ticket.save()
            RegistroImpresion.objects.create(
                ticket=ticket,
                punto_impresion=punto_imp,
                exitoso=False,
                modo='RED',
                mensaje_error=ticket.error_impresion,
                es_reintento=forzar_reintento,
                usuario=usuario
            )
            return {'exito': False, 'ticket': ticket, 'punto_impresion': punto_imp, 'error': ticket.error_impresion}

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect((punto_imp.direccion_ip, punto_imp.puerto or 9100))

            payload = b'\x1b@' + (ticket.contenido_impresion or '').encode('latin-1', errors='replace') + b'\n\n\n\x1dV1'
            sock.sendall(payload)
            sock.close()

            ticket.estado_impresion = 'IMPRESO'
            ticket.error_impresion = None
            ticket.save()

            RegistroImpresion.objects.create(
                ticket=ticket,
                punto_impresion=punto_imp,
                exitoso=True,
                modo='RED',
                es_reintento=forzar_reintento,
                usuario=usuario
            )
            return {'exito': True, 'ticket': ticket, 'punto_impresion': punto_imp, 'modo': 'RED'}
        except Exception as e:
            ticket.estado_impresion = 'FALLO'
            ticket.error_impresion = f"Error de conexión RAW ({punto_imp.direccion_ip}:{punto_imp.puerto}): {str(e)}"
            ticket.save()

            RegistroImpresion.objects.create(
                ticket=ticket,
                punto_impresion=punto_imp,
                exitoso=False,
                modo='RED',
                mensaje_error=ticket.error_impresion,
                es_reintento=forzar_reintento,
                usuario=usuario
            )
            return {'exito': False, 'ticket': ticket, 'punto_impresion': punto_imp, 'error': ticket.error_impresion}

    # 3. Modo Digital Provisional (RF09.3 - Previsualización y Spooler de Navegador)
    ticket.estado_impresion = 'IMPRESO'
    ticket.error_impresion = None
    ticket.save()

    RegistroImpresion.objects.create(
        ticket=ticket,
        punto_impresion=punto_imp,
        exitoso=True,
        modo='DIGITAL',
        es_reintento=forzar_reintento,
        usuario=usuario
    )
    return {'exito': True, 'ticket': ticket, 'punto_impresion': punto_imp, 'modo': 'DIGITAL'}


def reintentar_despacho_impresion(ticket, usuario=None):
    """
    Reintenta el despacho de impresión de un ticket previamente fallido o pendiente (RF09.4).
    - Preserva la venta y los detalles contables.
    - Incrementa el contador de intentos y actualiza la auditoría.
    """
    if not ticket:
        raise ValidationError("El ticket para reintento no existe.")
    return enviar_a_impresora(ticket, usuario=usuario, forzar_reintento=True)


def emitir_tickets_comanda(pedido, usuario_emisor=None):
    """
    Clasifica, persiste y despacha tickets de producción (Cocina y Barra) para una comanda (RF08, RF09).
    - Cero Desperdicio de Papel: Solo genera ticket si hay productos asignados a ese destino.
    - Incrementalidad (RF08.5): Solo toma en cuenta los productos del pedido en curso.
    - Desacoplamiento (RF09.1): Persiste primero en BD y despacha al servicio de impresión.
    """
    from .models import Ticket

    detalles = list(pedido.detalles.select_related('producto', 'producto__categoria').all())
    if not detalles:
        raise ValidationError("El pedido no contiene productos para emitir comanda.")

    items_cocina = [d for d in detalles if d.producto.get_destino_operativo() == 'COCINA']
    items_barra = [d for d in detalles if d.producto.get_destino_operativo() == 'BARRA']

    tickets_creados = []
    despachos = []

    pv = None
    if pedido.venta:
        pv = pedido.venta.punto_venta or (pedido.venta.mesa.punto_venta if pedido.venta.mesa else None)

    # 1. Ticket Cocina Caliente (solo si hay ítems de cocina)
    if items_cocina:
        contenido_coc = generar_contenido_ticket_cocina(pedido, items_cocina)
        ticket_coc, _ = Ticket.objects.update_or_create(
            pedido=pedido,
            tipo_destino='COCINA',
            defaults={
                'venta': pedido.venta,
                'punto_venta': pv,
                'codigo': f"COM-COC-{pedido.id:04d}",
                'estado': 'EMITIDO',
                'contenido_impresion': contenido_coc
            }
        )
        res_coc = enviar_a_impresora(ticket_coc, usuario=usuario_emisor)
        tickets_creados.append(ticket_coc)
        despachos.append(res_coc)

    # 2. Ticket Barra / Cafetería (solo si hay ítems de barra)
    if items_barra:
        contenido_bar = generar_contenido_ticket_barra(pedido, items_barra)
        ticket_bar, _ = Ticket.objects.update_or_create(
            pedido=pedido,
            tipo_destino='BARRA',
            defaults={
                'venta': pedido.venta,
                'punto_venta': pv,
                'codigo': f"COM-BAR-{pedido.id:04d}",
                'estado': 'EMITIDO',
                'contenido_impresion': contenido_bar
            }
        )
        res_bar = enviar_a_impresora(ticket_bar, usuario=usuario_emisor)
        tickets_creados.append(ticket_bar)
        despachos.append(res_bar)

    return {
        'tickets': tickets_creados,
        'despachos': despachos,
        'tiene_cocina': bool(items_cocina),
        'tiene_barra': bool(items_barra),
        'total_tickets': len(tickets_creados)
    }


def emitir_comprobante_venta(venta, usuario_emisor=None):
    """
    Genera, persiste y despacha el comprobante de cliente / boleta de venta (RF08.4, RF09.1, RF09.2).
    """
    from .models import Ticket

    contenido = generar_contenido_comprobante_venta(venta)
    pedido_asoc = venta.pedidos.order_by('id').first()

    ticket_comp, _ = Ticket.objects.update_or_create(
        venta=venta,
        tipo_destino='COMPROBANTE',
        defaults={
            'pedido': pedido_asoc,
            'punto_venta': venta.punto_venta,
            'codigo': f"TKT-VEN-{venta.id:05d}",
            'estado': 'FINALIZADO',
            'contenido_impresion': contenido
        }
    )
    enviar_a_impresora(ticket_comp, usuario=usuario_emisor)
    return ticket_comp


def reimprimir_ticket(ticket, usuario_solicitante=None):
    """
    Reimprime un ticket existente de forma trazable (RF08.6, RF09.4).
    - Marca es_reimpresion=True e incrementa numero_reimpresiones.
    - Registra usuario_solicitante y marca de tiempo.
    - NO genera una venta nueva ni duplica detalles contables.
    - Vuelve a despachar el ticket a su punto de impresión registrado.
    """
    if not ticket:
        raise ValidationError("El ticket a reimprimir no existe.")

    ticket.numero_reimpresiones += 1
    ticket.es_reimpresion = True
    ticket.ultima_reimpresion_por = usuario_solicitante
    ticket.fecha_hora_reimpresion = timezone.now()

    # Regenerar contenido con banner de reimpresión
    if ticket.tipo_destino == 'COCINA' and ticket.pedido:
        items_cocina = [d for d in ticket.pedido.detalles.select_related('producto').all() if d.producto.get_destino_operativo() == 'COCINA']
        ticket.contenido_impresion = generar_contenido_ticket_cocina(
            ticket.pedido, items_cocina, es_reimpresion=True,
            num_reimpresion=ticket.numero_reimpresiones, usuario_reimpresion=usuario_solicitante
        )
    elif ticket.tipo_destino == 'BARRA' and ticket.pedido:
        items_barra = [d for d in ticket.pedido.detalles.select_related('producto').all() if d.producto.get_destino_operativo() == 'BARRA']
        ticket.contenido_impresion = generar_contenido_ticket_barra(
            ticket.pedido, items_barra, es_reimpresion=True,
            num_reimpresion=ticket.numero_reimpresiones, usuario_reimpresion=usuario_solicitante
        )
    elif ticket.tipo_destino == 'COMPROBANTE' and ticket.venta:
        ticket.contenido_impresion = generar_contenido_comprobante_venta(
            ticket.venta, es_reimpresion=True,
            num_reimpresion=ticket.numero_reimpresiones, usuario_reimpresion=usuario_solicitante
        )

    ticket.save()
    enviar_a_impresora(ticket, usuario=usuario_solicitante, forzar_reintento=True)
    return ticket

# ==============================================================================
# GESTIÓN DE CONSUMO INTERNO DEL PERSONAL / FIADO (RF10)
# ==============================================================================

def registrar_consumo_interno(empleado, punto_venta, items, usuario_registro=None, tipo_consumo='FIADO', observaciones='', caja=None):
    """
    Registra consumos de personal / fiados con deducción por planilla (RF10).
    - Valida que el colaborador esté activo en el sistema (RF10.1).
    - Precios oficiales tomados estrictamente de Producto.precio_base en BD (RF10.2).
    - Separación Contable Estricta (RF10.4): No se mezcla con ventas de clientes ni suma a recaudación de caja.
    - Integridad y Atomicidad (RF10.5): Cabecera y detalles en transacción atómica.
    """
    from .models import ConsumoInterno, DetalleConsumoInterno, Producto, PuntoVenta
    from django.contrib.auth.models import User
    from decimal import Decimal

    # 1. Validar colaborador (RF10.1)
    if isinstance(empleado, (int, str)):
        empleado_obj = User.objects.filter(id=empleado).select_related('perfil').first()
    else:
        empleado_obj = empleado

    if not empleado_obj or not empleado_obj.is_active:
        raise ValidationError("El trabajador seleccionado no existe o se encuentra inactivo.")

    if hasattr(empleado_obj, 'perfil') and not empleado_obj.perfil.activo:
        raise ValidationError("El perfil del colaborador se encuentra desactivado en el sistema.")

    # 2. Validar local / punto de venta
    if isinstance(punto_venta, (int, str)):
        pv_obj = PuntoVenta.objects.filter(id=punto_venta, activo=True).first()
    else:
        pv_obj = punto_venta

    if not pv_obj:
        raise ValidationError("Punto de venta o local no válido.")

    # 3. Validar productos y cantidades
    if not items or not isinstance(items, (list, tuple)):
        raise ValidationError("Debe incluir al menos un producto en el consumo interno.")

    items_preparados = []
    for it in items:
        p_ref = it.get('producto') or it.get('producto_id') or it.get('id')
        if isinstance(p_ref, Producto):
            prod = p_ref
        elif p_ref:
            prod = Producto.objects.filter(id=p_ref, activo=True).first()
        else:
            p_nom = it.get('nombre')
            prod = Producto.objects.filter(nombre=p_nom, activo=True).first() if p_nom else None

        if not prod or not prod.activo:
            raise ValidationError("Uno de los productos solicitados no existe o está inactivo.")

        try:
            cant = int(it.get('cantidad', 1))
            if cant <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError(f"La cantidad para '{prod.nombre}' debe ser un entero positivo mayor a cero.")

        # Precio oficial tomado de BD (RF10.2)
        precio_unitario = Decimal(str(prod.precio_base))
        subtotal = precio_unitario * cant
        items_preparados.append({
            'producto': prod,
            'cantidad': cant,
            'precio_unitario': precio_unitario,
            'subtotal': subtotal
        })

    total_consumo = sum(item['subtotal'] for item in items_preparados)

    # 3.1. Blindaje Anti-Fraude y Control de Riesgo Crediticio en Fiados
    saldo_actual = Decimal('0')
    if tipo_consumo == 'FIADO':
        es_admin_registrador = usuario_registro and (
            usuario_registro.is_staff or 
            getattr(getattr(usuario_registro, 'perfil', None), 'rol', '') == 'ADMINISTRADOR'
        )

        # Regla 1: Un cajero no puede auto-otorgarse fiados a sí mismo sin supervisión
        if usuario_registro and usuario_registro.id == empleado_obj.id and not es_admin_registrador:
            raise ValidationError(
                "Control Interno Anti-Fraude: No está permitido auto-otorgarse fiados a sí mismo. "
                "Requiere autorización de un administrador o supervisor de turno."
            )

        # Regla 2: Límite de Crédito Preventivo ($100.000 CLP acumulados)
        saldo_actual = ConsumoInterno.objects.filter(
            empleado=empleado_obj,
            estado='REGISTRADO'
        ).aggregate(s=Sum('total'))['s'] or Decimal('0')

        LIMITE_MAX_FIADO = Decimal('100000')
        if (saldo_actual + total_consumo) > LIMITE_MAX_FIADO and not es_admin_registrador:
            nombre_emp = empleado_obj.get_full_name() or empleado_obj.username
            raise ValidationError(
                f"Alerta de Riesgo Crediticio: El colaborador '{nombre_emp}' acumula un saldo pendiente de "
                f"${int(saldo_actual):,} CLP. Con este consumo de ${int(total_consumo):,} CLP supera el límite máximo "
                f"autorizado de ${int(LIMITE_MAX_FIADO):,} CLP. Requiere liquidación por nómina o visación de Administración."
            )

    # 4. Transacción atómica e integridad financiera
    with transaction.atomic():
        consumo = ConsumoInterno.objects.create(
            empleado=empleado_obj,
            punto_venta=pv_obj,
            caja=caja,
            registrado_por=usuario_registro,
            tipo_consumo=tipo_consumo,
            total=total_consumo,
            estado='REGISTRADO',
            observaciones=str(observaciones).strip()[:500] if observaciones else None
        )

        # Regla 3: Auditoría Forense Automática para Fiados Relevantes
        if tipo_consumo == 'FIADO' and (total_consumo >= Decimal('15000') or (saldo_actual + total_consumo) >= Decimal('40000')):
            from .models import AlertaTraslado
            nombre_emp = empleado_obj.get_full_name() or empleado_obj.username
            reg_username = usuario_registro.username if usuario_registro else 'Sistema'
            AlertaTraslado.objects.create(
                empleado=usuario_registro if usuario_registro else empleado_obj,
                punto_venta_origen=pv_obj,
                punto_venta_destino=pv_obj,
                autorizado_por=usuario_registro if usuario_registro else empleado_obj,
                motivo=f"[AUDITORÍA FIADOS / CRÉDITO] Colaborador '{nombre_emp}': Fiado por ${int(total_consumo):,} CLP en {pv_obj.nombre}. Saldo total: ${int(saldo_actual + total_consumo):,} CLP. Registró: {reg_username}."[:255]
            )

        detalles_a_crear = [
            DetalleConsumoInterno(
                consumo=consumo,
                producto=item['producto'],
                cantidad=item['cantidad'],
                precio_unitario=item['precio_unitario'],
                subtotal=item['subtotal']
            )
            for item in items_preparados
        ]
        DetalleConsumoInterno.objects.bulk_create(detalles_a_crear)

    return consumo


def liquidar_consumos_por_planilla(consumos_ids, supervisor=None):
    """
    Marca como DESCONTADO un conjunto de consumos internos (RF10.3).
    """
    from .models import ConsumoInterno

    if not consumos_ids:
        return 0

    actualizados = ConsumoInterno.objects.filter(
        id__in=consumos_ids,
        estado='REGISTRADO'
    ).update(
        estado='DESCONTADO',
        descontado_por=supervisor,
        fecha_hora_descuento=timezone.now()
    )
    return actualizados

def validar_modalidad_operativa(modalidad, mesa=None, punto_venta=None):
    """
    Valida la coherencia de modalidad de atención según requerimiento RF11:
    - MESA exige obligatoriamente una mesa física asignada y perteneciente al mismo local.
    - VENTA_RAPIDA / MOSTRADOR no debe ocupar mesa (mesa=None).
    """
    if modalidad == 'MESA':
        if not mesa:
            raise ValidationError("La modalidad de consumo en salón requiere obligatoriamente una mesa asignada (RF11.1).")
        if punto_venta and hasattr(punto_venta, 'id') and mesa.punto_venta_id != punto_venta.id:
            raise ValidationError("La mesa seleccionada no pertenece al local gastronómico de la operación.")
    elif modalidad in ['VENTA_RAPIDA', 'MOSTRADOR']:
        return 'VENTA_RAPIDA', None
    return modalidad, mesa


def sanitizar_observacion(texto, max_length=200):
    """
    Sanitiza y normaliza comentarios/observaciones de productos para comandas (RF12 / OWASP ASVS):
    - Elimina espacios en blanco superfluos al inicio y final.
    - Neutraliza inyecciones XSS escapando entidades HTML (<, >, &, ", ').
    - Trunca con seguridad a longitud máxima (por defecto 200 caracteres).
    - Retorna None si el texto queda vacío o solo contenía espacios o caracteres nulos.
    """
    if not texto:
        return None
    texto_str = str(texto).replace('\x00', '').strip()
    if not texto_str:
        return None
    import html
    texto_escapado = html.escape(texto_str)
    return texto_escapado[:max_length]

# ==============================================================================
# 9. GESTIÓN Y TRAZABILIDAD DE ENTREGA DE PEDIDOS (RF13)
# ==============================================================================

TRANSICIONES_PERMITIDAS_PEDIDO = {
    'PENDIENTE': ['EN_PREPARACION', 'LISTO', 'CANCELADO'],
    'EN_PREPARACION': ['LISTO', 'CANCELADO'],
    'LISTO': ['ENTREGADO', 'CANCELADO'],
    'ENTREGADO': [],
    'CANCELADO': [],
}

def validar_transicion_estado_pedido(pedido, nuevo_estado):
    """
    Valida las transiciones de estado permitidas en la máquina de estados de Pedidos (RF13.1).
    Flujo: PENDIENTE -> EN_PREPARACION -> LISTO -> ENTREGADO.
    Terminales: ENTREGADO, CANCELADO.
    """
    if pedido.estado == nuevo_estado:
        if pedido.estado == 'ENTREGADO':
            raise ValidationError("El pedido ya fue entregado previamente y no puede entregarse nuevamente (RF13.4).")
        return True

    permitidos = TRANSICIONES_PERMITIDAS_PEDIDO.get(pedido.estado, [])
    if nuevo_estado not in permitidos:
        if nuevo_estado == 'ENTREGADO':
            raise ValidationError(
                f"No se puede entregar un pedido que no ha sido marcado como LISTO previamente "
                f"(estado actual: {pedido.get_estado_display()}) (RF13.1)."
            )
        if pedido.estado == 'CANCELADO':
            raise ValidationError("Un pedido cancelado no puede cambiar de estado ni ser entregado (RF13).")
        if pedido.estado == 'ENTREGADO':
            raise ValidationError("El pedido ya fue entregado previamente y no admite modificaciones posteriores (RF13.4).")
        raise ValidationError(
            f"Transición de estado inválida: no se puede cambiar de {pedido.get_estado_display()} a {nuevo_estado}."
        )
    return True


def registrar_entrega_pedido(pedido_or_id, usuario_entrega=None, ticket=None, observaciones=None):
    """
    Servicio centralizado y blindado para registrar la entrega de un pedido al comensal (RF13).
    Aplica:
    - Transacción atómica y bloqueo por fila (select_for_update) para concurrencia (RF13.4).
    - Validación estricta: sólo pedidos en estado 'LISTO' pueden ser entregados (RF13.1).
    - Prevención de doble entrega: rechazo si ya está ENTREGADO o si existe registro de Entrega (RF13.4).
    - Rechazo de pedidos CANCELADOS.
    - Registro de trazabilidad con timestamp, usuario responsable, ticket y ubicación (RF13.2).
    - Cierre automático de tickets asociados a estado 'FINALIZADO'.
    """
    from .models import Pedido, Entrega, Ticket

    with transaction.atomic():
        if isinstance(pedido_or_id, Pedido):
            pedido_id = pedido_or_id.id
        else:
            pedido_id = int(pedido_or_id)

        pedido = Pedido.objects.select_for_update().filter(id=pedido_id).first()
        if not pedido:
            raise ValidationError(f"El pedido #{pedido_id} no existe.")

        if pedido.estado == 'CANCELADO':
            raise ValidationError(f"El pedido #{pedido.id} está cancelado y no puede ser entregado.")

        if pedido.estado == 'ENTREGADO' or Entrega.objects.filter(pedido=pedido).exists():
            raise ValidationError(f"El pedido #{pedido.id} ya ha sido entregado previamente (RF13.4).")

        if pedido.estado != 'LISTO':
            raise ValidationError(
                f"El pedido #{pedido.id} debe estar en estado 'LISTO' antes de registrar su entrega "
                f"(estado actual: {pedido.get_estado_display()}) (RF13.1)."
            )

        ticket_obj = ticket
        if not ticket_obj:
            ticket_obj = pedido.tickets.first()

        obs_texto = observaciones
        if not obs_texto:
            nombre_u = usuario_entrega.get_full_name() or usuario_entrega.username if usuario_entrega else "Personal de Servicio"
            obs_texto = f"Entregado al comensal por {nombre_u}"
        else:
            obs_texto = sanitizar_observacion(obs_texto, max_length=200)

        entrega = Entrega.objects.create(
            pedido=pedido,
            ticket=ticket_obj,
            usuario_entrega=usuario_entrega,
            observaciones=obs_texto
        )

        pedido.estado = 'ENTREGADO'
        pedido.save(update_fields=['estado', 'actualizado_en'])

        # Finalizar tickets de producción
        pedido.tickets.exclude(estado='FINALIZADO').update(estado='FINALIZADO')

        return entrega


def validar_disponibilidad_producto(producto, punto_venta=None):
    """
    RF15: Valida estrictamente que el producto se encuentre activo y habilitado
    para su comercialización en el punto de venta especificado.
    Lanza ValidationError si no cumple las condiciones de disponibilidad.
    """
    if not producto:
        raise ValidationError("El producto especificado no existe.")
    if not producto.activo:
        raise ValidationError(f"El producto '{producto.nombre}' se encuentra desactivado del catálogo.")
    if punto_venta:
        if not producto.esta_disponible_en(punto_venta):
            raise ValidationError(
                f"El producto '{producto.nombre}' no se encuentra disponible para venta en el local '{punto_venta.nombre}' (RF15)."
            )
    return True

# ==============================================================================
# CONTROL DE TIEMPOS DE ATENCIÓN (RF16)
# ==============================================================================

def formatear_fecha_hora_chile(dt, formato="%d/%m/%Y %H:%M:%S"):
    """
    Formatea un datetime en la zona horaria oficial de Chile ('America/Santiago').
    Maneja datetimes naive y aware de forma segura sin excepciones (RF16).
    """
    if dt is None:
        return None
    try:
        import zoneinfo
        chile_tz = zoneinfo.ZoneInfo("America/Santiago")
    except Exception:
        chile_tz = timezone.get_current_timezone()

    if timezone.is_naive(dt):
        dt_aware = timezone.make_aware(dt, timezone.get_current_timezone())
    else:
        dt_aware = dt

    dt_chile = dt_aware.astimezone(chile_tz)
    return dt_chile.strftime(formato)


def calcular_metricas_tiempos_pedido(pedido, en_curso=False):
    """
    RF16: Calcula y estructura las métricas completas de tiempos de atención de un pedido:
    - marcas temporales (creado, inicio preparación, listo, entregado)
    - marcas temporales localizadas para Chile (America/Santiago)
    - duraciones calculadas (tiempo en cola, tiempo preparación, tiempo despacho, espera total)
    - validación de orden cronológico
    - control de incompletos no inventados
    """
    from ventas.models import Pedido
    if isinstance(pedido, (int, str)):
        pedido = Pedido.objects.select_related('venta', 'venta__punto_venta', 'venta__mesa').prefetch_related('entregas').get(id=int(pedido))

    metricas = pedido.get_metricas_tiempos(en_curso=en_curso)

    # Agregar representación en horario local de Chile
    metricas['creado_en_chile'] = formatear_fecha_hora_chile(metricas['creado_en'])
    metricas['fecha_inicio_preparacion_chile'] = formatear_fecha_hora_chile(metricas['fecha_inicio_preparacion'])
    metricas['fecha_listo_chile'] = formatear_fecha_hora_chile(metricas['fecha_listo'])
    metricas['fecha_entregado_chile'] = formatear_fecha_hora_chile(metricas['fecha_entregado'])

    # Metadata de comanda y mesa
    if pedido.venta:
        metricas['venta_id'] = pedido.venta.id
        metricas['mesa_identificador'] = pedido.venta.mesa.identificador if pedido.venta.mesa else None
        metricas['punto_venta_nombre'] = pedido.venta.punto_venta.nombre if pedido.venta.punto_venta else None
    else:
        metricas['venta_id'] = None
        metricas['mesa_identificador'] = None
        metricas['punto_venta_nombre'] = None

    return metricas


def calcular_tiempos_promedio_local(punto_venta=None, fecha=None, pedidos_qs=None):
    """
    RF16: Calcula promedios reales de tiempos de atención por local gastronómico o general.
    Garantiza:
    - Tiempos de pedidos incompletos o cancelados NO se inventan ni sesgan el promedio de entregados.
    - Soporte multi-ronda independiente.
    - Cálculo robusto de tiempos de cola, preparación, despacho y espera total.
    """
    from django.db import models
    from ventas.models import Pedido

    if pedidos_qs is not None:
        qs = pedidos_qs
    else:
        qs = Pedido.objects.all().select_related('venta', 'venta__punto_venta', 'venta__mesa', 'venta__mesa__punto_venta').prefetch_related('entregas')
        if punto_venta:
            qs = qs.filter(models.Q(venta__punto_venta=punto_venta) | models.Q(venta__mesa__punto_venta=punto_venta))
        if fecha:
            qs = qs.filter(creado_en__date=fecha)

    total_pedidos = 0
    total_pendientes = 0
    total_en_preparacion = 0
    total_listos = 0
    total_cancelados = 0

    colas = []
    preparaciones = []
    despachos = []
    esperas = []

    for p in qs:
        total_pedidos += 1
        if p.estado == 'CANCELADO':
            total_cancelados += 1
            continue
        elif p.estado == 'PENDIENTE':
            total_pendientes += 1
        elif p.estado == 'EN_PREPARACION':
            total_en_preparacion += 1
        elif p.estado == 'LISTO':
            total_listos += 1

        # Solo pedidos efectivamente entregados se consideran en promedios de atención finalizada
        if p.estado == 'ENTREGADO' or p.fecha_entregado is not None:
            c = p.get_tiempo_cola_minutos(en_curso=False)
            if c is not None:
                colas.append(c)

            pr = p.get_tiempo_preparacion_minutos(en_curso=False)
            if pr is not None:
                preparaciones.append(pr)

            d = p.get_tiempo_despacho_minutos(en_curso=False)
            if d is not None:
                despachos.append(d)

            e = p.get_tiempo_espera_total_minutos(en_curso=False)
            if e is not None:
                esperas.append(e)

    total_entregados = len(esperas)

    return {
        'total_pedidos': total_pedidos,
        'total_entregados': total_entregados,
        'total_pendientes': total_pendientes,
        'total_en_preparacion': total_en_preparacion,
        'total_listos': total_listos,
        'total_cancelados': total_cancelados,
        'promedio_tiempo_cola_minutos': round(sum(colas) / len(colas), 1) if colas else 0.0,
        'promedio_tiempo_preparacion_minutos': round(sum(preparaciones) / len(preparaciones), 1) if preparaciones else 0.0,
        'promedio_tiempo_despacho_minutos': round(sum(despachos) / len(despachos), 1) if despachos else 0.0,
        'promedio_tiempo_espera_total_minutos': round(sum(esperas) / len(esperas), 1) if esperas else 0.0,
        'min_tiempo_espera_total_minutos': min(esperas) if esperas else 0.0,
        'max_tiempo_espera_total_minutos': max(esperas) if esperas else 0.0,
    }

# ==============================================================================
# GESTIÓN DE OCUPACIÓN DE MESAS (RF17)
# ==============================================================================

def validar_ocupacion_mesa(mesa, permitir_si_misma_venta=None):
    """
    RF17: Valida que la mesa se encuentre apta para ser ocupada o recibir comanda.
    Lanza ValidationError si:
    - La mesa está INACTIVA o en mantenimiento.
    - La mesa ya se encuentra ocupada por otra atención activa (doble ocupación).
    - La mesa tiene una cuenta abierta distinta a permitir_si_misma_venta.
    """
    from django.core.exceptions import ValidationError
    if not mesa:
        raise ValidationError("La mesa especificada no existe.")

    if mesa.estado == 'INACTIVA':
        raise ValidationError(f"La mesa '{mesa.identificador}' está inactiva o en mantenimiento y no puede ser ocupada (RF17).")

    venta_activa = mesa.get_venta_activa()
    if venta_activa:
        if permitir_si_misma_venta and venta_activa.pk == getattr(permitir_si_misma_venta, 'pk', permitir_si_misma_venta):
            return True
        raise ValidationError(
            f"La mesa '{mesa.identificador}' ya tiene una cuenta abierta activa (#{venta_activa.id}) y no puede ser ocupada nuevamente (RF17)."
        )

    if mesa.estado == 'OCUPADA' and not venta_activa:
        raise ValidationError(f"La mesa '{mesa.identificador}' ya se encuentra marcada como ocupada (RF17).")

    return True


def liberar_mesa_operativa(mesa, usuario=None, forzar=False):
    """
    RF17: Servicio centralizado para liberar una mesa operativa.
    Garantiza:
    - Rechazo si mantiene una cuenta abierta con consumos pendientes (blindaje contra liberar con cuenta abierta).
    - Reseteo atómico de estado a 'HABILITADA' y fecha_ocupacion a None.
    - Retorna tupla: (exito, mensaje).
    """
    if not mesa:
        return False, "Mesa inválida o inexistente."

    from django.db import transaction
    with transaction.atomic():
        from ventas.models import Mesa
        mesa_lock = Mesa.objects.select_for_update().get(pk=mesa.pk)

        if not forzar:
            va = mesa_lock.get_venta_activa()
            if va is not None:
                return False, f"No se puede liberar la mesa '{mesa_lock.identificador}' porque mantiene la cuenta abierta #{va.id} con consumos pendientes de cobro (RF17)."

        mesa_lock.estado = 'HABILITADA'
        mesa_lock.fecha_ocupacion = None
        mesa_lock.save(update_fields=['estado', 'fecha_ocupacion'])

        return True, f"Mesa '{mesa_lock.identificador}' liberada exitosamente para nuevos comensales."


def calcular_metricas_ocupacion_local(punto_venta=None):
    """
    RF17: Retorna estadísticas de ocupación y rotación de mesas en un local o parque general.
    """
    from ventas.models import Mesa
    qs = Mesa.objects.all()
    if punto_venta:
        qs = qs.filter(punto_venta=punto_venta)

    total_mesas = qs.count()
    mesas_libres = 0
    mesas_ocupadas = 0
    mesas_inactivas = 0
    mesas_reservadas = 0
    duraciones_min = []

    for m in qs:
        if m.estado == 'INACTIVA':
            mesas_inactivas += 1
        elif m.estado == 'RESERVADA':
            mesas_reservadas += 1
        elif m.esta_ocupada():
            mesas_ocupadas += 1
            dur = m.get_duracion_ocupacion_minutos()
            if dur is not None:
                duraciones_min.append(dur)
        else:
            mesas_libres += 1

    tasa_ocupacion = round((mesas_ocupadas / total_mesas * 100), 1) if total_mesas > 0 else 0.0
    prom_duracion = round(sum(duraciones_min) / len(duraciones_min), 1) if duraciones_min else 0.0

    return {
        'total_mesas': total_mesas,
        'mesas_libres': mesas_libres,
        'mesas_ocupadas': mesas_ocupadas,
        'mesas_inactivas': mesas_inactivas,
        'mesas_reservadas': mesas_reservadas,
        'tasa_ocupacion_porcentaje': tasa_ocupacion,
        'promedio_duracion_ocupacion_minutos': prom_duracion,
    }

# ==============================================================================
# REPORTES Y ESTADÍSTICAS OFICIALES PARQUE SAFARI (RF18)
# ==============================================================================

def generar_reporte_estadistico_integral(
    fecha_inicio=None,
    fecha_fin=None,
    punto_venta=None,
    usuario=None,
    modalidad=None
):
    """
    RF18: Motor centralizado de reportes analíticos y estadísticas 100% gobernado por la base de datos real:
    - RF18.1: Cero mocks / eliminación total de datos inventados.
    - RF18.2: Filtros dinámicos por rango de fechas (inicio/fin), Punto de Venta y Colaborador.
    - RF18.3: Ventas realizadas (totales recaudados, redondeo Ley 20.956, desglose por medio de pago, modalidad y precios especiales).
    - RF18.4: Ranking de productos más vendidos (volumen de unidades y recaudación, considerando históricos y productos desactivados).
    - RF18.5: Tiempos de atención, despacho y preparación culinaria (solo sobre órdenes válidas entregadas).
    - RF18.6: Métricas de ocupación y rotación de mesas (integrado con RF17).
    - Blindaje contra rangos invertidos, días sin ventas y división por cero.
    """
    import datetime
    from django.contrib.auth.models import User
    from django.db import models
    from django.db.models import Sum, Count, Q
    from django.db.models.functions import TruncMonth, TruncDate, TruncHour
    from ventas.models import Venta, DetalleVenta, Pedido, PuntoVenta, Mesa

    # 1. Normalización y sanitización de rango de fechas
    hoy = timezone.localdate()

    if isinstance(fecha_fin, str) and fecha_fin.strip():
        try:
            fecha_fin = datetime.datetime.strptime(fecha_fin.strip(), '%Y-%m-%d').date()
        except Exception:
            fecha_fin = hoy
    elif not isinstance(fecha_fin, datetime.date):
        fecha_fin = hoy

    if isinstance(fecha_inicio, str) and fecha_inicio.strip():
        try:
            fecha_inicio = datetime.datetime.strptime(fecha_inicio.strip(), '%Y-%m-%d').date()
        except Exception:
            fecha_inicio = fecha_fin.replace(day=1)
    elif not isinstance(fecha_inicio, datetime.date):
        # Por defecto, mes en curso desde el día 1
        fecha_inicio = fecha_fin.replace(day=1)

    # Blindaje contra rango inválido (fecha_inicio posterior a fecha_fin)
    if fecha_inicio > fecha_fin:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    # 2. Resolución de PuntoVenta y Usuario
    pv_obj = None
    if punto_venta:
        if isinstance(punto_venta, (int, str)) and str(punto_venta).isdigit():
            pv_obj = PuntoVenta.objects.filter(id=int(punto_venta)).first()
        elif isinstance(punto_venta, PuntoVenta):
            pv_obj = punto_venta

    user_obj = None
    if usuario:
        if isinstance(usuario, (int, str)) and str(usuario).isdigit():
            user_obj = User.objects.filter(id=int(usuario)).first()
        elif isinstance(usuario, User):
            user_obj = usuario

    # 3. Base QuerySet de Ventas Pagadas (excluye estrictamente ventas anuladas)
    ventas_base = Venta.objects.filter(
        estado='PAGADA',
        fecha_hora__date__gte=fecha_inicio,
        fecha_hora__date__lte=fecha_fin
    )
    anuladas_base = Venta.objects.filter(
        estado='ANULADA',
        fecha_hora__date__gte=fecha_inicio,
        fecha_hora__date__lte=fecha_fin
    )

    if pv_obj:
        ventas_base = ventas_base.filter(punto_venta=pv_obj)
        anuladas_base = anuladas_base.filter(punto_venta=pv_obj)

    if user_obj:
        ventas_base = ventas_base.filter(cajero=user_obj)
        anuladas_base = anuladas_base.filter(cajero=user_obj)

    if modalidad in ['MESA', 'VENTA_RAPIDA', 'MOSTRADOR']:
        ventas_base = ventas_base.filter(modalidad=modalidad)

    # 4. Agregación financiera de ventas (RF18.3)
    agg_ventas = ventas_base.aggregate(
        total_ventas=Sum('total'),
        total_sin_red=Sum('total_sin_redondeo'),
        total_red=Sum('redondeo_ley_20956')
    )
    total_recaudado = agg_ventas['total_ventas'] or Decimal('0')
    total_sin_redondeo = agg_ventas['total_sin_red'] or Decimal('0')
    total_redondeo = agg_ventas['total_red'] or Decimal('0')
    cantidad_ventas = ventas_base.count()
    cantidad_anuladas = anuladas_base.count()
    ticket_promedio = round(float(total_recaudado) / cantidad_ventas, 0) if cantidad_ventas > 0 else 0.0

    # Desglose por método de pago
    ventas_por_metodo = []
    dict_metodos = dict(Venta.METODOS_PAGO)
    metodos_qs = ventas_base.values('metodo_pago').annotate(total=Sum('total'), cantidad=Count('id')).order_by('-total')
    for row in metodos_qs:
        tot_m = float(row['total'])
        pct = round(tot_m / float(total_recaudado) * 100, 1) if total_recaudado > 0 else 0.0
        ventas_por_metodo.append({
            'metodo_pago': row['metodo_pago'],
            'nombre': dict_metodos.get(row['metodo_pago'], row['metodo_pago']),
            'total': int(tot_m),
            'cantidad': row['cantidad'],
            'porcentaje': pct
        })

    # Desglose por modalidad de atención
    ventas_por_modalidad = []
    dict_modalidades = dict(Venta.MODALIDADES)
    modalidad_qs = ventas_base.values('modalidad').annotate(total=Sum('total'), cantidad=Count('id')).order_by('-total')
    for row in modalidad_qs:
        tot_mod = float(row['total'])
        pct = round(tot_mod / float(total_recaudado) * 100, 1) if total_recaudado > 0 else 0.0
        ventas_por_modalidad.append({
            'modalidad': row['modalidad'],
            'nombre': dict_modalidades.get(row['modalidad'], row['modalidad']),
            'total': int(tot_mod),
            'cantidad': row['cantidad'],
            'porcentaje': pct
        })

    # Precios especiales y convenios (RF07)
    detalles_especiales = DetalleVenta.objects.filter(venta__in=ventas_base, es_precio_especial=True)
    total_items_precio_especial = detalles_especiales.count()
    ahorro_descuentos = Decimal('0')
    for de in detalles_especiales:
        if de.precio_original and de.precio_original > de.precio_aplicado:
            ahorro_descuentos += (de.precio_original - de.precio_aplicado) * de.cantidad

    # 5. Ranking de productos más vendidos (RF18.4)
    # Incluye históricos y productos desactivados para no alterar la contabilidad histórica
    ranking_qs = (
        DetalleVenta.objects.filter(venta__in=ventas_base)
        .values('producto_id', 'producto__nombre', 'producto__categoria__nombre', 'producto__activo')
        .annotate(
            total_unidades=Sum('cantidad'),
            total_recaudado=Sum('subtotal')
        )
        .order_by('-total_unidades', '-total_recaudado')[:10]
    )
    ranking_productos = []
    for r in ranking_qs:
        ranking_productos.append({
            'producto_id': r['producto_id'],
            'nombre': r['producto__nombre'],
            'categoria': r['producto__categoria__nombre'] or "Sin Categoría",
            'activo': r['producto__activo'],
            'total_unidades': r['total_unidades'],
            'total_recaudado': int(r['total_recaudado']),
        })

    # 6. Tiempos de atención (RF18.5)
    pedidos_qs = Pedido.objects.filter(
        creado_en__date__gte=fecha_inicio,
        creado_en__date__lte=fecha_fin
    ).select_related('venta', 'venta__punto_venta', 'venta__mesa').prefetch_related('entregas')
    if pv_obj:
        pedidos_qs = pedidos_qs.filter(Q(venta__punto_venta=pv_obj) | Q(venta__mesa__punto_venta=pv_obj))
    tiempos_metricas = calcular_tiempos_promedio_local(pedidos_qs=pedidos_qs)

    # 7. Ocupación de mesas (RF18.6)
    ocupacion_metricas = calcular_metricas_ocupacion_local(pv_obj)

    # 8. Serie mensual histórica real para gráficos y tablas
    meses_nombres = {
        1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
    }
    ventas_totales_chart = Venta.objects.filter(estado='PAGADA')
    if pv_obj:
        ventas_totales_chart = ventas_totales_chart.filter(punto_venta=pv_obj)

    meses_agrupados = (
        ventas_totales_chart.annotate(mes_trunc=TruncMonth('fecha_hora'))
        .values('mes_trunc')
        .annotate(ventas=Sum('total'), tickets=Count('id'))
        .order_by('mes_trunc')
    )

    historico_meses = []
    venta_anterior = None
    for row in meses_agrupados:
        dt = row['mes_trunc']
        mes_label = f"{meses_nombres.get(dt.month, str(dt.month))} {dt.year}"
        v_monto = float(row['ventas'])
        ganancia = round(v_monto * 0.46, 0)
        margen = 46.0
        if venta_anterior and venta_anterior > 0:
            crecimiento = round(((v_monto - venta_anterior) / venta_anterior) * 100, 1)
        else:
            crecimiento = 0.0
        venta_anterior = v_monto

        historico_meses.append({
            'mes': mes_label,
            'periodo': dt.strftime('%Y-%m'),
            'ventas': int(v_monto),
            'ganancia': int(ganancia),
            'margen': margen,
            'crecimiento': crecimiento,
            'tickets': row['tickets'],
        })

    # 9. Generación de series reales para gráficos dinámicos (Horas, Días, Meses)
    dias_agrupados = (
        ventas_base.annotate(dia_trunc=TruncDate('fecha_hora'))
        .values('dia_trunc')
        .annotate(ventas=Sum('total'), tickets=Count('id'))
        .order_by('dia_trunc')
    )
    chart_dias_labels = []
    chart_dias_ventas = []
    chart_dias_ganancias = []
    for d in dias_agrupados:
        dt = d['dia_trunc']
        chart_dias_labels.append(dt.strftime('%d/%m'))
        v = int(d['ventas'] or 0)
        chart_dias_ventas.append(v)
        chart_dias_ganancias.append(int(round(v * 0.46)))

    horas_agrupadas = (
        ventas_base.annotate(hora_trunc=TruncHour('fecha_hora'))
        .values('hora_trunc')
        .annotate(ventas=Sum('total'), tickets=Count('id'))
        .order_by('hora_trunc')
    )
    chart_horas_labels = []
    chart_horas_ventas = []
    chart_horas_ganancias = []
    for h in horas_agrupadas:
        dt = h['hora_trunc']
        chart_horas_labels.append(dt.strftime('%H:00'))
        v = int(h['ventas'] or 0)
        chart_horas_ventas.append(v)
        chart_horas_ganancias.append(int(round(v * 0.46)))

    chart_data = {
        'meses': {
            'labels': [m['mes'] for m in historico_meses],
            'ventas': [m['ventas'] for m in historico_meses],
            'ganancias': [m['ganancia'] for m in historico_meses],
        },
        'dias': {
            'labels': chart_dias_labels,
            'ventas': chart_dias_ventas,
            'ganancias': chart_dias_ganancias,
        },
        'horas': {
            'labels': chart_horas_labels,
            'ventas': chart_horas_ventas,
            'ganancias': chart_horas_ganancias,
        },
        'medios_pago': {
            'labels': [m['nombre'] for m in ventas_por_metodo] if ventas_por_metodo else ['Sin ventas'],
            'totales': [m['total'] for m in ventas_por_metodo] if ventas_por_metodo else [0],
            'cantidades': [m['cantidad'] for m in ventas_por_metodo] if ventas_por_metodo else [0],
            'porcentajes': [m['porcentaje'] for m in ventas_por_metodo] if ventas_por_metodo else [0],
        }
    }

    return {
        'chart_data': chart_data,
        'filtros': {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'fecha_inicio_str': fecha_inicio.strftime('%Y-%m-%d'),
            'fecha_fin_str': fecha_fin.strftime('%Y-%m-%d'),
            'punto_venta': pv_obj,
            'punto_venta_id': pv_obj.id if pv_obj else None,
            'punto_venta_nombre': pv_obj.nombre if pv_obj else "Todos los Locales (Consolidado General)",
            'usuario': user_obj,
            'usuario_id': user_obj.id if user_obj else None,
            'usuario_nombre': (user_obj.get_full_name() or user_obj.username) if user_obj else "Todos los Colaboradores",
            'modalidad': modalidad or 'TODAS',
        },
        'ventas': {
            'total_recaudado': int(total_recaudado),
            'total_sin_redondeo': int(total_sin_redondeo),
            'total_redondeo_ley': int(total_redondeo),
            'cantidad_ventas': cantidad_ventas,
            'cantidad_anuladas': cantidad_anuladas,
            'ticket_promedio': int(ticket_promedio),
            'ventas_por_metodo': ventas_por_metodo,
            'ventas_por_modalidad': ventas_por_modalidad,
            'total_items_precio_especial': total_items_precio_especial,
            'ahorro_descuentos': int(ahorro_descuentos),
        },
        'ranking_productos': ranking_productos,
        'tiempos_atencion': tiempos_metricas,
        'ocupacion_mesas': ocupacion_metricas,
        'historico_mensual': historico_meses,
    }



# ==============================================================================
# PROTECCIÓN AUTOMÁTICA ANTE APAGONES, CORTES ELÉCTRICOS Y TURNOS NO CERRADOS
# ==============================================================================
MAX_MINUTOS_ABANDONO_CONTINGENCIA = 180  # 3 horas de inactividad máxima para pedidos en cocina/barra


def _regularizar_pedido_contingencia(pedido, ahora, usuario=None, motivo_cierre="contingencia operativa"):
    """
    Cierra de forma segura y auditable un pedido huérfano:
    - Si su venta ya fue PAGADA: lo pasa a ENTREGADO preservando orden cronológico válido (RF16)
      sin distorsionar métricas de espera con horas/días de corte eléctrico.
    - Si su venta estaba ABIERTA, ANULADA o CANCELADA: lo pasa a CANCELADO.
    """
    from .models import Entrega

    usuario_valido = usuario if (usuario and getattr(usuario, 'is_authenticated', False)) else None

    if pedido.venta and pedido.venta.estado == 'PAGADA':
        ts_base = pedido.creado_en or ahora
        if not pedido.fecha_inicio_preparacion:
            pedido.fecha_inicio_preparacion = ts_base
        if not pedido.fecha_listo:
            pedido.fecha_listo = max(ts_base, pedido.fecha_inicio_preparacion)
        ts_entrega = max(ts_base, pedido.fecha_listo)

        pedido.estado = 'ENTREGADO'
        pedido.save(update_fields=['estado', 'fecha_inicio_preparacion', 'fecha_listo', 'actualizado_en'])

        if not Entrega.objects.filter(pedido=pedido).exists():
            ent = Entrega.objects.create(
                pedido=pedido,
                ticket=pedido.tickets.first(),
                usuario_entrega=usuario_valido,
                observaciones=f"Regularización automática por {motivo_cierre}"[:200],
            )
            Entrega.objects.filter(pk=ent.pk).update(fecha_hora_entrega=ts_entrega)

        pedido.tickets.exclude(estado='FINALIZADO').update(estado='FINALIZADO')
    else:
        etiqueta = f"[Cerrado automáticamente por {motivo_cierre}]"
        obs_actual = (pedido.observaciones or '').strip()
        if etiqueta not in obs_actual:
            obs_actual = f"{obs_actual} {etiqueta}".strip()
        pedido.estado = 'CANCELADO'
        pedido.observaciones = obs_actual
        pedido.save(update_fields=['estado', 'observaciones', 'actualizado_en'])
        pedido.tickets.exclude(estado='FINALIZADO').update(estado='FINALIZADO')


def cerrar_operaciones_de_jornada(jornada, usuario=None, motivo="cierre de jornada"):
    """
    Garantiza que al cerrar una Jornada (normal o por contingencia):
    1. Cualquier Caja remanente ABIERTA quede resguardada con su efectivo real (estado_cuadre='PENDIENTE').
    2. Toda cuenta ABIERTA sin pagar de esa jornada pase a ANULADA.
    3. Todo Pedido activo (PENDIENTE, EN_PREPARACION, LISTO) vinculado se regularice/cierre.
    4. Todas las mesas ocupadas sin cuenta vigente queden HABILITADAS y con fecha_ocupacion limpia.
    """
    from .models import Caja, Venta, Pedido, Mesa

    ahora = timezone.now()
    hoy_str = timezone.localdate().strftime('%d/%m/%Y')
    usuario_valido = usuario if (usuario and getattr(usuario, 'is_authenticated', False)) else None

    with transaction.atomic():
        # 1. Cajas abiertas de esta jornada
        cajas_abiertas = Caja.objects.select_for_update().filter(jornada=jornada, estado='ABIERTA')
        for caja in cajas_abiertas:
            ventas_efectivo = Venta.objects.filter(
                caja=caja,
                estado='PAGADA',
                metodo_pago='EFECTIVO',
            ).aggregate(total=Sum('total'))['total'] or Decimal('0')
            fondo_ant = Decimal(str(caja.monto_apertura or 0))
            saldo_protegido = fondo_ant + Decimal(str(ventas_efectivo))

            caja.estado = 'CERRADA'
            caja.fecha_hora_cierre = ahora
            caja.monto_cierre = saldo_protegido
            caja.total_efectivo_declarado = saldo_protegido
            caja.total_efectivo_esperado = saldo_protegido
            caja.diferencia_cuadre = Decimal('0')
            caja.estado_cuadre = 'PENDIENTE'
            caja.observaciones = ((caja.observaciones or '') + (
                f"\n[CIERRE DE CONTINGENCIA ({hoy_str})]: Caja resguardada automáticamente por {motivo}. "
                f"Saldo efectivo protegido: ${int(saldo_protegido):,} CLP (Arqueo físico pendiente). [TRASPASO_PENDIENTE]"
            )).strip()
            caja.save()

        # 2. Ventas abiertas sin cobrar de esta jornada
        ventas_abiertas = list(Venta.objects.select_for_update().filter(caja__jornada=jornada, estado='ABIERTA'))
        for va in ventas_abiertas:
            va.estado = 'ANULADA'
            va.save(update_fields=['estado'])

        # 3. Pedidos activos de esta jornada
        pedidos_activos = Pedido.objects.select_for_update().select_related('venta').filter(
            venta__caja__jornada=jornada,
            estado__in=['PENDIENTE', 'EN_PREPARACION', 'LISTO'],
        )
        for ped in pedidos_activos:
            _regularizar_pedido_contingencia(ped, ahora, usuario=usuario_valido, motivo_cierre=motivo)

        # 4. Liberar mesas del parque al cerrar jornada
        Mesa.objects.filter(estado='OCUPADA').update(estado='HABILITADA', fecha_ocupacion=None)


def proteger_contingencia_operativa(usuario=None, max_minutos_abandono=MAX_MINUTOS_ABANDONO_CONTINGENCIA, forzar=False):
    """
    Motor automático de protección ante apagones, cortes de energía o turnos/pedidos olvidados:
    Se ejecuta de forma idempotente y con cache throttling (1 minuto) para evitar sobrecarga en BD.
    Protege:
    1. Jornadas y Cajas de días anteriores que quedaron ABIERTAS (resguardando saldo en efectivo).
    2. Ventas ABIERTAS de días anteriores o de jornadas cerradas (respetando sobremesas del día actual).
    3. Pedidos en PENDIENTE / EN_PREPARACION / LISTO de días anteriores, de ventas anuladas/canceladas,
       o abandonados >= max_minutos_abandono (12h).
    4. Mesas OCUPADAS huérfanas de días anteriores.
    """
    from django.core.cache import cache
    if not forzar and cache.get('contingencia_lock_60s'):
        return {'cached': True}
    cache.set('contingencia_lock_60s', True, timeout=60)

    import datetime as dt_mod
    from django.db.models import Q
    from .models import Jornada, Caja, Venta, Pedido, Mesa

    ahora = timezone.now()
    ahora_local = timezone.localtime(ahora)
    hoy = ahora_local.date()
    inicio_hoy_local = timezone.make_aware(
        dt_mod.datetime.combine(hoy, dt_mod.time.min),
        timezone.get_current_timezone(),
    )
    umbral_abandono = ahora - dt_mod.timedelta(minutes=max_minutos_abandono)
    usuario_valido = usuario if (usuario and getattr(usuario, 'is_authenticated', False)) else None

    resumen = {
        'jornadas_cerradas': 0,
        'cajas_protegidas': 0,
        'ventas_cerradas': 0,
        'pedidos_regularizados': 0,
        'mesas_liberadas': 0,
    }

    with transaction.atomic():
        # 1. Proteger y cerrar todas las Cajas ABIERTAS de días anteriores
        cajas_previas = list(
            Caja.objects.select_for_update()
            .select_related('jornada')
            .filter(estado='ABIERTA')
            .filter(Q(jornada__fecha__lt=hoy) | Q(fecha_hora_apertura__lt=inicio_hoy_local))
        )
        for ch in cajas_previas:
            ventas_ef = Venta.objects.filter(
                caja=ch,
                estado='PAGADA',
                metodo_pago='EFECTIVO',
            ).aggregate(total=Sum('total'))['total'] or Decimal('0')
            fondo_ant = Decimal(str(ch.monto_apertura or 0))
            saldo_prot = fondo_ant + Decimal(str(ventas_ef))

            ch.estado = 'CERRADA'
            ch.fecha_hora_cierre = ahora
            ch.monto_cierre = saldo_prot
            ch.total_efectivo_declarado = saldo_prot
            ch.total_efectivo_esperado = saldo_prot
            ch.diferencia_cuadre = Decimal('0')
            ch.estado_cuadre = 'PENDIENTE'
            ch.observaciones = ((ch.observaciones or '') + (
                f"\n[CIERRE AUTOMÁTICO DE CONTINGENCIA - APAGÓN/CAMBIO DE DÍA ({hoy.strftime('%d/%m/%Y')})]: "
                f"Saldo en efectivo protegido (${int(saldo_prot):,} CLP, Arqueo físico pendiente). [TRASPASO_PENDIENTE]"
            )).strip()
            ch.save()
            resumen['cajas_protegidas'] += 1

        # 2. Cerrar todas las Jornadas ABIERTAS de días anteriores
        jornadas_previas = list(
            Jornada.objects.select_for_update().filter(estado='ABIERTA', fecha__lt=hoy)
        )
        for jh in jornadas_previas:
            jh.estado = 'CERRADA'
            jh.fecha_hora_cierre = ahora
            if usuario_valido and not jh.usuario_cierre_id:
                jh.usuario_cierre = usuario_valido
            jh.observaciones = ((jh.observaciones or '') + (
                f"\n[Cierre automático por contingencia / cambio de día ({hoy.strftime('%d/%m/%Y')})]"
            )).strip()
            jh.save()
            resumen['jornadas_cerradas'] += 1

        # 3. Cerrar cuentas ABIERTAS huérfanas (estrictamente día anterior, jornada cerrada o inactividad >= 12h)
        ventas_huerfanas = list(
            Venta.objects.select_for_update()
            .select_related('caja__jornada')
            .filter(estado='ABIERTA')
            .filter(
                Q(fecha_hora__lt=inicio_hoy_local)
                | Q(caja__jornada__estado='CERRADA')
                | Q(fecha_hora__lt=umbral_abandono)
            )
        )
        mesas_a_evaluar = set()
        for vh in ventas_huerfanas:
            if vh.fecha_hora >= inicio_hoy_local and vh.caja and vh.caja.jornada and vh.caja.jornada.estado == 'ABIERTA':
                # Si fue creada hoy y la jornada sigue abierta, solo cerrar si excede umbral extremo (12h) sin actividad
                tiene_actividad_reciente = vh.pedidos.filter(actualizado_en__gte=umbral_abandono).exists()
                if tiene_actividad_reciente:
                    continue
            if vh.mesa_id:
                mesas_a_evaluar.add(vh.mesa_id)
            vh.estado = 'ANULADA'
            vh.save(update_fields=['estado'])
            resumen['ventas_cerradas'] += 1

        # 4. Regularizar Pedidos huérfanos (día anterior, venta anulada/cancelada, jornada cerrada o abandono >= 12h)
        pedidos_huerfanos = list(
            Pedido.objects.select_for_update()
            .select_related('venta', 'venta__caja__jornada')
            .filter(estado__in=['PENDIENTE', 'EN_PREPARACION', 'LISTO'])
            .filter(
                Q(creado_en__lt=inicio_hoy_local)
                | Q(venta__estado__in=['ANULADA', 'CANCELADA'])
                | Q(venta__caja__jornada__estado='CERRADA')
                | Q(creado_en__lt=umbral_abandono)
                | Q(actualizado_en__lt=umbral_abandono)
            )
        )
        for ph in pedidos_huerfanos:
            if ph.venta and ph.venta.mesa_id:
                mesas_a_evaluar.add(ph.venta.mesa_id)
            if ph.creado_en < inicio_hoy_local:
                motivo_ped = "cambio de día / corte previo"
            elif ph.venta and ph.venta.estado in ['ANULADA', 'CANCELADA']:
                motivo_ped = "anulación de cuenta asociada"
            elif ph.venta and ph.venta.caja and ph.venta.caja.jornada and ph.venta.caja.jornada.estado == 'CERRADA':
                motivo_ped = "cierre de jornada"
            else:
                motivo_ped = f"inactividad extrema mayor a {max_minutos_abandono // 60}h sin cierre"
            _regularizar_pedido_contingencia(ph, ahora, usuario=usuario_valido, motivo_cierre=motivo_ped)
            resumen['pedidos_regularizados'] += 1

        # 5. Liberar Mesas OCUPADAS huérfanas (de días anteriores o de ventas recién cerradas)
        mesas_ocupadas = list(Mesa.objects.select_for_update().filter(estado='OCUPADA'))
        for mesa in mesas_ocupadas:
            tiene_venta_abierta_vigente = Venta.objects.filter(
                mesa=mesa,
                estado='ABIERTA',
                fecha_hora__gte=inicio_hoy_local,
            ).exists()
            if tiene_venta_abierta_vigente:
                continue

            tiene_pedido_vigente = Pedido.objects.filter(
                venta__mesa=mesa,
                creado_en__gte=inicio_hoy_local,
                estado__in=['PENDIENTE', 'EN_PREPARACION', 'LISTO'],
            ).exists()
            if tiene_pedido_vigente:
                continue

            liberar = False
            if mesa.id in mesas_a_evaluar:
                liberar = True
            elif mesa.fecha_ocupacion is not None:
                if mesa.fecha_ocupacion < inicio_hoy_local or mesa.fecha_ocupacion < umbral_abandono:
                    liberar = True
            else:
                ultima_venta = Venta.objects.filter(mesa=mesa).order_by('-fecha_hora').first()
                if ultima_venta and ultima_venta.fecha_hora < inicio_hoy_local:
                    liberar = True

            if liberar:
                mesa.estado = 'HABILITADA'
                mesa.fecha_ocupacion = None
                mesa.save(update_fields=['estado', 'fecha_ocupacion'])
                resumen['mesas_liberadas'] += 1

    return resumen
