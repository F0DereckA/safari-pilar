const posConfig = (() => {

    const el = document.getElementById('posConfigData');

    if (!el) return {};

    try { return JSON.parse(el.textContent || '{}'); } catch (e) { return {}; }

})();



const productos = (() => {
    try {
        return JSON.parse(document.getElementById('productosPosData')?.textContent || '{}');
    } catch (e) {
        return {};
    }
})();

const ofertasPos = (() => {
    try {
        return JSON.parse(document.getElementById('ofertasPosData')?.textContent || '[]');
    } catch (e) {
        return [];
    }
})();



// Estado del carrito/pedido y notas

const cantidades = {};

Object.keys(productos).forEach(id => { cantidades[id] = 0; });

let notasProductosCajero = {};

let convenioActivo = null;



let categoriaActual = 'todos';



function escapeHtml(text) {

    const div = document.createElement('div');

    div.textContent = text || '';

    return div.innerHTML;

}



// Modales de Notas para Cajero

function abrirNotaCajeroModal(id, nombre) {

    document.getElementById('notaCajeroProductoId').value = id;

    document.getElementById('modalNotaCajeroTitulo').innerHTML = `<i class="bi bi-pencil-square text-warning me-2"></i>Nota para: ${escapeHtml(nombre)}`;

    const notaActual = notasProductosCajero[id] || '';

    document.getElementById('notaCajeroTextoInput').value = notaActual;



    const btnQuitar = document.getElementById('btnQuitarNotaCajero');

    if (btnQuitar) {

        btnQuitar.style.display = notaActual ? 'inline-block' : 'none';

    }



    const modalEl = document.getElementById('modalNotaCajero');

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

    modal.show();



    setTimeout(() => {

        const input = document.getElementById('notaCajeroTextoInput');

        if (input) {

            input.focus();

            input.select();

        }

    }, 350);

}



function quitarNotaCajero() {

    document.getElementById('notaCajeroTextoInput').value = '';

    guardarNotaCajero();

}



function guardarNotaCajero() {

    const id = document.getElementById('notaCajeroProductoId').value;

    const nota = document.getElementById('notaCajeroTextoInput').value.trim();

    notasProductosCajero[id] = nota;



    if (nota && (!cantidades[id] || cantidades[id] === 0)) {

        cambiarCantidad(id, 1);

    }



    actualizarBotonNotaCajero(id, nota);

    actualizarResumen();



    const modalEl = document.getElementById('modalNotaCajero');

    const modal = bootstrap.Modal.getInstance(modalEl);

    if (modal) modal.hide();

}



function actualizarBotonNotaCajero(id, nota) {

    const btn = document.getElementById(`btnNotaCajero_${id}`);

    const textSpan = document.getElementById(`btnNotaCajeroText_${id}`);

    if (btn && textSpan) {

        if (nota) {

            btn.classList.add('tiene-nota');

            const preview = nota.length > 14 ? nota.substring(0, 12) + '...' : nota;

            textSpan.innerHTML = `<i class="bi bi-check2 me-1"></i>${escapeHtml(preview)}`;

            btn.title = `Nota activa: ${nota}`;

        } else {

            btn.classList.remove('tiene-nota');

            textSpan.innerText = 'Nota';

            btn.title = 'Agregar nota o instrucción especial';

        }

    }

}



// Modificar cantidad con botones (+) y (-)

function cambiarCantidad(id, delta) {

    cantidades[id] = Math.max(0, (cantidades[id] || 0) + delta);

    const qtyElement = document.getElementById('qty-' + id);

    if (qtyElement) {

        qtyElement.innerText = cantidades[id];

    }

    actualizarResumen();

}



// Cálculo oficial de redondeo en efectivo conforme a Ley N° 20.956 (con excepción oficial de monedas físicas $1/$5)

function calcularRedondeoChile(monto, metodo, tienePromoMoneda = false) {

    const m = Math.round(Number(monto) || 0);

    if (metodo !== 'EFECTIVO' || m === 0 || tienePromoMoneda) return { final: m, ajuste: 0 };

    const resto = m % 10;

    if (resto === 0) return { final: m, ajuste: 0 };

    if (resto <= 4) return { final: m - resto, ajuste: -resto };

    return { final: m + (10 - resto), ajuste: 10 - resto };

}



function formatearMoneda(valor) {

    return '$' + Number(valor || 0).toLocaleString('es-CL');

}



