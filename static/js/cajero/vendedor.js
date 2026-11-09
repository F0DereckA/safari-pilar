const vendedorConfig = (() => {
    const el = document.getElementById('vendedorConfigData');
    if (!el) return {};
    try { return JSON.parse(el.textContent || '{}'); } catch (e) { return {}; }
})();

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.toast-container .toast').forEach(function(el) {
        const toast = new bootstrap.Toast(el, { delay: 4000 });
        toast.show();
        setTimeout(function() {
            try { toast.hide(); } catch(e){}
        }, 4000);
    });
});

function abrirModalAnular(ventaId, total) {
    const form = document.getElementById('formAnularVenta');
    form.action = '/ventas/' + ventaId + '/anular/';
    document.getElementById('lblVentaId').textContent = 'VEN-' + ventaId;
    document.getElementById('lblVentaTotal').textContent = '$' + Number(total).toLocaleString('es-CL') + ' CLP';
    const modalEl = document.getElementById('modalAnularVenta');
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
}

function obtenerCsrfTokenVendedor() {
    return document.getElementById('csrfTokenVendedorGlobal')?.value
        || document.querySelector('[name=csrfmiddlewaretoken]')?.value
        || '';
}

// Evitar ceros iniciales al digitar rápido montos en Caja (ej: escribir 123123 directo sin 0123123)
function limpiarCerosInicialesInput(input) {
    if (!input) return;
    if (input.value === '0') {
        input.value = '';
        return;
    }
    const limpio = input.value.replace(/^0+(?=\d)/, '');
    if (limpio !== input.value) {
        input.value = limpio;
    }
}

function leerPedidosDesdeScript(docRef) {
    const root = docRef || document;
    const scriptEl = root.getElementById('pedidosCajeroData');
    if (!scriptEl) return [];
    try {
        return JSON.parse(scriptEl.textContent || '[]');
    } catch (e) {
        return [];
    }
}

let pedidosCajero = leerPedidosDesdeScript(document);
let estadoFiltroActual = 'activos';

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function formatearMoneda(valor) {
    return '$' + Number(valor || 0).toLocaleString('es-CL');
}

