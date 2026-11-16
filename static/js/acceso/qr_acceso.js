function copiarUrl() {
    const btnCopiar = document.getElementById('btnCopiarUrl');
    const urlDestino = (btnCopiar && btnCopiar.dataset.url) ? btnCopiar.dataset.url : `${window.location.origin}/`;
    navigator.clipboard.writeText(urlDestino).then(function() {
        const icon = document.getElementById('iconCopy');
        const text = document.getElementById('textCopy');
        icon.className = 'bi bi-check2-circle me-1';
        text.innerText = '¡Copiado!';
        setTimeout(function() {
            icon.className = 'bi bi-clipboard me-1';
            text.innerText = 'Copiar Enlace';
        }, 2500);
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const btnCopiar = document.getElementById('btnCopiarUrl');
    if (btnCopiar) {
        btnCopiar.addEventListener('click', copiarUrl);
    }
});
