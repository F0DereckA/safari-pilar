import json
import re
from urllib.parse import quote, unquote

from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.shortcuts import redirect, render

from ventas.models import (
    Caja,
    PerfilEmpleado,
    RegistroConsentimiento,
    anonimizar_datos_usuario,
    registrar_evento_consentimiento,
)
from ventas.security import (
    RETENCION_DATOS_DIAS,
    VERSION_POLITICA_ACTUAL,
    VERSION_TERMINOS_ACTUAL,
    enmascarar_email,
    enmascarar_rut,
    limpiar_texto_seguro,
    verificar_rate_limit_ip,
)
from ventas.views import obtener_rol_usuario, requiere_rol


COOKIE_PREFS_NAME = 'safari_cookie_prefs'


def _construir_cookie_prefs(analytics_enabled):
    payload = json.dumps(
        {
            'essential': True,
            'analytics': bool(analytics_enabled),
            'v': VERSION_POLITICA_ACTUAL,
        },
        separators=(',', ':'),
    )
    # Codificación RFC-safe (%7B...%7D) para evitar comillas y escapes octales (\054) de SimpleCookie
    return quote(payload, safe='')


def _decodificar_cookie_prefs(raw):
    if not raw:
        return None
    candidatos = [raw]
    try:
        decodificado = unquote(raw)
        if decodificado != raw:
            candidatos.append(decodificado)
    except Exception:
        pass
    for candidato in candidatos:
        texto = str(candidato).strip()
        if len(texto) >= 2 and texto[0] == '"' and texto[-1] == '"':
            texto = texto[1:-1].replace('\\"', '"').replace('\\054', ',')
        try:
            data = json.loads(texto)
            if isinstance(data, dict):
                return data
        except (ValueError, TypeError):
            continue
    return None


def _extraer_cookie_analytics(request):
    data = _decodificar_cookie_prefs(request.COOKIES.get(COOKIE_PREFS_NAME, ''))
    return bool(data.get('analytics', False)) if data else False


def politica_privacidad_view(request):
    """Política de Privacidad académica y realista: qué datos, para qué, con quién y cuánto tiempo se guardan."""
    consentimiento_actual = None
    if request.user.is_authenticated and hasattr(request.user, 'perfil'):
        consentimiento_actual = request.user.perfil.consentimiento_vigente()

    context = {
        'version_politica': VERSION_POLITICA_ACTUAL,
        'version_terminos': VERSION_TERMINOS_ACTUAL,
        'retencion_dias': RETENCION_DATOS_DIAS,
        'consentimiento_actual': consentimiento_actual,
        'analytics_habilitado': _extraer_cookie_analytics(request),
        'es_administrador': request.user.is_authenticated and obtener_rol_usuario(request.user) == 'ADMINISTRADOR',
    }
    return render(request, 'ventas/acceso/politica_privacidad.html', context)


def terminos_condiciones_view(request):
    """Términos y Condiciones de uso académico para el prototipo Venta Safari."""
    context = {
        'version_terminos': VERSION_TERMINOS_ACTUAL,
        'version_politica': VERSION_POLITICA_ACTUAL,
        'retencion_dias': RETENCION_DATOS_DIAS,
        'es_administrador': request.user.is_authenticated and obtener_rol_usuario(request.user) == 'ADMINISTRADOR',
    }
    return render(request, 'ventas/acceso/terminos_condiciones.html', context)


