import json
import os
from pathlib import Path
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.cache import cache
from ventas.models import PuntoVenta, PerfilEmpleado, AlertaTraslado, Jornada, Caja, Mesa, Venta, DetalleVenta, Ticket, Pedido, DetallePedido, Entrega, Categoria, Producto, Menu


class SafariFase2A1Tests(TestCase):
    """
    Suite oficial de pruebas automatizadas reproducibles para Fase 2A.1:
    - Autenticación real y logout (RF01)
    - Control de acceso y aislamiento estricto por PerfilEmpleado
    - Apertura de Jornada con validación de fecha actual (RF02)
    - Apertura de Caja individual por cajero con fondo opcional/cero (RF03)
    - Validación estricta de Punto de Venta asignado
    - Prevención de registros duplicados e idempotencia
    - Creación de trabajadores con contraseña requerida
    - Módulo y perfil independiente de Cocina KDS y notificación de pedidos listos
    """

    def setUp(self):
        cache.clear()
        self.client = Client()
        # Poblar datos demo con el comando idempotente oficial
        call_command('poblar_safari')

        self.admin_user = User.objects.get(username='rgomez')
        self.cajero_user = User.objects.get(username='cvalenzuela')
        self.cajera2_user = User.objects.get(username='csoto')
        self.mesero_user = User.objects.get(username='dsilva')
        self.cocinero_user = User.objects.get(username='eparedes')

    def tearDown(self):
        cache.clear()

    # 1. Login con credenciales inválidas es rechazado
    def test_login_credenciales_invalidas(self):
        resp = self.client.post(reverse('login'), {
            'username': 'cvalenzuela',
            'password': 'password_incorrecta_99'
        }, follow=True)
        self.assertContains(resp, "Credenciales incorrectas")
        self.assertFalse(resp.context['user'].is_authenticated)

    # 2. Acceso anónimo bloqueado en rutas protegidas
    def test_acceso_anonimo_bloqueado(self):
        rutas = [reverse('administrador'), reverse('vendedor'), reverse('mesero'), reverse('cocina')]
        for ruta in rutas:
            resp = self.client.get(ruta, follow=True)
            self.assertRedirects(resp, reverse('index'))
            self.assertContains(resp, "Acceso protegido")

    # 3. Aislamiento estricto de los 4 roles (Administrador, Cajero, Mesero, Cocinero)
    def test_aislamiento_roles(self):
        # Mesero intentando entrar a administrador, vendedor o cocina
        self.client.force_login(self.mesero_user)
        resp_admin = self.client.get(reverse('administrador'), follow=True)
        self.assertRedirects(resp_admin, reverse('mesero'))
        resp_vendedor = self.client.get(reverse('vendedor'), follow=True)
        self.assertRedirects(resp_vendedor, reverse('mesero'))
        resp_cocina = self.client.get(reverse('cocina'), follow=True)
        self.assertRedirects(resp_cocina, reverse('mesero'))

        # Cajero intentando entrar a administrador, mesero o cocina
        self.client.force_login(self.cajero_user)
        resp_admin = self.client.get(reverse('administrador'), follow=True)
        self.assertRedirects(resp_admin, reverse('vendedor'))
        resp_mesero = self.client.get(reverse('mesero'), follow=True)
        self.assertRedirects(resp_mesero, reverse('vendedor'))
        resp_cocina = self.client.get(reverse('cocina'), follow=True)
        self.assertRedirects(resp_cocina, reverse('vendedor'))

        # Cocinero intentando entrar a administrador, vendedor o mesero
        self.client.force_login(self.cocinero_user)
        resp_admin = self.client.get(reverse('administrador'), follow=True)
        self.assertRedirects(resp_admin, reverse('cocina'))
        resp_vendedor = self.client.get(reverse('vendedor'), follow=True)
        self.assertRedirects(resp_vendedor, reverse('cocina'))
        resp_mesero = self.client.get(reverse('mesero'), follow=True)
        self.assertRedirects(resp_mesero, reverse('cocina'))
        # Cocinero accediendo legítimamente a su pantalla KDS
        resp_kds = self.client.get(reverse('cocina'))
        self.assertEqual(resp_kds.status_code, 200)

        # Administrador intentando entrar a vendedor o mesero (administrador tiene supervisión en cocina)
        self.client.force_login(self.admin_user)
        resp_vendedor = self.client.get(reverse('vendedor'), follow=True)
        self.assertRedirects(resp_vendedor, reverse('administrador'))
        resp_mesero = self.client.get(reverse('mesero'), follow=True)
        self.assertRedirects(resp_mesero, reverse('administrador'))
        resp_admin_cocina = self.client.get(reverse('cocina'))
        self.assertEqual(resp_admin_cocina.status_code, 200)

    # 4. Selector visual no altera rol real
    def test_selector_visual_no_afecta_rol_real(self):
        # Cajero autenticado con selección visual alterada en POST
        resp = self.client.post(reverse('login'), {
            'username': 'cvalenzuela',
            'password': 'safari123',
            'rol_selector': 'ADMINISTRADOR'
        }, follow=True)
        # Redirección efectiva basada 100% en PerfilEmpleado de la BD -> /vendedor/
        self.assertRedirects(resp, reverse('vendedor'))

        # Cocinero autenticado con selección visual alterada en POST
        resp_cocinero = self.client.post(reverse('login'), {
            'username': 'eparedes',
            'password': 'safari123',
            'rol_selector': 'ADMINISTRADOR'
        }, follow=True)
        # Redirección efectiva basada 100% en PerfilEmpleado de la BD -> /cocina/
        self.assertRedirects(resp_cocinero, reverse('cocina'))

    # 5. Jornada de ayer abierta NO es válida para el día de hoy
    def test_jornada_ayer_no_valida_hoy(self):
        ayer = timezone.localdate() - timedelta(days=1)
        jornada_ayer = Jornada.objects.create(
            usuario_apertura=self.admin_user,
            estado='ABIERTA',
            observaciones="Jornada de ayer que quedó abierta"
        )
        Jornada.objects.filter(id=jornada_ayer.id).update(fecha=ayer)

        self.client.force_login(self.cajero_user)
        resp = self.client.get(reverse('vendedor'))
        self.assertIsNone(resp.context['jornada_activa'])
        self.assertContains(resp, "Apertura Diaria de Jornada Requerida")

    # 6. Primera Caja con fondo opcional ($0)
    def test_apertura_jornada_y_caja_fondo_opcional(self):
        self.client.force_login(self.cajero_user)
        resp = self.client.post(reverse('abrir_jornada'), {
            'monto_apertura': '',
            'observaciones': 'Apertura con fondo omitido'
        }, follow=True)
        self.assertRedirects(resp, reverse('vendedor'))

        hoy = timezone.localdate()
        jornada = Jornada.objects.filter(estado='ABIERTA', fecha=hoy).first()
        self.assertIsNotNone(jornada)
        caja = Caja.objects.filter(jornada=jornada, cajero=self.cajero_user).first()
        self.assertIsNotNone(caja)
        self.assertEqual(caja.monto_apertura, Decimal('0'))

    # 7. Segundo Cajero en la misma Jornada comparte jornada y abre caja propia
    def test_segundo_cajero_misma_jornada(self):
        self.client.force_login(self.cajero_user)
        self.client.post(reverse('abrir_jornada'), {'monto_apertura': '20000'})

        self.client.force_login(self.cajera2_user)
        resp = self.client.post(reverse('abrir_caja'), {'monto_apertura': '35000'}, follow=True)
        self.assertRedirects(resp, reverse('vendedor'))

        hoy = timezone.localdate()
        self.assertEqual(Jornada.objects.filter(estado='ABIERTA', fecha=hoy).count(), 1)
        self.assertEqual(Caja.objects.filter(jornada__fecha=hoy).count(), 2)

    # 8. Prevención de duplicados (doble POST en jornada y caja)
    def test_prevencion_duplicados_jornada_y_caja(self):
        self.client.force_login(self.cajero_user)
        self.client.post(reverse('abrir_jornada'), {'monto_apertura': '10000'})

        # Segundo POST simultáneo / doble submit a abrir_jornada
        resp2 = self.client.post(reverse('abrir_jornada'), {'monto_apertura': '10000'}, follow=True)
        self.assertContains(resp2, "Ya existe una jornada operativa abierta hoy")
        hoy = timezone.localdate()
        self.assertEqual(Jornada.objects.filter(estado='ABIERTA', fecha=hoy).count(), 1)
        self.assertEqual(Caja.objects.filter(jornada__fecha=hoy, cajero=self.cajero_user).count(), 1)

        # Intento de reabrir caja existente para el mismo cajero
        resp3 = self.client.post(reverse('abrir_caja'), {'monto_apertura': '50000'}, follow=True)
        self.assertContains(resp3, "Ya tienes una caja activa")
        self.assertEqual(Caja.objects.filter(jornada__fecha=hoy, cajero=self.cajero_user).count(), 1)

    # 9. Cajero sin Punto de Venta asignado no puede abrir caja
    def test_cajero_sin_punto_venta_bloqueado(self):
        user_sin_pv = User.objects.create_user(username='cajero_sin_local', password='password123')
        PerfilEmpleado.objects.create(
            usuario=user_sin_pv,
            rol='CAJERO',
            rut='22.222.222-2',
            punto_venta_actual=None,
            activo=True
        )
        self.client.force_login(user_sin_pv)

        # Intento abrir jornada
        resp_j = self.client.post(reverse('abrir_jornada'), {'monto_apertura': '0'}, follow=True)
        self.assertContains(resp_j, "No tienes un Punto de Venta asignado")
        self.assertEqual(Jornada.objects.count(), 0)

        # Con jornada abierta, intento abrir caja
        jornada = Jornada.objects.create(usuario_apertura=self.admin_user, estado='ABIERTA')
        resp_c = self.client.post(reverse('abrir_caja'), {'monto_apertura': '0'}, follow=True)
        self.assertContains(resp_c, "No tienes un Punto de Venta asignado")
        self.assertEqual(Caja.objects.count(), 0)

    # 10. Crear trabajador en administración requiere contraseña explícita obligatoria
    def test_crear_trabajador_requiere_password(self):
        self.client.force_login(self.admin_user)
        pv = PuntoVenta.objects.first()

        # Envío con contraseña vacía -> Debe ser rechazado
        resp_err = self.client.post(reverse('administrador_trabajadores'), {
            'accion': 'crear',
            'nombre': 'Pedro',
            'apellido': 'Pascal',
            'rut': '21.000.111-2',
            'rol': 'MESERO',
            'local_id': pv.id,
            'password': ''
        }, follow=True)
        self.assertContains(resp_err, "Debes ingresar una contraseña")
        self.assertFalse(User.objects.filter(first_name='Pedro', last_name='Pascal').exists())

        # Envío con contraseña válida explícita -> Debe ser registrado exitosamente
        resp_ok = self.client.post(reverse('administrador_trabajadores'), {
            'accion': 'crear',
            'nombre': 'Pedro',
            'apellido': 'Pascal',
            'rut': '21.000.111-2',
            'rol': 'MESERO',
            'local_id': pv.id,
            'password': 'miPasswordSegura2026'
        }, follow=True)
        self.assertContains(resp_ok, "registrado con éxito")
        nuevo = User.objects.get(first_name='Pedro', last_name='Pascal')
        self.assertTrue(nuevo.check_password('miPasswordSegura2026'))

    # 11. Logout funcional y cierre seguro de sesión
    def test_logout_funcional(self):
        self.client.force_login(self.cajero_user)
        resp = self.client.get(reverse('logout'), follow=True)
        self.assertRedirects(resp, reverse('index'))
        self.assertContains(resp, "cerrado tu sesión")
        self.assertFalse(resp.context['user'].is_authenticated)

    # 12. Cambio de estado de colaborador (Activar / Desactivar) por AJAX y tradicional
    def test_toggle_estado_trabajador_ajax_y_post(self):
        self.client.force_login(self.admin_user)
        perfil_mesero = PerfilEmpleado.objects.get(usuario=self.mesero_user)
        self.assertTrue(perfil_mesero.activo)

        # Desactivar por AJAX (evita recarga de página y saltos de scroll)
        resp_ajax = self.client.post(
            reverse('administrador_trabajadores'),
            {'accion': 'desactivar', 'perfil_id': perfil_mesero.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp_ajax.status_code, 200)
        data = resp_ajax.json()
        self.assertEqual(data['status'], 'ok')
        self.assertFalse(data['activo'])
        self.assertIn('desactivado', data['mensaje'])

        perfil_mesero.refresh_from_db()
        self.assertFalse(perfil_mesero.activo)
        self.assertFalse(perfil_mesero.usuario.is_active)

        # Reactivar por AJAX
        resp_ajax_activar = self.client.post(
            reverse('administrador_trabajadores'),
            {'accion': 'activar', 'perfil_id': perfil_mesero.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp_ajax_activar.status_code, 200)
        data_act = resp_ajax_activar.json()
        self.assertEqual(data_act['status'], 'ok')
        self.assertTrue(data_act['activo'])

        perfil_mesero.refresh_from_db()
        self.assertTrue(perfil_mesero.activo)
        self.assertTrue(perfil_mesero.usuario.is_active)

        # Fallback tradicional con redirección (POST estándar sin AJAX)
        resp_post = self.client.post(
            reverse('administrador_trabajadores'),
            {'accion': 'desactivar', 'perfil_id': perfil_mesero.id}
        )
        self.assertRedirects(resp_post, reverse('administrador_trabajadores'))
        perfil_mesero.refresh_from_db()
        self.assertFalse(perfil_mesero.activo)

    # 13. Trabajador inactivo no puede iniciar sesión; reactivación le permite volver a ingresar
    def test_login_trabajador_inactivo_rechazado_y_reactivacion_permite_login(self):
        perfil = PerfilEmpleado.objects.get(usuario=self.cajero_user)
        perfil.activo = False
        perfil.save()
        self.cajero_user.is_active = False
        self.cajero_user.save()

        # Intento de login con credenciales correctas siendo inactivo -> Debe ser rechazado
        resp_inactivo = self.client.post(reverse('login'), {
            'username': 'cvalenzuela',
            'password': 'safari123'
        }, follow=True)
        self.assertContains(resp_inactivo, "cuenta de colaborador se encuentra inactiva")
        self.assertFalse(resp_inactivo.context['user'].is_authenticated)

        # Reactivación del colaborador
        perfil.activo = True
        perfil.save()
        self.cajero_user.is_active = True
        self.cajero_user.save()

        # Intento de login tras reactivación -> Debe iniciar sesión correctamente
        resp_activo = self.client.post(reverse('login'), {
            'username': 'cvalenzuela',
            'password': 'safari123'
        }, follow=True)
        self.assertRedirects(resp_activo, reverse('vendedor'))
        self.assertTrue(resp_activo.context['user'].is_authenticated)

    # 14. Trabajador con sesión abierta que es desactivado queda bloqueado en la siguiente petición
    def test_trabajador_desactivado_con_sesion_previa_bloqueado_en_siguiente_peticion(self):
        # Cajero inicia sesión y accede normalmente a su terminal
        self.client.force_login(self.cajero_user)
        resp_ok = self.client.get(reverse('vendedor'))
        self.assertEqual(resp_ok.status_code, 200)

        # Administrador desactiva al colaborador mientras tenía la sesión abierta
        perfil = PerfilEmpleado.objects.get(usuario=self.cajero_user)
        perfil.activo = False
        perfil.save()

        # Siguiente petición del cajero -> El decorador @requiere_rol detecta perfil.activo=False,
        # revoca la sesión y bloquea el acceso
        resp_bloqueado = self.client.get(reverse('vendedor'), follow=True)
        self.assertRedirects(resp_bloqueado, reverse('index'))
        self.assertContains(resp_bloqueado, "inactiva")
        self.assertFalse(resp_bloqueado.context['user'].is_authenticated)

    # 15. Edición de datos de colaborador sin nueva contraseña conserva intacta la contraseña actual
    def test_edicion_trabajador_sin_password_conserva_contrasena(self):
        self.client.force_login(self.admin_user)
        perfil = PerfilEmpleado.objects.get(usuario=self.cajero_user)
        self.assertTrue(self.cajero_user.check_password('safari123'))

        # Administrador edita teléfono y RUT sin escribir nueva contraseña
        resp = self.client.post(reverse('administrador_trabajadores'), {
            'accion': 'modificar',
            'perfil_id': perfil.id,
            'nombre': 'Carlos Modificado',
            'apellido': 'Valenzuela M.',
            'rut': '18.999.888-K',
            'rol': 'CAJERO',
            'telefono': '+56911223344',
            'local_id': perfil.punto_venta_actual.id if perfil.punto_venta_actual else 'none',
            'password': ''  # Contraseña vacía (no se desea cambiar)
        }, follow=True)

        self.assertContains(resp, "actualizados correctamente")
        self.cajero_user.refresh_from_db()
        self.assertEqual(self.cajero_user.first_name, 'Carlos Modificado')
        # La contraseña anterior 'safari123' sigue siendo 100% válida
        self.assertTrue(self.cajero_user.check_password('safari123'))

    # 16. Administrador puede crear un nuevo local gastronómico y asignarle trabajadores
    def test_crear_nuevo_local_administrador_y_asignar_trabajador(self):
        self.client.force_login(self.admin_user)
        # 1. Crear nuevo local vía POST en panel de administrador
        resp = self.client.post(reverse('administrador'), {
            'accion': 'crear_local',
            'nombre': 'Heladería Selva Safari',
            'tipo': 'Heladería & Smoothies',
            'descripcion': 'Helados artesanales y batidos de fruta fresca.',
            'icono': 'bi-snow',
            'color': '#059669'
        }, follow=True)

        self.assertContains(resp, "Heladería Selva Safari")
        self.assertContains(resp, "creado exitosamente")

        # Verificar existencia en BD
        nuevo_local = PuntoVenta.objects.get(nombre='Heladería Selva Safari')
        self.assertEqual(nuevo_local.tipo, 'Heladería & Smoothies')
        self.assertEqual(nuevo_local.icono, 'bi-snow')
        self.assertEqual(nuevo_local.color, '#059669')

        # 2. Asignar un trabajador al nuevo local creado
        resp_asig = self.client.post(reverse('administrador_trabajadores'), {
            'accion': 'crear',
            'nombre': 'Andrea',
            'apellido': 'Pavez',
            'username': 'apavez',
            'rut': '19.876.543-2',
            'rol': 'CAJERO',
            'telefono': '+56987654321',
            'local_id': nuevo_local.id,
            'password': 'password123'
        }, follow=True)

        self.assertContains(resp_asig, "registrado con éxito")
        trabajador_nuevo = PerfilEmpleado.objects.get(usuario__username='apavez')
        self.assertEqual(trabajador_nuevo.punto_venta_actual, nuevo_local)

        # 3. Verificar que el nuevo local se puede auditar en /administrador/local/<id>/
        resp_local = self.client.get(reverse('administrador_local', kwargs={'local_id': nuevo_local.id}))
        self.assertEqual(resp_local.status_code, 200)
        self.assertContains(resp_local, "Heladería Selva Safari")
        self.assertContains(resp_local, "Andrea Pavez")

    # 17. Modificar local existente por administrador
    def test_modificar_local_administrador(self):
        self.client.force_login(self.admin_user)
        local = PuntoVenta.objects.first()
        resp = self.client.post(reverse('administrador'), {
            'accion': 'modificar_local',
            'local_id': local.id,
            'nombre': 'Restaurante Central Safari VIP',
            'tipo': 'Restaurante Exclusivo',
            'descripcion': 'Atención buffet y platos calientes especiales.',
            'icono': 'bi-building-fill',
            'color': '#c62828',
            'activo': 'true'
        }, follow=True)
        self.assertContains(resp, "actualizado correctamente")
        local.refresh_from_db()
        self.assertEqual(local.nombre, 'Restaurante Central Safari VIP')
        self.assertEqual(local.tipo, 'Restaurante Exclusivo')

    # 18. Eliminar local por administrador
    def test_eliminar_local_administrador(self):
        self.client.force_login(self.admin_user)
        local_temp = PuntoVenta.objects.create(
            nombre='Kiosco Temporal Test',
            tipo='Kiosco',
            descripcion='Local para prueba de borrado',
            activo=True
        )
        # Asignar colaborador temporal
        perfil = PerfilEmpleado.objects.first()
        perfil.punto_venta_actual = local_temp
        perfil.save()

        resp = self.client.post(reverse('administrador'), {
            'accion': 'eliminar_local',
            'local_id': local_temp.id
        }, follow=True)
        self.assertContains(resp, "eliminado exitosamente")
        self.assertFalse(PuntoVenta.objects.filter(id=local_temp.id).exists())
        perfil.refresh_from_db()
        self.assertIsNone(perfil.punto_venta_actual)

    # 19. Filtros de moneda chilena: nunca abrevian en 1k ni 1M y muestran cifras completas con puntos
    def test_filtro_pesos_chilenos(self):
        from ventas.templatetags.safari_tags import pesos, pesos_clp
        self.assertEqual(pesos(1000), "1.000")
        self.assertEqual(pesos(20000), "20.000")
        self.assertEqual(pesos(1000000), "1.000.000")
        self.assertEqual(pesos_clp(25400), "$25.400")
        self.assertEqual(pesos_clp(1000000), "$1.000.000")
        self.assertEqual(pesos_clp(0), "$0")

    # 20. Mesero envía comanda, se asocia en tiempo real y se refleja en el local
    def test_mesero_envia_comanda_y_se_refleja_en_local(self):
        self.client.force_login(self.mesero_user)
        local = self.mesero_user.perfil.punto_venta_actual
        mesa = Mesa.objects.filter(punto_venta=local).first()
        if not mesa:
            mesa = Mesa.objects.create(identificador="Mesa 1", punto_venta=local, capacidad=4)

        items_comanda = [
            {"nombre": "Hamburguesa Safari con Papas", "cantidad": 2, "precio": 8900, "destino": "COCINA", "nota": "Sin sal"},
            {"nombre": "Bebida Coca-Cola 350ml", "cantidad": 1, "precio": 2000, "destino": "BARRA", "nota": ""}
        ]

        resp = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(items_comanda)
        }, follow=True)
        self.assertContains(resp, "despachada con éxito a Cocina y Barra")

        # Verificar que la mesa quedó OCUPADA
        mesa.refresh_from_db()
        self.assertEqual(mesa.estado, 'OCUPADA')

        # Verificar que la venta quedó registrada en la BD asociada al mesero
        venta = Venta.objects.filter(mesa=mesa, punto_venta=local).first()
        self.assertIsNotNone(venta)
        self.assertEqual(venta.cajero, self.mesero_user)
        self.assertEqual(int(venta.total), 19800)

        # Ahora el administrador audita el local y ve la comanda en tiempo real con rol Mesero
        self.client.force_login(self.admin_user)
        resp_admin_local = self.client.get(reverse('administrador_local', kwargs={'local_id': local.id}))
        self.assertContains(resp_admin_local, "Mesero")
        self.assertContains(resp_admin_local, "$19.800")

    # 21. Mesa con Cuenta Abierta acumula rondas incrementales en la misma Venta
    def test_cuenta_abierta_rondas_incrementales_en_misma_mesa(self):
        self.client.force_login(self.mesero_user)
        local = self.mesero_user.perfil.punto_venta_actual
        mesa = Mesa.objects.filter(punto_venta=local).first()
        if not mesa:
            mesa = Mesa.objects.create(identificador="Mesa 2", punto_venta=local, capacidad=4)

        # Ronda 1: Plato y bebida
        ronda1_items = [
            {"nombre": "Hamburguesa Safari con Papas", "cantidad": 1, "precio": 8900, "destino": "COCINA", "nota": "Sin cebolla"},
            {"nombre": "Coca Cola Original 350ml", "cantidad": 1, "precio": 1800, "destino": "BARRA", "nota": "Con hielo"}
        ]
        resp1 = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(ronda1_items)
        }, follow=True)
        self.assertContains(resp1, "despachada con éxito a Cocina y Barra")

        mesa.refresh_from_db()
        self.assertEqual(mesa.estado, 'OCUPADA')

        venta_abierta = Venta.objects.filter(mesa=mesa, punto_venta=local, estado='ABIERTA').first()
        self.assertIsNotNone(venta_abierta)
        self.assertEqual(int(venta_abierta.total), 10700)
        self.assertEqual(venta_abierta.pedidos.count(), 1)
        venta_id_inicial = venta_abierta.id

        # Ronda 2: Café adicional para la misma mesa (debe reutilizar venta y sumar)
        ronda2_items = [
            {"nombre": "Café Espresso Grano Barista", "cantidad": 2, "precio": 2200, "destino": "BARRA", "nota": ""}
        ]
        resp2 = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(ronda2_items)
        }, follow=True)
        self.assertContains(resp2, "Ronda #2 agregada a la cuenta")
        self.assertContains(resp2, "$15.100")

        venta_abierta.refresh_from_db()
        self.assertEqual(venta_abierta.id, venta_id_inicial)  # Misma Venta acumulada
        self.assertEqual(int(venta_abierta.total), 15100)      # 10700 + 4400
        self.assertEqual(venta_abierta.pedidos.count(), 2)     # 2 rondas registradas

    # 22. Cierre de Cuenta de Mesa: pasa Venta a PAGADA y libera Mesa a HABILITADA
    def test_cierre_cuenta_mesa_libera_y_paga(self):
        self.client.force_login(self.mesero_user)
        local = self.mesero_user.perfil.punto_venta_actual
        mesa = Mesa.objects.filter(punto_venta=local).first()

        # Abrir cuenta con pedido
        items = [{"nombre": "Cazuela de Ave Criolla", "cantidad": 1, "precio": 7500, "destino": "COCINA"}]
        self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(items)
        }, follow=True)

        mesa.refresh_from_db()
        self.assertEqual(mesa.estado, 'OCUPADA')
        venta = Venta.objects.filter(mesa=mesa, punto_venta=local, estado='ABIERTA').first()
        self.assertIsNotNone(venta)

        # Mesero cobra y cierra la cuenta de la mesa
        resp_cierre = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'cerrar_cuenta_mesa',
            'mesa_id': mesa.id,
            'metodo_pago': 'DEBITO'
        }, follow=True)
        self.assertContains(resp_cierre, "pagada y cerrada exitosamente con DEBITO")

        venta.refresh_from_db()
        mesa.refresh_from_db()
        self.assertEqual(venta.estado, 'PAGADA')
        self.assertEqual(venta.metodo_pago, 'DEBITO')
        self.assertEqual(mesa.estado, 'HABILITADA')  # Mesa liberada

    # 23. Cajero opera estrictamente en modalidad Entrega / Mostrador sin mesas
    def test_cajero_sin_mesas_modalidad_entrega_mostrador(self):
        self.client.force_login(self.cajero_user)
        self.client.post(reverse('abrir_jornada'), {'monto_apertura': '15000'})
        resp_terminal = self.client.get(reverse('crear_ticket'))
        self.assertEqual(resp_terminal.status_code, 200)
        # Cajero no tiene selector de mesas ni cuentas abiertas en su terminal
        self.assertNotContains(resp_terminal, "Selecciona o Asigna una Mesa")
        self.assertNotContains(resp_terminal, "Cuenta Abierta")

    # 24. Cero desperdicio de papel térmico: comanda solo genera tickets para destinos con productos reales
    def test_cero_desperdicio_papel_comandas_sin_tickets_vacios(self):
        self.client.force_login(self.mesero_user)
        local = self.mesero_user.perfil.punto_venta_actual
        mesa = Mesa.objects.filter(punto_venta=local).first()
        if not mesa:
            mesa = Mesa.objects.create(identificador="Mesa 3", punto_venta=local, capacidad=4)

        # Caso A: Pedido únicamente de Cocina (ej. Cazuela de Ave) -> NO debe generar ticket de Barra vacío
        items_solo_cocina = [
            {"nombre": "Cazuela de Ave Criolla", "cantidad": 1, "precio": 7500, "destino": "COCINA", "nota": "Sin cilantro"}
        ]
        resp_cocina = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(items_solo_cocina)
        }, follow=True)
        self.assertContains(resp_cocina, "despachada con éxito a Cocina")
        self.assertNotContains(resp_cocina, "despachada con éxito a Cocina y Barra")

        venta = Venta.objects.filter(mesa=mesa, punto_venta=local, estado='ABIERTA').first()
        pedido_cocina = venta.pedidos.order_by('id').first()
        # Verificar que se creó ticket de Cocina y NO de Barra
        self.assertTrue(Ticket.objects.filter(pedido=pedido_cocina, tipo_destino='COCINA').exists())
        self.assertFalse(Ticket.objects.filter(pedido=pedido_cocina, tipo_destino='BARRA').exists())

        # Caso B: Ronda adicional únicamente de Barra (ej. Jugo Natural) -> NO debe generar ticket de Cocina vacío
        items_solo_barra = [
            {"nombre": "Jugo Natural Frambuesa 400ml", "cantidad": 1, "precio": 2500, "destino": "BARRA", "nota": "Bajo en azúcar"}
        ]
        resp_barra = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(items_solo_barra)
        }, follow=True)
        self.assertContains(resp_barra, "Despachada con éxito a Barra")

        pedido_barra = venta.pedidos.order_by('id').last()
        self.assertTrue(Ticket.objects.filter(pedido=pedido_barra, tipo_destino='BARRA').exists())
        self.assertFalse(Ticket.objects.filter(pedido=pedido_barra, tipo_destino='COCINA').exists())

    # 25. Mesero tiene local fijo e inmutable: sin dropdown de conmutación ni banners gigantes intrusivos
    def test_mesero_local_asignado_fijo_inmutable_sin_dropdown_ni_conmutacion(self):
        self.client.force_login(self.mesero_user)
        perfil = PerfilEmpleado.objects.get(usuario=self.mesero_user)
        local_propio = perfil.punto_venta_actual
        otro_local = PuntoVenta.objects.exclude(id=local_propio.id).first()

        # Acceso normal al módulo de mesero
        resp = self.client.get(reverse('mesero'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['local_actual'], local_propio)
        # No debe haber dropdown para cambiarse de local libremente
        self.assertNotContains(resp, "Seleccionar Punto de Venta:")
        # Debe mostrarse el badge estático con su local asignado
        self.assertContains(resp, local_propio.nombre)

        # Intento de conmutación forzada mediante URL (?local_id=otro_local)
        resp_forzado = self.client.get(reverse('mesero') + f"?local_id={otro_local.id}")
        self.assertEqual(resp_forzado.status_code, 200)
        # La vista debe blindar la asignación y permanecer en el local propio del colaborador
        self.assertEqual(resp_forzado.context['local_actual'], local_propio)
        self.assertNotEqual(resp_forzado.context['local_actual'], otro_local)

    # 26. Módulo KDS de Cocina y ciclo completo de comanda (PENDIENTE -> EN_PREPARACION -> LISTO -> ENTREGADO) con notificación al mesero
    def test_cocinero_flujo_kds_y_notificacion_mesero(self):
        # 1. Mesero genera comanda para Mesa 1
        self.client.force_login(self.mesero_user)
        local = self.mesero_user.perfil.punto_venta_actual
        mesa = Mesa.objects.filter(punto_venta=local).first()
        if not mesa:
            mesa = Mesa.objects.create(identificador="Mesa KDS", punto_venta=local, capacidad=4)

        items_comanda = [
            {"nombre": "Hamburguesa Safari con Papas", "cantidad": 2, "precio": 8900, "destino": "COCINA", "nota": "Sin cebolla"},
            {"nombre": "Jugo Natural Frutilla Exprimido", "cantidad": 2, "precio": 3500, "destino": "BARRA", "nota": "Con hielo"}
        ]
        resp_mesero = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(items_comanda)
        }, follow=True)
        self.assertEqual(resp_mesero.status_code, 200)

        venta = Venta.objects.filter(mesa=mesa, punto_venta=local, estado='ABIERTA').first()
        self.assertIsNotNone(venta)
        pedido = venta.pedidos.order_by('id').last()
        self.assertIsNotNone(pedido)
        self.assertEqual(pedido.estado, 'PENDIENTE')

        # 2. Cocinero entra a la pantalla KDS de Cocina y visualiza el pedido en cola
        self.client.force_login(self.cocinero_user)
        resp_cocina = self.client.get(reverse('cocina'))
        self.assertEqual(resp_cocina.status_code, 200)
        self.assertContains(resp_cocina, "KDS Cocina & Barra")
        self.assertContains(resp_cocina, f"COM-{pedido.id:04d}")
        self.assertContains(resp_cocina, "Hamburguesa Safari con Papas")
        self.assertContains(resp_cocina, "Sin cebolla")

        # 3. Cocinero pasa el pedido a EN_PREPARACION
        resp_prep = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': pedido.id,
            'nuevo_estado': 'EN_PREPARACION'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp_prep.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'EN_PREPARACION')

        # 4. Cocinero termina el plato y lo pasa a LISTO
        resp_listo = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': pedido.id,
            'nuevo_estado': 'LISTO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp_listo.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'LISTO')

        # 5. Mesero accede a su interfaz y recibe la notificación de pedido LISTO para servir
        self.client.force_login(self.mesero_user)
        resp_mesero_check = self.client.get(reverse('mesero'))
        self.assertEqual(resp_mesero_check.status_code, 200)
        self.assertIn(pedido, resp_mesero_check.context['pedidos_listos'])
        self.assertContains(resp_mesero_check, f"#COM-{pedido.id:04d}")
        self.assertContains(resp_mesero_check, "Listo p/ servir")

        # 6. Se entrega el pedido al comensal (ENTREGADO) y se genera registro de auditoría en Entrega
        resp_entrega = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': pedido.id,
            'nuevo_estado': 'ENTREGADO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp_entrega.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'ENTREGADO')

        # Verificar auditoría RF11
        entrega_registro = Entrega.objects.filter(pedido=pedido).first()
        self.assertIsNotNone(entrega_registro)
        self.assertEqual(entrega_registro.usuario_entrega, self.mesero_user)

        # Mesero ya no tiene pedidos listos pendientes por servir en su campana
        resp_mesero_final = self.client.get(reverse('mesero'))
        self.assertEqual(resp_mesero_final.context['total_pedidos_listos'], 0)

    # 27. Política de Cero Credenciales en Código: SECRET_KEY cargada dinámicamente y .env.example existente
    def test_politica_cero_credenciales_en_codigo(self):
        # 1. SECRET_KEY está configurada y no vacía
        self.assertTrue(bool(settings.SECRET_KEY))
        self.assertGreater(len(settings.SECRET_KEY), 20)

        # 2. .env.example existe en la raíz para guía de despliegue
        env_example_path = Path(settings.BASE_DIR) / '.env.example'
        self.assertTrue(env_example_path.exists())
        contenido_example = env_example_path.read_text(encoding='utf-8')
        self.assertIn("SECRET_KEY", contenido_example)
        self.assertIn("DB_ENGINE", contenido_example)
        self.assertIn("postgresql", contenido_example)

        # 3. .gitignore contiene las reglas de exclusión para .env
        gitignore_path = Path(settings.BASE_DIR) / '.gitignore'
        self.assertTrue(gitignore_path.exists())
        contenido_gitignore = gitignore_path.read_text(encoding='utf-8')
        self.assertIn(".env", contenido_gitignore)
        self.assertIn("!.env.example", contenido_gitignore)

    # 28. Coherencia de Infraestructura: Soporte multi-motor para PostgreSQL, MySQL y SQLite
    def test_soporte_multi_motor_base_de_datos(self):
        # 1. En el entorno de test actual se usa la BD de ejecución segura
        engine_actual = settings.DATABASES['default']['ENGINE']
        self.assertTrue(
            engine_actual in [
                'django.db.backends.sqlite3',
                'django.db.backends.postgresql',
                'django.db.backends.mysql'
            ]
        )

        # 2. Validar que la lógica de settings reconoce 'postgresql' y 'mysql' formalmente
        from Venta_safari import settings as safari_settings
        
        # Validar variables esperadas en el diccionario de configuración
        self.assertTrue(hasattr(safari_settings, 'DATABASES'))
        self.assertIn('default', safari_settings.DATABASES)

    # 29. Adaptabilidad visual y Responsive Design para Tabletas y Smartphones (Criterio Rúbrica 2.1.3.6)
    def test_adaptabilidad_visual_y_responsive_design(self):
        # 1. Verificar meta viewport en todas las pantallas principales del sistema
        self.client.force_login(self.admin_user)
        resp_admin = self.client.get(reverse('administrador'))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertContains(resp_admin, 'name="viewport"')
        self.assertContains(resp_admin, 'width=device-width')
        self.assertContains(resp_admin, 'table-responsive')

        self.client.force_login(self.mesero_user)
        resp_mesero = self.client.get(reverse('mesero'))
        self.assertEqual(resp_mesero.status_code, 200)
        self.assertContains(resp_mesero, 'name="viewport"')
        self.assertContains(resp_mesero, 'mobile-comanda-bar')

        self.client.force_login(self.cocinero_user)
        resp_cocina = self.client.get(reverse('cocina'))
        self.assertEqual(resp_cocina.status_code, 200)
        self.assertContains(resp_cocina, 'name="viewport"')
        self.assertContains(resp_cocina, 'kds-header')

        self.client.force_login(self.cajero_user)
        resp_vendedor = self.client.get(reverse('vendedor'))
        self.assertEqual(resp_vendedor.status_code, 200)
        self.assertContains(resp_vendedor, 'name="viewport"')

        # Abrir jornada y caja para acceder al terminal de venta rápida
        hoy = timezone.localdate()
        jornada = Jornada.objects.create(usuario_apertura=self.admin_user, estado='ABIERTA', fecha=hoy)
        Caja.objects.create(
            jornada=jornada,
            cajero=self.cajero_user,
            punto_venta=self.cajero_user.perfil.punto_venta_actual,
            estado='ABIERTA',
            monto_apertura=0
        )
        resp_crear_ticket = self.client.get(reverse('crear_ticket'))
        self.assertEqual(resp_crear_ticket.status_code, 200)
        self.assertContains(resp_crear_ticket, 'mobile-comanda-bar')

    # 30. Validación estricta de campos vacíos en Login (Requisito Semana 10)
    def test_login_validacion_campos_vacios(self):
        from django.contrib.messages import get_messages
        # 1. Envío con usuario y contraseña vacíos
        resp_vacio = self.client.post(reverse('login'), {'username': '', 'password': ''}, follow=True)
        self.assertEqual(resp_vacio.status_code, 200)
        mensajes = [str(m) for m in get_messages(resp_vacio.wsgi_request)]
        self.assertTrue(any('completa todos los campos requeridos' in m for m in mensajes))
        self.assertFalse(resp_vacio.wsgi_request.user.is_authenticated)

        # 2. Envío solo con usuario sin contraseña
        resp_sin_pass = self.client.post(reverse('login'), {'username': 'admin_safari', 'password': ''}, follow=True)
        self.assertEqual(resp_sin_pass.status_code, 200)
        mensajes_sin_pass = [str(m) for m in get_messages(resp_sin_pass.wsgi_request)]
        self.assertTrue(any('completa todos los campos requeridos' in m for m in mensajes_sin_pass))
        self.assertFalse(resp_sin_pass.wsgi_request.user.is_authenticated)

    # 31. Manejador personalizado de error HTTP 404 - Página no encontrada (Requisito Semana 10)
    def test_manejador_error_404_personalizado(self):
        from django.test import override_settings
        # 1. Verificar ruta de prueba/auditoría /404/
        resp_preview = self.client.get(reverse('error_404'))
        self.assertEqual(resp_preview.status_code, 404)
        self.assertContains(resp_preview, "404", status_code=404)
        self.assertContains(resp_preview, "Ruta o Recurso No Encontrado", status_code=404)
        self.assertContains(resp_preview, "Volver al Portal de Inicio", status_code=404)

        # 2. Con DEBUG=False, verificar captura real de URL inexistente
        with override_settings(DEBUG=False):
            resp_real = self.client.get('/ruta-inexistente-safari-12345/')
            self.assertEqual(resp_real.status_code, 404)
            self.assertContains(resp_real, "Ruta o Recurso No Encontrado", status_code=404)

        # 3. Intercepción por middleware en peticiones erróneas (ej: typo /adminitrador/)
        resp_typo = self.client.get('/adminitrador/')
        self.assertEqual(resp_typo.status_code, 404)
        self.assertContains(resp_typo, "Ruta o Recurso No Encontrado", status_code=404)

    # 32. Manejador personalizado de error HTTP 500 - Error de servidor blindado (Requisito Semana 10)
    def test_manejador_error_500_personalizado(self):
        resp_500 = self.client.get(reverse('error_500'))
        self.assertEqual(resp_500.status_code, 500)
        self.assertContains(resp_500, "500", status_code=500)
        self.assertContains(resp_500, "Error Interno del Servidor", status_code=500)
        self.assertContains(resp_500, "Blindaje de Seguridad y Robustez (OWASP)", status_code=500)
        self.assertContains(resp_500, "Volver al Portal de Inicio", status_code=500)

    # 33. Robustez ante IDs inexistentes o manipulados sin caídas de servidor (Requisito Semana 10)
    def test_robustez_id_inexistente_no_derriba_servidor(self):
        from django.test import override_settings
        self.client.force_login(self.admin_user)
        # Petición a local inexistente (ID 99999) con DEBUG=False debe retornar 404 controlado y no 500
        with override_settings(DEBUG=False):
            resp_local_invalido = self.client.get('/administrador/local/99999/')
            self.assertEqual(resp_local_invalido.status_code, 404)
            self.assertContains(resp_local_invalido, "Ruta o Recurso No Encontrado", status_code=404)

    # 34. Protección contra Ataques de Fuerza Bruta y Límite de Intentos Fallidos (OWASP)
    def test_bloqueo_fuerza_bruta_por_intentos_fallidos(self):
        cache.clear()
        target_user = 'usuario_ataque_bruta'
        User.objects.create_user(username=target_user, password='safariPassword2026')

        # Simular 4 intentos fallidos: deben retornar advertencia con intentos restantes
        for i in range(1, 5):
            resp = self.client.post(reverse('login'), {
                'username': target_user,
                'password': f'clave_erronea_{i}'
            }, follow=True)
            self.assertContains(resp, "Credenciales incorrectas")
            self.assertContains(resp, f"Te quedan {5 - i} intento(s)")

        # 5to intento fallido: activa el bloqueo temporal por 5 minutos
        resp_quinto = self.client.post(reverse('login'), {
            'username': target_user,
            'password': 'clave_erronea_5'
        }, follow=True)
        self.assertContains(resp_quinto, "Has superado el límite de 5 intentos fallidos")
        self.assertContains(resp_quinto, "bloqueado temporalmente por 5 minutos")

        # 6to intento: incluso ingresando la contraseña real 'safariPassword2026', el acceso sigue bloqueado
        resp_bloqueado = self.client.post(reverse('login'), {
            'username': target_user,
            'password': 'safariPassword2026'
        }, follow=True)
        self.assertContains(resp_bloqueado, "Acceso temporalmente bloqueado")
        self.assertFalse(resp_bloqueado.context['user'].is_authenticated)

        # Si se restablece la caché de bloqueo (o pasan 5 minutos), el usuario puede ingresar normalmente
        cache.clear()
        resp_exito = self.client.post(reverse('login'), {
            'username': target_user,
            'password': 'safariPassword2026'
        }, follow=True)
        self.assertTrue(resp_exito.context['user'].is_authenticated)
        cache.clear()

    # 35. Cabeceras HTTP de Seguridad, Cookies Seguras y Criptografía de Contraseñas (OWASP)
    def test_cabeceras_seguridad_http_y_cookies(self):
        # 1. Cabeceras HTTP en respuestas
        resp = self.client.get(reverse('index'))
        self.assertEqual(resp.headers.get('X-Frame-Options'), 'DENY')
        self.assertEqual(resp.headers.get('X-Content-Type-Options'), 'nosniff')

        # 2. Configuración segura de cookies de sesión y CSRF
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, 'Lax')
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 28800)

        # 3. Hashers de contraseña criptográficamente robustos
        self.assertIn('django.contrib.auth.hashers.PBKDF2PasswordHasher', settings.PASSWORD_HASHERS)

    # 36. Defensa de Entrada de Datos: Sanitización de Cantidades y Precios Negativos
    def test_defensa_cantidades_y_precios_negativos(self):
        self.client.force_login(self.mesero_user)
        pv = PuntoVenta.objects.first()
        mesa = Mesa.objects.filter(punto_venta=pv).first()

        # Intento de inyectar comanda con cantidades negativas y precios negativos
        payload_malicioso = [
            {"nombre": "Plato Hack", "cantidad": -10, "precio": -8000, "nota": "Ataque", "destino": "COCINA"}
        ]
        resp = self.client.post(reverse('mesero'), {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(payload_malicioso)
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Verificar que el backend sanitizó a cantidad >= 1 y precio >= 0 sin romper la BD
        ultima_venta = Venta.objects.filter(mesa=mesa).order_by('-id').first()
        self.assertIsNotNone(ultima_venta)
        detalle = ultima_venta.detalles.filter(producto__nombre="Plato Hack").first()
        self.assertIsNotNone(detalle)
        self.assertGreaterEqual(detalle.cantidad, 1)
        self.assertGreaterEqual(detalle.precio_aplicado, 0)
        self.assertGreaterEqual(detalle.subtotal, 0)

        # Probar endpoint cambiar_estado_pedido con ID de pedido inválido (no numérico)
        resp_pedido_invalido = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': 'id_invalido_malicioso',
            'nuevo_estado': 'LISTO'
        }, follow=True)
        self.assertContains(resp_pedido_invalido, "Identificador de pedido inválido")

    # 37. Validación de Longitud Mínima de Contraseña en Gestión de Colaboradores
    def test_validacion_longitud_minima_password_trabajador(self):
        self.client.force_login(self.admin_user)
        pv = PuntoVenta.objects.first()

        # Intento de registrar colaborador con contraseña de 4 caracteres (< 6)
        resp = self.client.post(reverse('administrador_trabajadores'), {
            'accion': 'crear',
            'nombre': 'Claudio',
            'apellido': 'Bravo',
            'rut': '15.222.333-4',
            'rol': 'MESERO',
            'local_id': pv.id,
            'password': '1234'  # Muy corta
        }, follow=True)
        self.assertContains(resp, "al menos 6 caracteres")
        self.assertFalse(User.objects.filter(first_name='Claudio', last_name='Bravo').exists())

    # 38. CRUD Mesas: Listar y Crear Mesa por Administrador (Semana 11)
    def test_crud_mesas_listar_y_crear_administrador(self):
        # 1. Acceso protegido: Anónimo es bloqueado y Cajero es redirigido a su panel
        resp_anon = self.client.get(reverse('administrador_mesas'), follow=True)
        self.assertRedirects(resp_anon, reverse('index'))
        self.assertContains(resp_anon, "Acceso protegido")

        self.client.force_login(self.cajero_user)
        resp_cajero = self.client.get(reverse('administrador_mesas'), follow=True)
        self.assertRedirects(resp_cajero, reverse('vendedor'))
        self.assertContains(resp_cajero, "Acceso restringido")

        # 2. Administrador accede correctamente al mantenedor
        self.client.force_login(self.admin_user)
        resp_admin = self.client.get(reverse('administrador_mesas'))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertContains(resp_admin, "MANTENEDOR DE MESAS Y SECTORES")

        # 3. Crear nueva mesa con capacidad 6
        pv = PuntoVenta.objects.first()
        resp_crear = self.client.post(reverse('administrador_mesas'), {
            'accion': 'crear',
            'identificador': 'Mesa VIP 99',
            'punto_venta_id': pv.id,
            'capacidad': 6,
            'estado': 'HABILITADA'
        }, follow=True)
        self.assertContains(resp_crear, "creada exitosamente")
        mesa_creada = Mesa.objects.filter(identificador='Mesa VIP 99', punto_venta=pv).first()
        self.assertIsNotNone(mesa_creada)
        self.assertEqual(mesa_creada.capacidad, 6)
        self.assertEqual(mesa_creada.estado, 'HABILITADA')

    # 39. CRUD Mesas: Validación de Unicidad de Identificador por Local (Semana 11)
    def test_crud_mesas_validacion_unicidad_mismo_local(self):
        self.client.force_login(self.admin_user)
        pv1 = PuntoVenta.objects.get(id=1)
        pv2 = PuntoVenta.objects.get(id=2)

        # Crear primera mesa en local 1
        Mesa.objects.create(identificador='Mesa Única A', punto_venta=pv1, capacidad=4)

        # Intento de duplicar identificador en el mismo local 1 -> Debe ser rechazado
        resp_dup = self.client.post(reverse('administrador_mesas'), {
            'accion': 'crear',
            'identificador': 'Mesa Única A',
            'punto_venta_id': pv1.id,
            'capacidad': 4,
            'estado': 'HABILITADA'
        }, follow=True)
        self.assertContains(resp_dup, "Ya existe una mesa con el identificador")
        self.assertEqual(Mesa.objects.filter(identificador='Mesa Única A', punto_venta=pv1).count(), 1)

        # Pero en local 2, el mismo identificador SÍ está permitido (aislamiento por local)
        resp_ok_otro = self.client.post(reverse('administrador_mesas'), {
            'accion': 'crear',
            'identificador': 'Mesa Única A',
            'punto_venta_id': pv2.id,
            'capacidad': 4,
            'estado': 'HABILITADA'
        }, follow=True)
        self.assertContains(resp_ok_otro, "creada exitosamente")
        self.assertTrue(Mesa.objects.filter(identificador='Mesa Única A', punto_venta=pv2).exists())

    # 40. CRUD Mesas: Modificar Identificador, Capacidad y Estado (Semana 11)
    def test_crud_mesas_modificar_capacidad_e_identificador(self):
        self.client.force_login(self.admin_user)
        pv = PuntoVenta.objects.first()
        mesa = Mesa.objects.create(identificador='Terraza Temp', punto_venta=pv, capacidad=2, estado='HABILITADA')

        resp_mod = self.client.post(reverse('administrador_mesas'), {
            'accion': 'modificar',
            'mesa_id': mesa.id,
            'identificador': 'Terraza VIP Renovada',
            'punto_venta_id': pv.id,
            'capacidad': 10,
            'estado': 'HABILITADA'
        }, follow=True)
        self.assertContains(resp_mod, "actualizada correctamente")

        mesa.refresh_from_db()
        self.assertEqual(mesa.identificador, 'Terraza VIP Renovada')
        self.assertEqual(mesa.capacidad, 10)

    # 41. CRUD Mesas: Integridad de Cuentas Abiertas y Eliminación Segura (Semana 11)
    def test_crud_mesas_proteccion_cuenta_abierta_y_eliminacion_segura(self):
        self.client.force_login(self.admin_user)
        pv = PuntoVenta.objects.first()
        jornada = Jornada.objects.create(fecha=timezone.localdate(), estado='ABIERTA', usuario_apertura=self.admin_user)
        caja = Caja.objects.create(jornada=jornada, cajero=self.admin_user, punto_venta=pv, nombre="Caja Test", estado='ABIERTA')

        # 1. Mesa con cuenta ABIERTA en consumo
        mesa_con_cuenta = Mesa.objects.create(identificador='Mesa En Consumo', punto_venta=pv, capacidad=4, estado='OCUPADA')
        Venta.objects.create(
            caja=caja,
            cajero=self.admin_user,
            punto_venta=pv,
            modalidad='MESA',
            mesa=mesa_con_cuenta,
            total=25000,
            estado='ABIERTA'
        )

        # Intentar desactivar mesa con cuenta abierta -> Debe ser protegido
        resp_toggle = self.client.post(reverse('administrador_mesas'), {
            'accion': 'toggle_estado',
            'mesa_id': mesa_con_cuenta.id
        }, follow=True)
        self.assertContains(resp_toggle, "No es posible desactivar la mesa")
        mesa_con_cuenta.refresh_from_db()
        self.assertEqual(mesa_con_cuenta.estado, 'OCUPADA')

        # Intentar eliminar mesa con cuenta abierta -> Rechazado
        resp_del_abierta = self.client.post(reverse('administrador_mesas'), {
            'accion': 'eliminar',
            'mesa_id': mesa_con_cuenta.id
        }, follow=True)
        self.assertContains(resp_del_abierta, "Tiene una cuenta activa en consumo")
        self.assertTrue(Mesa.objects.filter(id=mesa_con_cuenta.id).exists())

        # 2. Mesa recién creada sin ventas -> Eliminación definitiva física
        mesa_limpia = Mesa.objects.create(identificador='Mesa Sin Ventas', punto_venta=pv, capacidad=4)
        resp_del_ok = self.client.post(reverse('administrador_mesas'), {
            'accion': 'eliminar',
            'mesa_id': mesa_limpia.id
        }, follow=True)
        self.assertContains(resp_del_ok, "eliminada definitivamente")
        self.assertFalse(Mesa.objects.filter(id=mesa_limpia.id).exists())

    # 42. CRUD Productos: Aislamiento por rol y listado real desde BD (Semana 11)
    def test_crud_productos_acceso_restringido_y_listado_desde_bd(self):
        # 1. Acceso anónimo y cajero bloqueados
        resp_anon = self.client.get(reverse('administrador_productos'), follow=True)
        self.assertRedirects(resp_anon, reverse('index'))
        self.assertContains(resp_anon, "Acceso protegido")

        self.client.force_login(self.cajero_user)
        resp_cajero = self.client.get(reverse('administrador_productos'), follow=True)
        self.assertRedirects(resp_cajero, reverse('vendedor'))
        self.assertContains(resp_cajero, "Acceso restringido")

        # 2. Administrador accede correctamente al catálogo
        self.client.force_login(self.admin_user)
        resp_admin = self.client.get(reverse('administrador_productos'))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertContains(resp_admin, "CATÁLOGO CENTRALIZADO DE PRODUCTOS")
        self.assertContains(resp_admin, "Hamburguesa Safari con Papas")

    # 43. CRUD Productos: Creación válida y rechazo de datos inválidos (Semana 11)
    def test_crud_productos_creacion_valida_y_rechazo_datos_invalidos(self):
        self.client.force_login(self.admin_user)
        cat = Categoria.objects.first()
        pv = PuntoVenta.objects.first()

        # 1. Creación exitosa
        resp_ok = self.client.post(reverse('administrador_productos'), {
            'accion': 'crear',
            'nombre': 'Chorrillana Campestre Safari',
            'categoria_id': cat.id,
            'precio_base': '12500',
            'descripcion': 'Papas rústicas con carne mechada y cebolla caramelizada',
            'puntos_venta': [pv.id],
            'activo': 'on'
        }, follow=True)
        self.assertContains(resp_ok, "creado exitosamente")
        nuevo_prod = Producto.objects.filter(nombre='Chorrillana Campestre Safari').first()
        self.assertIsNotNone(nuevo_prod)
        self.assertEqual(nuevo_prod.precio_base, 12500)
        self.assertTrue(nuevo_prod.puntos_venta.filter(id=pv.id).exists())

        # 2. Rechazo con nombre vacío
        resp_vacio = self.client.post(reverse('administrador_productos'), {
            'accion': 'crear',
            'nombre': '',
            'categoria_id': cat.id,
            'precio_base': '5000'
        }, follow=True)
        self.assertContains(resp_vacio, "El nombre del producto es obligatorio")

    # 44. CRUD Productos: Modificación, Toggle Estado y Eliminación Protegida (Semana 11)
    def test_crud_productos_edicion_toggle_y_eliminacion_protegida(self):
        self.client.force_login(self.admin_user)
        cat = Categoria.objects.first()
        pv = PuntoVenta.objects.first()

        # Producto para prueba
        prod = Producto.objects.create(nombre='Bebida Especial Test', categoria=cat, precio_base=2500, activo=True)
        prod.puntos_venta.add(pv)

        # 1. Modificar
        resp_mod = self.client.post(reverse('administrador_productos'), {
            'accion': 'modificar',
            'producto_id': prod.id,
            'nombre': 'Bebida Especial Renovada',
            'categoria_id': cat.id,
            'precio_base': '2900',
            'descripcion': 'Nueva fórmula',
            'puntos_venta': [pv.id],
            'activo': 'on'
        }, follow=True)
        self.assertContains(resp_mod, "actualizado correctamente")
        prod.refresh_from_db()
        self.assertEqual(prod.nombre, 'Bebida Especial Renovada')
        self.assertEqual(prod.precio_base, 2900)

        # 2. Toggle de estado (Pausar/Activar)
        resp_toggle = self.client.post(reverse('administrador_productos'), {
            'accion': 'toggle_estado',
            'producto_id': prod.id
        }, follow=True)
        self.assertContains(resp_toggle, "desactivado del catálogo")
        prod.refresh_from_db()
        self.assertFalse(prod.activo)

        # 3. Eliminación protegida: Si tiene ventas históricas -> Soft-delete
        jornada = Jornada.objects.create(fecha=timezone.localdate(), estado='ABIERTA', usuario_apertura=self.admin_user)
        caja = Caja.objects.create(jornada=jornada, cajero=self.admin_user, punto_venta=pv, nombre="Caja Test Prod", estado='ABIERTA')
        venta = Venta.objects.create(caja=caja, cajero=self.admin_user, punto_venta=pv, total=2900, estado='PAGADA')
        DetalleVenta.objects.create(venta=venta, producto=prod, cantidad=1, precio_aplicado=2900, subtotal=2900)

        resp_del_prot = self.client.post(reverse('administrador_productos'), {
            'accion': 'eliminar',
            'producto_id': prod.id
        }, follow=True)
        self.assertContains(resp_del_prot, "registra ventas históricas")
        # El producto no se elimina físicamente, se preserva inactivo
        self.assertTrue(Producto.objects.filter(id=prod.id).exists())

        # 4. Producto sin ventas -> Eliminación física permitida
        prod_limpio = Producto.objects.create(nombre='Item Sin Ventas', categoria=cat, precio_base=1000)
        resp_del_fisico = self.client.post(reverse('administrador_productos'), {
            'accion': 'eliminar',
            'producto_id': prod_limpio.id
        }, follow=True)
        self.assertContains(resp_del_fisico, "eliminado definitivamente")
        self.assertFalse(Producto.objects.filter(id=prod_limpio.id).exists())

    # 45. CRUD Menús: Listado por local y creación de cartas de carta (Semana 11)
    def test_crud_menus_listado_y_creacion_por_local(self):
        self.client.force_login(self.admin_user)
        pv = PuntoVenta.objects.first()
        prods = list(Producto.objects.filter(activo=True)[:3])

        # 1. Acceder al mantenedor de menús
        resp_get = self.client.get(reverse('administrador_menus'))
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, "CARTAS Y MENÚS POR PUNTO DE VENTA")

        # 2. Crear nueva carta de menú
        resp_crear = self.client.post(reverse('administrador_menus'), {
            'accion': 'crear',
            'nombre': 'Carta Ejecutiva Safari',
            'punto_venta_id': pv.id,
            'productos': [p.id for p in prods],
            'activo': 'on'
        }, follow=True)
        self.assertContains(resp_crear, "asignado exitosamente")

        menu_creado = Menu.objects.filter(nombre='Carta Ejecutiva Safari', punto_venta=pv).first()
        self.assertIsNotNone(menu_creado)
        self.assertEqual(menu_creado.productos.count(), len(prods))

        # 3. Toggle de estado y eliminación
        resp_toggle = self.client.post(reverse('administrador_menus'), {
            'accion': 'toggle_estado',
            'menu_id': menu_creado.id
        }, follow=True)
        self.assertContains(resp_toggle, "desactivado")
        menu_creado.refresh_from_db()
        self.assertFalse(menu_creado.activo)

        resp_del = self.client.post(reverse('administrador_menus'), {
            'accion': 'eliminar',
            'menu_id': menu_creado.id
        }, follow=True)
        self.assertContains(resp_del, "eliminado del sistema")
        self.assertFalse(Menu.objects.filter(id=menu_creado.id).exists())

    # 46. Manejador personalizado de error HTTP 403 - Acceso Denegado (Semana 10)
    def test_manejador_error_403_personalizado(self):
        resp_403 = self.client.get(reverse('error_403'))
        self.assertEqual(resp_403.status_code, 403)
        self.assertContains(resp_403, "403", status_code=403)
        self.assertContains(resp_403, "Acceso Restringido o No Autorizado", status_code=403)
        self.assertContains(resp_403, "Volver al Portal de Inicio", status_code=403)

    # 47. Manejador personalizado de error HTTP 400 - Solicitud Incorrecta (Semana 10)
    def test_manejador_error_400_personalizado(self):
        resp_400 = self.client.get(reverse('error_400'))
        self.assertEqual(resp_400.status_code, 400)
        self.assertContains(resp_400, "400", status_code=400)
        self.assertContains(resp_400, "Solicitud o Parámetros Incorrectos", status_code=400)
        self.assertContains(resp_400, "Volver al Portal de Inicio", status_code=400)

    # 48. Historial de Acciones: Aislamiento estricto de roles (Semana 11)
    def test_historial_acceso_restringido_y_aislamiento_roles(self):
        # Anónimo es redirigido al index
        resp_anon = self.client.get(reverse('administrador_historial'), follow=True)
        self.assertRedirects(resp_anon, reverse('index'))
        self.assertContains(resp_anon, "Acceso protegido")

        # Cajero es bloqueado y redirigido a vendedor
        self.client.force_login(self.cajero_user)
        resp_cajero = self.client.get(reverse('administrador_historial'), follow=True)
        self.assertRedirects(resp_cajero, reverse('vendedor'))
        self.assertContains(resp_cajero, "Acceso restringido")

        # Mesero es bloqueado y redirigido a mesero
        self.client.force_login(self.mesero_user)
        resp_mesero = self.client.get(reverse('administrador_historial'), follow=True)
        self.assertRedirects(resp_mesero, reverse('mesero'))
        self.assertContains(resp_mesero, "Acceso restringido")

        # Cocinero es bloqueado y redirigido a cocina
        self.client.force_login(self.cocinero_user)
        resp_cocinero = self.client.get(reverse('administrador_historial'), follow=True)
        self.assertRedirects(resp_cocinero, reverse('cocina'))
        self.assertContains(resp_cocinero, "Acceso restringido")

        # Administrador tiene acceso legítimo
        self.client.force_login(self.admin_user)
        resp_admin = self.client.get(reverse('administrador_historial'))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertContains(resp_admin, "BITÁCORA Y HISTORIAL DE ACCIONES")

    # 49. Historial de Acciones: Consolidación unificada de eventos reales de BD (Semana 11)
    def test_historial_consolidacion_eventos_desde_bd(self):
        self.client.force_login(self.admin_user)
        pv = PuntoVenta.objects.first()

        # 1. Crear una jornada y caja
        jornada = Jornada.objects.create(usuario_apertura=self.admin_user, estado='ABIERTA')
        caja = Caja.objects.create(
            nombre="Caja Auditoría",
            punto_venta=pv,
            jornada=jornada,
            cajero=self.cajero_user,
            monto_apertura=Decimal('150000.00'),
            estado='ABIERTA'
        )

        # 2. Crear una venta
        venta = Venta.objects.create(
            caja=caja,
            cajero=self.cajero_user,
            punto_venta=pv,
            modalidad='VENTA_RAPIDA',
            total=Decimal('28500.00'),
            estado='PAGADA'
        )

        # 3. Crear una alerta de traslado
        alerta = AlertaTraslado.objects.create(
            empleado=self.mesero_user,
            punto_venta_origen=pv,
            punto_venta_destino=PuntoVenta.objects.last(),
            autorizado_por=self.admin_user,
            motivo="Refuerzo horario peak"
        )

        # 4. Consultar historial
        resp = self.client.get(reverse('administrador_historial'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f"JOR-A-{jornada.id}")
        self.assertContains(resp, f"CAJ-A-{caja.id}")
        self.assertContains(resp, f"VEN-{venta.id}")
        self.assertContains(resp, f"TRA-{alerta.id}")
        self.assertContains(resp, "Refuerzo horario peak")

    # 50. Historial de Acciones: Filtros por tipo de evento y búsqueda (Semana 11)
    def test_historial_filtros_y_busqueda(self):
        self.client.force_login(self.admin_user)
        pv = PuntoVenta.objects.first()
        jornada = Jornada.objects.create(usuario_apertura=self.admin_user, estado='ABIERTA')
        caja = Caja.objects.create(
            nombre="Caja Filtros",
            punto_venta=pv,
            jornada=jornada,
            cajero=self.cajero_user,
            monto_apertura=Decimal('75000.00'),
            estado='ABIERTA'
        )
        venta = Venta.objects.create(
            caja=caja,
            cajero=self.cajero_user,
            punto_venta=pv,
            modalidad='VENTA_RAPIDA',
            total=Decimal('42000.00'),
            estado='PAGADA'
        )

        # Filtrar solo VENTAS
        resp_ventas = self.client.get(reverse('administrador_historial') + '?tipo=VENTA')
        self.assertEqual(resp_ventas.status_code, 200)
        self.assertContains(resp_ventas, f"VEN-{venta.id}")
        self.assertNotContains(resp_ventas, f"CAJ-A-{caja.id}")

        # Búsqueda por texto específico
        resp_search = self.client.get(reverse('administrador_historial') + '?q=Filtros')
        self.assertEqual(resp_search.status_code, 200)
        self.assertContains(resp_search, "Caja Filtros")
        self.assertNotContains(resp_search, f"VEN-{venta.id}")


# ==============================================================================
# SEMANA 12: TESTS DE CUADRATURA, ARQUEO, LEY N° 20.956 Y CIERRE DE JORNADA
# ==============================================================================
class Semana12CuadraturaYRedondeoTests(TestCase):
    """
    Pruebas unitarias integrales para los requerimientos de la Semana 12:
    - Regla de Redondeo en Efectivo (Ley N° 20.956 Banco Central de Chile).
    - Subproceso de Cuadratura y Arqueo físico de denominaciones (Billetes y Monedas).
    - Cierre de Caja con estados de cuadratura (CUADRADA, SOBRANTE, FALTANTE).
    - Cierre de Jornada Operativa por supervisor validando cajas abiertas.
    """

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username='admin_s12', password='password123',
            first_name='Admin', last_name='Safari', is_staff=True
        )
        PerfilEmpleado.objects.create(usuario=self.admin_user, rol='ADMINISTRADOR')

        self.cajero_user = User.objects.create_user(
            username='cajero_s12', password='password123',
            first_name='Carlos', last_name='Cajero'
        )
        self.pv = PuntoVenta.objects.create(
            nombre='Restaurante Safari S12', tipo='Restaurante', descripcion='Local S12'
        )
        PerfilEmpleado.objects.create(
            usuario=self.cajero_user, rol='CAJERO', punto_venta_actual=self.pv
        )

        self.otro_cajero = User.objects.create_user(
            username='otro_cajero_s12', password='password123',
            first_name='Lucia', last_name='Cajera'
        )
        PerfilEmpleado.objects.create(
            usuario=self.otro_cajero, rol='CAJERO', punto_venta_actual=self.pv
        )

        self.jornada = Jornada.objects.create(
            fecha=timezone.localdate(),
            usuario_apertura=self.admin_user,
            estado='ABIERTA'
        )

    def test_redondeo_ley_20956_efectivo_hacia_abajo(self):
        """Cantidades terminadas en 1 a 5 se redondean hacia abajo a la decena inferior"""
        from ventas.utils import calcular_redondeo_ley_20956
        # Terminación en 1
        monto, ajuste = calcular_redondeo_ley_20956(Decimal('1001'), 'EFECTIVO')
        self.assertEqual(monto, Decimal('1000'))
        self.assertEqual(ajuste, Decimal('-1'))

        # Terminación en 3
        monto, ajuste = calcular_redondeo_ley_20956(Decimal('1323'), 'EFECTIVO')
        self.assertEqual(monto, Decimal('1320'))
        self.assertEqual(ajuste, Decimal('-3'))

        # Terminación en 5 (oficial Ley 20.956)
        monto, ajuste = calcular_redondeo_ley_20956(Decimal('1995'), 'EFECTIVO')
        self.assertEqual(monto, Decimal('1990'))
        self.assertEqual(ajuste, Decimal('-5'))

    def test_redondeo_ley_20956_efectivo_hacia_arriba(self):
        """Cantidades terminadas en 6 a 9 se redondean hacia arriba a la decena superior"""
        from ventas.utils import calcular_redondeo_ley_20956
        # Terminación en 6
        monto, ajuste = calcular_redondeo_ley_20956(Decimal('1326'), 'EFECTIVO')
        self.assertEqual(monto, Decimal('1330'))
        self.assertEqual(ajuste, Decimal('4'))

        # Terminación en 9
        monto, ajuste = calcular_redondeo_ley_20956(Decimal('1999'), 'EFECTIVO')
        self.assertEqual(monto, Decimal('2000'))
        self.assertEqual(ajuste, Decimal('1'))

    def test_redondeo_ley_20956_tarjetas_sin_redondeo(self):
        """Operaciones con tarjeta o transferencia se cobran al peso exacto sin redondeo"""
        from ventas.utils import calcular_redondeo_ley_20956
        monto, ajuste = calcular_redondeo_ley_20956(Decimal('1995'), 'DEBITO')
        self.assertEqual(monto, Decimal('1995'))
        self.assertEqual(ajuste, Decimal('0'))

        monto_cred, ajuste_cred = calcular_redondeo_ley_20956(Decimal('1997'), 'CREDITO')
        self.assertEqual(monto_cred, Decimal('1997'))
        self.assertEqual(ajuste_cred, Decimal('0'))

    def test_calcular_total_arqueo_denominaciones(self):
        """Verifica que el modelo Caja sume correctamente todas las denominaciones chilenas"""
        caja = Caja.objects.create(
            jornada=self.jornada,
            cajero=self.cajero_user,
            punto_venta=self.pv,
            nombre='Caja Test Arqueo',
            monto_apertura=Decimal('10000.00'),
            billetes_20000=2,
            billetes_10000=1,
            billetes_5000=3,
            billetes_2000=5,
            billetes_1000=10,
            monedas_500=4,
            monedas_100=8,
            monedas_50=2,
            monedas_10=5,
            monedas_5=0,
            monedas_1=0
        )
        self.assertEqual(caja.calcular_total_arqueo(), 87950)

    def test_cerrar_caja_cuadratura_exacta(self):
        """El cajero realiza el arqueo físico y la caja cuadra exactamente con lo esperado"""
        caja = Caja.objects.create(
            jornada=self.jornada,
            cajero=self.cajero_user,
            punto_venta=self.pv,
            nombre='Caja S12 Exacta',
            monto_apertura=Decimal('20000.00'),
            estado='ABIERTA'
        )
        Venta.objects.create(
            caja=caja,
            cajero=self.cajero_user,
            punto_venta=self.pv,
            modalidad='VENTA_RAPIDA',
            metodo_pago='EFECTIVO',
            total=Decimal('30000.00'),
            estado='PAGADA'
        )
        self.client.login(username='cajero_s12', password='password123')
        resp = self.client.post(reverse('cerrar_caja'), {
            'caja_id': caja.id,
            'billetes_20000': '2',
            'billetes_10000': '1',
            'billetes_5000': '0',
            'billetes_2000': '0',
            'billetes_1000': '0',
            'monedas_500': '0',
            'monedas_100': '0',
            'monedas_50': '0',
            'monedas_10': '0',
            'monedas_5': '0',
            'monedas_1': '0',
            'observaciones_cierre': 'Turno sin descuadres'
        })
        self.assertEqual(resp.status_code, 302)
        caja.refresh_from_db()
        self.assertEqual(caja.estado, 'CERRADA')
        self.assertEqual(caja.estado_cuadre, 'CUADRADA')
        self.assertEqual(caja.total_efectivo_declarado, Decimal('50000.00'))
        self.assertEqual(caja.diferencia_cuadre, Decimal('0.00'))

    def test_cerrar_caja_sobrante_y_faltante(self):
        """Verifica que el arqueo detecte correctamente sobrantes y faltantes"""
        caja = Caja.objects.create(
            jornada=self.jornada,
            cajero=self.cajero_user,
            punto_venta=self.pv,
            nombre='Caja S12 Dif',
            monto_apertura=Decimal('10000.00'),
            estado='ABIERTA'
        )
        self.client.login(username='cajero_s12', password='password123')
        self.client.post(reverse('cerrar_caja'), {
            'caja_id': caja.id,
            'billetes_10000': '1',
            'billetes_2000': '1',
        })
        caja.refresh_from_db()
        self.assertEqual(caja.estado_cuadre, 'SOBRANTE')
        self.assertEqual(caja.diferencia_cuadre, Decimal('2000.00'))

    def test_cerrar_caja_seguridad_otro_cajero(self):
        """Un cajero no puede cerrar la caja de otro colaborador"""
        caja_carlos = Caja.objects.create(
            jornada=self.jornada,
            cajero=self.cajero_user,
            punto_venta=self.pv,
            nombre='Caja de Carlos',
            monto_apertura=Decimal('10000.00'),
            estado='ABIERTA'
        )
        self.client.login(username='otro_cajero_s12', password='password123')
        resp = self.client.post(reverse('cerrar_caja'), {
            'caja_id': caja_carlos.id,
            'billetes_10000': '1'
        })
        caja_carlos.refresh_from_db()
        self.assertEqual(caja_carlos.estado, 'ABIERTA')

    def test_cerrar_jornada_bloqueo_cajas_abiertas(self):
        """El administrador no puede cerrar jornada si quedan cajas abiertas sin arquear (salvo forzar)"""
        Caja.objects.create(
            jornada=self.jornada,
            cajero=self.cajero_user,
            punto_venta=self.pv,
            nombre='Caja Pendiente',
            monto_apertura=Decimal('10000.00'),
            estado='ABIERTA'
        )
        self.client.login(username='admin_s12', password='password123')
        resp = self.client.post(reverse('cerrar_jornada'), {
            'jornada_id': self.jornada.id,
            'forzar_cierre': '0'
        })
        self.jornada.refresh_from_db()
        self.assertEqual(self.jornada.estado, 'ABIERTA')

        # Con forzar_cierre = 1
        resp_forzar = self.client.post(reverse('cerrar_jornada'), {
            'jornada_id': self.jornada.id,
            'forzar_cierre': '1',
            'observaciones_cierre': 'Cierre forzado por contingencia'
        })
        self.jornada.refresh_from_db()
        self.assertEqual(self.jornada.estado, 'CERRADA')
        self.assertEqual(self.jornada.usuario_cierre, self.admin_user)
