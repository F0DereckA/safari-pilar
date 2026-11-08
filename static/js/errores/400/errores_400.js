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
