import base64
import hashlib
import hmac
import ipaddress
import re
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.cache import cache
from django.utils.html import strip_tags


VERSION_POLITICA_ACTUAL = '1.0-academica'
VERSION_TERMINOS_ACTUAL = '1.0-academica'

RETENCION_DATOS_DIAS = {
    'logs_seguridad_ip': 30,
    'consentimientos_auditoria': 365,
    'operacion_academica_simulada': 180,
    'cuentas_inactivas_anonimizacion': 180,
}

USUARIOS_DEMO_EVALUACION = frozenset({'rgomez', 'cvalenzuela', 'dsilva', 'eparedes'})


def obtener_clave_maestra_entorno():
    """Obtiene la clave criptográfica activa del entorno sin exponer valores estáticos débiles."""
    clave = getattr(settings, 'SECRET_KEY', None)
    if not clave:
        raise RuntimeError("SECRET_KEY no configurada en el entorno de ejecución.")
    return str(clave)


def hash_dato_sensible(valor, contexto='safari-pilar'):
    """Genera un hash SHA-256 con sal de entorno para minimizar PII en logs y auditoría (IP, UA, identificadores)."""
    if valor is None:
        return ''
    texto = str(valor).strip()
    if not texto:
        return ''
    sal = obtener_clave_maestra_entorno().encode('utf-8')
    mensaje = f"{contexto}:{texto}".encode('utf-8')
    return hmac.new(sal, mensaje, hashlib.sha256).hexdigest()


@lru_cache(maxsize=8)
def _construir_fernet_desde_clave(semilla_clave):
    digest = hashlib.sha256(semilla_clave.encode('utf-8')).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def obtener_fernet_cipher():
    """Construye cifrador simétrico Fernet (AES-128-CBC + HMAC-SHA256) desde variable dedicada o SECRET_KEY."""
    clave_pii = getattr(settings, 'SAFARI_PII_KEY', '') or obtener_clave_maestra_entorno()
    return _construir_fernet_desde_clave(f"safari-pii::{clave_pii}")


def cifrar_dato_pii(texto):
    """Cifra un dato sensible o snapshot antes de persistirlo o exportarlo fuera del núcleo."""
    if not texto:
        return ''
    cipher = obtener_fernet_cipher()
    return cipher.encrypt(str(texto).encode('utf-8')).decode('utf-8')


def descifrar_dato_pii(token):
    """Descifra un token generado por `cifrar_dato_pii` verificando su firma autenticada."""
    if not token:
        return ''
    cipher = obtener_fernet_cipher()
    try:
        return cipher.decrypt(str(token).encode('utf-8')).decode('utf-8')
    except (InvalidToken, ValueError, TypeError):
        return ''


def enmascarar_rut(rut):
    """Oculta dígitos intermedios de un RUT para visualización minimizada en resúmenes."""
    texto = str(rut or '').strip()
    if len(texto) <= 4:
        return '****' if texto else 'No registrado'
    return f"•••{texto[-4:]}"


def enmascarar_email(email):
    """Enmascara correo institucional manteniendo contexto mínimo legible."""
    texto = str(email or '').strip()
    if '@' not in texto:
        return '***' if texto else 'No registrado'
    local, dominio = texto.split('@', 1)
    prefijo = local[:2] if len(local) >= 2 else local[:1]
    return f"{prefijo}***@{dominio}"


def firmar_registro_consentimiento(username, version_politica, version_terminos, acepto_privacidad, acepto_terminos, acepto_cookies_analisis, timestamp_iso):
    """Genera firma HMAC-SHA256 verificable para auditar quién aceptó qué política y cuándo."""
    payload = "|".join([
        str(username or '').strip().lower(),
        str(version_politica or ''),
        str(version_terminos or ''),
        '1' if acepto_privacidad else '0',
        '1' if acepto_terminos else '0',
        '1' if acepto_cookies_analisis else '0',
        str(timestamp_iso or ''),
    ]).encode('utf-8')
    clave = obtener_clave_maestra_entorno().encode('utf-8')
    return hmac.new(clave, payload, hashlib.sha256).hexdigest()


def verificar_integridad_consentimiento(registro):
    """Valida matemáticamente que un registro de consentimiento no haya sido alterado."""
    if not registro or not getattr(registro, 'hash_integridad', ''):
        return False
    esperado = firmar_registro_consentimiento(
        username=registro.username_snapshot,
        version_politica=registro.version_politica,
        version_terminos=registro.version_terminos,
        acepto_privacidad=registro.acepto_privacidad,
        acepto_terminos=registro.acepto_terminos,
        acepto_cookies_analisis=registro.acepto_cookies_analisis,
        timestamp_iso=registro.aceptado_en.isoformat() if registro.aceptado_en else '',
    )
    return hmac.compare_digest(esperado, registro.hash_integridad)


def _normalizar_ip_valida(valor):
    """Valida sintácticamente una dirección IPv4/IPv6 (con o sin puerto) y retorna la IP limpia."""
    candidato = str(valor or '').strip()
    if not candidato:
        return ''
    if candidato.startswith('['):
        candidato = candidato[1:].split(']', 1)[0]
    elif candidato.count(':') == 1 and '.' in candidato:
        candidato = candidato.split(':', 1)[0]
    try:
        return str(ipaddress.ip_address(candidato))
    except ValueError:
        return ''


