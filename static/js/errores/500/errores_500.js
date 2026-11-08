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
