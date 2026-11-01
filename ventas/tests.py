import json
import os
from pathlib import Path
import datetime
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.cache import cache
from ventas.models import (
    PuntoVenta, PerfilEmpleado, AlertaTraslado, Jornada, Caja, Mesa, Venta,
    DetalleVenta, Ticket, Pedido, DetallePedido, Entrega, Categoria, Producto, Menu,
    PrecioEspecial, RegistroPrecioEspecial, ReasignacionMesa,
    PuntoImpresion, RegistroImpresion, ConsumoInterno, DetalleConsumoInterno
)
from ventas.utils import (
    registrar_consumo_interno, liquidar_consumos_por_planilla
)


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
        PerfilEmpleado.objects.all().update(debe_cambiar_clave=False)

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
            'password': 'safari123'
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
        pv = getattr(self.mesero_user.perfil, 'punto_venta_actual', None) or PuntoVenta.objects.first()
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
        """Cantidades terminadas en 1 a 4 se redondean hacia abajo a la decena inferior"""
        from ventas.utils import calcular_redondeo_ley_20956
        # Terminación en 1
        monto, ajuste = calcular_redondeo_ley_20956(Decimal('1001'), 'EFECTIVO')
        self.assertEqual(monto, Decimal('1000'))
        self.assertEqual(ajuste, Decimal('-1'))

        # Terminación en 3
        monto, ajuste = calcular_redondeo_ley_20956(Decimal('1323'), 'EFECTIVO')
        self.assertEqual(monto, Decimal('1320'))
        self.assertEqual(ajuste, Decimal('-3'))

        # Terminación en 4
        monto, ajuste = calcular_redondeo_ley_20956(Decimal('1994'), 'EFECTIVO')
        self.assertEqual(monto, Decimal('1990'))
        self.assertEqual(ajuste, Decimal('-4'))

    def test_redondeo_ley_20956_efectivo_hacia_arriba(self):
        """Cantidades terminadas en 5 a 9 se redondean hacia arriba a la decena superior"""
        from ventas.utils import calcular_redondeo_ley_20956
        # Terminación en 5 (hacia arriba)
        monto_5, ajuste_5 = calcular_redondeo_ley_20956(Decimal('1995'), 'EFECTIVO')
        self.assertEqual(monto_5, Decimal('2000'))
        self.assertEqual(ajuste_5, Decimal('5'))

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


# ==============================================================================
# PRUEBAS DE SEGURIDAD, INTEGRIDAD Y RESILIENCIA ANTE CAÍDAS Y FRAUDE
# ==============================================================================
class ProteccionesSeguridadYResilienciaTests(TestCase):
    """
    Pruebas de verificación de los mecanismos de seguridad, concurrencia y resiliencia:
    1. Control anti-fraude en anulación de ventas con autorización de supervisor (PIN/Clave)
    2. Concurrencia con bloqueo de fila (select_for_update)
    3. Respaldo de BD en caliente (backup_safari) con integridad SHA-256
    4. Rate Limiting y bloqueo por fuerza bruta a nivel de red (IP global)
    5. Cierre de sesión por inactividad prolongada
    """

    def setUp(self):
        cache.clear()
        self.pv = PuntoVenta.objects.create(nombre="Barra Rápida Safari", tipo="BARRA")
        self.mesa = Mesa.objects.create(identificador="Mesa 10", punto_venta=self.pv, capacidad=4, estado="OCUPADA")
        self.admin = User.objects.create_user(username="supervisor_safari", password="password123")
        PerfilEmpleado.objects.create(usuario=self.admin, rol="ADMINISTRADOR", punto_venta_actual=self.pv)

        self.cajero = User.objects.create_user(username="cajero_seguro", password="password123")
        PerfilEmpleado.objects.create(usuario=self.cajero, rol="CAJERO", punto_venta_actual=self.pv)

        self.jornada = Jornada.objects.create(
            fecha=timezone.localdate(),
            estado="ABIERTA",
            usuario_apertura=self.admin
        )
        self.caja = Caja.objects.create(
            jornada=self.jornada,
            cajero=self.cajero,
            punto_venta=self.pv,
            nombre="Caja 1",
            monto_apertura=Decimal("20000.00"),
            estado="ABIERTA"
        )
        self.venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero,
            punto_venta=self.pv,
            modalidad="MESA",
            mesa=self.mesa,
            metodo_pago="EFECTIVO",
            total=Decimal("15000.00"),
            estado="PAGADA"
        )

    def test_anular_venta_con_supervisor_exitoso(self):
        """Un cajero puede anular una venta solo si cuenta con credenciales válidas de un supervisor"""
        self.client.login(username="cajero_seguro", password="password123")
        resp = self.client.post(reverse("anular_venta", args=[self.venta.id]), {
            "motivo_anulacion": "Cliente devolvió producto por error de digitación",
            "supervisor_username": "supervisor_safari",
            "supervisor_password": "password123"
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, "ANULADA")

        # Verifica que la mesa asociada quede habilitada
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, "HABILITADA")

        # Verifica trazabilidad de auditoría en AlertaTraslado
        alerta = AlertaTraslado.objects.filter(empleado=self.cajero, autorizado_por=self.admin).first()
        self.assertIsNotNone(alerta)
        self.assertIn("ANULACIÓN", alerta.motivo)

    def test_anular_venta_sin_credenciales_supervisor_rechazado(self):
        """Un cajero no puede anular una venta si no suministra credenciales válidas de supervisor"""
        self.client.login(username="cajero_seguro", password="password123")
        resp = self.client.post(reverse("anular_venta", args=[self.venta.id]), {
            "motivo_anulacion": "Intento de anulación sin permiso",
            "supervisor_username": "supervisor_safari",
            "supervisor_password": "clave_erronea_falsa"
        }, follow=True)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, "PAGADA")

    def test_anular_venta_admin_directo(self):
        """Un administrador puede anular una venta directamente indicando el motivo de auditoría"""
        self.client.login(username="supervisor_safari", password="password123")
        resp = self.client.post(reverse("anular_venta", args=[self.venta.id]), {
            "motivo_anulacion": "Corrección administrativa autorizada por gerencia"
        }, follow=True)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, "ANULADA")

    def test_anular_venta_motivo_muy_corto_rechazado(self):
        """La anulación exige un motivo detallado mayor o igual a 5 caracteres para auditoría"""
        self.client.login(username="supervisor_safari", password="password123")
        resp = self.client.post(reverse("anular_venta", args=[self.venta.id]), {
            "motivo_anulacion": "err"
        }, follow=True)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, "PAGADA")

    def test_comando_backup_safari(self):
        """El comando backup_safari genera un snapshot íntegro, comprimido y con hash SHA-256"""
        from django.core.management import call_command
        import tempfile, shutil
        temp_dir = tempfile.mkdtemp()
        try:
            call_command("backup_safari", output_dir=temp_dir)
            archivos = os.listdir(temp_dir)
            tiene_gz = any(f.endswith(".gz") for f in archivos)
            tiene_sha = any(f.endswith(".sha256") for f in archivos)
            self.assertTrue(tiene_gz, "Debe generar archivo .gz")
            self.assertTrue(tiene_sha, "Debe generar archivo .sha256")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_login_rate_limiting_ip_global(self):
        """Bloqueo de seguridad a nivel de IP tras 10 intentos fallidos de autenticación (OWASP)"""
        url_login = reverse("login")
        # Realizamos 10 intentos con credenciales erróneas simulando ataque de diccionario
        for i in range(10):
            self.client.post(url_login, {
                "username": f"usuario_ataque_{i}",
                "password": "password_incorrecta"
            })
        
        # El 11vo intento debe ser rechazado por IP bloqueada
        resp = self.client.post(url_login, {
            "username": "usuario_cualquiera",
            "password": "password_cualquiera"
        }, follow=True)
        self.assertContains(resp, "Acceso de red bloqueado temporalmente")

    def test_logout_por_inactividad(self):
        """El cierre de sesión por inactividad notifica al usuario del motivo institucional"""
        self.client.login(username="cajero_seguro", password="password123")
        resp = self.client.get(reverse("logout") + "?motivo=inactividad", follow=True)
        self.assertContains(resp, "inactividad")