function calcularSubtotalItemJS(prod, qty) {

    const base = Number(prod.precio_base || prod.precio || 0);

    let subtotal = 0;

    let promoTexto = '';

    let ahorro = 0;



    if (prod.tipo_oferta === '3X2') {

        const g3 = Math.floor(qty / 3);

        const r3 = qty % 3;

        subtotal = (g3 * 2 + r3) * base;

        ahorro = (qty * base) - subtotal;

        if (g3 > 0) promoTexto = `Promo 3x2 (${g3} gratis)`;

    } else if (prod.tipo_oferta === '2X1') {

        const g2 = Math.floor(qty / 2);

        const r2 = qty % 2;

        subtotal = (g2 + r2) * base;

        ahorro = (qty * base) - subtotal;

        if (g2 > 0) promoTexto = `Promo 2x1 (${g2} gratis)`;

    } else if (prod.tipo_oferta === 'SEGUNDA_1') {
        const p2 = Number(prod.precio_oferta !== null && prod.precio_oferta !== undefined ? prod.precio_oferta : 1);
        const pares = Math.floor(qty / 2);
        const resto = qty % 2;
        const lim = Number(prod.limite_oferta_por_ticket || 0);
        let paresPromo = pares;
        let paresNormal = 0;
        if (lim > 0 && pares > lim) {
            paresPromo = lim;
            paresNormal = pares - lim;
        }
        subtotal = (paresPromo * (base + p2)) + (paresNormal * 2 * base) + (resto * base);
        ahorro = (qty * base) - subtotal;
        if (paresPromo > 0) {
            promoTexto = `Promo 2da a $${p2}` + (lim > 0 ? ` (máx ${lim})` : '');
        }

    } else if (prod.tipo_oferta === 'PRECIO_FIJO' && prod.precio_oferta) {

        subtotal = qty * Number(prod.precio_oferta);

        ahorro = (qty * base) - subtotal;

        promoTexto = `Precio Rebajado`;

    } else if (prod.tipo_oferta === 'DESCUENTO_PCT' && prod.descuento_pct > 0) {
        subtotal = qty * Number(prod.precio);
        ahorro = Math.max(0, (qty * base) - subtotal);
        promoTexto = `${Math.round(prod.descuento_pct)}% Dcto.`;

    } else if (prod.tipo_oferta === 'SEGUNDA_PCT') {
        const pct = Number(prod.descuento_pct || 50);
        const p2 = Math.round(base * (1 - (pct / 100)));
        const pares = Math.floor(qty / 2);
        const resto = qty % 2;
        const lim = Number(prod.limite_oferta_por_ticket || 0);
        let paresPromo = pares;
        let paresNormal = 0;
        if (lim > 0 && pares > lim) {
            paresPromo = lim;
            paresNormal = pares - lim;
        }
        subtotal = (paresPromo * (base + p2)) + (paresNormal * 2 * base) + (resto * base);
        ahorro = Math.max(0, (qty * base) - subtotal);
        if (paresPromo > 0) {
            promoTexto = `Promo 2da al ${Math.round(pct)}%` + (lim > 0 ? ` (máx ${lim})` : '');
        }

    } else if (prod.tipo_oferta === 'LLEVA_2_POR') {
        const packPrecio = Number(prod.precio_oferta || Math.round(base * 1.5));
        const pares = Math.floor(qty / 2);
        const resto = qty % 2;
        const lim = Number(prod.limite_oferta_por_ticket || 0);
        let paresPromo = pares;
        let paresNormal = 0;
        if (lim > 0 && pares > lim) {
            paresPromo = lim;
            paresNormal = pares - lim;
        }
        subtotal = (paresPromo * packPrecio) + (paresNormal * 2 * base) + (resto * base);
        ahorro = Math.max(0, (qty * base) - subtotal);
        if (paresPromo > 0) {
            promoTexto = `Pack 2 por $${packPrecio.toLocaleString('es-CL')}` + (lim > 0 ? ` (máx ${lim})` : '');
        }

    } else if (prod.tipo_oferta === 'CANTIDAD_MINIMA') {
        const minCant = Number(prod.cantidad_minima_oferta || 2);
        const precioUnit = Number(prod.precio_oferta || base);
        if (qty >= minCant) {
            subtotal = qty * precioUnit;
            ahorro = Math.max(0, (qty * base) - subtotal);
            promoTexto = `Precio x Vol (${qty} un. a $${precioUnit.toLocaleString('es-CL')})`;
        } else {
            subtotal = qty * base;
            ahorro = 0;
            promoTexto = `(Mín. ${minCant} un. para $${precioUnit.toLocaleString('es-CL')})`;
        }

    } else {

        subtotal = qty * Number(prod.precio);

    }

    return { subtotal, promoTexto, ahorro };

}



// Actualizar panel lateral en vivo

