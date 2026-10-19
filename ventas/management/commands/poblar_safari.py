from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ventas.models import PuntoVenta, PerfilEmpleado, Mesa, Categoria, Producto, Menu


class Command(BaseCommand):
    help = "Puebla datos iniciales de demostración de Parque Safari de manera idempotente (locales, usuarios y mesas)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-passwords',
            action='store_true',
            help='Restablece las contraseñas de todos los usuarios de demostración a safari123'
        )

    def handle(self, *args, **options):
        reset_passwords = options.get('reset_passwords', False)
        self.stdout.write(self.style.NOTICE("=== Iniciando población de datos demo Parque Safari ==="))

        # 1. PUNTOS DE VENTA (LOCALES)
        locales_def = [
            {
                "id": 1,
                "nombre": "Restaurante Central Safari",
                "tipo": "Restaurante & Buffet Caliente",
                "descripcion": "Comida por cocinar, platos de fondo caliente, minutas, hamburguesas y autoservicio para familias.",
                "icono": "bi-building-fill",
                "color": "#c62828"
            },
            {
                "id": 2,
                "nombre": "Cafetería & Pastelería La Selva",
                "tipo": "Cafetería Barista & Repostería",
                "descripcion": "Café de grano italiano de barista, sándwiches frescos de vitrina, jugos naturales exprimidos y pastelería.",
                "icono": "bi-cup-hot-fill",
                "color": "#6b21a8"
            },
            {
                "id": 3,
                "nombre": "Barra Rápida & Kiosco Oasis",
                "tipo": "Punto Snack & Bebidas Frías",
                "descripcion": "Bebidas frías, jugos en caja, empanadas de mantenedor, helados y snacks al paso en zonas de recorrido.",
                "icono": "bi-shop-window",
                "color": "#0284c7"
            }
        ]

        puntos = {}
        for ldef in locales_def:
            pv, creado = PuntoVenta.objects.get_or_create(
                id=ldef["id"],
                defaults={
                    "nombre": ldef["nombre"],
                    "tipo": ldef["tipo"],
                    "descripcion": ldef["descripcion"],
                    "icono": ldef["icono"],
                    "color": ldef["color"],
                    "activo": True
                }
            )
            if not creado:
                # Actualizar icono y color si estaban por defecto
                actualizado = False
                if not pv.icono or pv.icono == 'bi-shop':
                    pv.icono = ldef["icono"]
                    actualizado = True
                if not pv.color or pv.color == '#c62828' and ldef["id"] != 1:
                    pv.color = ldef["color"]
                    actualizado = True
                if actualizado:
                    pv.save()
            puntos[ldef["id"]] = pv
            if creado:
                self.stdout.write(self.style.SUCCESS(f"  [+] Local creado: {pv.nombre} (ID {pv.id})"))
            else:
                self.stdout.write(f"  [=] Local existente: {pv.nombre} (ID {pv.id})")

        # 2. USUARIOS ADMINISTRADORES
        admins_def = [
            {
                "username": "rgomez",
                "first_name": "Roberto",
                "last_name": "Gómez Silva",
                "email": "rgomez@parquesafari.cl",
                "rut": "13.234.567-8",
                "telefono": "+56 9 1234 5678"
            },
            {
                "username": "admin_safari",
                "first_name": "Administrador",
                "last_name": "General Safari",
                "email": "admin@parquesafari.cl",
                "rut": "10.111.222-3",
                "telefono": "+56 9 9999 8888"
            }
        ]

        for adm in admins_def:
            user, creado = User.objects.get_or_create(
                username=adm["username"],
                defaults={
                    "first_name": adm["first_name"],
                    "last_name": adm["last_name"],
                    "email": adm["email"],
                    "is_staff": True,
                    "is_superuser": True
                }
            )
            if creado:
                user.set_password("safari123")
                user.is_staff = True
                user.is_superuser = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f"  [+] Administrador creado: {user.username} (password: safari123)"))
            elif reset_passwords:
                user.set_password("safari123")
                user.save()
                self.stdout.write(self.style.WARNING(f"  [!] Password restablecido para admin: {user.username}"))
            else:
                self.stdout.write(f"  [=] Administrador existente: {user.username} (password conservada)")

            PerfilEmpleado.objects.get_or_create(
                usuario=user,
                defaults={
                    "rol": "ADMINISTRADOR",
                    "rut": adm["rut"],
                    "telefono": adm["telefono"],
                    "activo": True
                }
            )

        # 3. PERSONAL DEMO OPERATIVO (CAJEROS Y MESEROS)
        personal_inicial = [
            {"username": "cvalenzuela", "first_name": "Carlos", "last_name": "Valenzuela M.", "rut": "15.421.890-3", "rol": "CAJERO", "telefono": "+56 9 8421 8903", "local_id": 1},
            {"username": "mmorales", "first_name": "Marcela", "last_name": "Morales P.", "rut": "17.654.120-K", "rol": "MESERO", "telefono": "+56 9 7654 1201", "local_id": 1},
            {"username": "eparedes", "first_name": "Esteban", "last_name": "Paredes G.", "rut": "18.320.911-5", "rol": "COCINERO", "telefono": "+56 9 8320 9115", "local_id": 1},
            {"username": "dsilva", "first_name": "Daniela", "last_name": "Silva C.", "rut": "19.789.442-1", "rol": "MESERO", "telefono": "+56 9 9789 4421", "local_id": 1},
            {"username": "csoto", "first_name": "Camila", "last_name": "Soto Rojas", "rut": "16.890.312-4", "rol": "CAJERO", "telefono": "+56 9 6890 3124", "local_id": 2},
            {"username": "rfuentes", "first_name": "Rodrigo", "last_name": "Fuentes A.", "rut": "20.145.789-2", "rol": "MESERO", "telefono": "+56 9 0145 7892", "local_id": 2},
            {"username": "mgonzalez", "first_name": "Matías", "last_name": "González P.", "rut": "18.910.455-8", "rol": "CAJERO", "telefono": "+56 9 8910 4558", "local_id": 3},
            {"username": "varaya", "first_name": "Valentina", "last_name": "Araya T.", "rut": "19.345.678-0", "rol": "MESERO", "telefono": "+56 9 9345 6780", "local_id": 3},
        ]

        for pdata in personal_inicial:
            u, creado = User.objects.get_or_create(
                username=pdata["username"],
                defaults={
                    "first_name": pdata["first_name"],
                    "last_name": pdata["last_name"],
                    "email": f"{pdata['username']}@parquesafari.cl"
                }
            )
            if creado:
                u.set_password("safari123")
                u.save()
                self.stdout.write(self.style.SUCCESS(f"  [+] Usuario creado: {u.username} (password: safari123)"))
            elif reset_passwords:
                u.set_password("safari123")
                u.save()
                self.stdout.write(self.style.WARNING(f"  [!] Password restablecido para usuario: {u.username}"))
            else:
                self.stdout.write(f"  [=] Usuario existente: {u.username} (password conservada)")

            perfil, p_creado = PerfilEmpleado.objects.get_or_create(
                usuario=u,
                defaults={
                    "rol": pdata["rol"],
                    "rut": pdata["rut"],
                    "telefono": pdata["telefono"],
                    "punto_venta_actual": puntos.get(pdata["local_id"]),
                    "activo": True
                }
            )
            # Asegurar que el punto de venta y rol estén sincronizados
            if not p_creado:
                cambios = False
                if not perfil.punto_venta_actual and pdata["local_id"]:
                    perfil.punto_venta_actual = puntos.get(pdata["local_id"])
                    cambios = True
                if perfil.rol != pdata["rol"]:
                    perfil.rol = pdata["rol"]
                    cambios = True
                if cambios:
                    perfil.save()

        # 4. MESAS OPERATIVAS (Si no existen)
        if Mesa.objects.count() == 0:
            mesas_def = [
                # Local 1: Restaurante Central Safari
                {"identificador": "Mesa 1", "local_id": 1, "capacidad": 4, "estado": "HABILITADA"},
                {"identificador": "Mesa 2", "local_id": 1, "capacidad": 4, "estado": "OCUPADA"},
                {"identificador": "Mesa 3", "local_id": 1, "capacidad": 6, "estado": "HABILITADA"},
                {"identificador": "Mesa 4", "local_id": 1, "capacidad": 2, "estado": "OCUPADA"},
                {"identificador": "Mesa 5", "local_id": 1, "capacidad": 4, "estado": "HABILITADA"},
                {"identificador": "Mesa 6", "local_id": 1, "capacidad": 8, "estado": "HABILITADA"},
                {"identificador": "Terraza 1", "local_id": 1, "capacidad": 4, "estado": "HABILITADA"},
                {"identificador": "Terraza 2", "local_id": 1, "capacidad": 4, "estado": "HABILITADA"},
                # Local 2: Cafetería & Pastelería La Selva
                {"identificador": "Mesa 1", "local_id": 2, "capacidad": 2, "estado": "HABILITADA"},
                {"identificador": "Mesa 2", "local_id": 2, "capacidad": 4, "estado": "OCUPADA"},
                {"identificador": "Mesa 3", "local_id": 2, "capacidad": 2, "estado": "HABILITADA"},
                {"identificador": "Terraza 1", "local_id": 2, "capacidad": 4, "estado": "HABILITADA"},
                # Local 3: Barra Rápida & Kiosco Oasis
                {"identificador": "Mesa 1", "local_id": 3, "capacidad": 2, "estado": "HABILITADA"},
                {"identificador": "Barra 1", "local_id": 3, "capacidad": 4, "estado": "HABILITADA"},
            ]
            for mdata in mesas_def:
                pv = puntos.get(mdata["local_id"])
                if pv:
                    Mesa.objects.create(
                        identificador=mdata["identificador"],
                        punto_venta=pv,
                        capacidad=mdata["capacidad"],
                        estado=mdata["estado"]
                    )
            self.stdout.write(self.style.SUCCESS(f"  [+] Mesas operativas creadas ({len(mesas_def)} mesas)"))
        else:
            self.stdout.write(f"  [=] Mesas operativas ya existentes ({Mesa.objects.count()} mesas)")

        # 5. CATEGORÍAS GASTRONÓMICAS BASE
        categorias_def = [
            {"nombre": "Comida por Cocinar", "descripcion": "Platos calientes, hamburguesas y minutas preparadas al momento (KDS Cocina)"},
            {"nombre": "Comida Preparada", "descripcion": "Platos listos para buffet, mantenedor térmico y autoservicio"},
            {"nombre": "Bebidas Envasadas", "descripcion": "Gaseosas, aguas minerales y jugos sellados"},
            {"nombre": "Cafetería y Jugos", "descripcion": "Café de grano barista, infusiones calientes y jugos naturales (Barra)"},
            {"nombre": "Pastelería y Snacks", "descripcion": "Tortas, pastelería artesanal y snacks al paso"},
        ]
        cats = {}
        for cdef in categorias_def:
            cat_obj, c_creado = Categoria.objects.get_or_create(
                nombre=cdef["nombre"],
                defaults={"descripcion": cdef["descripcion"], "activo": True}
            )
            cats[cdef["nombre"]] = cat_obj
            if c_creado:
                self.stdout.write(self.style.SUCCESS(f"  [+] Categoría creada: {cat_obj.nombre}"))

        # 6. PRODUCTOS BASE POR LOCAL
        productos_def = [
            {"nombre": "Hamburguesa Safari con Papas", "cat": "Comida por Cocinar", "precio": 8900, "locales": [1]},
            {"nombre": "Churrasco Italiano con Papas", "cat": "Comida por Cocinar", "precio": 8500, "locales": [1]},
            {"nombre": "Porción Papas Fritas Rústicas", "cat": "Comida por Cocinar", "precio": 3600, "locales": [1, 3]},
            {"nombre": "Cazuela de Ave Criolla", "cat": "Comida Preparada", "precio": 7500, "locales": [1]},
            {"nombre": "Menú Infantil Nuggets con Papas", "cat": "Comida por Cocinar", "precio": 5900, "locales": [1]},
            {"nombre": "Empanada de Pino Horno", "cat": "Comida Preparada", "precio": 2800, "locales": [1, 3]},
            {"nombre": "Café Espresso Doble", "cat": "Cafetería y Jugos", "precio": 2500, "locales": [2]},
            {"nombre": "Café Cappuccino Vainilla", "cat": "Cafetería y Jugos", "precio": 3200, "locales": [2]},
            {"nombre": "Jugo Natural Frambuesa 400ml", "cat": "Cafetería y Jugos", "precio": 3900, "locales": [1, 2]},
            {"nombre": "Té e Infusiones Variadas", "cat": "Cafetería y Jugos", "precio": 1800, "locales": [2]},
            {"nombre": "Torta Selva Negra Safari", "cat": "Pastelería y Snacks", "precio": 4200, "locales": [2]},
            {"nombre": "Croissant Jamón y Queso", "cat": "Pastelería y Snacks", "precio": 3400, "locales": [2]},
            {"nombre": "Bebida Coca-Cola 350ml", "cat": "Bebidas Envasadas", "precio": 2000, "locales": [1, 2, 3]},
            {"nombre": "Bebida Sprite 350ml", "cat": "Bebidas Envasadas", "precio": 2000, "locales": [1, 2, 3]},
            {"nombre": "Agua Mineral sin Gas 500ml", "cat": "Bebidas Envasadas", "precio": 1500, "locales": [1, 2, 3]},
            {"nombre": "Jugo en Caja 200ml", "cat": "Bebidas Envasadas", "precio": 1350, "locales": [3]},
        ]
        prods_dict = {}
        for pdef in productos_def:
            cat_obj = cats.get(pdef["cat"])
            prod_obj, p_creado = Producto.objects.get_or_create(
                nombre=pdef["nombre"],
                defaults={
                    "categoria": cat_obj,
                    "precio_base": pdef["precio"],
                    "activo": True,
                    "descripcion": f"{pdef['nombre']} para servicio gastronómico Parque Safari"
                }
            )
            # Asegurar relación con puntos de venta asignados
            for lid in pdef["locales"]:
                if lid in puntos:
                    prod_obj.puntos_venta.add(puntos[lid])
            prods_dict[pdef["nombre"]] = prod_obj
            if p_creado:
                self.stdout.write(self.style.SUCCESS(f"  [+] Producto creado: {prod_obj.nombre} (${prod_obj.precio_base:,.0f})"))

        # 7. MENÚS DE CARTA POR LOCAL
        menus_def = [
            {
                "nombre": "Carta Almuerzos y Minutas Central",
                "local_id": 1,
                "productos": [
                    "Hamburguesa Safari con Papas", "Churrasco Italiano con Papas",
                    "Porción Papas Fritas Rústicas", "Cazuela de Ave Criolla",
                    "Menú Infantil Nuggets con Papas", "Bebida Coca-Cola 350ml",
                    "Jugo Natural Frambuesa 400ml"
                ]
            },
            {
                "nombre": "Carta Barista y Repostería La Selva",
                "local_id": 2,
                "productos": [
                    "Café Espresso Doble", "Café Cappuccino Vainilla",
                    "Té e Infusiones Variadas", "Torta Selva Negra Safari",
                    "Croissant Jamón y Queso", "Bebida Sprite 350ml"
                ]
            },
            {
                "nombre": "Menú Rápido y Bebidas Kiosco Oasis",
                "local_id": 3,
                "productos": [
                    "Empanada de Pino Horno", "Porción Papas Fritas Rústicas",
                    "Bebida Coca-Cola 350ml", "Agua Mineral sin Gas 500ml",
                    "Jugo en Caja 200ml"
                ]
            }
        ]

        for mdef in menus_def:
            pv = puntos.get(mdef["local_id"])
            if pv:
                menu_obj, m_creado = Menu.objects.get_or_create(
                    nombre=mdef["nombre"],
                    punto_venta=pv,
                    defaults={"activo": True}
                )
                for p_nom in mdef["productos"]:
                    if p_nom in prods_dict:
                        menu_obj.productos.add(prods_dict[p_nom])
                if m_creado:
                    self.stdout.write(self.style.SUCCESS(f"  [+] Menú creado: {menu_obj.nombre} en {pv.nombre}"))

        self.stdout.write(self.style.SUCCESS("=== Población completada con éxito e idempotencia comprobada ==="))