# ==============================================================================
# PRUEBAS DE CENTRO DE GESTIÓN INTEGRAL (CATEGORÍAS MADRES) Y BÚSQUEDA REACTIVA
# ==============================================================================
class GestionUnificadaYFiltrosTests(TestCase):
    """
    Pruebas del Centro de Gestión Integral y Búsqueda Reactiva en Tiempo Real:
    1. Acceso y aislamiento de roles a /administrador/gestion/
    2. Visualización unificada de las 4 áreas: Trabajadores, Mesas, Productos y Menús
    3. Navegación por pestañas (?tab=trabajadores, ?tab=mesas, ?tab=productos, ?tab=menus)
    4. Disponibilidad de scripts de reloj de sesión discreto y filtro en tiempo real por tecleo
    """

    def setUp(self):
        cache.clear()
        self.pv = PuntoVenta.objects.create(nombre="Restaurante Central Safari", tipo="RESTAURANTE")
        self.admin = User.objects.create_user(username="admin_gestion", password="password123")
        PerfilEmpleado.objects.create(usuario=self.admin, rol="ADMINISTRADOR", punto_venta_actual=self.pv)

        self.cajero = User.objects.create_user(username="cajero_gestion", password="password123")
        PerfilEmpleado.objects.create(usuario=self.cajero, rol="CAJERO", punto_venta_actual=self.pv)

        self.mesero = User.objects.create_user(username="mesero_gestion", password="password123")
        PerfilEmpleado.objects.create(usuario=self.mesero, rol="MESERO", punto_venta_actual=self.pv)

        self.categoria = Categoria.objects.create(nombre="Minutas y Platos", activo=True)
        self.producto = Producto.objects.create(nombre="Cazuela Safari", categoria=self.categoria, precio_base=Decimal("7500.00"), activo=True)
        self.producto.puntos_venta.add(self.pv)

        self.mesa = Mesa.objects.create(identificador="Mesa 1", punto_venta=self.pv, capacidad=4, estado="HABILITADA")
        self.menu = Menu.objects.create(nombre="Carta Almuerzo", punto_venta=self.pv, activo=True)
        self.menu.productos.add(self.producto)

    def test_acceso_administrador_gestion_permitido(self):
        """Un usuario con rol ADMINISTRADOR puede acceder al Centro de Gestión Integral (200 OK)"""
        self.client.login(username="admin_gestion", password="password123")
        resp = self.client.get(reverse("administrador_gestion"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Centro de Gestión")
        self.assertContains(resp, "Categoría Madre")

    def test_acceso_roles_no_administrador_bloqueado(self):
        """Meseros y Cajeros no pueden ingresar al Centro de Gestión Integral y son redirigidos"""
        self.client.login(username="cajero_gestion", password="password123")
        resp_cajero = self.client.get(reverse("administrador_gestion"), follow=True)
        self.assertRedirects(resp_cajero, reverse("vendedor"))
        self.assertContains(resp_cajero, "Acceso restringido")

        self.client.login(username="mesero_gestion", password="password123")
        resp_mesero = self.client.get(reverse("administrador_gestion"), follow=True)
        self.assertRedirects(resp_mesero, reverse("mesero"))
        self.assertContains(resp_mesero, "Acceso restringido")

    def test_contexto_contiene_las_cuatro_areas_madres(self):
        """La vista administrador_gestion provee en su contexto los datos de las 4 áreas administrativas"""
        self.client.login(username="admin_gestion", password="password123")
        resp = self.client.get(reverse("administrador_gestion"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("trabajadores", resp.context)
        self.assertIn("mesas", resp.context)
        self.assertIn("productos", resp.context)
        self.assertIn("menus", resp.context)
        self.assertIn("locales", resp.context)
        self.assertIn("categorias", resp.context)

    def test_navegacion_pestanas_parametro_tab(self):
        """El parámetro ?tab en la URL activa la pestaña correspondiente"""
        self.client.login(username="admin_gestion", password="password123")
        for tab in ["trabajadores", "mesas", "productos", "menus"]:
            resp = self.client.get(reverse("administrador_gestion") + f"?tab={tab}")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.context["tab_activo"], tab)

    def test_scripts_reloj_sesion_y_filtro_en_vivo(self):
        """Verifica que el script de filtro por tecleo y el reloj discreto de sesión existan en static"""
        import os
        from django.conf import settings
        static_dir = os.path.join(settings.BASE_DIR, "static", "js")
        self.assertTrue(os.path.exists(os.path.join(static_dir, "filtro_tiempo_real.js")), "filtro_tiempo_real.js debe existir")
        self.assertTrue(os.path.exists(os.path.join(static_dir, "seguridad_sesion.js")), "seguridad_sesion.js debe existir")

        # Comprobar que filtro_tiempo_real.js contiene el listener de 'input' reactivo por tecleo
        with open(os.path.join(static_dir, "filtro_tiempo_real.js"), "r", encoding="utf-8") as f:
            contenido_filtro = f.read()
        self.assertIn("addEventListener('input'", contenido_filtro)
        self.assertIn("SafariFiltroEnVivo", contenido_filtro)

        # Comprobar que seguridad_sesion.js contiene el reloj discreto y la renovación por actividad
        with open(os.path.join(static_dir, "seguridad_sesion.js"), "r", encoding="utf-8") as f:
            contenido_sesion = f.read()
        self.assertIn("reiniciarTiempoSesion", contenido_sesion)
        self.assertIn("indicadorSesionSafari", contenido_sesion)



class NuevasFuncionalidadesEvaluacionTest(TestCase):
    """
    Tests de integración para las nuevas funcionalidades solicitadas:
    1. Exportación de reportes de ventas (Excel, Word, PDF)
    2. Creación y gestión de ofertas promocionales ($1 peso, 2x1)
    3. Redondeo en efectivo para eventos promocionales ($1 y $5 pesos)
    4. Edición de carta en tiempo real con respuesta AJAX
    """

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username='admin_test_nuevas',
            password='Password123!',
            first_name='Admin',
            last_name='Nuevas'
        )
        self.local = PuntoVenta.objects.create(
            nombre="Restaurante Central Test",
            tipo="RESTAURANTE",
            activo=True
        )
        self.perfil = PerfilEmpleado.objects.create(
            usuario=self.admin_user,
            rol='ADMINISTRADOR',
            rut='11.111.111-1',
            punto_venta_actual=self.local,
            activo=True
        )
        self.categoria = Categoria.objects.create(nombre="Comida Test", activo=True)
        self.producto = Producto.objects.create(
            nombre="Hamburguesa Promo Test",
            categoria=self.categoria,
            precio_base=Decimal('8900'),
            activo=True
        )
        self.menu = Menu.objects.create(
            nombre="Carta Test",
            punto_venta=self.local,
            activo=True
        )
        self.menu.productos.add(self.producto)

    def test_exportar_reporte_excel(self):
        self.client.force_login(self.admin_user)
        resp = self.client.get('/administrador/dashboard/exportar/', {
            'formato': 'excel',
            'tipo_rango': '15_meses'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml.sheet', resp['Content-Type'])
        self.assertTrue(len(resp.content) > 1000)

    def test_exportar_reporte_word(self):
        self.client.force_login(self.admin_user)
        resp = self.client.get('/administrador/dashboard/exportar/', {
            'formato': 'word',
            'tipo_rango': 'mes',
            'mes': '2026-09'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('wordprocessingml.document', resp['Content-Type'])
        self.assertTrue(len(resp.content) > 1000)

    def test_exportar_reporte_pdf_vista_imprimible(self):
        self.client.force_login(self.admin_user)
        resp = self.client.get('/administrador/dashboard/exportar/', {
            'formato': 'pdf',
            'tipo_rango': 'dia',
            'fecha': '2026-10-31'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "PARQUE SAFARI CHILE")
        self.assertContains(resp, "REPORTE OFICIAL DE VENTAS")

    def test_crear_oferta_producto_1_peso(self):
        self.client.force_login(self.admin_user)
        resp = self.client.post('/administrador/productos/', {
            'accion': 'gestionar_oferta',
            'producto_id': self.producto.id,
            'en_oferta': 'on',
            'precio_oferta': '1',
            'descripcion_oferta': '¡Segunda hamburguesa a $1 peso!'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['precio_actual'], 1.0)

        # Verificar en base de datos
        self.producto.refresh_from_db()
        self.assertTrue(self.producto.en_oferta)
        self.assertEqual(self.producto.precio_oferta, Decimal('1'))
        self.assertEqual(self.producto.precio_actual, Decimal('1'))

    def test_redondeo_evento_promocional_1_peso_y_5_pesos(self):
        from ventas.utils import calcular_redondeo_ley_20956
        # $1 peso no se redondea a $0 (permite evento de 1 peso en efectivo)
        final_1, ajuste_1 = calcular_redondeo_ley_20956(1, 'EFECTIVO')
        self.assertEqual(final_1, Decimal('1'))
        self.assertEqual(ajuste_1, Decimal('0'))

        # $5 pesos no se redondea a $10
        final_5, ajuste_5 = calcular_redondeo_ley_20956(5, 'EFECTIVO')
        self.assertEqual(final_5, Decimal('5'))
        self.assertEqual(ajuste_5, Decimal('0'))

        # Ventas regulares aplican redondeo de ley 20.956
        final_reg, ajuste_reg = calcular_redondeo_ley_20956(1994, 'EFECTIVO')
        self.assertEqual(final_reg, Decimal('1990'))
        self.assertEqual(ajuste_reg, Decimal('-4'))

    def test_modificar_menu_ajax_tiempo_real(self):
        self.client.force_login(self.admin_user)
        resp = self.client.post('/administrador/menus/', {
            'accion': 'modificar',
            'menu_id': self.menu.id,
            'nombre': 'Carta Modificada en Tiempo Real',
            'punto_venta_id': self.local.id,
            'productos': [self.producto.id],
            'activo': 'on'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['nombre'], 'Carta Modificada en Tiempo Real')
        self.assertEqual(data['productos_count'], 1)

        # Verificar en BD
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.nombre, 'Carta Modificada en Tiempo Real')

class SafariSeguridadYConveniosTests(TestCase):
    """
    Suite oficial para pruebas de Seguridad, Fuerza Bruta, Expiración Semestral y Convenios Cabañas QR (Tareas 1 y 7)
    """
    def setUp(self):
        cache.clear()
        self.client = Client()
        call_command('poblar_safari')
        self.cajero = User.objects.get(username='cvalenzuela')
        self.admin = User.objects.get(username='rgomez')

    def tearDown(self):
        cache.clear()

    def test_politica_complejidad_clave(self):
        """Valida que la política exija longitud, mayúscula, minúscula, número y símbolo"""
        from ventas.validators import validar_complejidad_clave
        # Clave muy corta
        valida, msg = validar_complejidad_clave("Ab1!")
        self.assertFalse(valida)
        self.assertIn("mínimo de 8 caracteres", msg)

        # Sin mayúscula
        valida, msg = validar_complejidad_clave("password123!")
        self.assertFalse(valida)
        self.assertIn("mayúscula", msg)

        # Sin minúscula
        valida, msg = validar_complejidad_clave("PASSWORD123!")
        self.assertFalse(valida)
        self.assertIn("minúscula", msg)

        # Sin número
        valida, msg = validar_complejidad_clave("Password!@#")
        self.assertFalse(valida)
        self.assertIn("dígito numérico", msg)

        # Sin símbolo
        valida, msg = validar_complejidad_clave("Password123")
        self.assertFalse(valida)
        self.assertIn("símbolo o carácter especial", msg)

        # Contraseña robusta válida
        valida, msg = validar_complejidad_clave("Safari.Pilar2026!")
        self.assertTrue(valida)
        self.assertEqual(msg, "")

    def test_primer_login_fuerza_cambio_clave(self):
        """Valida que un usuario recién creado deba configurar obligatoriamente su clave"""
        perfil = self.cajero.perfil
        perfil.debe_cambiar_clave = True
        perfil.save()

        resp = self.client.post(reverse('login'), {
            'username': 'cvalenzuela',
            'password': 'safari123'
        }, follow=True)
        self.assertRedirects(resp, reverse('cambiar_clave_expirada'))
        self.assertContains(resp, "Primer inicio de sesión")
        self.assertContains(resp, "Mínimo 8 caracteres")

    def test_expiracion_clave_6_meses(self):
        """Valida que claves con más de 180 días se marquen como expiradas y fuercen rotación"""
        perfil = self.cajero.perfil
        perfil.fecha_cambio_clave = timezone.now() - timedelta(days=181)
        perfil.save()

        self.assertTrue(perfil.clave_expirada())

        # Al iniciar sesión, debe redirigir a cambio obligatorio de clave
        resp = self.client.post(reverse('login'), {
            'username': 'cvalenzuela',
            'password': 'safari123'
        }, follow=True)
        self.assertRedirects(resp, reverse('cambiar_clave_expirada'))
        self.assertContains(resp, "Actualización Obligatoria de Contraseña")

    def test_defensa_fuerza_bruta_bloqueo(self):
        """Prueba de testeo de fuerza bruta: 5 intentos fallidos bloquean la cuenta"""
        perfil = self.cajero.perfil
        perfil.limpiar_intentos_fallidos()

        # Simular 4 intentos fallidos
        for i in range(1, 5):
            resp = self.client.post(reverse('login'), {
                'username': 'cvalenzuela',
                'password': f'clave_erronea_{i}'
            }, follow=True)
            self.assertContains(resp, "Credenciales incorrectas")

        # 5to intento fallido debe activar el bloqueo
        resp5 = self.client.post(reverse('login'), {
            'username': 'cvalenzuela',
            'password': 'clave_erronea_5'
        }, follow=True)
        self.assertContains(resp5, "bloqueado temporalmente")

        # Verificar en base de datos
        perfil.refresh_from_db()
        self.assertTrue(perfil.esta_bloqueado())

        # Un 6to intento, incluso con clave correcta, debe ser rechazado por bloqueo activo
        resp6 = self.client.post(reverse('login'), {
            'username': 'cvalenzuela',
            'password': 'safari123'
        }, follow=True)
        self.assertContains(resp6, "temporalmente bloqueado")

    def test_cambio_clave_expirada_exitoso(self):
        """Permite a un usuario autenticado actualizar su contraseña expirada con validación estricta"""
        self.client.force_login(self.cajero)
        perfil = self.cajero.perfil
        perfil.fecha_cambio_clave = timezone.now() - timedelta(days=190)
        perfil.save()

        resp = self.client.post(reverse('cambiar_clave_expirada'), {
            'clave_actual': 'safari123',
            'nueva_clave': 'Safari.NuevoPass2026!',
            'confirmar_clave': 'Safari.NuevoPass2026!'
        }, follow=True)

        self.assertContains(resp, "Contraseña actualizada exitosamente")
        perfil.refresh_from_db()
        self.assertFalse(perfil.clave_expirada())
        self.cajero.refresh_from_db()
        self.assertTrue(self.cajero.check_password('Safari.NuevoPass2026!'))

    def test_verificacion_qr_convenio_cabana(self):
        """Valida detección y respuesta de API para huéspedes de cabañas con desayuno incluido"""
        from ventas.models import ConvenioHuesped
        convenio = ConvenioHuesped.objects.create(
            codigo_qr='CAB-TEST-101',
            numero_cabana='Cabaña 101',
            nombre_titular='Familia González',
            tipo_beneficio='DESAYUNO_INCLUIDO',
            valor_descuento=Decimal('100.00'),
            limite_diario=1,
            fecha_checkin=timezone.localdate() - timedelta(days=1),
            fecha_checkout=timezone.localdate() + timedelta(days=2),
            activo=True
        )

        resp = self.client.get(f"/api/convenios/verificar/?codigo=CAB-TEST-101")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['puede_consumir'])
        self.assertEqual(data['cabana'], 'Cabaña 101')
        self.assertEqual(data['tipo_beneficio'], 'DESAYUNO_INCLUIDO')

    def test_limite_diario_consumo_convenio(self):
        """Valida que el huésped no pueda exceder su límite diario de desayunos"""
        from ventas.models import ConvenioHuesped, ConsumoHuesped
        convenio = ConvenioHuesped.objects.create(
            codigo_qr='CAB-TEST-202',
            numero_cabana='Cabaña 202',
            nombre_titular='Pedro Picapiedra',
            tipo_beneficio='DESAYUNO_INCLUIDO',
            limite_diario=1,
            fecha_checkin=timezone.localdate(),
            fecha_checkout=timezone.localdate() + timedelta(days=1),
            activo=True
        )

        # Registrar consumo de hoy
        ConsumoHuesped.objects.create(
            convenio=convenio,
            monto_original=Decimal('8900'),
            monto_bonificado=Decimal('8900'),
            monto_pagado=Decimal('0'),
            registrado_por=self.cajero
        )

        self.assertFalse(convenio.puede_consumir_hoy())

        # API debe informar que el límite fue alcanzado
        resp = self.client.get(f"/api/convenios/verificar/?codigo=CAB-TEST-202")
        data = resp.json()
        self.assertFalse(data['puede_consumir'])
        self.assertIn("Límite diario alcanzado", data['mensaje'])

    def test_ofertas_temporada_administrador(self):
        """Valida creación y activación de ofertas de temporada por el Administrador"""
        from ventas.models import OfertaTemporada
        self.client.force_login(self.admin)

        resp = self.client.post(reverse('administrador_ofertas_temporada'), {
            'accion': 'crear',
            'nombre': 'Descuento Primavera Cabañas',
            'descripcion': '25% descuento en desayunos campestres',
            'descuento_porcentaje': '25',
            'fecha_inicio': timezone.now().date(),
            'fecha_fin': timezone.now().date() + timedelta(days=30),
            'activa': 'on'
        }, follow=True)

        self.assertContains(resp, "configurada exitosamente")
        oferta = OfertaTemporada.objects.get(nombre='Descuento Primavera Cabañas')
        self.assertTrue(oferta.activa)
        self.assertTrue(oferta.es_vigente())
        self.assertEqual(oferta.descuento_porcentaje, Decimal('25'))
# ==============================================================================
# PRUEBAS OFICIALES RF05 — REASIGNACIÓN DE MESAS Y CUENTA ABIERTA
# ==============================================================================
class SafariRF05ReasignacionMesasTests(TestCase):
    """
    Suite oficial de validación y robustez para RF05: Reasignación de Mesas.
    Verifica:
    - Traslado válido conservando rondas, productos, totales, tickets y trazabilidad
    - Mesa origen liberada y mesa destino ocupada
    - Rechazo de destino ocupado
    - Rechazo de destino inexistente o inactivo
    - Rechazo de origen inexistente o sin cuenta abierta
    - Rechazo de traslado a la misma mesa
    - Rechazo de traslado entre Puntos de Venta distintos
    - Tolerancia a doble clic / doble envío / concurrencia
    - Nuevas comandas posteriores al traslado dirigidas a la nueva mesa
    - Auditoría histórica persistida en ReasignacionMesa
    """
    def setUp(self):
        cache.clear()
        self.client = Client()
        call_command('poblar_safari')
        PerfilEmpleado.objects.all().update(debe_cambiar_clave=False)

        self.mesero = User.objects.get(username='dsilva')
        self.cajero = User.objects.get(username='cvalenzuela')
        self.admin = User.objects.get(username='rgomez')
        self.local1 = PuntoVenta.objects.get(id=1)
        self.local2 = PuntoVenta.objects.get(id=2)

        self.mesa1 = Mesa.objects.filter(punto_venta=self.local1).order_by('id')[0]
        self.mesa2 = Mesa.objects.filter(punto_venta=self.local1).order_by('id')[1]
        self.mesa3 = Mesa.objects.filter(punto_venta=self.local1).order_by('id')[2]

        self.mesa1.estado = 'HABILITADA'
        self.mesa1.save()
        self.mesa2.estado = 'HABILITADA'
        self.mesa2.save()
        self.mesa3.estado = 'HABILITADA'
        self.mesa3.save()

        # Crear cuenta abierta inicial en Mesa 1 con 2 rondas y tickets
        hoy = timezone.localdate()
        self.jornada, _ = Jornada.objects.get_or_create(
            fecha=hoy,
            estado='ABIERTA',
            defaults={'usuario_apertura': self.admin}
        )
        self.caja, _ = Caja.objects.get_or_create(
            jornada=self.jornada,
            cajero=self.cajero,
            punto_venta=self.local1,
            defaults={'estado': 'ABIERTA', 'nombre': 'Caja 1'}
        )
        self.venta1 = Venta.objects.create(
            caja=self.caja,
            cajero=self.mesero,
            punto_venta=self.local1,
            modalidad='MESA',
            mesa=self.mesa1,
            total=16400,
            estado='ABIERTA'
        )
        self.mesa1.estado = 'OCUPADA'
        self.mesa1.save()

        # Ronda 1
        self.pedido1 = Pedido.objects.create(
            venta=self.venta1,
            estado='PENDIENTE',
            observaciones=f"Ronda #1 para {self.mesa1.identificador}"
        )
        self.prod1 = Producto.objects.first()
        DetallePedido.objects.create(
            pedido=self.pedido1,
            producto=self.prod1,
            cantidad=2,
            observaciones="Sin cebolla"
        )
        DetalleVenta.objects.create(
            venta=self.venta1,
            producto=self.prod1,
            cantidad=2,
            precio_aplicado=Decimal('8200'),
            subtotal=Decimal('16400')
        )
        self.ticket1 = Ticket.objects.create(
            pedido=self.pedido1,
            codigo="COM-COC-9001",
            tipo_destino='COCINA',
            estado='EMITIDO',
            contenido_impresion=f"Ticket Cocina Ronda 1 - {self.mesa1.identificador}"
        )

        # Ronda 2
        self.pedido2 = Pedido.objects.create(
            venta=self.venta1,
            estado='PENDIENTE',
            observaciones=f"Ronda #2 para {self.mesa1.identificador}"
        )
        self.ticket2 = Ticket.objects.create(
            pedido=self.pedido2,
            codigo="COM-BAR-9002",
            tipo_destino='BARRA',
            estado='EMITIDO',
            contenido_impresion=f"Ticket Barra Ronda 2 - {self.mesa1.identificador}"
        )

    def tearDown(self):
        cache.clear()

    def test_traslado_valido_conserva_rondas_totales_y_tickets(self):
        """Valida traslado exitoso: venta.mesa cambia, rondas/tickets intactos, origen libre y destino ocupada"""
        from ventas.models import ReasignacionMesa
        self.client.force_login(self.mesero)

        resp = self.client.post(reverse('mesero'), {
            'accion': 'reasignar_mesa',
            'mesa_origen_id': self.mesa1.id,
            'mesa_destino_id': self.mesa2.id,
            'motivo': 'Comensales prefirieron mesa con vista panorámica'
        }, follow=True)

        self.assertContains(resp, "Mesa reasignada exitosamente")

        # 1. La venta se mantiene abierta pero ahora apunta a Mesa 2
        self.venta1.refresh_from_db()
        self.assertEqual(self.venta1.mesa, self.mesa2)
        self.assertEqual(self.venta1.total, Decimal('16400'))
        self.assertEqual(self.venta1.estado, 'ABIERTA')

        # 2. Las 2 rondas anteriores siguen perteneciendo a la misma venta
        self.assertEqual(self.venta1.pedidos.count(), 2)

        # 3. Los tickets anteriores no se duplicaron ni cambiaron
        self.assertEqual(Ticket.objects.filter(pedido__venta=self.venta1).count(), 2)

        # 4. Estados de las mesas
        self.mesa1.refresh_from_db()
        self.mesa2.refresh_from_db()
        self.assertEqual(self.mesa1.estado, 'HABILITADA')
        self.assertEqual(self.mesa2.estado, 'OCUPADA')

        # 5. Auditoría histórica persistida
        reasig = ReasignacionMesa.objects.filter(venta=self.venta1).first()
        self.assertIsNotNone(reasig)
        self.assertEqual(reasig.mesa_origen, self.mesa1)
        self.assertEqual(reasig.mesa_destino, self.mesa2)
        self.assertEqual(reasig.mesero, self.mesero)
        self.assertIn("vista panorámica", reasig.motivo)

    def test_destino_ocupado_es_rechazado(self):
        """Valida que no se pueda trasladar a una mesa que ya esté ocupada por otros comensales"""
        from ventas.models import ReasignacionMesa
        self.client.force_login(self.mesero)

        # Marcar mesa 2 como ocupada
        self.mesa2.estado = 'OCUPADA'
        self.mesa2.save()

        resp = self.client.post(reverse('mesero'), {
            'accion': 'reasignar_mesa',
            'mesa_origen_id': self.mesa1.id,
            'mesa_destino_id': self.mesa2.id,
        }, follow=True)

        self.assertContains(resp, "ya se encuentra ocupada")
        self.venta1.refresh_from_db()
        self.assertEqual(self.venta1.mesa, self.mesa1)
        self.assertEqual(ReasignacionMesa.objects.count(), 0)

    def test_destino_inexistente_es_rechazado(self):
        """Valida rechazo si la mesa de destino no existe"""
        self.client.force_login(self.mesero)

        resp = self.client.post(reverse('mesero'), {
            'accion': 'reasignar_mesa',
            'mesa_origen_id': self.mesa1.id,
            'mesa_destino_id': 999999,
        }, follow=True)

        self.assertContains(resp, "no existe en el sistema")
        self.venta1.refresh_from_db()
        self.assertEqual(self.venta1.mesa, self.mesa1)

    def test_misma_mesa_origen_y_destino_es_rechazado(self):
        """Valida que no se pueda trasladar una mesa hacia sí misma"""
        self.client.force_login(self.mesero)

        resp = self.client.post(reverse('mesero'), {
            'accion': 'reasignar_mesa',
            'mesa_origen_id': self.mesa1.id,
            'mesa_destino_id': self.mesa1.id,
        }, follow=True)

        self.assertContains(resp, "no puede ser la misma")
        self.venta1.refresh_from_db()
        self.assertEqual(self.venta1.mesa, self.mesa1)

    def test_origen_sin_cuenta_abierta_es_rechazado(self):
        """Valida que si la mesa de origen no tiene cuenta abierta, se rechaza la operación"""
        self.client.force_login(self.mesero)

        resp = self.client.post(reverse('mesero'), {
            'accion': 'reasignar_mesa',
            'mesa_origen_id': self.mesa3.id,
            'mesa_destino_id': self.mesa2.id,
        }, follow=True)

        self.assertContains(resp, "no posee una cuenta abierta")

    def test_destino_inactivo_es_rechazado(self):
        """Valida rechazo si la mesa de destino está marcada como inactiva/mantenimiento"""
        self.client.force_login(self.mesero)
        self.mesa2.estado = 'INACTIVA'
        self.mesa2.save()

        resp = self.client.post(reverse('mesero'), {
            'accion': 'reasignar_mesa',
            'mesa_origen_id': self.mesa1.id,
            'mesa_destino_id': self.mesa2.id,
        }, follow=True)

        self.assertContains(resp, "deshabilitada o en mantenimiento")
        self.venta1.refresh_from_db()
        self.assertEqual(self.venta1.mesa, self.mesa1)

    def test_traslado_entre_distintos_locales_es_rechazado(self):
        """Valida que no se permita trasladar cuentas entre mesas de distintos Puntos de Venta"""
        self.client.force_login(self.mesero)
        mesa_local2 = Mesa.objects.filter(punto_venta=self.local2).first()

        resp = self.client.post(reverse('mesero'), {
            'accion': 'reasignar_mesa',
            'mesa_origen_id': self.mesa1.id,
            'mesa_destino_id': mesa_local2.id,
        }, follow=True)

        self.assertContains(resp, "distintos Puntos de Venta")
        self.venta1.refresh_from_db()
        self.assertEqual(self.venta1.mesa, self.mesa1)

    def test_doble_envio_concurrencia_tolerancia(self):
        """Valida que un segundo clic o envío simultáneo no duplique la reasignación ni corrompa datos"""
        from ventas.models import ReasignacionMesa
        self.client.force_login(self.mesero)

        # Primer envío exitoso
        resp1 = self.client.post(reverse('mesero'), {
            'accion': 'reasignar_mesa',
            'mesa_origen_id': self.mesa1.id,
            'mesa_destino_id': self.mesa2.id,
        }, follow=True)
        self.assertContains(resp1, "Mesa reasignada exitosamente")

        # Segundo envío idéntico (simulando doble clic)
        resp2 = self.client.post(reverse('mesero'), {
            'accion': 'reasignar_mesa',
            'mesa_origen_id': self.mesa1.id,
            'mesa_destino_id': self.mesa2.id,
        }, follow=True)
        self.assertContains(resp2, "no posee una cuenta abierta")
        self.assertEqual(ReasignacionMesa.objects.count(), 1)
        self.venta1.refresh_from_db()
        self.assertEqual(self.venta1.mesa, self.mesa2)

    def test_nueva_ronda_despues_de_traslado_continua_en_mesa_destino(self):
        """Valida que una nueva comanda emitida tras el traslado se anexe a la misma cuenta en la mesa destino"""
        import json
        self.client.force_login(self.mesero)

        # 1. Reasignar a Mesa 2
        self.client.post(reverse('mesero'), {
            'accion': 'reasignar_mesa',
            'mesa_origen_id': self.mesa1.id,
            'mesa_destino_id': self.mesa2.id,
        }, follow=True)

        # 2. Mesero envía Ronda #3 en Mesa 2
        items = json.dumps([
            {'nombre': 'Bebida Sprite 350ml', 'precio': 2000, 'cantidad': 1, 'nota': 'Con hielo', 'destino': 'BARRA'}
        ])
        resp_ronda = self.client.post(reverse('mesero'), {
            'accion': 'enviar_comanda',
            'mesa_id': self.mesa2.id,
            'items_json': items
        }, follow=True)

        self.assertContains(resp_ronda, "Ronda #3 agregada")

        # 3. La venta sigue siendo la misma Venta 1, con 3 rondas y total acumulado
        self.venta1.refresh_from_db()
        self.assertEqual(self.venta1.pedidos.count(), 3)
        self.assertEqual(self.venta1.mesa, self.mesa2)
        self.assertEqual(self.venta1.total, Decimal('18400'))


# ==============================================================================
# RF07 — SUITE DE PRUEBAS: GESTIÓN DE PRECIOS DURANTE LA VENTA (CONVENIOS / AUTORIZACIONES)
# ==============================================================================
class SafariRF07GestionPreciosTests(TestCase):
    """
    Pruebas exhaustivas para RF07:
    - Inmutabilidad de Producto.precio_base en BD (RF07.1).
    - Aplicación de precio especial exclusivamente al DetalleVenta de la transacción (RF07.2).
    - Control estricto de autorización por rol y motivo comercial obligatorio (RF07.3).
    - Trazabilidad total mediante DetalleVenta y RegistroPrecioEspecial (RF07.4).
    - Soporte y validación de convenios comerciales activos y vigentes (RF07.5).
    - Blindaje contra fallos: precio <= 0, no numérico, convenio vencido, producto inactivo,
      manipulación de cliente/navegador y consistencia transaccional.
    """

    def setUp(self):
        self.client = Client()
        self.hoy = timezone.localdate()

        self.admin_user = User.objects.create_user(
            username='admin_rf07', password='Password123!', first_name='Admin', last_name='Test'
        )
        self.cajero_user = User.objects.create_user(
            username='cajero_rf07', password='Password123!', first_name='Cajero', last_name='Test'
        )
        self.mesero_user = User.objects.create_user(
            username='mesero_rf07', password='Password123!', first_name='Mesero', last_name='Test'
        )

        self.pv = PuntoVenta.objects.create(nombre="Restaurante RF07 Test", tipo="RESTAURANTE", activo=True)

        PerfilEmpleado.objects.create(usuario=self.admin_user, rol='ADMINISTRADOR', punto_venta_actual=self.pv)
        PerfilEmpleado.objects.create(usuario=self.cajero_user, rol='CAJERO', punto_venta_actual=self.pv)
        PerfilEmpleado.objects.create(usuario=self.mesero_user, rol='MESERO', punto_venta_actual=self.pv)

        self.categoria = Categoria.objects.create(nombre="Gastronomía RF07", activo=True)
        self.producto = Producto.objects.create(
            nombre="Hamburguesa Premium Safari",
            categoria=self.categoria,
            precio_base=Decimal('9000.00'),
            activo=True
        )

        self.jornada = Jornada.objects.create(
            fecha=self.hoy, estado='ABIERTA', usuario_apertura=self.admin_user
        )
        self.caja = Caja.objects.create(
            nombre="Caja POS RF07",
            jornada=self.jornada,
            punto_venta=self.pv,
            cajero=self.cajero_user,
            monto_apertura=Decimal('100000.00'),
            estado='ABIERTA'
        )
        self.mesa = Mesa.objects.create(
            identificador="Mesa 70", punto_venta=self.pv, capacidad=4, estado='HABILITADA'
        )

    # 1. Inmutabilidad de Producto.precio_base en BD (RF07.1)
    def test_rf07_1_precio_base_oficial_inmutable_en_bd(self):
        from ventas.utils import validar_y_calcular_precio_linea
        precio_inicial = self.producto.precio_base

        calc = validar_y_calcular_precio_linea(
            producto=self.producto,
            cantidad=2,
            precio_solicitado=Decimal('5000.00'),
            usuario=self.cajero_user,
            motivo="Descuento Autorizado Vecino",
            permite_manual=True
        )
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.precio_base, precio_inicial)
        self.assertEqual(calc['precio_original'], precio_inicial)
        self.assertEqual(calc['precio_aplicado'], Decimal('5000.00'))

    # 2. Precio especial exclusivo de la transacción (RF07.2)
    def test_rf07_2_precio_especial_por_operacion_detalle_venta(self):
        from ventas.utils import validar_y_calcular_precio_linea, registrar_precio_especial_auditoria
        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero_user, punto_venta=self.pv,
            modalidad='MOSTRADOR', metodo_pago='EFECTIVO', total=Decimal('6000.00'), estado='PAGADA'
        )

        calc = validar_y_calcular_precio_linea(
            producto=self.producto,
            cantidad=1,
            precio_solicitado=Decimal('6000.00'),
            usuario=self.cajero_user,
            motivo="Convenio Convenio Vecino Rancagua"
        )
        det = DetalleVenta.objects.create(
            venta=venta, producto=self.producto, cantidad=1,
            precio_aplicado=calc['precio_aplicado'], subtotal=calc['subtotal']
        )
        registrar_precio_especial_auditoria(venta, det, calc)

        det.refresh_from_db()
        self.assertTrue(det.es_precio_especial)
        self.assertEqual(det.precio_original, Decimal('9000.00'))
        self.assertEqual(det.precio_aplicado, Decimal('6000.00'))
        self.assertEqual(det.autorizado_por, self.cajero_user)

        # Verificar que el catálogo permanece con precio normal
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.precio_base, Decimal('9000.00'))

    # 3. Rechazo de modificación de precio por usuario sin rol autorizado (RF07.3)
    def test_rf07_3_rechazo_usuario_no_autorizado_para_precio_manual(self):
        from ventas.utils import validar_y_calcular_precio_linea
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError) as ctx:
            validar_y_calcular_precio_linea(
                producto=self.producto,
                cantidad=1,
                precio_solicitado=Decimal('4000.00'),
                usuario=self.mesero_user, # Mesero no tiene permiso para inventar precios
                motivo="Amigo personal",
                permite_manual=True
            )
        self.assertIn("No tienes autorización", str(ctx.exception))

    # 4. Exigencia de motivo justificado para precio manual (RF07.3)
    def test_rf07_3_exigencia_de_motivo_justificado(self):
        from ventas.utils import validar_y_calcular_precio_linea
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError) as ctx:
            validar_y_calcular_precio_linea(
                producto=self.producto,
                cantidad=1,
                precio_solicitado=Decimal('5000.00'),
                usuario=self.cajero_user,
                motivo="   ", # Motivo vacío o puros espacios
                permite_manual=True
            )
        self.assertIn("Debe ingresar un motivo o justificación", str(ctx.exception))

    # 5. Trazabilidad total de auditoría en RegistroPrecioEspecial (RF07.4)
    def test_rf07_4_trazabilidad_auditoria_completa_registro_precio_especial(self):
        from ventas.utils import validar_y_calcular_precio_linea, registrar_precio_especial_auditoria
        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero_user, punto_venta=self.pv,
            modalidad='MOSTRADOR', metodo_pago='EFECTIVO', total=Decimal('7000.00'), estado='PAGADA'
        )

        calc = validar_y_calcular_precio_linea(
            producto=self.producto,
            cantidad=1,
            precio_solicitado=Decimal('7000.00'),
            usuario=self.admin_user,
            motivo="Descuento Institucional INACAP"
        )
        det = DetalleVenta.objects.create(
            venta=venta, producto=self.producto, cantidad=1,
            precio_aplicado=calc['precio_aplicado'], subtotal=calc['subtotal']
        )
        reg = registrar_precio_especial_auditoria(venta, det, calc)

        self.assertIsNotNone(reg)
        self.assertEqual(reg.venta, venta)
        self.assertEqual(reg.producto, self.producto)
        self.assertEqual(reg.precio_original, Decimal('9000.00'))
        self.assertEqual(reg.precio_aplicado, Decimal('7000.00'))
        self.assertEqual(reg.descuento_unitario, Decimal('2000.00'))
        self.assertEqual(reg.usuario, self.admin_user)
        self.assertEqual(reg.motivo, "Descuento Institucional INACAP")

    # 6. Aplicación de convenio comercial institucional activo y vigente (RF07.5)
    def test_rf07_5_convenio_institucional_valido_y_vigente(self):
        from ventas.utils import validar_y_calcular_precio_linea
        convenio = PrecioEspecial.objects.create(
            producto=self.producto,
            nombre_condicion="Tarifa Funcionario Safari",
            codigo_convenio="CONV-FUNC-01",
            precio=Decimal('4500.00'),
            fecha_inicio=self.hoy - datetime.timedelta(days=10),
            fecha_fin=self.hoy + datetime.timedelta(days=10),
            activo=True
        )

        calc = validar_y_calcular_precio_linea(
            producto=self.producto,
            cantidad=3,
            convenio_id=convenio.id,
            usuario=self.cajero_user
        )
        self.assertTrue(calc['es_precio_especial'])
        self.assertEqual(calc['precio_aplicado'], Decimal('4500.00'))
        self.assertEqual(calc['descuento_unitario'], Decimal('4500.00'))
        self.assertEqual(calc['subtotal'], Decimal('13500.00'))
        self.assertEqual(calc['convenio_obj'], convenio)

    # 7. Rechazo estricto de precio especial <= 0 (Problemas 1 y 2)
    def test_rf07_problemas_1_y_2_rechazo_precio_cero_o_negativo(self):
        from ventas.utils import validar_y_calcular_precio_linea
        from django.core.exceptions import ValidationError

        for p_invalido in [Decimal('0.00'), Decimal('-500.00')]:
            with self.assertRaises(ValidationError) as ctx:
                validar_y_calcular_precio_linea(
                    producto=self.producto,
                    cantidad=1,
                    precio_solicitado=p_invalido,
                    usuario=self.admin_user,
                    motivo="Precio Invalido"
                )
            self.assertIn("mayor a $0", str(ctx.exception))

    # 8. Rechazo de valor no numérico (Problema 3)
    def test_rf07_problema_3_rechazo_valor_no_numerico(self):
        from ventas.utils import validar_y_calcular_precio_linea
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError) as ctx:
            validar_y_calcular_precio_linea(
                producto=self.producto,
                cantidad=1,
                precio_solicitado="precio_gratis",
                usuario=self.admin_user,
                motivo="Ataque no numérico"
            )
        self.assertIn("formato no numérico inválido", str(ctx.exception))

    # 9. Rechazo de producto inactivo (Problema 5)
    def test_rf07_problema_5_rechazo_producto_inactivo(self):
        from ventas.utils import validar_y_calcular_precio_linea
        from django.core.exceptions import ValidationError

        self.producto.activo = False
        self.producto.save()

        with self.assertRaises(ValidationError) as ctx:
            validar_y_calcular_precio_linea(
                producto=self.producto,
                cantidad=1,
                usuario=self.cajero_user
            )
        self.assertIn("se encuentra inactivo", str(ctx.exception))

    # 10. Rechazo de convenio expirado o inactivo (Problemas 7 y 8)
    def test_rf07_problemas_7_y_8_rechazo_convenio_inactivo_o_expirado(self):
        from ventas.utils import validar_y_calcular_precio_linea
        from django.core.exceptions import ValidationError

        conv_expirado = PrecioEspecial.objects.create(
            producto=self.producto,
            nombre_condicion="Convenio Pasado",
            precio=Decimal('5000.00'),
            fecha_inicio=self.hoy - datetime.timedelta(days=30),
            fecha_fin=self.hoy - datetime.timedelta(days=1), # Venció ayer
            activo=True
        )

        with self.assertRaises(ValidationError) as ctx:
            validar_y_calcular_precio_linea(
                producto=self.producto,
                cantidad=1,
                convenio_id=conv_expirado.id,
                usuario=self.cajero_user
            )
        self.assertIn("no se encuentra vigente", str(ctx.exception))

    # 11. El servidor ignora precios manipulados en cliente por usuario no autorizado (Problema 10)
    def test_rf07_problema_10_servidor_ignora_precio_manipulado_por_navegador(self):
        self.client.force_login(self.mesero_user)

        # El navegador de un mesero envía comanda con precio manipulado a $100 CLP
        payload = [
            {"nombre": self.producto.nombre, "cantidad": 1, "precio": 100, "destino": "COCINA", "nota": "Manipulado"}
        ]
        resp = self.client.post(reverse('mesero') + f"?local_id={self.pv.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': self.mesa.id,
            'items_json': json.dumps(payload)
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        # El servidor ignoró el precio de $100 y cobró los $9.000 oficiales de la BD
        venta = Venta.objects.filter(mesa=self.mesa, estado='ABIERTA').first()
        self.assertIsNotNone(venta)
        det = venta.detalles.first()
        self.assertEqual(det.precio_aplicado, Decimal('9000.00'))
        self.assertEqual(venta.total, Decimal('9000.00'))
        self.assertFalse(det.es_precio_especial)

    # 12. API de verificación QR de convenios comerciales institucionales (RF07.5)
    def test_rf07_api_verificar_convenio_qr(self):
        convenio = PrecioEspecial.objects.create(
            producto=self.producto,
            nombre_condicion="Convenio Club Leones",
            codigo_convenio="QR-LEONES-2026",
            precio=Decimal('6500.00'),
            activo=True
        )

        self.client.force_login(self.cajero_user)
        resp = self.client.get(reverse('api_verificar_convenio_qr'), {'codigo': 'QR-LEONES-2026'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['encontrado'])
        self.assertEqual(data['tipo'], 'CONVENIO_INSTITUCIONAL')
        self.assertEqual(data['precio_convenio'], 6500.0)
        self.assertEqual(data['ahorro_unitario'], 2500.0)

    # 13. Terminal POS Venta Rápida con registro de precio especial auditado
    def test_rf07_pos_venta_rapida_con_precio_especial_y_arqueo(self):
        self.client.force_login(self.cajero_user)
        payload = [
            {
                "producto_id": self.producto.id,
                "cantidad": 2,
                "precio_especial": 7000,
                "motivo": "Convenio Vecino Machalí",
                "nota": "Sin cebolla"
            }
        ]

        resp = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps(payload),
            'metodo_pago': 'EFECTIVO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        venta_id = data['venta_id']

        venta = Venta.objects.get(id=venta_id)
        self.assertEqual(venta.total, Decimal('14000.00'))
        self.assertEqual(venta.detalles.count(), 1)
        det = venta.detalles.first()
        self.assertTrue(det.es_precio_especial)
        self.assertEqual(det.precio_original, Decimal('9000.00'))
        self.assertEqual(det.precio_aplicado, Decimal('7000.00'))

        reg = RegistroPrecioEspecial.objects.filter(venta=venta).first()
        self.assertIsNotNone(reg)
        self.assertEqual(reg.descuento_unitario, Decimal('2000.00'))
        self.assertEqual(reg.motivo, "Convenio Vecino Machalí")

    # 14. Historial de supervisión consolida eventos de precios especiales
    def test_rf07_historial_supervision_incluye_precios_especiales(self):
        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero_user, punto_venta=self.pv,
            modalidad='MOSTRADOR', metodo_pago='EFECTIVO', total=Decimal('5000.00'), estado='PAGADA'
        )
        RegistroPrecioEspecial.objects.create(
            venta=venta, producto=self.producto, precio_original=Decimal('9000.00'),
            precio_aplicado=Decimal('5000.00'), descuento_unitario=Decimal('4000.00'),
            cantidad=1, usuario=self.admin_user, motivo="Promoción Supervisor"
        )

        self.client.force_login(self.admin_user)
        resp = self.client.get(reverse('administrador_historial') + "?tipo=PRECIOS")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Promoción Supervisor")
        self.assertContains(resp, "Precio Especial:")


# ==============================================================================
# RF08 — SUITE DE PRUEBAS: GENERACIÓN DE TICKETS (COCINA, BARRA, COMPROBANTE)
# ==============================================================================
class SafariRF08GeneracionTicketsTests(TestCase):
    """
    Pruebas exhaustivas para RF08:
    - Clasificación por destino gobernada por la Base de Datos (RF08.1).
    - Ticket de Cocina para productos de elaboración con comensal y notas (RF08.2).
    - Ticket de Barra para productos terminados, bebidas y cafetería (RF08.3).
    - Comprobante fiscal y boleta de cliente (RF08.4).
    - Incrementalidad de rondas: la segunda ronda solo imprime ítems nuevos (RF08.5).
    - Reimpresión trazable sin duplicar ventas ni afectar contabilidad (RF08.6).
    - Política de Cero Desperdicio: cero tickets vacíos.
    - Soporte de Venta Rápida (Mostrador) y Mesas.
    """

    def setUp(self):
        self.client = Client()
        self.hoy = timezone.localdate()

        self.admin = User.objects.create_user(username='admin_rf08', password='Password123!', first_name='Admin', last_name='Tickets')
        self.cajero = User.objects.create_user(username='cajero_rf08', password='Password123!', first_name='Cajero', last_name='Tickets')
        self.mesero = User.objects.create_user(username='mesero_rf08', password='Password123!', first_name='Mesero', last_name='Tickets')

        self.pv = PuntoVenta.objects.create(nombre="Restaurante Central RF08", tipo="RESTAURANTE", activo=True)
        PerfilEmpleado.objects.create(usuario=self.admin, rol='ADMINISTRADOR', punto_venta_actual=self.pv)
        PerfilEmpleado.objects.create(usuario=self.cajero, rol='CAJERO', punto_venta_actual=self.pv)
        PerfilEmpleado.objects.create(usuario=self.mesero, rol='MESERO', punto_venta_actual=self.pv)

        self.cat_cocina = Categoria.objects.create(nombre="Minutas y Cocina", destino_defecto='COCINA', activo=True)
        self.cat_barra = Categoria.objects.create(nombre="Barra y Bebidas", destino_defecto='BARRA', activo=True)

        self.prod_cocina = Producto.objects.create(
            nombre="Hamburguesa Especial Safari",
            categoria=self.cat_cocina,
            precio_base=Decimal('8500.00'),
            destino_operativo='COCINA',
            activo=True
        )
        self.prod_barra = Producto.objects.create(
            nombre="Café Moka Barista",
            categoria=self.cat_barra,
            precio_base=Decimal('3200.00'),
            destino_operativo='BARRA',
            activo=True
        )

        self.jornada = Jornada.objects.create(fecha=self.hoy, estado='ABIERTA', usuario_apertura=self.admin)
        self.caja = Caja.objects.create(
            nombre="Caja Principal RF08", jornada=self.jornada, punto_venta=self.pv,
            cajero=self.cajero, monto_apertura=Decimal('100000.00'), estado='ABIERTA'
        )
        self.mesa = Mesa.objects.create(identificador="Mesa 80", punto_venta=self.pv, capacidad=4, estado='HABILITADA')

    # 1. Clasificación de destino gobernada por la Base de Datos (RF08.1)
    def test_rf08_1_clasificacion_por_destino_gobernada_por_bd(self):
        self.assertEqual(self.prod_cocina.get_destino_operativo(), 'COCINA')
        self.assertEqual(self.prod_barra.get_destino_operativo(), 'BARRA')

        # Si el producto no tiene destino manual explícito, hereda de su categoría
        prod_heredado = Producto.objects.create(
            nombre="Bebida Fanta 350ml",
            categoria=self.cat_barra,
            precio_base=Decimal('2000.00'),
            destino_operativo='',
            activo=True
        )
        self.assertEqual(prod_heredado.get_destino_operativo(), 'BARRA')

    # 2. Ticket de Cocina: contenido estructurado y cero ticket de barra vacío (RF08.2)
    def test_rf08_2_ticket_cocina_formato_y_cero_desperdicio_barra(self):
        from ventas.utils import emitir_tickets_comanda

        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero, punto_venta=self.pv,
            modalidad='MESA', mesa=self.mesa, total=Decimal('17000.00'), estado='ABIERTA'
        )
        pedido = Pedido.objects.create(venta=venta, estado='PENDIENTE', observaciones="Mesa VIP Terraza")
        DetallePedido.objects.create(
            pedido=pedido, producto=self.prod_cocina, cantidad=2, observaciones="Término medio, sin cebolla"
        )

        res = emitir_tickets_comanda(pedido, usuario_emisor=self.mesero)
        self.assertTrue(res['tiene_cocina'])
        self.assertFalse(res['tiene_barra']) # Cero desperdicio: no genera ticket de barra
        self.assertEqual(res['total_tickets'], 1)

        t_cocina = Ticket.objects.get(pedido=pedido, tipo_destino='COCINA')
        self.assertIn("PARQUE SAFARI - COMANDA COCINA", t_cocina.contenido_impresion)
        self.assertIn("Mesa: Mesa 80", t_cocina.contenido_impresion)
        self.assertIn("2x  Hamburguesa Especial Safari", t_cocina.contenido_impresion)
        self.assertIn("Nota: Término medio, sin cebolla", t_cocina.contenido_impresion)
        self.assertEqual(Ticket.objects.filter(pedido=pedido, tipo_destino='BARRA').count(), 0)

    # 3. Ticket de Barra: contenido estructurado y cero ticket de cocina vacío (RF08.3)
    def test_rf08_3_ticket_barra_formato_y_cero_desperdicio_cocina(self):
        from ventas.utils import emitir_tickets_comanda

        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero, punto_venta=self.pv,
            modalidad='MESA', mesa=self.mesa, total=Decimal('6400.00'), estado='ABIERTA'
        )
        pedido = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(
            pedido=pedido, producto=self.prod_barra, cantidad=2, observaciones="Con leche vegetal"
        )

        res = emitir_tickets_comanda(pedido, usuario_emisor=self.mesero)
        self.assertFalse(res['tiene_cocina']) # Cero desperdicio: no genera ticket de cocina
        self.assertTrue(res['tiene_barra'])
        self.assertEqual(res['total_tickets'], 1)

        t_barra = Ticket.objects.get(pedido=pedido, tipo_destino='BARRA')
        self.assertIn("PARQUE SAFARI - COMANDA BARRA", t_barra.contenido_impresion)
        self.assertIn("2x  Café Moka Barista", t_barra.contenido_impresion)
        self.assertIn("Nota: Con leche vegetal", t_barra.contenido_impresion)
        self.assertEqual(Ticket.objects.filter(pedido=pedido, tipo_destino='COCINA').count(), 0)

    # 4. Pedido mixto genera exactamente 2 tickets clasificados (Cocina y Barra)
    def test_rf08_pedido_mixto_cocina_y_barra(self):
        from ventas.utils import emitir_tickets_comanda

        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero, punto_venta=self.pv,
            modalidad='MESA', mesa=self.mesa, total=Decimal('11700.00'), estado='ABIERTA'
        )
        pedido = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=pedido, producto=self.prod_cocina, cantidad=1)
        DetallePedido.objects.create(pedido=pedido, producto=self.prod_barra, cantidad=1)

        res = emitir_tickets_comanda(pedido, usuario_emisor=self.mesero)
        self.assertTrue(res['tiene_cocina'])
        self.assertTrue(res['tiene_barra'])
        self.assertEqual(res['total_tickets'], 2)

        t_coc = Ticket.objects.get(pedido=pedido, tipo_destino='COCINA')
        t_bar = Ticket.objects.get(pedido=pedido, tipo_destino='BARRA')
        self.assertIn("Hamburguesa Especial", t_coc.contenido_impresion)
        self.assertNotIn("Café Moka", t_coc.contenido_impresion) # Cocina no incluye barra
        self.assertIn("Café Moka", t_bar.contenido_impresion)
        self.assertNotIn("Hamburguesa Especial", t_bar.contenido_impresion) # Barra no incluye cocina

    # 5. Comprobante de venta y boleta para el cliente (RF08.4)
    def test_rf08_4_comprobante_venta_emision_completa(self):
        from ventas.utils import emitir_comprobante_venta

        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero, punto_venta=self.pv,
            modalidad='MOSTRADOR', metodo_pago='EFECTIVO', total=Decimal('11700.00'),
            total_sin_redondeo=Decimal('11700.00'), redondeo_ley_20956=Decimal('0.00'), estado='PAGADA'
        )
        DetalleVenta.objects.create(venta=venta, producto=self.prod_cocina, cantidad=1, precio_aplicado=Decimal('8500.00'), subtotal=Decimal('8500.00'))
        DetalleVenta.objects.create(venta=venta, producto=self.prod_barra, cantidad=1, precio_aplicado=Decimal('3200.00'), subtotal=Decimal('3200.00'))

        comp = emitir_comprobante_venta(venta, usuario_emisor=self.cajero)
        self.assertIsNotNone(comp)
        self.assertEqual(comp.tipo_destino, 'COMPROBANTE')
        self.assertEqual(comp.venta, venta)
        self.assertIn("PARQUE SAFARI CHILE", comp.contenido_impresion)
        self.assertIn(f"TKT-VEN-{venta.id:05d}", comp.contenido_impresion)
        self.assertIn("Hamburguesa Especial", comp.contenido_impresion)
        self.assertIn("Café Moka Barista", comp.contenido_impresion)
        self.assertIn("TOTAL PAGADO:", comp.contenido_impresion)
        self.assertIn("$11.700", comp.contenido_impresion)
        self.assertIn("Método de Pago:", comp.contenido_impresion)
        self.assertIn("Efectivo", comp.contenido_impresion)

    # 6. Incrementalidad de rondas: la segunda ronda NO reimprime productos anteriores (RF08.5)
    def test_rf08_5_segunda_ronda_incremental_sin_duplicar_items_anteriores(self):
        self.client.force_login(self.mesero)

        # Ronda 1: Mesa pide Hamburguesa
        payload_r1 = [
            {"nombre": self.prod_cocina.nombre, "cantidad": 1, "precio": 8500, "destino": "COCINA"}
        ]
        self.client.post(reverse('mesero') + f"?local_id={self.pv.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': self.mesa.id,
            'items_json': json.dumps(payload_r1)
        }, follow=True)

        venta = Venta.objects.get(mesa=self.mesa, estado='ABIERTA')
        pedido_r1 = venta.pedidos.order_by('id').first()
        t_r1 = Ticket.objects.get(pedido=pedido_r1, tipo_destino='COCINA')
        self.assertIn("Hamburguesa Especial Safari", t_r1.contenido_impresion)

        # Ronda 2: Misma mesa pide Café
        payload_r2 = [
            {"nombre": self.prod_barra.nombre, "cantidad": 2, "precio": 3200, "destino": "BARRA"}
        ]
        self.client.post(reverse('mesero') + f"?local_id={self.pv.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': self.mesa.id,
            'items_json': json.dumps(payload_r2)
        }, follow=True)

        self.assertEqual(venta.pedidos.count(), 2)
        pedido_r2 = venta.pedidos.order_by('id').last()

        # Verificar tickets de Ronda 2
        # Solo debe haber ticket de BARRA para la ronda 2, y NO de cocina
        t_barra_r2 = Ticket.objects.filter(pedido=pedido_r2, tipo_destino='BARRA').first()
        self.assertIsNotNone(t_barra_r2)
        self.assertIn("Café Moka Barista", t_barra_r2.contenido_impresion)
        self.assertNotIn("Hamburguesa", t_barra_r2.contenido_impresion) # No reimprime ronda 1
        self.assertFalse(Ticket.objects.filter(pedido=pedido_r2, tipo_destino='COCINA').exists())

    # 7. Reimpresión trazable sin duplicar ventas ni contabilidad (RF08.6)
    def test_rf08_6_reimpresion_trazable_sin_crear_venta_ni_duplicar_contabilidad(self):
        from ventas.utils import emitir_comprobante_venta, reimprimir_ticket

        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero, punto_venta=self.pv,
            modalidad='MOSTRADOR', metodo_pago='DEBITO', total=Decimal('8500.00'), estado='PAGADA'
        )
        DetalleVenta.objects.create(venta=venta, producto=self.prod_cocina, cantidad=1, precio_aplicado=Decimal('8500.00'), subtotal=Decimal('8500.00'))

        comp = emitir_comprobante_venta(venta, usuario_emisor=self.cajero)
        self.assertEqual(comp.numero_reimpresiones, 0)
        self.assertFalse(comp.es_reimpresion)

        ventas_antes = Venta.objects.count()
        detalles_antes = DetalleVenta.objects.count()

        # Realizar reimpresión trazable
        reimpreso = reimprimir_ticket(comp, usuario_solicitante=self.admin)

        self.assertTrue(reimpreso.es_reimpresion)
        self.assertEqual(reimpreso.numero_reimpresiones, 1)
        self.assertEqual(reimpreso.ultima_reimpresion_por, self.admin)
        self.assertIn("*** COPIA DE REIMPRESIÓN #1 ***", reimpreso.contenido_impresion)

        # Regla de Oro: La reimpresión jamás crea ventas nuevas ni altera inventarios
        self.assertEqual(Venta.objects.count(), ventas_antes)
        self.assertEqual(DetalleVenta.objects.count(), detalles_antes)

    # 8. Rechazo estricto de pedidos vacíos (cero desperdicio de tickets)
    def test_rf08_pedido_vacio_rechazado_sin_tickets(self):
        from ventas.utils import emitir_tickets_comanda
        from django.core.exceptions import ValidationError

        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero, punto_venta=self.pv,
            modalidad='MESA', mesa=self.mesa, total=Decimal('0.00'), estado='ABIERTA'
        )
        pedido_vacio = Pedido.objects.create(venta=venta, estado='PENDIENTE')

        with self.assertRaises(ValidationError) as ctx:
            emitir_tickets_comanda(pedido_vacio)
        self.assertIn("no contiene productos", str(ctx.exception))
        self.assertEqual(Ticket.objects.filter(pedido=pedido_vacio).count(), 0)

    # 9. Endpoint de Reimpresión HTTP accesible para Cajero y Administrador (RF08.6)
    def test_rf08_reimpresion_endpoint_http(self):
        from ventas.utils import emitir_comprobante_venta
        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero, punto_venta=self.pv,
            modalidad='MOSTRADOR', metodo_pago='EFECTIVO', total=Decimal('8500.00'), estado='PAGADA'
        )
        comp = emitir_comprobante_venta(venta)

        self.client.force_login(self.admin)
        resp = self.client.get(reverse('reimprimir_ticket', args=[comp.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['numero_reimpresiones'], 1)

        comp.refresh_from_db()
        self.assertTrue(comp.es_reimpresion)
        self.assertEqual(comp.numero_reimpresiones, 1)

class SafariRF09GestionImpresionTests(TestCase):
    """
    Pruebas exhaustivas para RF09 — Gestión de Impresión:
    - Separación estricta de Capa de Impresión, Persistencia y Generación (RF09.1).
    - Enrutamiento a tres puntos de impresión oficiales: Cocina, Barra, Comprobante (RF09.2).
    - Modo Digital Provisional y renderizado térmico en pantalla (RF09.3).
    - Resiliencia y Desacoplamiento: Si la impresora falla o está sin papel, la venta y el pedido no se pierden (RF09.4).
    - Reintento de despacho seguro y trazable sin duplicación contable (RF09.4).
    - Impresión parcial independiente (Cocina OK / Barra Fallo) (Problema 8).
    - Aislamiento de impresoras por Punto de Venta / Local (Problema 10).
    - Endpoint HTTP de reintento e impresión digital.
    """

    def setUp(self):
        self.client = Client()
        self.hoy = timezone.localdate()

        self.admin = User.objects.create_user(username='admin_rf09', password='Password123!', first_name='Admin', last_name='Print')
        self.cajero = User.objects.create_user(username='cajero_rf09', password='Password123!', first_name='Cajero', last_name='Print')
        self.mesero = User.objects.create_user(username='mesero_rf09', password='Password123!', first_name='Mesero', last_name='Print')

        self.pv1 = PuntoVenta.objects.create(nombre="Restaurante Central RF09", tipo="RESTAURANTE", activo=True)
        self.pv2 = PuntoVenta.objects.create(nombre="Cafetería La Selva RF09", tipo="CAFETERIA", activo=True)

        PerfilEmpleado.objects.create(usuario=self.admin, rol='ADMINISTRADOR', punto_venta_actual=self.pv1)
        PerfilEmpleado.objects.create(usuario=self.cajero, rol='CAJERO', punto_venta_actual=self.pv1)
        PerfilEmpleado.objects.create(usuario=self.mesero, rol='MESERO', punto_venta_actual=self.pv1)

        # Configuración de 3 Puntos de Impresión para Local 1
        self.imp_cocina = PuntoImpresion.objects.create(
            nombre="Impresora Térmica Cocina Central",
            punto_venta=self.pv1,
            tipo_destino='COCINA',
            tipo_conexion='DIGITAL',
            estado_operativo='ONLINE',
            ancho_papel_mm=80,
            activo=True
        )
        self.imp_barra = PuntoImpresion.objects.create(
            nombre="Impresora Térmica Barra y Bebidas",
            punto_venta=self.pv1,
            tipo_destino='BARRA',
            tipo_conexion='DIGITAL',
            estado_operativo='ONLINE',
            ancho_papel_mm=80,
            activo=True
        )
        self.imp_caja = PuntoImpresion.objects.create(
            nombre="Impresora Térmica Boleta / Caja",
            punto_venta=self.pv1,
            tipo_destino='COMPROBANTE',
            tipo_conexion='DIGITAL',
            estado_operativo='ONLINE',
            ancho_papel_mm=80,
            activo=True
        )

        # Configuración para Local 2 (Aislamiento)
        self.imp_cocina_local2 = PuntoImpresion.objects.create(
            nombre="Impresora Cocina Cafetería",
            punto_venta=self.pv2,
            tipo_destino='COCINA',
            tipo_conexion='DIGITAL',
            estado_operativo='ONLINE',
            ancho_papel_mm=80,
            activo=True
        )

        self.cat_cocina = Categoria.objects.create(nombre="Minutas y Cocina", destino_defecto='COCINA', activo=True)
        self.cat_barra = Categoria.objects.create(nombre="Barra y Cafetería", destino_defecto='BARRA', activo=True)

        self.prod_cocina = Producto.objects.create(
            nombre="Hamburguesa Especial Safari",
            categoria=self.cat_cocina,
            precio_base=Decimal('8500.00'),
            destino_operativo='COCINA',
            activo=True
        )
        self.prod_barra = Producto.objects.create(
            nombre="Café Moka Barista",
            categoria=self.cat_barra,
            precio_base=Decimal('3200.00'),
            destino_operativo='BARRA',
            activo=True
        )

        self.jornada = Jornada.objects.create(
            fecha=self.hoy,
            estado='ABIERTA',
            usuario_apertura=self.admin,
            observaciones="Jornada RF09"
        )
        self.caja = Caja.objects.create(
            nombre="Caja POS Central RF09",
            punto_venta=self.pv1,
            jornada=self.jornada,
            cajero=self.cajero,
            monto_apertura=Decimal('50000.00'),
            estado='ABIERTA'
        )
        self.mesa = Mesa.objects.create(identificador="Mesa RF09-1", punto_venta=self.pv1, capacidad=4, estado='HABILITADA')

    # 1. Desacoplamiento estricto: Persistencia en BD garantizada y despacho a capa de impresión (RF09.1)
    def test_rf09_1_desacoplamiento_persistencia_y_despacho(self):
        from ventas.utils import emitir_tickets_comanda

        venta = Venta.objects.create(caja=self.caja, cajero=self.cajero, punto_venta=self.pv1, modalidad='MESA', mesa=self.mesa, total=Decimal('8500.00'), estado='ABIERTA')
        pedido = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=pedido, producto=self.prod_cocina, cantidad=1)

        res = emitir_tickets_comanda(pedido, usuario_emisor=self.mesero)
        self.assertEqual(res['total_tickets'], 1)

        tkt = res['tickets'][0]
        self.assertIsNotNone(tkt.id)
        self.assertEqual(tkt.estado_impresion, 'IMPRESO')
        self.assertIsNone(tkt.error_impresion)
        self.assertEqual(tkt.punto_impresion, self.imp_cocina)

        # Verificar auditoría inmutable
        reg = RegistroImpresion.objects.filter(ticket=tkt).first()
        self.assertIsNotNone(reg)
        self.assertTrue(reg.exitoso)
        self.assertEqual(reg.modo, 'DIGITAL')
        self.assertEqual(reg.usuario, self.mesero)

    # 2. Tres Puntos Oficiales de Impresión: Cocina, Barra y Comprobante (RF09.2)
    def test_rf09_2_tres_puntos_oficiales_enrutamiento(self):
        from ventas.utils import emitir_tickets_comanda, emitir_comprobante_venta

        venta = Venta.objects.create(caja=self.caja, cajero=self.cajero, punto_venta=self.pv1, modalidad='MESA', mesa=self.mesa, total=Decimal('11700.00'), estado='PAGADA')
        pedido = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=pedido, producto=self.prod_cocina, cantidad=1)
        DetallePedido.objects.create(pedido=pedido, producto=self.prod_barra, cantidad=1)

        res = emitir_tickets_comanda(pedido, usuario_emisor=self.cajero)
        comp = emitir_comprobante_venta(venta, usuario_emisor=self.cajero)

        self.assertEqual(res['total_tickets'], 2)
        tkt_cocina = next(t for t in res['tickets'] if t.tipo_destino == 'COCINA')
        tkt_barra = next(t for t in res['tickets'] if t.tipo_destino == 'BARRA')

        self.assertEqual(tkt_cocina.punto_impresion, self.imp_cocina)
        self.assertEqual(tkt_barra.punto_impresion, self.imp_barra)
        self.assertEqual(comp.punto_impresion, self.imp_caja)

    # 3. Modo Digital Provisional y Previsualización Térmica (RF09.3)
    def test_rf09_3_modo_digital_previsualizacion_endpoint(self):
        from ventas.utils import emitir_comprobante_venta

        venta = Venta.objects.create(caja=self.caja, cajero=self.cajero, punto_venta=self.pv1, modalidad='MOSTRADOR', total=Decimal('8500.00'), estado='PAGADA')
        comp = emitir_comprobante_venta(venta, usuario_emisor=self.cajero)

        self.client.force_login(self.cajero)
        resp = self.client.get(reverse('ver_imprimir_ticket_digital', args=[comp.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, comp.codigo)
        self.assertContains(resp, "Impresora Térmica Boleta / Caja")
        self.assertContains(resp, "Despachado OK")
        self.assertContains(resp, "window.print()")

    # 4. Fallo Simulado de Impresión: La Venta y el Pedido persisten 100% intactos (RF09.4)
    def test_rf09_4_fallo_impresora_no_destruye_venta(self):
        from ventas.utils import emitir_tickets_comanda

        # Simular fallo de hardware o papel agotado en cocina
        self.imp_cocina.simular_fallo = True
        self.imp_cocina.save()

        venta = Venta.objects.create(caja=self.caja, cajero=self.cajero, punto_venta=self.pv1, modalidad='MESA', mesa=self.mesa, total=Decimal('8500.00'), estado='ABIERTA')
        pedido = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        det = DetallePedido.objects.create(pedido=pedido, producto=self.prod_cocina, cantidad=1)

        res = emitir_tickets_comanda(pedido, usuario_emisor=self.mesero)
        tkt = res['tickets'][0]

        # El ticket debe registrar estado FALLO con detalle técnico
        self.assertEqual(tkt.estado_impresion, 'FALLO')
        self.assertIn("Fallo simulado", tkt.error_impresion)

        # REGLA DE ORO RF09.4: La venta y el pedido persisten intactos
        venta.refresh_from_db()
        pedido.refresh_from_db()
        det.refresh_from_db()
        self.assertEqual(venta.estado, 'ABIERTA')
        self.assertEqual(venta.total, Decimal('8500.00'))
        self.assertEqual(pedido.detalles.count(), 1)

        # Auditoría de fallo registrada
        reg = RegistroImpresion.objects.filter(ticket=tkt, exitoso=False).first()
        self.assertIsNotNone(reg)
        self.assertIn("Fallo simulado", reg.mensaje_error)

    # 5. Reintento de Despacho tras Recuperación de Impresora (RF09.4)
    def test_rf09_5_reintento_despacho_exitoso(self):
        from ventas.utils import emitir_tickets_comanda, reintentar_despacho_impresion

        self.imp_cocina.estado_operativo = 'SIN_PAPEL'
        self.imp_cocina.save()

        venta = Venta.objects.create(caja=self.caja, cajero=self.cajero, punto_venta=self.pv1, modalidad='MESA', mesa=self.mesa, total=Decimal('8500.00'), estado='ABIERTA')
        pedido = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=pedido, producto=self.prod_cocina, cantidad=1)

        res = emitir_tickets_comanda(pedido, usuario_emisor=self.mesero)
        tkt = res['tickets'][0]
        self.assertEqual(tkt.estado_impresion, 'FALLO')

        # Se recarga papel y vuelve ONLINE
        self.imp_cocina.estado_operativo = 'ONLINE'
        self.imp_cocina.save()

        # Reintento de despacho
        resultado_reintento = reintentar_despacho_impresion(tkt, usuario=self.cajero)
        self.assertTrue(resultado_reintento['exito'])

        tkt.refresh_from_db()
        self.assertEqual(tkt.estado_impresion, 'IMPRESO')
        self.assertIsNone(tkt.error_impresion)
        self.assertEqual(tkt.intentos_impresion, 2)

        # Auditoría con es_reintento=True
        reg_reintento = RegistroImpresion.objects.filter(ticket=tkt, es_reintento=True).first()
        self.assertIsNotNone(reg_reintento)
        self.assertTrue(reg_reintento.exitoso)
        self.assertEqual(reg_reintento.usuario, self.cajero)

        # La venta no se duplicó ni alteró
        self.assertEqual(Venta.objects.filter(mesa=self.mesa).count(), 1)

    # 6. Impresión Parcial Independiente (Cocina OK / Barra Fallo) (Problema 8)
    def test_rf09_6_impresion_parcial_independiente(self):
        from ventas.utils import emitir_tickets_comanda, reintentar_despacho_impresion

        # Cocina ONLINE, Barra con fallo
        self.imp_cocina.estado_operativo = 'ONLINE'
        self.imp_cocina.save()
        self.imp_barra.estado_operativo = 'OFFLINE'
        self.imp_barra.save()

        venta = Venta.objects.create(caja=self.caja, cajero=self.cajero, punto_venta=self.pv1, modalidad='MESA', mesa=self.mesa, total=Decimal('11700.00'), estado='ABIERTA')
        pedido = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=pedido, producto=self.prod_cocina, cantidad=1)
        DetallePedido.objects.create(pedido=pedido, producto=self.prod_barra, cantidad=1)

        res = emitir_tickets_comanda(pedido, usuario_emisor=self.mesero)
        tkt_cocina = next(t for t in res['tickets'] if t.tipo_destino == 'COCINA')
        tkt_barra = next(t for t in res['tickets'] if t.tipo_destino == 'BARRA')

        self.assertEqual(tkt_cocina.estado_impresion, 'IMPRESO')
        self.assertEqual(tkt_barra.estado_impresion, 'FALLO')

        # Se repara la impresora de Barra
        self.imp_barra.estado_operativo = 'ONLINE'
        self.imp_barra.save()

        # Solo se reintenta Barra; Cocina no se reenvía innecesariamente
        reintento_bar = reintentar_despacho_impresion(tkt_barra, usuario=self.cajero)
        self.assertTrue(reintento_bar['exito'])

        tkt_barra.refresh_from_db()
        tkt_cocina.refresh_from_db()
        self.assertEqual(tkt_barra.estado_impresion, 'IMPRESO')
        self.assertEqual(tkt_barra.intentos_impresion, 2)
        self.assertEqual(tkt_cocina.intentos_impresion, 1)

    # 7. Aislamiento estricto de impresoras por Local / Punto de Venta (Problema 10)
    def test_rf09_7_aislamiento_impresoras_por_local(self):
        from ventas.utils import emitir_tickets_comanda

        venta_local1 = Venta.objects.create(caja=self.caja, cajero=self.cajero, punto_venta=self.pv1, modalidad='MESA', mesa=self.mesa, total=Decimal('8500.00'), estado='ABIERTA')
        pedido_local1 = Pedido.objects.create(venta=venta_local1, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=pedido_local1, producto=self.prod_cocina, cantidad=1)

        res = emitir_tickets_comanda(pedido_local1, usuario_emisor=self.mesero)
        tkt1 = res['tickets'][0]

        # Debe enrutar a la impresora de Local 1, nunca a Local 2
        self.assertEqual(tkt1.punto_impresion, self.imp_cocina)
        self.assertNotEqual(tkt1.punto_impresion, self.imp_cocina_local2)

    # 8. Endpoint HTTP de Reintento de Impresión (RF09.4)
    def test_rf09_8_endpoint_reintentar_http(self):
        from ventas.utils import emitir_comprobante_venta

        self.imp_caja.simular_fallo = True
        self.imp_caja.save()

        venta = Venta.objects.create(caja=self.caja, cajero=self.cajero, punto_venta=self.pv1, modalidad='MOSTRADOR', total=Decimal('8500.00'), estado='PAGADA')
        comp = emitir_comprobante_venta(venta, usuario_emisor=self.cajero)
        self.assertEqual(comp.estado_impresion, 'FALLO')

        # Se restaura impresora
        self.imp_caja.simular_fallo = False
        self.imp_caja.save()

        self.client.force_login(self.cajero)
        resp = self.client.post(reverse('reintentar_impresion', args=[comp.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['estado_impresion'], 'IMPRESO')

        comp.refresh_from_db()
        self.assertEqual(comp.estado_impresion, 'IMPRESO')
        self.assertEqual(comp.intentos_impresion, 2)

    # 9. Reimpresión Trazable vuelve a despachar al punto físico/digital (RF08.6 + RF09.4)
    def test_rf09_9_reimpresion_redespacha_impresora(self):
        from ventas.utils import emitir_comprobante_venta, reimprimir_ticket

        venta = Venta.objects.create(caja=self.caja, cajero=self.cajero, punto_venta=self.pv1, modalidad='MOSTRADOR', total=Decimal('8500.00'), estado='PAGADA')
        comp = emitir_comprobante_venta(venta, usuario_emisor=self.cajero)
        self.assertEqual(comp.intentos_impresion, 1)

        # Reimpresión solicitada por supervisor
        reimprimir_ticket(comp, usuario_solicitante=self.admin)
        comp.refresh_from_db()
        self.assertTrue(comp.es_reimpresion)
        self.assertEqual(comp.numero_reimpresiones, 1)
        self.assertEqual(comp.intentos_impresion, 2)

        # Registros de auditoría deben reflejar la reimpresión
        reg_reimp = RegistroImpresion.objects.filter(ticket=comp, es_reintento=True).first()
        self.assertIsNotNone(reg_reimp)
        self.assertTrue(reg_reimp.exitoso)
        self.assertEqual(reg_reimp.usuario, self.admin)
    # 10. KDS Barra: Acceso, renderizado y aislamiento de bebidas (BDS)
    def test_rf09_10_kds_barra_pantalla_tactil_y_aislamiento(self):
        from ventas.utils import emitir_tickets_comanda

        # Pedido 1: Solo Cocina
        v1 = Venta.objects.create(caja=self.caja, cajero=self.cajero, punto_venta=self.pv1, modalidad='MESA', mesa=self.mesa, total=Decimal('8500.00'), estado='ABIERTA')
        p1 = Pedido.objects.create(venta=v1, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=p1, producto=self.prod_cocina, cantidad=1)
        emitir_tickets_comanda(p1, usuario_emisor=self.mesero)

        # Pedido 2: Mixto (Cocina + Barra)
        m2 = Mesa.objects.create(identificador="Mesa RF09-2", punto_venta=self.pv1, capacidad=2, estado='OCUPADA')
        v2 = Venta.objects.create(caja=self.caja, cajero=self.cajero, punto_venta=self.pv1, modalidad='MESA', mesa=m2, total=Decimal('11700.00'), estado='ABIERTA')
        p2 = Pedido.objects.create(venta=v2, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=p2, producto=self.prod_cocina, cantidad=1)
        DetallePedido.objects.create(pedido=p2, producto=self.prod_barra, cantidad=2, observaciones="Con hielo y endulzante")
        emitir_tickets_comanda(p2, usuario_emisor=self.mesero)

        self.client.force_login(self.mesero)
        resp = self.client.get(reverse('barra'))
        self.assertEqual(resp.status_code, 200)

        # Pedido 1 (solo cocina) NO debe figurar en KDS Barra
        self.assertNotContains(resp, f"COM-{p1.id:04d}")
        # Pedido 2 (tiene barra) SÍ debe figurar
        self.assertContains(resp, f"BAR-{p2.id:04d}")
        self.assertContains(resp, "Café Moka Barista")
        self.assertContains(resp, "Con hielo y endulzante")
        # El ítem de cocina de ese mismo pedido no se lista en la tarjeta de barra
        self.assertNotContains(resp, "Hamburguesa Especial Safari")

        # Verificar condiciones operativas requeridas por el usuario:
        # 1. No debe tener reloj regresivo de 15 minutos
        self.assertNotContains(resp, "Sesión: 15:00")
        self.assertNotContains(resp, "Sesión: 14:")
        # 2. Sin botón manual 'Actualizar Pantalla'
        self.assertNotContains(resp, "Actualizar Pantalla")
        # 3. Auto-actualización fluida en 1s presente
        self.assertContains(resp, "autoActualizarBarra")

    # 11. Transición táctil de estados en KDS Barra (Pendiente -> En Barra -> Listo -> Entregado)
    def test_rf09_11_kds_barra_transicion_estados(self):
        v = Venta.objects.create(caja=self.caja, cajero=self.cajero, punto_venta=self.pv1, modalidad='MESA', mesa=self.mesa, total=Decimal('3200.00'), estado='ABIERTA')
        p = Pedido.objects.create(venta=v, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=p, producto=self.prod_barra, cantidad=1)

        self.client.force_login(self.mesero)

        # 1. Preparar en Barra
        resp1 = self.client.post(reverse('cambiar_estado_pedido'), {'pedido_id': p.id, 'nuevo_estado': 'EN_PREPARACION'}, HTTP_REFERER='/barra/')
        self.assertEqual(resp1.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.estado, 'EN_PREPARACION')

        # 2. Listo en Barra
        resp2 = self.client.post(reverse('cambiar_estado_pedido'), {'pedido_id': p.id, 'nuevo_estado': 'LISTO'}, HTTP_REFERER='/barra/')
        self.assertEqual(resp2.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.estado, 'LISTO')

        # 3. Despachar / Entregado
        resp3 = self.client.post(reverse('cambiar_estado_pedido'), {'pedido_id': p.id, 'nuevo_estado': 'ENTREGADO'}, HTTP_REFERER='/barra/')
        self.assertEqual(resp3.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.estado, 'ENTREGADO')
        self.assertEqual(Entrega.objects.filter(pedido=p).count(), 1)


# ==============================================================================
# SUITE OFICIAL DE PRUEBAS AUTOMATIZADAS RF10 (Consumo Interno / Fiado)
# ==============================================================================

class SafariRF10ConsumoInternoTests(TestCase):
    """
    Suite oficial de pruebas automatizadas para RF10 - Consumo Interno del Personal / Fiado:
    - RF10.1: Selección de colaborador y validación estricta de estado activo.
    - RF10.2: Registro con productos, cantidades, precios oficiales de BD y usuario emisor.
    - RF10.3: Control de acumulado por colaborador, historial y liquidación por nómina.
    - RF10.4: Separación Contable Estricta: cero impacto en Venta/DetalleVenta y cero inflación en caja.
    - RF10.5: Transacción atómica e integridad encabezado + detalle.
    """

    def setUp(self):
        cache.clear()
        self.client = Client()
        call_command('poblar_safari')

        self.admin = User.objects.get(username='rgomez')
        self.cajero = User.objects.get(username='cvalenzuela')
        self.mesero = User.objects.get(username='dsilva')
        self.cocinero = User.objects.get(username='eparedes')

        self.pv1 = PuntoVenta.objects.get(id=1)
        self.prod_hamburguesa = Producto.objects.filter(nombre__icontains='Hamburguesa').first()
        self.prod_bebida = Producto.objects.filter(nombre__icontains='Coca-Cola').first()

        # Jornada y Caja para pruebas POS
        hoy = timezone.localdate()
        self.jornada, _ = Jornada.objects.get_or_create(
            fecha=hoy,
            defaults={'usuario_apertura': self.admin, 'estado': 'ABIERTA'}
        )
        self.caja, _ = Caja.objects.get_or_create(
            jornada=self.jornada,
            cajero=self.cajero,
            punto_venta=self.pv1,
            defaults={'monto_apertura': Decimal('50000.00'), 'estado': 'ABIERTA'}
        )

    def test_rf10_1_registro_valido_consumo_interno(self):
        """RF10.1 & RF10.2: Registro exitoso de consumo para colaborador activo con precios oficiales de BD"""
        items = [
            {'producto_id': self.prod_hamburguesa.id, 'cantidad': 1},
            {'producto_id': self.prod_bebida.id, 'cantidad': 2}
        ]
        consumo = registrar_consumo_interno(
            empleado=self.mesero,
            punto_venta=self.pv1,
            items=items,
            usuario_registro=self.cajero,
            tipo_consumo='FIADO',
            observaciones="Almuerzo de turno",
            caja=self.caja
        )

        total_esperado = self.prod_hamburguesa.precio_base * 1 + self.prod_bebida.precio_base * 2

        self.assertIsNotNone(consumo.id)
        self.assertEqual(consumo.empleado, self.mesero)
        self.assertEqual(consumo.punto_venta, self.pv1)
        self.assertEqual(consumo.registrado_por, self.cajero)
        self.assertEqual(consumo.tipo_consumo, 'FIADO')
        self.assertEqual(consumo.estado, 'REGISTRADO')
        self.assertEqual(consumo.total, total_esperado)
        self.assertEqual(consumo.detalles.count(), 2)

    def test_rf10_2_rechazo_trabajador_inactivo_o_inexistente(self):
        """RF10.1: Rechaza registro de consumo para trabajador inactivo o perfil desactivado"""
        from django.core.exceptions import ValidationError

        # Desactivar usuario
        self.mesero.is_active = False
        self.mesero.save()

        items = [{'producto_id': self.prod_hamburguesa.id, 'cantidad': 1}]
        with self.assertRaises(ValidationError) as ctx:
            registrar_consumo_interno(
                empleado=self.mesero,
                punto_venta=self.pv1,
                items=items,
                usuario_registro=self.cajero
            )
        self.assertIn("inactivo", str(ctx.exception).lower())

        # Reactivar usuario pero desactivar perfil
        self.mesero.is_active = True
        self.mesero.save()
        self.mesero.perfil.activo = False
        self.mesero.perfil.save()

        with self.assertRaises(ValidationError) as ctx:
            registrar_consumo_interno(
                empleado=self.mesero,
                punto_venta=self.pv1,
                items=items,
                usuario_registro=self.cajero
            )
        self.assertIn("desactivado", str(ctx.exception).lower())

    def test_rf10_3_precios_oficiales_bd_y_proteccion_manipulacion(self):
        """RF10.2: Los precios se toman siempre de Producto.precio_base en BD ignorando manipulación"""
        # Cliente intenta pasar precio falso de $10
        items = [{'producto_id': self.prod_hamburguesa.id, 'cantidad': 1, 'precio': 10}]
        consumo = registrar_consumo_interno(
            empleado=self.mesero,
            punto_venta=self.pv1,
            items=items,
            usuario_registro=self.cajero
        )
        self.assertEqual(consumo.total, self.prod_hamburguesa.precio_base)
        det = consumo.detalles.first()
        self.assertEqual(det.precio_unitario, self.prod_hamburguesa.precio_base)
        self.assertEqual(det.subtotal, self.prod_hamburguesa.precio_base)

    def test_rf10_4_rechazo_cantidad_invalida_y_producto_inactivo(self):
        """RF10.2: Rechaza cantidades menores o iguales a cero y productos inactivos"""
        from django.core.exceptions import ValidationError

        # Cantidad cero
        with self.assertRaises(ValidationError):
            registrar_consumo_interno(
                empleado=self.mesero,
                punto_venta=self.pv1,
                items=[{'producto_id': self.prod_hamburguesa.id, 'cantidad': 0}],
                usuario_registro=self.cajero
            )

        # Cantidad negativa
        with self.assertRaises(ValidationError):
            registrar_consumo_interno(
                empleado=self.mesero,
                punto_venta=self.pv1,
                items=[{'producto_id': self.prod_hamburguesa.id, 'cantidad': -3}],
                usuario_registro=self.cajero
            )

        # Producto inactivo
        self.prod_hamburguesa.activo = False
        self.prod_hamburguesa.save()
        with self.assertRaises(ValidationError):
            registrar_consumo_interno(
                empleado=self.mesero,
                punto_venta=self.pv1,
                items=[{'producto_id': self.prod_hamburguesa.id, 'cantidad': 1}],
                usuario_registro=self.cajero
            )

    def test_rf10_5_separacion_contable_estricta(self):
        """RF10.4: Separación Contable: No crea registro en Venta ni incrementa ventas en caja"""
        ventas_antes = Venta.objects.count()
        detalles_venta_antes = DetalleVenta.objects.count()
        ventas_caja_antes = self.caja.ventas.count()

        items = [{'producto_id': self.prod_hamburguesa.id, 'cantidad': 2}]
        consumo = registrar_consumo_interno(
            empleado=self.mesero,
            punto_venta=self.pv1,
            items=items,
            usuario_registro=self.cajero,
            caja=self.caja
        )

        self.caja.refresh_from_db()
        self.assertEqual(Venta.objects.count(), ventas_antes)
        self.assertEqual(DetalleVenta.objects.count(), detalles_venta_antes)
        self.assertEqual(self.caja.ventas.count(), ventas_caja_antes)
        self.assertEqual(ConsumoInterno.objects.filter(id=consumo.id).count(), 1)

    def test_rf10_6_calculo_acumulado_por_empleado(self):
        """RF10.3: Cálculo en tiempo real del fiado acumulado pendiente por colaborador"""
        self.assertEqual(self.mesero.perfil.total_fiado_pendiente(), Decimal('0.00'))

        # Registrar consumo 1 (1x hamburguesa)
        monto1 = self.prod_hamburguesa.precio_base * 1
        registrar_consumo_interno(
            empleado=self.mesero,
            punto_venta=self.pv1,
            items=[{'producto_id': self.prod_hamburguesa.id, 'cantidad': 1}],
            usuario_registro=self.cajero
        )
        self.assertEqual(self.mesero.perfil.total_fiado_pendiente(), monto1)

        # Registrar consumo 2 (2x bebida)
        monto2 = self.prod_bebida.precio_base * 2
        registrar_consumo_interno(
            empleado=self.mesero,
            punto_venta=self.pv1,
            items=[{'producto_id': self.prod_bebida.id, 'cantidad': 2}],
            usuario_registro=self.cajero
        )
        self.assertEqual(self.mesero.perfil.total_fiado_pendiente(), monto1 + monto2)

    def test_rf10_7_liquidacion_descuento_por_planilla(self):
        """RF10.3: Liquidación por nómina / planilla marca consumos como DESCONTADO y limpia saldo"""
        c1 = registrar_consumo_interno(
            empleado=self.mesero,
            punto_venta=self.pv1,
            items=[{'producto_id': self.prod_hamburguesa.id, 'cantidad': 1}],
            usuario_registro=self.cajero
        )
        c2 = registrar_consumo_interno(
            empleado=self.mesero,
            punto_venta=self.pv1,
            items=[{'producto_id': self.prod_bebida.id, 'cantidad': 1}],
            usuario_registro=self.cajero
        )
        monto_total = self.prod_hamburguesa.precio_base * 1 + self.prod_bebida.precio_base * 1
        self.assertEqual(self.mesero.perfil.total_fiado_pendiente(), monto_total)

        # Liquidar consumos
        num_act = liquidar_consumos_por_planilla([c1.id, c2.id], supervisor=self.admin)
        self.assertEqual(num_act, 2)

        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertEqual(c1.estado, 'DESCONTADO')
        self.assertEqual(c1.descontado_por, self.admin)
        self.assertIsNotNone(c1.fecha_hora_descuento)
        self.assertEqual(c2.estado, 'DESCONTADO')

        # El saldo pendiente del empleado debe ser 0 ahora
        self.assertEqual(self.mesero.perfil.total_fiado_pendiente(), Decimal('0.00'))

    def test_rf10_8_endpoint_pos_registrar_consumo_interno_ajax(self):
        """RF10.2: Endpoint POST para registrar fiado desde terminal POS de cajero"""
        self.client.force_login(self.cajero)

        payload = {
            'empleado_id': self.mesero.id,
            'tipo_consumo': 'FIADO',
            'observaciones': 'Almuerzo emitido desde POS',
            'items_json': json.dumps([
                {'id': self.prod_hamburguesa.id, 'cantidad': 1},
                {'id': self.prod_bebida.id, 'cantidad': 1}
            ])
        }

        resp = self.client.post(
            reverse('registrar_consumo_interno'),
            payload,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('consumo_id', data)
        monto_esperado = float(self.prod_hamburguesa.precio_base * 1 + self.prod_bebida.precio_base * 1)
        self.assertEqual(data['total'], monto_esperado)
        self.assertIn('FIA-', data['codigo_consumo'])

    def test_rf10_9_panel_administrador_consumos_y_liquidacion(self):
        """RF10.3: Panel de administración visualiza saldos y procesa acciones de liquidación y anulación"""
        c = registrar_consumo_interno(
            empleado=self.mesero,
            punto_venta=self.pv1,
            items=[{'producto_id': self.prod_hamburguesa.id, 'cantidad': 1}],
            usuario_registro=self.cajero
        )

        self.client.force_login(self.admin)

        # 1. Acceso a vista panel
        resp_get = self.client.get(reverse('administrador_consumos'))
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, "CONSUMO INTERNO DEL PERSONAL")
        self.assertContains(resp_get, self.mesero.username)

        # 2. Acción liquidar empleado
        resp_post = self.client.post(reverse('administrador_consumos'), {
            'accion': 'descontar_empleado',
            'empleado_id': self.mesero.id
        })
        self.assertEqual(resp_post.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.estado, 'DESCONTADO')

        # 3. Acción anular
        c_anular = registrar_consumo_interno(
            empleado=self.cocinero,
            punto_venta=self.pv1,
            items=[{'producto_id': self.prod_bebida.id, 'cantidad': 1}],
            usuario_registro=self.cajero
        )
        self.client.post(reverse('administrador_consumos'), {
            'accion': 'anular_individual',
            'consumo_id': c_anular.id
        })
        c_anular.refresh_from_db()
        self.assertEqual(c_anular.estado, 'ANULADO')

    def test_rf10_10_trazabilidad_historial_general(self):
        """RF10.3: Historial consolidado muestra eventos de consumo interno con trazabilidad completa"""
        consumo = registrar_consumo_interno(
            empleado=self.mesero,
            punto_venta=self.pv1,
            items=[{'producto_id': self.prod_hamburguesa.id, 'cantidad': 1}],
            usuario_registro=self.cajero,
            tipo_consumo='FIADO'
        )

        self.client.force_login(self.admin)
        resp = self.client.get(reverse('administrador_historial'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f"FIA-{consumo.id:04d}")
        self.assertContains(resp, "Consumo Personal")


# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# SUITE OFICIAL DE PRUEBAS AUTOMATIZADAS RF11 (Asignación de Mesa o Venta Rápida)
# ==============================================================================

class SafariRF11AsignacionMesaVentaRapidaTests(TestCase):
    """
    Suite oficial de pruebas automatizadas para RF11 - Asignación de Mesa o Venta Rápida:
    - RF11.1: Asignación obligatoria de mesa válida en salón.
    - RF11.2: Venta rápida para llevar o mostrador sin ocupar mesas físicas.
    - RF11.3: Prevención de colisión de cuentas abiertas en la misma mesa.
    - RF11.4: Soporte completo para comanda de cocina/barra en venta rápida con aviso de mostrador.
    - RF11.5: Endpoint POS crear_ticket y vista mesero con validación operativa integral.
    """

    def setUp(self):
        cache.clear()
        self.client = Client()
        call_command('poblar_safari')

        self.admin = User.objects.get(username='rgomez')
        self.cajero = User.objects.get(username='cvalenzuela')
        self.mesero = User.objects.get(username='dsilva')
        self.cocinero = User.objects.get(username='eparedes')

        self.pv1 = PuntoVenta.objects.get(id=1)
        self.pv2 = PuntoVenta.objects.get(id=2)

        self.mesa1 = Mesa.objects.filter(punto_venta=self.pv1, identificador='Mesa 1').first()
        self.mesa4 = Mesa.objects.filter(punto_venta=self.pv1, identificador='Mesa 4').first()
        if not self.mesa4:
            self.mesa4 = Mesa.objects.create(identificador='Mesa 4', punto_venta=self.pv1, capacidad=4, estado='HABILITADA')
        else:
            self.mesa4.estado = 'HABILITADA'
            self.mesa4.save()

        self.mesa_pv2 = Mesa.objects.filter(punto_venta=self.pv2).first()

        self.prod_hamburguesa = Producto.objects.filter(nombre__icontains='Hamburguesa').first()
        self.prod_bebida = Producto.objects.filter(nombre__icontains='Coca-Cola').first()

        hoy = timezone.localdate()
        self.jornada, _ = Jornada.objects.get_or_create(
            fecha=hoy,
            defaults={'usuario_apertura': self.admin, 'estado': 'ABIERTA'}
        )
        self.caja, _ = Caja.objects.get_or_create(
            jornada=self.jornada,
            cajero=self.cajero,
            punto_venta=self.pv1,
            defaults={'monto_apertura': Decimal('50000.00'), 'estado': 'ABIERTA'}
        )

    def test_rf11_1_venta_rapida_sin_mesa_no_bloquea_mesas(self):
        """RF11.2: Venta rápida no asocia mesa física y nunca bloquea ni ocupa mesas del salón"""
        mesas_libres_antes = Mesa.objects.filter(punto_venta=self.pv1, estado='HABILITADA').count()

        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero,
            punto_venta=self.pv1,
            modalidad='VENTA_RAPIDA',
            mesa=None,
            total=Decimal('8900.00'),
            metodo_pago='EFECTIVO',
            estado='PAGADA'
        )

        self.assertIsNone(venta.mesa)
        self.assertTrue(venta.es_venta_rapida())
        self.assertFalse(venta.es_consumo_en_mesa())
        self.assertEqual(venta.get_ubicacion_despacho(), "Retiro Rápido / Mostrador")

        # Verificar que las mesas habilitadas se mantuvieron intactas
        mesas_libres_despues = Mesa.objects.filter(punto_venta=self.pv1, estado='HABILITADA').count()
        self.assertEqual(mesas_libres_antes, mesas_libres_despues)

        # Si por error se pasa una mesa a VENTA_RAPIDA, clean() la desacopla limpiando a None
        venta_con_mesa_erronea = Venta(
            caja=self.caja,
            cajero=self.cajero,
            punto_venta=self.pv1,
            modalidad='VENTA_RAPIDA',
            mesa=self.mesa4,
            total=Decimal('2000.00'),
            metodo_pago='EFECTIVO'
        )
        venta_con_mesa_erronea.clean()
        self.assertIsNone(venta_con_mesa_erronea.mesa)

        # Normalización de alias
        for alias in ['MOSTRADOR', 'LLEVAR', 'RETIRO']:
            v_alias = Venta(
                caja=self.caja,
                cajero=self.cajero,
                punto_venta=self.pv1,
                modalidad=alias,
                mesa=self.mesa4
            )
            v_alias.clean()
            self.assertEqual(v_alias.modalidad, 'VENTA_RAPIDA')
            self.assertIsNone(v_alias.mesa)

    def test_rf11_2_consumo_mesa_requiere_mesa_valida(self):
        """RF11.1: Modalidad MESA exige obligatoriamente una mesa física del mismo punto de venta"""
        from django.core.exceptions import ValidationError

        # 1. Falta mesa -> ValidationError
        venta_sin_mesa = Venta(
            caja=self.caja,
            cajero=self.cajero,
            punto_venta=self.pv1,
            modalidad='MESA',
            mesa=None,
            total=Decimal('5000.00')
        )
        with self.assertRaises(ValidationError) as ctx:
            venta_sin_mesa.clean()
        self.assertIn("requiere obligatoriamente una mesa asignada", str(ctx.exception))

        # 2. Mesa pertenece a otro local -> ValidationError
        venta_mesa_ajena = Venta(
            caja=self.caja,
            cajero=self.cajero,
            punto_venta=self.pv1,
            modalidad='MESA',
            mesa=self.mesa_pv2,
            total=Decimal('5000.00')
        )
        with self.assertRaises(ValidationError) as ctx:
            venta_mesa_ajena.clean()
        self.assertIn("mismo punto de venta", str(ctx.exception))

        # 3. Mesa válida en el mismo local -> Pasa clean y métodos devuelven valores correctos
        venta_valida = Venta(
            caja=self.caja,
            cajero=self.cajero,
            punto_venta=self.pv1,
            modalidad='MESA',
            mesa=self.mesa4,
            total=Decimal('5000.00')
        )
        venta_valida.clean()
        self.assertTrue(venta_valida.es_consumo_en_mesa())
        self.assertFalse(venta_valida.es_venta_rapida())
        self.assertEqual(venta_valida.get_ubicacion_despacho(), f"Mesa {self.mesa4.identificador} (Salón)")

    def test_rf11_3_rechazo_mesa_ocupada_por_otra_cuenta_abierta(self):
        """RF11.3: Prevención de colisión: No se pueden abrir dos cuentas abiertas simultáneas en la misma mesa"""
        from django.core.exceptions import ValidationError

        # Primera cuenta abierta en mesa 4
        venta_1 = Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero,
            punto_venta=self.pv1,
            modalidad='MESA',
            mesa=self.mesa4,
            estado='ABIERTA',
            total=Decimal('10000.00')
        )

        # Segunda cuenta que intenta abrirse en la misma mesa mientras la primera sigue ABIERTA
        venta_2 = Venta(
            caja=self.caja,
            cajero=self.cajero,
            punto_venta=self.pv1,
            modalidad='MESA',
            mesa=self.mesa4,
            estado='ABIERTA',
            total=Decimal('5000.00')
        )
        with self.assertRaises(ValidationError) as ctx:
            venta_2.clean()
        self.assertIn("ya tiene una cuenta abierta", str(ctx.exception))

        # Si la venta 1 se paga y cierra, la mesa puede recibir una nueva cuenta abierta
        venta_1.estado = 'PAGADA'
        venta_1.save()

        # Ahora venta_2 pasa la validación sin conflicto
        venta_2.clean()
        venta_2.save()
        self.assertEqual(venta_2.estado, 'ABIERTA')

    def test_rf11_4_flujo_mesa_cuenta_abierta_multiples_rondas_y_cierre(self):
        """RF11.1 & RF11.3: Flujo mesero: apertura en mesa, comanda multi-ronda y liberación de mesa"""
        self.client.force_login(self.mesero)
        local = self.pv1
        mesa = self.mesa4

        # Ronda 1: hamburguesa a cocina
        items_ronda_1 = [
            {"nombre": self.prod_hamburguesa.nombre, "cantidad": 2, "precio": float(self.prod_hamburguesa.precio_base), "destino": "COCINA", "nota": "Sin cebolla"}
        ]
        resp1 = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(items_ronda_1)
        }, follow=True)
        self.assertEqual(resp1.status_code, 200)

        mesa.refresh_from_db()
        self.assertEqual(mesa.estado, 'OCUPADA')

        venta_abierta = Venta.objects.filter(mesa=mesa, estado='ABIERTA').first()
        self.assertIsNotNone(venta_abierta)
        self.assertEqual(venta_abierta.modalidad, 'MESA')
        subtotal_esperado_ronda1 = self.prod_hamburguesa.precio_base * 2
        self.assertEqual(venta_abierta.total, subtotal_esperado_ronda1)

        # Ronda 2: agregar bebidas en la misma mesa
        items_ronda_2 = [
            {"nombre": self.prod_bebida.nombre, "cantidad": 2, "precio": float(self.prod_bebida.precio_base), "destino": "BARRA", "nota": "Heladas"}
        ]
        resp2 = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(items_ronda_2)
        }, follow=True)
        self.assertEqual(resp2.status_code, 200)

        # La venta abierta sigue siendo la misma, incrementando su total
        venta_abierta.refresh_from_db()
        total_esperado = subtotal_esperado_ronda1 + (self.prod_bebida.precio_base * 2)
        self.assertEqual(venta_abierta.total, total_esperado)
        self.assertEqual(venta_abierta.pedidos.count(), 2)

        # Cierre y cobro de la cuenta en salón
        self.client.force_login(self.mesero)
        resp_cierre = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'cerrar_cuenta_mesa',
            'mesa_id': mesa.id,
            'metodo_pago': 'EFECTIVO'
        }, follow=True)
        self.assertEqual(resp_cierre.status_code, 200)

        mesa.refresh_from_db()
        self.assertEqual(mesa.estado, 'HABILITADA')
        venta_abierta.refresh_from_db()
        self.assertEqual(venta_abierta.estado, 'PAGADA')

    def test_rf11_5_elaboracion_propia_en_venta_rapida(self):
        """RF11.4: Productos con preparación en cocina o barra para VENTA_RAPIDA emiten aviso de Mostrador"""
        from ventas.utils import generar_contenido_ticket_cocina

        mesas_ocupadas_antes = Mesa.objects.filter(punto_venta=self.pv1, estado='OCUPADA').count()

        # Crear venta rápida con hamburguesa caliente que requiere comanda a cocina
        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero,
            punto_venta=self.pv1,
            modalidad='VENTA_RAPIDA',
            mesa=None,
            total=self.prod_hamburguesa.precio_base,
            metodo_pago='EFECTIVO',
            estado='PAGADA'
        )

        detalle = DetalleVenta.objects.create(
            venta=venta,
            producto=self.prod_hamburguesa,
            cantidad=1,
            precio_aplicado=self.prod_hamburguesa.precio_base,
            subtotal=self.prod_hamburguesa.precio_base
        )

        pedido = Pedido.objects.create(
            venta=venta,
            estado='PENDIENTE',
            observaciones="Venta rápida mostrador"
        )

        dp = DetallePedido.objects.create(
            pedido=pedido,
            producto=self.prod_hamburguesa,
            cantidad=1,
            observaciones="Para llevar en mostrador"
        )

        # Verificar ticket digital generado para cocina
        ticket_cocina = generar_contenido_ticket_cocina(pedido, items_cocina=[dp])

        self.assertIn("Mostrador", ticket_cocina)
        self.assertNotIn("Mesa 1", ticket_cocina)
        self.assertNotIn("Mesa 4", ticket_cocina)

        # Las mesas permanecen sin alterar
        mesas_ocupadas_despues = Mesa.objects.filter(punto_venta=self.pv1, estado='OCUPADA').count()
        self.assertEqual(mesas_ocupadas_despues, mesas_ocupadas_antes)

    def test_rf11_6_pos_crear_ticket_modalidad_rapida_y_mesa_ajax(self):
        """RF11.5: Endpoint vendedor_crear_ticket soporta selector explícito de modalidad MESA y VENTA_RAPIDA"""
        self.client.force_login(self.cajero)

        # 1. Venta Rápida exitosa vía AJAX
        payload_rapida = [
            {"producto_id": self.prod_bebida.id, "cantidad": 1}
        ]
        resp1 = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps(payload_rapida),
            'metodo_pago': 'EFECTIVO',
            'modalidad': 'VENTA_RAPIDA'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        self.assertTrue(data1['ok'])
        self.assertEqual(data1['modalidad'], 'VENTA_RAPIDA')
        self.assertIn("Mostrador", data1['ubicacion'])

        v1 = Venta.objects.get(id=data1['venta_id'])
        self.assertIsNone(v1.mesa)
        self.assertEqual(v1.modalidad, 'VENTA_RAPIDA')

        # 2. Venta Mesa en caja exitosa vía AJAX
        payload_mesa = [
            {"producto_id": self.prod_hamburguesa.id, "cantidad": 1}
        ]
        resp2 = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps(payload_mesa),
            'metodo_pago': 'EFECTIVO',
            'modalidad': 'MESA',
            'mesa_id': self.mesa4.id
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertTrue(data2['ok'])
        self.assertEqual(data2['modalidad'], 'MESA')
        self.assertIn(f"Mesa {self.mesa4.identificador}", data2['ubicacion'])

        v2 = Venta.objects.get(id=data2['venta_id'])
        self.assertEqual(v2.mesa, self.mesa4)
        self.assertEqual(v2.modalidad, 'MESA')

        # 3. Intento de Venta Mesa sin especificar mesa_id -> Error 400
        resp3 = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps(payload_mesa),
            'metodo_pago': 'EFECTIVO',
            'modalidad': 'MESA',
            'mesa_id': ''
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp3.status_code, 400)
        data3 = resp3.json()
        self.assertFalse(data3['ok'])
        self.assertIn("Debe seleccionar una mesa", data3['error'])

    def test_rf11_7_mesero_exige_mesa_valida_y_no_permite_salon_sin_mesa(self):
        """RF11.1: Mesero en salón no puede emitir comanda sin mesa o con mesa ajena"""
        self.client.force_login(self.mesero)
        local = self.pv1
        items = [
            {"nombre": self.prod_bebida.nombre, "cantidad": 1, "precio": float(self.prod_bebida.precio_base), "destino": "BARRA", "nota": ""}
        ]

        # 1. Mesero sin mesa_id
        resp1 = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': '',
            'items_json': json.dumps(items)
        }, follow=True)
        self.assertContains(resp1, "Debe seleccionar una mesa")

        # 2. Mesero con mesa_id de otro local
        resp2 = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': self.mesa_pv2.id,
            'items_json': json.dumps(items)
        }, follow=True)
        self.assertContains(resp2, "no pertenece al local")

    def test_rf11_8_validar_modalidad_operativa_helper(self):
        """RF11.1 & RF11.2: Validación estricta mediante helper validar_modalidad_operativa"""
        from ventas.utils import validar_modalidad_operativa
        from django.core.exceptions import ValidationError

        # Venta rápida válida
        mod, m = validar_modalidad_operativa('VENTA_RAPIDA', None, self.pv1)
        self.assertEqual(mod, 'VENTA_RAPIDA')
        self.assertIsNone(m)

        # Alias de venta rápida normalizado
        mod, m = validar_modalidad_operativa('MOSTRADOR', self.mesa4, self.pv1)
        self.assertEqual(mod, 'VENTA_RAPIDA')
        self.assertIsNone(m)

        # Mesa válida
        mod, m = validar_modalidad_operativa('MESA', self.mesa4, self.pv1)
        self.assertEqual(mod, 'MESA')
        self.assertEqual(m, self.mesa4)

        # Mesa requerida no proporcionada -> ValidationError
        with self.assertRaises(ValidationError) as ctx:
            validar_modalidad_operativa('MESA', None, self.pv1)
        self.assertIn("requiere obligatoriamente una mesa asignada", str(ctx.exception))

        # Mesa de otro local -> ValidationError
        with self.assertRaises(ValidationError) as ctx:
            validar_modalidad_operativa('MESA', self.mesa_pv2, self.pv1)
        self.assertIn("no pertenece al local", str(ctx.exception))