function actualizarResumen() {

    let total = 0;

    let totalItems = 0;

    const lista = document.getElementById('listaItemsPedido');

    lista.innerHTML = '';



    let tieneItems = false;



    for (const [id, qty] of Object.entries(cantidades)) {

        if (qty > 0 && productos[id]) {

            tieneItems = true;

            totalItems += qty;

            const prod = productos[id];

            const calc = calcularSubtotalItemJS(prod, qty);

            const subtotal = calc.subtotal;

            total += subtotal;



            const notaProd = notasProductosCajero[id] || '';

            const row = document.createElement('div');

            row.className = 'order-item-row d-flex justify-content-between align-items-center';

            row.innerHTML = `

                <div style="max-width: 68%;">

                    <div class="fw-bold text-dark" style="font-size: 0.9rem;">${escapeHtml(prod.nombre)}</div>

                    ${calc.promoTexto ? `

                        <div class="badge bg-danger text-white mb-1" style="font-size: 0.72rem;">

                            <i class="bi bi-fire me-1"></i>${escapeHtml(calc.promoTexto)} (Ahorro: ${formatearMoneda(calc.ahorro)})

                        </div>

                    ` : ''}

                    ${notaProd ? `

                        <div class="order-item-nota">

                            <strong class="text-danger">* NOTA:</strong> ${escapeHtml(notaProd)}

                        </div>

                    ` : ''}

                    <small class="text-muted">${qty} x ${formatearMoneda(prod.precio)}</small>

                </div>

                <div class="text-end">

                    <span class="fw-bold text-danger d-block">${formatearMoneda(subtotal)}</span>

                    <div>

                        <button type="button" class="btn btn-sm btn-link text-muted p-0 ms-2" onclick="cambiarCantidad(${id}, -1)" title="Restar">

                            <i class="bi bi-dash-circle fs-5"></i>

                        </button>

                        <button type="button" class="btn btn-sm btn-link text-warning p-0 ms-1" onclick="cambiarCantidad(${id}, 1)" title="Sumar">

                            <i class="bi bi-plus-circle fs-5"></i>

                        </button>

                    </div>

                </div>

            `;

            lista.appendChild(row);

        }

    }



    if (!tieneItems) {

        lista.innerHTML = `

            <div class="text-center text-muted py-4" id="emptyCartMessage">

                <i class="bi bi-cart-x fs-1 text-secondary opacity-50"></i>

                <p class="mt-2 mb-0 small">El pedido está vacío.</p>

                <span class="text-muted" style="font-size: 0.75rem;">Agrega alimentos o bebidas usando los botones (+).</span>

            </div>

        `;

    }



    document.getElementById('subtotalDisplay').innerText = formatearMoneda(total);



    // Cálculo de Descuento Huésped / Cabaña QR (Tarea 7)

    let montoBonificado = 0;

    const filaDesc = document.getElementById('filaDescuentoConvenio');

    const montoDescSpan = document.getElementById('montoDescuentoConvenio');



    if (convenioActivo && total > 0) {

        if (convenioActivo.tipo_beneficio === 'DESAYUNO_INCLUIDO') {

            montoBonificado = total;

        } else if (convenioActivo.tipo_beneficio === 'DESCUENTO_PORCENTAJE') {

            montoBonificado = Math.round(total * (convenioActivo.valor_descuento / 100));

        } else if (convenioActivo.tipo_beneficio === 'DESCUENTO_MONTO') {

            montoBonificado = Math.min(total, Math.round(convenioActivo.valor_descuento));

        }

        if (filaDesc && montoDescSpan) {

            filaDesc.classList.remove('d-none');

            filaDesc.classList.add('d-flex');

            montoDescSpan.innerText = `-${formatearMoneda(montoBonificado)}`;

        }

    } else if (filaDesc) {

        filaDesc.classList.add('d-none');

        filaDesc.classList.remove('d-flex');

    }



    const modalidadActiva = document.querySelector('input[name="pos_modalidad"]:checked')?.value || 'VENTA_RAPIDA';

    const modoCobroMesa = modalidadActiva === 'MESA'

        ? (document.querySelector('input[name="pos_modo_cuenta"]:checked')?.value || 'PAGADA')

        : 'PAGADA';



    const bloqueMetodo = document.getElementById('bloqueMetodoPagoPOS');

    const btnCobro = document.getElementById('btnProcesarCobroPOS');

    if (modoCobroMesa === 'ABIERTA') {

        if (bloqueMetodo) bloqueMetodo.classList.add('d-none');

        if (btnCobro && !btnCobro.disabled) {

            btnCobro.innerHTML = '<i class="bi bi-send-check-fill me-2"></i>Enviar Pedido a Salón y Cocina/Barra';

        }

    } else {

        if (bloqueMetodo) bloqueMetodo.classList.remove('d-none');

        if (btnCobro && !btnCobro.disabled) {

            btnCobro.innerHTML = '<i class="bi bi-cash-coin me-2"></i>Cobrar y Enviar a Cocina/Barra';

        }

    }



    const metodoSeleccionado = modoCobroMesa === 'ABIERTA'
        ? 'DEBITO'
        : (document.querySelector('input[name="pos_metodo_pago"]:checked')?.value || 'EFECTIVO');

    // Descuento reactivo por medio de pago o convenio tarjeta
    let descMedioPago = 0;
    let ofertaMedioPagoAplicada = null;
    const baseParaDesc = Math.max(0, total - montoBonificado);
    if (baseParaDesc > 0 && Array.isArray(ofertasPos)) {
        for (const op of ofertasPos) {
            if (op.medio_pago_requerido === 'TODOS' || op.medio_pago_requerido === metodoSeleccionado) {
                if (op.monto_minimo_compra > 0 && baseParaDesc < op.monto_minimo_compra) {
                    continue;
                }
                let candDesc = Math.round(baseParaDesc * (op.descuento_porcentaje / 100));
                if (op.tope_descuento_clp > 0 && candDesc > op.tope_descuento_clp) {
                    candDesc = op.tope_descuento_clp;
                }
                if (candDesc > descMedioPago) {
                    descMedioPago = candDesc;
                    ofertaMedioPagoAplicada = op;
                }
            }
        }
    }

    const filaDescTarjeta = document.getElementById('filaDescuentoTarjeta');
    const labelDescTarjeta = document.getElementById('labelDescuentoTarjeta');
    const montoDescTarjeta = document.getElementById('montoDescuentoTarjeta');

    if (descMedioPago > 0 && ofertaMedioPagoAplicada) {
        if (filaDescTarjeta && montoDescTarjeta) {
            filaDescTarjeta.classList.remove('d-none');
            filaDescTarjeta.classList.add('d-flex');
            if (labelDescTarjeta) {
                const nombreCorto = ofertaMedioPagoAplicada.banco_convenio || ofertaMedioPagoAplicada.nombre || 'Promo';
                labelDescTarjeta.innerText = `Promo ${nombreCorto} (${Math.round(ofertaMedioPagoAplicada.descuento_porcentaje)}%):`;
            }
            montoDescTarjeta.innerText = `-${formatearMoneda(descMedioPago)}`;
        }
    } else if (filaDescTarjeta) {
        filaDescTarjeta.classList.add('d-none');
        filaDescTarjeta.classList.remove('d-flex');
    }

    const totalFinalPagar = Math.max(0, total - montoBonificado - descMedioPago);



    // Detección de promo con monedas físicas de $1 o $5 pesos

    const tienePromoMoneda = pedidoItems.some(it => {

        const p = catalogoProductos.find(x => x.id === it.id);

        return p && (p.tipo_oferta === 'SEGUNDA_1' || Number(p.precio_oferta) === 1 || Number(p.precio_oferta) === 5);

    });



    const resRedondeo = calcularRedondeoChile(totalFinalPagar, metodoSeleccionado, tienePromoMoneda);

    const boxRedondeo = document.getElementById('boxRedondeoPOS');

    const txtRedondeo = document.getElementById('txtRedondeoPOS');



    document.getElementById('totalActualDisplay').innerText = formatearMoneda(resRedondeo.final);



    if (boxRedondeo && txtRedondeo) {

        if (tienePromoMoneda && metodoSeleccionado === 'EFECTIVO' && total > 0) {

            boxRedondeo.classList.remove('d-none');

            txtRedondeo.innerHTML = `<i class="bi bi-coin text-warning me-1"></i> <strong>Promo Moneda Física:</strong> Cobro exacto sin redondeo. Recibir moneda física de $1 o $5 en caja.`;

        } else if (modoCobroMesa === 'PAGADA' && metodoSeleccionado === 'EFECTIVO' && total > 0 && resRedondeo.ajuste !== 0) {

            boxRedondeo.classList.remove('d-none');

            txtRedondeo.innerText = `Ajuste Ley 20.956: ${resRedondeo.ajuste > 0 ? '+' : ''}$${resRedondeo.ajuste} CLP (Efectivo)`;

        } else {

            boxRedondeo.classList.add('d-none');

        }

    }



    document.getElementById('itemCountBadge').innerText = totalItems + (totalItems === 1 ? ' ítem' : ' ítems');



    // Actualizar barra flotante para tabletas y smartphones

    const mobTotal = document.getElementById('mobileComandaTotal');

    const mobLabel = document.getElementById('mobileComandaMesa');

    const selectMesa = document.getElementById('pos_mesa_id');

    const textoUbicacion = (modalidadActiva === 'MESA' && selectMesa && selectMesa.selectedIndex > 0)

        ? selectMesa.options[selectMesa.selectedIndex].text.split('(')[0].trim()

        : 'Mostrador';

    if (mobTotal) mobTotal.innerText = formatearMoneda(resRedondeo.final);

    if (mobLabel) mobLabel.innerText = `${textoUbicacion} • ${totalItems} ` + (totalItems === 1 ? 'ítem' : 'ítems');

}



