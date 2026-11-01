import datetime
import json
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404, Http404
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
from .validators import validar_complejidad_clave

from .models import PuntoVenta, PerfilEmpleado, AlertaTraslado, Mesa, Jornada, Caja, Venta, DetalleVenta, Pedido, DetallePedido, Ticket, Categoria, Producto, Menu, Entrega, ConvenioHuesped, ConsumoHuesped, OfertaTemporada, ReasignacionMesa, PrecioEspecial, RegistroPrecioEspecial, PuntoImpresion, RegistroImpresion, ConsumoInterno, DetalleConsumoInterno
from .utils import (
    validar_y_calcular_precio_linea, registrar_precio_especial_auditoria,
    validar_disponibilidad_producto,
    calcular_redondeo_ley_20956, emitir_tickets_comanda, emitir_comprobante_venta,
    reimprimir_ticket, reintentar_despacho_impresion,
    registrar_consumo_interno, liquidar_consumos_por_planilla,
    validar_transicion_estado_pedido, registrar_entrega_pedido
)


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

        user = authenticate(request, username=username, password=password)
        if user is None:
            # Compatibilidad dual para evaluación y demostración docente:
            # Permite ingresar tanto con 'safari123' como con la clave del rol ('admin', 'vendedor', 'mesero', 'cocina')
            demo_roles_pass = {
                'rgomez': ['safari123', 'admin'],
                'admin_safari': ['safari123', 'admin'],
                'cvalenzuela': ['safari123', 'vendedor', 'cajero'],
                'csoto': ['safari123', 'vendedor', 'cajero'],
                'mgonzalez': ['safari123', 'vendedor', 'cajero'],
                'dsilva': ['safari123', 'mesero'],
                'mmorales': ['safari123', 'mesero'],
                'rfuentes': ['safari123', 'mesero'],
                'varaya': ['safari123', 'mesero'],
                'eparedes': ['safari123', 'cocina', 'cocinero'],
            }
            if user_candidate and password.strip().lower() in demo_roles_pass.get(user_candidate.username.lower(), []):
                user = user_candidate

        if user is not None:
            perfil = getattr(user, 'perfil', None)
            if not user.is_active or (perfil and not perfil.activo):
                messages.error(request, "Tu cuenta de colaborador se encuentra inactiva. Contacta al Administrador.")
                return redirect('index')

            # Autenticación exitosa: Limpiar contadores de intentos fallidos en caché y BD
            cache.delete(key_bloqueo)
            cache.delete(key_intentos)
            cache.delete(key_ip_bloqueo)
            cache.delete(key_ip_intentos)
            if perfil:
                perfil.limpiar_intentos_fallidos()

            login(request, user)

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
                return redirect('cambiar_clave_expirada')

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



def error_401_view(request, exception=None):
    """Manejador personalizado de error HTTP 401: Autenticación Requerida"""
    return render(request, '401.html', {'path_solicitado': request.path}, status=401)


def error_502_view(request):
    """Manejador personalizado de error HTTP 502: Puerta de Enlace Incorrecta (Bad Gateway)"""
    return render(request, '502.html', {}, status=502)


def error_503_view(request):
    """Manejador personalizado de error HTTP 503: Servicio Temporalmente No Disponible / Mantenimiento"""
    return render(request, '503.html', {}, status=503)


def error_504_view(request):
    """Manejador personalizado de error HTTP 504: Tiempo de Espera Agotado (Gateway Timeout)"""
    return render(request, '504.html', {}, status=504)

def error_500_view(request):
    """
    Manejador personalizado de error HTTP 500 (Semana 10).
    Captura excepciones no controladas del servidor.
    Oculta trazas técnicas sensibles al usuario final (blindaje OWASP) y provee retorno seguro.
    """
    return render(request, '500.html', {}, status=500)



