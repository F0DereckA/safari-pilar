/**
 * Venta Safari - Gestión de Consentimiento de Cookies y Telemetría
 * Principio estricto: Cero analítica hasta que el usuario acepte explícitamente.
 */
(function () {
    const COOKIE_NAME = 'safari_cookie_prefs';
    const POLICY_VERSION = '1.0-academica';

    function escribirPreferenciasCookieLocal(habilitarAnalisis) {
        const payload = {
            essential: true,
            analytics: Boolean(habilitarAnalisis),
            v: POLICY_VERSION
        };
        const encoded = encodeURIComponent(JSON.stringify(payload));
        const maxAge = 180 * 86400;
        const secureAttr = (window.location && window.location.protocol === 'https:') ? '; Secure' : '';
        document.cookie = COOKIE_NAME + '=' + encoded + '; Path=/; Max-Age=' + maxAge + '; SameSite=Lax' + secureAttr;
        return payload;
    }

    function intentarParsearPrefs(valorCrudo) {
        if (!valorCrudo) return null;
        let texto = valorCrudo.trim();
        let requeriaLimpieza = false;

        // Soportar formato legacy RFC-2109 con comillas y escapes octales (\054) generados por SimpleCookie
        if (texto.length >= 2 && texto[0] === '"' && texto[texto.length - 1] === '"') {
            texto = texto.slice(1, -1).replace(/\\"/g, '"').replace(/\\054/g, ',');
            requeriaLimpieza = true;
        }

        const candidatos = [texto];
        try {
            const decoded = decodeURIComponent(texto);
            if (decoded !== texto) candidatos.unshift(decoded);
        } catch (errDec) {
            // Ignorar si ya viene decodificado o con escape octal parcial
        }

        for (let j = 0; j < candidatos.length; j++) {
            let cand = candidatos[j].trim();
            if (cand.indexOf('\\054') !== -1) {
                cand = cand.replace(/\\054/g, ',').replace(/\\"/g, '"');
                requeriaLimpieza = true;
            }
            try {
                const parsed = JSON.parse(cand);
                if (parsed && typeof parsed === 'object' && parsed.essential === true) {
                    if (requeriaLimpieza) {
                        escribirPreferenciasCookieLocal(Boolean(parsed.analytics));
                    }
                    return parsed;
                }
            } catch (errParse) {
                // Intentar siguiente formato
            }
        }
        return null;
    }

    function leerPreferenciasCookie() {
        const prefix = COOKIE_NAME + '=';
        const partes = document.cookie ? document.cookie.split(';') : [];
        for (let i = 0; i < partes.length; i++) {
            const c = partes[i].trim();
            if (c.indexOf(prefix) === 0) {
                const rawVal = c.substring(prefix.length);
                const parsed = intentarParsearPrefs(rawVal);
                if (parsed) return parsed;
            }
        }
        return null;
    }

    // Estado inicial garantizado: analítica completamente bloqueada salvo consentimiento explícito
    const prefsIniciales = leerPreferenciasCookie();
    const analiticaInicial = Boolean(prefsIniciales && prefsIniciales.analytics === true);

    window.SafariTelemetry = {
        enabled: analiticaInicial,
        initialized: false,
        eventsQueue: [],
        init: function () {
            if (!this.enabled || this.initialized) return false;
            this.initialized = true;
            document.documentElement.setAttribute('data-safari-analytics', 'enabled');
            return true;
        },
        track: function (evento, detalle) {
            // Bloqueo estricto: jamás registrar analítica sin aceptación explícita previa
            if (!this.enabled) return false;
            if (!this.initialized) this.init();
            this.eventsQueue.push({ evento: String(evento || ''), ts: new Date().toISOString(), detalle: detalle || {} });
            return true;
        },
        disable: function () {
            this.enabled = false;
            this.initialized = false;
            this.eventsQueue = [];
            document.documentElement.setAttribute('data-safari-analytics', 'disabled');
        }
    };

    if (analiticaInicial) {
        window.SafariTelemetry.init();
    } else {
        document.documentElement.setAttribute('data-safari-analytics', 'disabled');
    }

    function obtenerCsrfToken() {
        const bannerCsrf = document.getElementById('safariCookieCsrfToken');
        if (bannerCsrf && bannerCsrf.value) return bannerCsrf.value;
        const inputToken = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (inputToken && inputToken.value) return inputToken.value;
        const hiddenGlobal = document.getElementById('csrfTokenVendedorGlobal') || document.getElementById('csrfTokenMeseroGlobal');
        if (hiddenGlobal && hiddenGlobal.value) return hiddenGlobal.value;
        const cookieMatch = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return cookieMatch ? decodeURIComponent(cookieMatch[1]) : '';
    }

    document.addEventListener('DOMContentLoaded', function () {
        const banner = document.getElementById('safariCookieBanner');
        const dialog = document.getElementById('dialogConfigCookies');
        const chkAnalisisDialog = document.getElementById('chkCookiesAnalisisDialog');
        const btnSoloEsenciales = document.getElementById('btnCookiesSoloEsenciales');
        const btnAceptarTodas = document.getElementById('btnCookiesAceptarTodas');
        const btnAbrirConfig = document.getElementById('btnCookiesAbrirConfig');
        const btnGuardarDialog = document.getElementById('btnGuardarCookiesDialog');
        const btnCerrarDialog = document.getElementById('btnCerrarDialogCookies');
        const urlEndpoint = (banner && banner.getAttribute('data-consent-url')) || '/privacidad/consentimiento/';
        let guardando = false;

        if (!banner) return;

        function sincronizarVistaConPrefs() {
            const actual = leerPreferenciasCookie();
            banner.hidden = Boolean(actual && actual.essential === true);
            if (chkAnalisisDialog) {
                chkAnalisisDialog.checked = Boolean(actual && actual.analytics === true);
            }
            if (actual && actual.analytics === true) {
                window.SafariTelemetry.enabled = true;
                window.SafariTelemetry.init();
            } else {
                window.SafariTelemetry.disable();
            }
        }

        sincronizarVistaConPrefs();
        window.addEventListener('pageshow', sincronizarVistaConPrefs);

        async function guardarPreferenciaCookies(habilitarAnalisis, origen) {
            if (guardando) return;
            guardando = true;
            const permitirAnalisis = Boolean(habilitarAnalisis);

            // Persistir decisión explícita del usuario en formato URL-safe limpio en la cookie del navegador
            escribirPreferenciasCookieLocal(permitirAnalisis);
            if (permitirAnalisis) {
                window.SafariTelemetry.enabled = true;
                window.SafariTelemetry.init();
            } else {
                window.SafariTelemetry.disable();
            }
            banner.hidden = true;
            if (dialog && dialog.open) {
                dialog.close();
            }

            try {
                const resp = await fetch(urlEndpoint, {
                    method: 'POST',
                    keepalive: true,
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': obtenerCsrfToken()
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        analytics: permitirAnalisis,
                        acepto_privacidad: true,
                        acepto_terminos: true,
                        origen: origen || 'COOKIE_BANNER'
                    })
                });
                if (resp.ok) {
                    const data = await resp.json();
                    const confirmado = Boolean(data && data.analytics);
                    escribirPreferenciasCookieLocal(confirmado);
                    if (confirmado) {
                        window.SafariTelemetry.enabled = true;
                        window.SafariTelemetry.init();
                    } else {
                        window.SafariTelemetry.disable();
                    }
                }
            } catch (err) {
                // La cookie local limpia conserva la elección explícita sin reactivar el banner
            } finally {
                guardando = false;
            }
        }

        if (btnSoloEsenciales) {
            btnSoloEsenciales.addEventListener('click', function () {
                if (chkAnalisisDialog) chkAnalisisDialog.checked = false;
                guardarPreferenciaCookies(false, 'COOKIE_BANNER');
            });
        }

        if (btnAceptarTodas) {
            btnAceptarTodas.addEventListener('click', function () {
                if (chkAnalisisDialog) chkAnalisisDialog.checked = true;
                guardarPreferenciaCookies(true, 'COOKIE_BANNER');
            });
        }

        function abrirDialogoCookies() {
            if (!dialog) return;
            const actual = leerPreferenciasCookie();
            if (chkAnalisisDialog) {
                chkAnalisisDialog.checked = Boolean(actual && actual.analytics === true);
            }
            if (typeof dialog.showModal === 'function') {
                if (!dialog.open) dialog.showModal();
            } else {
                dialog.setAttribute('open', '');
            }
        }

        if (btnAbrirConfig) {
            btnAbrirConfig.addEventListener('click', abrirDialogoCookies);
        }

        document.querySelectorAll('[data-open-cookie-prefs]').forEach(function (trigger) {
            trigger.addEventListener('click', function (ev) {
                ev.preventDefault();
                abrirDialogoCookies();
            });
        });

        if (btnCerrarDialog && dialog) {
            btnCerrarDialog.addEventListener('click', function () {
                if (dialog.open) dialog.close();
            });
        }

        if (btnGuardarDialog) {
            btnGuardarDialog.addEventListener('click', function () {
                const analisisOn = Boolean(chkAnalisisDialog && chkAnalisisDialog.checked);
                guardarPreferenciaCookies(analisisOn, 'COOKIE_BANNER');
            });
        }

        // Light-dismiss fallback para Safari/navegadores sin soporte completo de closedby="any"
        if (dialog) {
            let pointerStartedOnBackdrop = false;
            dialog.addEventListener('pointerdown', function (e) {
                pointerStartedOnBackdrop = (e.target === dialog);
            });
            dialog.addEventListener('click', function (e) {
                if (pointerStartedOnBackdrop && e.target === dialog) {
                    dialog.close();
                }
                pointerStartedOnBackdrop = false;
            });
        }
    });
})();