function scrollHaciaComanda() {

    const panel = document.querySelector('.order-summary-panel');

    if (panel) {

        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });

    }

}



// Consumo Interno del Personal / Fiado (RF10)

function abrirModalConsumoInterno() {

    let total = 0;

    let itemsCount = 0;

    let itemsHtml = '';



    for (const [id, qty] of Object.entries(cantidades)) {

        if (qty > 0 && productos[id]) {

            const prod = productos[id];

            const sub = prod.precio * qty;

            total += sub;

            itemsCount += qty;

            itemsHtml += `<div class="d-flex justify-content-between py-1 border-bottom border-light">

                <span>${qty}x ${escapeHtml(prod.nombre)}</span>

                <span class="fw-bold">${formatearMoneda(sub)}</span>

            </div>`;

        }

    }



    if (itemsCount === 0) {

        swalWarningBootstrap.fire({

            title: "Pedido vacío",

            text: "Agrega al menos un producto antes de registrar consumo interno o fiado.",

            icon: "warning",

            confirmButtonText: "Entendido"

        });

        return;

    }



    document.getElementById('consumoCantItems').innerText = `${itemsCount} ítems`;

    document.getElementById('consumoListaItems').innerHTML = itemsHtml;

    document.getElementById('consumoTotalDisplay').innerText = formatearMoneda(total);



    const modalEl = document.getElementById('modalConsumoInterno');

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

    modal.show();

}



async function confirmarConsumoInterno() {

    const empleadoId = document.getElementById('consumoEmpleadoId').value;

    const tipoConsumo = document.getElementById('consumoTipo').value;

    const observaciones = document.getElementById('consumoObservaciones').value;



    if (!empleadoId) {

        swalWarningBootstrap.fire({

            title: "Colaborador requerido",

            text: "Debes seleccionar al colaborador beneficiario del consumo interno.",

            icon: "warning",

            confirmButtonText: "Aceptar"

        });

        return;

    }



    const items = [];

    for (const [id, qty] of Object.entries(cantidades)) {

        if (qty > 0 && productos[id]) {

            const prod = productos[id];

            items.push({

                id: id,

                nombre: prod.nombre,

                cantidad: qty,

                nota: notasProductosCajero[id] || ''

            });

        }

    }



    const btnConfirmar = document.getElementById('btnConfirmarConsumoInterno');

    btnConfirmar.disabled = true;

    btnConfirmar.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Registrando...';



    try {

        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

        const formData = new FormData();

        formData.append('empleado_id', empleadoId);

        formData.append('tipo_consumo', tipoConsumo);

        formData.append('observaciones', observaciones);

        formData.append('items_json', JSON.stringify(items));

        formData.append('csrfmiddlewaretoken', csrfToken);



        const response = await fetch((posConfig.urlRegistrarConsumoInterno || '/vendedor/consumo-interno/'), {

            method: 'POST',

            body: formData,

            headers: {

                'X-Requested-With': 'XMLHttpRequest',

                'Accept': 'application/json'

            }

        });



        const data = await response.json();



        if (data.ok) {

            const modalEl = document.getElementById('modalConsumoInterno');

            const modal = bootstrap.Modal.getInstance(modalEl);

            if (modal) modal.hide();



            swalSuccessBootstrap.fire({

                title: "¡Consumo Registrado!",

                html: `<b>${data.codigo_consumo}</b> registrado exitosamente para <b>${data.empleado}</b>.<br><br>Total: <b>${formatearMoneda(data.total)}</b> cargado para deducción en nómina.<br><small class="text-muted">Separación contable estricta: No se suma a la recaudación de caja diaria.</small>`,

                icon: "success",

                confirmButtonText: "Aceptar"

            });



            limpiarPedido();

        } else {

            swalErrorBootstrap.fire({

                title: "Error al registrar",

                text: data.error || "No se pudo procesar el consumo interno.",

                icon: "error",

                confirmButtonText: "Reintentar"

            });

        }

    } catch (err) {

        console.error(err);

        swalErrorBootstrap.fire({

            title: "Error de comunicación",

            text: "Ocurrió un error al contactar al servidor. Revisa tu conexión.",

            icon: "error",

            confirmButtonText: "Cerrar"

        });

    } finally {

        btnConfirmar.disabled = false;

        btnConfirmar.innerHTML = '<i class="bi bi-check2-circle me-1"></i> Confirmar y Registrar';

    }

}



// Limpiar el pedido

function limpiarPedido() {

    for (const id in cantidades) {

        cantidades[id] = 0;

        const qtyElement = document.getElementById('qty-' + id);

        if (qtyElement) qtyElement.innerText = '0';

    }

    notasProductosCajero = {};

    document.querySelectorAll('.btn-nota-cajero').forEach(b => {

        b.classList.remove('tiene-nota');

        const span = b.querySelector('span');

        if (span) span.innerText = 'Nota';

    });

    actualizarResumen();

}



