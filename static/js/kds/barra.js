// Reloj en vivo
function actualizarReloj() {
    const ahora = new Date();
    const horas = String(ahora.getHours()).padStart(2, '0');
    const minutos = String(ahora.getMinutes()).padStart(2, '0');
    const segundos = String(ahora.getSeconds()).padStart(2, '0');
    const el = document.getElementById('relojVivo');
    if (el) el.innerText = `${horas}:${minutos}:${segundos}`;
}
setInterval(actualizarReloj, 1000);
actualizarReloj();

// ==============================================================================
// Echo & Aloy: Alerta Sonora de Comandas (Motor Unificado Web Audio API)
// ==============================================================================
const KdsAudio = (() => {
    const STORAGE_KEY = 'safari_kds_audio_barra';

    function emitirCampanaComanda() {
        if (window.SafariAudioAlerts) {
            return window.SafariAudioAlerts.play('barra', STORAGE_KEY);
        }
        return false;
    }

    function isHabilitado() {
        if (window.SafariAudioAlerts) {
            return window.SafariAudioAlerts.isEnabled(STORAGE_KEY);
        }
        return localStorage.getItem(STORAGE_KEY) !== 'false';
    }

    function init() {
        if (window.SafariAudioAlerts) {
            window.SafariAudioAlerts.bindToggleButton({
                buttonId: 'btnToggleKdsAudio',
                storageKey: STORAGE_KEY,
                testProfile: 'barra',
                variant: 'dark-header',
            });
        }
    }

    return { init, emitirCampanaComanda, isHabilitado };
})();

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', KdsAudio.init);
} else {
    KdsAudio.init();
}

// Sincronización Delta Liviana y Auto-actualización secuencial sin apilamiento + Bus Instantáneo
let actualizandoBarra = false;
let ultimaVersionDeltaBarra = null;
let prevColaBarra = null;
let prevActivosIdsBarra = null;
let barraSyncTimer = null;

function buildDeltaUrlBarra() {
    const params = new URLSearchParams(window.location.search);
    params.set('zona', 'BARRA');
    return '/api/sincronizacion/estado/?' + params.toString();
}

function programarSyncBarra(delayMs) {
    clearTimeout(barraSyncTimer);
    const delay = typeof delayMs === 'number'
        ? delayMs
        : (document.visibilityState === 'visible' ? 1500 : 5000);
    barraSyncTimer = setTimeout(() => autoActualizarBarra(false), delay);
}

