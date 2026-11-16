/**
 * Parque Safari - Control de Seguridad y Tiempo de Sesión
 * 1. Muestra un reloj discreto y estilizado con la cuenta regresiva en el header o flotante.
 * 2. Cierre flexible: mientras haya actividad física (tecleo, movimiento de cursor, click, scroll, touch),
 *    la sesión se renueva AUTOMÁTICAMENTE a 15:00 y NUNCA se cierra.
 * 3. Si transcurren 15 minutos continuos de 100% inactividad, se cierra de manera segura.
 */
(function () {
    // Tarea 2: KDS Cocina y Barra son estaciones táctiles continuas; sin cierre por inactividad
    if (window.location.pathname.includes('/cocina/') || window.location.pathname.includes('/barra/')) {
        return;
    }

    const TIEMPO_TOTAL_SEGUNDOS = 15 * 60; // 15 minutos (900s)
    let segundosRestantes = TIEMPO_TOTAL_SEGUNDOS;
    let timerInterval = null;
    let debounceTimer = null;

    function construirRelojElemento() {
        const relojEl = document.createElement('button');
        relojEl.type = 'button';
        relojEl.id = 'indicadorSesionSafari';
        relojEl.className = 'd-inline-flex align-items-center gap-1 px-3 py-1 rounded-pill shadow-sm safari-session-pill';
        relojEl.title = 'Tiempo de sesión restante por inactividad. Se renueva automáticamente al interactuar.';
        relojEl.setAttribute('aria-label', 'Tiempo de sesión restante por inactividad; presiona para renovar');

        const icono = document.createElement('i');
        icono.id = 'iconoRelojSesion';
        icono.className = 'bi bi-clock-history text-secondary';

        const etiqueta = document.createElement('span');
        etiqueta.className = 'text-muted small d-none d-sm-inline';
        etiqueta.textContent = 'Sesión:';

        const texto = document.createElement('span');
        texto.id = 'relojSesionTxt';
        texto.className = 'fw-bold text-dark font-monospace';
        texto.textContent = '15:00';

        relojEl.appendChild(icono);
        relojEl.appendChild(etiqueta);
        relojEl.appendChild(texto);
        return relojEl;
    }

    function asegurarRelojEnDOM() {
        let relojEl = document.getElementById('indicadorSesionSafari');
        if (!relojEl) {
            const contenedorNav = document.getElementById('contenedorRelojSesion') ||
                                  document.querySelector('.safari-header .d-flex.align-items-center.gap-3') ||
                                  document.querySelector('.navbar .container-fluid') ||
                                  document.querySelector('header');

            relojEl = construirRelojElemento();
            if (contenedorNav) {
                const btnSalir = contenedorNav.querySelector('a[href*="logout"]');
                if (btnSalir && btnSalir.parentNode === contenedorNav) {
                    contenedorNav.insertBefore(relojEl, btnSalir);
                } else {
                    contenedorNav.appendChild(relojEl);
                }
            } else {
                const contenedorFlotante = document.createElement('div');
                contenedorFlotante.className = 'safari-session-floating';
                contenedorFlotante.appendChild(relojEl);
                document.body.appendChild(contenedorFlotante);
            }
            relojEl.addEventListener('click', function () {
                reiniciarTiempoSesion();
            });
        }
    }

    function formatearTiempo(segundos) {
        const min = Math.floor(segundos / 60);
        const seg = segundos % 60;
        return `${String(min).padStart(2, '0')}:${String(seg).padStart(2, '0')}`;
    }

    function actualizarVisualizacion() {
        asegurarRelojEnDOM();
        const txtEl = document.getElementById('relojSesionTxt');
        const iconoEl = document.getElementById('iconoRelojSesion');
        const relojEl = document.getElementById('indicadorSesionSafari');

        if (txtEl) {
            txtEl.textContent = formatearTiempo(segundosRestantes);
        }

        if (relojEl && iconoEl) {
            relojEl.classList.remove('is-warning', 'is-danger');
            if (segundosRestantes <= 60) {
                relojEl.classList.add('is-danger');
                iconoEl.className = 'bi bi-exclamation-triangle-fill text-danger animate-pulse';
                if (txtEl) txtEl.className = 'fw-bold text-danger font-monospace';
            } else if (segundosRestantes <= 180) {
                relojEl.classList.add('is-warning');
                iconoEl.className = 'bi bi-hourglass-split text-warning-emphasis';
                if (txtEl) txtEl.className = 'fw-bold text-warning-emphasis font-monospace';
            } else {
                iconoEl.className = 'bi bi-clock-history text-secondary';
                if (txtEl) txtEl.className = 'fw-bold text-dark font-monospace';
            }
        }
    }

    function reiniciarTiempoSesion() {
        segundosRestantes = TIEMPO_TOTAL_SEGUNDOS;
        actualizarVisualizacion();
        ocultarAvisoInactividad();
    }

    function cerrarSesion() {
        clearInterval(timerInterval);
        window.location.href = '/logout/?motivo=inactividad';
    }

    function mostrarAvisoInactividad() {
        let toastEl = document.getElementById('toastInactividadSafari');
        if (!toastEl) {
            toastEl = document.createElement('div');
            toastEl.id = 'toastInactividadSafari';
            toastEl.className = 'toast align-items-center text-bg-warning border-0 position-fixed bottom-0 end-0 m-3 shadow-lg safari-session-toast';
            toastEl.setAttribute('role', 'alert');
            toastEl.setAttribute('aria-live', 'assertive');
            toastEl.setAttribute('aria-atomic', 'true');

            const flexWrap = document.createElement('div');
            flexWrap.className = 'd-flex';

            const body = document.createElement('div');
            body.className = 'toast-body d-flex align-items-center gap-2';

            const ico = document.createElement('i');
            ico.className = 'bi bi-clock-history fs-4';

            const msgBox = document.createElement('div');
            const titulo = document.createElement('strong');
            titulo.textContent = 'Inactividad detectada';
            const sub = document.createElement('div');
            sub.className = 'small';
            sub.textContent = 'Mueve el cursor o presiona cualquier tecla para continuar tu turno.';
            msgBox.appendChild(titulo);
            msgBox.appendChild(sub);

            body.appendChild(ico);
            body.appendChild(msgBox);

            const btnClose = document.createElement('button');
            btnClose.type = 'button';
            btnClose.className = 'btn-close me-2 m-auto';
            btnClose.setAttribute('aria-label', 'Cerrar aviso de inactividad');
            btnClose.addEventListener('click', function () {
                toastEl.classList.remove('show');
            });

            flexWrap.appendChild(body);
            flexWrap.appendChild(btnClose);
            toastEl.appendChild(flexWrap);
            document.body.appendChild(toastEl);
        }
        if (!toastEl.classList.contains('show')) {
            toastEl.classList.add('show');
        }
    }

    function ocultarAvisoInactividad() {
        const toastEl = document.getElementById('toastInactividadSafari');
        if (toastEl && toastEl.classList.contains('show')) {
            toastEl.classList.remove('show');
        }
    }

    function handleActividad() {
        if (debounceTimer) return;
        debounceTimer = setTimeout(function () {
            debounceTimer = null;
            reiniciarTiempoSesion();
        }, 1000);
    }

    document.addEventListener('DOMContentLoaded', function () {
        actualizarVisualizacion();

        const eventos = ['mousemove', 'mousedown', 'keydown', 'keypress', 'input', 'touchstart', 'scroll', 'click'];
        eventos.forEach(function (ev) {
            window.addEventListener(ev, handleActividad, { passive: true });
        });

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