function cambiarModalidadOperativa(modalidad) {

    const selectorBox = document.getElementById('selectorMesaBox');

    const badgeTxt = document.getElementById('badgeModalidadTexto');

    if (modalidad === 'MESA') {

        if (selectorBox) selectorBox.classList.remove('d-none');

        if (badgeTxt) {

            badgeTxt.innerText = 'Consumo en Salón';

            badgeTxt.className = 'badge bg-danger-subtle text-danger border px-2 py-0';

        }

    } else {

        if (selectorBox) selectorBox.classList.add('d-none');

        const mesaSelect = document.getElementById('pos_mesa_id');

        if (mesaSelect) mesaSelect.value = '';

        const radioCobrarAhora = document.getElementById('modo_cobrar_ahora');

        if (radioCobrarAhora) radioCobrarAhora.checked = true;

        if (badgeTxt) {

            badgeTxt.innerText = 'Venta Rápida';

            badgeTxt.className = 'badge bg-secondary-subtle text-secondary border px-2 py-0';

        }

    }

    actualizarResumen();

}



// Procesar venta / pedido real contra SQLite y despachar inmediatamente a Cocina, Barra y Salón

async function procesarCobroPOS() {

    const modalidadCobro = document.querySelector('input[name="pos_modalidad"]:checked')?.value || 'VENTA_RAPIDA';

    const mesaIdCobro = document.getElementById('pos_mesa_id')?.value || '';

    const modoCuenta = modalidadCobro === 'MESA'

        ? (document.querySelector('input[name="pos_modo_cuenta"]:checked')?.value || 'PAGADA')

        : 'PAGADA';



    if (modalidadCobro === 'MESA' && !mesaIdCobro) {

        swalWarningBootstrap.fire({

            title: "Mesa Requerida (RF11.1)",

            text: "Debes elegir una mesa del salón para asignar el pedido.",

            icon: "warning",

            confirmButtonText: "Entendido"

        });

        return;

    }



    let subtotalBruto = 0;

    const itemsPayload = [];

    for (const [id, qty] of Object.entries(cantidades)) {

        if (qty > 0 && productos[id]) {

            const prod = productos[id];

            const calc = calcularSubtotalItemJS(prod, qty);

            subtotalBruto += calc.subtotal;

            itemsPayload.push({

                producto_id: Number(id),

                nombre: prod.nombre,

                cantidad: qty,

                nota: notasProductosCajero[id] || ''

            });

        }

    }



    if (itemsPayload.length === 0) {

        swalWarningBootstrap.fire({

            title: "Pedido vacío",

            text: "Agrega al menos un alimento o bebida antes de procesar el pedido.",

            icon: "warning",

            confirmButtonText: "Entendido"

        });

        return;

    }



    let montoBonificado = 0;

    if (convenioActivo && subtotalBruto > 0) {

        if (convenioActivo.tipo_beneficio === 'DESAYUNO_INCLUIDO') {

            montoBonificado = subtotalBruto;

        } else if (convenioActivo.tipo_beneficio === 'DESCUENTO_PORCENTAJE') {

            montoBonificado = Math.round(subtotalBruto * (convenioActivo.valor_descuento / 100));

        } else if (convenioActivo.tipo_beneficio === 'DESCUENTO_MONTO') {

            montoBonificado = Math.min(subtotalBruto, Math.round(convenioActivo.valor_descuento));

        }

    }



    const metodoCobro = document.querySelector('input[name="pos_metodo_pago"]:checked')?.value || 'EFECTIVO';

    const datosPedido = {
        itemsPayload,
        metodoCobro,
        modalidadCobro,
        mesaIdCobro,
        modoCuenta,
        montoBonificado,
        subtotalBruto
    };

    // Si es pago electrónico con tarjeta, simular Terminal POS Bancario Transbank/Getnet (Cortana & Inspector Legal)
    if ((metodoCobro === 'DEBITO' || metodoCobro === 'CREDITO') && modoCuenta === 'PAGADA') {
        pedidoPendientePos = datosPedido;
        const totalTexto = document.getElementById('totalActualDisplay')?.innerText || '$0';
        abrirModalPosSimulado(metodoCobro, totalTexto);
        return;
    }

    await ejecutarDespachoTicketBackend(datosPedido);
}

let pedidoPendientePos = null;

function abrirModalPosSimulado(metodoCobro, montoTexto) {
    const modalEl = document.getElementById('modalPosBancarioSimulado');
    if (!modalEl) {
        if (pedidoPendientePos) {
            ejecutarDespachoTicketBackend(pedidoPendientePos);
        }
        return;
    }
    const txtTipo = document.getElementById('posTipoTarjetaTexto');
    if (txtTipo) {
        txtTipo.innerText = metodoCobro === 'CREDITO' ? 'CRÉDITO TRANSBANK' : 'DÉBITO REDCOMPRA';
    }
    const txtMonto = document.getElementById('posMontoDisplay');
    if (txtMonto) {
        txtMonto.innerText = (montoTexto || document.getElementById('totalActualDisplay')?.innerText || '$0') + ' CLP';
    }
    const statusText = document.getElementById('posStatusText');
    if (statusText) {
        statusText.innerText = 'Esperando tarjeta del cliente (Chip o Contactless)...';
    }
    const btnSim = document.getElementById('btnSimularAcercarTarjeta');
    if (btnSim) {
        btnSim.disabled = false;
        btnSim.innerHTML = '<i class="bi bi-upc-scan me-1"></i> Simular Lectura de Tarjeta (Aprobada)';
    }
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
}