async function autoActualizarBarra(forzar = false) {
    if (actualizandoBarra) return;
    if (!forzar && document.querySelector('.modal.show')) {
        programarSyncBarra();
        return;
    }

    actualizandoBarra = true;
    const scrollActual = window.scrollY;

    try {
        const deltaUrl = buildDeltaUrlBarra();
        let huboCambios = forzar;

        try {
            const fetchOpts = { headers: { 'X-Requested-With': 'XMLHttpRequest' } };
            if (!forzar) fetchOpts.priority = 'low';
            const deltaResp = await fetch(deltaUrl, fetchOpts);
            if (deltaResp.ok) {
                const delta = await deltaResp.json();
                if (delta.ok) {
                    const kpiMap = {
                        'barraBadgePendientes': delta.pendientes,
                        'barraBadgePreparacion': delta.preparacion,
                        'barraBadgeListos': delta.listos,
                        'barraBadgeCola': delta.cola_total
                    };
                    for (const [id, val] of Object.entries(kpiMap)) {
                        const el = document.getElementById(id);
                        if (el && el.innerText !== String(val)) el.innerText = String(val);
                    }

                    const actualesArr = Array.isArray(delta.activos_ids) ? delta.activos_ids : null;
                    if (prevColaBarra !== null) {
                        const hayIdNuevo = actualesArr && prevActivosIdsBarra
                            ? actualesArr.some((id) => !prevActivosIdsBarra.has(id))
                            : false;
                        if (hayIdNuevo || delta.cola_total > prevColaBarra) {
                            KdsAudio.emitirCampanaComanda();
                        }
                    }
                    if (actualesArr) {
                        prevActivosIdsBarra = new Set(actualesArr);
                    }
                    prevColaBarra = delta.cola_total;

                    if (!forzar && ultimaVersionDeltaBarra && ultimaVersionDeltaBarra === delta.version) {
                        return;
                    }
                    ultimaVersionDeltaBarra = delta.version;
                    huboCambios = true;
                }
            }
        } catch (e) {
            huboCambios = true;
        }

        if (!huboCambios) {
            return;
        }

        const domOpts = { headers: { 'X-Requested-With': 'XMLHttpRequest' } };
        if (!forzar) domOpts.priority = 'low';
        const resp = await fetch(window.location.href, domOpts);
        if (!resp.ok) {
            return;
        }
        const textoHtml = await resp.text();
        const parser = new DOMParser();
        const nuevoDoc = parser.parseFromString(textoHtml, 'text/html');

        const nuevoContenedor = nuevoDoc.getElementById('contenedorBarraComandas');
        const actualContenedor = document.getElementById('contenedorBarraComandas');
        if (nuevoContenedor && actualContenedor) {
            if (nuevoContenedor.innerHTML.trim() !== actualContenedor.innerHTML.trim()) {
                actualContenedor.innerHTML = nuevoContenedor.innerHTML;
            }
        }

        const nuevoHist = nuevoDoc.getElementById('historialEntregadosBarra');
        const actualHist = document.getElementById('historialEntregadosBarra');
        if (nuevoHist && actualHist && nuevoHist.innerHTML.trim() !== actualHist.innerHTML.trim()) {
            actualHist.innerHTML = nuevoHist.innerHTML;
        }

        ['barraBadgePendientes', 'barraBadgePreparacion', 'barraBadgeListos', 'barraBadgeCola'].forEach(id => {
            const nuevoEl = nuevoDoc.getElementById(id);
            const actualEl = document.getElementById(id);
            if (nuevoEl && actualEl && nuevoEl.innerText !== actualEl.innerText) {
                actualEl.innerText = nuevoEl.innerText;
            }
        });

        window.scrollTo(0, scrollActual);
    } catch (err) {
        // Silencioso ante fluctuaciones
    } finally {
        actualizandoBarra = false;
        programarSyncBarra();
    }
}

// Control Táctil de Disponibilidad de Bebidas / Tragos desde KDS Barra (RF15)
window.toggleStockProducto = async function(productoId, btn) {
    if (!productoId) return;
    if (btn) btn.disabled = true;

    try {
        const csrfEl = document.querySelector('[name=csrfmiddlewaretoken]');
        const csrfToken = csrfEl ? csrfEl.value : '';

        const formData = new FormData();
        formData.append('producto_id', productoId);
        if (csrfToken) formData.append('csrfmiddlewaretoken', csrfToken);

        const resp = await fetch('/api/kds/toggle-stock/', {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
        });

        const ct = resp.headers.get('content-type') || '';
        const data = ct.includes('application/json') ? await resp.json() : {};

        if (resp.status === 401 || data.sesion_expirada) {
            alert(data.error || 'Tu sesión expiró. Recarga la página e inicia sesión.');
            return;
        }

        if (resp.ok && data.ok) {
            if (btn) {
                if (data.activo) {
                    btn.className = 'btn btn-sm btn-success fw-bold';
                    btn.innerHTML = '<i class="bi bi-check-circle me-1"></i> Disponible';
                } else {
                    btn.className = 'btn btn-sm btn-danger fw-bold';
                    btn.innerHTML = '<i class="bi bi-slash-circle me-1"></i> Agotado en Barra';
                }
            }
            ultimaVersionDeltaBarra = null;
        }
    } catch (e) {
        console.error("Error al alternar stock en barra:", e);
    } finally {
        if (btn) btn.disabled = false;
    }
};

// Sincronización secuencial sin apilamiento + respuesta instantánea por BroadcastChannel
programarSyncBarra(1200);

document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        autoActualizarBarra(false);
    } else {
        programarSyncBarra(5000);
    }
});

