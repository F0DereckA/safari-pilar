const buscador = document.getElementById('buscadorConvenios');
buscador.addEventListener('input', function() {
    const query = this.value.toLowerCase().trim();
    const filas = document.querySelectorAll('.fila-convenio');
    filas.forEach(fila => {
        const texto = fila.textContent.toLowerCase();
        fila.style.display = texto.includes(query) ? '' : 'none';
    });
});