function simularTransaccionPos() {
    const statusText = document.getElementById('posStatusText');
    const btnSim = document.getElementById('btnSimularAcercarTarjeta');
    if (btnSim) {
        btnSim.disabled = true;
        btnSim.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Leyendo Chip / Contactless...';
    }
    if (statusText) statusText.innerText = 'Leyendo Chip criptográfico EMV...';

    setTimeout(() => {
        if (statusText) statusText.innerText = 'Conectando con Servidor Transbank / Switch Bancario...';
        setTimeout(() => {
            const codAuth = 'AUTH-' + Math.floor(100000 + Math.random() * 900000);
            if (statusText) {
                statusText.innerHTML = `<strong class="text-success"><i class="bi bi-check-circle-fill me-1"></i> ¡Transacción Aprobada! Aut: #${codAuth}</strong>`;
            }
            setTimeout(() => {
                completarCobroPosExitoso();
            }, 600);
        }, 600);
    }, 500);
}

async function completarCobroPosExitoso() {
    const modalEl = document.getElementById('modalPosBancarioSimulado');
    if (modalEl) {
        const instance = bootstrap.Modal.getInstance(modalEl);
        if (instance) instance.hide();
    }
    if (pedidoPendientePos) {
        const datos = { ...pedidoPendientePos };
        pedidoPendientePos = null;
        await ejecutarDespachoTicketBackend(datos);
    }
}

async function ejecutarDespachoTicketBackend(datos) {
    const { itemsPayload, metodoCobro, modalidadCobro, mesaIdCobro, modoCuenta, montoBonificado, subtotalBruto } = datos;
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    const btnCobro = document.getElementById('btnProcesarCobroPOS');
    if (btnCobro) {
        btnCobro.disabled = true;
        btnCobro.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Registrando y enviando a KDS...';
    }

    try {
        const formData = new FormData();
        formData.append('items_json', JSON.stringify(itemsPayload));
        formData.append('metodo_pago', metodoCobro);
        formData.append('modalidad', modalidadCobro);
        formData.append('mesa_id', mesaIdCobro);
        formData.append('modo_cuenta', modoCuenta);
        formData.append('monto_bonificado', String(montoBonificado));
        formData.append('csrfmiddlewaretoken', csrfToken);

        const resp = await fetch((posConfig.urlCrearTicket || window.location.pathname), {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            }
        });

        let data = {};
        try {
            data = await resp.json();
        } catch (jsonErr) {
            data = { ok: false, error: `Respuesta del servidor no válida (código HTTP ${resp.status}).` };
        }

        if (!resp.ok || !data.ok) {
            swalErrorBootstrap.fire({
                title: "No se pudo emitir la comanda",
                text: data.error || "Verifica que tu caja esté habilitada e intenta nuevamente.",
                icon: "error",
                confirmButtonText: "Entendido"
            });
            return;
        }

        // Registrar beneficio QR de cabaña si aplica
        if (convenioActivo && montoBonificado > 0) {
            const qrData = new FormData();
            qrData.append('codigo', convenioActivo.codigo);
            qrData.append('monto_original', subtotalBruto);
            qrData.append('monto_bonificado', montoBonificado);
            qrData.append('monto_pagado', Math.max(0, subtotalBruto - montoBonificado));
            qrData.append('csrfmiddlewaretoken', csrfToken);
            fetch('/api/convenios/aplicar/', { method: 'POST', body: qrData }).catch(e => console.error(e));
        }

        document.getElementById('modalTicketId').innerText = '#' + data.codigo_comanda;
        const elMetodoTxt = document.getElementById('modalMetodoPagoTexto');
        if (elMetodoTxt) {
            elMetodoTxt.innerText = data.modo_cuenta === 'ABIERTA' ? 'Pago al Final en Salón' : metodoCobro;
        }
        document.getElementById('modalTotalCobrado').innerText = formatearMoneda(data.total);

        const ticketsEmitidosStr = (data.tickets && data.tickets.length > 0)
            ? `<div class="mt-1 small text-dark">Tickets emitidos: <strong>${escapeHtml(data.tickets.join(' • '))}</strong></div>`
            : '';

        document.getElementById('modalDestinoTexto').innerHTML = `
            Comanda <strong>#${escapeHtml(data.codigo_comanda)}</strong> (${escapeHtml(data.ubicacion || 'Mostrador')}) enviada en tiempo real a <strong>${escapeHtml(data.destino || 'Producción')}</strong>.
            ${ticketsEmitidosStr}
        `;

        const comandaBadge = document.getElementById('comandaBadge');
        if (comandaBadge && data.pedido_id) {
            comandaBadge.innerText = '#COM-' + String(Number(data.pedido_id) + 1).padStart(4, '0');
        }

        limpiarPedido();
        const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalCobro'));
        modal.show();

    } catch (err) {
        console.error(err);
        swalErrorBootstrap.fire({
            title: "Error de conexión",
            text: "No fue posible conectar con el servidor central. Intenta nuevamente.",
            icon: "error",
            confirmButtonText: "Cerrar"
        });
    } finally {
        if (btnCobro) {
            btnCobro.disabled = false;
            btnCobro.innerHTML = '<i class="bi bi-cash-coin me-2"></i>Cobrar y Enviar a Cocina/Barra';
        }
    }

        actualizarResumen();

    }

}



function simularCobro() {

    return procesarCobroPOS();

}



// Filtrado por categoría

function filtrarCategoria(cat, element) {

    categoriaActual = cat;

    document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));

    if (element) element.classList.add('active');

    aplicarFiltros();

}



function filtrarProductos() {

    aplicarFiltros();

}



function limpiarFiltroTexto() {

    document.getElementById('filtroTexto').value = '';

    aplicarFiltros();

}



function aplicarFiltros() {

    const texto = document.getElementById('filtroTexto').value.toLowerCase().trim();

    const items = document.querySelectorAll('.item-producto');

    let visibles = 0;



    items.forEach(item => {

        const cat = item.getAttribute('data-categoria');

        const nombre = item.getAttribute('data-nombre').toLowerCase();



        const coincideCategoria = (categoriaActual === 'todos' || cat === categoriaActual);

        const coincideTexto = (texto === '' || nombre.includes(texto));



        if (coincideCategoria && coincideTexto) {

            item.classList.remove('d-none');

            visibles++;

        } else {

            item.classList.add('d-none');

        }

    });



    const sinResultados = document.getElementById('sinResultados');

    if (visibles === 0) {

        sinResultados.classList.remove('d-none');

    } else {

        sinResultados.classList.add('d-none');

    }

}



