// static/js/acceso/login.js
// Manejo seguro del portal de acceso conforme a Norma ISO/IEC 27400

document.addEventListener('DOMContentLoaded', function() {
    // 1. Toggle de visibilidad de contraseña (ojo tachado / visible)
    const btnToggle = document.getElementById('btnToggleClave');
    if (btnToggle) {
        btnToggle.addEventListener('click', function() {
            const passInput = document.getElementById('id_password');
            const icon = document.getElementById('iconoOjoClave');
            if (passInput) {
                if (passInput.type === 'password') {
                    passInput.type = 'text';
                    if (icon) icon.className = 'bi bi-eye';
                } else {
                    passInput.type = 'password';
                    if (icon) icon.className = 'bi bi-eye-slash';
                }
            }
        });
    }

    // 2. Selección rápida e ingreso 1 Clic para evaluación docente
    document.querySelectorAll('.btn-demo-user').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const user = this.getAttribute('data-user');
            const userInp = document.getElementById('id_username');
            const passInp = document.getElementById('id_password');
            const form = document.getElementById('formLoginFormal');
            if (userInp && user) {
                userInp.value = user;
            }
            if (passInp) {
                passInp.value = 'safari123';
            }
            if (form) {
                form.submit();
            }
        });
    });

    // 3. Ingreso directo a terminales operativas de pantalla (Cocina / Barra)
    document.querySelectorAll('.btn-demo-direct').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const user = this.getAttribute('data-user');
            const destino = this.getAttribute('data-destino');
            const userInp = document.getElementById('id_username');
            const nextInp = document.getElementById('id_next');
            const passInp = document.getElementById('id_password');
            const form = document.getElementById('formLoginFormal');

            if (userInp && user) userInp.value = user;
            if (nextInp && destino) nextInp.value = destino;
            if (passInp) passInp.value = 'safari123';
            if (form) {
                form.submit();
            }
        });
    });

    // 4. Inicializar toasts automáticos en la esquina
    document.querySelectorAll('.toast-container .toast').forEach(function(el) {
        const toast = new bootstrap.Toast(el, { delay: 4500 });
        toast.show();
        setTimeout(function() {
            try { toast.hide(); } catch(e){}
        }, 4500);
    });
});
