import datetime as dt_mod
import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from ventas.models import (
    AlertaTraslado,
    Categoria,
    ConsumoHuesped,
    ConsumoInterno,
    ConvenioHuesped,
    DetalleVenta,
    Menu,
    Mesa,
    OfertaTemporada,
    PrecioEspecial,
    Producto,
    PuntoVenta,
    RegistroPrecioEspecial,
    Ticket,
    Venta,
)
from ventas.test_suites.base import SafariDemoTestCase
from ventas.utils import (
    calcular_redondeo_ley_20956,
    generar_contenido_comprobante_venta,
    generar_firma_qr_convenio,
    liquidar_consumos_por_planilla,
    registrar_consumo_interno,
    registrar_precio_especial_auditoria,
    validar_disponibilidad_producto,
    validar_y_calcular_precio_linea,
    verificar_firma_qr_convenio,
)


class CatalogoPosicionamientoYPromocionesTests(SafariDemoTestCase):
    """
    Suite consolidada de Productos, Menús, Posicionamiento por Local y Promociones:
    - CRUD Productos y Menús (RBAC, nombre obligatorio, toggle estado, soft-delete con historial vs hard-delete, AJAX).
    - RF15 Posicionamiento por local y menús activos, multi-local, rechazo de ajenos/inactivos/carta apagada, preservación contable.
    - Promociones ($1 peso, exención Ley 20.956 moneda física, campañas MEDIO_PAGO con topes, SEGUNDA_1, SEGUNDA_PCT, LLEVA_2_POR, CANTIDAD_MINIMA).
    - Contraste Positivo vs Negativo en filtrado de catálogo POS Cajero.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat_suite = Categoria.objects.create(nombre="Gastronomía Suite M4", activo=True)
        cls.prod_base = Producto.objects.create(
            nombre="Hamburguesa Clásica Suite M4",
            categoria=cls.cat_suite,
            precio_base=Decimal('6500'),
            destino_operativo='COCINA',
            activo=True,
        )
        cls.prod_base.puntos_venta.add(cls.pv_central)

        cls.prod_barra = Producto.objects.create(
            nombre="Jugo Safari Suite M4",
            categoria=cls.cat_suite,
            precio_base=Decimal('2500'),
            destino_operativo='BARRA',
            activo=True,
        )
        cls.prod_barra.puntos_venta.add(cls.pv_central, cls.pv_selva)

    def test_crud_productos_y_menus_con_soft_vs_hard_delete(self):
        # 1. RBAC: anónimo y cajero bloqueados en administradores de catálogo/menús
        for usuario, destino, alerta in [(None, reverse('index'), "Acceso protegido"), (self.cajero_user, reverse('vendedor'), "Acceso restringido")]:
            with self.subTest(rol_cat=usuario.username if usuario else 'ANON'):
                if usuario:
                    self.client.force_login(usuario)
                else:
                    self.client.logout()
                r = self.client.get(reverse('administrador_productos'), follow=True)
                self.assertRedirects(r, destino)
                self.assertContains(r, alerta)

        # 2. Admin lista, crea producto válido y rechaza nombre vacío
        self.client.force_login(self.admin_user)
        r_list = self.client.get(reverse('administrador_productos'))
        self.assertContrastePositivoNegativo(
            r_list,
            debe_estar=("CATÁLOGO CENTRALIZADO DE PRODUCTOS", "Hamburguesa Safari con Papas"),
        )

        r_crear = self.client.post(
            reverse('administrador_productos'),
            {
                'accion': 'crear',
                'nombre': 'Chorrillana Campestre Safari',
                'categoria_id': self.cat_suite.id,
                'precio_base': '12500',
                'descripcion': 'Papas rústicas con carne mechada',
                'puntos_venta': [self.pv_central.id],
                'activo': 'on',
            },
            follow=True,
        )
        self.assertContains(r_crear, "creado exitosamente")
        prod_new = Producto.objects.get(nombre='Chorrillana Campestre Safari')
        self.assertEqual(prod_new.precio_base, Decimal('12500'))

        r_vacio = self.client.post(
            reverse('administrador_productos'),
            {'accion': 'crear', 'nombre': '', 'categoria_id': self.cat_suite.id, 'precio_base': '5000'},
            follow=True,
        )
        self.assertContains(r_vacio, "El nombre del producto es obligatorio")

        # 3. Modificar, toggle_estado y soft-delete con ventas vs hard-delete sin ventas
        self.client.post(
            reverse('administrador_productos'),
            {
                'accion': 'modificar',
                'producto_id': prod_new.id,
                'nombre': 'Chorrillana Renovada',
                'categoria_id': self.cat_suite.id,
                'precio_base': '13500',
                'descripcion': 'Nueva fórmula',
                'puntos_venta': [self.pv_central.id],
                'activo': 'on',
            },
            follow=True,
        )
        prod_new.refresh_from_db()
        self.assertEqual(prod_new.nombre, 'Chorrillana Renovada')
        self.assertEqual(prod_new.precio_base, Decimal('13500'))

        r_tog = self.client.post(reverse('administrador_productos'), {'accion': 'toggle_estado', 'producto_id': prod_new.id}, follow=True)
        self.assertContains(r_tog, "desactivado del catálogo")
        prod_new.refresh_from_db()
        self.assertFalse(prod_new.activo)

        _, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        v_hist = Venta.objects.create(caja=caja, cajero=self.admin_user, punto_venta=self.pv_central, total=13500, estado='PAGADA')
        DetalleVenta.objects.create(venta=v_hist, producto=prod_new, cantidad=1, precio_aplicado=13500, subtotal=13500)

        r_del_soft = self.client.post(reverse('administrador_productos'), {'accion': 'eliminar', 'producto_id': prod_new.id}, follow=True)
        self.assertContains(r_del_soft, "registra ventas históricas")
        self.assertTrue(Producto.objects.filter(id=prod_new.id).exists())

        prod_sin_ventas = Producto.objects.create(nombre='Item Limpio Borrable', categoria=self.cat_suite, precio_base=1000)
        r_del_hard = self.client.post(reverse('administrador_productos'), {'accion': 'eliminar', 'producto_id': prod_sin_ventas.id}, follow=True)
        self.assertContains(r_del_hard, "eliminado definitivamente")
        self.assertFalse(Producto.objects.filter(id=prod_sin_ventas.id).exists())

        # 4. CRUD Menús + Modificar AJAX en tiempo real
        self.assertContains(self.client.get(reverse('administrador_menus')), "CARTAS Y MENÚS POR PUNTO DE VENTA")
        r_m_crear = self.client.post(
            reverse('administrador_menus'),
            {'accion': 'crear', 'nombre': 'Carta Ejecutiva Safari', 'punto_venta_id': self.pv_central.id, 'productos': [self.prod_base.id], 'activo': 'on'},
            follow=True,
        )
        self.assertContains(r_m_crear, "asignado exitosamente")
        menu_m = Menu.objects.get(nombre='Carta Ejecutiva Safari', punto_venta=self.pv_central)

        r_m_ajax = self.client.post(
            reverse('administrador_menus'),
            {
                'accion': 'modificar',
                'menu_id': menu_m.id,
                'nombre': 'Carta Modificada en Tiempo Real',
                'punto_venta_id': self.pv_central.id,
                'productos': [self.prod_base.id, self.prod_barra.id],
                'activo': 'on',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_m_ajax.status_code, 200)
        self.assertEqual(r_m_ajax.json()['nombre'], 'Carta Modificada en Tiempo Real')
        self.assertEqual(r_m_ajax.json()['productos_count'], 2)

        self.client.post(reverse('administrador_menus'), {'accion': 'toggle_estado', 'menu_id': menu_m.id}, follow=True)
        menu_m.refresh_from_db()
        self.assertFalse(menu_m.activo)
        self.client.post(reverse('administrador_menus'), {'accion': 'eliminar', 'menu_id': menu_m.id}, follow=True)
        self.assertFalse(Menu.objects.filter(id=menu_m.id).exists())

    def test_rf15_posicionamiento_por_local_menus_y_contraste_catalogo(self):
        local_vacio = PuntoVenta.objects.create(nombre="Cafetería Sin Carta M4", tipo="CAFETERIA", activo=True)
        Menu.objects.create(nombre="Carta Vacía M4", punto_venta=local_vacio, activo=True)
        mesa_a = Mesa.objects.filter(punto_venta=self.pv_central, estado='HABILITADA').first()

        prod_excl_b = Producto.objects.create(nombre="Snack Exclusivo Selva M4", categoria=self.cat_suite, precio_base=Decimal('2500'), activo=True)
        prod_excl_b.puntos_venta.add(self.pv_selva)

        prod_inactivo = Producto.objects.create(nombre="Plato Descontinuado M4", categoria=self.cat_suite, precio_base=Decimal('5000'), activo=False)
        prod_inactivo.puntos_venta.add(self.pv_central)

        prod_solo_menu = Producto.objects.create(nombre="Postre Carta Central M4", categoria=self.cat_suite, precio_base=Decimal('4200'), activo=True)
        menu_central = Menu.objects.create(nombre="Carta Especial Central M4", punto_venta=self.pv_central, activo=True)
        menu_central.productos.add(prod_solo_menu)

        self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        self.abrir_jornada_y_caja(self.pv_selva, self.cajera2_user, admin=self.admin_user)

        # Contraste positivo vs negativo en catálogo de GET crear_ticket del Cajero Local Central
        self.client.force_login(self.cajero_user)
        resp_pos_get = self.client.get(reverse('crear_ticket'))
        self.assertEqual(resp_pos_get.status_code, 200)
        prods_ctx = list(resp_pos_get.context['productos_activos'])
        for p_pos in (self.prod_base, self.prod_barra, prod_solo_menu):
            self.assertIn(p_pos, prods_ctx)
        for p_neg in (prod_excl_b, prod_inactivo):
            self.assertNotIn(p_neg, prods_ctx)
        self.assertContrastePositivoNegativo(
            resp_pos_get,
            debe_estar=(self.prod_base.nombre, prod_solo_menu.nombre),
            no_debe_estar=(prod_excl_b.nombre, prod_inactivo.nombre),
            contexto="Catálogo filtrado en POS Cajero Local Central",
        )

        # Venta POS válida de producto directo, multi-local y solo-en-menú-activo
        for prod_ok in (self.prod_base, self.prod_barra, prod_solo_menu):
            with self.subTest(venta_pos_local1=prod_ok.nombre):
                r = self.client.post(
                    reverse('crear_ticket'),
                    {'items_json': json.dumps([{'producto_id': prod_ok.id, 'cantidad': 1}]), 'metodo_pago': 'EFECTIVO', 'modalidad': 'VENTA_RAPIDA'},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.json()['ok'])

        # Producto multi-local también se vende en Local Selva
        self.client.force_login(self.cajera2_user)
        r_b = self.client.post(
            reverse('crear_ticket'),
            {'items_json': json.dumps([{'producto_id': self.prod_barra.id, 'cantidad': 1}]), 'metodo_pago': 'EFECTIVO'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_b.status_code, 200)

        # Desactivar menú inhabilita producto exclusivo de carta
        menu_central.activo = False
        menu_central.save()
        self.assertFalse(prod_solo_menu.esta_disponible_en(self.pv_central))

        # Retirar producto asignado pero conservar contabilidad histórica tras venta
        self.client.force_login(self.cajero_user)
        r_hist = self.client.post(
            reverse('crear_ticket'),
            {'items_json': json.dumps([{'producto_id': self.prod_base.id, 'cantidad': 2}]), 'metodo_pago': 'EFECTIVO'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        v_hist_id = r_hist.json()['venta_id']
        self.prod_base.puntos_venta.remove(self.pv_central)
        self.assertFalse(self.prod_base.esta_disponible_en(self.pv_central))
        v_hist = Venta.objects.get(id=v_hist_id)
        self.assertEqual(v_hist.total, Decimal('13000.00'))

        # SubTests negativos en POS Cajero y Mesero
        for prod_rej, msg_esp in [
            (prod_excl_b, "no se encuentra disponible para venta en el local"),
            (prod_inactivo, "desactivado del catálogo"),
            (prod_solo_menu, "no se encuentra disponible"),
            (self.prod_base, "no se encuentra disponible"),
        ]:
            with self.subTest(rechazo_pos=prod_rej.nombre):
                self.client.force_login(self.cajero_user)
                r_bad = self.client.post(
                    reverse('crear_ticket'),
                    {'items_json': json.dumps([{'producto_id': prod_rej.id, 'cantidad': 1}]), 'metodo_pago': 'EFECTIVO'},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )
                self.assertEqual(r_bad.status_code, 400)
                self.assertIn(msg_esp, r_bad.json()['error'])

            with self.subTest(rechazo_mesero=prod_rej.nombre):
                self.client.force_login(self.mesero_user)
                r_m_bad = self.client.post(
                    reverse('mesero') + f"?local_id={self.pv_central.id}",
                    {'accion': 'enviar_comanda', 'mesa_id': mesa_a.id, 'items_json': json.dumps([{'id': prod_rej.id, 'cantidad': 1}])},
                    follow=True,
                )
                self.assertContains(r_m_bad, msg_esp)

        # Restaurar asignación de prod_base para resto de suite y validar local vacío
        self.prod_base.puntos_venta.add(self.pv_central)
        with self.assertRaises(ValidationError):
            validar_disponibilidad_producto(self.prod_base, local_vacio)

    def test_promociones_redondeo_1_peso_tipos_oferta_y_campana_medio_pago(self):
        # 1. SubTest Ley 20.956 y excepciones evento $1/$5 y moneda física
        casos_redondeo = [
            ('evento_1_peso', Decimal('1'), 'EFECTIVO', False, Decimal('1'), Decimal('0')),
            ('evento_5_pesos', Decimal('5'), 'EFECTIVO', False, Decimal('5'), Decimal('0')),
            ('regular_termina_4', Decimal('1994'), 'EFECTIVO', False, Decimal('1990'), Decimal('-4')),
            ('regular_termina_7', Decimal('10007'), 'EFECTIVO', False, Decimal('10010'), Decimal('3')),
            ('promo_moneda_fisica_8901', Decimal('8901'), 'EFECTIVO', True, Decimal('8901'), Decimal('0')),
            ('sin_promo_moneda_8901', Decimal('8901'), 'EFECTIVO', False, Decimal('8900'), Decimal('-1')),
            ('debito_sin_redondeo', Decimal('13574'), 'DEBITO', False, Decimal('13574'), Decimal('0')),
            ('credito_sin_redondeo', Decimal('13574'), 'CREDITO', False, Decimal('13574'), Decimal('0')),
            ('transferencia_sin_redondeo', Decimal('13574'), 'TRANSFERENCIA', False, Decimal('13574'), Decimal('0')),
        ]
        for caso, monto, medio, flag_mon, fin_esp, adj_esp in casos_redondeo:
            with self.subTest(redondeo=caso):
                fin, adj = calcular_redondeo_ley_20956(monto, medio, tiene_promo_moneda_fisica=flag_mon)
                self.assertEqual(fin, fin_esp)
                self.assertEqual(adj, adj_esp)

        # 2. Oferta a $1 AJAX y activación promo moneda $1 admin
        self.client.force_login(self.admin_user)
        r_of = self.client.post(
            reverse('administrador_productos'),
            {
                'accion': 'gestionar_oferta',
                'producto_id': self.prod_base.id,
                'en_oferta': 'on',
                'precio_oferta': '1',
                'descripcion_oferta': '¡Segunda hamburguesa a $1 peso!',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_of.status_code, 200)
        self.assertEqual(r_of.json()['precio_actual'], 1.0)

        self.client.post(reverse('administrador_ofertas_temporada'), {'accion': 'activar_promo_moneda_1', 'producto_id': self.prod_base.id}, follow=True)
        self.prod_base.refresh_from_db()
        self.assertTrue(self.prod_base.en_oferta)
        self.assertEqual(self.prod_base.tipo_oferta, 'SEGUNDA_1')
        self.assertEqual(self.prod_base.precio_oferta, Decimal('1'))

        # 3. Promociones de producto: SEGUNDA_1 c/ tope, SEGUNDA_PCT, LLEVA_2_POR, CANTIDAD_MINIMA, toggle & delete
        self.client.post(
            reverse('administrador_ofertas_temporada'),
            {
                'accion': 'guardar_promo_producto',
                'producto_id': self.prod_base.id,
                'tipo_oferta': 'SEGUNDA_1',
                'precio_oferta': '500',
                'limite_oferta_por_ticket': '1',
                'descripcion_oferta': '2da a $500 (máx 1)',
            },
            follow=True,
        )
        self.prod_base.refresh_from_db()
        tot_s1, ah_s1, _ = self.prod_base.calcular_total_promocion(4)
        self.assertEqual(tot_s1, Decimal('20000'))  # (6500+500) + (2*6500)
        self.assertEqual(ah_s1, Decimal('6000'))

        # SEGUNDA_PCT al 50%
        self.prod_base.tipo_oferta = 'SEGUNDA_PCT'
        self.prod_base.descuento_pct = Decimal('50')
        self.prod_base.limite_oferta_por_ticket = 0
        self.prod_base.save()
        self.assertEqual(self.prod_base.calcular_total_promocion(2)[:2], (Decimal('9750'), Decimal('3250')))
        self.assertEqual(self.prod_base.calcular_total_promocion(3)[:2], (Decimal('16250'), Decimal('3250')))

        # LLEVA_2_POR con tope 1
        self.prod_base.tipo_oferta = 'LLEVA_2_POR'
        self.prod_base.precio_oferta = Decimal('10000')
        self.prod_base.limite_oferta_por_ticket = 1
        self.prod_base.save()
        self.assertEqual(self.prod_base.calcular_total_promocion(2)[:2], (Decimal('10000'), Decimal('3000')))
        self.assertEqual(self.prod_base.calcular_total_promocion(4)[:2], (Decimal('23000'), Decimal('3000')))

        # CANTIDAD_MINIMA >= 3 a $5.000
        self.prod_base.tipo_oferta = 'CANTIDAD_MINIMA'
        self.prod_base.precio_oferta = Decimal('5000')
        self.prod_base.cantidad_minima_oferta = 3
        self.prod_base.save()
        self.assertEqual(self.prod_base.calcular_total_promocion(2)[:2], (Decimal('13000'), Decimal('0')))
        self.assertEqual(self.prod_base.calcular_total_promocion(3)[:2], (Decimal('15000'), Decimal('4500')))

        # Toggle y eliminar promo producto para dejar precio_base limpio en POS
        self.client.post(reverse('administrador_ofertas_temporada'), {'accion': 'toggle_promo_producto', 'producto_id': self.prod_base.id})
        self.prod_base.refresh_from_db()
        self.assertFalse(self.prod_base.en_oferta)
        self.client.post(reverse('administrador_ofertas_temporada'), {'accion': 'eliminar_promo_producto', 'producto_id': self.prod_base.id})
        self.prod_base.refresh_from_db()
        self.assertEqual(self.prod_base.tipo_oferta, 'NINGUNA')
        self.assertIsNone(self.prod_base.precio_oferta)

        # 4. Campañas OfertaTemporada: crear, editar, eliminar y descuento automático en POS por medio_pago
        hoy = timezone.now().date()
        self.client.post(
            reverse('administrador_ofertas_temporada'),
            {
                'accion': 'crear',
                'nombre': '15% Descuento Débito Santander',
                'descripcion': 'Beneficio exclusivo débito',
                'tipo_campana': 'MEDIO_PAGO',
                'descuento_porcentaje': '15',
                'medio_pago_requerido': 'DEBITO',
                'banco_convenio': 'Banco Santander',
                'monto_minimo_compra': '5000',
                'tope_descuento_clp': '3000',
                'limite_usos': '50',
                'fecha_inicio': hoy,
                'fecha_fin': hoy + dt_mod.timedelta(days=15),
                'activa': 'on',
            },
            follow=True,
        )
        camp = OfertaTemporada.objects.get(nombre='15% Descuento Débito Santander')
        self.assertEqual(camp.calcular_descuento(Decimal('30000'), medio_pago='DEBITO'), Decimal('3000'))
        self.assertEqual(camp.calcular_descuento(Decimal('30000'), medio_pago='EFECTIVO'), Decimal('0'))

        # Editar y eliminar campaña temporal
        camp_tmp = OfertaTemporada.objects.create(
            nombre='Campaña Temporal Borrar', descuento_porcentaje=Decimal('10'), fecha_inicio=hoy, fecha_fin=hoy + dt_mod.timedelta(days=5), activa=True
        )
        self.client.post(
            reverse('administrador_ofertas_temporada'),
            {
                'accion': 'editar_campana', 'oferta_id': camp_tmp.id, 'nombre': 'Campaña Modificada',
                'tipo_campana': 'GENERAL', 'descuento_porcentaje': '20', 'medio_pago_requerido': 'TODOS',
                'monto_minimo_compra': '0', 'tope_descuento_clp': '0', 'limite_usos': '10', 'activa': 'on',
            },
            follow=True,
        )
        camp_tmp.refresh_from_db()
        self.assertEqual(camp_tmp.nombre, 'Campaña Modificada')
        self.client.post(reverse('administrador_ofertas_temporada'), {'accion': 'eliminar_campana', 'oferta_id': camp_tmp.id}, follow=True)
        self.assertFalse(OfertaTemporada.objects.filter(id=camp_tmp.id).exists())

        # Desactivar tope en campaña para probar descuento lineal 20% en caja POS con DEBITO vs sin descuento en EFECTIVO
        camp.activa = False
        camp.save()
        camp_pos = OfertaTemporada.objects.create(
            nombre='Promo 20% Tarjeta Débito POS',
            tipo_campana='MEDIO_PAGO',
            descuento_porcentaje=Decimal('20'),
            medio_pago_requerido='DEBITO',
            fecha_inicio=hoy,
            fecha_fin=hoy + dt_mod.timedelta(days=10),
            activa=True,
        )
        self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        self.client.force_login(self.cajero_user)
        r_pos_deb = self.client.post(
            reverse('crear_ticket'),
            {
                'modalidad': 'VENTA_RAPIDA',
                'metodo_pago': 'DEBITO',
                'pos_metodo_pago': 'DEBITO',
                'modo_cuenta': 'PAGADA',
                'items_json': json.dumps([{'id': self.prod_base.id, 'cantidad': 2, 'precio': int(self.prod_base.precio_base)}]),
            },
        )
        self.assertEqual(r_pos_deb.status_code, 302)
        v_deb = Venta.objects.filter(cajero=self.cajero_user, metodo_pago='DEBITO').order_by('-id').first()
        self.assertEqual(v_deb.total, (2 * self.prod_base.precio_base) * Decimal('0.80'))
        camp_pos.refresh_from_db()
        self.assertEqual(camp_pos.usos_actuales, 1)


class PreciosEspecialesConveniosPropinasYConsumosTests(SafariDemoTestCase):
    """
    Suite consolidada de Reglas Financieras, Tributarias, Convenios y Consumo Interno:
    - RF07: Precio base inmutable, autorización por rol, motivo obligatorio, convenios vigentes, auditoría y anti-manipulación.
    - Convenios Huésped & QR HMAC-SHA256: verificación criptográfica, enmascaramiento PII, límite diario, RLS local y recalculo servidor.
    - Ley N° 20.918 Propina Voluntaria vs IVA 19%: opciones 0/10/15/20%/personalizada, exención 100% de IVA y XML DTE.
    - RF10 Consumo Interno / Fiados: validaciones, auto-fiado anti-fraude, alerta >=$15k, liquidación y separación contable estricta.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat_m4 = Categoria.objects.create(nombre="Precios Finanzas M4", activo=True)
        cls.prod_9000 = Producto.objects.create(
            nombre="Hamburguesa Premium Suite M4",
            categoria=cls.cat_m4,
            precio_base=Decimal('9000.00'),
            destino_operativo='COCINA',
            activo=True,
        )
        cls.prod_9000.puntos_venta.add(cls.pv_central)

        cls.prod_10000 = Producto.objects.create(
            nombre="Tabla Safari Suite M4",
            categoria=cls.cat_m4,
            precio_base=Decimal('10000.00'),
            destino_operativo='COCINA',
            activo=True,
        )
        cls.prod_10000.puntos_venta.add(cls.pv_central)

    def test_rf07_precios_especiales_trazabilidad_pos_e_inmutabilidad(self):
        hoy = timezone.localdate()
        _, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        mesa = Mesa.objects.filter(punto_venta=self.pv_central, estado='HABILITADA').first()

        # 1. Precio base inmutable y auditoría en DetalleVenta + RegistroPrecioEspecial
        calc = validar_y_calcular_precio_linea(
            producto=self.prod_9000, cantidad=2, precio_solicitado=Decimal('6000.00'),
            usuario=self.cajero_user, motivo="Descuento Autorizado Vecino", permite_manual=True,
        )
        self.prod_9000.refresh_from_db()
        self.assertEqual(self.prod_9000.precio_base, Decimal('9000.00'))
        self.assertEqual((calc['precio_original'], calc['precio_aplicado']), (Decimal('9000.00'), Decimal('6000.00')))

        v_rf07 = Venta.objects.create(
            caja=caja, cajero=self.cajero_user, punto_venta=self.pv_central,
            modalidad='VENTA_RAPIDA', metodo_pago='EFECTIVO', total=calc['subtotal'], estado='PAGADA',
        )
        det = DetalleVenta.objects.create(
            venta=v_rf07, producto=self.prod_9000, cantidad=2,
            precio_aplicado=calc['precio_aplicado'], subtotal=calc['subtotal'],
        )
        reg = registrar_precio_especial_auditoria(v_rf07, det, calc)
        det.refresh_from_db()
        self.assertTrue(det.es_precio_especial)
        self.assertEqual(det.autorizado_por, self.cajero_user)
        self.assertEqual(reg.descuento_unitario, Decimal('3000.00'))

        # Historial ?tipo=PRECIOS lo consolida
        self.client.force_login(self.admin_user)
        r_hist = self.client.get(reverse('administrador_historial') + "?tipo=PRECIOS")
        self.assertContains(r_hist, "Descuento Autorizado Vecino")
        self.assertContains(r_hist, "Precio Especial:")

        # 2. Convenio institucional activo y vigente
        conv_ok = PrecioEspecial.objects.create(
            producto=self.prod_9000, nombre_condicion="Tarifa Funcionario Safari",
            codigo_convenio="CONV-FUNC-M4", precio=Decimal('4500.00'),
            fecha_inicio=hoy - dt_mod.timedelta(days=5), fecha_fin=hoy + dt_mod.timedelta(days=5), activo=True,
        )
        calc_conv = validar_y_calcular_precio_linea(producto=self.prod_9000, cantidad=3, convenio_id=conv_ok.id, usuario=self.cajero_user)
        self.assertEqual((calc_conv['precio_aplicado'], calc_conv['subtotal']), (Decimal('4500.00'), Decimal('13500.00')))

        # API verificar_convenio_qr en convenio institucional
        self.client.force_login(self.cajero_user)
        r_qr_inst = self.client.get(reverse('api_verificar_convenio_qr'), {'codigo': 'CONV-FUNC-M4'})
        self.assertEqual(r_qr_inst.status_code, 200)
        self.assertEqual(r_qr_inst.json()['tipo'], 'CONVENIO_INSTITUCIONAL')
        self.assertEqual(r_qr_inst.json()['precio_convenio'], 4500.0)

        # 3. SubTests de rechazos negativos RF07
        conv_exp = PrecioEspecial.objects.create(
            producto=self.prod_9000, nombre_condicion="Convenio Pasado", precio=Decimal('5000.00'),
            fecha_inicio=hoy - dt_mod.timedelta(days=30), fecha_fin=hoy - dt_mod.timedelta(days=1), activo=True,
        )
        prod_off = Producto.objects.create(nombre="Producto Inactivo RF07", categoria=self.cat_m4, precio_base=Decimal('5000'), activo=False)

        for caso, kwargs_v, msg_err in [
            ('mesero_sin_permiso', {'producto': self.prod_9000, 'cantidad': 1, 'precio_solicitado': Decimal('4000'), 'usuario': self.mesero_user, 'motivo': 'Amigo', 'permite_manual': True}, "No tienes autorización"),
            ('motivo_en_blanco', {'producto': self.prod_9000, 'cantidad': 1, 'precio_solicitado': Decimal('5000'), 'usuario': self.cajero_user, 'motivo': '   ', 'permite_manual': True}, "Debe ingresar un motivo"),
            ('precio_cero', {'producto': self.prod_9000, 'cantidad': 1, 'precio_solicitado': Decimal('0'), 'usuario': self.admin_user, 'motivo': 'Cero'}, "mayor a $0"),
            ('precio_negativo', {'producto': self.prod_9000, 'cantidad': 1, 'precio_solicitado': Decimal('-500'), 'usuario': self.admin_user, 'motivo': 'Neg'}, "mayor a $0"),
            ('no_numerico', {'producto': self.prod_9000, 'cantidad': 1, 'precio_solicitado': 'gratis', 'usuario': self.admin_user, 'motivo': 'NaN'}, "formato no numérico inválido"),
            ('producto_inactivo', {'producto': prod_off, 'cantidad': 1, 'usuario': self.cajero_user}, "se encuentra inactivo"),
            ('convenio_expirado', {'producto': self.prod_9000, 'cantidad': 1, 'convenio_id': conv_exp.id, 'usuario': self.cajero_user}, "no se encuentra vigente"),
        ]:
            with self.subTest(rf07_rechazo=caso):
                with self.assertRaises(ValidationError) as ctx:
                    validar_y_calcular_precio_linea(**kwargs_v)
                self.assertIn(msg_err, str(ctx.exception))

        # 4. Servidor ignora precio manipulado desde navegador por Mesero
        self.client.force_login(self.mesero_user)
        self.client.post(
            reverse('mesero') + f"?local_id={self.pv_central.id}",
            {'accion': 'enviar_comanda', 'mesa_id': mesa.id, 'items_json': json.dumps([{'id': self.prod_9000.id, 'cantidad': 1, 'precio': 100}])},
            follow=True,
        )
        v_mesero = Venta.objects.filter(mesa=mesa, estado='ABIERTA').first()
        self.assertEqual(v_mesero.detalles.first().precio_aplicado, Decimal('9000.00'))
        self.assertFalse(v_mesero.detalles.first().es_precio_especial)

        # 5. POS crear_ticket exige motivo explícito en precio_especial (400) y registra venta con motivo (200)
        self.client.force_login(self.cajero_user)
        r_sin_motivo = self.client.post(
            reverse('crear_ticket'),
            {'items_json': json.dumps([{'id': self.prod_9000.id, 'cantidad': 1, 'precio_especial': 7000}]), 'metodo_pago': 'EFECTIVO'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_sin_motivo.status_code, 400)

        r_con_motivo = self.client.post(
            reverse('crear_ticket'),
            {'items_json': json.dumps([{'producto_id': self.prod_9000.id, 'cantidad': 2, 'precio_especial': 7000, 'motivo': 'Convenio Vecino Machalí'}]), 'metodo_pago': 'EFECTIVO'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_con_motivo.status_code, 200)
        v_pos = Venta.objects.get(id=r_con_motivo.json()['venta_id'])
        self.assertEqual(v_pos.total, Decimal('14000.00'))
        self.assertTrue(RegistroPrecioEspecial.objects.filter(venta=v_pos, motivo="Convenio Vecino Machalí").exists())

    def test_convenios_huesped_qr_hmac_rls_limite_y_recalculo(self):
        hoy = timezone.localdate()
        js_src = (Path(settings.BASE_DIR) / 'static' / 'js' / 'cajero' / 'crear_ticket.js').read_text(encoding='utf-8')
        self.assertContrastePositivoNegativo(
            js_src,
            debe_estar=('convenio_aplicado_en_venta',),
            no_debe_estar=('pedidoItems', 'catalogoProductos'),
            contexto="Static JS cajero/crear_ticket.js limpio",
        )

        # 1. Criptografía HMAC-SHA256 positiva y negativa (1 bit adulterado)
        codigo_pase = "CAB-SAFARI-2026-M4"
        firma_ok = generar_firma_qr_convenio(codigo_pase)
        self.assertEqual(len(firma_ok), 16)
        self.assertTrue(verificar_firma_qr_convenio(codigo_pase, firma_ok))
        self.assertTrue(verificar_firma_qr_convenio(codigo_pase, firma_ok.upper()))
        firma_falsa = firma_ok[:-1] + ('0' if firma_ok[-1] != '0' else '1')
        for f_bad in (firma_falsa, "", None):
            self.assertFalse(verificar_firma_qr_convenio(codigo_pase, f_bad))

        conv_desayuno = ConvenioHuesped.objects.create(
            codigo_qr='CAB-DESAYUNO-M4', numero_cabana='Cabaña 101', nombre_titular='Familia González',
            tipo_beneficio='DESAYUNO_INCLUIDO', valor_descuento=Decimal('100.00'), limite_diario=1,
            fecha_checkin=hoy - dt_mod.timedelta(days=1), fecha_checkout=hoy + dt_mod.timedelta(days=2), activo=True,
        )
        conv_pct20 = ConvenioHuesped.objects.create(
            codigo_qr='CAB-PCT20-M4', numero_cabana='Cabaña 19', nombre_titular='Roberto Carlos Silva',
            tipo_beneficio='DESCUENTO_PORCENTAJE', valor_descuento=Decimal('20.00'), limite_diario=1,
            fecha_checkin=hoy - dt_mod.timedelta(days=1), fecha_checkout=hoy + dt_mod.timedelta(days=2), activo=True,
        )

        # 2. Verificación QR: anónimo 401, sin firma/tamper 403, firma válida 200 sin exponer apellido completo
        self.assertEqual(
            self.client.get(f"{reverse('api_verificar_convenio_qr')}?codigo={conv_desayuno.token_qr_firmado}", HTTP_X_REQUESTED_WITH='XMLHttpRequest').status_code,
            401,
        )
        _, caja1 = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        self.client.force_login(self.cajero_user)
        self.assertEqual(self.client.get(f"{reverse('api_verificar_convenio_qr')}?codigo=CAB-DESAYUNO-M4").status_code, 403)
        r_tamper = self.client.get(f"{reverse('api_verificar_convenio_qr')}?codigo={conv_desayuno.codigo_qr}:{firma_falsa}")
        self.assertEqual(r_tamper.status_code, 403)
        self.assertTrue(r_tamper.json().get('tampered'))

        r_valido = self.client.get(f"{reverse('api_verificar_convenio_qr')}?codigo={conv_desayuno.token_qr_firmado}")
        self.assertEqual(r_valido.status_code, 200)
        d_val = r_valido.json()
        self.assertTrue(d_val['ok'] and d_val['puede_consumir'])
        self.assertContrastePositivoNegativo(d_val['titular'], debe_estar=('***',), no_debe_estar=('González',))

        # 3. POS crear_ticket con QR sin firma -> 403 y cero ConsumoHuesped; con firma -> atómico $0 + límite diario agotado
        r_qr_bad = self.client.post(
            reverse('crear_ticket'),
            {'items_json': json.dumps([{'id': self.prod_9000.id, 'cantidad': 1}]), 'metodo_pago': 'EFECTIVO', 'codigo_convenio': 'CAB-DESAYUNO-M4'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_qr_bad.status_code, 403)
        self.assertEqual(ConsumoHuesped.objects.filter(convenio=conv_desayuno).count(), 0)

        r_qr_ok = self.client.post(
            reverse('crear_ticket'),
            {'items_json': json.dumps([{'id': self.prod_9000.id, 'cantidad': 1}]), 'metodo_pago': 'EFECTIVO', 'codigo_convenio': conv_desayuno.token_qr_firmado},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_qr_ok.status_code, 200)
        self.assertTrue(r_qr_ok.json()['convenio_aplicado_en_venta'])
        self.assertEqual(r_qr_ok.json()['total'], 0.0)
        self.assertEqual(ConsumoHuesped.objects.filter(convenio=conv_desayuno).count(), 1)
        self.assertFalse(conv_desayuno.puede_consumir_hoy())
        self.assertIn("Límite diario alcanzado", self.client.get(f"{reverse('api_verificar_convenio_qr')}?codigo={conv_desayuno.token_qr_firmado}").json()['mensaje'])

        # 4. api_aplicar_consumo_convenio: RLS entre locales 403, sin firma 403, recalculo servidor contra inflación cliente + PII protegida
        v_ref = Venta.objects.create(caja=caja1, cajero=self.cajero_user, punto_venta=self.pv_central, modalidad='VENTA_RAPIDA', metodo_pago='EFECTIVO', total=Decimal('10000'), estado='PAGADA')
        DetalleVenta.objects.create(venta=v_ref, producto=self.prod_10000, cantidad=1, precio_aplicado=Decimal('10000'), subtotal=Decimal('10000'))
        t_l1 = Ticket.objects.create(venta=v_ref, punto_venta=self.pv_central, tipo_destino='CLIENTE', codigo='TCK-M4-L1', contenido_impresion='OK')

        # Usuario de Local 2 bloqueado por RLS
        self.client.force_login(self.cajera2_user)
        self.assertEqual(
            self.client.post(reverse('api_aplicar_consumo_convenio'), {'codigo': conv_pct20.token_qr_firmado, 'ticket_id': t_l1.id, 'monto_original': '10000'}).status_code,
            403,
        )

        self.client.force_login(self.cajero_user)
        self.assertEqual(
            self.client.post(reverse('api_aplicar_consumo_convenio'), {'codigo': 'CAB-PCT20-M4', 'ticket_id': t_l1.id, 'monto_original': '10000'}).status_code,
            403,
        )

        r_ap = self.client.post(
            reverse('api_aplicar_consumo_convenio'),
            {
                'codigo': conv_pct20.token_qr_firmado,
                'ticket_id': t_l1.id,
                'monto_original': '1',
                'monto_bonificado': '999999',
                'monto_pagado': '0',
            },
        )
        self.assertEqual(r_ap.status_code, 200)
        d_ap = r_ap.json()
        self.assertEqual((d_ap['monto_original'], d_ap['monto_bonificado'], d_ap['monto_pagado']), (10000.0, 2000.0, 8000.0))
        self.assertNotIn('Silva', d_ap['mensaje'])

    def test_ley_20918_propina_exenta_iva_19_subtest_y_dte_comprobante(self):
        _, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        mesa = Mesa.objects.filter(punto_venta=self.pv_central, estado='HABILITADA').first()

        # 1. SubTests paramétricos: 0%, 10%, 15%, 20% y personalizada NO alteran Neto ni IVA 19%
        escenarios_propina = [
            ('0%', Decimal('10000'), Decimal('0'), 0),
            ('10%', Decimal('10000'), Decimal('1000'), 10),
            ('15%', Decimal('10000'), Decimal('1500'), 15),
            ('20%', Decimal('10000'), Decimal('2000'), 20),
            ('manual_3500', Decimal('25000'), Decimal('3500'), 14),
        ]
        for etq, consumo, propina, pct in escenarios_propina:
            with self.subTest(propina_opcion=etq):
                v = Venta.objects.create(
                    caja=caja, cajero=self.cajero_user, punto_venta=self.pv_central,
                    modalidad='MESA', mesa=mesa, metodo_pago='DEBITO',
                    propina=propina, porcentaje_propina=pct,
                    total_sin_redondeo=consumo + propina, redondeo_ley_20956=Decimal('0'),
                    total=consumo + propina, estado='PAGADA',
                )
                DetalleVenta.objects.create(venta=v, producto=self.prod_10000, cantidad=1, precio_aplicado=consumo, subtotal=consumo)
                neto_esp = round(consumo / Decimal('1.19'), 2)
                iva_esp = round(consumo * Decimal('19') / Decimal('119'), 0)
                self.assertEqual(v.get_subtotal_consumo(), consumo)
                self.assertEqual(v.get_monto_neto(), neto_esp)
                self.assertEqual(v.get_monto_iva(), iva_esp)
                # Contraste negativo: IVA jamás igual al de (consumo + propina) si propina > 0
                if propina > 0:
                    self.assertNotEqual(iva_esp, round((consumo + propina) * Decimal('19') / Decimal('119'), 0))

        # 2. Flujo real Cajero cobra mesa con 15% y Mesero cierra cuenta con 20%
        mesa.estado = 'OCUPADA'
        mesa.save()
        v_caj = Venta.objects.create(
            caja=caja, cajero=self.cajero_user, punto_venta=self.pv_central,
            modalidad='MESA', mesa=mesa, total=Decimal('20000'), total_sin_redondeo=Decimal('20000'), estado='ABIERTA',
        )
        DetalleVenta.objects.create(venta=v_caj, producto=self.prod_10000, cantidad=2, precio_aplicado=Decimal('10000'), subtotal=Decimal('20000'))
        self.client.force_login(self.cajero_user)
        r_c = self.client.post(
            reverse('vendedor'),
            {'accion': 'cobrar_cuenta_mesa', 'mesa_id': mesa.id, 'metodo_pago': 'DEBITO', 'monto_pago': '20000', 'porcentaje_propina': '15'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_c.status_code, 200)
        v_caj.refresh_from_db()
        self.assertEqual((v_caj.propina, v_caj.total, v_caj.get_subtotal_consumo()), (Decimal('3000'), Decimal('23000'), Decimal('20000')))

        mesa.estado = 'OCUPADA'
        mesa.save()
        v_mes = Venta.objects.create(
            caja=caja, cajero=self.cajero_user, punto_venta=self.pv_central,
            modalidad='MESA', mesa=mesa, total=Decimal('15000'), total_sin_redondeo=Decimal('15000'), estado='ABIERTA',
        )
        DetalleVenta.objects.create(venta=v_mes, producto=self.prod_10000, cantidad=1, precio_aplicado=Decimal('15000'), subtotal=Decimal('15000'))
        self.client.force_login(self.mesero_user)
        r_m = self.client.post(reverse('mesero'), {'accion': 'cerrar_cuenta_mesa', 'mesa_id': mesa.id, 'metodo_pago': 'TRANSFERENCIA', 'porcentaje_propina': '20'})
        self.assertEqual(r_m.status_code, 302)
        v_mes.refresh_from_db()
        self.assertEqual((v_mes.propina, v_mes.total, v_mes.get_subtotal_consumo()), (Decimal('3000'), Decimal('18000'), Decimal('15000')))

        # 3. Contraste Comprobante MESA sin propina (sugerencia Ley 20.918) vs con 15% propina + XML DTE
        v_sin_prop = Venta.objects.create(
            caja=caja, cajero=self.cajero_user, punto_venta=self.pv_central,
            modalidad='MESA', mesa=mesa, total=Decimal('20000'), estado='PAGADA',
        )
        txt_sin_prop = generar_contenido_comprobante_venta(v_sin_prop)
        self.assertContrastePositivoNegativo(
            txt_sin_prop,
            debe_estar=("Propina Sugerida 10% (Ley 20.918)", "$2.000", "Total Sugerido c/Propina", "$22.000", "100% voluntaria"),
            no_debe_estar=("Propina 15% (Exenta IVA):",),
            contexto="Comprobante MESA con sugerencia voluntaria 10%",
        )

        v_dte = Venta.objects.create(
            caja=caja, cajero=self.cajero_user, punto_venta=self.pv_central,
            modalidad='MESA', mesa=mesa, metodo_pago='DEBITO', propina=Decimal('1500'),
            porcentaje_propina=15, total_sin_redondeo=Decimal('11500'), redondeo_ley_20956=Decimal('0'),
            total=Decimal('11500'), estado='PAGADA',
        )
        DetalleVenta.objects.create(venta=v_dte, producto=self.prod_10000, cantidad=1, precio_aplicado=Decimal('10000'), subtotal=Decimal('10000'))
        txt_comp = generar_contenido_comprobante_venta(v_dte)
        self.assertContrastePositivoNegativo(
            txt_comp,
            debe_estar=("Subtotal Consumo:", "Neto Afecto (19% IVA):", "IVA 19% (Gastronomía):", "Propina 15% (Exenta IVA):", "+$1.500"),
            no_debe_estar=("Propina Sugerida 10% (Ley 20.918)",),
            contexto="Comprobante texto con desglose de propina exenta 15%",
        )

        tck = Ticket.objects.create(venta=v_dte, tipo_destino='CLIENTE', codigo="TCK-PROP-M4", contenido_impresion=txt_comp)
        self.client.force_login(self.cajero_user)
        r_dte = self.client.get(reverse('ver_imprimir_ticket_digital', args=[tck.id]))
        self.assertEqual(r_dte.status_code, 200)
        self.assertContrastePositivoNegativo(
            r_dte,
            debe_estar=("Propina Voluntaria (100% Exenta de IVA)", "&lt;MntNeto&gt;8403&lt;/MntNeto&gt;", "&lt;IVA&gt;1597&lt;/IVA&gt;"),
            no_debe_estar=("&lt;IVA&gt;1836&lt;/IVA&gt;",),  # Nunca IVA sobre $11.500
            contexto="Ticket DTE XML con IVA solo sobre consumo",
        )

    def test_rf10_consumo_interno_validaciones_antifraude_liquidacion_y_separacion_contable(self):
        _, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        ventas_antes = Venta.objects.count()
        detalles_antes = DetalleVenta.objects.count()
        ventas_caja_antes = caja.ventas.count()

        # 1. Registro válido usa precio BD (ignorando manipulación precio=10) + Contraste contable: 0 impacto en Venta/Caja
        c1 = registrar_consumo_interno(
            empleado=self.mesero_user, punto_venta=self.pv_central,
            items=[{'producto_id': self.prod_9000.id, 'cantidad': 1, 'precio': 10}],
            usuario_registro=self.cajero_user, tipo_consumo='FIADO', observaciones="Almuerzo turno", caja=caja,
        )
        caja.refresh_from_db()
        self.assertEqual(c1.total, Decimal('9000.00'))
        self.assertEqual(c1.estado, 'REGISTRADO')
        self.assertEqual(self.mesero_user.perfil.total_fiado_pendiente(), Decimal('9000.00'))
        # Contraste contable estricto:
        self.assertEqual(Venta.objects.count(), ventas_antes)
        self.assertEqual(DetalleVenta.objects.count(), detalles_antes)
        self.assertEqual(caja.ventas.count(), ventas_caja_antes)

        # 2. SubTests negativos: cantidad <= 0, producto inactivo, usuario/perfil inactivo, auto-fiado cajero
        prod_off = Producto.objects.create(nombre="Plato Inactivo RF10", categoria=self.cat_m4, precio_base=Decimal('5000'), activo=False)
        for caso, emp, items_bad, reg_por, err_sub in [
            ('cantidad_cero', self.mesero_user, [{'producto_id': self.prod_9000.id, 'cantidad': 0}], self.cajero_user, "cantidad"),
            ('cantidad_negativa', self.mesero_user, [{'producto_id': self.prod_9000.id, 'cantidad': -2}], self.cajero_user, "cantidad"),
            ('producto_inactivo', self.mesero_user, [{'producto_id': prod_off.id, 'cantidad': 1}], self.cajero_user, "inactivo"),
            ('auto_fiado_cajero', self.cajero_user, [{'producto_id': self.prod_9000.id, 'cantidad': 1}], self.cajero_user, "anti-fraude"),
        ]:
            with self.subTest(consumo_rechazo=caso):
                with self.assertRaises(ValidationError) as ctx:
                    registrar_consumo_interno(empleado=emp, punto_venta=self.pv_central, items=items_bad, usuario_registro=reg_por)
                if err_sub != "cantidad":
                    self.assertIn(err_sub, str(ctx.exception).lower())

        # Desactivar usuario y luego perfil -> rechazados y restaurados
        self.mesero_user.is_active = False
        self.mesero_user.save()
        with self.assertRaises(ValidationError) as ctx_u:
            registrar_consumo_interno(empleado=self.mesero_user, punto_venta=self.pv_central, items=[{'producto_id': self.prod_9000.id, 'cantidad': 1}], usuario_registro=self.cajero_user)
        self.assertIn("inactivo", str(ctx_u.exception).lower())
        self.mesero_user.is_active = True
        self.mesero_user.save()
        self.mesero_user.perfil.activo = False
        self.mesero_user.perfil.save()
        with self.assertRaises(ValidationError) as ctx_p:
            registrar_consumo_interno(empleado=self.mesero_user, punto_venta=self.pv_central, items=[{'producto_id': self.prod_9000.id, 'cantidad': 1}], usuario_registro=self.cajero_user)
        self.assertIn("desactivado", str(ctx_p.exception).lower())
        self.mesero_user.perfil.activo = True
        self.mesero_user.perfil.save()

        # 3. Fiado >= $15.000 dispara AlertaTraslado obligatoria
        c_grande = registrar_consumo_interno(
            empleado=self.cajero_user, punto_venta=self.pv_central,
            items=[{'producto_id': self.prod_9000.id, 'cantidad': 2}],
            usuario_registro=self.admin_user, tipo_consumo='FIADO',
        )
        self.assertGreaterEqual(c_grande.total, Decimal('15000'))
        self.assertTrue(AlertaTraslado.objects.filter(motivo__contains="[AUDITORÍA FIADOS / CRÉDITO]").exists())

        # 4. Endpoint POS registrar_consumo_interno AJAX e historial + Liquidación planilla / Panel Admin y Anulación con motivo
        self.client.force_login(self.cajero_user)
        r_pos_fia = self.client.post(
            reverse('registrar_consumo_interno'),
            {
                'empleado_id': self.mesero_user.id,
                'tipo_consumo': 'FIADO',
                'observaciones': 'Almuerzo POS M4',
                'items_json': json.dumps([{'id': self.prod_9000.id, 'cantidad': 1}]),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(r_pos_fia.status_code, 200)
        d_fia = r_pos_fia.json()
        self.assertTrue(d_fia['ok'])
        self.assertIn('FIA-', d_fia['codigo_consumo'])
        c_pos_id = d_fia['consumo_id']

        # Verificar que ni el fiado POS haya creado Venta/DetalleVenta en la caja
        self.assertEqual(Venta.objects.count(), ventas_antes)
        self.assertEqual(DetalleVenta.objects.count(), detalles_antes)

        # Panel administración consumos e historial general
        self.client.force_login(self.admin_user)
        self.assertContains(self.client.get(reverse('administrador_consumos')), "CONSUMO INTERNO DEL PERSONAL")
        self.assertContains(self.client.get(reverse('administrador_historial')), f"FIA-{c1.id:04d}")

        # Liquidar c1 por planilla y luego liquidar restante de mesero desde panel admin
        self.assertEqual(liquidar_consumos_por_planilla([c1.id], supervisor=self.admin_user), 1)
        c1.refresh_from_db()
        self.assertEqual(c1.estado, 'DESCONTADO')
        self.assertEqual(c1.descontado_por, self.admin_user)
        self.assertEqual(self.mesero_user.perfil.total_fiado_pendiente(), Decimal('9000.00'))

        self.client.post(reverse('administrador_consumos'), {'accion': 'descontar_empleado', 'empleado_id': self.mesero_user.id})
        self.assertEqual(ConsumoInterno.objects.get(id=c_pos_id).estado, 'DESCONTADO')
        self.assertEqual(self.mesero_user.perfil.total_fiado_pendiente(), Decimal('0.00'))

        # Anulación consumo interno: motivo <5 chars rechazado, motivo válido aprobado + AlertaTraslado
        self.client.post(reverse('administrador_consumos'), {'accion': 'anular_individual', 'consumo_id': str(c_grande.id), 'motivo_anulacion': 'no'}, follow=True)
        c_grande.refresh_from_db()
        self.assertEqual(c_grande.estado, 'REGISTRADO')

        self.client.post(
            reverse('administrador_consumos'),
            {'accion': 'anular_individual', 'consumo_id': str(c_grande.id), 'motivo_anulacion': 'Pagó en efectivo en oficina'},
            follow=True,
        )
        c_grande.refresh_from_db()
        self.assertEqual(c_grande.estado, 'ANULADO')
        self.assertTrue(
            AlertaTraslado.objects.filter(autorizado_por=self.admin_user, motivo__contains=f"[ANULACIÓN CONSUMO INTERNO #{c_grande.id}]").exists()
        )
