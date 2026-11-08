// static/js/administrador/admin_header.js
// Manejo ergonómico de navegación por 3 Categorías Madre (Hover en PC, Touch en Móvil/Tablet)
// Cumplimiento estricto de Norma ISO/IEC 27400 y directivas de arquitectura modular AGENTS.md

document.addEventListener('DOMContentLoaded', function() {
    // 1. Manejo fluido de hover con debounce para PC (pantallas >= 992px)
    if (window.matchMedia('(min-width: 992px)').matches) {
        document.querySelectorAll('.safari-category-dropdown').forEach(function(dropdown) {
            let timeoutId = null;
            const toggleBtn = dropdown.querySelector('[data-bs-toggle="dropdown"]');
            const menu = dropdown.querySelector('.dropdown-menu');

            if (!toggleBtn || !menu) return;

            dropdown.addEventListener('mouseenter', function() {
                clearTimeout(timeoutId);
                // Cerrar otros dropdowns de categoría abiertos
                document.querySelectorAll('.safari-category-dropdown .dropdown-menu.show').forEach(function(m) {
                    if (m !== menu) {
                        m.classList.remove('show');
                        const otherBtn = m.closest('.safari-category-dropdown')?.querySelector('[data-bs-toggle="dropdown"]');
                        if (otherBtn) {
                            otherBtn.classList.remove('show');
                            otherBtn.setAttribute('aria-expanded', 'false');
                        }
                    }
                });

                menu.classList.add('show');
                toggleBtn.classList.add('show');
                toggleBtn.setAttribute('aria-expanded', 'true');
            });

            dropdown.addEventListener('mouseleave', function() {
                timeoutId = setTimeout(function() {
                    menu.classList.remove('show');
                    toggleBtn.classList.remove('show');
                    toggleBtn.setAttribute('aria-expanded', 'false');
                }, 180);
            });
        });
    }

    // 2. Cierre automático de menú móvil Offcanvas al navegar
    document.querySelectorAll('#offcanvasSafariMenu a.dropdown-item').forEach(function(link) {
        link.addEventListener('click', function() {
            const offcanvasEl = document.getElementById('offcanvasSafariMenu');
            if (offcanvasEl && typeof bootstrap !== 'undefined') {
                const offcanvasInstance = bootstrap.Offcanvas.getInstance(offcanvasEl);
                if (offcanvasInstance) offcanvasInstance.hide();
            }
        });
    });

    // 3. Indicador de sesión activa
    const relojContenedor = document.getElementById('contenedorRelojSesion');
    if (relojContenedor && !relojContenedor.hasChildNodes()) {
        const spanReloj = document.createElement('span');
        spanReloj.className = 'badge bg-white text-muted border border-secondary-subtle px-2.5 py-1 rounded-pill small d-none d-md-inline-flex align-items-center gap-1 shadow-xs';
        spanReloj.innerHTML = '<i class="bi bi-clock-history text-secondary"></i> <span id="relojSesionTexto">Sesión Activa</span>';
        relojContenedor.appendChild(spanReloj);
    }
});
