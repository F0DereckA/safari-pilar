import os
import re
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ventas.models import Caja, Jornada, Ticket, Venta
from ventas.security import (
    cifrar_dato_pii,
    descifrar_dato_pii,
    hash_dato_sensible,
    limpiar_texto_seguro,
    obtener_ip_segura,
)
from ventas.templatetags.safari_tags import pesos, pesos_clp
from ventas.test_suites.base import ContrasteAssertMixin, SafariDemoTestCase
from ventas.utils import calcular_redondeo_ley_20956


class ArquitecturaEstaticosSimpleTests(ContrasteAssertMixin, SimpleTestCase):
    """
    Pruebas puras sin base de datos (<0.1s): formateo CLP, matriz completa Ley 20.956,
    higiene de secretos, configuración productiva, cifrado PII y auditoría estática CSP/CSS/HTML.
    """

    def test_filtro_pesos_chilenos_subtest(self):
        casos = [
            (pesos, 1000, "1.000"),
            (pesos, 20000, "20.000"),
            (pesos, 1000000, "1.000.000"),
            (pesos_clp, 25400, "$25.400"),
            (pesos_clp, 1000000, "$1.000.000"),
            (pesos_clp, 0, "$0"),
        ]
        for fn, entrada, esperado in casos:
            with self.subTest(fn=fn.__name__, entrada=entrada):
                self.assertEqual(fn(entrada), esperado)

    def test_redondeo_ley_20956_matriz_contraste_efectivo_vs_tarjeta(self):
        """Contraste tributario: EFECTIVO redondea decena (<=4 baja, >=5 sube); TARJETAS ajuste 0."""
        casos_efectivo = [
            ("1000", "1000", "0"),
            ("1001", "1000", "-1"),
            ("1323", "1320", "-3"),
            ("1994", "1990", "-4"),
            ("1995", "2000", "5"),
            ("1326", "1330", "4"),
            ("1829", "1830", "1"),
            ("1999", "2000", "1"),
        ]
        for bruto, esperado, ajuste in casos_efectivo:
            with self.subTest(metodo="EFECTIVO", bruto=bruto):
                final, adj = calcular_redondeo_ley_20956(Decimal(bruto), "EFECTIVO")
                self.assertEqual(final, Decimal(esperado))
                self.assertEqual(adj, Decimal(ajuste))

        for metodo in ("DEBITO", "CREDITO", "TRANSFERENCIA"):
            for bruto in ("1995", "1997", "1821", "1826"):
                with self.subTest(metodo=metodo, bruto=bruto):
                    final, adj = calcular_redondeo_ley_20956(Decimal(bruto), metodo)
                    self.assertEqual(final, Decimal(bruto))
                    self.assertEqual(adj, Decimal("0"))

    def test_politica_cero_credenciales_produccion_y_multi_motor(self):
        base = Path(settings.BASE_DIR)

        self.assertTrue(bool(settings.SECRET_KEY))
        self.assertGreater(len(settings.SECRET_KEY), 20)

        env_example = (base / ".env.example").read_text(encoding="utf-8")
        self.assertContrastePositivoNegativo(
            env_example,
            debe_estar=("SECRET_KEY", "DB_ENGINE", "postgresql"),
            contexto=".env.example",
        )

        gitignore = (base / ".gitignore").read_text(encoding="utf-8")
        self.assertContrastePositivoNegativo(
            gitignore,
            debe_estar=(".env", "!.env.example"),
            contexto=".gitignore",
        )

        # Contraste negativo: sin credenciales hardcodeadas ni hashers rápidos en producción
        login_js = (base / "static" / "js" / "acceso" / "login.js").read_text(encoding="utf-8")
        utils_py = (base / "ventas" / "utils.py").read_text(encoding="utf-8")
        settings_py = (base / "Venta_safari" / "settings.py").read_text(encoding="utf-8")

        self.assertNotIn("safari123", login_js)
        self.assertNotIn("safari_secret_key_antifraude_default", utils_py)
        self.assertNotIn("SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-", settings_py)

        # Aislamiento de PasswordHasher rápido exclusivo para runner de pruebas
        from Venta_safari import settings as safari_settings

        self.assertIn(
            "django.contrib.auth.hashers.PBKDF2PasswordHasher",
            settings.PASSWORD_HASHERS,
        )
        self.assertNotIn(
            "FastTestPBKDF2PasswordHasher",
            safari_settings._BASE_PASSWORD_HASHERS[0],
        )

        # Multi-motor BD y parámetros productivos (requirements, Mailers, HSTS, Proxy, Demo mode)
        self.assertIn(
            settings.DATABASES["default"]["ENGINE"],
            [
                "django.db.backends.sqlite3",
                "django.db.backends.postgresql",
                "django.db.backends.mysql",
            ],
        )
        req_txt = (base / "requirements.txt").read_text(encoding="utf-8").lower()
        self.assertIn("openpyxl", req_txt)
        self.assertIn("python-docx", req_txt)

        self.assertFalse(getattr(settings, "SAFARI_TRUST_PROXY", True))
        self.assertIn("MAILERS", dir(settings))
        self.assertIn("'default'", repr(settings.MAILERS))
        self.assertContrastePositivoNegativo(
            settings_py,
            debe_estar=("smtp.EmailBackend", "SECURE_HSTS_SECONDS", "SAFARI_DEMO_MODE"),
            contexto="settings.py productivo",
        )

    def test_obtener_ip_segura_protegida_contra_spoofing_proxy(self):
        rf = RequestFactory()
        req = rf.get("/", REMOTE_ADDR="190.10.20.30", HTTP_X_FORWARDED_FOR="8.8.8.8, 1.1.1.1")
        with override_settings(SAFARI_TRUST_PROXY=False):
            self.assertEqual(obtener_ip_segura(req), "190.10.20.30")

        with override_settings(SAFARI_TRUST_PROXY=True):
            # Último salto agregado por proxy confiable; nunca primer salto manipulable
            self.assertEqual(obtener_ip_segura(req), "1.1.1.1")

        req_inval = rf.get("/", REMOTE_ADDR="190.10.20.30", HTTP_X_FORWARDED_FOR="bad-ip-spoof")
        with override_settings(SAFARI_TRUST_PROXY=True):
            self.assertEqual(obtener_ip_segura(req_inval), "190.10.20.30")

    def test_cifrado_pii_hashing_y_sanitizacion_xss(self):
        secreto = "18.111.222-K|turno-noche"
        token = cifrar_dato_pii(secreto)
        self.assertNotEqual(token, secreto)
        self.assertEqual(descifrar_dato_pii(token), secreto)
        self.assertEqual(descifrar_dato_pii(token + "tamper"), "")

        h1 = hash_dato_sensible("192.168.1.55", contexto="audit")
        self.assertEqual(len(h1), 64)
        self.assertNotIn("192.168.1.55", h1)

        limpio = limpiar_texto_seguro("<script>alert(1)</script>Carlos")
        self.assertEqual(limpio, "alert(1)Carlos")

    def test_css_accesibilidad_y_js_csp_sin_inline(self):
        base_dir = Path(settings.BASE_DIR)
        base_css = (base_dir / "static" / "css" / "global" / "base.css").read_text(encoding="utf-8")
        for token in (
            ":focus-visible",
            "#fde047",
            ".text-lcd-amber",
            ".text-lcd-green",
            ".text-on-brand-muted",
            "prefers-reduced-motion",
            "forced-colors",
        ):
            with self.subTest(token_css=token):
                self.assertIn(token, base_css)

        for css_file in (base_dir / "static" / "css").rglob("*.css"):
            css_txt = css_file.read_text(encoding="utf-8")
            with self.subTest(css_file=css_file.name):
                self.assertIsNone(
                    re.search(r"outline\s*:\s*(?:none|0)\b", css_txt),
                    f"outline:none/0 sin :focus-visible en {css_file}",
                )

        mesero_css = (base_dir / "static" / "css" / "mesero" / "mesero.css").read_text(encoding="utf-8")
        mesero_html = (
            base_dir / "ventas" / "templates" / "ventas" / "mesero" / "mesero.html"
        ).read_text(encoding="utf-8")
        for clase in (
            "mesa-card",
            "product-mesero-card",
            "comanda-mesero-panel",
            "qty-control-btn",
            "btn-nota-plato",
            "btn-comensal",
            "btn-modo-sol",
        ):
            self.assertIn(f".{clase}", mesero_css)
            self.assertIn(clase, mesero_html)

        # Scripts globales de sesión y filtro reactivo
        filtro_js = (base_dir / "static" / "js" / "global" / "filtro_tiempo_real.js").read_text(encoding="utf-8")
        sesion_js = (base_dir / "static" / "js" / "global" / "seguridad_sesion.js").read_text(encoding="utf-8")
        self.assertContrastePositivoNegativo(
            filtro_js, debe_estar=("addEventListener('input'", "SafariFiltroEnVivo"), contexto="filtro_tiempo_real.js"
        )
        self.assertContrastePositivoNegativo(
            sesion_js, debe_estar=("reiniciarTiempoSesion", "indicadorSesionSafari"), contexto="seguridad_sesion.js"
        )

        # Cero eventos inline ni URIs javascript: en todo JS estático
        for js_file in (base_dir / "static" / "js").rglob("*.js"):
            js_txt = js_file.read_text(encoding="utf-8")
            with self.subTest(js_file=js_file.name):
                self.assertIsNone(
                    re.search(r"\bon(?:click|change|input|submit)\s*=", js_txt),
                    f"Atributo inline dinamico hallado en {js_file}",
                )
                self.assertIsNone(
                    re.search(r"javascript\s*:", js_txt),
                    f"URI javascript: hallada en {js_file}",
                )

    def test_plantillas_patrones_contraste_y_cero_inline_csp(self):
        """Audita 100% de plantillas HTML: contraste legible (emphasis) y cero <style>/<script> inline."""
        base = Path(settings.BASE_DIR)
        static_root = base / "static"
        patrones_prohibidos = [
            re.compile(r"\btext-light-subtle\b"),
            re.compile(r"\bbtn-outline-light\b[^\"']*\btext-white\b"),
            re.compile(r"\bbtn-outline-(?:warning|info)\b[^\"']*\btext-dark\b"),
            re.compile(r"\btext-warning\b(?!-emphasis)"),
            re.compile(r"\btext-info\b(?!-emphasis)"),
            re.compile(r"\btext-white-50\b"),
        ]

        html_files = (
            list((base / "templates").rglob("*.html"))
            + list((base / "ventas" / "templates" / "ventas").rglob("*.html"))
        )
        self.assertGreaterEqual(len(html_files), 30, "Deben auditarse al menos 30 plantillas")

        for hf in html_files:
            txt = hf.read_text(encoding="utf-8")
            with self.subTest(plantilla=str(hf.relative_to(base))):
                self.assertEqual(len(re.findall(r"<style\b[^>]*>(.*?)</style>", txt, re.S | re.I)), 0)
                scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", txt, re.S | re.I)
                inline_js = [
                    body
                    for attrs, body in scripts
                    if "src=" not in attrs.lower()
                    and "application/json" not in attrs.lower()
                    and body.strip()
                ]
                self.assertEqual(len(inline_js), 0, f"{hf.name} contiene <script> JS ejecutable")
                for ref in re.findall(r"""\{%\s*static\s+['"]([^'"]+)['"]\s*%\}""", txt):
                    self.assertTrue(os.path.exists(static_root / ref), f"Falta static/{ref} referenciado en {hf.name}")
                for pat in patrones_prohibidos:
                    self.assertIsNone(pat.search(txt), f"Patrón bajo contraste {pat.pattern} en {hf.name}")

        banner_html = (
            base / "ventas" / "templates" / "ventas" / "acceso" / "include_cookie_banner.html"
        ).read_text(encoding="utf-8")
        self.assertContrastePositivoNegativo(
            banner_html,
            debe_estar=("text-success-emphasis", "bg-success-subtle"),
            no_debe_estar=("bg-success-subtle text-success ", 'bg-success-subtle text-success"'),
            contexto="Cookie banner badge WCAG AA",
        )


