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
