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

    def test_anular_venta_caja_cerrada_bloqueado(self):
        """Control Anti-Fraude: No se puede anular una venta de una caja ya cerrada y arqueada"""
        self.caja.estado = 'CERRADA'
        self.caja.save()
        self.client.login(username="supervisor_safari", password="password123")
        resp = self.client.post(reverse("anular_venta", args=[self.venta.id]), {
            "motivo_anulacion": "Intento de anulación de caja cerrada"
        }, follow=True)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, "PAGADA")
        self.assertContains(resp, "caja")

    def test_cajero_no_puede_cancelar_pedido_directo(self):
        """Control Anti-Fraude: Un cajero no puede cancelar un pedido en curso directamente"""
        pedido = Pedido.objects.create(venta=self.venta, estado="EN_PREPARACION")
        self.client.login(username="cajero_seguro", password="password123")
        resp = self.client.post(reverse("cambiar_estado_pedido"), {
            "pedido_id": str(pedido.id),
            "nuevo_estado": "CANCELADO"
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 403)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "EN_PREPARACION")

    def test_desactivar_trabajador_con_caja_abierta_bloqueado(self):
        """Control Anti-Fraude: No se puede dar de baja a un colaborador con caja abierta"""
        self.client.login(username="supervisor_safari", password="password123")
        perfil_cajero = self.cajero.perfil
        resp = self.client.post(reverse("administrador_trabajadores"), {
            "accion": "desactivar",
            "perfil_id": str(perfil_cajero.id)
        }, follow=True)
        perfil_cajero.refresh_from_db()
        self.assertTrue(perfil_cajero.activo)
        self.assertContains(resp, "caja individual actualmente abierta")

    def test_anulacion_consumo_interno_requiere_motivo_y_audita(self):
        """Control Anti-Fraude: Anulación de consumo interno exige justificación y genera auditoría"""
        consumo = ConsumoInterno.objects.create(
            empleado=self.cajero,
            punto_venta=self.pv,
            registrado_por=self.admin,
            total=Decimal("5000.00"),
            estado="REGISTRADO"
        )
        self.client.login(username="supervisor_safari", password="password123")
        # 1. Sin motivo o motivo corto -> Rechazado
        resp_err = self.client.post(reverse("administrador_consumos"), {
            "accion": "anular_individual",
            "consumo_id": str(consumo.id),
            "motivo_anulacion": "no"
        }, follow=True)
        consumo.refresh_from_db()
        self.assertEqual(consumo.estado, "REGISTRADO")

        # 2. Con motivo válido -> Aprobado y auditado
        resp_ok = self.client.post(reverse("administrador_consumos"), {
            "accion": "anular_individual",
            "consumo_id": str(consumo.id),
            "motivo_anulacion": "Colaborador pagó en efectivo en oficina central"
        }, follow=True)
        consumo.refresh_from_db()
        self.assertEqual(consumo.estado, "ANULADO")
        alerta = AlertaTraslado.objects.filter(autorizado_por=self.admin, motivo__contains=f"[ANULACIÓN CONSUMO INTERNO #{consumo.id}]").first()
        self.assertIsNotNone(alerta)

    def test_anulacion_venta_con_alimentos_entregados_genera_alerta_especial(self):
        """Control Anti-Fraude: Anular venta con comida ya entregada registra alerta de merma/fraude"""
        Pedido.objects.create(venta=self.venta, estado="ENTREGADO")
        self.client.login(username="supervisor_safari", password="password123")
        resp = self.client.post(reverse("anular_venta", args=[self.venta.id]), {
            "motivo_anulacion": "Comensal reclamó comida fría tras haberla recibido"
        }, follow=True)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado, "ANULADA")
        alerta = AlertaTraslado.objects.filter(empleado=self.admin, motivo__contains="ALERTA DE MERMA/FRAUDE").first()
        self.assertIsNotNone(alerta)

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
        static_dir = os.path.join(settings.BASE_DIR, "static", "js", "global")
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
        self.producto.puntos_venta.add(self.pv)

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
        self.prod_cocina.puntos_venta.add(self.pv)
        self.prod_barra.puntos_venta.add(self.pv)

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
        self.prod_cocina.puntos_venta.add(self.pv1)
        self.prod_barra.puntos_venta.add(self.pv1)

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
        # 3. Auto-actualización fluida en 1s presente en su módulo estático por zona (static/js/kds/barra.js)
        self.assertContains(resp, "js/kds/barra.js")
        barra_js_path = os.path.join(settings.BASE_DIR, "static", "js", "kds", "barra.js")
        with open(barra_js_path, "r", encoding="utf-8") as f:
            self.assertIn("autoActualizarBarra", f.read())

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


