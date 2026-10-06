from decimal import Decimal
from django import template

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