// Renderizar tarjetas de tickets reales desde la Base de Datos
function renderizarTickets() {
    const tickets = pedidosCajero || [];
    const contenedor = document.getElementById('contenedorTickets');
    if (!contenedor) return;
    const textoBusqueda = (document.getElementById('filtroTicketTexto')?.value || '').toLowerCase().trim();

    contenedor.innerHTML = '';

    // Contadores KPI reales
    let totalEnCurso = 0;
    let totalCocina = 0;
    let totalBarra = 0;
    let totalListos = 0;

    tickets.forEach(t => {
        if (t.estadoBd === 'LISTO') {
            totalListos++;
            totalEnCurso++;
        } else if (t.estadoBd === 'PENDIENTE' || t.estadoBd === 'EN_PREPARACION') {
            totalEnCurso++;
            if (t.tieneCocina) totalCocina++;
            if (t.tieneBarra) totalBarra++;
        }
    });

    const kpiTotalEl = document.getElementById('kpiTotal');
    const kpiCocinaEl = document.getElementById('kpiCocina');
    const kpiBarraEl = document.getElementById('kpiBarra');
    const kpiListosEl = document.getElementById('kpiListos');
    if (kpiTotalEl) kpiTotalEl.innerText = totalEnCurso;
    if (kpiCocinaEl) kpiCocinaEl.innerText = totalCocina;
    if (kpiBarraEl) kpiBarraEl.innerText = totalBarra;
    if (kpiListosEl) kpiListosEl.innerText = totalListos;

    let visibles = 0;

    tickets.forEach(ticket => {
        // Filtro por pestaña de estado
        let cumpleEstado = false;
        if (estadoFiltroActual === 'activos') {
            cumpleEstado = (ticket.estadoBd !== 'ENTREGADO');
        } else if (estadoFiltroActual === 'cocina') {
            cumpleEstado = (ticket.estadoBd === 'PENDIENTE' || ticket.estadoBd === 'EN_PREPARACION') && ticket.tieneCocina;
        } else if (estadoFiltroActual === 'barra') {
            cumpleEstado = (ticket.estadoBd === 'PENDIENTE' || ticket.estadoBd === 'EN_PREPARACION') && ticket.tieneBarra;
        } else if (estadoFiltroActual === 'listo') {
            cumpleEstado = (ticket.estadoBd === 'LISTO');
        } else if (estadoFiltroActual === 'entregado') {
            cumpleEstado = (ticket.estadoBd === 'ENTREGADO');
        }

        // Filtro por Texto
        let cumpleTexto = false;
        if (textoBusqueda === '') {
            cumpleTexto = true;
        } else {
            const idMatch = (ticket.id || '').toLowerCase().includes(textoBusqueda);
            const entregaMatch = (ticket.tipoEntrega || '').toLowerCase().includes(textoBusqueda);
            const itemMatch = (ticket.items || []).some(i => (i.nombre || '').toLowerCase().includes(textoBusqueda));
            const obsMatch = ticket.observacion ? ticket.observacion.toLowerCase().includes(textoBusqueda) : false;
            cumpleTexto = idMatch || entregaMatch || itemMatch || obsMatch;
        }

        if (cumpleEstado && cumpleTexto) {
            visibles++;
            const col = document.createElement('div');
            col.className = 'col-md-6 col-xl-4';

            let statusBadgeHtml = '';
            let actionBtnHtml = '';

            if (ticket.estadoBd === 'PENDIENTE') {
                if (ticket.tieneCocina) {
                    statusBadgeHtml = `<span class="badge-status status-cocina"><i class="bi bi-hourglass-split"></i> Pendiente en Cocina</span>`;
                } else {
                    statusBadgeHtml = `<span class="badge-status status-barra"><i class="bi bi-hourglass-split"></i> Pendiente en Barra</span>`;
                }
                actionBtnHtml = `
                    <button class="btn btn-sm btn-outline-success rounded-pill fw-bold" onclick="cambiarEstadoTicket(${ticket.pedido_id}, 'LISTO')">
                        <i class="bi bi-check2-circle me-1"></i> Marcar Listo
                    </button>
                `;
            } else if (ticket.estadoBd === 'EN_PREPARACION') {
                if (ticket.tieneCocina) {
                    statusBadgeHtml = `<span class="badge-status status-cocina"><i class="bi bi-fire"></i> Preparando en Cocina</span>`;
                } else {
                    statusBadgeHtml = `<span class="badge-status status-barra"><i class="bi bi-cup-hot-fill"></i> Preparando en Barra</span>`;
                }
                actionBtnHtml = `
                    <button class="btn btn-sm btn-outline-success rounded-pill fw-bold" onclick="cambiarEstadoTicket(${ticket.pedido_id}, 'LISTO')">
                        <i class="bi bi-check2-circle me-1"></i> Marcar Listo
                    </button>
                `;
            } else if (ticket.estadoBd === 'LISTO') {
                statusBadgeHtml = `<span class="badge-status status-listo"><i class="bi bi-bag-check-fill"></i> Listo para Entrega</span>`;
                actionBtnHtml = `
                    <button class="btn btn-sm btn-success rounded-pill fw-bold" onclick="cambiarEstadoTicket(${ticket.pedido_id}, 'ENTREGADO')">
                        <i class="bi bi-check-all me-1"></i> Entregar a Comensal
                    </button>
                `;
            } else {
                statusBadgeHtml = `<span class="badge-status status-entregado"><i class="bi bi-check-all"></i> Entregado</span>`;
                actionBtnHtml = `<span class="badge bg-light text-muted border px-2 py-1">Despachado</span>`;
            }

            let itemsHtml = '';
            (ticket.items || []).forEach(it => {
                let catBadge = '';
                if (it.cat === 'preparada') catBadge = '<span class="badge cat-preparada" style="font-size:0.65rem;">Preparada</span>';
                else if (it.cat === 'cocinar') catBadge = '<span class="badge cat-cocinar" style="font-size:0.65rem;">Cocinar</span>';
                else if (it.cat === 'envasada') catBadge = '<span class="badge cat-envasada" style="font-size:0.65rem;">Envasada</span>';
                else if (it.cat === 'cafeteria') catBadge = '<span class="badge cat-cafeteria" style="font-size:0.65rem;">Barra</span>';

                itemsHtml += `
                    <div class="ticket-item-line">
                        <div>
                            <strong>${it.cant}x</strong> ${escapeHtml(it.nombre)} ${catBadge}
                        </div>
                        <span class="text-muted small">${formatearMoneda(it.precio * it.cant)}</span>
                    </div>
                    ${it.nota ? `
                        <div class="ticket-item-nota">
                            <strong class="text-danger">* NOTA:</strong> ${escapeHtml(it.nota)}
                        </div>
                    ` : ''}
                `;
            });

            const badgeCuentaHtml = ticket.ventaEstado === 'ABIERTA'
                ? '<span class="badge bg-warning text-dark border ms-1" style="font-size:0.68rem;">Por cobrar en Salón</span>'
                : '<span class="badge bg-success-subtle text-success border border-success-subtle ms-1" style="font-size:0.68rem;">Pagado</span>';

            col.innerHTML = `
                <div class="ticket-card">
                    <div class="ticket-card-header">
                        <div>
                            <div class="ticket-id">
                                <i class="bi bi-receipt text-warning me-1"></i>#${escapeHtml(ticket.id)} ${badgeCuentaHtml}
                            </div>
                            <small class="text-muted fw-semibold">${escapeHtml(ticket.hora)} • <i class="bi ${ticket.esMesa ? 'bi-geo-alt-fill text-danger' : 'bi-bag-check text-secondary'}"></i> ${escapeHtml(ticket.tipoEntrega)}</small>
                        </div>
                        <div>
                            ${statusBadgeHtml}
                        </div>
                    </div>

                    <div class="ticket-card-body">
                        <div class="mb-3">
                            ${itemsHtml}
                        </div>
                        ${ticket.observacion ? `
                            <div class="p-2 rounded-2 mb-2" style="background-color: #fffbeb; border: 1px solid #fef3c7; font-size: 0.8rem; color: #92400e;">
                                <i class="bi bi-info-circle-fill me-1"></i><strong>Detalle:</strong> ${escapeHtml(ticket.observacion)}
                            </div>
                        ` : ''}
                        <div class="d-flex justify-content-between text-muted small mt-2 pt-2 border-top">
                            <span>Destino: <strong>${escapeHtml(ticket.destino)}</strong></span>
                            <span>Por: ${escapeHtml(ticket.cajero || 'Caja')}</span>
                        </div>
                    </div>

                    <div class="ticket-card-footer">
                        <div>
                            <small class="text-muted d-block" style="font-size: 0.72rem;">TOTAL COMANDADO</small>
                            <span class="ticket-total">${formatearMoneda(ticket.total)}</span>
                        </div>
                        <div>
                            ${actionBtnHtml}
                        </div>
                    </div>
                </div>
            `;
            contenedor.appendChild(col);
        }
    });

    const sinTickets = document.getElementById('sinTickets');
    if (sinTickets) {
        if (visibles === 0) {
            sinTickets.classList.remove('d-none');
        } else {
            sinTickets.classList.add('d-none');
        }
    }
}