document.addEventListener('DOMContentLoaded', () => {

    const inputNota = document.getElementById('notaCajeroTextoInput');

    if (inputNota) {

        inputNota.addEventListener('keydown', (e) => {

            if (e.key === 'Enter' && !e.shiftKey) {

                e.preventDefault();

                guardarNotaCajero();

            }

        });

    }



    // Preseleccionar mesa si el Cajero ingresó desde el panel de Mesas en Salón (?mesa_id=...)

    const mesaPreId = String(posConfig.mesaPreseleccionadaId || '');

    if (mesaPreId) {

        const radioMesa = document.getElementById('modalidad_mesa');

        const selectMesa = document.getElementById('pos_mesa_id');

        if (radioMesa && selectMesa) {

            radioMesa.checked = true;

            cambiarModalidadOperativa('MESA');

            selectMesa.value = mesaPreId;

            actualizarResumen();

        }

    } else {

        actualizarResumen();

    }



    // Configuración universal para inputs de monto: limpiar 0 en focus y evitar ceros iniciales

    document.querySelectorAll('input[type="number"], .input-monto-limpio').forEach(input => {

        input.addEventListener('focus', function() {

            if (this.value === '0' || this.value === '') {

                this.value = '';

            } else {

                this.select();

            }

        });

        input.addEventListener('click', function() {

            if (this.value === '0') {

                this.value = '';

            } else {

                this.select();

            }

        });

        input.addEventListener('keydown', function(e) {

            if (this.value === '0' && e.key >= '0' && e.key <= '9') {

                this.value = '';

            }

        });

        input.addEventListener('input', function() {

            if (this.value && this.value.length > 1 && this.value.startsWith('0') && !this.value.includes('.')) {

                this.value = this.value.replace(/^0+(?=\d)/, '');

            }

        });

    });

});



// Lógica de Validación QR Huéspedes y Cabañas (Tarea 7)

document.getElementById('btnVerificarQR')?.addEventListener('click', verificarCodigoQR);

document.getElementById('inputCodigoConvenio')?.addEventListener('keypress', function(e) {

    if (e.key === 'Enter') {

        e.preventDefault();

        verificarCodigoQR();

    }

});



async function verificarCodigoQR() {

    const input = document.getElementById('inputCodigoConvenio');

    const codigo = input.value.trim();

    const badge = document.getElementById('badgeConvenioEstado');

    const infoBox = document.getElementById('infoConvenioBox');



    if (!codigo) {

        alert('Por favor ingresa o escanea un código QR o de barra.');

        return;

    }



    try {

        badge.className = 'badge bg-warning text-dark';

        badge.innerText = 'Consultando...';



        const resp = await fetch(`/api/convenios/verificar/?codigo=${encodeURIComponent(codigo)}`);

        const data = await resp.json();



        infoBox.classList.remove('d-none');



        if (data.ok && data.puede_consumir) {

            convenioActivo = data;

            badge.className = 'badge bg-success';

            badge.innerText = 'Válido y Aplicado';

            infoBox.className = 'mt-2 small p-2 rounded-2 border bg-success-subtle text-success border-success-subtle';

            infoBox.innerHTML = `

                <div class="fw-bold"><i class="bi bi-check-circle-fill me-1"></i>${data.cabana} • ${data.titular}</div>

                <div><strong>Beneficio:</strong> ${data.tipo_display}</div>

                <div class="text-muted" style="font-size: 0.75rem;">Consumos hoy: ${data.consumos_hoy} de ${data.limite_diario} permitidos.</div>

            `;

            actualizarResumen();

        } else {

            convenioActivo = null;

            badge.className = 'badge bg-danger';

            badge.innerText = 'No Aplicable';

            infoBox.className = 'mt-2 small p-2 rounded-2 border bg-danger-subtle text-danger border-danger-subtle';

            infoBox.innerHTML = `<i class="bi bi-x-circle-fill me-1"></i>${data.mensaje || 'Código no válido o límite diario alcanzado.'}`;

            actualizarResumen();

        }

    } catch (err) {

        badge.className = 'badge bg-danger';

        badge.innerText = 'Error';

        infoBox.classList.remove('d-none');

        infoBox.className = 'mt-2 small p-2 rounded-2 border bg-danger-subtle text-danger border-danger-subtle';

        infoBox.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-1"></i>Error de conexión al verificar pase.';

    }

}



// Monitoreo de Crédito / Fiado del Colaborador en Tiempo Real
document.addEventListener('DOMContentLoaded', () => {
    const selectColab = document.getElementById('consumoEmpleadoId');
    if (selectColab) {
        selectColab.addEventListener('change', function() {
            const opt = this.options[this.selectedIndex];
            const box = document.getElementById('boxInfoCreditoColaborador');
            const txtSaldo = document.getElementById('txtSaldoColaborador');
            const badge = document.getElementById('badgeEstadoCredito');
            if (!box || !opt || !opt.value) {
                if (box) box.classList.add('d-none');
                return;
            }
            const saldo = Number(opt.dataset.saldo || 0);
            box.classList.remove('d-none');
            txtSaldo.innerText = '$' + saldo.toLocaleString('es-CL') + ' CLP';
            if (saldo >= 60000) {
                badge.className = 'badge bg-danger';
                badge.innerText = '⚠️ Alto Riesgo (Cercano a Límite $100k)';
            } else if (saldo >= 30000) {
                badge.className = 'badge bg-warning text-dark';
                badge.innerText = 'Moderado';
            } else if (saldo > 0) {
                badge.className = 'badge bg-info-subtle text-info-emphasis';
                badge.innerText = 'Bajo';
            } else {
                badge.className = 'badge bg-success-subtle text-success';
                badge.innerText = 'Al Día ($0)';
            }
        });
    }
});


