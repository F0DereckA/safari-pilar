/* ==========================================================================
   Navegación Segura en Pantallas de Error Cliente HTTP 4xx (400, 401, 403, 404)
   ========================================================================== */

function volverAtrasSafari() {
    if (window.history.length > 1) {
        window.history.back();
    } else {
        window.location.href = '/';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('click', (ev) => {
        const trigger = ev.target.closest('[data-safari-action]');
        if (!trigger) return;
        const accion = trigger.dataset.safariAction;
        if (accion === 'back') {
            volverAtrasSafari();
        }
    });
});
