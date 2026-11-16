/* ==========================================================================
   Impresión Oficial de Reportes de Ventas (RF18) - Zona Impresión
   ========================================================================== */

function imprimirReporteVentas() {
    window.print();
}

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-safari-action="print"]').forEach(function(btn) {
        btn.addEventListener('click', imprimirReporteVentas);
    });
});
