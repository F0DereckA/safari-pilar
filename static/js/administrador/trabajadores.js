function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', function () {
    // Restaurar posición de scroll previa si existió un envío de formulario tradicional
    const savedScroll = sessionStorage.getItem('admin_trabajadores_scroll');
    if (savedScroll !== null) {
        sessionStorage.removeItem('admin_trabajadores_scroll');
        window.scrollTo({
            top: parseInt(savedScroll, 10),
            behavior: 'instant'
        });
    }

    const buscarInput = document.getElementById('buscarTrabajador');
    const filtroLocal = document.getElementById('filtroLocal');
    const filtroRol = document.getElementById('filtroRol');
    const filtroEstado = document.getElementById('filtroEstado');
    const btnLimpiar = document.getElementById('btnLimpiarFiltros');
    const rows = document.querySelectorAll('.worker-row');
    const contadorResultados = document.getElementById('contadorResultados');
    const sinResultadosMensaje = document.getElementById('sinResultadosMensaje');

    // Función de filtrado dinámico en tiempo real
    function filtrarTrabajadores() {
        const query = buscarInput.value.toLowerCase().trim();
        const localSeleccionado = filtroLocal.value;
        const rolSeleccionado = filtroRol.value;
        const estadoSeleccionado = filtroEstado.value;

        let visibles = 0;

        rows.forEach(row => {
            const nombre = row.getAttribute('data-nombre') || '';
            const rut = row.getAttribute('data-rut') || '';
            const localId = row.getAttribute('data-local-id') || '';
            const rol = row.getAttribute('data-rol') || '';
            const estado = row.getAttribute('data-estado') || '';

            // Condiciones
            const coincideTexto = !query || nombre.includes(query) || rut.includes(query);
            const coincideLocal = (localSeleccionado === 'todos') || (localId === localSeleccionado);
            const coincideRol = (rolSeleccionado === 'todos') || (rol === rolSeleccionado);
            const coincideEstado = (estadoSeleccionado === 'todos') || (estado === estadoSeleccionado);

            if (coincideTexto && coincideLocal && coincideRol && coincideEstado) {
                row.classList.remove('d-none');
                visibles++;
            } else {
                row.classList.add('d-none');
            }
        });

        // Actualizar contador
        if (contadorResultados) {
            contadorResultados.innerHTML = `<i class="bi bi-funnel-fill text-warning me-1"></i> Mostrando ${visibles} de ${rows.length} colaboradores`;
        }

        // Mensaje si no hay resultados
        if (visibles === 0 && rows.length > 0) {
            sinResultadosMensaje.classList.remove('d-none');
        } else {
            sinResultadosMensaje.classList.add('d-none');
        }
    }

    // Eventos de entrada en vivo
    buscarInput.addEventListener('input', filtrarTrabajadores);
    filtroLocal.addEventListener('change', filtrarTrabajadores);
    filtroRol.addEventListener('change', filtrarTrabajadores);
    filtroEstado.addEventListener('change', filtrarTrabajadores);

    // Botón Limpiar Filtros
    btnLimpiar.addEventListener('click', function () {
        buscarInput.value = '';
        filtroLocal.value = 'todos';
        filtroRol.value = 'todos';
        filtroEstado.value = 'todos';
        filtrarTrabajadores();
    });

    // Población del Modal Modificar Trabajador
    const modalEditar = document.getElementById('modalEditarTrabajador');
    if (modalEditar) {
        modalEditar.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            document.getElementById('editPerfilId').value = button.getAttribute('data-perfil-id') || '';
            document.getElementById('editNombre').value = button.getAttribute('data-first-name') || '';
            document.getElementById('editApellido').value = button.getAttribute('data-last-name') || '';
            document.getElementById('editRut').value = button.getAttribute('data-rut') || '';
            document.getElementById('editRol').value = button.getAttribute('data-rol') || 'CAJERO';
            document.getElementById('editTelefono').value = button.getAttribute('data-telefono') || '';
            document.getElementById('editLocalId').value = button.getAttribute('data-local-id') || 'none';
        });
    }

    // Población del Modal Traslado Rápido
    const modalTrasladar = document.getElementById('modalTrasladar');
    if (modalTrasladar) {
        modalTrasladar.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            document.getElementById('trasladoPerfilId').value = button.getAttribute('data-perfil-id') || '';
            document.getElementById('trasladoColaboradorNombre').textContent = button.getAttribute('data-nombre') || '';
            document.getElementById('trasladoLocalActual').textContent = button.getAttribute('data-local-actual') || 'Sin Asignar';

            const actualId = button.getAttribute('data-local-actual-id');
            const selectDestino = document.getElementById('trasladoNuevoLocalSelect');
            selectDestino.value = '';

            // Deshabilitar la opción del local actual en el selector de destino
            Array.from(selectDestino.options).forEach(opt => {
                opt.disabled = (opt.value === actualId);
            });
        });
    }

    // Ejecución asíncrona del cambio de estado (AJAX)
    function ejecutarToggleEstado(form) {
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalBtnHtml = submitBtn ? submitBtn.innerHTML : '';
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';
        }

        const formData = new FormData(form);
        const perfilId = form.getAttribute('data-perfil-id');

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Error en el servidor al cambiar estado');
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'ok') {
                const row = document.getElementById(`worker-row-${data.perfil_id}`);
                if (row) {
                    // 1. Actualizar data-estado de la fila para los filtros
                    row.setAttribute('data-estado', data.activo ? 'activo' : 'inactivo');

                    // 2. Actualizar celda de estado visual
                    const statusCell = row.querySelector('.worker-status-cell');
                    if (statusCell) {
                        if (data.activo) {
                            statusCell.innerHTML = `
                                <span class="badge-staff-activo">
                                    <i class="bi bi-check-circle-fill me-1"></i>Activo
                                </span>
                            `;
                        } else {
                            statusCell.innerHTML = `
                                <span class="badge bg-secondary text-white px-2 py-1 rounded-pill">
                                    <i class="bi bi-x-circle-fill me-1"></i>Inactivo
                                </span>
                            `;
                        }
                    }

                    // 3. Actualizar el botón de alternar estado dentro del contenedor
                    const toggleWrapper = document.getElementById(`toggle-wrapper-${data.perfil_id}`);
                    if (toggleWrapper) {
                        const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
                        if (data.activo) {
                            toggleWrapper.innerHTML = `
                                <form method="POST" action="${form.action}" class="d-inline form-toggle-estado form-ajax" data-ajax="true" data-perfil-id="${data.perfil_id}" data-nombre="${escapeHtml(data.nombre)}">
                                    <input type="hidden" name="csrfmiddlewaretoken" value="${csrfToken}">
                                    <input type="hidden" name="accion" value="desactivar">
                                    <input type="hidden" name="perfil_id" value="${data.perfil_id}">
                                    <button type="submit" class="btn btn-outline-warning btn-action-icon" title="Desactivar colaborador">
                                        <i class="bi bi-pause-fill text-warning" style="font-size: 0.95rem;"></i>
                                    </button>
                                </form>
                            `;
                        } else {
                            toggleWrapper.innerHTML = `
                                <form method="POST" action="${form.action}" class="d-inline form-toggle-estado form-ajax" data-ajax="true" data-perfil-id="${data.perfil_id}" data-nombre="${escapeHtml(data.nombre)}">
                                    <input type="hidden" name="csrfmiddlewaretoken" value="${csrfToken}">
                                    <input type="hidden" name="accion" value="activar">
                                    <input type="hidden" name="perfil_id" value="${data.perfil_id}">
                                    <button type="submit" class="btn btn-outline-success btn-action-icon" title="Reactivar colaborador">
                                        <i class="bi bi-play-fill text-success" style="font-size: 0.95rem;"></i>
                                    </button>
                                </form>
                            `;
                        }
                    }
                }

                // 4. Actualizar contador KPI de personal activo
                const kpiPersonalActivo = document.getElementById('kpiPersonalActivo');
                if (kpiPersonalActivo && data.total_activos !== undefined) {
                    kpiPersonalActivo.textContent = data.total_activos;
                }

                // 5. Re-evaluar filtros sin mover el scroll
                filtrarTrabajadores();

                // 6. Notificación SweetAlert Toast con estilos Bootstrap
                swalToast.fire({
                    icon: 'success',
                    title: data.mensaje || 'Estado actualizado con éxito.'
                });
            } else {
                swalDangerBootstrap.fire({
                    icon: 'error',
                    title: 'No se pudo actualizar',
                    text: data.mensaje || 'Ocurrió un error inesperado al actualizar el estado.'
                });
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnHtml;
                }
            }
        })
        .catch(err => {
            console.error('Error al cambiar estado:', err);
            swalDangerBootstrap.fire({
                icon: 'error',
                title: 'Error de conexión',
                text: 'No fue posible comunicarse con el servidor.'
            });
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnHtml;
            }
        });
    }

    // Delegación de eventos para confirmaciones con SweetAlert2 Bootstrap
    const tbodyTrabajadores = document.getElementById('tbodyTrabajadores');
    if (tbodyTrabajadores) {
        tbodyTrabajadores.addEventListener('submit', function (event) {
            // 1. Manejo de Activar / Desactivar con SweetAlert2
            const formToggle = event.target.closest('.form-toggle-estado');
            if (formToggle) {
                event.preventDefault();
                const accion = formToggle.querySelector('input[name="accion"]')?.value;
                const nombre = formToggle.getAttribute('data-nombre') || 'este colaborador';

                if (accion === 'desactivar') {
                    swalWarningBootstrap.fire({
                        title: "¿Desactivar colaborador?",
                        html: `¿Seguro que deseas desactivar a <strong>${nombre}</strong>?<br><span class="text-muted small">El colaborador quedará inhabilitado para iniciar sesión o abrir turnos.</span>`,
                        icon: "warning",
                        showCancelButton: true,
                        confirmButtonText: '<i class="bi bi-pause-fill me-1"></i> Sí, desactivar',
                        cancelButtonText: '<i class="bi bi-x-circle me-1"></i> Cancelar',
                        reverseButtons: true
                    }).then((result) => {
                        if (result.isConfirmed) {
                            ejecutarToggleEstado(formToggle);
                        }
                    });
                } else if (accion === 'activar') {
                    swalWithBootstrapButtons.fire({
                        title: "¿Reactivar colaborador?",
                        html: `¿Deseas reactivar el acceso al sistema para <strong>${nombre}</strong>?<br><span class="text-muted small">El colaborador volverá a estar habilitado para sus labores.</span>`,
                        icon: "question",
                        showCancelButton: true,
                        confirmButtonText: '<i class="bi bi-play-fill me-1"></i> Sí, reactivar',
                        cancelButtonText: '<i class="bi bi-x-circle me-1"></i> Cancelar',
                        reverseButtons: true
                    }).then((result) => {
                        if (result.isConfirmed) {
                            ejecutarToggleEstado(formToggle);
                        }
                    });
                }
                return;
            }

            // 2. Manejo de Eliminar con SweetAlert2 Bootstrap
            const formEliminar = event.target.closest('.form-eliminar-trabajador');
            if (formEliminar && !formEliminar.dataset.confirmado) {
                event.preventDefault();
                const nombre = formEliminar.getAttribute('data-nombre') || 'este colaborador';

                swalDangerBootstrap.fire({
                    title: "¿Eliminar definitivamente?",
                    html: `¿Estás seguro de eliminar a <strong>${nombre}</strong>?<br><span class="text-danger fw-bold"><i class="bi bi-exclamation-triangle-fill me-1"></i>Esta acción es irreversible y borrará la cuenta de usuario del sistema.</span>`,
                    icon: "error",
                    showCancelButton: true,
                    confirmButtonText: '<i class="bi bi-trash-fill me-1"></i> Sí, eliminar definitivamente',
                    cancelButtonText: '<i class="bi bi-x-circle me-1"></i> Cancelar',
                    reverseButtons: true
                }).then((result) => {
                    if (result.isConfirmed) {
                        formEliminar.dataset.confirmado = "true";
                        sessionStorage.setItem('admin_trabajadores_scroll', window.scrollY.toString());
                        formEliminar.submit();
                    }
                });
            }
        });
    }

    // Preservación de Scroll para formularios estándar (crear, editar, trasladar)
    document.querySelectorAll('form').forEach(f => {
        f.addEventListener('submit', function () {
            if (!this.classList.contains('form-ajax') && this.dataset.ajax !== 'true') {
                sessionStorage.setItem('admin_trabajadores_scroll', window.scrollY.toString());
            }
        });
    });

    // Ejecución inicial de filtrado
    filtrarTrabajadores();
});