// ==============================================================================
// Cortana & Atlas: Emulador de Balanza Digital Serial/USB (Buffet al Peso)
// ==============================================================================
const BalanzaDigital = (() => {
    let pesoBrutoGramos = 0;
    let taraGramos = 0;
    let productoSeleccionadoId = null;
    let modalBalanzaInstance = null;

    function init() {
        const modalEl = document.getElementById('modalBalanzaDigital');
        if (!modalEl) return;

        // Poblar selector con productos
        const selectEl = document.getElementById('selectProductoBalanza');
        if (selectEl && Object.keys(productos).length > 0) {
            selectEl.innerHTML = '';
            Object.values(productos).forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = `${p.nombre} - $${p.precio_base.toLocaleString('es-CL')} CLP`;
                selectEl.appendChild(opt);
            });
            selectEl.addEventListener('change', (e) => {
                productoSeleccionadoId = parseInt(e.target.value);
                actualizarDisplay();
            });
            productoSeleccionadoId = parseInt(selectEl.value);
        }

        // Botones de peso rápido
        document.querySelectorAll('.btn-peso-rapido').forEach(btn => {
            btn.addEventListener('click', () => {
                const delta = parseInt(btn.getAttribute('data-peso-g') || '0');
                pesoBrutoGramos = Math.max(0, pesoBrutoGramos + delta);
                document.getElementById('sliderPesoBalanza').value = pesoBrutoGramos;
                actualizarDisplay();
            });
        });

        // Slider manual fino
        const slider = document.getElementById('sliderPesoBalanza');
        if (slider) {
            slider.addEventListener('input', (e) => {
                pesoBrutoGramos = parseInt(e.target.value);
                actualizarDisplay();
            });
        }

        // Tarar (descontar plato actual)
        document.getElementById('btnBalanzaTarar')?.addEventListener('click', () => {
            taraGramos = pesoBrutoGramos;
            actualizarDisplay();
        });

        // Poner en cero
        document.getElementById('btnBalanzaCero')?.addEventListener('click', () => {
            pesoBrutoGramos = 0;
            taraGramos = 0;
            if (slider) slider.value = 0;
            actualizarDisplay();
        });

        // Transferir al ticket
        document.getElementById('btnBalanzaTransferir')?.addEventListener('click', transferirAlTicket);
    }

    function actualizarDisplay() {
        const pesoNetoGramos = Math.max(0, pesoBrutoGramos - taraGramos);
        const pesoNetoKg = pesoNetoGramos / 1000.0;
        const brutoKg = pesoBrutoGramos / 1000.0;
        const taraKg = taraGramos / 1000.0;

        const prod = productos[productoSeleccionadoId];
        const precioUnit = prod ? prod.precio_base : 0;
        // Asumiendo que el precio base es por kg si es al peso, o calculando proporción
        const total = Math.round(pesoNetoKg * precioUnit);

        const elPeso = document.getElementById('balanzaDisplayPeso');
        const elBruto = document.getElementById('balanzaDisplayBruto');
        const elTara = document.getElementById('balanzaDisplayTara');
        const elPrecioKg = document.getElementById('balanzaDisplayPrecioKg');
        const elTotal = document.getElementById('balanzaDisplayTotal');
        const elLabelGramos = document.getElementById('labelGramosSlider');

        if (elPeso) elPeso.textContent = pesoNetoKg.toFixed(3);
        if (elBruto) elBruto.textContent = `${brutoKg.toFixed(3)} kg`;
        if (elTara) elTara.textContent = `${taraKg.toFixed(3)} kg`;
        if (elPrecioKg) elPrecioKg.textContent = `$${precioUnit.toLocaleString('es-CL')} / kg`;
        if (elTotal) elTotal.textContent = `$${total.toLocaleString('es-CL')} CLP`;
        if (elLabelGramos) elLabelGramos.textContent = `${pesoBrutoGramos} gramos`;
    }

    function transferirAlTicket() {
        const pesoNetoGramos = Math.max(0, pesoBrutoGramos - taraGramos);
        if (pesoNetoGramos <= 0) {
            if (typeof Swal !== 'undefined') {
                Swal.fire('Balanza en Cero', 'Debes colocar peso en la balanza antes de transferir.', 'warning');
            } else {
                alert('Debes colocar peso en la balanza antes de transferir.');
            }
            return;
        }

        if (!productoSeleccionadoId || !productos[productoSeleccionadoId]) {
            return;
        }

        // Agregar 1 unidad del ítem con la nota de balanza
        cambiarCantidad(productoSeleccionadoId, 1);
        const notaBalanza = `Balanza: ${pesoNetoGramos}g neto (Tara: ${taraGramos}g)`;
        notasProductosCajero[productoSeleccionadoId] = notaBalanza;
        actualizarBotonNotaCajero(productoSeleccionadoId, notaBalanza);
        actualizarResumen();

        const modalEl = document.getElementById('modalBalanzaDigital');
        if (modalEl) {
            const inst = bootstrap.Modal.getInstance(modalEl);
            if (inst) inst.hide();
        }

        if (typeof Swal !== 'undefined') {
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'success',
                title: `Peso registrado: ${pesoNetoGramos}g`,
                showConfirmButton: false,
                timer: 2000
            });
        }
    }

    function abrirModal() {
        const modalEl = document.getElementById('modalBalanzaDigital');
        if (!modalEl) return;
        if (!modalBalanzaInstance) {
            modalBalanzaInstance = new bootstrap.Modal(modalEl);
        }
        actualizarDisplay();
        modalBalanzaInstance.show();
    }

    return { init, abrirModal };
})();

window.abrirModalBalanzaDigital = () => BalanzaDigital.abrirModal();

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', BalanzaDigital.init);
} else {
    BalanzaDigital.init();
}
