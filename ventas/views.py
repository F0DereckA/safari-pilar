import datetime

import json

import logging

import time

from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404, Http404

from django.urls import reverse

from django.http import JsonResponse, HttpResponse

from django.contrib import messages

from django.db import models, transaction

from django.db.models import Sum, Count, Q, F

from django.utils import timezone

from django.core.cache import cache

from django.core.exceptions import ValidationError

from decimal import Decimal

from django.contrib.auth.models import User

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash

from django.contrib.auth.password_validation import validate_password

from .validators import validar_complejidad_clave

from .security import (
    USUARIOS_DEMO_EVALUACION,
    VERSION_POLITICA_ACTUAL,
    VERSION_TERMINOS_ACTUAL,
    demo_mode_activo,
    enmascarar_rut,
    hash_alias_navegador,
    hash_dato_sensible,
    limpiar_texto_seguro,
    resolver_usuario_demo_eval,
    usuario_tiene_consentimiento_vigente,
    validar_acceso_rls_local,
    verificar_rate_limit_ip,
)


logger = logging.getLogger(__name__)

from .models import PuntoVenta, PerfilEmpleado, AlertaTraslado, Mesa, Jornada, Caja, Venta, DetalleVenta, Pedido, DetallePedido, Ticket, Categoria, Producto, Menu, Entrega, ConvenioHuesped, ConsumoHuesped, OfertaTemporada, ReasignacionMesa, PrecioEspecial, RegistroPrecioEspecial, PuntoImpresion, RegistroImpresion, ConsumoInterno, DetalleConsumoInterno, registrar_evento_consentimiento

from .utils import (

    validar_y_calcular_precio_linea, registrar_precio_especial_auditoria,

    validar_disponibilidad_producto,

    calcular_redondeo_ley_20956, emitir_tickets_comanda, emitir_comprobante_venta,

    reimprimir_ticket, reintentar_despacho_impresion,

    registrar_consumo_interno, liquidar_consumos_por_planilla,

    validar_transicion_estado_pedido, registrar_entrega_pedido,

    proteger_contingencia_operativa, cerrar_operaciones_de_jornada

)





def get_locales_data():

    """Retorna los datos operativos de todos los locales gastronómicos registrados en la BD de Parque Safari"""

    # Cargar todos los puntos de venta reales registrados en la BD (cero métricas simuladas)

    locales_bd = list(PuntoVenta.objects.all().order_by('id'))
    locales = {}

    hoy = timezone.localdate()
    ahora_dt = timezone.localtime()
    ahora_hora = ahora_dt.time()

    # Regla Operativa Oficial Parque Safari: Todos los locales abren a las 10:00 y cierran a las 18:00 (10:00 AM a 6:00 PM)
    hora_apertura = datetime.time(10, 0)
    hora_cierre = datetime.time(18, 0)
    en_horario = (hora_apertura <= ahora_hora < hora_cierre)

    # Batch load para evitar consultas N+1 por cada local en la vista administrativa
    ventas_por_local = {}
    for rv in (
        Venta.objects.filter(fecha_hora__date=hoy)
        .exclude(estado__in=['ANULADA', 'CANCELADA'])
        .select_related('cajero', 'cajero__perfil', 'mesa')
        .prefetch_related('detalles__producto__categoria')
        .order_by('-fecha_hora')
    ):
        ventas_por_local.setdefault(rv.punto_venta_id, []).append(rv)

    cajas_por_local_list = {}
    for c in Caja.objects.filter(jornada__fecha=hoy).select_related('cajero'):
        cajas_por_local_list.setdefault(c.punto_venta_id, []).append(c)

    perfiles_por_local = {}
    for p in PerfilEmpleado.objects.filter(punto_venta_actual__isnull=False, activo=True).select_related('usuario'):
        perfiles_por_local.setdefault(p.punto_venta_actual_id, []).append(p)

    cajas_por_local = {}
    paleta_cat = ["#ef4444", "#f59e0b", "#0284c7", "#9333ea", "#16a34a"]
    iconos_mp = {
        "Efectivo": "bi-cash-coin",
        "Tarjeta Débito": "bi-credit-card",
        "Tarjeta Crédito": "bi-credit-card-2-front",
        "Transferencia": "bi-bank",
    }
    for pv in locales_bd:
        real_ventas_hoy = ventas_por_local.get(pv.id, [])
        cajas_hoy = cajas_por_local_list.get(pv.id, [])
        caja_apertura = sum(int(c.monto_apertura or 0) for c in cajas_hoy)
        cajas_por_local[pv.id] = {c.cajero_id: c for c in cajas_hoy}

        real_tickets = []
        suma_ventas_reales = 0
        tickets_pagados = 0
        comandas_abiertas = 0
        caja_efectivo = 0
        caja_tarjeta = 0
        categorias_monto = {}
        metodos_monto = {}

        for rv in real_ventas_hoy:
            rol_c = obtener_rol_usuario(rv.cajero) or "Mesero"
            v_items = []
            for d in rv.detalles.all():
                nom = d.producto.nombre
                cat_obj = d.producto.categoria if d.producto else None
                if cat_obj and getattr(cat_obj, 'destino_defecto', None) == 'BARRA':
                    dest = "Barra"
                elif cat_obj and getattr(cat_obj, 'destino_defecto', None) == 'COCINA':
                    dest = "Cocina"
                else:
                    dest = "Cocina" if any(w in nom.lower() for w in ['hamburguesa', 'cazuela', 'churrasco', 'papas', 'nuggets', 'almuerzo']) else "Barra"

                v_items.append({
                    "nombre": nom,
                    "cantidad": d.cantidad,
                    "precio": int(d.precio_aplicado),
                    "subtotal": int(d.subtotal),
                    "destino": dest,
                    "nota": ""
                })

                if rv.estado == 'PAGADA':
                    cat_nombre = cat_obj.nombre if cat_obj else "Otros Productos"
                    categorias_monto[cat_nombre] = categorias_monto.get(cat_nombre, 0) + int(d.subtotal or 0)

            if rv.estado == 'PAGADA':
                monto_rv = int(rv.total or 0)
                suma_ventas_reales += monto_rv
                tickets_pagados += 1
                mp = (rv.metodo_pago or 'EFECTIVO').upper()
                if mp == 'EFECTIVO':
                    caja_efectivo += monto_rv
                elif mp in ['DEBITO', 'CREDITO']:
                    caja_tarjeta += monto_rv
                mp_label = {
                    'EFECTIVO': 'Efectivo',
                    'DEBITO': 'Tarjeta Débito',
                    'CREDITO': 'Tarjeta Crédito',
                    'TRANSFERENCIA': 'Transferencia',
                }.get(mp, rv.get_metodo_pago_display())
                metodos_monto[mp_label] = metodos_monto.get(mp_label, 0) + monto_rv
            elif rv.estado == 'ABIERTA':
                comandas_abiertas += 1

            if len(real_tickets) < 25:
                estado_ticket = "Pagado" if rv.estado == 'PAGADA' else ("En Cocina" if any(it["destino"] == "Cocina" for it in v_items) else "En Barra")
                real_tickets.append({
                    "id": f"COM-{rv.id:04d}",
                    "hora": timezone.localtime(rv.fecha_hora).strftime("%H:%M"),
                    "cliente": rv.mesa.identificador if rv.mesa else "Mostrador",
                    "total": int(rv.total),
                    "cajero": rv.cajero.get_full_name() or rv.cajero.username,
                    "creador_rol": "Mesero" if rol_c == 'MESERO' else "Cajero",
                    "estado": estado_ticket,
                    "items": v_items,
                    "items_json": json.dumps(v_items)
                })

        total_ventas_calc = suma_ventas_reales
        tickets_emitidos_calc = tickets_pagados
        ticket_prom_calc = round(total_ventas_calc / tickets_emitidos_calc) if tickets_emitidos_calc else 0

        total_cat = sum(categorias_monto.values())
        ventas_categoria = [
            {
                "nombre": c_nom,
                "monto": c_monto,
                "porcentaje": round((c_monto / total_cat) * 100) if total_cat else 0,
                "color": paleta_cat[idx % len(paleta_cat)],
            }
            for idx, (c_nom, c_monto) in enumerate(sorted(categorias_monto.items(), key=lambda x: -x[1]))
        ]

        total_met = sum(metodos_monto.values())
        metodos_pago = [
            {
                "metodo": m_nom,
                "monto": m_monto,
                "porcentaje": round((m_monto / total_met) * 100) if total_met else 0,
                "icono": iconos_mp.get(m_nom, "bi-wallet2"),
            }
            for m_nom, m_monto in sorted(metodos_monto.items(), key=lambda x: -x[1])
        ]

        turno_oficial = "Horario Oficial (10:00 - 18:00)"
        if pv.activo:
            estado_local = "Abierto (10:00 - 18:00)" if en_horario else "Cerrado (Horario 10:00 - 18:00)"
        else:
            estado_local = "Inactivo"

        locales[pv.id] = {
            "id": pv.id,
            "nombre": pv.nombre,
            "tipo": pv.tipo or "Punto de Venta",
            "descripcion": pv.descripcion or "Punto gastronómico operativo de Parque Safari.",
            "icono": getattr(pv, 'icono', None) or "bi-shop",
            "color": getattr(pv, 'color', None) or "#c62828",
            "estado": estado_local,
            "en_horario": en_horario,
            "horario_apertura": "10:00",
            "horario_cierre": "18:00",
            "turno": turno_oficial,
            "total_ventas": total_ventas_calc,
            "tickets_emitidos": tickets_emitidos_calc,
            "comandas_abiertas": comandas_abiertas,
            "ticket_promedio": ticket_prom_calc,
            "caja_apertura": caja_apertura,
            "caja_efectivo": caja_efectivo,
            "caja_tarjeta": caja_tarjeta,
            "saldo_actual": int(caja_apertura) + caja_efectivo,
            "personal": [],
            "ventas_categoria": ventas_categoria,
            "metodos_pago": metodos_pago,
            "tickets_recientes": real_tickets
        }

    # Sincronizar dotación de personal real desde la BD respetando el límite de 1 puesto de trabajo
    for loc_id, loc in locales.items():
        perfiles = perfiles_por_local.get(loc_id, [])
        if perfiles:
            cajas_local = cajas_por_local.get(loc_id, {})
            personal_list = []
            for p in perfiles:
                caja_asoc = cajas_local.get(p.usuario_id)
                if caja_asoc and caja_asoc.fecha_hora_apertura:
                    hora_login = timezone.localtime(caja_asoc.fecha_hora_apertura).strftime("%H:%M")
                elif p.usuario.last_login:
                    hora_login = timezone.localtime(p.usuario.last_login).strftime("%H:%M")
                else:
                    hora_login = "--:--"
                roles_estacion = {
                    'MESERO': f"Salón {loc['nombre'].split()[0]}",
                    'COCINERO': f"Cocina {loc['nombre'].split()[0]}",
                    'BARRA': f"Barra {loc['nombre'].split()[0]}",
                }
                caja_nombre = (
                    caja_asoc.nombre
                    if caja_asoc
                    else roles_estacion.get(p.rol, f"Caja {loc['nombre'].split()[0]} #1")
                )
                personal_list.append({
                    "perfil_id": p.id,
                    "nombre": p.usuario.get_full_name() or p.usuario.username,
                    "rut": enmascarar_rut(p.rut) if p.rut else "S/RUT",
                    "cargo": p.get_rol_display(),
                    "hora_login": hora_login,
                    "caja": caja_nombre,
                    "estado": "Activo",
                })
            loc["personal"] = personal_list

    return locales





def obtener_rol_usuario(user):

    """Retorna el rol oficial ('ADMINISTRADOR', 'CAJERO', 'MESERO', 'COCINERO', 'BARRA') del usuario autenticado"""

    if not user.is_authenticated:

        return None

    try:

        perfil = user.perfil

        return perfil.rol

    except (PerfilEmpleado.DoesNotExist, AttributeError):

        if user.is_superuser or user.is_staff:

            return 'ADMINISTRADOR'

        return None


RUTA_INICIO_POR_ROL = {
    'ADMINISTRADOR': 'administrador',
    'CAJERO': 'vendedor',
    'MESERO': 'mesero',
    'COCINERO': 'cocina',
    'BARRA': 'barra',
}





def requiere_rol(roles_permitidos):

    """

    Decorador para restringir el acceso a vistas según el rol de PerfilEmpleado.

    Si no está autenticado, redirige a index con advertencia.

    Si el usuario o su PerfilEmpleado está inactivo, revoca la sesión y redirige a index.

    Si el rol no está permitido, redirige al módulo autorizado según su propio rol.

    """

    def decorator(view_func):

        @wraps(view_func)

        def _wrapped_view(request, *args, **kwargs):

            es_api = (
                request.path.startswith('/api/')
                or request.headers.get('x-requested-with') == 'XMLHttpRequest'
                or 'application/json' in request.headers.get('accept', '')
            )

            if not request.user.is_authenticated:

                if es_api:
                    return JsonResponse({
                        'ok': False,
                        'status': 'error',
                        'sesion_expirada': True,
                        'error': "Sesión expirada o no iniciada. Inicia sesión nuevamente."
                    }, status=401)

                messages.warning(request, "Acceso protegido: Debes iniciar sesión con tus credenciales para ingresar.")

                return redirect('index')



            # Verificar si el usuario o su PerfilEmpleado fue desactivado

            if not request.user.is_active:

                logout(request)

                if es_api:
                    return JsonResponse({
                        'ok': False,
                        'status': 'error',
                        'sesion_expirada': True,
                        'error': "Tu cuenta de colaborador ha sido desactivada. La sesión fue cerrada por seguridad."
                    }, status=401)

                messages.error(request, "Tu cuenta de colaborador ha sido desactivada. La sesión fue cerrada por seguridad.")

                return redirect('index')



            perfil = getattr(request.user, 'perfil', None)

            if perfil and not perfil.activo:

                logout(request)

                if es_api:
                    return JsonResponse({
                        'ok': False,
                        'status': 'error',
                        'sesion_expirada': True,
                        'error': "Tu cuenta de colaborador se encuentra inactiva. La sesión fue cerrada por seguridad."
                    }, status=401)

                messages.error(request, "Tu cuenta de colaborador se encuentra inactiva. La sesión fue cerrada por seguridad.")

                return redirect('index')



            # H19: Blindaje ISO/IEC 27400: Obligar cambio de clave expirada o de primer ingreso

            if request.session.get('requiere_cambio_clave'):

                if es_api:
                    return JsonResponse({
                        'ok': False,
                        'status': 'error',
                        'requiere_cambio_clave': True,
                        'error': "Actualización obligatoria de clave requerida antes de operar."
                    }, status=403)

                messages.warning(

                    request,

                    "Actualización obligatoria de clave requerida (Norma ISO/IEC 27400). "

                    "Debes cambiar tu contraseña antes de operar en el sistema."

                )

                return redirect('cambiar_clave_expirada')



            rol = obtener_rol_usuario(request.user)

            if rol not in roles_permitidos:

                if es_api:

                    return JsonResponse({'ok': False, 'error': f"Acceso denegado: Tu perfil ({rol or 'Sin Rol'}) no tiene autorización para este recurso."}, status=403)

                messages.error(request, f"Acceso restringido: Tu perfil ({rol or 'Sin Rol'}) no tiene autorización para acceder a esta sección.")

                return redirect(RUTA_INICIO_POR_ROL.get(rol, 'index'))



            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator





def obtener_ip_cliente(request):

    """H8: Obtiene la dirección IP real del cliente validando formato seguro (OWASP)"""

    import ipaddress

    remote_addr = (request.META.get('REMOTE_ADDR') or '127.0.0.1').strip()

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:

        candidate = x_forwarded_for.split(',')[0].strip()

        try:

            ipaddress.ip_address(candidate)

            return candidate

        except ValueError:

            pass

    try:

        ipaddress.ip_address(remote_addr)

        return remote_addr

    except ValueError:

        return '127.0.0.1'





def obtener_url_redireccion_segura(request, default_url):

    """H20: Mitigación de Redirección Abierta (CWE-601 / OWASP)"""

    from django.utils.http import url_has_allowed_host_and_scheme

    next_url = request.POST.get('next') or request.GET.get('next')

    if next_url and url_has_allowed_host_and_scheme(

        url=next_url,

        allowed_hosts={request.get_host()},

        require_https=request.is_secure()

    ):

        return next_url

    return default_url





MAX_INTENTOS_LOGIN = 5

TIEMPO_BLOQUEO_LOGIN = 300  # 5 minutos en segundos





def _leer_tokens_ack_cookie(request):
    from urllib.parse import unquote
    raw = request.COOKIES.get('safari_ack_users', '')
    if not raw:
        return []
    try:
        decodificado = unquote(raw)
        data = json.loads(decodificado)
        if isinstance(data, list):
            return [str(x)[:16] for x in data if isinstance(x, str) and len(x) <= 16][:25]
    except (ValueError, TypeError):
        pass
    return []


def _adjuntar_cookie_ack_usuario(request, response, user, perfil=None):
    from urllib.parse import quote
    tokens = _leer_tokens_ack_cookie(request)
    nuevos = [hash_alias_navegador(user.username)]
    if perfil and getattr(perfil, 'rut', ''):
        tok_rut = hash_alias_navegador(perfil.rut)
        if tok_rut:
            nuevos.append(tok_rut)
    for t in nuevos:
        if t and t not in tokens:
            tokens.append(t)
    tokens = tokens[-25:]
    payload = quote(json.dumps(tokens, separators=(',', ':')), safe='')
    response.set_cookie(
        'safari_ack_users',
        payload,
        max_age=180 * 86400,
        httponly=False,
        samesite='Lax',
        secure=request.is_secure(),
    )
    return response


