from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.management import call_command
from ventas.models import PuntoVenta, PerfilEmpleado, Jornada, Caja


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
    """

    def setUp(self):
        self.client = Client()
        # Poblar datos demo con el comando idempotente oficial
        call_command('poblar_safari')

        self.admin_user = User.objects.get(username='rgomez')
        self.cajero_user = User.objects.get(username='cvalenzuela')
        self.cajera2_user = User.objects.get(username='csoto')
        self.mesero_user = User.objects.get(username='dsilva')

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
        rutas = [reverse('administrador'), reverse('vendedor'), reverse('mesero')]
        for ruta in rutas:
            resp = self.client.get(ruta, follow=True)
            self.assertRedirects(resp, reverse('index'))
            self.assertContains(resp, "Acceso protegido")

    # 3. Aislamiento estricto de los 3 roles
    def test_aislamiento_roles(self):
        # Mesero intentando entrar a administrador o vendedor
        self.client.force_login(self.mesero_user)
        resp_admin = self.client.get(reverse('administrador'), follow=True)
        self.assertRedirects(resp_admin, reverse('mesero'))
        resp_vendedor = self.client.get(reverse('vendedor'), follow=True)
        self.assertRedirects(resp_vendedor, reverse('mesero'))

        # Cajero intentando entrar a administrador o mesero
        self.client.force_login(self.cajero_user)
        resp_admin = self.client.get(reverse('administrador'), follow=True)
        self.assertRedirects(resp_admin, reverse('vendedor'))
        resp_mesero = self.client.get(reverse('mesero'), follow=True)
        self.assertRedirects(resp_mesero, reverse('vendedor'))

        # Administrador intentando entrar a vendedor o mesero
        self.client.force_login(self.admin_user)
        resp_vendedor = self.client.get(reverse('vendedor'), follow=True)
        self.assertRedirects(resp_vendedor, reverse('administrador'))
        resp_mesero = self.client.get(reverse('mesero'), follow=True)
        self.assertRedirects(resp_mesero, reverse('administrador'))

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