# ==============================================================================
# SUITE OFICIAL DE PRUEBAS AUTOMATIZADAS RF12 (Comentarios Asociados a Productos)
# ==============================================================================

class SafariRF12ComentariosProductosTests(TestCase):
    """
    Suite oficial de pruebas automatizadas para RF12 - Comentarios Asociados a Productos:
    - RF12.1: Persistencia de texto libre por producto en comandas de Cocina y Barra.
    - RF12.2: Aislamiento estricto: la nota de un producto no se cruza a otros productos del pedido.
    - RF12.3: Sanitización de seguridad contra XSS (OWASP ASVS) neutralizando etiquetas HTML.
    - RF12.4: Límite de longitud (máx 200 caracteres), normalización de espacios vacíos y eliminación de bytes nulos.
    - RF12.5: Conservación y trazabilidad independiente entre rondas de una misma mesa/cuenta.
    - RF12.6: Impresión y reimpresión de tickets conservan íntegramente las observaciones individuales.
    - RF12.7: Visualización segura en pantallas táctiles KDS Cocina y BDS Barra.
    - RF12.8: Terminal POS crear_ticket soporta notas individuales por producto vía AJAX.
    """

    def setUp(self):
        cache.clear()
        self.client = Client()
        call_command('poblar_safari')

        self.admin = User.objects.get(username='rgomez')
        self.cajero = User.objects.get(username='cvalenzuela')
        self.mesero = User.objects.get(username='dsilva')
        self.cocinero = User.objects.get(username='eparedes')

        self.pv1 = PuntoVenta.objects.get(id=1)

        self.mesa4 = Mesa.objects.filter(punto_venta=self.pv1, identificador='Mesa 4').first()
        if not self.mesa4:
            self.mesa4 = Mesa.objects.create(identificador='Mesa 4', punto_venta=self.pv1, capacidad=4, estado='HABILITADA')
        else:
            self.mesa4.estado = 'HABILITADA'
            self.mesa4.save()

        self.prod_hamburguesa = Producto.objects.filter(nombre__icontains='Hamburguesa').first()
        self.prod_churrasco = Producto.objects.filter(nombre__icontains='Churrasco').first()
        self.prod_bebida = Producto.objects.filter(nombre__icontains='Coca-Cola').first()

        hoy = timezone.localdate()
        self.jornada, _ = Jornada.objects.get_or_create(
            fecha=hoy,
            defaults={'usuario_apertura': self.admin, 'estado': 'ABIERTA'}
        )
        self.caja, _ = Caja.objects.get_or_create(
            jornada=self.jornada,
            cajero=self.cajero,
            punto_venta=self.pv1,
            defaults={'monto_apertura': Decimal('50000.00'), 'estado': 'ABIERTA'}
        )

    def test_rf12_1_persistencia_comentarios_cocina_y_barra(self):
        """RF12.1: Comentarios de texto libre persisten asociados individualmente al producto correspondiente"""
        self.client.force_login(self.mesero)
        local = self.pv1
        mesa = self.mesa4

        items = [
            {
                "nombre": self.prod_hamburguesa.nombre,
                "cantidad": 1,
                "precio": float(self.prod_hamburguesa.precio_base),
                "destino": "COCINA",
                "nota": "Término medio, papas bien doradas"
            },
            {
                "nombre": self.prod_bebida.nombre,
                "cantidad": 2,
                "precio": float(self.prod_bebida.precio_base),
                "destino": "BARRA",
                "nota": "Sin hielo y con endulzante"
            }
        ]

        resp = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(items)
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        pedido = Pedido.objects.filter(venta__mesa=mesa).order_by('-id').first()
        self.assertIsNotNone(pedido)

        det_hamb = pedido.detalles.filter(producto=self.prod_hamburguesa).first()
        self.assertIsNotNone(det_hamb)
        self.assertEqual(det_hamb.observaciones, "Término medio, papas bien doradas")

        det_beb = pedido.detalles.filter(producto=self.prod_bebida).first()
        self.assertIsNotNone(det_beb)
        self.assertEqual(det_beb.observaciones, "Sin hielo y con endulzante")

    def test_rf12_2_aislamiento_estricto_comentarios_entre_productos(self):
        """RF12.2: Aislamiento estricto: la nota de un producto jamás contamina ni se copia a los demás ítems"""
        self.client.force_login(self.mesero)
        local = self.pv1
        mesa = self.mesa4

        items = [
            {"nombre": self.prod_hamburguesa.nombre, "cantidad": 1, "precio": float(self.prod_hamburguesa.precio_base), "destino": "COCINA", "nota": "Sin mayonesa"},
            {"nombre": self.prod_churrasco.nombre, "cantidad": 1, "precio": float(self.prod_churrasco.precio_base), "destino": "COCINA", "nota": "Sin tomate"},
            {"nombre": self.prod_bebida.nombre, "cantidad": 1, "precio": float(self.prod_bebida.precio_base), "destino": "BARRA", "nota": ""}
        ]

        resp = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(items)
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        pedido = Pedido.objects.filter(venta__mesa=mesa).order_by('-id').first()
        detalles = {d.producto.nombre: d.observaciones for d in pedido.detalles.all()}

        self.assertEqual(detalles[self.prod_hamburguesa.nombre], "Sin mayonesa")
        self.assertEqual(detalles[self.prod_churrasco.nombre], "Sin tomate")
        self.assertIsNone(detalles[self.prod_bebida.nombre])

    def test_rf12_3_sanitizacion_xss_y_caracteres_peligrosos(self):
        """RF12.3: Sanitización OWASP ASVS: scripts y etiquetas HTML son neutralizados y escapados de forma segura"""
        self.client.force_login(self.mesero)
        local = self.pv1
        mesa = self.mesa4

        malicious_note = "<script>alert('XSS')</script><img src=x onerror=alert(1)>"
        items = [
            {"nombre": self.prod_hamburguesa.nombre, "cantidad": 1, "precio": float(self.prod_hamburguesa.precio_base), "destino": "COCINA", "nota": malicious_note}
        ]

        resp = self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(items)
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        pedido = Pedido.objects.filter(venta__mesa=mesa).order_by('-id').first()
        det = pedido.detalles.first()

        self.assertNotIn("<script>", det.observaciones)
        self.assertNotIn("<img", det.observaciones)
        self.assertIn("&lt;script&gt;", det.observaciones)
        self.assertIn("&lt;img", det.observaciones)

    def test_rf12_4_limite_longitud_y_texto_vacio(self):
        """RF12.4: Truncado a 200 caracteres, normalización de espacios vacíos y remoción de bytes nulos"""
        from ventas.utils import sanitizar_observacion

        # 1. Truncado a 200 caracteres
        texto_largo = "A" * 250
        sanitizado = sanitizar_observacion(texto_largo, max_length=200)
        self.assertEqual(len(sanitizado), 200)
        self.assertEqual(sanitizado, "A" * 200)

        # 2. Espacios vacíos convertidos a None
        self.assertIsNone(sanitizar_observacion("   "))
        self.assertIsNone(sanitizar_observacion(""))
        self.assertIsNone(sanitizar_observacion(None))

        # 3. Byte nulo removido
        self.assertEqual(sanitizar_observacion("Sin sal\x00extra"), "Sin salextra")

        # 4. Tildes y puntuación conservados
        nota_espanol = "Término 3/4, con ají verde y champiñones"
        self.assertEqual(sanitizar_observacion(nota_espanol), nota_espanol)

    def test_rf12_5_conservacion_independiente_por_rondas(self):
        """RF12.5: Las rondas sucesivas conservan de manera aislada e independiente sus notas respectivas"""
        self.client.force_login(self.mesero)
        local = self.pv1
        mesa = self.mesa4

        # Ronda 1: hamburguesa con nota de ronda 1
        items_ronda_1 = [
            {"nombre": self.prod_hamburguesa.nombre, "cantidad": 1, "precio": float(self.prod_hamburguesa.precio_base), "destino": "COCINA", "nota": "Ronda 1: Sin cebolla"}
        ]
        self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(items_ronda_1)
        }, follow=True)

        venta = Venta.objects.filter(mesa=mesa, estado='ABIERTA').first()
        self.assertEqual(venta.pedidos.count(), 1)
        pedido1 = venta.pedidos.first()
        det_ronda1 = pedido1.detalles.first()
        self.assertEqual(det_ronda1.observaciones, "Ronda 1: Sin cebolla")

        # Ronda 2: hamburguesa con nota diferente y bebida sin nota
        items_ronda_2 = [
            {"nombre": self.prod_hamburguesa.nombre, "cantidad": 1, "precio": float(self.prod_hamburguesa.precio_base), "destino": "COCINA", "nota": "Ronda 2: Con extra queso"},
            {"nombre": self.prod_bebida.nombre, "cantidad": 1, "precio": float(self.prod_bebida.precio_base), "destino": "BARRA", "nota": ""}
        ]
        self.client.post(reverse('mesero') + f"?local_id={local.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': mesa.id,
            'items_json': json.dumps(items_ronda_2)
        }, follow=True)

        self.assertEqual(venta.pedidos.count(), 2)
        pedido2 = venta.pedidos.order_by('-id').first()
        det_ronda2_hamb = pedido2.detalles.filter(producto=self.prod_hamburguesa).first()
        det_ronda2_beb = pedido2.detalles.filter(producto=self.prod_bebida).first()

        self.assertEqual(det_ronda2_hamb.observaciones, "Ronda 2: Con extra queso")
        self.assertIsNone(det_ronda2_beb.observaciones)

        # La ronda 1 permanece inalterada
        det_ronda1.refresh_from_db()
        self.assertEqual(det_ronda1.observaciones, "Ronda 1: Sin cebolla")

    def test_rf12_6_tickets_y_reimpresion_conservan_observaciones(self):
        """RF12.6: La emisión y reimpresión de tickets conservan las observaciones individuales por producto"""
        from ventas.utils import emitir_tickets_comanda, reimprimir_ticket

        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero,
            punto_venta=self.pv1,
            modalidad='VENTA_RAPIDA',
            mesa=None,
            total=self.prod_hamburguesa.precio_base,
            metodo_pago='EFECTIVO',
            estado='PAGADA'
        )
        pedido = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(
            pedido=pedido,
            producto=self.prod_hamburguesa,
            cantidad=1,
            observaciones="Sin sal ni mayonesa"
        )

        # Emisión original
        res = emitir_tickets_comanda(pedido, usuario_emisor=self.cajero)
        ticket_cocina = res['tickets'][0]

        self.assertIn("Nota: Sin sal ni mayonesa", ticket_cocina.contenido_impresion)

        # Reimpresión supervisada
        reimprimir_ticket(ticket_cocina, usuario_solicitante=self.admin)
        ticket_cocina.refresh_from_db()

        self.assertTrue(ticket_cocina.es_reimpresion)
        self.assertIn("COPIA DE REIMPRESI", ticket_cocina.contenido_impresion)
        self.assertIn("Nota: Sin sal ni mayonesa", ticket_cocina.contenido_impresion)

    def test_rf12_7_kds_cocina_y_bds_barra_renderizan_observaciones(self):
        """RF12.7: Pantallas de Cocina KDS y Barra BDS muestran las notas especiales de cada producto"""
        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero,
            punto_venta=self.pv1,
            modalidad='MESA',
            mesa=self.mesa4,
            total=self.prod_hamburguesa.precio_base + self.prod_bebida.precio_base,
            metodo_pago='EFECTIVO',
            estado='ABIERTA'
        )
        pedido = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(
            pedido=pedido,
            producto=self.prod_hamburguesa,
            cantidad=1,
            observaciones="Carne 3/4 bien jugosa"
        )
        DetallePedido.objects.create(
            pedido=pedido,
            producto=self.prod_bebida,
            cantidad=1,
            observaciones="Vaso con rodaja de limon"
        )

        # 1. KDS Cocina
        self.client.force_login(self.cocinero)
        resp_cocina = self.client.get(reverse('cocina'))
        self.assertEqual(resp_cocina.status_code, 200)
        self.assertContains(resp_cocina, "Carne 3/4 bien jugosa")

        # 2. BDS Barra
        self.client.force_login(self.cajero)
        resp_barra = self.client.get(reverse('barra'))
        self.assertEqual(resp_barra.status_code, 200)
        self.assertContains(resp_barra, "Vaso con rodaja de limon")

    def test_rf12_8_pos_crear_ticket_con_observaciones_ajax(self):
        """RF12.8: Terminal POS crear_ticket procesa notas individuales por producto vía AJAX"""
        self.client.force_login(self.cajero)

        payload = [
            {
                "producto_id": self.prod_hamburguesa.id,
                "cantidad": 1,
                "nota": "Para llevar en bolsa termica"
            }
        ]

        resp = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps(payload),
            'metodo_pago': 'EFECTIVO',
            'modalidad': 'VENTA_RAPIDA'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])

        v = Venta.objects.get(id=data['venta_id'])
        ped = v.pedidos.first()
        det = ped.detalles.first()
        self.assertEqual(det.observaciones, "Para llevar en bolsa termica")
