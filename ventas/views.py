import datetime
import json
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404, Http404
from django.http import JsonResponse
from django.contrib import messages
from django.db import models, transaction
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout

from .models import PuntoVenta, PerfilEmpleado, AlertaTraslado, Mesa, Jornada, Caja, Venta, DetalleVenta, Pedido, DetallePedido, Ticket, Categoria, Producto, Menu, Entrega


def get_locales_data():
    """Retorna los datos operativos de todos los locales gastronómicos registrados en la BD de Parque Safari"""
    # Métricas y simulaciones base de la jornada para los locales demo iniciales
    mock_metricas = {
        1: {
            "nombre": "Restaurante Central Safari",
            "tipo": "Restaurante & Buffet Caliente",
            "descripcion": "Comida por cocinar, platos de fondo caliente, minutas, hamburguesas y autoservicio para familias.",
            "icono": "bi-building-fill",
            "color": "#c62828",
            "turno": "Turno Continuo (09:00 - 19:30)",
            "total_ventas": 940000,
            "tickets_emitidos": 72,
            "ticket_promedio": 13055,
            "caja_apertura": 100000,
            "caja_efectivo": 320000,
            "caja_tarjeta": 620000,
            "saldo_actual": 420000,
            "ventas_categoria": [
                {"nombre": "Comida por Cocinar", "monto": 560000, "porcentaje": 60, "color": "#ef4444"},
                {"nombre": "Comida Preparada", "monto": 180000, "porcentaje": 19, "color": "#f59e0b"},
                {"nombre": "Bebidas Envasadas", "monto": 120000, "porcentaje": 13, "color": "#0284c7"},
                {"nombre": "Cafetería y Jugos", "monto": 80000, "porcentaje": 8, "color": "#9333ea"}
            ],
            "metodos_pago": [
                {"metodo": "Tarjeta Débito", "monto": 480000, "porcentaje": 51, "icono": "bi-credit-card"},
                {"metodo": "Efectivo", "monto": 320000, "porcentaje": 34, "icono": "bi-cash-coin"},
                {"metodo": "Tarjeta Crédito", "monto": 140000, "porcentaje": 15, "icono": "bi-credit-card-2-front"}
            ],
            "tickets_recientes": [
                {
                    "id": "COM-0084",
                    "hora": "14:21",
                    "cliente": "Mesa 8",
                    "total": 25400,
                    "cajero": "Carlos Valenzuela",
                    "creador_rol": "Mesero",
                    "estado": "En Cocina",
                    "items": [
                        {"nombre": "Hamburguesa Safari con Papas", "cantidad": 2, "precio": 8900, "subtotal": 17800, "destino": "Cocina", "nota": "Sin cebolla"},
                        {"nombre": "Bebida Coca-Cola 350ml", "cantidad": 2, "precio": 2000, "subtotal": 4000, "destino": "Barra", "nota": "Bien fría"},
                        {"nombre": "Porción Papas Fritas Rústicas", "cantidad": 1, "precio": 3600, "subtotal": 3600, "destino": "Cocina", "nota": "Poco condimento"}
                    ]
                },
                {
                    "id": "COM-0081",
                    "hora": "14:10",
                    "cliente": "Mesa 4",
                    "total": 23000,
                    "cajero": "Carlos Valenzuela",
                    "creador_rol": "Cajero",
                    "estado": "En Cocina",
                    "items": [
                        {"nombre": "Churrasco Italiano con Papas", "cantidad": 2, "precio": 8500, "subtotal": 17000, "destino": "Cocina", "nota": "Mayonesa casera aparte"},
                        {"nombre": "Café Cappuccino", "cantidad": 2, "precio": 3000, "subtotal": 6000, "destino": "Barra", "nota": "Leche descremada"}
                    ]
                },
                {
                    "id": "COM-0078",
                    "hora": "13:55",
                    "cliente": "Mesa 2",
                    "total": 18900,
                    "cajero": "Matías González",
                    "creador_rol": "Mesero",
                    "estado": "Entregado",
                    "items": [
                        {"nombre": "Cazuela de Ave Criolla", "cantidad": 2, "precio": 7500, "subtotal": 15000, "destino": "Cocina", "nota": "Bien caliente"},
                        {"nombre": "Jugo Natural de Fruta", "cantidad": 1, "precio": 3900, "subtotal": 3900, "destino": "Barra", "nota": "Frambuesa con hielo"}
                    ]
                },
                {
                    "id": "COM-0075",
                    "hora": "13:40",
                    "cliente": "Mostrador",
                    "total": 14500,
                    "cajero": "Carlos Valenzuela",
                    "creador_rol": "Cajero",
                    "estado": "Entregado",
                    "items": [
                        {"nombre": "Menú Infantil Nuggets con Papas", "cantidad": 2, "precio": 5900, "subtotal": 11800, "destino": "Cocina", "nota": "Con ketchup"},
                        {"nombre": "Jugo en Caja 200ml", "cantidad": 2, "precio": 1350, "subtotal": 2700, "destino": "Barra", "nota": ""}
                    ]
                }
            ]
        },
        2: {
            "nombre": "Cafetería & Pastelería La Selva",
            "tipo": "Cafetería Barista & Repostería",
            "descripcion": "Café de grano italiano de barista, sándwiches frescos de vitrina, jugos naturales exprimidos y pastelería.",
            "icono": "bi-cup-hot-fill",
            "color": "#6b21a8",
            "turno": "Turno Mañana/Tarde (09:30 - 19:00)",
            "total_ventas": 520000,
            "tickets_emitidos": 45,
            "ticket_promedio": 11555,
            "caja_apertura": 80000,
            "caja_efectivo": 190000,
            "caja_tarjeta": 330000,
            "saldo_actual": 270000,
            "ventas_categoria": [
                {"nombre": "Cafetería y Jugos", "monto": 260000, "porcentaje": 50, "color": "#9333ea"},
                {"nombre": "Comida Preparada", "monto": 160000, "porcentaje": 31, "color": "#f59e0b"},
                {"nombre": "Bebidas Envasadas", "monto": 80000, "porcentaje": 15, "color": "#0284c7"},
                {"nombre": "Comida por Cocinar", "monto": 20000, "porcentaje": 4, "color": "#ef4444"}
            ],
            "metodos_pago": [
                {"metodo": "Tarjeta Débito", "monto": 280000, "porcentaje": 54, "icono": "bi-credit-card"},
                {"metodo": "Efectivo", "monto": 190000, "porcentaje": 37, "icono": "bi-cash-coin"},
                {"metodo": "Tarjeta Crédito", "monto": 50000, "porcentaje": 9, "icono": "bi-credit-card-2-front"}
            ],
            "tickets_recientes": [
                {
                    "id": "COM-0082",
                    "hora": "14:15",
                    "cliente": "Para Llevar",
                    "total": 13300,
                    "cajero": "Camila Soto",
                    "creador_rol": "Cajero",
                    "estado": "En Barra",
                    "items": [
                        {"nombre": "Café de Grano / Cortado", "cantidad": 2, "precio": 2400, "subtotal": 4800, "destino": "Barra", "nota": "Término caliente"},
                        {"nombre": "Sándwich Ave Pimentón", "cantidad": 1, "precio": 4200, "subtotal": 4200, "destino": "Barra", "nota": "Calentar pan"},
                        {"nombre": "Medialuna Rellena", "cantidad": 2, "precio": 2150, "subtotal": 4300, "destino": "Barra", "nota": "Manjar"}
                    ]
                },
                {
                    "id": "COM-0079",
                    "hora": "13:58",
                    "cliente": "Terraza #1",
                    "total": 8600,
                    "cajero": "Camila Soto",
                    "creador_rol": "Mesero",
                    "estado": "Entregado",
                    "items": [
                        {"nombre": "Café Cappuccino", "cantidad": 2, "precio": 2800, "subtotal": 5600, "destino": "Barra", "nota": "Canela en polvo"},
                        {"nombre": "Empanada de Queso", "cantidad": 1, "precio": 3000, "subtotal": 3000, "destino": "Barra", "nota": "Al horno"}
                    ]
                },
                {
                    "id": "COM-0076",
                    "hora": "13:42",
                    "cliente": "Para Llevar",
                    "total": 11200,
                    "cajero": "Camila Soto",
                    "creador_rol": "Cajero",
                    "estado": "Entregado",
                    "items": [
                        {"nombre": "Limonada Menta Jengibre", "cantidad": 2, "precio": 3200, "subtotal": 6400, "destino": "Barra", "nota": "Hielo aparte"},
                        {"nombre": "Sándwich Pan Jamón y Queso", "cantidad": 1, "precio": 3500, "subtotal": 3500, "destino": "Barra", "nota": "Tostado"},
                        {"nombre": "Agua Mineral 500ml", "cantidad": 1, "precio": 1300, "subtotal": 1300, "destino": "Barra", "nota": "Sin gas"}
                    ]
                }
            ]
        },
        3: {
            "nombre": "Barra Rápida & Kiosco Oasis",
            "tipo": "Punto Snack & Bebidas Frías",
            "descripcion": "Bebidas frías, jugos en caja, empanadas de mantenedor, helados y snacks al paso en zonas de recorrido.",
            "icono": "bi-shop-window",
            "color": "#0284c7",
            "turno": "Turno Tarde (10:00 - 18:30)",
            "total_ventas": 385000,
            "tickets_emitidos": 38,
            "ticket_promedio": 10131,
            "caja_apertura": 60000,
            "caja_efectivo": 165000,
            "caja_tarjeta": 220000,
            "saldo_actual": 225000,
            "ventas_categoria": [
                {"nombre": "Bebidas Envasadas", "monto": 195000, "porcentaje": 51, "color": "#0284c7"},
                {"nombre": "Comida Preparada", "monto": 150000, "porcentaje": 39, "color": "#f59e0b"},
                {"nombre": "Cafetería y Jugos", "monto": 40000, "porcentaje": 10, "color": "#9333ea"},
                {"nombre": "Comida por Cocinar", "monto": 0, "porcentaje": 0, "color": "#ef4444"}
            ],
            "metodos_pago": [
                {"metodo": "Tarjeta Débito", "monto": 170000, "porcentaje": 44, "icono": "bi-credit-card"},
                {"metodo": "Efectivo", "monto": 165000, "porcentaje": 43, "icono": "bi-cash-coin"},
                {"metodo": "Tarjeta Crédito", "monto": 50000, "porcentaje": 13, "icono": "bi-credit-card-2-front"}
            ],
            "tickets_recientes": [
                {
                    "id": "COM-0083",
                    "hora": "14:18",
                    "cliente": "Mostrador",
                    "total": 7500,
                    "cajero": "Matías González",
                    "creador_rol": "Cajero",
                    "estado": "Listo",
                    "items": [
                        {"nombre": "Bebida Coca-Cola 350ml", "cantidad": 2, "precio": 2000, "subtotal": 4000, "destino": "Barra", "nota": ""},
                        {"nombre": "Pan Jamón y Queso", "cantidad": 1, "precio": 3500, "subtotal": 3500, "destino": "Barra", "nota": ""}
                    ]
                },
                {
                    "id": "COM-0080",
                    "hora": "14:02",
                    "cliente": "Paso",
                    "total": 6200,
                    "cajero": "Matías González",
                    "creador_rol": "Cajero",
                    "estado": "Entregado",
                    "items": [
                        {"nombre": "Empanada de Pino al Horno", "cantidad": 1, "precio": 3200, "subtotal": 3200, "destino": "Barra", "nota": ""},
                        {"nombre": "Agua Mineral 500ml", "cantidad": 2, "precio": 1500, "subtotal": 3000, "destino": "Barra", "nota": ""}
                    ]
                },
                {
                    "id": "COM-0077",
                    "hora": "13:46",
                    "cliente": "Paso",
                    "total": 4500,
                    "cajero": "Matías González",
                    "creador_rol": "Cajero",
                    "estado": "Entregado",
                    "items": [
                        {"nombre": "Sándwich Ave Pimentón", "cantidad": 1, "precio": 3000, "subtotal": 3000, "destino": "Barra", "nota": ""},
                        {"nombre": "Agua Mineral 500ml", "cantidad": 1, "precio": 1500, "subtotal": 1500, "destino": "Barra", "nota": ""}
                    ]
                }
            ]
        }
    }

    # Cargar todos los puntos de venta reales registrados en la BD
    locales_bd = PuntoVenta.objects.all().order_by('id')
    locales = {}

    hoy = timezone.localdate()
    ahora_dt = timezone.localtime()
    ahora_hora = ahora_dt.time()

    # Regla Operativa Oficial Parque Safari: Todos los locales abren a las 10:00 y cierran a las 18:00 (10:00 AM a 6:00 PM)
    hora_apertura = datetime.time(10, 0)
    hora_cierre = datetime.time(18, 0)
    en_horario = (hora_apertura <= ahora_hora < hora_cierre)

    for pv in locales_bd:
        demo = mock_metricas.get(pv.id, {})

        # Regla Parque Safari: Guiado por día y hora. Las ventas corresponden exclusivamente al día actual (hoy).
        # Al finalizar el día o empezar un nuevo día, la cuenta vuelve automáticamente a 0.
        real_ventas_hoy = Venta.objects.filter(
            punto_venta=pv,
            fecha_hora__date=hoy
        ).select_related('cajero', 'cajero__perfil', 'mesa').prefetch_related('detalles__producto').order_by('-fecha_hora')

        real_tickets = []
        suma_ventas_reales = 0

        for rv in real_ventas_hoy:
            rol_c = obtener_rol_usuario(rv.cajero) or "Mesero"
            v_items = []
            for d in rv.detalles.all():
                nom = d.producto.nombre
                dest = "Cocina" if any(w in nom.lower() for w in ['hamburguesa', 'cazuela', 'churrasco', 'papas', 'nuggets', 'almuerzo']) else "Barra"
                v_items.append({
                    "nombre": nom,
                    "cantidad": d.cantidad,
                    "precio": int(d.precio_aplicado),
                    "subtotal": int(d.subtotal),
                    "destino": dest,
                    "nota": ""
                })
            suma_ventas_reales += int(rv.total)
            real_tickets.append({
                "id": f"COM-{rv.id:04d}",
                "hora": timezone.localtime(rv.fecha_hora).strftime("%H:%M"),
                "cliente": rv.mesa.identificador if rv.mesa else "Mostrador",
                "total": int(rv.total),
                "cajero": rv.cajero.get_full_name() or rv.cajero.username,
                "creador_rol": "Mesero" if rol_c == 'MESERO' else "Cajero",
                "estado": "En Cocina" if any(it["destino"] == "Cocina" for it in v_items) else "Listo",
                "items": v_items,
                "items_json": json.dumps(v_items)
            })

        # Si el local tiene ventas hoy, se muestran; si no, la cuenta del día está limpia en 0
        total_ventas_calc = suma_ventas_reales
        tickets_emitidos_calc = len(real_tickets)
        ticket_prom_calc = round(total_ventas_calc / tickets_emitidos_calc) if tickets_emitidos_calc else 0

        turno_oficial = "Horario Oficial (10:00 - 18:00)"
        if pv.activo:
            estado_local = "Abierto (10:00 - 18:00)" if en_horario else "Cerrado (Horario 10:00 - 18:00)"
        else:
            estado_local = "Inactivo"

        locales[pv.id] = {
            "id": pv.id,
            "nombre": pv.nombre,
            "tipo": pv.tipo or demo.get("tipo", "Punto de Venta"),
            "descripcion": pv.descripcion or demo.get("descripcion", "Punto gastronómico operativo de Parque Safari."),
            "icono": getattr(pv, 'icono', None) or demo.get("icono", "bi-shop"),
            "color": getattr(pv, 'color', None) or demo.get("color", "#c62828"),
            "estado": estado_local,
            "en_horario": en_horario,
            "horario_apertura": "10:00",
            "horario_cierre": "18:00",
            "turno": turno_oficial,
            "total_ventas": total_ventas_calc,
            "tickets_emitidos": tickets_emitidos_calc,
            "ticket_promedio": ticket_prom_calc,
            "caja_apertura": demo.get("caja_apertura", 0),
            "caja_efectivo": demo.get("caja_efectivo", 0),
            "caja_tarjeta": demo.get("caja_tarjeta", 0),
            "saldo_actual": suma_ventas_reales,
            "personal": [],
            "ventas_categoria": demo.get("ventas_categoria", []),
            "metodos_pago": demo.get("metodos_pago", []),
            "tickets_recientes": real_tickets
        }

    # Si por algún motivo aún no hay locales en BD (p.ej. antes del seeding), cargar los mock por defecto
    if not locales and mock_metricas:
        for mid, mdata in mock_metricas.items():
            locales[mid] = {
                "id": mid,
                **mdata,
                "estado": "En Servicio",
                "personal": []
            }

    # Sincronizar dotación de personal real desde la BD respetando el límite de 1 puesto de trabajo
    for loc_id, loc in locales.items():
        perfiles = PerfilEmpleado.objects.filter(punto_venta_actual_id=loc_id, activo=True).select_related('usuario')
        if perfiles.exists():
            loc["personal"] = [
                {
                    "perfil_id": p.id,
                    "nombre": p.usuario.get_full_name() or p.usuario.username,
                    "rut": p.rut or "S/RUT",
                    "cargo": p.get_rol_display(),
                    "hora_login": "08:30" if p.rol == 'MESERO' else "08:45",
                    "caja": f"Caja {loc['nombre'].split()[0]} #1",
                    "estado": "Activo"
                }
                for p in perfiles
            ]

    return locales