# ==============================================================================
# SUITE OFICIAL DE PRUEBAS AUTOMATIZADAS RF13 (Registro de Entrega de Productos)
# ==============================================================================
class SafariRF13RegistroEntregaProductosTests(TestCase):
    """
    Pruebas unitarias e integración de alta fidelidad para RF13:
    - RF13.1: Ciclo de vida y máquina de estados (PENDIENTE -> EN_PREPARACION -> LISTO -> ENTREGADO).
    - RF13.2: Registro de auditoría trazable con fecha/hora, usuario responsable, ticket, local y ubicación.
    - RF13.3: Granularidad operativa por comanda (Pedido) e integración con tickets de producción.
    - RF13.4: Prevención estricta de doble entrega y blindaje de concurrencia.
    - Rechazo de entregas prematuras (antes de LISTO) y de pedidos CANCELADOS.
    - Aislamiento de tiempos y entregas multi-ronda.
    - Integración visual y operativa con panel de Mesero y Auditoría Administrador.
    """

    def setUp(self):
        from django.contrib.auth.models import User
        from django.utils import timezone
        from ventas.models import PuntoVenta, PerfilEmpleado, Mesa, Producto, Categoria, Venta, Pedido, DetallePedido, Ticket, Entrega, Jornada, Caja

        self.pv_central = PuntoVenta.objects.create(nombre="Restaurante Central Safari", activo=True)
        self.pv_barra = PuntoVenta.objects.create(nombre="Barra Rápida Safari", activo=True)

        self.admin_user = User.objects.create_superuser('admin_rf13', 'admin@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.admin_user, rol='ADMINISTRADOR', punto_venta_actual=self.pv_central)

        self.cocinero_user = User.objects.create_user('cocinero_rf13', 'cocinero@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.cocinero_user, rol='COCINERO', punto_venta_actual=self.pv_central)

        self.mesero_user = User.objects.create_user('mesero_rf13', 'mesero@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.mesero_user, rol='MESERO', punto_venta_actual=self.pv_central)

        self.cajero_user = User.objects.create_user('cajero_rf13', 'cajero@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.cajero_user, rol='CAJERO', punto_venta_actual=self.pv_central)

        self.cajero_barra_user = User.objects.create_user('cajero_barra_rf13', 'cajerobarra@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.cajero_barra_user, rol='CAJERO', punto_venta_actual=self.pv_barra)

        self.mesa_m1 = Mesa.objects.create(identificador="M1", capacidad=4, punto_venta=self.pv_central, estado='HABILITADA')

        self.cat_cocina = Categoria.objects.create(nombre="Cocina Caliente")
        self.prod_hamburguesa = Producto.objects.create(
            nombre="Hamburguesa Safari Premium",
            categoria=self.cat_cocina,
            precio_base=Decimal('8500'),
            activo=True
        )

        self.cat_barra = Categoria.objects.create(nombre="Cafetería y Jugos")
        self.prod_jugo = Producto.objects.create(
            nombre="Jugo Natural Frambuesa",
            categoria=self.cat_barra,
            precio_base=Decimal('3500'),
            activo=True
        )

        hoy = timezone.localdate()
        self.jornada, _ = Jornada.objects.get_or_create(
            fecha=hoy,
            defaults={'usuario_apertura': self.admin_user, 'estado': 'ABIERTA'}
        )
        self.caja, _ = Caja.objects.get_or_create(
            jornada=self.jornada,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
            defaults={'monto_apertura': Decimal('50000.00'), 'estado': 'ABIERTA'}
        )
        self.caja_barra, _ = Caja.objects.get_or_create(
            jornada=self.jornada,
            cajero=self.cajero_barra_user,
            punto_venta=self.pv_barra,
            defaults={'monto_apertura': Decimal('50000.00'), 'estado': 'ABIERTA'}
        )

    def test_rf13_1_flujo_valido_completo_hasta_entrega(self):
        """RF13.1: Ciclo completo válido PENDIENTE -> EN_PREPARACION -> LISTO -> ENTREGADO con trazabilidad"""
        from ventas.models import Venta, Pedido, DetallePedido, Ticket, Entrega

        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
            modalidad='MESA',
            mesa=self.mesa_m1,
            total=Decimal('12000'),
            estado='ABIERTA'
        )
        pedido = Pedido.objects.create(venta=venta, estado='PENDIENTE', observaciones="Sin sal")
        dp = DetallePedido.objects.create(pedido=pedido, producto=self.prod_hamburguesa, cantidad=1)
        ticket = Ticket.objects.create(pedido=pedido, venta=venta, codigo="COM-COC-1301", tipo_destino='COCINA', estado='EMITIDO')

        # 1. Pasar a EN_PREPARACION
        self.client.force_login(self.cocinero_user)
        resp1 = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': pedido.id,
            'nuevo_estado': 'EN_PREPARACION'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp1.status_code, 200)
        pedido.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(pedido.estado, 'EN_PREPARACION')
        self.assertIsNotNone(pedido.fecha_inicio_preparacion)
        self.assertEqual(ticket.estado, 'EN_PROCESO')

        # 2. Pasar a LISTO
        resp2 = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': pedido.id,
            'nuevo_estado': 'LISTO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp2.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'LISTO')
        self.assertIsNotNone(pedido.fecha_listo)

        # 3. Mesero entrega el pedido al comensal (ENTREGADO)
        self.client.force_login(self.mesero_user)
        resp3 = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': pedido.id,
            'nuevo_estado': 'ENTREGADO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp3.status_code, 200)
        pedido.refresh_from_db()
        ticket.refresh_from_db()
        self.assertEqual(pedido.estado, 'ENTREGADO')
        self.assertEqual(ticket.estado, 'FINALIZADO')

        # Verificar auditoría en Entrega
        entrega = Entrega.objects.filter(pedido=pedido).first()
        self.assertIsNotNone(entrega)
        self.assertEqual(entrega.usuario_entrega, self.mesero_user)
        self.assertEqual(entrega.ticket, ticket)
        self.assertIsNotNone(entrega.fecha_hora_entrega)

    def test_rf13_2_rechazo_entrega_antes_de_estar_listo(self):
        """RF13.1 / Problema 1: Se rechaza marcar como ENTREGADO un pedido que está PENDIENTE o EN_PREPARACION"""
        from ventas.models import Venta, Pedido, DetallePedido, Entrega

        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
            modalidad='VENTA_RAPIDA',
            total=Decimal('8500'),
            estado='PAGADA'
        )
        pedido = Pedido.objects.create(venta=venta, estado='PENDIENTE')

        self.client.force_login(self.mesero_user)

        # Intento de entregar pedido en PENDIENTE
        resp_pend = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': pedido.id,
            'nuevo_estado': 'ENTREGADO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp_pend.status_code, 400)
        self.assertIn("error", resp_pend.json()['status'])
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'PENDIENTE')
        self.assertEqual(Entrega.objects.filter(pedido=pedido).count(), 0)

        # Intento de entregar pedido en EN_PREPARACION
        pedido.estado = 'EN_PREPARACION'
        pedido.save()

        resp_prep = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': pedido.id,
            'nuevo_estado': 'ENTREGADO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp_prep.status_code, 400)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'EN_PREPARACION')
        self.assertEqual(Entrega.objects.filter(pedido=pedido).count(), 0)

    def test_rf13_3_prevencion_doble_entrega_y_concurrencia(self):
        """RF13.4 / Problema 2: Prevención estricta de doble entrega; segundo intento rechazado con cero duplicados"""
        from ventas.models import Venta, Pedido, Entrega
        from django.core.exceptions import ValidationError

        venta = Venta.objects.create(caja=self.caja, cajero=self.cajero_user, punto_venta=self.pv_central, modalidad='VENTA_RAPIDA', total=Decimal('3500'), estado='PAGADA')
        pedido = Pedido.objects.create(venta=venta, estado='LISTO')

        self.client.force_login(self.mesero_user)

        # Primera entrega: exitosa
        resp1 = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': pedido.id,
            'nuevo_estado': 'ENTREGADO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(Entrega.objects.filter(pedido=pedido).count(), 1)

        # Segunda entrega concurrente/duplicada: debe fallar con 400
        resp2 = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': pedido.id,
            'nuevo_estado': 'ENTREGADO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("error", resp2.json()['status'])
        # Garantía de cero duplicados en base de datos
        self.assertEqual(Entrega.objects.filter(pedido=pedido).count(), 1)

        # Validación directa a nivel de modelo
        with self.assertRaises(ValidationError):
            Entrega.objects.create(pedido=pedido, usuario_entrega=self.cajero_user)

    def test_rf13_4_rechazo_entrega_pedido_cancelado(self):
        """RF13.1 / Problema 6: Un pedido CANCELADO no puede ser entregado ni cambiar de estado"""
        from ventas.models import Venta, Pedido, Entrega
        from django.core.exceptions import ValidationError

        venta = Venta.objects.create(caja=self.caja, cajero=self.cajero_user, punto_venta=self.pv_central, modalidad='VENTA_RAPIDA', total=Decimal('5000'), estado='PAGADA')
        pedido = Pedido.objects.create(venta=venta, estado='CANCELADO')

        self.client.force_login(self.mesero_user)
        resp = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': pedido.id,
            'nuevo_estado': 'ENTREGADO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 400)
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'CANCELADO')
        self.assertEqual(Entrega.objects.filter(pedido=pedido).count(), 0)

        # Nivel modelo
        with self.assertRaises(ValidationError):
            Entrega.objects.create(pedido=pedido, usuario_entrega=self.mesero_user)

    def test_rf13_5_trazabilidad_ubicacion_local_y_tiempos(self):
        """RF13.2 / RF16: Registro de entrega calcula ubicación, punto de venta y tiempos transcurridos válidos"""
        from ventas.models import Venta, Pedido, Entrega
        from ventas.utils import registrar_entrega_pedido
        from django.utils import timezone
        import datetime

        # Venta en Mesa
        venta_mesa = Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
            modalidad='MESA',
            mesa=self.mesa_m1,
            total=Decimal('8500'),
            estado='ABIERTA'
        )
        pedido_mesa = Pedido.objects.create(venta=venta_mesa, estado='LISTO')
        pedido_mesa.fecha_inicio_preparacion = timezone.now() - datetime.timedelta(minutes=10)
        pedido_mesa.fecha_listo = timezone.now() - datetime.timedelta(minutes=2)
        pedido_mesa.save()

        entrega_m = registrar_entrega_pedido(pedido_mesa, usuario_entrega=self.mesero_user)
        self.assertEqual(entrega_m.get_ubicacion(), "Mesa M1 (Salón)")
        self.assertEqual(entrega_m.get_punto_venta(), self.pv_central)
        self.assertGreaterEqual(entrega_m.get_tiempo_desde_creacion_minutos(), 0.0)
        self.assertGreaterEqual(pedido_mesa.get_tiempo_preparacion_minutos(), 0.0)

        # Venta Rápida
        venta_vr = Venta.objects.create(
            caja=self.caja_barra,
            cajero=self.cajero_barra_user,
            punto_venta=self.pv_barra,
            modalidad='VENTA_RAPIDA',
            total=Decimal('3500'),
            estado='PAGADA'
        )
        pedido_vr = Pedido.objects.create(venta=venta_vr, estado='LISTO')
        entrega_vr = registrar_entrega_pedido(pedido_vr, usuario_entrega=self.cajero_user)
        self.assertEqual(entrega_vr.get_ubicacion(), "Retiro Rápido / Mostrador")
        self.assertEqual(entrega_vr.get_punto_venta(), self.pv_barra)

    def test_rf13_6_mesero_servir_pedido_listo_en_salon(self):
        """RF13.2 / Integración Salón: Mesero visualiza comanda lista y pulsa 'Servir'; mesa se mantiene OCUPADA"""
        from ventas.models import Venta, Pedido, Entrega

        self.mesa_m1.estado = 'OCUPADA'
        self.mesa_m1.save()

        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
            modalidad='MESA',
            mesa=self.mesa_m1,
            total=Decimal('12000'),
            estado='ABIERTA'
        )
        pedido = Pedido.objects.create(venta=venta, estado='LISTO', observaciones="Mesa 1 comensales VIP")

        self.client.force_login(self.mesero_user)

        # Mesero ve el pedido listo en su interfaz
        resp_get = self.client.get(reverse('mesero'))
        self.assertEqual(resp_get.status_code, 200)
        self.assertIn(pedido, resp_get.context['pedidos_listos'])

        # Mesero pulsa botón "Servir"
        resp_post = self.client.post(reverse('cambiar_estado_pedido'), {
            'pedido_id': pedido.id,
            'nuevo_estado': 'ENTREGADO'
        }, HTTP_REFERER='/mesero/')
        self.assertEqual(resp_post.status_code, 302)

        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, 'ENTREGADO')

        # La mesa debe seguir OCUPADA mientras los comensales comen y la cuenta siga ABIERTA
        self.mesa_m1.refresh_from_db()
        self.assertEqual(self.mesa_m1.estado, 'OCUPADA')

        # Entrega registrada por el mesero
        entrega = Entrega.objects.filter(pedido=pedido).first()
        self.assertEqual(entrega.usuario_entrega, self.mesero_user)

    def test_rf13_7_segunda_ronda_tiempos_y_entregas_independientes(self):
        """RF13.3 / Problema 5: Segunda ronda de la misma mesa tiene Pedido y Entrega estrictamente independientes"""
        from ventas.models import Venta, Pedido, Entrega
        from ventas.utils import registrar_entrega_pedido

        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
            modalidad='MESA',
            mesa=self.mesa_m1,
            total=Decimal('20000'),
            estado='ABIERTA'
        )

        # Ronda 1
        p1 = Pedido.objects.create(venta=venta, estado='LISTO', observaciones="Ronda 1")
        e1 = registrar_entrega_pedido(p1, usuario_entrega=self.mesero_user, observaciones="Entregada Ronda 1")
        p1.refresh_from_db()
        self.assertEqual(p1.estado, 'ENTREGADO')

        # Ronda 2
        p2 = Pedido.objects.create(venta=venta, estado='LISTO', observaciones="Ronda 2")
        e2 = registrar_entrega_pedido(p2, usuario_entrega=self.mesero_user, observaciones="Entregada Ronda 2")
        p2.refresh_from_db()
        self.assertEqual(p2.estado, 'ENTREGADO')

        # Comprobación de aislamiento
        self.assertNotEqual(p1.id, p2.id)
        self.assertNotEqual(e1.id, e2.id)
        self.assertEqual(e1.pedido, p1)
        self.assertEqual(e2.pedido, p2)
        self.assertEqual(venta.pedidos.count(), 2)
        self.assertEqual(Entrega.objects.filter(pedido__venta=venta).count(), 2)

    def test_rf13_8_historial_auditoria_muestra_entrega(self):
        """RF13.2 / Auditoría: El panel de historial administrativo refleja el evento de Entrega con ubicación y tiempo"""
        from ventas.models import Venta, Pedido, Entrega
        from ventas.utils import registrar_entrega_pedido

        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
            modalidad='MESA',
            mesa=self.mesa_m1,
            total=Decimal('15000'),
            estado='ABIERTA'
        )
        pedido = Pedido.objects.create(venta=venta, estado='LISTO')
        entrega = registrar_entrega_pedido(pedido, usuario_entrega=self.mesero_user, observaciones="Despacho comensal mesa 1")

        self.client.force_login(self.admin_user)
        resp = self.client.get(reverse('administrador_historial'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f"ENT-{entrega.id}")
        self.assertContains(resp, f"Entrega Pedido #{pedido.id}")


# ==============================================================================
# SUITE OFICIAL DE PRUEBAS AUTOMATIZADAS RF14 (Gestión de Puntos de Venta)
# ==============================================================================
class SafariRF14GestionPuntosVentaTests(TestCase):
    """
    Pruebas unitarias e integración de alta fidelidad para RF14 (Gestión de Puntos de Venta):
    - CRUD completo de puntos de venta (crear, modificar, activar/desactivar, eliminar).
    - Prevención de nombres duplicados (case-insensitive) y rechazo de nombres vacíos.
    - Blindaje contra desactivación o eliminación de locales con cajas abiertas o cuentas en salón.
    - Soft-delete obligatorio cuando existen transacciones históricas para proteger la auditoría.
    - Eliminación física limpia cuando no existe historial operativo.
    - Desasignación automática y segura de trabajadores al dar de baja el local.
    - Asociación coherente de mesas, menús y productos disponibles por local.
    - Control de acceso estricto: denegación de privilegios a roles no administradores (403/redirect).
    - Manejo seguro de identificadores de local inexistentes (404 controlado).
    """

    def setUp(self):
        from django.contrib.auth.models import User
        from django.utils import timezone
        from ventas.models import PuntoVenta, PerfilEmpleado, Mesa, Producto, Categoria, Venta, Caja, Jornada, Menu

        self.admin_user = User.objects.create_superuser('admin_rf14', 'admin14@safari.cl', 'safari123')
        self.pv_central = PuntoVenta.objects.create(nombre="Restaurante Central Safari", tipo="Restaurante", activo=True)
        PerfilEmpleado.objects.create(usuario=self.admin_user, rol='ADMINISTRADOR', punto_venta_actual=self.pv_central)

        self.cajero_user = User.objects.create_user('cajero_rf14', 'cajero14@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.cajero_user, rol='CAJERO', punto_venta_actual=self.pv_central)

        self.mesero_user = User.objects.create_user('mesero_rf14', 'mesero14@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.mesero_user, rol='MESERO', punto_venta_actual=self.pv_central)

        self.cocinero_user = User.objects.create_user('cocinero_rf14', 'cocinero14@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.cocinero_user, rol='COCINERO', punto_venta_actual=self.pv_central)

        hoy = timezone.localdate()
        self.jornada, _ = Jornada.objects.get_or_create(
            fecha=hoy,
            defaults={'usuario_apertura': self.admin_user, 'estado': 'ABIERTA'}
        )
        self.caja, _ = Caja.objects.get_or_create(
            jornada=self.jornada,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
            defaults={'monto_apertura': Decimal('50000.00'), 'estado': 'ABIERTA'}
        )

    def test_rf14_1_crear_punto_venta_exitoso(self):
        """RF14: Administrador crea un nuevo punto de venta con todos sus atributos operativos"""
        from ventas.models import PuntoVenta

        self.client.force_login(self.admin_user)
        resp = self.client.post(reverse('administrador'), {
            'accion': 'crear_local',
            'nombre': 'Punto Waffles & Churros Oasis',
            'tipo': 'Pastelería & Snacks',
            'descripcion': 'Waffles recién horneados y bebidas calientes.',
            'icono': 'bi-cup-hot-fill',
            'color': '#d97706'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'ok')

        pv = PuntoVenta.objects.get(nombre='Punto Waffles & Churros Oasis')
        self.assertEqual(pv.tipo, 'Pastelería & Snacks')
        self.assertEqual(pv.icono, 'bi-cup-hot-fill')
        self.assertEqual(pv.color, '#d97706')
        self.assertTrue(pv.activo)

    def test_rf14_2_prevencion_duplicados_case_insensitive(self):
        """RF14 / Problema: Rechazo estricto de nombres duplicados (insensible a mayúsculas/minúsculas)"""
        from ventas.models import PuntoVenta

        self.client.force_login(self.admin_user)
        # Nombre exacto en mayúsculas
        resp = self.client.post(reverse('administrador'), {
            'accion': 'crear_local',
            'nombre': 'RESTAURANTE CENTRAL SAFARI',
            'tipo': 'Restaurante'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json()['status'])
        self.assertIn("Ya existe un local", resp.json()['mensaje'])

    def test_rf14_3_rechazo_nombre_vacio(self):
        """RF14 / Validación: Rechazo de nombres vacíos o solo compuestos de espacios"""
        self.client.force_login(self.admin_user)
        resp = self.client.post(reverse('administrador'), {
            'accion': 'crear_local',
            'nombre': '   ',
            'tipo': 'Cafetería'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json()['status'])

    def test_rf14_4_modificar_punto_venta_exitoso(self):
        """RF14: Administrador modifica atributos de un punto de venta existente"""
        from ventas.models import PuntoVenta

        local = PuntoVenta.objects.create(nombre="Kiosco África", tipo="Kiosco", activo=True)
        self.client.force_login(self.admin_user)

        resp = self.client.post(reverse('administrador'), {
            'accion': 'modificar_local',
            'local_id': local.id,
            'nombre': 'Kiosco Sabana Africana',
            'tipo': 'Punto Snacks & Bebidas',
            'descripcion': 'Bebidas heladas y snacks.',
            'icono': 'bi-snow',
            'color': '#0284c7',
            'activo': 'true'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 200)
        local.refresh_from_db()
        self.assertEqual(local.nombre, 'Kiosco Sabana Africana')
        self.assertEqual(local.tipo, 'Punto Snacks & Bebidas')
        self.assertEqual(local.color, '#0284c7')

    def test_rf14_5_rechazo_desactivar_o_eliminar_con_caja_abierta(self):
        """RF14 / Problema: No se puede desactivar ni eliminar un local que tiene una caja operativa ABIERTA"""
        from ventas.models import PuntoVenta, Caja

        self.client.force_login(self.admin_user)

        # 1. Intento de desactivar vía modificar_local
        resp_desact = self.client.post(reverse('administrador'), {
            'accion': 'modificar_local',
            'local_id': self.pv_central.id,
            'nombre': self.pv_central.nombre,
            'activo': 'false'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp_desact.status_code, 400)
        self.assertIn("cajas abiertas", resp_desact.json()['mensaje'])
        self.pv_central.refresh_from_db()
        self.assertTrue(self.pv_central.activo)

        # 2. Intento de eliminar vía eliminar_local
        resp_elim = self.client.post(reverse('administrador'), {
            'accion': 'eliminar_local',
            'local_id': self.pv_central.id
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp_elim.status_code, 400)
        self.assertIn("cajas abiertas", resp_elim.json()['mensaje'])
        self.assertTrue(PuntoVenta.objects.filter(id=self.pv_central.id).exists())

    def test_rf14_6_rechazo_desactivar_o_eliminar_con_venta_abierta(self):
        """RF14 / Problema: No se puede desactivar ni eliminar un local con comanda abierta en salón"""
        from ventas.models import PuntoVenta, Mesa, Venta

        pv_nuevo = PuntoVenta.objects.create(nombre="Terraza Safari Club", tipo="Bar", activo=True)
        mesa = Mesa.objects.create(identificador="T1", capacidad=4, punto_venta=pv_nuevo, estado='OCUPADA')
        Venta.objects.create(
            caja=self.caja,
            cajero=self.cajero_user,
            punto_venta=pv_nuevo,
            modalidad='MESA',
            mesa=mesa,
            total=Decimal('5000'),
            estado='ABIERTA'
        )

        self.client.force_login(self.admin_user)

        # Intento de desactivación rechazado
        resp_mod = self.client.post(reverse('administrador'), {
            'accion': 'modificar_local',
            'local_id': pv_nuevo.id,
            'nombre': pv_nuevo.nombre,
            'activo': 'false'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp_mod.status_code, 400)
        self.assertIn("cuentas en consumo activas", resp_mod.json()['mensaje'])

        # Intento de eliminación rechazado
        resp_del = self.client.post(reverse('administrador'), {
            'accion': 'eliminar_local',
            'local_id': pv_nuevo.id
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp_del.status_code, 400)
        self.assertIn("cuentas en consumo activas", resp_del.json()['mensaje'])

    def test_rf14_7_soft_delete_preserva_historico_ventas_y_cajas(self):
        """RF14 / Problema: Locales con transacciones históricas no se eliminan físicamente (soft-delete activo=False)"""
        from ventas.models import PuntoVenta, Venta, Caja

        from django.contrib.auth.models import User
        from ventas.models import PerfilEmpleado

        pv_hist = PuntoVenta.objects.create(nombre="Buffet Antiguo Histórico", tipo="Buffet", activo=True)
        u_hist = User.objects.create_user('cajero_hist14', 'cajerohist14@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=u_hist, rol='CAJERO', punto_venta_actual=pv_hist)
        # Caja histórica ya cerrada
        caja_cerrada = Caja.objects.create(
            jornada=self.jornada,
            cajero=u_hist,
            punto_venta=pv_hist,
            monto_apertura=Decimal('10000'),
            estado='CERRADA'
        )
        # Venta histórica ya pagada
        venta_pagada = Venta.objects.create(
            caja=caja_cerrada,
            cajero=self.cajero_user,
            punto_venta=pv_hist,
            modalidad='VENTA_RAPIDA',
            total=Decimal('15000'),
            estado='PAGADA'
        )

        self.client.force_login(self.admin_user)

        resp = self.client.post(reverse('administrador'), {
            'accion': 'eliminar_local',
            'local_id': pv_hist.id
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['modo'], 'soft-delete')

        pv_hist.refresh_from_db()
        self.assertFalse(pv_hist.activo)
        # Registros de auditoría intactos
        self.assertTrue(Venta.objects.filter(id=venta_pagada.id).exists())
        self.assertTrue(Caja.objects.filter(id=caja_cerrada.id).exists())

    def test_rf14_8_hard_delete_sin_historial_y_desasigna_trabajadores(self):
        """RF14: Local virgen sin historial se elimina físicamente y libera a los trabajadores asignados"""
        from ventas.models import PuntoVenta, PerfilEmpleado
        from django.contrib.auth.models import User

        pv_virgen = PuntoVenta.objects.create(nombre="Kiosco Demo Temporal", tipo="Kiosco", activo=True)
        u_temp = User.objects.create_user('temp_colab', 'temp@safari.cl', 'safari123')
        perfil_temp = PerfilEmpleado.objects.create(usuario=u_temp, rol='MESERO', punto_venta_actual=pv_virgen)

        self.client.force_login(self.admin_user)

        resp = self.client.post(reverse('administrador'), {
            'accion': 'eliminar_local',
            'local_id': pv_virgen.id
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['modo'], 'hard-delete')

        # Local ya no existe
        self.assertFalse(PuntoVenta.objects.filter(id=pv_virgen.id).exists())

        # Colaborador liberado y no eliminado
        perfil_temp.refresh_from_db()
        self.assertIsNone(perfil_temp.punto_venta_actual)
        self.assertTrue(User.objects.filter(id=u_temp.id).exists())

    def test_rf14_9_asociacion_mesas_menus_y_productos(self):
        """RF14: Asociación estructural de mesas, menús y productos habilitados por punto de venta"""
        from ventas.models import PuntoVenta, Mesa, Menu, Producto, Categoria

        pv = PuntoVenta.objects.create(nombre="Rincón Criollo Parrillero", tipo="Parrillada", activo=True)
        mesa = Mesa.objects.create(identificador="P1", capacidad=6, punto_venta=pv, estado='HABILITADA')
        menu = Menu.objects.create(nombre="Carta Asados Safari", punto_venta=pv)

        cat, _ = Categoria.objects.get_or_create(nombre="Carnes")
        prod = Producto.objects.create(nombre="Parrillada Familiar Safari", precio_base=Decimal('28000'), categoria=cat)
        prod.puntos_venta.add(pv)

        self.assertEqual(mesa.punto_venta, pv)
        self.assertEqual(menu.punto_venta, pv)
        self.assertIn(pv, prod.puntos_venta.all())
        self.assertIn(prod, pv.productos_disponibles.all())

    def test_rf14_10_control_acceso_roles_no_admin(self):
        """RF14 / Seguridad: Roles Cajero, Mesero, Cocinero y anónimos son bloqueados y redirigidos con alerta"""
        # 1. Cajero
        self.client.force_login(self.cajero_user)
        r1 = self.client.post(reverse('administrador'), {'accion': 'crear_local', 'nombre': 'Local Hacker 1'}, follow=True)
        self.assertRedirects(r1, reverse('vendedor'))
        self.assertContains(r1, "Acceso restringido")

        # 2. Mesero
        self.client.force_login(self.mesero_user)
        r2 = self.client.post(reverse('administrador'), {'accion': 'crear_local', 'nombre': 'Local Hacker 2'}, follow=True)
        self.assertRedirects(r2, reverse('mesero'))
        self.assertContains(r2, "Acceso restringido")

        # 3. Cocinero
        self.client.force_login(self.cocinero_user)
        r3 = self.client.get(reverse('administrador_local', kwargs={'local_id': self.pv_central.id}), follow=True)
        self.assertRedirects(r3, reverse('cocina'))
        self.assertContains(r3, "Acceso restringido")

        # 4. Anónimo
        self.client.logout()
        r4 = self.client.post(reverse('administrador'), {'accion': 'crear_local', 'nombre': 'Local Anonimo'}, follow=True)
        self.assertRedirects(r4, reverse('index'))
        self.assertContains(r4, "Acceso protegido")

    def test_rf14_11_manejo_local_inexistente(self):
        """RF14 / Robustez: Manejo seguro y controlado de identificadores de local inexistentes"""
        self.client.force_login(self.admin_user)

        # GET local inexistente -> 404
        r_get = self.client.get(reverse('administrador_local', kwargs={'local_id': 999999}))
        self.assertEqual(r_get.status_code, 404)

        # Modificar local inexistente -> 404
        r_mod = self.client.post(reverse('administrador'), {
            'accion': 'modificar_local',
            'local_id': 999999,
            'nombre': 'Local Fantasma'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r_mod.status_code, 404)



# ==============================================================================
# SUITE OFICIAL DE PRUEBAS AUTOMATIZADAS RF15 (Posicionamiento de Productos y Menús)
# ==============================================================================

class SafariRF15PosicionamientoProductosMenusTests(TestCase):
    """
    Suite oficial de pruebas automatizadas para RF15 - Posicionamiento de Productos y Menús:
    - Validación de disponibilidad de productos por Punto de Venta (local).
    - Menú por local: inclusión de productos vía Menú activo o asignación directa.
    - Rechazo estricto en POS Cajero y Mesero de productos no disponibles o de otro local.
    - Rechazo de productos desactivados (activo=False).
    - Preservación de integridad histórica contable al desasignar o desactivar productos.
    - Menú vacío o local sin productos.
    - Actualización dinámica: cambios en el catálogo de un local invalidan ventas en terminales.
    - Productos multi-local disponibles en todos sus puntos de venta asignados.
    - Filtrado dinámico en la vista de emisión de tickets del Cajero.
    """

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.hoy = timezone.localdate()

        # Usuarios
        self.admin = User.objects.create_user('admin_rf15', 'admin15@safari.cl', 'safari123')
        self.cajero_a = User.objects.create_user('cajero15_a', 'cajero_a@safari.cl', 'safari123')
        self.cajero_b = User.objects.create_user('cajero15_b', 'cajero_b@safari.cl', 'safari123')
        self.mesero_a = User.objects.create_user('mesero15_a', 'mesero_a@safari.cl', 'safari123')

        # Locales
        self.local_a = PuntoVenta.objects.create(nombre="Terraza Safari Central", tipo="RESTAURANTE", activo=True)
        self.local_b = PuntoVenta.objects.create(nombre="Kiosco Safari Express", tipo="KIOSCO", activo=True)
        self.local_vacio = PuntoVenta.objects.create(nombre="Cafetería Sin Carta", tipo="CAFETERIA", activo=True)

        # Perfiles
        PerfilEmpleado.objects.create(usuario=self.admin, rol='ADMINISTRADOR', punto_venta_actual=self.local_a)
        PerfilEmpleado.objects.create(usuario=self.cajero_a, rol='CAJERO', punto_venta_actual=self.local_a)
        PerfilEmpleado.objects.create(usuario=self.cajero_b, rol='CAJERO', punto_venta_actual=self.local_b)
        PerfilEmpleado.objects.create(usuario=self.mesero_a, rol='MESERO', punto_venta_actual=self.local_a)

        # Categoría
        self.cat = Categoria.objects.create(nombre="Gastronomía RF15", activo=True)

        # Productos
        self.prod_a = Producto.objects.create(
            nombre="Plato Exclusivo Terraza",
            categoria=self.cat,
            precio_base=Decimal('8500'),
            activo=True
        )
        self.prod_a.puntos_venta.add(self.local_a)

        self.prod_b = Producto.objects.create(
            nombre="Snack Exclusivo Kiosco",
            categoria=self.cat,
            precio_base=Decimal('2500'),
            activo=True
        )
        self.prod_b.puntos_venta.add(self.local_b)

        self.prod_multi = Producto.objects.create(
            nombre="Bebida Compartida Ambos Locales",
            categoria=self.cat,
            precio_base=Decimal('1800'),
            activo=True
        )
        self.prod_multi.puntos_venta.add(self.local_a, self.local_b)

        self.prod_inactivo = Producto.objects.create(
            nombre="Plato Descontinuado RF15",
            categoria=self.cat,
            precio_base=Decimal('5000'),
            activo=False
        )
        self.prod_inactivo.puntos_venta.add(self.local_a)

        self.prod_solo_menu = Producto.objects.create(
            nombre="Postre Especial Carta Terraza",
            categoria=self.cat,
            precio_base=Decimal('4200'),
            activo=True
        )

        # Menús
        self.menu_a = Menu.objects.create(
            nombre="Carta Ejecutiva Terraza",
            punto_venta=self.local_a,
            activo=True
        )
        self.menu_a.productos.add(self.prod_solo_menu)

        self.menu_vacio = Menu.objects.create(
            nombre="Carta Vacía",
            punto_venta=self.local_vacio,
            activo=True
        )

        # Jornada y Cajas
        self.jornada = Jornada.objects.create(
            fecha=self.hoy,
            estado='ABIERTA',
            usuario_apertura=self.admin
        )
        self.caja_a = Caja.objects.create(
            nombre="Caja Terraza 1",
            jornada=self.jornada,
            cajero=self.cajero_a,
            punto_venta=self.local_a,
            monto_apertura=Decimal('50000'),
            estado='ABIERTA'
        )
        self.caja_b = Caja.objects.create(
            nombre="Caja Kiosco 1",
            jornada=self.jornada,
            cajero=self.cajero_b,
            punto_venta=self.local_b,
            monto_apertura=Decimal('30000'),
            estado='ABIERTA'
        )

        # Mesa para mesero
        self.mesa_a = Mesa.objects.create(
            identificador="T1",
            punto_venta=self.local_a,
            capacidad=4,
            estado='HABILITADA'
        )

    def test_rf15_1_producto_disponible_en_local_permite_venta_pos(self):
        """RF15.1: Cajero puede vender exitosamente un producto asignado al Punto de Venta de su caja"""
        self.client.force_login(self.cajero_a)
        payload = [
            {"producto_id": self.prod_a.id, "cantidad": 2}
        ]
        resp = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps(payload),
            'metodo_pago': 'EFECTIVO',
            'modalidad': 'VENTA_RAPIDA'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['total'], 17000.0)

        # Verificar Venta en base de datos
        venta = Venta.objects.get(id=data['venta_id'])
        self.assertEqual(venta.punto_venta, self.local_a)
        self.assertEqual(venta.detalles.first().producto, self.prod_a)

    def test_rf15_2_producto_no_disponible_en_local_rechazado_pos(self):
        """RF15.2 / Problema 1: Cajero de Local A intenta vender producto exclusivo de Local B -> HTTP 400 rechazado"""
        self.client.force_login(self.cajero_a)
        payload = [
            {"producto_id": self.prod_b.id, "cantidad": 1}
        ]
        resp = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps(payload),
            'metodo_pago': 'EFECTIVO',
            'modalidad': 'VENTA_RAPIDA'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['ok'])
        self.assertIn("no se encuentra disponible para venta en el local", data['error'])
        self.assertIn(self.local_a.nombre, data['error'])

    def test_rf15_3_producto_desactivado_rechazado_en_venta_pos(self):
        """RF15.3 / Problema 2: Terminal intenta vender producto desactivado del catálogo (activo=False) -> Rechazado"""
        self.client.force_login(self.cajero_a)
        payload = [
            {"producto_id": self.prod_inactivo.id, "cantidad": 1}
        ]
        resp = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps(payload),
            'metodo_pago': 'EFECTIVO',
            'modalidad': 'VENTA_RAPIDA'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['ok'])
        self.assertIn("desactivado del catálogo", data['error'])

    def test_rf15_4_mesero_comanda_permite_producto_disponible_en_local(self):
        """RF15.4: Mesero en salón emite comanda con producto asignado a su local -> Éxito total"""
        self.client.force_login(self.mesero_a)
        items = [
            {"id": self.prod_a.id, "nombre": self.prod_a.nombre, "cantidad": 1, "precio": float(self.prod_a.precio_base), "destino": "COCINA"}
        ]
        resp = self.client.post(reverse('mesero') + f"?local_id={self.local_a.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': self.mesa_a.id,
            'items_json': json.dumps(items)
        }, follow=True)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "despachada con éxito")

        self.mesa_a.refresh_from_db()
        self.assertEqual(self.mesa_a.estado, 'OCUPADA')
        venta = Venta.objects.filter(mesa=self.mesa_a, estado='ABIERTA').first()
        self.assertIsNotNone(venta)
        self.assertEqual(venta.detalles.first().producto, self.prod_a)

    def test_rf15_5_mesero_comanda_rechaza_producto_de_otro_local(self):
        """RF15.5 / Problema 1: Mesero intenta colar producto de otro local en la comanda -> Rechazado con mensaje"""
        self.client.force_login(self.mesero_a)
        items = [
            {"id": self.prod_b.id, "nombre": self.prod_b.nombre, "cantidad": 1, "precio": float(self.prod_b.precio_base), "destino": "BARRA"}
        ]
        resp = self.client.post(reverse('mesero') + f"?local_id={self.local_a.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': self.mesa_a.id,
            'items_json': json.dumps(items)
        }, follow=True)

        self.assertContains(resp, "no se encuentra disponible para venta en el local")
        self.assertEqual(DetalleVenta.objects.filter(producto=self.prod_b).count(), 0)

    def test_rf15_6_mesero_comanda_rechaza_producto_desactivado(self):
        """RF15.6 / Problema 2: Mesero intenta emitir comanda con producto desactivado -> Rechazado"""
        self.client.force_login(self.mesero_a)
        items = [
            {"id": self.prod_inactivo.id, "nombre": self.prod_inactivo.nombre, "cantidad": 1, "precio": float(self.prod_inactivo.precio_base), "destino": "COCINA"}
        ]
        resp = self.client.post(reverse('mesero') + f"?local_id={self.local_a.id}", {
            'accion': 'enviar_comanda',
            'mesa_id': self.mesa_a.id,
            'items_json': json.dumps(items)
        }, follow=True)

        self.assertContains(resp, "desactivado del catálogo")
        self.assertEqual(DetalleVenta.objects.filter(producto=self.prod_inactivo).count(), 0)

    def test_rf15_7_producto_disponible_por_menu_activo(self):
        """RF15.7: Producto NO asignado en puntos_venta pero presente en Carta activa del local se valida y vende"""
        # prod_solo_menu no está en puntos_venta de local_a, pero sí en menu_a (activo)
        self.assertFalse(self.prod_solo_menu.puntos_venta.filter(id=self.local_a.id).exists())
        self.assertTrue(self.prod_solo_menu.esta_disponible_en(self.local_a))
        self.assertTrue(self.local_a.get_productos_disponibles().filter(id=self.prod_solo_menu.id).exists())

        self.client.force_login(self.cajero_a)
        payload = [
            {"producto_id": self.prod_solo_menu.id, "cantidad": 1}
        ]
        resp = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps(payload),
            'metodo_pago': 'EFECTIVO',
            'modalidad': 'VENTA_RAPIDA'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

    def test_rf15_8_menu_desactivado_inhabilita_productos_exclusivos(self):
        """RF15.8: Desactivar una carta inhabilita inmediatamente los productos que solo estaban en esa carta"""
        self.menu_a.activo = False
        self.menu_a.save()

        self.assertFalse(self.prod_solo_menu.esta_disponible_en(self.local_a))
        self.assertFalse(self.local_a.get_productos_disponibles().filter(id=self.prod_solo_menu.id).exists())

        self.client.force_login(self.cajero_a)
        payload = [
            {"producto_id": self.prod_solo_menu.id, "cantidad": 1}
        ]
        resp = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps(payload),
            'metodo_pago': 'EFECTIVO',
            'modalidad': 'VENTA_RAPIDA'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 400)
        self.assertIn("no se encuentra disponible", resp.json()['error'])

    def test_rf15_9_actualizacion_dinamica_desasignar_producto(self):
        """RF15.9 / Problema 5: Administrador retira producto de local; terminal antigua que intente venderlo es rechazada"""
        # Inicialmente disponible
        self.assertTrue(self.prod_a.esta_disponible_en(self.local_a))

        # Administrador retira el producto del catálogo de ese local
        self.prod_a.puntos_venta.remove(self.local_a)
        self.assertFalse(self.prod_a.esta_disponible_en(self.local_a))

        # Terminal intenta vender el producto retirado
        self.client.force_login(self.cajero_a)
        payload = [{"producto_id": self.prod_a.id, "cantidad": 1}]
        resp = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps(payload),
            'metodo_pago': 'EFECTIVO',
            'modalidad': 'VENTA_RAPIDA'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 400)
        self.assertIn("no se encuentra disponible", resp.json()['error'])

    def test_rf15_10_historico_ventas_preservado_tras_retirar_producto_de_local(self):
        """RF15.10 / Problema 4: Producto retirado o desactivado conserva 100% sus ventas históricas e integridad contable"""
        # Registrar venta inicial
        self.client.force_login(self.cajero_a)
        payload = [{"producto_id": self.prod_a.id, "cantidad": 3}]
        resp = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps(payload),
            'metodo_pago': 'EFECTIVO',
            'modalidad': 'VENTA_RAPIDA'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        venta_id = resp.json()['venta_id']

        # Desasignar del local y soft-deactivate
        self.prod_a.puntos_venta.clear()
        self.prod_a.activo = False
        self.prod_a.save()

        # Auditoría histórica
        venta = Venta.objects.get(id=venta_id)
        self.assertEqual(venta.total, Decimal('25500.00')) # 3 * 8500
        det = venta.detalles.first()
        self.assertEqual(det.producto, self.prod_a)
        self.assertEqual(det.cantidad, 3)
        self.assertEqual(det.subtotal, Decimal('25500.00'))

    def test_rf15_11_menu_vacio_y_local_sin_productos(self):
        """RF15.11 / Problema 3: Menú vacío y local sin productos configurados no ofrecen catálogo y rechazan compras"""
        self.assertTrue(self.menu_vacio.esta_vacio())
        self.assertEqual(self.menu_vacio.productos_activos().count(), 0)
        self.assertEqual(self.local_vacio.get_productos_disponibles().count(), 0)

        # Validar rechazo con helper
        from ventas.utils import validar_disponibilidad_producto
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError) as ctx:
            validar_disponibilidad_producto(self.prod_a, self.local_vacio)
        self.assertIn("no se encuentra disponible para venta en el local", str(ctx.exception))

    def test_rf15_12_producto_multi_local_disponible_en_ambos(self):
        """RF15.12: Producto asignado a múltiples locales puede ser vendido legítimamente en ambos terminales"""
        # Terminal Local A
        self.client.force_login(self.cajero_a)
        r_a = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps([{"producto_id": self.prod_multi.id, "cantidad": 1}]),
            'metodo_pago': 'EFECTIVO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r_a.status_code, 200)
        self.assertTrue(r_a.json()['ok'])

        # Terminal Local B
        self.client.force_login(self.cajero_b)
        r_b = self.client.post(reverse('crear_ticket'), {
            'items_json': json.dumps([{"producto_id": self.prod_multi.id, "cantidad": 1}]),
            'metodo_pago': 'EFECTIVO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r_b.status_code, 200)
        self.assertTrue(r_b.json()['ok'])

    def test_rf15_13_vendedor_crear_ticket_get_filtra_catalogo_por_local(self):
        """RF15.13: GET en terminal vendedor_crear_ticket entrega solo productos disponibles del local del cajero"""
        self.client.force_login(self.cajero_a)
        resp = self.client.get(reverse('crear_ticket'))
        self.assertEqual(resp.status_code, 200)

        prods_context = list(resp.context['productos_activos'])
        # prod_a y prod_multi y prod_solo_menu deben estar presentes
        self.assertIn(self.prod_a, prods_context)
        self.assertIn(self.prod_multi, prods_context)
        self.assertIn(self.prod_solo_menu, prods_context)

        # prod_b (exclusivo de local_b) y prod_inactivo NO deben estar presentes
        self.assertNotIn(self.prod_b, prods_context)
        self.assertNotIn(self.prod_inactivo, prods_context)

# ==============================================================================
# RF16: PRUEBAS DE CONTROL DE TIEMPOS DE ATENCIÓN
# ==============================================================================
class SafariRF16ControlTiemposAtencionTests(TestCase):
    """
    Pruebas unitarias e integración de alta fidelidad para RF16:
    - RF16.1: Cálculo exacto de timestamps y duraciones en ciclo de vida completo.
    - RF16.2: Blindaje de duraciones no negativas ante desfases o skew de reloj.
    - RF16.3: Incompletos no inventados: pedidos pendientes/en prep retornan None en cálculos cerrados.
    - RF16.4: Tiempos en curso (en_curso=True) para monitoreo activo de KDS.
    - RF16.5: Robustez ante cambio de día y medianoche (cruce de fechas 23:50 a 00:15).
    - RF16.6: Zona horaria oficial de Chile ('America/Santiago') sin errores naive/aware.
    - RF16.7: Aislamiento estricto de tiempos en comandas multi-ronda sobre una misma mesa.
    - RF16.8: Pedido cancelado excluido de métricas de entrega sin tiempos fabricados.
    - RF16.9: Servicio de promedios por local (calcular_tiempos_promedio_local) para reportes de auditoría.
    - RF16.10: Métodos auxiliares de despacho en modelo Entrega (get_tiempo_desde_listo_minutos).
    - RF16.11: Trazabilidad y visualización en vista administrador_historial.
    - RF16.12: Dashboard administrador_local incorpora métricas de tiempos de atención.
    """

    def setUp(self):
        from decimal import Decimal
        from django.contrib.auth.models import User
        from django.utils import timezone
        from ventas.models import PuntoVenta, PerfilEmpleado, Mesa, Producto, Categoria, Venta, Pedido, DetallePedido, Ticket, Entrega, Jornada, Caja

        self.pv_central = PuntoVenta.objects.create(nombre="Restaurante Central Safari", activo=True)
        self.pv_barra = PuntoVenta.objects.create(nombre="Barra Rápida Safari", activo=True)

        self.admin_user = User.objects.create_superuser('admin_rf16', 'admin@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.admin_user, rol='ADMINISTRADOR', punto_venta_actual=self.pv_central)

        self.cocinero_user = User.objects.create_user('cocinero_rf16', 'cocinero@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.cocinero_user, rol='COCINERO', punto_venta_actual=self.pv_central)

        self.mesero_user = User.objects.create_user('mesero_rf16', 'mesero@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.mesero_user, rol='MESERO', punto_venta_actual=self.pv_central)

        self.cajero_user = User.objects.create_user('cajero_rf16', 'cajero@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.cajero_user, rol='CAJERO', punto_venta_actual=self.pv_central)

        self.mesa_m1 = Mesa.objects.create(identificador="M-T16", capacidad=4, punto_venta=self.pv_central, estado='HABILITADA')

        self.cat_cocina = Categoria.objects.create(nombre="Cocina Caliente T16")
        self.prod_hamburguesa = Producto.objects.create(
            nombre="Hamburguesa Temporizada",
            categoria=self.cat_cocina,
            precio_base=Decimal('8900'),
            activo=True
        )
        self.prod_hamburguesa.puntos_venta.add(self.pv_central)

        hoy = timezone.localdate()
        self.jornada, _ = Jornada.objects.get_or_create(
            fecha=hoy,
            defaults={'usuario_apertura': self.admin_user, 'estado': 'ABIERTA'}
        )
        self.caja, _ = Caja.objects.get_or_create(
            jornada=self.jornada,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
            defaults={'monto_apertura': Decimal('50000.00'), 'estado': 'ABIERTA'}
        )

        # Venta base para pruebas
        self.venta = Venta.objects.create(
            punto_venta=self.pv_central,
            mesa=self.mesa_m1,
            cajero=self.mesero_user,
            caja=self.caja,
            modalidad='MESA',
            estado='PENDIENTE'
        )

    def test_rf16_1_calculo_tiempos_ciclo_completo_normal(self):
        """RF16.1: Cálculo exacto de cola, preparación, despacho y espera total en ciclo normal"""
        import datetime
        from django.utils import timezone
        from ventas.models import Pedido, DetallePedido, Entrega

        base_time = timezone.now() - datetime.timedelta(minutes=30)

        # Crear pedido simulando creado_en
        pedido = Pedido.objects.create(venta=self.venta, estado='PENDIENTE')
        Pedido.objects.filter(id=pedido.id).update(creado_en=base_time)
        pedido.refresh_from_db()

        # Inicio preparación a los 5 minutos
        t_inicio = base_time + datetime.timedelta(minutes=5)
        # Listo a los 20 minutos (15 min de preparación)
        t_listo = base_time + datetime.timedelta(minutes=20)
        # Entregado a los 23 minutos (3 min de despacho)
        t_entrega = base_time + datetime.timedelta(minutes=23)

        pedido.fecha_inicio_preparacion = t_inicio
        pedido.fecha_listo = t_listo
        pedido.estado = 'LISTO'
        pedido.save()

        entrega = Entrega.objects.create(
            pedido=pedido,
            usuario_entrega=self.cocinero_user,
            observaciones="Entrega a tiempo"
        )
        Entrega.objects.filter(id=entrega.id).update(fecha_hora_entrega=t_entrega)
        entrega.refresh_from_db()
        pedido.refresh_from_db()
        pedido.estado = 'ENTREGADO'
        pedido.save()

        # Verificaciones métricas
        self.assertEqual(pedido.get_tiempo_cola_minutos(), 5.0)
        self.assertEqual(pedido.get_tiempo_cola_segundos(), 300)
        self.assertEqual(pedido.get_tiempo_preparacion_minutos(), 15.0)
        self.assertEqual(pedido.get_tiempo_preparacion_segundos(), 900)
        self.assertEqual(pedido.get_tiempo_despacho_minutos(), 3.0)
        self.assertEqual(pedido.get_tiempo_despacho_segundos(), 180)
        self.assertEqual(pedido.get_tiempo_espera_total_minutos(), 23.0)
        self.assertEqual(pedido.get_tiempo_espera_total_segundos(), 1380)

        # Validación de orden temporal
        es_valido, inconsistencias = pedido.validar_orden_temporal()
        self.assertTrue(es_valido)
        self.assertEqual(len(inconsistencias), 0)

    def test_rf16_2_tiempos_no_negativos_blindaje_desfase(self):
        """RF16.2: Blindaje de duraciones no negativas ante desfases cronológicos o reloj invertido"""
        import datetime
        from django.utils import timezone
        from ventas.models import Pedido

        base_time = timezone.now()
        pedido = Pedido.objects.create(venta=self.venta, estado='LISTO')
        Pedido.objects.filter(id=pedido.id).update(creado_en=base_time)
        pedido.refresh_from_db()

        # Invertir deliberadamente timestamps
        pedido.fecha_inicio_preparacion = base_time - datetime.timedelta(minutes=5)  # antes de creación
        pedido.fecha_listo = pedido.fecha_inicio_preparacion - datetime.timedelta(minutes=3)  # antes de inicio
        pedido.fecha_entregado = pedido.fecha_listo - datetime.timedelta(minutes=2)  # antes de listo
        pedido.save()

        # Los cálculos deben retornar 0.0 y NUNCA números negativos
        self.assertEqual(pedido.get_tiempo_cola_minutos(), 0.0)
        self.assertEqual(pedido.get_tiempo_preparacion_minutos(), 0.0)
        self.assertEqual(pedido.get_tiempo_despacho_minutos(), 0.0)
        self.assertEqual(pedido.get_tiempo_espera_total_minutos(), 0.0)

        # validar_orden_temporal debe alertar las inconsistencias
        es_valido, inconsistencias = pedido.validar_orden_temporal()
        self.assertFalse(es_valido)
        self.assertGreaterEqual(len(inconsistencias), 3)

    def test_rf16_3_incompletos_no_inventados(self):
        """RF16.3: Incompletos no inventados: pedidos no entregados retornan None en cálculos cerrados"""
        import datetime
        from django.utils import timezone
        from ventas.models import Pedido

        base_time = timezone.now() - datetime.timedelta(minutes=10)
        pedido_pendiente = Pedido.objects.create(venta=self.venta, estado='PENDIENTE')
        Pedido.objects.filter(id=pedido_pendiente.id).update(creado_en=base_time)
        pedido_pendiente.refresh_from_db()

        # Para un pedido pendiente, la espera total cerrada debe ser None (no inventada)
        self.assertIsNone(pedido_pendiente.get_tiempo_espera_total_minutos(en_curso=False))
        self.assertIsNone(pedido_pendiente.get_tiempo_preparacion_minutos(en_curso=False))
        self.assertIsNone(pedido_pendiente.get_tiempo_despacho_minutos(en_curso=False))
        self.assertIsNone(pedido_pendiente.fecha_entregado)

        # Pedido en preparación sin marcar como listo
        pedido_prep = Pedido.objects.create(venta=self.venta, estado='EN_PREPARACION')
        pedido_prep.fecha_inicio_preparacion = timezone.now() - datetime.timedelta(minutes=4)
        pedido_prep.save()

        self.assertIsNone(pedido_prep.get_tiempo_preparacion_minutos(en_curso=False))
        self.assertIsNone(pedido_prep.get_tiempo_espera_total_minutos(en_curso=False))

    def test_rf16_4_tiempos_en_curso_monitoreo_kds(self):
        """RF16.4: Tiempos en curso (en_curso=True) permiten monitorear demoras en tiempo real en KDS"""
        import datetime
        from django.utils import timezone
        from ventas.models import Pedido

        t_creacion = timezone.now() - datetime.timedelta(minutes=12)
        pedido = Pedido.objects.create(venta=self.venta, estado='PENDIENTE')
        Pedido.objects.filter(id=pedido.id).update(creado_en=t_creacion)
        pedido.refresh_from_db()

        # En curso para PENDIENTE calcula cola transcurrida
        t_cola_curso = pedido.get_tiempo_cola_minutos(en_curso=True)
        self.assertIsNotNone(t_cola_curso)
        self.assertGreaterEqual(t_cola_curso, 11.9)

        # Espera total en curso
        t_espera_curso = pedido.get_tiempo_espera_total_minutos(en_curso=True)
        self.assertIsNotNone(t_espera_curso)
        self.assertGreaterEqual(t_espera_curso, 11.9)

        # Cambiar a EN_PREPARACION hace 6 minutos
        pedido.estado = 'EN_PREPARACION'
        pedido.fecha_inicio_preparacion = timezone.now() - datetime.timedelta(minutes=6)
        pedido.save()

        t_prep_curso = pedido.get_tiempo_preparacion_minutos(en_curso=True)
        self.assertIsNotNone(t_prep_curso)
        self.assertGreaterEqual(t_prep_curso, 5.9)

    def test_rf16_5_cambio_de_dia_medianoche(self):
        """RF16.5: Robustez ante cruce de medianoche (pedido creado 23:50 y entregado 00:15 del día siguiente)"""
        import datetime
        from django.utils import timezone
        from ventas.models import Pedido, Entrega

        # Definir fechas a través de medianoche
        tz = timezone.get_current_timezone()
        t_creacion = timezone.make_aware(datetime.datetime(2026, 11, 1, 23, 50, 0), tz)
        t_inicio = timezone.make_aware(datetime.datetime(2026, 11, 1, 23, 55, 0), tz)
        t_listo = timezone.make_aware(datetime.datetime(2026, 11, 2, 0, 10, 0), tz)
        t_entrega = timezone.make_aware(datetime.datetime(2026, 11, 2, 0, 15, 0), tz)

        pedido = Pedido.objects.create(venta=self.venta, estado='LISTO')
        Pedido.objects.filter(id=pedido.id).update(
            creado_en=t_creacion,
            fecha_inicio_preparacion=t_inicio,
            fecha_listo=t_listo,
            estado='LISTO'
        )
        pedido.refresh_from_db()

        entrega = Entrega.objects.create(pedido=pedido, usuario_entrega=self.cocinero_user)
        Entrega.objects.filter(id=entrega.id).update(fecha_hora_entrega=t_entrega)
        entrega.refresh_from_db()
        pedido.refresh_from_db()

        # Verificaciones cruzando medianoche (25 minutos totales)
        self.assertEqual(pedido.get_tiempo_cola_minutos(), 5.0)
        self.assertEqual(pedido.get_tiempo_preparacion_minutos(), 15.0)
        self.assertEqual(pedido.get_tiempo_despacho_minutos(), 5.0)
        self.assertEqual(pedido.get_tiempo_espera_total_minutos(), 25.0)

        # Orden temporal válido a través del día
        es_valido, _ = pedido.validar_orden_temporal()
        self.assertTrue(es_valido)

    def test_rf16_6_zona_horaria_chile(self):
        """RF16.6: Formateo y métricas localizadas para la zona horaria oficial de Chile"""
        import datetime
        from django.utils import timezone
        from ventas.utils import formatear_fecha_hora_chile, calcular_metricas_tiempos_pedido
        from ventas.models import Pedido

        tz = timezone.get_current_timezone()
        dt_test = timezone.make_aware(datetime.datetime(2026, 11, 1, 14, 30, 45), tz)

        str_formateada = formatear_fecha_hora_chile(dt_test)
        self.assertEqual(str_formateada, "01/11/2026 14:30:45")

        # Datetime naive debe manejarse sin excepción
        dt_naive = datetime.datetime(2026, 11, 1, 14, 30, 45)
        str_naive = formatear_fecha_hora_chile(dt_naive)
        self.assertIn("01/11/2026", str_naive)

        # None debe retornar None
        self.assertIsNone(formatear_fecha_hora_chile(None))

        # Métricas de pedido enriquecidas con strings chilenos
        pedido = Pedido.objects.create(venta=self.venta, estado='PENDIENTE')
        metricas = calcular_metricas_tiempos_pedido(pedido)
        self.assertIn('creado_en_chile', metricas)
        self.assertIn('mesa_identificador', metricas)
        self.assertEqual(metricas['mesa_identificador'], "M-T16")

    def test_rf16_7_rondas_separadas_tiempos_independientes(self):
        """RF16.7: Aislamiento estricto de tiempos en comandas multi-ronda de una misma mesa"""
        import datetime
        from django.utils import timezone
        from ventas.models import Pedido, Entrega

        tz = timezone.get_current_timezone()
        t0 = timezone.now() - datetime.timedelta(hours=2)

        # Ronda 1
        ronda_1 = Pedido.objects.create(venta=self.venta, estado='LISTO')
        Pedido.objects.filter(id=ronda_1.id).update(
            creado_en=t0,
            fecha_inicio_preparacion=t0 + datetime.timedelta(minutes=3),
            fecha_listo=t0 + datetime.timedelta(minutes=15),
            estado='LISTO'
        )
        ronda_1.refresh_from_db()

        ent_1 = Entrega.objects.create(pedido=ronda_1, usuario_entrega=self.cocinero_user)
        Entrega.objects.filter(id=ent_1.id).update(fecha_hora_entrega=t0 + datetime.timedelta(minutes=18))
        ent_1.refresh_from_db()

        # Ronda 2 generada 50 minutos después
        t_r2 = t0 + datetime.timedelta(minutes=50)
        ronda_2 = Pedido.objects.create(venta=self.venta, estado='LISTO')
        Pedido.objects.filter(id=ronda_2.id).update(
            creado_en=t_r2,
            fecha_inicio_preparacion=t_r2 + datetime.timedelta(minutes=4),
            fecha_listo=t_r2 + datetime.timedelta(minutes=16),
            estado='LISTO'
        )
        ronda_2.refresh_from_db()

        ent_2 = Entrega.objects.create(pedido=ronda_2, usuario_entrega=self.cocinero_user)
        Entrega.objects.filter(id=ent_2.id).update(fecha_hora_entrega=t_r2 + datetime.timedelta(minutes=20))
        ent_2.refresh_from_db()

        ronda_1.refresh_from_db()
        ronda_2.refresh_from_db()

        # Tiempos de Ronda 1
        self.assertEqual(ronda_1.get_tiempo_cola_minutos(), 3.0)
        self.assertEqual(ronda_1.get_tiempo_preparacion_minutos(), 12.0)
        self.assertEqual(ronda_1.get_tiempo_despacho_minutos(), 3.0)
        self.assertEqual(ronda_1.get_tiempo_espera_total_minutos(), 18.0)

        # Tiempos de Ronda 2 estrictamente independientes (no suma los 50 min previos)
        self.assertEqual(ronda_2.get_tiempo_cola_minutos(), 4.0)
        self.assertEqual(ronda_2.get_tiempo_preparacion_minutos(), 12.0)
        self.assertEqual(ronda_2.get_tiempo_despacho_minutos(), 4.0)
        self.assertEqual(ronda_2.get_tiempo_espera_total_minutos(), 20.0)

    def test_rf16_8_pedido_cancelado_sin_tiempos_inventados(self):
        """RF16.8: Pedido cancelado no reporta tiempo de entrega ni contamina los cálculos de servicio"""
        from ventas.models import Pedido
        from ventas.utils import calcular_tiempos_promedio_local

        pedido_canc = Pedido.objects.create(venta=self.venta, estado='CANCELADO')
        self.assertIsNone(pedido_canc.get_tiempo_espera_total_minutos(en_curso=False))
        self.assertIsNone(pedido_canc.fecha_entregado)

        promedios = calcular_tiempos_promedio_local(punto_venta=self.pv_central)
        self.assertEqual(promedios['total_cancelados'], 1)
        self.assertEqual(promedios['total_entregados'], 0)
        self.assertEqual(promedios['promedio_tiempo_espera_total_minutos'], 0.0)

    def test_rf16_9_servicio_promedios_local_para_reportes(self):
        """RF16.9: calcular_tiempos_promedio_local agrega únicamente órdenes entregadas reales"""
        import datetime
        from django.utils import timezone
        from ventas.models import Pedido, Entrega
        from ventas.utils import calcular_tiempos_promedio_local

        base = timezone.now() - datetime.timedelta(minutes=45)

        # Pedido 1 entregado: 10 min de espera total, 6 min de preparación
        p1 = Pedido.objects.create(venta=self.venta, estado='LISTO')
        Pedido.objects.filter(id=p1.id).update(
            creado_en=base,
            fecha_inicio_preparacion=base + datetime.timedelta(minutes=2),
            fecha_listo=base + datetime.timedelta(minutes=8),
            estado='ENTREGADO'
        )
        p1.refresh_from_db()
        e1 = Entrega.objects.create(pedido=p1, usuario_entrega=self.cocinero_user)
        Entrega.objects.filter(id=e1.id).update(fecha_hora_entrega=base + datetime.timedelta(minutes=10))
        e1.refresh_from_db()

        # Pedido 2 entregado: 20 min de espera total, 14 min de preparación
        p2 = Pedido.objects.create(venta=self.venta, estado='LISTO')
        Pedido.objects.filter(id=p2.id).update(
            creado_en=base,
            fecha_inicio_preparacion=base + datetime.timedelta(minutes=4),
            fecha_listo=base + datetime.timedelta(minutes=18),
            estado='ENTREGADO'
        )
        p2.refresh_from_db()
        e2 = Entrega.objects.create(pedido=p2, usuario_entrega=self.cocinero_user)
        Entrega.objects.filter(id=e2.id).update(fecha_hora_entrega=base + datetime.timedelta(minutes=20))
        e2.refresh_from_db()

        # Pedido 3 en preparación (no entregado)
        p3 = Pedido.objects.create(venta=self.venta, estado='EN_PREPARACION')
        p3.fecha_inicio_preparacion = timezone.now() - datetime.timedelta(minutes=5)
        p3.save()

        # Pedido 4 pendiente
        Pedido.objects.create(venta=self.venta, estado='PENDIENTE')

        promedios = calcular_tiempos_promedio_local(punto_venta=self.pv_central)

        self.assertEqual(promedios['total_pedidos'], 4)
        self.assertEqual(promedios['total_entregados'], 2)
        self.assertEqual(promedios['total_pendientes'], 1)
        self.assertEqual(promedios['total_en_preparacion'], 1)

        # Espera promedio: (10 + 20) / 2 = 15.0 min
        self.assertEqual(promedios['promedio_tiempo_espera_total_minutos'], 15.0)
        self.assertEqual(promedios['min_tiempo_espera_total_minutos'], 10.0)
        self.assertEqual(promedios['max_tiempo_espera_total_minutos'], 20.0)

        # Prep promedio: (6 + 14) / 2 = 10.0 min
        self.assertEqual(promedios['promedio_tiempo_preparacion_minutos'], 10.0)

    def test_rf16_10_entrega_model_metodos_desde_listo(self):
        """RF16.10: Modelo Entrega calcula tiempo desde listo hasta entrega comensal"""
        import datetime
        from django.utils import timezone
        from ventas.models import Pedido, Entrega

        t_listo = timezone.now() - datetime.timedelta(minutes=7)
        pedido = Pedido.objects.create(venta=self.venta, estado='LISTO', fecha_listo=t_listo)

        entrega = Entrega.objects.create(pedido=pedido, usuario_entrega=self.cocinero_user)
        # 5 minutos después de estar listo
        Entrega.objects.filter(id=entrega.id).update(fecha_hora_entrega=t_listo + datetime.timedelta(minutes=5))
        entrega.refresh_from_db()

        self.assertEqual(entrega.get_tiempo_desde_listo_minutos(), 5.0)
        self.assertEqual(entrega.get_tiempo_desde_listo_segundos(), 300)

    def test_rf16_11_administrador_historial_visualiza_tiempos_reales(self):
        """RF16.11: Vista administrador_historial muestra tiempos reales de despacho y preparación"""
        import datetime
        from django.urls import reverse
        from django.utils import timezone
        from ventas.models import Pedido, Entrega

        base = timezone.now() - datetime.timedelta(minutes=15)
        pedido = Pedido.objects.create(venta=self.venta, estado='LISTO')
        Pedido.objects.filter(id=pedido.id).update(
            creado_en=base,
            fecha_inicio_preparacion=base + datetime.timedelta(minutes=2),
            fecha_listo=base + datetime.timedelta(minutes=10),
            estado='ENTREGADO'
        )
        pedido.refresh_from_db()

        entrega = Entrega.objects.create(pedido=pedido, usuario_entrega=self.cocinero_user, observaciones="Despacho VIP")
        Entrega.objects.filter(id=entrega.id).update(fecha_hora_entrega=base + datetime.timedelta(minutes=12))
        entrega.refresh_from_db()

        self.client.force_login(self.admin_user)
        resp = self.client.get(reverse('administrador_historial'))
        self.assertEqual(resp.status_code, 200)

        # Debe contener la descripción formateada con minutos totales y de preparación
        contenido = resp.content.decode('utf-8')
        self.assertIn("12.0 min total", contenido)
        self.assertIn("Prep: 8.0 min", contenido)

    def test_rf16_12_administrador_local_incluye_promedios_tiempos(self):
        """RF16.12: Dashboard administrador_local incorpora métricas de tiempos de atención en context y UI"""
        from django.urls import reverse

        self.client.force_login(self.admin_user)
        resp = self.client.get(reverse('administrador_local', kwargs={'local_id': self.pv_central.id}))
        self.assertEqual(resp.status_code, 200)

        self.assertIn('promedios_tiempos', resp.context)
        promedios = resp.context['promedios_tiempos']
        self.assertIn('promedio_tiempo_espera_total_minutos', promedios)
        self.assertIn('promedio_tiempo_preparacion_minutos', promedios)

        contenido = resp.content.decode('utf-8')
        self.assertIn("Espera Total Promedio", contenido)
        self.assertIn("Prep. Cocina Promedio", contenido)

# ==============================================================================
# RF17: PRUEBAS DE GESTIÓN DE OCUPACIÓN DE MESAS
# ==============================================================================
class SafariRF17GestionOcupacionMesasTests(TestCase):
    """
    Pruebas unitarias e integración de alta fidelidad para RF17:
    - RF17.1: Inicio de ocupación y cálculo de duración (minutos/segundos).
    - RF17.2: Blindaje contra doble ocupación concurrente.
    - RF17.3: Blindaje contra liberación de mesa con cuenta abierta activa.
    - RF17.4: Liberación limpia sin cuenta abierta o forzada tras anulación.
    - RF17.5: Cierre atómico de cuenta de mesa y liberación de mesa.
    - RF17.6: Rechazo estricto de ocupación y comandas en mesas inactivas o en mantenimiento.
    - RF17.7: Envío de múltiples rondas no reinicia el tiempo de ocupación comensal.
    - RF17.8: Reasignación de mesa transfiere el tiempo de inicio y libera mesa origen.
    - RF17.9: Estado de ocupación 100% reconstruible desde la base de datos tras reinicio de navegador.
    - RF17.10: Servicio de métricas agregadas de ocupación y rotación por local (calcular_metricas_ocupacion_local).
    """

    def setUp(self):
        from decimal import Decimal
        from django.contrib.auth.models import User
        from django.utils import timezone
        from ventas.models import PuntoVenta, PerfilEmpleado, Mesa, Producto, Categoria, Venta, Jornada, Caja

        self.pv_central = PuntoVenta.objects.create(nombre="Restaurante Central Safari T17", activo=True)

        self.admin_user = User.objects.create_superuser('admin_rf17', 'admin@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.admin_user, rol='ADMINISTRADOR', punto_venta_actual=self.pv_central)

        self.mesero_user = User.objects.create_user('mesero_rf17', 'mesero@safari.cl', 'safari123')
        self.perfil_mesero = PerfilEmpleado.objects.create(usuario=self.mesero_user, rol='MESERO', punto_venta_actual=self.pv_central)

        self.cajero_user = User.objects.create_user('cajero_rf17', 'cajero@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.cajero_user, rol='CAJERO', punto_venta_actual=self.pv_central)

        self.mesa_1 = Mesa.objects.create(identificador="M1-RF17", capacidad=4, punto_venta=self.pv_central, estado='HABILITADA')
        self.mesa_2 = Mesa.objects.create(identificador="M2-RF17", capacidad=6, punto_venta=self.pv_central, estado='HABILITADA')
        self.mesa_inactiva = Mesa.objects.create(identificador="M-INACTIVA", capacidad=2, punto_venta=self.pv_central, estado='INACTIVA')

        self.cat_fondo = Categoria.objects.create(nombre="Platos Fondo T17")
        self.prod_churrasco = Producto.objects.create(
            nombre="Churrasco Safari T17",
            categoria=self.cat_fondo,
            precio_base=Decimal('7900'),
            activo=True
        )
        self.prod_churrasco.puntos_venta.add(self.pv_central)

        hoy = timezone.localdate()
        self.jornada, _ = Jornada.objects.get_or_create(
            fecha=hoy,
            defaults={'usuario_apertura': self.admin_user, 'estado': 'ABIERTA'}
        )
        self.caja, _ = Caja.objects.get_or_create(
            jornada=self.jornada,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
            defaults={'monto_apertura': Decimal('50000.00'), 'estado': 'ABIERTA'}
        )

    def test_rf17_1_inicio_ocupacion_y_duracion_calculada(self):
        """RF17.1: Inicio de ocupación y cálculo dinámico de duración en minutos y segundos"""
        import datetime
        from django.utils import timezone

        t_inicio = timezone.now() - datetime.timedelta(minutes=25)
        self.mesa_1.ocupar(timestamp=t_inicio)
        self.mesa_1.refresh_from_db()

        self.assertEqual(self.mesa_1.estado, 'OCUPADA')
        self.assertTrue(self.mesa_1.esta_ocupada())
        self.assertFalse(self.mesa_1.esta_disponible())
        self.assertEqual(self.mesa_1.get_inicio_ocupacion(), t_inicio)

        duracion_min = self.mesa_1.get_duracion_ocupacion_minutos()
        self.assertIsNotNone(duracion_min)
        self.assertAlmostEqual(duracion_min, 25.0, places=0)

        duracion_seg = self.mesa_1.get_duracion_ocupacion_segundos()
        self.assertIsNotNone(duracion_seg)
        self.assertGreaterEqual(duracion_seg, 1490)

    def test_rf17_2_doble_ocupacion_rechazada_concurrencia(self):
        """RF17.2: Blindaje contra doble ocupación concurrente (ORM y vista mesero)"""
        from django.core.exceptions import ValidationError
        from django.urls import reverse

        # 1. ORM
        self.mesa_1.ocupar()
        with self.assertRaises(ValidationError):
            self.mesa_1.ocupar()

        # 2. Vista Mesero POST ocupar_mesa sobre mesa ya ocupada
        self.client.force_login(self.mesero_user)
        resp = self.client.post(reverse('mesero'), {
            'accion': 'ocupar_mesa',
            'mesa_id': self.mesa_1.id
        })
        self.assertEqual(resp.status_code, 302)

        # La mesa debe seguir ocupada sin duplicidad
        self.mesa_1.refresh_from_db()
        self.assertEqual(self.mesa_1.estado, 'OCUPADA')

    def test_rf17_3_liberacion_con_cuenta_abierta_rechazada(self):
        """RF17.3: Blindaje estricto: no se permite liberar una mesa que mantiene una cuenta abierta con consumos"""
        from decimal import Decimal
        from django.core.exceptions import ValidationError
        from django.urls import reverse
        from ventas.models import Venta
        from ventas.utils import liberar_mesa_operativa

        # Crear cuenta abierta en mesa_1
        venta_abierta = Venta.objects.create(
            caja=self.caja,
            cajero=self.mesero_user,
            punto_venta=self.pv_central,
            modalidad='MESA',
            mesa=self.mesa_1,
            total=Decimal('15800'),
            estado='ABIERTA'
        )
        self.mesa_1.ocupar()
        self.mesa_1.refresh_from_db()

        # 1. Intento directo vía método liberar() del modelo
        with self.assertRaises(ValidationError):
            self.mesa_1.liberar(forzar=False)

        # 2. Intento vía servicio de negocio
        exito, msg = liberar_mesa_operativa(self.mesa_1, forzar=False)
        self.assertFalse(exito)
        self.assertIn("cuenta abierta", msg.lower())

        # 3. Intento vía POST en módulo mesero
        self.client.force_login(self.mesero_user)
        resp = self.client.post(reverse('mesero'), {
            'accion': 'liberar_mesa',
            'mesa_id': self.mesa_1.id
        })
        self.assertEqual(resp.status_code, 302)

        self.mesa_1.refresh_from_db()
        self.assertEqual(self.mesa_1.estado, 'OCUPADA')
        self.assertTrue(self.mesa_1.esta_ocupada())

    def test_rf17_4_liberacion_exitosa_sin_cuenta_o_forzada(self):
        """RF17.4: Liberación limpia sin cuenta abierta o forzada por supervisión"""
        from django.urls import reverse

        # Mesa ocupada sin cuenta abierta
        self.mesa_1.ocupar()
        self.mesa_1.refresh_from_db()
        self.assertTrue(self.mesa_1.esta_ocupada())

        self.client.force_login(self.mesero_user)
        resp = self.client.post(reverse('mesero'), {
            'accion': 'liberar_mesa',
            'mesa_id': self.mesa_1.id
        })
        self.assertEqual(resp.status_code, 302)

        self.mesa_1.refresh_from_db()
        self.assertEqual(self.mesa_1.estado, 'HABILITADA')
        self.assertIsNone(self.mesa_1.fecha_ocupacion)
        self.assertTrue(self.mesa_1.esta_disponible())
        self.assertIsNone(self.mesa_1.get_duracion_ocupacion_minutos())

    def test_rf17_5_cierre_cuenta_mesa_libera_atomicamente(self):
        """RF17.5: Cierre y pago de cuenta abierta libera atómicamente la mesa y limpia ocupación"""
        from decimal import Decimal
        from django.urls import reverse
        from ventas.models import Venta

        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.mesero_user,
            punto_venta=self.pv_central,
            modalidad='MESA',
            mesa=self.mesa_1,
            total=Decimal('10000'),
            estado='ABIERTA'
        )
        self.mesa_1.ocupar()

        self.client.force_login(self.mesero_user)
        resp = self.client.post(reverse('mesero'), {
            'accion': 'cerrar_cuenta_mesa',
            'mesa_id': self.mesa_1.id,
            'metodo_pago': 'EFECTIVO'
        })
        self.assertEqual(resp.status_code, 302)

        venta.refresh_from_db()
        self.mesa_1.refresh_from_db()

        self.assertEqual(venta.estado, 'PAGADA')
        self.assertEqual(self.mesa_1.estado, 'HABILITADA')
        self.assertIsNone(self.mesa_1.fecha_ocupacion)
        self.assertTrue(self.mesa_1.esta_disponible())

    def test_rf17_6_mesa_inactiva_rechaza_ocupacion_y_comandas(self):
        """RF17.6: Mesa inactiva o en mantenimiento rechaza ocupación directa y emisión de comandas"""
        import json
        from django.core.exceptions import ValidationError
        from django.urls import reverse

        # 1. ORM
        with self.assertRaises(ValidationError):
            self.mesa_inactiva.ocupar()

        # 2. POST ocupar_mesa
        self.client.force_login(self.mesero_user)
        resp_ocupar = self.client.post(reverse('mesero'), {
            'accion': 'ocupar_mesa',
            'mesa_id': self.mesa_inactiva.id
        })
        self.assertEqual(resp_ocupar.status_code, 302)
        self.mesa_inactiva.refresh_from_db()
        self.assertEqual(self.mesa_inactiva.estado, 'INACTIVA')

        # 3. POST enviar_comanda
        items_payload = json.dumps([{
            'id': self.prod_churrasco.id,
            'nombre': self.prod_churrasco.nombre,
            'precio': int(self.prod_churrasco.precio_base),
            'cantidad': 1,
            'nota': ''
        }])
        resp_comanda = self.client.post(reverse('mesero'), {
            'accion': 'enviar_comanda',
            'mesa_id': self.mesa_inactiva.id,
            'items_json': items_payload
        })
        self.assertEqual(resp_comanda.status_code, 302)
        self.mesa_inactiva.refresh_from_db()
        self.assertEqual(self.mesa_inactiva.estado, 'INACTIVA')
        self.assertEqual(self.mesa_inactiva.ventas.count(), 0)

    def test_rf17_7_nueva_ronda_no_reinicia_tiempo_ocupacion(self):
        """RF17.7: Emisión de rondas sucesivas (Ronda 2, 3...) NO reinicia el tiempo de inicio de ocupación"""
        import json
        import datetime
        from django.utils import timezone
        from django.urls import reverse
        from ventas.models import Venta

        t_inicio = timezone.now() - datetime.timedelta(minutes=45)

        # Crear venta abierta inicial simulando apertura hace 45 minutos
        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.mesero_user,
            punto_venta=self.pv_central,
            modalidad='MESA',
            mesa=self.mesa_1,
            total=self.prod_churrasco.precio_base,
            estado='ABIERTA'
        )
        Venta.objects.filter(id=venta.id).update(fecha_hora=t_inicio)
        self.mesa_1.ocupar(timestamp=t_inicio)
        self.mesa_1.refresh_from_db()
        venta.refresh_from_db()

        self.assertEqual(self.mesa_1.get_inicio_ocupacion(), t_inicio)

        # Enviar Ronda 2 vía POST enviar_comanda
        self.client.force_login(self.mesero_user)
        items_ronda2 = json.dumps([{
            'id': self.prod_churrasco.id,
            'nombre': self.prod_churrasco.nombre,
            'precio': int(self.prod_churrasco.precio_base),
            'cantidad': 2,
            'nota': 'Ronda adicional'
        }])
        resp = self.client.post(reverse('mesero'), {
            'accion': 'enviar_comanda',
            'mesa_id': self.mesa_1.id,
            'items_json': items_ronda2
        })
        self.assertEqual(resp.status_code, 302)

        self.mesa_1.refresh_from_db()
        # El timestamp de ocupación DEBE ser el original de hace 45 min
        self.assertEqual(self.mesa_1.fecha_ocupacion, t_inicio)
        self.assertEqual(self.mesa_1.get_inicio_ocupacion(), t_inicio)
        duracion = self.mesa_1.get_duracion_ocupacion_minutos()
        self.assertGreaterEqual(duracion, 44.9)

    def test_rf17_8_reasignacion_mesa_transfiere_tiempo_y_libera_origen(self):
        """RF17.8: Reasignación de mesa traslada el timestamp de ocupación y libera la mesa origen"""
        import datetime
        from django.utils import timezone
        from django.urls import reverse
        from ventas.models import Venta

        t_inicio = timezone.now() - datetime.timedelta(minutes=30)
        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.mesero_user,
            punto_venta=self.pv_central,
            modalidad='MESA',
            mesa=self.mesa_1,
            total=self.prod_churrasco.precio_base,
            estado='ABIERTA'
        )
        Venta.objects.filter(id=venta.id).update(fecha_hora=t_inicio)
        self.mesa_1.ocupar(timestamp=t_inicio)
        self.mesa_1.refresh_from_db()

        # Reasignar de mesa_1 a mesa_2
        self.client.force_login(self.mesero_user)
        resp = self.client.post(reverse('mesero'), {
            'accion': 'reasignar_mesa',
            'mesa_origen_id': self.mesa_1.id,
            'mesa_destino_id': self.mesa_2.id,
            'motivo': 'Comensales prefieren sombra'
        })
        self.assertEqual(resp.status_code, 302)

        self.mesa_1.refresh_from_db()
        self.mesa_2.refresh_from_db()

        # Mesa origen libre
        self.assertEqual(self.mesa_1.estado, 'HABILITADA')
        self.assertIsNone(self.mesa_1.fecha_ocupacion)
        self.assertTrue(self.mesa_1.esta_disponible())

        # Mesa destino ocupada con el tiempo preservado
        self.assertEqual(self.mesa_2.estado, 'OCUPADA')
        self.assertEqual(self.mesa_2.fecha_ocupacion, t_inicio)
        duracion_destino = self.mesa_2.get_duracion_ocupacion_minutos()
        self.assertGreaterEqual(duracion_destino, 29.9)

    def test_rf17_9_estado_reconstruible_100_por_ciento_desde_bd(self):
        """RF17.9: Reconstrucción total del estado y resumen de ocupación tras reinicio o recarga"""
        import datetime
        from django.utils import timezone
        from ventas.models import Mesa, Venta

        t_inicio = timezone.now() - datetime.timedelta(minutes=18)
        self.mesa_1.ocupar(timestamp=t_inicio)

        venta = Venta.objects.create(
            caja=self.caja,
            cajero=self.mesero_user,
            punto_venta=self.pv_central,
            modalidad='MESA',
            mesa=self.mesa_1,
            total=Decimal('15000'),
            estado='ABIERTA'
        )

        # Simular nueva instancia obtenida de la BD (como tras reinicio de navegador)
        mesa_recargada = Mesa.objects.get(id=self.mesa_1.id)
        resumen = mesa_recargada.get_resumen_ocupacion()

        self.assertEqual(resumen['identificador'], "M1-RF17")
        self.assertEqual(resumen['estado'], "OCUPADA")
        self.assertTrue(resumen['esta_ocupada'])
        self.assertFalse(resumen['esta_disponible'])
        self.assertTrue(resumen['tiene_cuenta_abierta'])
        self.assertEqual(resumen['venta_abierta_id'], venta.id)
        self.assertEqual(resumen['total_cuenta_abierta'], 15000)
        self.assertAlmostEqual(resumen['duracion_ocupacion_minutos'], 18.0, places=0)
        self.assertIsNotNone(resumen['inicio_ocupacion_chile'])

    def test_rf17_10_servicio_metricas_ocupacion_local(self):
        """RF17.10: calcular_metricas_ocupacion_local calcula tasas y promedios reales de ocupación"""
        import datetime
        from django.utils import timezone
        from ventas.utils import calcular_metricas_ocupacion_local

        # mesa_1 ocupada hace 20 min
        self.mesa_1.ocupar(timestamp=timezone.now() - datetime.timedelta(minutes=20))
        # mesa_2 libre
        self.mesa_2.estado = 'HABILITADA'
        self.mesa_2.fecha_ocupacion = None
        self.mesa_2.save()
        # mesa_inactiva INACTIVA

        metricas = calcular_metricas_ocupacion_local(punto_venta=self.pv_central)

        self.assertEqual(metricas['total_mesas'], 3)
        self.assertEqual(metricas['mesas_libres'], 1)
        self.assertEqual(metricas['mesas_ocupadas'], 1)
        self.assertEqual(metricas['mesas_inactivas'], 1)
        self.assertAlmostEqual(metricas['tasa_ocupacion_porcentaje'], 33.3, places=1)
        self.assertAlmostEqual(metricas['promedio_duracion_ocupacion_minutos'], 20.0, places=0)



class SafariRF18ReportesEstadisticasTests(TestCase):
    """
    Pruebas unitarias y de integración de alta fidelidad para RF18 (Reportes y Estadísticas):
    - RF18.1: Cero mocks: erradicación de datos inventados ($49.5M, 84 fake tickets, etc.), 100% ORM real.
    - RF18.2: Filtros dinámicos por rango de fechas (inicio/fin) con sanitización de rangos invertidos.
    - RF18.3: Filtro por Punto de Venta / Local gastronómico y aislamiento estricto de métricas.
    - RF18.4: Filtro por Colaborador / Usuario cajero.
    - RF18.5: Exclusión estricta de ventas anuladas en la recaudación financiera y auditoría de anulación.
    - RF18.6: Desglose financiero por método de pago y modalidad de atención (Mesa, Venta Rápida, Mostrador).
    - RF18.7: Contabilidad de precios especiales, convenios y cálculo de ahorro para comensales.
    - RF18.8: Ranking Top 10 de productos más vendidos con inclusión de productos históricos desactivados.
    - RF18.9: Integración de métricas de tiempos de atención (espera, cola y preparación en cocina) con RF16.
    - RF18.10: Integración de métricas de ocupación y rotación de mesas con RF17.
    - RF18.11: Exportación oficial de reportes (Excel y Word) con datos 100% reales sin simulación mock.
    - RF18.12: Acceso y renderizado completo del Dashboard de Administrador (HTTP 200).
    - RF18.13: Control de acceso y blindaje RBAC: rechazo a roles no autorizados (Mesero, Cajero).
    """

    def setUp(self):
        import datetime
        from decimal import Decimal
        from django.contrib.auth.models import User
        from django.utils import timezone
        from ventas.models import (
            PuntoVenta, PerfilEmpleado, Mesa, Producto, Categoria,
            Venta, DetalleVenta, Pedido, Entrega, Jornada, Caja
        )

        self.pv_central = PuntoVenta.objects.create(nombre="Restaurante Central T18", activo=True)
        self.pv_selva = PuntoVenta.objects.create(nombre="Cafeteria La Selva T18", activo=True)

        self.admin_user = User.objects.create_superuser('admin_rf18', 'admin18@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.admin_user, rol='ADMINISTRADOR', punto_venta_actual=self.pv_central)

        self.cajero_1 = User.objects.create_user('cajero1_rf18', 'c1_18@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.cajero_1, rol='CAJERO', punto_venta_actual=self.pv_central)

        self.cajero_2 = User.objects.create_user('cajero2_rf18', 'c2_18@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.cajero_2, rol='CAJERO', punto_venta_actual=self.pv_selva)

        self.mesero_user = User.objects.create_user('mesero_rf18', 'm18@safari.cl', 'safari123')
        PerfilEmpleado.objects.create(usuario=self.mesero_user, rol='MESERO', punto_venta_actual=self.pv_central)

        self.mesa_1 = Mesa.objects.create(identificador="M1-RF18", capacidad=4, punto_venta=self.pv_central, estado='HABILITADA')
        self.mesa_2 = Mesa.objects.create(identificador="M2-RF18", capacidad=4, punto_venta=self.pv_central, estado='HABILITADA')

        self.cat_platos = Categoria.objects.create(nombre="Platos T18")
        self.cat_bebidas = Categoria.objects.create(nombre="Bebidas T18")

        self.prod_activo = Producto.objects.create(
            nombre="Lomo Saltado Safari",
            categoria=self.cat_platos,
            precio_base=Decimal('8500'),
            activo=True
        )
        self.prod_activo.puntos_venta.add(self.pv_central)

        self.prod_desactivado = Producto.objects.create(
            nombre="Jugo Natural Mango Antiguo",
            categoria=self.cat_bebidas,
            precio_base=Decimal('3000'),
            activo=False
        )
        self.prod_desactivado.puntos_venta.add(self.pv_central)

        hoy = timezone.localdate()
        self.jornada, _ = Jornada.objects.get_or_create(
            fecha=hoy,
            defaults={'usuario_apertura': self.admin_user, 'estado': 'ABIERTA'}
        )
        self.caja_1, _ = Caja.objects.get_or_create(
            jornada=self.jornada,
            cajero=self.cajero_1,
            punto_venta=self.pv_central,
            defaults={'monto_apertura': Decimal('50000.00'), 'estado': 'ABIERTA'}
        )
        self.caja_2, _ = Caja.objects.get_or_create(
            jornada=self.jornada,
            cajero=self.cajero_2,
            punto_venta=self.pv_selva,
            defaults={'monto_apertura': Decimal('50000.00'), 'estado': 'ABIERTA'}
        )

    def test_rf18_1_cero_mocks_datos_100_reales(self):
        """RF18.1: Base de datos limpia retorna 0 en recaudación y tickets, erradicando mocks de $49.5M y 84 tickets"""
        from ventas.utils import generar_reporte_estadistico_integral
        from ventas.exportador_reportes import obtener_datos_reporte

        reporte = generar_reporte_estadistico_integral()
        self.assertEqual(reporte['ventas']['total_recaudado'], 0)
        self.assertEqual(reporte['ventas']['cantidad_ventas'], 0)
        self.assertEqual(reporte['ventas']['ticket_promedio'], 0.0)
        self.assertEqual(len(reporte['ranking_productos']), 0)
        self.assertEqual(reporte['tiempos_atencion']['total_entregados'], 0)

        datos_rep = obtener_datos_reporte(tipo_rango='dia')
        self.assertEqual(datos_rep['total_ventas'], 0)
        self.assertEqual(datos_rep['total_tickets'], 0)
        self.assertEqual(len(datos_rep['filas_detalle']), 0)
        self.assertNotEqual(datos_rep['total_tickets'], 84)

    def test_rf18_2_filtro_rango_fechas_y_sanitizacion_invertida(self):
        """RF18.2: Filtro por rango de fechas aísla ventas y auto-corrige fechas invertidas sin error"""
        import datetime
        from decimal import Decimal
        from django.utils import timezone
        from ventas.models import Venta
        from ventas.utils import generar_reporte_estadistico_integral

        hoy = timezone.localdate()
        dia_ayer = hoy - datetime.timedelta(days=1)
        dia_antier = hoy - datetime.timedelta(days=2)
        dia_viejo = hoy - datetime.timedelta(days=10)

        t_ayer = timezone.now() - datetime.timedelta(days=1)
        t_antier = timezone.now() - datetime.timedelta(days=2)
        t_viejo = timezone.now() - datetime.timedelta(days=10)

        v1 = Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('10000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA'
        )
        Venta.objects.filter(id=v1.id).update(fecha_hora=t_viejo)

        v2 = Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('25000'), estado='PAGADA', metodo_pago='TARJETA_DEBITO', modalidad='VENTA_RAPIDA'
        )
        Venta.objects.filter(id=v2.id).update(fecha_hora=t_antier)

        v3 = Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('40000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA'
        )
        Venta.objects.filter(id=v3.id).update(fecha_hora=t_ayer)

        # Filtro entre antier y ayer
        rep = generar_reporte_estadistico_integral(fecha_inicio=dia_antier, fecha_fin=dia_ayer)
        self.assertEqual(rep['ventas']['cantidad_ventas'], 2)
        self.assertEqual(rep['ventas']['total_recaudado'], 65000)

        # Rango invertido: fecha_inicio ayer, fecha_fin antier -> Debe auto-corregir sin error
        rep_inv = generar_reporte_estadistico_integral(fecha_inicio=dia_ayer, fecha_fin=dia_antier)
        self.assertEqual(rep_inv['ventas']['cantidad_ventas'], 2)
        self.assertEqual(rep_inv['ventas']['total_recaudado'], 65000)

    def test_rf18_3_filtro_por_punto_de_venta(self):
        """RF18.3: Filtro por Punto de Venta aísla exclusivamente las transacciones de dicho local"""
        from decimal import Decimal
        from ventas.models import Venta
        from ventas.utils import generar_reporte_estadistico_integral

        Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('35000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA'
        )
        Venta.objects.create(
            caja=self.caja_2, punto_venta=self.pv_selva, cajero=self.cajero_2,
            total=Decimal('15000'), estado='PAGADA', metodo_pago='TARJETA_DEBITO', modalidad='VENTA_RAPIDA'
        )

        rep_central = generar_reporte_estadistico_integral(punto_venta=self.pv_central.id)
        self.assertEqual(rep_central['ventas']['cantidad_ventas'], 1)
        self.assertEqual(rep_central['ventas']['total_recaudado'], 35000)

        rep_selva = generar_reporte_estadistico_integral(punto_venta=self.pv_selva.id)
        self.assertEqual(rep_selva['ventas']['cantidad_ventas'], 1)
        self.assertEqual(rep_selva['ventas']['total_recaudado'], 15000)

        # Consolidado general
        rep_todos = generar_reporte_estadistico_integral()
        self.assertEqual(rep_todos['ventas']['cantidad_ventas'], 2)
        self.assertEqual(rep_todos['ventas']['total_recaudado'], 50000)

    def test_rf18_4_filtro_por_usuario_colaborador(self):
        """RF18.4: Filtro por colaborador aísla las ventas recaudadas por dicho cajero"""
        from decimal import Decimal
        from ventas.models import Venta
        from ventas.utils import generar_reporte_estadistico_integral

        Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('18000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA'
        )
        Venta.objects.create(
            caja=self.caja_2, punto_venta=self.pv_selva, cajero=self.cajero_2,
            total=Decimal('22000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA'
        )

        rep_u1 = generar_reporte_estadistico_integral(usuario=self.cajero_1.id)
        self.assertEqual(rep_u1['ventas']['cantidad_ventas'], 1)
        self.assertEqual(rep_u1['ventas']['total_recaudado'], 18000)

        rep_u2 = generar_reporte_estadistico_integral(usuario=self.cajero_2.id)
        self.assertEqual(rep_u2['ventas']['cantidad_ventas'], 1)
        self.assertEqual(rep_u2['ventas']['total_recaudado'], 22000)

    def test_rf18_5_ventas_excluye_estrictamente_anuladas(self):
        """RF18.5: Exclusión estricta de ventas anuladas de los totales recaudados"""
        from decimal import Decimal
        from ventas.models import Venta
        from ventas.utils import generar_reporte_estadistico_integral

        Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('60000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA'
        )
        Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('40000'), estado='ANULADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA'
        )

        rep = generar_reporte_estadistico_integral()
        self.assertEqual(rep['ventas']['total_recaudado'], 60000)
        self.assertEqual(rep['ventas']['cantidad_ventas'], 1)
        self.assertEqual(rep['ventas']['cantidad_anuladas'], 1)

    def test_rf18_6_desglose_medios_pago_y_modalidad(self):
        """RF18.6: Desglose exacto por método de pago y modalidad de servicio (Mesa vs Venta Rápida)"""
        from decimal import Decimal
        from ventas.models import Venta
        from ventas.utils import generar_reporte_estadistico_integral

        # Venta 1: Efectivo, Mesa ($30.000)
        Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('30000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='MESA', mesa=self.mesa_1
        )
        # Venta 2: Débito, Venta Rápida ($70.000)
        Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('70000'), estado='PAGADA', metodo_pago='TARJETA_DEBITO', modalidad='VENTA_RAPIDA'
        )

        rep = generar_reporte_estadistico_integral()
        self.assertEqual(rep['ventas']['total_recaudado'], 100000)

        # Métodos de pago
        metodos = {m['metodo_pago']: m for m in rep['ventas']['ventas_por_metodo']}
        self.assertEqual(metodos['TARJETA_DEBITO']['total'], 70000)
        self.assertEqual(metodos['TARJETA_DEBITO']['porcentaje'], 70.0)
        self.assertEqual(metodos['EFECTIVO']['total'], 30000)
        self.assertEqual(metodos['EFECTIVO']['porcentaje'], 30.0)

        # Modalidades
        modalidades = {m['modalidad']: m for m in rep['ventas']['ventas_por_modalidad']}
        self.assertEqual(modalidades['VENTA_RAPIDA']['total'], 70000)
        self.assertEqual(modalidades['VENTA_RAPIDA']['porcentaje'], 70.0)
        self.assertEqual(modalidades['MESA']['total'], 30000)
        self.assertEqual(modalidades['MESA']['porcentaje'], 30.0)

    def test_rf18_7_precios_especiales_convenios_ahorro(self):
        """RF18.7: Auditoría de ítems con precio especial o convenio y cálculo de ahorro comensal"""
        from decimal import Decimal
        from ventas.models import Venta, DetalleVenta
        from ventas.utils import generar_reporte_estadistico_integral

        v = Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('14000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA'
        )
        # 2 unidades a $7.000 cada una (precio original $10.000). Ahorro = (10000 - 7000) * 2 = 6000
        DetalleVenta.objects.create(
            venta=v,
            producto=self.prod_activo,
            cantidad=2,
            precio_aplicado=Decimal('7000'),
            subtotal=Decimal('14000'),
            es_precio_especial=True,
            precio_original=Decimal('10000'),
            motivo_precio_especial='CONVENIO'
        )

        rep = generar_reporte_estadistico_integral()
        self.assertEqual(rep['ventas']['total_items_precio_especial'], 1)
        self.assertEqual(rep['ventas']['ahorro_descuentos'], 6000)

    def test_rf18_8_ranking_productos_incluye_historicos_desactivados(self):
        """RF18.8: Ranking Top 10 agrega unidades y montos, conservando productos históricos ya desactivados"""
        from decimal import Decimal
        from ventas.models import Venta, DetalleVenta
        from ventas.utils import generar_reporte_estadistico_integral

        v1 = Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('42500'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA'
        )
        # 5 unidades de producto activo
        DetalleVenta.objects.create(
            venta=v1, producto=self.prod_activo, cantidad=5,
            precio_aplicado=Decimal('8500'), subtotal=Decimal('42500')
        )

        v2 = Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('60000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA'
        )
        # 20 unidades del producto histórico desactivado
        DetalleVenta.objects.create(
            venta=v2, producto=self.prod_desactivado, cantidad=20,
            precio_aplicado=Decimal('3000'), subtotal=Decimal('60000')
        )

        rep = generar_reporte_estadistico_integral()
        ranking = rep['ranking_productos']
        self.assertEqual(len(ranking), 2)

        # Primero: el producto desactivado por tener mayor volumen (20 unidades)
        self.assertEqual(ranking[0]['nombre'], self.prod_desactivado.nombre)
        self.assertEqual(ranking[0]['total_unidades'], 20)
        self.assertEqual(ranking[0]['total_recaudado'], 60000)
        self.assertFalse(ranking[0]['activo'])

        # Segundo: el producto activo (5 unidades)
        self.assertEqual(ranking[1]['nombre'], self.prod_activo.nombre)
        self.assertEqual(ranking[1]['total_unidades'], 5)
        self.assertEqual(ranking[1]['total_recaudado'], 42500)
        self.assertTrue(ranking[1]['activo'])

    def test_rf18_9_metricas_tiempos_atencion_en_reporte(self):
        """RF18.9: Integración de métricas de tiempos (RF16) en el reporte analítico"""
        import datetime
        from decimal import Decimal
        from django.utils import timezone
        from ventas.models import Venta, Pedido, Entrega
        from ventas.utils import generar_reporte_estadistico_integral

        now = timezone.now()
        base = now - datetime.timedelta(minutes=20)

        v = Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('10000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA'
        )
        p = Pedido.objects.create(venta=v, estado='LISTO')
        Pedido.objects.filter(id=p.id).update(
            creado_en=base,
            fecha_inicio_preparacion=base + datetime.timedelta(minutes=5),
            fecha_listo=base + datetime.timedelta(minutes=15),
            estado='ENTREGADO'
        )
        p.refresh_from_db()
        e = Entrega.objects.create(pedido=p, usuario_entrega=self.mesero_user)
        Entrega.objects.filter(id=e.id).update(fecha_hora_entrega=base + datetime.timedelta(minutes=20))
        e.refresh_from_db()

        rep = generar_reporte_estadistico_integral()
        tiempos = rep['tiempos_atencion']
        self.assertEqual(tiempos['total_entregados'], 1)
        self.assertAlmostEqual(tiempos['promedio_tiempo_espera_total_minutos'], 20.0, places=0)
        self.assertAlmostEqual(tiempos['promedio_tiempo_cola_minutos'], 5.0, places=0)
        self.assertAlmostEqual(tiempos['promedio_tiempo_preparacion_minutos'], 10.0, places=0)
        self.assertAlmostEqual(tiempos['promedio_tiempo_despacho_minutos'], 5.0, places=0)

    def test_rf18_10_metricas_ocupacion_mesas_en_reporte(self):
        """RF18.10: Integración de métricas de ocupación de mesas (RF17) en el reporte analítico"""
        import datetime
        from django.utils import timezone
        from ventas.utils import generar_reporte_estadistico_integral

        # Ocupamos mesa_1 hace 30 minutos
        self.mesa_1.ocupar(timestamp=timezone.now() - datetime.timedelta(minutes=30))

        rep = generar_reporte_estadistico_integral(punto_venta=self.pv_central.id)
        ocup = rep['ocupacion_mesas']
        self.assertEqual(ocup['total_mesas'], 2)
        self.assertEqual(ocup['mesas_ocupadas'], 1)
        self.assertEqual(ocup['mesas_libres'], 1)
        self.assertAlmostEqual(ocup['tasa_ocupacion_porcentaje'], 50.0, places=1)
        self.assertAlmostEqual(ocup['promedio_duracion_ocupacion_minutos'], 30.0, places=0)

    def test_rf18_11_exportacion_reporte_sin_mocks(self):
        """RF18.11: Exportación en Excel y Word con datos 100% reales sin simulación mock"""
        from decimal import Decimal
        from ventas.models import Venta
        from ventas.exportador_reportes import obtener_datos_reporte, generar_excel_ventas, generar_word_ventas

        Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('50000'), estado='PAGADA', metodo_pago='TARJETA_DEBITO', modalidad='VENTA_RAPIDA'
        )

        datos = obtener_datos_reporte(tipo_rango='15_meses')
        self.assertEqual(datos['total_ventas'], 50000)
        self.assertEqual(datos['total_tickets'], 1)
        self.assertNotEqual(datos['total_tickets'], 84)

        # Generación de Excel
        excel_io = generar_excel_ventas(datos)
        self.assertGreater(excel_io.getbuffer().nbytes, 1000)

        # Generación de Word
        word_io = generar_word_ventas(datos)
        self.assertGreater(word_io.getbuffer().nbytes, 1000)

    def test_rf18_12_dashboard_admin_acceso_y_render_completo(self):
        """RF18.12: Acceso exitoso al Dashboard de Administrador (HTTP 200) y render de métricas reales"""
        from decimal import Decimal
        from django.urls import reverse
        from ventas.models import Venta

        Venta.objects.create(
            caja=self.caja_1, punto_venta=self.pv_central, cajero=self.cajero_1,
            total=Decimal('90000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA'
        )

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('administrador_dashboard'))
        self.assertEqual(response.status_code, 200)

        # Contexto del dashboard
        self.assertIn('reporte', response.context)
        self.assertIn('ranking_productos', response.context)
        self.assertIn('tiempos', response.context)
        self.assertIn('ocupacion', response.context)
        self.assertIn('chart_data_json', response.context)

        # Contenido HTML renderizado
        content = response.content.decode('utf-8')
        self.assertIn('Ranking de Productos Más Vendidos', content)
        self.assertIn('Tiempo Espera Total', content)
        self.assertIn('Ocupación Mesas', content)
        self.assertIn('formExportarVentas', content)

    def test_rf18_13_dashboard_bloqueo_roles_no_autorizados(self):
        """RF18.13: Blindaje RBAC: Meseros y Cajeros no pueden acceder al Dashboard de Administrador"""
        from django.urls import reverse

        # Mesero no autorizado
        self.client.force_login(self.mesero_user)
        response_mesero = self.client.get(reverse('administrador_dashboard'))
        self.assertIn(response_mesero.status_code, [302, 403])

        # Cajero no autorizado
        self.client.force_login(self.cajero_1)
        response_cajero = self.client.get(reverse('administrador_dashboard'))
        self.assertIn(response_cajero.status_code, [302, 403])


class SafariSincronizacionTiempoRealCajaMeseroKdsTests(TestCase):
    """
    Pruebas integrales de regresión operativa:
    1. Campos numéricos de Caja sin value="0" prellenado (ingreso directo sin 0 inicial).
    2. Diseño responsivo sin recortes en KDS Cocina y Barra (flex-direction: column y grilla amplia).
    3. Sincronización 100% SQLite entre Cajero, Salón (Mesero), Cocina y Barra.
    """

    def setUp(self):
        cache.clear()
        self.client = Client()
        call_command('poblar_safari')
        PerfilEmpleado.objects.all().update(debe_cambiar_clave=False)
        self.cajero = User.objects.get(username='cvalenzuela')
        self.mesero = User.objects.get(username='dsilva')
        self.cocinero = User.objects.get(username='eparedes')
        self.local = self.cajero.perfil.punto_venta_actual

    def tearDown(self):
        cache.clear()

    def test_inputs_numericos_caja_sin_cero_inicial(self):
        self.client.force_login(self.cajero)
        resp_inicial = self.client.get(reverse('vendedor'))
        self.assertEqual(resp_inicial.status_code, 200)
        html_inicial = resp_inicial.content.decode('utf-8')
        self.assertNotIn('value="0"', html_inicial)

        # Apertura con campo vacío debe asumir $0 limpio; y luego al tener caja activa tampoco hay value="0" en arqueo
        self.client.post(reverse('abrir_jornada'), {'monto_apertura': ''}, follow=True)
        resp_activa = self.client.get(reverse('vendedor'))
        html_activa = resp_activa.content.decode('utf-8')
        self.assertNotIn('value="0"', html_activa)
        caja = Caja.objects.filter(cajero=self.cajero, estado='ABIERTA').first()
        self.assertIsNotNone(caja)
        self.assertEqual(int(caja.monto_apertura), 0)

    def test_diseno_kds_cocina_y_barra_sin_recorte_flexbox(self):
        self.client.force_login(self.cocinero)
        resp_cocina = self.client.get(reverse('cocina'))
        self.assertEqual(resp_cocina.status_code, 200)
        html_cocina = resp_cocina.content.decode('utf-8')
        self.assertIn('css/kds/cocina.css', html_cocina)
        cocina_css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'kds', 'cocina.css')
        with open(cocina_css_path, 'r', encoding='utf-8') as f:
            cocina_css = f.read()
        self.assertNotIn('flex-column: column', cocina_css)
        self.assertIn('flex-direction: column', cocina_css)

        resp_barra = self.client.get(reverse('barra'))
        self.assertEqual(resp_barra.status_code, 200)
        html_barra = resp_barra.content.decode('utf-8')
        self.assertIn('js/kds/barra.js', html_barra)
        barra_js_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'kds', 'barra.js')
        with open(barra_js_path, 'r', encoding='utf-8') as f:
            self.assertIn('autoActualizarBarra', f.read())

    def test_conexion_integral_cajero_mesa_mesero_cocina_y_barra(self):
        self.client.force_login(self.cajero)
        self.client.post(reverse('abrir_jornada'), {'monto_apertura': '20000'}, follow=True)

        mesa = Mesa.objects.filter(punto_venta=self.local, estado='HABILITADA').first()
        self.assertIsNotNone(mesa)

        # 1. Cajero envía clientes a la mesa desde su panel -> se ocupa en BD y se refleja en Mesero
        resp_ocupar = self.client.post(
            reverse('vendedor'),
            {'accion': 'ocupar_mesa', 'mesa_id': str(mesa.id)},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(resp_ocupar.status_code, 200)
        self.assertTrue(resp_ocupar.json()['ok'])
        mesa.refresh_from_db()
        self.assertEqual(mesa.estado, 'OCUPADA')

        # 2. Cajero emite pedido mixto (Cocina + Barra) asignado a esa mesa desde crear_ticket
        prod_cocina = [p for p in self.local.get_productos_disponibles() if p.get_destino_operativo() == 'COCINA'][0]
        prod_barra = [p for p in self.local.get_productos_disponibles() if p.get_destino_operativo() == 'BARRA'][0]

        items_payload = [
            {'producto_id': prod_cocina.id, 'nombre': prod_cocina.nombre, 'cantidad': 1, 'nota': 'Sin sal'},
            {'producto_id': prod_barra.id, 'nombre': prod_barra.nombre, 'cantidad': 2, 'nota': 'Bien frio'},
        ]
        resp_pos = self.client.post(
            reverse('crear_ticket'),
            {
                'items_json': json.dumps(items_payload),
                'metodo_pago': 'DEBITO',
                'modalidad': 'MESA',
                'mesa_id': str(mesa.id),
                'modo_cuenta': 'PAGADA',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(resp_pos.status_code, 200)
        data_pos = resp_pos.json()
        self.assertTrue(data_pos['ok'])
        pedido_id = data_pos['pedido_id']

        # 3. Verificar reflejo inmediato en Monitor de Cajero (SQLite real)
        resp_vend = self.client.get(reverse('vendedor'))
        pedidos_cajero = json.loads(resp_vend.context['pedidos_cajero_json'])
        self.assertTrue(any(p['pedido_id'] == pedido_id for p in pedidos_cajero))

        # 4. Verificar reflejo inmediato en Salón del Mesero
        self.client.force_login(self.mesero)
        resp_mesero = self.client.get(reverse('mesero'))
        self.assertGreaterEqual(resp_mesero.context['mesas_ocupadas'], 1)
        pedidos_mesa = json.loads(resp_mesero.context['pedidos_mesa_activos_json'])
        self.assertIn(str(mesa.id), pedidos_mesa)
        self.assertTrue(any(p['pedido_id'] == pedido_id for p in pedidos_mesa[str(mesa.id)]))

        # 5. Verificar llegada inmediata de tickets a KDS Cocina y KDS Barra
        self.client.force_login(self.cocinero)
        resp_kds_cocina = self.client.get(reverse('cocina') + '?zona=COCINA')
        self.assertContains(resp_kds_cocina, f"COM-{pedido_id:04d}")
        self.assertContains(resp_kds_cocina, prod_cocina.nombre)

        resp_kds_barra = self.client.get(reverse('barra'))
        self.assertContains(resp_kds_barra, f"#BAR-{pedido_id:04d}")
        self.assertContains(resp_kds_barra, prod_barra.nombre)

    def test_cajero_cobra_cuenta_abierta_de_salon_y_libera_mesa(self):
        # Mesero abre cuenta en salón
        self.client.force_login(self.mesero)
        mesa = Mesa.objects.filter(punto_venta=self.local, estado='HABILITADA').first()
        prod_cocina = [p for p in self.local.get_productos_disponibles() if p.get_destino_operativo() == 'COCINA'][0]
        self.client.post(reverse('mesero'), {
            'accion': 'enviar_comanda',
            'mesa_id': str(mesa.id),
            'items_json': json.dumps([{
                'id': prod_cocina.id,
                'nombre': prod_cocina.nombre,
                'cantidad': 1,
                'precio': int(prod_cocina.precio_actual),
                'destino': 'COCINA',
                'nota': ''
            }])
        }, follow=True)
        mesa.refresh_from_db()
        self.assertEqual(mesa.estado, 'OCUPADA')

        # Cajero habilita su caja individual en la jornada activa y cobra la cuenta abierta del salón desde su panel
        self.client.force_login(self.cajero)
        self.client.post(reverse('abrir_caja'), {'monto_apertura': '10000'}, follow=True)
        resp_cobro = self.client.post(
            reverse('vendedor'),
            {'accion': 'cobrar_cuenta_mesa', 'mesa_id': str(mesa.id), 'metodo_pago': 'EFECTIVO'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(resp_cobro.status_code, 200)
        self.assertTrue(resp_cobro.json()['ok'])
        mesa.refresh_from_db()
        self.assertEqual(mesa.estado, 'HABILITADA')
        self.assertFalse(Venta.objects.filter(mesa=mesa, estado='ABIERTA').exists())

    def test_migracion_estaticos_css_js_img_por_zonas(self):
        import os
        import pathlib
        import re
        from django.conf import settings

        base = pathlib.Path(settings.BASE_DIR)
        static_root = base / 'static'
        zonas_estaticos = [
            'global',
            'acceso',
            'administrador',
            'cajero',
            'mesero',
            'kds',
            'impresion',
            'errores/400',
            'errores/500',
        ]
        for tipo in ('css', 'js', 'img'):
            for zona in zonas_estaticos:
                ruta_zona = static_root / tipo / zona
                self.assertTrue(ruta_zona.is_dir(), f"Debe existir la carpeta de zona static/{tipo}/{zona}")

        # Plantillas de errores HTTP organizadas en templates/errores/{400,500}/ sin .html sueltos
        for sub_err in ('400', '500'):
            self.assertTrue((base / 'templates' / 'errores' / sub_err).is_dir())
        self.assertEqual(
            list((base / 'templates').glob('*.html')),
            [],
            "No deben existir plantillas .html sueltas en la raíz de templates/",
        )

        # Plantillas de la app organizadas en ventas/templates/ventas/<zona>/ sin .html sueltos
        zonas_templates_ventas = ['acceso', 'administrador', 'cajero', 'mesero', 'kds', 'impresion']
        for zona_tpl in zonas_templates_ventas:
            self.assertTrue(
                (base / 'ventas' / 'templates' / 'ventas' / zona_tpl).is_dir(),
                f"Debe existir ventas/templates/ventas/{zona_tpl}",
            )
        self.assertEqual(
            list((base / 'ventas' / 'templates' / 'ventas').glob('*.html')),
            [],
            "No deben existir plantillas .html sueltas en ventas/templates/ventas/",
        )

        # Raíz del repositorio limpia y reglas permanentes activas para futuras interacciones
        for ext_prohibida in ('*.html', '*.docx', '*.xlsx', '*.png'):
            self.assertEqual(
                list(base.glob(ext_prohibida)),
                [],
                f"No deben quedar archivos {ext_prohibida} sueltos en la raíz del proyecto",
            )
        self.assertTrue((base / 'AGENTS.md').is_file(), "Debe existir AGENTS.md en la raíz del proyecto")
        self.assertTrue(
            (base / '.agents' / 'rules' / 'orden_arquitectura_safari.md').is_file(),
            "Debe existir la regla de workspace .agents/rules/orden_arquitectura_safari.md",
        )

        html_files = (
            list((base / 'templates').rglob('*.html'))
            + list((base / 'ventas' / 'templates' / 'ventas').rglob('*.html'))
        )
        self.assertGreaterEqual(len(html_files), 30, "Deben auditarse las 30 plantillas del sistema")

        for hf in html_files:
            txt = hf.read_text(encoding='utf-8')
            styles = re.findall(r'<style\b[^>]*>(.*?)</style>', txt, re.S | re.I)
            self.assertEqual(len(styles), 0, f"{hf.name} no debe contener bloques <style> incrustados")

            scripts = re.findall(r'<script\b([^>]*)>(.*?)</script>', txt, re.S | re.I)
            inline_js = [
                body for attrs, body in scripts
                if 'src=' not in attrs.lower()
                and 'application/json' not in attrs.lower()
                and body.strip()
            ]
            self.assertEqual(len(inline_js), 0, f"{hf.name} no debe contener bloques <script> JS ejecutables incrustados")

            refs = re.findall(r"""\{%\s*static\s+['"]([^'"]+)['"]\s*%\}""", txt)
            for ref in refs:
                self.assertTrue(
                    os.path.exists(static_root / ref),
                    f"El recurso estático '{ref}' referenciado en {hf.name} debe existir en static/"
                )

        # Acceso QR servido limpiamente por Django y manejo 404 operativo
        resp_qr = self.client.get(reverse('qr_acceso'))
        self.assertEqual(resp_qr.status_code, 200)
        resp_404 = self.client.get('/ruta-inexistente-auditoria-orden/')
        self.assertEqual(resp_404.status_code, 404)



    def test_proteccion_apagon_dia_anterior_limpia_jornada_caja_mesa_y_pedidos_y_traspasa_fondo(self):
        import datetime as dt_mod
        from decimal import Decimal
        from ventas.models import Jornada, Caja, Venta, Pedido, DetallePedido, Mesa, Producto

        local = PuntoVenta.objects.get(id=1)
        mesa = Mesa.objects.filter(punto_venta=local, estado='HABILITADA').first()
        prod = Producto.objects.filter(activo=True).first()

        ayer_dt = timezone.now() - dt_mod.timedelta(days=1, hours=2)
        ayer_fecha = timezone.localtime(ayer_dt).date()

        jornada_ayer = Jornada.objects.create(usuario_apertura=self.cajero, estado='ABIERTA')
        Jornada.objects.filter(pk=jornada_ayer.pk).update(fecha=ayer_fecha, fecha_hora_apertura=ayer_dt)

        caja_ayer = Caja.objects.create(
            jornada=jornada_ayer,
            cajero=self.cajero,
            punto_venta=local,
            nombre="Caja Ayer Apagón",
            monto_apertura=Decimal('10000'),
            estado='ABIERTA',
        )
        Caja.objects.filter(pk=caja_ayer.pk).update(fecha_hora_apertura=ayer_dt)

        # Venta pagada ayer en efectivo ($15.000) con pedido que quedó en preparación por corte de luz
        venta_pagada = Venta.objects.create(
            caja=caja_ayer,
            cajero=self.cajero,
            punto_venta=local,
            modalidad='VENTA_RAPIDA',
            metodo_pago='EFECTIVO',
            total=Decimal('15000'),
            estado='PAGADA',
        )
        Venta.objects.filter(pk=venta_pagada.pk).update(fecha_hora=ayer_dt)
        ped_pagado = Pedido.objects.create(venta=venta_pagada, estado='EN_PREPARACION', fecha_inicio_preparacion=ayer_dt)
        DetallePedido.objects.create(pedido=ped_pagado, producto=prod, cantidad=1)
        Pedido.objects.filter(pk=ped_pagado.pk).update(creado_en=ayer_dt, actualizado_en=ayer_dt)

        # Venta abierta sin cobrar en Mesa con pedido LISTO olvidado ayer
        mesa.ocupar(timestamp=ayer_dt)
        venta_abierta_ayer = Venta.objects.create(
            caja=caja_ayer,
            cajero=self.mesero,
            punto_venta=local,
            modalidad='MESA',
            mesa=mesa,
            metodo_pago='EFECTIVO',
            total=Decimal('5600'),
            estado='ABIERTA',
        )
        Venta.objects.filter(pk=venta_abierta_ayer.pk).update(fecha_hora=ayer_dt)
        ped_abierto = Pedido.objects.create(venta=venta_abierta_ayer, estado='LISTO', fecha_inicio_preparacion=ayer_dt, fecha_listo=ayer_dt)
        DetallePedido.objects.create(pedido=ped_abierto, producto=prod, cantidad=2)
        Pedido.objects.filter(pk=ped_abierto.pk).update(creado_en=ayer_dt, actualizado_en=ayer_dt)

        # Al día siguiente entra PRIMERO Cocina (antes incluso de que Cajero abra jornada)
        self.client.force_login(self.cocinero)
        resp_kds = self.client.get(reverse('cocina'))
        self.assertEqual(resp_kds.status_code, 200)
        self.assertEqual(len(resp_kds.context['pedidos']), 0)

        jornada_ayer.refresh_from_db()
        caja_ayer.refresh_from_db()
        venta_abierta_ayer.refresh_from_db()
        ped_abierto.refresh_from_db()
        ped_pagado.refresh_from_db()
        mesa.refresh_from_db()

        self.assertEqual(jornada_ayer.estado, 'CERRADA')
        self.assertEqual(caja_ayer.estado, 'CERRADA')
        self.assertEqual(caja_ayer.total_efectivo_declarado, Decimal('25000'))
        self.assertEqual(venta_abierta_ayer.estado, 'ANULADA')
        self.assertEqual(ped_abierto.estado, 'CANCELADO')
        self.assertEqual(ped_pagado.estado, 'ENTREGADO')
        self.assertTrue(ped_pagado.validar_orden_temporal()[0])
        self.assertEqual(mesa.estado, 'HABILITADA')
        self.assertIsNone(mesa.fecha_ocupacion)

        # Cuando luego entra el Cajero y abre la nueva jornada con fondo vacío, recibe los $25.000 protegidos
        self.client.force_login(self.cajero)
        self.client.post(reverse('abrir_jornada'), {'monto_apertura': ''}, follow=True)
        caja_hoy = Caja.objects.filter(cajero=self.cajero, estado='ABIERTA', jornada__fecha=timezone.localdate()).first()
        self.assertIsNotNone(caja_hoy)
        self.assertEqual(caja_hoy.monto_apertura, Decimal('25000'))

    def test_pedido_olvidado_por_horas_sin_cerrar_se_limpia_automaticamente(self):
        import datetime as dt_mod
        from decimal import Decimal
        from ventas.models import Jornada, Caja, Venta, Pedido, DetallePedido, Mesa, Producto

        local = PuntoVenta.objects.get(id=1)
        mesa = Mesa.objects.filter(punto_venta=local, estado='HABILITADA').first()
        prod = Producto.objects.filter(activo=True).first()

        # Simula el caso real de #COM-0023 olvidado 857 minutos sin cerrar
        hace_857_min = timezone.now() - dt_mod.timedelta(minutes=857)
        jornada = Jornada.objects.create(usuario_apertura=self.mesero, estado='ABIERTA')
        caja = Caja.objects.create(
            jornada=jornada,
            cajero=self.mesero,
            punto_venta=local,
            nombre="Caja Madrugada",
            monto_apertura=Decimal('0'),
            estado='ABIERTA',
        )
        mesa.ocupar(timestamp=hace_857_min)
        venta_abandonada = Venta.objects.create(
            caja=caja,
            cajero=self.mesero,
            punto_venta=local,
            modalidad='MESA',
            mesa=mesa,
            metodo_pago='EFECTIVO',
            total=Decimal('5600'),
            estado='ABIERTA',
        )
        Venta.objects.filter(pk=venta_abandonada.pk).update(fecha_hora=hace_857_min)

        ped_zombie = Pedido.objects.create(
            venta=venta_abandonada,
            estado='LISTO',
            fecha_inicio_preparacion=hace_857_min,
            fecha_listo=hace_857_min,
        )
        DetallePedido.objects.create(pedido=ped_zombie, producto=prod, cantidad=2)
        Pedido.objects.filter(pk=ped_zombie.pk).update(creado_en=hace_857_min, actualizado_en=hace_857_min)

        self.client.force_login(self.cocinero)
        resp = self.client.get(reverse('cocina'))
        self.assertEqual(resp.status_code, 200)
        ids_en_kds = [p['id'] for p in resp.context['pedidos']]
        self.assertNotIn(ped_zombie.id, ids_en_kds)

        ped_zombie.refresh_from_db()
        venta_abandonada.refresh_from_db()
        mesa.refresh_from_db()
        self.assertEqual(ped_zombie.estado, 'CANCELADO')
        self.assertEqual(venta_abandonada.estado, 'ANULADA')
        self.assertEqual(mesa.estado, 'HABILITADA')

    def test_cerrar_jornada_limpia_pedidos_en_kds_del_mismo_dia(self):
        from decimal import Decimal
        from django.contrib.auth.models import User
        from ventas.models import Jornada, Caja, Venta, Pedido, DetallePedido, Mesa, Producto

        admin = User.objects.filter(perfil__rol='ADMINISTRADOR').first()
        local = PuntoVenta.objects.get(id=1)
        mesa = Mesa.objects.filter(punto_venta=local, estado='HABILITADA').first()
        prod = Producto.objects.filter(activo=True).first()

        jornada = Jornada.objects.create(usuario_apertura=self.cajero, estado='ABIERTA')
        caja = Caja.objects.create(
            jornada=jornada,
            cajero=self.cajero,
            punto_venta=local,
            nombre="Caja Turno Día",
            monto_apertura=Decimal('10000'),
            estado='ABIERTA',
        )
        mesa.ocupar()
        venta = Venta.objects.create(
            caja=caja,
            cajero=self.mesero,
            punto_venta=local,
            modalidad='MESA',
            mesa=mesa,
            metodo_pago='EFECTIVO',
            total=Decimal('5600'),
            estado='ABIERTA',
        )
        ped = Pedido.objects.create(venta=venta, estado='LISTO', fecha_inicio_preparacion=timezone.now(), fecha_listo=timezone.now())
        DetallePedido.objects.create(pedido=ped, producto=prod, cantidad=2)

        # Administrador fuerza cierre de jornada
        self.client.force_login(admin)
        self.client.post(reverse('cerrar_jornada'), {
            'jornada_id': jornada.id,
            'forzar_cierre': '1',
            'observaciones_cierre': 'Fin de operaciones del día',
        })

        ped.refresh_from_db()
        venta.refresh_from_db()
        caja.refresh_from_db()
        mesa.refresh_from_db()
        self.assertEqual(caja.estado, 'CERRADA')
        self.assertEqual(venta.estado, 'ANULADA')
        self.assertEqual(ped.estado, 'CANCELADO')
        self.assertEqual(mesa.estado, 'HABILITADA')

        # KDS Cocina ya no muestra el pedido de la jornada cerrada
        self.client.force_login(self.cocinero)
        resp_kds = self.client.get(reverse('cocina'))
        self.assertEqual(len(resp_kds.context['pedidos']), 0)


class EzioYAloyNuevasFuncionalidadesTests(TestCase):
    """
    Batería integral de pruebas automatizadas para las funcionalidades y parches solicitados por Ezio y Aloy:
    1. Endpoint delta de sincronización liviana (/api/sincronizacion/estado/).
    2. Control táctil de stock en KDS (Cocina/Barra) y protección contra venta de productos agotados (/api/kds/toggle-stock/).
    3. Desglose y sugerencia voluntaria de propina del 10% (Ley N° 20.918 Art. 64 bis) en comprobantes y liquidación.
    4. División de cuentas y abonos parciales (Split Bill) en atención de mesas sin liberar anticipadamente.
    5. Motor anti-abandono y contingencia operativa en KDS (prevención de pedidos huérfanos > 180 min).
    """

    def setUp(self):
        from django.contrib.auth.models import User
        from ventas.models import PuntoVenta, PerfilEmpleado, Categoria, Producto, Mesa, Jornada, Caja, Venta, Pedido, DetallePedido, Ticket
        from django.utils import timezone
        import datetime
        from decimal import Decimal

        self.pv = PuntoVenta.objects.create(nombre="Restaurante Central KDS", activo=True)
        self.cat = Categoria.objects.create(nombre="Cocina Caliente", activo=True)
        self.cat_barra = Categoria.objects.create(nombre="Barra Safari", activo=True)

        self.prod_empanada = Producto.objects.create(
            nombre="Empanada de Pino Horno",
            categoria=self.cat,
            precio_base=Decimal('2500'),
            activo=True,
            destino_operativo='COCINA'
        )
        self.prod_empanada.puntos_venta.add(self.pv)

        self.prod_bebida = Producto.objects.create(
            nombre="Bebida Cola 500ml",
            categoria=self.cat_barra,
            precio_base=Decimal('1800'),
            activo=True,
            destino_operativo='BARRA'
        )
        self.prod_bebida.puntos_venta.add(self.pv)

        self.mesa1 = Mesa.objects.create(identificador="Mesa 1", punto_venta=self.pv, capacidad=4, estado='HABILITADA')

        # Usuarios por rol
        self.admin = User.objects.create_user(username="admin_kds", password="Password123!", is_staff=True)
        PerfilEmpleado.objects.create(usuario=self.admin, rol='ADMINISTRADOR', activo=True, punto_venta_actual=self.pv)

        self.cocinero = User.objects.create_user(username="cocinero_kds", password="Password123!")
        PerfilEmpleado.objects.create(usuario=self.cocinero, rol='COCINERO', activo=True, punto_venta_actual=self.pv)

        self.mesero = User.objects.create_user(username="mesero_kds", password="Password123!")
        PerfilEmpleado.objects.create(usuario=self.mesero, rol='MESERO', activo=True, punto_venta_actual=self.pv)

        self.cajero = User.objects.create_user(username="cajero_kds", password="Password123!")
        PerfilEmpleado.objects.create(usuario=self.cajero, rol='CAJERO', activo=True, punto_venta_actual=self.pv)

        hoy = timezone.localdate()
        self.jornada = Jornada.objects.create(fecha=hoy, estado='ABIERTA', usuario_apertura=self.admin)
        self.caja = Caja.objects.create(
            nombre="Caja Principal KDS",
            punto_venta=self.pv,
            jornada=self.jornada,
            cajero=self.cajero,
            monto_apertura=Decimal('50000'),
            estado='ABIERTA'
        )

    def test_01_api_sincronizacion_estado_delta_liviano(self):
        """Verifica que /api/sincronizacion/estado/ responda en formato JSON ultra liviano con versión hash"""
        self.client.force_login(self.cocinero)
        url = reverse('api_sincronizacion_estado') + f"?local_id={self.pv.id}&zona=COCINA"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('version', data)
        self.assertEqual(data['cola_total'], 0)
        self.assertEqual(data['mesas_ocupadas'], 0)

        # Crear un pedido activo y verificar que la versión delta cambia
        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero, punto_venta=self.pv,
            modalidad='MESA', mesa=self.mesa1, total=Decimal('5000'), estado='ABIERTA'
        )
        self.mesa1.ocupar()
        ped = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=ped, producto=self.prod_empanada, cantidad=2)

        resp2 = self.client.get(url)
        data2 = resp2.json()
        self.assertEqual(data2['cola_total'], 1)
        self.assertEqual(data2['pendientes'], 1)
        self.assertEqual(data2['mesas_ocupadas'], 1)
        self.assertNotEqual(data['version'], data2['version'])

    def test_02_toggle_stock_producto_desde_kds(self):
        """Verifica que el cocinero pueda pausar/agotar un producto desde KDS y se audite en AlertaTraslado"""
        self.client.force_login(self.cocinero)
        url = reverse('api_toggle_stock_producto')
        resp = self.client.post(url, {'producto_id': self.prod_empanada.id})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertFalse(data['activo'])

        self.prod_empanada.refresh_from_db()
        self.assertFalse(self.prod_empanada.activo)

        # Verificar auditoría
        from ventas.models import AlertaTraslado
        alerta = AlertaTraslado.objects.filter(motivo__contains="[KDS STOCK]").first()
        self.assertIsNotNone(alerta)
        self.assertIn("Empanada de Pino Horno", alerta.motivo)
        self.assertIn("AGOTADO EN COCINA", alerta.motivo)

        # Intento de mesero sin permisos da 403
        self.client.force_login(self.mesero)
        resp_mesero = self.client.post(url, {'producto_id': self.prod_empanada.id})
        self.assertEqual(resp_mesero.status_code, 403)

    def test_03_propina_voluntaria_ley_20918_en_comprobante(self):
        """Verifica que el comprobante de comensal en mesa incluya desglose y cálculo de propina voluntaria 10%"""
        from ventas.utils import generar_contenido_comprobante_venta
        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero, punto_venta=self.pv,
            modalidad='MESA', mesa=self.mesa1, total=Decimal('20000'), estado='PAGADA'
        )
        texto = generar_contenido_comprobante_venta(venta)
        self.assertIn("Propina Sugerida 10% (Ley 20.918)", texto)
        self.assertIn("$2.000", texto)
        self.assertIn("Total Sugerido c/Propina", texto)
        self.assertIn("$22.000", texto)
        self.assertIn("100% voluntaria", texto)

    def test_04_split_bill_abono_parcial_en_caja(self):
        """Verifica cobro parcial (división de cuenta): genera venta parcial pagada y mantiene mesa ocupada con saldo pendiente"""
        self.client.force_login(self.cajero)
        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero, punto_venta=self.pv,
            modalidad='MESA', mesa=self.mesa1, total=Decimal('30000'), estado='ABIERTA'
        )
        self.mesa1.ocupar()

        # Comensal 1 paga $10.000 en efectivo
        url = reverse('vendedor')
        resp = self.client.post(url, {
            'accion': 'cobrar_cuenta_mesa',
            'mesa_id': self.mesa1.id,
            'metodo_pago': 'EFECTIVO',
            'monto_pago': '10000',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['es_parcial'])
        self.assertEqual(data['saldo_restante'], 20000.0)

        # Mesa debe seguir ocupada con saldo $20.000
        self.mesa1.refresh_from_db()
        self.assertEqual(self.mesa1.estado, 'OCUPADA')
        venta.refresh_from_db()
        self.assertEqual(venta.total, Decimal('20000'))
        self.assertEqual(venta.estado, 'ABIERTA')

        # Se debe haber generado una venta pagada por $10.000
        ventas_pagadas = Venta.objects.filter(mesa=self.mesa1, estado='PAGADA')
        self.assertEqual(ventas_pagadas.count(), 1)
        self.assertEqual(ventas_pagadas.first().total, Decimal('10000'))

    def test_05_regularizacion_contingencia_pedidos_rezagados(self):
        """Verifica que pedidos abandonados > 180 min sean regularizados y no queden como zombies de 800+ min en KDS"""
        from ventas.utils import proteger_contingencia_operativa
        hace_4_horas = timezone.now() - datetime.timedelta(hours=4)

        venta = Venta.objects.create(
            caja=self.caja, cajero=self.cajero, punto_venta=self.pv,
            modalidad='MESA', mesa=self.mesa1, total=Decimal('5000'), estado='PAGADA'
        )
        ped = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        Pedido.objects.filter(id=ped.id).update(creado_en=hace_4_horas, actualizado_en=hace_4_horas)

        res = proteger_contingencia_operativa(usuario=self.admin, forzar=True)
        self.assertGreaterEqual(res['pedidos_regularizados'], 1)

        ped.refresh_from_db()
        # Como la venta estaba pagada, se regulariza a ENTREGADO con fecha válida
        self.assertEqual(ped.estado, 'ENTREGADO')


class AuditoriaSeguridadRomperSistemaTests(TestCase):
    """
    Batería forense destructiva ("Romper el sistema") encargada por el usuario (Ezio y Cortana):
    Prueba metódicamente todos los vectores de ataque, leyes de Chile y controles de seguridad:
    1. Ataques de fuerza bruta y contraseñas débiles (ISO/IEC 27400).
    2. Intentos de elevación de privilegios, puertas traseras y auto-bloqueo (Anti-lockout & RBAC).
    3. Intentos de alteración de precios a $0 y modificación sigilosa de catálogo.
    4. Ataques de manipulación de mesas ocupadas hacia mantenimiento.
    5. Cierre forzado de jornadas y detección obligatoria de alertas de auditoría forense.
    6. Cumplimiento de leyes de Chile: Ley 20.956 (redondeo en efectivo), Ley 20.918 (propina voluntaria 10%) y Ley 19.628 (protección de datos personales y contraseñas).
    """

    def setUp(self):
        from django.contrib.auth.models import User
        from ventas.models import PuntoVenta, PerfilEmpleado, Categoria, Producto, Mesa, Jornada, Caja, Venta, AlertaTraslado
        from decimal import Decimal
        from django.utils import timezone

        self.pv = PuntoVenta.objects.create(nombre="Restaurante Central Auditoría", activo=True)
        self.cat = Categoria.objects.create(nombre="Alimentos Seguros", activo=True)

        self.prod = Producto.objects.create(
            nombre="Pastel de Choclo Safari",
            categoria=self.cat,
            precio_base=Decimal('6500'),
            activo=True
        )
        self.prod.puntos_venta.add(self.pv)

        self.mesa = Mesa.objects.create(identificador="Mesa 5", punto_venta=self.pv, capacidad=4, estado='HABILITADA')

        # Administrador Maestro
        self.admin = User.objects.create_user(username="admin_supremo", password="AdminSecure2026!#", is_staff=True)
        self.perfil_admin = PerfilEmpleado.objects.create(
            usuario=self.admin, rol='ADMINISTRADOR', activo=True, punto_venta_actual=self.pv
        )

        # Cajero
        self.cajero = User.objects.create_user(username="cajero_eval", password="CajeroSecure2026!#")
        self.perfil_cajero = PerfilEmpleado.objects.create(
            usuario=self.cajero, rol='CAJERO', activo=True, punto_venta_actual=self.pv
        )

        hoy = timezone.localdate()
        self.jornada = Jornada.objects.create(fecha=hoy, estado='ABIERTA', usuario_apertura=self.admin)
        self.caja = Caja.objects.create(
            nombre="Caja Auditoría",
            punto_venta=self.pv,
            jornada=self.jornada,
            cajero=self.cajero,
            monto_apertura=Decimal('40000'),
            estado='ABIERTA'
        )

    def test_01_ataque_contrasena_debil_rechazada_en_administrador(self):
        """Intento de inyectar contraseñas débiles o triviales al crear personal: debe ser rechazado conforme a ISO/IEC 27400"""
        from django.contrib.auth.models import User
        self.client.force_login(self.admin)
        url = reverse('administrador_trabajadores')

        claves_debiles = ['123', '12345', '123456', 'password', 'qwerty']
        for clave in claves_debiles:
            resp = self.client.post(url, {
                'accion': 'crear',
                'nombre': 'Infiltrado',
                'apellido': 'Test',
                'username': f'infiltrado_{clave[:4]}',
                'password': clave,
                'rol': 'CAJERO',
                'local_id': self.pv.id
            }, follow=True)
            # El usuario NO debe haberse creado
            self.assertFalse(User.objects.filter(username=f'infiltrado_{clave[:4]}').exists(), f"Fallo de seguridad: Clave débil '{clave}' fue aceptada")

        # Con clave robusta según ISO/IEC 27400
        resp_ok = self.client.post(url, {
            'accion': 'crear',
            'nombre': 'Seguro',
            'apellido': 'Oficial',
            'username': 'seguro_oficial',
            'password': 'PasswordRobusto2026!#',
            'rol': 'CAJERO',
            'local_id': self.pv.id
        }, follow=True)
        user_creado = User.objects.filter(username='seguro_oficial').first()
        self.assertIsNotNone(user_creado)
        # La clave jamás debe estar en texto plano en la BD
        self.assertTrue(user_creado.password.startswith('pbkdf2_sha256$') or user_creado.password.startswith('argon2$'))
        self.assertNotEqual(user_creado.password, 'PasswordRobusto2026!#')

    def test_02_ataque_autodesactivacion_y_bloqueo_administrador(self):
        """Intento de auto-desactivar o degradar al único administrador activo: debe ser bloqueado para evitar lockout"""
        self.client.force_login(self.admin)
        url = reverse('administrador_trabajadores')

        # 1. Intento de desactivarse a sí mismo
        resp = self.client.post(url, {'accion': 'desactivar', 'perfil_id': self.perfil_admin.id}, follow=True)
        self.perfil_admin.refresh_from_db()
        self.assertTrue(self.perfil_admin.activo, "Fallo: El administrador pudo desactivarse a sí mismo.")

        # 2. Intento de cambiarse el rol a MESERO
        resp2 = self.client.post(url, {
            'accion': 'modificar',
            'perfil_id': self.perfil_admin.id,
            'rol': 'MESERO',
            'local_id': self.pv.id
        }, follow=True)
        self.perfil_admin.refresh_from_db()
        self.assertEqual(self.perfil_admin.rol, 'ADMINISTRADOR', "Fallo: El único administrador pudo degradar su propio rol.")

    def test_03_ataque_cambio_rol_con_caja_abierta_bloqueado(self):
        """Intento de cambiar el rol a un cajero que tiene una caja abierta: debe ser denegado por control anti-fraude"""
        self.client.force_login(self.admin)
        url = reverse('administrador_trabajadores')

        # El cajero tiene la caja 'Caja Auditoría' en estado ABIERTA
        resp = self.client.post(url, {
            'accion': 'modificar',
            'perfil_id': self.perfil_cajero.id,
            'rol': 'MESERO',
            'local_id': self.pv.id
        }, follow=True)

        self.perfil_cajero.refresh_from_db()
        self.assertEqual(self.perfil_cajero.rol, 'CAJERO', "Fallo: Se permitió cambiar el rol de un colaborador con caja abierta.")

    def test_04_ataque_producto_precio_cero_o_negativo_bloqueado(self):
        """Intento de crear productos con precio $0 o negativo: debe ser bloqueado impidiendo fuga de inventario"""
        from ventas.models import Producto
        self.client.force_login(self.admin)
        url = reverse('administrador_productos')

        # Precio 0
        resp0 = self.client.post(url, {
            'accion': 'crear',
            'nombre': 'Plato Gratis Ilegal',
            'categoria_id': self.cat.id,
            'precio_base': '0',
            'activo': 'on'
        }, follow=True)
        self.assertFalse(Producto.objects.filter(nombre='Plato Gratis Ilegal').exists())

        # Precio negativo
        resp_neg = self.client.post(url, {
            'accion': 'crear',
            'nombre': 'Plato Negativo',
            'categoria_id': self.cat.id,
            'precio_base': '-1500',
            'activo': 'on'
        }, follow=True)
        self.assertFalse(Producto.objects.filter(nombre='Plato Negativo').exists())

        # Modificación de precio legal: audita en AlertaTraslado
        resp_mod = self.client.post(url, {
            'accion': 'modificar',
            'producto_id': self.prod.id,
            'nombre': self.prod.nombre,
            'categoria_id': self.cat.id,
            'precio_base': '7500',
            'activo': 'on'
        }, follow=True)
        self.prod.refresh_from_db()
        self.assertEqual(self.prod.precio_base, Decimal('7500'))

        from ventas.models import AlertaTraslado
        alerta = AlertaTraslado.objects.filter(motivo__contains="[AUDITORÍA PRECIOS]").first()
        self.assertIsNotNone(alerta)
        self.assertTrue("6,500" in alerta.motivo or "6.500" in alerta.motivo or "6500" in alerta.motivo)
        self.assertTrue("7,500" in alerta.motivo or "7.500" in alerta.motivo or "7500" in alerta.motivo)

    def test_05_ataque_inactivar_mesa_ocupada_bloqueado(self):
        """Intento de marcar en mantenimiento o inactivar una mesa con comensales comiendo: debe ser denegado"""
        from ventas.models import Venta
        self.client.force_login(self.admin)
        url = f"/administrador/mesas/?local_id={self.pv.id}"

        # Mesa ocupada con cuenta abierta
        self.mesa.ocupar()
        Venta.objects.create(
            caja=self.caja, cajero=self.cajero, punto_venta=self.pv,
            modalidad='MESA', mesa=self.mesa, total=Decimal('15000'), estado='ABIERTA'
        )

        resp = self.client.post(url, {
            'accion': 'modificar',
            'mesa_id': self.mesa.id,
            'identificador': self.mesa.identificador,
            'capacidad': 4,
            'punto_venta_id': self.pv.id,
            'estado': 'INACTIVA'
        }, follow=True)

        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.estado, 'OCUPADA', "Fallo: Se permitió inactivar una mesa con comensales y cuenta abierta.")

    def test_06_cierre_forzado_jornada_genera_alerta_forense(self):
        """Si un supervisor fuerza el cierre de jornada con cajas abiertas, se genera alerta forense obligatoria"""
        from ventas.models import AlertaTraslado
        self.client.force_login(self.admin)
        url = reverse('cerrar_jornada')

        # Cierre forzado con la caja 'Caja Auditoría' aún abierta
        resp = self.client.post(url, {
            'jornada_id': self.jornada.id,
            'forzar_cierre': '1',
            'observaciones_cierre': 'Cierre por emergencia nocturna'
        }, follow=True)

        self.jornada.refresh_from_db()
        self.assertEqual(self.jornada.estado, 'CERRADA')

        alerta = AlertaTraslado.objects.filter(motivo__contains="[ALERTA AUDITORÍA: CIERRE FORZADO DE JORNADA").first()
        self.assertIsNotNone(alerta, "Fallo: No se emitió la alerta forense de cierre forzado de jornada con cajas abiertas.")
        self.assertIn("Caja Auditoría", alerta.motivo)

    def test_07_ley_chilena_20956_redondeo_en_efectivo(self):
        """Verifica el cumplimiento matemático exacto de la Ley Chilena N° 20.956 para efectivo vs tarjetas"""
        from ventas.utils import calcular_redondeo_ley_20956
        from decimal import Decimal

        # Regla: 1 a 5 pesos terminan en 0 hacia abajo. 6 a 9 pesos terminan en 10 hacia arriba.
        # Caso 1: $1.821 en Efectivo -> $1.820 (ajuste -1)
        final, adj = calcular_redondeo_ley_20956(Decimal('1821'), 'EFECTIVO')
        self.assertEqual(final, Decimal('1820'))
        self.assertEqual(adj, Decimal('-1'))

        # Caso 2: $1.824 en Efectivo -> $1.820 (ajuste -4)
        final, adj = calcular_redondeo_ley_20956(Decimal('1824'), 'EFECTIVO')
        self.assertEqual(final, Decimal('1820'))
        self.assertEqual(adj, Decimal('-4'))

        # Caso 2b: $1.825 en Efectivo -> $1.830 (ajuste +5)
        final, adj = calcular_redondeo_ley_20956(Decimal('1825'), 'EFECTIVO')
        self.assertEqual(final, Decimal('1830'))
        self.assertEqual(adj, Decimal('5'))

        # Caso 3: $1.826 en Efectivo -> $1.830 (ajuste +4)
        final, adj = calcular_redondeo_ley_20956(Decimal('1826'), 'EFECTIVO')
        self.assertEqual(final, Decimal('1830'))
        self.assertEqual(adj, Decimal('4'))

        # Caso 4: $1.829 en Efectivo -> $1.830 (ajuste +1)
        final, adj = calcular_redondeo_ley_20956(Decimal('1829'), 'EFECTIVO')
        self.assertEqual(final, Decimal('1830'))
        self.assertEqual(adj, Decimal('1'))

        # Caso 5: En Tarjeta de Débito / Crédito: NO se redondea (ajuste 0)
        final, adj = calcular_redondeo_ley_20956(Decimal('1825'), 'DEBITO')
        self.assertEqual(final, Decimal('1825'))
        self.assertEqual(adj, Decimal('0'))

    def test_08_ley_19628_y_seguridad_contrasenas_cero_texto_plano(self):
        """Garantiza cumplimiento de Ley 19.628 y Norma ISO/IEC 27400: Cero contraseñas en texto plano en la BD"""
        from django.contrib.auth.models import User
        users = User.objects.all()
        for u in users:
            self.assertTrue(
                u.password.startswith('pbkdf2_sha256$') or u.password.startswith('argon2$'),
                f"Alerta Crítica: El usuario '{u.username}' tiene una contraseña no hasheada o insegura."
            )
            self.assertFalse(u.password.isalnum() and len(u.password) < 20, "Alerta: Contraseña en texto plano detectada en la BD.")
    def test_09_antifraude_fiados_bloqueo_autofiadoy_limite_100k(self):
        """Blindaje anti-fraude en fiados: bloqueo de auto-fiado a cajeros, límite $100.000 y alerta automática"""
        from ventas.utils import registrar_consumo_interno
        from ventas.models import AlertaTraslado
        from django.core.exceptions import ValidationError

        # 1. Cajero no puede auto-otorgarse fiado
        with self.assertRaises(ValidationError) as ctx1:
            registrar_consumo_interno(
                empleado=self.cajero,
                punto_venta=self.pv,
                items=[{'producto_id': self.prod.id, 'cantidad': 1}],
                usuario_registro=self.cajero,
                tipo_consumo='FIADO'
            )
        self.assertIn("anti-fraude", str(ctx1.exception).lower())

        # 2. Fiado de $15.000 o más genera AlertaTraslado obligatoria
        consumo_grande = registrar_consumo_interno(
            empleado=self.cajero,
            punto_venta=self.pv,
            items=[{'producto_id': self.prod.id, 'cantidad': 3}],
            usuario_registro=self.admin,
            tipo_consumo='FIADO'
        )
        self.assertGreaterEqual(consumo_grande.total, Decimal('15000'))
        alerta_fiado = AlertaTraslado.objects.filter(motivo__contains="[AUDITORÍA FIADOS / CRÉDITO]").first()
        self.assertIsNotNone(alerta_fiado)

    def test_10_promo_moneda_1_peso_sin_redondeo_y_activacion_admin(self):
        """Excepción Ley 20.956 y promo docente: 2da unidad a $1 peso no se redondea en efectivo y activa en admin"""
        from ventas.utils import calcular_redondeo_ley_20956

        # Prueba de redondeo con promo de moneda física
        # Regular: $8.901 se redondearía a $8.900 (ajuste -1)
        monto_reg, adj_reg = calcular_redondeo_ley_20956(Decimal('8901'), 'EFECTIVO', tiene_promo_moneda_fisica=False)
        self.assertEqual(monto_reg, Decimal('8900'))

        # Con promo moneda física traída por cliente: se cobra exacto $8.901
        monto_promo, adj_promo = calcular_redondeo_ley_20956(Decimal('8901'), 'EFECTIVO', tiene_promo_moneda_fisica=True)
        self.assertEqual(monto_promo, Decimal('8901'))
        self.assertEqual(adj_promo, Decimal('0'))

        # Activación desde panel administrador_ofertas_temporada
        self.client.force_login(self.admin)
        resp_act = self.client.post(reverse('administrador_ofertas_temporada'), {
            'accion': 'activar_promo_moneda_1',
            'producto_id': self.prod.id
        }, follow=True)
        self.prod.refresh_from_db()
        self.assertTrue(self.prod.en_oferta)
        self.assertEqual(self.prod.tipo_oferta, 'SEGUNDA_1')
        self.assertEqual(self.prod.precio_oferta, Decimal('1'))



    def test_11_administrador_campana_descuento_tarjeta_debito_y_topes(self):
        """Prueba: Administrador crea campaña con descuento por medio de pago (Tarjeta Débito), compra mínima y tope CLP"""
        from ventas.models import OfertaTemporada
        self.client.force_login(self.admin)

        resp = self.client.post(reverse('administrador_ofertas_temporada'), {
            'accion': 'crear',
            'nombre': '15% Descuento Débito Santander',
            'descripcion': 'Beneficio exclusivo con tarjeta débito Banco Santander',
            'tipo_campana': 'MEDIO_PAGO',
            'descuento_porcentaje': '15',
            'medio_pago_requerido': 'DEBITO',
            'banco_convenio': 'Banco Santander',
            'monto_minimo_compra': '5000',
            'tope_descuento_clp': '3000',
            'limite_usos': '50',
            'fecha_inicio': timezone.now().date(),
            'fecha_fin': timezone.now().date() + timedelta(days=15),
            'activa': 'on'
        }, follow=True)

        self.assertContains(resp, "creada y configurada exitosamente")
        camp = OfertaTemporada.objects.get(nombre='15% Descuento Débito Santander')
        self.assertTrue(camp.activa)
        self.assertEqual(camp.tipo_campana, 'MEDIO_PAGO')
        self.assertEqual(camp.medio_pago_requerido, 'DEBITO')
        self.assertEqual(camp.banco_convenio, 'Banco Santander')
        self.assertEqual(camp.tope_descuento_clp, Decimal('3000'))

        # Verificación del cálculo con tope y medio de pago
        desc_valido = camp.calcular_descuento(Decimal('30000'), medio_pago='DEBITO')
        # 15% de 30.000 = 4.500, pero tope es 3.000
        self.assertEqual(desc_valido, Decimal('3000'))

        # Si paga en efectivo no aplica
        desc_efectivo = camp.calcular_descuento(Decimal('30000'), medio_pago='EFECTIVO')
        self.assertEqual(desc_efectivo, Decimal('0'))

    def test_12_administrador_editar_y_eliminar_campana(self):
        """Prueba: Administrador edita y elimina permanentemente una campaña comercial"""
        from ventas.models import OfertaTemporada
        self.client.force_login(self.admin)

        camp = OfertaTemporada.objects.create(
            nombre='Campaña Temporal a Borrar',
            descuento_porcentaje=Decimal('10'),
            fecha_inicio=timezone.now().date(),
            fecha_fin=timezone.now().date() + timedelta(days=5),
            activa=True
        )

        # 1. Editar
        resp_edit = self.client.post(reverse('administrador_ofertas_temporada'), {
            'accion': 'editar_campana',
            'oferta_id': camp.id,
            'nombre': 'Campaña Temporal Modificada',
            'tipo_campana': 'GENERAL',
            'descuento_porcentaje': '20',
            'medio_pago_requerido': 'TODOS',
            'monto_minimo_compra': '0',
            'tope_descuento_clp': '0',
            'limite_usos': '10',
            'activa': 'on'
        }, follow=True)
        camp.refresh_from_db()
        self.assertEqual(camp.nombre, 'Campaña Temporal Modificada')
        self.assertEqual(camp.descuento_porcentaje, Decimal('20'))

        # 2. Eliminar
        resp_del = self.client.post(reverse('administrador_ofertas_temporada'), {
            'accion': 'eliminar_campana',
            'oferta_id': camp.id,
        }, follow=True)
        self.assertContains(resp_del, "eliminada permanentemente")
        self.assertFalse(OfertaTemporada.objects.filter(id=camp.id).exists())

    def test_13_administrador_promo_producto_precio_custom_y_limite_comanda(self):
        """Prueba: Administrador configura promo 2da unidad a $500 pesos con límite por comanda"""
        self.client.force_login(self.admin)

        resp = self.client.post(reverse('administrador_ofertas_temporada'), {
            'accion': 'guardar_promo_producto',
            'producto_id': self.prod.id,
            'tipo_oferta': 'SEGUNDA_1',
            'precio_oferta': '500',
            'limite_oferta_por_ticket': '1',
            'descripcion_oferta': '¡Segunda unidad a $500 pesos (máx 1 por mesa)!'
        }, follow=True)

        self.assertContains(resp, "configurada exitosamente")
        self.prod.refresh_from_db()
        self.assertTrue(self.prod.en_oferta)
        self.assertEqual(self.prod.tipo_oferta, 'SEGUNDA_1')
        self.assertEqual(self.prod.precio_oferta, Decimal('500'))
        self.assertEqual(self.prod.limite_oferta_por_ticket, 1)

        # Verificación del cálculo con límite de ticket:
        # self.prod.precio_base = 5000 (o el que tenga)
        # 4 unidades (2 pares):
        # Como el límite es 1 par promo: 1 par a (base + 500) + 1 par a (2 * base)
        total, ahorro, texto = self.prod.calcular_total_promocion(4)
        esperado = (self.prod.precio_base + Decimal('500')) + (2 * self.prod.precio_base)
        self.assertEqual(total, esperado)
        self.assertEqual(ahorro, self.prod.precio_base - Decimal('500'))

    def test_14_administrador_toggle_y_eliminar_promo_producto(self):
        """Prueba: Administrador pausa y luego elimina una promoción de producto"""
        self.client.force_login(self.admin)

        # Configurar promo
        self.prod.en_oferta = True
        self.prod.tipo_oferta = '2X1'
        self.prod.save()

        # Toggle (pausar)
        self.client.post(reverse('administrador_ofertas_temporada'), {
            'accion': 'toggle_promo_producto',
            'producto_id': self.prod.id
        })
        self.prod.refresh_from_db()
        self.assertFalse(self.prod.en_oferta)

        # Eliminar
        self.client.post(reverse('administrador_ofertas_temporada'), {
            'accion': 'eliminar_promo_producto',
            'producto_id': self.prod.id
        })
        self.prod.refresh_from_db()
        self.assertFalse(self.prod.en_oferta)
        self.assertEqual(self.prod.tipo_oferta, 'NINGUNA')
        self.assertIsNone(self.prod.precio_oferta)

    def test_15_descuento_automatico_medio_pago_en_caja_pos(self):
        """Prueba: Cobro en caja POS aplica automáticamente descuento de campaña activa al pagar con Tarjeta Débito"""
        from ventas.models import OfertaTemporada, Venta

        camp = OfertaTemporada.objects.create(
            nombre='Promo 20% Tarjeta Débito',
            tipo_campana='MEDIO_PAGO',
            descuento_porcentaje=Decimal('20'),
            medio_pago_requerido='DEBITO',
            fecha_inicio=timezone.now().date(),
            fecha_fin=timezone.now().date() + timedelta(days=10),
            activa=True
        )

        self.client.force_login(self.cajero)
        payload = {
            'modalidad': 'VENTA_RAPIDA',
            'metodo_pago': 'DEBITO', 'pos_metodo_pago': 'DEBITO',
            'modo_cuenta': 'PAGADA',
            'items_json': json.dumps([{'id': self.prod.id, 'cantidad': 2, 'precio': int(self.prod.precio_base)}])
        }

        resp = self.client.post(reverse('crear_ticket'), payload)
        self.assertEqual(resp.status_code, 302)

        venta = Venta.objects.filter(cajero=self.cajero, metodo_pago='DEBITO').order_by('-id').first()
        self.assertIsNotNone(venta)
        # Subtotal bruto = 2 * self.prod.precio_base
        # Descuento 20%
        subtotal_esperado = (2 * self.prod.precio_base) * Decimal('0.80')
        self.assertEqual(venta.total, subtotal_esperado)
        camp.refresh_from_db()
        self.assertEqual(camp.usos_actuales, 1)
