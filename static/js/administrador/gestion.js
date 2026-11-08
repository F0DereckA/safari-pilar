function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.toast-container .toast').forEach(function(el) {
        const toast = new bootstrap.Toast(el, { delay: 4000 });
        toast.show();
        setTimeout(function() {
            try { toast.hide(); } catch(e){}
        }, 4000);
    });
});

function cambiarPestana(tabName) {
    const tabTrigger = document.querySelector('#pills-' + tabName + '-tab');
    if (tabTrigger) {
        const bsTab = new bootstrap.Tab(tabTrigger);
        bsTab.show();
        // Actualizar URL sin recargar
        const url = new URL(window.location);
        url.searchParams.set('tab', tabName);
        window.history.replaceState({}, '', url);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Sincronizar parámetro ?tab con Bootstrap Tabs
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    if (tabParam) {
        cambiarPestana(tabParam);
    }

    // Al cambiar de tab, actualizar el query param en el navegador
    const tabLinks = document.querySelectorAll('#gestionTabs button[data-bs-toggle="pill"]');
    tabLinks.forEach(function (tabEl) {
        tabEl.addEventListener('shown.bs.tab', function (event) {
            const targetId = event.target.getAttribute('data-bs-target');
            const tabNombre = targetId.replace('#pills-', '');
            const url = new URL(window.location);
            url.searchParams.set('tab', tabNombre);
            window.history.replaceState({}, '', url);
        });
    });

    // Configurar los 4 buscadores reactivos en tiempo real con filtro_tiempo_real.js
    // 1. Trabajadores
    SafariFiltroEnVivo.configurar({
        inputId: 'buscarTrabajadorEnVivo',
        itemSelector: '.worker-row',
        counterId: 'contadorTrabajadoresEnVivo',
        emptyId: 'sinTrabajadoresMensaje',
        secondaryFilters: [
            { selectId: 'filtroLocalTrab', dataAttr: 'local' },
            { selectId: 'filtroRolTrab', dataAttr: 'rol' }
        ]
    });

    // 2. Mesas
    SafariFiltroEnVivo.configurar({
        inputId: 'buscarMesaEnVivo',
        itemSelector: '.mesa-item',
        counterId: 'contadorMesasEnVivo',
        emptyId: 'sinMesasMensaje',
        secondaryFilters: [
            { selectId: 'filtroLocalMesa', dataAttr: 'local' },
            { selectId: 'filtroEstadoMesa', dataAttr: 'estado' }
        ]
    });

    // 3. Productos
    SafariFiltroEnVivo.configurar({
        inputId: 'buscarProductoEnVivo',
        itemSelector: '.producto-fila',
        counterId: 'contadorProductosEnVivo',
        emptyId: 'sinProductosMensaje',
        secondaryFilters: [
            { selectId: 'filtroCategoriaProd', dataAttr: 'categoria' },
            { selectId: 'filtroLocalProd', dataAttr: 'local' }
        ]
    });

    // 4. Menús
    SafariFiltroEnVivo.configurar({
        inputId: 'buscarMenuEnVivo',
        itemSelector: '.menu-card-item',
        counterId: 'contadorMenusEnVivo',
        emptyId: 'sinMenusMensaje',
        secondaryFilters: [
            { selectId: 'filtroLocalMenu', dataAttr: 'local' }
        ]
    });
});

function mostrarToastSafari(mensaje, tipo='success') {
    const toastEl = document.getElementById('toastSafariNotif');
    const textoEl = document.getElementById('toastSafariTexto');
    if (textoEl) textoEl.textContent = mensaje;
    if (toastEl) {
        toastEl.className = `toast align-items-center text-white bg-${tipo} border-0 rounded-4 shadow-lg`;
        const toastInst = bootstrap.Toast.getInstance(toastEl) || new bootstrap.Toast(toastEl, { delay: 3500 });
        toastInst.show();
    }
}