if (window.SafariSyncBus) {
    window.SafariSyncBus.subscribe((ev) => {
        if (ev && (ev.type === 'nueva_comanda' || ev.type === 'pedido_estado')) {
            ultimaVersionDeltaBarra = null;
            autoActualizarBarra(false);
        }
    });
}

// Modo Concentración Táctico KDS (Barra)
function inicializarModoCondensado() {
    const STORAGE_KEY = 'safari_barra_modo_condensado';
    const btn = document.getElementById('btnToggleCondensadoKds');
    if (!btn) return;

    function aplicarEstadoConcentracion(activo) {
        document.body.classList.toggle('kds-modo-condensado', activo);
        btn.classList.toggle('active', activo);
        btn.setAttribute('aria-pressed', activo ? 'true' : 'false');

        const icono = document.getElementById('iconoModoConcentracion');
        if (icono) {
            icono.className = activo
                ? 'bi bi-arrows-angle-expand me-1'
                : 'bi bi-arrows-angle-contract me-1';
        }

        const texto = document.getElementById('textoModoConcentracion');
        if (texto) {
            texto.textContent = activo ? 'Salir Concentración' : 'Modo Concentración';
        }
    }

    let guardado = false;
    try {
        guardado = localStorage.getItem(STORAGE_KEY) === 'true';
    } catch (_err) {
        guardado = false;
    }
    aplicarEstadoConcentracion(guardado);

    btn.addEventListener('click', () => {
        const activo = !document.body.classList.contains('kds-modo-condensado');
        aplicarEstadoConcentracion(activo);
        try {
            localStorage.setItem(STORAGE_KEY, activo ? 'true' : 'false');
        } catch (_err) {
            // Ignorar si almacenamiento local está bloqueado
        }
    });

    document.addEventListener('keydown', (ev) => {
        if (ev.key !== 'Escape') return;
        if (!document.body.classList.contains('kds-modo-condensado')) return;
        if (document.querySelector('.modal.show, dialog[open]')) return;
        aplicarEstadoConcentracion(false);
        try {
            localStorage.setItem(STORAGE_KEY, 'false');
        } catch (_err) {
            // Ignorar si almacenamiento local está bloqueado
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarModoCondensado);
} else {
    inicializarModoCondensado();
}

// Envío AJAX táctil de cambio de estado
async function enviarAccionBarraAjax(e, form) {
    e.preventDefault();
    const scrollPos = window.scrollY;
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    const formData = new FormData(form);
    try {
        const resp = await fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
        });
        const ct = resp.headers.get('content-type') || '';
        const data = ct.includes('application/json') ? await resp.json() : {};
        if (resp.status === 401 || data.sesion_expirada) {
            alert(data.error || 'Tu sesión expiró. Inicia sesión nuevamente.');
            return;
        }
        if (!resp.ok || (!data.ok && data.status !== 'ok')) {
            alert(data.mensaje || data.error || 'No se pudo actualizar el estado del pedido.');
            return;
        }
        ultimaVersionDeltaBarra = null;
        if (window.SafariSyncBus) {
            window.SafariSyncBus.publish({
                type: 'pedido_estado',
                pedido_id: data.pedido_id,
                nuevo_estado: data.nuevo_estado,
                estacion: data.estacion || 'BARRA',
            });
        }
        await autoActualizarBarra(true);
        window.scrollTo(0, scrollPos);
    } catch (err) {
        form.submit();
    } finally {
        if (submitBtn) submitBtn.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const contenedorComandas = document.getElementById('contenedorBarraComandas');
    if (contenedorComandas) {
        contenedorComandas.addEventListener('submit', function(e) {
            const form = e.target.closest('form[data-barra-ajax="true"]');
            if (form) {
                enviarAccionBarraAjax(e, form);
            }
        });
    }

    const modalStock = document.getElementById('modalStockBarra');
    if (modalStock) {
        modalStock.addEventListener('click', function(e) {
            const btn = e.target.closest('[data-stock-toggle-id]');
            if (btn) {
                const prodId = btn.getAttribute('data-stock-toggle-id');
                window.toggleStockProducto(prodId, btn);
            }
        });
    }
});
