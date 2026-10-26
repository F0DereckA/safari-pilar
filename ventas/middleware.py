from django.conf import settings
from django.http import Http404
from django.core.exceptions import PermissionDenied, BadRequest


class SafariErrorHandlingMiddleware:
    """
    Middleware de Excepciones y Errores HTTP Personalizados (Semana 10 / OWASP ASVS).
    Garantiza que cualquier ruta errónea, recurso inexistente (404), acceso prohibido (403),
    solicitud inválida (400) o fallo de servidor (500) muestre siempre la interfaz corporativa
    de Parque Safari, eliminando la pantalla técnica amarilla de Django tanto en desarrollo como en producción.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Si el código de respuesta es 404 y no es un archivo estático ni favicon
        if response.status_code == 404:
            static_url = getattr(settings, 'STATIC_URL', '/static/')
            path = request.path.lower()
            if not path.startswith(static_url.lower()) and not path.startswith('/static/'):
                if not path.endswith(('.ico', '.png', '.jpg', '.jpeg', '.svg', '.css', '.js', '.map', '.woff', '.woff2', '.ttf')):
                    from ventas.views import error_404_view
                    return error_404_view(request)

        # Si el código de respuesta es 403 y no es estático
        elif response.status_code == 403:
            static_url = getattr(settings, 'STATIC_URL', '/static/')
            path = request.path.lower()
            if not path.startswith(static_url.lower()) and not path.startswith('/static/'):
                from ventas.views import error_403_view
                return error_403_view(request)

        # Si el código de respuesta es 400 y no es estático
        elif response.status_code == 400:
            static_url = getattr(settings, 'STATIC_URL', '/static/')
            path = request.path.lower()
            if not path.startswith(static_url.lower()) and not path.startswith('/static/'):
                from ventas.views import error_400_view
                return error_400_view(request)

        # Cabeceras de seguridad reforzadas OWASP (Defense in Depth)
        if 'Referrer-Policy' not in response:
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if 'Permissions-Policy' not in response:
            response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        return response

    def process_exception(self, request, exception):
        """Captura excepciones no controladas o controladas lanzadas desde vistas"""
        if isinstance(exception, Http404):
            from ventas.views import error_404_view
            return error_404_view(request, exception)
        elif isinstance(exception, PermissionDenied):
            from ventas.views import error_403_view
            return error_403_view(request, exception)
        elif isinstance(exception, BadRequest):
            from ventas.views import error_400_view
            return error_400_view(request, exception)

        # Excepciones no controladas (500)
        from ventas.views import error_500_view
        return error_500_view(request)
