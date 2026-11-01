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


def calcular_redondeo_ley_20956(monto, metodo_pago='EFECTIVO'):
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
    if 0 < monto_int <= 5:
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
    mesa_txt = f"Mesa: {venta.mesa.identificador}" if (venta.modalidad == 'MESA' and venta.mesa) else "Venta Rápida / Mostrador"
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
    mesa_txt = f"Mesa: {venta.mesa.identificador}" if (venta.modalidad == 'MESA' and venta.mesa) else "Venta Rápida / Mostrador"
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
    subtotal_bruto = venta.total_sin_redondeo or subtotal_items
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

    # 4. Transacción atómica e integridad (RF10.5)
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
