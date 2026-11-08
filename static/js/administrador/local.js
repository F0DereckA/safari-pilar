function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', function () {
    const dropdownAlertasBtn = document.getElementById('dropdownAlertas');
    if (!dropdownAlertasBtn) return;

    const csrfToken = document.querySelector('#formCsrfAlertas [name=csrfmiddlewaretoken]')?.value || '';

    function marcarAlertasLeidas(alertaId = 'todas') {
        const formData = new FormData();
        formData.append('accion', 'marcar_leida_alerta');
        formData.append('alerta_id', alertaId);

        fetch(document.getElementById('formCsrfAlertas')?.getAttribute('action') || window.location.pathname, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'ok') {
                if (alertaId === 'todas') {
                    // Ocultar suavemente el badge contador de la campana
                    const badgeCount = document.getElementById('badgeAlertasCount');
                    if (badgeCount) {
                        badgeCount.style.transition = 'all 0.3s ease';
                        badgeCount.style.opacity = '0';
                        badgeCount.style.transform = 'scale(0.5)';
                        setTimeout(() => { badgeCount.remove(); }, 300);
                    }

                    // Actualizar badge interior
                    const badgeEstado = document.getElementById('badgeAlertasEstado');
                    if (badgeEstado) {
                        badgeEstado.className = 'badge bg-success-subtle text-success rounded-pill px-2 py-1 small fw-bold';
                        badgeEstado.textContent = 'Al día';
                    }

                    // Ocultar botón de marcar todas
                    const btnMarcar = document.getElementById('btnMarcarTodasLeidas');
                    if (btnMarcar) btnMarcar.remove();

                    // Quitar etiquetas NUEVA y botones individuales
                    document.querySelectorAll('.badge-alerta-nueva').forEach(el => el.remove());
                    document.querySelectorAll('.btn-descartar-alerta').forEach(el => el.remove());
                    document.querySelectorAll('.alerta-item').forEach(el => {
                        el.classList.remove('border-warning');
                        el.classList.add('border-light-subtle', 'text-muted');
                    });
                } else {
                    // Si se descartó una individual
                    const item = document.getElementById(`alerta-item-${alertaId}`);
                    if (item) {
                        item.querySelector('.badge-alerta-nueva')?.remove();
                        item.querySelector('.btn-descartar-alerta')?.remove();
                        item.classList.remove('border-warning');
                        item.classList.add('border-light-subtle', 'text-muted');
                    }
                    const badgeCount = document.getElementById('badgeAlertasCount');
                    if (badgeCount) {
                        if (data.pendientes > 0) {
                            badgeCount.textContent = data.pendientes;
                        } else {
                            badgeCount.remove();
                            const badgeEstado = document.getElementById('badgeAlertasEstado');
                            if (badgeEstado) {
                                badgeEstado.className = 'badge bg-success-subtle text-success rounded-pill px-2 py-1 small fw-bold';
                                badgeEstado.textContent = 'Al día';
                            }
                            const btnMarcar = document.getElementById('btnMarcarTodasLeidas');
                            if (btnMarcar) btnMarcar.remove();
                        }
                    }
                }
            }
        })
        .catch(err => console.error('Error al actualizar alertas del local:', err));
    }

    // 1. Al abrir el dropdown de alertas, marcarlas automáticamente como leídas
    const dropdownElement = dropdownAlertasBtn.closest('.dropdown');
    if (dropdownElement) {
        dropdownElement.addEventListener('show.bs.dropdown', function () {
            const badgeCount = document.getElementById('badgeAlertasCount');
            if (badgeCount) {
                marcarAlertasLeidas('todas');
            }
        });
    }

    // 2. Botón explícito "Marcar leídas"
    const btnMarcarTodas = document.getElementById('btnMarcarTodasLeidas');
    if (btnMarcarTodas) {
        btnMarcarTodas.addEventListener('click', function (e) {
            e.stopPropagation();
            marcarAlertasLeidas('todas');
        });
    }

    // 3. Botones individuales para descartar/leer una alerta específica
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-descartar-alerta');
        if (btn) {
            e.stopPropagation();
            const alertaId = btn.getAttribute('data-alerta-id');
            marcarAlertasLeidas(alertaId);
        }
    });

    // ==========================================
    // FILTRADO DINÁMICO EN TIEMPO REAL DE TICKETS
    // ==========================================
    window.filtrarTickets = function() {
        const texto = (document.getElementById('filtroTextoTicket')?.value || '').toLowerCase().trim();
        const hora = document.getElementById('filtroHoraTicket')?.value || 'todas';
        const rol = document.getElementById('filtroRolTicket')?.value || 'todos';
        const estado = document.getElementById('filtroEstadoTicket')?.value || 'todos';

        const rows = document.querySelectorAll('#tablaTicketsRecientes .ticket-row');
        let visibles = 0;

        rows.forEach(row => {
            const id = (row.getAttribute('data-id') || '').toLowerCase();
            const horaVal = row.getAttribute('data-hora') || '';
            const cliente = (row.getAttribute('data-cliente') || '').toLowerCase();
            const cajero = (row.getAttribute('data-cajero') || '').toLowerCase();
            const rolVal = row.getAttribute('data-rol') || '';
            const estadoVal = row.getAttribute('data-estado') || '';

            const matchTexto = !texto || id.includes(texto) || cliente.includes(texto) || cajero.includes(texto);

            let matchHora = true;
            if (hora !== 'todas') {
                const hInt = parseInt(horaVal.split(':')[0], 10);
                if (hora === 'anterior') {
                    matchHora = hInt < 12;
                } else {
                    matchHora = hInt === parseInt(hora, 10);
                }
            }

            const matchRol = rol === 'todos' || rolVal === rol;
            const matchEstado = estado === 'todos' || estadoVal === estado;

            if (matchTexto && matchHora && matchRol && matchEstado) {
                row.style.display = '';
                visibles++;
            } else {
                row.style.display = 'none';
            }
        });

        const badge = document.getElementById('contadorTicketsVisibles');
        if (badge) {
            badge.innerText = `${visibles} de ${rows.length} Comandas`;
        }
    };

    window.limpiarFiltrosTickets = function() {
        if (document.getElementById('filtroTextoTicket')) document.getElementById('filtroTextoTicket').value = '';
        if (document.getElementById('filtroHoraTicket')) document.getElementById('filtroHoraTicket').value = 'todas';
        if (document.getElementById('filtroRolTicket')) document.getElementById('filtroRolTicket').value = 'todos';
        if (document.getElementById('filtroEstadoTicket')) document.getElementById('filtroEstadoTicket').value = 'todos';
        window.filtrarTickets();
    };

    // ==========================================
    // APERTURA DE MODAL DETALLE DE TICKET
    // ==========================================
    document.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-ver-detalle-ticket');
        if (!btn) return;

        const id = btn.getAttribute('data-ticket-id') || '';
        const hora = btn.getAttribute('data-ticket-hora') || '';
        const cliente = btn.getAttribute('data-ticket-cliente') || '';
        const cajero = btn.getAttribute('data-ticket-cajero') || '';
        const rol = btn.getAttribute('data-ticket-rol') || '';
        const total = btn.getAttribute('data-ticket-total') || '$0';
        const estado = btn.getAttribute('data-ticket-estado') || '';
        const itemsRaw = btn.getAttribute('data-ticket-items') || '[]';

        document.getElementById('mdlTicketCodigo').innerText = '#' + id;
        document.getElementById('mdlTicketCliente').innerText = cliente;
        document.getElementById('mdlTicketHora').innerText = hora + ' hrs';
        document.getElementById('mdlTicketCajero').innerText = cajero;
        document.getElementById('mdlTicketTotal').innerText = total;

        const rolBadge = document.getElementById('mdlTicketRolBadge');
        if (rol === 'Mesero') {
            rolBadge.className = 'badge bg-warning text-dark rounded-pill';
            rolBadge.innerHTML = '<i class="bi bi-person-walking me-1"></i>Mesero';
        } else {
            rolBadge.className = 'badge bg-primary text-white rounded-pill';
            rolBadge.innerHTML = '<i class="bi bi-person-badge me-1"></i>Cajero';
        }

        const estBadge = document.getElementById('mdlTicketEstadoBadge');
        if (estado === 'En Cocina') {
            estBadge.className = 'badge bg-danger text-white';
            estBadge.innerHTML = '<i class="bi bi-fire me-1"></i>' + estado;
        } else if (estado === 'En Barra') {
            estBadge.className = 'badge text-white';
            estBadge.style.backgroundColor = '#6b21a8';
            estBadge.innerHTML = '<i class="bi bi-cup-hot me-1"></i>' + estado;
        } else if (estado === 'Listo') {
            estBadge.className = 'badge bg-success text-white';
            estBadge.innerHTML = '<i class="bi bi-check2-circle me-1"></i>' + estado;
        } else {
            estBadge.className = 'badge bg-secondary text-white';
            estBadge.innerHTML = '<i class="bi bi-check2-all me-1"></i>' + estado;
        }

        let items = [];
        try {
            items = JSON.parse(itemsRaw);
        } catch (err) {
            items = [];
        }

        const tbody = document.getElementById('mdlTicketItemsBody');
        tbody.innerHTML = '';

        if (items.length > 0) {
            items.forEach(it => {
                const tr = document.createElement('tr');
                const destBadge = it.destino === 'Cocina'
                    ? '<span class="badge bg-danger-subtle text-danger border border-danger-subtle">Cocina</span>'
                    : '<span class="badge bg-primary-subtle text-primary border border-primary-subtle">Barra</span>';
                const notaHtml = it.nota ? `<small class="text-danger d-block fst-italic">* ${escapeHtml(it.nota)}</small>` : '';
                tr.innerHTML = `
                    <td><strong>${it.cantidad}x</strong></td>
                    <td>
                        <div class="fw-bold text-dark">${escapeHtml(it.nombre)}</div>
                        ${notaHtml}
                    </td>
                    <td>${destBadge}</td>
                    <td class="text-end text-muted">$${(it.precio || 0).toLocaleString('es-CL')}</td>
                    <td class="text-end fw-bold text-dark">$${(it.subtotal || (it.cantidad * it.precio) || 0).toLocaleString('es-CL')}</td>
                `;
                tbody.appendChild(tr);
            });
            document.getElementById('mdlTicketItemsConteo').innerText = `${items.length} productos incluidos`;
        } else {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-2">Comanda consolidada de servicio</td></tr>';
            document.getElementById('mdlTicketItemsConteo').innerText = 'Comanda procesada';
        }

        const modal = new bootstrap.Modal(document.getElementById('modalDetalleTicket'));
        modal.show();
    });
});