class ArquitecturaRenderCspYContrastTests(SafariDemoTestCase):
    """Pruebas renderizadas de arquitectura modular, responsive, CSP DOM y contraste UI."""

    def _parse_html_contract(self, html_text):
        findings = {
            "style_tags": 0,
            "exec_scripts": 0,
            "inline_events": [],
            "js_uris": [],
            "footers": 0,
            "headings": [],
            "modals_missing_label": 0,
            "close_btns_missing_aria": 0,
            "orphan_inputs": [],
        }

        class DomContractParser(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=False)
                self.stack = []
                self.labels_for = set()
                self.raw_inputs = []

            def handle_starttag(self, tag, attrs):
                t = tag.lower()
                ad = dict(attrs)
                for k, v in attrs:
                    kl = k.lower()
                    if kl.startswith("on") and kl != "on":
                        findings["inline_events"].append((t, k, v))
                    if v and "javascript:" in str(v).lower():
                        findings["js_uris"].append((t, k, v))
                self.stack.append({"tag": t})
                if t == "style":
                    findings["style_tags"] += 1
                elif t == "script":
                    stype = (ad.get("type") or "").strip().lower()
                    if not ad.get("src") and stype != "application/json":
                        findings["exec_scripts"] += 1
                elif t == "footer":
                    findings["footers"] += 1
                elif t in ("h1", "h2", "h3", "h4", "h5", "h6"):
                    findings["headings"].append(int(t[1]))
                elif t == "label" and ad.get("for"):
                    self.labels_for.add(ad["for"])
                elif t in ("input", "select", "textarea"):
                    wrapped = any(s["tag"] == "label" for s in self.stack[:-1])
                    self.raw_inputs.append((t, ad, wrapped))
                cls = (ad.get("class") or "").split()
                if "modal" in cls and not ad.get("aria-labelledby") and not ad.get("aria-label"):
                    findings["modals_missing_label"] += 1
                if "btn-close" in cls and not ad.get("aria-label"):
                    findings["close_btns_missing_aria"] += 1

            def handle_startendtag(self, tag, attrs):
                self.handle_starttag(tag, attrs)
                self.handle_endtag(tag)

            def handle_endtag(self, tag):
                t = tag.lower()
                for idx in range(len(self.stack) - 1, -1, -1):
                    if self.stack[idx]["tag"] == t:
                        del self.stack[idx:]
                        break

        parser = DomContractParser()
        parser.feed(html_text)
        for t, ad, wrapped in parser.raw_inputs:
            itype = (ad.get("type") or "").lower()
            if itype in ("hidden", "submit", "button", "reset"):
                continue
            iid = ad.get("id")
            if not ((iid and iid in parser.labels_for) or wrapped or ad.get("aria-label") or ad.get("aria-labelledby")):
                findings["orphan_inputs"].append((t, iid, ad.get("name")))
        return findings

    def test_migracion_estaticos_css_js_img_por_zonas(self):
        """Contrato estructural obligatorio de carpetas por zona, raíz limpia y reglas AGENTS.md."""
        base = Path(settings.BASE_DIR)
        static_root = base / "static"
        zonas_estaticos = [
            "global",
            "acceso",
            "administrador",
            "cajero",
            "mesero",
            "kds",
            "impresion",
            "errores/400",
            "errores/500",
        ]
        for tipo in ("css", "js", "img"):
            for zona in zonas_estaticos:
                self.assertTrue((static_root / tipo / zona).is_dir(), f"Debe existir static/{tipo}/{zona}")

        for sub_err in ("400", "500"):
            self.assertTrue((base / "templates" / "errores" / sub_err).is_dir())
        self.assertEqual(list((base / "templates").glob("*.html")), [])

        for zona_tpl in ("acceso", "administrador", "cajero", "mesero", "kds", "impresion"):
            self.assertTrue((base / "ventas" / "templates" / "ventas" / zona_tpl).is_dir())
        self.assertEqual(list((base / "ventas" / "templates" / "ventas").glob("*.html")), [])

        for ext_prohibida in ("*.html", "*.docx", "*.xlsx", "*.png"):
            self.assertEqual(list(base.glob(ext_prohibida)), [], f"Raíz sucia con {ext_prohibida}")
        self.assertTrue((base / "AGENTS.md").is_file())
        self.assertTrue((base / ".agents" / "rules" / "orden_arquitectura_safari.md").is_file())

        self.assertEqual(self.client.get(reverse("qr_acceso")).status_code, 200)
        self.assertEqual(self.client.get("/ruta-inexistente-auditoria-orden/").status_code, 404)

    def test_inputs_numericos_caja_limpios_y_responsive_kds(self):
        """Inputs caja sin value='0' prellenado, responsive viewport y flexbox KDS sin recortes."""
        # Antes de abrir caja: sin value="0" prellenado
        self.client.force_login(self.cajero_user)
        resp_inicial = self.client.get(reverse("vendedor"))
        self.assertContrastePositivoNegativo(
            resp_inicial,
            debe_estar=('name="viewport"', "width=device-width"),
            no_debe_estar=('value="0"',),
            contexto="Caja inicial sin 0 prefijado",
        )

        # Abrir con campo vacío asume $0 en BD pero mantiene limpio el input arqueo
        self.client.post(reverse("abrir_jornada"), {"monto_apertura": ""}, follow=True)
        resp_activa = self.client.get(reverse("vendedor"))
        self.assertNotContains(resp_activa, 'value="0"')
        caja = Caja.objects.filter(cajero=self.cajero_user, estado="ABIERTA").first()
        self.assertIsNotNone(caja)
        self.assertEqual(int(caja.monto_apertura), 0)

        resp_ticket = self.client.get(reverse("crear_ticket"))
        self.assertContrastePositivoNegativo(
            resp_ticket,
            debe_estar=("mobile-comanda-bar", 'name="viewport"'),
            contexto="POS Responsive",
        )

        self.client.force_login(self.admin_user)
        self.assertContrastePositivoNegativo(
            self.client.get(reverse("administrador")),
            debe_estar=('name="viewport"', "table-responsive"),
            contexto="Admin Responsive",
        )

        self.client.force_login(self.mesero_user)
        self.assertContrastePositivoNegativo(
            self.client.get(reverse("mesero")),
            debe_estar=('name="viewport"', "mobile-comanda-bar"),
            contexto="Mesero Responsive",
        )

        self.client.force_login(self.cocinero_user)
        resp_cocina = self.client.get(reverse("cocina"))
        self.assertContrastePositivoNegativo(
            resp_cocina,
            debe_estar=('name="viewport"', "kds-header", "css/kds/cocina.css"),
            contexto="Cocina KDS",
        )
        cocina_css = (Path(settings.BASE_DIR) / "static" / "css" / "kds" / "cocina.css").read_text(encoding="utf-8")
        self.assertContrastePositivoNegativo(
            cocina_css,
            debe_estar=("flex-direction: column",),
            no_debe_estar=("flex-column: column",),
            contexto="Cocina flexbox CSS",
        )

        resp_barra = self.client.get(reverse("barra"))
        self.assertContains(resp_barra, "js/kds/barra.js")
        barra_js = (Path(settings.BASE_DIR) / "static" / "js" / "kds" / "barra.js").read_text(encoding="utf-8")
        self.assertIn("autoActualizarBarra", barra_js)

    def test_vistas_renderizadas_csp_dom_superficies_oscuras_y_xml_dte(self):
        """Audita DOM/CSP/WCAG de todas las rutas + superficies oscuras LCD/Balanza/XML DTE."""
        jornada, caja = self.abrir_jornada_y_caja(self.pv_central, self.cajero_user, admin=self.admin_user)
        venta = Venta.objects.create(
            caja=caja,
            cajero=self.cajero_user,
            punto_venta=self.pv_central,
            modalidad="VENTA_RAPIDA",
            metodo_pago="EFECTIVO",
            total=Decimal("4500"),
            estado="PAGADA",
        )
        ticket = Ticket.objects.create(
            venta=venta,
            punto_venta=self.pv_central,
            tipo_destino="CLIENTE",
            codigo="TCK-ARQ-CHECK",
            contenido_impresion="SAFARI ARQ",
        )

        rutas_publicas = [
            (reverse("index"), 200),
            (reverse("politica_privacidad"), 200),
            (reverse("terminos_condiciones"), 200),
            (reverse("qr_acceso"), 200),
            (reverse("error_400"), 400),
            (reverse("error_401"), 401),
            (reverse("error_403"), 403),
            (reverse("error_404"), 404),
            (reverse("error_500"), 500),
            (reverse("error_502"), 502),
            (reverse("error_503"), 503),
            (reverse("error_504"), 504),
        ]
        for url, expected_status in rutas_publicas:
            with self.subTest(zona="publica", url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, expected_status)
                findings = self._parse_html_contract(resp.content.decode("utf-8"))
                self.assertEqual(findings["style_tags"], 0)
                self.assertEqual(findings["exec_scripts"], 0)
                self.assertEqual(findings["inline_events"], [])
                self.assertEqual(findings["js_uris"], [])
                self.assertLessEqual(findings["footers"], 1)
                self.assertLessEqual(findings["headings"].count(1), 1)
                self.assertEqual(findings["modals_missing_label"], 0)
                self.assertEqual(findings["close_btns_missing_aria"], 0)
                self.assertEqual(findings["orphan_inputs"], [])

        self.client.force_login(self.admin_user)
        rutas_admin = [
            reverse("administrador"),
            reverse("administrador_local", args=[self.pv_central.id]),
            reverse("administrador_trabajadores"),
            reverse("administrador_mesas"),
            reverse("administrador_productos"),
            reverse("administrador_menus"),
            reverse("administrador_historial"),
            reverse("administrador_dashboard"),
            reverse("administrador_gestion"),
            reverse("administrador_consumos"),
            reverse("administrador_convenios"),
            reverse("administrador_ofertas_temporada"),
            reverse("mi_privacidad"),
        ]
        for url in rutas_admin:
            with self.subTest(zona="admin", url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                html = resp.content.decode("utf-8")
                findings = self._parse_html_contract(html)
                self.assertEqual(findings["style_tags"], 0)
                self.assertEqual(findings["exec_scripts"], 0)
                self.assertEqual(findings["inline_events"], [])
                self.assertEqual(findings["js_uris"], [])
                self.assertLessEqual(findings["footers"], 1)
                self.assertLessEqual(findings["headings"].count(1), 1)
                for a, b in zip(findings["headings"], findings["headings"][1:]):
                    self.assertLessEqual(b, a + 1, f"Salto h{a}->h{b} en {url}")
                self.assertEqual(findings["modals_missing_label"], 0)
                self.assertEqual(findings["close_btns_missing_aria"], 0)
                self.assertEqual(findings["orphan_inputs"], [])

        # Dashboard & Gestión UI markers
        self.assertContrastePositivoNegativo(
            self.client.get(reverse("administrador_dashboard")),
            debe_estar=('data-timeframe="mes"', 'aria-pressed="true"'),
            contexto="Dashboard timeframe contrast",
        )
        self.assertContrastePositivoNegativo(
            self.client.get(reverse("administrador_gestion")),
            debe_estar=('data-gestion-tab="trabajadores"', 'tabindex="0"'),
            contexto="Gestión tabs focus",
        )

        # Cajero routes + Balanza Digital + XML DTE dark surfaces
        self.client.force_login(self.cajero_user)
        for url in (
            reverse("vendedor"),
            reverse("crear_ticket"),
            reverse("ver_imprimir_ticket_digital", args=[ticket.id]),
        ):
            with self.subTest(zona="cajero", url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                findings = self._parse_html_contract(resp.content.decode("utf-8"))
                self.assertEqual(findings["style_tags"], 0)
                self.assertEqual(findings["exec_scripts"], 0)
                self.assertEqual(findings["inline_events"], [])
                self.assertEqual(findings["js_uris"], [])
                self.assertEqual(findings["modals_missing_label"], 0)
                self.assertEqual(findings["close_btns_missing_aria"], 0)
                self.assertEqual(findings["orphan_inputs"], [])

        html_pos = self.client.get(reverse("crear_ticket")).content.decode("utf-8")
        self.assertContrastePositivoNegativo(
            html_pos,
            debe_estar=(
                'id="modalPosBancarioSimulado"',
                'data-bs-theme="dark"',
                'data-pos-action="abrir-balanza"',
                'id="modalBalanzaDigital"',
                "balanza-digital-display",
                "balanzaDisplayPeso",
                "text-lcd-green",
            ),
            contexto="POS superficies oscuras y Balanza Digital",
        )

        html_ticket = self.client.get(reverse("ver_imprimir_ticket_digital", args=[ticket.id])).content.decode("utf-8")
        self.assertContrastePositivoNegativo(
            html_ticket,
            debe_estar=(
                "arbolXmlDteCollapse",
                "ticket-xml-pre",
                "text-lcd-amber",
                '&lt;TED version="1.0"&gt;',
                '&lt;CAF version="1.0"&gt;',
            ),
            contexto="Ticket digital Árbol XML DTE",
        )

        # Mesero y KDS
        self.client.force_login(self.mesero_user)
        findings_m = self._parse_html_contract(self.client.get(reverse("mesero")).content.decode("utf-8"))
        self.assertEqual(findings_m["inline_events"], [])
        self.assertEqual(findings_m["orphan_inputs"], [])
        self.assertLessEqual(findings_m["footers"], 1)

        self.client.force_login(self.cocinero_user)
        for url in (reverse("cocina"), reverse("barra")):
            findings_k = self._parse_html_contract(self.client.get(url).content.decode("utf-8"))
            self.assertEqual(findings_k["inline_events"], [])
            self.assertEqual(findings_k["orphan_inputs"], [])
            self.assertEqual(findings_k["modals_missing_label"], 0)

    def test_qr_acceso_dinamico_contraste_demo_vs_produccion(self):
        """Contraste Positivo/Negativo en /qr/: producción oculta credenciales demo e IP fija."""
        with override_settings(SAFARI_DEMO_MODE=False, ALLOWED_HOSTS=["pos.safari.local", "testserver"]):
            resp_prod = self.client.get(reverse("qr_acceso"), HTTP_HOST="pos.safari.local")
            self.assertEqual(resp_prod.status_code, 200)
            self.assertContrastePositivoNegativo(
                resp_prod,
                debe_estar=("http://pos.safari.local/",),
                no_debe_estar=("192.168.1.6", "Usuarios Operativos Demo", "cvalenzuela", "safari123"),
                contexto="QR modo producción",
            )

        with override_settings(SAFARI_DEMO_MODE=True, ALLOWED_HOSTS=["pos.safari.local", "testserver"]):
            resp_demo = self.client.get(reverse("qr_acceso"), HTTP_HOST="pos.safari.local")
            self.assertEqual(resp_demo.status_code, 200)
            self.assertContrastePositivoNegativo(
                resp_demo,
                debe_estar=("http://pos.safari.local/", "Usuarios Operativos Demo", "cvalenzuela"),
                no_debe_estar=("192.168.1.6", "safari123"),
                contexto="QR modo demo",
            )
