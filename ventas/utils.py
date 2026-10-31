"""
Utilidades y Lógica Financiera para Parque Safari (Venta_safari).
Normativas Oficiales:
- Ley N° 20.956 (Regla de Redondeo en Efectivo del Banco Central de Chile).
- Subproceso de Cuadratura y Arqueo de Cajas (Protocolo Oficial de Cierre).
- Soporte para Eventos Promocionales con monedas de $1 y $5 pesos.
"""

from decimal import Decimal
from django.db.models import Sum


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
