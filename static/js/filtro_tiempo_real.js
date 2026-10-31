/**
 * Parque Safari - Filtro y Búsqueda en Tiempo Real (Reactividad por Cada Tecleo)
 * Permite filtrar tablas, tarjetas y listas instantáneamente con cada tecla pulsada ('input' event).
 * Sin necesidad de presionar Enter ni recargar la página ("apreta Z y se actualiza al tiro").
 */
(function () {
    // Normalizar texto: minúsculas y eliminación de tildes/diacríticos
    function normalizar(texto) {
        if (!texto) return '';
        return String(texto)
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .trim();
    }

    /**
     * Inicializa un buscador en tiempo real
     * @param {Object} config
     *   - inputId: ID del input de texto
     *   - itemSelector: Selector CSS de cada fila o tarjeta a filtrar
     *   - textSelector: Selector opcional de texto interno (o todo el item si no se pasa)
     *   - counterId: ID opcional del badge o texto de conteo de resultados
     *   - emptyId: ID opcional del contenedor de mensaje "sin resultados"
     *   - secondaryFilters: Array de { selectId: string, dataAttr: string } para filtros adicionales (locales, roles, etc.)
     */
    function configurarFiltroEnVivo(config) {
        const input = document.getElementById(config.inputId);
        if (!input) return;

        const items = document.querySelectorAll(config.itemSelector);
        const counter = config.counterId ? document.getElementById(config.counterId) : null;
        const emptyMsg = config.emptyId ? document.getElementById(config.emptyId) : null;

        // Función de filtrado reactivo
        function ejecutarFiltro() {
            const query = normalizar(input.value);
            let coincidencias = 0;

            // Valores de filtros secundarios si existen
            const filtrosExtra = (config.secondaryFilters || []).map(f => {
                const el = document.getElementById(f.selectId);
                return {
                    valor: el ? normalizar(el.value) : '',
                    dataAttr: f.dataAttr
                };
            }).filter(f => f.valor && f.valor !== 'todos' && f.valor !== '');

            items.forEach(function (item) {
                // Comprobación de texto
                let coincideTexto = true;
                if (query) {
                    const textoItem = config.textSelector
                        ? normalizar(Array.from(item.querySelectorAll(config.textSelector)).map(el => el.textContent).join(' '))
                        : normalizar(item.textContent);
                    coincideTexto = textoItem.includes(query);
                }

                // Comprobación de filtros secundarios (por ejemplo local o rol)
                let coincideFiltrosExtra = true;
                filtrosExtra.forEach(f => {
                    const itemVal = normalizar(item.getAttribute(`data-${f.dataAttr}`) || item.dataset[f.dataAttr] || '');
                    if (itemVal && itemVal !== f.valor) {
                        coincideFiltrosExtra = false;
                    }
                });

                if (coincideTexto && coincideFiltrosExtra) {
                    item.style.display = '';
                    item.classList.remove('d-none');
                    coincidencias++;
                } else {
                    item.style.display = 'none';
                    item.classList.add('d-none');
                }
            });

            // Actualizar contador si existe
            if (counter) {
                counter.textContent = coincidencias;
            }

            // Mostrar u ocultar mensaje de "sin resultados"
            if (emptyMsg) {
                if (coincidencias === 0 && items.length > 0) {
                    emptyMsg.classList.remove('d-none');
                    emptyMsg.style.display = 'block';
                } else {
                    emptyMsg.classList.add('d-none');
                    emptyMsg.style.display = 'none';
                }
            }
        }

        // Reactividad instantánea con cada tecleo ('input' se dispara con cada letra, borrado o pegado)
        input.addEventListener('input', ejecutarFiltro);
        input.addEventListener('keyup', ejecutarFiltro);

        // Si el input está dentro de un form, evitar que Enter recargue la página si es búsqueda puramente cliente
        const formPadre = input.closest('form');
        if (formPadre && !formPadre.classList.contains('form-servidor')) {
            formPadre.addEventListener('submit', function (e) {
                e.preventDefault();
                ejecutarFiltro();
            });
        }

        // Vincular filtros secundarios para que también actualicen al cambiar
        (config.secondaryFilters || []).forEach(f => {
            const el = document.getElementById(f.selectId);
            if (el) {
                el.addEventListener('change', ejecutarFiltro);
            }
        });

        // Botón de limpiar búsqueda si existe
        const btnLimpiar = document.querySelector(`[data-limpiar-filtro="${config.inputId}"]`);
        if (btnLimpiar) {
            btnLimpiar.addEventListener('click', function () {
                input.value = '';
                ejecutarFiltro();
                input.focus();
            });
        }
    }

    // Exponer globalmente para inicializar en cualquier módulo
    window.SafariFiltroEnVivo = {
        configurar: configurarFiltroEnVivo,
        normalizar: normalizar
    };

    // Auto-inicialización para campos comunes al cargar el DOM
    document.addEventListener('DOMContentLoaded', function () {
        // 1. Buscador de Trabajadores
        if (document.getElementById('buscarTrabajador')) {
            configurarFiltroEnVivo({
                inputId: 'buscarTrabajador',
                itemSelector: '.worker-row',
                counterId: 'contadorResultados',
                emptyId: 'sinResultadosMensaje',
                secondaryFilters: [
                    { selectId: 'filtroLocal', dataAttr: 'local' },
                    { selectId: 'filtroRol', dataAttr: 'rol' },
                    { selectId: 'filtroEstado', dataAttr: 'estado' }
                ]
            });
        }

        // 2. Buscador de Productos
        if (document.getElementById('buscarProductoEnVivo')) {
            configurarFiltroEnVivo({
                inputId: 'buscarProductoEnVivo',
                itemSelector: '.producto-fila',
                counterId: 'contadorProductosEnVivo',
                emptyId: 'sinProductosMensaje',
                secondaryFilters: [
                    { selectId: 'filtroCategoriaProd', dataAttr: 'categoria' },
                    { selectId: 'filtroLocalProd', dataAttr: 'local' }
                ]
            });
        }

        // 3. Buscador de Mesas
        if (document.getElementById('buscarMesaEnVivo')) {
            configurarFiltroEnVivo({
                inputId: 'buscarMesaEnVivo',
                itemSelector: '.mesa-item',
                counterId: 'contadorMesasEnVivo',
                emptyId: 'sinMesasMensaje',
                secondaryFilters: [
                    { selectId: 'filtroLocalMesa', dataAttr: 'local' },
                    { selectId: 'filtroEstadoMesa', dataAttr: 'estado' }
                ]
            });
        }

        // 4. Buscador de Menús
        if (document.getElementById('buscarMenuEnVivo')) {
            configurarFiltroEnVivo({
                inputId: 'buscarMenuEnVivo',
                itemSelector: '.menu-card-item',
                counterId: 'contadorMenusEnVivo',
                emptyId: 'sinMenusMensaje',
                secondaryFilters: [
                    { selectId: 'filtroLocalMenu', dataAttr: 'local' }
                ]
            });
        }

        // 5. Buscador de Historial de Acciones
        if (document.getElementById('buscarHistorialEnVivo')) {
            configurarFiltroEnVivo({
                inputId: 'buscarHistorialEnVivo',
                itemSelector: '.evento-historial-row',
                counterId: 'contadorHistorialEnVivo',
                emptyId: 'sinHistorialMensaje',
                secondaryFilters: [
                    { selectId: 'filtroTipoHistorial', dataAttr: 'tipo' },
                    { selectId: 'filtroLocalHistorial', dataAttr: 'local' }
                ]
            });
        }
    });
})();
