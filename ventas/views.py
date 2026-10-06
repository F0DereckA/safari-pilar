import json
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404, Http404
from django.http import JsonResponse
from django.contrib import messages
from django.db import models, transaction
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from .models import PuntoVenta, PerfilEmpleado, AlertaTraslado, Mesa, Jornada, Caja, Venta, DetalleVenta, Pedido, DetallePedido, Ticket, Categoria, Producto


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

    for pv in locales_bd:
        demo = mock_metricas.get(pv.id, {})

        # Consultar ventas reales asociadas en la BD para este punto de venta
        real_ventas = Venta.objects.filter(punto_venta=pv).select_related('cajero', 'cajero__perfil', 'mesa').prefetch_related('detalles__producto').order_by('-fecha_hora')[:20]
        real_tickets = []
        suma_ventas_reales = 0

        for rv in real_ventas:
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

        base_tickets = demo.get("tickets_recientes", [])
        for bt in base_tickets:
            if "items_json" not in bt:
                bt["items_json"] = json.dumps(bt.get("items", []))
            if "creador_rol" not in bt:
                bt["creador_rol"] = "Cajero"

        tickets_combinados = real_tickets + base_tickets
        total_ventas_calc = demo.get("total_ventas", 0) + suma_ventas_reales
        tickets_emitidos_calc = demo.get("tickets_emitidos", 0) + len(real_tickets)
        ticket_prom_calc = round(total_ventas_calc / tickets_emitidos_calc) if tickets_emitidos_calc else 0

        locales[pv.id] = {
            "id": pv.id,
            "nombre": pv.nombre,
            "tipo": pv.tipo or demo.get("tipo", "Punto de Venta"),
            "descripcion": pv.descripcion or demo.get("descripcion", "Punto gastronómico operativo de Parque Safari."),
            "icono": getattr(pv, 'icono', None) or demo.get("icono", "bi-shop"),
            "color": getattr(pv, 'color', None) or demo.get("color", "#c62828"),
            "estado": "En Servicio" if pv.activo else "Inactivo",
            "turno": demo.get("turno", "Turno General (09:00 - 19:00)"),
            "total_ventas": total_ventas_calc,
            "tickets_emitidos": tickets_emitidos_calc,
            "ticket_promedio": ticket_prom_calc,
            "caja_apertura": demo.get("caja_apertura", 0),
            "caja_efectivo": demo.get("caja_efectivo", 0),
            "caja_tarjeta": demo.get("caja_tarjeta", 0),
            "saldo_actual": demo.get("saldo_actual", 0) + suma_ventas_reales,
            "personal": [],
            "ventas_categoria": demo.get("ventas_categoria", []),
            "metodos_pago": demo.get("metodos_pago", []),
            "tickets_recientes": tickets_combinados
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
                return redirect('index')

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def login_view(request):
    """RF01: Inicio de sesión real con django.contrib.auth y redirección automática por rol"""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Validar autenticación
        user = authenticate(request, username=username, password=password)
        if user is not None:
            perfil = getattr(user, 'perfil', None)
            if not user.is_active or (perfil and not perfil.activo):
                messages.error(request, "Tu cuenta de colaborador se encuentra inactiva. Contacta al Administrador.")
                return redirect('index')

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

            messages.error(request, "Credenciales incorrectas. Verifica tu nombre de usuario y contraseña.")
            return redirect('index')

    return redirect('index')


def logout_view(request):
    """Cierre de sesión seguro y retorno al portal inicial"""
    logout(request)
    messages.info(request, "Has cerrado tu sesión de forma segura. ¡Hasta pronto!")
    return redirect('index')


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

    context = {
        "jornada_activa": jornada_activa,
        "caja_activa": caja_activa,
        "punto_venta": punto_venta,
        "usuario": request.user,
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
            jornada_activa = Jornada.objects.filter(estado='ABIERTA', fecha=hoy).first()
            if not jornada_activa:
                messages.error(request, "No existe una jornada abierta para el día de hoy. Debe realizarse la apertura de jornada primero.")
                return redirect('vendedor')

            # Reutilizar caja si ya existe una abierta para este cajero en esta jornada
            caja_existente = Caja.objects.filter(
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


@requiere_rol(['CAJERO'])
def crear_ticket(request):
    """Terminal POS de venta rápida y cobro (requiere jornada del día y caja activa)"""
    hoy = timezone.localdate()
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

    context = {
        "locales": locales.values(),
        "total_ventas": total_ventas,
        "total_tickets": total_tickets,
        "total_personal": total_personal,
        "ticket_promedio_global": ticket_promedio_global,
        "personal_completo": personal_completo,
        "alertas_traslado": alertas_traslado,
        "total_alertas_no_leidas": total_alertas_no_leidas,
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
        "total_alertas_no_leidas": total_alertas_no_leidas,
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
    local_defecto = perfil_usuario.punto_venta_actual_id if (perfil_usuario and perfil_usuario.punto_venta_actual) else 1

    # Obtener el local seleccionado (por defecto el asignado al mesero o Local 1)
    try:
        local_id = int(request.GET.get('local_id', local_defecto))
    except (ValueError, TypeError):
        local_id = local_defecto

    locales = PuntoVenta.objects.filter(activo=True).order_by('id')
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
            mesa_obj = get_object_or_404(Mesa, id=mesa_id, punto_venta=local_actual)
            metodo_pago = request.POST.get('metodo_pago', 'EFECTIVO')

            with transaction.atomic():
                venta_abierta = Venta.objects.filter(
                    mesa=mesa_obj,
                    punto_venta=local_actual,
                    estado='ABIERTA'
                ).first()

                if venta_abierta:
                    venta_abierta.estado = 'PAGADA'
                    venta_abierta.metodo_pago = metodo_pago
                    venta_abierta.save()

                    mesa_obj.estado = 'HABILITADA'
                    mesa_obj.save()

                    total_formateado = f"${int(venta_abierta.total):,}".replace(",", ".")
                    messages.success(request, f"¡Cuenta de {mesa_obj.identificador} pagada y cerrada exitosamente con {metodo_pago}! Total recaudado: {total_formateado}. La mesa ha quedado libre para nuevos comensales.")
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

            total_calculado = sum(int(it.get('cantidad', 1)) * int(it.get('precio', 0)) for it in items_lista)
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
                venta_abierta = Venta.objects.filter(
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
                    estado='EN_PREPARACION',
                    observaciones=f"Ronda #{num_ronda} enviada por mesero {request.user.get_full_name() or request.user.username} para {mesa_obj.identificador if mesa_obj else 'Mesa'}"
                )

                cat_general, _ = Categoria.objects.get_or_create(nombre="Gastronomía Safari")
                for it in items_lista:
                    p_nom = it.get('nombre', 'Producto')
                    p_precio = int(it.get('precio', 0))
                    p_cant = int(it.get('cantidad', 1))
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
                        observaciones=it.get('nota', '')
                    )

                tiene_cocina = any(it.get('destino') == 'COCINA' for it in items_lista)
                tiene_barra = any(it.get('destino') == 'BARRA' for it in items_lista)

                if tiene_cocina or not tiene_barra:
                    Ticket.objects.create(
                        pedido=nuevo_pedido,
                        codigo=f"COM-COC-{nuevo_pedido.id:04d}",
                        tipo_destino='COCINA',
                        estado='EN_PROCESO',
                        contenido_impresion=f"Comanda Cocina (Ronda #{num_ronda}) - {mesa_obj.identificador if mesa_obj else 'Mesa'}"
                    )
                if tiene_barra:
                    Ticket.objects.create(
                        pedido=nuevo_pedido,
                        codigo=f"COM-BAR-{nuevo_pedido.id:04d}",
                        tipo_destino='BARRA',
                        estado='EN_PROCESO',
                        contenido_impresion=f"Comanda Barra (Ronda #{num_ronda}) - {mesa_obj.identificador if mesa_obj else 'Mesa'}"
                    )

            if es_ronda_adicional:
                total_acumulado_txt = f"${int(venta.total):,}".replace(",", ".")
                messages.success(request, f"¡Ronda #{num_ronda} agregada a la cuenta de {mesa_obj.identificador}! Tickets despachados con éxito a Cocina y Barra. Total acumulado: {total_acumulado_txt}")
            else:
                messages.success(request, f"¡Cuenta abierta para {mesa_obj.identificador}! Comanda #{nuevo_pedido.id:04d} despachada con éxito a Cocina y Barra. Mesa marcada en atención.")

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

    # Cuentas abiertas activas por mesa en este punto de venta
    ventas_abiertas = Venta.objects.filter(
        punto_venta=local_actual,
        estado='ABIERTA',
        mesa__isnull=False
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
    }
    return render(request, 'ventas/mesero.html', context)



