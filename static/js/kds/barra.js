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
// Echo & Aloy: Alerta Sonora Nativa Web Audio API (880 Hz / 150 ms senoidal)
// Cero dependencias ni MP3s externos. Fiabilidad para estación Barra.
// ==============================================================================
const KdsAudio = (() => {
    let audioCtx = null;
    let habilitado = localStorage.getItem('safari_kds_audio_barra') !== 'false';

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

    function emitirCampanaComanda() {
        if (!habilitado) return;
        try {
            initContext();
            if (!audioCtx) return;

            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();

            osc.type = 'sine';
            osc.frequency.setValueAtTime(880, audioCtx.currentTime);

            gain.gain.setValueAtTime(0.001, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.28, audioCtx.currentTime + 0.015);
            gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.15);

            osc.connect(gain);
            gain.connect(audioCtx.destination);

            osc.start(audioCtx.currentTime);
            osc.stop(audioCtx.currentTime + 0.16);
        } catch (e) {
            console.debug('Aviso auditivo omitido:', e);
        }
    }

    function toggleAudio() {
        habilitado = !habilitado;
        localStorage.setItem('safari_kds_audio_barra', habilitado);
        actualizarBoton();
        if (habilitado) emitirCampanaComanda();
    }

    function actualizarBoton() {
        const btn = document.getElementById('btnToggleKdsAudio');
        if (!btn) return;
        if (habilitado) {
            btn.className = 'btn btn-sm btn-outline-light rounded-pill px-3 d-flex align-items-center gap-1 shadow-sm';
            btn.innerHTML = '<i class="bi bi-volume-up-fill text-warning"></i> <span class="d-none d-md-inline small fw-bold">Sonido ON</span>';
            btn.title = 'Alerta sonora comanda activa (880 Hz). Clic para silenciar.';
        } else {
            btn.className = 'btn btn-sm btn-outline-secondary text-white-50 rounded-pill px-3 d-flex align-items-center gap-1 shadow-sm';
            btn.innerHTML = '<i class="bi bi-volume-mute-fill"></i> <span class="d-none d-md-inline small fw-bold">Sonido OFF</span>';
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
let actualizandoBarra = false;
let ultimaVersionDeltaBarra = null;
let prevColaBarra = null;

async function autoActualizarBarra(forzar = false) {
    if (actualizandoBarra) return;
    if (!forzar && document.querySelector('.modal.show')) return;

    actualizandoBarra = true;
    const scrollActual = window.scrollY;

    try {
        const deltaUrl = '/api/sincronizacion/estado/' + window.location.search;
        let huboCambios = forzar;

        try {
            const deltaResp = await fetch(deltaUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
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

                    // Detección sonora ante nuevas comandas de coctelería/barra
                    if (prevColaBarra !== null && delta.cola_total > prevColaBarra) {
                        KdsAudio.emitirCampanaComanda();
                    }
                    prevColaBarra = delta.cola_total;

                    if (!forzar && ultimaVersionDeltaBarra && ultimaVersionDeltaBarra === delta.version) {
                        actualizandoBarra = false;
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
            actualizandoBarra = false;
            return;
        }

        const resp = await fetch(window.location.href, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!resp.ok) {
            actualizandoBarra = false;
            return;
        }
        const textoHtml = await resp.text();
        const parser = new DOMParser();
        const nuevoDoc = parser.parseFromString(textoHtml, 'text/html');

        // Actualizar tarjetas
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

        // Actualizar badges KPI superiores
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
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });

        if (resp.ok) {
            const data = await resp.json();
            if (data.ok) {
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
        }
    } catch (e) {
        console.error("Error al alternar stock en barra:", e);
    } finally {
        if (btn) btn.disabled = false;
    }
};

// Auto-actualización a 1 segundo (1000 ms)
let barraInterval = setInterval(autoActualizarBarra, 1000);

document.addEventListener('visibilitychange', () => {
    clearInterval(barraInterval);
    if (document.visibilityState === 'visible') {
        autoActualizarBarra();
        barraInterval = setInterval(autoActualizarBarra, 1000);
    } else {
        barraInterval = setInterval(autoActualizarBarra, 5000);
    }
});

// Modo Condensado Táctico KDS
function inicializarModoCondensado() {
    const btn = document.getElementById('btnToggleCondensadoKds');
    if (!btn) return;
    const guardado = localStorage.getItem('safari_kds_modo_condensado');
    if (guardado === 'true') {
        document.body.classList.add('kds-modo-condensado');
    }
    btn.addEventListener('click', () => {
        document.body.classList.toggle('kds-modo-condensado');
        const activo = document.body.classList.contains('kds-modo-condensado');
        localStorage.setItem('safari_kds_modo_condensado', activo ? 'true' : 'false');
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
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        ultimaVersionDeltaBarra = null;
        await autoActualizarBarra(true);
        window.scrollTo(0, scrollPos);
    } catch (err) {
        form.submit();
    }
}
