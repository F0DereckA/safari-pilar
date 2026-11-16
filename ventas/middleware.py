import time
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import BadRequest, PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect

from ventas.security import hash_dato_sensible, verificar_rate_limit_ip


CSP_SAFARI_DEFAULT = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com data:; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' https://cdn.jsdelivr.net; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SafariSessionSecurityMiddleware:
    """
    Control de expiración de sesión en el servidor e integridad anti-secuestro:
    - Caduca sesiones autenticadas tras `SESSION_INACTIVITY_TIMEOUT` segundos reales de inactividad en servidor.
    - Excluye del cierre las estaciones continuas KDS (/cocina/, /barra/) y no renueva actividad en polling delta pasivo.
    - Valida huella SHA-256 de User-Agent para mitigar robo de cookie de sesión.
    """

    RUTAS_ESTACION_CONTINUA = ('/cocina/', '/barra/')
    RUTAS_POLLING_PASIVO = ('/api/sincronizacion/estado/',)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, 'user', None) and request.user.is_authenticated:
            path = request.path or '/'
            timeout_inact = int(getattr(settings, 'SESSION_INACTIVITY_TIMEOUT', 900))
            ahora = time.time()

            # 1. Validación de integridad de huella User-Agent en sesión activa
            ua_actual = request.META.get('HTTP_USER_AGENT', '')
            ua_hash_actual = hash_dato_sensible(ua_actual, contexto='session-ua') if ua_actual else ''
            ua_hash_guardado = request.session.get('_safari_ua_hash')
            if ua_hash_guardado and ua_hash_actual and ua_hash_guardado != ua_hash_actual:
                logout(request)
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or path.startswith('/api/'):
                    return JsonResponse({'ok': False, 'error': 'Sesión invalidada por cambio anómalo de dispositivo.'}, status=401)
                messages.warning(request, "Tu sesión se cerró por seguridad al detectarse cambio inesperado de navegador.")
                resp = redirect('index')
                resp['Clear-Site-Data'] = '"cache", "storage"'
                return resp

            # 2. Expiración por inactividad en servidor (excepto KDS de visualización continua)
            es_kds_continuo = any(path.startswith(r) for r in self.RUTAS_ESTACION_CONTINUA)
            es_polling = any(path.startswith(r) for r in self.RUTAS_POLLING_PASIVO)
            ultima_actividad = request.session.get('_safari_last_activity')

            if (not es_kds_continuo) and ultima_actividad is not None:
                try:
                    transcurrido = ahora - float(ultima_actividad)
                except (TypeError, ValueError):
                    transcurrido = 0

                if transcurrido > timeout_inact:
                    logout(request)
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or path.startswith('/api/'):
                        resp_401 = JsonResponse({'ok': False, 'sesion_expirada': True, 'error': 'Sesión expirada por inactividad.'}, status=401)
                        resp_401['Clear-Site-Data'] = '"cache", "storage"'
                        return resp_401
                    messages.warning(request, "Tu sesión venció en el servidor tras superar el tiempo límite de inactividad.")
                    resp = redirect('index')
                    resp['Clear-Site-Data'] = '"cache", "storage"'
                    return resp

            # 3. Registrar actividad activa (sin extender expiración por llamadas de polling en segundo plano)
            if not es_polling:
                if ultima_actividad is None or (ahora - float(ultima_actividad)) >= 15:
                    request.session['_safari_last_activity'] = ahora
                if not ua_hash_guardado and ua_hash_actual:
                    request.session['_safari_ua_hash'] = ua_hash_actual

        return self.get_response(request)


