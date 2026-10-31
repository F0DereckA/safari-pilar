import re
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.utils import timezone


def validar_complejidad_clave(password: str) -> tuple[bool, str]:
    """
    Regla Global de Seguridad de Contraseñas (ISO/IEC 27400 y políticas internas):
    - Mínimo 8 caracteres de longitud.
    - Al menos una letra mayúscula [A-Z].
    - Al menos una letra minúscula [a-z].
    - Al menos un dígito [0-9].
    - Al menos un símbolo o carácter especial.
    Retorna (es_valida, mensaje_error).
    """
    if not password or len(password) < 8:
        return False, "La contraseña debe tener un mínimo de 8 caracteres."
    
    if not re.search(r'[A-Z]', password):
        return False, "La contraseña debe incluir al menos una letra mayúscula (A-Z)."
        
    if not re.search(r'[a-z]', password):
        return False, "La contraseña debe incluir al menos una letra minúscula (a-z)."
        
    if not re.search(r'[0-9]', password):
        return False, "La contraseña debe incluir al menos un dígito numérico (0-9)."
        
    if not re.search(r'[!@#$%^&*(),.?":{}|<>\-_+=\[\]\\/`~;]', password):
        return False, "La contraseña debe incluir al menos un símbolo o carácter especial (!@#$%^&* etc.)."
        
    return True, ""


class SafariPasswordValidator:
    """Validador oficial de contraseñas de Django para Parque Safari"""
    def validate(self, password, user=None):
        es_valida, mensaje = validar_complejidad_clave(password)
        if not es_valida:
            raise ValidationError(
                _(mensaje),
                code='password_insufficient_complexity',
            )

    def get_help_text(self):
        return _(
            "Tu contraseña debe tener al menos 8 caracteres y contener una combinación "
            "de mayúsculas, minúsculas, números y caracteres especiales."
        )
