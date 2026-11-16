import datetime as dt_mod
import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from ventas.models import (
    AlertaTraslado,
    Caja,
    Categoria,
    DetallePedido,
    DetalleVenta,
    Jornada,
    Mesa,
    Pedido,
    PerfilEmpleado,
    Producto,
    PuntoVenta,
    ReasignacionMesa,
    Ticket,
    Venta,
)
from ventas.test_suites.base import SafariDemoTestCase
from ventas.utils import (
    calcular_metricas_ocupacion_local,
    generar_contenido_ticket_cocina,
    liberar_mesa_operativa,
    proteger_contingencia_operativa,
    validar_modalidad_operativa,
)


class OperacionJornadaCajaYAnulacionesTests(SafariDemoTestCase):
    """
    Suite consolidada de Ciclo Operativo Diario:
    - Apertura/cierre de Jornada y Caja (fondo opcional $0, multicajero, duplicados, sin local).
    - Arqueo de denominaciones chilenas, cuadratura exacta, sobrantes, faltantes y bloqueo cruzado.
    - Anulaciones con supervisor/admin, bloqueo en caja cerrada, merma/fraude en comida entregada.
    - Resiliencia ante apagón del día anterior, limpieza automática de pedidos rezagados/zombies y cierre KDS.
    - Flujos de Mesero en salón, cuentas abiertas por rondas, Split Bill (Ronda 2 y 3 POS) y caja cerrada.
    """

    def test_jornada_ayer_no_valida_hoy_y_apertura_caja_reglas(self):
        # 1. Jornada abierta de ayer NO es válida hoy
        ayer = timezone.localdate() - dt_mod.timedelta(days=1)
        jornada_ayer = Jornada.objects.create(
            usuario_apertura=self.admin_user,
            estado='ABIERTA',
            observaciones="Jornada de ayer que quedó abierta",
        )
        Jornada.objects.filter(id=jornada_ayer.id).update(fecha=ayer)

        self.client.force_login(self.cajero_user)
        resp_inicio = self.client.get(reverse('vendedor'))
        self.assertIsNone(resp_inicio.context['jornada_activa'])
        self.assertContrastePositivoNegativo(
            resp_inicio,
            debe_estar=("Apertura Diaria de Jornada Requerida",),
            no_debe_estar=("Ya existe una jornada operativa abierta hoy",),
            contexto="Cajero antes de abrir jornada hoy",
        )

        # 2. Cajero sin Punto de Venta asignado es bloqueado tanto al abrir jornada como al abrir caja
        user_sin_pv = User.objects.create_user(username='cajero_sin_local_m3', password='Password123!')
        PerfilEmpleado.objects.create(
            usuario=user_sin_pv,
            rol='CAJERO',
            rut='22.222.222-3',
            punto_venta_actual=None,
            activo=True,
            debe_cambiar_clave=False,
        )
        self.client.force_login(user_sin_pv)
        resp_j = self.client.post(reverse('abrir_jornada'), {'monto_apertura': '0'}, follow=True)
        self.assertContains(resp_j, "No tienes un Punto de Venta asignado")
        hoy = timezone.localdate()
        self.assertEqual(Jornada.objects.filter(fecha=hoy, estado='ABIERTA').count(), 0)

        # 3. Apertura válida de jornada y caja con fondo omitido ($0) + prevención de doble envío
        self.client.force_login(self.cajero_user)
        resp_ap = self.client.post(
            reverse('abrir_jornada'),
            {'monto_apertura': '', 'observaciones': 'Apertura con fondo omitido'},
            follow=True,
        )
        self.assertRedirects(resp_ap, reverse('vendedor'))
        jornada = Jornada.objects.filter(estado='ABIERTA', fecha=hoy).first()
        self.assertIsNotNone(jornada)
        caja1 = Caja.objects.filter(jornada=jornada, cajero=self.cajero_user).first()
        self.assertIsNotNone(caja1)
        self.assertEqual(caja1.monto_apertura, Decimal('0'))

        # Segundo POST doble submit en abrir_jornada y abrir_caja no duplica
        resp_dup_j = self.client.post(reverse('abrir_jornada'), {'monto_apertura': '10000'}, follow=True)
        self.assertContains(resp_dup_j, "Ya existe una jornada operativa abierta hoy")
        resp_dup_c = self.client.post(reverse('abrir_caja'), {'monto_apertura': '50000'}, follow=True)
        self.assertContains(resp_dup_c, "Ya tienes una caja activa")
        self.assertEqual(Jornada.objects.filter(estado='ABIERTA', fecha=hoy).count(), 1)
        self.assertEqual(Caja.objects.filter(jornada__fecha=hoy, cajero=self.cajero_user).count(), 1)

        # 4. Segundo cajero comparte la misma jornada y abre su propia caja
        self.client.force_login(self.cajera2_user)
        resp_c2 = self.client.post(reverse('abrir_caja'), {'monto_apertura': '35000'}, follow=True)
        self.assertRedirects(resp_c2, reverse('vendedor'))
        self.assertEqual(Jornada.objects.filter(estado='ABIERTA', fecha=hoy).count(), 1)
        self.assertEqual(Caja.objects.filter(jornada__fecha=hoy).count(), 2)

        # 5. Con jornada ya abierta hoy, usuario sin PV sigue bloqueado al abrir_caja
        self.client.force_login(user_sin_pv)
        resp_sin_pv_c = self.client.post(reverse('abrir_caja'), {'monto_apertura': '0'}, follow=True)
        self.assertContains(resp_sin_pv_c, "No tienes un Punto de Venta asignado")
        self.assertEqual(Caja.objects.filter(cajero=user_sin_pv).count(), 0)

    def test_arqueo_denominaciones_cuadratura_bloqueos_y_cierre_jornada_subtest(self):
        hoy = timezone.localdate()

        # 1. Cálculo exacto de denominaciones CLP en modelo Caja
        jornada_calc = Jornada.objects.create(
            fecha=hoy - dt_mod.timedelta(days=10),
            estado='CERRADA',
            usuario_apertura=self.admin_user,
        )
        caja_calc = Caja.objects.create(
            jornada=jornada_calc,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
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
            monedas_1=0,
            estado='CERRADA',
        )
        self.assertEqual(caja_calc.calcular_total_arqueo(), 87950)

        # 2. SubTests de cuadratura: CUADRADA, SOBRANTE y FALTANTE (una jornada aislada por escenario)
        escenarios_cuadre = [
            ('CUADRADA', Decimal('20000.00'), Decimal('30000.00'), {'billetes_20000': '2', 'billetes_10000': '1'}, Decimal('50000.00'), Decimal('0.00')),
            ('SOBRANTE', Decimal('10000.00'), Decimal('0.00'), {'billetes_10000': '1', 'billetes_2000': '1'}, Decimal('12000.00'), Decimal('2000.00')),
            ('FALTANTE', Decimal('20000.00'), Decimal('0.00'), {'billetes_10000': '1', 'billetes_5000': '1'}, Decimal('15000.00'), Decimal('-5000.00')),
        ]
        self.client.force_login(self.cajero_user)
        for idx, (estado_esp, apertura, venta_total, arqueo_post, decl_esp, dif_esp) in enumerate(escenarios_cuadre):
            with self.subTest(cuadratura=estado_esp):
                j_sub = Jornada.objects.create(
                    fecha=hoy - dt_mod.timedelta(days=idx + 1),
                    estado='ABIERTA',
                    usuario_apertura=self.admin_user,
                )
                caja_tmp = Caja.objects.create(
                    jornada=j_sub,
                    cajero=self.cajero_user,
                    punto_venta=self.pv_central,
                    nombre=f'Caja Cuadre {idx}',
                    monto_apertura=apertura,
                    estado='ABIERTA',
                )
                if venta_total > 0:
                    Venta.objects.create(
                        caja=caja_tmp,
                        cajero=self.cajero_user,
                        punto_venta=self.pv_central,
                        modalidad='VENTA_RAPIDA',
                        metodo_pago='EFECTIVO',
                        total=venta_total,
                        estado='PAGADA',
                    )
                post_data = {'caja_id': caja_tmp.id, 'observaciones_cierre': f'Arqueo {estado_esp}'}
                post_data.update(arqueo_post)
                resp = self.client.post(reverse('cerrar_caja'), post_data)
                self.assertEqual(resp.status_code, 302)
                caja_tmp.refresh_from_db()
                self.assertEqual(caja_tmp.estado, 'CERRADA')
                self.assertEqual(caja_tmp.estado_cuadre, estado_esp)
                self.assertEqual(caja_tmp.total_efectivo_declarado, decl_esp)
                self.assertEqual(caja_tmp.diferencia_cuadre, dif_esp)

        # 3. Otro cajero NO puede cerrar caja ajena
        jornada = Jornada.objects.create(
            fecha=hoy,
            estado='ABIERTA',
            usuario_apertura=self.admin_user,
        )
        caja_abierta = Caja.objects.create(
            jornada=jornada,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
            nombre='Caja Carlos Protegida',
            monto_apertura=Decimal('10000.00'),
            estado='ABIERTA',
        )
        self.client.force_login(self.cajera2_user)
        self.client.post(reverse('cerrar_caja'), {'caja_id': caja_abierta.id, 'billetes_10000': '1'})
        caja_abierta.refresh_from_db()
        self.assertEqual(caja_abierta.estado, 'ABIERTA')

        # 4. Cierre de jornada bloqueado si hay cajas abiertas (forzar_cierre=0), permitido con forzar_cierre=1 limpiando KDS
        mesa = Mesa.objects.filter(punto_venta=self.pv_central, estado='HABILITADA').first()
        prod = Producto.objects.filter(activo=True).first()
        mesa.ocupar()
        venta_abierta = Venta.objects.create(
            caja=caja_abierta,
            cajero=self.mesero_user,
            punto_venta=self.pv_central,
            modalidad='MESA',
            mesa=mesa,
            metodo_pago='EFECTIVO',
            total=Decimal('5600'),
            estado='ABIERTA',
        )
        ped_kds = Pedido.objects.create(
            venta=venta_abierta,
            estado='LISTO',
            fecha_inicio_preparacion=timezone.now(),
            fecha_listo=timezone.now(),
        )
        DetallePedido.objects.create(pedido=ped_kds, producto=prod, cantidad=2)

        self.client.force_login(self.admin_user)
        self.client.post(reverse('cerrar_jornada'), {'jornada_id': jornada.id, 'forzar_cierre': '0'})
        jornada.refresh_from_db()
        self.assertEqual(jornada.estado, 'ABIERTA')

        self.client.post(
            reverse('cerrar_jornada'),
            {
                'jornada_id': jornada.id,
                'forzar_cierre': '1',
                'observaciones_cierre': 'Cierre forzado por contingencia',
            },
        )
        jornada.refresh_from_db()
        caja_abierta.refresh_from_db()
        venta_abierta.refresh_from_db()
        ped_kds.refresh_from_db()
        mesa.refresh_from_db()
        self.assertEqual(jornada.estado, 'CERRADA')
        self.assertEqual(jornada.usuario_cierre, self.admin_user)
        self.assertEqual(caja_abierta.estado, 'CERRADA')
        self.assertEqual(venta_abierta.estado, 'ANULADA')
        self.assertEqual(ped_kds.estado, 'CANCELADO')
        self.assertEqual(mesa.estado, 'HABILITADA')

        # KDS Cocina del día queda en 0 pedidos visibles
        self.client.force_login(self.cocinero_user)
        resp_kds = self.client.get(reverse('cocina'))
        self.assertEqual(len(resp_kds.context['pedidos']), 0)

    def test_anulaciones_venta_y_controles_antifraude_subtest(self):
        _, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        mesa = Mesa.objects.filter(punto_venta=self.pv_central, estado='HABILITADA').first()

        def crear_venta_pagada(ocupar_mesa=False):
            m = mesa if ocupar_mesa else None
            if ocupar_mesa:
                mesa.estado = 'OCUPADA'
                mesa.save(update_fields=['estado'])
            return Venta.objects.create(
                caja=caja,
                cajero=self.cajero_user,
                punto_venta=self.pv_central,
                modalidad='MESA' if ocupar_mesa else 'VENTA_RAPIDA',
                mesa=m,
                metodo_pago='EFECTIVO',
                total=Decimal('15000.00'),
                estado='PAGADA',
            )

        # Rechazos subTest: clave supervisor errónea, motivo < 5 chars, caja cerrada, cajero cancelando pedido
        v_prot = crear_venta_pagada()
        with self.subTest(caso='supervisor_clave_erronea'):
            self.client.force_login(self.cajero_user)
            self.client.post(
                reverse('anular_venta', args=[v_prot.id]),
                {
                    'motivo_anulacion': 'Intento de anulación sin permiso',
                    'supervisor_username': self.admin_user.username,
                    'supervisor_password': 'clave_erronea_falsa',
                },
                follow=True,
            )
            v_prot.refresh_from_db()
            self.assertEqual(v_prot.estado, 'PAGADA')

        with self.subTest(caso='motivo_muy_corto'):
            self.client.force_login(self.admin_user)
            self.client.post(
                reverse('anular_venta', args=[v_prot.id]),
                {'motivo_anulacion': 'err'},
                follow=True,
            )
            v_prot.refresh_from_db()
            self.assertEqual(v_prot.estado, 'PAGADA')

        with self.subTest(caso='cajero_no_cancela_pedido_directo'):
            ped = Pedido.objects.create(venta=v_prot, estado='EN_PREPARACION')
            self.client.force_login(self.cajero_user)
            resp_ped = self.client.post(
                reverse('cambiar_estado_pedido'),
                {'pedido_id': str(ped.id), 'nuevo_estado': 'CANCELADO'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            self.assertEqual(resp_ped.status_code, 403)
            ped.refresh_from_db()
            self.assertEqual(ped.estado, 'EN_PREPARACION')

        # Caso exitoso con credenciales supervisor: libera mesa y registra AlertaTraslado
        v_mesa = crear_venta_pagada(ocupar_mesa=True)
        self.client.force_login(self.cajero_user)
        resp_sup = self.client.post(
            reverse('anular_venta', args=[v_mesa.id]),
            {
                'motivo_anulacion': 'Cliente devolvió producto por error de digitación',
                'supervisor_username': self.admin_user.username,
                'supervisor_password': 'Password123!' if self.admin_user.check_password('Password123!') else 'safari123',
            },
            follow=True,
        )
        # En poblar_safari las claves demo son conocidas; verificar hash directo o probar admin directo si difiere
        v_mesa.refresh_from_db()
        if v_mesa.estado == 'PAGADA':
            # Re-sincronizar contraseña conocida para probar flujo real de credenciales supervisor
            self.admin_user.set_password('SupervisorKey#2026')
            self.admin_user.save()
            resp_sup = self.client.post(
                reverse('anular_venta', args=[v_mesa.id]),
                {
                    'motivo_anulacion': 'Cliente devolvió producto por error de digitación',
                    'supervisor_username': self.admin_user.username,
                    'supervisor_password': 'SupervisorKey#2026',
                },
                follow=True,
            )
            v_mesa.refresh_from_db()
        self.assertEqual(resp_sup.status_code, 200)
        self.assertEqual(v_mesa.estado, 'ANULADA')
        mesa.refresh_from_db()
        self.assertEqual(mesa.estado, 'HABILITADA')
        alerta = AlertaTraslado.objects.filter(empleado=self.cajero_user, autorizado_por=self.admin_user).first()
        self.assertIsNotNone(alerta)
        self.assertIn("ANULACIÓN", alerta.motivo)

        # Admin directo sobre venta con alimento ENTREGADO -> ALERTA DE MERMA/FRAUDE
        v_merma = crear_venta_pagada()
        Pedido.objects.create(venta=v_merma, estado='ENTREGADO')
        self.client.force_login(self.admin_user)
        self.client.post(
            reverse('anular_venta', args=[v_merma.id]),
            {'motivo_anulacion': 'Comensal reclamó comida fría tras haberla recibido'},
            follow=True,
        )
        v_merma.refresh_from_db()
        self.assertEqual(v_merma.estado, 'ANULADA')
        self.assertTrue(
            AlertaTraslado.objects.filter(
                empleado=self.admin_user,
                motivo__contains="ALERTA DE MERMA/FRAUDE",
            ).exists()
        )

        # Bloqueo anti-fraude sobre caja CERRADA y trabajador con caja abierta
        self.client.force_login(self.admin_user)
        resp_desact = self.client.post(
            reverse('administrador_trabajadores'),
            {'accion': 'desactivar', 'perfil_id': str(self.cajero_user.perfil.id)},
            follow=True,
        )
        self.cajero_user.perfil.refresh_from_db()
        self.assertTrue(self.cajero_user.perfil.activo)
        self.assertContains(resp_desact, "caja individual actualmente abierta")

        caja.estado = 'CERRADA'
        caja.save()
        resp_cerrada = self.client.post(
            reverse('anular_venta', args=[v_prot.id]),
            {'motivo_anulacion': 'Intento de anulación de caja cerrada'},
            follow=True,
        )
        v_prot.refresh_from_db()
        self.assertEqual(v_prot.estado, 'PAGADA')
        self.assertContains(resp_cerrada, "caja")

    def test_proteccion_apagon_dia_anterior_zombies_y_traspaso_fondo(self):
        local = self.pv_central
        mesa = Mesa.objects.filter(punto_venta=local, estado='HABILITADA').first()
        prod = Producto.objects.filter(activo=True).first()

        ayer_dt = timezone.now() - dt_mod.timedelta(days=1, hours=2)
        ayer_fecha = timezone.localtime(ayer_dt).date()

        jornada_ayer = Jornada.objects.create(usuario_apertura=self.cajero_user, estado='ABIERTA')
        Jornada.objects.filter(pk=jornada_ayer.pk).update(fecha=ayer_fecha, fecha_hora_apertura=ayer_dt)
        caja_ayer = Caja.objects.create(
            jornada=jornada_ayer,
            cajero=self.cajero_user,
            punto_venta=local,
            nombre="Caja Ayer Apagón",
            monto_apertura=Decimal('10000'),
            estado='ABIERTA',
        )
        Caja.objects.filter(pk=caja_ayer.pk).update(fecha_hora_apertura=ayer_dt)

        # Venta PAGADA ayer en efectivo ($15.000) con pedido EN_PREPARACION + Venta ABIERTA ($5.600) con pedido LISTO
        venta_pagada = Venta.objects.create(
            caja=caja_ayer, cajero=self.cajero_user, punto_venta=local,
            modalidad='VENTA_RAPIDA', metodo_pago='EFECTIVO', total=Decimal('15000'), estado='PAGADA',
        )
        Venta.objects.filter(pk=venta_pagada.pk).update(fecha_hora=ayer_dt)
        ped_pagado = Pedido.objects.create(venta=venta_pagada, estado='EN_PREPARACION', fecha_inicio_preparacion=ayer_dt)
        DetallePedido.objects.create(pedido=ped_pagado, producto=prod, cantidad=1)
        Pedido.objects.filter(pk=ped_pagado.pk).update(creado_en=ayer_dt, actualizado_en=ayer_dt)

        mesa.ocupar(timestamp=ayer_dt)
        venta_abierta = Venta.objects.create(
            caja=caja_ayer, cajero=self.mesero_user, punto_venta=local,
            modalidad='MESA', mesa=mesa, metodo_pago='EFECTIVO', total=Decimal('5600'), estado='ABIERTA',
        )
        Venta.objects.filter(pk=venta_abierta.pk).update(fecha_hora=ayer_dt)
        ped_abierto = Pedido.objects.create(
            venta=venta_abierta, estado='LISTO', fecha_inicio_preparacion=ayer_dt, fecha_listo=ayer_dt
        )
        DetallePedido.objects.create(pedido=ped_abierto, producto=prod, cantidad=2)
        Pedido.objects.filter(pk=ped_abierto.pk).update(creado_en=ayer_dt, actualizado_en=ayer_dt)

        # Entra Cocina primero: auto-cierra ayer, anula unpaid y marca ENTREGADO el pagado
        self.client.force_login(self.cocinero_user)
        resp_kds = self.client.get(reverse('cocina'))
        self.assertEqual(resp_kds.status_code, 200)
        self.assertEqual(len(resp_kds.context['pedidos']), 0)

        for obj in (jornada_ayer, caja_ayer, venta_abierta, ped_abierto, ped_pagado, mesa):
            obj.refresh_from_db()
        self.assertEqual(jornada_ayer.estado, 'CERRADA')
        self.assertEqual(caja_ayer.estado, 'CERRADA')
        self.assertEqual(caja_ayer.total_efectivo_declarado, Decimal('25000'))
        self.assertEqual(venta_abierta.estado, 'ANULADA')
        self.assertEqual(ped_abierto.estado, 'CANCELADO')
        self.assertEqual(ped_pagado.estado, 'ENTREGADO')
        self.assertTrue(ped_pagado.validar_orden_temporal()[0])
        self.assertEqual(mesa.estado, 'HABILITADA')
        self.assertIsNone(mesa.fecha_ocupacion)

        # Cajero abre hoy con fondo vacío y hereda los $25.000
        self.client.force_login(self.cajero_user)
        self.client.post(reverse('abrir_jornada'), {'monto_apertura': ''}, follow=True)
        caja_hoy = Caja.objects.filter(cajero=self.cajero_user, estado='ABIERTA', jornada__fecha=timezone.localdate()).first()
        self.assertIsNotNone(caja_hoy)
        self.assertEqual(caja_hoy.monto_apertura, Decimal('25000'))

        # Pedido olvidado > 180 min hoy (zombie 857 min) + helper proteger_contingencia_operativa
        hace_857_min = timezone.now() - dt_mod.timedelta(minutes=857)
        mesa.ocupar(timestamp=hace_857_min)
        venta_z = Venta.objects.create(
            caja=caja_hoy, cajero=self.mesero_user, punto_venta=local,
            modalidad='MESA', mesa=mesa, metodo_pago='EFECTIVO', total=Decimal('5600'), estado='ABIERTA',
        )
        Venta.objects.filter(pk=venta_z.pk).update(fecha_hora=hace_857_min)
        ped_zombie = Pedido.objects.create(
            venta=venta_z, estado='LISTO', fecha_inicio_preparacion=hace_857_min, fecha_listo=hace_857_min
        )
        DetallePedido.objects.create(pedido=ped_zombie, producto=prod, cantidad=2)
        Pedido.objects.filter(pk=ped_zombie.pk).update(creado_en=hace_857_min, actualizado_en=hace_857_min)

        cache.clear()
        self.client.force_login(self.cocinero_user)
        resp_kds2 = self.client.get(reverse('cocina'))
        self.assertNotIn(ped_zombie.id, [p['id'] for p in resp_kds2.context['pedidos']])
        ped_zombie.refresh_from_db()
        venta_z.refresh_from_db()
        mesa.refresh_from_db()
        self.assertEqual(ped_zombie.estado, 'CANCELADO')
        self.assertEqual(venta_z.estado, 'ANULADA')
        self.assertEqual(mesa.estado, 'HABILITADA')

        # Rezagado en venta PAGADA se regulariza a ENTREGADO vía servicio
        hace_4_h = timezone.now() - dt_mod.timedelta(hours=4)
        v_rez = Venta.objects.create(
            caja=caja_hoy, cajero=self.cajero_user, punto_venta=local,
            modalidad='MESA', mesa=mesa, total=Decimal('5000'), estado='PAGADA',
        )
        p_rez = Pedido.objects.create(venta=v_rez, estado='PENDIENTE')
        Pedido.objects.filter(id=p_rez.id).update(creado_en=hace_4_h, actualizado_en=hace_4_h)
        res = proteger_contingencia_operativa(usuario=self.admin_user, forzar=True)
        self.assertGreaterEqual(res['pedidos_regularizados'], 1)
        p_rez.refresh_from_db()
        self.assertEqual(p_rez.estado, 'ENTREGADO')

    def test_mesero_comandas_rondas_split_bill_y_bloqueo_caja_cerrada(self):
        _, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        mesa = Mesa.objects.filter(punto_venta=self.pv_central, estado='HABILITADA').first()
        prods = list(self.pv_central.get_productos_disponibles())
        prod_cocina = next(p for p in prods if p.get_destino_operativo() == 'COCINA')
        prod_barra = next(p for p in prods if p.get_destino_operativo() == 'BARRA')
        p_c = prod_cocina.precio_base
        p_b = prod_barra.precio_base

        # Ronda 1 vía Mesero (Accept JSON devuelve {ok, status})
        self.client.force_login(self.mesero_user)
        resp_r1 = self.client.post(
            reverse('mesero'),
            {
                'accion': 'enviar_comanda',
                'mesa_id': mesa.id,
                'items_json': json.dumps([{'id': prod_cocina.id, 'cantidad': 2, 'precio': 1}]),
            },
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(resp_r1.status_code, 200)
        data_r1 = resp_r1.json()
        self.assertTrue(data_r1['ok'])
        self.assertEqual(data_r1['status'], 'ok')

        venta_abierta = Venta.objects.get(mesa=mesa, punto_venta=self.pv_central, estado='ABIERTA')
        self.assertEqual(venta_abierta.cajero, self.mesero_user)
        self.assertEqual(venta_abierta.total, p_c * 2)

        # Admin ve la comanda reflejada con rol Mesero en su local
        self.client.force_login(self.admin_user)
        resp_admin = self.client.get(reverse('administrador_local', kwargs={'local_id': self.pv_central.id}))
        self.assertContains(resp_admin, "Mesero")

        # Split Bill parcial 1 plato desde Mesero + Ronda 2 Mesero + Ronda 3 POS preservan monto_abonado_parcial
        self.client.force_login(self.mesero_user)
        self.client.post(
            reverse('mesero'),
            {
                'accion': 'cerrar_cuenta_mesa',
                'mesa_id': mesa.id,
                'metodo_pago': 'TRANSFERENCIA',
                'monto_pago': str(int(p_c)),
            },
        )
        venta_abierta.refresh_from_db()
        mesa.refresh_from_db()
        self.assertEqual(mesa.estado, 'OCUPADA')
        self.assertEqual(venta_abierta.monto_abonado_parcial, p_c)
        self.assertEqual(venta_abierta.total, p_c)
        venta_parcial = Venta.objects.filter(venta_origen=venta_abierta, estado='PAGADA').first()
        self.assertIsNotNone(venta_parcial)
        self.assertEqual(venta_parcial.total, p_c)

        resp_r2 = self.client.post(
            reverse('mesero') + f"?local_id={self.pv_central.id}",
            {
                'accion': 'enviar_comanda',
                'mesa_id': mesa.id,
                'items_json': json.dumps([{'id': prod_barra.id, 'cantidad': 1}]),
            },
            follow=True,
        )
        self.assertContains(resp_r2, "Ronda #2")
        venta_abierta.refresh_from_db()
        self.assertEqual(venta_abierta.monto_abonado_parcial, p_c)
        self.assertEqual(venta_abierta.total, p_c + p_b)
        self.assertEqual(sum(d.subtotal for d in venta_abierta.detalles.all()), (p_c * 2) + p_b)
        self.assertEqual(venta_parcial.get_subtotal_consumo() + venta_abierta.get_subtotal_consumo(), (p_c * 2) + p_b)

        # Ronda 3 vía POS crear_ticket también preserva monto_abonado_parcial
        self.client.force_login(self.cajero_user)
        resp_pos_r3 = self.client.post(
            reverse('crear_ticket'),
            {
                'items_json': json.dumps([{'id': prod_barra.id, 'cantidad': 1}]),
                'modalidad': 'MESA',
                'mesa_id': mesa.id,
                'modo_cuenta': 'ABIERTA',
                'metodo_pago': 'EFECTIVO',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_pos_r3.status_code, 200)
        venta_abierta.refresh_from_db()
        self.assertEqual(venta_abierta.monto_abonado_parcial, p_c)
        self.assertEqual(venta_abierta.total, p_c + (p_b * 2))

        # Abono parcial desde panel Cajero cobrar_cuenta_mesa devuelve es_parcial=True y saldo_restante exacto
        abono_cajero = int(p_b)
        esperado_restante = float(venta_abierta.total) - abono_cajero
        resp_parc_cajero = self.client.post(
            reverse('vendedor'),
            {
                'accion': 'cobrar_cuenta_mesa',
                'mesa_id': mesa.id,
                'metodo_pago': 'EFECTIVO',
                'monto_pago': str(abono_cajero),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_parc_cajero.status_code, 200)
        data_parc = resp_parc_cajero.json()
        self.assertTrue(data_parc['ok'])
        self.assertTrue(data_parc['es_parcial'])
        self.assertEqual(data_parc['saldo_restante'], esperado_restante)

        # Cajero cobra el saldo restante completo -> libera la mesa
        resp_cobro_final = self.client.post(
            reverse('vendedor'),
            {'accion': 'cobrar_cuenta_mesa', 'mesa_id': mesa.id, 'metodo_pago': 'DEBITO'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(resp_cobro_final.status_code, 200)
        self.assertTrue(resp_cobro_final.json()['ok'])
        mesa.refresh_from_db()
        self.assertEqual(mesa.estado, 'HABILITADA')
        self.assertFalse(Venta.objects.filter(mesa=mesa, estado='ABIERTA').exists())

        # Abrir una nueva comanda mientras la caja sigue abierta, luego cerrar caja y verificar bloqueo 400 JSON
        mesa_bloq = Mesa.objects.filter(punto_venta=self.pv_central, estado='HABILITADA').first()
        self.client.force_login(self.mesero_user)
        self.client.post(
            reverse('mesero'),
            {'accion': 'enviar_comanda', 'mesa_id': mesa_bloq.id, 'items_json': json.dumps([{'id': prod_cocina.id, 'cantidad': 1}])},
        )
        mesa_libre = Mesa.objects.filter(punto_venta=self.pv_central, estado='HABILITADA').exclude(id=mesa_bloq.id).first()

        caja.estado = 'CERRADA'
        caja.save()
        for accion_bloq, extra in [
            ('cerrar_cuenta_mesa', {'mesa_id': mesa_bloq.id, 'metodo_pago': 'EFECTIVO'}),
            ('enviar_comanda', {'mesa_id': mesa_libre.id, 'items_json': json.dumps([{'id': prod_barra.id, 'cantidad': 1}])}),
        ]:
            with self.subTest(accion_caja_cerrada=accion_bloq):
                r_bloq = self.client.post(
                    reverse('mesero'),
                    {'accion': accion_bloq, **extra},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )
                self.assertEqual(r_bloq.status_code, 400)


class LocalesMesasReasignacionYOcupacionTests(SafariDemoTestCase):
    """
    Suite consolidada de Infraestructura por Local, Mesas y Ocupación:
    - RF14: CRUD completo de Puntos de Venta, duplicados case-insensitive, protección operativa, soft vs hard delete y 404/RBAC.
    - CRUD Mesas: unicidad aislada por local, protección de cuentas abiertas, eliminación limpia.
    - RF05: Reasignación de mesas conservando rondas, totales, tickets, tiempo y auditoría ReasignacionMesa.
    - RF11 & RF17: VENTA_RAPIDA vs MESA, colisiones, duración real, reconstrucción en BD y métricas de ocupación.
    - Contraste Positivo vs Negativo en terminales Cajero POS, Mesero y Administración.
    """

    def test_rf14_locales_crud_protecciones_y_rbac_subtest(self):
        # 1. Crear local exitosamente vía AJAX
        self.client.force_login(self.admin_user)
        resp_crear = self.client.post(
            reverse('administrador'),
            {
                'accion': 'crear_local',
                'nombre': 'Punto Waffles & Churros Oasis',
                'tipo': 'Pastelería & Snacks',
                'descripcion': 'Waffles recién horneados y bebidas calientes.',
                'icono': 'bi-cup-hot-fill',
                'color': '#d97706',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_crear.status_code, 200)
        self.assertEqual(resp_crear.json()['status'], 'ok')
        pv_nuevo = PuntoVenta.objects.get(nombre='Punto Waffles & Churros Oasis')
        self.assertTrue(pv_nuevo.activo)

        # 2. SubTests de rechazos al crear/modificar/consultar locales
        nombre_existente_upper = self.pv_central.nombre.upper()
        for desc_err, payload_err, status_esp in [
            ('duplicado_case_insensitive', {'accion': 'crear_local', 'nombre': nombre_existente_upper, 'tipo': 'Restaurante'}, 400),
            ('nombre_vacio', {'accion': 'crear_local', 'nombre': '   ', 'tipo': 'Cafetería'}, 400),
            ('modificar_inexistente', {'accion': 'modificar_local', 'local_id': 999999, 'nombre': 'Fantasma'}, 404),
        ]:
            with self.subTest(validacion_local=desc_err):
                r_err = self.client.post(reverse('administrador'), payload_err, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                self.assertEqual(r_err.status_code, status_esp)
        self.assertEqual(self.client.get(reverse('administrador_local', kwargs={'local_id': 999999})).status_code, 404)

        # 3. Modificar local existente
        resp_mod = self.client.post(
            reverse('administrador'),
            {
                'accion': 'modificar_local',
                'local_id': pv_nuevo.id,
                'nombre': 'Kiosco Sabana Renovado',
                'tipo': 'Punto Snacks',
                'descripcion': 'Bebidas heladas.',
                'icono': 'bi-snow',
                'color': '#0284c7',
                'activo': 'true',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_mod.status_code, 200)
        pv_nuevo.refresh_from_db()
        self.assertEqual(pv_nuevo.nombre, 'Kiosco Sabana Renovado')

        # 4. Blindaje: no se puede desactivar/eliminar local con caja ABIERTA ni con cuenta ABIERTA en salón
        jornada, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        for acc_bloq in ('modificar_local', 'eliminar_local'):
            with self.subTest(blindaje_caja_abierta=acc_bloq):
                r_bl = self.client.post(
                    reverse('administrador'),
                    {'accion': acc_bloq, 'local_id': self.pv_central.id, 'nombre': self.pv_central.nombre, 'activo': 'false'},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )
                self.assertEqual(r_bl.status_code, 400)
                self.assertIn("cajas abiertas", r_bl.json()['mensaje'])

        mesa_tmp = Mesa.objects.create(identificador="T-RF14", capacidad=4, punto_venta=pv_nuevo, estado='OCUPADA')
        Venta.objects.create(
            caja=caja, cajero=self.cajero_user, punto_venta=pv_nuevo,
            modalidad='MESA', mesa=mesa_tmp, total=Decimal('5000'), estado='ABIERTA',
        )
        for acc_bloq in ('modificar_local', 'eliminar_local'):
            with self.subTest(blindaje_venta_abierta=acc_bloq):
                r_va = self.client.post(
                    reverse('administrador'),
                    {'accion': acc_bloq, 'local_id': pv_nuevo.id, 'nombre': pv_nuevo.nombre, 'activo': 'false'},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )
                self.assertEqual(r_va.status_code, 400)
                self.assertIn("cuentas en consumo activas", r_va.json()['mensaje'])

        # 5. Soft-delete preserva transacciones históricas vs Hard-delete en local virgen libera trabajador sin borrar User
        pv_hist = PuntoVenta.objects.create(nombre="Buffet Antiguo Histórico", tipo="Buffet", activo=True)
        u_hist = User.objects.create_user('cajero_hist_m3', 'cajerohist_m3@safari.cl', 'Password123!')
        PerfilEmpleado.objects.create(usuario=u_hist, rol='CAJERO', punto_venta_actual=pv_hist)
        caja_hist = Caja.objects.create(
            jornada=jornada, cajero=u_hist, punto_venta=pv_hist, monto_apertura=Decimal('10000'), estado='CERRADA'
        )
        venta_hist = Venta.objects.create(
            caja=caja_hist, cajero=self.cajero_user, punto_venta=pv_hist,
            modalidad='VENTA_RAPIDA', total=Decimal('15000'), estado='PAGADA',
        )
        r_soft = self.client.post(
            reverse('administrador'),
            {'accion': 'eliminar_local', 'local_id': pv_hist.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_soft.status_code, 200)
        self.assertEqual(r_soft.json()['modo'], 'soft-delete')
        pv_hist.refresh_from_db()
        self.assertFalse(pv_hist.activo)
        self.assertTrue(Venta.objects.filter(id=venta_hist.id).exists())

        pv_virgen = PuntoVenta.objects.create(nombre="Kiosco Demo Temporal", tipo="Kiosco", activo=True)
        u_temp = User.objects.create_user('temp_colab_m3', 'temp_m3@safari.cl', 'Password123!')
        perfil_temp = PerfilEmpleado.objects.create(usuario=u_temp, rol='MESERO', punto_venta_actual=pv_virgen)
        r_hard = self.client.post(
            reverse('administrador'),
            {'accion': 'eliminar_local', 'local_id': pv_virgen.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_hard.status_code, 200)
        self.assertEqual(r_hard.json()['modo'], 'hard-delete')
        self.assertFalse(PuntoVenta.objects.filter(id=pv_virgen.id).exists())
        perfil_temp.refresh_from_db()
        self.assertIsNone(perfil_temp.punto_venta_actual)
        self.assertTrue(User.objects.filter(id=u_temp.id).exists())

        # 6. SubTest RBAC: roles no administradores y anónimos rechazados
        for usuario, destino, alerta in [
            (self.cajero_user, reverse('vendedor'), "Acceso restringido"),
            (self.mesero_user, reverse('mesero'), "Acceso restringido"),
            (self.cocinero_user, reverse('cocina'), "Acceso restringido"),
            (None, reverse('index'), "Acceso protegido"),
        ]:
            with self.subTest(rol_rechazado=usuario.username if usuario else 'ANON'):
                if usuario:
                    self.client.force_login(usuario)
                    r = self.client.get(reverse('administrador_local', kwargs={'local_id': self.pv_central.id}), follow=True)
                else:
                    self.client.logout()
                    r = self.client.post(reverse('administrador'), {'accion': 'crear_local', 'nombre': 'Hacker'}, follow=True)
                self.assertRedirects(r, destino)
                self.assertContains(r, alerta)

    def test_crud_mesas_y_rf05_reasignacion_completa_subtest(self):
        # 1. RBAC y listado + creación CRUD Mesas con unicidad aislada por local
        self.client.force_login(self.cajero_user)
        r_caj = self.client.get(reverse('administrador_mesas'), follow=True)
        self.assertRedirects(r_caj, reverse('vendedor'))
        self.assertContains(r_caj, "Acceso restringido")

        self.client.force_login(self.admin_user)
        resp_get = self.client.get(reverse('administrador_mesas'))
        self.assertContains(resp_get, "MANTENEDOR DE MESAS Y SECTORES")

        self.client.post(
            reverse('administrador_mesas'),
            {'accion': 'crear', 'identificador': 'Mesa Única M3', 'punto_venta_id': self.pv_central.id, 'capacidad': 6, 'estado': 'HABILITADA'},
            follow=True,
        )
        m_creada = Mesa.objects.get(identificador='Mesa Única M3', punto_venta=self.pv_central)
        self.assertEqual(m_creada.capacidad, 6)

        # Duplicado en mismo local rechazado; mismo identificador en local 2 permitido
        r_dup = self.client.post(
            reverse('administrador_mesas'),
            {'accion': 'crear', 'identificador': 'Mesa Única M3', 'punto_venta_id': self.pv_central.id, 'capacidad': 4, 'estado': 'HABILITADA'},
            follow=True,
        )
        self.assertContains(r_dup, "Ya existe una mesa con el identificador")
        r_otro = self.client.post(
            reverse('administrador_mesas'),
            {'accion': 'crear', 'identificador': 'Mesa Única M3', 'punto_venta_id': self.pv_selva.id, 'capacidad': 4, 'estado': 'HABILITADA'},
            follow=True,
        )
        self.assertContains(r_otro, "creada exitosamente")

        # Modificar mesa limpia y luego eliminarla físicamente
        self.client.post(
            reverse('administrador_mesas'),
            {
                'accion': 'modificar',
                'mesa_id': m_creada.id,
                'identificador': 'Terraza VIP M3',
                'punto_venta_id': self.pv_central.id,
                'capacidad': 10,
                'estado': 'HABILITADA',
            },
            follow=True,
        )
        m_creada.refresh_from_db()
        self.assertEqual(m_creada.identificador, 'Terraza VIP M3')
        self.assertEqual(m_creada.capacidad, 10)
        r_del_clean = self.client.post(reverse('administrador_mesas'), {'accion': 'eliminar', 'mesa_id': m_creada.id}, follow=True)
        self.assertContains(r_del_clean, "eliminada definitivamente")
        self.assertFalse(Mesa.objects.filter(id=m_creada.id).exists())

        # 2. Preparar cuenta abierta multi-ronda para RF05 + protección de mesa abierta en Admin
        _, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        mesa1, mesa2, mesa3 = list(Mesa.objects.filter(punto_venta=self.pv_central, estado='HABILITADA').order_by('id')[:3])
        mesa_inact = Mesa.objects.create(identificador="M-INACT-RF05", punto_venta=self.pv_central, capacidad=4, estado='INACTIVA')
        mesa_ocup = Mesa.objects.create(identificador="M-OCUP-RF05", punto_venta=self.pv_central, capacidad=4, estado='OCUPADA')
        mesa_local2 = Mesa.objects.filter(punto_venta=self.pv_selva).first()

        t_inicio = timezone.now() - dt_mod.timedelta(minutes=30)
        prod = Producto.objects.filter(activo=True).first()
        venta1 = Venta.objects.create(
            caja=caja, cajero=self.mesero_user, punto_venta=self.pv_central,
            modalidad='MESA', mesa=mesa1, total=Decimal('16400'), estado='ABIERTA',
        )
        mesa1.ocupar(timestamp=t_inicio)
        ped1 = Pedido.objects.create(venta=venta1, estado='PENDIENTE', observaciones="Ronda #1")
        DetallePedido.objects.create(pedido=ped1, producto=prod, cantidad=2, observaciones="Sin cebolla")
        DetalleVenta.objects.create(venta=venta1, producto=prod, cantidad=2, precio_aplicado=Decimal('8200'), subtotal=Decimal('16400'))
        Ticket.objects.create(pedido=ped1, codigo="COM-COC-RF05-1", tipo_destino='COCINA', estado='EMITIDO', contenido_impresion="Ronda 1")
        ped2 = Pedido.objects.create(venta=venta1, estado='PENDIENTE', observaciones="Ronda #2")
        Ticket.objects.create(pedido=ped2, codigo="COM-BAR-RF05-2", tipo_destino='BARRA', estado='EMITIDO', contenido_impresion="Ronda 2")

        # Admin no puede desactivar ni eliminar mesa con cuenta abierta
        self.assertContains(
            self.client.post(reverse('administrador_mesas'), {'accion': 'toggle_estado', 'mesa_id': mesa1.id}, follow=True),
            "No es posible desactivar la mesa",
        )
        self.assertContains(
            self.client.post(reverse('administrador_mesas'), {'accion': 'eliminar', 'mesa_id': mesa1.id}, follow=True),
            "Tiene una cuenta activa en consumo",
        )

        # 3. SubTest rechazos inválidos de reasignación RF05
        self.client.force_login(self.mesero_user)
        rechazos_rf05 = [
            ('destino_ocupado', mesa1.id, mesa_ocup.id, "ya se encuentra ocupada"),
            ('destino_inexistente', mesa1.id, 999999, "no existe en el sistema"),
            ('misma_mesa', mesa1.id, mesa1.id, "no puede ser la misma"),
            ('origen_sin_cuenta', mesa3.id, mesa2.id, "no posee una cuenta abierta"),
            ('destino_inactivo', mesa1.id, mesa_inact.id, "deshabilitada o en mantenimiento"),
            ('distintos_locales', mesa1.id, mesa_local2.id, "distintos Puntos de Venta"),
        ]
        for desc_r, orig_id, dest_id, msg_esp in rechazos_rf05:
            with self.subTest(rechazo_rf05=desc_r):
                r_rej = self.client.post(
                    reverse('mesero'),
                    {'accion': 'reasignar_mesa', 'mesa_origen_id': orig_id, 'mesa_destino_id': dest_id},
                    follow=True,
                )
                self.assertContains(r_rej, msg_esp)
                venta1.refresh_from_db()
                self.assertEqual(venta1.mesa, mesa1)
        self.assertEqual(ReasignacionMesa.objects.count(), 0)

        # 4. Traslado válido: conserva rondas/tickets/timestamp + doble clic rechazado + Ronda 3 en destino
        r_ok = self.client.post(
            reverse('mesero'),
            {
                'accion': 'reasignar_mesa',
                'mesa_origen_id': mesa1.id,
                'mesa_destino_id': mesa2.id,
                'motivo': 'Comensales prefirieron vista panorámica',
            },
            follow=True,
        )
        self.assertContains(r_ok, "Mesa reasignada exitosamente")
        venta1.refresh_from_db()
        mesa1.refresh_from_db()
        mesa2.refresh_from_db()
        self.assertEqual(venta1.mesa, mesa2)
        self.assertEqual(venta1.total, Decimal('16400'))
        self.assertEqual(venta1.pedidos.count(), 2)
        self.assertEqual(Ticket.objects.filter(pedido__venta=venta1).count(), 2)
        self.assertEqual(mesa1.estado, 'HABILITADA')
        self.assertIsNone(mesa1.fecha_ocupacion)
        self.assertEqual(mesa2.estado, 'OCUPADA')
        self.assertEqual(mesa2.fecha_ocupacion, t_inicio)

        reasig = ReasignacionMesa.objects.filter(venta=venta1).first()
        self.assertIsNotNone(reasig)
        self.assertEqual(reasig.mesa_origen, mesa1)
        self.assertEqual(reasig.mesa_destino, mesa2)
        self.assertIn("vista panorámica", reasig.motivo)

        # Doble envío tolerante
        r_dup_envio = self.client.post(
            reverse('mesero'),
            {'accion': 'reasignar_mesa', 'mesa_origen_id': mesa1.id, 'mesa_destino_id': mesa2.id},
            follow=True,
        )
        self.assertContains(r_dup_envio, "no posee una cuenta abierta")
        self.assertEqual(ReasignacionMesa.objects.count(), 1)

        # Ronda #3 posterior en nueva mesa se anexa a la misma venta
        prod_local = self.pv_central.get_productos_disponibles().first()
        r_r3 = self.client.post(
            reverse('mesero'),
            {
                'accion': 'enviar_comanda',
                'mesa_id': mesa2.id,
                'items_json': json.dumps([{'id': prod_local.id, 'cantidad': 1}]),
            },
            follow=True,
        )
        self.assertContains(r_r3, "Ronda #3 agregada")
        venta1.refresh_from_db()
        self.assertEqual(venta1.pedidos.count(), 3)
        self.assertEqual(venta1.total, Decimal('16400') + prod_local.precio_base)

    def test_rf11_y_rf17_modalidades_ocupacion_duracion_y_metricas(self):
        _, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        mesa_a, mesa_b = list(Mesa.objects.filter(punto_venta=self.pv_central, estado='HABILITADA').order_by('id')[:2])
        mesa_inact = Mesa.objects.create(identificador="M-INACT-RF17", punto_venta=self.pv_central, capacidad=2, estado='INACTIVA')
        mesa_pv2 = Mesa.objects.filter(punto_venta=self.pv_selva).first()
        prods = list(self.pv_central.get_productos_disponibles())
        prod_cocina = next(p for p in prods if p.get_destino_operativo() == 'COCINA')
        prod_barra = next(p for p in prods if p.get_destino_operativo() == 'BARRA')

        # 1. RF11 aliases VENTA_RAPIDA desacoplan mesa y nunca bloquean mesas
        for alias in ['VENTA_RAPIDA', 'MOSTRADOR', 'LLEVAR', 'RETIRO']:
            with self.subTest(alias_rapido=alias):
                mod, m_res = validar_modalidad_operativa(alias, mesa_a, self.pv_central)
                self.assertEqual(mod, 'VENTA_RAPIDA')
                self.assertIsNone(m_res)
                v_tmp = Venta(caja=caja, cajero=self.cajero_user, punto_venta=self.pv_central, modalidad=alias, mesa=mesa_a)
                v_tmp.clean()
                self.assertEqual(v_tmp.modalidad, 'VENTA_RAPIDA')
                self.assertIsNone(v_tmp.mesa)

        # Modalidad MESA: validaciones positivas y negativas
        mod_ok, m_ok = validar_modalidad_operativa('MESA', mesa_a, self.pv_central)
        self.assertEqual((mod_ok, m_ok), ('MESA', mesa_a))
        for m_inv, err_sub in [(None, "requiere obligatoriamente una mesa"), (mesa_pv2, "mismo punto de venta")]:
            with self.subTest(mesa_invalida=str(m_inv)):
                with self.assertRaises(ValidationError) as ctx:
                    Venta(caja=caja, cajero=self.cajero_user, punto_venta=self.pv_central, modalidad='MESA', mesa=m_inv).clean()
                self.assertIn(err_sub, str(ctx.exception))

        # POS AJAX crear_ticket VENTA_RAPIDA vs MESA vs falta mesa_id -> 400
        self.client.force_login(self.cajero_user)
        r_rap = self.client.post(
            reverse('crear_ticket'),
            {'items_json': json.dumps([{'producto_id': prod_barra.id, 'cantidad': 1}]), 'metodo_pago': 'EFECTIVO', 'modalidad': 'VENTA_RAPIDA'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_rap.status_code, 200)
        self.assertIn("Mostrador", r_rap.json()['ubicacion'])
        self.assertIsNone(Venta.objects.get(id=r_rap.json()['venta_id']).mesa)

        # Ticket de cocina en venta rápida muestra Mostrador y NO mesas
        ped_rap = Pedido.objects.create(venta=Venta.objects.get(id=r_rap.json()['venta_id']), estado='PENDIENTE')
        dp_rap = DetallePedido.objects.create(pedido=ped_rap, producto=prod_cocina, cantidad=1)
        ticket_txt = generar_contenido_ticket_cocina(ped_rap, items_cocina=[dp_rap])
        self.assertContrastePositivoNegativo(ticket_txt, debe_estar=("Mostrador",), no_debe_estar=(mesa_a.identificador, mesa_b.identificador))

        r_mesa_pos = self.client.post(
            reverse('crear_ticket'),
            {'items_json': json.dumps([{'producto_id': prod_cocina.id, 'cantidad': 1}]), 'metodo_pago': 'EFECTIVO', 'modalidad': 'MESA', 'mesa_id': mesa_b.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_mesa_pos.status_code, 200)
        self.assertEqual(Venta.objects.get(id=r_mesa_pos.json()['venta_id']).mesa, mesa_b)

        r_sin_mesa_pos = self.client.post(
            reverse('crear_ticket'),
            {'items_json': json.dumps([{'producto_id': prod_cocina.id, 'cantidad': 1}]), 'metodo_pago': 'EFECTIVO', 'modalidad': 'MESA', 'mesa_id': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r_sin_mesa_pos.status_code, 400)
        self.assertIn("Debe seleccionar una mesa", r_sin_mesa_pos.json()['error'])

        # 2. RF17: Ocupación, duración, doble ocupación, mesa inactiva, rondas preservan timestamp y reconstrucción en BD
        t_25m = timezone.now() - dt_mod.timedelta(minutes=25)
        mesa_a.ocupar(timestamp=t_25m)
        mesa_a.refresh_from_db()
        self.assertTrue(mesa_a.esta_ocupada())
        self.assertFalse(mesa_a.esta_disponible())
        self.assertAlmostEqual(mesa_a.get_duracion_ocupacion_minutos(), 25.0, places=0)
        self.assertGreaterEqual(mesa_a.get_duracion_ocupacion_segundos(), 1490)

        with self.assertRaises(ValidationError):
            mesa_a.ocupar()
        with self.assertRaises(ValidationError):
            mesa_inact.ocupar()

        # Mesero no puede enviar comanda ni ocupar mesa inactiva o ajena
        self.client.force_login(self.mesero_user)
        for m_id_bad, msg_bad in [('', "Debe seleccionar una mesa"), (mesa_pv2.id, "no pertenece al local"), (mesa_inact.id, "inactiva")]:
            with self.subTest(mesero_mesa_invalida=m_id_bad):
                r_m_bad = self.client.post(
                    reverse('mesero') + f"?local_id={self.pv_central.id}",
                    {'accion': 'enviar_comanda', 'mesa_id': m_id_bad, 'items_json': json.dumps([{'id': prod_cocina.id, 'cantidad': 1}])},
                    follow=True,
                )
                self.assertContains(r_m_bad, msg_bad)

        # Enviar comanda en mesa ya ocupada manualmente conserva fecha_ocupacion y bloquea liberación con cuenta abierta
        self.client.post(
            reverse('mesero'),
            {'accion': 'enviar_comanda', 'mesa_id': mesa_a.id, 'items_json': json.dumps([{'id': prod_cocina.id, 'cantidad': 1}])},
        )
        mesa_a.refresh_from_db()
        self.assertEqual(mesa_a.fecha_ocupacion, t_25m)
        with self.assertRaises(ValidationError):
            mesa_a.liberar(forzar=False)
        ok_lib, msg_lib = liberar_mesa_operativa(mesa_a, forzar=False)
        self.assertFalse(ok_lib)
        self.assertIn("cuenta abierta", msg_lib.lower())

        # Colisión en ORM: segunda Venta ABIERTA en la misma mesa rechazada
        with self.assertRaises(ValidationError) as ctx_col:
            Venta(caja=caja, cajero=self.cajero_user, punto_venta=self.pv_central, modalidad='MESA', mesa=mesa_a, estado='ABIERTA').clean()
        self.assertIn("ya tiene una cuenta abierta", str(ctx_col.exception))

        # Reconstrucción desde BD get_resumen_ocupacion() y métricas calcular_metricas_ocupacion_local()
        resumen = Mesa.objects.get(id=mesa_a.id).get_resumen_ocupacion()
        self.assertTrue(resumen['esta_ocupada'])
        self.assertTrue(resumen['tiene_cuenta_abierta'])
        self.assertAlmostEqual(resumen['duracion_ocupacion_minutos'], 25.0, places=0)
        self.assertIsNotNone(resumen['inicio_ocupacion_chile'])

        metricas = calcular_metricas_ocupacion_local(punto_venta=self.pv_central)
        self.assertGreaterEqual(metricas['mesas_ocupadas'], 1)
        self.assertGreaterEqual(metricas['mesas_inactivas'], 1)
        self.assertGreater(metricas['tasa_ocupacion_porcentaje'], 0)

        # Ocupar mesa_b sin cuenta y liberarla limpiamente
        mesa_b.ocupar()
        self.client.post(reverse('mesero'), {'accion': 'liberar_mesa', 'mesa_id': mesa_b.id})
        mesa_b.refresh_from_db()
        self.assertEqual(mesa_b.estado, 'HABILITADA')
        self.assertIsNone(mesa_b.fecha_ocupacion)

    def test_contraste_positivo_negativo_terminales_pos_cajero_vs_mesero(self):
        self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)

        # Cajero Terminal POS (/vendedor/crear-ticket/): DEBE mostrar modalidad entrega/rápida y NUNCA UI de salón mesero o admin
        self.client.force_login(self.cajero_user)
        resp_pos = self.client.get(reverse('crear_ticket'))
        self.assertEqual(resp_pos.status_code, 200)
        self.assertContrastePositivoNegativo(
            resp_pos,
            debe_estar=(self.pv_central.nombre,),
            no_debe_estar=("Selecciona o Asigna una Mesa", "Cuenta Abierta", "Crear Nuevo Local"),
            contexto="Cajero POS crear_ticket",
        )

        # Mesero en salón: local fijo e inmutable incluso intentando ?local_id=<otro>
        otro_local = self.pv_selva
        mesa_ajena = Mesa.objects.create(identificador="MESA-EXTERNA-CONTRAST", punto_venta=otro_local, capacidad=4, estado='HABILITADA')
        self.client.force_login(self.mesero_user)
        resp_mesero = self.client.get(reverse('mesero') + f"?local_id={otro_local.id}")
        self.assertEqual(resp_mesero.status_code, 200)
        self.assertEqual(resp_mesero.context['local_actual'], self.pv_central)
        self.assertNotEqual(resp_mesero.context['local_actual'], otro_local)
        self.assertContrastePositivoNegativo(
            resp_mesero,
            debe_estar=(self.pv_central.nombre,),
            no_debe_estar=("Seleccionar Punto de Venta:", mesa_ajena.identificador, "Crear Nuevo Local"),
            contexto="Mesero local fijo contra ?local_id ajeno",
        )

    def test_contraste_positivo_negativo_bloqueo_atencion_sin_caja_abierta(self):
        """Contraste POSITIVO vs NEGATIVO: bloquea ocupar mesas y enviar comandas sin jornada/caja abierta."""
        mesa = Mesa.objects.filter(punto_venta=self.pv_central, estado='HABILITADA').first()
        if not mesa:
            mesa = Mesa.objects.create(identificador="MESA-GATE-POS", punto_venta=self.pv_central, capacidad=4, estado='HABILITADA')
        prod = Producto.objects.filter(activo=True, puntos_venta=self.pv_central).first() or Producto.objects.filter(activo=True).first()
        items_payload = json.dumps([
            {'id': prod.id, 'nombre': prod.nombre, 'precio': float(prod.precio_base), 'cantidad': 1}
        ])

        def verificar_bloqueo(escenario_nombre, esperado_ui_mesero, esperar_jornada_abierta=False):
            with self.subTest(escenario=escenario_nombre):
                # 1. Cajero: oculta/reemplaza Enviar Clientes y Tomar Pedido; POST AJAX ocupar_mesa bloqueado (400)
                self.client.force_login(self.cajero_user)
                resp_caj_get = self.client.get(reverse('vendedor'))
                self.assertEqual(resp_caj_get.status_code, 200)
                self.assertContrastePositivoNegativo(
                    resp_caj_get,
                    debe_estar=("Requiere Caja Abierta",),
                    no_debe_estar=('data-mesa-action="ocupar"', "Tomar Pedido"),
                    contexto=f"Cajero GET bloqueado ({escenario_nombre})",
                )
                resp_caj_post = self.client.post(
                    reverse('vendedor'),
                    {'accion': 'ocupar_mesa', 'mesa_id': mesa.id},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )
                self.assertEqual(resp_caj_post.status_code, 400)
                self.assertFalse(resp_caj_post.json().get('ok'))
                mesa.refresh_from_db()
                self.assertEqual(mesa.estado, 'HABILITADA')

                # 2. Mesero: muestra alerta bloqueo; ocupar_mesa y enviar_comanda retornan 400 sin autocrear Jornada/Venta
                self.client.force_login(self.mesero_user)
                resp_mes_get = self.client.get(reverse('mesero'))
                self.assertEqual(resp_mes_get.status_code, 200)
                self.assertFalse(resp_mes_get.context['puede_atender_salon'])
                self.assertContrastePositivoNegativo(
                    resp_mes_get,
                    debe_estar=(esperado_ui_mesero, "Atención Bloqueada sin Caja", "Requiere Caja Abierta"),
                    no_debe_estar=("Enviar a Cocina y Barra",),
                    contexto=f"Mesero GET bloqueado ({escenario_nombre})",
                )

                resp_mes_ocup = self.client.post(
                    reverse('mesero'),
                    {'accion': 'ocupar_mesa', 'mesa_id': mesa.id},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )
                self.assertEqual(resp_mes_ocup.status_code, 400)
                self.assertFalse(resp_mes_ocup.json().get('ok'))
                mesa.refresh_from_db()
                self.assertEqual(mesa.estado, 'HABILITADA')

                ventas_antes = Venta.objects.count()
                resp_mes_com = self.client.post(
                    reverse('mesero'),
                    {'accion': 'enviar_comanda', 'mesa_id': mesa.id, 'items_json': items_payload},
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )
                self.assertEqual(resp_mes_com.status_code, 400)
                self.assertFalse(resp_mes_com.json().get('ok'))
                self.assertEqual(Venta.objects.count(), ventas_antes)
                self.assertEqual(
                    Jornada.objects.filter(fecha=timezone.localdate(), estado='ABIERTA').exists(),
                    esperar_jornada_abierta,
                )

        # Escenario Negativo A: Ni siquiera existe Jornada abierta hoy -> NO debe autocrearse al intentar comandar
        Jornada.objects.filter(fecha=timezone.localdate(), estado='ABIERTA').update(estado='CERRADA')
        verificar_bloqueo("sin_jornada", "Jornada Operativa No Abierta", esperar_jornada_abierta=False)

        # Escenario Negativo B: Existe Jornada abierta hoy, pero NO hay Caja abierta aún en el local
        jornada_hoy = Jornada.objects.create(usuario_apertura=self.admin_user, estado='ABIERTA')
        verificar_bloqueo("jornada_sin_caja", "Caja del Local Sin Apertura", esperar_jornada_abierta=True)

        # Escenario Negativo C: Caja abierta en OTRO local no habilita este local para Mesero
        caja_otra = Caja.objects.create(
            nombre="Caja Selva Ajena",
            punto_venta=self.pv_selva,
            jornada=jornada_hoy,
            cajero=self.cajera2_user,
            monto_apertura=25000,
            estado='ABIERTA',
        )
        verificar_bloqueo("solo_caja_otro_local", "Caja del Local Sin Apertura", esperar_jornada_abierta=True)
        caja_otra.delete()

        # Escenario Negativo D: La única caja del local ya fue CERRADA
        caja_cerrada = Caja.objects.create(
            nombre="Caja Cerrada Turno 1",
            punto_venta=self.pv_central,
            jornada=jornada_hoy,
            cajero=self.cajero_user,
            monto_apertura=25000,
            estado='CERRADA',
        )
        verificar_bloqueo("caja_cerrada_local", "Caja del Local Sin Apertura", esperar_jornada_abierta=True)
        caja_cerrada.delete()

        # Contraste Positivo: Cajero abre su Caja -> desaparecen los bloqueos UI y ambos roles operan normalmente
        self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)

        self.client.force_login(self.cajero_user)
        resp_caj_ok = self.client.get(reverse('vendedor'))
        self.assertEqual(resp_caj_ok.status_code, 200)
        self.assertContrastePositivoNegativo(
            resp_caj_ok,
            debe_estar=('data-mesa-action="ocupar"', "Enviar Clientes", "Tomar Pedido"),
            no_debe_estar=("Requiere Caja Abierta",),
            contexto="Cajero GET operativo con caja abierta",
        )
        resp_ocup_caj = self.client.post(
            reverse('vendedor'),
            {'accion': 'ocupar_mesa', 'mesa_id': mesa.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_ocup_caj.status_code, 200)
        self.assertTrue(resp_ocup_caj.json().get('ok'))
        mesa.refresh_from_db()
        self.assertEqual(mesa.estado, 'OCUPADA')

        self.client.force_login(self.mesero_user)
        resp_mes_ok = self.client.get(reverse('mesero'))
        self.assertEqual(resp_mes_ok.status_code, 200)
        self.assertTrue(resp_mes_ok.context['puede_atender_salon'])
        self.assertContrastePositivoNegativo(
            resp_mes_ok,
            debe_estar=("Enviar a Cocina y Barra",),
            no_debe_estar=("Atención Bloqueada sin Caja", "Caja del Local Sin Apertura", "Jornada Operativa No Abierta"),
            contexto="Mesero GET operativo con caja abierta",
        )
        resp_com_ok = self.client.post(
            reverse('mesero'),
            {'accion': 'enviar_comanda', 'mesa_id': mesa.id, 'items_json': items_payload},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp_com_ok.status_code, 200)
        self.assertTrue(resp_com_ok.json().get('ok'))
