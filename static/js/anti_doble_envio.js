/**
 * Venta Safari - Protección contra Doble Envío (Double Submit Prevention)
 * Deshabilita los botones de envío inmediatamente al procesar formularios POST
 * y muestra retroalimentación visual (spinner) evitando duplicación de registros.
 */
document.addEventListener('DOMContentLoaded', function () {
    const forms = document.querySelectorAll('form[method="POST"], form[method="post"]');

    forms.forEach(function (form) {
        form.addEventListener('submit', function (event) {
            // Ignorar formularios asíncronos (AJAX) que gestionan su propio ciclo de vida
            if (form.dataset.ajax === 'true' || form.classList.contains('form-ajax')) {
                return;
            }

            // Verificar si el formulario ya está en proceso de envío
            if (form.dataset.enviando === 'true') {
                event.preventDefault();
                event.stopPropagation();
                return false;
            }

            // Si el formulario falla la validación HTML5, no bloquear
            if (!form.checkValidity()) {
                return;
            }

            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn) {
                form.dataset.enviando = 'true';
                submitBtn.dataset.originalContent = submitBtn.innerHTML;

                // Bloqueo y estado visual en el siguiente microtick
                setTimeout(function () {
                    submitBtn.disabled = true;
                    submitBtn.classList.add('disabled');
                    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Procesando...';
                }, 10);

                // Timeout de seguridad: si no ha habido redirección en 8 segundos, restaurar botón
                setTimeout(function () {
                    form.dataset.enviando = 'false';
                    submitBtn.disabled = false;
                    submitBtn.classList.remove('disabled');
                    if (submitBtn.dataset.originalContent) {
                        submitBtn.innerHTML = submitBtn.dataset.originalContent;
                    }
                }, 8000);
            }
        });
    });
});