def login_view(request):

    """RF01: Inicio de sesión real con django.contrib.auth, consentimiento 1 sola vez por usuario, protección de fuerza bruta y redirección por rol"""

    if request.method == 'POST':

        permitido_ip, retry_after, _ = verificar_rate_limit_ip(
            request,
            namespace='login_post_ip',
            max_requests=80,
            window_seconds=60,
        )
        if not permitido_ip:
            resp_429 = HttpResponse(
                "Demasiados intentos de inicio de sesión desde tu dirección IP. Espera unos segundos.",
                status=429,
                content_type='text/plain; charset=utf-8',
            )
            resp_429['Retry-After'] = str(retry_after)
            return resp_429

        username = limpiar_texto_seguro(request.POST.get('username', ''), max_length=150)

        password = request.POST.get('password', '')

        demo_rol_eval = limpiar_texto_seguro(request.POST.get('demo_rol_eval', ''), max_length=50).lower()

        acepto_politicas = request.POST.get('acepto_politicas', '') in ('1', 'on', 'true', 'yes')

        exigir_consentimiento = (
            request.POST.get('portal_consent_required') == '1'
            or 'mozilla' in (request.META.get('HTTP_USER_AGENT', '') or '').lower()
        )

        es_demo_autorizado = bool(demo_rol_eval and demo_mode_activo() and not password)

        if es_demo_autorizado and not username:
            username = demo_rol_eval

        # Validar campos requeridos obligatorios (Semana 10)

        if not username or (not password and not es_demo_autorizado):

            messages.warning(request, "Por favor completa todos los campos requeridos (nombre de usuario y contraseña).")

            return redirect('index')



        # Control de Rate Limiting y Protección contra Ataques de Fuerza Bruta (OWASP)

        ip_cliente = obtener_ip_cliente(request)

        key_bloqueo = f"login_bloqueado_{ip_cliente}_{username.lower()}"

        key_intentos = f"login_intentos_{ip_cliente}_{username.lower()}"

        key_ip_bloqueo = f"login_ip_bloqueado_{ip_cliente}"

        key_ip_intentos = f"login_ip_intentos_{ip_cliente}"



        if cache.get(key_ip_bloqueo):

            messages.error(

                request,

                "Acceso de red bloqueado temporalmente por acumulación de múltiples intentos fallidos. "

                "Por motivos de seguridad institucional, espera 15 minutos antes de volver a intentarlo."

            )

            return redirect('index')



        if cache.get(key_bloqueo):

            messages.error(

                request,

                f"Acceso temporalmente bloqueado por superar el límite de {MAX_INTENTOS_LOGIN} intentos fallidos. "

                "Por motivos de seguridad, espera 5 minutos antes de volver a intentarlo."

            )

            return redirect('index')



        # Permitir inicio de sesión tanto con nombre de usuario como con RUT institucional

        user_candidate = User.objects.filter(username__iexact=username).first()

        if not user_candidate:

            perfil_rut = PerfilEmpleado.objects.filter(rut__iexact=username).select_related('usuario').first()

            if perfil_rut and perfil_rut.usuario:

                user_candidate = perfil_rut.usuario

                username = user_candidate.username



        # Validación a nivel de Base de Datos para bloqueo persistente por fuerza bruta (Tarea 1)

        if user_candidate and hasattr(user_candidate, 'perfil') and user_candidate.perfil.esta_bloqueado():

            minutos_restantes = max(1, int((user_candidate.perfil.bloqueado_hasta - timezone.now()).total_seconds() // 60) + 1)

            messages.error(

                request,

                f"Cuenta bloqueada temporalmente por superar {MAX_INTENTOS_LOGIN} intentos fallidos. "

                f"Por seguridad institucional, espera {minutos_restantes} minuto(s) antes de volver a intentar."

            )

            return redirect('index')



        if es_demo_autorizado and demo_rol_eval == username.lower():
            user = resolver_usuario_demo_eval(demo_rol_eval)
        else:
            user = authenticate(request, username=username, password=password)



        if user is not None:

            perfil = getattr(user, 'perfil', None)

            if not user.is_active or (perfil and not perfil.activo):

                messages.error(request, "Tu cuenta de colaborador se encuentra inactiva. Contacta al Administrador.")

                return redirect('index')

            ya_acepto_vigente = usuario_tiene_consentimiento_vigente(user)

            if exigir_consentimiento and not acepto_politicas and not ya_acepto_vigente:

                messages.error(
                    request,
                    "Debes marcar la casilla para aceptar la Política de Privacidad y los Términos y Condiciones antes de ingresar.",
                )

                return redirect('index')



            # Autenticación exitosa: Limpiar contadores de intentos fallidos en caché y BD

            cache.delete(key_bloqueo)

            cache.delete(key_intentos)

            cache.delete(key_ip_bloqueo)

            cache.delete(key_ip_intentos)

            if perfil:

                perfil.limpiar_intentos_fallidos()



            if hasattr(user, 'backend'):
                login(request, user)
            else:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            request.session['_safari_last_activity'] = time.time()
            ua_actual = request.META.get('HTTP_USER_AGENT', '')
            if ua_actual:
                request.session['_safari_ua_hash'] = hash_dato_sensible(ua_actual, contexto='session-ua')

            if acepto_politicas:
                acepto_cookies_analisis = request.POST.get('acepto_cookies_analisis', '') in ('1', 'on', 'true', 'yes')
                registrar_evento_consentimiento(
                    request=request,
                    usuario=user,
                    origen='LOGIN_PORTAL',
                    acepto_privacidad=True,
                    acepto_terminos=True,
                    acepto_cookies_analisis=acepto_cookies_analisis,
                )

            respuesta_login = None

            # Verificar cambio forzoso de contraseña en primer ingreso o expiración semestral de 6 meses (ISO/IEC 27400)

            if perfil and (perfil.debe_cambiar_clave or perfil.clave_expirada()):

                request.session['requiere_cambio_clave'] = True

                if perfil.debe_cambiar_clave:

                    messages.warning(

                        request,

                        "Primer inicio de sesión detectado: Conforme a la Norma ISO/IEC 27400, "

                        "debes cambiar tu contraseña temporal por una segura antes de ingresar a tu terminal."

                    )

                else:

                    messages.warning(

                        request,

                        "Tu contraseña ha superado el ciclo obligatorio de 6 meses (180 días). "

                        "Por seguridad institucional, debes actualizarla ahora."

                    )

                respuesta_login = redirect('cambiar_clave_expirada')

            if respuesta_login is None:

                # Redirección directa si se especificó un destino explícito autorizado (ej: KDS Cocina o BDS Barra)

                next_url = request.POST.get('next', '').strip()

                if next_url in ('/cocina/', '/barra/', '/mesero/', '/vendedor/', '/administrador/'):

                    respuesta_login = redirect(next_url)

            if respuesta_login is None:

                rol = obtener_rol_usuario(user)
                ruta_inicio = RUTA_INICIO_POR_ROL.get(rol)

                if ruta_inicio:

                    respuesta_login = redirect(ruta_inicio)

                else:

                    messages.warning(request, "Usuario autenticado sin rol asignado en el sistema.")

                    respuesta_login = redirect('index')

            if acepto_politicas or ya_acepto_vigente:
                _adjuntar_cookie_ack_usuario(request, respuesta_login, user, perfil)

            return respuesta_login

        else:

            # Registrar intento fallido tanto en BD como en caché (Tarea 1)

            if user_candidate and hasattr(user_candidate, 'perfil'):

                user_candidate.perfil.registrar_intento_fallido(max_intentos=MAX_INTENTOS_LOGIN, minutos_bloqueo=5)



            existing_user = User.objects.filter(username=username).first()

            if existing_user and existing_user.check_password(password):

                perfil = getattr(existing_user, 'perfil', None)

                if not existing_user.is_active or (perfil and not perfil.activo):

                    messages.error(request, "Tu cuenta de colaborador se encuentra inactiva. Contacta al Administrador.")

                    return redirect('index')



            intentos_previos = cache.get(key_intentos, 0)

            intentos_actuales = intentos_previos + 1



            intentos_ip = cache.get(key_ip_intentos, 0) + 1

            if intentos_ip >= 10:

                cache.set(key_ip_bloqueo, True, timeout=900)  # Bloqueo de 15 minutos

                cache.delete(key_ip_intentos)

            else:

                cache.set(key_ip_intentos, intentos_ip, timeout=TIEMPO_BLOQUEO_LOGIN)



            if intentos_actuales >= MAX_INTENTOS_LOGIN:

                cache.set(key_bloqueo, True, timeout=TIEMPO_BLOQUEO_LOGIN)

                cache.delete(key_intentos)

                messages.error(

                    request,

                    f"Credenciales incorrectas. Has superado el límite de {MAX_INTENTOS_LOGIN} intentos fallidos. "

                    "Tu acceso ha sido bloqueado temporalmente por 5 minutos por razones de seguridad."

                )

            else:

                cache.set(key_intentos, intentos_actuales, timeout=TIEMPO_BLOQUEO_LOGIN)

                intentos_restantes = MAX_INTENTOS_LOGIN - intentos_actuales

                messages.error(

                    request,

                    f"Credenciales incorrectas. Verifica tu nombre de usuario y contraseña. "

                    f"Te quedan {intentos_restantes} intento(s) antes del bloqueo de seguridad."

                )



            return redirect('index')



    return redirect('index')





def logout_view(request):

    """H23: Cierre de sesión seguro con protección contra Cross-Site Request Forgery (CSRF)"""

    if request.method not in ['POST', 'GET']:

        return HttpResponseNotAllowed(['POST', 'GET'])

    referer = request.META.get('HTTP_REFERER')

    host = request.get_host()

    if request.method == 'GET' and referer and host not in referer:

        messages.warning(request, "Solicitud de cierre de sesión cancelada por origen no confiable.")

        return redirect('index')



    motivo = request.GET.get('motivo') or request.POST.get('motivo')

    logout(request)

    if motivo == 'inactividad':

        messages.warning(request, "Tu sesión fue cerrada automáticamente tras 15 minutos de inactividad por políticas de seguridad institucional.")

    else:

        messages.info(request, "Has cerrado tu sesión de forma segura. ¡Hasta pronto!")

    resp = redirect('index')
    resp['Clear-Site-Data'] = '"cache", "storage"'
    return resp





def error_404_view(request, exception=None):

    """

    Manejador personalizado de error HTTP 404 (Semana 10).

    Captura rutas inexistentes, URLs malformadas y llamadas get_object_or_404.

    Presenta interfaz amigable y coherente con Parque Safari sin exponer detalles técnicos.

    """

    rol = None

    if request.user.is_authenticated:

        rol = obtener_rol_usuario(request.user)

    return render(request, 'errores/400/404.html', {'rol_usuario': rol, 'path_solicitado': request.path}, status=404)





def error_403_view(request, exception=None):

    """

    Manejador personalizado de error HTTP 403 (Semana 10).

    Captura accesos no autorizados y permisos denegados.

    """

    rol = None

    if request.user.is_authenticated:

        rol = obtener_rol_usuario(request.user)

    return render(request, 'errores/400/403.html', {'rol_usuario': rol, 'path_solicitado': request.path}, status=403)





def error_400_view(request, exception=None):

    """

    Manejador personalizado de error HTTP 400 (Semana 10).

    Captura solicitudes inválidas y manipulación de parámetros.

    """

    rol = None

    if request.user.is_authenticated:

        rol = obtener_rol_usuario(request.user)

    return render(request, 'errores/400/400.html', {'rol_usuario': rol, 'path_solicitado': request.path}, status=400)







def error_401_view(request, exception=None):

    """Manejador personalizado de error HTTP 401: Autenticación Requerida"""

    return render(request, 'errores/400/401.html', {'path_solicitado': request.path}, status=401)





def error_502_view(request):

    """Manejador personalizado de error HTTP 502: Puerta de Enlace Incorrecta (Bad Gateway)"""

    return render(request, 'errores/500/502.html', {}, status=502)





def error_503_view(request):

    """Manejador personalizado de error HTTP 503: Servicio Temporalmente No Disponible / Mantenimiento"""

    return render(request, 'errores/500/503.html', {}, status=503)





def error_504_view(request):

    """Manejador personalizado de error HTTP 504: Tiempo de Espera Agotado (Gateway Timeout)"""

    return render(request, 'errores/500/504.html', {}, status=504)



def error_500_view(request):

    """

    Manejador personalizado de error HTTP 500 (Semana 10).

    Captura excepciones no controladas del servidor.

    Oculta trazas técnicas sensibles al usuario final (blindaje OWASP) y provee retorno seguro.

    """

    return render(request, 'errores/500/500.html', {}, status=500)







def qr_acceso_view(request):

    """Vista informativa con código QR de conexión dinámica sin exponer IPs ni cuentas fuera de evaluación."""

    url_acceso = request.build_absolute_uri(reverse('index'))

    return render(request, 'ventas/acceso/qr_acceso.html', {
        'url_acceso': url_acceso,
        'demo_mode_activo': demo_mode_activo(),
    })





def index(request):

    """Portal principal de acceso corporativo: detección automática de rol y redirección inmediata (Tarea 9)"""

    if request.user.is_authenticated:

        rol = obtener_rol_usuario(request.user)
        ruta_inicio = RUTA_INICIO_POR_ROL.get(rol)
        if ruta_inicio:
            return redirect(ruta_inicio)

    ack_tokens = _leer_tokens_ack_cookie(request)
    if demo_mode_activo():
        demo_users = User.objects.filter(username__in=USUARIOS_DEMO_EVALUACION, is_active=True).select_related('perfil')
        for u_demo in demo_users:
            if usuario_tiene_consentimiento_vigente(u_demo):
                tok = hash_alias_navegador(u_demo.username)
                if tok and tok not in ack_tokens:
                    ack_tokens.append(tok)

    ack_config = {
        'tokens': ack_tokens,
        'policy_version': VERSION_POLITICA_ACTUAL,
        'terms_version': VERSION_TERMINOS_ACTUAL,
    }
    return render(request, 'ventas/acceso/index.html', {
        'demo_mode_activo': demo_mode_activo(),
        'ack_config': ack_config,
    })





@requiere_rol(['CAJERO'])

def vendedor(request):

    """

    Pantalla intermedia del Cajero:

    RF02: Verificación y apertura de jornada diaria correspondiente a la fecha actual.

    RF03: Verificación y apertura de caja individual por cajero.

    Monitor en tiempo real conectado 100% a BD de comandas activas y mesas del salón.

    """

    proteger_contingencia_operativa(usuario=request.user)

    hoy = timezone.localdate()



    # RF02: Buscar si existe jornada operativa abierta para el día actual

    jornada_activa = Jornada.objects.select_related('usuario_apertura').filter(estado='ABIERTA', fecha=hoy).first()



    # RF03: Buscar la caja individual del cajero logueado para la jornada activa

    caja_activa = None

    if jornada_activa:

        caja_activa = Caja.objects.select_related('punto_venta', 'cajero').filter(

            jornada=jornada_activa,

            cajero=request.user,

            estado='ABIERTA'

        ).first()



    perfil = getattr(request.user, 'perfil', None)

    punto_venta = perfil.punto_venta_actual if (perfil and perfil.punto_venta_actual) else PuntoVenta.objects.filter(activo=True).first()

    local_operativo = caja_activa.punto_venta if (caja_activa and caja_activa.punto_venta) else punto_venta

    if not local_operativo:

        local_operativo = PuntoVenta.objects.filter(activo=True).first()

    if not punto_venta:

        punto_venta = local_operativo



    # Acciones operativas sobre mesas del salón desde Caja (ocupar, liberar o cobrar mesa)

    if request.method == 'POST':

        accion = request.POST.get('accion', '').strip()

        mesa_id = request.POST.get('mesa_id', '').strip()

        es_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')



        if accion in ['ocupar_mesa', 'liberar_mesa', 'cobrar_cuenta_mesa']:

            if not local_operativo:

                if es_ajax:

                    return JsonResponse({'ok': False, 'error': 'No tienes un local asignado.'}, status=400)

                messages.error(request, "No tienes un Punto de Venta asignado.")

                return redirect('vendedor')

            try:
                mesa_id = int(mesa_id)
            except (ValueError, TypeError):
                err_mesa = "Debes especificar una mesa válida para operar."
                if es_ajax:
                    return JsonResponse({'ok': False, 'error': err_mesa}, status=400)
                messages.error(request, err_mesa)
                return redirect('vendedor')



            if accion == 'ocupar_mesa':
                _, _, err_caja = _validar_jornada_y_caja_abierta_local(
                    local_operativo, caja_asignada=caja_activa, exigir_caja_asignada=True
                )
                if err_caja:
                    if es_ajax:
                        return JsonResponse({'ok': False, 'error': err_caja}, status=400)
                    messages.warning(request, err_caja)
                    return redirect('vendedor')

                from ventas.utils import validar_ocupacion_mesa

                with transaction.atomic():

                    mesa_obj = Mesa.objects.select_for_update().filter(id=mesa_id, punto_venta=local_operativo).first()

                    if not mesa_obj:

                        if es_ajax:

                            return JsonResponse({'ok': False, 'error': 'La mesa solicitada no existe en este local.'}, status=400)

                        messages.error(request, "La mesa solicitada no existe o no pertenece a este local.")

                        return redirect('vendedor')

                    try:

                        validar_ocupacion_mesa(mesa_obj)

                        mesa_obj.ocupar()

                        msg_ok = f"Clientes asignados a {mesa_obj.identificador}. Mesa marcada En Atención para el salón."

                        if es_ajax:

                            return JsonResponse({'ok': True, 'mensaje': msg_ok, 'mesa_id': mesa_obj.id, 'estado': mesa_obj.estado})

                        messages.success(request, msg_ok)

                    except ValidationError as ve:

                        err = ve.message if hasattr(ve, 'message') else str(ve)

                        if es_ajax:

                            return JsonResponse({'ok': False, 'error': err}, status=400)

                        messages.error(request, err)

                return redirect('vendedor')



            elif accion == 'liberar_mesa':

                from ventas.utils import liberar_mesa_operativa

                mesa_obj = Mesa.objects.filter(id=mesa_id, punto_venta=local_operativo).first()

                if not mesa_obj:

                    if es_ajax:

                        return JsonResponse({'ok': False, 'error': 'La mesa solicitada no existe en este local.'}, status=400)

                    messages.error(request, "La mesa solicitada no existe o no pertenece a este local.")

                    return redirect('vendedor')

                exito, msg_res = liberar_mesa_operativa(mesa_obj, usuario=request.user, forzar=False)

                if es_ajax:

                    return JsonResponse({'ok': exito, 'mensaje': msg_res, 'error': None if exito else msg_res}, status=200 if exito else 400)

                if exito:

                    messages.success(request, msg_res)

                else:

                    messages.error(request, msg_res)

                return redirect('vendedor')



            elif accion == 'cobrar_cuenta_mesa':

                if not caja_activa:

                    err = "Debes tener tu caja individual abierta para cobrar una mesa."

                    if es_ajax:

                        return JsonResponse({'ok': False, 'error': err}, status=400)

                    messages.warning(request, err)

                    return redirect('vendedor')



                metodo_pago = (request.POST.get('metodo_pago') or request.POST.get('pos_metodo_pago') or 'EFECTIVO').upper()

                if metodo_pago not in ['EFECTIVO', 'DEBITO', 'CREDITO', 'TRANSFERENCIA']:

                    metodo_pago = 'EFECTIVO'



                with transaction.atomic():

                    mesa_obj = Mesa.objects.select_for_update().filter(id=mesa_id, punto_venta=local_operativo).first()

                    if not mesa_obj:

                        if es_ajax:

                            return JsonResponse({'ok': False, 'error': 'La mesa solicitada no existe.'}, status=400)

                        messages.error(request, "La mesa solicitada no existe.")

                        return redirect('vendedor')



                    venta_abierta = Venta.objects.select_for_update().filter(

                        mesa=mesa_obj,

                        punto_venta=local_operativo,

                        estado='ABIERTA',

                        fecha_hora__date=hoy

                    ).first()

                    if not venta_abierta:

                        err = f"La {mesa_obj.identificador} no tiene consumos pendientes por cobrar."

                        if es_ajax:

                            return JsonResponse({'ok': False, 'error': err}, status=400)

                        messages.warning(request, err)

                        return redirect('vendedor')



                    monto_pago_raw = request.POST.get('monto_pago')

                    monto_pago = None

                    if monto_pago_raw:

                        try:

                            monto_pago = Decimal(str(monto_pago_raw))

                        except Exception:

                            monto_pago = None



                    # Base de consumo gastronómico (alimentos y bebidas sujetos a IVA 19%)

                    base_consumo = monto_pago if (monto_pago and Decimal('0') < monto_pago < venta_abierta.total) else venta_abierta.total



                    # Opciones Dinámicas de Propina (0%, 10%, 15%, 20% o personalizada - EXENTA DE IVA Ley 20.918)

                    porcentaje_propina = 0

                    monto_propina_calculada = Decimal('0')

                    pct_raw = request.POST.get('porcentaje_propina')

                    monto_propina_raw = request.POST.get('monto_propina')

                    incluir_propina = request.POST.get('incluir_propina') in ['1', 'true', 'on', True]



                    if pct_raw is not None and str(pct_raw).strip() != '':

                        try:

                            porcentaje_propina = max(0, min(100, int(pct_raw)))

                            monto_propina_calculada = Decimal(str(int(round(base_consumo * Decimal(str(porcentaje_propina)) / Decimal('100')))))

                        except (ValueError, TypeError):

                            porcentaje_propina = 0

                    elif monto_propina_raw is not None and str(monto_propina_raw).strip() != '':

                        try:

                            monto_propina_calculada = max(Decimal('0'), Decimal(str(monto_propina_raw)))

                            if base_consumo > 0:

                                porcentaje_propina = int(round((monto_propina_calculada / base_consumo) * Decimal('100')))

                        except Exception:

                            monto_propina_calculada = Decimal('0')

                    elif incluir_propina:

                        porcentaje_propina = 10

                        monto_propina_calculada = Decimal(str(int(round(base_consumo * Decimal('0.10')))))



                    # Soporte para División de Cuentas y Abonos Parciales (Split Bill)

                    if monto_pago and Decimal('0') < monto_pago < venta_abierta.total:

                        monto_abono = monto_pago

                        total_con_propina = monto_abono + monto_propina_calculada

                        monto_final, ajuste_redondeo = calcular_redondeo_ley_20956(total_con_propina, metodo_pago)

                        saldo_restante = max(Decimal('0'), venta_abierta.total - monto_pago)



                        venta_parcial = Venta.objects.create(

                            caja=caja_activa,

                            cajero=request.user,

                            punto_venta=local_operativo,

                            venta_origen=venta_abierta,

                            modalidad='MESA',

                            mesa=mesa_obj,

                            metodo_pago=metodo_pago,

                            propina=monto_propina_calculada,

                            porcentaje_propina=porcentaje_propina,

                            total_sin_redondeo=total_con_propina,

                            redondeo_ley_20956=ajuste_redondeo,

                            total=monto_final,

                            estado='PAGADA'

                        )

                        emitir_comprobante_venta(venta_parcial, usuario_emisor=request.user)



                        venta_abierta.monto_abonado_parcial = (venta_abierta.monto_abonado_parcial or Decimal('0.00')) + monto_abono

                        venta_abierta.total = saldo_restante

                        venta_abierta.save()



                        # La mesa permanece ocupada con el saldo pendiente restante

                        mesa_obj.estado = 'OCUPADA'

                        mesa_obj.save(update_fields=['estado'])



                        msg_ok = f"Abono parcial de ${int(monto_final):,} CLP registrado para {mesa_obj.identificador}. Saldo pendiente de la mesa: ${int(saldo_restante):,} CLP."

                        if es_ajax:

                            return JsonResponse({'ok': True, 'es_parcial': True, 'mensaje': msg_ok, 'saldo_restante': float(saldo_restante), 'venta_id': venta_parcial.id, 'propina': float(monto_propina_calculada)})

                        messages.success(request, msg_ok)

                        return redirect('vendedor')



                    # Liquidación total de la mesa

                    monto_consumo_total = venta_abierta.total

                    total_con_propina = monto_consumo_total + monto_propina_calculada

                    monto_final, ajuste_redondeo = calcular_redondeo_ley_20956(total_con_propina, metodo_pago)



                    venta_abierta.caja = caja_activa

                    venta_abierta.cajero = request.user

                    venta_abierta.propina = monto_propina_calculada

                    venta_abierta.porcentaje_propina = porcentaje_propina

                    venta_abierta.total_sin_redondeo = total_con_propina

                    venta_abierta.redondeo_ley_20956 = ajuste_redondeo

                    venta_abierta.total = monto_final

                    venta_abierta.metodo_pago = metodo_pago

                    venta_abierta.estado = 'PAGADA'

                    venta_abierta.save()



                    emitir_comprobante_venta(venta_abierta, usuario_emisor=request.user)

                    mesa_obj.liberar(forzar=True)



                    msg_ok = f"¡Mesa {mesa_obj.identificador} cobrada exitosamente (${int(monto_final):,} CLP - {metodo_pago}) y liberada!"

                    if es_ajax:

                        return JsonResponse({'ok': True, 'mensaje': msg_ok, 'venta_id': venta_abierta.id, 'total': float(monto_final)})

                    messages.success(request, msg_ok)

                return redirect('vendedor')



    ahora_dt = timezone.localtime()

    ahora_hora = ahora_dt.time()

    hora_apertura = datetime.time(10, 0)

    hora_cierre = datetime.time(18, 0)

    en_horario = (hora_apertura <= ahora_hora < hora_cierre)



    resumen_caja = None

    if caja_activa:

        from ventas.utils import calcular_resumen_caja

        resumen_caja = calcular_resumen_caja(caja_activa)



    ventas_recientes = []

    if caja_activa:

        ventas_recientes = Venta.objects.filter(caja=caja_activa).select_related('mesa').order_by('-fecha_hora')[:10]

    elif local_operativo:

        ventas_recientes = Venta.objects.filter(punto_venta=local_operativo).select_related('mesa').order_by('-fecha_hora')[:10]



    # Consultar Pedidos reales del día en el local para el Monitor en Vivo del Cajero

    pedidos_cajero_data = []

    kpi_en_desarrollo = 0

    kpi_cocina = 0

    kpi_barra = 0

    kpi_listos = 0



    if local_operativo:

        pedidos_hoy = Pedido.objects.filter(

            venta__punto_venta=local_operativo,

            creado_en__date=hoy

        ).exclude(estado='CANCELADO').exclude(

            venta__estado__in=['ANULADA', 'CANCELADA']

        ).exclude(

            venta__caja__jornada__estado='CERRADA'

        ).select_related(

            'venta__mesa', 'venta__cajero', 'venta__caja'

        ).prefetch_related('detalles__producto__categoria', 'tickets').order_by('-creado_en')



        for ped in pedidos_hoy:

            tiene_cocina = False

            tiene_barra = False

            items_serializados = []



            for det in ped.detalles.all():

                dest = det.producto.get_destino_operativo()

                if dest == 'BARRA':

                    tiene_barra = True

                    cat_slug = 'cafeteria'

                else:

                    tiene_cocina = True

                    cat_slug = 'cocinar'



                precio_unit = int(det.producto.precio_actual)

                items_serializados.append({

                    'nombre': det.producto.nombre,

                    'cant': det.cantidad,

                    'cat': cat_slug,

                    'destino': dest,

                    'precio': precio_unit,

                    'nota': det.observaciones or '',

                })



            if not tiene_cocina and not tiene_barra:

                tiene_cocina = True



            tiene_listo_parcial = (
                ped.estado not in ('LISTO', 'ENTREGADO')
                and (
                    (tiene_cocina and ped.estado_cocina == 'LISTO')
                    or (tiene_barra and ped.estado_barra == 'LISTO')
                )
            )

            if ped.estado == 'ENTREGADO':
                estado_ui = 'entregado'
            elif ped.estado == 'LISTO':
                estado_ui = 'listo'
                kpi_listos += 1
                kpi_en_desarrollo += 1
            else:
                kpi_en_desarrollo += 1
                if tiene_listo_parcial:
                    kpi_listos += 1
                if tiene_cocina:
                    kpi_cocina += 1
                if tiene_barra:
                    kpi_barra += 1
                estado_ui = 'cocina' if tiene_cocina else 'barra'

            if tiene_cocina and tiene_barra:
                destino_txt = 'Cocina & Barra'
            elif tiene_cocina:
                destino_txt = 'Cocina Caliente'
            else:
                destino_txt = 'Barra & Cafetería'

            if ped.venta.mesa:
                ident = ped.venta.mesa.identificador
                tipo_entrega = ident if 'mesa' in ident.lower() else f"Mesa {ident}"
            else:
                tipo_entrega = "Mostrador / Para Llevar"

            pedidos_cajero_data.append({
                'pedido_id': ped.id,
                'id': f"COM-{ped.id:04d}",
                'venta_id': ped.venta_id,
                'hora': timezone.localtime(ped.creado_en).strftime('%H:%M'),
                'tipoEntrega': tipo_entrega,
                'esMesa': bool(ped.venta.mesa),
                'items': items_serializados,
                'total': int(ped.venta.total),
                'ventaEstado': ped.venta.estado,
                'estado': estado_ui,
                'estadoBd': ped.estado,
                'estadoCocina': ped.estado_cocina,
                'estadoBarra': ped.estado_barra,
                'tieneListoParcial': tiene_listo_parcial,
                'estadoDisplay': ped.get_estado_display(),
                'tieneCocina': tiene_cocina,
                'tieneBarra': tiene_barra,
                'destino': destino_txt,
                'cajero': ped.venta.cajero.get_full_name() or ped.venta.cajero.username,
                'observacion': ped.observaciones or '',
            })



    # Estado en vivo de las mesas del salón para coordinación Cajero <-> Mesero

    mesas_salon_info = []

    mesas_libres_count = 0

    mesas_ocupadas_count = 0

    if local_operativo:

        mesas_qs = Mesa.objects.filter(punto_venta=local_operativo).order_by('id')

        ventas_abiertas_map = {

            va.mesa_id: va

            for va in Venta.objects.filter(punto_venta=local_operativo, estado='ABIERTA', mesa__isnull=False)

        }

        pedidos_activos_por_mesa = {}

        for p_act in Pedido.objects.filter(

            venta__punto_venta=local_operativo,

            venta__mesa__isnull=False,

            creado_en__date=hoy,

            estado__in=['PENDIENTE', 'EN_PREPARACION', 'LISTO']

        ).select_related('venta'):

            m_id = p_act.venta.mesa_id

            pedidos_activos_por_mesa[m_id] = pedidos_activos_por_mesa.get(m_id, 0) + 1



        for m in mesas_qs:

            if m.estado == 'HABILITADA':

                mesas_libres_count += 1

            elif m.estado == 'OCUPADA':

                mesas_ocupadas_count += 1

            va = ventas_abiertas_map.get(m.id)

            mesas_salon_info.append({

                'id': m.id,

                'identificador': m.identificador,

                'capacidad': m.capacidad,

                'estado': m.estado,

                'tiene_deuda_abierta': bool(va),

                'total_abierto': int(va.total) if va else 0,

                'venta_abierta_id': va.id if va else None,

                'pedidos_activos': pedidos_activos_por_mesa.get(m.id, 0),

            })



    context = {

        "jornada_activa": jornada_activa,

        "caja_activa": caja_activa,

        "resumen_caja": resumen_caja,

        "ventas_recientes": ventas_recientes,

        "punto_venta": local_operativo,

        "usuario": request.user,

        "hoy_str": hoy.strftime("%d/%m/%Y"),

        "ahora_hora_str": ahora_dt.strftime("%H:%M"),

        "en_horario": en_horario,

        "horario_oficial": "10:00 a 18:00",

        "pedidos_cajero_json": json.dumps(pedidos_cajero_data),

        "kpi_en_desarrollo": kpi_en_desarrollo,

        "kpi_cocina": kpi_cocina,

        "kpi_barra": kpi_barra,

        "kpi_listos": kpi_listos,

        "mesas_salon_info": mesas_salon_info,

        "mesas_libres_count": mesas_libres_count,

        "mesas_ocupadas_count": mesas_ocupadas_count,

    }

    return render(request, 'ventas/cajero/vendedor.html', context)


@requiere_rol(['CAJERO', 'ADMINISTRADOR'])
def api_desbloquear_pin_pos(request):
    """Verifica o configura en servidor el PIN operativo cifrado del cajero o su contraseña de turno."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)

    permitido_ip, retry_after, _ = verificar_rate_limit_ip(
        request,
        namespace='api_desbloquear_pin_pos',
        max_requests=8,
        window_seconds=60,
        key_extra=str(request.user.id),
    )
    if not permitido_ip:
        resp_429 = JsonResponse(
            {'ok': False, 'error': 'Demasiados intentos de desbloqueo. Espera unos segundos.'},
            status=429,
        )
        resp_429['Retry-After'] = str(retry_after)
        return resp_429

    perfil = getattr(request.user, 'perfil', None)
    if not perfil:
        return JsonResponse({'ok': False, 'error': 'Perfil operativo no encontrado.'}, status=403)

    accion = (request.POST.get('accion') or 'desbloquear').strip().lower()
    if accion == 'configurar_pin':
        password = request.POST.get('password') or ''
        nuevo_pin = (request.POST.get('nuevo_pin') or '').strip()
        if not password or not request.user.check_password(password):
            return JsonResponse({'ok': False, 'error': 'Contraseña actual incorrecta.'}, status=403)
        if not (len(nuevo_pin) == 4 and nuevo_pin.isdigit()):
            return JsonResponse(
                {'ok': False, 'error': 'El PIN operativo debe tener exactamente 4 dígitos numéricos.'},
                status=400,
            )
        perfil.set_pin_operativo(nuevo_pin)
        return JsonResponse({'ok': True, 'mensaje': 'PIN operativo cifrado configurado correctamente.'})

    pin = (request.POST.get('pin') or '').strip()
    password = request.POST.get('password') or ''

    if pin:
        if not (len(pin) == 4 and pin.isdigit()):
            return JsonResponse({'ok': False, 'error': 'El PIN debe tener 4 dígitos numéricos.'}, status=400)
        if not perfil.pin_operativo_hash:
            return JsonResponse(
                {
                    'ok': False,
                    'error': 'Aún no has configurado un PIN cifrado. Usa "Configurar PIN" o desbloquea con tu contraseña de turno.',
                },
                status=403,
            )
        if not perfil.check_pin_operativo(pin):
            return JsonResponse({'ok': False, 'error': 'PIN operativo incorrecto.'}, status=403)
        return JsonResponse({'ok': True, 'mensaje': 'Terminal de caja desbloqueado exitosamente.'})

    if password:
        if not request.user.check_password(password):
            return JsonResponse({'ok': False, 'error': 'Contraseña de turno incorrecta.'}, status=403)
        return JsonResponse({'ok': True, 'mensaje': 'Terminal de caja desbloqueado exitosamente.'})

    return JsonResponse({'ok': False, 'error': 'Ingresa tu PIN operativo o contraseña de turno.'}, status=400)


@requiere_rol(['CAJERO'])

def abrir_jornada(request):

    """

    RF02: El primer cajero (o administrador) abre la jornada diaria de operaciones del parque.

    Simultáneamente se inicializa la caja individual del primer cajero (RF03).

    """

    if request.method == 'POST':

        perfil = getattr(request.user, 'perfil', None)

        if not perfil or not perfil.punto_venta_actual:

            messages.error(request, "No tienes un Punto de Venta asignado a tu perfil. Solicita al Administrador que te asigne un puesto de trabajo antes de abrir la jornada y la caja.")

            return redirect('vendedor')



        with transaction.atomic():

            hoy = timezone.localdate()

            jornada_activa = Jornada.objects.filter(estado='ABIERTA', fecha=hoy).first()

            if jornada_activa:

                messages.info(request, f"Ya existe una jornada operativa abierta hoy (Jornada #{jornada_activa.id}). Te incorporas a ella.")

                return redirect('vendedor')



            observaciones = request.POST.get('observaciones', '').strip()

            monto_apertura_raw = request.POST.get('monto_apertura', '').strip()

            try:

                monto_apertura = float(monto_apertura_raw) if monto_apertura_raw else 0.0

                if monto_apertura < 0:

                    monto_apertura = 0.0

            except ValueError:

                monto_apertura = 0.0



            # Protección integral de contingencia: cierra jornadas/cajas/cuentas/pedidos/mesas pendientes de días previos

            proteger_contingencia_operativa(usuario=request.user)

            Mesa.objects.filter(estado='OCUPADA').update(estado='HABILITADA', fecha_ocupacion=None)



            # Recuperación de saldo protegido ante apagón previo si el cajero ingresa fondo $0

            contingencia_msg = ""

            caja_pendiente = Caja.objects.select_for_update().filter(

                punto_venta=perfil.punto_venta_actual,

                observaciones__contains='[TRASPASO_PENDIENTE]'

            ).exclude(jornada__fecha=hoy).order_by('-fecha_hora_apertura').first()

            if not caja_pendiente:

                caja_pendiente = Caja.objects.select_for_update().filter(

                    cajero=request.user,

                    observaciones__contains='[TRASPASO_PENDIENTE]'

                ).exclude(jornada__fecha=hoy).order_by('-fecha_hora_apertura').first()



            if caja_pendiente:

                saldo_traspaso = Decimal(str(caja_pendiente.total_efectivo_declarado or 0))

                caja_pendiente.observaciones = (caja_pendiente.observaciones or '').replace(

                    '[TRASPASO_PENDIENTE]', '[TRASPASO_APLICADO]'

                )

                caja_pendiente.save(update_fields=['observaciones'])

                if monto_apertura == 0.0 and saldo_traspaso > 0:

                    monto_apertura = float(saldo_traspaso)

                    observaciones = f"Fondo traspasado por contingencia eléctrica previa: ${int(saldo_traspaso):,} CLP (Caja #{caja_pendiente.id})"

                    contingencia_msg = f" ⚡ Contingencia por corte de energía resuelta: Se traspasó el saldo en efectivo de ${int(saldo_traspaso):,} CLP de la jornada anterior como fondo inicial."



            # Crear la Jornada diaria oficial de hoy

            nueva_jornada = Jornada.objects.create(

                usuario_apertura=request.user,

                estado='ABIERTA',

                observaciones=observaciones or f"Apertura de jornada por cajero {request.user.get_full_name() or request.user.username}"

            )



            # Crear la caja individual para este cajero (RF03)

            punto_venta = perfil.punto_venta_actual

            nombre_caja = f"Caja {punto_venta.nombre.split()[0]} - {request.user.first_name or request.user.username}"

            obs_caja = f"Apertura inicial con fondo: ${int(monto_apertura):,}" if monto_apertura > 0 else "Apertura inicial sin fondo"



            nueva_caja, _ = Caja.objects.get_or_create(

                jornada=nueva_jornada,

                cajero=request.user,

                defaults={

                    "nombre": nombre_caja,

                    "punto_venta": punto_venta,

                    "monto_apertura": monto_apertura,

                    "estado": 'ABIERTA',

                    "observaciones": obs_caja

                }

            )



        fondo_txt = f" con fondo inicial de ${int(monto_apertura):,}" if monto_apertura > 0 else ""

        messages.success(request, f"¡Jornada #{nueva_jornada.id} abierta con éxito! Tu {nueva_caja.nombre} quedó habilitada{fondo_txt}.{contingencia_msg}")

        return redirect('vendedor')



    return redirect('vendedor')





@requiere_rol(['CAJERO'])

def abrir_caja(request):

    """

    RF03: Cada cajero que ingresa a una jornada abierta habilita su propia caja individual.

    Si ya posee una caja abierta en esta jornada, la reutiliza y no crea duplicados.

    """

    if request.method == 'POST':

        perfil = getattr(request.user, 'perfil', None)

        if not perfil or not perfil.punto_venta_actual:

            messages.error(request, "No tienes un Punto de Venta asignado a tu perfil. Solicita al Administrador que te asigne un puesto de trabajo antes de abrir la caja.")

            return redirect('vendedor')



        proteger_contingencia_operativa(usuario=request.user)

        with transaction.atomic():

            hoy = timezone.localdate()

            jornada_activa = Jornada.objects.select_for_update().filter(estado='ABIERTA', fecha=hoy).first()

            if not jornada_activa:

                messages.error(request, "No existe una jornada abierta para el día de hoy. Debe realizarse la apertura de jornada primero.")

                return redirect('vendedor')



            # Reutilizar caja si ya existe una abierta para este cajero en esta jornada

            caja_existente = Caja.objects.select_for_update().filter(

                jornada=jornada_activa,

                cajero=request.user,

                estado='ABIERTA'

            ).first()



            if caja_existente:

                messages.info(request, f"Ya tienes una caja activa en esta jornada ({caja_existente.nombre}). Continuando turno.")

                return redirect('vendedor')



            monto_apertura_raw = request.POST.get('monto_apertura', '').strip()

            try:

                monto_apertura = float(monto_apertura_raw) if monto_apertura_raw else 0.0

                if monto_apertura < 0:

                    monto_apertura = 0.0

            except ValueError:

                monto_apertura = 0.0



            punto_venta = perfil.punto_venta_actual

            caja_pend = Caja.objects.select_for_update().filter(

                cajero=request.user,

                observaciones__contains='[TRASPASO_PENDIENTE]'

            ).exclude(jornada__fecha=hoy).order_by('-fecha_hora_apertura').first()

            obs_post = request.POST.get('observaciones', '').strip()

            if caja_pend:

                saldo_trasp = Decimal(str(caja_pend.total_efectivo_declarado or 0))

                caja_pend.observaciones = (caja_pend.observaciones or '').replace('[TRASPASO_PENDIENTE]', '[TRASPASO_APLICADO]')

                caja_pend.save(update_fields=['observaciones'])

                if monto_apertura == 0.0 and saldo_trasp > 0:

                    monto_apertura = float(saldo_trasp)

                    if not obs_post:

                        obs_post = f"Fondo traspasado por contingencia previa: ${int(saldo_trasp):,} CLP (Caja #{caja_pend.id})"

            nombre_caja = f"Caja {punto_venta.nombre.split()[0]} - {request.user.first_name or request.user.username}"

            observaciones = obs_post or (f"Fondo inicial: ${int(monto_apertura):,}" if monto_apertura > 0 else "Sin fondo inicial")



            nueva_caja, creada = Caja.objects.get_or_create(

                jornada=jornada_activa,

                cajero=request.user,

                defaults={

                    "nombre": nombre_caja,

                    "punto_venta": punto_venta,

                    "monto_apertura": monto_apertura,

                    "estado": 'ABIERTA',

                    "observaciones": observaciones

                }

            )



        if creada:

            fondo_txt = f" con fondo inicial de ${int(monto_apertura):,}" if monto_apertura > 0 else ""

            messages.success(request, f"¡Tu {nueva_caja.nombre} ha sido habilitada en la Jornada #{jornada_activa.id}{fondo_txt}!")

        else:

            messages.info(request, f"Ya tienes tu {nueva_caja.nombre} habilitada en la Jornada #{jornada_activa.id}.")

        return redirect('vendedor')



    return redirect('vendedor')





@requiere_rol(['CAJERO', 'ADMINISTRADOR'])

def cerrar_caja(request):

    """

    Subproceso de Cuadratura y Arqueo al Cerrar Caja (Semana 12).

    Desglose obligatorio de billetes ($20.000, $10.000, $5.000, $2.000, $1.000)

    y monedas ($500, $100, $50, $10, $5, $1) según pauta y Ley N° 20.956.

    """

    if request.method == 'POST':

        caja_id = request.POST.get('caja_id')

        if not caja_id:

            messages.error(request, "No se especificó la caja a cerrar.")

            return redirect('vendedor')



        with transaction.atomic():

            caja = get_object_or_404(Caja.objects.select_for_update(), id=caja_id)



            # Validación de permisos: cajero asignado o administrador

            es_admin = request.user.is_staff or request.user.is_superuser or (

                hasattr(request.user, 'perfil') and request.user.perfil.rol == 'ADMINISTRADOR'

            )

            if caja.cajero != request.user and not es_admin:

                messages.error(request, "No tienes permisos para cerrar la caja de otro colaborador.")

                return redirect('vendedor')



            if caja.estado == 'CERRADA':

                messages.warning(request, f"La {caja.nombre} ya se encuentra cerrada.")

                return redirect('vendedor')



            # Procesar desglose de billetes y monedas

            def parse_cant(field):

                raw = request.POST.get(field, '0').strip()

                try:

                    val = int(raw)

                    return max(0, val)

                except (ValueError, TypeError):

                    return 0



            caja.billetes_20000 = parse_cant('billetes_20000')

            caja.billetes_10000 = parse_cant('billetes_10000')

            caja.billetes_5000 = parse_cant('billetes_5000')

            caja.billetes_2000 = parse_cant('billetes_2000')

            caja.billetes_1000 = parse_cant('billetes_1000')



            caja.monedas_500 = parse_cant('monedas_500')

            caja.monedas_100 = parse_cant('monedas_100')

            caja.monedas_50 = parse_cant('monedas_50')

            caja.monedas_10 = parse_cant('monedas_10')

            caja.monedas_5 = parse_cant('monedas_5')

            caja.monedas_1 = parse_cant('monedas_1')



            obs_cierre = request.POST.get('observaciones_cierre', '').strip()

            if obs_cierre:

                caja.observaciones = (caja.observaciones or '') + f"\n[Cierre por {request.user.username}]: {obs_cierre}"



            # Resumen financiero y comparación de cuadratura

            from ventas.utils import calcular_resumen_caja

            resumen = calcular_resumen_caja(caja)



            total_contado = caja.calcular_total_arqueo()

            total_esperado = resumen['total_efectivo_esperado']

            diferencia = Decimal(str(total_contado)) - total_esperado



            caja.total_efectivo_declarado = Decimal(str(total_contado))

            caja.total_efectivo_esperado = total_esperado

            caja.diferencia_cuadre = diferencia

            caja.monto_cierre = Decimal(str(total_contado))

            caja.fecha_hora_cierre = timezone.now()

            caja.estado = 'CERRADA'



            if diferencia == 0:

                caja.estado_cuadre = 'CUADRADA'

                msg_estado = "Cuadratura Exacta (Sin diferencias)"

                msg_func = messages.success

            elif diferencia > 0:

                caja.estado_cuadre = 'SOBRANTE'

                msg_estado = f"Sobrante de caja: +${int(diferencia):,} CLP".replace(',', '.')

                msg_func = messages.warning

            else:

                caja.estado_cuadre = 'FALTANTE'

                msg_estado = f"Faltante de caja: -${int(abs(diferencia)):,} CLP".replace(',', '.')

                msg_func = messages.error



            caja.save()



        msg_func(

            request,

            f"✅ ¡{caja.nombre} cerrada y arqueada exitosamente! "

            f"Efectivo contado: ${int(total_contado):,} CLP | "

            f"Esperado: ${int(total_esperado):,} CLP | "

            f"Resultado: {msg_estado}."

        )



        origen = request.POST.get('origen_redirect', '')

        if origen == 'administrador_local' and caja.punto_venta:

            return redirect('administrador_local', local_id=caja.punto_venta.id)

        elif origen == 'administrador':

            return redirect('administrador')

        return redirect('vendedor')



    return redirect('vendedor')





@requiere_rol(['ADMINISTRADOR'])

def cerrar_jornada(request):

    """

    Cierre de Jornada Operativa Diaria (Semana 12).

    Permite al supervisor/administrador finalizar la jornada diaria

    validando que todas las cajas del día estén cerradas y cuadradas.

    """

    if request.method == 'POST':

        jornada_id = request.POST.get('jornada_id')

        if not jornada_id:

            messages.error(request, "No se especificó la jornada a cerrar.")

            return redirect('administrador')



        jornada = get_object_or_404(Jornada, id=jornada_id)



        if jornada.estado == 'CERRADA':

            messages.warning(request, f"La Jornada #{jornada.id} ya se encuentra cerrada.")

            return redirect('administrador')



        # Verificar si quedan cajas abiertas asociadas a esta jornada

        cajas_abiertas_list = list(jornada.cajas.filter(estado='ABIERTA'))

        forzar = request.POST.get('forzar_cierre') == '1'



        if cajas_abiertas_list and not forzar:

            nombres = ", ".join([c.nombre for c in cajas_abiertas_list])

            messages.error(

                request,

                f"No es posible cerrar la jornada porque aún hay {len(cajas_abiertas_list)} caja(s) abierta(s): {nombres}. "

                f"Todas las cajas deben cerrarse y arquearse antes del cierre de jornada."

            )

            return redirect('administrador')



        # Auditoría Forense Obligatoria si se fuerza el cierre con cajas abiertas

        if cajas_abiertas_list and forzar:

            nombres = ", ".join([c.nombre for c in cajas_abiertas_list])

            pv_ref = cajas_abiertas_list[0].punto_venta if cajas_abiertas_list[0].punto_venta else PuntoVenta.objects.first()

            AlertaTraslado.objects.create(

                empleado=request.user,

                punto_venta_origen=pv_ref,

                punto_venta_destino=pv_ref,

                autorizado_por=request.user,

                motivo=f"[ALERTA AUDITORÍA: CIERRE FORZADO DE JORNADA #{jornada.id}] Cajas forzadas sin arquear: {nombres}. Requiere arqueo físico urgente por supervisión."[:255]

            )



        obs = request.POST.get('observaciones_cierre', '').strip()

        if obs:

            jornada.observaciones = (jornada.observaciones or '') + f"\n[Cierre Jornada por {request.user.username}]: {obs}"



        # Cerrar y proteger cajas remanentes, cuentas sin cobrar, pedidos en cola y mesas al finalizar jornada

        cerrar_operaciones_de_jornada(

            jornada,

            usuario=request.user,

            motivo=obs or 'cierre oficial de jornada por supervisión'

        )



        jornada.estado = 'CERRADA'

        jornada.fecha_hora_cierre = timezone.now()

        jornada.usuario_cierre = request.user

        jornada.save()



        messages.success(

            request,

            f"🔒 ¡Jornada #{jornada.id} ({jornada.fecha.strftime('%d/%m/%Y')}) cerrada oficialmente con éxito por supervisión!"

        )

        return redirect('administrador')



    return redirect('administrador')





@requiere_rol(['CAJERO'])

def crear_ticket(request):

    """Terminal POS de venta rápida y cobro con soporte para Precios Especiales y Convenios (RF07)"""

    proteger_contingencia_operativa(usuario=request.user)

    hoy = timezone.localdate()

    ahora_dt = timezone.localtime()

    ahora_hora = ahora_dt.time()

    hora_apertura = datetime.time(10, 0)

    hora_cierre = datetime.time(18, 0)

    en_horario = (hora_apertura <= ahora_hora < hora_cierre)



    jornada_activa = Jornada.objects.select_related('usuario_apertura').filter(estado='ABIERTA', fecha=hoy).first()

    caja_activa = None

    if jornada_activa:

        caja_activa = Caja.objects.select_related('punto_venta', 'cajero').filter(

            jornada=jornada_activa,

            cajero=request.user,

            estado='ABIERTA'

        ).first()



    if not jornada_activa or not caja_activa:

        if request.method == 'POST' and (request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')):

            return JsonResponse({'ok': False, 'error': 'Debes tener jornada y caja individual abierta antes de emitir tickets.'}, status=400)

        messages.warning(request, "Debes tener tu jornada del día y caja individual abierta antes de emitir tickets.")

        return redirect('vendedor')



    perfil = getattr(request.user, 'perfil', None)

    punto_venta = perfil.punto_venta_actual if (perfil and perfil.punto_venta_actual) else PuntoVenta.objects.filter(activo=True).first()



    # Procesar Venta POS real (RF07)

    if request.method == 'POST':

        items_raw = request.POST.get('items_json', '[]')

        metodo_pago = request.POST.get('metodo_pago', 'EFECTIVO').upper()

        if metodo_pago not in ['EFECTIVO', 'DEBITO', 'CREDITO', 'TRANSFERENCIA']:

            metodo_pago = 'EFECTIVO'



        try:

            items_lista = json.loads(items_raw)

        except Exception:

            items_lista = []



        if not items_lista:

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                return JsonResponse({'ok': False, 'error': 'El pedido no contiene ítems para procesar.'}, status=400)

            messages.warning(request, "El pedido no contiene ítems para procesar.")

            return redirect('crear_ticket')



        with transaction.atomic():

            caja = Caja.objects.select_for_update().filter(id=caja_activa.id).first()

            if not caja or caja.estado != 'ABIERTA':

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                    return JsonResponse({'ok': False, 'error': 'La caja individual no se encuentra abierta.'}, status=400)

                messages.error(request, "Tu caja individual no se encuentra abierta.")

                return redirect('vendedor')



            lineas_calculadas = []

            subtotal_bruto = Decimal('0')



            for it in items_lista:

                p_id = it.get('producto_id') or it.get('id')

                p_nom = it.get('nombre')

                p_cant = it.get('cantidad', 1)

                p_precio_solicitado = it.get('precio_especial')

                p_conv_id = it.get('convenio_id')

                p_motivo = (it.get('motivo_precio_especial') or it.get('motivo') or '').strip()



                prod = None

                if p_id:

                    prod = Producto.objects.select_for_update().filter(id=p_id).first()

                if not prod and p_nom:

                    prod = Producto.objects.select_for_update().filter(nombre=p_nom).first()



                if not prod:

                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                        return JsonResponse({'ok': False, 'error': f"El producto '{p_nom or p_id}' no existe en la base de datos."}, status=400)

                    messages.error(request, f"El producto '{p_nom or p_id}' no existe en el catálogo.")

                    return redirect('crear_ticket')



                # RF15: Validación estricta de disponibilidad del producto en el punto de venta de la caja

                pv_caja = caja.punto_venta if caja else punto_venta

                try:

                    validar_disponibilidad_producto(prod, pv_caja)

                except ValidationError as ve:

                    err_msg = ve.message if hasattr(ve, 'message') else str(ve)

                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                        return JsonResponse({'ok': False, 'error': err_msg}, status=400)

                    messages.error(request, err_msg)

                    return redirect('crear_ticket')



                precio_req_val = None

                if p_precio_solicitado is not None:

                    try:

                        p_dec = Decimal(str(p_precio_solicitado))

                        if p_dec != prod.precio_base:

                            precio_req_val = p_dec

                    except Exception:

                        pass



                if precio_req_val is not None and not p_motivo:

                    err_msg = "Debes especificar un motivo explícito para aplicar un precio especial manual."

                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                        return JsonResponse({'ok': False, 'error': err_msg}, status=400)

                    messages.error(request, err_msg)

                    return redirect('crear_ticket')



                try:

                    calc = validar_y_calcular_precio_linea(

                        producto=prod,

                        cantidad=p_cant,

                        precio_solicitado=precio_req_val,

                        convenio_id=p_conv_id,

                        usuario=request.user,

                        motivo=p_motivo,

                        permite_manual=bool(precio_req_val is not None and p_motivo)

                    )

                except Exception as ve:

                    err_msg = ve.message if hasattr(ve, 'message') else str(ve)

                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                        return JsonResponse({'ok': False, 'error': err_msg}, status=400)

                    messages.error(request, f"Error en precio: {err_msg}")

                    return redirect('crear_ticket')



                subtotal_bruto += calc['subtotal']

                nota_item_pos = str(it.get('nota', '') or '').replace('\x00', '').strip()[:100]

                lineas_calculadas.append((prod, calc, nota_item_pos))



            modalidad = request.POST.get('modalidad', 'VENTA_RAPIDA').upper()

            if modalidad not in ['VENTA_RAPIDA', 'MESA', 'MOSTRADOR']:

                modalidad = 'VENTA_RAPIDA'

            mesa_id = request.POST.get('mesa_id')

            modo_cuenta = request.POST.get('modo_cuenta', 'PAGADA').upper()

            if modo_cuenta not in ['PAGADA', 'ABIERTA']:

                modo_cuenta = 'PAGADA'



            mesa_obj = None

            es_ajax_req = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')

            if modalidad == 'MESA':

                if not mesa_id:

                    if es_ajax_req:

                        return JsonResponse({'ok': False, 'error': 'Debe seleccionar una mesa válida para atención en salón (RF11.1).'}, status=400)

                    messages.error(request, 'Debe seleccionar una mesa válida para atención en salón.')

                    return redirect('crear_ticket')



                mesa_obj = Mesa.objects.select_for_update().filter(id=mesa_id, punto_venta=caja.punto_venta).first()

                if not mesa_obj:

                    if es_ajax_req:

                        return JsonResponse({'ok': False, 'error': 'La mesa seleccionada no existe o no pertenece a este local.'}, status=400)

                    messages.error(request, 'La mesa seleccionada no pertenece a este local.')

                    return redirect('crear_ticket')



                if mesa_obj.estado == 'INACTIVA':

                    if es_ajax_req:

                        return JsonResponse({'ok': False, 'error': f"La mesa {mesa_obj.identificador} se encuentra inactiva o en mantenimiento."}, status=400)

                    messages.error(request, f"La mesa {mesa_obj.identificador} se encuentra inactiva o en mantenimiento.")

                    return redirect('crear_ticket')



                if modo_cuenta == 'PAGADA' and Venta.objects.select_for_update().filter(mesa=mesa_obj, estado='ABIERTA').exists():

                    if es_ajax_req:

                        return JsonResponse({'ok': False, 'error': f"La mesa {mesa_obj.identificador} ya tiene una cuenta abierta en salón."}, status=400)

                    messages.error(request, f"La mesa {mesa_obj.identificador} ya tiene una cuenta abierta en salón.")

                    return redirect('crear_ticket')

            else:

                modalidad = 'VENTA_RAPIDA'

                mesa_obj = None

                modo_cuenta = 'PAGADA'



            # Validación y cálculo servidor-autoritativo de convenio QR Huésped / Cabaña (HMAC-SHA256 + select_for_update)

            conv_huesped_aplicar = None

            monto_bonificado_dec = Decimal('0')

            codigo_conv_raw = limpiar_texto_seguro(

                request.POST.get('codigo_convenio') or request.POST.get('codigo_qr') or '',

                max_length=120

            )

            if codigo_conv_raw:

                if ':' in codigo_conv_raw:

                    partes_conv = codigo_conv_raw.split(':', 1)

                    codigo_conv = partes_conv[0].strip()

                    firma_conv = partes_conv[1].strip()

                else:

                    codigo_conv = codigo_conv_raw

                    firma_conv = limpiar_texto_seguro(

                        request.POST.get('firma_convenio') or request.POST.get('firma') or '',

                        max_length=64

                    )

                conv_obj = ConvenioHuesped.objects.select_for_update().filter(codigo_qr__iexact=codigo_conv).first() if codigo_conv else None

                if conv_obj:

                    from ventas.utils import verificar_firma_qr_convenio

                    if not firma_conv or not verificar_firma_qr_convenio(conv_obj.codigo_qr, firma_conv):

                        err_hmac = 'Firma criptográfica HMAC-SHA256 del convenio QR faltante o inválida.'

                        if es_ajax_req:

                            return JsonResponse({'ok': False, 'tampered': True, 'error': err_hmac}, status=403)

                        messages.error(request, err_hmac)

                        return redirect('crear_ticket')

                    if not conv_obj.puede_consumir_hoy():

                        err_lim = 'El convenio de cabaña no está vigente hoy o alcanzó su límite diario.'

                        if es_ajax_req:

                            return JsonResponse({'ok': False, 'error': err_lim}, status=400)

                        messages.error(request, err_lim)

                        return redirect('crear_ticket')

                    if conv_obj.tipo_beneficio == 'DESAYUNO_INCLUIDO':

                        monto_bonificado_dec = subtotal_bruto

                    elif conv_obj.tipo_beneficio == 'DESCUENTO_PORCENTAJE':

                        pct_desc = max(Decimal('0'), min(Decimal('100'), Decimal(str(conv_obj.valor_descuento or 0))))

                        monto_bonificado_dec = Decimal(str(int(round(subtotal_bruto * pct_desc / Decimal('100')))))

                    elif conv_obj.tipo_beneficio == 'DESCUENTO_MONTO':

                        monto_bonificado_dec = min(subtotal_bruto, max(Decimal('0'), Decimal(str(conv_obj.valor_descuento or 0))))

                    conv_huesped_aplicar = conv_obj



            subtotal_efectivo = max(Decimal('0'), subtotal_bruto - monto_bonificado_dec)

            # Descuento comercial por Medio de Pago (Tarjeta Débito, Crédito, Banco) o Campaña de Temporada
            descuento_medio_pago = Decimal('0')
            campana_promo_aplicada = None
            for camp in OfertaTemporada.objects.filter(activa=True):
                if camp.es_vigente():
                    if camp.medio_pago_requerido in ['TODOS', metodo_pago]:
                        desc_cand = camp.calcular_descuento(subtotal_efectivo, medio_pago=metodo_pago)
                        if desc_cand > descuento_medio_pago:
                            descuento_medio_pago = desc_cand
                            campana_promo_aplicada = camp

            if descuento_medio_pago > Decimal('0'):
                subtotal_efectivo = max(Decimal('0'), subtotal_efectivo - descuento_medio_pago)
                if campana_promo_aplicada:
                    OfertaTemporada.objects.filter(id=campana_promo_aplicada.id).update(usos_actuales=models.F('usos_actuales') + 1)



            es_ronda_adicional = False

            if modalidad == 'MESA' and modo_cuenta == 'ABIERTA':

                venta_existente = Venta.objects.select_for_update().filter(

                    mesa=mesa_obj,

                    punto_venta=caja.punto_venta,

                    estado='ABIERTA'

                ).first()

                if venta_existente:

                    venta = venta_existente

                    venta.total += subtotal_efectivo

                    venta.total_sin_redondeo = (venta.total_sin_redondeo or Decimal('0')) + subtotal_efectivo

                    venta.save()

                    es_ronda_adicional = True

                else:

                    venta = Venta.objects.create(

                        caja=caja,

                        cajero=request.user,

                        punto_venta=caja.punto_venta,

                        modalidad='MESA',

                        mesa=mesa_obj,

                        metodo_pago=metodo_pago,

                        total=subtotal_efectivo,

                        total_sin_redondeo=subtotal_efectivo,

                        redondeo_ley_20956=Decimal('0'),

                        estado='ABIERTA'

                    )

                if mesa_obj.estado == 'HABILITADA':

                    mesa_obj.ocupar()

                elif mesa_obj.estado != 'OCUPADA':

                    mesa_obj.estado = 'OCUPADA'

                    mesa_obj.save(update_fields=['estado'])

            else:

                tiene_promo_moneda = any(

                    (prod and getattr(prod, 'tipo_oferta', '') == 'SEGUNDA_1') or

                    (calc.get('precio_aplicado') in [Decimal('1'), Decimal('5'), 1, 5])

                    for prod, calc, _ in lineas_calculadas

                )

                # Opciones Dinámicas de Propina (0%, 10%, 15%, 20% o personalizada - EXENTA DE IVA Ley 20.918)
                porcentaje_propina = 0
                monto_propina_calculada = Decimal('0')
                pct_raw = request.POST.get('porcentaje_propina')
                monto_propina_raw = request.POST.get('monto_propina')
                incluir_propina = request.POST.get('incluir_propina') in ['1', 'true', 'on', True]

                if pct_raw is not None and str(pct_raw).strip() != '':
                    try:
                        porcentaje_propina = max(0, min(100, int(pct_raw)))
                        monto_propina_calculada = Decimal(str(int(round(subtotal_efectivo * Decimal(str(porcentaje_propina)) / Decimal('100')))))
                    except (ValueError, TypeError):
                        porcentaje_propina = 0
                elif monto_propina_raw is not None and str(monto_propina_raw).strip() != '':
                    try:
                        monto_propina_calculada = max(Decimal('0'), Decimal(str(monto_propina_raw)))
                        if subtotal_efectivo > 0:
                            porcentaje_propina = int(round((monto_propina_calculada / subtotal_efectivo) * Decimal('100')))
                    except Exception:
                        monto_propina_calculada = Decimal('0')
                elif incluir_propina:
                    porcentaje_propina = 10
                    monto_propina_calculada = Decimal(str(int(round(subtotal_efectivo * Decimal('0.10')))))

                total_con_propina = subtotal_efectivo + monto_propina_calculada
                monto_final, ajuste_redondeo = calcular_redondeo_ley_20956(total_con_propina, metodo_pago, tiene_promo_moneda_fisica=tiene_promo_moneda)

                venta = Venta.objects.create(

                    caja=caja,

                    cajero=request.user,

                    punto_venta=caja.punto_venta,

                    modalidad=modalidad,

                    mesa=mesa_obj,

                    metodo_pago=metodo_pago,

                    propina=monto_propina_calculada,

                    porcentaje_propina=porcentaje_propina,

                    total=monto_final,

                    total_sin_redondeo=total_con_propina,

                    redondeo_ley_20956=ajuste_redondeo,

                    estado='PAGADA'

                )

                if modalidad == 'MESA' and mesa_obj:

                    if mesa_obj.estado == 'HABILITADA':

                        mesa_obj.ocupar()

                    elif mesa_obj.estado != 'OCUPADA':

                        mesa_obj.estado = 'OCUPADA'

                        mesa_obj.save(update_fields=['estado'])



            if modalidad == 'MESA' and mesa_obj:

                num_ronda = venta.pedidos.count() + 1

                obs_pedido = f"Pedido Caja POS (Ronda #{num_ronda}) para {mesa_obj.identificador} por {request.user.get_full_name() or request.user.username}"

            else:

                obs_pedido = f"Venta rápida POS #{venta.id} atendida por {request.user.get_full_name() or request.user.username}"



            pedido = Pedido.objects.create(

                venta=venta,

                estado='PENDIENTE',

                observaciones=obs_pedido

            )



            tiene_cocina = False

            tiene_barra = False



            for prod, calc, nota in lineas_calculadas:

                det = DetalleVenta.objects.create(

                    venta=venta,

                    producto=prod,

                    cantidad=calc['cantidad'],

                    precio_aplicado=calc['precio_aplicado'],

                    subtotal=calc['subtotal'],

                    precio_original=calc['precio_original'],

                    es_precio_especial=calc['es_precio_especial'],

                    motivo_precio_especial=calc['motivo'],

                    autorizado_por=calc['autorizado_por']

                )

                if calc['es_precio_especial']:

                    registrar_precio_especial_auditoria(venta, det, calc)



                nota_pedido = nota

                if calc['es_precio_especial']:

                    nota_pedido = f"{nota_pedido} [{calc['motivo']}]".strip()



                DetallePedido.objects.create(

                    pedido=pedido,

                    producto=prod,

                    cantidad=calc['cantidad'],

                    observaciones=nota_pedido

                )



                dest_op = prod.get_destino_operativo()

                if dest_op == 'BARRA':

                    tiene_barra = True

                else:

                    tiene_cocina = True



            if not tiene_cocina and not tiene_barra:

                tiene_cocina = True



            # RF08: Emisión clasificada por BD y comprobante de cliente

            ticket_info = emitir_tickets_comanda(pedido, usuario_emisor=request.user)

            comprobante = None

            if venta.estado == 'PAGADA':

                comprobante = emitir_comprobante_venta(venta, usuario_emisor=request.user)



            convenio_aplicado_en_venta = False

            if conv_huesped_aplicar and monto_bonificado_dec > Decimal('0'):

                ticket_ref_conv = ticket_info['tickets'][0] if ticket_info.get('tickets') else comprobante

                ConsumoHuesped.objects.create(

                    convenio=conv_huesped_aplicar,

                    ticket=ticket_ref_conv,

                    monto_original=subtotal_bruto,

                    monto_bonificado=monto_bonificado_dec,

                    monto_pagado=subtotal_efectivo,

                    registrado_por=request.user,

                    observaciones=f"Descuento aplicado atómico en POS: {conv_huesped_aplicar.get_tipo_beneficio_display()}"

                )

                convenio_aplicado_en_venta = True



            tickets_generados = [t.codigo for t in ticket_info['tickets']]

            if comprobante:

                tickets_generados.append(comprobante.codigo)



            zonas_despacho = []

            if ticket_info.get('tiene_cocina'):

                zonas_despacho.append('Cocina Caliente')

            if ticket_info.get('tiene_barra'):

                zonas_despacho.append('Barra & Cafetería')

            destino_resumen = ' y '.join(zonas_despacho) if zonas_despacho else 'Producción'



            if es_ajax_req:

                return JsonResponse({

                    'ok': True,

                    'venta_id': venta.id,

                    'pedido_id': pedido.id,

                    'codigo_comanda': f"COM-{pedido.id:04d}",

                    'total': float(venta.total),

                    'total_sin_redondeo': float(venta.total_sin_redondeo or venta.total),

                    'propina': float(getattr(venta, 'propina', 0)),

                    'porcentaje_propina': int(getattr(venta, 'porcentaje_propina', 0)),

                    'redondeo': float(venta.redondeo_ley_20956 or 0),

                    'tickets': tickets_generados,

                    'modalidad': venta.modalidad,

                    'modo_cuenta': venta.estado,

                    'destino': destino_resumen,

                    'ubicacion': venta.get_ubicacion_despacho(),

                    'convenio_aplicado_en_venta': convenio_aplicado_en_venta,

                    'mensaje': (

                        f"¡Pedido enviado a {mesa_obj.identificador} y derivado a {destino_resumen}!"

                        if venta.estado == 'ABIERTA'

                        else f"¡Venta POS #{venta.id} registrada exitosamente por ${int(venta.total):,} CLP!"

                    )

                })



            messages.success(request, f"¡Venta #{venta.id} emitida exitosamente por ${int(venta.total):,} CLP! Comanda derivada a {destino_resumen}.")

            return redirect('crear_ticket')



    perfil = getattr(request.user, 'perfil', None)

    punto_venta = perfil.punto_venta_actual if (perfil and perfil.punto_venta_actual) else PuntoVenta.objects.filter(activo=True).first()

    if caja_activa and caja_activa.punto_venta:

        punto_venta = caja_activa.punto_venta



    if punto_venta:

        productos_activos = punto_venta.get_productos_disponibles().select_related('categoria').prefetch_related('precios_especiales')

    else:

        productos_activos = Producto.objects.filter(activo=True).select_related('categoria').prefetch_related('precios_especiales')

    convenios_activos = PrecioEspecial.objects.filter(activo=True).select_related('producto')

    trabajadores_activos = User.objects.filter(is_active=True, perfil__activo=True).select_related('perfil', 'perfil__punto_venta_actual').order_by('first_name', 'username')

    mesas_disponibles = Mesa.objects.filter(punto_venta=punto_venta, estado='HABILITADA').order_by('identificador') if punto_venta else Mesa.objects.none()



    # Mesas operativas del salón (libres y en atención) para vincular clientes/pedidos desde Caja

    mesas_salon_pos = []

    if punto_venta:

        ventas_abiertas_ids = set(

            Venta.objects.filter(punto_venta=punto_venta, estado='ABIERTA', mesa__isnull=False).values_list('mesa_id', flat=True)

        )

        for m in Mesa.objects.filter(punto_venta=punto_venta).exclude(estado='INACTIVA').order_by('id'):

            mesas_salon_pos.append({

                'id': m.id,

                'identificador': m.identificador,

                'capacidad': m.capacidad,

                'estado': m.estado,

                'tiene_deuda_abierta': m.id in ventas_abiertas_ids,

            })



    # Serializar catálogo real de BD para el terminal POS

    productos_pos_list = []

    for p in productos_activos:

        dest = p.get_destino_operativo()

        nom_l = (p.nombre or '').lower()

        cat_l = (p.categoria.nombre if p.categoria else '').lower()

        if dest == 'BARRA':

            if any(k in nom_l or k in cat_l for k in ['café', 'cafe', 'té', 'te', 'cappuccino', 'moka', 'espresso', 'jugo natural', 'limonada', 'frambuesa', 'infus', 'barista']):

                cat_slug = 'cafeteria'

                cat_badge = 'Barra: Preparado'

            else:

                cat_slug = 'envasada'

                cat_badge = 'Bebida / Barra'

        else:

            if any(k in cat_l or k in nom_l for k in ['preparada', 'empanada', 'medialuna', 'muffin', 'pan ', 'sandwich']):

                cat_slug = 'preparada'

                cat_badge = 'Comida Preparada'

            else:

                cat_slug = 'cocinar'

                cat_badge = 'Cocina Caliente'



        productos_pos_list.append({

            'id': p.id,

            'nombre': p.nombre,

            'descripcion': p.descripcion or f"Especialidad disponible en {punto_venta.nombre if punto_venta else 'Parque Safari'}.",

            'cat': cat_slug,

            'cat_badge': cat_badge,

            'destino': dest,

            'precio': int(p.precio_actual),

            'precio_base': int(p.precio_base),

            'en_oferta': p.en_oferta,

            'tipo_oferta': p.tipo_oferta if p.en_oferta else 'NINGUNA',

            'precio_oferta': int(p.precio_oferta) if (p.en_oferta and p.precio_oferta is not None) else None,

            'descuento_pct': float(p.descuento_pct or 0) if p.en_oferta else 0,

            'desc_oferta': p.descripcion_oferta or '',
            'limite_oferta_por_ticket': getattr(p, 'limite_oferta_por_ticket', 0),
            'cantidad_minima_oferta': getattr(p, 'cantidad_minima_oferta', 2),
        })



    mesa_preseleccionada_id = request.GET.get('mesa_id', '').strip()



    context = {

        "mesas_disponibles": mesas_disponibles,

        "mesas_salon_pos": mesas_salon_pos,

        "mesa_preseleccionada_id": mesa_preseleccionada_id,

        "jornada_activa": jornada_activa,

        "caja_activa": caja_activa,

        "punto_venta": punto_venta,

        "usuario": request.user,

        "hoy_str": hoy.strftime("%d/%m/%Y"),

        "ahora_hora_str": ahora_dt.strftime("%H:%M"),

        "en_horario": en_horario,

        "horario_oficial": "10:00 a 18:00",

        "productos_activos": productos_activos,

        "productos_pos_list": productos_pos_list,

        "productos_pos_json": json.dumps({str(item['id']): item for item in productos_pos_list}),

        "convenios_activos": convenios_activos,

        "trabajadores_activos": trabajadores_activos,
        "ofertas_pos_list": [
            {
                'id': o.id,
                'nombre': o.nombre,
                'tipo_campana': o.tipo_campana,
                'medio_pago_requerido': o.medio_pago_requerido,
                'banco_convenio': o.banco_convenio or '',
                'descuento_porcentaje': float(o.descuento_porcentaje),
                'monto_minimo_compra': float(o.monto_minimo_compra),
                'tope_descuento_clp': float(o.tope_descuento_clp),
            } for o in OfertaTemporada.objects.filter(activa=True) if o.es_vigente()
        ],
        "ofertas_pos_json": json.dumps([
            {
                'id': o.id,
                'nombre': o.nombre,
                'tipo_campana': o.tipo_campana,
                'medio_pago_requerido': o.medio_pago_requerido,
                'banco_convenio': o.banco_convenio or '',
                'descuento_porcentaje': float(o.descuento_porcentaje),
                'monto_minimo_compra': float(o.monto_minimo_compra),
                'tope_descuento_clp': float(o.tope_descuento_clp),
            } for o in OfertaTemporada.objects.filter(activa=True) if o.es_vigente()
        ]),

    }

    return render(request, 'ventas/cajero/vendedor_crear_ticket.html', context)





@requiere_rol(['ADMINISTRADOR'])

def administrador(request):

    """Panel General de Administración y Supervisión de Locales"""

    proteger_contingencia_operativa(usuario=request.user)

    if request.method == 'POST':

        accion = request.POST.get('accion')

        if accion == 'marcar_leida_alerta':

            alerta_id = request.POST.get('alerta_id')

            if alerta_id == 'todas':

                AlertaTraslado.objects.filter(leida=False).update(leida=True)

            elif alerta_id:

                AlertaTraslado.objects.filter(id=alerta_id).update(leida=True)



            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                pendientes = AlertaTraslado.objects.filter(leida=False).count()

                return JsonResponse({'status': 'ok', 'pendientes': pendientes})

            return redirect('administrador')



        elif accion == 'crear_local':

            nombre = request.POST.get('nombre', '').strip()

            tipo = request.POST.get('tipo', '').strip()

            descripcion = request.POST.get('descripcion', '').strip()

            icono = request.POST.get('icono', '').strip() or 'bi-shop'

            color = request.POST.get('color', '').strip() or '#c62828'



            if not nombre:

                msg = "Debes ingresar un nombre para el nuevo local gastronómico."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                    return JsonResponse({'status': 'error', 'mensaje': msg}, status=400)

                messages.error(request, msg)

                return redirect('administrador')



            if PuntoVenta.objects.filter(nombre__iexact=nombre).exists():

                msg = f"Ya existe un local gastronómico registrado con el nombre '{nombre}'."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                    return JsonResponse({'status': 'error', 'mensaje': msg}, status=400)

                messages.error(request, msg)

                return redirect('administrador')



            nuevo_local = PuntoVenta.objects.create(

                nombre=nombre,

                tipo=tipo or "Punto de Venta",

                descripcion=descripcion or f"Local gastronómico operativo '{nombre}' en Parque Safari.",

                icono=icono,

                color=color,

                activo=True

            )

            msg_exito = f"¡Local gastronómico '{nuevo_local.nombre}' creado exitosamente! Ya se encuentra disponible para asignación de colaboradores y auditoría."

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                return JsonResponse({'status': 'ok', 'mensaje': msg_exito, 'local_id': nuevo_local.id, 'nombre': nuevo_local.nombre})

            messages.success(request, msg_exito)

            return redirect('administrador')



        elif accion == 'modificar_local':

            local_id = request.POST.get('local_id')

            try:

                pv = PuntoVenta.objects.get(id=int(local_id))

            except (ValueError, TypeError, PuntoVenta.DoesNotExist):

                msg = "El local gastronómico especificado no existe."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                    return JsonResponse({'status': 'error', 'mensaje': msg}, status=404)

                messages.error(request, msg)

                return redirect('administrador')



            nombre = request.POST.get('nombre', '').strip()

            tipo = request.POST.get('tipo', '').strip()

            descripcion = request.POST.get('descripcion', '').strip()

            icono = request.POST.get('icono', '').strip() or pv.icono or 'bi-shop'

            color = request.POST.get('color', '').strip() or pv.color or '#c62828'

            activo_raw = request.POST.get('activo', 'true')

            activo = activo_raw in ['true', 'True', '1', 'on']



            if not nombre:

                msg = "El nombre del local gastronómico no puede estar en blanco."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                    return JsonResponse({'status': 'error', 'mensaje': msg}, status=400)

                messages.error(request, msg)

                return redirect('administrador')



            if PuntoVenta.objects.filter(nombre__iexact=nombre).exclude(id=pv.id).exists():

                msg = f"Ya existe otro local registrado con el nombre '{nombre}'."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                    return JsonResponse({'status': 'error', 'mensaje': msg}, status=400)

                messages.error(request, msg)

                return redirect('administrador')



            # Blindaje RF14: No desactivar si tiene cajas o ventas abiertas

            if not activo and pv.activo:

                if pv.tiene_cajas_abiertas() or pv.tiene_ventas_abiertas():

                    msg = f"No es posible desactivar el local '{pv.nombre}' mientras tenga cajas abiertas o cuentas en consumo activas (RF14)."

                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                        return JsonResponse({'status': 'error', 'mensaje': msg}, status=400)

                    messages.error(request, msg)

                    return redirect('administrador')



            pv.nombre = nombre

            pv.tipo = tipo or "Punto de Venta"

            pv.descripcion = descripcion or pv.descripcion

            pv.icono = icono

            pv.color = color

            pv.activo = activo

            pv.save()



            msg_exito = f"¡Local gastronómico '{pv.nombre}' actualizado correctamente!"

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                return JsonResponse({'status': 'ok', 'mensaje': msg_exito, 'local_id': pv.id, 'activo': pv.activo})

            messages.success(request, msg_exito)

            return redirect('administrador')



        elif accion == 'eliminar_local':

            local_id = request.POST.get('local_id')

            try:

                pv = PuntoVenta.objects.get(id=int(local_id))

            except (ValueError, TypeError, PuntoVenta.DoesNotExist):

                msg = "El local gastronómico a eliminar no existe."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                    return JsonResponse({'status': 'error', 'mensaje': msg}, status=404)

                messages.error(request, msg)

                return redirect('administrador')



            nombre_local = pv.nombre



            # Blindaje RF14: No permitir eliminar ni desactivar si hay cajas o ventas abiertas

            if pv.tiene_cajas_abiertas() or pv.tiene_ventas_abiertas():

                msg = f"No es posible eliminar o desactivar el local '{nombre_local}' porque tiene cajas abiertas o cuentas en consumo activas (RF14)."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                    return JsonResponse({'status': 'error', 'mensaje': msg}, status=400)

                messages.error(request, msg)

                return redirect('administrador')



            # Desasignar colaboradores de este local

            PerfilEmpleado.objects.filter(punto_venta_actual=pv).update(punto_venta_actual=None)



            # Si tiene transacciones o registros históricos: SOFT-DELETE obligatorio

            if pv.tiene_historial_operativo():

                pv.activo = False

                pv.save(update_fields=['activo'])

                msg_adv = f"El local '{nombre_local}' contiene transacciones y ventas históricas en auditoría. Ha sido desactivado e inactivado del servicio (soft-delete) para proteger los datos (RF14)."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                    return JsonResponse({'status': 'ok', 'modo': 'soft-delete', 'mensaje': msg_adv, 'local_id': pv.id, 'activo': False})

                messages.warning(request, msg_adv)

                return redirect('administrador')



            # Si no tiene historial: eliminación física limpia

            Mesa.objects.filter(punto_venta=pv).delete()

            pv.puntos_impresion.all().delete()

            pv.menus.all().delete()

            pv.delete()



            msg_exito = f"Local gastronómico '{nombre_local}' eliminado exitosamente del sistema."

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                return JsonResponse({'status': 'ok', 'modo': 'hard-delete', 'mensaje': msg_exito})

            messages.success(request, msg_exito)

            return redirect('administrador')



    locales = get_locales_data()

    total_ventas = sum(l["total_ventas"] for l in locales.values())

    total_tickets = sum(l["tickets_emitidos"] for l in locales.values())

    total_personal = sum(len(l["personal"]) for l in locales.values())

    ticket_promedio_global = round(total_ventas / total_tickets) if total_tickets else 0



    # Lista consolidada de personal

    personal_completo = []

    for loc_id, loc in locales.items():

        for p in loc["personal"]:

            personal_completo.append({**p, "local_nombre": loc["nombre"], "local_id": loc_id})



    # Alertas recientes de traslado de personal y conteo de no leídas

    alertas_traslado = AlertaTraslado.objects.select_related('empleado', 'punto_venta_origen', 'punto_venta_destino').order_by('-fecha_hora')[:5]

    total_alertas_no_leidas = AlertaTraslado.objects.filter(leida=False).count()



    hoy = timezone.localdate()

    ahora_dt = timezone.localtime()

    ahora_hora = ahora_dt.time()

    en_horario = (datetime.time(10, 0) <= ahora_hora < datetime.time(18, 0))



    # Semana 12: Jornada operativa y estado de cajas para supervisión

    jornada_activa = Jornada.objects.select_related('usuario_apertura', 'usuario_cierre').prefetch_related('cajas__cajero', 'cajas__punto_venta').filter(

        fecha=hoy

    ).order_by('-id').first()

    cajas_jornada = list(jornada_activa.cajas.all()) if jornada_activa else []

    cajas_abiertas_count = sum(1 for c in cajas_jornada if c.estado == 'ABIERTA')



    context = {

        "locales": locales.values(),

        "total_ventas": total_ventas,

        "total_tickets": total_tickets,

        "total_personal": total_personal,

        "ticket_promedio_global": ticket_promedio_global,

        "personal_completo": personal_completo,

        "alertas_traslado": alertas_traslado,

        "total_alertas_no_leidas": total_alertas_no_leidas,

        "jornada_activa": jornada_activa,

        "cajas_jornada": cajas_jornada,

        "cajas_abiertas_count": cajas_abiertas_count,

        "hoy_str": hoy.strftime("%d/%m/%Y"),

        "ahora_hora_str": ahora_dt.strftime("%H:%M"),

        "en_horario": en_horario,

        "horario_oficial": "10:00 a 18:00",

    }

    return render(request, 'ventas/administrador/administrador.html', context)





@requiere_rol(['ADMINISTRADOR'])

def administrador_local(request, local_id):

    """Página detallada de la jornada y personal de un local específico"""

    proteger_contingencia_operativa(usuario=request.user)

    if request.method == 'POST':

        accion = request.POST.get('accion')

        if accion == 'marcar_leida_alerta':

            alerta_id = request.POST.get('alerta_id')

            if alerta_id == 'todas':

                AlertaTraslado.objects.filter(

                    models.Q(punto_venta_origen_id=local_id) | models.Q(punto_venta_destino_id=local_id),

                    leida=False

                ).update(leida=True)

            elif alerta_id:

                AlertaTraslado.objects.filter(id=alerta_id).update(leida=True)



            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                pendientes = AlertaTraslado.objects.filter(

                    models.Q(punto_venta_origen_id=local_id) | models.Q(punto_venta_destino_id=local_id),

                    leida=False

                ).count()

                return JsonResponse({'status': 'ok', 'pendientes': pendientes})

            return redirect('administrador_local', local_id=local_id)



    locales = get_locales_data()

    if local_id not in locales:

        raise Http404("El local gastronómico solicitado no existe.")

    

    local = locales[local_id]



    hoy = timezone.localdate()

    ahora_dt = timezone.localtime()

    ahora_hora = ahora_dt.time()

    hora_apertura = datetime.time(10, 0)

    hora_cierre = datetime.time(18, 0)

    en_horario = (hora_apertura <= ahora_hora < hora_cierre)



    # Alertas de traslado que involucran a este local (salientes o entrantes)

    alertas_local = AlertaTraslado.objects.filter(

        models.Q(punto_venta_origen_id=local_id) | models.Q(punto_venta_destino_id=local_id)

    ).select_related('empleado', 'punto_venta_origen', 'punto_venta_destino').order_by('-fecha_hora')[:10]

    total_alertas_no_leidas = AlertaTraslado.objects.filter(

        models.Q(punto_venta_origen_id=local_id) | models.Q(punto_venta_destino_id=local_id),

        leida=False

    ).count()



    local_obj = PuntoVenta.objects.filter(id=local_id).first()

    from ventas.utils import calcular_tiempos_promedio_local

    promedios_tiempos = calcular_tiempos_promedio_local(punto_venta=local_obj)



    context = {

        "local": local,

        "locales": locales.values(),

        "alertas_local": alertas_local,

        "hoy_str": hoy.strftime("%d/%m/%Y"),

        "ahora_hora_str": ahora_dt.strftime("%H:%M"),

        "en_horario": en_horario,

        "horario_oficial": "10:00 a 18:00",

        "promedios_tiempos": promedios_tiempos,

    }

    return render(request, 'ventas/administrador/administrador_local.html', context)





def _validar_clave_colaborador(password, user_candidate=None):
    """Valida complejidad mínima (ISO/IEC 27400) y validadores oficiales de Django."""
    es_valida, msg_err = validar_complejidad_clave(password)
    if not es_valida:
        return msg_err
    try:
        validate_password(password, user=user_candidate)
    except ValidationError as exc:
        return exc.messages[0] if exc.messages else "La contraseña no cumple con los requisitos de seguridad institucional."
    return None


@requiere_rol(['ADMINISTRADOR'])

def administrador_trabajadores(request):

    """Gestión de Trabajadores (CRUD, minimización de datos, límite de 1 puesto de trabajo y alertas de traslado)"""

    if request.method == 'POST':

        permitido_ip, retry_after, _ = verificar_rate_limit_ip(
            request,
            namespace='admin_trabajadores_ip',
            max_requests=45,
            window_seconds=60,
        )
        if not permitido_ip:
            resp_429 = HttpResponse("Demasiadas operaciones administrativas desde tu IP. Espera unos segundos.", status=429)
            resp_429['Retry-After'] = str(retry_after)
            return resp_429

        accion = request.POST.get('accion')



        if accion == 'crear':

            nombre = limpiar_texto_seguro(request.POST.get('nombre', ''), max_length=60)

            apellido = limpiar_texto_seguro(request.POST.get('apellido', ''), max_length=60)

            username = limpiar_texto_seguro(request.POST.get('username', ''), max_length=60).lower()

            rut = limpiar_texto_seguro(request.POST.get('rut', ''), max_length=12)

            rol = request.POST.get('rol', 'CAJERO')

            roles_validos = {codigo for codigo, _ in PerfilEmpleado.ROLES}

            if rol not in roles_validos:

                messages.error(request, "Rol operativo inválido.")

                return redirect('administrador_trabajadores')

            telefono = limpiar_texto_seguro(request.POST.get('telefono', ''), max_length=20)

            email_opcional = limpiar_texto_seguro(request.POST.get('email', ''), max_length=120)

            local_id = request.POST.get('local_id')

            if not nombre or not apellido:

                messages.error(request, "Nombre y apellido válidos son obligatorios (sin etiquetas HTML).")

                return redirect('administrador_trabajadores')



            if not username:

                username = f"{nombre[:1].lower()}{apellido.replace(' ', '').lower()}" if nombre and apellido else f"safari_user_{User.objects.count()+1}"

            

            if User.objects.filter(username=username).exists():

                username = f"{username}_{User.objects.count()+1}"



            password = request.POST.get('password', '').strip()

            if not password:

                messages.error(request, "Debes ingresar una contraseña para el nuevo colaborador.")

                return redirect('administrador_trabajadores')



            msg_error_clave = _validar_clave_colaborador(
                password,
                user_candidate=User(username=username, first_name=nombre, last_name=apellido, email=email_opcional),
            )
            if msg_error_clave:
                messages.error(request, msg_error_clave)
                return redirect('administrador_trabajadores')



            local_obj = PuntoVenta.objects.filter(id=local_id).first() if local_id else None

            user = User.objects.create(

                username=username,

                first_name=nombre,

                last_name=apellido,

                email=email_opcional

            )

            user.set_password(password)

            user.save()



            perfil = PerfilEmpleado.objects.create(

                usuario=user,

                rol=rol,

                rut=rut,

                telefono=telefono,

                punto_venta_actual=local_obj,

                activo=True,

                debe_cambiar_clave=True

            )

            local_nom = local_obj.nombre if local_obj else "Sin Puesto Asignado"

            messages.success(request, f"¡Colaborador '{nombre} {apellido}' registrado con éxito con puesto único en: {local_nom}!")

            return redirect('administrador_trabajadores')



        elif accion == 'modificar':

            perfil_id = request.POST.get('perfil_id')

            perfil = get_object_or_404(PerfilEmpleado, id=perfil_id)

            user = perfil.usuario



            user.first_name = limpiar_texto_seguro(request.POST.get('nombre', user.first_name), max_length=60) or user.first_name

            user.last_name = limpiar_texto_seguro(request.POST.get('apellido', user.last_name), max_length=60) or user.last_name

            nueva_pass = request.POST.get('password', '').strip()

            if nueva_pass:

                msg_error_clave = _validar_clave_colaborador(nueva_pass, user_candidate=user)
                if msg_error_clave:
                    messages.error(request, msg_error_clave)
                    return redirect('administrador_trabajadores')

                user.set_password(nueva_pass)

            user.save()



            rut_post = request.POST.get('rut', '').strip()
            if rut_post:
                perfil.rut = limpiar_texto_seguro(rut_post, max_length=12)

            nuevo_rol = request.POST.get('rol', perfil.rol)

            roles_validos = {codigo for codigo, _ in PerfilEmpleado.ROLES}

            if nuevo_rol not in roles_validos:

                messages.error(request, "Rol operativo inválido.")

                return redirect('administrador_trabajadores')



            if perfil.rol != nuevo_rol:

                # Anti-Lockout: No revocar privilegios del propio administrador ni del único activo

                if user == request.user and nuevo_rol != 'ADMINISTRADOR':

                    messages.error(request, "Acción denegada por seguridad: No puedes revocar tus propios privilegios de administrador.")

                    return redirect('administrador_trabajadores')

                if perfil.rol == 'ADMINISTRADOR' and nuevo_rol != 'ADMINISTRADOR':

                    if PerfilEmpleado.objects.filter(rol='ADMINISTRADOR', activo=True).count() <= 1:

                        messages.error(request, "Acción denegada por seguridad: Este es el único administrador activo del sistema. No puede ser degradado.")

                        return redirect('administrador_trabajadores')



                # Control Anti-Fraude: No cambiar de rol si tiene una caja actualmente abierta

                if perfil.rol == 'CAJERO' and nuevo_rol != 'CAJERO':

                    if Caja.objects.filter(cajero=user, estado='ABIERTA').exists():

                        messages.error(

                            request,

                            f"Acción denegada por control anti-fraude: '{user.get_full_name() or user.username}' tiene una caja individual abierta. "

                            "Debe cerrar y arquear la caja antes de cambiar su rol operativo."

                        )

                        return redirect('administrador_trabajadores')

                perfil.rol = nuevo_rol



            tel_post = request.POST.get('telefono', '').strip()
            if tel_post:
                perfil.telefono = limpiar_texto_seguro(tel_post, max_length=20)



            nuevo_local_id = request.POST.get('local_id')

            nuevo_local = PuntoVenta.objects.filter(id=nuevo_local_id).first() if (nuevo_local_id and nuevo_local_id != 'none') else None

            antiguo_local = perfil.punto_venta_actual



            # Si el administrador cambió el puesto de trabajo (local), se emite la Alerta de Traslado

            if nuevo_local != antiguo_local:

                motivo = request.POST.get('motivo_traslado', '').strip() or "Reasignación operativa de personal por administración"

                AlertaTraslado.objects.create(

                    empleado=user,

                    punto_venta_origen=antiguo_local,

                    punto_venta_destino=nuevo_local if nuevo_local else PuntoVenta.objects.first(),

                    motivo=motivo

                )

                perfil.punto_venta_actual = nuevo_local

                perfil.save()

                origen_nom = antiguo_local.nombre if antiguo_local else "Sin Asignar"

                destino_nom = nuevo_local.nombre if nuevo_local else "Sin Asignar"

                messages.warning(request, f"🚨 ALERTA EMITIDA: '{user.get_full_name()}' trasladado desde '{origen_nom}' hacia '{destino_nom}'. Se ha notificado al punto de venta.")

            else:

                perfil.save()

                messages.success(request, f"Datos del colaborador '{user.get_full_name()}' actualizados correctamente.")



            return redirect('administrador_trabajadores')



        elif accion == 'trasladar':

            perfil_id = request.POST.get('perfil_id')

            perfil = get_object_or_404(PerfilEmpleado, id=perfil_id)

            user = perfil.usuario

            nuevo_local_id = request.POST.get('nuevo_local_id')

            nuevo_local = get_object_or_404(PuntoVenta, id=nuevo_local_id)

            antiguo_local = perfil.punto_venta_actual

            motivo = request.POST.get('motivo', '').strip() or "Reasignación inmediata por requerimiento operativo"



            if nuevo_local != antiguo_local:

                AlertaTraslado.objects.create(

                    empleado=user,

                    punto_venta_origen=antiguo_local,

                    punto_venta_destino=nuevo_local,

                    motivo=motivo

                )

                perfil.punto_venta_actual = nuevo_local

                perfil.save()

                origen_nom = antiguo_local.nombre if antiguo_local else "Sin Asignar"

                messages.warning(request, f"🚨 ALERTA DE TRASLADO EMITIDA: '{user.get_full_name()}' trasladado a '{nuevo_local.nombre}'. Se notificó al punto de venta.")

            else:

                messages.info(request, f"El colaborador ya se encontraba asignado a {nuevo_local.nombre}.")



            return redirect('administrador_trabajadores')



        elif accion == 'desactivar':

            perfil_id = request.POST.get('perfil_id')

            perfil = get_object_or_404(PerfilEmpleado, id=perfil_id)

            if perfil.usuario == request.user:

                messages.error(request, "Acción denegada por seguridad: No puedes desactivar tu propia cuenta de administrador.")

                return redirect('administrador_trabajadores')

            if perfil.rol == 'ADMINISTRADOR' and PerfilEmpleado.objects.filter(rol='ADMINISTRADOR', activo=True).count() <= 1:

                messages.error(request, "Acción denegada por seguridad: Este es el único administrador activo del sistema. No se puede desactivar para evitar la pérdida total de acceso administrativo.")

                return redirect('administrador_trabajadores')

            if Caja.objects.filter(cajero=perfil.usuario, estado='ABIERTA').exists():

                messages.error(

                    request,

                    f"Imposible desactivar a '{perfil.usuario.get_full_name() or perfil.usuario.username}': "

                    "Tiene una caja individual actualmente abierta. Debe cerrar y arquear la caja antes de dar de baja al colaborador (Control Anti-Fraude)."

                )

                return redirect('administrador_trabajadores')

            perfil.activo = False

            perfil.save()

            perfil.usuario.is_active = False

            perfil.usuario.save()

            nombre = perfil.usuario.get_full_name() or perfil.usuario.username

            messages.info(request, f"Colaborador '{nombre}' desactivado.")



            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                total_activos = PerfilEmpleado.objects.filter(activo=True).count()

                total_trabajadores = PerfilEmpleado.objects.count()

                total_inactivos = total_trabajadores - total_activos

                return JsonResponse({

                    'status': 'ok',

                    'accion': 'desactivar',

                    'perfil_id': perfil.id,

                    'activo': False,

                    'nombre': nombre,

                    'total_activos': total_activos,

                    'total_inactivos': total_inactivos,

                    'total_trabajadores': total_trabajadores,

                    'mensaje': f"Colaborador '{nombre}' desactivado correctamente."

                })



            return redirect('administrador_trabajadores')



        elif accion == 'activar':

            perfil_id = request.POST.get('perfil_id')

            perfil = get_object_or_404(PerfilEmpleado, id=perfil_id)

            perfil.activo = True

            perfil.save()

            perfil.usuario.is_active = True

            perfil.usuario.save()

            nombre = perfil.usuario.get_full_name() or perfil.usuario.username

            messages.success(request, f"Colaborador '{nombre}' reactivado.")



            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                total_activos = PerfilEmpleado.objects.filter(activo=True).count()

                total_trabajadores = PerfilEmpleado.objects.count()

                total_inactivos = total_trabajadores - total_activos

                return JsonResponse({

                    'status': 'ok',

                    'accion': 'activar',

                    'perfil_id': perfil.id,

                    'activo': True,

                    'nombre': nombre,

                    'total_activos': total_activos,

                    'total_inactivos': total_inactivos,

                    'total_trabajadores': total_trabajadores,

                    'mensaje': f"Colaborador '{nombre}' reactivado exitosamente."

                })



            return redirect('administrador_trabajadores')



        elif accion == 'eliminar':

            perfil_id = request.POST.get('perfil_id')

            perfil = get_object_or_404(PerfilEmpleado, id=perfil_id)

            if Caja.objects.filter(cajero=perfil.usuario, estado='ABIERTA').exists():

                messages.error(

                    request,

                    f"Imposible eliminar a '{perfil.usuario.get_full_name() or perfil.usuario.username}': "

                    "Tiene una caja individual actualmente abierta. Debe cerrar y arquear la caja antes de dar de baja al colaborador (Control Anti-Fraude)."

                )

                return redirect('administrador_trabajadores')

            if perfil.usuario == request.user:

                messages.error(request, "Acción denegada: No puedes eliminar tu propia cuenta de administrador en uso.")

                return redirect('administrador_trabajadores')

            nom = perfil.usuario.get_full_name() or perfil.usuario.username

            from django.db.models import ProtectedError

            try:

                perfil.usuario.delete()

                messages.success(request, f"Colaborador '{nom}' eliminado del sistema.")

            except ProtectedError:

                perfil.activo = False

                perfil.save(update_fields=['activo'])

                perfil.usuario.is_active = False

                perfil.usuario.save(update_fields=['is_active'])

                messages.warning(

                    request,

                    f"Colaborador '{nom}' posee historial contable y operacional protegido en el sistema; "

                    "ha sido desactivado permanentemente para preservar la integridad de auditoría."

                )

            return redirect('administrador_trabajadores')



        elif accion == 'marcar_leida_alerta':

            alerta_id = request.POST.get('alerta_id')

            if alerta_id:

                AlertaTraslado.objects.filter(id=alerta_id).update(leida=True)

            return redirect('administrador_trabajadores')



    # GET: Listado y datos de contexto

    trabajadores = PerfilEmpleado.objects.select_related('usuario', 'punto_venta_actual').all().order_by('usuario__first_name')

    locales = PuntoVenta.objects.filter(activo=True).order_by('id')

    alertas_recientes = AlertaTraslado.objects.select_related('empleado', 'punto_venta_origen', 'punto_venta_destino').order_by('-fecha_hora')[:12]



    total_trabajadores = trabajadores.count()

    total_activos = trabajadores.filter(activo=True).count()

    total_inactivos = total_trabajadores - total_activos

    total_alertas = AlertaTraslado.objects.count()



    context = {

        "trabajadores": trabajadores,

        "locales": locales,

        "alertas_recientes": alertas_recientes,

        "total_trabajadores": total_trabajadores,

        "total_activos": total_activos,

        "total_inactivos": total_inactivos,

        "total_alertas": total_alertas,

    }

    return render(request, 'ventas/administrador/administrador_trabajadores.html', context)





@requiere_rol(['ADMINISTRADOR'])

def administrador_mesas(request):

    """

    CRUD de Mesas para Administrador (Semana 11):

    Gestión integral de mesas por Punto de Venta: listar, crear, modificar, activar/desactivar y eliminar protegido.

    Garantiza unicidad de identificador por local y protección contra alteración de cuentas abiertas en consumo.

    """

    proteger_contingencia_operativa(usuario=request.user)

    locales = PuntoVenta.objects.filter(activo=True).order_by('id')



    # Filtro opcional por local

    local_id_filtro = request.GET.get('local_id', '')

    local_seleccionado = None

    if local_id_filtro:

        try:

            local_id = int(local_id_filtro)

            local_seleccionado = PuntoVenta.objects.filter(id=local_id).first()

        except (ValueError, TypeError):

            pass



    # Búsqueda por texto (ej: "Mesa 1", "Terraza")

    busqueda_q = request.POST.get('q', request.GET.get('q', '')).strip()



    if request.method == 'POST':

        accion = request.POST.get('accion')



        if accion == 'crear':

            identificador = request.POST.get('identificador', '').strip()

            punto_venta_id = request.POST.get('punto_venta_id')

            capacidad_raw = request.POST.get('capacidad', '4')

            estado = request.POST.get('estado', 'HABILITADA')



            if not identificador:

                messages.error(request, "El identificador de la mesa es obligatorio (ej: Mesa 12, Terraza 5).")

                return redirect('administrador_mesas')



            try:

                capacidad = max(1, int(capacidad_raw))

            except (ValueError, TypeError):

                capacidad = 4



            local_obj = PuntoVenta.objects.filter(id=punto_venta_id, activo=True).first()

            if not local_obj:

                messages.error(request, "Debes seleccionar un Punto de Venta válido para la mesa.")

                return redirect('administrador_mesas')



            # Validación de unicidad de identificador en el mismo Punto de Venta

            if Mesa.objects.filter(identificador__iexact=identificador, punto_venta=local_obj).exists():

                messages.error(request, f"Ya existe una mesa con el identificador '{identificador}' en {local_obj.nombre}.")

                return redirect(f"/administrador/mesas/?local_id={local_obj.id}")



            Mesa.objects.create(

                identificador=identificador,

                punto_venta=local_obj,

                capacidad=capacidad,

                estado=estado

            )

            messages.success(request, f"¡Mesa '{identificador}' creada exitosamente en {local_obj.nombre} (Capacidad: {capacidad} personas)!")

            return redirect(f"/administrador/mesas/?local_id={local_obj.id}")



        elif accion == 'modificar':

            mesa_id = request.POST.get('mesa_id')

            mesa_obj = get_object_or_404(Mesa, id=mesa_id)



            nuevo_identificador = request.POST.get('identificador', '').strip()

            nuevo_local_id = request.POST.get('punto_venta_id')

            nueva_capacidad_raw = request.POST.get('capacidad', '4')

            nuevo_estado = request.POST.get('estado', mesa_obj.estado)



            if not nuevo_identificador:

                messages.error(request, "El identificador de la mesa no puede quedar vacío.")

                return redirect(f"/administrador/mesas/?local_id={mesa_obj.punto_venta_id}")



            try:

                nueva_capacidad = max(1, int(nueva_capacidad_raw))

            except (ValueError, TypeError):

                nueva_capacidad = mesa_obj.capacidad



            nuevo_local = PuntoVenta.objects.filter(id=nuevo_local_id, activo=True).first() or mesa_obj.punto_venta



            # Validación de unicidad excluyendo la propia mesa

            if Mesa.objects.filter(identificador__iexact=nuevo_identificador, punto_venta=nuevo_local).exclude(id=mesa_obj.id).exists():

                messages.error(request, f"Ya existe otra mesa con el identificador '{nuevo_identificador}' en {nuevo_local.nombre}.")

                return redirect(f"/administrador/mesas/?local_id={mesa_obj.punto_venta_id}")



            # Regla de Integridad de Cuenta Abierta y Comensales en Salón

            cuenta_abierta = Venta.objects.filter(mesa=mesa_obj, estado='ABIERTA').exists()

            if (cuenta_abierta or mesa_obj.estado == 'OCUPADA') and nuevo_estado in ['INACTIVA', 'MANTENIMIENTO']:

                messages.error(request, f"Acción denegada: La mesa '{mesa_obj.identificador}' se encuentra actualmente en atención/consumo con comensales o cuenta abierta. Debe ser cobrada y liberada antes de desactivarla.")

                return redirect(f"/administrador/mesas/?local_id={mesa_obj.punto_venta_id}")



            mesa_obj.identificador = nuevo_identificador

            mesa_obj.punto_venta = nuevo_local

            mesa_obj.capacidad = nueva_capacidad

            mesa_obj.estado = nuevo_estado

            mesa_obj.save()



            messages.success(request, f"¡Mesa '{nuevo_identificador}' actualizada correctamente!")

            return redirect(f"/administrador/mesas/?local_id={nuevo_local.id}")



        elif accion == 'toggle_estado':

            mesa_id = request.POST.get('mesa_id')

            mesa_obj = get_object_or_404(Mesa, id=mesa_id)



            if mesa_obj.estado == 'INACTIVA':

                mesa_obj.estado = 'HABILITADA'

                mesa_obj.save()

                messages.success(request, f"Mesa '{mesa_obj.identificador}' activada y habilitada para atención.")

            else:

                cuenta_abierta = Venta.objects.filter(mesa=mesa_obj, estado='ABIERTA').exists()

                if cuenta_abierta:

                    messages.warning(request, f"No es posible desactivar la mesa '{mesa_obj.identificador}' porque tiene una comanda abierta en salón.")

                    return redirect(f"/administrador/mesas/?local_id={mesa_obj.punto_venta_id}")

                mesa_obj.estado = 'INACTIVA'

                mesa_obj.save()

                messages.info(request, f"Mesa '{mesa_obj.identificador}' desactivada (marcada en mantenimiento).")



            return redirect(f"/administrador/mesas/?local_id={mesa_obj.punto_venta_id}")



        elif accion == 'eliminar':

            mesa_id = request.POST.get('mesa_id')

            mesa_obj = get_object_or_404(Mesa, id=mesa_id)

            local_id = mesa_obj.punto_venta_id



            # Protección de Integridad Referencial

            tiene_ventas = mesa_obj.ventas.exists()

            tiene_cuenta_abierta = mesa_obj.ventas.filter(estado='ABIERTA').exists()



            if tiene_cuenta_abierta:

                messages.error(request, f"Imposible eliminar la mesa '{mesa_obj.identificador}': Tiene una cuenta activa en consumo.")

                return redirect(f"/administrador/mesas/?local_id={local_id}")



            if tiene_ventas:

                # Soft-delete o marcado como inactiva para no violar historial contable

                mesa_obj.estado = 'INACTIVA'

                mesa_obj.save()

                messages.warning(

                    request,

                    f"La mesa '{mesa_obj.identificador}' posee historial de ventas registradas. "

                    "Por motivos de auditoría e integridad tributaria, se ha desactivado y retirado del plano operativo sin eliminar sus registros históricos."

                )

            else:

                identificador_eliminado = mesa_obj.identificador

                mesa_obj.delete()

                messages.success(request, f"Mesa '{identificador_eliminado}' eliminada definitivamente del sistema.")



            return redirect(f"/administrador/mesas/?local_id={local_id}")



    # Queryset base de mesas

    mesas_qs = Mesa.objects.select_related('punto_venta').order_by('punto_venta__id', 'identificador')

    if local_seleccionado:

        mesas_qs = mesas_qs.filter(punto_venta=local_seleccionado)

    if busqueda_q:

        mesas_qs = mesas_qs.filter(models.Q(identificador__icontains=busqueda_q) | models.Q(punto_venta__nombre__icontains=busqueda_q))



    # Métricas de mesas

    total_mesas = mesas_qs.count()

    mesas_libres = mesas_qs.filter(estado='HABILITADA').count()

    mesas_ocupadas = mesas_qs.filter(estado='OCUPADA').count()

    mesas_inactivas = mesas_qs.filter(estado='INACTIVA').count()



    context = {

        'mesas': mesas_qs,

        'locales': locales,

        'local_seleccionado': local_seleccionado,

        'busqueda_q': busqueda_q,

        'total_mesas': total_mesas,

        'mesas_libres': mesas_libres,

        'mesas_ocupadas': mesas_ocupadas,

        'mesas_inactivas': mesas_inactivas,

    }

    return render(request, 'ventas/administrador/administrador_mesas.html', context)





@requiere_rol(['ADMINISTRADOR'])

def administrador_productos(request):

    """

    CRUD de Catálogo Centralizado de Productos Gastronómicos (Semana 11):

    Gestión administrativa conectada a la base de datos real (listar, crear, modificar, activar/desactivar y eliminar protegido).

    Permite asociar productos a categorías oficiales y a los puntos de venta donde se comercializan.

    """

    categorias = Categoria.objects.filter(activo=True).order_by('nombre')

    locales = PuntoVenta.objects.filter(activo=True).order_by('id')



    # Filtros GET

    cat_filtro_id = request.GET.get('categoria_id', '')

    local_filtro_id = request.GET.get('local_id', '')

    busqueda_q = request.POST.get('q', request.GET.get('q', '')).strip()



    if request.method == 'POST':

        accion = request.POST.get('accion')



        if accion == 'crear':

            nombre = request.POST.get('nombre', '').strip()

            categoria_id = request.POST.get('categoria_id')

            precio_base_raw = request.POST.get('precio_base', '0').strip()

            descripcion = request.POST.get('descripcion', '').strip()

            puntos_venta_ids = request.POST.getlist('puntos_venta')

            activo = request.POST.get('activo') in ['on', 'true', 'True', '1']

            en_oferta = request.POST.get('en_oferta') in ['on', 'true', 'True', '1']

            precio_oferta_raw = request.POST.get('precio_oferta', '').strip()

            precio_oferta = None

            if en_oferta and precio_oferta_raw:

                try:

                    precio_oferta = max(Decimal('0'), Decimal(precio_oferta_raw.replace('.', '').replace(',', '.')))

                except Exception:

                    precio_oferta = None

            descripcion_oferta = request.POST.get('descripcion_oferta', '').strip()



            if not nombre:

                messages.error(request, "El nombre del producto es obligatorio.")

                return redirect(obtener_url_redireccion_segura(request, 'administrador_productos'))



            try:

                precio_base = Decimal(precio_base_raw.replace('.', '').replace(',', '.'))

            except Exception:

                messages.error(request, "El precio base debe ser un valor numérico válido.")

                return redirect(obtener_url_redireccion_segura(request, 'administrador_productos'))



            if precio_base <= Decimal('0'):

                messages.error(request, "El precio base del producto debe ser estrictamente mayor a $0 CLP (prevención de fuga de inventario no autorizada).")

                return redirect(obtener_url_redireccion_segura(request, 'administrador_productos'))



            cat_obj = get_object_or_404(Categoria, id=categoria_id)



            tipo_oferta = request.POST.get('tipo_oferta', 'NINGUNA').strip()

            descuento_pct_raw = request.POST.get('descuento_pct', '0').strip()

            try:

                descuento_pct = max(Decimal('0'), min(Decimal('100'), Decimal(descuento_pct_raw)))

            except Exception:

                descuento_pct = Decimal('0')



            prod = Producto.objects.create(

                nombre=nombre,

                categoria=cat_obj,

                precio_base=precio_base,

                descripcion=descripcion,

                activo=activo,

                en_oferta=en_oferta,

                tipo_oferta=tipo_oferta,

                precio_oferta=precio_oferta,

                descuento_pct=descuento_pct,

                descripcion_oferta=descripcion_oferta

            )

            if puntos_venta_ids:

                prod.puntos_venta.set(PuntoVenta.objects.filter(id__in=puntos_venta_ids))



            precio_fmt = f"${int(precio_base):,}".replace(',', '.')

            messages.success(request, f"¡Producto '{nombre}' ({precio_fmt}) creado exitosamente en categoría '{cat_obj.nombre}'!")

            return redirect(obtener_url_redireccion_segura(request, 'administrador_productos'))



        elif accion == 'modificar':

            producto_id = request.POST.get('producto_id')

            prod = get_object_or_404(Producto, id=producto_id)



            nombre = (request.POST.get('nombre') or prod.nombre or '').strip()

            categoria_id = request.POST.get('categoria_id')

            precio_base_raw = str(request.POST.get('precio_base', prod.precio_base)).strip()

            descripcion = (request.POST.get('descripcion') or prod.descripcion or '').strip()

            puntos_venta_ids = request.POST.getlist('puntos_venta')

            activo = request.POST.get('activo') in ['on', 'true', 'True', '1']

            en_oferta = request.POST.get('en_oferta') in ['on', 'true', 'True', '1']

            precio_oferta_raw = (request.POST.get('precio_oferta') or '').strip()

            precio_oferta = None

            if en_oferta and precio_oferta_raw:

                try:

                    precio_oferta = max(Decimal('0'), Decimal(precio_oferta_raw.replace('.', '').replace(',', '.')))

                except Exception:

                    precio_oferta = None

            descripcion_oferta = (request.POST.get('descripcion_oferta') or prod.descripcion_oferta or '').strip()



            if not nombre:

                messages.error(request, "El nombre del producto no puede quedar vacío.")

                return redirect(obtener_url_redireccion_segura(request, 'administrador_productos'))



            try:

                precio_base = Decimal(precio_base_raw.replace('.', '').replace(',', '.'))

                if precio_base <= Decimal('0'):

                    messages.error(request, "El precio base del producto debe ser estrictamente mayor a $0 CLP.")

                    return redirect(obtener_url_redireccion_segura(request, 'administrador_productos'))

            except Exception:

                precio_base = prod.precio_base



            # Auditoría permanente e inmutable ante cambios de precios oficiales en catálogo

            if precio_base != prod.precio_base:

                pv_prod = prod.puntos_venta.first() or PuntoVenta.objects.first()

                AlertaTraslado.objects.create(

                    empleado=request.user,

                    punto_venta_origen=pv_prod,

                    punto_venta_destino=pv_prod,

                    autorizado_por=request.user,

                    motivo=f"[AUDITORÍA PRECIOS] Producto '{prod.nombre}': Precio base cambiado de ${int(prod.precio_base):,} a ${int(precio_base):,} CLP por Administrador {request.user.username}"[:255]

                )



            cat_obj = Categoria.objects.filter(id=categoria_id).first() or prod.categoria



            tipo_oferta = (request.POST.get('tipo_oferta') or prod.tipo_oferta or 'NINGUNA').strip()

            descuento_pct_raw = str(request.POST.get('descuento_pct', prod.descuento_pct or '0')).strip()

            try:

                descuento_pct = max(Decimal('0'), min(Decimal('100'), Decimal(descuento_pct_raw)))

            except Exception:

                descuento_pct = prod.descuento_pct



            prod.nombre = nombre

            prod.categoria = cat_obj

            prod.precio_base = precio_base

            prod.descripcion = descripcion

            prod.activo = activo

            prod.en_oferta = en_oferta

            prod.tipo_oferta = tipo_oferta

            prod.precio_oferta = precio_oferta

            prod.descuento_pct = descuento_pct

            prod.descripcion_oferta = descripcion_oferta

            prod.save()



            if puntos_venta_ids:

                prod.puntos_venta.set(PuntoVenta.objects.filter(id__in=puntos_venta_ids))

            else:

                prod.puntos_venta.clear()



            messages.success(request, f"¡Producto '{nombre}' actualizado correctamente!")

            return redirect(obtener_url_redireccion_segura(request, 'administrador_productos'))



        elif accion == 'gestionar_oferta':

            producto_id = request.POST.get('producto_id')

            prod = get_object_or_404(Producto, id=producto_id)

            en_oferta = request.POST.get('en_oferta') in ['on', 'true', 'True', '1']

            precio_oferta_raw = request.POST.get('precio_oferta', '').strip()

            precio_oferta = None

            if en_oferta and precio_oferta_raw:

                try:

                    precio_oferta = max(Decimal('0'), Decimal(precio_oferta_raw.replace('.', '').replace(',', '.')))

                except Exception:

                    precio_oferta = None

            descripcion_oferta = request.POST.get('descripcion_oferta', '').strip()



            tipo_oferta = request.POST.get('tipo_oferta', getattr(prod, 'tipo_oferta', 'NINGUNA')).strip()

            descuento_pct_raw = request.POST.get('descuento_pct', '0').strip()

            try:

                descuento_pct = max(Decimal('0'), min(Decimal('100'), Decimal(descuento_pct_raw)))

            except Exception:

                descuento_pct = Decimal('0')



            prod.en_oferta = en_oferta

            prod.tipo_oferta = tipo_oferta

            prod.descuento_pct = descuento_pct

            prod.precio_oferta = precio_oferta

            prod.descripcion_oferta = descripcion_oferta

            prod.save()



            if request.headers.get('x-requested-with') == 'XMLHttpRequest':

                return JsonResponse({

                    'status': 'ok',

                    'producto_id': prod.id,

                    'en_oferta': prod.en_oferta,

                    'tipo_oferta': prod.tipo_oferta,

                    'tipo_oferta_display': prod.get_tipo_oferta_display(),

                    'precio_base': float(prod.precio_base),

                    'precio_oferta': float(prod.precio_oferta) if prod.precio_oferta is not None else None,

                    'precio_actual': float(prod.precio_actual),

                    'descuento_pct': float(prod.descuento_pct),

                    'descripcion_oferta': prod.descripcion_oferta or '',

                    'mensaje': f"¡Oferta para '{prod.nombre}' actualizada exitosamente en tiempo real!"

                })

            messages.success(request, f"¡Oferta para '{prod.nombre}' actualizada!")

            return redirect(obtener_url_redireccion_segura(request, 'administrador_productos'))

        elif accion == 'toggle_estado':

            producto_id = request.POST.get('producto_id')

            prod = get_object_or_404(Producto, id=producto_id)

            prod.activo = not prod.activo

            prod.save()

            estado_txt = "activado y disponible" if prod.activo else "desactivado del catálogo"

            messages.info(request, f"Producto '{prod.nombre}' {estado_txt}.")

            return redirect('administrador_productos')



        elif accion == 'eliminar':

            producto_id = request.POST.get('producto_id')

            prod = get_object_or_404(Producto, id=producto_id)



            tiene_ventas = DetalleVenta.objects.filter(producto=prod).exists() or DetallePedido.objects.filter(producto=prod).exists()

            if tiene_ventas:

                # Soft-delete para no quebrar integridad tributaria ni historial

                prod.activo = False

                prod.save()

                messages.warning(

                    request,

                    f"El producto '{prod.nombre}' registra ventas históricas en el sistema. "

                    "Por motivos de integridad contable y tributaria, se ha desactivado del catálogo sin eliminar sus registros históricos."

                )

            else:

                nom = prod.nombre

                prod.delete()

                messages.success(request, f"Producto '{nom}' eliminado definitivamente de la base de datos.")



            return redirect('administrador_productos')



    # Queryset base

    productos_qs = Producto.objects.select_related('categoria').prefetch_related('puntos_venta').order_by('categoria__nombre', 'nombre')

    if cat_filtro_id:

        productos_qs = productos_qs.filter(categoria_id=cat_filtro_id)

    if local_filtro_id:

        productos_qs = productos_qs.filter(puntos_venta__id=local_filtro_id)

    if busqueda_q:

        productos_qs = productos_qs.filter(models.Q(nombre__icontains=busqueda_q) | models.Q(descripcion__icontains=busqueda_q))



    total_productos = productos_qs.count()

    activos_count = productos_qs.filter(activo=True).count()

    inactivos_count = total_productos - activos_count



    context = {

        'productos': productos_qs,

        'categorias': categorias,

        'locales': locales,

        'cat_filtro_id': int(cat_filtro_id) if cat_filtro_id.isdigit() else None,

        'local_filtro_id': int(local_filtro_id) if local_filtro_id.isdigit() else None,

        'busqueda_q': busqueda_q,

        'total_productos': total_productos,

        'activos_count': activos_count,

        'inactivos_count': inactivos_count,

    }

    return render(request, 'ventas/administrador/administrador_productos.html', context)





@requiere_rol(['ADMINISTRADOR'])

def administrador_menus(request):

    """

    CRUD de Menús de Carta por Punto de Venta (Semana 11):

    Gestión administrativa de cartas gastronómicas asociadas a cada local con sus productos vinculados.

    """

    locales = PuntoVenta.objects.filter(activo=True).order_by('id')

    productos_disponibles = Producto.objects.filter(activo=True).select_related('categoria').order_by('categoria__nombre', 'nombre')



    if request.method == 'POST':

        accion = request.POST.get('accion')



        if accion == 'crear':

            nombre = request.POST.get('nombre', '').strip()

            punto_venta_id = request.POST.get('punto_venta_id')

            productos_ids = request.POST.getlist('productos')

            activo = request.POST.get('activo') in ['on', 'true', 'True', '1']



            if not nombre:

                messages.error(request, "El nombre de la carta o menú es obligatorio.")

                return redirect('administrador_menus')



            local_obj = get_object_or_404(PuntoVenta, id=punto_venta_id)

            menu_obj = Menu.objects.create(

                nombre=nombre,

                punto_venta=local_obj,

                activo=activo

            )

            if productos_ids:

                menu_obj.productos.set(Producto.objects.filter(id__in=productos_ids))



            messages.success(request, f"¡Menú '{nombre}' asignado exitosamente a {local_obj.nombre} ({menu_obj.productos.count()} productos vinculados)!")

            return redirect('administrador_menus')



        elif accion == 'modificar':

            menu_id = request.POST.get('menu_id')

            menu_obj = get_object_or_404(Menu, id=menu_id)



            nombre = request.POST.get('nombre', menu_obj.nombre).strip()

            punto_venta_id = request.POST.get('punto_venta_id')

            productos_ids = request.POST.getlist('productos')

            activo = request.POST.get('activo') in ['on', 'true', 'True', '1']



            if not nombre:

                if request.headers.get('x-requested-with') == 'XMLHttpRequest':

                    return JsonResponse({'status': 'error', 'mensaje': 'El nombre del menú no puede quedar vacío.'}, status=400)

                messages.error(request, "El nombre del menú no puede quedar vacío.")

                return redirect(obtener_url_redireccion_segura(request, 'administrador_menus'))



            local_obj = PuntoVenta.objects.filter(id=punto_venta_id).first() or menu_obj.punto_venta

            menu_obj.nombre = nombre

            menu_obj.punto_venta = local_obj

            menu_obj.activo = activo

            menu_obj.save()



            if productos_ids:

                menu_obj.productos.set(Producto.objects.filter(id__in=productos_ids))

            else:

                menu_obj.productos.clear()



            if request.headers.get('x-requested-with') == 'XMLHttpRequest':

                prods_data = [

                    {'id': p.id, 'nombre': p.nombre, 'precio': float(p.precio_base)}

                    for p in menu_obj.productos.all()

                ]

                return JsonResponse({

                    'status': 'ok',

                    'menu_id': menu_obj.id,

                    'nombre': menu_obj.nombre,

                    'local_nombre': menu_obj.punto_venta.nombre,

                    'productos_count': menu_obj.productos.count(),

                    'productos': prods_data,

                    'activo': menu_obj.activo,

                    'mensaje': f"¡Carta '{nombre}' actualizada correctamente en tiempo real!"

                })



            messages.success(request, f"¡Menú '{nombre}' actualizado correctamente!")

            return redirect(obtener_url_redireccion_segura(request, 'administrador_menus'))

        elif accion == 'toggle_estado':

            menu_id = request.POST.get('menu_id')

            menu_obj = get_object_or_404(Menu, id=menu_id)

            menu_obj.activo = not menu_obj.activo

            menu_obj.save()

            estado_txt = "activado" if menu_obj.activo else "desactivado"

            messages.info(request, f"Menú '{menu_obj.nombre}' {estado_txt}.")

            return redirect('administrador_menus')



        elif accion == 'eliminar':

            menu_id = request.POST.get('menu_id')

            menu_obj = get_object_or_404(Menu, id=menu_id)

            nom = menu_obj.nombre

            menu_obj.delete()

            messages.success(request, f"Menú '{nom}' eliminado del sistema.")

            return redirect('administrador_menus')



    menus_qs = Menu.objects.select_related('punto_venta').prefetch_related('productos__categoria').order_by('punto_venta__id', 'nombre')



    context = {

        'menus': menus_qs,

        'locales': locales,

        'productos_disponibles': productos_disponibles,

        'total_menus': menus_qs.count(),

    }

    return render(request, 'ventas/administrador/administrador_menus.html', context)







@requiere_rol(['ADMINISTRADOR'])

def administrador_gestion(request):

    """

    Centro de Gestión y Administración Integral (Categoría Madre):

    Unifica en una única página con pestañas y búsqueda reactiva por cada tecleo ('input'):

    1. Trabajadores y Dotación

    2. Mesas del Parque

    3. Catálogo de Productos

    4. Menús y Cartas

    """

    tab_activo = request.GET.get('tab', 'trabajadores').strip().lower()

    if tab_activo not in ['trabajadores', 'mesas', 'productos', 'menus']:

        tab_activo = 'trabajadores'



    locales = PuntoVenta.objects.filter(activo=True).order_by('id')

    categorias = Categoria.objects.filter(activo=True).order_by('nombre')



    # 1. Trabajadores

    trabajadores = User.objects.select_related('perfil', 'perfil__punto_venta_actual').all().order_by('username')

    total_trabajadores = trabajadores.count()

    total_activos_trab = sum(1 for t in trabajadores if hasattr(t, 'perfil') and t.perfil.activo)

    total_inactivos_trab = total_trabajadores - total_activos_trab



    # 2. Mesas

    mesas_qs = Mesa.objects.select_related('punto_venta').all().order_by('punto_venta__id', 'identificador')

    total_mesas = mesas_qs.count()

    mesas_habilitadas = sum(1 for m in mesas_qs if m.estado == 'HABILITADA')

    mesas_ocupadas = sum(1 for m in mesas_qs if m.estado == 'OCUPADA')

    mesas_mantenimiento = sum(1 for m in mesas_qs if m.estado == 'MANTENIMIENTO')



    # 3. Productos

    productos_qs = Producto.objects.select_related('categoria').prefetch_related('puntos_venta').all().order_by('categoria__nombre', 'nombre')

    total_productos = productos_qs.count()

    activos_productos = sum(1 for p in productos_qs if p.activo)

    inactivos_productos = total_productos - activos_productos



    # 4. Menús

    menus_qs = Menu.objects.select_related('punto_venta').prefetch_related('productos').all().order_by('punto_venta__id', 'nombre')

    total_menus = menus_qs.count()



    ahora_dt = timezone.localtime()

    ahora_hora = ahora_dt.time()

    hora_apertura = datetime.time(10, 0)

    hora_cierre = datetime.time(18, 0)

    en_horario = (hora_apertura <= ahora_hora < hora_cierre)



    total_alertas_no_leidas = AlertaTraslado.objects.filter(leida=False).count()



    context = {

        'tab_activo': tab_activo,

        'locales': locales,

        'categorias': categorias,

        # Trabajadores

        'trabajadores': trabajadores,

        'total_trabajadores': total_trabajadores,

        'total_activos_trab': total_activos_trab,

        'total_inactivos_trab': total_inactivos_trab,

        # Mesas

        'mesas': mesas_qs,

        'total_mesas': total_mesas,

        'mesas_habilitadas': mesas_habilitadas,

        'mesas_ocupadas': mesas_ocupadas,

        'mesas_mantenimiento': mesas_mantenimiento,

        # Productos

        'productos': productos_qs,

        'total_productos': total_productos,

        'activos_productos': activos_productos,

        'inactivos_productos': inactivos_productos,

        # Menús

        'menus': menus_qs,

        'total_menus': total_menus,

        'productos_disponibles': productos_qs.filter(activo=True),

        # Generales

        'en_horario': en_horario,

        'total_alertas_no_leidas': total_alertas_no_leidas,

    }

    return render(request, 'ventas/administrador/administrador_gestion.html', context)





@requiere_rol(['ADMINISTRADOR'])

def administrador_historial(request):

    """

    Historial de Acciones y Trazabilidad Operativa (Semana 11).

    Consolida de manera unificada y cronológica los eventos reales registrados en la BD:

    - Aperturas y Cierres de Jornada (Jornada)

    - Aperturas y Cierres de Caja (Caja)

    - Traslados y reasignaciones de colaboradores (AlertaTraslado)

    - Ventas realizadas y cobradas (Venta)

    - Despachos y entregas de pedidos en Cocina KDS (Entrega)

    """

    tipo_filtro = request.GET.get('tipo', 'TODOS').strip().upper()

    local_filtro = request.GET.get('local', '').strip()

    busqueda = request.GET.get('q', '').strip().lower()



    eventos = []



    # 1. Eventos de Jornada

    jornadas_qs = Jornada.objects.select_related('usuario_apertura', 'usuario_cierre').all()

    for j in jornadas_qs:

        eventos.append({

            'id_ref': f"JOR-A-{j.id}",

            'tipo': 'JORNADA',

            'subtipo': 'Apertura de Jornada',

            'badge_clase': 'badge-status-success',

            'icono': 'bi-calendar-check-fill text-success',

            'titulo': f"Apertura de Jornada #{j.id}",

            'descripcion': f"Jornada operativa iniciada ({j.fecha}). Observaciones: {j.observaciones or 'Sin observaciones'}",

            'usuario': j.usuario_apertura.get_full_name() or j.usuario_apertura.username,

            'local': 'Parque Safari General',

            'local_id': None,

            'fecha_hora': j.fecha_hora_apertura,

            'monto': None,

            'estado': j.estado,

        })

        if j.fecha_hora_cierre and j.usuario_cierre:

            eventos.append({

                'id_ref': f"JOR-C-{j.id}",

                'tipo': 'JORNADA',

                'subtipo': 'Cierre de Jornada',

                'badge_clase': 'badge-status-danger',

                'icono': 'bi-calendar-x-fill text-danger',

                'titulo': f"Cierre de Jornada #{j.id}",

                'descripcion': f"Jornada operativa finalizada y cuadrada por supervisión.",

                'usuario': j.usuario_cierre.get_full_name() or j.usuario_cierre.username,

                'local': 'Parque Safari General',

                'local_id': None,

                'fecha_hora': j.fecha_hora_cierre,

                'monto': None,

                'estado': 'CERRADA',

            })



    # 2. Eventos de Caja

    cajas_qs = Caja.objects.select_related('cajero', 'punto_venta', 'jornada').all()

    for c in cajas_qs:

        eventos.append({

            'id_ref': f"CAJ-A-{c.id}",

            'tipo': 'CAJA',

            'subtipo': 'Apertura de Caja',

            'badge_clase': 'badge-status-success',

            'icono': 'bi-cash-coin text-success',

            'titulo': f"Apertura {c.nombre}",

            'descripcion': f"Caja habilitada en {c.punto_venta.nombre} con fondo de ${c.monto_apertura:,.0f} CLP.",

            'usuario': c.cajero.get_full_name() or c.cajero.username,

            'local': c.punto_venta.nombre,

            'local_id': str(c.punto_venta.id),

            'fecha_hora': c.fecha_hora_apertura,

            'monto': c.monto_apertura,

            'estado': c.estado,

        })

        if c.fecha_hora_cierre and c.monto_cierre is not None:

            cuadre_txt = ""

            if c.total_efectivo_declarado is not None:

                diff_val = c.diferencia_cuadre or 0

                if diff_val == 0:

                    badge_c = 'badge-status-success'

                    diff_tag = "Cuadratura Exacta ($0)"

                elif diff_val > 0:

                    badge_c = 'badge-status-warning'

                    diff_tag = f"Sobrante (+${int(diff_val):,} CLP)".replace(',', '.')

                else:

                    badge_c = 'badge-status-danger'

                    diff_tag = f"Faltante (-${int(abs(diff_val)):,} CLP)".replace(',', '.')

                cuadre_txt = f" | Arqueo: ${int(c.total_efectivo_declarado):,} contado vs ${int(c.total_efectivo_esperado or 0):,} esperado ({diff_tag})"

            else:

                badge_c = 'badge-status-danger'



            eventos.append({

                'id_ref': f"CAJ-C-{c.id}",

                'tipo': 'CAJA',

                'subtipo': 'Cierre y Cuadre de Caja',

                'badge_clase': badge_c,

                'icono': 'bi-lock-fill text-danger',

                'titulo': f"Cierre {c.nombre}",

                'descripcion': f"Caja cerrada en {c.punto_venta.nombre} con saldo final de ${c.monto_cierre:,.0f} CLP.{cuadre_txt}",

                'usuario': c.cajero.get_full_name() or c.cajero.username,

                'local': c.punto_venta.nombre,

                'local_id': str(c.punto_venta.id),

                'fecha_hora': c.fecha_hora_cierre,

                'monto': c.monto_cierre,

                'estado': 'CERRADA',

            })



    # 3. Eventos de Traslado de Personal

    traslados_qs = AlertaTraslado.objects.select_related('empleado', 'punto_venta_origen', 'punto_venta_destino', 'autorizado_por').all()

    for t in traslados_qs:

        origen_nom = t.punto_venta_origen.nombre if t.punto_venta_origen else "Sin Asignar"

        autor_nom = (t.autorizado_por.get_full_name() or t.autorizado_por.username) if t.autorizado_por else "Administración"

        emp_nom = t.empleado.get_full_name() or t.empleado.username

        if t.motivo and t.motivo.startswith("[ANULACIÓN"):

            eventos.append({

                'id_ref': f"ANUL-{t.id}",

                'tipo': 'VENTA',

                'subtipo': 'Anulación Autorizada (Anti-Fraude)',

                'badge_clase': 'badge-status-danger',

                'icono': 'bi-shield-x text-danger',

                'titulo': f"Anulación: {emp_nom}",

                'descripcion': t.motivo,

                'usuario': autor_nom,

                'local': t.punto_venta_destino.nombre if t.punto_venta_destino else "Parque Safari General",

                'local_id': str(t.punto_venta_destino.id) if t.punto_venta_destino else None,

                'fecha_hora': t.fecha_hora,

                'monto': None,

                'estado': 'ANULADA',

            })

        else:

            eventos.append({

                'id_ref': f"TRA-{t.id}",

                'tipo': 'TRASLADO',

                'subtipo': 'Reasignación de Personal',

                'badge_clase': 'badge-status-warning',

                'icono': 'bi-arrow-left-right text-warning',

                'titulo': f"Reasignación: {emp_nom}",

                'descripcion': f"Traslado desde '{origen_nom}' hacia '{t.punto_venta_destino.nombre}'. Motivo: {t.motivo or 'Operativo'}",

                'usuario': autor_nom,

                'local': t.punto_venta_destino.nombre,

                'local_id': str(t.punto_venta_destino.id),

                'fecha_hora': t.fecha_hora,

                'monto': None,

                'estado': 'LEÍDA' if t.leida else 'PENDIENTE',

            })



    # 4. Eventos de Venta

    ventas_qs = Venta.objects.select_related('cajero', 'punto_venta', 'mesa').all()

    for v in ventas_qs:

        modalidad_txt = f"Consumo en Mesa {v.mesa.identificador}" if (v.modalidad == 'MESA' and v.mesa) else "Venta Rápida / Mostrador"

        if v.estado == 'PAGADA':

            v_badge = 'badge-status-success'

            v_icono = 'bi-receipt text-success'

        elif v.estado == 'ANULADA':

            v_badge = 'badge-status-danger'

            v_icono = 'bi-receipt text-danger'

        else:

            v_badge = 'badge-status-warning'

            v_icono = 'bi-receipt text-warning'

        eventos.append({

            'id_ref': f"VEN-{v.id}",

            'tipo': 'VENTA',

            'subtipo': f"Venta {v.get_modalidad_display()}",

            'badge_clase': v_badge,

            'icono': v_icono,

            'titulo': f"Venta #{v.id} (${v.total:,.0f} CLP)",

            'descripcion': f"{modalidad_txt} • Pago: {v.get_metodo_pago_display()} • Estado: {v.get_estado_display()}",

            'usuario': v.cajero.get_full_name() or v.cajero.username,

            'local': v.punto_venta.nombre,

            'local_id': str(v.punto_venta.id),

            'fecha_hora': v.fecha_hora,

            'monto': v.total,

            'estado': v.estado,

        })



    # 5. Eventos de Entrega / Cocina KDS (RF13)

    entregas_qs = Entrega.objects.select_related('pedido__venta__punto_venta', 'pedido__venta__mesa', 'usuario_entrega').all()

    for e in entregas_qs:

        local_e = e.get_punto_venta()

        usu_ent = (e.usuario_entrega.get_full_name() or e.usuario_entrega.username) if e.usuario_entrega else "Cocina KDS"

        tiempo_despacho = e.get_tiempo_desde_creacion_minutos()

        tiempo_prep = e.pedido.get_tiempo_preparacion_minutos() if e.pedido else None

        prep_txt = f" • Prep: {tiempo_prep:.1f} min" if tiempo_prep is not None else ""

        eventos.append({

            'id_ref': f"ENT-{e.id}",

            'tipo': 'COCINA',

            'subtipo': 'Entrega de Pedido',

            'badge_clase': 'badge-status-success',

            'icono': 'bi-check-circle-fill text-success',

            'titulo': f"Entrega Pedido #{e.pedido.id}",

            'descripcion': f"Comanda despachada ({e.get_ubicacion()}) en {tiempo_despacho:.1f} min total{prep_txt}. Obs: {e.observaciones or 'Completado'}",

            'usuario': usu_ent,

            'local': local_e.nombre if local_e else 'Cocina Central',

            'local_id': str(local_e.id) if local_e else None,

            'fecha_hora': e.fecha_hora_entrega,

            'monto': None,

            'estado': 'ENTREGADO',

        })



    # 6. Eventos de Reasignación de Mesas (RF05)

    reasignaciones_qs = ReasignacionMesa.objects.select_related('venta', 'mesa_origen', 'mesa_destino', 'mesero', 'mesa_origen__punto_venta').all()

    for r in reasignaciones_qs:

        eventos.append({

            'id_ref': f"TRASM-{r.id}",

            'tipo': 'MESAS',

            'subtipo': 'Reasignación de Mesa',

            'badge_clase': 'badge-status-warning',

            'icono': 'bi-arrow-left-right text-primary',

            'titulo': f"Reasignación {r.mesa_origen.identificador} -> {r.mesa_destino.identificador}",

            'descripcion': f"Traslado de cuenta abierta (Venta #{r.venta.id}, ${int(r.venta.total):,} CLP). Motivo: {r.motivo or 'Cambio por comensal'}",

            'usuario': r.mesero.get_full_name() or r.mesero.username,

            'local': r.mesa_origen.punto_venta.nombre,

            'local_id': str(r.mesa_origen.punto_venta.id),

            'fecha_hora': r.fecha_hora,

            'monto': r.venta.total,

            'estado': 'TRASLADADA',

        })



    # 7. Eventos de Precios Especiales y Convenios Autorizados (RF07)

    precios_esp_qs = RegistroPrecioEspecial.objects.select_related('venta', 'producto', 'usuario', 'convenio_origen', 'venta__punto_venta').all()

    for pe in precios_esp_qs:

        local_p = pe.venta.punto_venta if (pe.venta and pe.venta.punto_venta) else None

        eventos.append({

            'id_ref': f"PRESP-{pe.id}",

            'tipo': 'PRECIOS',

            'subtipo': 'Precio Especial Autorizado',

            'badge_clase': 'badge-status-info',

            'icono': 'bi-tags-fill text-info',

            'titulo': f"Precio Especial: {pe.producto.nombre}",

            'descripcion': f"${int(pe.precio_original):,} -> ${int(pe.precio_aplicado):,} (Ahorro unit: ${int(pe.descuento_unitario):,}). Motivo: {pe.motivo} (Venta #{pe.venta.id})",

            'usuario': pe.usuario.get_full_name() or pe.usuario.username,

            'local': local_p.nombre if local_p else "Parque Safari General",

            'local_id': str(local_p.id) if local_p else None,

            'fecha_hora': pe.fecha_hora,

            'monto': pe.precio_aplicado * pe.cantidad,

            'estado': 'APLICADO',

        })



    # 8. Eventos de Reimpresión de Tickets (RF08.6)

    reimpresiones_qs = Ticket.objects.filter(es_reimpresion=True).select_related('venta', 'pedido', 'ultima_reimpresion_por', 'venta__punto_venta')

    for tr in reimpresiones_qs:

        local_t = tr.venta.punto_venta if (tr.venta and tr.venta.punto_venta) else None

        usu_r = (tr.ultima_reimpresion_por.get_full_name() or tr.ultima_reimpresion_por.username) if tr.ultima_reimpresion_por else "Supervisión"

        eventos.append({

            'id_ref': f"REIMP-{tr.codigo}",

            'tipo': 'TICKETS',

            'subtipo': f"Reimpresión de Ticket ({tr.get_tipo_destino_display()})",

            'badge_clase': 'badge-status-warning',

            'icono': 'bi-printer-fill text-warning',

            'titulo': f"Reimpresión {tr.codigo} (Copia #{tr.numero_reimpresiones})",

            'descripcion': f"Reimpresión de ticket {tr.get_tipo_destino_display()} ({'Venta #' + str(tr.venta.id) if tr.venta else 'Pedido #' + str(tr.pedido_id)}).",

            'usuario': usu_r,

            'local': local_t.nombre if local_t else "Parque Safari General",

            'local_id': str(local_t.id) if local_t else None,

            'fecha_hora': tr.fecha_hora_reimpresion or tr.fecha_hora,

            'monto': tr.venta.total if tr.venta else None,

            'estado': 'REIMPRESO',

        })



    # 9. Eventos de Consumo Interno y Fiados del Personal (RF10)

    consumos_qs = ConsumoInterno.objects.select_related('empleado', 'punto_venta', 'registrado_por', 'descontado_por').all()

    for ci in consumos_qs:

        emp_nom = ci.empleado.get_full_name() or ci.empleado.username

        reg_nom = ci.registrado_por.get_full_name() or ci.registrado_por.username if ci.registrado_por else "Cajero"

        if ci.estado == 'REGISTRADO':

            badge_ci = 'badge-status-warning'

            icono_ci = 'bi-wallet2 text-warning'

        elif ci.estado == 'DESCONTADO':

            badge_ci = 'badge-status-success'

            icono_ci = 'bi-check-all text-success'

        else:

            badge_ci = 'badge-status-danger'

            icono_ci = 'bi-x-circle text-danger'



        desc_txt = f"{ci.get_tipo_consumo_display()} para {emp_nom} (${int(ci.total):,} CLP). Registrado por: {reg_nom}."

        if ci.observaciones:

            desc_txt += f" Obs: {ci.observaciones}"

        if ci.estado == 'DESCONTADO' and ci.descontado_por:

            desc_txt += f" (Liquidado por {ci.descontado_por.username})"



        eventos.append({

            'id_ref': f"FIA-{ci.id:04d}",

            'tipo': 'CONSUMO_INTERNO',

            'subtipo': f"Consumo {ci.get_tipo_consumo_display()}",

            'badge_clase': badge_ci,

            'icono': icono_ci,

            'titulo': f"Consumo Personal: {emp_nom} (${int(ci.total):,} CLP)",

            'descripcion': desc_txt,

            'usuario': reg_nom,

            'local': ci.punto_venta.nombre if ci.punto_venta else "Parque Safari General",

            'local_id': str(ci.punto_venta.id) if ci.punto_venta else None,

            'fecha_hora': ci.fecha_hora,

            'monto': ci.total,

            'estado': ci.get_estado_display(),

        })



    # Ordenar cronológicamente descendente (lo más reciente primero)

    eventos.sort(key=lambda x: x['fecha_hora'], reverse=True)



    # Conteo de KPIs globales

    total_eventos = len(eventos)

    total_jornadas = sum(1 for e in eventos if e['tipo'] == 'JORNADA')

    total_cajas = sum(1 for e in eventos if e['tipo'] == 'CAJA')

    total_traslados = sum(1 for e in eventos if e['tipo'] == 'TRASLADO')

    total_ventas = sum(1 for e in eventos if e['tipo'] == 'VENTA')

    total_cocina = sum(1 for e in eventos if e['tipo'] == 'COCINA')



    # Filtro por tipo

    if tipo_filtro and tipo_filtro != 'TODOS':

        eventos = [e for e in eventos if e['tipo'] == tipo_filtro]



    # Filtro por local

    if local_filtro:

        eventos = [e for e in eventos if e['local_id'] == local_filtro]



    # Búsqueda libre

    if busqueda:

        eventos = [

            e for e in eventos

            if busqueda in e['titulo'].lower()

            or busqueda in e['descripcion'].lower()

            or busqueda in e['usuario'].lower()

            or busqueda in e['local'].lower()

            or busqueda in e['id_ref'].lower()

        ]



    locales_disponibles = PuntoVenta.objects.filter(activo=True).order_by('nombre')



    context = {

        'eventos': eventos,

        'total_eventos_filtrados': len(eventos),

        'total_eventos': total_eventos,

        'total_jornadas': total_jornadas,

        'total_cajas': total_cajas,

        'total_traslados': total_traslados,

        'total_ventas': total_ventas,

        'total_cocina': total_cocina,

        'locales_disponibles': locales_disponibles,

        'tipo_filtro': tipo_filtro,

        'local_filtro': local_filtro,

        'busqueda': busqueda,

    }

    return render(request, 'ventas/administrador/administrador_historial.html', context)





@requiere_rol(['ADMINISTRADOR'])

def administrador_dashboard(request):

    """

    Página de Dashboard Analítico y Estadístico Oficial Parque Safari (RF18):

    - 100% gobernado por datos reales de BD (cero mocks).

    - Filtros por rango de fechas (fecha_inicio, fecha_fin), local gastronómico y usuario.

    - Ventas reales, ticket promedio y desglose por medio de pago / modalidad.

    - Ranking real de productos más vendidos.

    - Métricas reales de tiempos de atención (cola, preparación y despacho).

    - Métricas reales de rotación y ocupación de mesas (RF17).

    """

    from ventas.utils import generar_reporte_estadistico_integral



    fecha_inicio = request.GET.get('fecha_inicio')

    fecha_fin = request.GET.get('fecha_fin')

    local_id = request.GET.get('local_id')

    usuario_id = request.GET.get('usuario_id')

    modalidad = request.GET.get('modalidad')



    reporte = generar_reporte_estadistico_integral(

        fecha_inicio=fecha_inicio,

        fecha_fin=fecha_fin,

        punto_venta=local_id,

        usuario=usuario_id,

        modalidad=modalidad

    )



    locales = PuntoVenta.objects.filter(activo=True).order_by('nombre')

    usuarios = User.objects.filter(perfil__isnull=False).select_related('perfil').order_by('first_name', 'last_name')



    historico_mensual = reporte['historico_mensual']

    ultimo_mes = historico_mensual[-1] if historico_mensual else {

        'mes': timezone.localdate().strftime('%b %Y'),

        'ventas': reporte['ventas']['total_recaudado'],

        'ganancia': int(round(reporte['ventas'].get('total_neto_sin_iva', 0) * 0.46)),

        'margen': 46.0,

        'crecimiento': 0.0,

        'tickets': reporte['ventas']['cantidad_ventas']

    }



    import json

    context = {

        "reporte": reporte,

        "filtros": reporte['filtros'],

        "ventas": reporte['ventas'],

        "ranking_productos": reporte['ranking_productos'],

        "tiempos": reporte['tiempos_atencion'],

        "ocupacion": reporte['ocupacion_mesas'],

        "historico_15_meses": historico_mensual,

        "chart_data": reporte['chart_data'],

        "chart_data_json": json.dumps(reporte['chart_data']),

        "ganancia_mes_actual": ultimo_mes.get('ganancia', 0),

        "ventas_mes_actual": ultimo_mes.get('ventas', 0),

        "crecimiento_mes": ultimo_mes.get('crecimiento', 0.0),

        "crecimiento_interanual": 0.0,

        "locales": locales,

        "usuarios": usuarios,

    }

    return render(request, 'ventas/administrador/administrador_dashboard.html', context)





def _validar_jornada_y_caja_abierta_local(punto_venta, caja_asignada=None, exigir_caja_asignada=False, lock=False):
    """
    Valida de forma uniforme si el local posee una Jornada operativa ABIERTA hoy y una Caja ABIERTA.
    Nunca autocrea jornadas; devuelve `(jornada, caja, error_msg)` para bloquear atención sin apertura.
    """
    hoy = timezone.localdate()
    jornada_qs = Jornada.objects.select_for_update() if lock else Jornada.objects
    jornada = jornada_qs.filter(estado='ABIERTA', fecha=hoy).first()
    if not jornada:
        return (
            None,
            None,
            "No hay una jornada operativa abierta hoy. Solicita al cajero o administrador abrir jornada y caja antes de atender.",
        )

    if exigir_caja_asignada:
        if (
            caja_asignada is not None
            and caja_asignada.jornada_id == jornada.id
            and caja_asignada.estado == 'ABIERTA'
            and (not punto_venta or caja_asignada.punto_venta_id == punto_venta.id)
        ):
            return jornada, caja_asignada, None
        return (
            jornada,
            None,
            "Debes abrir tu caja operativa antes de atender clientes, asignar mesas o emitir tickets.",
        )

    cajas_qs = Caja.objects.select_for_update() if lock else Caja.objects
    caja = cajas_qs.filter(punto_venta=punto_venta, jornada=jornada, estado='ABIERTA').first()
    if not caja:
        caja_cerrada = Caja.objects.filter(punto_venta=punto_venta, jornada=jornada, estado='CERRADA').exists()
        if caja_cerrada:
            return (
                jornada,
                None,
                "La caja del local está cerrada. Solicita al cajero abrir caja antes de atender mesas o emitir comandas.",
            )
        return (
            jornada,
            None,
            "No hay ninguna caja abierta en este local. Solicita al cajero abrir caja antes de atender mesas o emitir comandas.",
        )
    return jornada, caja, None


def _resolver_local_operativo(request, locales_qs, predeterminar_id=None):
    """
    Resuelve el PuntoVenta operativo aplicando Row-Level Security estricto:
    - Colaborador con punto_venta_actual asignado queda bloqueado en su local.
    - ADMINISTRADOR o superusuario sin local fijo puede filtrar vía ?local_id=.
    - Colaborador sin local asignado no puede seleccionar otro local por ?local_id=.
    """
    perfil = getattr(request.user, 'perfil', None)
    if perfil and perfil.punto_venta_actual:
        return perfil.punto_venta_actual, False

    es_admin = bool(request.user.is_superuser or (perfil and perfil.rol == 'ADMINISTRADOR'))
    if not es_admin:
        return None, True

    local_id_raw = request.GET.get('local_id')
    if local_id_raw:
        return get_object_or_404(PuntoVenta, id=int(local_id_raw)) if str(local_id_raw).isdigit() else locales_qs.first(), False
    if predeterminar_id is not None:
        return PuntoVenta.objects.filter(id=predeterminar_id).first() or locales_qs.first(), False
    return locales_qs.first(), False


@requiere_rol(['MESERO'])

def mesero(request):

    """Módulo Dinámico para Meseros: Asignación de Mesas, Pedidos en Vivo y Desglose de Comandas por Zona (Cocina / Barra)"""

    proteger_contingencia_operativa(usuario=request.user)

    perfil_usuario = getattr(request.user, 'perfil', None)

    locales = PuntoVenta.objects.filter(activo=True).order_by('id')



    # Regla de Negocio + RLS: El mesero no puede cambiarse de local ni acceder sin puesto asignado

    local_actual, bloqueado_rls = _resolver_local_operativo(request, locales, predeterminar_id=1)

    if bloqueado_rls:

        return HttpResponse("Acceso denegado (RLS): no tienes un punto de venta asignado.", status=403)



    # Mesero activo es el colaborador autenticado en sesión

    mesero_activo = perfil_usuario

    meseros = PerfilEmpleado.objects.filter(rol='MESERO', activo=True).select_related('usuario', 'punto_venta_actual')



    # Procesar acciones POST

    if request.method == 'POST':

        accion = request.POST.get('accion')

        mesa_id = request.POST.get('mesa_id')



        if accion == 'liberar_mesa':

            from ventas.utils import liberar_mesa_operativa

            mesa_obj = Mesa.objects.filter(id=mesa_id, punto_venta=local_actual).first()

            if not mesa_obj:

                messages.error(request, "La mesa solicitada no existe o no pertenece a este local.")

            else:

                exito, msg = liberar_mesa_operativa(mesa_obj, usuario=request.user, forzar=False)

                if exito:

                    messages.success(request, msg)

                else:

                    messages.error(request, msg)

            return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



        elif accion == 'ocupar_mesa':
            es_ajax_mesa = (
                request.headers.get('x-requested-with') == 'XMLHttpRequest'
                or 'application/json' in request.headers.get('accept', '')
            )
            try:
                mesa_id_int = int(mesa_id)
            except (ValueError, TypeError):
                err_mesa = "Debes especificar una mesa válida para operar."
                if es_ajax_mesa:
                    return JsonResponse({'ok': False, 'error': err_mesa}, status=400)
                messages.error(request, err_mesa)
                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")

            from ventas.utils import validar_ocupacion_mesa

            with transaction.atomic():
                _, _, err_caja = _validar_jornada_y_caja_abierta_local(local_actual, lock=True)
                if err_caja:
                    if es_ajax_mesa:
                        return JsonResponse({'ok': False, 'error': err_caja}, status=400)
                    messages.error(request, err_caja)
                    return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")

                mesa_obj = Mesa.objects.select_for_update().filter(id=mesa_id_int, punto_venta=local_actual).first()
                if not mesa_obj:
                    err_no_mesa = "La mesa solicitada no existe o no pertenece a este local."
                    if es_ajax_mesa:
                        return JsonResponse({'ok': False, 'error': err_no_mesa}, status=400)
                    messages.error(request, err_no_mesa)
                else:
                    try:
                        validar_ocupacion_mesa(mesa_obj)
                        mesa_obj.ocupar()
                        msg_ok = f"Mesa {mesa_obj.identificador} asignada y marcada como ocupada (RF17)."
                        if es_ajax_mesa:
                            return JsonResponse({'ok': True, 'mensaje': msg_ok, 'mesa_id': mesa_obj.id, 'estado': mesa_obj.estado})
                        messages.success(request, msg_ok)
                    except ValidationError as e:
                        err = e.message if hasattr(e, 'message') else str(e)
                        if es_ajax_mesa:
                            return JsonResponse({'ok': False, 'error': err}, status=400)
                        messages.error(request, err)

            return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



        elif accion == 'cerrar_cuenta_mesa':

            es_ajax_cobro = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')

            metodo_pago = request.POST.get('metodo_pago', 'EFECTIVO').upper()

            if metodo_pago not in ['EFECTIVO', 'DEBITO', 'CREDITO', 'TRANSFERENCIA']:

                if es_ajax_cobro:

                    return JsonResponse({'ok': False, 'error': f"Método de pago '{metodo_pago}' no permitido."}, status=400)

                messages.error(request, f"Método de pago '{metodo_pago}' no permitido.")

                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



            with transaction.atomic():

                mesa_obj = get_object_or_404(Mesa.objects.select_for_update(), id=mesa_id, punto_venta=local_actual)

                venta_abierta = Venta.objects.select_for_update().filter(

                    mesa=mesa_obj,

                    punto_venta=local_actual,

                    estado='ABIERTA'

                ).first()



                if venta_abierta:

                    caja_cobro = venta_abierta.caja

                    if (
                        not caja_cobro
                        or caja_cobro.estado != 'ABIERTA'
                        or (caja_cobro.jornada and caja_cobro.jornada.estado != 'ABIERTA')
                    ):

                        caja_cobro = Caja.objects.select_for_update().filter(

                            punto_venta=local_actual,

                            estado='ABIERTA',

                            jornada__estado='ABIERTA',

                        ).first()

                    if not caja_cobro:

                        err_caja = "No hay una caja abierta en este local para registrar cobros. Solicita al cajero abrir caja."

                        if es_ajax_cobro:

                            return JsonResponse({'ok': False, 'error': err_caja}, status=400)

                        messages.error(request, err_caja)

                        return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



                    from ventas.utils import calcular_redondeo_ley_20956

                    monto_pago_raw = request.POST.get('monto_pago')

                    monto_pago = None

                    if monto_pago_raw:

                        try:

                            monto_pago = Decimal(str(monto_pago_raw))

                        except Exception:

                            monto_pago = None



                    # Base de consumo gastronómico (alimentos y bebidas sujetos a IVA 19%)

                    base_consumo = monto_pago if (monto_pago and Decimal('0') < monto_pago < venta_abierta.total) else venta_abierta.total



                    # Opciones Dinámicas de Propina (0%, 10%, 15%, 20% o personalizada - EXENTA DE IVA Ley 20.918)

                    porcentaje_propina = 0

                    monto_propina_calculada = Decimal('0')

                    pct_raw = request.POST.get('porcentaje_propina')

                    monto_propina_raw = request.POST.get('monto_propina')

                    incluir_propina = request.POST.get('incluir_propina') in ['1', 'true', 'on', True]



                    if pct_raw is not None and str(pct_raw).strip() != '':

                        try:

                            porcentaje_propina = max(0, min(100, int(pct_raw)))

                            monto_propina_calculada = Decimal(str(int(round(base_consumo * Decimal(str(porcentaje_propina)) / Decimal('100')))))

                        except (ValueError, TypeError):

                            porcentaje_propina = 0

                    elif monto_propina_raw is not None and str(monto_propina_raw).strip() != '':

                        try:

                            monto_propina_calculada = max(Decimal('0'), Decimal(str(monto_propina_raw)))

                            if base_consumo > 0:

                                porcentaje_propina = int(round((monto_propina_calculada / base_consumo) * Decimal('100')))

                        except Exception:

                            monto_propina_calculada = Decimal('0')

                    elif incluir_propina:

                        porcentaje_propina = 10

                        monto_propina_calculada = Decimal(str(int(round(base_consumo * Decimal('0.10')))))



                    # Soporte para División de Cuentas / Abono Parcial en Mesero (Split Bill)

                    if monto_pago and Decimal('0') < monto_pago < venta_abierta.total:

                        monto_abono = monto_pago

                        total_con_propina = monto_abono + monto_propina_calculada

                        monto_final, ajuste_redondeo = calcular_redondeo_ley_20956(total_con_propina, metodo_pago)

                        saldo_restante = max(Decimal('0'), venta_abierta.total - monto_pago)



                        venta_parcial = Venta.objects.create(

                            caja=caja_cobro,

                            cajero=request.user,

                            punto_venta=local_actual,

                            modalidad='MESA',

                            mesa=mesa_obj,

                            venta_origen=venta_abierta,

                            metodo_pago=metodo_pago,

                            propina=monto_propina_calculada,

                            porcentaje_propina=porcentaje_propina,

                            total_sin_redondeo=total_con_propina,

                            redondeo_ley_20956=ajuste_redondeo,

                            total=monto_final,

                            estado='PAGADA'

                        )

                        emitir_comprobante_venta(venta_parcial, usuario_emisor=request.user)



                        venta_abierta.monto_abonado_parcial = (venta_abierta.monto_abonado_parcial or Decimal('0.00')) + monto_abono

                        venta_abierta.total = saldo_restante

                        venta_abierta.save()



                        mesa_obj.estado = 'OCUPADA'

                        mesa_obj.save(update_fields=['estado'])



                        msg_ok = f"Abono parcial de ${int(monto_final):,} CLP registrado para {mesa_obj.identificador}. Saldo pendiente de la mesa: ${int(saldo_restante):,} CLP."

                        messages.success(request, msg_ok)

                        return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



                    monto_consumo_total = venta_abierta.total

                    total_con_propina = monto_consumo_total + monto_propina_calculada

                    monto_final, ajuste_redondeo = calcular_redondeo_ley_20956(total_con_propina, metodo_pago)

                    if venta_abierta.caja_id != caja_cobro.id:

                        venta_abierta.caja = caja_cobro

                    venta_abierta.propina = monto_propina_calculada

                    venta_abierta.porcentaje_propina = porcentaje_propina

                    venta_abierta.total_sin_redondeo = total_con_propina

                    venta_abierta.redondeo_ley_20956 = ajuste_redondeo

                    venta_abierta.total = monto_final

                    venta_abierta.estado = 'PAGADA'

                    venta_abierta.metodo_pago = metodo_pago

                    venta_abierta.save()



                    # RF08.4: Emisión de comprobante de venta de comensal

                    emitir_comprobante_venta(venta_abierta, usuario_emisor=request.user)



                    mesa_obj.liberar(forzar=True)



                    total_formateado = f"${int(venta_abierta.total):,}".replace(",", ".")

                    txt_redondeo = f" (Ajuste Ley 20.956 en efectivo: {'+' if ajuste_redondeo > 0 else ''}${int(ajuste_redondeo):,} CLP)" if ajuste_redondeo != 0 else ""

                    messages.success(request, f"¡Cuenta de {mesa_obj.identificador} pagada y cerrada exitosamente con {metodo_pago}! Total recaudado: {total_formateado}{txt_redondeo}. La mesa ha quedado libre para nuevos comensales.")

                else:

                    mesa_obj.liberar(forzar=True)

                    messages.info(request, f"Mesa {mesa_obj.identificador} liberada.")



            return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



        elif accion == 'reasignar_mesa':

            mesa_origen_id = request.POST.get('mesa_origen_id') or mesa_id

            mesa_destino_id = request.POST.get('mesa_destino_id')

            motivo = request.POST.get('motivo', '').strip()[:200]



            if not mesa_origen_id:

                messages.error(request, "Debe especificar la mesa de origen para realizar la reasignación.")

                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



            if not mesa_destino_id:

                messages.error(request, "Debe seleccionar una mesa de destino válida para trasladar la atención.")

                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



            try:

                mesa_origen_id = int(mesa_origen_id)

                mesa_destino_id = int(mesa_destino_id)

            except (ValueError, TypeError):

                messages.error(request, "Los identificadores de mesa deben ser valores numéricos válidos.")

                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



            if mesa_origen_id == mesa_destino_id:

                messages.warning(request, "La mesa de destino no puede ser la misma mesa de origen.")

                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



            with transaction.atomic():

                mesa_origen = Mesa.objects.select_for_update().filter(id=mesa_origen_id).first()

                mesa_destino = Mesa.objects.select_for_update().filter(id=mesa_destino_id).first()



                if not mesa_origen:

                    messages.error(request, "La mesa de origen no existe en el sistema.")

                    return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



                if not mesa_destino:

                    messages.error(request, "La mesa de destino no existe en el sistema.")

                    return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



                # Validación de aislamiento: no permitir traslados entre Puntos de Venta distintos

                if mesa_origen.punto_venta_id != local_actual.id or mesa_destino.punto_venta_id != local_actual.id:

                    messages.error(request, "Operación denegada: No se permite reasignar cuentas entre mesas de distintos Puntos de Venta o locales.")

                    return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



                # Buscar la venta abierta en la mesa de origen

                venta_abierta = Venta.objects.select_for_update().filter(

                    mesa=mesa_origen,

                    punto_venta=local_actual,

                    estado='ABIERTA'

                ).first()



                if not venta_abierta:

                    messages.error(request, f"La {mesa_origen.identificador} no posee una cuenta abierta para trasladar (la mesa pudo haber sido cerrada o liberada por otro colaborador).")

                    return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



                # Validar estado inactivo de la mesa destino

                if mesa_destino.estado == 'INACTIVA':

                    messages.error(request, f"No es posible reasignar a {mesa_destino.identificador} porque se encuentra deshabilitada o en mantenimiento.")

                    return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



                # Validar si mesa destino ya está ocupada o tiene cuenta abierta

                cuenta_destino_abierta = Venta.objects.filter(

                    mesa=mesa_destino,

                    punto_venta=local_actual,

                    estado='ABIERTA'

                ).exists()



                if mesa_destino.estado == 'OCUPADA' or cuenta_destino_abierta:

                    messages.error(request, f"No es posible el traslado: {mesa_destino.identificador} ya se encuentra ocupada con otra atención activa.")

                    return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



                # Reasignar la venta a la mesa destino (manteniendo intactos pedidos, rondas, productos y tickets)

                venta_abierta.mesa = mesa_destino

                venta_abierta.save()



                # Actualizar estado de mesa destino a OCUPADA conservando timestamp de inicio (RF17)

                mesa_destino.fecha_ocupacion = mesa_origen.fecha_ocupacion or venta_abierta.fecha_hora

                mesa_destino.estado = 'OCUPADA'

                mesa_destino.save(update_fields=['estado', 'fecha_ocupacion'])



                # Liberar mesa origen si no posee otras cuentas abiertas (RF17)

                otras_abiertas_origen = Venta.objects.filter(

                    mesa=mesa_origen,

                    punto_venta=local_actual,

                    estado='ABIERTA'

                ).exclude(id=venta_abierta.id).exists()



                if not otras_abiertas_origen:

                    mesa_origen.liberar(forzar=True)



                # Registrar auditoría histórica permanente (RF05)

                motivo_limpio = motivo or "Solicitud de cambio de mesa por comensal"

                ReasignacionMesa.objects.create(

                    venta=venta_abierta,

                    mesa_origen=mesa_origen,

                    mesa_destino=mesa_destino,

                    mesero=request.user,

                    motivo=motivo_limpio

                )



                rondas_count = venta_abierta.pedidos.count()

                total_fmt = f"${int(venta_abierta.total):,}".replace(",", ".")

                messages.success(

                    request,

                    f"¡Mesa reasignada exitosamente (RF05)! La cuenta de {mesa_origen.identificador} "

                    f"({total_fmt} en {rondas_count} {'ronda' if rondas_count == 1 else 'rondas'}) "

                    f"fue trasladada a {mesa_destino.identificador}. {mesa_origen.identificador} ha quedado libre."

                )



            return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



        elif accion == 'enviar_comanda':

            es_ajax_req = (
                request.headers.get('x-requested-with') == 'XMLHttpRequest'
                or 'application/json' in request.headers.get('accept', '')
            )

            if not mesa_id:

                err_msg = "Debe seleccionar una mesa válida para emitir pedidos en salón (RF11.1)."

                if es_ajax_req:

                    return JsonResponse({'ok': False, 'error': err_msg}, status=400)

                messages.error(request, err_msg)

                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



            mesa_obj = Mesa.objects.filter(id=mesa_id).first()

            if not mesa_obj or mesa_obj.punto_venta_id != local_actual.id:

                err_msg = "La mesa seleccionada no existe o no pertenece al local gastronómico actual."

                if es_ajax_req:

                    return JsonResponse({'ok': False, 'error': err_msg}, status=400)

                messages.error(request, err_msg)

                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



            if mesa_obj.estado == 'INACTIVA':

                err_msg = f"No es posible emitir pedidos en la mesa {mesa_obj.identificador} porque se encuentra inactiva o en mantenimiento (RF17)."

                if es_ajax_req:

                    return JsonResponse({'ok': False, 'error': err_msg}, status=400)

                messages.error(request, err_msg)

                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



            items_raw = request.POST.get('items_json', '[]')

            try:

                items_lista = json.loads(items_raw)

            except Exception:

                items_lista = []



            # Sanitización de ítems: filtrar datos malformados y asegurar cantidades válidas (OWASP)

            items_validos = []

            for it in items_lista:

                try:

                    cant = max(1, int(it.get('cantidad', 1)))

                    raw_id = it.get('id') or it.get('producto_id')

                    p_id_int = int(raw_id) if raw_id and str(raw_id).isdigit() else None

                    items_validos.append({

                        'id': p_id_int,

                        'nombre': str(it.get('nombre', '')).strip()[:120],

                        'precio_especial': it.get('precio_especial'),

                        'cantidad': cant,

                        'nota': str(it.get('nota', '') or '').replace('\x00', '').strip()[:100],

                        'destino': 'BARRA' if it.get('destino') == 'BARRA' else 'COCINA',

                        'convenio_id': it.get('convenio_id'),

                        'motivo': (it.get('motivo_precio_especial') or it.get('motivo') or '').strip()

                    })

                except (ValueError, TypeError):

                    continue



            if not items_validos:

                err_msg = "La comanda debe contener al menos un producto válido."

                if es_ajax_req:

                    return JsonResponse({'ok': False, 'error': err_msg}, status=400)

                messages.error(request, err_msg)

                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



            hoy = timezone.localdate()

            with transaction.atomic():
                mesa_obj = Mesa.objects.select_for_update().filter(id=mesa_obj.id, punto_venta=local_actual).first()
                if not mesa_obj:
                    err_mesa = "La mesa solicitada no existe o no pertenece a este local."
                    if es_ajax_req:
                        return JsonResponse({'ok': False, 'error': err_mesa}, status=400)
                    messages.error(request, err_mesa)
                    return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")

                jornada, caja, err_caja = _validar_jornada_y_caja_abierta_local(local_actual, lock=True)
                if err_caja or not caja:
                    if es_ajax_req:
                        return JsonResponse({'ok': False, 'error': err_caja}, status=400)
                    messages.error(request, err_caja)
                    return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



                es_autorizado_precio = (

                    request.user.is_superuser or request.user.is_staff or

                    (hasattr(request.user, 'perfil') and request.user.perfil.rol in ['ADMINISTRADOR', 'CAJERO'])

                )

                lineas_procesadas = []

                subtotal_acumulado_ronda = Decimal('0')



                for it in items_validos:

                    p_id = it.get('id')

                    p_nom = it['nombre']

                    p_precio_esp = it.get('precio_especial')

                    p_cant = it['cantidad']

                    p_conv_id = it.get('convenio_id')

                    p_motivo = it.get('motivo')



                    prod_obj = None

                    if p_id:

                        prod_obj = Producto.objects.filter(id=p_id).first()

                    if not prod_obj and p_nom:

                        prod_obj = Producto.objects.filter(nombre__iexact=p_nom).first()

                    if not prod_obj and p_nom:

                        prod_obj = Producto.objects.filter(nombre=p_nom).first()



                    if not prod_obj:

                        err_msg = f"El producto '{p_nom or p_id}' no existe en el catálogo."

                        if es_ajax_req:

                            return JsonResponse({'ok': False, 'error': err_msg}, status=400)

                        messages.error(request, err_msg)

                        return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



                    try:

                        validar_disponibilidad_producto(prod_obj, local_actual)

                    except ValidationError as ve:

                        err_msg = ve.message if hasattr(ve, 'message') else str(ve)

                        if es_ajax_req:

                            return JsonResponse({'ok': False, 'error': err_msg}, status=400)

                        messages.error(request, err_msg)

                        return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



                    # RF07: Validación y cálculo servidor-autoritativo (ignora precio genérico del cliente; exige precio_especial + motivo)

                    precio_req = None

                    if es_autorizado_precio and p_precio_esp is not None:

                        try:

                            p_dec = Decimal(str(p_precio_esp))

                            if p_dec != prod_obj.precio_base:

                                precio_req = p_dec

                        except Exception:

                            precio_req = None



                    if precio_req is not None and not p_motivo:

                        err_msg = "Debes ingresar un motivo explícito para aplicar un precio especial."

                        if es_ajax_req:

                            return JsonResponse({'ok': False, 'error': err_msg}, status=400)

                        messages.error(request, err_msg)

                        return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



                    try:

                        calc = validar_y_calcular_precio_linea(

                            producto=prod_obj,

                            cantidad=p_cant,

                            precio_solicitado=precio_req,

                            convenio_id=p_conv_id,

                            usuario=request.user,

                            motivo=p_motivo,

                            permite_manual=bool(es_autorizado_precio and precio_req is not None and p_motivo)

                        )

                    except ValidationError:

                        calc = validar_y_calcular_precio_linea(

                            producto=prod_obj,

                            cantidad=p_cant,

                            precio_solicitado=None,

                            convenio_id=None,

                            usuario=request.user,

                            permite_manual=False

                        )



                    if calc['es_precio_especial']:

                        total_item = calc['subtotal']

                        texto_promo = calc['motivo']

                    else:

                        total_item, ahorro_item, texto_promo = prod_obj.calcular_total_promocion(p_cant)



                    subtotal_acumulado_ronda += total_item

                    lineas_procesadas.append((it, prod_obj, calc, total_item, texto_promo))



                if not caja:

                    caja = Caja.objects.create(

                        jornada=jornada,

                        cajero=request.user,

                        nombre=f"Caja {local_actual.nombre.split()[0]} - {request.user.first_name or request.user.username}",

                        punto_venta=local_actual,

                        monto_apertura=0,

                        estado='ABIERTA',

                        observaciones='Caja de comandas y pedidos de salón'

                    )



                # Regla de Cuenta Abierta: Si la mesa ya tiene una venta ABIERTA hoy, acumular preservando abonos parciales

                venta_abierta = Venta.objects.select_for_update().filter(

                    mesa=mesa_obj,

                    punto_venta=local_actual,

                    estado='ABIERTA',

                    fecha_hora__date=hoy

                ).first()



                if venta_abierta:

                    if not venta_abierta.caja or venta_abierta.caja.estado != 'ABIERTA':

                        venta_abierta.caja = caja

                    venta = venta_abierta

                    venta.total = (venta.total or Decimal('0')) + subtotal_acumulado_ronda

                    venta.total_sin_redondeo = (venta.total_sin_redondeo or Decimal('0')) + subtotal_acumulado_ronda

                    venta.save()

                    es_ronda_adicional = True

                else:

                    venta = Venta.objects.create(

                        caja=caja,

                        cajero=request.user,

                        punto_venta=local_actual,

                        modalidad='MESA',

                        mesa=mesa_obj,

                        metodo_pago='EFECTIVO',

                        total=subtotal_acumulado_ronda,

                        total_sin_redondeo=subtotal_acumulado_ronda,

                        estado='ABIERTA'

                    )

                    es_ronda_adicional = False



                if mesa_obj:

                    if mesa_obj.estado == 'HABILITADA':

                        mesa_obj.ocupar()

                    elif mesa_obj.estado != 'OCUPADA':

                        mesa_obj.estado = 'OCUPADA'

                        mesa_obj.save(update_fields=['estado'])

                    elif not mesa_obj.fecha_ocupacion:

                        mesa_obj.fecha_ocupacion = timezone.now()

                        mesa_obj.save(update_fields=['fecha_ocupacion'])



                num_ronda = venta.pedidos.count() + 1

                nuevo_pedido = Pedido.objects.create(

                    venta=venta,

                    estado='PENDIENTE',

                    observaciones=f"Ronda #{num_ronda} enviada por mesero {request.user.get_full_name() or request.user.username} para {mesa_obj.identificador if mesa_obj else 'Mesa'}"

                )



                for it, prod_obj, calc, total_item, texto_promo in lineas_procesadas:

                    det = DetalleVenta.objects.create(

                        venta=venta,

                        producto=prod_obj,

                        cantidad=calc['cantidad'],

                        precio_aplicado=calc['precio_aplicado'],

                        subtotal=total_item,

                        precio_original=calc['precio_original'],

                        es_precio_especial=calc['es_precio_especial'],

                        motivo_precio_especial=calc['motivo'],

                        autorizado_por=calc['autorizado_por']

                    )



                    if calc['es_precio_especial']:

                        registrar_precio_especial_auditoria(venta, det, calc)



                    nota_item = it['nota']

                    if texto_promo:

                        nota_item = f"{nota_item} [{texto_promo}]".strip()

                    DetallePedido.objects.create(

                        pedido=nuevo_pedido,

                        producto=prod_obj,

                        cantidad=calc['cantidad'],

                        observaciones=nota_item

                    )



                # RF08: Clasificación por BD e incrementalidad de tickets (Cocina / Barra / Cero vacíos)

                ticket_info = emitir_tickets_comanda(nuevo_pedido, usuario_emisor=request.user)

                zonas_despachadas = []

                if ticket_info['tiene_cocina']:

                    zonas_despachadas.append("Cocina")

                if ticket_info['tiene_barra']:

                    zonas_despachadas.append("Barra")

                if not zonas_despachadas:

                    zonas_despachadas.append("Producción")



                zonas_txt = " y ".join(zonas_despachadas)



            if es_ronda_adicional:

                total_acumulado_txt = f"${int(venta.total):,}".replace(",", ".")

                msg_ok = f"¡Ronda #{num_ronda} agregada a la cuenta de {mesa_obj.identificador}! Despachada con éxito a {zonas_txt}. Total acumulado: {total_acumulado_txt}"

            else:

                msg_ok = f"¡Cuenta abierta para {mesa_obj.identificador}! Comanda #{nuevo_pedido.id:04d} despachada con éxito a {zonas_txt}. Mesa marcada en atención."



            if es_ajax_req:

                return JsonResponse({

                    'ok': True,

                    'status': 'ok',

                    'venta_id': venta.id,

                    'pedido_id': nuevo_pedido.id,

                    'num_ronda': num_ronda,

                    'total': float(venta.total),

                    'es_ronda_adicional': es_ronda_adicional,

                    'zonas': zonas_txt,

                    'mensaje': msg_ok,

                })



            messages.success(request, msg_ok)

            return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")



    # Mesas del local

    mesas = Mesa.objects.filter(punto_venta=local_actual).order_by('id')

    total_mesas = mesas.count()

    mesas_libres = mesas.filter(estado='HABILITADA').count()

    mesas_ocupadas = mesas.filter(estado='OCUPADA').count()



    # Catálogo de alimentos y bebidas clasificados con destino operativo de comandas (RF15: Fuente de verdad BD)

    if local_actual:

        prods_local = local_actual.get_productos_disponibles().select_related('categoria')

        catalogo_productos = [p.to_mesero_dict() for p in prods_local]

    else:

        catalogo_productos = []



    hoy = timezone.localdate()

    ahora_dt = timezone.localtime()

    ahora_hora = ahora_dt.time()

    hora_apertura = datetime.time(10, 0)

    hora_cierre = datetime.time(18, 0)

    en_horario = (hora_apertura <= ahora_hora < hora_cierre)



    # Cuentas abiertas activas por mesa en este punto de venta (estrictamente del día actual hoy)

    ventas_abiertas = Venta.objects.filter(

        punto_venta=local_actual,

        estado='ABIERTA',

        mesa__isnull=False,

        fecha_hora__date=hoy

    ).select_related('mesa', 'cajero').prefetch_related('detalles__producto', 'pedidos')



    cuentas_abiertas_data = {}

    for va in ventas_abiertas:
        rondas_count = len(va.pedidos.all())
        detalles_list = []
        for d in va.detalles.all():
            detalles_list.append({
                'nombre': d.producto.nombre,
                'cantidad': d.cantidad,
                'precio': int(d.precio_aplicado),
                'subtotal': int(d.subtotal)
            })
        inicio_mesa = va.mesa.fecha_ocupacion or va.fecha_hora
        duracion_min = 0.0
        if inicio_mesa:
            delta_seg = (ahora_dt - timezone.localtime(inicio_mesa)).total_seconds()
            duracion_min = max(0.0, round(delta_seg / 60.0, 1))
        cuentas_abiertas_data[str(va.mesa.id)] = {
            'venta_id': va.id,
            'mesa_id': va.mesa.id,
            'mesa_identificador': va.mesa.identificador,
            'cajero_nombre': va.cajero.get_full_name() or va.cajero.username,
            'total': int(va.total),
            'rondas': rondas_count,
            'hora_apertura': timezone.localtime(va.fecha_hora).strftime('%H:%M'),
            'duracion_minutos': duracion_min,
            'items': detalles_list
        }



    pedidos_listos = Pedido.objects.filter(

        venta__punto_venta=local_actual,

        creado_en__date=hoy

    ).filter(

        Q(estado='LISTO') | Q(estado_cocina='LISTO') | Q(estado_barra='LISTO')

    ).exclude(

        estado__in=['ENTREGADO', 'CANCELADO']

    ).exclude(

        venta__estado__in=['ANULADA', 'CANCELADA']

    ).exclude(

        venta__caja__jornada__estado='CERRADA'

    ).select_related('venta__mesa')



    # Pedidos activos hoy por mesa (incluyendo pedidos pagados en Caja y derivados a mesa del salón)

    pedidos_mesa_activos_data = {}

    pedidos_activos_salon = Pedido.objects.filter(

        venta__punto_venta=local_actual,

        venta__mesa__isnull=False,

        creado_en__date=hoy,

        estado__in=['PENDIENTE', 'EN_PREPARACION', 'LISTO']

    ).exclude(

        venta__estado__in=['ANULADA', 'CANCELADA']

    ).exclude(

        venta__caja__jornada__estado='CERRADA'

    ).select_related('venta__mesa', 'venta__cajero').prefetch_related('detalles__producto').order_by('-creado_en')



    for pa in pedidos_activos_salon:

        m_key = str(pa.venta.mesa_id)

        if m_key not in pedidos_mesa_activos_data:

            pedidos_mesa_activos_data[m_key] = []

        pedidos_mesa_activos_data[m_key].append({

            'pedido_id': pa.id,

            'codigo': f"COM-{pa.id:04d}",

            'estado': pa.estado,

            'estado_display': pa.get_estado_display(),

            'venta_estado': pa.venta.estado,

            'total': int(pa.venta.total),

            'hora': timezone.localtime(pa.creado_en).strftime('%H:%M'),

            'cajero': pa.venta.cajero.get_full_name() or pa.venta.cajero.username,

            'items': [

                {'nombre': d.producto.nombre, 'cantidad': d.cantidad, 'nota': d.observaciones or ''}

                for d in pa.detalles.all()

            ]

        })



    # Tarea 6: Sincronizar ofertas activas de la BD con el catálogo del mesero

    prods_ofertas_map = {p.nombre.lower().strip(): p for p in Producto.objects.filter(activo=True, en_oferta=True)}

    for prod_item in catalogo_productos:

        p_match = prods_ofertas_map.get(prod_item["nombre"].lower().strip())

        if p_match and p_match.precio_oferta is not None and p_match.precio_oferta > 0:

            prod_item["precio_base"] = prod_item["precio"]

            prod_item["precio"] = int(p_match.precio_oferta)

            prod_item["en_oferta"] = True

            prod_item["descripcion_oferta"] = p_match.descripcion_oferta or "¡OFERTA ESPECIAL!"



    jornada_activa, caja_abierta_local, motivo_bloqueo_atencion = _validar_jornada_y_caja_abierta_local(
        local_actual, lock=False
    )
    puede_atender_salon = bool(jornada_activa and caja_abierta_local)

    context = {

        "local_actual": local_actual,

        "locales": locales,

        "meseros": meseros,

        "mesero_activo": mesero_activo,

        "mesas": mesas,

        "total_mesas": total_mesas,

        "mesas_libres": mesas_libres,

        "mesas_ocupadas": mesas_ocupadas,

        "catalogo_productos": catalogo_productos,

        "cuentas_abiertas_json": json.dumps(cuentas_abiertas_data),

        "pedidos_mesa_activos_json": json.dumps(pedidos_mesa_activos_data),

        "pedidos_listos": pedidos_listos,

        "total_pedidos_listos": pedidos_listos.count(),

        "hoy_str": hoy.strftime("%d/%m/%Y"),

        "ahora_hora_str": ahora_dt.strftime("%H:%M"),

        "en_horario": en_horario,

        "jornada_activa": jornada_activa,

        "caja_abierta_local": caja_abierta_local,

        "puede_atender_salon": puede_atender_salon,

        "motivo_bloqueo_atencion": motivo_bloqueo_atencion or "",

        "horario_oficial": "10:00 a 18:00",

    }

    return render(request, 'ventas/mesero/mesero.html', context)





def _obtener_catalogo_stock_estacion(local_actual, estacion):
    """Retorna productos del local filtrados por su destino operativo efectivo (COCINA o BARRA)."""
    if not local_actual:
        return []
    qs = (
        Producto.objects.filter(puntos_venta=local_actual)
        .select_related('categoria')
        .order_by('categoria__nombre', 'nombre')
    )
    return [p for p in qs if p.get_destino_operativo() == estacion]


@requiere_rol(['COCINERO', 'ADMINISTRADOR'])

def cocina(request):

    """

    KDS (Kitchen Display System) - Módulo Operativo de Cocina y Barra.

    Permite al personal de cocina ver los pedidos en cola, gestionar su estado

    de preparación y avisar al personal de salón cuando los platos están listos.

    """

    proteger_contingencia_operativa(usuario=request.user)

    hoy = timezone.localdate()

    ahora_dt = timezone.localtime()

    ahora_hora = ahora_dt.time()

    en_horario = (datetime.time(10, 0) <= ahora_hora < datetime.time(18, 0))



    perfil = getattr(request.user, 'perfil', None)

    locales = PuntoVenta.objects.filter(activo=True).order_by('id')



    # Determinar el local operativo del cocinero respetando RLS

    local_actual, bloqueado_rls = _resolver_local_operativo(request, locales)

    if bloqueado_rls:

        return HttpResponse("Acceso denegado (RLS): no tienes un punto de venta asignado.", status=403)



    # Filtro por destino/zona: 'TODAS', 'COCINA', 'BARRA'

    # Regla estricta de aislamiento Cocina vs Barra:
    # La pantalla de Cocina opera exclusivamente sobre productos destinados a Cocina Caliente/Elaboración.
    zona_filtro = 'COCINA'



    # Consultar pedidos del día activos excluyendo órdenes rezagadas > 4 horas (evita pedidos zombies de 800+ min en KDS)

    hace_4_horas = ahora_dt - datetime.timedelta(hours=4)

    pedidos_qs = Pedido.objects.filter(

        venta__punto_venta=local_actual,

        creado_en__date=hoy,

        creado_en__gte=hace_4_horas,

        estado__in=['PENDIENTE', 'EN_PREPARACION', 'LISTO'],

        estado_cocina__in=['PENDIENTE', 'EN_PREPARACION', 'LISTO']

    ).exclude(

        venta__estado__in=['ANULADA', 'CANCELADA']

    ).exclude(

        venta__caja__jornada__estado='CERRADA'

    ).select_related('venta__mesa', 'venta__cajero').prefetch_related('detalles__producto__categoria', 'tickets').order_by('creado_en')



    pedidos_data = []

    total_pendientes = 0

    total_en_preparacion = 0

    total_listos = 0



    for ped in pedidos_qs:

        tiempo_creacion = timezone.localtime(ped.creado_en)

        minutos = int((ahora_dt - tiempo_creacion).total_seconds() // 60)

        

        items_pedido = []

        tiene_cocina = False

        tiene_barra = False

        

        for det in ped.detalles.all():

            destino_item = det.producto.get_destino_operativo()

            if destino_item == 'BARRA':

                tiene_barra = True

            else:

                tiene_cocina = True



            items_pedido.append({

                'nombre': det.producto.nombre,

                'cantidad': det.cantidad,

                'observaciones': det.observaciones or '',

                'destino': destino_item,

            })



        if not tiene_cocina:
            continue

        items_filtrados = [it for it in items_pedido if it['destino'] == 'COCINA']
        if not items_filtrados:
            continue



        estado_estacion = ped.estado_cocina or ped.estado

        if estado_estacion == 'PENDIENTE':

            total_pendientes += 1

        elif estado_estacion == 'EN_PREPARACION':

            total_en_preparacion += 1

        elif estado_estacion == 'LISTO':

            total_listos += 1



        pedidos_data.append({

            'id': ped.id,

            'codigo_ticket': f"COM-{ped.id:04d}",

            'estado': estado_estacion,

            'estado_display': ped.get_estado_cocina_display(),

            'estado_global': ped.estado,

            'mesa': ped.venta.mesa.identificador if ped.venta.mesa else 'Mostrador / Para Llevar',

            'es_mesa': bool(ped.venta.mesa),

            'cajero': ped.venta.cajero.get_full_name() or ped.venta.cajero.username,

            'hora_creacion': tiempo_creacion.strftime('%H:%M'),

            'minutos_transcurridos': minutos,

            'es_demorado': minutos >= 15,

            'observaciones': ped.observaciones or '',

            'items': items_filtrados,

            'total_unidades': sum(it['cantidad'] for it in items_filtrados),

            'tiene_cocina': tiene_cocina,

            'tiene_barra': tiene_barra,

        })



    ultimos_entregados = Pedido.objects.filter(

        venta__punto_venta=local_actual,

        creado_en__date=hoy,

        estado_cocina='ENTREGADO'

    ).select_related('venta__mesa').order_by('-actualizado_en')[:5]



    catalogo_stock = _obtener_catalogo_stock_estacion(local_actual, 'COCINA')



    context = {

        'local_actual': local_actual,

        'locales': locales,

        'pedidos': pedidos_data,

        'zona_filtro': zona_filtro,

        'total_pendientes': total_pendientes,

        'total_en_preparacion': total_en_preparacion,

        'total_listos': total_listos,

        'total_cola': len(pedidos_data),

        'ultimos_entregados': ultimos_entregados,

        'catalogo_stock': catalogo_stock,

        'hoy_str': hoy.strftime("%d/%m/%Y"),

        'ahora_hora_str': ahora_dt.strftime("%H:%M"),

        'en_horario': en_horario,

        'horario_oficial': "10:00 a 18:00",

    }

    return render(request, 'ventas/kds/cocina.html', context)





@requiere_rol(['COCINERO', 'BARRA', 'ADMINISTRADOR', 'MESERO', 'CAJERO'])





def barra(request):

    """

    BDS (Bar Display System) - Módulo Operativo de Barra & Cafetería (KDS Barra).

    Pantalla táctil dedicada para personal de barra, baristas y bartender.

    Mismas condiciones operativas que Cocina:

    - Sin cronómetro ni desconexión forzada de 15 minutos.

    - Auto-actualización fluida en vivo (1 segundo) con Scroll-Lock.

    - Cero botones manuales de refresco.

    - Visualización exclusiva de productos de Barra (bebidas, jugos, cafetería, snacks).

    """

    proteger_contingencia_operativa(usuario=request.user)

    hoy = timezone.localdate()

    ahora_dt = timezone.localtime()

    ahora_hora = ahora_dt.time()

    en_horario = (datetime.time(10, 0) <= ahora_hora < datetime.time(18, 0))



    perfil = getattr(request.user, 'perfil', None)

    locales = PuntoVenta.objects.filter(activo=True).order_by('id')



    local_actual, bloqueado_rls = _resolver_local_operativo(request, locales)

    if bloqueado_rls:

        return HttpResponse("Acceso denegado (RLS): no tienes un punto de venta asignado.", status=403)



    hace_4_horas = ahora_dt - datetime.timedelta(hours=4)

    pedidos_qs = Pedido.objects.filter(

        venta__punto_venta=local_actual,

        creado_en__date=hoy,

        creado_en__gte=hace_4_horas,

        estado__in=['PENDIENTE', 'EN_PREPARACION', 'LISTO'],

        estado_barra__in=['PENDIENTE', 'EN_PREPARACION', 'LISTO']

    ).exclude(

        venta__estado__in=['ANULADA', 'CANCELADA']

    ).exclude(

        venta__caja__jornada__estado='CERRADA'

    ).select_related('venta__mesa', 'venta__cajero').prefetch_related('detalles__producto__categoria', 'tickets').order_by('creado_en')



    pedidos_data = []

    total_pendientes = 0

    total_en_preparacion = 0

    total_listos = 0



    for ped in pedidos_qs:

        tiempo_creacion = timezone.localtime(ped.creado_en)

        minutos = int((ahora_dt - tiempo_creacion).total_seconds() // 60)



        items_barra = []

        for det in ped.detalles.all():

            dest = det.producto.get_destino_operativo()

            if dest == 'BARRA':

                items_barra.append({

                    'nombre': det.producto.nombre,

                    'cantidad': det.cantidad,

                    'observaciones': det.observaciones or '',

                    'destino': 'BARRA',

                })



        # Solo incluir pedidos que contengan ítems para Barra

        if not items_barra:

            continue



        estado_estacion = ped.estado_barra or ped.estado

        if estado_estacion == 'PENDIENTE':

            total_pendientes += 1

        elif estado_estacion == 'EN_PREPARACION':

            total_en_preparacion += 1

        elif estado_estacion == 'LISTO':

            total_listos += 1



        pedidos_data.append({

            'id': ped.id,

            'codigo_ticket': f"BAR-{ped.id:04d}",

            'estado': estado_estacion,

            'estado_display': ped.get_estado_barra_display(),

            'estado_global': ped.estado,

            'mesa': ped.venta.mesa.identificador if ped.venta.mesa else 'Mostrador / Para Llevar',

            'es_mesa': bool(ped.venta.mesa),

            'cajero': ped.venta.cajero.get_full_name() or ped.venta.cajero.username,

            'hora_creacion': tiempo_creacion.strftime('%H:%M'),

            'minutos_transcurridos': minutos,

            'es_demorado': minutos >= 15,

            'observaciones': ped.observaciones or '',

            'items': items_barra,

            'total_items': sum(it['cantidad'] for it in items_barra),

        })



    ultimos_entregados = Pedido.objects.filter(

        venta__punto_venta=local_actual,

        creado_en__date=hoy,

        estado_barra='ENTREGADO',

        detalles__producto__categoria__destino_defecto='BARRA'

    ).distinct().select_related('venta__mesa').order_by('-actualizado_en')[:5]



    catalogo_stock = _obtener_catalogo_stock_estacion(local_actual, 'BARRA')

    context = {

        'local_actual': local_actual,

        'locales': locales,

        'pedidos': pedidos_data,

        'total_pendientes': total_pendientes,

        'total_en_preparacion': total_en_preparacion,

        'total_listos': total_listos,

        'total_cola': len(pedidos_data),

        'ultimos_entregados': ultimos_entregados,

        'catalogo_stock': catalogo_stock,

        'hoy_str': hoy.strftime("%d/%m/%Y"),

        'ahora_hora_str': ahora_dt.strftime("%H:%M"),

        'en_horario': en_horario,

        'puede_ir_cocina': obtener_rol_usuario(request.user) in ('COCINERO', 'ADMINISTRADOR'),

    }

    return render(request, 'ventas/kds/barra.html', context)



@requiere_rol(['COCINERO', 'BARRA', 'ADMINISTRADOR', 'MESERO', 'CAJERO'])

def cambiar_estado_pedido(request):

    """

    Endpoint para cambiar el estado de preparación de un pedido en cocina/barra:

    PENDIENTE -> EN_PREPARACION -> LISTO -> ENTREGADO

    Garantiza concurrencia con select_for_update y validación estricta de máquina de estados (RF13).

    """

    if request.method == 'POST':

        pedido_raw = request.POST.get('pedido_id', '')

        try:

            pedido_id = int(pedido_raw)

        except (ValueError, TypeError):

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                return JsonResponse({'ok': False, 'status': 'error', 'mensaje': 'Identificador de pedido inválido'}, status=400)

            messages.error(request, "Identificador de pedido inválido.")

            return redirect('cocina')



        nuevo_estado = request.POST.get('nuevo_estado', '').upper()



        estados_validos = ['PENDIENTE', 'EN_PREPARACION', 'LISTO', 'ENTREGADO', 'CANCELADO']

        if nuevo_estado not in estados_validos:

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                return JsonResponse({'ok': False, 'status': 'error', 'mensaje': 'Estado inválido'}, status=400)

            messages.error(request, "Estado de pedido inválido.")

            return redirect('cocina')



        rol_usuario = obtener_rol_usuario(request.user)

        if nuevo_estado == 'CANCELADO':

            if rol_usuario in ['CAJERO', 'MESERO']:

                err_perm = "Acción denegada por seguridad: Un cajero o mesero no puede cancelar pedidos en curso directamente. La cancelación de ventas o comandas debe gestionarse a través del módulo de anulación con autorización formal de supervisión (Control Anti-Fraude)."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                    return JsonResponse({'ok': False, 'status': 'error', 'mensaje': err_perm}, status=403)

                messages.error(request, err_perm)

                return redirect('cocina')



        ticket_id = request.POST.get('ticket_id')

        ticket_obj = None

        if ticket_id:

            try:

                ticket_obj = Ticket.objects.filter(id=int(ticket_id)).first()

            except (ValueError, TypeError):

                ticket_obj = None



        observaciones_entrega = request.POST.get('observaciones_entrega') or request.POST.get('observaciones')



        estacion = (request.POST.get('estacion') or '').strip().upper()

        if estacion not in ('COCINA', 'BARRA'):

            referer_hdr = (request.META.get('HTTP_REFERER') or '').lower()

            if '/barra/' in referer_hdr:

                estacion = 'BARRA'

            elif '/cocina/' in referer_hdr:

                estacion = 'COCINA'

            elif ticket_obj and ticket_obj.tipo_destino in ('COCINA', 'BARRA'):

                estacion = ticket_obj.tipo_destino



        usa_estacion = False

        try:

            with transaction.atomic():

                pedido = Pedido.objects.select_for_update().filter(id=pedido_id).first()

                if not pedido:

                    raise ValidationError(f"El pedido #{pedido_id} no existe.")

                if not validar_acceso_rls_local(request, pedido.venta.punto_venta):
                    err_rls = "Acceso denegado (RLS): El pedido no corresponde a tu local asignado."
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
                        return JsonResponse({'ok': False, 'status': 'error', 'mensaje': err_rls}, status=403)
                    return error_403_view(request)



                estaciones_activas = pedido.get_estaciones_activas()

                usa_estacion = estacion in ('COCINA', 'BARRA') and estacion in estaciones_activas

                ahora = timezone.now()



                if usa_estacion:

                    campo_est = 'estado_cocina' if estacion == 'COCINA' else 'estado_barra'

                    estado_actual_est = getattr(pedido, campo_est)

                    validar_transicion_estado_pedido(pedido, nuevo_estado, estado_actual_override=estado_actual_est)

                    setattr(pedido, campo_est, nuevo_estado)



                    if nuevo_estado == 'EN_PREPARACION':

                        if not pedido.fecha_inicio_preparacion:

                            pedido.fecha_inicio_preparacion = ahora

                        if ticket_obj:

                            ticket_obj.estado = 'EN_PROCESO'

                            ticket_obj.save(update_fields=['estado'])

                        else:

                            pedido.tickets.filter(tipo_destino=estacion, estado='EMITIDO').update(estado='EN_PROCESO')

                    elif nuevo_estado == 'LISTO':

                        if not pedido.fecha_listo:

                            pedido.fecha_listo = ahora

                    elif nuevo_estado == 'ENTREGADO':

                        if ticket_obj:

                            ticket_obj.estado = 'ENTREGADO'

                            ticket_obj.save(update_fields=['estado'])

                        else:

                            pedido.tickets.filter(tipo_destino=estacion).exclude(estado='ENTREGADO').update(estado='ENTREGADO')



                    estados_est = [pedido.estado_cocina if e == 'COCINA' else pedido.estado_barra for e in estaciones_activas]

                    if all(es == 'CANCELADO' for es in estados_est):

                        pedido.estado = 'CANCELADO'

                        pedido.save()

                    elif all(es == 'ENTREGADO' for es in estados_est):

                        if pedido.estado != 'LISTO':

                            pedido.estado = 'LISTO'

                            if not pedido.fecha_listo:

                                pedido.fecha_listo = ahora

                            pedido.save(update_fields=['estado', 'fecha_listo', 'estado_cocina', 'estado_barra', 'actualizado_en'])

                        registrar_entrega_pedido(

                            pedido_or_id=pedido,

                            usuario_entrega=request.user if request.user.is_authenticated else None,

                            ticket=ticket_obj,

                            observaciones=observaciones_entrega

                        )

                    else:

                        activos_no_cancel = [es for es in estados_est if es != 'CANCELADO'] or estados_est

                        if all(es in ('LISTO', 'ENTREGADO') for es in activos_no_cancel):

                            nuevo_global = 'LISTO'

                            if not pedido.fecha_inicio_preparacion:

                                pedido.fecha_inicio_preparacion = ahora

                            if not pedido.fecha_listo:

                                pedido.fecha_listo = ahora

                        elif any(es in ('EN_PREPARACION', 'LISTO', 'ENTREGADO') for es in activos_no_cancel):

                            nuevo_global = 'EN_PREPARACION'

                            if not pedido.fecha_inicio_preparacion:

                                pedido.fecha_inicio_preparacion = ahora

                        else:

                            nuevo_global = 'PENDIENTE'

                        pedido.estado = nuevo_global

                        pedido.save()

                else:

                    if nuevo_estado == 'ENTREGADO':

                        registrar_entrega_pedido(

                            pedido_or_id=pedido,

                            usuario_entrega=request.user if request.user.is_authenticated else None,

                            ticket=ticket_obj,

                            observaciones=observaciones_entrega

                        )

                    else:

                        validar_transicion_estado_pedido(pedido, nuevo_estado)

                        if nuevo_estado != pedido.estado:

                            pedido.estado = nuevo_estado

                            pedido.estado_cocina = nuevo_estado

                            pedido.estado_barra = nuevo_estado

                            if nuevo_estado == 'EN_PREPARACION':

                                if not pedido.fecha_inicio_preparacion:

                                    pedido.fecha_inicio_preparacion = ahora

                                if ticket_obj:

                                    ticket_obj.estado = 'EN_PROCESO'

                                    ticket_obj.save(update_fields=['estado'])

                                else:

                                    pedido.tickets.filter(estado='EMITIDO').update(estado='EN_PROCESO')

                            elif nuevo_estado == 'LISTO':

                                if not pedido.fecha_listo:

                                    pedido.fecha_listo = ahora

                            pedido.save()



        except ValidationError as ve:

            msg_err = ve.message if hasattr(ve, 'message') else str(ve)

            if isinstance(msg_err, list):

                msg_err = "; ".join(msg_err)

            elif isinstance(msg_err, dict):

                msg_err = str(msg_err)

            if msg_err.startswith("['") and msg_err.endswith("']"):

                msg_err = msg_err[2:-2]



            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

                return JsonResponse({'ok': False, 'status': 'error', 'mensaje': msg_err}, status=400)

            messages.error(request, msg_err)

            referer = request.META.get('HTTP_REFERER')

            if referer and any(r in referer for r in ['/cocina/', '/mesero/', '/barra/', '/vendedor/']):

                return redirect(referer)

            return redirect('cocina')



        if usa_estacion:

            disp_est = pedido.get_estado_cocina_display() if estacion == 'COCINA' else pedido.get_estado_barra_display()

            label_est = 'Cocina' if estacion == 'COCINA' else 'Barra'

            mensaje_exito = f"Pedido #{pedido.id:04d} ({label_est}) actualizado a '{disp_est}' exitosamente."

        else:

            disp_est = pedido.get_estado_display()

            mensaje_exito = f"Pedido #{pedido.id:04d} actualizado a '{disp_est}' exitosamente."



        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

            return JsonResponse({

                'ok': True,

                'status': 'ok',

                'pedido_id': pedido.id,

                'estacion': estacion if usa_estacion else 'TODAS',

                'nuevo_estado': nuevo_estado,

                'estado_cocina': pedido.estado_cocina,

                'estado_barra': pedido.estado_barra,

                'estado_display': disp_est,

                'mensaje': mensaje_exito

            })



        messages.success(request, mensaje_exito)

        referer = request.META.get('HTTP_REFERER')

        if referer and any(r in referer for r in ['/cocina/', '/mesero/', '/barra/', '/vendedor/']):

            return redirect(referer)

        return redirect('cocina')



    return redirect('cocina')











@requiere_rol(['CAJERO', 'ADMINISTRADOR'])

def anular_venta(request, venta_id):

    """

    Control Anti-Fraude en Ventas:

    Permite anular una venta previa garantizando trazabilidad y autorización de supervisión.

    - Si el usuario es ADMINISTRADOR: puede anular indicando motivo.

    - Si el usuario es CAJERO: debe suministrar credenciales válidas (username y password) de un ADMINISTRADOR / Supervisor.

    - Requiere motivo explicativo obligatorio (mínimo 5 caracteres).

    - Aplica transaction.atomic() y select_for_update() para evitar condiciones de carrera.

    - Restaura el estado de la mesa si estaba en consumo y registra auditoría en el historial.

    """

    if request.method == 'POST':

        permitido_ip, retry_after, _ = verificar_rate_limit_ip(
            request,
            namespace='anular_venta_ip',
            max_requests=25,
            window_seconds=60,
        )
        if not permitido_ip:
            resp_429 = HttpResponse("Demasiadas solicitudes de anulación desde tu IP. Espera unos segundos.", status=429)
            resp_429['Retry-After'] = str(retry_after)
            return resp_429

        motivo = limpiar_texto_seguro(request.POST.get('motivo_anulacion', ''), max_length=250)

        if not motivo or len(motivo) < 5:

            messages.error(request, "Debe especificar un motivo detallado para la anulación (mínimo 5 caracteres).")

            return redirect(obtener_url_redireccion_segura(request, 'vendedor'))



        rol_actual = obtener_rol_usuario(request.user)

        autorizado_por = None



        if rol_actual == 'ADMINISTRADOR':

            autorizado_por = request.user

        else:

            sup_user = request.POST.get('supervisor_username', '').strip()

            sup_pass = request.POST.get('supervisor_password', '')

            sup_intentos_key = f"anular_sup_intentos_{request.user.id}"

            sup_bloqueo_key = f"anular_sup_bloqueo_{request.user.id}"



            if cache.get(sup_bloqueo_key):

                messages.error(request, "Acceso bloqueado: Demasiados intentos fallidos de supervisor. Espere 10 minutos.")

                return redirect(obtener_url_redireccion_segura(request, 'vendedor'))



            if not sup_user or not sup_pass:

                messages.error(request, "Acción denegada: Se requiere usuario y contraseña de Supervisor/Administrador para autorizar la anulación.")

                return redirect(obtener_url_redireccion_segura(request, 'vendedor'))



            supervisor = authenticate(request, username=sup_user, password=sup_pass)

            if not supervisor or obtener_rol_usuario(supervisor) != 'ADMINISTRADOR':

                intentos = cache.get(sup_intentos_key, 0) + 1

                cache.set(sup_intentos_key, intentos, timeout=600)

                if intentos >= 5:

                    cache.set(sup_bloqueo_key, True, timeout=600)

                    messages.error(request, "Acceso bloqueado: Se superó el límite de 5 intentos de supervisor para autorizar anulaciones.")

                else:

                    messages.error(request, f"Acción denegada: Credenciales de Supervisor inválidas ({5 - intentos} intentos restantes).")

                return redirect(obtener_url_redireccion_segura(request, 'vendedor'))



            cache.delete(sup_intentos_key)

            cache.delete(sup_bloqueo_key)

            autorizado_por = supervisor



        with transaction.atomic():

            venta = Venta.objects.select_for_update().filter(id=venta_id).first()

            if not venta:

                messages.error(request, f"La venta #{venta_id} no fue encontrada en el sistema.")

                return redirect(obtener_url_redireccion_segura(request, 'vendedor'))

            if not validar_acceso_rls_local(request, venta.punto_venta):

                return error_403_view(request)



            if venta.estado == 'ANULADA':

                messages.warning(request, f"La venta #{venta.id} ya se encontraba anulada.")

                return redirect(obtener_url_redireccion_segura(request, 'vendedor'))



            # Blindaje Anti-Fraude: Cajas y Jornadas cerradas son inmutables

            if venta.caja and venta.caja.estado == 'CERRADA':

                messages.error(

                    request,

                    f"Acción denegada por seguridad contable: La venta #{venta.id} pertenece a la caja '{venta.caja.nombre}', "

                    "la cual ya fue cerrada y arqueada formalmente. Los registros de cajas cerradas son legalmente inmutables."

                )

                return redirect(obtener_url_redireccion_segura(request, 'vendedor'))



            if venta.caja and venta.caja.jornada and venta.caja.jornada.estado == 'CERRADA':

                messages.error(

                    request,

                    f"Acción denegada por seguridad contable: La venta #{venta.id} corresponde a la Jornada #{venta.caja.jornada.id}, "

                    "la cual ya fue finalizada y auditada por la supervisión."

                )

                return redirect(obtener_url_redireccion_segura(request, 'vendedor'))



            tiene_entregados = venta.pedidos.filter(estado='ENTREGADO').exists() or Entrega.objects.filter(pedido__venta=venta).exists()

            alerta_merma_tag = " [ALERTA DE MERMA/FRAUDE: ALIMENTOS YA ENTREGADOS AL CLIENTE]" if tiene_entregados else ""



            monto_previo = venta.total

            venta.estado = 'ANULADA'

            venta.save()



            # Cancelar comandas activas asociadas para retirarlas inmediatamente de Cocina/Barra

            pedidos_asociados = venta.pedidos.filter(estado__in=['PENDIENTE', 'EN_PREPARACION', 'LISTO'])

            for ped_an in pedidos_asociados:

                ped_an.estado = 'CANCELADO'

                ped_an.observaciones = ((ped_an.observaciones or '') + f' [Venta anulada: {motivo}]').strip()

                ped_an.save(update_fields=['estado', 'observaciones', 'actualizado_en'])

                ped_an.tickets.exclude(estado='FINALIZADO').update(estado='FINALIZADO')



            # Si estaba ligada a una mesa, liberar mesa si no quedan otras ventas abiertas

            if venta.mesa:

                otras_activas = Venta.objects.filter(mesa=venta.mesa, estado='ABIERTA').exclude(id=venta.id).exists()

                if not otras_activas:

                    mesa = Mesa.objects.select_for_update().get(id=venta.mesa.id)

                    mesa.estado = 'HABILITADA'

                    mesa.fecha_ocupacion = None

                    mesa.save(update_fields=['estado', 'fecha_ocupacion'])



            # Trazabilidad en AlertaTraslado / Bitácora

            audit_msg = (

                f"[ANULACIÓN #{venta.id}]{alerta_merma_tag} ${int(monto_previo):,} CLP. "

                f"Solicitado por {request.user.username}. "

                f"Autorizado por {autorizado_por.username}. Motivo: {motivo}"

            )

            AlertaTraslado.objects.create(

                empleado=request.user,

                punto_venta_origen=venta.punto_venta,

                punto_venta_destino=venta.punto_venta,

                autorizado_por=autorizado_por,

                fecha_hora=timezone.now(),

                motivo=audit_msg[:255]

            )



            messages.success(

                request,

                f"¡Venta #{venta.id} anulada exitosamente! Autorizado por supervisor '{autorizado_por.get_full_name() or autorizado_por.username}'. Registro guardado en auditoría."

            )

            return redirect(obtener_url_redireccion_segura(request, 'vendedor'))



    return redirect('vendedor')





@requiere_rol(['ADMINISTRADOR'])

def administrador_backup(request):

    """

    Generación manual/inmediata de Copia de Seguridad de la Base de Datos (Disaster Recovery).

    Crea un snapshot íntegro, comprimido y con verificación SHA-256 en la carpeta /backups/.

    """

    if request.method == 'POST':

        from django.core.management import call_command

        from io import StringIO

        out = StringIO()

        try:

            call_command('backup_safari', stdout=out)

            messages.success(request, "Copia de seguridad física generada con éxito en caliente, comprimida en GZIP y verificada con SHA-256.")

        except Exception:

            logger.exception("Error interno generando respaldo de base de datos")

            messages.error(request, "No fue posible generar la copia de seguridad. Revisa los registros del servidor.")

        return redirect('administrador')

    return redirect('administrador')





@requiere_rol(['ADMINISTRADOR'])

def exportar_reporte_ventas(request):

    """

    Exportacion de Reporte de Ventas en multiples formatos:

    - Excel (.xlsx) con openpyxl

    - Word (.docx) con python-docx

    - PDF / Vista imprimible oficial

    Soporta temporalidad: Dia especifico (de los 15 meses), Semana, Mes o Comparativa 15 meses.

    """

    from ventas.exportador_reportes import obtener_datos_reporte, generar_excel_ventas, generar_word_ventas



    tipo_rango = request.GET.get('tipo_rango', '15_meses').strip()

    fecha_str = request.GET.get('fecha', '').strip()

    mes_str = request.GET.get('mes', '').strip()

    local_id = request.GET.get('local_id', 'todos').strip()

    formato = request.GET.get('formato', 'excel').strip().lower()



    datos = obtener_datos_reporte(tipo_rango=tipo_rango, fecha_str=fecha_str, mes_str=mes_str, local_id=local_id)

    timestamp = timezone.localtime().strftime('%Y%m%d_%H%M')



    if formato in ['excel', 'xlsx']:

        archivo_io = generar_excel_ventas(datos)

        nombre_archivo = f"Reporte_Ventas_Parque_Safari_{tipo_rango}_{timestamp}.xlsx"

        response = HttpResponse(

            archivo_io.getvalue(),

            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        )

        response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'

        return response



    elif formato in ['word', 'docx']:

        archivo_io = generar_word_ventas(datos)

        nombre_archivo = f"Reporte_Ventas_Parque_Safari_{tipo_rango}_{timestamp}.docx"

        response = HttpResponse(

            archivo_io.getvalue(),

            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'

        )

        response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'

        return response



    elif formato in ['pdf', 'imprimir']:

        return render(request, 'ventas/impresion/reporte_ventas_impresion.html', {'datos': datos})



    else:

        archivo_io = generar_excel_ventas(datos)

        nombre_archivo = f"Reporte_Ventas_Parque_Safari_{tipo_rango}_{timestamp}.xlsx"

        response = HttpResponse(

            archivo_io.getvalue(),

            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        )

        response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'

        return response



# ==============================================================================

# CAMBIO OBLIGATORIO DE CONTRASEÑA CADA 6 MESES (ISO/IEC 27400 - Tarea 1)

# ==============================================================================

def cambiar_clave_expirada(request):

    """Permite renovar una contraseña expirada o forzar rotación semestral de clave"""

    if not request.user.is_authenticated:

        messages.error(request, "Debes iniciar sesión para actualizar tu contraseña.")

        return redirect('index')



    perfil = getattr(request.user, 'perfil', None)



    if request.method == 'POST':

        permitido_ip, retry_after, _ = verificar_rate_limit_ip(
            request,
            namespace='cambiar_clave_ip',
            max_requests=20,
            window_seconds=300,
        )
        if not permitido_ip:
            resp_429 = HttpResponse("Demasiados intentos de cambio de clave desde tu IP. Espera unos minutos.", status=429)
            resp_429['Retry-After'] = str(retry_after)
            return resp_429

        clave_actual = request.POST.get('clave_actual', '')

        nueva_clave = request.POST.get('nueva_clave', '')

        confirmar_clave = request.POST.get('confirmar_clave', '')



        if not request.user.check_password(clave_actual):

            messages.error(request, "La contraseña actual ingresada es incorrecta.")

            return render(request, 'ventas/acceso/cambiar_clave_expirada.html')



        if nueva_clave != confirmar_clave:

            messages.error(request, "La nueva contraseña y la confirmación no coinciden.")

            return render(request, 'ventas/acceso/cambiar_clave_expirada.html')



        if clave_actual == nueva_clave:

            messages.error(request, "La nueva contraseña no puede ser idéntica a la actual.")

            return render(request, 'ventas/acceso/cambiar_clave_expirada.html')



        es_valida, mensaje_err = validar_complejidad_clave(nueva_clave)

        if not es_valida:

            messages.error(request, mensaje_err)

            return render(request, 'ventas/acceso/cambiar_clave_expirada.html')



        # Cifrar/hashear inmediatamente con PBKDF2/SHA-256 (Norma ISO/IEC 27400)

        request.user.set_password(nueva_clave)

        request.user.save()



        if perfil:

            perfil.debe_cambiar_clave = False

            perfil.fecha_cambio_clave = timezone.now()

            perfil.limpiar_intentos_fallidos()

            perfil.save(update_fields=['debe_cambiar_clave', 'fecha_cambio_clave', 'intentos_fallidos', 'bloqueado_hasta'])



        update_session_auth_hash(request, request.user)

        request.session.pop('requiere_cambio_clave', None)



        messages.success(request, "¡Contraseña actualizada exitosamente! Tu cuenta cumple con la política de seguridad semestral.")

        rol = obtener_rol_usuario(request.user)

        return redirect(RUTA_INICIO_POR_ROL.get(rol, 'index'))



    return render(request, 'ventas/acceso/cambiar_clave_expirada.html')





# ==============================================================================

# API VERIFICACIÓN QR Y CONVENIOS CABAÑAS (RF13 - Tarea 7)

# ==============================================================================

@requiere_rol(['CAJERO', 'ADMINISTRADOR', 'MESERO'])

def api_verificar_convenio_qr(request):

    """Verifica código QR o de barras con firma HMAC-SHA256 anti-fraude para cabañas y convenios"""

    permitido_ip, retry_after, _ = verificar_rate_limit_ip(
        request,
        namespace='api_verificar_convenio_qr',
        max_requests=40,
        window_seconds=60,
    )
    if not permitido_ip:
        resp_429 = JsonResponse({'ok': False, 'mensaje': 'Límite de verificaciones por IP alcanzado. Espera unos segundos.'}, status=429)
        resp_429['Retry-After'] = str(retry_after)
        return resp_429

    from ventas.utils import generar_firma_qr_convenio, verificar_firma_qr_convenio

    raw_codigo = limpiar_texto_seguro(request.GET.get('codigo', ''), max_length=120)
    firma_param = limpiar_texto_seguro(request.GET.get('firma', ''), max_length=64)

    if not raw_codigo:

        return JsonResponse({'ok': False, 'mensaje': 'Por favor ingresa o escanea un código QR o de barra.'}, status=400)

    # Detección de token criptográfico HMAC integrado (formato: CODIGO:FIRMA)
    if ':' in raw_codigo:
        partes_qr = raw_codigo.split(':', 1)
        codigo = partes_qr[0].strip()
        firma_qr = partes_qr[1].strip()
    else:
        codigo = raw_codigo
        firma_qr = firma_param

    # Si se suministró firma, verificar autenticidad matemática estricta
    if firma_qr:
        if not verificar_firma_qr_convenio(codigo, firma_qr):
            return JsonResponse({
                'ok': False,
                'encontrado': False,
                'tampered': True,
                'error_criptografico': True,
                'mensaje': 'ALERTA ANTI-FRAUDE: La firma criptográfica HMAC-SHA256 del código QR es inválida o ha sido adulterada.'
            }, status=403)



    # 1. Búsqueda prioritaria en Convenios Comerciales y Precios Especiales (RF07.5)

    conv_especial = PrecioEspecial.objects.filter(

        Q(codigo_convenio__iexact=codigo) | Q(nombre_condicion__iexact=codigo),

        activo=True

    ).select_related('producto').first()



    if conv_especial:

        hoy = timezone.localdate()

        vigente = conv_especial.es_vigente(hoy)

        return JsonResponse({

            'ok': True,

            'encontrado': True,

            'valido_hoy': vigente,

            'puede_consumir': vigente,

            'tipo': 'CONVENIO_INSTITUCIONAL',

            'codigo': conv_especial.codigo_convenio or str(conv_especial.id),

            'convenio_id': conv_especial.id,

            'nombre_condicion': conv_especial.nombre_condicion,

            'producto_id': conv_especial.producto.id,

            'producto_nombre': conv_especial.producto.nombre,

            'precio_base': float(conv_especial.producto.precio_base),

            'precio_convenio': float(conv_especial.precio),

            'ahorro_unitario': float(max(Decimal('0'), conv_especial.producto.precio_base - conv_especial.precio)),

            'mensaje': f"Convenio comercial '{conv_especial.nombre_condicion}' verificado para {conv_especial.producto.nombre}: ${conv_especial.precio:,.0f} CLP." if vigente else f"Convenio '{conv_especial.nombre_condicion}' fuera de vigencia."

        })



    convenio = ConvenioHuesped.objects.filter(codigo_qr__iexact=codigo).first()

    if not convenio:

        return JsonResponse({

            'ok': False,

            'encontrado': False,

            'mensaje': f'El código "{codigo}" no corresponde a ningún huésped o convenio registrado.'

        }, status=404)



    # Para convenios de huéspedes (ConvenioHuesped), la firma HMAC-SHA256 es estrictamente obligatoria
    if not firma_qr or not verificar_firma_qr_convenio(convenio.codigo_qr, firma_qr):
        return JsonResponse({
            'ok': False,
            'encontrado': False,
            'tampered': True,
            'error_criptografico': True,
            'mensaje': 'Código QR rechazado: se requiere firma criptográfica HMAC-SHA256 válida.'
        }, status=403)



    valido_hoy = convenio.es_valido_hoy()

    consumos_hoy = convenio.consumos_hoy_count()

    puede_consumir = convenio.puede_consumir_hoy()



    mensaje = "Pase válido y activo."

    if not convenio.activo:

        mensaje = "El convenio se encuentra desactivado administrativamente."

    elif not valido_hoy:

        mensaje = f"El pase no está vigente hoy (Estadía: {convenio.fecha_checkin.strftime('%d/%m/%Y')} al {convenio.fecha_checkout.strftime('%d/%m/%Y')})."

    elif not puede_consumir:

        mensaje = f"Límite diario alcanzado: ya se han utilizado {consumos_hoy} de {convenio.limite_diario} consumos permitidos hoy."



    partes_titular = [p for p in (convenio.nombre_titular or '').split() if p]

    titular_enmascarado = ' '.join((p[:2] + '***') if len(p) > 2 else (p[0] + '***') for p in partes_titular) or 'Huésped'



    return JsonResponse({

        'ok': True,

        'encontrado': True,

        'valido_hoy': valido_hoy,

        'puede_consumir': puede_consumir,

        'codigo': convenio.codigo_qr,

        'cabana': convenio.numero_cabana,

        'titular': titular_enmascarado,

        'tipo_beneficio': convenio.tipo_beneficio,

        'tipo_display': convenio.get_tipo_beneficio_display(),

        'valor_descuento': float(convenio.valor_descuento),

        'limite_diario': convenio.limite_diario,

        'consumos_hoy': consumos_hoy,

        'mensaje': mensaje

    })





@requiere_rol(['CAJERO', 'ADMINISTRADOR', 'MESERO'])

def api_aplicar_consumo_convenio(request):

    """Registra el consumo del beneficio (desayuno o descuento) asociado a un huésped de cabaña de forma atómica"""

    if request.method != 'POST':

        return JsonResponse({'ok': False, 'mensaje': 'Método no permitido'}, status=405)

    permitido_ip, retry_after, _ = verificar_rate_limit_ip(
        request,
        namespace='api_aplicar_consumo_convenio',
        max_requests=30,
        window_seconds=60,
    )
    if not permitido_ip:
        resp_429 = JsonResponse({'ok': False, 'mensaje': 'Límite de solicitudes por IP alcanzado.'}, status=429)
        resp_429['Retry-After'] = str(retry_after)
        return resp_429

    from decimal import InvalidOperation
    from ventas.utils import verificar_firma_qr_convenio

    raw_codigo = limpiar_texto_seguro(request.POST.get('codigo', ''), max_length=120)
    firma_param = limpiar_texto_seguro(request.POST.get('firma', ''), max_length=64)

    if ':' in raw_codigo:
        partes_qr = raw_codigo.split(':', 1)
        codigo = partes_qr[0].strip()
        firma_qr = partes_qr[1].strip()
    else:
        codigo = raw_codigo
        firma_qr = firma_param

    if not codigo:
        return JsonResponse({'ok': False, 'mensaje': 'Código de convenio requerido.'}, status=400)

    if not firma_qr or not verificar_firma_qr_convenio(codigo, firma_qr):
        return JsonResponse({
            'ok': False,
            'tampered': True,
            'error_criptografico': True,
            'mensaje': 'Firma criptográfica HMAC-SHA256 faltante o inválida.'
        }, status=403)

    ticket_id = request.POST.get('ticket_id')

    try:

        dec_orig = max(Decimal('0'), Decimal(str(request.POST.get('monto_original', '0'))))

    except (InvalidOperation, TypeError, ValueError):

        return JsonResponse({'ok': False, 'mensaje': 'Valores numéricos de montos inválidos.'}, status=400)

    with transaction.atomic():

        convenio = ConvenioHuesped.objects.select_for_update().filter(codigo_qr__iexact=codigo).first()

        if not convenio:

            return JsonResponse({'ok': False, 'mensaje': 'Convenio no encontrado.'}, status=404)

        if not convenio.puede_consumir_hoy():

            return JsonResponse({'ok': False, 'mensaje': 'El huésped ya alcanzó su límite de consumos de hoy o pase fuera de vigencia.'}, status=400)

        ticket = Ticket.objects.select_for_update().select_related('venta', 'punto_venta', 'pedido__venta').filter(id=ticket_id).first() if ticket_id else None

        if ticket_id and not ticket:

            return JsonResponse({'ok': False, 'mensaje': 'Ticket asociado no encontrado.'}, status=404)

        perfil_op = getattr(request.user, 'perfil', None)

        pv_validar = ticket.get_punto_venta() if ticket else (perfil_op.punto_venta_actual if perfil_op else None)

        if not pv_validar and obtener_rol_usuario(request.user) != 'ADMINISTRADOR':

            return JsonResponse({'ok': False, 'mensaje': 'Acceso denegado (RLS): no tienes un local operativo asignado.'}, status=403)

        if pv_validar and not validar_acceso_rls_local(request, pv_validar):

            return JsonResponse({'ok': False, 'mensaje': 'Acceso denegado (RLS): el recurso pertenece a otro local.'}, status=403)

        if ticket and ConsumoHuesped.objects.filter(ticket=ticket).exists():

            return JsonResponse({'ok': False, 'mensaje': 'Este ticket ya registró un consumo de convenio.'}, status=400)

        if ticket:

            venta_ref = ticket.venta or (ticket.pedido.venta if ticket.pedido else None)

            if venta_ref:

                subtotal_det = sum(d.subtotal for d in venta_ref.detalles.all())

                if subtotal_det > Decimal('0'):

                    dec_orig = subtotal_det

                elif venta_ref.total and venta_ref.total > Decimal('0'):

                    dec_orig = venta_ref.total

        if convenio.tipo_beneficio == 'DESAYUNO_INCLUIDO':

            dec_bon = dec_orig

        elif convenio.tipo_beneficio == 'DESCUENTO_PORCENTAJE':

            pct_desc = max(Decimal('0'), min(Decimal('100'), Decimal(str(convenio.valor_descuento or 0))))

            dec_bon = Decimal(str(int(round(dec_orig * pct_desc / Decimal('100')))))

        elif convenio.tipo_beneficio == 'DESCUENTO_MONTO':

            dec_bon = min(dec_orig, max(Decimal('0'), Decimal(str(convenio.valor_descuento or 0))))

        else:

            dec_bon = Decimal('0')

        dec_pag = max(Decimal('0'), dec_orig - dec_bon)

        ConsumoHuesped.objects.create(

            convenio=convenio,

            ticket=ticket,

            monto_original=dec_orig,

            monto_bonificado=dec_bon,

            monto_pagado=dec_pag,

            registrado_por=request.user,

            observaciones=f"Descuento aplicado en local: {convenio.get_tipo_beneficio_display()}"

        )

        consumos_actuales = convenio.consumos_hoy_count()

    partes_titular = [p for p in (convenio.nombre_titular or '').split() if p]

    titular_enmascarado = ' '.join((p[:2] + '***') if len(p) > 2 else (p[0] + '***') for p in partes_titular) or 'Huésped'

    return JsonResponse({

        'ok': True,

        'monto_original': float(dec_orig),

        'monto_bonificado': float(dec_bon),

        'monto_pagado': float(dec_pag),

        'mensaje': f"Beneficio aplicado exitosamente para {convenio.numero_cabana} ({titular_enmascarado}).",

        'consumos_hoy': consumos_actuales

    })





# ==============================================================================

# GESTIÓN ADMINISTRATIVA DE CONVENIOS CABAÑAS (Tarea 7)

# ==============================================================================

@requiere_rol(['ADMINISTRADOR'])

def administrador_convenios(request):

    """Panel de administración para dar de alta pases de cabañas y auditar desayunos consumidos"""

    rol = obtener_rol_usuario(request.user)

    if rol != 'ADMINISTRADOR':

        messages.error(request, "Acceso restringido al personal de Administración.")

        return redirect('index')



    if request.method == 'POST':

        accion = request.POST.get('accion')

        if accion == 'crear':

            numero_cabana = request.POST.get('numero_cabana', '').strip()

            nombre_titular = request.POST.get('nombre_titular', '').strip()

            rut_titular = request.POST.get('rut_titular', '').strip()

            tipo_beneficio = request.POST.get('tipo_beneficio', 'DESAYUNO_INCLUIDO')

            valor_descuento = request.POST.get('valor_descuento', '100')

            limite_diario = int(request.POST.get('limite_diario', 1))

            fecha_checkin = request.POST.get('fecha_checkin')

            fecha_checkout = request.POST.get('fecha_checkout')

            codigo_qr = request.POST.get('codigo_qr', '').strip()



            if not codigo_qr:

                import secrets

                codigo_qr = f"CAB-{numero_cabana.replace(' ', '')}-{secrets.token_hex(4).upper()}"



            ConvenioHuesped.objects.create(

                codigo_qr=codigo_qr,

                numero_cabana=numero_cabana,

                nombre_titular=nombre_titular,

                rut_titular=rut_titular,

                tipo_beneficio=tipo_beneficio,

                valor_descuento=Decimal(str(valor_descuento)),

                limite_diario=limite_diario,

                fecha_checkin=fecha_checkin or timezone.now().date(),

                fecha_checkout=fecha_checkout,

                activo=True

            )

            messages.success(request, f"Pase para {numero_cabana} ({nombre_titular}) creado con éxito. Código QR: {codigo_qr}")

            return redirect('administrador_convenios')



        elif accion == 'toggle':

            convenio_id = request.POST.get('convenio_id')

            c = get_object_or_404(ConvenioHuesped, id=convenio_id)

            c.activo = not c.activo

            c.save(update_fields=['activo'])

            estado_txt = "activado" if c.activo else "desactivado"

            messages.success(request, f"Pase de {c.numero_cabana} {estado_txt} correctamente.")

            return redirect('administrador_convenios')



    convenios = ConvenioHuesped.objects.all().order_by('-creado_en')

    consumos_hoy = ConsumoHuesped.objects.filter(fecha_hora__date=timezone.now().date()).select_related('convenio', 'registrado_por').order_by('-fecha_hora')



    context = {

        'convenios': convenios,

        'consumos_hoy': consumos_hoy,

        'total_convenios': convenios.count(),

        'activos_count': convenios.filter(activo=True).count(),

        'consumos_count': consumos_hoy.count()

    }

    return render(request, 'ventas/administrador/administrador_convenios.html', context)





# ==============================================================================

# GESTIÓN DE OFERTAS DE TEMPORADA (Tarea 7)

# ==============================================================================

@requiere_rol(['ADMINISTRADOR'])

def administrador_ofertas_temporada(request):
    """
    Panel integral de Administración de Promociones, Descuentos por Tarjetas/Bancos
    y Campañas de Temporada (Parque Safari).
    Permite:
    - Crear, editar, pausar/activar y eliminar campañas de temporada y convenios con tarjetas.
    - Configurar límites comerciales: tope de descuento CLP, compra mínima, límite de usos.
    - Administrar promociones por producto (2da unidad a $1/$5/$500 o precio custom, 2x1, 3x2, % dto).
    - Asignar límites de promociones por comanda/ticket para control de costos.
    """
    rol = obtener_rol_usuario(request.user)
    if rol != 'ADMINISTRADOR':
        messages.error(request, "Acceso restringido al personal de Administración.")
        return redirect('index')

    if request.method == 'POST':
        accion = request.POST.get('accion')

        # 1. Crear Campaña de Temporada / Medio de Pago
        if accion == 'crear':
            nombre = request.POST.get('nombre', '').strip()
            descripcion = request.POST.get('descripcion', '').strip()
            tipo_campana = request.POST.get('tipo_campana', 'GENERAL')
            descuento_porcentaje = Decimal(request.POST.get('descuento_porcentaje', '0') or '0')
            medio_pago_requerido = request.POST.get('medio_pago_requerido', 'TODOS')
            banco_convenio = request.POST.get('banco_convenio', '').strip()
            monto_minimo_compra = Decimal(request.POST.get('monto_minimo_compra', '0') or '0')
            tope_descuento_clp = Decimal(request.POST.get('tope_descuento_clp', '0') or '0')
            limite_usos = int(request.POST.get('limite_usos', '0') or '0')
            fecha_inicio = request.POST.get('fecha_inicio') or timezone.now().date()
            fecha_fin = request.POST.get('fecha_fin')
            activa = request.POST.get('activa') == 'on'

            cat_id = request.POST.get('categoria_aplicable')
            categoria_obj = Categoria.objects.filter(id=cat_id).first() if cat_id else None

            if not nombre:
                messages.error(request, "Debe ingresar un nombre para la campaña.")
                return redirect('administrador_ofertas_temporada')

            if not fecha_fin:
                messages.error(request, "Debe especificar la fecha de término de la campaña.")
                return redirect('administrador_ofertas_temporada')

            prod_esp_id = request.POST.get('producto_especifico')
            producto_especifico_obj = Producto.objects.filter(id=prod_esp_id).first() if prod_esp_id else None

            OfertaTemporada.objects.create(
                nombre=nombre,
                descripcion=descripcion,
                tipo_campana=tipo_campana,
                descuento_porcentaje=descuento_porcentaje,
                medio_pago_requerido=medio_pago_requerido,
                banco_convenio=banco_convenio,
                monto_minimo_compra=monto_minimo_compra,
                tope_descuento_clp=tope_descuento_clp,
                limite_usos=limite_usos,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                activa=activa,
                categoria_aplicable=categoria_obj,
                producto_especifico=producto_especifico_obj
            )
            messages.success(request, f"Campaña '{nombre}' creada y configurada exitosamente.")
            return redirect('administrador_ofertas_temporada')

        # 2. Editar Campaña
        elif accion == 'editar_campana':
            oferta_id = request.POST.get('oferta_id')
            o = get_object_or_404(OfertaTemporada, id=oferta_id)
            o.nombre = request.POST.get('nombre', o.nombre).strip()
            o.descripcion = request.POST.get('descripcion', '').strip()
            o.tipo_campana = request.POST.get('tipo_campana', o.tipo_campana)
            o.descuento_porcentaje = Decimal(request.POST.get('descuento_porcentaje', str(o.descuento_porcentaje)) or '0')
            o.medio_pago_requerido = request.POST.get('medio_pago_requerido', o.medio_pago_requerido)
            o.banco_convenio = request.POST.get('banco_convenio', '').strip()
            o.monto_minimo_compra = Decimal(request.POST.get('monto_minimo_compra', '0') or '0')
            o.tope_descuento_clp = Decimal(request.POST.get('tope_descuento_clp', '0') or '0')
            o.limite_usos = int(request.POST.get('limite_usos', '0') or '0')
            if request.POST.get('fecha_inicio'):
                o.fecha_inicio = request.POST.get('fecha_inicio')
            if request.POST.get('fecha_fin'):
                o.fecha_fin = request.POST.get('fecha_fin')
            o.activa = request.POST.get('activa') == 'on'

            cat_id = request.POST.get('categoria_aplicable')
            o.categoria_aplicable = Categoria.objects.filter(id=cat_id).first() if cat_id else None
            prod_esp_id = request.POST.get('producto_especifico')
            o.producto_especifico = Producto.objects.filter(id=prod_esp_id).first() if prod_esp_id else None

            o.save()
            messages.success(request, f"Campaña '{o.nombre}' actualizada exitosamente.")
            return redirect('administrador_ofertas_temporada')

        # 3. Eliminar Campaña Permanentemente
        elif accion == 'eliminar_campana':
            oferta_id = request.POST.get('oferta_id')
            o = get_object_or_404(OfertaTemporada, id=oferta_id)
            nom = o.nombre
            o.delete()
            messages.success(request, f"Campaña '{nom}' eliminada permanentemente del sistema.")
            return redirect('administrador_ofertas_temporada')

        # 4. Toggle Pausar/Activar Campaña
        elif accion == 'toggle':
            oferta_id = request.POST.get('oferta_id')
            o = get_object_or_404(OfertaTemporada, id=oferta_id)
            o.activa = not o.activa
            o.save(update_fields=['activa'])
            estado = "activada" if o.activa else "pausada"
            messages.success(request, f"Campaña '{o.nombre}' {estado} correctamente.")
            return redirect('administrador_ofertas_temporada')

        # 5. Guardar / Editar Promoción de Producto (2da Unidad $X, 2x1, 3x2, % Dto)
        elif accion == 'guardar_promo_producto':
            producto_id = request.POST.get('producto_id')
            prod = get_object_or_404(Producto, id=producto_id)
            tipo_oferta = request.POST.get('tipo_oferta', 'SEGUNDA_1')
            precio_oferta_raw = request.POST.get('precio_oferta')
            descuento_pct_raw = request.POST.get('descuento_pct', '0')
            limite_ticket_raw = request.POST.get('limite_oferta_por_ticket', '0')
            descripcion_oferta = request.POST.get('descripcion_oferta', '').strip()

            prod.en_oferta = True
            prod.tipo_oferta = tipo_oferta
            prod.limite_oferta_por_ticket = max(0, int(limite_ticket_raw or '0'))

            if tipo_oferta == 'SEGUNDA_1':
                try:
                    val_segunda = Decimal(str(precio_oferta_raw or '1'))
                except Exception:
                    val_segunda = Decimal('1')
                prod.precio_oferta = val_segunda
                if not descripcion_oferta:
                    descripcion_oferta = f"Segunda unidad a ${val_segunda:,.0f} CLP"
            elif tipo_oferta == '2X1':
                prod.precio_oferta = None
                if not descripcion_oferta:
                    descripcion_oferta = "Promoción 2x1 (Lleva 2 y Paga 1)"
            elif tipo_oferta == '3X2':
                prod.precio_oferta = None
                if not descripcion_oferta:
                    descripcion_oferta = "Promoción 3x2 (Lleva 3 y Paga 2)"
            elif tipo_oferta == 'PRECIO_FIJO':
                try:
                    val_fijo = Decimal(str(precio_oferta_raw or prod.precio_base))
                except Exception:
                    val_fijo = prod.precio_base
                prod.precio_oferta = val_fijo
                if not descripcion_oferta:
                    descripcion_oferta = f"Precio Especial: ${val_fijo:,.0f} CLP"
            elif tipo_oferta == 'DESCUENTO_PCT':
                try:
                    val_pct = Decimal(str(descuento_pct_raw or '10'))
                except Exception:
                    val_pct = Decimal('10')
                prod.descuento_pct = val_pct
                if not descripcion_oferta:
                    descripcion_oferta = f"{val_pct}% Descuento Especial"
            elif tipo_oferta == 'SEGUNDA_PCT':
                try:
                    val_pct = Decimal(str(descuento_pct_raw or '50'))
                except Exception:
                    val_pct = Decimal('50')
                prod.descuento_pct = val_pct
                if not descripcion_oferta:
                    descripcion_oferta = f"Segunda unidad con {val_pct:,.0f}% de descuento"
            elif tipo_oferta == 'LLEVA_2_POR':
                try:
                    val_pack = Decimal(str(precio_oferta_raw or (prod.precio_base * Decimal('1.5'))))
                except Exception:
                    val_pack = prod.precio_base * Decimal('1.5')
                prod.precio_oferta = val_pack
                if not descripcion_oferta:
                    descripcion_oferta = f"Pack 2 por ${val_pack:,.0f} CLP"
            elif tipo_oferta == 'CANTIDAD_MINIMA':
                try:
                    val_unit = Decimal(str(precio_oferta_raw or prod.precio_base))
                except Exception:
                    val_unit = prod.precio_base
                min_cant = max(2, int(request.POST.get('cantidad_minima_oferta', '2') or '2'))
                prod.precio_oferta = val_unit
                prod.cantidad_minima_oferta = min_cant
                if not descripcion_oferta:
                    descripcion_oferta = f"Desde {min_cant} un. a ${val_unit:,.0f} c/u"

            prod.descripcion_oferta = descripcion_oferta
            prod.save()
            messages.success(request, f"¡Promoción configurada exitosamente para '{prod.nombre}'!")
            return redirect('administrador_ofertas_temporada')

        # 6. Toggle Activar/Pausar Promoción de Producto
        elif accion == 'toggle_promo_producto':
            producto_id = request.POST.get('producto_id')
            prod = get_object_or_404(Producto, id=producto_id)
            prod.en_oferta = not prod.en_oferta
            prod.save(update_fields=['en_oferta'])
            estado = "activada" if prod.en_oferta else "pausada"
            messages.success(request, f"Promoción para '{prod.nombre}' {estado}.")
            return redirect('administrador_ofertas_temporada')

        # 7. Eliminar Promoción de Producto (quitar oferta)
        elif accion == 'eliminar_promo_producto':
            producto_id = request.POST.get('producto_id')
            prod = get_object_or_404(Producto, id=producto_id)
            prod.en_oferta = False
            prod.tipo_oferta = 'NINGUNA'
            prod.precio_oferta = None
            prod.descuento_pct = Decimal('0')
            prod.limite_oferta_por_ticket = 0
            prod.descripcion_oferta = None
            prod.save()
            messages.info(request, f"Promoción eliminada para '{prod.nombre}'. El producto vuelve a su tarifa estándar.")
            return redirect('administrador_ofertas_temporada')

        # 8. Compatibilidad histórica: activar/desactivar promo moneda 1
        elif accion == 'activar_promo_moneda_1':
            producto_id = request.POST.get('producto_id')
            prod = get_object_or_404(Producto, id=producto_id)
            prod.en_oferta = True
            prod.tipo_oferta = 'SEGUNDA_1'
            prod.precio_oferta = Decimal('1')
            prod.descripcion_oferta = 'Segunda unidad a $1 peso con moneda física (Ley 20.956)'
            prod.save()
            messages.success(request, f"¡Promoción oficial activada para '{prod.nombre}': 2da unidad a $1 peso con moneda física!")
            return redirect('administrador_ofertas_temporada')

        elif accion == 'desactivar_promo_moneda_1':
            producto_id = request.POST.get('producto_id')
            prod = get_object_or_404(Producto, id=producto_id)
            prod.en_oferta = False
            prod.tipo_oferta = 'NINGUNA'
            prod.precio_oferta = None
            prod.descripcion_oferta = None
            prod.save()
            messages.info(request, f"Promoción de moneda física desactivada para '{prod.nombre}'.")
            return redirect('administrador_ofertas_temporada')

    ofertas = OfertaTemporada.objects.all().order_by('-fecha_inicio')
    productos_en_oferta = Producto.objects.filter(en_oferta=True).order_by('nombre')
    todos_productos = Producto.objects.filter(activo=True).order_by('nombre')
    categorias = Categoria.objects.filter(activo=True)

    context = {
        'ofertas': ofertas,
        'activas_count': ofertas.filter(activa=True).count(),
        'productos_en_oferta': productos_en_oferta,
        'productos_oferta_count': productos_en_oferta.count(),
        'todos_productos': todos_productos,
        'categorias': categorias,
        'tipos_campana_choices': OfertaTemporada.TIPOS_CAMPANA,
        'medios_pago_choices': OfertaTemporada.MEDIOS_PAGO_CHOICES,
        'tipos_oferta_producto_choices': Producto.TIPOS_OFERTA,
    }
    return render(request, 'ventas/administrador/administrador_ofertas_temporada.html', context)



# ==============================================================================

# REIMPRESIÓN TRAZABLE DE TICKETS (RF08.6)

# ==============================================================================

@requiere_rol(['ADMINISTRADOR', 'CAJERO', 'MESERO', 'COCINERO', 'BARRA'])

def reimprimir_ticket_view(request, ticket_id):

    """Reimprime un ticket de producción o comprobante de forma trazable (RF08.6)"""

    ticket = get_object_or_404(Ticket, id=ticket_id)

    if not validar_acceso_rls_local(request, ticket.get_punto_venta()):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
            return JsonResponse({'ok': False, 'mensaje': 'Acceso denegado (RLS): ticket de otro local.'}, status=403)
        return error_403_view(request)

    reimprimir_ticket(ticket, usuario_solicitante=request.user)



    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

        return JsonResponse({

            'ok': True,

            'ticket_id': ticket.id,

            'ticket_codigo': ticket.codigo,

            'tipo_destino': ticket.tipo_destino,

            'numero_reimpresiones': ticket.numero_reimpresiones,

            'contenido': ticket.contenido_impresion,

            'mensaje': f"Ticket #{ticket.codigo} reimpreso exitosamente (Copia #{ticket.numero_reimpresiones})."

        })



    messages.success(request, f"Ticket #{ticket.codigo} reimpreso exitosamente (Copia #{ticket.numero_reimpresiones}).")

    return redirect(obtener_url_redireccion_segura(request, 'vendedor'))



@requiere_rol(['ADMINISTRADOR', 'CAJERO', 'MESERO', 'COCINERO', 'BARRA'])

def ver_imprimir_ticket_digital(request, ticket_id):

    """

    Previsualización e impresión digital térmica de ticket (RF09.3).

    Permite abrir la ventana de impresión térmica o del navegador con formato 80mm/58mm.

    """

    ticket = get_object_or_404(Ticket.objects.select_related('punto_impresion', 'punto_venta', 'pedido', 'venta'), id=ticket_id)

    if not validar_acceso_rls_local(request, ticket.get_punto_venta()):

        return error_403_view(request)

    punto_imp = ticket.punto_impresion

    if not punto_imp and ticket.get_punto_venta():

        punto_imp = ticket.get_punto_venta().puntos_impresion.filter(tipo_destino=ticket.tipo_destino).first()



    venta_obj = ticket.venta or (ticket.pedido.venta if ticket.pedido else None)

    subtotal_consumo = venta_obj.get_subtotal_consumo() if venta_obj else Decimal('0')

    propina_10 = int(round(Decimal(str(subtotal_consumo)) * Decimal('0.10')))

    propina_15 = int(round(Decimal(str(subtotal_consumo)) * Decimal('0.15')))

    propina_20 = int(round(Decimal(str(subtotal_consumo)) * Decimal('0.20')))

    monto_neto = venta_obj.get_monto_neto() if venta_obj else Decimal('0')

    monto_iva = venta_obj.get_monto_iva() if venta_obj else Decimal('0')



    return render(request, 'ventas/impresion/ticket_impresion_digital.html', {

        'ticket': ticket,

        'venta': venta_obj,

        'punto_impresion': punto_imp,

        'subtotal_consumo': subtotal_consumo,

        'monto_neto': monto_neto,

        'monto_iva': monto_iva,

        'propina_10': propina_10,

        'propina_15': propina_15,

        'propina_20': propina_20,

        'propina_sugerida': propina_10,

        'total_con_propina': int(subtotal_consumo) + propina_10

    })





@requiere_rol(['ADMINISTRADOR', 'CAJERO', 'MESERO', 'COCINERO', 'BARRA'])

def reintentar_impresion_view(request, ticket_id):

    """

    Reintenta el despacho de impresión de un ticket fallido o pendiente (RF09.4).

    Si el punto de impresión volvió a estar online, despacha sin alterar la venta.

    """

    ticket = get_object_or_404(Ticket, id=ticket_id)

    if not validar_acceso_rls_local(request, ticket.get_punto_venta()):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
            return JsonResponse({'ok': False, 'error': 'Acceso denegado (RLS): ticket de otro local.'}, status=403)
        return error_403_view(request)

    resultado = reintentar_despacho_impresion(ticket, usuario=request.user if request.user.is_authenticated else None)



    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

        return JsonResponse({

            'ok': resultado.get('exito', False),

            'ticket_id': ticket.id,

            'ticket_codigo': ticket.codigo,

            'estado_impresion': ticket.estado_impresion,

            'intentos': ticket.intentos_impresion,

            'error': ticket.error_impresion,

            'mensaje': "Despacho a impresora completado con éxito." if resultado.get('exito') else f"Fallo al reintentar: {ticket.error_impresion}"

        })



    if resultado.get('exito'):

        messages.success(request, f"¡Ticket #{ticket.codigo} reenviado exitosamente a {ticket.punto_impresion.nombre if ticket.punto_impresion else 'la impresora'}!")

    else:

        messages.error(request, f"No se pudo completar el reintento de impresión de #{ticket.codigo}: {ticket.error_impresion}")



    return redirect(request.META.get('HTTP_REFERER') or f"/tickets/{ticket.id}/imprimir/")





# ==============================================================================

# CONSUMO INTERNO DEL PERSONAL / FIADOS POR PLANILLA (RF10)

# ==============================================================================



@requiere_rol(['ADMINISTRADOR', 'CAJERO'])

def registrar_consumo_interno_view(request):

    """

    Endpoint y vista para registrar consumos de colaboradores o fiados por planilla (RF10).

    - Valida que el colaborador seleccionado esté activo (RF10.1).

    - Aplica precios oficiales tomados de la BD en Producto.precio_base (RF10.2).

    - Separación Contable Estricta (RF10.4): No crea registro en Venta ni suma a caja.total_recaudado.

    - Integridad y Atomicidad (RF10.5).

    """

    if request.method != 'POST':

        return JsonResponse({'ok': False, 'error': 'Método no permitido. Se requiere POST.'}, status=405)

    permitido_ip, retry_after, _ = verificar_rate_limit_ip(
        request,
        namespace='consumo_interno_ip',
        max_requests=35,
        window_seconds=60,
    )
    if not permitido_ip:
        resp_429 = JsonResponse({'ok': False, 'error': 'Límite de solicitudes alcanzado para este control.'}, status=429)
        resp_429['Retry-After'] = str(retry_after)
        return resp_429



    empleado_id = request.POST.get('empleado_id')

    tipo_consumo = request.POST.get('tipo_consumo', 'FIADO').upper()

    observaciones = limpiar_texto_seguro(request.POST.get('observaciones', ''), max_length=200)

    items_raw = request.POST.get('items_json', '[]')



    try:

        items = json.loads(items_raw) if isinstance(items_raw, str) else items_raw

    except Exception:

        items = []



    if not items:

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

            return JsonResponse({'ok': False, 'error': 'Debes incluir al menos un producto para registrar consumo interno.'}, status=400)

        messages.error(request, 'Debes incluir al menos un producto para registrar consumo interno.')

        return redirect('crear_ticket')



    # Determinar punto de venta y caja

    perfil = getattr(request.user, 'perfil', None)

    punto_venta = perfil.punto_venta_actual if (perfil and perfil.punto_venta_actual) else PuntoVenta.objects.filter(activo=True).first()



    # Si es cajero, verificar caja activa

    hoy = timezone.localdate()

    jornada_activa = Jornada.objects.filter(estado='ABIERTA', fecha=hoy).first()

    caja_activa = None

    if jornada_activa:

        caja_activa = Caja.objects.filter(jornada=jornada_activa, cajero=request.user, estado='ABIERTA').first()



    if not punto_venta and caja_activa:

        punto_venta = caja_activa.punto_venta



    if not punto_venta:

        punto_venta = PuntoVenta.objects.filter(activo=True).first()



    try:

        consumo = registrar_consumo_interno(

            empleado=empleado_id,

            punto_venta=punto_venta,

            items=items,

            usuario_registro=request.user,

            tipo_consumo=tipo_consumo,

            observaciones=observaciones,

            caja=caja_activa

        )

    except Exception as e:

        err_msg = getattr(e, 'message', str(e))

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

            return JsonResponse({'ok': False, 'error': err_msg}, status=400)

        messages.error(request, f"Error al registrar consumo: {err_msg}")

        return redirect('crear_ticket')



    nombre_emp = consumo.empleado.get_full_name() or consumo.empleado.username

    msg_exito = f"¡Consumo #{consumo.id:04d} registrado con éxito para {nombre_emp} por ${int(consumo.total):,} CLP! (RF10 - Descuento por Planilla)."



    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):

        return JsonResponse({

            'ok': True,

            'consumo_id': consumo.id,

            'codigo_consumo': f"FIA-{consumo.id:04d}",

            'empleado': nombre_emp,

            'total': float(consumo.total),

            'tipo_consumo': consumo.get_tipo_consumo_display(),

            'mensaje': msg_exito

        })



    messages.success(request, msg_exito)

    return redirect('crear_ticket')





@requiere_rol(['ADMINISTRADOR'])

def administrador_consumos(request):

    """

    Panel Administrativo para Gestión y Liquidación de Consumos Internos y Fiados (RF10.3).

    - Monitorea saldos por colaborador y pendientes de descuento en nómina.

    - Permite liquidar por planilla o anular consumos erróneos.

    """

    if request.method == 'POST':

        accion = request.POST.get('accion')



        if accion == 'descontar_empleado':

            empleado_id = request.POST.get('empleado_id')

            emp = get_object_or_404(User, id=empleado_id)

            consumos_pendientes = list(ConsumoInterno.objects.filter(empleado=emp, estado='REGISTRADO').values_list('id', flat=True))

            total_liquidado = ConsumoInterno.objects.filter(id__in=consumos_pendientes).aggregate(total=Sum('total'))['total'] or 0



            liquidar_consumos_por_planilla(consumos_pendientes, supervisor=request.user)

            nombre_emp = emp.get_full_name() or emp.username

            messages.success(request, f"Se liquidaron exitosamente {len(consumos_pendientes)} consumos por un total de ${int(total_liquidado):,} CLP para {nombre_emp}.")



        elif accion == 'descontar_individual':

            consumo_id = request.POST.get('consumo_id')

            consumo = get_object_or_404(ConsumoInterno, id=consumo_id)

            if consumo.estado == 'REGISTRADO':

                liquidar_consumos_por_planilla([consumo.id], supervisor=request.user)

                messages.success(request, f"Consumo #{consumo.id:04d} liquidado y marcado como descontado por planilla.")

            else:

                messages.warning(request, f"El consumo #{consumo.id:04d} ya se encuentra en estado {consumo.get_estado_display()}.")



        elif accion == 'anular_individual':

            consumo_id = request.POST.get('consumo_id')

            motivo_post = request.POST.get('motivo_anulacion')
            if motivo_post is not None:
                motivo_anul = motivo_post.strip()
                if len(motivo_anul) < 5:
                    messages.error(request, "Debe ingresar un motivo detallado de anulación (mínimo 5 caracteres) para auditoría.")
                    return redirect('administrador_consumos')
            else:
                motivo_anul = "Anulación administrativa autorizada por supervisión" 

            consumo = get_object_or_404(ConsumoInterno, id=consumo_id)

            if consumo.estado == 'DESCONTADO':

                messages.error(request, f"Acción denegada: El consumo #{consumo.id:04d} ya fue liquidado y descontado por planilla.")

                return redirect('administrador_consumos')

            consumo.estado = 'ANULADO'

            consumo.observaciones = f"{(consumo.observaciones or '')} [Anulado por {request.user.username}: {motivo_anul}]".strip()

            consumo.save(update_fields=['estado', 'observaciones'])

            AlertaTraslado.objects.create(

                empleado=consumo.empleado,

                punto_venta_origen=consumo.punto_venta,

                punto_venta_destino=consumo.punto_venta,

                autorizado_por=request.user,

                motivo=f"[ANULACIÓN CONSUMO INTERNO #{consumo.id}] Empleado: {consumo.empleado.username}, Total: ${consumo.total}. Motivo: {motivo_anul}"[:255]

            )

            messages.warning(request, f"El consumo #{consumo.id:04d} ha sido anulado y registrado en auditoría inmutable.")



        return redirect('administrador_consumos')



    # Filtros GET

    filtro_estado = request.GET.get('estado', '').strip()

    filtro_local = request.GET.get('local_id', '').strip()



    consumos_qs = ConsumoInterno.objects.select_related('empleado', 'empleado__perfil', 'punto_venta', 'registrado_por', 'descontado_por').prefetch_related('detalles__producto').all()



    if filtro_estado:

        consumos_qs = consumos_qs.filter(estado=filtro_estado)



    if filtro_local and filtro_local.isdigit():

        consumos_qs = consumos_qs.filter(punto_venta_id=int(filtro_local))



    # KPIs Globales

    total_pendiente = ConsumoInterno.objects.filter(estado='REGISTRADO').aggregate(t=Sum('total'))['t'] or Decimal('0.00')

    total_descontado = ConsumoInterno.objects.filter(estado='DESCONTADO').aggregate(t=Sum('total'))['t'] or Decimal('0.00')

    empleados_con_deuda = ConsumoInterno.objects.filter(estado='REGISTRADO').values('empleado').distinct().count()



    # Resumen por Colaborador con Indicadores de Riesgo Crediticio Anti-Fraude

    colaboradores_perfiles = PerfilEmpleado.objects.filter(usuario__is_active=True).select_related('usuario', 'punto_venta_actual').order_by('usuario__first_name', 'usuario__username')

    resumen_colaboradores = []

    colaboradores_alto_riesgo = 0

    for p in colaboradores_perfiles:

        deuda = p.total_fiado_pendiente()

        if deuda >= Decimal('60000'):

            nivel_riesgo = 'ALTO'

            colaboradores_alto_riesgo += 1

        elif deuda >= Decimal('30000'):

            nivel_riesgo = 'MODERADO'

        elif deuda > Decimal('0'):

            nivel_riesgo = 'BAJO'

        else:

            nivel_riesgo = 'AL_DIA'



        resumen_colaboradores.append({

            'usuario': p.usuario,

            'rut': getattr(p, 'rut', '') or 'Sin registrar',

            'rol': p.get_rol_display(),

            'local_nombre': p.punto_venta_actual.nombre if p.punto_venta_actual else 'Sin Asignar',

            'total_pendiente': deuda,

            'nivel_riesgo': nivel_riesgo

        })



    # Ordenar: primero los que tienen deuda pendiente descendente

    resumen_colaboradores.sort(key=lambda x: (x['total_pendiente'] <= 0, -x['total_pendiente'], x['usuario'].username))



    locales = PuntoVenta.objects.filter(activo=True).order_by('id')



    context = {

        'total_pendiente': total_pendiente,

        'total_descontado': total_descontado,

        'empleados_con_deuda': empleados_con_deuda,

        'colaboradores_alto_riesgo': colaboradores_alto_riesgo,

        'consumos': consumos_qs,

        'resumen_colaboradores': resumen_colaboradores,

        'locales': locales,

    }

    return render(request, 'ventas/administrador/administrador_consumos.html', context)







@requiere_rol(['COCINERO', 'BARRA', 'ADMINISTRADOR', 'MESERO', 'CAJERO'])
def api_sincronizacion_estado(request):
    """
    Endpoint delta de alta eficiencia (~150-350 bytes JSON).
    Permite a KDS (Cocina/Barra), Mesero, Cajero y Administrador verificar cambios reales
    mediante firma MD5 antes de descargar HTML, además de notificar instantáneamente pedidos LISTOS.
    """
    hoy = timezone.localdate()
    local_id = request.GET.get('local_id')
    zona = request.GET.get('zona', 'TODAS').upper()

    if zona == 'ADMIN' and not local_id:
        perfil = getattr(request.user, 'perfil', None)
        if not (request.user.is_superuser or (perfil and perfil.rol == 'ADMINISTRADOR')):
            return JsonResponse({'ok': False, 'error': 'Acceso denegado (RLS): exclusivo de administración.'}, status=403)

        ult_venta = Venta.objects.order_by('-id').values_list('id', 'estado', 'total').first()
        venta_sig = f"{ult_venta[0]}:{ult_venta[1]}:{int(ult_venta[2] or 0)}" if ult_venta else "0"
        ventas_hoy_cnt = Venta.objects.filter(fecha_hora__date=hoy).exclude(estado__in=['ANULADA', 'CANCELADA']).count()
        ult_ped = Pedido.objects.order_by('-actualizado_en', '-id').values_list(
            'id', 'estado', 'estado_cocina', 'estado_barra', 'actualizado_en'
        ).first()
        ts_ped = int(ult_ped[4].timestamp()) if ult_ped and ult_ped[4] else 0
        ped_sig = f"{ult_ped[0]}:{ult_ped[1]}:{ult_ped[2]}:{ult_ped[3]}:{ts_ped}" if ult_ped else "0"
        alertas_no_leidas = AlertaTraslado.objects.filter(leida=False).count()
        cajas_abiertas_cnt = Caja.objects.filter(estado='ABIERTA').count()

        import hashlib
        sig_str = f"ADMIN:{ventas_hoy_cnt}:{venta_sig}:{ped_sig}:{alertas_no_leidas}:{cajas_abiertas_cnt}"
        version_hash = hashlib.md5(sig_str.encode('utf-8')).hexdigest()[:12]

        resp = JsonResponse({
            'ok': True,
            'version': version_hash,
            'alertas_no_leidas': alertas_no_leidas,
            'cajas_abiertas': cajas_abiertas_cnt,
            'ventas_hoy': ventas_hoy_cnt,
            'ts': ts_ped,
        })
        resp['Cache-Control'] = 'no-store'
        return resp

    local_actual = None
    if local_id:
        try:
            local_actual = PuntoVenta.objects.filter(id=int(local_id), activo=True).first()
        except (ValueError, TypeError):
            local_actual = None
        if local_actual and not validar_acceso_rls_local(request, local_actual):
            return JsonResponse({'ok': False, 'error': 'Acceso denegado (RLS): no puedes consultar estados de otro local.'}, status=403)

    if not local_actual:
        perfil = getattr(request.user, 'perfil', None)
        if perfil and perfil.punto_venta_actual:
            local_actual = perfil.punto_venta_actual
        elif request.user.is_superuser or (perfil and perfil.rol == 'ADMINISTRADOR'):
            local_actual = PuntoVenta.objects.filter(activo=True).first()
        else:
            return JsonResponse({'ok': False, 'error': 'Acceso denegado (RLS): trabajador sin punto de venta asignado.'}, status=403)

    ahora_dt = timezone.localtime()
    hace_4_horas = ahora_dt - datetime.timedelta(hours=4)

    pedidos_activos = list(
        Pedido.objects.filter(
            venta__punto_venta=local_actual,
            creado_en__date=hoy,
            creado_en__gte=hace_4_horas,
            estado__in=['PENDIENTE', 'EN_PREPARACION', 'LISTO'],
        )
        .exclude(venta__estado__in=['ANULADA', 'CANCELADA'])
        .exclude(venta__caja__jornada__estado='CERRADA')
        .select_related('venta__mesa')
        .prefetch_related('detalles__producto__categoria')
    )

    tot_pendientes = 0
    tot_preparacion = 0
    tot_listos = 0
    activos_ids = []
    listos_detalle = []

    if zona in ('COCINA', 'BARRA'):
        campo_zona = 'estado_cocina' if zona == 'COCINA' else 'estado_barra'
        for p in pedidos_activos:
            est_zona = getattr(p, campo_zona)
            if zona in p.get_estaciones_activas() and est_zona in ('PENDIENTE', 'EN_PREPARACION', 'LISTO'):
                activos_ids.append(p.id)
                if est_zona == 'PENDIENTE':
                    tot_pendientes += 1
                elif est_zona == 'EN_PREPARACION':
                    tot_preparacion += 1
                elif est_zona == 'LISTO':
                    tot_listos += 1
    else:
        for p in pedidos_activos:
            activos_ids.append(p.id)
            if p.estado == 'PENDIENTE':
                tot_pendientes += 1
            elif p.estado == 'EN_PREPARACION':
                tot_preparacion += 1
            if p.estado == 'LISTO' or p.estado_cocina == 'LISTO' or p.estado_barra == 'LISTO':
                tot_listos += 1

            estaciones = p.get_estaciones_activas()
            mesa_lbl = p.venta.mesa.identificador if (p.venta and p.venta.mesa) else 'Mostrador'
            es_mesa = bool(p.venta and p.venta.mesa_id)
            codigo_com = f"COM-{p.id:04d}"
            agregado_est = False
            if 'COCINA' in estaciones and p.estado_cocina == 'LISTO':
                listos_detalle.append({
                    'key': f"{p.id}:COCINA",
                    'pedido_id': p.id,
                    'codigo': codigo_com,
                    'estacion': 'Cocina',
                    'mesa': mesa_lbl,
                    'es_mesa': es_mesa,
                })
                agregado_est = True
            if 'BARRA' in estaciones and p.estado_barra == 'LISTO':
                listos_detalle.append({
                    'key': f"{p.id}:BARRA",
                    'pedido_id': p.id,
                    'codigo': codigo_com,
                    'estacion': 'Barra',
                    'mesa': mesa_lbl,
                    'es_mesa': es_mesa,
                })
                agregado_est = True
            if p.estado == 'LISTO' and not agregado_est:
                listos_detalle.append({
                    'key': f"{p.id}:GENERAL",
                    'pedido_id': p.id,
                    'codigo': codigo_com,
                    'estacion': 'Cocina/Barra',
                    'mesa': mesa_lbl,
                    'es_mesa': es_mesa,
                })

    tot_cola = tot_pendientes + tot_preparacion + tot_listos

    # Firma reactiva de mesas: refleja cualquier cambio (HABILITADA, OCUPADA, RESERVADA, INACTIVA)
    mesas_loc = list(Mesa.objects.filter(punto_venta=local_actual).order_by('id').values_list('id', 'estado'))
    mesas_ocupadas = sum(1 for _, est in mesas_loc if est == 'OCUPADA')
    mesas_sig = "-".join(f"{mid}:{est}" for mid, est in mesas_loc)

    # Firma reactiva de cuentas abiertas de salón (1 consulta agregada)
    ventas_agg = Venta.objects.filter(punto_venta=local_actual, estado='ABIERTA').aggregate(
        cnt=Count('id'),
        total=models.Sum('total'),
    )
    ventas_abiertas_count = int(ventas_agg['cnt'] or 0)
    ventas_abiertas_sum = int(ventas_agg['total'] or 0)

    # Última venta y último pedido (solo columnas escalares indexadas)
    ult_venta = (
        Venta.objects.filter(punto_venta=local_actual, fecha_hora__date=hoy)
        .order_by('-id')
        .values_list('id', 'estado', 'total')
        .first()
    )
    venta_sig = f"{ult_venta[0]}:{ult_venta[1]}:{int(ult_venta[2] or 0)}" if ult_venta else "0"

    ult_ped_general = (
        Pedido.objects.filter(venta__punto_venta=local_actual, creado_en__date=hoy)
        .order_by('-actualizado_en', '-id')
        .values_list('id', 'estado', 'estado_cocina', 'estado_barra', 'actualizado_en')
        .first()
    )
    ts_ped = int(ult_ped_general[4].timestamp()) if ult_ped_general and ult_ped_general[4] else 0
    ped_estado_sig = (
        f"{ult_ped_general[0]}:{ult_ped_general[1]}:{ult_ped_general[2]}:{ult_ped_general[3]}:{ts_ped}"
        if ult_ped_general else "0"
    )

    stock_count = Producto.objects.filter(activo=True).count()

    jornada_sync_id = Jornada.objects.filter(estado='ABIERTA', fecha=hoy).values_list('id', flat=True).first()
    cajas_abiertas_sig = (
        "-".join(
            str(cid) for cid in Caja.objects.filter(
                punto_venta=local_actual, jornada_id=jornada_sync_id, estado='ABIERTA'
            ).order_by('id').values_list('id', flat=True)
        )
        if jornada_sync_id else "sin_jornada"
    )
    listos_keys_sig = ",".join(item['key'] for item in listos_detalle)
    activos_sig = ",".join(str(pid) for pid in activos_ids)

    import hashlib
    sig_str = (
        f"{local_actual.id if local_actual else 0}:{tot_cola}:{tot_pendientes}:{tot_preparacion}:{tot_listos}:"
        f"{mesas_sig}:{ventas_abiertas_count}:{ventas_abiertas_sum}:{venta_sig}:{ped_estado_sig}:"
        f"{stock_count}:{jornada_sync_id or 0}:{cajas_abiertas_sig}:{listos_keys_sig}:{activos_sig}"
    )
    version_hash = hashlib.md5(sig_str.encode('utf-8')).hexdigest()[:12]

    resp = JsonResponse({
        'ok': True,
        'version': version_hash,
        'cola_total': tot_cola,
        'pendientes': tot_pendientes,
        'preparacion': tot_preparacion,
        'listos': tot_listos,
        'mesas_ocupadas': mesas_ocupadas,
        'pedidos_listos': tot_listos,
        'activos_ids': activos_ids,
        'listos_detalle': listos_detalle,
        'ts': ts_ped,
    })
    resp['Cache-Control'] = 'no-store'
    return resp





@requiere_rol(['COCINERO', 'BARRA', 'ADMINISTRADOR'])

def api_toggle_stock_producto(request):

    """

    Permite al personal de cocina/barra pausar o habilitar un plato en tiempo real con 1 clic (RF15).

    Cuando un insumo se agota en cocina, se desactiva inmediatamente para que meseros y cajeros

    vean el aviso 'Agotado en cocina' y no puedan ingresarlo en comandas ni tickets.

    """

    if request.method != 'POST':

        return JsonResponse({'ok': False, 'error': 'Método no permitido. Se requiere POST.'}, status=405)

    permitido_ip, retry_after, _ = verificar_rate_limit_ip(
        request,
        namespace='api_toggle_stock_ip',
        max_requests=45,
        window_seconds=60,
    )
    if not permitido_ip:
        resp_429 = JsonResponse({'ok': False, 'error': 'Límite de solicitudes alcanzado para este control.'}, status=429)
        resp_429['Retry-After'] = str(retry_after)
        return resp_429



    prod_id = request.POST.get('producto_id')

    if not prod_id and request.body:

        try:

            body = json.loads(request.body.decode('utf-8'))

            prod_id = body.get('producto_id')

        except Exception:

            pass



    if not prod_id:

        return JsonResponse({'ok': False, 'error': 'Identificador de producto no especificado.'}, status=400)



    try:

        prod_id = int(prod_id)

    except (ValueError, TypeError):

        return JsonResponse({'ok': False, 'error': 'Identificador numérico inválido.'}, status=400)



    with transaction.atomic():

        prod = Producto.objects.select_for_update().filter(id=prod_id).first()

        if not prod:

            return JsonResponse({'ok': False, 'error': f"El producto #{prod_id} no existe."}, status=404)

        pvs_prod = list(prod.puntos_venta.all())
        if pvs_prod and not any(validar_acceso_rls_local(request, pv) for pv in pvs_prod):
            return JsonResponse({'ok': False, 'error': 'Acceso denegado (RLS): el producto no pertenece a tu local.'}, status=403)



        prod.activo = not prod.activo

        prod.save(update_fields=['activo'])



        estado_txt = "DISPONIBLE" if prod.activo else "AGOTADO EN COCINA"

        usuario_nom = request.user.get_full_name() or request.user.username



        pv_prod = prod.puntos_venta.first() or PuntoVenta.objects.first()

        AlertaTraslado.objects.create(

            empleado=request.user,

            punto_venta_origen=pv_prod,

            punto_venta_destino=pv_prod,

            autorizado_por=request.user,

            motivo=f"[KDS STOCK] Plato '{prod.nombre}' marcado como {estado_txt} por {usuario_nom}"[:255]

        )



    return JsonResponse({

        'ok': True,

        'producto_id': prod.id,

        'nombre': prod.nombre,

        'activo': prod.activo,

        'mensaje': f"Plato '{prod.nombre}' actualizado a {estado_txt}."

    })

