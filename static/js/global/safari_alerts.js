/**
 * Safari Pilar - SweetAlert2 configurado con clases y estilos de Bootstrap 5
 * Reemplaza los popups nativos del navegador por modales estilizados, accesibles y modernos.
 */

// Instancia estándar con botones de Bootstrap
const swalWithBootstrapButtons = Swal.mixin({
    customClass: {
        confirmButton: "btn btn-success px-4 py-2 rounded-pill fw-bold mx-2 shadow-sm",
        cancelButton: "btn btn-danger px-4 py-2 rounded-pill fw-bold mx-2 shadow-sm",
        actions: "gap-2 my-2"
    },
    buttonsStyling: false
});

// Instancia para acciones destructivas / eliminar
const swalDangerBootstrap = Swal.mixin({
    customClass: {
        confirmButton: "btn btn-danger px-4 py-2 rounded-pill fw-bold mx-2 shadow-sm",
        cancelButton: "btn btn-secondary px-4 py-2 rounded-pill fw-bold mx-2 shadow-sm",
        actions: "gap-2 my-2"
    },
    buttonsStyling: false
});

// Instancia para advertencias / pausar o desactivar
const swalWarningBootstrap = Swal.mixin({
    customClass: {
        confirmButton: "btn btn-warning text-dark px-4 py-2 rounded-pill fw-bold mx-2 shadow-sm",
        cancelButton: "btn btn-secondary px-4 py-2 rounded-pill fw-bold mx-2 shadow-sm",
        actions: "gap-2 my-2"
    },
    buttonsStyling: false
});

// Toast flotante elegante en la esquina superior derecha
const swalToast = Swal.mixin({
    toast: true,
    position: "top-end",
    showConfirmButton: false,
    timer: 3500,
    timerProgressBar: true,
    didOpen: (toast) => {
        toast.onmouseenter = Swal.stopTimer;
        toast.onmouseleave = Swal.resumeTimer;
    }
});