def obtener_ip_segura(request):
    """
    Extrae la IP cliente de forma resistente a spoofing de cabeceras.
    Solo confía en `X-Forwarded-For` cuando `SAFARI_TRUST_PROXY=True` (detrás de Nginx/PythonAnywhere),
    y en caso contrario utiliza directamente `REMOTE_ADDR`.
    """
    if getattr(settings, 'SAFARI_TRUST_PROXY', False):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if x_forwarded_for:
            # Toma el último salto cliente confiable validado por proxy inverso si existen múltiples cabeceras
            partes = [p.strip() for p in x_forwarded_for.split(',') if p.strip()]
            for candidato in reversed(partes):
                ip_limpia = _normalizar_ip_valida(candidato)
                if ip_limpia:
                    return ip_limpia
    ip_remote = _normalizar_ip_valida(request.META.get('REMOTE_ADDR', ''))
    return ip_remote or '0.0.0.0'


def verificar_rate_limit_ip(request, namespace, max_requests, window_seconds, key_extra=''):
    """
    Control de tasa (Rate Limiting) por IP y ruta en caché segura.
    Retorna `(permitido: bool, retry_after: int, restantes: int)`.
    """
    ip = obtener_ip_segura(request)
    ip_hash = hashlib.sha256(f"{namespace}:{ip}:{key_extra}".encode('utf-8')).hexdigest()[:24]
    cache_key = f"safari_rl:{namespace}:{ip_hash}"

    actual = cache.get(cache_key)
    if actual is None:
        cache.set(cache_key, 1, timeout=window_seconds)
        return True, 0, max(0, max_requests - 1)

    if int(actual) >= int(max_requests):
        return False, int(window_seconds), 0

    try:
        nuevo_valor = cache.incr(cache_key)
    except ValueError:
        nuevo_valor = int(actual) + 1
        cache.set(cache_key, nuevo_valor, timeout=window_seconds)

    return True, 0, max(0, max_requests - int(nuevo_valor))


def limpiar_texto_seguro(valor, max_length=150, quitar_html=True):
    """Sanitiza entradas de texto en servidor contra HTML/XSS y caracteres de control."""
    if valor is None:
        return ''
    texto = str(valor)
    if quitar_html:
        texto = strip_tags(texto)
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', texto)
    texto = re.sub(r'[<>]', '', texto)
    return texto.strip()[:max_length]


def validar_acceso_rls_local(request, punto_venta_obj):
    """
    Row-Level Security (RLS) por usuario/local:
    - ADMINISTRADOR (o superuser activo) puede supervisar cualquier local activo.
    - CAJERO / MESERO / COCINERO solo pueden consultar o mutar recursos pertenecientes a su local asignado.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfil', None)
    if not perfil or not perfil.activo:
        return False
    if perfil.rol == 'ADMINISTRADOR':
        return True
    if punto_venta_obj is None:
        return False
    if perfil.punto_venta_actual_id is None:
        return False
    punto_id = getattr(punto_venta_obj, 'id', punto_venta_obj)
    return int(perfil.punto_venta_actual_id) == int(punto_id)


def demo_mode_activo():
    """Indica si el acceso rápido de evaluación académica sin exposición de clave está habilitado."""
    return bool(getattr(settings, 'SAFARI_DEMO_MODE', False))


def hash_alias_navegador(identificador):
    """
    Huella determinística corta y no reversible (FNV-1a 32-bit con versión de política)
    para reconocer en el navegador si una cuenta ya aceptó las políticas vigentes sin guardar PII en cookies.
    """
    valor = str(identificador or '').strip().lower()
    if not valor:
        return ''
    texto = f"safari-ack:{VERSION_POLITICA_ACTUAL}:{VERSION_TERMINOS_ACTUAL}:{valor}"
    h = 0x811C9DC5
    for ch in texto.encode('utf-8'):
        h ^= ch
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def usuario_tiene_consentimiento_vigente(user):
    """Indica si el usuario ya aceptó y auditó la versión actual de Privacidad y Términos."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    perfil = getattr(user, 'perfil', None)
    if perfil is not None:
        return bool(perfil.consentimiento_vigente())
    from ventas.models import RegistroConsentimiento
    return RegistroConsentimiento.objects.filter(
        usuario=user,
        acepto_privacidad=True,
        acepto_terminos=True,
        version_politica=VERSION_POLITICA_ACTUAL,
        version_terminos=VERSION_TERMINOS_ACTUAL,
    ).exists()


def resolver_usuario_demo_eval(username):
    """
    Permite acceso controlado de evaluación académica únicamente cuando `SAFARI_DEMO_MODE=True`
    y solo para usuarios explícitamente aprobados en el sandbox, evitando contraseñas en HTML/JS.
    """
    if not demo_mode_activo():
        return None
    candidato = str(username or '').strip().lower()
    if candidato not in USUARIOS_DEMO_EVALUACION:
        return None
    from django.contrib.auth.models import User
    user = User.objects.filter(username__iexact=candidato, is_active=True).select_related('perfil').first()
    if not user:
        return None
    perfil = getattr(user, 'perfil', None)
    if not perfil or not perfil.activo:
        return None
    return user
