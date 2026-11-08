function togglePass(inputId, btn) {
    const input = document.getElementById(inputId);
    const icon = btn.querySelector('i');
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.replace('bi-eye', 'bi-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.replace('bi-eye-slash', 'bi-eye');
    }
}

const inputNueva = document.getElementById('nuevaClave');
const inputConfirmar = document.getElementById('confirmarClave');
const matchNotice = document.getElementById('matchNotice');
const matchSuccess = document.getElementById('matchSuccess');
const btnGuardar = document.getElementById('btnGuardarClave');
const barFortaleza = document.getElementById('barFortaleza');
const txtFortaleza = document.getElementById('txtFortaleza');

// Validación dinámica reactiva por cada tecleo
inputNueva.addEventListener('input', validarFormulario);
inputConfirmar.addEventListener('input', validarFormulario);

function updateRule(elementId, isValid) {
    const el = document.getElementById(elementId);
    const icon = el.querySelector('i');
    if (isValid) {
        el.className = 'rule-item valid';
        icon.className = 'bi bi-check-circle-fill text-success';
    } else {
        el.className = 'rule-item invalid';
        icon.className = 'bi bi-circle';
    }
}

function validarFormulario() {
    const val = inputNueva.value;
    const conf = inputConfirmar.value;

    const rLength = val.length >= 8;
    const rUpper = /[A-Z]/.test(val);
    const rLower = /[a-z]/.test(val);
    const rNumber = /[0-9]/.test(val);
    const rSymbol = /[!@#$%^&*(),.?":{}|<>\-_+=\[\]\\/`~;]/.test(val);

    updateRule('ruleLength', rLength);
    updateRule('ruleUpper', rUpper);
    updateRule('ruleLower', rLower);
    updateRule('ruleNumber', rNumber);
    updateRule('ruleSymbol', rSymbol);

    // Conteo de requisitos cumplidos (0 a 5)
    let cumplidos = 0;
    if (rLength) cumplidos++;
    if (rUpper) cumplidos++;
    if (rLower) cumplidos++;
    if (rNumber) cumplidos++;
    if (rSymbol) cumplidos++;

    // Actualizar barra y texto de fortaleza
    const porcentaje = cumplidos * 20;
    barFortaleza.style.width = porcentaje + '%';

    if (cumplidos <= 1) {
        barFortaleza.className = 'progress-bar bg-danger';
        txtFortaleza.innerText = `${cumplidos}/5 - Muy débil`;
        txtFortaleza.style.color = '#dc2626';
    } else if (cumplidos <= 3) {
        barFortaleza.className = 'progress-bar bg-warning';
        txtFortaleza.innerText = `${cumplidos}/5 - Intermedia`;
        txtFortaleza.style.color = '#d97706';
    } else if (cumplidos === 4) {
        barFortaleza.className = 'progress-bar bg-info';
        txtFortaleza.innerText = `${cumplidos}/5 - Buena`;
        txtFortaleza.style.color = '#0284c7';
    } else {
        barFortaleza.className = 'progress-bar bg-success';
        txtFortaleza.innerText = `5/5 - ¡Robusta y Segura!`;
        txtFortaleza.style.color = '#16a34a';
    }

    // Comprobar coincidencia
    let coinciden = false;
    if (conf.length > 0) {
        if (conf === val && val.length > 0) {
            matchSuccess.classList.remove('d-none');
            matchNotice.classList.add('d-none');
            coinciden = true;
        } else {
            matchNotice.classList.remove('d-none');
            matchSuccess.classList.add('d-none');
            coinciden = false;
        }
    } else {
        matchNotice.classList.add('d-none');
        matchSuccess.classList.add('d-none');
    }

    // Activar botón solo si se cumplen los 5 requisitos y las contraseñas coinciden
    if (cumplidos === 5 && coinciden) {
        btnGuardar.disabled = false;
        btnGuardar.style.opacity = '1';
        btnGuardar.classList.add('shadow');
    } else {
        btnGuardar.disabled = true;
        btnGuardar.style.opacity = '0.65';
        btnGuardar.classList.remove('shadow');
    }
}
