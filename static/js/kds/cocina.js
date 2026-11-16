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
// Echo & Aloy: Alerta Sonora de Comandas (Web Audio API - Campana Gastronómica)
// Sonido acústico armónico estilo campana de cocina (E5 -> A5, ~700 ms)
// Cero dependencias externas ni archivos MP3. Fiabilidad total en hardware KDS.
// ==============================================================================
const KdsAudio = (() => {
    let audioCtx = null;
    let habilitado = localStorage.getItem('safari_kds_audio_cocina') !== 'false';

    function initContext() {
        if (!audioCtx) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (AudioContextClass) {
                audioCtx = new AudioContextClass();
            }
        }
        if (audioCtx && audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
    }

    function reproducirTono(freq, inicio, duracion, vol = 0.25, tipo = 'triangle') {
        if (!audioCtx) return;
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();

        osc.type = tipo;
        osc.frequency.setValueAtTime(freq, inicio);

        // Curva envolvente: ataque suave anti-clipping y decaimiento acústico natural
        gain.gain.setValueAtTime(0.0001, inicio);
        gain.gain.exponentialRampToValueAtTime(vol, inicio + 0.025);
        gain.gain.exponentialRampToValueAtTime(0.0001, inicio + duracion);

        osc.connect(gain);
        gain.connect(audioCtx.destination);

        osc.start(inicio);
        osc.stop(inicio + duracion + 0.05);
    }

    function emitirCampanaComanda() {
        if (!habilitado) return;
        try {
            initContext();
            if (!audioCtx) return;

            const t = audioCtx.currentTime;
            // Doble campana gastronómica de cocina (~700 ms total)
            // Golpe 1 (E5 / 659.25 Hz, armónico cálido, duración 280 ms)
            reproducirTono(659.25, t, 0.28, 0.25, 'triangle');
            // Golpe 2 (A5 / 880.00 Hz, resonancia acampanada abierta, duración 520 ms)
            reproducirTono(880.00, t + 0.18, 0.52, 0.30, 'triangle');
        } catch (e) {
            console.debug('Aviso auditivo omitido:', e);
        }
    }

    function toggleAudio() {
        habilitado = !habilitado;
        localStorage.setItem('safari_kds_audio_cocina', habilitado);
        actualizarBoton();
        if (habilitado) emitirCampanaComanda();
    }

    function actualizarBoton() {
        const btn = document.getElementById('btnToggleKdsAudio');
        if (!btn) return;
        if (habilitado) {
            btn.className = 'btn btn-sm btn-outline-light rounded-pill px-3 d-flex align-items-center gap-1 shadow-sm';
            btn.innerHTML = '<i class="bi bi-volume-up-fill" aria-hidden="true"></i> <span class="d-none d-md-inline small fw-bold">Sonido ON</span>';
            btn.setAttribute('aria-pressed', 'true');
            btn.title = 'Alerta sonora de cocina activa (Campana E5-A5). Clic para silenciar.';
        } else {
            btn.className = 'btn btn-sm btn-outline-light text-on-brand-muted rounded-pill px-3 d-flex align-items-center gap-1 shadow-sm';
            btn.innerHTML = '<i class="bi bi-volume-mute-fill" aria-hidden="true"></i> <span class="d-none d-md-inline small fw-bold">Sonido OFF</span>';
            btn.setAttribute('aria-pressed', 'false');
            btn.title = 'Alerta sonora silenciada. Clic para activar.';
        }
    }

    function init() {
        actualizarBoton();
        const btn = document.getElementById('btnToggleKdsAudio');
        if (btn) btn.addEventListener('click', toggleAudio);
        ['click', 'touchstart'].forEach(evt => {
            document.addEventListener(evt, initContext, { once: true, passive: true });
        });
    }

    return { init, emitirCampanaComanda, toggleAudio, isHabilitado: () => habilitado };
})();

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', KdsAudio.init);
} else {
    KdsAudio.init();
}

// Sincronización Delta Liviana (~150 bytes) y Auto-actualización fluida en segundo plano con Scroll Lock
let actualizandoKds = false;
let ultimaVersionDeltaCocina = null;
let prevColaCocina = null;

async function autoActualizarCocina(forzar = false) {
    if (actualizandoKds) return;
    if (!forzar && document.querySelector('.modal.show')) return;

    actualizandoKds = true;
    const scrollActual = window.scrollY;

    try {
        // 1. Paso Delta Liviano: consultar versión hash de 150 bytes
        const deltaUrl = '/api/sincronizacion/estado/' + window.location.search;
        let huboCambios = forzar;

        try {
            const deltaResp = await fetch(deltaUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (deltaResp.ok) {
                const delta = await deltaResp.json();
                if (delta.ok) {
                    // Refrescar KPIs inmediatamente desde el delta sin renderizar HTML
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

                    // Echo & Aloy: Detección sonora ante nuevas comandas entrantes
                    if (prevColaCocina !== null && delta.cola_total > prevColaCocina) {
                        KdsAudio.emitirCampanaComanda();
                    }
                    prevColaCocina = delta.cola_total;

                    if (!forzar && ultimaVersionDeltaCocina && ultimaVersionDeltaCocina === delta.version) {
                        actualizandoKds = false;
                        return; // Zero overhead: el estado no ha cambiado
                    }
                    ultimaVersionDeltaCocina = delta.version;
                    huboCambios = true;
                }
            }
        } catch (e) {
            huboCambios = true; // Si falla el delta, fallback seguro a descarga normal
        }

        if (!huboCambios) {
            actualizandoKds = false;
            return;
        }

        // 2. Si la versión cambió, descargar DOM actualizado
        const resp = await fetch(window.location.href, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!resp.ok) {
            actualizandoKds = false;
            return;
        }
        const textoHtml = await resp.text();
        const parser = new DOMParser();
        const nuevoDoc = parser.parseFromString(textoHtml, 'text/html');

        // Actualizar tarjetas de comandas
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

        // Actualizar badges KPI superiores
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

// Auto-actualización ultra-rápida a 1 segundo (1000 ms) con ahorro inteligente de recursos
let kdsInterval = setInterval(autoActualizarCocina, 1000);

document.addEventListener('visibilitychange', () => {
    clearInterval(kdsInterval);
    if (document.visibilityState === 'visible') {
        autoActualizarCocina();
        kdsInterval = setInterval(autoActualizarCocina, 1000);
    } else {
        kdsInterval = setInterval(autoActualizarCocina, 5000);
    }
});

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