// Cambiar estado de un pedido directamente en la Base de Datos
async function cambiarEstadoTicket(pedidoId, nuevoEstado) {
    try {
        const formData = new FormData();
        formData.append('pedido_id', pedidoId);
        formData.append('nuevo_estado', nuevoEstado);
        formData.append('csrfmiddlewaretoken', obtenerCsrfTokenVendedor());

        const resp = await fetch((vendedorConfig.urlCambiarEstadoPedido || '/pedido/estado/'), {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
        });
        const data = await resp.json();
        if (data.ok) {
            await autoActualizarVendedor(true);
            if (typeof swalToast !== 'undefined') {
                swalToast.fire({ icon: 'success', title: `Comanda #COM-${String(pedidoId).padStart(4, '0')} actualizada a ${data.estado_display}.` });
            }
        } else if (typeof swalErrorBootstrap !== 'undefined') {
            swalErrorBootstrap.fire({ title: 'No se pudo actualizar', text: data.error || 'Error al cambiar estado.', icon: 'error' });
        }
    } catch (e) {
        console.error(e);
    }
}

// Acciones rápidas de Salón desde Caja (Enviar clientes a mesa, Liberar mesa, Cobrar mesa)
async function ocuparMesaCajero(mesaId, mesaNombre) {
    try {
        const formData = new FormData();
        formData.append('accion', 'ocupar_mesa');
        formData.append('mesa_id', mesaId);
        formData.append('csrfmiddlewaretoken', obtenerCsrfTokenVendedor());

        const resp = await fetch((vendedorConfig.urlVendedor || window.location.pathname), {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
        });
        const data = await resp.json();
        if (data.ok) {
            await autoActualizarVendedor(true);
            if (typeof swalToast !== 'undefined') {
                swalToast.fire({ icon: 'success', title: data.mensaje || `${mesaNombre} asignada para atención en salón.` });
            }
        } else if (typeof swalWarningBootstrap !== 'undefined') {
            swalWarningBootstrap.fire({ title: 'No disponible', text: data.error || 'No se pudo ocupar la mesa.', icon: 'warning' });
        }
    } catch (e) {
        console.error(e);
    }
}

