/**
 * Controlador de Gestión Integral de Promociones, Campañas y Descuentos
 * Parque Safari — Aloy & Ezio Architecture
 */

document.addEventListener('DOMContentLoaded', function () {
    // -------------------------------------------------------------
    // 1. Selector de Tipo de Promoción por Producto (Modal Crear)
    // -------------------------------------------------------------
    const tipoOfertaSelect = document.getElementById('promoTipoOferta');
    const campoPrecioOferta = document.getElementById('campoPrecioOferta');
    const campoDescuentoPct = document.getElementById('campoDescuentoPct');
    const campoCantidadMinima = document.getElementById('campoCantidadMinima');
    const inputPrecioOferta = document.getElementById('promoPrecioOferta');
    const inputDescuentoPct = document.getElementById('promoDescuentoPct');
    const labelPrecioOferta = document.getElementById('labelPrecioOferta');
    const labelDescuentoPct = document.getElementById('labelDescuentoPct');

    function actualizarCamposPromoProducto() {
        if (!tipoOfertaSelect) return;
        const tipo = tipoOfertaSelect.value;

        if (tipo === 'SEGUNDA_1') {
            if (campoPrecioOferta) campoPrecioOferta.classList.remove('d-none');
            if (campoDescuentoPct) campoDescuentoPct.classList.add('d-none');
            if (campoCantidadMinima) campoCantidadMinima.classList.add('d-none');
            if (labelPrecioOferta) labelPrecioOferta.innerText = 'Precio de la 2da Unidad (CLP):';
            if (inputPrecioOferta && !inputPrecioOferta.value) inputPrecioOferta.value = '1';
        } else if (tipo === 'PRECIO_FIJO') {
            if (campoPrecioOferta) campoPrecioOferta.classList.remove('d-none');
            if (campoDescuentoPct) campoDescuentoPct.classList.add('d-none');
            if (campoCantidadMinima) campoCantidadMinima.classList.add('d-none');
            if (labelPrecioOferta) labelPrecioOferta.innerText = 'Precio Promocional Fijo (CLP):';
        } else if (tipo === 'LLEVA_2_POR') {
            if (campoPrecioOferta) campoPrecioOferta.classList.remove('d-none');
            if (campoDescuentoPct) campoDescuentoPct.classList.add('d-none');
            if (campoCantidadMinima) campoCantidadMinima.classList.add('d-none');
            if (labelPrecioOferta) labelPrecioOferta.innerText = 'Precio Total del Pack por 2 Unidades (CLP):';
        } else if (tipo === 'CANTIDAD_MINIMA') {
            if (campoPrecioOferta) campoPrecioOferta.classList.remove('d-none');
            if (campoDescuentoPct) campoDescuentoPct.classList.add('d-none');
            if (campoCantidadMinima) campoCantidadMinima.classList.remove('d-none');
            if (labelPrecioOferta) labelPrecioOferta.innerText = 'Precio Rebajado por Unidad (CLP):';
        } else if (tipo === 'DESCUENTO_PCT') {
            if (campoPrecioOferta) campoPrecioOferta.classList.add('d-none');
            if (campoDescuentoPct) campoDescuentoPct.classList.remove('d-none');
            if (campoCantidadMinima) campoCantidadMinima.classList.add('d-none');
            if (labelDescuentoPct) labelDescuentoPct.innerText = 'Porcentaje de Descuento (%):';
        } else if (tipo === 'SEGUNDA_PCT') {
            if (campoPrecioOferta) campoPrecioOferta.classList.add('d-none');
            if (campoDescuentoPct) campoDescuentoPct.classList.remove('d-none');
            if (campoCantidadMinima) campoCantidadMinima.classList.add('d-none');
            if (labelDescuentoPct) labelDescuentoPct.innerText = 'Porcentaje de Descuento en la 2da Unidad (%):';
            if (inputDescuentoPct && !inputDescuentoPct.value) inputDescuentoPct.value = '50';
        } else {
            // 2X1, 3X2
            if (campoPrecioOferta) campoPrecioOferta.classList.add('d-none');
            if (campoDescuentoPct) campoDescuentoPct.classList.add('d-none');
            if (campoCantidadMinima) campoCantidadMinima.classList.add('d-none');
        }
    }

    if (tipoOfertaSelect) {
        tipoOfertaSelect.addEventListener('change', actualizarCamposPromoProducto);
        actualizarCamposPromoProducto();
    }

    // -------------------------------------------------------------
    // 2. Selector de Tipo de Campaña (Modal Crear Campaña)
    // -------------------------------------------------------------
    const tipoCampanaSelect = document.getElementById('campanaTipo');
    const grupoMedioPago = document.getElementById('grupoMedioPago');
    const grupoBanco = document.getElementById('grupoBanco');

    function actualizarCamposCampana() {
        if (!tipoCampanaSelect) return;
        const tipo = tipoCampanaSelect.value;
        if (tipo === 'MEDIO_PAGO') {
            if (grupoMedioPago) grupoMedioPago.classList.remove('d-none');
            if (grupoBanco) grupoBanco.classList.remove('d-none');
        } else {
            if (grupoMedioPago) grupoMedioPago.classList.remove('d-none');
            if (grupoBanco) grupoBanco.classList.remove('d-none');
        }
    }

    if (tipoCampanaSelect) {
        tipoCampanaSelect.addEventListener('change', actualizarCamposCampana);
        actualizarCamposCampana();
    }

    // -------------------------------------------------------------
    // 3. Modal Editar Campaña (Cargar datos vía data-attributes)
    // -------------------------------------------------------------
    const modalEditarCampana = document.getElementById('modalEditarCampana');
    if (modalEditarCampana) {
        modalEditarCampana.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            if (!button) return;

            const id = button.getAttribute('data-id');
            const nombre = button.getAttribute('data-nombre') || '';
            const desc = button.getAttribute('data-descripcion') || '';
            const tipo = button.getAttribute('data-tipo') || 'GENERAL';
            const pct = button.getAttribute('data-pct') || '0';
            const medio = button.getAttribute('data-medio') || 'TODOS';
            const banco = button.getAttribute('data-banco') || '';
            const minimo = button.getAttribute('data-minimo') || '0';
            const tope = button.getAttribute('data-tope') || '0';
            const limite = button.getAttribute('data-limite') || '0';
            const inicio = button.getAttribute('data-inicio') || '';
            const fin = button.getAttribute('data-fin') || '';
            const activa = button.getAttribute('data-activa') === 'true';
            const cat = button.getAttribute('data-cat') || '';
            const prod = button.getAttribute('data-prod') || '';

            document.getElementById('edit_oferta_id').value = id;
            document.getElementById('edit_campana_nombre').value = nombre;
            document.getElementById('edit_campana_descripcion').value = desc;
            document.getElementById('edit_campana_tipo').value = tipo;
            document.getElementById('edit_campana_pct').value = pct;
            document.getElementById('edit_campana_medio').value = medio;
            document.getElementById('edit_campana_banco').value = banco;
            document.getElementById('edit_campana_minimo').value = minimo;
            document.getElementById('edit_campana_tope').value = tope;
            document.getElementById('edit_campana_limite').value = limite;
            document.getElementById('edit_campana_inicio').value = inicio;
            document.getElementById('edit_campana_fin').value = fin;
            document.getElementById('edit_campana_activa').checked = activa;

            const selCat = document.getElementById('edit_campana_categoria');
            if (selCat) selCat.value = cat;
            const selProd = document.getElementById('edit_campana_producto');
            if (selProd) selProd.value = prod;
        });
    }

    // -------------------------------------------------------------
    // 4. Modal Editar Promoción de Producto
    // -------------------------------------------------------------
    const modalEditarPromoProd = document.getElementById('modalEditarPromoProducto');
    if (modalEditarPromoProd) {
        modalEditarPromoProd.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            if (!button) return;

            const prodId = button.getAttribute('data-id');
            const prodNombre = button.getAttribute('data-nombre') || '';
            const tipo = button.getAttribute('data-tipo') || 'SEGUNDA_1';
            const precio = button.getAttribute('data-precio') || '1';
            const pct = button.getAttribute('data-pct') || '0';
            const limite = button.getAttribute('data-limite') || '0';
            const desc = button.getAttribute('data-desc') || '';
            const minCant = button.getAttribute('data-min-cant') || '2';

            document.getElementById('edit_promo_producto_id').value = prodId;
            document.getElementById('edit_promo_nombre_display').innerText = prodNombre;
            document.getElementById('edit_promo_tipo').value = tipo;
            document.getElementById('edit_promo_precio').value = precio;
            document.getElementById('edit_promo_pct').value = pct;
            document.getElementById('edit_promo_limite').value = limite;
            document.getElementById('edit_promo_desc').value = desc;
            const inputMinCant = document.getElementById('edit_promo_min_cant');
            if (inputMinCant) inputMinCant.value = minCant;

            const editTipoSelect = document.getElementById('edit_promo_tipo');
            function actualizarCamposEditPromo() {
                const t = editTipoSelect.value;
                const gPrecio = document.getElementById('edit_grupo_precio');
                const gPct = document.getElementById('edit_grupo_pct');
                const gMin = document.getElementById('edit_grupo_min_cant');
                const lPct = document.getElementById('edit_label_pct');
                if (t === 'SEGUNDA_1' || t === 'PRECIO_FIJO' || t === 'LLEVA_2_POR') {
                    if (gPrecio) gPrecio.classList.remove('d-none');
                    if (gPct) gPct.classList.add('d-none');
                    if (gMin) gMin.classList.add('d-none');
                } else if (t === 'CANTIDAD_MINIMA') {
                    if (gPrecio) gPrecio.classList.remove('d-none');
                    if (gPct) gPct.classList.add('d-none');
                    if (gMin) gMin.classList.remove('d-none');
                } else if (t === 'DESCUENTO_PCT') {
                    if (gPrecio) gPrecio.classList.add('d-none');
                    if (gPct) gPct.classList.remove('d-none');
                    if (gMin) gMin.classList.add('d-none');
                    if (lPct) lPct.innerText = 'Porcentaje de Descuento (%):';
                } else if (t === 'SEGUNDA_PCT') {
                    if (gPrecio) gPrecio.classList.add('d-none');
                    if (gPct) gPct.classList.remove('d-none');
                    if (gMin) gMin.classList.add('d-none');
                    if (lPct) lPct.innerText = 'Porcentaje de Descuento en la 2da Unidad (%):';
                } else {
                    if (gPrecio) gPrecio.classList.add('d-none');
                    if (gPct) gPct.classList.add('d-none');
                    if (gMin) gMin.classList.add('d-none');
                }
            }
            editTipoSelect.addEventListener('change', actualizarCamposEditPromo);
            actualizarCamposEditPromo();
        });
    }

    // -------------------------------------------------------------
    // 5. Presets rápidos de 2da Unidad ($1, $5, $500, etc.)
    // -------------------------------------------------------------
    document.querySelectorAll('.btn-preset-precio').forEach(btn => {
        btn.addEventListener('click', function () {
            const valor = this.getAttribute('data-valor');
            const targetInput = document.getElementById('promoPrecioOferta');
            if (targetInput) {
                targetInput.value = valor;
            }
        });
    });
});
