/**
 * Parque Safari - Control de Seguridad y Tiempo de Sesión
 * 1. Muestra un reloj discreto y estilizado con la cuenta regresiva en el header o flotante.
 * 2. Cierre flexible: mientras haya actividad física (tecleo, movimiento de cursor, click, scroll, touch),
 *    la sesión se renueva AUTOMÁTICAMENTE a 15:00 y NUNCA se cierra.
 * 3. Si transcurren 15 minutos continuos de 100% inactividad, se cierra de manera segura.
 */
(function () {
    const TIEMPO_TOTAL_SEGUNDOS = 15 * 60; // 15 minutos (900s)
    let segundosRestantes = TIEMPO_TOTAL_SEGUNDOS;
    let timerInterval = null;
    let debounceTimer = null;

    // Crear o vincular el elemento visual del reloj
    function asegurarRelojEnDOM() {
        let relojEl = document.getElementById('indicadorSesionSafari');
        if (!relojEl) {
            // Buscar un contenedor preferente en la barra de navegación
            const contenedorNav = document.getElementById('contenedorRelojSesion') ||
                                  document.querySelector('.safari-header .d-flex.align-items-center.gap-3') ||
                                  document.querySelector('.navbar .container-fluid') ||
                                  document.querySelector('header');

            const relojHtml = `
            <div id="indicadorSesionSafari" class="d-inline-flex align-items-center gap-1 px-3 py-1 rounded-pill shadow-sm"
                 style="background: rgba(255, 255, 255, 0.95); border: 1.5px solid #e2e8f0; font-size: 0.85rem; font-family: system-ui, sans-serif; transition: all 0.3s ease; cursor: pointer; user-select: none;"
                 title="Tiempo de sesión restante por inactividad. Se renueva automáticamente al mover el cursor o escribir.">
                <i class="bi bi-clock-history text-secondary" id="iconoRelojSesion" style="font-size: 0.9rem;"></i>
                <span class="text-muted small d-none d-sm-inline">Sesión:</span>
                <span id="relojSesionTxt" class="fw-bold text-dark font-monospace">15:00</span>
            </div>`;

            if (contenedorNav) {
                // Insertar justo antes del botón de salir o al final
                const btnSalir = contenedorNav.querySelector('a[href*="logout"]');
                if (btnSalir) {
                    btnSalir.insertAdjacentHTML('beforebegin', relojHtml);
                } else {
                    contenedorNav.insertAdjacentHTML('beforeend', relojHtml);
                }
            } else {
                // Flotante discreto en esquina superior derecha
                const contenedorFlotante = document.createElement('div');
                contenedorFlotante.style.position = 'fixed';
                contenedorFlotante.style.top = '12px';
                contenedorFlotante.style.right = '16px';
                contenedorFlotante.style.zIndex = '9999';
                contenedorFlotante.innerHTML = relojHtml;
                document.body.appendChild(contenedorFlotante);
            }
            relojEl = document.getElementById('indicadorSesionSafari');
            if (relojEl) {
                relojEl.addEventListener('click', function () {
                    reiniciarTiempoSesion();
                });
            }
        }
    }

    // Formatear segundos a MM:SS
    function formatearTiempo(segundos) {
        const min = Math.floor(segundos / 60);
        const seg = segundos % 60;
        return `${String(min).padStart(2, '0')}:${String(seg).padStart(2, '0')}`;
    }

    // Actualizar la interfaz del reloj
    function actualizarVisualizacion() {
        asegurarRelojEnDOM();
        const txtEl = document.getElementById('relojSesionTxt');
        const iconoEl = document.getElementById('iconoRelojSesion');
        const relojEl = document.getElementById('indicadorSesionSafari');

        if (txtEl) {
            txtEl.textContent = formatearTiempo(segundosRestantes);
        }

        if (relojEl && iconoEl) {
            if (segundosRestantes <= 60) {
                // Último minuto de inactividad
                relojEl.style.borderColor = '#ef4444';
                relojEl.style.backgroundColor = '#fef2f2';
                iconoEl.className = 'bi bi-exclamation-triangle-fill text-danger animate-pulse';
                if (txtEl) txtEl.className = 'fw-bold text-danger font-monospace';
            } else if (segundosRestantes <= 180) {
                // Últimos 3 minutos
                relojEl.style.borderColor = '#f59e0b';
                relojEl.style.backgroundColor = '#fffbeb';
                iconoEl.className = 'bi bi-hourglass-split text-warning';
                if (txtEl) txtEl.className = 'fw-bold text-warning-emphasis font-monospace';
            } else {
                // Estado normal y activo
                relojEl.style.borderColor = '#cbd5e1';
                relojEl.style.backgroundColor = 'rgba(255, 255, 255, 0.95)';
                iconoEl.className = 'bi bi-clock-history text-secondary';
                if (txtEl) txtEl.className = 'fw-bold text-dark font-monospace';
            }
        }
    }

    // Reiniciar temporizador ante actividad física
    function reiniciarTiempoSesion() {
        segundosRestantes = TIEMPO_TOTAL_SEGUNDOS;
        actualizarVisualizacion();
        ocultarAvisoInactividad();
    }

    function cerrarSesion() {
        clearInterval(timerInterval);
        window.location.href = '/logout/?motivo=inactividad';
    }

    // Mostrar aviso no intrusivo si quedan menos de 60 segundos
    function mostrarAvisoInactividad() {
        let toastEl = document.getElementById('toastInactividadSafari');
        if (!toastEl) {
            const toastHtml = `
            <div id="toastInactividadSafari" class="toast align-items-center text-bg-warning border-0 position-fixed bottom-0 end-0 m-3 shadow-lg"
                 role="alert" aria-live="assertive" aria-atomic="true" style="z-index: 10000; min-width: 320px;">
                <div class="d-flex">
                    <div class="toast-body d-flex align-items-center gap-2">
                        <i class="bi bi-clock-history fs-4"></i>
                        <div>
                            <strong>Inactividad detectada</strong>
                            <div class="small">Mueve el cursor o presiona cualquier tecla para continuar tu turno.</div>
                        </div>
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" onclick="document.getElementById('toastInactividadSafari').classList.remove('show');"></button>
                </div>
            </div>`;
            document.body.insertAdjacentHTML('beforeend', toastHtml);
            toastEl = document.getElementById('toastInactividadSafari');
        }
        if (toastEl && !toastEl.classList.contains('show')) {
            toastEl.classList.add('show');
        }
    }

    function ocultarAvisoInactividad() {
        const toastEl = document.getElementById('toastInactividadSafari');
        if (toastEl && toastEl.classList.contains('show')) {
            toastEl.classList.remove('show');
        }
    }

    // Escuchar eventos físicos de actividad con debounce inteligente
    function handleActividad() {
        if (debounceTimer) return;
        debounceTimer = setTimeout(function () {
            debounceTimer = null;
            // Cualquier movimiento o tecla renueva el reloj y evita el cierre
            reiniciarTiempoSesion();
        }, 1000); // 1 segundo de amortiguación
    }

    document.addEventListener('DOMContentLoaded', function () {
        actualizarVisualizacion();

        // Escuchar todas las interacciones posibles del usuario
        const eventos = ['mousemove', 'mousedown', 'keydown', 'keypress', 'input', 'touchstart', 'scroll', 'click'];
        eventos.forEach(function (ev) {
            window.addEventListener(ev, handleActividad, { passive: true });
        });

        // Intervalo de descuento por segundo
        clearInterval(timerInterval);
        timerInterval = setInterval(function () {
            segundosRestantes--;

            if (segundosRestantes === 60) {
                mostrarAvisoInactividad();
            }

            if (segundosRestantes <= 0) {
                cerrarSesion();
            } else {
                actualizarVisualizacion();
            }
        }, 1000);
    });
})();
