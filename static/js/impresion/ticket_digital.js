document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('auto_print') === '1') {
        setTimeout(function() {
            window.print();
        }, 500);
    }
});
