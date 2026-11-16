// static/js/acceso/login.js
// Manejo seguro del portal de acceso: Cero contraseñas en código cliente y consentimiento explícito sin casilla premarcada

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('formLoginFormal');
    const userInp = document.getElementById('id_username');
    const passInp = document.getElementById('id_password');
    const nextInp = document.getElementById('id_next');
    const demoInp = document.getElementById('id_demo_rol_eval');
    const chkPoliticas = document.getElementById('id_acepto_politicas');
    const cajaConsentimiento = document.getElementById('cajaConsentimientoLogin');
    const wrapperCheckbox = document.getElementById('wrapperCheckboxConsentimiento');
    const avisoYaAcepto = document.getElementById('avisoYaAceptoLogin');
    const errorConsentimiento = document.getElementById('errorConsentimientoLogin');

    const ackConfigEl = document.getElementById('safariAckConfig');
    let ackConfig = {
        tokens: [],
        policy_version: 'v1.0-academica',
        terms_version: 'v1.0-academica',
    };
    if (ackConfigEl && ackConfigEl.textContent) {
        try {
            const parsedAck = JSON.parse(ackConfigEl.textContent);
            if (parsedAck && typeof parsedAck === 'object') {
                ackConfig = {
                    tokens: Array.isArray(parsedAck.tokens) ? parsedAck.tokens : [],
                    policy_version: parsedAck.policy_version || 'v1.0-academica',
                    terms_version: parsedAck.terms_version || 'v1.0-academica',
                };
            }
        } catch (_err) {
            // Fallback por defecto si el JSON de configuración no es válido
        }
    }

    function hashAliasNavegador(identificador) {
        const limpio = (identificador || '').trim().toLowerCase();
        if (!limpio) return '';
        const texto = 'safari-ack:' + ackConfig.policy_version + ':' + ackConfig.terms_version + ':' + limpio;
        const bytes = typeof TextEncoder !== 'undefined'
            ? new TextEncoder().encode(texto)
            : Array.prototype.map.call(texto, function (c) { return c.charCodeAt(0) & 0xff; });
        let h = 0x811c9dc5;
        for (let i = 0; i < bytes.length; i++) {
            h = Math.imul((h ^ bytes[i]) >>> 0, 0x01000193) >>> 0;
        }
        return (h >>> 0).toString(16).padStart(8, '0');
    }

    function leerTokensCookieAck() {
        if (!document.cookie) return [];
        const partes = document.cookie.split(';');
        for (let i = 0; i < partes.length; i++) {
            const item = partes[i].trim();
            if (item.indexOf('safari_ack_users=') === 0) {
                const raw = item.slice('safari_ack_users='.length).replace(/^"|"$/g, '');
                try {
                    const arr = JSON.parse(decodeURIComponent(raw));
                    if (Array.isArray(arr)) {
                        return arr.filter(function (v) { return typeof v === 'string' && v.length > 0; });
                    }
                } catch (_err) {
                    return [];
                }
            }
        }
        return [];
    }

    function obtenerTokensAckSet() {
        const conjunto = new Set();
        for (let i = 0; i < ackConfig.tokens.length; i++) {
            if (ackConfig.tokens[i]) conjunto.add(String(ackConfig.tokens[i]));
        }
        const deCookie = leerTokensCookieAck();
        for (let i = 0; i < deCookie.length; i++) {
            conjunto.add(deCookie[i]);
        }
        return conjunto;
    }

    function usuarioYaAcepto(identificador) {
        const token = hashAliasNavegador(identificador);
        if (!token) return false;
        return obtenerTokensAckSet().has(token);
    }

    function actualizarEstadoConsentimientoUI(identificador) {
        const aceptado = usuarioYaAcepto(identificador);
        if (cajaConsentimiento) {
            cajaConsentimiento.classList.toggle('consent-already-accepted', aceptado);
            if (aceptado) cajaConsentimiento.classList.remove('consent-error');
        }
        if (wrapperCheckbox) wrapperCheckbox.hidden = aceptado;
        if (avisoYaAcepto) avisoYaAcepto.hidden = !aceptado;
        if (aceptado && chkPoliticas) {
            chkPoliticas.classList.remove('user-invalid-fallback');
        }
        if (aceptado && errorConsentimiento) {
            errorConsentimiento.hidden = true;
        }
        return aceptado;
    }

    // 1. Toggle de visibilidad de contraseña (ocultamiento visual activo por defecto)
    const btnToggle = document.getElementById('btnToggleClave');
    if (btnToggle) {
        btnToggle.addEventListener('click', function () {
            const icon = document.getElementById('iconoOjoClave');
            if (passInp) {
                if (passInp.type === 'password') {
                    passInp.type = 'text';
                    if (icon) icon.className = 'bi bi-eye';
                } else {
                    passInp.type = 'password';
                    if (icon) icon.className = 'bi bi-eye-slash';
                }
            }
        });
    }

    // Limpiar bandera de acceso rápido si el colaborador escribe contraseña manualmente
    if (passInp && demoInp) {
        passInp.addEventListener('input', function () {
            if (passInp.value.length > 0) {
                demoInp.value = '';
            }
        });
    }

    function validarConsentimientoInteractivo() {
        if (!chkPoliticas) return true;
        if (wrapperCheckbox && wrapperCheckbox.hidden) wrapperCheckbox.hidden = false;
        if (avisoYaAcepto && !avisoYaAcepto.hidden) avisoYaAcepto.hidden = true;
        if (!chkPoliticas.checked) {
            chkPoliticas.classList.add('user-invalid-fallback');
            if (cajaConsentimiento) cajaConsentimiento.classList.add('consent-error');
            if (errorConsentimiento) {
                errorConsentimiento.textContent = 'Debes marcar esta casilla para aceptar la Política de Privacidad y los Términos antes de ingresar.';
                errorConsentimiento.hidden = false;
            }
            chkPoliticas.focus();
            return false;
        }
        chkPoliticas.classList.remove('user-invalid-fallback');
        if (cajaConsentimiento) cajaConsentimiento.classList.remove('consent-error');
        if (errorConsentimiento) errorConsentimiento.hidden = true;
        return true;
    }

    if (chkPoliticas) {
        chkPoliticas.addEventListener('change', function () {
            if (chkPoliticas.checked) {
                chkPoliticas.classList.remove('user-invalid-fallback');
                if (cajaConsentimiento) cajaConsentimiento.classList.remove('consent-error');
                if (errorConsentimiento) errorConsentimiento.hidden = true;
            }
        });
    }

    if (userInp) {
        actualizarEstadoConsentimientoUI(userInp.value);
        userInp.addEventListener('input', function () {
            if (demoInp) demoInp.value = '';
            actualizarEstadoConsentimientoUI(userInp.value);
        });
        userInp.addEventListener('change', function () {
            actualizarEstadoConsentimientoUI(userInp.value);
        });
    }

    window.addEventListener('pageshow', function () {
        if (userInp) actualizarEstadoConsentimientoUI(userInp.value);
    });

    if (form) {
        form.addEventListener('submit', function (ev) {
            form.classList.add('safari-form-validated');
            if (userInp && !userInp.value.trim()) {
                userInp.classList.add('user-invalid-fallback');
                userInp.focus();
                ev.preventDefault();
                return false;
            }
            const tieneDemoAutorizado = Boolean(demoInp && demoInp.value);
            if (tieneDemoAutorizado) {
                if (!usuarioYaAcepto(demoInp.value) && !validarConsentimientoInteractivo()) {
                    ev.preventDefault();
                    return false;
                }
                return true;
            }
            if (passInp && !passInp.value) {
                passInp.classList.add('user-invalid-fallback');
                passInp.focus();
                ev.preventDefault();
                return false;
            }
        });
    }

    // 2. Evaluación académica 1 Clic (sin exponer contraseñas en HTML ni JavaScript)
    document.querySelectorAll('.btn-demo-user').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const user = this.getAttribute('data-user');
            if (form) form.classList.add('safari-form-validated');
            actualizarEstadoConsentimientoUI(user);
            if (!usuarioYaAcepto(user) && !validarConsentimientoInteractivo()) return;
            if (userInp && user) userInp.value = user;
            if (passInp) passInp.value = '';
            if (nextInp) nextInp.value = '';
            if (demoInp && user) demoInp.value = user;
            if (form) form.submit();
        });
    });

    // 3. Ingreso directo a terminales KDS (Cocina / Barra) sin exposición de contraseña
    document.querySelectorAll('.btn-demo-direct').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const user = this.getAttribute('data-user');
            const destino = this.getAttribute('data-destino');
            if (form) form.classList.add('safari-form-validated');
            actualizarEstadoConsentimientoUI(user);
            if (!usuarioYaAcepto(user) && !validarConsentimientoInteractivo()) return;
            if (userInp && user) userInp.value = user;
            if (passInp) passInp.value = '';
            if (nextInp && destino) nextInp.value = destino;
            if (demoInp && user) demoInp.value = user;
            if (form) form.submit();
        });
    });

    // 4. Inicializar toasts automáticos en la esquina
    document.querySelectorAll('.toast-container .toast').forEach(function (el) {
        if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
            const toast = new bootstrap.Toast(el, { delay: 4500 });
            toast.show();
            setTimeout(function () {
                try { toast.hide(); } catch (e) {}
            }, 4500);
        }
    });
});