async function liberarMesaCajero(mesaId, mesaNombre) {
    try {
        const formData = new FormData();
        formData.append('accion', 'liberar_mesa');
        formData.append('mesa_id', mesaId);
        formData.append('csrfmiddlewaretoken', obtenerCsrfTokenVendedor());

        const resp = await fetch((vendedorConfig.urlVendedor || window.location.pathname), {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
        });
        const data = await resp.json();
        if (data.ok) {
            await autoActualizarVendedor(true);
            if (typeof swalToast !== 'undefined') {
                swalToast.fire({ icon: 'success', title: data.mensaje || `${mesaNombre} liberada.` });
            }
        } else if (typeof swalWarningBootstrap !== 'undefined') {
            swalWarningBootstrap.fire({ title: 'Atención pendiente', text: data.error || 'No se puede liberar aún.', icon: 'warning' });
        }
    } catch (e) {
        console.error(e);
    }
}

async function cobrarMesaCajero(mesaId, mesaNombre, totalAbierto) {
    const propina10 = Math.round(totalAbierto * 0.10);
    const htmlModal = `
        <div class="text-start mb-3">
            <div class="text-center py-2 mb-3 bg-light rounded-3 border">
                <span class="text-muted small d-block">TOTAL CONSUMO ACUMULADO:</span>
                <span class="text-danger fs-3 fw-bold">${formatearMoneda(totalAbierto)} CLP</span>
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold small text-dark">Método de Pago:</label>
                <select id="swalMetodoPago" class="form-select form-select-sm">
                    <option value="EFECTIVO" selected>Efectivo (aplica redondeo Ley 20.956)</option>
                    <option value="DEBITO">Tarjeta de Débito</option>
                    <option value="CREDITO">Tarjeta de Crédito</option>
                    <option value="TRANSFERENCIA">Transferencia Electrónica</option>
                </select>
            </div>
            <div class="mb-3">
                <label class="form-label fw-bold small text-dark">Monto a Cobrar / Abono Parcial (CLP):</label>
                <input type="number" id="swalMontoPago" class="form-control form-control-sm font-monospace" value="${totalAbierto}" min="1" max="${totalAbierto}">
                <small class="text-muted" style="font-size: 0.72rem;">Ingresa un monto menor para registrar un abono / división de cuenta (la mesa seguirá ocupada con el saldo).</small>
            </div>
            <div class="form-check form-switch p-2 bg-light rounded-3 border">
                <input class="form-check-input ms-0 me-2" type="checkbox" id="swalIncluirPropina">
                <label class="form-check-label fw-bold small text-dark" for="swalIncluirPropina">
                    Sugerir Propina Voluntaria 10% (+${formatearMoneda(propina10)} CLP)
                </label>
                <div class="small text-muted ps-4" style="font-size: 0.7rem;">Ley N° 20.918 Art. 64 bis • 100% voluntaria</div>
            </div>
        </div>
    `;

    const { value: formValues } = await Swal.fire({
        title: `Cobro en Salón • ${mesaNombre}`,
        html: htmlModal,
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-cash-coin me-1"></i> Procesar Cobro',
        cancelButtonText: 'Cancelar',
        customClass: {
            confirmButton: 'btn btn-success fw-bold rounded-pill px-4 mx-1',
            cancelButton: 'btn btn-outline-secondary rounded-pill px-3 mx-1'
        },
        buttonsStyling: false,
        preConfirm: () => {
            const metodo = document.getElementById('swalMetodoPago').value;
            const monto = parseFloat(document.getElementById('swalMontoPago').value) || totalAbierto;
            const propina = document.getElementById('swalIncluirPropina').checked;
            return { metodo, monto, propina };
        }
    });

    if (!formValues) return;

    try {
        const formData = new FormData();
        formData.append('accion', 'cobrar_cuenta_mesa');
        formData.append('mesa_id', mesaId);
        formData.append('metodo_pago', formValues.metodo);
        formData.append('monto_pago', formValues.monto);
        if (formValues.propina) {
            formData.append('incluir_propina', '1');
        }
        formData.append('csrfmiddlewaretoken', obtenerCsrfTokenVendedor());

        const resp = await fetch((vendedorConfig.urlVendedor || window.location.pathname), {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
        });
        const data = await resp.json();
        if (data.ok) {
            await autoActualizarVendedor(true);
            swalSuccessBootstrap.fire({
                title: '¡Mesa Cobrada y Liberada!',
                text: data.mensaje || `Cuenta de ${mesaNombre} pagada con éxito.`,
                icon: 'success'
            });
        } else {
            swalErrorBootstrap.fire({
                title: 'No se pudo cobrar',
                text: data.error || 'Error al procesar el cobro de la mesa.',
                icon: 'error'
            });
        }
    } catch (e) {
        console.error(e);
    }
}

