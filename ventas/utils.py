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


def emitir_tickets_comanda(pedido, usuario_emisor=None):
    """
    Clasifica y emite tickets de producción (Cocina y Barra) para una comanda o ronda (RF08.1, RF08.2, RF08.3).
    - Cero Desperdicio de Papel: Solo genera ticket si hay productos asignados a ese destino.
    - Incrementalidad (RF08.5): Solo toma en cuenta los productos del pedido en curso (ronda actual).
    Retorna un diccionario con los tickets emitidos.
    """
    from .models import Ticket

    detalles = list(pedido.detalles.select_related('producto', 'producto__categoria').all())
    if not detalles:
        raise ValidationError("El pedido no contiene productos para emitir comanda.")

    items_cocina = [d for d in detalles if d.producto.get_destino_operativo() == 'COCINA']
    items_barra = [d for d in detalles if d.producto.get_destino_operativo() == 'BARRA']

    tickets_creados = []

    # 1. Ticket Cocina Caliente (solo si hay ítems de cocina)
    if items_cocina:
        contenido_coc = generar_contenido_ticket_cocina(pedido, items_cocina)
        ticket_coc, _ = Ticket.objects.update_or_create(
            pedido=pedido,
            tipo_destino='COCINA',
            defaults={
                'venta': pedido.venta,
                'codigo': f"COM-COC-{pedido.id:04d}",
                'estado': 'EMITIDO',
                'contenido_impresion': contenido_coc
            }
        )
        tickets_creados.append(ticket_coc)

    # 2. Ticket Barra / Cafetería (solo si hay ítems de barra)
    if items_barra:
        contenido_bar = generar_contenido_ticket_barra(pedido, items_barra)
        ticket_bar, _ = Ticket.objects.update_or_create(
            pedido=pedido,
            tipo_destino='BARRA',
            defaults={
                'venta': pedido.venta,
                'codigo': f"COM-BAR-{pedido.id:04d}",
                'estado': 'EMITIDO',
                'contenido_impresion': contenido_bar
            }
        )
        tickets_creados.append(ticket_bar)

    return {
        'tickets': tickets_creados,
        'tiene_cocina': bool(items_cocina),
        'tiene_barra': bool(items_barra),
        'total_tickets': len(tickets_creados)
    }


def emitir_comprobante_venta(venta, usuario_emisor=None):
    """
    Genera el comprobante de cliente / boleta de venta (RF08.4).
    """
    from .models import Ticket

    contenido = generar_contenido_comprobante_venta(venta)
    pedido_asoc = venta.pedidos.order_by('id').first()

    ticket_comp, _ = Ticket.objects.update_or_create(
        venta=venta,
        tipo_destino='COMPROBANTE',
        defaults={
            'pedido': pedido_asoc,
            'codigo': f"TKT-VEN-{venta.id:05d}",
            'estado': 'FINALIZADO',
            'contenido_impresion': contenido
        }
    )
    return ticket_comp


def reimprimir_ticket(ticket, usuario_solicitante=None):
    """
    Reimprime un ticket existente de forma trazable (RF08.6).
    - Marca es_reimpresion=True e incrementa numero_reimpresiones.
    - Registra usuario_solicitante y marca de tiempo.
    - NO genera una venta nueva ni duplica detalles contables.
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
    return ticket

