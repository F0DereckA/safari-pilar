// Actualizar reloj en vivo
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
    const STORAGE_KEY = 'safari_kds_audio_cocina';

    function emitirCampanaComanda() {
        if (window.SafariAudioAlerts) {
            return window.SafariAudioAlerts.play('cocina', STORAGE_KEY);
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
                testProfile: 'cocina',
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
let actualizandoKds = false;
let ultimaVersionDeltaCocina = null;
let prevColaCocina = null;
let prevActivosIdsCocina = null;
let kdsSyncTimer = null;

function buildDeltaUrlCocina() {
    const params = new URLSearchParams(window.location.search);
    params.set('zona', 'COCINA');
    return '/api/sincronizacion/estado/?' + params.toString();
}

function programarSyncCocina(delayMs) {
    clearTimeout(kdsSyncTimer);
    const delay = typeof delayMs === 'number'
        ? delayMs
        : (document.visibilityState === 'visible' ? 1500 : 5000);
    kdsSyncTimer = setTimeout(() => autoActualizarCocina(false), delay);
}

async function autoActualizarCocina(forzar = false) {
    if (actualizandoKds) return;
    if (!forzar && document.querySelector('.modal.show')) {
        programarSyncCocina();
        return;
    }

    actualizandoKds = true;
    const scrollActual = window.scrollY;

    try {
        const deltaUrl = buildDeltaUrlCocina();
        let huboCambios = forzar;

        try {
            const fetchOpts = { headers: { 'X-Requested-With': 'XMLHttpRequest' } };
            if (!forzar) fetchOpts.priority = 'low';
            const deltaResp = await fetch(deltaUrl, fetchOpts);
            if (deltaResp.ok) {
                const delta = await deltaResp.json();
                if (delta.ok) {
                    const kpiMap = {
                        'kdsBadgePendientes': delta.pendientes,
                        'kdsBadgePreparacion': delta.preparacion,
                        'kdsBadgeListos': delta.listos,
                        'kdsBadgeCola': delta.cola_total
                    };
                    for (const [id, val] of Object.entries(kpiMap)) {
                        const el = document.getElementById(id);
                        if (el && el.innerText !== String(val)) el.innerText = String(val);
                    }

                    // Detección sonora fiable por IDs entrantes y aumento de cola
                    const actualesArr = Array.isArray(delta.activos_ids) ? delta.activos_ids : null;
                    if (prevColaCocina !== null) {
                        const hayIdNuevo = actualesArr && prevActivosIdsCocina
                            ? actualesArr.some((id) => !prevActivosIdsCocina.has(id))
                            : false;
                        if (hayIdNuevo || delta.cola_total > prevColaCocina) {
                            KdsAudio.emitirCampanaComanda();
                        }
                    }
                    if (actualesArr) {
                        prevActivosIdsCocina = new Set(actualesArr);
                    }
                    prevColaCocina = delta.cola_total;

                    if (!forzar && ultimaVersionDeltaCocina && ultimaVersionDeltaCocina === delta.version) {
                        return; // Zero overhead: el estado no ha cambiado
                    }
                    ultimaVersionDeltaCocina = delta.version;
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

        const nuevoContenedor = nuevoDoc.getElementById('contenedorKdsComandas');
        const actualContenedor = document.getElementById('contenedorKdsComandas');
        if (nuevoContenedor && actualContenedor) {
            if (nuevoContenedor.innerHTML.trim() !== actualContenedor.innerHTML.trim()) {
                actualContenedor.innerHTML = nuevoContenedor.innerHTML;
            }
        }

        const nuevoHist = nuevoDoc.getElementById('historialEntregadosKds');
        const actualHist = document.getElementById('historialEntregadosKds');
        if (nuevoHist && actualHist && nuevoHist.innerHTML.trim() !== actualHist.innerHTML.trim()) {
            actualHist.innerHTML = nuevoHist.innerHTML;
        }

        ['kdsBadgePendientes', 'kdsBadgePreparacion', 'kdsBadgeListos', 'kdsBadgeCola'].forEach(id => {
            const nuevoEl = nuevoDoc.getElementById(id);
            const actualEl = document.getElementById(id);
            if (nuevoEl && actualEl && nuevoEl.innerText !== actualEl.innerText) {
                actualEl.innerText = nuevoEl.innerText;
            }
        });

        window.scrollTo(0, scrollActual);
    } catch (err) {
        // Silencioso ante fluctuaciones de red
    } finally {
        actualizandoKds = false;
        programarSyncCocina();
    }
}

// Control Táctil de Disponibilidad de Platos desde KDS Cocina (RF15)
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
                    btn.innerHTML = '<i class="bi bi-slash-circle me-1"></i> Agotado en Cocina';
                }
            }
            ultimaVersionDeltaCocina = null; // Forzar sync
        }
    } catch (e) {
        console.error("Error al alternar stock de plato:", e);
    } finally {
        if (btn) btn.disabled = false;
    }
};

// Sincronización secuencial sin apilamiento + respuesta instantánea por BroadcastChannel
programarSyncCocina(1200);

document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        autoActualizarCocina(false);
    } else {
        programarSyncCocina(5000);
    }
});

if (window.SafariSyncBus) {
    window.SafariSyncBus.subscribe((ev) => {
        if (ev && (ev.type === 'nueva_comanda' || ev.type === 'pedido_estado')) {
            ultimaVersionDeltaCocina = null;
            autoActualizarCocina(false);
        }
    });
}

// Modo Concentración Táctico KDS (Cocina)
function inicializarModoCondensado() {
    const STORAGE_KEY = 'safari_kds_modo_condensado';
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
async function enviarAccionKdsAjax(e, form) {
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
        ultimaVersionDeltaCocina = null;
        if (window.SafariSyncBus) {
            window.SafariSyncBus.publish({
                type: 'pedido_estado',
                pedido_id: data.pedido_id,
                nuevo_estado: data.nuevo_estado,
                estacion: data.estacion || 'COCINA',
            });
        }
        await autoActualizarCocina(true);
        window.scrollTo(0, scrollPos);
    } catch (err) {
        form.submit(); // Respaldo tradicional si falla la red
    } finally {
        if (submitBtn) submitBtn.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const contenedorComandas = document.getElementById('contenedorKdsComandas');
    if (contenedorComandas) {
        contenedorComandas.addEventListener('submit', function(e) {
            const form = e.target.closest('form[data-kds-ajax="true"]');
            if (form) {
                enviarAccionKdsAjax(e, form);
            }
        });
    }

    const modalStock = document.getElementById('modalStockCocina');
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