// Tarea 1 y 7: Guardado de Carta por AJAX en tiempo real sin recargar pantalla
function guardarMenuGestionAjax(e, menuId) {
    e.preventDefault();
    const form = e.target;
    const btn = document.getElementById(`btn_guardar_menu_${menuId}`);
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Guardando...';
    }
    const formData = new FormData(form);
    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'ok') {
            // Actualizar nombre y local en la tarjeta
            const elNom = document.getElementById(`menu_nombre_val_${menuId}`);
            if (elNom) elNom.textContent = data.nombre;

            const elModalTit = document.getElementById(`modal_tit_menu_${menuId}`);
            if (elModalTit) elModalTit.textContent = data.nombre;

            const elLoc = document.getElementById(`menu_local_val_${menuId}`);
            if (elLoc) elLoc.innerHTML = `<i class="bi bi-geo-alt-fill text-danger me-1"></i>${data.local_nombre}`;

            const elBadge = document.getElementById(`menu_badge_count_${menuId}`);
            if (elBadge) elBadge.textContent = `${data.productos_count} platos vinculados`;

            // Actualizar lista de productos
            const elLista = document.getElementById(`menu_prods_list_${menuId}`);
            if (elLista) {
                if (data.productos && data.productos.length > 0) {
                    elLista.innerHTML = data.productos.map(p => `
                        <span class="badge bg-white text-dark border small py-1 px-2">
                            ${escapeHtml(p.nombre)} ($${Math.round(p.precio).toLocaleString('es-CL')})
                        </span>
                    `).join('');
                } else {
                    elLista.innerHTML = '<span class="text-muted small">Sin productos asignados a la carta</span>';
                }
            }

            // Cerrar modal flotante con animación suave
            const modalEl = document.getElementById(`modalEditarMenuGestion_${menuId}`);
            if (modalEl) {
                const modalInst = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                modalInst.hide();
            }

            mostrarToastSafari(data.mensaje || '¡Carta actualizada en tiempo real!');
        } else {
            alert(data.mensaje || 'Error al guardar la carta');
        }
    })
    .catch(err => {
        console.error(err);
        form.submit();
    })
    .finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Guardar Cambios';
        }
    });
}

// Tarea 6 y 7: Guardado de Ofertas por AJAX en tiempo real sin recargar pantalla
function toggleOfertaCamposGestion(prodId) {
    const chk = document.getElementById(`check_oferta_g_${prodId}`);
    const div = document.getElementById(`campos_oferta_g_${prodId}`);
    if (chk && div) {
        if (chk.checked) {
            div.classList.remove('d-none');
        } else {
            div.classList.add('d-none');
        }
    }
}

function guardarOfertaGestionAjax(e, prodId) {
    e.preventDefault();
    const form = e.target;
    const btn = document.getElementById(`btn_guardar_oferta_g_${prodId}`);
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Guardando...';
    }
    const formData = new FormData(form);
    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'ok') {
            const celdaPrecio = document.getElementById(`celda_precio_${prodId}`);
            if (celdaPrecio) {
                if (data.en_oferta) {
                    if (data.tipo_oferta === 'PRECIO_FIJO' && data.precio_oferta) {
                        celdaPrecio.innerHTML = `
                            <div>
                                <del class="text-muted small">$${Math.round(data.precio_base).toLocaleString('es-CL')}</del>
                                <strong class="text-danger fs-6">$${Math.round(data.precio_oferta).toLocaleString('es-CL')} CLP</strong>
                            </div>
                            <span class="badge bg-danger shadow-xs py-1 px-2" style="font-size: 0.68rem;">
                                <i class="bi bi-tag-fill me-1"></i>${data.descripcion_oferta || 'PRECIO FIJO'}
                            </span>
                        `;
                    } else {
                        let bText = data.descripcion_oferta || 'OFERTA ACTIVA';
                        if (data.tipo_oferta === '3X2') bText = 'PROMO 3x2 (LLEVA 3, PAGA 2)';
                        else if (data.tipo_oferta === '2X1') bText = 'PROMO 2x1 (LLEVA 2, PAGA 1)';
                        else if (data.tipo_oferta === 'SEGUNDA_1') bText = data.descripcion_oferta || '¡2da unidad a $1 peso!';
                        celdaPrecio.innerHTML = `
                            <div>
                                <strong class="text-dark fs-6">$${Math.round(data.precio_base).toLocaleString('es-CL')} CLP</strong>
                            </div>
                            <span class="badge bg-danger shadow-xs py-1 px-2" style="font-size: 0.68rem;">
                                <i class="bi bi-fire me-1"></i>${bText}
                            </span>
                        `;
                    }
                } else {
                    celdaPrecio.innerHTML = `<strong class="text-danger">$${Math.round(data.precio_base).toLocaleString('es-CL')} CLP</strong>`;
                }
            }
            const modalEl = document.getElementById(`modalOfertaProdGestion_${prodId}`);
            if (modalEl) {
                const modalInst = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                modalInst.hide();
            }
            mostrarToastSafari(data.mensaje || '¡Oferta actualizada en tiempo real!');
        } else {
            alert(data.mensaje || 'Error al guardar la oferta');
        }
    })
    .catch(err => {
        console.error(err);
        form.submit();
    })
    .finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Guardar Oferta';
        }
    });
}