def registrar_consentimiento_view(request):
    """
    Endpoint para registrar consentimiento explícito de Cookies / Privacidad.
    Regla estricta: nada de análisis ni telemetría hasta que la persona acepte explícitamente.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    permitido, retry_after, _ = verificar_rate_limit_ip(
        request,
        namespace='consentimiento_cookies',
        max_requests=30,
        window_seconds=60,
    )
    if not permitido:
        resp_429 = JsonResponse({'ok': False, 'error': 'Demasiadas solicitudes. Intenta en unos segundos.'}, status=429)
        resp_429['Retry-After'] = str(retry_after)
        return resp_429

    es_json = 'application/json' in (request.content_type or '').lower() or request.headers.get('x-requested-with') == 'XMLHttpRequest'
    if es_json and request.body:
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)
        acepto_analisis = bool(payload.get('analytics', False))
        acepto_priv = bool(payload.get('acepto_privacidad', False))
        acepto_term = bool(payload.get('acepto_terminos', False))
        origen = limpiar_texto_seguro(payload.get('origen', 'COOKIE_BANNER'), max_length=30) or 'COOKIE_BANNER'
    else:
        acepto_analisis = request.POST.get('acepto_cookies_analisis') in ('1', 'on', 'true', 'yes')
        acepto_priv = request.POST.get('acepto_privacidad') in ('1', 'on', 'true', 'yes')
        acepto_term = request.POST.get('acepto_terminos') in ('1', 'on', 'true', 'yes')
        origen = 'COOKIE_BANNER'

    if origen not in {'LOGIN_PORTAL', 'MI_PRIVACIDAD', 'COOKIE_BANNER', 'REVOKE_ARCO'}:
        origen = 'COOKIE_BANNER'

    registro = registrar_evento_consentimiento(
        request=request,
        usuario=request.user if request.user.is_authenticated else None,
        origen=origen,
        acepto_privacidad=acepto_priv,
        acepto_terminos=acepto_term,
        acepto_cookies_analisis=acepto_analisis,
    )

    prefs_json = _construir_cookie_prefs(acepto_analisis)
    if es_json:
        response = JsonResponse({
            'ok': True,
            'essential': True,
            'analytics': acepto_analisis,
            'registro_id': registro.id,
            'aceptado_en': registro.aceptado_en.isoformat(),
            'quien': registro.username_snapshot,
        })
    else:
        messages.success(request, "Tus preferencias de cookies fueron guardadas correctamente.")
        response = redirect(request.META.get('HTTP_REFERER') or 'index')

    response.set_cookie(
        COOKIE_PREFS_NAME,
        prefs_json,
        max_age=180 * 86400,
        httponly=False,
        samesite='Lax',
        secure=request.is_secure(),
    )
    return response


@requiere_rol(['ADMINISTRADOR'])
def mi_privacidad_view(request):
    """
    Portal de Autogestión ARCO y Control de Datos Personales.
    Acceso restringido exclusivamente al rol ADMINISTRADOR para evitar que el personal
    operativo consulte o modifique libremente sus fichas personales desde terminales.
    """
    user = request.user
    perfil = getattr(user, 'perfil', None)
    rol_actual = obtener_rol_usuario(user)

    if request.method == 'POST':
        permitido, retry_after, _ = verificar_rate_limit_ip(
            request,
            namespace='mi_privacidad_post',
            max_requests=30,
            window_seconds=60,
        )
        if not permitido:
            messages.error(request, f"Demasiadas modificaciones seguidas. Espera {retry_after}s antes de reintentar.")
            return redirect('mi_privacidad')

        accion = request.POST.get('accion', '').strip()

        if accion == 'rectificar':
            nuevo_nombre = limpiar_texto_seguro(request.POST.get('first_name', ''), max_length=60)
            nuevo_apellido = limpiar_texto_seguro(request.POST.get('last_name', ''), max_length=60)
            nuevo_email = limpiar_texto_seguro(request.POST.get('email', ''), max_length=120)
            nuevo_telefono = limpiar_texto_seguro(request.POST.get('telefono', ''), max_length=20)

            if not nuevo_nombre or not nuevo_apellido:
                messages.error(request, "Nombre y apellido son obligatorios para mantener tu identidad operativa.")
                return redirect('mi_privacidad')

            if nuevo_email:
                try:
                    validate_email(nuevo_email)
                except ValidationError:
                    messages.error(request, "El formato del correo electrónico ingresado no es válido.")
                    return redirect('mi_privacidad')

            if nuevo_telefono and not re.match(r'^[\d\s+\-()]{7,20}$', nuevo_telefono):
                messages.error(request, "El formato del teléfono no es válido (usa solo dígitos, +, espacios o guiones).")
                return redirect('mi_privacidad')

            user.first_name = nuevo_nombre
            user.last_name = nuevo_apellido
            user.email = nuevo_email
            user.save(update_fields=['first_name', 'last_name', 'email'])

            if perfil is not None:
                perfil.telefono = nuevo_telefono
                perfil.save(update_fields=['telefono'])

            messages.success(request, "Tus datos personales fueron rectificados y guardados con validación de servidor.")
            return redirect('mi_privacidad')

        elif accion == 'borrar_opcionales':
            user.email = ''
            user.save(update_fields=['email'])
            if perfil is not None:
                perfil.telefono = ''
                perfil.save(update_fields=['telefono'])
            messages.success(request, "Se eliminaron tus datos opcionales (correo y teléfono) aplicando minimización de datos.")
            return redirect('mi_privacidad')

        elif accion == 'actualizar_consentimiento':
            acepto_priv = request.POST.get('acepto_privacidad') in ('1', 'on', 'true', 'yes')
            acepto_term = request.POST.get('acepto_terminos') in ('1', 'on', 'true', 'yes')
            acepto_analisis = request.POST.get('acepto_cookies_analisis') in ('1', 'on', 'true', 'yes')

            if not (acepto_priv and acepto_term):
                messages.error(request, "Debes marcar explícitamente la casilla de aceptación de Privacidad y Términos para registrar un consentimiento válido.")
                return redirect('mi_privacidad')

            reg = registrar_evento_consentimiento(
                request=request,
                usuario=user,
                origen='MI_PRIVACIDAD',
                acepto_privacidad=True,
                acepto_terminos=True,
                acepto_cookies_analisis=acepto_analisis,
            )
            messages.success(
                request,
                f"Consentimiento actualizado y firmado (Registro #{reg.id}, {reg.aceptado_en:%d/%m/%Y %H:%M}).",
            )
            response = redirect('mi_privacidad')
            response.set_cookie(
                COOKIE_PREFS_NAME,
                _construir_cookie_prefs(acepto_analisis),
                max_age=180 * 86400,
                httponly=False,
                samesite='Lax',
                secure=request.is_secure(),
            )
            return response

        elif accion == 'eliminar_cuenta':
            confirmacion = request.POST.get('confirmacion', '').strip().upper()
            password_actual = request.POST.get('password_confirmacion', '')

            if confirmacion != 'CONFIRMAR':
                messages.error(request, "Para eliminar y anonimizar tus datos debes escribir exactamente la palabra CONFIRMAR.")
                return redirect('mi_privacidad')

            if not password_actual or not user.check_password(password_actual):
                messages.error(request, "Contraseña de confirmación incorrecta.")
                return redirect('mi_privacidad')

            if rol_actual == 'ADMINISTRADOR':
                admins_activos = PerfilEmpleado.objects.filter(rol='ADMINISTRADOR', activo=True).exclude(usuario=user).count()
                if admins_activos == 0:
                    messages.error(
                        request,
                        "Acción bloqueada por continuidad operativa: eres el único Administrador activo del sistema.",
                    )
                    return redirect('mi_privacidad')

            if Caja.objects.filter(cajero=user, estado='ABIERTA').exists():
                messages.error(
                    request,
                    "Debes cerrar y arquear tu caja abierta antes de solicitar la baja y anonimización de tu cuenta.",
                )
                return redirect('mi_privacidad')

            anonimizar_datos_usuario(user, request=request, motivo='Autogestión ARCO del colaborador')
            logout(request)
            messages.info(
                request,
                "Tus datos personales identificables fueron eliminados y anonimizados correctamente del sistema.",
            )
            resp = redirect('index')
            resp['Clear-Site-Data'] = '"cache", "storage"'
            return resp

    historial_consentimientos = RegistroConsentimiento.objects.filter(usuario=user).order_by('-aceptado_en')[:15]
    context = {
        'rol_usuario': rol_actual,
        'perfil': perfil,
        'rut_enmascarado': enmascarar_rut(perfil.rut if perfil else ''),
        'email_enmascarado': enmascarar_email(user.email),
        'historial_consentimientos': historial_consentimientos,
        'version_politica': VERSION_POLITICA_ACTUAL,
        'version_terminos': VERSION_TERMINOS_ACTUAL,
        'retencion_dias': RETENCION_DATOS_DIAS,
        'analytics_habilitado': _extraer_cookie_analytics(request),
    }
    return render(request, 'ventas/acceso/mi_privacidad.html', context)
