import datetime as dt_mod
import gzip
import hashlib
import io
import json
import os
import socket
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from ventas.exportador_reportes import (
    generar_excel_ventas,
    generar_word_ventas,
    obtener_datos_reporte,
)
from ventas.models import (
    AlertaTraslado,
    Caja,
    Categoria,
    DetallePedido,
    DetalleVenta,
    Entrega,
    Jornada,
    Menu,
    Mesa,
    Pedido,
    PerfilEmpleado,
    Producto,
    PuntoImpresion,
    PuntoVenta,
    RegistroImpresion,
    Ticket,
    Venta,
)
from ventas.test_suites.base import SafariDemoTestCase, SafariIsolatedTestCase
from ventas.utils import (
    calcular_metricas_tiempos_pedido,
    calcular_tiempos_promedio_local,
    emitir_comprobante_venta,
    emitir_tickets_comanda,
    enviar_a_impresora,
    formatear_fecha_hora_chile,
    generar_reporte_estadistico_integral,
    registrar_entrega_pedido,
    reimprimir_ticket,
    reintentar_despacho_impresion,
    sanitizar_observacion,
)
from ventas.views import get_locales_data


class KdsCocinaBarraYComentariosTests(SafariDemoTestCase):
    """
    Suite consolidada de KDS Cocina Caliente, BDS Barra, Sincronización Delta, RF12 y RF13:
    - Aislamiento estricto Cocina vs Barra con Contraste Positivo vs Negativo y regresión Flexbox/UX.
    - Transiciones independientes por estación en pedidos mixtos, RBAC anti-fraude cancelación y RLS cruzado.
    - Delta Sync (`/api/sincronizacion/estado/`) y Control Stock KDS (`/api/kds/toggle-stock/`).
    - RF12 Comentarios e indicaciones (sanitización, longitud 200, escape XSS, aislamiento ítem/ronda, POS/KDS).
    - RF13 Entregas validadas, bloqueos de máquina de estados via `subTest`, multi-ronda y preservación de mesa OCUPADA.
    - Flujo integral Cajero -> Mesero -> Cocina -> Barra -> Cajero.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat_cocina = Categoria.objects.create(
            nombre="Platos Fuertes KDS M5",
            destino_defecto='COCINA',
            activo=True,
        )
        cls.cat_barra = Categoria.objects.create(
            nombre="Jugos y Cafetería M5",
            destino_defecto='BARRA',
            activo=True,
        )
        cls.prod_cocina = Producto.objects.create(
            nombre="Bife Safari KDS M5",
            categoria=cls.cat_cocina,
            precio_base=Decimal('8500'),
            destino_operativo='COCINA',
            activo=True,
        )
        cls.prod_cocina.puntos_venta.add(cls.pv_central)

        cls.prod_cocina_b = Producto.objects.create(
            nombre="Papas Bravas KDS M5",
            categoria=cls.cat_cocina,
            precio_base=Decimal('4200'),
            destino_operativo='COCINA',
            activo=True,
        )
        cls.prod_cocina_b.puntos_venta.add(cls.pv_central)

        cls.prod_barra = Producto.objects.create(
            nombre="Limonada Menta KDS M5",
            categoria=cls.cat_barra,
            precio_base=Decimal('3200'),
            destino_operativo='BARRA',
            activo=True,
        )
        cls.prod_barra.puntos_venta.add(cls.pv_central)

        cls.prod_otro_local = Producto.objects.create(
            nombre="Pizza Selva Remota M5",
            categoria=cls.cat_cocina,
            precio_base=Decimal('9000'),
            destino_operativo='COCINA',
            activo=True,
        )
        cls.prod_otro_local.puntos_venta.add(cls.pv_selva)

        for menu in Menu.objects.filter(punto_venta=cls.pv_central, activo=True):
            menu.productos.add(cls.prod_cocina, cls.prod_cocina_b, cls.prod_barra)

        cls.mesa_m1 = Mesa.objects.create(
            punto_venta=cls.pv_central,
            identificador="M-KDS-1",
            capacidad=4,
            estado='HABILITADA',
        )
        cls.mesa_m2 = Mesa.objects.create(
            punto_venta=cls.pv_central,
            identificador="M-KDS-2",
            capacidad=4,
            estado='HABILITADA',
        )
        cls.mesa_selva = Mesa.objects.create(
            punto_venta=cls.pv_selva,
            identificador="M-SELVA-KDS",
            capacidad=4,
            estado='HABILITADA',
        )

    def _crear_comanda(self, caja, mesa, items, modalidad='MESA', estado_venta='ABIERTA', estado_pedido='PENDIENTE', obs_pedido="Comanda Test"):
        total = sum((prod.precio_base * cant for prod, cant, _ in items), Decimal('0'))
        venta = Venta.objects.create(
            caja=caja,
            cajero=self.cajero_user,
            punto_venta=caja.punto_venta,
            modalidad=modalidad,
            mesa=mesa,
            total=total,
            estado=estado_venta,
            metodo_pago='EFECTIVO',
        )
        pedido = Pedido.objects.create(venta=venta, estado=estado_pedido, observaciones=obs_pedido)
        for prod, cant, nota in items:
            DetalleVenta.objects.create(
                venta=venta,
                producto=prod,
                cantidad=cant,
                precio_aplicado=prod.precio_base,
                subtotal=prod.precio_base * cant,
            )
            DetallePedido.objects.create(
                pedido=pedido,
                producto=prod,
                cantidad=cant,
                observaciones=nota,
            )
        emitir_tickets_comanda(pedido, usuario_emisor=self.mesero_user)
        return venta, pedido

    def test_kds_cocina_vs_barra_aislamiento_estricto_y_contraste(self):
        _, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, self.admin_user)
        self._crear_comanda(caja, self.mesa_m1, [(self.prod_cocina, 1, "Término medio")])
        self._crear_comanda(caja, self.mesa_m2, [(self.prod_barra, 2, "Poca azúcar")])

        self.client.force_login(self.cocinero_user)

        # Contraste Cocina: ve platos calientes y activos propios; nunca ruido decorativo de estación ni barra
        resp_cocina = self.client.get(reverse('cocina'))
        self.assertEqual(resp_cocina.status_code, 200)
        self.assertContrastePositivoNegativo(
            resp_cocina,
            debe_estar=(
                "KDS COCINA CALIENTE",
                "Bife Safari KDS M5",
                "Término medio",
                "css/kds/cocina.css",
                "js/global/toasts.js",
                "js/kds/cocina.js",
                "Modo Concentración",
            ),
            no_debe_estar=(
                "Estación Cocina Caliente",
                "Producción Gastronómica Exclusiva",
                "KDS En Vivo",
                "Bienvenido(a)",
                "Limonada Menta KDS M5",
                "Pizza Selva Remota M5",
                "Poca azúcar",
                "KDS BARRA & BEBIDAS",
                "css/kds/barra.css",
                "js/kds/barra.js",
                "Sesión: 15:00",
                "Actualizar Pantalla",
                "zona=BARRA",
            ),
            contexto="Monitor KDS Cocina Caliente",
        )

        # Contraste Barra: ve bebidas propias; nunca platos de cocina, ruido "Barra En Vivo" ni scripts de cocina
        resp_barra = self.client.get(reverse('barra'))
        self.assertEqual(resp_barra.status_code, 200)
        self.assertContrastePositivoNegativo(
            resp_barra,
            debe_estar=(
                "KDS BARRA & BEBIDAS",
                "Limonada Menta KDS M5",
                "Poca azúcar",
                "css/kds/barra.css",
                "js/global/toasts.js",
                "js/kds/barra.js",
                "Modo Concentración",
                "Sonido ON",
            ),
            no_debe_estar=(
                "Barra En Vivo",
                "Bienvenido(a)",
                "Bife Safari KDS M5",
                "Pizza Selva Remota M5",
                "Término medio",
                "KDS COCINA CALIENTE",
                "css/kds/cocina.css",
                "js/kds/cocina.js",
                "Sesión: 15:00",
                "Actualizar Pantalla",
            ),
            contexto="Monitor BDS Barra",
        )

        # Mensajes operativos en Cocina usan toast flotante breve en esquina (sin banner fijo superior)
        resp_aviso_kds = self.client.get(reverse('administrador'), follow=True)
        self.assertContrastePositivoNegativo(
            resp_aviso_kds,
            debe_estar=('role="region"', 'aria-label="Notificaciones"', 'data-bs-autohide="true"'),
            no_debe_estar=("alert-dismissible", "Bienvenido(a)"),
            contexto="Avisos en Cocina como toast flotante breve sin barra fija",
        )

        # Regresión Flexbox CSS KDS (no flex-column inválido) + script autoActualizarBarra
        cocina_css = Path(settings.BASE_DIR, 'static', 'css', 'kds', 'cocina.css').read_text(encoding='utf-8')
        barra_js = Path(settings.BASE_DIR, 'static', 'js', 'kds', 'barra.js').read_text(encoding='utf-8')
        self.assertIn('flex-direction: column', cocina_css)
        self.assertNotIn('flex-column: column', cocina_css)
        self.assertIn('autoActualizarBarra', barra_js)

        # Regresión inputs numéricos POS Caja sin value="0" prefijado
        self.client.force_login(self.cajero_user)
        resp_pos = self.client.get(reverse('vendedor'))
        self.assertEqual(resp_pos.status_code, 200)
        self.assertNotContains(resp_pos, 'value="0"')

    def test_transiciones_independientes_mixto_y_sincronizacion_delta(self):
        _, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, self.admin_user)
        _, ped_mixto = self._crear_comanda(
            caja,
            self.mesa_m1,
            [(self.prod_cocina, 1, None), (self.prod_barra, 1, None)],
        )

        # Pedido de otro local para verificar aislamiento RLS
        _, caja_selva = self.abrir_jornada_y_caja(self.pv_selva, self.cajera2_user, self.admin_user)
        _, ped_selva = self._crear_comanda(caja_selva, self.mesa_selva, [(self.prod_otro_local, 1, None)])

        self.client.force_login(self.cocinero_user)

        # Firma delta inicial para Cocina y Barra
        resp_sync_0 = self.client.get(reverse('api_sincronizacion_estado'), {'zona': 'COCINA'})
        self.assertEqual(resp_sync_0.status_code, 200)
        hash_inicial = resp_sync_0.json()['version']

        # Estación COCINA avanza a EN_PREPARACION y LISTO sin alterar BARRA
        for nuevo_est in ('EN_PREPARACION', 'LISTO'):
            r = self.client.post(
                reverse('cambiar_estado_pedido'),
                {'pedido_id': ped_mixto.id, 'nuevo_estado': nuevo_est, 'estacion': 'COCINA'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            self.assertEqual(r.status_code, 200)

        ped_mixto.refresh_from_db()
        self.assertEqual(ped_mixto.estado_cocina, 'LISTO')
        self.assertEqual(ped_mixto.estado_barra, 'PENDIENTE')
        self.assertEqual(ped_mixto.estado, 'EN_PREPARACION')

        resp_sync_1 = self.client.get(reverse('api_sincronizacion_estado'), {'zona': 'COCINA'})
        self.assertNotEqual(resp_sync_1.json()['version'], hash_inicial)

        # Estación BARRA avanza independientemente hasta LISTO -> Pedido global LISTO
        for nuevo_est in ('EN_PREPARACION', 'LISTO'):
            r = self.client.post(
                reverse('cambiar_estado_pedido'),
                {'pedido_id': ped_mixto.id, 'nuevo_estado': nuevo_est, 'estacion': 'BARRA'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            self.assertEqual(r.status_code, 200)

        ped_mixto.refresh_from_db()
        self.assertEqual(ped_mixto.estado_barra, 'LISTO')
        self.assertEqual(ped_mixto.estado, 'LISTO')

        # RLS cruzado: cocinero Central no puede mutar pedido de Selva ni consultar su sync
        r_rls_mut = self.client.post(
            reverse('cambiar_estado_pedido'),
            {'pedido_id': ped_selva.id, 'nuevo_estado': 'EN_PREPARACION'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_rls_mut.status_code, 403)
        r_rls_sync = self.client.get(reverse('api_sincronizacion_estado'), {'local_id': self.pv_selva.id})
        self.assertEqual(r_rls_sync.status_code, 403)

        # Anti-fraude cancelación directa: mesero y cajero bloqueados (403); cocinero autorizado
        for usr_bloqueado in (self.mesero_user, self.cajero_user):
            with self.subTest(rol_cancel_block=usr_bloqueado.username):
                self.client.force_login(usr_bloqueado)
                r_forb = self.client.post(
                    reverse('cambiar_estado_pedido'),
                    {'pedido_id': ped_mixto.id, 'nuevo_estado': 'CANCELADO'},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )
                self.assertEqual(r_forb.status_code, 403)

        self.client.force_login(self.cocinero_user)
        _, ped_cancelable = self._crear_comanda(
            caja, None, [(self.prod_cocina_b, 1, None)], modalidad='VENTA_RAPIDA'
        )
        r_ok_cancel = self.client.post(
            reverse('cambiar_estado_pedido'),
            {'pedido_id': ped_cancelable.id, 'nuevo_estado': 'CANCELADO', 'estacion': 'COCINA'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_ok_cancel.status_code, 200)
        ped_cancelable.refresh_from_db()
        self.assertEqual(ped_cancelable.estado, 'CANCELADO')

    def test_alertas_listos_delta_admin_y_zero_n1_en_estaciones(self):
        """
        Verifica optimización de latencia y señales auditivas Cocina/Barra -> Cajero/Mesero:
        - listos_detalle en /api/sincronizacion/estado/ emite keys por estación (COCINA / BARRA).
        - ?zona=ADMIN responde JSON liviano para Admin y bloquea (403) a otros roles.
        - Pedido.get_estaciones_activas() realiza 0 SQL queries cuando los detalles están prefetched.
        - Vistas operativas cargan motor unificado safari_audio_alerts.js y regiones accesibles.
        - SESSION_SAVE_EVERY_REQUEST=False evita escrituras SQL por polling.
        """
        self.assertFalse(settings.SESSION_SAVE_EVERY_REQUEST)

        _, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, self.admin_user)
        _, ped_mixto = self._crear_comanda(
            caja,
            self.mesa_m1,
            [(self.prod_cocina, 1, None), (self.prod_barra, 1, None)],
        )

        # Cero consultas extra en get_estaciones_activas() tras prefetch_related
        peds_pref = list(
            Pedido.objects.filter(id=ped_mixto.id).prefetch_related('detalles__producto__categoria')
        )
        with self.assertNumQueries(0):
            estaciones = peds_pref[0].get_estaciones_activas()
        self.assertEqual(estaciones, {'COCINA', 'BARRA'})

        # Cocina marca LISTO -> Cajero y Mesero reciben key COCINA inmediatamente en listos_detalle
        self.client.force_login(self.cocinero_user)
        for st in ('EN_PREPARACION', 'LISTO'):
            self.assertEqual(
                self.client.post(
                    reverse('cambiar_estado_pedido'),
                    {'pedido_id': ped_mixto.id, 'nuevo_estado': st, 'estacion': 'COCINA'},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                ).status_code,
                200,
            )

        self.client.force_login(self.mesero_user)
        r_sync_c = self.client.get(reverse('api_sincronizacion_estado'))
        self.assertEqual(r_sync_c.status_code, 200)
        self.assertEqual(r_sync_c.headers.get('Cache-Control'), 'no-store')
        d_c = r_sync_c.json()
        keys_c = [item['key'] for item in d_c.get('listos_detalle', [])]
        self.assertIn(f'{ped_mixto.id}:COCINA', keys_c)
        self.assertNotIn(f'{ped_mixto.id}:BARRA', keys_c)

        # Barra también marca LISTO -> version cambia y listos_detalle emite BARRA
        self.client.force_login(self.cocinero_user)
        for st in ('EN_PREPARACION', 'LISTO'):
            self.assertEqual(
                self.client.post(
                    reverse('cambiar_estado_pedido'),
                    {'pedido_id': ped_mixto.id, 'nuevo_estado': st, 'estacion': 'BARRA'},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                ).status_code,
                200,
            )

        self.client.force_login(self.cajero_user)
        r_sync_b = self.client.get(reverse('api_sincronizacion_estado'))
        self.assertEqual(r_sync_b.status_code, 200)
        d_b = r_sync_b.json()
        self.assertNotEqual(d_b['version'], d_c['version'])
        keys_b = [item['key'] for item in d_b.get('listos_detalle', [])]
        self.assertIn(f'{ped_mixto.id}:COCINA', keys_b)
        self.assertIn(f'{ped_mixto.id}:BARRA', keys_b)

        # RBAC en zona=ADMIN: solo ADMINISTRADOR autorizado
        for usr_no in (self.cajero_user, self.mesero_user, self.cocinero_user):
            with self.subTest(rol_admin_sync=usr_no.username):
                self.client.force_login(usr_no)
                self.assertEqual(
                    self.client.get(reverse('api_sincronizacion_estado'), {'zona': 'ADMIN'}).status_code,
                    403,
                )
        self.client.force_login(self.admin_user)
        r_admin_sync = self.client.get(reverse('api_sincronizacion_estado'), {'zona': 'ADMIN'})
        self.assertEqual(r_admin_sync.status_code, 200)
        self.assertTrue(r_admin_sync.json()['ok'])
        self.assertIn('alertas_no_leidas', r_admin_sync.json())

        # Integración HTML de motor de sonido unificado y toasts accesibles (Cajero monitor + POS crear_ticket + Mesero)
        self.client.force_login(self.cajero_user)
        resp_vend = self.client.get(reverse('vendedor'))
        self.assertContrastePositivoNegativo(
            resp_vend,
            debe_estar=('btnTogglePosAudio', 'safariReadyToastRegion', 'safariReadyAriaLive', 'safari_audio_alerts.js'),
            no_debe_estar=('value="0"',),
            contexto="Panel Cajero con audio y alertas accesibles",
        )
        resp_ct = self.client.get(reverse('crear_ticket'))
        self.assertContrastePositivoNegativo(
            resp_ct,
            debe_estar=('btnTogglePosAudio', 'safariReadyToastRegion', 'safariReadyAriaLive', 'safari_audio_alerts.js'),
            contexto="POS Crear Ticket con audio y alertas accesibles",
        )

        self.client.force_login(self.mesero_user)
        resp_mes = self.client.get(reverse('mesero'))
        self.assertContrastePositivoNegativo(
            resp_mes,
            debe_estar=('btnToggleMeseroAudio', 'safariReadyToastRegion', 'safariReadyAriaLive', 'safari_audio_alerts.js'),
            contexto="Panel Mesero con audio y alertas accesibles",
        )

    def test_control_stock_kds_toggle_y_rbac(self):
        # Roles de salón/caja no pueden pausar platos en KDS
        for usr_no in (self.mesero_user, self.cajero_user):
            with self.subTest(rol_no_stock=usr_no.username):
                self.client.force_login(usr_no)
                resp = self.client.post(
                    reverse('api_toggle_stock_producto'),
                    {'producto_id': self.prod_cocina.id},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )
                self.assertEqual(resp.status_code, 403)

        # Cocinero pausa y reactiva producto de su local generando AlertaTraslado [KDS STOCK]
        self.client.force_login(self.cocinero_user)
        resp_off = self.client.post(
            reverse('api_toggle_stock_producto'),
            {'producto_id': self.prod_cocina.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_off.status_code, 200)
        self.prod_cocina.refresh_from_db()
        self.assertFalse(self.prod_cocina.activo)
        self.assertTrue(
            AlertaTraslado.objects.filter(motivo__startswith='[KDS STOCK]').exists()
        )

        # RLS cruzado sobre producto exclusivo de otro local
        resp_cross = self.client.post(
            reverse('api_toggle_stock_producto'),
            {'producto_id': self.prod_otro_local.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_cross.status_code, 403)

        # Reactivar stock
        resp_on = self.client.post(
            reverse('api_toggle_stock_producto'),
            {'producto_id': self.prod_cocina.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_on.status_code, 200)
        self.prod_cocina.refresh_from_db()
        self.assertTrue(self.prod_cocina.activo)

    def test_rf12_comentarios_sanitizacion_xss_y_aislamiento_rondas(self):
        # 1. Sanitización de observaciones via subTest
        casos_san = [
            ("vacio", "   \t\n ", None),
            ("acentos_nulo", "Sin cebolla\x00 ni ají", "Sin cebolla ni ají"),
            ("longitud_200", "X" * 260, "X" * 200),
        ]
        for nombre, entrada, esperado in casos_san:
            with self.subTest(sanitizar=nombre):
                res = sanitizar_observacion(entrada)
                self.assertEqual(res, esperado)
                if res:
                    self.assertLessEqual(len(res), 200)

        # 2. XSS escaping al renderizar KDS y Tickets + aislamiento entre ítems y rondas POS/Mesero
        self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, self.admin_user)
        xss_nota = 'Sin sal <script>alert("xss")</script><img src=x onerror=alert(1)>'

        # Venta POS rápida con nota en ítem 1 y sin nota en ítem 2
        self.client.force_login(self.cajero_user)
        resp_pos = self.client.post(
            reverse('crear_ticket'),
            {
                'metodo_pago': 'EFECTIVO',
                'modalidad': 'VENTA_RAPIDA',
                'items_json': json.dumps([
                    {'producto_id': self.prod_cocina.id, 'cantidad': 1, 'nota': xss_nota},
                    {'producto_id': self.prod_cocina_b.id, 'cantidad': 1, 'nota': ''},
                ]),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_pos.status_code, 200)
        ped_pos = Pedido.objects.get(id=resp_pos.json()['pedido_id'])
        det1 = ped_pos.detalles.get(producto=self.prod_cocina)
        det2 = ped_pos.detalles.get(producto=self.prod_cocina_b)
        self.assertIn("Sin sal", det1.observaciones or '')
        self.assertFalse(det2.observaciones)

        # Ticket térmico y reimpresión conservan Nota
        tkt_pos = Ticket.objects.filter(pedido=ped_pos, tipo_destino='COCINA').first()
        self.assertIn("Sin sal", tkt_pos.contenido_impresion)
        reimprimir_ticket(tkt_pos, usuario_solicitante=self.cajero_user)
        self.assertIn("Sin sal", tkt_pos.contenido_impresion)

        # KDS escapa etiquetas peligrosas (contraste positivo vs negativo)
        self.client.force_login(self.cocinero_user)
        resp_kds = self.client.get(reverse('cocina'))
        self.assertContrastePositivoNegativo(
            resp_kds,
            debe_estar=("Sin sal", "lt;script"),
            no_debe_estar=('<script>alert("xss")</script>', '<img src=x onerror=alert(1)>'),
            contexto="Sanitización XSS de notas en KDS Cocina",
        )

        # Rondas independientes en Mesa desde Mesero
        self.client.force_login(self.mesero_user)
        self.client.post(
            reverse('mesero'),
            {
                'accion': 'enviar_comanda',
                'local_id': self.pv_central.id,
                'mesa_id': self.mesa_m1.id,
                'items_json': json.dumps([{'id': self.prod_cocina.id, 'cantidad': 1, 'nota': 'R1 Poco hecho'}]),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.client.post(
            reverse('mesero'),
            {
                'accion': 'enviar_comanda',
                'local_id': self.pv_central.id,
                'mesa_id': self.mesa_m1.id,
                'items_json': json.dumps([{'id': self.prod_barra.id, 'cantidad': 1, 'nota': 'R2 Sin hielo'}]),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        tkt_r1 = Ticket.objects.filter(pedido__venta__mesa=self.mesa_m1, tipo_destino='COCINA').first()
        tkt_r2 = Ticket.objects.filter(pedido__venta__mesa=self.mesa_m1, tipo_destino='BARRA').first()
        self.assertContrastePositivoNegativo(
            tkt_r1.contenido_impresion,
            debe_estar=("R1 Poco hecho",),
            no_debe_estar=("R2 Sin hielo",),
            contexto="Aislamiento nota Ronda 1 Cocina",
        )
        self.assertContrastePositivoNegativo(
            tkt_r2.contenido_impresion,
            debe_estar=("R2 Sin hielo",),
            no_debe_estar=("R1 Poco hecho",),
            contexto="Aislamiento nota Ronda 2 Barra",
        )

    def test_rf13_maquina_estados_entregas_y_bloqueos_subtest(self):
        _, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, self.admin_user)

        # Bloqueos de entrega prematura / cancelada mediante subTest
        for estado_invalido in ('PENDIENTE', 'EN_PREPARACION', 'CANCELADO'):
            with self.subTest(entrega_bloqueada=estado_invalido):
                _, ped_bad = self._crear_comanda(
                    caja, None, [(self.prod_cocina, 1, None)], modalidad='VENTA_RAPIDA', estado_pedido=estado_invalido
                )
                with self.assertRaises(ValidationError):
                    registrar_entrega_pedido(ped_bad, usuario_entrega=self.mesero_user)

        # Entrega válida LISTO -> ENTREGADO cierra ticket en FINALIZADO y mantiene mesa OCUPADA
        self.mesa_m1.estado = 'OCUPADA'
        self.mesa_m1.save()
        _, ped_ok = self._crear_comanda(caja, self.mesa_m1, [(self.prod_cocina, 1, None)], estado_pedido='PENDIENTE')
        self.client.force_login(self.cocinero_user)
        for st in ('EN_PREPARACION', 'LISTO'):
            self.client.post(
                reverse('cambiar_estado_pedido'),
                {'pedido_id': ped_ok.id, 'nuevo_estado': st, 'estacion': 'COCINA'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )

        self.client.force_login(self.mesero_user)
        resp_ent = self.client.post(
            reverse('cambiar_estado_pedido'),
            {'pedido_id': ped_ok.id, 'nuevo_estado': 'ENTREGADO'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_ent.status_code, 200)
        ped_ok.refresh_from_db()
        self.mesa_m1.refresh_from_db()
        self.assertEqual(ped_ok.estado, 'ENTREGADO')
        self.assertEqual(self.mesa_m1.estado, 'OCUPADA')
        self.assertEqual(ped_ok.tickets.filter(estado='FINALIZADO').count(), 1)
        self.assertEqual(Entrega.objects.filter(pedido=ped_ok, usuario_entrega=self.mesero_user).count(), 1)

        # Doble entrega rechazada tanto en servicio como HTTP AJAX 400
        with self.assertRaises(ValidationError):
            registrar_entrega_pedido(ped_ok, usuario_entrega=self.mesero_user)
        resp_dup = self.client.post(
            reverse('cambiar_estado_pedido'),
            {'pedido_id': ped_ok.id, 'nuevo_estado': 'ENTREGADO'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_dup.status_code, 400)

        # Entregas independientes por ronda en la misma cuenta abierta
        ped_r2 = Pedido.objects.create(venta=ped_ok.venta, estado='LISTO', observaciones="Ronda 2")
        e2 = registrar_entrega_pedido(ped_r2, usuario_entrega=self.mesero_user, observaciones="Entregada R2")
        e1 = Entrega.objects.get(pedido=ped_ok)
        self.assertNotEqual(e1.id, e2.id)
        self.assertEqual(e2.pedido, ped_r2)

    def test_flujo_integral_cajero_mesero_cocina_y_barra(self):
        # 1. Cajero abre jornada y caja
        self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, self.admin_user, fondo=40000)

        # 2. Mesero envía comanda mixta en salón
        self.client.force_login(self.mesero_user)
        resp_cmd = self.client.post(
            reverse('mesero'),
            {
                'accion': 'enviar_comanda',
                'local_id': self.pv_central.id,
                'mesa_id': self.mesa_m1.id,
                'items_json': json.dumps([
                    {'id': self.prod_cocina.id, 'cantidad': 1, 'nota': 'Al punto'},
                    {'id': self.prod_barra.id, 'cantidad': 1, 'nota': 'Sin menta'},
                ]),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_cmd.status_code, 200)
        ped = Pedido.objects.get(id=resp_cmd.json()['pedido_id'])
        self.assertEqual(ped.tickets.count(), 2)

        # 3. Cocina y Barra completan sus estaciones
        self.client.force_login(self.cocinero_user)
        for st in ('EN_PREPARACION', 'LISTO'):
            self.client.post(reverse('cambiar_estado_pedido'), {'pedido_id': ped.id, 'nuevo_estado': st, 'estacion': 'COCINA'})
            self.client.post(reverse('cambiar_estado_pedido'), {'pedido_id': ped.id, 'nuevo_estado': st, 'estacion': 'BARRA'})

        # 4. Mesero entrega
        self.client.force_login(self.mesero_user)
        self.client.post(reverse('cambiar_estado_pedido'), {'pedido_id': ped.id, 'nuevo_estado': 'ENTREGADO'})
        ped.refresh_from_db()
        self.assertEqual(ped.estado, 'ENTREGADO')

        # 5. Cajero cobra y libera la mesa (contraste: mesa_id inválido -> 400 JSON, mesa_id válido -> PAGADA + HABILITADA)
        self.client.force_login(self.cajero_user)
        resp_cobro_bad = self.client.post(
            reverse('vendedor'),
            {'accion': 'cobrar_cuenta_mesa', 'mesa_id': '', 'metodo_pago': 'EFECTIVO'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_cobro_bad.status_code, 400)

        resp_cobro = self.client.post(
            reverse('vendedor'),
            {
                'accion': 'cobrar_cuenta_mesa',
                'mesa_id': self.mesa_m1.id,
                'metodo_pago': 'EFECTIVO',
                'porcentaje_propina': '0',
            },
            follow=True,
        )
        self.assertEqual(resp_cobro.status_code, 200)
        ped.venta.refresh_from_db()
        self.mesa_m1.refresh_from_db()
        self.assertEqual(ped.venta.estado, 'PAGADA')
        self.assertEqual(self.mesa_m1.estado, 'HABILITADA')


class TicketsImpresionYTiemposAtencionTests(SafariIsolatedTestCase):
    """
    Suite consolidada de RF08 (Gobierno de Tickets), RF09 (Despacho Resiliente a Impresoras) y RF16 (Tiempos KDS):
    - Enrutamiento por destino operativo / categoría, cero desperdicio de papel, incrementalidad y reimpresión no contable.
    - Impresoras físicas RED vs DIGITAL, previsualización térmica, resiliencia ante fallo, reintento parcial, aislamiento multi-local y sanitización de errores socket RAW.
    - Cálculo de métricas RF16 (cola, preparación, despacho, total), validación cronológica y clamping ante desfase de reloj, cruce de medianoche, exclusión de incompletos/cancelados y promedios por local.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat_cocina = Categoria.objects.create(nombre="Carnes RF08", destino_defecto='COCINA', activo=True)
        cls.cat_barra = Categoria.objects.create(nombre="Bebidas RF08", destino_defecto='BARRA', activo=True)

        cls.prod_cocina = Producto.objects.create(
            nombre="Lomo Saltado RF08",
            categoria=cls.cat_cocina,
            precio_base=Decimal('8500'),
            destino_operativo='COCINA',
            activo=True,
        )
        cls.prod_cocina.puntos_venta.add(cls.pv)

        cls.prod_r2 = Producto.objects.create(
            nombre="Postre Helado RF08",
            categoria=cls.cat_cocina,
            precio_base=Decimal('4000'),
            destino_operativo='COCINA',
            activo=True,
        )
        cls.prod_r2.puntos_venta.add(cls.pv)

        cls.prod_barra = Producto.objects.create(
            nombre="Jugo Frambuesa RF08",
            categoria=cls.cat_barra,
            precio_base=Decimal('3200'),
            destino_operativo='BARRA',
            activo=True,
        )
        cls.prod_barra.puntos_venta.add(cls.pv)

        cls.prod_herencia = Producto.objects.create(
            nombre="Café Cortado Herencia",
            categoria=cls.cat_barra,
            precio_base=Decimal('2500'),
            destino_operativo='AUTO',
            activo=True,
        )
        cls.prod_herencia.puntos_venta.add(cls.pv)

        cls.mesa = Mesa.objects.create(punto_venta=cls.pv, identificador="M-RF08", capacidad=4, estado='HABILITADA')

        cls.imp_cocina = PuntoImpresion.objects.create(
            nombre="Térmica Cocina Central",
            punto_venta=cls.pv,
            tipo_destino='COCINA',
            tipo_conexion='DIGITAL',
            estado_operativo='ONLINE',
            activo=True,
        )
        cls.imp_barra = PuntoImpresion.objects.create(
            nombre="Térmica Barra Central",
            punto_venta=cls.pv,
            tipo_destino='BARRA',
            tipo_conexion='DIGITAL',
            estado_operativo='ONLINE',
            activo=True,
        )
        cls.imp_comp = PuntoImpresion.objects.create(
            nombre="Térmica Caja Central",
            punto_venta=cls.pv,
            tipo_destino='COMPROBANTE',
            tipo_conexion='DIGITAL',
            estado_operativo='ONLINE',
            activo=True,
        )
        cls.imp_cocina_sec = PuntoImpresion.objects.create(
            nombre="Térmica Cocina Local 2",
            punto_venta=cls.pv_secundario,
            tipo_destino='COCINA',
            tipo_conexion='DIGITAL',
            estado_operativo='ONLINE',
            activo=True,
        )

    def test_rf08_enrutamiento_cero_desperdicio_incremental_y_reimpresion(self):
        self.assertEqual(self.prod_herencia.get_destino_operativo(), 'BARRA')
        _, caja = self.abrir_jornada_y_caja(self.pv, self.cajero_user, self.admin_user)

        # Pedido vacío falla con ValidationError
        venta = Venta.objects.create(
            caja=caja, cajero=self.cajero_user, punto_venta=self.pv, modalidad='MESA',
            mesa=self.mesa, total=Decimal('25000'), estado='ABIERTA',
        )
        ped_vacio = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        with self.assertRaises(ValidationError):
            emitir_tickets_comanda(ped_vacio, usuario_emisor=self.mesero_user)

        # Solo cocina: cero ticket de barra
        ped_coc = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=ped_coc, producto=self.prod_cocina, cantidad=1)
        res_coc = emitir_tickets_comanda(ped_coc, usuario_emisor=self.mesero_user)
        self.assertEqual([t.tipo_destino for t in res_coc['tickets']], ['COCINA'])

        # Solo barra: cero ticket de cocina
        ped_bar = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=ped_bar, producto=self.prod_barra, cantidad=1)
        res_bar = emitir_tickets_comanda(ped_bar, usuario_emisor=self.mesero_user)
        self.assertEqual([t.tipo_destino for t in res_bar['tickets']], ['BARRA'])

        # Pedido mixto: separación exclusiva con Contraste Positivo vs Negativo
        ped_mix = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=ped_mix, producto=self.prod_cocina, cantidad=1)
        DetallePedido.objects.create(pedido=ped_mix, producto=self.prod_barra, cantidad=2)
        res_mix = emitir_tickets_comanda(ped_mix, usuario_emisor=self.mesero_user)
        tkt_c = next(t for t in res_mix['tickets'] if t.tipo_destino == 'COCINA')
        tkt_b = next(t for t in res_mix['tickets'] if t.tipo_destino == 'BARRA')
        self.assertContrastePositivoNegativo(
            tkt_c.contenido_impresion,
            debe_estar=("Lomo Saltado RF08",),
            no_debe_estar=("Jugo Frambuesa RF08",),
            contexto="Ticket Cocina no filtra ítem de Barra",
        )
        self.assertContrastePositivoNegativo(
            tkt_b.contenido_impresion,
            debe_estar=("Jugo Frambuesa RF08",),
            no_debe_estar=("Lomo Saltado RF08",),
            contexto="Ticket Barra no filtra ítem de Cocina",
        )

        # Ronda 2 incremental: NO repite Lomo Saltado de rondas previas
        ped_r2 = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=ped_r2, producto=self.prod_r2, cantidad=1)
        tkt_r2 = emitir_tickets_comanda(ped_r2, usuario_emisor=self.mesero_user)['tickets'][0]
        self.assertContrastePositivoNegativo(
            tkt_r2.contenido_impresion,
            debe_estar=("Postre Helado RF08",),
            no_debe_estar=("Lomo Saltado RF08",),
            contexto="Incrementalidad Ronda 2",
        )

        # Comprobante fiscal TKT-VEN y Reimpresión HTTP sin duplicar Venta
        DetalleVenta.objects.create(
            venta=venta, producto=self.prod_cocina, cantidad=1,
            precio_aplicado=Decimal('8500'), subtotal=Decimal('8500'),
        )
        comp = emitir_comprobante_venta(venta, usuario_emisor=self.cajero_user)
        self.assertEqual(comp.codigo, f"TKT-VEN-{venta.id:05d}")
        self.assertEqual(comp.tipo_destino, 'COMPROBANTE')

        ventas_antes = Venta.objects.count()
        detalles_antes = DetalleVenta.objects.count()
        self.client.force_login(self.cajero_user)
        resp_re = self.client.post(
            reverse('reimprimir_ticket', args=[tkt_c.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_re.status_code, 200)
        tkt_c.refresh_from_db()
        self.assertTrue(tkt_c.es_reimpresion)
        self.assertEqual(tkt_c.numero_reimpresiones, 1)
        self.assertEqual(Venta.objects.count(), ventas_antes)
        self.assertEqual(DetalleVenta.objects.count(), detalles_antes)

    def test_rf09_despacho_impresoras_digital_fallo_reintento_parcial_y_seguridad_red(self):
        _, caja = self.abrir_jornada_y_caja(self.pv, self.cajero_user, self.admin_user)
        venta = Venta.objects.create(
            caja=caja, cajero=self.cajero_user, punto_venta=self.pv, modalidad='MESA',
            mesa=self.mesa, total=Decimal('11700'), estado='ABIERTA',
        )
        ped = Pedido.objects.create(venta=venta, estado='PENDIENTE')
        DetallePedido.objects.create(pedido=ped, producto=self.prod_cocina, cantidad=1)
        DetallePedido.objects.create(pedido=ped, producto=self.prod_barra, cantidad=1)

        # 1. Impresión parcial: Cocina ONLINE (OK) y Barra OFFLINE (FALLO)
        self.imp_barra.estado_operativo = 'OFFLINE'
        self.imp_barra.save()
        res = emitir_tickets_comanda(ped, usuario_emisor=self.mesero_user)
        tkt_coc = next(t for t in res['tickets'] if t.tipo_destino == 'COCINA')
        tkt_bar = next(t for t in res['tickets'] if t.tipo_destino == 'BARRA')
        self.assertEqual(tkt_coc.estado_impresion, 'IMPRESO')
        self.assertEqual(tkt_bar.estado_impresion, 'FALLO')
        self.assertTrue(RegistroImpresion.objects.filter(ticket=tkt_coc, exitoso=True, modo='DIGITAL').exists())
        self.assertTrue(RegistroImpresion.objects.filter(ticket=tkt_bar, exitoso=False).exists())
        # Venta y pedido preservados pese al fallo de hardware
        self.assertEqual(Venta.objects.filter(id=venta.id).count(), 1)

        # 2. Previsualización térmica digital (Cocina OK vs Barra FALLO)
        self.client.force_login(self.cajero_user)
        resp_dig_ok = self.client.get(reverse('ver_imprimir_ticket_digital', args=[tkt_coc.id]))
        self.assertContrastePositivoNegativo(
            resp_dig_ok,
            debe_estar=("impresion/ticket_digital.js", 'data-safari-action="print"', "Despachado OK"),
            no_debe_estar=("Fallo de Impresión",),
            contexto="Previsualización ticket digital despachado OK",
        )
        resp_dig_err = self.client.get(reverse('ver_imprimir_ticket_digital', args=[tkt_bar.id]))
        self.assertContrastePositivoNegativo(
            resp_dig_err,
            debe_estar=("Fallo de Impresión", "Reintentar Despacho Ahora"),
            no_debe_estar=("Despachado OK",),
            contexto="Previsualización ticket en FALLO con botón de reintento",
        )

        # 3. Reintento selectivo Barra (Cocina NO se re-imprime)
        self.imp_barra.estado_operativo = 'ONLINE'
        self.imp_barra.save()
        intentos_coc_antes = tkt_coc.intentos_impresion
        resp_reint = self.client.post(
            reverse('reintentar_impresion', args=[tkt_bar.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_reint.status_code, 200)
        self.assertTrue(resp_reint.json()['ok'])
        tkt_bar.refresh_from_db()
        tkt_coc.refresh_from_db()
        self.assertEqual(tkt_bar.estado_impresion, 'IMPRESO')
        self.assertIsNone(tkt_bar.error_impresion)
        self.assertEqual(tkt_bar.intentos_impresion, 2)
        self.assertEqual(tkt_coc.intentos_impresion, intentos_coc_antes)
        self.assertTrue(RegistroImpresion.objects.filter(ticket=tkt_bar, es_reintento=True, exitoso=True).exists())

        # 4. Seguridad RAW Socket 9100 (Ola 3): error de red nunca filtra IP, puerto ni mensaje interno socket
        self.imp_cocina.tipo_conexion = 'RED'
        self.imp_cocina.direccion_ip = '192.168.99.200'
        self.imp_cocina.puerto = 9100
        self.imp_cocina.save()

        with patch('socket.socket') as mock_sock:
            mock_sock.return_value.connect.side_effect = OSError("timed out connecting 192.168.99.200:9100")
            res_net = enviar_a_impresora(tkt_coc, usuario=self.cajero_user, forzar_reintento=True)

        self.assertFalse(res_net['exito'])
        tkt_coc.refresh_from_db()
        reg_net = RegistroImpresion.objects.filter(ticket=tkt_coc, exitoso=False).order_by('-id').first()
        for campo_err in (tkt_coc.error_impresion or '', reg_net.mensaje_error or ''):
            self.assertContrastePositivoNegativo(
                campo_err,
                debe_estar=("Error de conexión con impresora térmica de red",),
                no_debe_estar=("192.168.99.200", "9100", "timed out"),
                contexto="Sanitización de error de red RAW 9100",
            )

        # Aislamiento multi-local de impresoras
        self.assertNotEqual(self.imp_cocina.id, self.imp_cocina_sec.id)
        self.assertEqual(self.imp_cocina_sec.punto_venta, self.pv_secundario)

    def test_rf16_ciclo_tiempos_skew_y_en_curso_vs_finalizado(self):
        _, caja = self.abrir_jornada_y_caja(self.pv, self.cajero_user, self.admin_user)
        venta = Venta.objects.create(
            caja=caja, cajero=self.cajero_user, punto_venta=self.pv, modalidad='MESA',
            mesa=self.mesa, total=Decimal('8500'), estado='ABIERTA',
        )

        # 1. Ciclo cronológico completo: T0=0m, prep=5m, listo=15m, entrega=20m
        t0 = timezone.now() - dt_mod.timedelta(minutes=30)
        ped = Pedido.objects.create(venta=venta, estado='LISTO')
        entrega = registrar_entrega_pedido(ped, usuario_entrega=self.mesero_user)
        Pedido.objects.filter(id=ped.id).update(
            creado_en=t0,
            fecha_inicio_preparacion=t0 + dt_mod.timedelta(minutes=5),
            fecha_listo=t0 + dt_mod.timedelta(minutes=15),
        )
        Entrega.objects.filter(id=entrega.id).update(fecha_hora_entrega=t0 + dt_mod.timedelta(minutes=20))
        ped.refresh_from_db()
        entrega.refresh_from_db()

        valido, inconsistencias = ped.validar_orden_temporal()
        self.assertTrue(valido)
        self.assertEqual(inconsistencias, [])
        self.assertEqual(ped.get_tiempo_cola_minutos(), 5.0)
        self.assertEqual(ped.get_tiempo_preparacion_minutos(), 10.0)
        self.assertEqual(ped.get_tiempo_despacho_minutos(), 5.0)
        self.assertEqual(ped.get_tiempo_espera_total_minutos(), 20.0)
        self.assertEqual(entrega.get_tiempo_desde_listo_minutos(), 5.0)
        self.assertEqual(entrega.get_tiempo_desde_creacion_minutos(), 20.0)

        met = calcular_metricas_tiempos_pedido(ped)
        self.assertEqual(met['tiempo_espera_total_minutos'], 20.0)
        self.assertIn('/', met['creado_en_chile'])

        # 2. Cruce de medianoche (23:50 -> 00:15 = 25.0 min)
        t_noche = timezone.make_aware(dt_mod.datetime(2026, 11, 10, 23, 50, 0))
        ped_noche = Pedido.objects.create(venta=venta, estado='LISTO')
        ent_noche = registrar_entrega_pedido(ped_noche, usuario_entrega=self.mesero_user)
        Pedido.objects.filter(id=ped_noche.id).update(creado_en=t_noche)
        Entrega.objects.filter(id=ent_noche.id).update(fecha_hora_entrega=t_noche + dt_mod.timedelta(minutes=25))
        ped_noche.refresh_from_db()
        self.assertEqual(ped_noche.get_tiempo_espera_total_minutos(), 25.0)

        # 3. Desfase de reloj invertido: validar_orden_temporal detecta >=3 anomalías y clamping >= 0.0
        ped_skew = Pedido.objects.create(venta=venta, estado='LISTO')
        ent_skew = registrar_entrega_pedido(ped_skew, usuario_entrega=self.mesero_user)
        Pedido.objects.filter(id=ped_skew.id).update(
            creado_en=t0,
            fecha_inicio_preparacion=t0 - dt_mod.timedelta(minutes=10),
            fecha_listo=t0 - dt_mod.timedelta(minutes=20),
        )
        Entrega.objects.filter(id=ent_skew.id).update(fecha_hora_entrega=t0 - dt_mod.timedelta(minutes=30))
        ped_skew.refresh_from_db()
        valido_sk, inc_sk = ped_skew.validar_orden_temporal()
        self.assertFalse(valido_sk)
        self.assertGreaterEqual(len(inc_sk), 3)
        self.assertGreaterEqual(ped_skew.get_tiempo_espera_total_minutos(), 0.0)

        # 4. Estados incompletos/cancelados: en_curso=False NO inventa tiempos (retorna None)
        for st in ('PENDIENTE', 'EN_PREPARACION', 'LISTO', 'CANCELADO'):
            with self.subTest(incompleto_estado=st):
                p_inc = Pedido.objects.create(venta=venta, estado=st)
                Pedido.objects.filter(id=p_inc.id).update(creado_en=timezone.now() - dt_mod.timedelta(minutes=8))
                p_inc.refresh_from_db()
                self.assertIsNone(p_inc.get_tiempo_espera_total_minutos(en_curso=False))
                if st != 'CANCELADO':
                    self.assertGreaterEqual(p_inc.get_tiempo_espera_total_minutos(en_curso=True), 7.5)

        # 5. Formateo de fecha Chile (aware, naive, None)
        self.assertIsNone(formatear_fecha_hora_chile(None))
        naive_dt = dt_mod.datetime(2026, 11, 14, 15, 30, 0)
        self.assertIn("14/11/2026", formatear_fecha_hora_chile(naive_dt))

    def test_rf16_promedios_local_y_vistas_admin_historial_local(self):
        _, caja = self.abrir_jornada_y_caja(self.pv, self.cajero_user, self.admin_user)
        venta = Venta.objects.create(
            caja=caja, cajero=self.cajero_user, punto_venta=self.pv, modalidad='MESA',
            mesa=self.mesa, total=Decimal('17000'), estado='ABIERTA',
        )
        base = timezone.now() - dt_mod.timedelta(minutes=40)

        # R1 (10m) y R2 (20m) entregados -> promedio espera 15.0m; R3 pendiente y R4 cancelado ignorados
        for idx, dur in enumerate((10, 20), start=1):
            p = Pedido.objects.create(venta=venta, estado='LISTO', observaciones=f"R{idx}")
            e = registrar_entrega_pedido(p, usuario_entrega=self.mesero_user)
            Pedido.objects.filter(id=p.id).update(
                creado_en=base,
                fecha_inicio_preparacion=base + dt_mod.timedelta(minutes=2),
                fecha_listo=base + dt_mod.timedelta(minutes=dur - 2),
            )
            Entrega.objects.filter(id=e.id).update(fecha_hora_entrega=base + dt_mod.timedelta(minutes=dur))

        Pedido.objects.create(venta=venta, estado='PENDIENTE', observaciones="Ruido incompleto")
        Pedido.objects.create(venta=venta, estado='CANCELADO', observaciones="Ruido cancelado")

        prom = calcular_tiempos_promedio_local(punto_venta=self.pv)
        self.assertEqual(prom['total_entregados'], 2)
        self.assertEqual(prom['total_cancelados'], 1)
        self.assertEqual(prom['promedio_tiempo_espera_total_minutos'], 15.0)

        # Vistas HTML de Administrador: Historial y Local exponen tiempos reales
        self.client.force_login(self.admin_user)
        resp_hist = self.client.get(reverse('administrador_historial'))
        self.assertContains(resp_hist, "Prep:")

        resp_local = self.client.get(reverse('administrador_local', args=[self.pv.id]))
        self.assertIn('promedios_tiempos', resp_local.context)
        self.assertContains(resp_local, "Espera Total Promedio")


class ReportesEstadisticasYGestionAdminTests(SafariIsolatedTestCase):
    """
    Suite consolidada de RF18 Analytics BI, Contabilidad Neta real, Exportadores, Historial, Gestión y Backup:
    - Cero mocks sobre BD limpia (`0` ingresos, `0` tickets, nunca valores heredados ficticios).
    - Filtros por rango (e inversión automática), punto de venta, usuario, modalidad, exclusión estricta de ANULADA,
      ranking histórico incluyendo productos desactivados y desglose de precios especiales/ahorro.
    - Separación PAGADA vs ABIERTA en `get_locales_data()` y contabilidad tributaria neta (sin IVA/propina/redondeo en ganancia).
    - Exportaciones binarias reales `.xlsx`, `.docx` y vista `.pdf` + RBAC estricto.
    - Historial unificado (`JOR-A`, `CAJ-A`, `VEN-`, `TRA-`, `ENT-`), Gestión 4 áreas (`?tab=`) y `backup_safari` `.gz`+`.sha256`.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cat = Categoria.objects.create(nombre="Gastronomía Reporte M5", activo=True)
        cls.prod_activo = Producto.objects.create(
            nombre="Menú Safari Reporte", categoria=cls.cat, precio_base=Decimal('10000'), activo=True
        )
        cls.prod_activo.puntos_venta.add(cls.pv, cls.pv_secundario)

        cls.prod_desactivado = Producto.objects.create(
            nombre="Plato Histórico Desactivado", categoria=cls.cat, precio_base=Decimal('3000'), activo=False
        )

        cls.cajera_alt = User.objects.create_user(username='cajera_alt_m5', password='Password123!')
        PerfilEmpleado.objects.create(
            usuario=cls.cajera_alt, rol='CAJERO', rut='44.444.444-5',
            punto_venta_actual=cls.pv_secundario, activo=True, debe_cambiar_clave=False,
        )
        cls.cocinero_iso = User.objects.create_user(username='cocinero_m5', password='Password123!')
        PerfilEmpleado.objects.create(
            usuario=cls.cocinero_iso, rol='COCINERO', rut='55.555.555-6',
            punto_venta_actual=cls.pv, activo=True, debe_cambiar_clave=False,
        )
        cls.mesa_pv1 = Mesa.objects.create(punto_venta=cls.pv, identificador="M-REP-1", capacidad=4, estado='HABILITADA')
        cls.mesa_pv2 = Mesa.objects.create(punto_venta=cls.pv_secundario, identificador="M-REP-2", capacidad=4, estado='HABILITADA')

    def test_rf18_cero_mocks_y_filtros_dinamicos_db(self):
        # 1. BD vacía debe reportar estrictamente 0 (Contraste contra datos simulados legacy $49.5M / 84 tickets)
        rep_vacio = generar_reporte_estadistico_integral()
        exp_vacio = obtener_datos_reporte(tipo_rango='mes')
        self.assertEqual(rep_vacio['ventas']['total_recaudado'], 0)
        self.assertEqual(rep_vacio['ventas']['cantidad_ventas'], 0)
        self.assertEqual(exp_vacio['total_ventas'], 0)
        self.assertNotEqual(exp_vacio['total_tickets'], 84)

        _, caja1 = self.abrir_jornada_y_caja(self.pv, self.cajero_user, self.admin_user)
        _, caja2 = self.abrir_jornada_y_caja(self.pv_secundario, self.cajera_alt, self.admin_user)

        hoy = timezone.localdate()
        ayer = hoy - dt_mod.timedelta(days=1)
        t_ayer = timezone.make_aware(dt_mod.datetime.combine(ayer, dt_mod.time(14, 0)))

        # Venta 1 hoy PV1 Cajero1 Débito Venta Rápida ($70.000)
        v1 = Venta.objects.create(
            caja=caja1, punto_venta=self.pv, cajero=self.cajero_user,
            total=Decimal('70000'), estado='PAGADA', metodo_pago='TARJETA_DEBITO', modalidad='VENTA_RAPIDA',
        )
        DetalleVenta.objects.create(venta=v1, producto=self.prod_activo, cantidad=5, precio_aplicado=Decimal('10000'), subtotal=Decimal('50000'))
        # 2 ítems con convenio/precio especial (original 10000 -> aplicado 7000 => ahorro 6000)
        DetalleVenta.objects.create(
            venta=v1, producto=self.prod_activo, cantidad=2, precio_aplicado=Decimal('7000'),
            subtotal=Decimal('14000'), es_precio_especial=True, precio_original=Decimal('10000'),
            motivo_precio_especial='CONVENIO',
        )

        # Venta 2 ayer PV2 CajeraAlt Efectivo Mesa ($30.000) incluyendo producto histórico DESACTIVADO
        v2 = Venta.objects.create(
            caja=caja2, punto_venta=self.pv_secundario, cajero=self.cajera_alt,
            total=Decimal('30000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='MESA',
            mesa=self.mesa_pv2,
        )
        Venta.objects.filter(id=v2.id).update(fecha_hora=t_ayer)
        DetalleVenta.objects.create(venta=v2, producto=self.prod_desactivado, cantidad=10, precio_aplicado=Decimal('3000'), subtotal=Decimal('30000'))

        # Venta 3 ANULADA ($999.000): debe sumar a cantidad_anuladas pero NUNCA al total recaudado
        Venta.objects.create(
            caja=caja1, punto_venta=self.pv, cajero=self.cajero_user,
            total=Decimal('999000'), estado='ANULADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA',
        )

        # Consolidado global
        rep_all = generar_reporte_estadistico_integral(fecha_inicio=ayer, fecha_fin=hoy)
        self.assertEqual(rep_all['ventas']['total_recaudado'], 100000)
        self.assertEqual(rep_all['ventas']['cantidad_ventas'], 2)
        self.assertEqual(rep_all['ventas']['cantidad_anuladas'], 1)
        self.assertEqual(rep_all['ventas']['total_items_precio_especial'], 1)
        self.assertEqual(rep_all['ventas']['ahorro_descuentos'], 6000)

        # Desgloses por método de pago y modalidad
        metodos = {m['metodo_pago']: m for m in rep_all['ventas']['ventas_por_metodo']}
        modalidades = {m['modalidad']: m for m in rep_all['ventas']['ventas_por_modalidad']}
        self.assertEqual(metodos['TARJETA_DEBITO']['porcentaje'], 70.0)
        self.assertEqual(metodos['EFECTIVO']['porcentaje'], 30.0)
        self.assertEqual(modalidades['VENTA_RAPIDA']['total'], 70000)
        self.assertEqual(modalidades['MESA']['total'], 30000)

        # Ranking incluye producto desactivado histórico ordenado por unidades (10 > 7)
        ranking = rep_all['ranking_productos']
        self.assertEqual(ranking[0]['nombre'], self.prod_desactivado.nombre)
        self.assertFalse(ranking[0]['activo'])
        self.assertEqual(ranking[0]['total_unidades'], 10)

        # Matriz subTest de filtros (rango fecha, inversión automática, local, usuario, modalidad)
        casos_filtros = [
            ("solo_hoy", {'fecha_inicio': hoy, 'fecha_fin': hoy}, 70000, 1),
            ("rango_invertido", {'fecha_inicio': hoy, 'fecha_fin': ayer}, 100000, 2),
            ("por_local_pv2", {'fecha_inicio': ayer, 'fecha_fin': hoy, 'punto_venta': self.pv_secundario.id}, 30000, 1),
            ("por_usuario_alt", {'fecha_inicio': ayer, 'fecha_fin': hoy, 'usuario': self.cajera_alt.id}, 30000, 1),
            ("por_modalidad_mesa", {'fecha_inicio': ayer, 'fecha_fin': hoy, 'modalidad': 'MESA'}, 30000, 1),
        ]
        for etiqueta, kwargs, total_esp, cant_esp in casos_filtros:
            with self.subTest(filtro=etiqueta):
                r = generar_reporte_estadistico_integral(**kwargs)
                self.assertEqual(r['ventas']['total_recaudado'], total_esp)
                self.assertEqual(r['ventas']['cantidad_ventas'], cant_esp)

    def test_contabilidad_neta_y_locales_data_sin_inflacion_iva_propina(self):
        _, caja = self.abrir_jornada_y_caja(self.pv, self.cajero_user, self.admin_user)

        # 1. Separación PAGADA vs ABIERTA en get_locales_data
        Venta.objects.create(
            caja=caja, punto_venta=self.pv, cajero=self.cajero_user,
            total=Decimal('15000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA',
        )
        Venta.objects.create(
            caja=caja, punto_venta=self.pv, cajero=self.cajero_user,
            total=Decimal('9000'), estado='ABIERTA', metodo_pago='EFECTIVO', modalidad='MESA',
            mesa=self.mesa_pv1,
        )
        locales_data = get_locales_data()
        self.assertEqual(locales_data[self.pv.id]['total_ventas'], 15000)
        self.assertEqual(locales_data[self.pv.id]['comandas_abiertas'], 1)

        # 2. Contabilidad tributaria chilena: neto sin IVA vs propina y redondeo (solo sobre venta controlada)
        Venta.objects.all().delete()
        Venta.objects.create(
            caja=caja,
            punto_venta=self.pv,
            cajero=self.cajero_user,
            total=Decimal('13086'),
            total_sin_redondeo=Decimal('13090'),
            propina=Decimal('1190'),
            redondeo_ley_20956=Decimal('-4'),
            estado='PAGADA',
            metodo_pago='EFECTIVO',
            modalidad='VENTA_RAPIDA',
        )
        rep = generar_reporte_estadistico_integral()
        self.assertEqual(rep['ventas']['total_recaudado'], 13086)
        self.assertEqual(rep['ventas']['total_consumo_bruto'], 11900)
        self.assertEqual(rep['ventas']['total_neto_sin_iva'], 10000)
        self.assertEqual(rep['ventas']['total_iva_19'], 1900)
        self.assertEqual(rep['ventas']['total_propinas'], 1190)
        self.assertEqual(rep['ventas']['total_redondeo_ley'], -4)
        self.assertEqual(rep['chart_data']['meses']['ganancias'][-1], 4600)

        datos_exp = obtener_datos_reporte(tipo_rango='mes')
        self.assertEqual(datos_exp['total_neto_sin_iva'], 10000)
        self.assertEqual(datos_exp['total_iva_19'], 1900)
        self.assertEqual(datos_exp['total_propinas'], 1190)
        self.assertEqual(datos_exp['total_redondeo'], -4)
        self.assertEqual(datos_exp['ganancia_estimada'], 4600)

    def test_rf18_exportaciones_excel_word_pdf_y_dashboard_rbac(self):
        _, caja = self.abrir_jornada_y_caja(self.pv, self.cajero_user, self.admin_user)
        Venta.objects.create(
            caja=caja, punto_venta=self.pv, cajero=self.cajero_user,
            total=Decimal('25000'), estado='PAGADA', metodo_pago='TARJETA_DEBITO', modalidad='VENTA_RAPIDA',
        )

        # Exportadores unitarios Excel y Word válidos
        datos = obtener_datos_reporte(tipo_rango='mes')
        xlsx_io = generar_excel_ventas(datos)
        docx_io = generar_word_ventas(datos)
        self.assertTrue(xlsx_io.getvalue().startswith(b'PK'))
        self.assertTrue(docx_io.getvalue().startswith(b'PK'))

        # RBAC Dashboard & Exportar bloqueado para operativos
        for usr_no in (self.cajero_user, self.mesero_user):
            with self.subTest(rbac_dash_block=usr_no.username):
                self.client.force_login(usr_no)
                r_dash = self.client.get(reverse('administrador_dashboard'))
                self.assertEqual(r_dash.status_code, 302)
                r_exp = self.client.get(reverse('exportar_reporte_ventas'), {'formato': 'excel'})
                self.assertEqual(r_exp.status_code, 302)

        # Admin renderiza Dashboard real sin valores simulados y descarga los 3 formatos
        self.client.force_login(self.admin_user)
        resp_dash = self.client.get(reverse('administrador_dashboard'))
        self.assertEqual(resp_dash.status_code, 200)
        self.assertContrastePositivoNegativo(
            resp_dash,
            debe_estar=("25.000",),
            no_debe_estar=("49.5M", "$49.5"),
            contexto="Dashboard Admin con datos reales sin mocks",
        )

        for fmt, content_sub in (
            ('excel', 'spreadsheetml'),
            ('word', 'wordprocessingml'),
            ('pdf', 'text/html'),
        ):
            with self.subTest(export_fmt=fmt):
                r = self.client.get(reverse('exportar_reporte_ventas'), {'formato': fmt, 'tipo_rango': 'mes'})
                self.assertEqual(r.status_code, 200)
                self.assertIn(content_sub, r['Content-Type'])

    def test_administrador_historial_y_gestion_unificada_rbac_y_filtros(self):
        _, caja = self.abrir_jornada_y_caja(self.pv, self.cajero_user, self.admin_user)
        venta = Venta.objects.create(
            caja=caja, punto_venta=self.pv, cajero=self.cajero_user,
            total=Decimal('18000'), estado='PAGADA', metodo_pago='EFECTIVO', modalidad='VENTA_RAPIDA',
        )
        AlertaTraslado.objects.create(
            empleado=self.mesero_user,
            punto_venta_origen=self.pv,
            punto_venta_destino=self.pv_secundario,
            autorizado_por=self.admin_user,
            motivo="Refuerzo almuerzo",
        )
        ped = Pedido.objects.create(venta=venta, estado='LISTO')
        registrar_entrega_pedido(ped, usuario_entrega=self.mesero_user)

        # RBAC: operativos y anónimos bloqueados
        for usr_no in (None, self.cajero_user, self.mesero_user, self.cocinero_iso):
            with self.subTest(rbac_admin_views=usr_no.username if usr_no else 'ANON'):
                if usr_no:
                    self.client.force_login(usr_no)
                else:
                    self.client.logout()
                self.assertEqual(self.client.get(reverse('administrador_historial')).status_code, 302)
                self.assertEqual(self.client.get(reverse('administrador_gestion')).status_code, 302)

        self.client.force_login(self.admin_user)

        # Historial consolidado y filtros (positivo vs negativo)
        resp_all = self.client.get(reverse('administrador_historial'))
        self.assertEqual(resp_all.status_code, 200)
        refs = {ev['id_ref'] for ev in resp_all.context['eventos']}
        self.assertTrue(any(r.startswith('JOR-A-') for r in refs))
        self.assertTrue(any(r.startswith('CAJ-A-') for r in refs))
        self.assertTrue(any(r.startswith('VEN-') for r in refs))
        self.assertTrue(any(r.startswith('TRA-') for r in refs))
        self.assertTrue(any(r.startswith('ENT-') for r in refs))

        resp_tipo = self.client.get(reverse('administrador_historial'), {'tipo': 'VENTA', 'q': '18'})
        refs_filtradas = {ev['id_ref'] for ev in resp_tipo.context['eventos']}
        self.assertTrue(any(r.startswith('VEN-') for r in refs_filtradas))
        self.assertFalse(any(r.startswith('JOR-A-') for r in refs_filtradas))

        # Gestión unificada con 4 áreas y parámetro ?tab=
        for tab in ('trabajadores', 'mesas', 'productos', 'menus'):
            with self.subTest(gestion_tab=tab):
                r_g = self.client.get(reverse('administrador_gestion'), {'tab': tab})
                self.assertEqual(r_g.status_code, 200)
                self.assertEqual(r_g.context['tab_activo'], tab)

    def test_comando_backup_safari_integridad_y_checksum(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp_dir:
            call_command('backup_safari', output_dir=tmp_dir, keep_days=14, stdout=out)
            archivos = os.listdir(tmp_dir)
            gz_files = [f for f in archivos if f.endswith('.sqlite3.gz')]
            sha_files = [f for f in archivos if f.endswith('.sha256')]

            self.assertEqual(len(gz_files), 1)
            self.assertEqual(len(sha_files), 1)

            gz_path = os.path.join(tmp_dir, gz_files[0])
            sha_path = os.path.join(tmp_dir, sha_files[0])
            digest_guardado = Path(sha_path).read_text(encoding='utf-8').strip().split()[0]

            with gzip.open(gz_path, 'rb') as f_gz:
                contenido_db = f_gz.read()
            self.assertGreater(len(contenido_db), 0)
            self.assertEqual(hashlib.sha256(contenido_db).hexdigest(), digest_guardado)
