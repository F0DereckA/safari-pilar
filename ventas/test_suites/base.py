import io
from decimal import Decimal
from django.core.cache import cache
from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from ventas.models import Caja, Jornada, PerfilEmpleado, PuntoVenta


class ContrasteAssertMixin:
    """Helpers reutilizables para aserciones pareadas Positivo vs Negativo."""

    def assertContrastePositivoNegativo(self, contenido, debe_estar=(), no_debe_estar=(), contexto=''):
        """Verifica en un mismo bloque qué DEBE mostrarse/estar y qué NO DEBE aparecer jamás."""
        if hasattr(contenido, 'content'):
            texto = contenido.content.decode('utf-8')
        else:
            texto = str(contenido)
        prefijo = f"[{contexto}] " if contexto else ""
        for esperado in debe_estar:
            self.assertIn(
                esperado,
                texto,
                f"{prefijo}Falta elemento POSITIVO esperado: {esperado!r}",
            )
        for prohibido in no_debe_estar:
            self.assertNotIn(
                prohibido,
                texto,
                f"{prefijo}Apareció elemento NEGATIVO prohibido: {prohibido!r}",
            )

    @staticmethod
    def abrir_jornada_y_caja(pv, cajero, admin=None, fondo=50000, nombre='Caja Principal'):
        usuario_ap = admin or cajero
        jornada = Jornada.objects.filter(fecha=timezone.localdate(), estado='ABIERTA').first()
        if not jornada:
            jornada = Jornada.objects.create(usuario_apertura=usuario_ap, estado='ABIERTA')
        caja = Caja.objects.filter(jornada=jornada, cajero=cajero).first()
        if not caja:
            caja = Caja.objects.create(
                nombre=nombre,
                punto_venta=pv,
                jornada=jornada,
                cajero=cajero,
                monto_apertura=Decimal(str(fondo)),
                estado='ABIERTA',
            )
        return jornada, caja


class SafariDemoTestCase(ContrasteAssertMixin, TestCase):
    """
    Base optimizada con `setUpTestData`: ejecuta `poblar_safari` UNA sola vez por clase
    (evitando recomputar hashes y re-sembrar fixtures en cada método individual).
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        call_command('poblar_safari', stdout=io.StringIO())
        PerfilEmpleado.objects.all().update(debe_cambiar_clave=False)

        cls.pv_central = PuntoVenta.objects.get(id=1)
        cls.pv_selva = PuntoVenta.objects.get(id=2)
        cls.pv_oasis = PuntoVenta.objects.get(id=3)

        cls.admin_user = User.objects.get(username='rgomez')
        cls.cajero_user = User.objects.get(username='cvalenzuela')
        cls.cajera2_user = User.objects.get(username='csoto')
        cls.cajero3_user = User.objects.get(username='mgonzalez')
        cls.mesero_user = User.objects.get(username='dsilva')
        cls.mesero2_user = User.objects.get(username='rfuentes')
        cls.cocinero_user = User.objects.get(username='eparedes')

    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = Client()

    def tearDown(self):
        cache.clear()
        super().tearDown()


class SafariIsolatedTestCase(ContrasteAssertMixin, TestCase):
    """
    Base liviana con BD mínima aislada (`setUpTestData` único por clase), sin datos demo pre-sembrados.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.pv = PuntoVenta.objects.create(
            nombre='Restaurante Central Safari',
            tipo='Restaurante',
            activo=True,
        )
        cls.pv_secundario = PuntoVenta.objects.create(
            nombre='Cafetería La Selva Test',
            tipo='Cafetería',
            activo=True,
        )
        cls.admin_user = User.objects.create_user(
            username='admin_suite',
            first_name='Ana',
            last_name='Administradora',
            email='ana.admin@safari.cl',
            password='AdminSuite!2026',
        )
        cls.admin_perfil = PerfilEmpleado.objects.create(
            usuario=cls.admin_user,
            rol='ADMINISTRADOR',
            rut='11.222.333-4',
            telefono='+56911112222',
            punto_venta_actual=cls.pv,
            activo=True,
            debe_cambiar_clave=False,
        )
        cls.cajero_user = User.objects.create_user(
            username='cajero_suite',
            first_name='Carlos',
            last_name='Cajero',
            email='carlos.cajero@safari.cl',
            password='CajeroSuite!2026',
        )
        cls.cajero_perfil = PerfilEmpleado.objects.create(
            usuario=cls.cajero_user,
            rol='CAJERO',
            rut='14.567.890-K',
            telefono='+56912345678',
            punto_venta_actual=cls.pv,
            activo=True,
            debe_cambiar_clave=False,
        )
        cls.mesero_user = User.objects.create_user(
            username='mesero_suite',
            first_name='Diego',
            last_name='Mesero',
            email='diego.mesero@safari.cl',
            password='MeseroSuite!2026',
        )
        cls.mesero_perfil = PerfilEmpleado.objects.create(
            usuario=cls.mesero_user,
            rol='MESERO',
            rut='16.777.888-2',
            telefono='+56988887777',
            punto_venta_actual=cls.pv,
            activo=True,
            debe_cambiar_clave=False,
        )

    def setUp(self):
        super().setUp()
        cache.clear()
        self.client = Client()

    def tearDown(self):
        cache.clear()
        super().tearDown()
