import json
import re
import time as _time
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from ventas.models import (
    Caja,
    Jornada,
    Pedido,
    PerfilEmpleado,
    PuntoVenta,
    RegistroConsentimiento,
    Ticket,
    Venta,
    anonimizar_datos_usuario,
    purgar_datos_por_retencion,
)
from ventas.security import enmascarar_email, enmascarar_rut, hash_alias_navegador
from ventas.test_suites.base import SafariDemoTestCase
from ventas.validators import validar_complejidad_clave


class AutenticacionAccesoYSeguridadTests(SafariDemoTestCase):
    """
    Suite consolidada de Autenticación, RBAC, Seguridad Defensiva (OWASP),
    Enmascaramiento PII, PIN cifrado POS, Sesiones e IP/RLS.
    """

    def test_cabeceras_http_cors_y_cookies_seguras(self):
        resp = self.client.get(reverse("index"))
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 28800)
        self.assertFalse(settings.CORS_ALLOW_ALL_ORIGINS)

        # CORS cerrado bloquea orígenes maliciosos en POST y GET API
        self.client.force_login(self.cajero_user)
        resp_post = self.client.post(
            reverse("registrar_consentimiento"),
            data=json.dumps({"analytics": False}),
            content_type="application/json",
            HTTP_ORIGIN="https://sitio-malicioso.ejemplo.cl",
        )
        self.assertEqual(resp_post.status_code, 403)
        resp_api = self.client.get(
            reverse("api_sincronizacion_estado"),
            HTTP_ORIGIN="https://otra-web.no-autorizada.test",
        )
        self.assertEqual(resp_api.status_code, 403)

    def test_manejadores_errores_http_y_robustez_id_subtest(self):
        casos_error = [
            (reverse("error_400"), 400, "Solicitud o Parámetros Incorrectos"),
            (reverse("error_403"), 403, "Acceso Restringido o No Autorizado"),
            (reverse("error_404"), 404, "Ruta o Recurso No Encontrado"),
            (reverse("error_500"), 500, "Blindaje de Seguridad y Robustez (OWASP)"),
        ]
        for url, status, texto_esperado in casos_error:
            with self.subTest(url=url, status=status):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, status)
                self.assertContrastePositivoNegativo(
                    resp,
                    debe_estar=(str(status), texto_esperado, "Volver al Portal de Inicio"),
                    no_debe_estar=("Traceback (most recent call last)", "ImproperlyConfigured", "SELECT "),
                    contexto=f"HTTP {status}",
                )

        # Rutas inexistentes o ID manipulado con DEBUG=False nunca derrumban con 500
        with override_settings(DEBUG=False):
            for ruta_bad in ("/ruta-inexistente-safari-12345/", "/adminitrador/"):
                resp = self.client.get(ruta_bad)
                self.assertEqual(resp.status_code, 404)
                self.assertContains(resp, "Ruta o Recurso No Encontrado", status_code=404)

            self.client.force_login(self.admin_user)
            resp_id_bad = self.client.get("/administrador/local/99999/")
            self.assertEqual(resp_id_bad.status_code, 404)
            self.assertContains(resp_id_bad, "Ruta o Recurso No Encontrado", status_code=404)

    def test_login_validaciones_selector_inactivos_logout_y_fuerza_bruta(self):
        # 1. Campos vacíos
        for payload in ({"username": "", "password": ""}, {"username": "admin_safari", "password": ""}):
            with self.subTest(campos_vacios=payload):
                resp_v = self.client.post(reverse("login"), payload, follow=True)
                mensajes = [str(m) for m in get_messages(resp_v.wsgi_request)]
                self.assertTrue(any("completa todos los campos requeridos" in m for m in mensajes))
                self.assertFalse(resp_v.wsgi_request.user.is_authenticated)

        # 2. Credenciales inválidas
        resp_inv = self.client.post(
            reverse("login"),
            {"username": "cvalenzuela", "password": "password_incorrecta_99"},
            follow=True,
        )
        self.assertContains(resp_inv, "Credenciales incorrectas")
        self.assertFalse(resp_inv.context["user"].is_authenticated)

        # 3. Selector visual manipulado nunca escala rol real en BD
        for username, destino in (("cvalenzuela", "vendedor"), ("eparedes", "cocina")):
            with self.subTest(selector_tamper=username):
                cache.clear()
                resp_sel = self.client.post(
                    reverse("login"),
                    {"username": username, "password": "safari123", "rol_selector": "ADMINISTRADOR"},
                    follow=True,
                )
                self.assertRedirects(resp_sel, reverse(destino))
                self.assertNotContains(resp_sel, "Bienvenido(a)")
                self.client.logout()

        # 4. Logout normal y por inactividad
        self.client.force_login(self.cajero_user)
        resp_out = self.client.get(reverse("logout"), follow=True)
        self.assertRedirects(resp_out, reverse("index"))
        self.assertContains(resp_out, "cerrado tu sesión")
        self.assertFalse(resp_out.context["user"].is_authenticated)

        self.client.force_login(self.cajero_user)
        resp_inact = self.client.get(reverse("logout") + "?motivo=inactividad", follow=True)
        self.assertContains(resp_inact, "inactividad")

        # 5. Usuario inactivo rechazado + reactivado admitido + revocación en sesión activa
        perfil_m = PerfilEmpleado.objects.get(usuario=self.mesero_user)
        perfil_m.activo = False
        perfil_m.save()
        self.mesero_user.is_active = False
        self.mesero_user.save()

        resp_m_inact = self.client.post(
            reverse("login"), {"username": "dsilva", "password": "safari123"}, follow=True
        )
        self.assertContains(resp_m_inact, "cuenta de colaborador se encuentra inactiva")
        self.assertFalse(resp_m_inact.context["user"].is_authenticated)

        perfil_m.activo = True
        perfil_m.save()
        self.mesero_user.is_active = True
        self.mesero_user.save()
        cache.clear()

        resp_m_ok = self.client.post(
            reverse("login"), {"username": "dsilva", "password": "safari123"}, follow=True
        )
        self.assertRedirects(resp_m_ok, reverse("mesero"))
        self.assertEqual(self.client.get(reverse("mesero")).status_code, 200)

        # Desactivar en vivo -> la siguiente petición revoca sesión inmediatamente
        perfil_m.activo = False
        perfil_m.save()
        resp_rev = self.client.get(reverse("mesero"), follow=True)
        self.assertRedirects(resp_rev, reverse("index"))
        self.assertContains(resp_rev, "inactiva")
        self.assertFalse(resp_rev.context["user"].is_authenticated)
        perfil_m.activo = True
        perfil_m.save()

        # 6. Fuerza bruta por cuenta (5 intentos -> bloqueo temporal 5 min)
        cache.clear()
        target_user = User.objects.create_user(username="usuario_bruta_suite", password="safariPassword2026!")
        PerfilEmpleado.objects.create(
            usuario=target_user,
            rol="MESERO",
            punto_venta_actual=self.pv_central,
            activo=True,
            debe_cambiar_clave=False,
        )
        for i in range(1, 5):
            r = self.client.post(
                reverse("login"), {"username": "usuario_bruta_suite", "password": f"err_{i}"}, follow=True
            )
            self.assertContains(r, f"Te quedan {5 - i} intento(s)")

        r5 = self.client.post(
            reverse("login"), {"username": "usuario_bruta_suite", "password": "err_5"}, follow=True
        )
        self.assertContains(r5, "Has superado el límite de 5 intentos fallidos")
        self.assertContains(r5, "15 minutos")
        target_user.perfil.refresh_from_db()
        self.assertTrue(target_user.perfil.esta_bloqueado())
        seg_db = (target_user.perfil.bloqueado_hasta - timezone.now()).total_seconds()
        self.assertGreater(seg_db, 14 * 60)

        r6 = self.client.post(
            reverse("login"),
            {"username": "usuario_bruta_suite", "password": "safariPassword2026!"},
            follow=True,
        )
        self.assertContains(r6, "bloqueado temporalmente")
        self.assertContains(r6, 'id="alertaBloqueoIpLogin"')
        self.assertFalse(r6.context["user"].is_authenticated)

        # 7. Cuenta regresiva compartida entre distintos usuarios por IP: 4 cambios + 5° error -> bloqueo 15 min
        cache.clear()
        for idx, atacante in enumerate(("intento_a", "intento_b", "intento_c", "intento_d"), start=1):
            resp_rot_user = self.client.post(
                reverse("login"), {"username": atacante, "password": "clave_incorrecta"}, follow=True
            )
            self.assertContains(resp_rot_user, f"Te quedan {5 - idx} intento(s)")
            self.assertContains(resp_rot_user, f"llevas {idx} de 5 intento(s) fallido(s)")

        resp_5_distinto = self.client.post(
            reverse("login"), {"username": "intento_e", "password": "clave_incorrecta"}, follow=True
        )
        self.assertContains(resp_5_distinto, "bloqueado temporalmente por 15 minutos")
        self.assertContains(resp_5_distinto, 'id="countdownBloqueoLogin"')

        # Incluso intentando con otro usuario legítimo y contraseña correcta desde la misma IP/sesión sigue bloqueado
        resp_ip = self.client.post(
            reverse("login"), {"username": self.mesero_user.username, "password": "safari123"}, follow=True
        )
        self.assertContains(resp_ip, "Acceso de red bloqueado temporalmente")
        self.assertFalse(resp_ip.context["user"].is_authenticated)

    def test_aislamiento_roles_vistas_apis_y_contraste_ui_por_rol(self):
        """Verifica RBAC estricto + JSON 401/403 API + Contraste Positivo/Negativo de UI por rol."""
        # Anónimo: HTML redirige a index; API XHR devuelve 401 JSON (jamás 302 HTML)
        for ruta_name in ("administrador", "vendedor", "mesero", "cocina", "administrador_mesas"):
            resp_anon = self.client.get(reverse(ruta_name), follow=True)
            self.assertRedirects(resp_anon, reverse("index"))
            self.assertContains(resp_anon, "Acceso protegido")

        resp_api_401 = self.client.get(
            reverse("api_verificar_convenio_qr"),
            {"codigo": "X"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp_api_401.status_code, 401)
        self.assertTrue(resp_api_401.json().get("sesion_expirada"))

        # Portal de login: nunca expone "safari123" ni casilla premarcada
        html_index = self.client.get(reverse("index")).content.decode("utf-8")
        self.assertContrastePositivoNegativo(
            html_index,
            debe_estar=('id="id_acepto_politicas"', "safariAckConfig"),
            no_debe_estar=("safari123",),
            contexto="Login portal sin secretos",
        )
        chk_tag = html_index.split('id="id_acepto_politicas"')[1].split(">")[0]
        self.assertNotIn("checked", chk_tag)

        # Matriz RBAC de redirección por rol + contraste de pantalla propia (incluye bloqueo de /mi-privacidad/)
        matriz_roles = [
            (self.mesero_user, "mesero", ("administrador", "vendedor", "cocina", "mi_privacidad")),
            (self.cajero_user, "vendedor", ("administrador", "mesero", "cocina", "mi_privacidad")),
            (self.cocinero_user, "cocina", ("administrador", "vendedor", "mesero", "mi_privacidad")),
        ]
        for usuario, propia, prohibidas in matriz_roles:
            self.client.force_login(usuario)
            for p_route in prohibidas:
                with self.subTest(rol=usuario.username, bloqueada=p_route):
                    self.assertRedirects(self.client.get(reverse(p_route), follow=True), reverse(propia))

        # Contraste Mesero: local fijo inmutable sin selector desplegable, sin controles admin ni link /mi-privacidad/
        self.client.force_login(self.mesero_user)
        resp_mesero = self.client.get(reverse("mesero"))
        self.assertEqual(resp_mesero.status_code, 200)
        self.assertContrastePositivoNegativo(
            resp_mesero,
            debe_estar=(self.pv_central.nombre,),
            no_debe_estar=(
                '<select name="local_id"',
                'action="/administrador/',
                "safari123",
                reverse("mi_privacidad"),
                "Mis Datos",
                ">Online<",
                "Cocina & Barra: Online",
                "Bienvenido(a)",
            ),
            contexto="Mesero contraste navegación, local fijo y sin ruido visual ni datos",
        )
        for ruta_legal in ("politica_privacidad", "terminos_condiciones"):
            self.assertContrastePositivoNegativo(
                self.client.get(reverse(ruta_legal)),
                no_debe_estar=(reverse("mi_privacidad"), "Mis Datos (ARCO)"),
                contexto=f"Mesero en {ruta_legal} sin acceso a Mis Datos",
            )

        # Administrador: puede supervisar cocina/barra, ve /mi-privacidad/, no entra a caja vendedor/mesero
        self.client.force_login(self.admin_user)
        self.assertRedirects(self.client.get(reverse("vendedor"), follow=True), reverse("administrador"))
        self.assertRedirects(self.client.get(reverse("mesero"), follow=True), reverse("administrador"))
        self.assertEqual(self.client.get(reverse("cocina")).status_code, 200)
        self.assertEqual(self.client.get(reverse("mi_privacidad")).status_code, 200)
        self.assertContrastePositivoNegativo(
            self.client.get(reverse("administrador")),
            debe_estar=(reverse("mi_privacidad"), reverse("administrador_trabajadores")),
            no_debe_estar=("safari123",),
            contexto="Administrador conserva enlace a Mi Privacidad y Trabajadores",
        )
        for ruta_legal in ("politica_privacidad", "terminos_condiciones"):
            self.assertContrastePositivoNegativo(
                self.client.get(reverse(ruta_legal)),
                debe_estar=(reverse("mi_privacidad"),),
                contexto=f"Administrador en {ruta_legal} conserva enlace a Mi Privacidad",
            )

        # Cocinero API JSON 403 sobre endpoints exclusivos Cajero + Modo Concentración en KDS sin /mi-privacidad/
        self.client.force_login(self.cocinero_user)
        resp_api_403 = self.client.post(
            reverse("api_desbloquear_pin_pos"),
            {"accion": "desbloquear", "pin": "1234"},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(resp_api_403.status_code, 403)
        self.assertFalse(resp_api_403.json().get("ok"))

        for ruta_kds in ("cocina", "barra"):
            resp_kds = self.client.get(reverse(ruta_kds))
            self.assertContrastePositivoNegativo(
                resp_kds,
                debe_estar=('id="btnToggleCondensadoKds"', 'id="textoModoConcentracion"', 'aria-pressed="false"', "kds-kpi-strip"),
                no_debe_estar=(
                    'name="monto_apertura"',
                    "safari123",
                    reverse("mi_privacidad"),
                    "Mis Datos",
                    "Estación Cocina Caliente",
                    "Producción Gastronómica Exclusiva",
                    "KDS En Vivo",
                    "Barra En Vivo",
                    "Bienvenido(a)",
                ),
                contexto=f"KDS {ruta_kds} Concentración & aislamiento sin ruido ni datos personales",
            )

        # Cajero POS: /vendedor/ y /vendedor/crear-ticket/ nunca muestran enlace a /mi-privacidad/ ni "Mis Datos"
        self.client.force_login(self.cajero_user)
        self.assertContrastePositivoNegativo(
            self.client.get(reverse("vendedor")),
            no_debe_estar=(reverse("mi_privacidad"), "Mis Datos"),
            contexto="Cajero monitor sin enlace a Mis Datos",
        )
        jornada_pos = Jornada.objects.create(fecha=timezone.now().date(), estado="ABIERTA", usuario_apertura=self.admin_user)
        Caja.objects.create(
            nombre="Caja Contraste UI",
            jornada=jornada_pos,
            punto_venta=self.pv_central,
            cajero=self.cajero_user,
            monto_apertura=Decimal("10000"),
            estado="ABIERTA",
        )
        self.assertContrastePositivoNegativo(
            self.client.get(reverse("crear_ticket")),
            no_debe_estar=(reverse("mi_privacidad"), "Mis Datos"),
            contexto="Cajero crear_ticket sin enlace a Mis Datos",
        )

        css_base = Path(settings.BASE_DIR) / "static" / "css" / "kds"
        self.assertIn("body.kds-modo-condensado .kds-kpi-strip", (css_base / "cocina.css").read_text(encoding="utf-8"))
        self.assertIn("body.kds-modo-condensado .barra-btn-action", (css_base / "barra.css").read_text(encoding="utf-8"))

    def test_gestion_trabajadores_politica_claves_iso27400_y_enmascaramiento_pii(self):
        """ISO/IEC 27400 complejidad/expiración/hashing, anti-lockout, caja abierta y cero PII cruda."""
        # 1. Validador unitario subTest positivo vs negativo
        claves_invalidas = [
            ("Ab1!", "mínimo de 8 caracteres"),
            ("A" * 10 + "b1!" + "x" * 20, "30 caracteres"),
            ("password123!", "mayúscula"),
            ("PASSWORD123!", "minúscula"),
            ("Password!@#", "dígito numérico"),
            ("Password123", "símbolo o carácter especial"),
        ]
        for clave, fragmento in claves_invalidas:
            with self.subTest(clave_invalida=clave):
                ok, msg = validar_complejidad_clave(clave)
                self.assertFalse(ok)
                self.assertIn(fragmento, msg)
        ok_strong, msg_strong = validar_complejidad_clave("Safari.Pilar2026!")
        self.assertTrue(ok_strong)
        self.assertEqual(msg_strong, "")

        # 2. Rechazar claves débiles al crear trabajador; aceptar robusta con hash seguro
        self.client.force_login(self.admin_user)
        url_trab = reverse("administrador_trabajadores")
        for idx, clave_debil in enumerate(("", "123", "1234", "123456", "password", "qwerty", "safari123")):
            with self.subTest(crear_clave_debil=clave_debil or "<empty>"):
                uname = f"infiltrado_{idx}"
                resp_bad = self.client.post(
                    url_trab,
                    {
                        "accion": "crear",
                        "nombre": "Test",
                        "apellido": "Debil",
                        "username": uname,
                        "rut": f"20.000.00{idx}-1",
                        "rol": "MESERO",
                        "local_id": self.pv_central.id,
                        "password": clave_debil,
                    },
                    follow=True,
                )
                self.assertFalse(User.objects.filter(username=uname).exists())
                self.assertTrue(
                    "8 caracteres" in resp_bad.content.decode("utf-8")
                    or "ingresar una contraseña" in resp_bad.content.decode("utf-8")
                )

        resp_ok = self.client.post(
            url_trab,
            {
                "accion": "crear",
                "nombre": "Lucia",
                "apellido": "Mendez",
                "username": "lmendez_segura",
                "rut": "18.777.666-5",
                "rol": "CAJERO",
                "telefono": "+56955554444",
                "local_id": self.pv_central.id,
                "password": "SafariFuerte!2026",
            },
            follow=True,
        )
        self.assertContains(resp_ok, "registrado con éxito")
        u_lucia = User.objects.get(username="lmendez_segura")
        self.assertTrue(u_lucia.check_password("SafariFuerte!2026"))
        for u in User.objects.all():
            self.assertTrue(u.password.startswith(("pbkdf2_sha256$", "argon2$")))
            self.assertNotEqual(u.password, "safari123")

        # Truncado estricto en backend para usuario (50) y nombre/apellido (100)
        resp_lim_trab = self.client.post(
            url_trab,
            {
                "accion": "crear",
                "nombre": "N" * 140,
                "apellido": "A" * 140,
                "username": "u" * 80,
                "rut": "18.888.999-K",
                "rol": "MESERO",
                "local_id": self.pv_central.id,
                "password": "SafariFuerte!2026",
            },
            follow=True,
        )
        self.assertContains(resp_lim_trab, "registrado con éxito")
        u_lim = User.objects.get(username="u" * 50)
        self.assertEqual(len(u_lim.username), 50)
        self.assertEqual(len(u_lim.first_name), 100)
        self.assertEqual(len(u_lim.last_name), 100)

        # 3. Modificar sin clave ni RUT/teléfono preserva contraseña y PII existentes en BD
        perfil_caj = self.cajero_user.perfil
        rut_orig = perfil_caj.rut
        tel_orig = perfil_caj.telefono
        email_orig = self.cajero_user.email
        self.client.post(
            url_trab,
            {
                "accion": "modificar",
                "perfil_id": perfil_caj.id,
                "nombre": "Carlos Mod",
                "apellido": "Valenzuela M.",
                "rol": "CAJERO",
                "rut": "",
                "telefono": "",
                "local_id": self.pv_central.id,
                "password": "",
            },
            follow=True,
        )
        self.cajero_user.refresh_from_db()
        perfil_caj.refresh_from_db()
        self.assertEqual(self.cajero_user.first_name, "Carlos Mod")
        self.assertTrue(self.cajero_user.check_password("safari123"))
        self.assertEqual(perfil_caj.rut, rut_orig)
        self.assertEqual(perfil_caj.telefono, tel_orig)

        # 4. Anti-lockout admin y bloqueo de cambio de rol / desactivación con caja abierta
        perfil_admin = self.admin_user.perfil
        self.client.post(url_trab, {"accion": "desactivar", "perfil_id": perfil_admin.id}, follow=True)
        perfil_admin.refresh_from_db()
        self.assertTrue(perfil_admin.activo)

        self.client.post(
            url_trab,
            {"accion": "modificar", "perfil_id": perfil_admin.id, "rol": "MESERO", "local_id": self.pv_central.id},
            follow=True,
        )
        perfil_admin.refresh_from_db()
        self.assertEqual(perfil_admin.rol, "ADMINISTRADOR")

        # Toggle activar/desactivar mesero por AJAX y POST estándar
        perfil_m = self.mesero_user.perfil
        r_ajax_off = self.client.post(
            url_trab, {"accion": "desactivar", "perfil_id": perfil_m.id}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(r_ajax_off.status_code, 200)
        self.assertFalse(r_ajax_off.json()["activo"])
        r_ajax_on = self.client.post(
            url_trab, {"accion": "activar", "perfil_id": perfil_m.id}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertTrue(r_ajax_on.json()["activo"])

        # Cajero con caja abierta NO puede cambiar rol ni desactivarse
        self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        resp_caja_desac = self.client.post(
            url_trab, {"accion": "desactivar", "perfil_id": perfil_caj.id}, follow=True
        )
        perfil_caj.refresh_from_db()
        self.assertTrue(perfil_caj.activo)
        self.assertContains(resp_caja_desac, "caja individual actualmente abierta")

        self.client.post(
            url_trab,
            {"accion": "modificar", "perfil_id": perfil_caj.id, "rol": "MESERO", "local_id": self.pv_central.id},
            follow=True,
        )
        perfil_caj.refresh_from_db()
        self.assertEqual(perfil_caj.rol, "CAJERO")

        # 5. Contraste Positivo/Negativo PII en plantillas administrativas
        if rut_orig and email_orig:
            rut_mask = enmascarar_rut(rut_orig)
            email_mask = enmascarar_email(email_orig)
            resp_trab = self.client.get(url_trab)
            self.assertContrastePositivoNegativo(
                resp_trab,
                debe_estar=(rut_mask, email_mask),
                no_debe_estar=(rut_orig, email_orig, tel_orig) if tel_orig else (rut_orig, email_orig),
                contexto="Trabajadores Admin sin PII cruda",
            )
            for ruta_adm, kw in (
                ("administrador", {}),
                ("administrador_local", {"local_id": self.pv_central.id}),
                ("administrador_consumos", {}),
                ("administrador_gestion", {}),
            ):
                body = self.client.get(reverse(ruta_adm, kwargs=kw))
                no_pii = tuple(x for x in (rut_orig, tel_orig) if x)
                if no_pii:
                    self.assertContrastePositivoNegativo(body, no_debe_estar=no_pii, contexto=f"PII {ruta_adm}")

        # 6. Primer login y expiración > 180 días + rotación exitosa
        self.client.logout()
        cache.clear()
        perfil_m.debe_cambiar_clave = True
        perfil_m.save()
        resp_primer = self.client.post(
            reverse("login"), {"username": "dsilva", "password": "safari123"}, follow=True
        )
        self.assertRedirects(resp_primer, reverse("cambiar_clave_expirada"))
        self.assertContains(resp_primer, "Primer inicio de sesión")

        self.client.logout()
        cache.clear()
        perfil_m.debe_cambiar_clave = False
        perfil_m.fecha_cambio_clave = timezone.now() - timedelta(days=181)
        perfil_m.save()
        self.assertTrue(perfil_m.clave_expirada())
        resp_exp = self.client.post(
            reverse("login"), {"username": "dsilva", "password": "safari123"}, follow=True
        )
        self.assertRedirects(resp_exp, reverse("cambiar_clave_expirada"))
        self.assertContains(resp_exp, "Actualización Obligatoria de Contraseña")

        resp_rot = self.client.post(
            reverse("cambiar_clave_expirada"),
            {
                "clave_actual": "safari123",
                "nueva_clave": "Safari.NuevoPass2026!",
                "confirmar_clave": "Safari.NuevoPass2026!",
            },
            follow=True,
        )
        self.assertContains(resp_rot, "Contraseña actualizada exitosamente")
        perfil_m.refresh_from_db()
        self.assertFalse(perfil_m.clave_expirada())
        self.mesero_user.refresh_from_db()
        self.assertTrue(self.mesero_user.check_password("Safari.NuevoPass2026!"))

    def test_asignacion_admin_roles_cocinero_y_barra_y_acceso_kds(self):
        """Admin puede asignar roles COCINERO y BARRA en trabajadores; cada rol accede directo a su ventana KDS."""
        self.client.force_login(self.admin_user)
        url_trab = reverse("administrador_trabajadores")

        resp_admin_html = self.client.get(url_trab)
        self.assertEqual(resp_admin_html.status_code, 200)
        self.assertContains(resp_admin_html, 'value="COCINERO"')
        self.assertContains(resp_admin_html, 'value="BARRA"')

        resp_gestion_html = self.client.get(reverse("administrador_gestion"))
        self.assertEqual(resp_gestion_html.status_code, 200)
        self.assertContains(resp_gestion_html, 'value="BARRA"')

        for uname, rol_codigo, ruta_esperada in (
            ("chef_nuevo", "COCINERO", "cocina"),
            ("barista_nuevo", "BARRA", "barra"),
        ):
            resp_crear = self.client.post(
                url_trab,
                {
                    "accion": "crear",
                    "nombre": "Personal",
                    "apellido": rol_codigo.title(),
                    "username": uname,
                    "rut": "19.123.456-7" if rol_codigo == "COCINERO" else "19.765.432-1",
                    "rol": rol_codigo,
                    "local_id": self.pv_central.id,
                    "password": "SafariKds!2026",
                },
                follow=True,
            )
            self.assertContains(resp_crear, "registrado con éxito")
            u_trab = User.objects.get(username=uname)
            self.assertEqual(u_trab.perfil.rol, rol_codigo)
            self.assertTrue(u_trab.password.startswith(("pbkdf2_sha256$", "argon2$")))
            u_trab.perfil.debe_cambiar_clave = False
            u_trab.perfil.save(update_fields=["debe_cambiar_clave"])

        # Reasignación de rol en modificación existente (BARRA <-> COCINERO)
        u_bar = User.objects.get(username="barista_nuevo")
        self.client.post(
            url_trab,
            {
                "accion": "modificar",
                "perfil_id": u_bar.perfil.id,
                "nombre": "Personal",
                "apellido": "CocinaTemp",
                "rol": "COCINERO",
                "local_id": self.pv_central.id,
            },
            follow=True,
        )
        u_bar.perfil.refresh_from_db()
        self.assertEqual(u_bar.perfil.rol, "COCINERO")

        self.client.post(
            url_trab,
            {
                "accion": "modificar",
                "perfil_id": u_bar.perfil.id,
                "nombre": "Personal",
                "apellido": "Barra",
                "rol": "BARRA",
                "local_id": self.pv_central.id,
            },
            follow=True,
        )
        u_bar.perfil.refresh_from_db()
        self.assertEqual(u_bar.perfil.rol, "BARRA")

        # Worker BARRA: al entrar a / redirige directo a /barra/, entra con 200 y queda aislado de cocina/admin/caja/mesero
        self.client.force_login(u_bar)
        self.assertRedirects(self.client.get(reverse("index"), follow=False), reverse("barra"))
        resp_barra = self.client.get(reverse("barra"))
        self.assertEqual(resp_barra.status_code, 200)
        self.assertContrastePositivoNegativo(
            resp_barra,
            debe_estar=("Barra Activa",),
            no_debe_estar=("Ir a Cocina",),
            contexto="Puesto de Barra sin botón de Cocina",
        )
        for ruta_prohibida in ("cocina", "administrador", "vendedor", "mesero", "mi_privacidad"):
            with self.subTest(rol="BARRA", bloqueada=ruta_prohibida):
                self.assertRedirects(self.client.get(reverse(ruta_prohibida), follow=True), reverse("barra"))

        # Worker COCINERO creado desde Trabajadores: al entrar a / redirige directo a /cocina/
        u_chef = User.objects.get(username="chef_nuevo")
        self.client.force_login(u_chef)
        self.assertRedirects(self.client.get(reverse("index"), follow=False), reverse("cocina"))
        self.assertEqual(self.client.get(reverse("cocina")).status_code, 200)

    def test_desbloqueo_pos_pin_cifrado_sin_filtracion(self):
        self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        self.cajero_user.set_password("ClavePosSeguro#2026")
        self.cajero_user.save()
        self.client.force_login(self.cajero_user)

        resp = self.client.get(reverse("vendedor"))
        self.assertNotIn("pins_validos_json", resp.context)
        self.assertNotIn("pin_hint", resp.context)
        url_pin = reverse("api_desbloquear_pin_pos")
        self.assertContrastePositivoNegativo(
            resp,
            debe_estar=("vendedorConfigData", url_pin),
            no_debe_estar=("pinsValidos", "btnPinAyuda", "boxPinPistas", "btnDesbloqueoDirecto"),
            contexto="Terminal vendedor sin pistas de PIN",
        )

        self.assertEqual(self.client.post(url_pin, {"accion": "desbloquear", "pin": "1234"}).status_code, 403)
        self.assertEqual(self.client.post(url_pin, {"accion": "desbloquear", "password": "mal"}).status_code, 403)
        r_pwd = self.client.post(url_pin, {"accion": "desbloquear", "password": "ClavePosSeguro#2026"})
        self.assertEqual(r_pwd.status_code, 200)
        self.assertTrue(r_pwd.json()["ok"])

        r_cfg = self.client.post(
            url_pin,
            {"accion": "configurar_pin", "password": "ClavePosSeguro#2026", "nuevo_pin": "4927"},
        )
        self.assertEqual(r_cfg.status_code, 200)
        self.cajero_user.perfil.refresh_from_db()
        self.assertNotEqual(self.cajero_user.perfil.pin_operativo_hash, "4927")
        self.assertNotIn("4927", self.cajero_user.perfil.pin_operativo_hash)
        self.assertTrue(self.cajero_user.perfil.check_pin_operativo("4927"))

        self.assertEqual(self.client.post(url_pin, {"accion": "desbloquear", "pin": "4927"}).status_code, 200)
        self.assertEqual(self.client.post(url_pin, {"accion": "desbloquear", "pin": "0000"}).status_code, 403)

        ultimo = None
        for _ in range(8):
            ultimo = self.client.post(url_pin, {"accion": "desbloquear", "pin": "0000"}).status_code
        self.assertEqual(ultimo, 429)

    def test_sesiones_expiracion_servidor_y_rls_local_e_huerfanos(self):
        # 1. Expiración en servidor + Clear-Site-Data
        self.client.force_login(self.cajero_user)
        self.assertEqual(self.client.get(reverse("vendedor")).status_code, 200)

        sesion = self.client.session
        sesion["_safari_last_activity"] = _time.time() - (settings.SESSION_INACTIVITY_TIMEOUT + 30)
        sesion.save()
        self.assertEqual(self.client.get(reverse("api_sincronizacion_estado")).status_code, 401)

        self.client.force_login(self.cajero_user)
        s2 = self.client.session
        s2["_safari_last_activity"] = _time.time() - (settings.SESSION_INACTIVITY_TIMEOUT + 30)
        s2.save()
        resp_redir = self.client.get(reverse("mi_privacidad"))
        self.assertEqual(resp_redir.status_code, 302)
        self.assertIn('"storage"', resp_redir.headers.get("Clear-Site-Data", ""))

        self.client.force_login(self.cajero_user)
        resp_out = self.client.get(reverse("logout"))
        self.assertEqual(resp_out.status_code, 302)
        self.assertIn('"cache"', resp_out.headers.get("Clear-Site-Data", ""))

        # 2. Row-Level Security entre Local 1 y Local 2 (IDOR 403 vs Admin 200)
        jornada = Jornada.objects.create(
            fecha=timezone.now().date(), estado="ABIERTA", usuario_apertura=self.admin_user
        )
        caja_l2 = Caja.objects.create(
            nombre="Caja Local 2 RLS",
            jornada=jornada,
            punto_venta=self.pv_selva,
            cajero=self.cajera2_user,
            monto_apertura=Decimal("20000"),
            estado="ABIERTA",
        )
        venta_l2 = Venta.objects.create(
            caja=caja_l2,
            cajero=self.cajera2_user,
            punto_venta=self.pv_selva,
            modalidad="MESON",
            total=Decimal("5000"),
            estado="PAGADA",
        )
        pedido_l2 = Pedido.objects.create(venta=venta_l2, estado="PENDIENTE")
        ticket_l2 = Ticket.objects.create(
            venta=venta_l2, punto_venta=self.pv_selva, tipo_destino="CLIENTE", codigo="TCK-L2-RLS"
        )

        self.client.force_login(self.cajero_user)
        self.assertEqual(
            self.client.get(reverse("ver_imprimir_ticket_digital", args=[ticket_l2.id])).status_code, 403
        )
        self.assertEqual(
            self.client.get(
                reverse("reimprimir_ticket", args=[ticket_l2.id]), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(f"{reverse('api_sincronizacion_estado')}?local_id={self.pv_selva.id}").status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("cambiar_estado_pedido"),
                {"pedido_id": pedido_l2.id, "nuevo_estado": "EN_PREPARACION"},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            ).status_code,
            403,
        )

        self.client.force_login(self.admin_user)
        self.assertEqual(
            self.client.get(reverse("ver_imprimir_ticket_digital", args=[ticket_l2.id])).status_code, 200
        )
        self.assertEqual(
            self.client.get(f"{reverse('api_sincronizacion_estado')}?local_id={self.pv_selva.id}").status_code,
            200,
        )

        # 3. Colaborador operativo sin local asignado -> 403 en vistas y sync
        for uname, rol, rutas in (
            ("mesero_huerfano", "MESERO", ("mesero", "barra", "api_sincronizacion_estado")),
            ("cocinero_huerfano", "COCINERO", ("cocina", "barra", "api_sincronizacion_estado")),
        ):
            u_h = User.objects.create_user(username=uname, password="HuerfanoOla3!2026")
            PerfilEmpleado.objects.create(
                usuario=u_h, rol=rol, punto_venta_actual=None, activo=True, debe_cambiar_clave=False
            )
            self.client.force_login(u_h)
            for ruta in rutas:
                with self.subTest(huerfano=uname, ruta=ruta):
                    self.assertEqual(self.client.get(reverse(ruta)).status_code, 403)


class PrivacidadConsentimientoYArcoTests(SafariDemoTestCase):
    """Consentimiento 1-vez por usuario, Cookies sin análisis previo, Derechos ARCO y purga 30d."""

    def test_consentimiento_login_una_vez_y_cookies_sin_analisis_previo(self):
        resp_priv = self.client.get(reverse("politica_privacidad"))
        self.assertContrastePositivoNegativo(
            resp_priv,
            debe_estar=(
                "¿Para qué usamos los datos?",
                "¿Qué datos pedimos?",
                "¿Con quién se comparten?",
                "Plazos Definidos de Retención",
            ),
            contexto="/privacidad/",
        )
        resp_term = self.client.get(reverse("terminos_condiciones"))
        self.assertContains(resp_term, "Naturaleza Académica del Sistema")

        # 1er ingreso sin marcar casilla -> rechazado
        self.cajero_user.set_password("ClaveUnaVez#2026")
        self.cajero_user.save()
        r_sin = self.client.post(
            reverse("login"),
            {"username": "cvalenzuela", "password": "ClaveUnaVez#2026", "portal_consent_required": "1"},
            follow=True,
        )
        self.assertFalse(r_sin.context["user"].is_authenticated)
        self.assertContains(r_sin, "aceptar la Política de Privacidad")

        # 1er ingreso aceptando -> autentica, emite token HMAC sin username crudo, registra en BD
        r_primero = self.client.post(
            reverse("login"),
            {
                "username": "cvalenzuela",
                "password": "ClaveUnaVez#2026",
                "portal_consent_required": "1",
                "acepto_politicas": "1",
            },
            follow=False,
        )
        self.assertEqual(r_primero.status_code, 302)
        self.assertIn("safari_ack_users", r_primero.cookies)
        ack_vals = json.loads(unquote(r_primero.cookies["safari_ack_users"].value))
        hash_cval = hash_alias_navegador("cvalenzuela")
        self.assertIn(hash_cval, ack_vals)
        self.assertNotIn("cvalenzuela", ",".join(ack_vals))

        reg = RegistroConsentimiento.objects.filter(usuario=self.cajero_user, origen="LOGIN_PORTAL").first()
        self.assertIsNotNone(reg)
        self.assertTrue(reg.acepto_privacidad and reg.acepto_terminos)
        self.assertFalse(reg.acepto_cookies_analisis)
        self.assertTrue(reg.es_integro())

        # Mismo usuario pasa en 2do login y desde otro navegador sin volver a pedir casilla
        self.client.get(reverse("logout"), follow=True)
        resp_idx = self.client.get(reverse("index"))
        self.assertIn(hash_cval, resp_idx.context["ack_config"]["tokens"])
        r_seg = self.client.post(
            reverse("login"),
            {"username": "cvalenzuela", "password": "ClaveUnaVez#2026", "portal_consent_required": "1"},
            follow=True,
        )
        self.assertTrue(r_seg.context["user"].is_authenticated)

        otro_nav = Client()
        r_otro = otro_nav.post(
            reverse("login"),
            {"username": "cvalenzuela", "password": "ClaveUnaVez#2026", "portal_consent_required": "1"},
            follow=True,
        )
        self.assertTrue(r_otro.context["user"].is_authenticated)

        # Otro usuario distinto (dsilva) en el MISMO navegador aún debe aceptar su 1ª vez
        self.client.get(reverse("logout"), follow=True)
        r_otro_user = self.client.post(
            reverse("login"),
            {
                "username": "dsilva",
                "password": "",
                "demo_rol_eval": "dsilva",
                "portal_consent_required": "1",
            },
            follow=True,
        )
        self.assertFalse(r_otro_user.context["user"].is_authenticated)

        # Cookies esenciales + CSRF en /privacidad/ y /terminos/ + rate-limit 429
        resp_esenc = self.client.post(
            reverse("registrar_consentimiento"),
            data=json.dumps({"analytics": False, "acepto_privacidad": True, "acepto_terminos": True}),
            content_type="application/json",
        )
        self.assertEqual(resp_esenc.status_code, 200)
        self.assertFalse(resp_esenc.json()["analytics"])
        cookie_val = json.loads(unquote(resp_esenc.cookies["safari_cookie_prefs"].value))
        self.assertFalse(cookie_val["analytics"])
        self.assertNotIn("\\054", resp_esenc.cookies["safari_cookie_prefs"].OutputString())

        csrf_client = Client(enforce_csrf_checks=True)
        for ruta_info in ("politica_privacidad", "terminos_condiciones"):
            resp_info = csrf_client.get(reverse(ruta_info))
            m_tok = re.search(
                rb'id=["\x27]safariCookieCsrfToken["\x27][^>]*value=["\x27]([^"\x27]+)["\x27]',
                resp_info.content,
            )
            self.assertIsNotNone(m_tok)
            resp_post_csrf = csrf_client.post(
                reverse("registrar_consentimiento"),
                data=json.dumps({"analytics": True, "acepto_privacidad": True, "acepto_terminos": True}),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=m_tok.group(1).decode(),
            )
            self.assertEqual(resp_post_csrf.status_code, 200)
            self.assertTrue(resp_post_csrf.json()["analytics"])
            self.assertTrue(csrf_client.get(reverse("politica_privacidad")).context["analytics_habilitado"])

        cache.clear()
        url_cons = reverse("registrar_consentimiento")
        for _ in range(30):
            self.assertEqual(
                self.client.post(
                    url_cons, data=json.dumps({"analytics": False}), content_type="application/json"
                ).status_code,
                200,
            )
        bloqueado = self.client.post(
            url_cons, data=json.dumps({"analytics": False}), content_type="application/json"
        )
        self.assertEqual(bloqueado.status_code, 429)
        self.assertIn("Retry-After", bloqueado.headers)

    def test_derechos_arco_ver_rectificar_borrar_y_retencion_30d(self):
        # 0. Contraste Negativo: trabajadores operativos NO pueden ver ni alterar datos propios en /mi-privacidad/
        cache.clear()
        trabajadores_bloqueados = [
            (self.mesero_user, "mesero"),
            (self.cajero_user, "vendedor"),
            (self.cocinero_user, "cocina"),
        ]
        for usuario, ruta_propia in trabajadores_bloqueados:
            usuario.refresh_from_db()
            snapshot = (
                usuario.first_name,
                usuario.last_name,
                usuario.email,
                usuario.perfil.telefono,
                usuario.is_active,
                usuario.username,
            )
            self.client.force_login(usuario)
            resp_get_bloqueado = self.client.get(reverse("mi_privacidad"), follow=True)
            self.assertRedirects(resp_get_bloqueado, reverse(ruta_propia))
            self.assertNotContains(resp_get_bloqueado, "1. Datos Almacenados Actualmente")

            for payload_post in (
                {"accion": "rectificar", "first_name": "CambioNoAutorizado", "email": "hack@ejemplo.cl"},
                {"accion": "borrar_opcionales"},
                {"accion": "eliminar_cuenta", "confirmacion": "CONFIRMAR", "password_confirmacion": "SafariPass#1"},
            ):
                resp_post_bloqueado = self.client.post(reverse("mi_privacidad"), payload_post, follow=True)
                self.assertRedirects(resp_post_bloqueado, reverse(ruta_propia))

            usuario.refresh_from_db()
            self.assertEqual(
                (
                    usuario.first_name,
                    usuario.last_name,
                    usuario.email,
                    usuario.perfil.telefono,
                    usuario.is_active,
                    usuario.username,
                ),
                snapshot,
            )

        # 1. Contraste Positivo (Solo ADMINISTRADOR): ver datos propios (nunca contraseña en texto plano)
        admin_arco = User.objects.create_user(
            username="admin_arco_temp",
            first_name="Administrador",
            last_name="Temporal",
            email="admin.arco@safari.cl",
            password="ClaveArcoTest#2026",
        )
        PerfilEmpleado.objects.create(
            usuario=admin_arco,
            rol="ADMINISTRADOR",
            rut="18.222.333-4",
            punto_venta_actual=self.pv_central,
            activo=True,
            debe_cambiar_clave=False,
        )
        self.client.force_login(admin_arco)
        resp_ver = self.client.get(reverse("mi_privacidad"))
        self.assertContrastePositivoNegativo(
            resp_ver, debe_estar=(admin_arco.username,), no_debe_estar=("safari123",), contexto="ARCO Ver Admin"
        )

        # 2. Rectificar + sanitizar XSS + bloquear escalada desde Administrador
        self.client.post(
            reverse("mi_privacidad"),
            {
                "accion": "rectificar",
                "first_name": "<b>Camila</b>",
                "last_name": "Gómez Actualizada",
                "email": "cgomez.arco@ejemplo.cl",
                "telefono": "+56 9 5555 4444",
                "rol": "SUPER_ADMIN",
            },
            follow=True,
        )
        admin_arco.refresh_from_db()
        self.assertEqual(admin_arco.first_name, "Camila")
        self.assertEqual(admin_arco.last_name, "Gómez Actualizada")
        self.assertEqual(admin_arco.email, "cgomez.arco@ejemplo.cl")
        self.assertEqual(admin_arco.perfil.rol, "ADMINISTRADOR")

        # 3. Borrar opcionales como Administrador
        self.client.post(reverse("mi_privacidad"), {"accion": "borrar_opcionales"})
        admin_arco.refresh_from_db()
        self.assertEqual(admin_arco.email, "")
        self.assertEqual(admin_arco.perfil.telefono, "")

        # 4. Baja ARCO + anonimización sin conservar IP/UA en evento de revocación
        rf = RequestFactory()
        req = rf.post("/mi-privacidad/", REMOTE_ADDR="190.10.20.55", HTTP_USER_AGENT="SafariTestBrowser/1.0")
        u_arco = User.objects.create_user(
            username="usuario_arco_ola3",
            first_name="Diego",
            last_name="Rojas",
            email="diego.arco@safari.cl",
            password="ArcoOla3!2026",
        )
        PerfilEmpleado.objects.create(
            usuario=u_arco,
            rol="MESERO",
            rut="19.111.222-3",
            punto_venta_actual=self.pv_central,
            activo=True,
            debe_cambiar_clave=False,
        )
        reg = RegistroConsentimiento.objects.create(
            usuario=u_arco,
            username_snapshot="usuario_arco_ola3",
            rol_snapshot="MESERO",
            origen="LOGIN_PORTAL",
            version_politica="1.0",
            version_terminos="1.0",
            acepto_privacidad=True,
            acepto_terminos=True,
            acepto_cookies_analisis=False,
            ip_hash="hash_ip_demo_35d",
            user_agent_hash="hash_ua_demo_35d",
        )
        RegistroConsentimiento.objects.filter(pk=reg.pk).update(aceptado_en=timezone.now() - timedelta(days=35))

        antiguo_cookie = RegistroConsentimiento.objects.create(
            usuario=None,
            username_snapshot="visitante_expirado",
            origen="COOKIE_BANNER",
            acepto_privacidad=True,
            acepto_terminos=True,
            acepto_cookies_analisis=False,
        )
        RegistroConsentimiento.objects.filter(pk=antiguo_cookie.pk).update(
            aceptado_en=timezone.now() - timedelta(days=45)
        )

        resumen = purgar_datos_por_retencion(dias_consentimiento=365, dias_inactivos=180)
        self.assertGreaterEqual(resumen["hashes_ip_purgados"], 1)
        self.assertGreaterEqual(resumen["cookies_anonimas_purgadas"], 1)
        reg.refresh_from_db()
        self.assertEqual(reg.ip_hash, "")
        self.assertEqual(reg.user_agent_hash, "")
        self.assertFalse(RegistroConsentimiento.objects.filter(pk=antiguo_cookie.pk).exists())

        anon_user = anonimizar_datos_usuario(u_arco, request=req)
        u_arco.refresh_from_db()
        self.assertFalse(u_arco.is_active)
        self.assertTrue(u_arco.username.startswith("anon_"))
        self.assertIsNone(u_arco.perfil.rut)

        ev_rev = RegistroConsentimiento.objects.filter(
            origen="REVOKE_ARCO", username_snapshot=f"{anon_user} (baja)"
        ).first()
        self.assertIsNotNone(ev_rev)
        self.assertEqual(ev_rev.ip_hash, "")
        self.assertEqual(ev_rev.user_agent_hash, "")

        # 5. Flujo HTTP completo de eliminación desde /mi-privacidad/ (con otro admin activo + bloqueo al último admin)
        self.client.force_login(admin_arco)
        resp_baja = self.client.post(
            reverse("mi_privacidad"),
            {
                "accion": "eliminar_cuenta",
                "confirmacion": "CONFIRMAR",
                "password_confirmacion": "ClaveArcoTest#2026",
            },
        )
        self.assertEqual(resp_baja.status_code, 302)
        admin_arco.refresh_from_db()
        self.assertFalse(admin_arco.is_active)
        self.assertTrue(admin_arco.username.startswith("anon_"))

        # Protección anti-lockout: el último Administrador activo no puede autoeliminarse
        PerfilEmpleado.objects.filter(rol="ADMINISTRADOR", activo=True).exclude(usuario=self.admin_user).update(activo=False)
        self.admin_user.set_password("ClaveUnicoAdmin#2026")
        self.admin_user.save()
        self.client.force_login(self.admin_user)
        resp_unico_admin = self.client.post(
            reverse("mi_privacidad"),
            {
                "accion": "eliminar_cuenta",
                "confirmacion": "CONFIRMAR",
                "password_confirmacion": "ClaveUnicoAdmin#2026",
            },
            follow=True,
        )
        self.assertContains(resp_unico_admin, "único Administrador activo")
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.is_active)
