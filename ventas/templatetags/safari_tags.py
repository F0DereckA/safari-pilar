from decimal import Decimal
from django import template
from ventas.security import enmascarar_rut as _mask_rut, enmascarar_email as _mask_email

register = template.Library()


@register.filter(name='pesos')
def pesos(valor):
    """
    Formatea cualquier número a pesos chilenos completos con puntos de miles.
    Ejemplo: 25400 -> "25.400", 1000000 -> "1.000.000".
    Nunca abrevia con 'k' ni 'M'.
    """
    if valor is None or valor == '':
        return '0'
    try:
        if isinstance(valor, (int, float, Decimal)):
            val = int(round(float(valor)))
        else:
            cleaned = str(valor).replace('$', '').replace('.', '').replace(',', '').strip()
            val = int(round(float(cleaned)))
        return f"{val:,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(valor)


@register.filter(name='pesos_clp')
def pesos_clp(valor):
    """
    Retorna el valor con signo peso y formato chileno completo.
    Ejemplo: 25400 -> "$25.400", 1000000 -> "$1.000.000".
    """
    return f"${pesos(valor)}"


@register.filter(name='enmascarar_rut')
def enmascarar_rut_filter(valor):
    """Enmascara RUT para vistas administrativas dejando visibles los últimos dígitos."""
    texto = str(valor or '').strip()
    if not texto or texto.lower() in ('sin rut', 's/rut', 's/r', 'sin registrar'):
        return texto or 'Sin RUT'
    return _mask_rut(texto)


@register.filter(name='enmascarar_email')
def enmascarar_email_filter(valor):
    """Enmascara correo electrónico para minimizar exposición PII en listados."""
    texto = str(valor or '').strip()
    if not texto or '@' not in texto:
        return texto or 'Sin email'
    return _mask_email(texto)


@register.filter(name='enmascarar_telefono')
def enmascarar_telefono_filter(valor):
    """Enmascara dígitos centrales de teléfonos en listados administrativos."""
    texto = str(valor or '').strip()
    if not texto:
        return 'No informado'
    if len(texto) <= 4:
        return '*' * len(texto)
    return f"{texto[:3]}****{texto[-3:]}"
