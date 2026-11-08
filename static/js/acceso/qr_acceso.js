function copiarUrl() {
    navigator.clipboard.writeText("http://192.168.1.6:8000/").then(function() {
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
