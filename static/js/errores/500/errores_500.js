/* ==========================================================================
   Recuperación y Navegación en Pantallas de Error Servidor HTTP 5xx (500, 502, 503, 504)
   ========================================================================== */

function volverAtrasSafari() {
    if (window.history.length > 1) {
        window.history.back();
    } else {
        window.location.href = '/';
    }
}

function reintentarCargaSafari() {
    window.location.reload();
}

document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('click', (ev) => {
        const trigger = ev.target.closest('[data-safari-action]');
        if (!trigger) return;
        const accion = trigger.dataset.safariAction;
        if (accion === 'back') {
            volverAtrasSafari();
        } else if (accion === 'reload') {
            reintentarCargaSafari();
        }
    });
});