// Filtrar por pestaña de estado
function filtrarEstado(estado, elemento) {
    estadoFiltroActual = estado;
    document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
    if (elemento) elemento.classList.add('active');
    renderizarTickets();
}

function filtrarTickets() {
    renderizarTickets();
}

function limpiarFiltroTicket() {
    const input = document.getElementById('filtroTicketTexto');
    if (input) input.value = '';
    renderizarTickets();
}

// Sincronización en tiempo real cada 1 segundo contra SQLite (Cajero <-> Mesero <-> Cocina <-> Barra)
let actualizandoVendedor = false;
let ultimaVersionDeltaCajero = null;

async function autoActualizarVendedor(forzar = false) {
    if (actualizandoVendedor) return;
    if (!forzar && (document.querySelector('.modal.show') || document.querySelector('.swal2-container'))) {
        return;
    }
    actualizandoVendedor = true;
    try {
        // 1. Paso Delta Liviano (~150 bytes)
        const deltaUrl = '/api/sincronizacion/estado/' + window.location.search;
        let debeActualizar = forzar;

        try {
            const deltaResp = await fetch(deltaUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (deltaResp.ok) {
                const delta = await deltaResp.json();
                if (delta.ok) {
                    if (!forzar && ultimaVersionDeltaCajero && ultimaVersionDeltaCajero === delta.version) {
                        actualizandoVendedor = false;
                        return; // Zero overhead: el estado no ha cambiado
                    }
                    ultimaVersionDeltaCajero = delta.version;
                    debeActualizar = true;
                }
            }
        } catch (e) {
            debeActualizar = true;
        }

        if (!debeActualizar) {
            actualizandoVendedor = false;
            return;
        }

        const resp = await fetch(window.location.href, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!resp.ok) return;
        const html = await resp.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        // Actualizar comandas activas
        pedidosCajero = leerPedidosDesdeScript(doc);
        renderizarTickets();

        // Actualizar panel en vivo de mesas del salón
        const nuevoPanelMesas = doc.getElementById('panelMesasSalonCajero');
        const actualPanelMesas = document.getElementById('panelMesasSalonCajero');
        if (nuevoPanelMesas && actualPanelMesas && nuevoPanelMesas.innerHTML.trim() !== actualPanelMesas.innerHTML.trim()) {
            actualPanelMesas.innerHTML = nuevoPanelMesas.innerHTML;
        }

        // Actualizar tabla de ventas recientes
        const nuevasVentas = doc.getElementById('seccionVentasRecientesCajero');
        const actualesVentas = document.getElementById('seccionVentasRecientesCajero');
        if (nuevasVentas && actualesVentas && nuevasVentas.innerHTML.trim() !== actualesVentas.innerHTML.trim()) {
            actualesVentas.innerHTML = nuevasVentas.innerHTML;
        }
    } catch (err) {
        // Silencioso ante microcortes de red
    } finally {
        actualizandoVendedor = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    renderizarTickets();
    if (vendedorConfig.cajaActiva) {
        calcularArqueoCaja();
    }

    // Enfocar automáticamente el campo de monto al abrir modales de Jornada / Caja (ingreso directo sin borrar 0)
    ['modalAbrirJornada', 'modalAbrirCaja'].forEach(modalId => {
        const modalEl = document.getElementById(modalId);
        if (modalEl) {
            modalEl.addEventListener('show.bs.modal', () => {
                const montoInput = modalEl.querySelector('input[name="monto_apertura"]');
                if (montoInput) {
                    montoInput.value = '';
                }
            });
            modalEl.addEventListener('shown.bs.modal', () => {
                const montoInput = modalEl.querySelector('input[name="monto_apertura"]');
                if (montoInput) {
                    montoInput.value = '';
                    montoInput.focus();
                    montoInput.select();
                }
            });
        }
    });

    // Configuración universal para inputs de monto y arqueo: limpiar 0 en focus y evitar ceros iniciales
    document.querySelectorAll('input[type="number"], .input-monto-limpio, .input-arqueo').forEach(input => {
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

    // Sincronización en tiempo real cada 1 segundo
    setInterval(() => autoActualizarVendedor(false), 1000);
});

// =========================================================================
// SUBPROCESO DE CUADRATURA Y ARQUEO DE CAJA
// =========================================================================
const ESPERADO_EFECTIVO = Number(vendedorConfig.esperadoEfectivo || 0);

function calcularArqueoCaja() {
    const inputs = document.querySelectorAll('.input-arqueo');
    let totalContado = 0;
    inputs.forEach(input => {
        const denom = parseInt(input.dataset.denominacion) || 0;
        const cant = parseInt(input.value) || 0;
        const subtotal = cant * denom;
        totalContado += subtotal;
        const subSpan = document.getElementById('sub_' + input.id);
        if (subSpan) {
            subSpan.innerText = '$' + subtotal.toLocaleString('es-CL');
        }
    });

    const displayContado = document.getElementById('displayTotalContado');
    if (displayContado) {
        displayContado.innerText = '$' + totalContado.toLocaleString('es-CL');
    }

    const diferencia = totalContado - ESPERADO_EFECTIVO;
    const badgeResultado = document.getElementById('badgeResultadoCuadre');
    const detalleDiff = document.getElementById('detalleDiferenciaCuadre');

    if (badgeResultado && detalleDiff) {
        if (diferencia === 0) {
            badgeResultado.className = 'badge bg-success fs-6 px-3 py-2';
            badgeResultado.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Cuadratura Exacta';
            detalleDiff.className = 'small fw-bold text-success mt-1';
            detalleDiff.innerText = 'Diferencia: $0 CLP (Caja Cuadrada Perfecta)';
        } else if (diferencia > 0) {
            badgeResultado.className = 'badge bg-warning text-dark fs-6 px-3 py-2';
            badgeResultado.innerHTML = '<i class="bi bi-exclamation-triangle-fill me-1"></i> Sobrante de Caja';
            detalleDiff.className = 'small fw-bold text-warning-emphasis mt-1';
            detalleDiff.innerText = `Diferencia: +$${diferencia.toLocaleString('es-CL')} CLP (Sobrante Físico)`;
        } else {
            badgeResultado.className = 'badge bg-danger fs-6 px-3 py-2';
            badgeResultado.innerHTML = '<i class="bi bi-x-circle-fill me-1"></i> Faltante de Caja';
            detalleDiff.className = 'small fw-bold text-danger mt-1';
            detalleDiff.innerText = `Diferencia: -$${Math.abs(diferencia).toLocaleString('es-CL')} CLP (Faltante Físico)`;
        }
    }
}

function confirmarCierreCaja() {
    const form = document.getElementById('formCerrarCaja');
    if (!form) return;

    const inputs = document.querySelectorAll('.input-arqueo');
    let totalContado = 0;
    inputs.forEach(input => {
        const denom = parseInt(input.dataset.denominacion) || 0;
        const cant = parseInt(input.value) || 0;
        totalContado += cant * denom;
    });
    const diferencia = totalContado - ESPERADO_EFECTIVO;

    let estadoTexto = "Cuadratura Exacta ($0)";
    let iconoModal = "question";
    if (diferencia > 0) {
        estadoTexto = `Sobrante de +$${diferencia.toLocaleString('es-CL')} CLP`;
        iconoModal = "warning";
    } else if (diferencia < 0) {
        estadoTexto = `Faltante de -$${Math.abs(diferencia).toLocaleString('es-CL')} CLP`;
        iconoModal = "warning";
    }

    swalWarningBootstrap.fire({
        title: "¿Confirmar Cierre y Arqueo de Caja?",
        html: `
            <div class="text-start small p-2 bg-light rounded-3 mb-2">
                <div><strong>Total Físico Contado:</strong> $${totalContado.toLocaleString('es-CL')} CLP</div>
                <div><strong>Total Teórico Esperado:</strong> $${ESPERADO_EFECTIVO.toLocaleString('es-CL')} CLP</div>
                <div class="mt-1"><strong>Resultado:</strong> <span class="fw-bold">${estadoTexto}</span></div>
            </div>
            <p class="small text-muted mb-0">Una vez cerrada, la caja no admitirá más tickets en este turno y quedará registrada en auditoría.</p>
        `,
        icon: iconoModal,
        showCancelButton: true,
        confirmButtonText: '<i class="bi bi-lock-fill me-1"></i> Sí, cerrar caja',
        cancelButtonText: '<i class="bi bi-x-circle me-1"></i> Cancelar',
        reverseButtons: true
    }).then((result) => {
        if (result.isConfirmed) {
            form.submit();
        }
    });
}

// ==========================================================================
// Ezio Auditore - Bloqueo Rápido de Terminal Compartido (PIN Lock)
// ==========================================================================
const PosPinLock = (() => {
    let pinIngresado = '';
    let pinsValidos = ['1234'];
    let pinHint = '1234';
    let inactividadTimer = null;
    const TIEMPO_INACTIVIDAD_MS = 180000; // 3 minutos (ergonomía POS)
    let bloqueado = false;

    function init() {
        const overlay = document.getElementById('safariPosLockOverlay');
        const btnBloquear = document.getElementById('btnBloquearCaja');
        if (!overlay || !btnBloquear) return;

        // Leer PINs válidos desde configuración inyectada
        try {
            const configEl = document.getElementById('vendedorConfigData');
            if (configEl) {
                const cfg = JSON.parse(configEl.textContent || '{}');
                if (Array.isArray(cfg.pinsValidos) && cfg.pinsValidos.length > 0) {
                    pinsValidos = cfg.pinsValidos.map(String);
                }
                if (cfg.pinHint) {
                    pinHint = String(cfg.pinHint);
                }
            }
        } catch (e) {
            console.warn('Error leyendo pinsValidos:', e);
        }
        if (!pinsValidos.includes('1234')) pinsValidos.push('1234');

        btnBloquear.addEventListener('click', bloquear);

        // Teclado numérico en pantalla
        document.querySelectorAll('.btn-key[data-digit]').forEach(btn => {
            btn.addEventListener('click', () => {
                const dig = btn.getAttribute('data-digit');
                ingresarDigito(dig);
            });
        });

        document.getElementById('btnPinClear')?.addEventListener('click', limpiarPin);
        document.getElementById('btnPinBackspace')?.addEventListener('click', borrarDigito);

        // Botón de ayuda/pista de PIN
        document.getElementById('btnPinAyuda')?.addEventListener('click', () => {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    title: 'PIN de Desbloqueo',
                    html: `<p class="small mb-2 text-muted">Para desbloquear este terminal puedes utilizar:</p>
                           <ul class="text-start small mb-0">
                               <li>PIN maestro de terminal: <strong class="font-monospace">1234</strong></li>
                               <li>Últimos 4 dígitos de tu RUT: <strong class="font-monospace">${pinHint}</strong></li>
                           </ul>`,
                    icon: 'info',
                    confirmButtonText: 'Entendido',
                    confirmButtonColor: '#198754'
                });
            } else {
                alert(`PIN de desbloqueo: 1234 o últimos 4 dígitos de tu RUT (${pinHint})`);
            }
        });

        // Teclado físico
        document.addEventListener('keydown', (e) => {
            if (!bloqueado) return;
            if (e.key >= '0' && e.key <= '9') {
                ingresarDigito(e.key);
            } else if (e.key === 'Backspace') {
                borrarDigito();
            } else if (e.key === 'Escape' || e.key === 'c' || e.key === 'C') {
                limpiarPin();
            }
        });

        // Detector de inactividad
        const resetTimer = () => {
            if (bloqueado) return;
            clearTimeout(inactividadTimer);
            inactividadTimer = setTimeout(bloquear, TIEMPO_INACTIVIDAD_MS);
        };

        ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll'].forEach(evt => {
            window.addEventListener(evt, resetTimer, { passive: true });
        });
        resetTimer();
    }

    function bloquear() {
        bloqueado = true;
        limpiarPin();
        const overlay = document.getElementById('safariPosLockOverlay');
        if (overlay) {
            overlay.classList.remove('d-none');
            overlay.style.setProperty('display', 'flex', 'important');
        }
    }

    function desbloquear() {
        bloqueado = false;
        limpiarPin();
        const overlay = document.getElementById('safariPosLockOverlay');
        if (overlay) {
            overlay.classList.add('d-none');
            overlay.style.setProperty('display', 'none', 'important');
        }
        clearTimeout(inactividadTimer);
        inactividadTimer = setTimeout(bloquear, TIEMPO_INACTIVIDAD_MS);
    }

    function ingresarDigito(dig) {
        if (pinIngresado.length >= 4) return;
        pinIngresado += dig;
        actualizarDots();

        if (pinIngresado.length === 4) {
            verificarPin();
        }
    }

    function borrarDigito() {
        if (pinIngresado.length > 0) {
            pinIngresado = pinIngresado.slice(0, -1);
            actualizarDots();
        }
    }

    function limpiarPin() {
        pinIngresado = '';
        actualizarDots();
        const msg = document.getElementById('pinErrorMessage');
        if (msg) msg.classList.add('invisible');
    }

    function actualizarDots() {
        for (let i = 0; i < 4; i++) {
            const dot = document.getElementById(`pinDot${i}`);
            if (dot) {
                if (i < pinIngresado.length) dot.classList.add('active');
                else dot.classList.remove('active');
            }
        }
    }

    function verificarPin() {
        const pinLimpio = String(pinIngresado).trim();
        if (pinsValidos.includes(pinLimpio) || pinLimpio === '1234') {
            desbloquear();
        } else {
            const msg = document.getElementById('pinErrorMessage');
            if (msg) msg.classList.remove('invisible');
            setTimeout(limpiarPin, 800);
        }
    }

    return { init, bloquear, desbloquear };
})();

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', PosPinLock.init);
} else {
    PosPinLock.init();
}
