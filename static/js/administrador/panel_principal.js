document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.toast-container .toast').forEach(function(el) {
        const toast = new bootstrap.Toast(el, { delay: 4000 });
        toast.show();
        setTimeout(function() {
            try { toast.hide(); } catch(e){}
        }, 4000);
    });
});

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
        .catch(err => console.error('Error al actualizar alertas:', err));
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
});

let actualizandoAdminLive = false;
async function autoActualizarAdminLive() {
    if (actualizandoAdminLive) return;
    if (document.querySelector('.modal.show')) return; // No interrumpir si hay un modal abierto
    actualizandoAdminLive = true;
    const scrollPos = window.scrollY;

    try {
        const resp = await fetch(window.location.href, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!resp.ok) {
            actualizandoAdminLive = false;
            return;
        }
        const html = await resp.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        const nuevoCont = doc.getElementById('contenedorAdminEnVivo');
        const actualCont = document.getElementById('contenedorAdminEnVivo');
        if (nuevoCont && actualCont && nuevoCont.innerHTML.trim() !== actualCont.innerHTML.trim()) {
            actualCont.innerHTML = nuevoCont.innerHTML;
        }

        // Actualizar contador de alertas
        const nA = doc.getElementById('badgeAlertasCount');
        const aA = document.getElementById('badgeAlertasCount');
        if (nA && aA && nA.innerText !== aA.innerText) {
            aA.innerText = nA.innerText;
        }

        window.scrollTo(0, scrollPos);
    } catch(e) {
        // Silencioso ante contingencias de red (Tarea 7)
    } finally {
        actualizandoAdminLive = false;
    }
}
// Sincronizar en vivo cada 1.5 segundos (1500 ms) con gestion inteligente de recursos
let adminInterval = setInterval(autoActualizarAdminLive, 1500);

document.addEventListener('visibilitychange', () => {
    clearInterval(adminInterval);
    if (document.visibilityState === 'visible') {
        autoActualizarAdminLive();
        adminInterval = setInterval(autoActualizarAdminLive, 1500);
    } else {
        adminInterval = setInterval(autoActualizarAdminLive, 6000);
    }
});
