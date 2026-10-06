from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ventas.models import PuntoVenta, PerfilEmpleado, Mesa


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
            {"username": "eparedes", "first_name": "Esteban", "last_name": "Paredes G.", "rut": "18.320.911-5", "rol": "MESERO", "telefono": "+56 9 8320 9115", "local_id": 1},
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
            # Asegurar que el punto de venta esté asignado si el perfil ya existía sin puesto
            if not p_creado and not perfil.punto_venta_actual and pdata["local_id"]:
                perfil.punto_venta_actual = puntos.get(pdata["local_id"])
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

        self.stdout.write(self.style.SUCCESS("=== Población completada con éxito e idempotencia comprobada ==="))
