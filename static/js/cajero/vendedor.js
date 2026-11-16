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
            if (t.tieneListoParcial) totalListos++;
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
            cumpleEstado = (ticket.estadoBd === 'LISTO' || Boolean(ticket.tieneListoParcial));
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
                    <button type="button" class="btn btn-sm btn-outline-success rounded-pill fw-bold" data-ticket-accion-id="${ticket.pedido_id}" data-ticket-nuevo-estado="LISTO">
                        <i class="bi bi-check2-circle me-1" aria-hidden="true"></i> Marcar Listo
                    </button>
                `;
            } else if (ticket.estadoBd === 'EN_PREPARACION') {
                if (ticket.tieneListoParcial) {
                    const estListoNom = ticket.estadoCocina === 'LISTO' ? 'Cocina Listo' : 'Barra Listo';
                    statusBadgeHtml = `<span class="badge-status status-listo"><i class="bi bi-bell-fill"></i> ${estListoNom} (Mixto)</span>`;
                } else if (ticket.tieneCocina) {
                    statusBadgeHtml = `<span class="badge-status status-cocina"><i class="bi bi-fire"></i> Preparando en Cocina</span>`;
                } else {
                    statusBadgeHtml = `<span class="badge-status status-barra"><i class="bi bi-cup-hot-fill"></i> Preparando en Barra</span>`;
                }
                actionBtnHtml = `
                    <button type="button" class="btn btn-sm btn-outline-success rounded-pill fw-bold" data-ticket-accion-id="${ticket.pedido_id}" data-ticket-nuevo-estado="LISTO">
                        <i class="bi bi-check2-circle me-1" aria-hidden="true"></i> Marcar Listo
                    </button>
                `;
            } else if (ticket.estadoBd === 'LISTO') {
                statusBadgeHtml = `<span class="badge-status status-listo"><i class="bi bi-bag-check-fill"></i> Listo para Entrega</span>`;
                actionBtnHtml = `
                    <button type="button" class="btn btn-sm btn-success rounded-pill fw-bold" data-ticket-accion-id="${ticket.pedido_id}" data-ticket-nuevo-estado="ENTREGADO">
                        <i class="bi bi-check-all me-1" aria-hidden="true"></i> Entregar a Comensal
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
                                <i class="bi bi-receipt text-warning-emphasis me-1" aria-hidden="true"></i>#${escapeHtml(ticket.id)} ${badgeCuentaHtml}
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
        const ct = resp.headers.get('content-type') || '';
        const data = ct.includes('application/json') ? await resp.json() : {};
        if (resp.status === 401 || data.sesion_expirada) {
            if (typeof swalErrorBootstrap !== 'undefined') {
                swalErrorBootstrap.fire({ title: 'Sesión expirada', text: data.error || 'Inicia sesión nuevamente.', icon: 'warning' }).then(() => window.location.reload());
            }
            return;
        }
        if (resp.ok && (data.ok || data.status === 'ok')) {
            if (window.SafariSyncBus) {
                window.SafariSyncBus.publish({
                    type: 'pedido_estado',
                    pedido_id: pedidoId,
                    nuevo_estado: nuevoEstado,
                });
            }
            await autoActualizarVendedor(true);
            if (typeof swalToast !== 'undefined') {
                swalToast.fire({ icon: 'success', title: `Comanda #COM-${String(pedidoId).padStart(4, '0')} actualizada a ${data.estado_display}.` });
            }
        } else if (typeof swalErrorBootstrap !== 'undefined') {
            swalErrorBootstrap.fire({ title: 'No se pudo actualizar', text: data.mensaje || data.error || 'Error al cambiar estado.', icon: 'error' });
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
            if (window.SafariSyncBus) window.SafariSyncBus.publish({ type: 'mesa_estado', mesa_id: mesaId });
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
            if (window.SafariSyncBus) window.SafariSyncBus.publish({ type: 'mesa_estado', mesa_id: mesaId });
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
    let porcentajeSeleccionado = 10; // 10% sugerido por defecto (Ley N° 20.918)
    const totalNum = Math.max(0, Math.round(Number(totalAbierto) || 0));

    const htmlModal = `
        <div class="text-start mb-2">
            <div class="text-center py-2 mb-3 bg-light rounded-3 border">
                <span class="text-muted small d-block">TOTAL CONSUMO EN MESA:</span>
                <span class="text-success fs-3 fw-bold" id="swalTotalConsumoDisplay">$${totalNum.toLocaleString('es-CL')} CLP</span>
            </div>

            <div class="mb-3">
                <label class="form-label fw-bold small text-dark mb-1">Método de Pago:</label>
                <select id="swalMetodoPago" class="form-select form-select-sm">
                    <option value="EFECTIVO" selected>Efectivo (aplica redondeo Ley 20.956)</option>
                    <option value="DEBITO">Tarjeta de Débito (Redcompra)</option>
                    <option value="CREDITO">Tarjeta de Crédito</option>
                    <option value="TRANSFERENCIA">Transferencia Electrónica</option>
                </select>
            </div>

            <div class="mb-3">
                <label class="form-label fw-bold small text-dark mb-1">Monto a Cobrar / Abono Parcial (CLP):</label>
                <input type="number" id="swalMontoPago" class="form-control form-control-sm font-monospace" value="${totalNum}" min="1" max="${totalNum}">
                <small class="text-muted" style="font-size: 0.72rem;">Deja el total o ingresa un monto menor para registrar un abono / división de cuenta (Split Bill).</small>
            </div>

            <div class="p-3 bg-light rounded-3 border mb-3">
                <div class="d-flex align-items-center justify-content-between mb-2">
                    <label class="fw-bold small text-dark mb-0">
                        <i class="bi bi-heart-fill text-danger me-1"></i> Propina Voluntaria (Ley N° 20.918):
                    </label>
                    <span class="badge bg-secondary-subtle text-secondary px-2 py-1 rounded-pill small" style="font-size: 0.7rem;">Exenta de IVA</span>
                </div>
                <div class="btn-group w-100 mb-2" role="group" id="swalTipGroup">
                    <button type="button" class="btn btn-sm btn-outline-secondary" data-pct="0">0%</button>
                    <button type="button" class="btn btn-sm btn-success fw-bold" data-pct="10">10%</button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" data-pct="15">15%</button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" data-pct="20">20%</button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" data-pct="custom">Otro $</button>
                </div>
                <div id="swalCustomTipContainer" class="mb-2 d-none">
                    <div class="input-group input-group-sm">
                        <span class="input-group-text">$</span>
                        <input type="number" id="swalCustomTipInput" class="form-control font-monospace" placeholder="Ingresa monto voluntario" min="0">
                    </div>
                </div>
                <div class="small text-muted" style="font-size: 0.7rem;">
                    * 100% voluntaria para el personal de servicio. No se incluye en la base de IVA 19%.
                </div>
            </div>

            <!-- Desglose Tributario y de Cobro en Vivo -->
            <div class="card border rounded-3 p-2 bg-white" style="font-size: 0.78rem;">
                <div class="d-flex justify-content-between text-muted py-1 border-bottom">
                    <span>Subtotal Consumo (Alimentos/Bebidas):</span>
                    <strong class="font-monospace text-dark" id="swalResumenConsumo">$0</strong>
                </div>
                <div class="d-flex justify-content-between text-muted py-1 border-bottom">
                    <span>• Neto Imponible (19% IVA):</span>
                    <span class="font-monospace" id="swalResumenNeto">$0</span>
                </div>
                <div class="d-flex justify-content-between text-muted py-1 border-bottom">
                    <span>• IVA 19% (Gastronomía):</span>
                    <span class="font-monospace" id="swalResumenIva">$0</span>
                </div>
                <div class="d-flex justify-content-between text-success py-1 border-bottom fw-semibold">
                    <span>Propina Voluntaria (<span id="swalPctLabel">10%</span>):</span>
                    <span class="font-monospace" id="swalResumenPropina">+$0</span>
                </div>
                <div class="d-flex justify-content-between text-muted py-1 border-bottom" id="swalFilaRedondeo">
                    <span>Redondeo Ley 20.956 (Efectivo):</span>
                    <span class="font-monospace" id="swalResumenRedondeo">$0</span>
                </div>
                <div class="d-flex justify-content-between text-dark py-2 fs-6 fw-bold">
                    <span>TOTAL A COBRAR:</span>
                    <span class="font-monospace text-primary fs-5" id="swalResumenTotalFinal">$0 CLP</span>
                </div>
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
        didOpen: () => {
            const recalcularDesglose = () => {
                const metodo = document.getElementById('swalMetodoPago')?.value || 'EFECTIVO';
                const inputMonto = document.getElementById('swalMontoPago');
                const montoBase = Math.max(0, parseFloat(inputMonto?.value) || totalNum);
                const neto = Math.round(montoBase / 1.19);
                const iva = Math.round(montoBase * 19 / 119);

                let propina = 0;
                if (porcentajeSeleccionado === 'custom') {
                    propina = Math.max(0, parseFloat(document.getElementById('swalCustomTipInput')?.value) || 0);
                } else {
                    propina = Math.round(montoBase * (Number(porcentajeSeleccionado) / 100));
                }

                const totalSinRedondeo = montoBase + propina;
                let ajusteRedondeo = 0;
                if (metodo === 'EFECTIVO') {
                    const resto = totalSinRedondeo % 10;
                    if (resto >= 1 && resto <= 4) {
                        ajusteRedondeo = -resto;
                    } else if (resto >= 5 && resto <= 9) {
                        ajusteRedondeo = 10 - resto;
                    }
                }
                const totalFinal = totalSinRedondeo + ajusteRedondeo;

                const elConsumo = document.getElementById('swalResumenConsumo');
                const elNeto = document.getElementById('swalResumenNeto');
                const elIva = document.getElementById('swalResumenIva');
                const elPct = document.getElementById('swalPctLabel');
                const elProp = document.getElementById('swalResumenPropina');
                const elFilaRed = document.getElementById('swalFilaRedondeo');
                const elRed = document.getElementById('swalResumenRedondeo');
                const elTot = document.getElementById('swalResumenTotalFinal');

                if (elConsumo) elConsumo.innerText = `$${Math.round(montoBase).toLocaleString('es-CL')}`;
                if (elNeto) elNeto.innerText = `$${neto.toLocaleString('es-CL')}`;
                if (elIva) elIva.innerText = `$${iva.toLocaleString('es-CL')}`;
                if (elPct) elPct.innerText = porcentajeSeleccionado === 'custom' ? 'Manual' : `${porcentajeSeleccionado}%`;
                if (elProp) elProp.innerText = `+$${Math.round(propina).toLocaleString('es-CL')}`;

                if (elFilaRed && elRed) {
                    if (metodo === 'EFECTIVO') {
                        elFilaRed.classList.remove('d-none');
                        elRed.innerText = `${ajusteRedondeo >= 0 ? '+' : ''}$${ajusteRedondeo} CLP`;
                    } else {
                        elFilaRed.classList.add('d-none');
                    }
                }
                if (elTot) elTot.innerText = `$${Math.round(totalFinal).toLocaleString('es-CL')} CLP`;
            };

            const tipButtons = document.querySelectorAll('#swalTipGroup button');
            const customContainer = document.getElementById('swalCustomTipContainer');
            const customInput = document.getElementById('swalCustomTipInput');

            tipButtons.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    tipButtons.forEach(b => {
                        b.classList.remove('btn-success', 'fw-bold');
                        b.classList.add('btn-outline-secondary');
                    });
                    btn.classList.remove('btn-outline-secondary');
                    btn.classList.add('btn-success', 'fw-bold');

                    const pctVal = btn.getAttribute('data-pct');
                    if (pctVal === 'custom') {
                        porcentajeSeleccionado = 'custom';
                        customContainer?.classList.remove('d-none');
                        customInput?.focus();
                    } else {
                        porcentajeSeleccionado = Number(pctVal);
                        customContainer?.classList.add('d-none');
                    }
                    recalcularDesglose();
                });
            });

            document.getElementById('swalMetodoPago')?.addEventListener('change', recalcularDesglose);
            document.getElementById('swalMontoPago')?.addEventListener('input', recalcularDesglose);
            customInput?.addEventListener('input', recalcularDesglose);

            recalcularDesglose();
        },
        preConfirm: () => {
            const metodo = document.getElementById('swalMetodoPago')?.value || 'EFECTIVO';
            const monto = parseFloat(document.getElementById('swalMontoPago')?.value) || totalNum;
            let propinaCalculada = 0;
            let pct = 0;

            if (porcentajeSeleccionado === 'custom') {
                propinaCalculada = Math.max(0, parseFloat(document.getElementById('swalCustomTipInput')?.value) || 0);
                pct = monto > 0 ? Math.round((propinaCalculada / monto) * 100) : 0;
            } else {
                pct = Number(porcentajeSeleccionado) || 0;
                propinaCalculada = Math.round(monto * (pct / 100));
            }
            return { metodo, monto, porcentajePropina: pct, montoPropina: propinaCalculada };
        }
    });

    if (!formValues) return;

    try {
        const formData = new FormData();
        formData.append('accion', 'cobrar_cuenta_mesa');
        formData.append('mesa_id', mesaId);
        formData.append('metodo_pago', formValues.metodo);
        formData.append('monto_pago', formValues.monto);
        formData.append('porcentaje_propina', String(formValues.porcentajePropina));
        formData.append('monto_propina', String(formValues.montoPropina));
        if (formValues.montoPropina > 0) {
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
            if (window.SafariSyncBus) window.SafariSyncBus.publish({ type: 'mesa_estado', mesa_id: mesaId });
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

// Sincronización en tiempo real + Alerta sonora inmediata de pedidos listos (Cocina/Barra -> Cajero)
const STORAGE_AUDIO_CAJERO = 'safari_audio_v2_cajero';
let actualizandoVendedor = false;
let syncPendienteVendedor = false;
let ultimaVersionDeltaCajero = null;
let vendedorSyncTimer = null;

const seenReadyKeysCajero = (() => {
    const initSet = new Set();
    (pedidosCajero || []).forEach(t => {
        if (t.estadoBd === 'ENTREGADO' || t.estadoBd === 'CANCELADO') return;
        if (t.estadoCocina === 'LISTO') initSet.add(`${t.pedido_id}:COCINA`);
        if (t.estadoBarra === 'LISTO') initSet.add(`${t.pedido_id}:BARRA`);
        if (t.estadoBd === 'LISTO' && t.estadoCocina !== 'LISTO' && t.estadoBarra !== 'LISTO') {
            initSet.add(`${t.pedido_id}:GENERAL`);
        }
    });
    return initSet;
})();

function procesarAlertasListosCajero(listosDetalle) {
    if (!Array.isArray(listosDetalle)) return;
    const actualesKeys = new Set(listosDetalle.map(item => item.key));
    const nuevos = listosDetalle.filter(item => item.key && !seenReadyKeysCajero.has(item.key));

    // Limpiar de memoria los ya entregados para permitir futuras alertas si reingresan
    for (const k of Array.from(seenReadyKeysCajero)) {
        if (!actualesKeys.has(k)) seenReadyKeysCajero.delete(k);
    }
    actualesKeys.forEach(k => seenReadyKeysCajero.add(k));

    if (nuevos.length > 0) {
        if (window.SafariAudioAlerts) {
            window.SafariAudioAlerts.play('pedido_listo', STORAGE_AUDIO_CAJERO);
        }
        if (window.SafariReadyNotifier) {
            nuevos.slice(0, 3).forEach(item => window.SafariReadyNotifier.notifyReady(item));
        }
    }
}

function programarSyncVendedor(delayMs) {
    clearTimeout(vendedorSyncTimer);
    const delay = typeof delayMs === 'number'
        ? delayMs
        : (document.visibilityState === 'visible' ? 1500 : 4000);
    vendedorSyncTimer = setTimeout(() => autoActualizarVendedor(false), delay);
}

async function autoActualizarVendedor(forzar = false) {
    if (actualizandoVendedor) {
        syncPendienteVendedor = true;
        return;
    }
    if (!forzar && (document.querySelector('.modal.show') || document.querySelector('.swal2-container'))) {
        programarSyncVendedor();
        return;
    }
    actualizandoVendedor = true;
    try {
        const deltaUrl = '/api/sincronizacion/estado/' + window.location.search;
        let debeActualizar = forzar;

        try {
            const deltaOpts = { headers: { 'X-Requested-With': 'XMLHttpRequest' } };
            if (!forzar) deltaOpts.priority = 'low';
            const deltaResp = await fetch(deltaUrl, deltaOpts);
            if (deltaResp.ok) {
                const delta = await deltaResp.json();
                if (delta.ok) {
                    // Notificación auditiva/visual INMEDIATA sin esperar recarga de HTML completo
                    if (Array.isArray(delta.listos_detalle)) {
                        procesarAlertasListosCajero(delta.listos_detalle);
                    }
                    const kpiListosEl = document.getElementById('kpiListos');
                    if (kpiListosEl && typeof delta.listos === 'number') {
                        kpiListosEl.innerText = String(delta.listos);
                    }

                    if (!forzar && ultimaVersionDeltaCajero && ultimaVersionDeltaCajero === delta.version) {
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
            return;
        }

        const domOpts = { headers: { 'X-Requested-With': 'XMLHttpRequest' } };
        if (!forzar) domOpts.priority = 'low';
        const resp = await fetch(window.location.href, domOpts);
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
        if (syncPendienteVendedor) {
            syncPendienteVendedor = false;
            programarSyncVendedor(80);
        } else {
            programarSyncVendedor();
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    renderizarTickets();
    if (vendedorConfig.cajaActiva) {
        calcularArqueoCaja();
    }

    const filtroTicketTexto = document.getElementById('filtroTicketTexto');
    if (filtroTicketTexto) {
        filtroTicketTexto.addEventListener('input', filtrarTickets);
    }

    const btnLimpiarFiltroTicket = document.getElementById('btnLimpiarFiltroTicket');
    if (btnLimpiarFiltroTicket) {
        btnLimpiarFiltroTicket.addEventListener('click', limpiarFiltroTicket);
    }

    document.querySelectorAll('#vendedorFilterEstadoGroup [data-filter-estado]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#vendedorFilterEstadoGroup [data-filter-estado]').forEach(b => b.setAttribute('aria-pressed', 'false'));
            btn.setAttribute('aria-pressed', 'true');
            filtrarEstado(btn.getAttribute('data-filter-estado'), btn);
        });
    });

    const panelMesasSalon = document.getElementById('panelMesasSalonCajero');
    if (panelMesasSalon) {
        panelMesasSalon.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-mesa-action]');
            if (!btn) return;
            const action = btn.getAttribute('data-mesa-action');
            const id = Number(btn.getAttribute('data-mesa-id'));
            const nombre = btn.getAttribute('data-mesa-nombre') || '';
            if (action === 'ocupar') ocuparMesaCajero(id, nombre);
            else if (action === 'cobrar') cobrarMesaCajero(id, nombre, Number(btn.getAttribute('data-mesa-total') || 0));
            else if (action === 'liberar') liberarMesaCajero(id, nombre);
        });
    }

    const contTickets = document.getElementById('contenedorTickets');
    if (contTickets) {
        contTickets.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-ticket-accion-id]');
            if (btn) {
                cambiarEstadoTicket(Number(btn.getAttribute('data-ticket-accion-id')), btn.getAttribute('data-ticket-nuevo-estado'));
            }
        });
    }

    const secVentasRecientes = document.getElementById('seccionVentasRecientesCajero');
    if (secVentasRecientes) {
        secVentasRecientes.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-anular-venta-id]');
            if (btn) {
                abrirModalAnular(btn.getAttribute('data-anular-venta-id'), btn.getAttribute('data-anular-venta-total'));
            }
        });
    }

    const formCerrarCaja = document.getElementById('formCerrarCaja');
    if (formCerrarCaja) {
        formCerrarCaja.addEventListener('input', (e) => {
            if (e.target.matches('.input-arqueo')) {
                limpiarCerosInicialesInput(e.target);
                calcularArqueoCaja();
            }
        });
    }

    const btnConfirmarCierreCaja = document.getElementById('btnConfirmarCierreCaja');
    if (btnConfirmarCierreCaja) {
        btnConfirmarCierreCaja.addEventListener('click', confirmarCierreCaja);
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

    if (window.SafariAudioAlerts) {
        window.SafariAudioAlerts.bindToggleButton({
            buttonId: 'btnTogglePosAudio',
            storageKey: STORAGE_AUDIO_CAJERO,
            testProfile: 'pedido_listo',
            variant: 'light-header',
        });
    }

    // Sincronización secuencial inteligente + bus instantáneo entre pestañas
    programarSyncVendedor(1200);

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            autoActualizarVendedor(false);
        } else {
            programarSyncVendedor(4000);
        }
    });

    if (window.SafariSyncBus) {
        window.SafariSyncBus.subscribe((ev) => {
            if (ev && (ev.type === 'pedido_estado' || ev.type === 'nueva_comanda')) {
                ultimaVersionDeltaCajero = null;
                autoActualizarVendedor(false);
            }
        });
    }
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
// Sistema de Bloqueo Rápido de Terminal Compartido (Verificación en Servidor)
// ==========================================================================
const PosPinLock = (() => {
    let pinIngresado = '';
    let inactividadTimer = null;
    const TIEMPO_INACTIVIDAD_MS = 15 * 60 * 1000; // 15 minutos (ergonomía POS operativa)
    let bloqueado = false;
    let enError = false;
    let verificando = false;
    let timerError = null;
    let urlDesbloqueo = '/api/vendedor/desbloquear-pin/';

    function init() {
        const overlay = document.getElementById('safariPosLockOverlay');
        const btnBloquear = document.getElementById('btnBloquearCaja');
        if (!overlay) return;

        if (typeof vendedorConfig !== 'undefined' && vendedorConfig.urlDesbloquearPin) {
            urlDesbloqueo = vendedorConfig.urlDesbloquearPin;
        }

        if (btnBloquear) {
            btnBloquear.addEventListener('click', (e) => {
                e.preventDefault();
                bloquear();
            });
        }

        document.querySelectorAll('.btn-key[data-digit]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                ingresarDigito(btn.getAttribute('data-digit'));
            });
        });

        document.getElementById('btnPinClear')?.addEventListener('click', (e) => {
            e.preventDefault();
            limpiarPin();
        });
        document.getElementById('btnPinBackspace')?.addEventListener('click', (e) => {
            e.preventDefault();
            borrarDigito();
        });

        document.getElementById('btnPosVerificarPassword')?.addEventListener('click', (e) => {
            e.preventDefault();
            verificarPasswordTurno();
        });
        document.getElementById('posLockPasswordInput')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                verificarPasswordTurno();
            }
        });

        document.getElementById('btnToggleConfigPin')?.addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('panelConfigPinPos')?.classList.toggle('d-none');
        });
        document.getElementById('btnGuardarPinPos')?.addEventListener('click', (e) => {
            e.preventDefault();
            guardarPinOperativo();
        });

        // Teclado físico (ignorar mientras escribe en campos de contraseña)
        document.addEventListener('keydown', (e) => {
            if (!bloqueado) return;
            const activeTag = document.activeElement?.tagName;
            if (activeTag === 'INPUT' || activeTag === 'TEXTAREA') return;
            if (e.key >= '0' && e.key <= '9') {
                ingresarDigito(e.key);
            } else if (e.key === 'Backspace') {
                borrarDigito();
            } else if (e.key === 'Escape' || e.key === 'c' || e.key === 'C') {
                limpiarPin();
            } else if (e.key === 'Enter' && pinIngresado.length === 4) {
                verificarPin();
            }
        });

        const resetTimer = () => {
            if (bloqueado) return;
            clearTimeout(inactividadTimer);
            inactividadTimer = setTimeout(bloquear, TIEMPO_INACTIVIDAD_MS);
        };

        ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll', 'click'].forEach(evt => {
            window.addEventListener(evt, resetTimer, { passive: true });
        });
        resetTimer();
    }

    let ultimoElementoEnfocadoAntesBloqueo = null;

    function trapLockOverlayTab(e) {
        if (!bloqueado || e.key !== 'Tab') return;
        const overlay = document.getElementById('safariPosLockOverlay');
        if (!overlay) return;
        const focusables = Array.from(overlay.querySelectorAll('button:not([disabled]), input:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])')).filter(el => el.offsetParent !== null);
        if (!focusables.length) return;
        const primero = focusables[0];
        const ultimo = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === primero) {
            e.preventDefault();
            ultimo.focus();
        } else if (!e.shiftKey && document.activeElement === ultimo) {
            e.preventDefault();
            primero.focus();
        }
    }

    function bloquear() {
        ultimoElementoEnfocadoAntesBloqueo = document.activeElement;
        bloqueado = true;
        limpiarPin();
        const passEl = document.getElementById('posLockPasswordInput');
        if (passEl) passEl.value = '';
        const overlay = document.getElementById('safariPosLockOverlay');
        if (overlay) {
            overlay.classList.remove('d-none');
            overlay.style.setProperty('display', 'flex', 'important');
            document.addEventListener('keydown', trapLockOverlayTab);
            const firstKey = overlay.querySelector('.btn-key[data-digit="1"]') || passEl;
            if (firstKey) firstKey.focus();
        }
    }

    function desbloquear() {
        bloqueado = false;
        limpiarPin();
        const passEl = document.getElementById('posLockPasswordInput');
        if (passEl) passEl.value = '';
        const overlay = document.getElementById('safariPosLockOverlay');
        if (overlay) {
            overlay.classList.add('d-none');
            overlay.style.setProperty('display', 'none', 'important');
        }
        document.removeEventListener('keydown', trapLockOverlayTab);
        if (ultimoElementoEnfocadoAntesBloqueo && typeof ultimoElementoEnfocadoAntesBloqueo.focus === 'function') {
            ultimoElementoEnfocadoAntesBloqueo.focus();
            ultimoElementoEnfocadoAntesBloqueo = null;
        }
        clearTimeout(inactividadTimer);
        inactividadTimer = setTimeout(bloquear, TIEMPO_INACTIVIDAD_MS);
    }

    function mostrarErrorCredencial(mensaje) {
        enError = true;
        const msg = document.getElementById('pinErrorMessage');
        if (msg) {
            msg.textContent = mensaje || 'Credencial incorrecta. Intenta de nuevo.';
            msg.classList.remove('invisible');
        }
        const display = document.querySelector('.lock-pin-display');
        if (display) {
            display.classList.add('shake');
            setTimeout(() => display.classList.remove('shake'), 450);
        }
        timerError = setTimeout(limpiarPin, 1600);
    }

    function ingresarDigito(dig) {
        if (verificando) return;
        if (enError) limpiarPin();
        if (pinIngresado.length >= 4) return;
        pinIngresado += String(dig);
        actualizarDots();
        if (pinIngresado.length === 4) {
            verificarPin();
        }
    }

    function borrarDigito() {
        if (verificando) return;
        if (enError) {
            limpiarPin();
            return;
        }
        if (pinIngresado.length > 0) {
            pinIngresado = pinIngresado.slice(0, -1);
            actualizarDots();
        }
    }

    function limpiarPin() {
        if (timerError) clearTimeout(timerError);
        timerError = null;
        enError = false;
        pinIngresado = '';
        actualizarDots();
        const msg = document.getElementById('pinErrorMessage');
        if (msg) {
            msg.textContent = 'PIN incorrecto. Intenta de nuevo.';
            msg.classList.add('invisible');
        }
        document.querySelector('.lock-pin-display')?.classList.remove('shake');
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

    async function enviarVerificacionServidor(payloadExtra) {
        if (verificando) return;
        verificando = true;
        try {
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', obtenerCsrfTokenVendedor());
            Object.entries(payloadExtra).forEach(([k, v]) => formData.append(k, v));

            const resp = await fetch(urlDesbloqueo, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
            });
            const ct = resp.headers.get('content-type') || '';
            const data = ct.includes('application/json') ? await resp.json() : {};
            if (resp.status === 401 || data.sesion_expirada) {
                window.location.reload();
                return;
            }
            if (resp.ok && data.ok) {
                desbloquear();
                if (typeof swalToast !== 'undefined') {
                    swalToast.fire({ icon: 'success', title: data.mensaje || 'Terminal de caja desbloqueado exitosamente.' });
                }
            } else {
                mostrarErrorCredencial(data.error || 'Credencial inválida.');
            }
        } catch (err) {
            mostrarErrorCredencial('Error de conexión al verificar credenciales.');
        } finally {
            verificando = false;
        }
    }

    function verificarPin() {
        const pinLimpio = String(pinIngresado).trim();
        if (!/^\d{4}$/.test(pinLimpio)) {
            mostrarErrorCredencial('Ingresa un PIN numérico de 4 dígitos.');
            return;
        }
        enviarVerificacionServidor({ accion: 'desbloquear', pin: pinLimpio });
    }

    function verificarPasswordTurno() {
        const passEl = document.getElementById('posLockPasswordInput');
        const pwd = passEl ? passEl.value : '';
        if (!pwd) {
            mostrarErrorCredencial('Ingresa tu contraseña de turno.');
            return;
        }
        enviarVerificacionServidor({ accion: 'desbloquear', password: pwd });
    }

    async function guardarPinOperativo() {
        const passCur = document.getElementById('posConfigCurrentPassword')?.value || '';
        const nuevoPin = document.getElementById('posConfigNuevoPin')?.value.trim() || '';
        if (!passCur || !/^\d{4}$/.test(nuevoPin)) {
            mostrarErrorCredencial('Ingresa tu contraseña actual y un PIN de 4 dígitos.');
            return;
        }
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', obtenerCsrfTokenVendedor());
        formData.append('accion', 'configurar_pin');
        formData.append('password', passCur);
        formData.append('nuevo_pin', nuevoPin);
        try {
            const resp = await fetch(urlDesbloqueo, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
            });
            const data = await resp.json();
            if (resp.ok && data.ok) {
                document.getElementById('panelConfigPinPos')?.classList.add('d-none');
                document.getElementById('posConfigCurrentPassword').value = '';
                document.getElementById('posConfigNuevoPin').value = '';
                if (typeof swalToast !== 'undefined') {
                    swalToast.fire({ icon: 'success', title: data.mensaje || 'PIN cifrado configurado.' });
                }
            } else {
                mostrarErrorCredencial(data.error || 'No se pudo configurar el PIN.');
            }
        } catch (err) {
            mostrarErrorCredencial('Error de conexión al guardar PIN.');
        }
    }

    return { init, bloquear, desbloquear };
})();

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', PosPinLock.init);
} else {
    PosPinLock.init();
}