def obtener_rol_usuario(user):
    """Retorna el rol oficial ('ADMINISTRADOR', 'CAJERO', 'MESERO') del usuario autenticado"""
    if not user.is_authenticated:
        return None
    try:
        perfil = user.perfil
        return perfil.rol
    except (PerfilEmpleado.DoesNotExist, AttributeError):
        if user.is_superuser or user.is_staff:
            return 'ADMINISTRADOR'
        return None


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
            if not request.user.is_authenticated:
                messages.warning(request, "Acceso protegido: Debes iniciar sesión con tus credenciales para ingresar.")
                return redirect('index')

            # Verificar si el usuario o su PerfilEmpleado fue desactivado
            if not request.user.is_active:
                logout(request)
                messages.error(request, "Tu cuenta de colaborador ha sido desactivada. La sesión fue cerrada por seguridad.")
                return redirect('index')

            perfil = getattr(request.user, 'perfil', None)
            if perfil and not perfil.activo:
                logout(request)
                messages.error(request, "Tu cuenta de colaborador se encuentra inactiva. La sesión fue cerrada por seguridad.")
                return redirect('index')

            rol = obtener_rol_usuario(request.user)
            if rol not in roles_permitidos:
                messages.error(request, f"Acceso restringido: Tu perfil ({rol or 'Sin Rol'}) no tiene autorización para acceder a esta sección.")
                if rol == 'ADMINISTRADOR':
                    return redirect('administrador')
                elif rol == 'CAJERO':
                    return redirect('vendedor')
                elif rol == 'MESERO':
                    return redirect('mesero')
                elif rol == 'COCINERO':
                    return redirect('cocina')
                return redirect('index')

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def obtener_ip_cliente(request):
    """Obtiene la dirección IP real del cliente considerando proxies inversos"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip


MAX_INTENTOS_LOGIN = 5
TIEMPO_BLOQUEO_LOGIN = 300  # 5 minutos en segundos


def login_view(request):
    """RF01: Inicio de sesión real con django.contrib.auth, protección de fuerza bruta y redirección automática por rol"""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Validar campos requeridos obligatorios (Semana 10)
        if not username or not password:
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

        # Validar autenticación
        user = authenticate(request, username=username, password=password)
        if user is not None:
            perfil = getattr(user, 'perfil', None)
            if not user.is_active or (perfil and not perfil.activo):
                messages.error(request, "Tu cuenta de colaborador se encuentra inactiva. Contacta al Administrador.")
                return redirect('index')

            # Autenticación exitosa: Limpiar contadores de intentos fallidos
            cache.delete(key_bloqueo)
            cache.delete(key_intentos)
            cache.delete(key_ip_bloqueo)
            cache.delete(key_ip_intentos)

            login(request, user)
            rol = obtener_rol_usuario(user)

            if rol == 'ADMINISTRADOR':
                messages.success(request, f"Bienvenido(a) Administrador(a) {user.get_full_name() or user.username}.")
                return redirect('administrador')
            elif rol == 'CAJERO':
                messages.success(request, f"Bienvenido(a) Cajero(a) {user.get_full_name() or user.username}.")
                return redirect('vendedor')
            elif rol == 'MESERO':
                messages.success(request, f"Bienvenido(a) Mesero(a) {user.get_full_name() or user.username}.")
                return redirect('mesero')
            elif rol == 'COCINERO':
                messages.success(request, f"Bienvenido(a) Cocinero(a) {user.get_full_name() or user.username}.")
                return redirect('cocina')
            else:
                messages.warning(request, "Usuario autenticado sin rol asignado en el sistema.")
                return redirect('index')
        else:
            # Comprobar si el usuario existe y su contraseña coincide pero la cuenta está inactiva
            # (El backend estándar de Django retorna None en authenticate() si is_active es False)
            existing_user = User.objects.filter(username=username).first()
            if existing_user and existing_user.check_password(password):
                perfil = getattr(existing_user, 'perfil', None)
                if not existing_user.is_active or (perfil and not perfil.activo):
                    messages.error(request, "Tu cuenta de colaborador se encuentra inactiva. Contacta al Administrador.")
                    return redirect('index')

            # Registro de intento fallido para prevención de fuerza bruta
            intentos_previos = cache.get(key_intentos, 0)
            intentos_actuales = intentos_previos + 1

            # Registro de intentos fallidos a nivel de IP global (máx 10 por IP)
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
    """Cierre de sesión seguro y retorno al portal inicial"""
    motivo = request.GET.get('motivo')
    logout(request)
    if motivo == 'inactividad':
        messages.warning(request, "Tu sesión fue cerrada automáticamente tras 15 minutos de inactividad por políticas de seguridad institucional.")
    else:
        messages.info(request, "Has cerrado tu sesión de forma segura. ¡Hasta pronto!")
    return redirect('index')


def error_404_view(request, exception=None):
    """
    Manejador personalizado de error HTTP 404 (Semana 10).
    Captura rutas inexistentes, URLs malformadas y llamadas get_object_or_404.
    Presenta interfaz amigable y coherente con Parque Safari sin exponer detalles técnicos.
    """
    rol = None
    if request.user.is_authenticated:
        rol = obtener_rol_usuario(request.user)
    return render(request, '404.html', {'rol_usuario': rol, 'path_solicitado': request.path}, status=404)


def error_403_view(request, exception=None):
    """
    Manejador personalizado de error HTTP 403 (Semana 10).
    Captura accesos no autorizados y permisos denegados.
    """
    rol = None
    if request.user.is_authenticated:
        rol = obtener_rol_usuario(request.user)
    return render(request, '403.html', {'rol_usuario': rol, 'path_solicitado': request.path}, status=403)


def error_400_view(request, exception=None):
    """
    Manejador personalizado de error HTTP 400 (Semana 10).
    Captura solicitudes inválidas y manipulación de parámetros.
    """
    rol = None
    if request.user.is_authenticated:
        rol = obtener_rol_usuario(request.user)
    return render(request, '400.html', {'rol_usuario': rol, 'path_solicitado': request.path}, status=400)


def error_500_view(request):
    """
    Manejador personalizado de error HTTP 500 (Semana 10).
    Captura excepciones no controladas del servidor.
    Oculta trazas técnicas sensibles al usuario final (blindaje OWASP) y provee retorno seguro.
    """
    return render(request, '500.html', {}, status=500)



def index(request):
    return render(request, 'ventas/index.html')


@requiere_rol(['CAJERO'])
def vendedor(request):
    """
    Pantalla intermedia del Cajero:
    RF02: Verificación y apertura de jornada diaria correspondiente a la fecha actual.
    RF03: Verificación y apertura de caja individual por cajero.
    """
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
    punto_venta = perfil.punto_venta_actual if perfil else None

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
        ventas_recientes = Venta.objects.filter(caja=caja_activa).order_by('-fecha_hora')[:10]
    elif punto_venta:
        ventas_recientes = Venta.objects.filter(punto_venta=punto_venta).order_by('-fecha_hora')[:10]

    context = {
        "jornada_activa": jornada_activa,
        "caja_activa": caja_activa,
        "resumen_caja": resumen_caja,
        "ventas_recientes": ventas_recientes,
        "punto_venta": punto_venta,
        "usuario": request.user,
        "hoy_str": hoy.strftime("%d/%m/%Y"),
        "ahora_hora_str": ahora_dt.strftime("%H:%M"),
        "en_horario": en_horario,
        "horario_oficial": "10:00 a 18:00",
    }
    return render(request, 'ventas/vendedor.html', context)


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
        messages.success(request, f"¡Jornada #{nueva_jornada.id} abierta con éxito! Tu {nueva_caja.nombre} quedó habilitada{fondo_txt}.")
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
            nombre_caja = f"Caja {punto_venta.nombre.split()[0]} - {request.user.first_name or request.user.username}"
            observaciones = request.POST.get('observaciones', '').strip() or (f"Fondo inicial: ${int(monto_apertura):,}" if monto_apertura > 0 else "Sin fondo inicial")

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
        cajas_abiertas = jornada.cajas.filter(estado='ABIERTA')
        forzar = request.POST.get('forzar_cierre') == '1'

        if cajas_abiertas.exists() and not forzar:
            nombres = ", ".join([c.nombre for c in cajas_abiertas])
            messages.error(
                request,
                f"No es posible cerrar la jornada porque aún hay {cajas_abiertas.count()} caja(s) abierta(s): {nombres}. "
                f"Todas las cajas deben cerrarse y arquearse antes del cierre de jornada."
            )
            return redirect('administrador')

        obs = request.POST.get('observaciones_cierre', '').strip()
        if obs:
            jornada.observaciones = (jornada.observaciones or '') + f"\n[Cierre Jornada por {request.user.username}]: {obs}"

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
    """Terminal POS de venta rápida y cobro (requiere jornada del día y caja activa)"""
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
        messages.warning(request, "Debes tener tu jornada del día y caja individual abierta antes de emitir tickets.")
        return redirect('vendedor')

    perfil = getattr(request.user, 'perfil', None)
    punto_venta = perfil.punto_venta_actual if perfil else None

    context = {
        "jornada_activa": jornada_activa,
        "caja_activa": caja_activa,
        "punto_venta": punto_venta,
        "usuario": request.user,
        "hoy_str": hoy.strftime("%d/%m/%Y"),
        "ahora_hora_str": ahora_dt.strftime("%H:%M"),
        "en_horario": en_horario,
        "horario_oficial": "10:00 a 18:00",
    }
    return render(request, 'ventas/vendedor_crear_ticket.html', context)


@requiere_rol(['ADMINISTRADOR'])
def administrador(request):
    """Panel General de Administración y Supervisión de Locales"""
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
                messages.error(request, "Debes ingresar un nombre para el nuevo local gastronómico.")
                return redirect('administrador')

            if PuntoVenta.objects.filter(nombre__iexact=nombre).exists():
                messages.error(request, f"Ya existe un local gastronómico registrado con el nombre '{nombre}'.")
                return redirect('administrador')

            nuevo_local = PuntoVenta.objects.create(
                nombre=nombre,
                tipo=tipo or "Punto de Venta",
                descripcion=descripcion or f"Local gastronómico operativo '{nombre}' en Parque Safari.",
                icono=icono,
                color=color,
                activo=True
            )
            messages.success(request, f"¡Local gastronómico '{nuevo_local.nombre}' creado exitosamente! Ya se encuentra disponible para asignación de colaboradores y auditoría.")
            return redirect('administrador')

        elif accion == 'modificar_local':
            local_id = request.POST.get('local_id')
            pv = get_object_or_404(PuntoVenta, id=local_id)
            nombre = request.POST.get('nombre', '').strip()
            tipo = request.POST.get('tipo', '').strip()
            descripcion = request.POST.get('descripcion', '').strip()
            icono = request.POST.get('icono', '').strip() or pv.icono or 'bi-shop'
            color = request.POST.get('color', '').strip() or pv.color or '#c62828'
            activo_raw = request.POST.get('activo', 'true')
            activo = activo_raw in ['true', 'True', '1', 'on']

            if not nombre:
                messages.error(request, "El nombre del local gastronómico no puede estar en blanco.")
                return redirect('administrador')

            if PuntoVenta.objects.filter(nombre__iexact=nombre).exclude(id=pv.id).exists():
                messages.error(request, f"Ya existe otro local registrado con el nombre '{nombre}'.")
                return redirect('administrador')

            pv.nombre = nombre
            pv.tipo = tipo or "Punto de Venta"
            pv.descripcion = descripcion or pv.descripcion
            pv.icono = icono
            pv.color = color
            pv.activo = activo
            pv.save()

            messages.success(request, f"¡Local gastronómico '{pv.nombre}' actualizado correctamente!")
            return redirect('administrador')

        elif accion == 'eliminar_local':
            local_id = request.POST.get('local_id')
            pv = get_object_or_404(PuntoVenta, id=local_id)
            nombre_local = pv.nombre

            # Desasignar colaboradores de este local
            PerfilEmpleado.objects.filter(punto_venta_actual=pv).update(punto_venta_actual=None)

            # Eliminar mesas que no tengan ventas asociadas
            Mesa.objects.filter(punto_venta=pv, ventas__isnull=True).delete()

            try:
                pv.delete()
                messages.success(request, f"Local gastronómico '{nombre_local}' eliminado exitosamente del sistema.")
            except models.ProtectedError:
                pv.activo = False
                pv.save()
                messages.warning(request, f"El local '{nombre_local}' contiene transacciones y ventas históricas en auditoría. Ha sido desactivado e inactivado del servicio.")

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
    return render(request, 'ventas/administrador.html', context)


@requiere_rol(['ADMINISTRADOR'])
def administrador_local(request, local_id):
    """Página detallada de la jornada y personal de un local específico"""
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

    context = {
        "local": local,
        "locales": locales.values(),
        "alertas_local": alertas_local,
        "hoy_str": hoy.strftime("%d/%m/%Y"),
        "ahora_hora_str": ahora_dt.strftime("%H:%M"),
        "en_horario": en_horario,
        "horario_oficial": "10:00 a 18:00",
    }
    return render(request, 'ventas/administrador_local.html', context)


@requiere_rol(['ADMINISTRADOR'])
def administrador_trabajadores(request):
    """Gestión de Trabajadores (CRUD, búsqueda dinámica, límite de 1 puesto de trabajo y alertas de traslado)"""
    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'crear':
            nombre = request.POST.get('nombre', '').strip()
            apellido = request.POST.get('apellido', '').strip()
            username = request.POST.get('username', '').strip().lower()
            rut = request.POST.get('rut', '').strip()
            rol = request.POST.get('rol', 'CAJERO')
            telefono = request.POST.get('telefono', '').strip()
            local_id = request.POST.get('local_id')

            if not username:
                username = f"{nombre[:1].lower()}{apellido.replace(' ', '').lower()}" if nombre and apellido else f"safari_user_{User.objects.count()+1}"
            
            if User.objects.filter(username=username).exists():
                username = f"{username}_{User.objects.count()+1}"

            password = request.POST.get('password', '').strip()
            if not password:
                messages.error(request, "Debes ingresar una contraseña para el nuevo colaborador.")
                return redirect('administrador_trabajadores')

            if len(password) < 6:
                messages.error(request, "La contraseña debe tener al menos 6 caracteres por razones de seguridad.")
                return redirect('administrador_trabajadores')

            local_obj = PuntoVenta.objects.filter(id=local_id).first() if local_id else None
            user = User.objects.create(
                username=username,
                first_name=nombre,
                last_name=apellido,
                email=f"{username}@parquesafari.cl"
            )
            user.set_password(password)
            user.save()

            perfil = PerfilEmpleado.objects.create(
                usuario=user,
                rol=rol,
                rut=rut,
                telefono=telefono,
                punto_venta_actual=local_obj,
                activo=True
            )
            local_nom = local_obj.nombre if local_obj else "Sin Puesto Asignado"
            messages.success(request, f"¡Colaborador '{nombre} {apellido}' registrado con éxito con puesto único en: {local_nom}!")
            return redirect('administrador_trabajadores')

        elif accion == 'modificar':
            perfil_id = request.POST.get('perfil_id')
            perfil = get_object_or_404(PerfilEmpleado, id=perfil_id)
            user = perfil.usuario

            user.first_name = request.POST.get('nombre', user.first_name).strip()
            user.last_name = request.POST.get('apellido', user.last_name).strip()
            nueva_pass = request.POST.get('password', '').strip()
            if nueva_pass:
                if len(nueva_pass) < 6:
                    messages.error(request, "La nueva contraseña debe tener al menos 6 caracteres por razones de seguridad.")
                    return redirect('administrador_trabajadores')
                user.set_password(nueva_pass)
            user.save()

            perfil.rut = request.POST.get('rut', perfil.rut).strip()
            perfil.rol = request.POST.get('rol', perfil.rol)
            perfil.telefono = request.POST.get('telefono', perfil.telefono).strip()

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
            nom = perfil.usuario.get_full_name() or perfil.usuario.username
            perfil.usuario.delete()
            messages.success(request, f"Colaborador '{nom}' eliminado del sistema.")
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
    return render(request, 'ventas/administrador_trabajadores.html', context)


@requiere_rol(['ADMINISTRADOR'])
def administrador_mesas(request):
    """
    CRUD de Mesas para Administrador (Semana 11):
    Gestión integral de mesas por Punto de Venta: listar, crear, modificar, activar/desactivar y eliminar protegido.
    Garantiza unicidad de identificador por local y protección contra alteración de cuentas abiertas en consumo.
    """
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

            # Regla de Integridad de Cuenta Abierta
            cuenta_abierta = Venta.objects.filter(mesa=mesa_obj, estado='ABIERTA').exists()
            if cuenta_abierta and nuevo_estado == 'INACTIVA':
                messages.warning(request, f"La mesa '{mesa_obj.identificador}' tiene actualmente una comanda o cuenta abierta en consumo. Debe ser cobrada o cerrada antes de marcarla como Inactiva.")
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
    return render(request, 'ventas/administrador_mesas.html', context)


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

            if not nombre:
                messages.error(request, "El nombre del producto es obligatorio.")
                return redirect('administrador_productos')

            try:
                precio_base = max(Decimal('0'), Decimal(precio_base_raw.replace('.', '').replace(',', '.')))
            except Exception:
                messages.error(request, "El precio base debe ser un valor numérico válido.")
                return redirect('administrador_productos')

            cat_obj = get_object_or_404(Categoria, id=categoria_id)

            prod = Producto.objects.create(
                nombre=nombre,
                categoria=cat_obj,
                precio_base=precio_base,
                descripcion=descripcion,
                activo=activo
            )
            if puntos_venta_ids:
                prod.puntos_venta.set(PuntoVenta.objects.filter(id__in=puntos_venta_ids))

            precio_fmt = f"${int(precio_base):,}".replace(',', '.')
            messages.success(request, f"¡Producto '{nombre}' ({precio_fmt}) creado exitosamente en categoría '{cat_obj.nombre}'!")
            return redirect('administrador_productos')

        elif accion == 'modificar':
            producto_id = request.POST.get('producto_id')
            prod = get_object_or_404(Producto, id=producto_id)

            nombre = request.POST.get('nombre', prod.nombre).strip()
            categoria_id = request.POST.get('categoria_id')
            precio_base_raw = request.POST.get('precio_base', str(prod.precio_base)).strip()
            descripcion = request.POST.get('descripcion', prod.descripcion).strip()
            puntos_venta_ids = request.POST.getlist('puntos_venta')
            activo = request.POST.get('activo') in ['on', 'true', 'True', '1']

            if not nombre:
                messages.error(request, "El nombre del producto no puede quedar vacío.")
                return redirect('administrador_productos')

            try:
                precio_base = max(Decimal('0'), Decimal(precio_base_raw.replace('.', '').replace(',', '.')))
            except Exception:
                precio_base = prod.precio_base

            cat_obj = Categoria.objects.filter(id=categoria_id).first() or prod.categoria

            prod.nombre = nombre
            prod.categoria = cat_obj
            prod.precio_base = precio_base
            prod.descripcion = descripcion
            prod.activo = activo
            prod.save()

            if puntos_venta_ids:
                prod.puntos_venta.set(PuntoVenta.objects.filter(id__in=puntos_venta_ids))
            else:
                prod.puntos_venta.clear()

            messages.success(request, f"¡Producto '{nombre}' actualizado correctamente!")
            return redirect('administrador_productos')

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
    return render(request, 'ventas/administrador_productos.html', context)


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
                messages.error(request, "El nombre del menú no puede quedar vacío.")
                return redirect('administrador_menus')

            local_obj = PuntoVenta.objects.filter(id=punto_venta_id).first() or menu_obj.punto_venta
            menu_obj.nombre = nombre
            menu_obj.punto_venta = local_obj
            menu_obj.activo = activo
            menu_obj.save()

            if productos_ids:
                menu_obj.productos.set(Producto.objects.filter(id__in=productos_ids))
            else:
                menu_obj.productos.clear()

            messages.success(request, f"¡Menú '{nombre}' actualizado correctamente!")
            return redirect('administrador_menus')

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
    return render(request, 'ventas/administrador_menus.html', context)



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
    return render(request, 'ventas/administrador_gestion.html', context)


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

    # 5. Eventos de Entrega / Cocina KDS
    entregas_qs = Entrega.objects.select_related('pedido__venta__punto_venta', 'usuario_entrega').all()
    for e in entregas_qs:
        local_e = e.pedido.venta.punto_venta if (e.pedido and e.pedido.venta) else None
        usu_ent = (e.usuario_entrega.get_full_name() or e.usuario_entrega.username) if e.usuario_entrega else "Cocina KDS"
        eventos.append({
            'id_ref': f"ENT-{e.id}",
            'tipo': 'COCINA',
            'subtipo': 'Entrega de Pedido',
            'badge_clase': 'badge-status-success',
            'icono': 'bi-check-circle-fill text-success',
            'titulo': f"Entrega Pedido #{e.pedido.id}",
            'descripcion': f"Comanda despachada al cliente. Observaciones: {e.observaciones or 'Completado'}",
            'usuario': usu_ent,
            'local': local_e.nombre if local_e else 'Cocina Central',
            'local_id': str(local_e.id) if local_e else None,
            'fecha_hora': e.fecha_hora_entrega,
            'monto': None,
            'estado': 'ENTREGADO',
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
    return render(request, 'ventas/administrador_historial.html', context)


@requiere_rol(['ADMINISTRADOR'])
def administrador_dashboard(request):
    """Página de Dashboard Analítico con gráfico mixto barras + línea (hasta 15 meses)"""
    # Histórico de 15 meses (Julio 2025 a Septiembre 2026)
    historico_15_meses = [
        {"mes": "Jul 2025", "ventas": 28500000, "ganancia": 12800000, "margen": 44.9, "crecimiento": 5.2},
        {"mes": "Ago 2025", "ventas": 31200000, "ganancia": 14100000, "margen": 45.1, "crecimiento": 9.4},
        {"mes": "Sep 2025", "ventas": 42800000, "ganancia": 19900000, "margen": 46.4, "crecimiento": 37.1},
        {"mes": "Oct 2025", "ventas": 34100000, "ganancia": 15400000, "margen": 45.1, "crecimiento": -20.3},
        {"mes": "Nov 2025", "ventas": 36500000, "ganancia": 16700000, "margen": 45.7, "crecimiento": 7.0},
        {"mes": "Dic 2025", "ventas": 48900000, "ganancia": 23200000, "margen": 47.4, "crecimiento": 33.9},
        {"mes": "Ene 2026", "ventas": 58400000, "ganancia": 28600000, "margen": 48.9, "crecimiento": 19.4},
        {"mes": "Feb 2026", "ventas": 62100000, "ganancia": 30800000, "margen": 49.5, "crecimiento": 6.3},
        {"mes": "Mar 2026", "ventas": 39800000, "ganancia": 18100000, "margen": 45.4, "crecimiento": -35.9},
        {"mes": "Abr 2026", "ventas": 33400000, "ganancia": 14900000, "margen": 44.6, "crecimiento": -16.0},
        {"mes": "May 2026", "ventas": 30500000, "ganancia": 13600000, "margen": 44.5, "crecimiento": -8.6},
        {"mes": "Jun 2026", "ventas": 27900000, "ganancia": 12200000, "margen": 43.7, "crecimiento": -8.5},
        {"mes": "Jul 2026", "ventas": 33800000, "ganancia": 15600000, "margen": 46.1, "crecimiento": 21.1},
        {"mes": "Ago 2026", "ventas": 36900000, "ganancia": 17200000, "margen": 46.6, "crecimiento": 9.1},
        {"mes": "Sep 2026", "ventas": 49500000, "ganancia": 23800000, "margen": 48.0, "crecimiento": 34.1},
    ]

    context = {
        "historico_15_meses": historico_15_meses,
        "ganancia_mes_actual": 23800000,
        "ventas_mes_actual": 49500000,
        "crecimiento_mes": 34.1,
        "crecimiento_interanual": 19.5, # Sep 2026 vs Sep 2025
    }
    return render(request, 'ventas/administrador_dashboard.html', context)


@requiere_rol(['MESERO'])
def mesero(request):
    """Módulo Dinámico para Meseros: Asignación de Mesas, Pedidos en Vivo y Desglose de Comandas por Zona (Cocina / Barra)"""
    perfil_usuario = getattr(request.user, 'perfil', None)
    locales = PuntoVenta.objects.filter(activo=True).order_by('id')

    # Regla de Negocio: El mesero no puede cambiarse de local libremente; pertenece rígidamente a su local asignado
    if perfil_usuario and perfil_usuario.punto_venta_actual:
        local_actual = perfil_usuario.punto_venta_actual
    else:
        try:
            local_id = int(request.GET.get('local_id', 1))
        except (ValueError, TypeError):
            local_id = 1
        local_actual = PuntoVenta.objects.filter(id=local_id).first() or locales.first()

    # Mesero activo es el colaborador autenticado en sesión
    mesero_activo = perfil_usuario
    meseros = PerfilEmpleado.objects.filter(rol='MESERO', activo=True).select_related('usuario', 'punto_venta_actual')

    # Procesar acciones POST
    if request.method == 'POST':
        accion = request.POST.get('accion')
        mesa_id = request.POST.get('mesa_id')

        if accion == 'liberar_mesa':
            Mesa.objects.filter(id=mesa_id).update(estado='HABILITADA')
            messages.success(request, "Mesa liberada correctamente para nuevos comensales.")
            return redirect(f"/mesero/?local_id={local_actual.id}")

        elif accion == 'ocupar_mesa':
            Mesa.objects.filter(id=mesa_id).update(estado='OCUPADA')
            messages.info(request, "Mesa asignada y marcada como ocupada.")
            return redirect(f"/mesero/?local_id={local_actual.id}")

        elif accion == 'cerrar_cuenta_mesa':
            metodo_pago = request.POST.get('metodo_pago', 'EFECTIVO')

            with transaction.atomic():
                mesa_obj = get_object_or_404(Mesa.objects.select_for_update(), id=mesa_id, punto_venta=local_actual)
                venta_abierta = Venta.objects.select_for_update().filter(
                    mesa=mesa_obj,
                    punto_venta=local_actual,
                    estado='ABIERTA'
                ).first()

                if venta_abierta:
                    from ventas.utils import calcular_redondeo_ley_20956
                    monto_final, ajuste_redondeo = calcular_redondeo_ley_20956(venta_abierta.total, metodo_pago)

                    venta_abierta.total_sin_redondeo = venta_abierta.total
                    venta_abierta.redondeo_ley_20956 = ajuste_redondeo
                    venta_abierta.total = monto_final
                    venta_abierta.estado = 'PAGADA'
                    venta_abierta.metodo_pago = metodo_pago
                    venta_abierta.save()

                    mesa_obj.estado = 'HABILITADA'
                    mesa_obj.save()

                    total_formateado = f"${int(venta_abierta.total):,}".replace(",", ".")
                    txt_redondeo = f" (Ajuste Ley 20.956 en efectivo: {'+' if ajuste_redondeo > 0 else ''}${int(ajuste_redondeo):,} CLP)" if ajuste_redondeo != 0 else ""
                    messages.success(request, f"¡Cuenta de {mesa_obj.identificador} pagada y cerrada exitosamente con {metodo_pago}! Total recaudado: {total_formateado}{txt_redondeo}. La mesa ha quedado libre para nuevos comensales.")
                else:
                    mesa_obj.estado = 'HABILITADA'
                    mesa_obj.save()
                    messages.info(request, f"Mesa {mesa_obj.identificador} liberada.")

            return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")

        elif accion == 'enviar_comanda':
            mesa_obj = Mesa.objects.filter(id=mesa_id).first()

            items_raw = request.POST.get('items_json', '[]')
            try:
                items_lista = json.loads(items_raw)
            except Exception:
                items_lista = []

            # Sanitización de ítems: filtrar datos malformados y asegurar valores no negativos (OWASP)
            items_validos = []
            for it in items_lista:
                try:
                    cant = max(1, int(it.get('cantidad', 1)))
                    precio = max(0, int(it.get('precio', 0)))
                    items_validos.append({
                        'nombre': str(it.get('nombre', 'Producto')).strip()[:120],
                        'precio': precio,
                        'cantidad': cant,
                        'nota': str(it.get('nota', '')).strip()[:200],
                        'destino': 'BARRA' if it.get('destino') == 'BARRA' else 'COCINA'
                    })
                except (ValueError, TypeError):
                    continue

            total_calculado = sum(it['cantidad'] * it['precio'] for it in items_validos)
            if total_calculado <= 0:
                total_calculado = 15000

            hoy = timezone.localdate()
            with transaction.atomic():
                jornada, _ = Jornada.objects.get_or_create(
                    estado='ABIERTA', fecha=hoy,
                    defaults={'usuario_apertura': request.user, 'observaciones': 'Jornada Operativa en Curso'}
                )
                caja = Caja.objects.filter(punto_venta=local_actual, jornada=jornada).first()
                if not caja:
                    caja, _ = Caja.objects.get_or_create(
                        jornada=jornada,
                        cajero=request.user,
                        defaults={
                            'nombre': f"Caja {local_actual.nombre.split()[0]} - {request.user.first_name or request.user.username}",
                            'punto_venta': local_actual,
                            'monto_apertura': 0,
                            'estado': 'ABIERTA',
                            'observaciones': 'Caja de comandas y pedidos de salón'
                        }
                    )

                # Regla de Cuenta Abierta: Si la mesa ya tiene una venta ABIERTA, reutilizarla
                venta_abierta = Venta.objects.select_for_update().filter(
                    mesa=mesa_obj,
                    punto_venta=local_actual,
                    estado='ABIERTA'
                ).first()

                if venta_abierta:
                    venta = venta_abierta
                    venta.total += total_calculado
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
                        total=total_calculado,
                        estado='ABIERTA'
                    )
                    es_ronda_adicional = False

                if mesa_obj:
                    mesa_obj.estado = 'OCUPADA'
                    mesa_obj.save()

                num_ronda = venta.pedidos.count() + 1
                nuevo_pedido = Pedido.objects.create(
                    venta=venta,
                    estado='PENDIENTE',
                    observaciones=f"Ronda #{num_ronda} enviada por mesero {request.user.get_full_name() or request.user.username} para {mesa_obj.identificador if mesa_obj else 'Mesa'}"
                )

                cat_general, _ = Categoria.objects.get_or_create(nombre="Gastronomía Safari")
                for it in items_validos:
                    p_nom = it['nombre']
                    p_precio = it['precio']
                    p_cant = it['cantidad']
                    prod_obj, _ = Producto.objects.get_or_create(
                        nombre=p_nom,
                        defaults={'categoria': cat_general, 'precio_base': p_precio}
                    )
                    DetalleVenta.objects.create(
                        venta=venta,
                        producto=prod_obj,
                        cantidad=p_cant,
                        precio_aplicado=p_precio,
                        subtotal=p_cant * p_precio
                    )
                    DetallePedido.objects.create(
                        pedido=nuevo_pedido,
                        producto=prod_obj,
                        cantidad=p_cant,
                        observaciones=it['nota']
                    )

                tiene_cocina = any(it['destino'] == 'COCINA' for it in items_validos)
                tiene_barra = any(it['destino'] == 'BARRA' for it in items_validos)

                # Fallback de seguridad si ningún ítem trae destino definido
                if not tiene_cocina and not tiene_barra:
                    tiene_cocina = True

                zonas_despachadas = []
                if tiene_cocina:
                    Ticket.objects.create(
                        pedido=nuevo_pedido,
                        codigo=f"COM-COC-{nuevo_pedido.id:04d}",
                        tipo_destino='COCINA',
                        estado='EMITIDO',
                        contenido_impresion=f"Comanda Cocina (Ronda #{num_ronda}) - {mesa_obj.identificador if mesa_obj else 'Mesa'}"
                    )
                    zonas_despachadas.append("Cocina")
                if tiene_barra:
                    Ticket.objects.create(
                        pedido=nuevo_pedido,
                        codigo=f"COM-BAR-{nuevo_pedido.id:04d}",
                        tipo_destino='BARRA',
                        estado='EMITIDO',
                        contenido_impresion=f"Comanda Barra (Ronda #{num_ronda}) - {mesa_obj.identificador if mesa_obj else 'Mesa'}"
                    )
                    zonas_despachadas.append("Barra")

                zonas_txt = " y ".join(zonas_despachadas)

            if es_ronda_adicional:
                total_acumulado_txt = f"${int(venta.total):,}".replace(",", ".")
                messages.success(request, f"¡Ronda #{num_ronda} agregada a la cuenta de {mesa_obj.identificador}! Despachada con éxito a {zonas_txt}. Total acumulado: {total_acumulado_txt}")
            else:
                messages.success(request, f"¡Cuenta abierta para {mesa_obj.identificador}! Comanda #{nuevo_pedido.id:04d} despachada con éxito a {zonas_txt}. Mesa marcada en atención.")

            return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")

    # Mesas del local
    mesas = Mesa.objects.filter(punto_venta=local_actual).order_by('id')
    total_mesas = mesas.count()
    mesas_libres = mesas.filter(estado='HABILITADA').count()
    mesas_ocupadas = mesas.filter(estado='OCUPADA').count()

    # Catálogo de alimentos y bebidas clasificados con destino operativo de comandas
    catalogo_productos = [
        # Comida por cocinar (Destino: COCINA)
        {
            "id": 101,
            "nombre": "Hamburguesa Safari con Papas",
            "categoria": "cocinar",
            "categoria_nombre": "Comida por Cocinar",
            "destino": "COCINA",
            "destino_badge": "Impresora Cocina",
            "icono": "bi-fire",
            "precio": 8900,
            "descripcion": "Hamburguesa casera 200g, cheddar, lechuga, tomate y papas fritas rústicas."
        },
        {
            "id": 102,
            "nombre": "Cazuela de Ave Criolla",
            "categoria": "cocinar",
            "categoria_nombre": "Comida por Cocinar",
            "destino": "COCINA",
            "destino_badge": "Impresora Cocina",
            "icono": "bi-fire",
            "precio": 7500,
            "descripcion": "Plato de fondo tradicional caliente con pollo de campo, choclo y zapallo."
        },
        {
            "id": 103,
            "nombre": "Churrasco Italiano con Papas",
            "categoria": "cocinar",
            "categoria_nombre": "Comida por Cocinar",
            "destino": "COCINA",
            "destino_badge": "Impresora Cocina",
            "icono": "bi-fire",
            "precio": 8500,
            "descripcion": "Láminas de vacuno a la plancha, palta fresca, tomate y mayonesa casera en pan frica."
        },
        {
            "id": 104,
            "nombre": "Porción Papas Fritas Rústicas",
            "categoria": "cocinar",
            "categoria_nombre": "Comida por Cocinar",
            "destino": "COCINA",
            "destino_badge": "Impresora Cocina",
            "icono": "bi-fire",
            "precio": 3500,
            "descripcion": "Papas fritas con piel crujientes doradas al momento con sal de mar."
        },
        {
            "id": 105,
            "nombre": "Menú Infantil Nuggets con Papas",
            "categoria": "cocinar",
            "categoria_nombre": "Comida por Cocinar",
            "destino": "COCINA",
            "destino_badge": "Impresora Cocina",
            "icono": "bi-fire",
            "precio": 5900,
            "descripcion": "6 nuggets de pechuga de pollo crocantes con papas fritas para niños."
        },
        # Comida preparada (Destino: SALÓN / MOSTRADOR)
        {
            "id": 201,
            "nombre": "Sándwich Pan Jamón y Queso",
            "categoria": "preparada",
            "categoria_nombre": "Comida Preparada",
            "destino": "SALON",
            "destino_badge": "Despacho Inmediato",
            "icono": "bi-basket2-fill",
            "precio": 3500,
            "descripcion": "Pan marraqueta fresca con láminas de jamón pierna artesanal y queso chanco de campo."
        },
        {
            "id": 202,
            "nombre": "Sándwich Ave Pimentón",
            "categoria": "preparada",
            "categoria_nombre": "Comida Preparada",
            "destino": "SALON",
            "destino_badge": "Despacho Inmediato",
            "icono": "bi-basket2-fill",
            "precio": 4200,
            "descripcion": "Pasta cremosa de pechuga de ave desmenuzada con pimentón rojo en pan molde rústico."
        },
        {
            "id": 203,
            "nombre": "Empanada de Pino al Horno",
            "categoria": "preparada",
            "categoria_nombre": "Comida Preparada",
            "destino": "SALON",
            "destino_badge": "Mantenedor Caliente",
            "icono": "bi-basket2-fill",
            "precio": 2800,
            "descripcion": "Empanada tradicional horneada, pino de carne picada, aceituna sevillana y huevo duro."
        },
        {
            "id": 204,
            "nombre": "Croissant de Mantequilla",
            "categoria": "preparada",
            "categoria_nombre": "Comida Preparada",
            "destino": "SALON",
            "destino_badge": "Vitrina / Repostería",
            "icono": "bi-basket2-fill",
            "precio": 2400,
            "descripcion": "Medialuna hojaldrada horneada fresca de pastelería de la mañana."
        },
        # Bebidas envasadas (Destino: BARRA)
        {
            "id": 301,
            "nombre": "Coca Cola Original 350ml",
            "categoria": "envasada",
            "categoria_nombre": "Bebidas Envasadas",
            "destino": "BARRA",
            "destino_badge": "Impresora Barra",
            "icono": "bi-cup-straw",
            "precio": 1800,
            "descripcion": "Bebida gaseosa helada en lata 350ml directo de conservadora de frío."
        },
        {
            "id": 302,
            "nombre": "Coca Cola Sin Azúcar 350ml",
            "categoria": "envasada",
            "categoria_nombre": "Bebidas Envasadas",
            "destino": "BARRA",
            "destino_badge": "Impresora Barra",
            "icono": "bi-cup-straw",
            "precio": 1800,
            "descripcion": "Bebida gaseosa sin calorías helada en lata 350ml."
        },
        {
            "id": 303,
            "nombre": "Agua Mineral Sin Gas 500ml",
            "categoria": "envasada",
            "categoria_nombre": "Bebidas Envasadas",
            "destino": "BARRA",
            "destino_badge": "Impresora Barra",
            "icono": "bi-cup-straw",
            "precio": 1500,
            "descripcion": "Agua purificada de manantial natural en botella pet 500ml."
        },
        {
            "id": 304,
            "nombre": "Jugo en Caja Naranja Watt's",
            "categoria": "envasada",
            "categoria_nombre": "Bebidas Envasadas",
            "destino": "BARRA",
            "destino_badge": "Impresora Barra",
            "icono": "bi-cup-straw",
            "precio": 1400,
            "descripcion": "Jugo néctar de naranja individual con bombilla 200ml."
        },
        # Cafetería y jugos naturales (Destino: BARRA)
        {
            "id": 401,
            "nombre": "Café Espresso Grano Barista",
            "categoria": "cafeteria",
            "categoria_nombre": "Cafetería y Jugos",
            "destino": "BARRA",
            "destino_badge": "Impresora Barra",
            "icono": "bi-cup-hot-fill",
            "precio": 2200,
            "descripcion": "Café de grano italiano recién molido, extracción corta con crema avellana dorada."
        },
        {
            "id": 402,
            "nombre": "Capuchino Italiano Vainilla",
            "categoria": "cafeteria",
            "categoria_nombre": "Cafetería y Jugos",
            "destino": "BARRA",
            "destino_badge": "Impresora Barra",
            "icono": "bi-cup-hot-fill",
            "precio": 2900,
            "descripcion": "Espresso de grano con leche texturizada vaporizada y toque de cacao en polvo."
        },
        {
            "id": 403,
            "nombre": "Jugo Natural Frutilla Exprimido",
            "categoria": "cafeteria",
            "categoria_nombre": "Cafetería y Jugos",
            "destino": "BARRA",
            "destino_badge": "Impresora Barra",
            "icono": "bi-cup-hot-fill",
            "precio": 3500,
            "descripcion": "Jugo 100% natural licuado al momento con pulpa de fruta fresca de temporada."
        },
        {
            "id": 404,
            "nombre": "Jugo Natural Naranja Exprimido",
            "categoria": "cafeteria",
            "categoria_nombre": "Cafetería y Jugos",
            "destino": "BARRA",
            "destino_badge": "Impresora Barra",
            "icono": "bi-cup-hot-fill",
            "precio": 3200,
            "descripcion": "Jugo recién exprimido de naranjas dulces seleccionadas."
        }
    ]

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
        rondas_count = va.pedidos.count()
        detalles_list = []
        for d in va.detalles.all():
            detalles_list.append({
                'nombre': d.producto.nombre,
                'cantidad': d.cantidad,
                'precio': int(d.precio_aplicado),
                'subtotal': int(d.subtotal)
            })
        cuentas_abiertas_data[str(va.mesa.id)] = {
            'venta_id': va.id,
            'mesa_id': va.mesa.id,
            'mesa_identificador': va.mesa.identificador,
            'cajero_nombre': va.cajero.get_full_name() or va.cajero.username,
            'total': int(va.total),
            'rondas': rondas_count,
            'hora_apertura': timezone.localtime(va.fecha_hora).strftime('%H:%M'),
            'items': detalles_list
        }

    pedidos_listos = Pedido.objects.filter(
        venta__punto_venta=local_actual,
        estado='LISTO',
        creado_en__date=hoy
    ).select_related('venta__mesa')

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
        "pedidos_listos": pedidos_listos,
        "total_pedidos_listos": pedidos_listos.count(),
        "hoy_str": hoy.strftime("%d/%m/%Y"),
        "ahora_hora_str": ahora_dt.strftime("%H:%M"),
        "en_horario": en_horario,
        "horario_oficial": "10:00 a 18:00",
    }
    return render(request, 'ventas/mesero.html', context)


@requiere_rol(['COCINERO', 'ADMINISTRADOR'])
def cocina(request):
    """
    KDS (Kitchen Display System) - Módulo Operativo de Cocina y Barra.
    Permite al personal de cocina ver los pedidos en cola, gestionar su estado
    de preparación y avisar al personal de salón cuando los platos están listos.
    """
    hoy = timezone.localdate()
    ahora_dt = timezone.localtime()
    ahora_hora = ahora_dt.time()
    en_horario = (datetime.time(10, 0) <= ahora_hora < datetime.time(18, 0))

    perfil = getattr(request.user, 'perfil', None)
    locales = PuntoVenta.objects.filter(activo=True).order_by('id')

    # Determinar el local operativo del cocinero
    if perfil and perfil.punto_venta_actual:
        local_actual = perfil.punto_venta_actual
    else:
        local_id = request.GET.get('local_id')
        if local_id:
            local_actual = get_object_or_404(PuntoVenta, id=local_id)
        else:
            local_actual = locales.first()

    # Filtro por destino/zona: 'TODAS', 'COCINA', 'BARRA'
    zona_filtro = request.GET.get('zona', 'TODAS').upper()

    # Consultar pedidos del día activos
    pedidos_qs = Pedido.objects.filter(
        venta__punto_venta=local_actual,
        creado_en__date=hoy,
        estado__in=['PENDIENTE', 'EN_PREPARACION', 'LISTO']
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
            cat_id = det.producto.categoria_id if det.producto.categoria else 1
            if cat_id in [1, 2]:
                destino_item = 'COCINA'
                tiene_cocina = True
            else:
                destino_item = 'BARRA'
                tiene_barra = True

            items_pedido.append({
                'nombre': det.producto.nombre,
                'cantidad': det.cantidad,
                'observaciones': det.observaciones or '',
                'destino': destino_item,
            })

        if zona_filtro == 'COCINA' and not tiene_cocina:
            continue
        elif zona_filtro == 'BARRA' and not tiene_barra:
            continue

        if ped.estado == 'PENDIENTE':
            total_pendientes += 1
        elif ped.estado == 'EN_PREPARACION':
            total_en_preparacion += 1
        elif ped.estado == 'LISTO':
            total_listos += 1

        pedidos_data.append({
            'id': ped.id,
            'codigo_ticket': f"COM-{ped.id:04d}",
            'estado': ped.estado,
            'estado_display': ped.get_estado_display(),
            'mesa': ped.venta.mesa.identificador if ped.venta.mesa else 'Mostrador / Para Llevar',
            'es_mesa': bool(ped.venta.mesa),
            'cajero': ped.venta.cajero.get_full_name() or ped.venta.cajero.username,
            'hora_creacion': tiempo_creacion.strftime('%H:%M'),
            'minutos_transcurridos': minutos,
            'es_demorado': minutos >= 15,
            'observaciones': ped.observaciones or '',
            'items': items_pedido,
            'tiene_cocina': tiene_cocina,
            'tiene_barra': tiene_barra,
        })

    ultimos_entregados = Pedido.objects.filter(
        venta__punto_venta=local_actual,
        creado_en__date=hoy,
        estado='ENTREGADO'
    ).select_related('venta__mesa').order_by('-actualizado_en')[:5]

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
        'hoy_str': hoy.strftime("%d/%m/%Y"),
        'ahora_hora_str': ahora_dt.strftime("%H:%M"),
        'en_horario': en_horario,
        'horario_oficial': "10:00 a 18:00",
    }
    return render(request, 'ventas/cocina.html', context)


@requiere_rol(['COCINERO', 'ADMINISTRADOR', 'MESERO', 'CAJERO'])
def cambiar_estado_pedido(request):
    """
    Endpoint para cambiar el estado de preparación de un pedido en cocina/barra:
    PENDIENTE -> EN_PREPARACION -> LISTO -> ENTREGADO
    """
    if request.method == 'POST':
        pedido_raw = request.POST.get('pedido_id', '')
        try:
            pedido_id = int(pedido_raw)
        except (ValueError, TypeError):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
                return JsonResponse({'status': 'error', 'mensaje': 'Identificador de pedido inválido'}, status=400)
            messages.error(request, "Identificador de pedido inválido.")
            return redirect('cocina')

        nuevo_estado = request.POST.get('nuevo_estado', '').upper()

        estados_validos = ['PENDIENTE', 'EN_PREPARACION', 'LISTO', 'ENTREGADO', 'CANCELADO']
        if nuevo_estado not in estados_validos:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
                return JsonResponse({'status': 'error', 'mensaje': 'Estado inválido'}, status=400)
            messages.error(request, "Estado de pedido inválido.")
            return redirect('cocina')

        pedido = get_object_or_404(Pedido, id=pedido_id)
        pedido.estado = nuevo_estado
        pedido.save()

        if nuevo_estado == 'ENTREGADO':
            Entrega.objects.create(
                pedido=pedido,
                usuario_entrega=request.user,
                observaciones=f"Entregado al personal de servicio por {request.user.get_full_name() or request.user.username}"
            )
            pedido.tickets.update(estado='FINALIZADO')
        elif nuevo_estado == 'EN_PREPARACION':
            pedido.tickets.filter(estado='EMITIDO').update(estado='EN_PROCESO')

        mensaje_exito = f"Pedido #{pedido.id:04d} actualizado a '{pedido.get_estado_display()}' exitosamente."

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
            return JsonResponse({
                'status': 'ok',
                'pedido_id': pedido.id,
                'nuevo_estado': nuevo_estado,
                'estado_display': pedido.get_estado_display(),
                'mensaje': mensaje_exito
            })

        messages.success(request, mensaje_exito)
        referer = request.META.get('HTTP_REFERER')
        if referer and ('/cocina/' in referer or '/mesero/' in referer):
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
        motivo = request.POST.get('motivo_anulacion', '').strip()
        if not motivo or len(motivo) < 5:
            messages.error(request, "Debe especificar un motivo detallado para la anulación (mínimo 5 caracteres).")
            return redirect(request.META.get('HTTP_REFERER', 'vendedor'))

        rol_actual = obtener_rol_usuario(request.user)
        autorizado_por = None

        if rol_actual == 'ADMINISTRADOR':
            autorizado_por = request.user
        else:
            sup_user = request.POST.get('supervisor_username', '').strip()
            sup_pass = request.POST.get('supervisor_password', '')

            if not sup_user or not sup_pass:
                messages.error(request, "Acción denegada: Se requiere usuario y contraseña de Supervisor/Administrador para autorizar la anulación.")
                return redirect(request.META.get('HTTP_REFERER', 'vendedor'))

            supervisor = authenticate(request, username=sup_user, password=sup_pass)
            if not supervisor or obtener_rol_usuario(supervisor) != 'ADMINISTRADOR':
                messages.error(request, "Acción denegada: Credenciales de Supervisor inválidas o usuario sin privilegios de Administrador.")
                return redirect(request.META.get('HTTP_REFERER', 'vendedor'))

            autorizado_por = supervisor

        with transaction.atomic():
            venta = Venta.objects.select_for_update().filter(id=venta_id).first()
            if not venta:
                messages.error(request, f"La venta #{venta_id} no fue encontrada en el sistema.")
                return redirect(request.META.get('HTTP_REFERER', 'vendedor'))

            if venta.estado == 'ANULADA':
                messages.warning(request, f"La venta #{venta.id} ya se encontraba anulada.")
                return redirect(request.META.get('HTTP_REFERER', 'vendedor'))

            monto_previo = venta.total
            venta.estado = 'ANULADA'
            venta.save()

            # Si estaba ligada a una mesa, liberar mesa si no quedan otras ventas abiertas
            if venta.mesa:
                otras_activas = Venta.objects.filter(mesa=venta.mesa, estado='ABIERTA').exclude(id=venta.id).exists()
                if not otras_activas:
                    mesa = Mesa.objects.select_for_update().get(id=venta.mesa.id)
                    mesa.estado = 'HABILITADA'
                    mesa.save()

            # Trazabilidad en AlertaTraslado / Bitácora
            audit_msg = (
                f"[ANULACIÓN #{venta.id}] ${int(monto_previo):,} CLP. "
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
            return redirect(request.META.get('HTTP_REFERER', 'vendedor'))

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
        except Exception as e:
            messages.error(request, f"Error al generar la copia de seguridad: {str(e)}")
        return redirect('administrador')
    return redirect('administrador')