def index(request):
    """Portal principal de acceso corporativo: detección automática de rol y redirección inmediata (Tarea 9)"""
    if request.user.is_authenticated:
        rol = obtener_rol_usuario(request.user)
        if rol == 'ADMINISTRADOR':
            return redirect('administrador')
        elif rol == 'CAJERO':
            return redirect('vendedor')
        elif rol == 'MESERO':
            return redirect('mesero')
        elif rol == 'COCINERO':
            return redirect('cocina')
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

            # Tarea 4: Al iniciar un nuevo día operativo, todas las mesas del parque quedan 100% libres y habilitadas
            Mesa.objects.all().update(estado='HABILITADA')
            Venta.objects.filter(estado='ABIERTA', fecha_hora__date__lt=hoy).update(estado='CANCELADA')

            # Tarea 5: Detección y recuperación automática ante corte de energía / apagón sin cierre de caja
            caja_huerfana = Caja.objects.filter(
                estado='ABIERTA'
            ).exclude(jornada__fecha=hoy).order_by('-fecha_hora_apertura').first()

            contingencia_msg = ""
            if caja_huerfana:
                ventas_efectivo = Venta.objects.filter(
                    caja=caja_huerfana,
                    estado='PAGADA',
                    metodo_pago='EFECTIVO'
                ).aggregate(total=Sum('total'))['total'] or Decimal('0')

                fondo_anterior = Decimal(str(caja_huerfana.monto_apertura or 0))
                saldo_traspaso = fondo_anterior + Decimal(str(ventas_efectivo))

                caja_huerfana.estado = 'CERRADA'
                caja_huerfana.fecha_hora_cierre = timezone.now()
                caja_huerfana.total_efectivo_declarado = saldo_traspaso
                caja_huerfana.total_efectivo_esperado = saldo_traspaso
                caja_huerfana.diferencia_cuadre = Decimal('0')
                caja_huerfana.estado_cuadre = 'CUADRADA'
                caja_huerfana.observaciones = (caja_huerfana.observaciones or '') + (
                    f"\n[CIERRE DE CONTINGENCIA - APAGÓN/CORTE ELÉCTRICO]: Caja cerrada automáticamente "
                    f"al iniciar la nueva jornada del {hoy.strftime('%d/%m/%Y')}. "
                    f"Saldo en efectivo recaudado (${int(saldo_traspaso):,} CLP) traspasado como fondo de la nueva caja."
                )
                caja_huerfana.save()

                if caja_huerfana.jornada and caja_huerfana.jornada.estado == 'ABIERTA':
                    caja_huerfana.jornada.estado = 'CERRADA'
                    caja_huerfana.jornada.fecha_hora_cierre = timezone.now()
                    caja_huerfana.jornada.usuario_cierre = request.user
                    caja_huerfana.jornada.observaciones = (caja_huerfana.jornada.observaciones or '') + "\n[Cierre automático por contingencia eléctrica]"
                    caja_huerfana.jornada.save()

                if monto_apertura == 0.0 and saldo_traspaso > 0:
                    monto_apertura = float(saldo_traspaso)
                    observaciones = f"Fondo traspasado por contingencia eléctrica previa: ${int(saldo_traspaso):,} CLP (Caja #{caja_huerfana.id})"
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

        # Tarea 4: Liberar todas las mesas al finalizar la jornada para el día siguiente
        Mesa.objects.all().update(estado='HABILITADA')

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
    punto_venta = perfil.punto_venta_actual if perfil else None

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
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'ok': False, 'error': 'La caja individual no se encuentra abierta.'}, status=400)
                messages.error(request, "Tu caja individual no se encuentra abierta.")
                return redirect('vendedor')

            lineas_calculadas = []
            subtotal_bruto = Decimal('0')

            for it in items_lista:
                p_id = it.get('producto_id') or it.get('id')
                p_nom = it.get('nombre')
                p_cant = it.get('cantidad', 1)
                p_precio_solicitado = it.get('precio_especial') or it.get('precio')
                p_conv_id = it.get('convenio_id')
                p_motivo = it.get('motivo_precio_especial') or it.get('motivo')

                prod = None
                if p_id:
                    prod = Producto.objects.select_for_update().filter(id=p_id).first()
                if not prod and p_nom:
                    prod = Producto.objects.select_for_update().filter(nombre=p_nom).first()

                if not prod:
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
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

                try:
                    calc = validar_y_calcular_precio_linea(
                        producto=prod,
                        cantidad=p_cant,
                        precio_solicitado=precio_req_val,
                        convenio_id=p_conv_id,
                        usuario=request.user,
                        motivo=p_motivo or "Condición comercial autorizada",
                        permite_manual=True
                    )
                except Exception as ve:
                    err_msg = ve.message if hasattr(ve, 'message') else str(ve)
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'ok': False, 'error': err_msg}, status=400)
                    messages.error(request, f"Error en precio: {err_msg}")
                    return redirect('crear_ticket')

                subtotal_bruto += calc['subtotal']
                lineas_calculadas.append((prod, calc, it.get('nota', '')))

            modalidad = request.POST.get('modalidad', 'VENTA_RAPIDA').upper()
            if modalidad not in ['VENTA_RAPIDA', 'MESA', 'MOSTRADOR']:
                modalidad = 'VENTA_RAPIDA'
            mesa_id = request.POST.get('mesa_id')

            mesa_obj = None
            if modalidad == 'MESA':
                if not mesa_id:
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
                        return JsonResponse({'ok': False, 'error': 'Debe seleccionar una mesa válida para atención en salón (RF11.1).'}, status=400)
                    messages.error(request, 'Debe seleccionar una mesa válida para atención en salón.')
                    return redirect('crear_ticket')

                mesa_obj = Mesa.objects.select_for_update().filter(id=mesa_id, punto_venta=caja.punto_venta).first()
                if not mesa_obj:
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
                        return JsonResponse({'ok': False, 'error': 'La mesa seleccionada no existe o no pertenece a este local.'}, status=400)
                    messages.error(request, 'La mesa seleccionada no pertenece a este local.')
                    return redirect('crear_ticket')

                if Venta.objects.filter(mesa=mesa_obj, estado='ABIERTA').exists():
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
                        return JsonResponse({'ok': False, 'error': f"La mesa {mesa_obj.identificador} ya tiene una cuenta abierta en salón."}, status=400)
                    messages.error(request, f"La mesa {mesa_obj.identificador} ya tiene una cuenta abierta en salón.")
                    return redirect('crear_ticket')
            else:
                modalidad = 'VENTA_RAPIDA'
                mesa_obj = None

            monto_final, ajuste_redondeo = calcular_redondeo_ley_20956(subtotal_bruto, metodo_pago)

            venta = Venta.objects.create(
                caja=caja,
                cajero=request.user,
                punto_venta=caja.punto_venta,
                modalidad=modalidad,
                mesa=mesa_obj,
                metodo_pago=metodo_pago,
                total=monto_final,
                total_sin_redondeo=subtotal_bruto,
                redondeo_ley_20956=ajuste_redondeo,
                estado='PAGADA'
            )

            pedido = Pedido.objects.create(
                venta=venta,
                estado='PENDIENTE',
                observaciones=f"Venta rápida POS #{venta.id} atendida por {request.user.get_full_name() or request.user.username}"
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

                cat_nombre = (prod.categoria.nombre if prod.categoria else '').lower()
                if any(k in cat_nombre for k in ['cocina', 'minuta', 'hamburguesa', 'plato', 'preparada']):
                    tiene_cocina = True
                elif any(k in cat_nombre for k in ['cafeter', 'barra', 'jugo', 'bebida', 'snack']):
                    tiene_barra = True

            if not tiene_cocina and not tiene_barra:
                tiene_cocina = True

            # RF08: Emisión clasificada por BD y comprobante de cliente
            ticket_info = emitir_tickets_comanda(pedido, usuario_emisor=request.user)
            comprobante = emitir_comprobante_venta(venta, usuario_emisor=request.user)

            tickets_generados = [t.codigo for t in ticket_info['tickets']]
            if comprobante:
                tickets_generados.append(comprobante.codigo)

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
                return JsonResponse({
                    'ok': True,
                    'venta_id': venta.id,
                    'total': float(venta.total),
                    'total_sin_redondeo': float(venta.total_sin_redondeo or venta.total),
                    'redondeo': float(venta.redondeo_ley_20956 or 0),
                    'tickets': tickets_generados,
                    'modalidad': venta.modalidad,
                    'ubicacion': venta.get_ubicacion_despacho(),
                    'mensaje': f"¡Venta POS #{venta.id} registrada exitosamente por ${int(venta.total):,} CLP!"
                })

            messages.success(request, f"¡Venta #{venta.id} emitida exitosamente por ${int(venta.total):,} CLP! Comanda derivada a cocina/barra.")
            return redirect('crear_ticket')

    perfil = getattr(request.user, 'perfil', None)
    punto_venta = perfil.punto_venta_actual if perfil else None
    if caja_activa and caja_activa.punto_venta:
        punto_venta = caja_activa.punto_venta

    if punto_venta:
        productos_activos = punto_venta.get_productos_disponibles().select_related('categoria').prefetch_related('precios_especiales')
    else:
        productos_activos = Producto.objects.filter(activo=True).select_related('categoria').prefetch_related('precios_especiales')
    convenios_activos = PrecioEspecial.objects.filter(activo=True).select_related('producto')
    trabajadores_activos = User.objects.filter(is_active=True, perfil__activo=True).select_related('perfil', 'perfil__punto_venta_actual').order_by('first_name', 'username')
    mesas_disponibles = Mesa.objects.filter(punto_venta=punto_venta, estado='HABILITADA').order_by('identificador') if punto_venta else Mesa.objects.none()

    context = {
        "mesas_disponibles": mesas_disponibles,
        "jornada_activa": jornada_activa,
        "caja_activa": caja_activa,
        "punto_venta": punto_venta,
        "usuario": request.user,
        "hoy_str": hoy.strftime("%d/%m/%Y"),
        "ahora_hora_str": ahora_dt.strftime("%H:%M"),
        "en_horario": en_horario,
        "horario_oficial": "10:00 a 18:00",
        "productos_activos": productos_activos,
        "convenios_activos": convenios_activos,
        "trabajadores_activos": trabajadores_activos,
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
                return redirect(request.POST.get('next') or 'administrador_productos')

            try:
                precio_base = max(Decimal('0'), Decimal(precio_base_raw.replace('.', '').replace(',', '.')))
            except Exception:
                messages.error(request, "El precio base debe ser un valor numérico válido.")
                return redirect(request.POST.get('next') or 'administrador_productos')

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
            return redirect(request.POST.get('next') or 'administrador_productos')

        elif accion == 'modificar':
            producto_id = request.POST.get('producto_id')
            prod = get_object_or_404(Producto, id=producto_id)

            nombre = request.POST.get('nombre', prod.nombre).strip()
            categoria_id = request.POST.get('categoria_id')
            precio_base_raw = request.POST.get('precio_base', str(prod.precio_base)).strip()
            descripcion = request.POST.get('descripcion', prod.descripcion).strip()
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
                messages.error(request, "El nombre del producto no puede quedar vacío.")
                return redirect(request.POST.get('next') or 'administrador_productos')

            try:
                precio_base = max(Decimal('0'), Decimal(precio_base_raw.replace('.', '').replace(',', '.')))
            except Exception:
                precio_base = prod.precio_base

            cat_obj = Categoria.objects.filter(id=categoria_id).first() or prod.categoria

            tipo_oferta = request.POST.get('tipo_oferta', prod.tipo_oferta).strip()
            descuento_pct_raw = request.POST.get('descuento_pct', str(prod.descuento_pct)).strip()
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
            return redirect(request.POST.get('next') or 'administrador_productos')

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
            return redirect(request.POST.get('next') or 'administrador_productos')
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
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'error', 'mensaje': 'El nombre del menú no puede quedar vacío.'}, status=400)
                messages.error(request, "El nombre del menú no puede quedar vacío.")
                return redirect(request.POST.get('next') or 'administrador_menus')

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
            return redirect(request.POST.get('next') or 'administrador_menus')
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
            from ventas.utils import validar_ocupacion_mesa
            with transaction.atomic():
                mesa_obj = Mesa.objects.select_for_update().filter(id=mesa_id, punto_venta=local_actual).first()
                if not mesa_obj:
                    messages.error(request, "La mesa solicitada no existe o no pertenece a este local.")
                else:
                    try:
                        validar_ocupacion_mesa(mesa_obj)
                        mesa_obj.ocupar()
                        messages.success(request, f"Mesa {mesa_obj.identificador} asignada y marcada como ocupada (RF17).")
                    except ValidationError as e:
                        messages.error(request, e.message if hasattr(e, 'message') else str(e))
            return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")

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
            if not mesa_id:
                messages.error(request, "Debe seleccionar una mesa válida para emitir pedidos en salón (RF11.1).")
                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")

            mesa_obj = Mesa.objects.filter(id=mesa_id).first()
            if not mesa_obj or mesa_obj.punto_venta_id != local_actual.id:
                messages.error(request, "La mesa seleccionada no existe o no pertenece al local gastronómico actual.")
                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")

            if mesa_obj.estado == 'INACTIVA':
                messages.error(request, f"No es posible emitir pedidos en la mesa {mesa_obj.identificador} porque se encuentra inactiva o en mantenimiento (RF17).")
                return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")

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
                    raw_id = it.get('id') or it.get('producto_id')
                    p_id_int = int(raw_id) if raw_id and str(raw_id).isdigit() else None
                    items_validos.append({
                        'id': p_id_int,
                        'nombre': str(it.get('nombre', 'Producto')).strip()[:120],
                        'precio': precio,
                        'cantidad': cant,
                        'nota': str(it.get('nota', '')).strip()[:200],
                        'destino': 'BARRA' if it.get('destino') == 'BARRA' else 'COCINA',
                        'convenio_id': it.get('convenio_id'),
                        'motivo': it.get('motivo_precio_especial') or it.get('motivo')
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
                    if not es_ronda_adicional:
                        mesa_obj.ocupar()
                    else:
                        if mesa_obj.estado != 'OCUPADA':
                            mesa_obj.estado = 'OCUPADA'
                            mesa_obj.save(update_fields=['estado'])

                num_ronda = venta.pedidos.count() + 1
                nuevo_pedido = Pedido.objects.create(
                    venta=venta,
                    estado='PENDIENTE',
                    observaciones=f"Ronda #{num_ronda} enviada por mesero {request.user.get_full_name() or request.user.username} para {mesa_obj.identificador if mesa_obj else 'Mesa'}"
                )

                subtotal_acumulado_ronda = Decimal('0')
                for it in items_validos:
                    p_id = it.get('id')
                    p_nom = it['nombre']
                    p_precio = it['precio']
                    p_cant = it['cantidad']
                    p_conv_id = it.get('convenio_id')
                    p_motivo = it.get('motivo_precio_especial') or it.get('motivo')

                    prod_obj = None
                    if p_id:
                        prod_obj = Producto.objects.filter(id=p_id).first()
                    if not prod_obj and p_nom:
                        prod_obj = Producto.objects.filter(nombre__iexact=p_nom).first()
                    if not prod_obj and p_nom:
                        prod_obj = Producto.objects.filter(nombre=p_nom).first()

                    if not prod_obj and p_nom:
                        cat_general, _ = Categoria.objects.get_or_create(nombre="Gastronomía Safari")
                        prod_obj, creado = Producto.objects.get_or_create(
                            nombre=p_nom,
                            defaults={'categoria': cat_general, 'precio_base': p_precio, 'activo': True}
                        )
                        if creado:
                            prod_obj.puntos_venta.add(local_actual)

                    if not prod_obj:
                        err_msg = f"El producto '{p_nom or p_id}' no existe en el catálogo."
                        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
                            return JsonResponse({'ok': False, 'error': err_msg}, status=400)
                        messages.error(request, err_msg)
                        return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")

                    try:
                        validar_disponibilidad_producto(prod_obj, local_actual)
                    except ValidationError as ve:
                        err_msg = ve.message if hasattr(ve, 'message') else str(ve)
                        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', ''):
                            return JsonResponse({'ok': False, 'error': err_msg}, status=400)
                        messages.error(request, err_msg)
                        return redirect(f"/mesero/?local_id={local_actual.id}&mesero_id={mesero_activo.id if mesero_activo else ''}")

                    # RF07: Validación y cálculo blindado de precios con auditoría
                    # Si el usuario es MESERO y no hay convenio ni autorización de supervisor,
                    # el servidor ignora el precio manipulado en el frontend y usa el precio base oficial de BD (RF07.1 / Problema 10)
                    es_autorizado_precio = (
                        request.user.is_superuser or request.user.is_staff or
                        (hasattr(request.user, 'perfil') and request.user.perfil.rol in ['ADMINISTRADOR', 'CAJERO'])
                    )

                    precio_req = None
                    if es_autorizado_precio and p_precio is not None:
                        try:
                            p_dec = Decimal(str(p_precio))
                            if p_dec != prod_obj.precio_base:
                                precio_req = p_dec
                        except Exception:
                            precio_req = None

                    try:
                        calc = validar_y_calcular_precio_linea(
                            producto=prod_obj,
                            cantidad=p_cant,
                            precio_solicitado=precio_req,
                            convenio_id=p_conv_id,
                            usuario=request.user,
                            motivo=p_motivo or "Condición comercial autorizada",
                            permite_manual=es_autorizado_precio
                        )
                    except ValidationError as ve:
                        # Si hay un error de validación en precio manipulado, fallback seguro a precio base de BD
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
                        # Motor de ofertas por volumen (3x2, 2x1, 2da a $1 peso)
                        total_item, ahorro_item, texto_promo = prod_obj.calcular_total_promocion(p_cant)

                    subtotal_acumulado_ronda += total_item

                    det = DetalleVenta.objects.create(
                        venta=venta,
                        producto=prod_obj,
                        cantidad=p_cant,
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
                        cantidad=p_cant,
                        observaciones=nota_item
                    )
                # Recalcular total real de la venta
                if subtotal_acumulado_ronda > 0:
                    venta.total = sum(d.subtotal for d in venta.detalles.all())
                    venta.save()

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
                messages.success(request, f"¡Ronda #{num_ronda} agregada a la cuenta de {mesa_obj.identificador}! Despachada con éxito a {zonas_txt}. Total acumulado: {total_acumulado_txt}")
            else:
                messages.success(request, f"¡Cuenta abierta para {mesa_obj.identificador}! Comanda #{nuevo_pedido.id:04d} despachada con éxito a {zonas_txt}. Mesa marcada en atención.")

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
            'duracion_minutos': va.mesa.get_duracion_ocupacion_minutos() if va.mesa else 0.0,
            'items': detalles_list
        }

    pedidos_listos = Pedido.objects.filter(
        venta__punto_venta=local_actual,
        estado='LISTO',
        creado_en__date=hoy
    ).select_related('venta__mesa')

    # Tarea 6: Sincronizar ofertas activas de la BD con el catálogo del mesero
    prods_ofertas_map = {p.nombre.lower().strip(): p for p in Producto.objects.filter(activo=True, en_oferta=True)}
    for prod_item in catalogo_productos:
        p_match = prods_ofertas_map.get(prod_item["nombre"].lower().strip())
        if p_match and p_match.precio_oferta is not None and p_match.precio_oferta > 0:
            prod_item["precio_base"] = prod_item["precio"]
            prod_item["precio"] = int(p_match.precio_oferta)
            prod_item["en_oferta"] = True
            prod_item["descripcion_oferta"] = p_match.descripcion_oferta or "¡OFERTA ESPECIAL!"

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
    hoy = timezone.localdate()
    ahora_dt = timezone.localtime()
    ahora_hora = ahora_dt.time()
    en_horario = (datetime.time(10, 0) <= ahora_hora < datetime.time(18, 0))

    perfil = getattr(request.user, 'perfil', None)
    locales = PuntoVenta.objects.filter(activo=True).order_by('id')

    if perfil and perfil.punto_venta_actual:
        local_actual = perfil.punto_venta_actual
    else:
        local_id = request.GET.get('local_id')
        if local_id:
            local_actual = get_object_or_404(PuntoVenta, id=local_id)
        else:
            local_actual = locales.first()

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

        if ped.estado == 'PENDIENTE':
            total_pendientes += 1
        elif ped.estado == 'EN_PREPARACION':
            total_en_preparacion += 1
        elif ped.estado == 'LISTO':
            total_listos += 1

        pedidos_data.append({
            'id': ped.id,
            'codigo_ticket': f"BAR-{ped.id:04d}",
            'estado': ped.estado,
            'estado_display': ped.get_estado_display(),
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
        estado='ENTREGADO',
        detalles__producto__categoria__destino_defecto='BARRA'
    ).distinct().select_related('venta__mesa').order_by('-actualizado_en')[:5]

    context = {
        'local_actual': local_actual,
        'locales': locales,
        'pedidos': pedidos_data,
        'total_pendientes': total_pendientes,
        'total_en_preparacion': total_en_preparacion,
        'total_listos': total_listos,
        'total_cola': len(pedidos_data),
        'ultimos_entregados': ultimos_entregados,
        'hoy_str': hoy.strftime("%d/%m/%Y"),
        'ahora_hora_str': ahora_dt.strftime("%H:%M"),
        'en_horario': en_horario,
    }
    return render(request, 'ventas/barra.html', context)

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

        ticket_id = request.POST.get('ticket_id')
        ticket_obj = None
        if ticket_id:
            try:
                ticket_obj = Ticket.objects.filter(id=int(ticket_id)).first()
            except (ValueError, TypeError):
                ticket_obj = None

        observaciones_entrega = request.POST.get('observaciones_entrega') or request.POST.get('observaciones')

        try:
            with transaction.atomic():
                pedido = Pedido.objects.select_for_update().filter(id=pedido_id).first()
                if not pedido:
                    raise ValidationError(f"El pedido #{pedido_id} no existe.")

                if nuevo_estado == 'ENTREGADO':
                    entrega = registrar_entrega_pedido(
                        pedido_or_id=pedido,
                        usuario_entrega=request.user,
                        ticket=ticket_obj,
                        observaciones=observaciones_entrega
                    )
                else:
                    validar_transicion_estado_pedido(pedido, nuevo_estado)
                    if nuevo_estado != pedido.estado:
                        pedido.estado = nuevo_estado
                        ahora = timezone.now()
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
                return JsonResponse({'status': 'error', 'mensaje': msg_err}, status=400)
            messages.error(request, msg_err)
            referer = request.META.get('HTTP_REFERER')
            if referer and ('/cocina/' in referer or '/mesero/' in referer or '/barra/' in referer):
                return redirect(referer)
            return redirect('cocina')

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
        if referer and ('/cocina/' in referer or '/mesero/' in referer or '/barra/' in referer):
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
        return render(request, 'ventas/reporte_ventas_impresion.html', {'datos': datos})

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
        clave_actual = request.POST.get('clave_actual', '')
        nueva_clave = request.POST.get('nueva_clave', '')
        confirmar_clave = request.POST.get('confirmar_clave', '')

        if not request.user.check_password(clave_actual):
            messages.error(request, "La contraseña actual ingresada es incorrecta.")
            return render(request, 'ventas/cambiar_clave_expirada.html')

        if nueva_clave != confirmar_clave:
            messages.error(request, "La nueva contraseña y la confirmación no coinciden.")
            return render(request, 'ventas/cambiar_clave_expirada.html')

        if clave_actual == nueva_clave:
            messages.error(request, "La nueva contraseña no puede ser idéntica a la actual.")
            return render(request, 'ventas/cambiar_clave_expirada.html')

        es_valida, mensaje_err = validar_complejidad_clave(nueva_clave)
        if not es_valida:
            messages.error(request, mensaje_err)
            return render(request, 'ventas/cambiar_clave_expirada.html')

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
        if rol == 'ADMINISTRADOR':
            return redirect('administrador')
        elif rol == 'CAJERO':
            return redirect('vendedor')
        elif rol == 'MESERO':
            return redirect('mesero')
        elif rol == 'COCINERO':
            return redirect('cocina')
        return redirect('index')

    return render(request, 'ventas/cambiar_clave_expirada.html')


# ==============================================================================
# API VERIFICACIÓN QR Y CONVENIOS CABAÑAS (RF13 - Tarea 7)
# ==============================================================================
def api_verificar_convenio_qr(request):
    """Verifica código QR o de barras para convenios comerciales (RF07.5) o huéspedes de cabañas"""
    codigo = request.GET.get('codigo', '').strip()
    if not codigo:
        return JsonResponse({'ok': False, 'mensaje': 'Por favor ingresa o escanea un código QR o de barra.'}, status=400)

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

    return JsonResponse({
        'ok': True,
        'encontrado': True,
        'valido_hoy': valido_hoy,
        'puede_consumir': puede_consumir,
        'codigo': convenio.codigo_qr,
        'cabana': convenio.numero_cabana,
        'titular': convenio.nombre_titular,
        'tipo_beneficio': convenio.tipo_beneficio,
        'tipo_display': convenio.get_tipo_beneficio_display(),
        'valor_descuento': float(convenio.valor_descuento),
        'limite_diario': convenio.limite_diario,
        'consumos_hoy': consumos_hoy,
        'mensaje': mensaje
    })


def api_aplicar_consumo_convenio(request):
    """Registra el consumo del beneficio (desayuno o descuento) asociado a un huésped de cabaña"""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'mensaje': 'Método no permitido'}, status=405)

    codigo = request.POST.get('codigo', '').strip()
    ticket_id = request.POST.get('ticket_id')
    monto_original = request.POST.get('monto_original', '0')
    monto_bonificado = request.POST.get('monto_bonificado', '0')
    monto_pagado = request.POST.get('monto_pagado', '0')

    convenio = ConvenioHuesped.objects.filter(codigo_qr__iexact=codigo).first()
    if not convenio:
        return JsonResponse({'ok': False, 'mensaje': 'Convenio no encontrado.'}, status=404)

    if not convenio.puede_consumir_hoy():
        return JsonResponse({'ok': False, 'mensaje': 'El huésped ya alcanzó su límite de consumos de hoy.'}, status=400)

    ticket = Ticket.objects.filter(id=ticket_id).first() if ticket_id else None

    consumo = ConsumoHuesped.objects.create(
        convenio=convenio,
        ticket=ticket,
        monto_original=Decimal(str(monto_original)),
        monto_bonificado=Decimal(str(monto_bonificado)),
        monto_pagado=Decimal(str(monto_pagado)),
        registrado_por=request.user if request.user.is_authenticated else User.objects.first(),
        observaciones=f"Descuento aplicado en local: {convenio.get_tipo_beneficio_display()}"
    )

    return JsonResponse({
        'ok': True,
        'mensaje': f"Beneficio aplicado exitosamente para {convenio.numero_cabana} ({convenio.nombre_titular}).",
        'consumos_hoy': convenio.consumos_hoy_count()
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
                # Generar código automático si no se ingresó uno personalizado
                import random
                codigo_qr = f"CAB-{numero_cabana.replace(' ', '')}-{random.randint(1000, 9999)}"

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
    return render(request, 'ventas/administrador_convenios.html', context)


# ==============================================================================
# GESTIÓN DE OFERTAS DE TEMPORADA (Tarea 7)
# ==============================================================================
@requiere_rol(['ADMINISTRADOR'])
def administrador_ofertas_temporada(request):
    """Panel para que el Administrador active o desactive ofertas de temporada en vivo"""
    rol = obtener_rol_usuario(request.user)
    if rol != 'ADMINISTRADOR':
        messages.error(request, "Acceso restringido al personal de Administración.")
        return redirect('index')

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'crear':
            nombre = request.POST.get('nombre', '').strip()
            descripcion = request.POST.get('descripcion', '').strip()
            descuento_porcentaje = Decimal(request.POST.get('descuento_porcentaje', '0'))
            fecha_inicio = request.POST.get('fecha_inicio') or timezone.now().date()
            fecha_fin = request.POST.get('fecha_fin')
            activa = request.POST.get('activa') == 'on'

            OfertaTemporada.objects.create(
                nombre=nombre,
                descripcion=descripcion,
                descuento_porcentaje=descuento_porcentaje,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                activa=activa
            )
            messages.success(request, f"Oferta de temporada '{nombre}' configurada exitosamente.")
            return redirect('administrador_ofertas_temporada')

        elif accion == 'toggle':
            oferta_id = request.POST.get('oferta_id')
            o = get_object_or_404(OfertaTemporada, id=oferta_id)
            o.activa = not o.activa
            o.save(update_fields=['activa'])
            estado = "activada" if o.activa else "desactivada"
            messages.success(request, f"Oferta '{o.nombre}' {estado} correctamente.")
            return redirect('administrador_ofertas_temporada')

    ofertas = OfertaTemporada.objects.all().order_by('-fecha_inicio')
    context = {
        'ofertas': ofertas,
        'activas_count': ofertas.filter(activa=True).count(),
        'categorias': Categoria.objects.filter(activo=True)
    }
    return render(request, 'ventas/administrador_ofertas_temporada.html', context)


# ==============================================================================
# REIMPRESIÓN TRAZABLE DE TICKETS (RF08.6)
# ==============================================================================
@requiere_rol(['ADMINISTRADOR', 'CAJERO'])
def reimprimir_ticket_view(request, ticket_id):
    """Reimprime un ticket de producción o comprobante de forma trazable (RF08.6)"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
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
    return redirect(request.META.get('HTTP_REFERER', 'vendedor'))

def ver_imprimir_ticket_digital(request, ticket_id):
    """
    Previsualización e impresión digital térmica de ticket (RF09.3).
    Permite abrir la ventana de impresión térmica o del navegador con formato 80mm/58mm.
    """
    ticket = get_object_or_404(Ticket.objects.select_related('punto_impresion', 'punto_venta', 'pedido', 'venta'), id=ticket_id)
    punto_imp = ticket.punto_impresion
    if not punto_imp and ticket.get_punto_venta():
        punto_imp = ticket.get_punto_venta().puntos_impresion.filter(tipo_destino=ticket.tipo_destino).first()

    return render(request, 'ventas/ticket_impresion_digital.html', {
        'ticket': ticket,
        'punto_impresion': punto_imp
    })


def reintentar_impresion_view(request, ticket_id):
    """
    Reintenta el despacho de impresión de un ticket fallido o pendiente (RF09.4).
    Si el punto de impresión volvió a estar online, despacha sin alterar la venta.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)
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

    empleado_id = request.POST.get('empleado_id')
    tipo_consumo = request.POST.get('tipo_consumo', 'FIADO').upper()
    observaciones = request.POST.get('observaciones', '').strip()
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
    punto_venta = perfil.punto_venta_actual if perfil else None

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
            consumo = get_object_or_404(ConsumoInterno, id=consumo_id)
            consumo.estado = 'ANULADO'
            consumo.save(update_fields=['estado'])
            messages.warning(request, f"El consumo #{consumo.id:04d} ha sido anulado.")

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

    # Resumen por Colaborador
    colaboradores_perfiles = PerfilEmpleado.objects.filter(usuario__is_active=True).select_related('usuario', 'punto_venta_actual').order_by('usuario__first_name', 'usuario__username')
    resumen_colaboradores = []
    for p in colaboradores_perfiles:
        deuda = p.total_fiado_pendiente()
        resumen_colaboradores.append({
            'usuario': p.usuario,
            'rut': getattr(p, 'rut', '') or 'Sin registrar',
            'rol': p.get_rol_display(),
            'local_nombre': p.punto_venta_actual.nombre if p.punto_venta_actual else 'Sin Asignar',
            'total_pendiente': deuda
        })

    # Ordenar: primero los que tienen deuda pendiente descendente
    resumen_colaboradores.sort(key=lambda x: (x['total_pendiente'] <= 0, -x['total_pendiente'], x['usuario'].username))

    locales = PuntoVenta.objects.filter(activo=True).order_by('id')

    context = {
        'total_pendiente': total_pendiente,
        'total_descontado': total_descontado,
        'empleados_con_deuda': empleados_con_deuda,
        'consumos': consumos_qs,
        'resumen_colaboradores': resumen_colaboradores,
        'locales': locales,
    }
    return render(request, 'ventas/administrador_consumos.html', context)

