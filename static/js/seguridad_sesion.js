/**
 * Parque Safari - Control de Seguridad de Sesión por Inactividad
 * Mitiga accesos no autorizados en terminales compartidas (caja, mesero, cocina, admin)
 * al cerrar la sesión de manera segura tras 15 minutos sin interacción física.
 */
(function () {
    const TIEMPO_INACTIVIDAD_MS = 15 * 60 * 1000; // 15 minutos
    const TIEMPO_AVISO_MS = 14 * 60 * 1000;       // Aviso a los 14 minutos (60s antes)
    let temporizadorInactividad = null;
    let temporizadorAviso = null;
    let intervaloCuentaRegresiva = null;
    let segundosRestantes = 60;

    // Crear dinámicamente modal de advertencia en el DOM
    function crearModalAviso() {
        if (document.getElementById('modalInactividadSafari')) return;

        const modalHtml = `
        <div class="modal fade" id="modalInactividadSafari" data-bs-backdrop="static" data-bs-keyboard="false" tabindex="-1" aria-hidden="true" style="z-index: 99999;">
            <div class="modal-dialog modal-dialog-centered" style="max-width: 440px;">
                <div class="modal-content border-0 shadow-lg rounded-4 overflow-hidden">
                    <div class="modal-header bg-warning bg-opacity-10 border-0 p-4 pb-2">
                        <div class="d-flex align-items-center gap-3">
                            <div class="rounded-circle bg-warning bg-opacity-25 d-flex align-items-center justify-content-center" style="width: 48px; height: 48px;">
                                <i class="bi bi-shield-exclamation text-warning fs-3"></i>
                            </div>
                            <div>
                                <h6 class="fw-bold mb-0 text-dark">Alerta de Inactividad</h6>
                                <span class="badge bg-warning text-dark small">Seguridad Institucional</span>
                            </div>
                        </div>
                    </div>
                    <div class="modal-body p-4 pt-3 text-center">
                        <p class="text-muted mb-3">
                            Por protección de datos y control de accesos, tu sesión en <strong>Parque Safari</strong> se cerrará automáticamente en:
                        </p>
                        <div class="display-5 fw-bold text-danger mb-3" id="contadorInactividadSegundos">
                            60s
                        </div>
                        <p class="small text-muted mb-0">
                            Mueve el cursor, presiona cualquier tecla o haz clic abajo para mantener tu turno activo.
                        </p>
                    </div>
                    <div class="modal-footer border-0 p-4 pt-0 justify-content-center">
                        <button type="button" class="btn btn-dark rounded-pill px-4 fw-bold" id="btnContinuarSesion">
                            <i class="bi bi-arrow-repeat me-1"></i> Continuar Trabajando
                        </button>
                    </div>
                </div>
            </div>
        </div>`;
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        const btnContinuar = document.getElementById('btnContinuarSesion');
        if (btnContinuar) {
            btnContinuar.addEventListener('click', function () {
                reiniciarTemporizador();
            });
        }
    }

    function mostrarAviso() {
        crearModalAviso();
        const modalEl = document.getElementById('modalInactividadSafari');
        if (!modalEl) return;

        segundosRestantes = 60;
        const contadorEl = document.getElementById('contadorInactividadSegundos');
        if (contadorEl) contadorEl.textContent = `${segundosRestantes}s`;

        // Abrir modal con Bootstrap si está disponible
        if (window.bootstrap && window.bootstrap.Modal) {
            const bsModal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
            bsModal.show();
        } else {
            modalEl.classList.add('show');
            modalEl.style.display = 'block';
        }

        // Cuenta regresiva por segundo
        clearInterval(intervaloCuentaRegresiva);
        intervaloCuentaRegresiva = setInterval(function () {
            segundosRestantes--;
            if (contadorEl) contadorEl.textContent = `${segundosRestantes}s`;

            if (segundosRestantes <= 0) {
                clearInterval(intervaloCuentaRegresiva);
                cerrarSesionPorInactividad();
            }
        }, 1000);
    }

    function ocultarAviso() {
        clearInterval(intervaloCuentaRegresiva);
        const modalEl = document.getElementById('modalInactividadSafari');
        if (modalEl) {
            if (window.bootstrap && window.bootstrap.Modal) {
                const bsModal = window.bootstrap.Modal.getInstance(modalEl);
                if (bsModal) bsModal.hide();
            } else {
                modalEl.classList.remove('show');
                modalEl.style.display = 'none';
            }
        }
    }

    function cerrarSesionPorInactividad() {
        window.location.href = '/logout/?motivo=inactividad';
    }

    function reiniciarTemporizador() {
        ocultarAviso();
        clearTimeout(temporizadorAviso);
        clearTimeout(temporizadorInactividad);

        temporizadorAviso = setTimeout(mostrarAviso, TIEMPO_AVISO_MS);
        temporizadorInactividad = setTimeout(cerrarSesionPorInactividad, TIEMPO_INACTIVIDAD_MS);
    }

    // Escuchar eventos físicos de actividad
    const eventosActividad = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll'];
    let debounceTimer = null;

    function handleActividad() {
        if (debounceTimer) return;
        debounceTimer = setTimeout(function () {
            debounceTimer = null;
            // Solo reiniciar si no estamos ya en los últimos 60 segundos de advertencia
            if (segundosRestantes === 60) {
                reiniciarTemporizador();
            }
        }, 2000);
    }

    document.addEventListener('DOMContentLoaded', function () {
        eventosActividad.forEach(function (evento) {
            window.addEventListener(evento, handleActividad, { passive: true });
        });
        reiniciarTemporizador();
    });
})();