class SafariErrorHandlingMiddleware:
    """
    Middleware de Seguridad Defensiva, Rate Limiting IP, CORS Cerrado y Errores HTTP Personalizados.
    - Bloquea peticiones cross-origin no autorizadas en mutaciones/APIs (CORS estricto).
    - Aplica control de ráfagas por IP en métodos de escritura devolviendo HTTP 429.
    - Refuerza cabeceras CSP, Referrer-Policy, Permissions-Policy y plantillas corporativas de error.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _aplicar_cabeceras_seguridad(self, response):
        if 'Referrer-Policy' not in response:
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if 'Permissions-Policy' not in response:
            response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), browsing-topics=()'
        if 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = CSP_SAFARI_DEFAULT
        return response

    def _origen_autorizado(self, request, origin):
        parsed = urlparse(origin)
        host_origin = parsed.netloc.lower()
        host_actual = (request.get_host() or '').lower()
        if host_origin and host_actual and host_origin == host_actual:
            return True
        permitidos = {o.rstrip('/').lower() for o in getattr(settings, 'CORS_ALLOWED_ORIGINS', [])}
        return origin.rstrip('/').lower() in permitidos

    def __call__(self, request):
        path = (request.path or '').lower()
        static_url = getattr(settings, 'STATIC_URL', '/static/').lower()
        es_estatico = path.startswith(static_url) or path.startswith('/static/')

        # 1. Validación estricta de CORS cerrado para orígenes externos en escrituras y APIs
        origin = request.META.get('HTTP_ORIGIN', '').strip()
        if origin and not es_estatico:
            if not self._origen_autorizado(request, origin):
                if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') or path.startswith('/api/'):
                    resp_cors = JsonResponse(
                        {'ok': False, 'error': 'Acceso CORS denegado: origen externo no autorizado.'},
                        status=403,
                    )
                    return self._aplicar_cabeceras_seguridad(resp_cors)

        # 2. Límite global por IP para evitar ráfagas destructivas sobre rutas mutadoras (HTTP 429)
        if not es_estatico and request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            permitido, retry_after, _ = verificar_rate_limit_ip(
                request,
                namespace='global_post_burst',
                max_requests=180,
                window_seconds=60,
            )
            if not permitido:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or path.startswith('/api/'):
                    resp_429 = JsonResponse(
                        {'ok': False, 'error': 'Demasiadas solicitudes desde tu dirección IP. Espera un momento.'},
                        status=429,
                    )
                else:
                    resp_429 = HttpResponse(
                        "Demasiadas solicitudes consecutivas detectadas desde tu IP. Espera unos segundos.",
                        status=429,
                        content_type='text/plain; charset=utf-8',
                    )
                resp_429['Retry-After'] = str(retry_after)
                return self._aplicar_cabeceras_seguridad(resp_429)

        response = self.get_response(request)

        # Preservar respuestas JSON aplicando cabeceras HTTP defensivas
        if 'application/json' in response.get('Content-Type', '').lower():
            return self._aplicar_cabeceras_seguridad(response)

        # Renderizado corporativo de errores 404 / 403 / 400
        if response.status_code == 404 and not es_estatico:
            if not path.endswith(('.ico', '.png', '.jpg', '.jpeg', '.svg', '.css', '.js', '.map', '.woff', '.woff2', '.ttf')):
                from ventas.views import error_404_view
                return self._aplicar_cabeceras_seguridad(error_404_view(request))
        elif response.status_code == 403 and not es_estatico:
            from ventas.views import error_403_view
            return self._aplicar_cabeceras_seguridad(error_403_view(request))
        elif response.status_code == 400 and not es_estatico:
            from ventas.views import error_400_view
            return self._aplicar_cabeceras_seguridad(error_400_view(request))

        return self._aplicar_cabeceras_seguridad(response)

    def process_exception(self, request, exception):
        """Captura excepciones no controladas o controladas lanzadas desde vistas"""
        if isinstance(exception, Http404):
            from ventas.views import error_404_view
            return self._aplicar_cabeceras_seguridad(error_404_view(request, exception))
        elif isinstance(exception, PermissionDenied):
            from ventas.views import error_403_view
            return self._aplicar_cabeceras_seguridad(error_403_view(request, exception))
        elif isinstance(exception, BadRequest):
            from ventas.views import error_400_view
            return self._aplicar_cabeceras_seguridad(error_400_view(request, exception))

        from ventas.views import error_500_view
        return self._aplicar_cabeceras_seguridad(error_500_view(request))
