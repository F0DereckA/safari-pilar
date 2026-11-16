/**
 * Inicializa toasts flotantes breves en esquina para avisos operativos/errores.
 * Pausa el cierre automático mientras el usuario mantiene el foco o puntero sobre el toast.
 */
(function () {
    function inicializarToastsSafari() {
        if (typeof bootstrap === 'undefined' || !bootstrap.Toast) return;

        document.querySelectorAll('.toast-container[role="region"] .toast').forEach(function (el) {
            if (el.dataset.safariToastInit === '1') return;
            el.dataset.safariToastInit = '1';

            const delayMs = Number.parseInt(el.dataset.bsDelay || '3500', 10) || 3500;
            const instance = bootstrap.Toast.getOrCreateInstance(el, {
                delay: delayMs,
                autohide: true,
            });

            el.addEventListener('hide.bs.toast', function (ev) {
                if (el.contains(document.activeElement)) {
                    ev.preventDefault();
                }
            });

            el.addEventListener('focusout', function () {
                setTimeout(function () {
                    if (!el.contains(document.activeElement) && el.classList.contains('show')) {
                        instance.hide();
                    }
                }, delayMs);
            });

            instance.show();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', inicializarToastsSafari);
    } else {
        inicializarToastsSafari();
    }
})();
