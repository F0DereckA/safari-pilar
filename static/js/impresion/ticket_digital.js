document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-safari-action="print"]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            window.print();
        });
    });

    document.querySelectorAll('[data-safari-action="back"]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            window.history.back();
        });
    });

    if (typeof window.bootstrap === 'undefined') {
        document.querySelectorAll('[data-bs-toggle="collapse"]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var targetSel = btn.getAttribute('data-bs-target');
                if (!targetSel) return;
                var target = document.querySelector(targetSel);
                if (!target) return;
                var opened = target.classList.toggle('show');
                btn.setAttribute('aria-expanded', opened ? 'true' : 'false');
            });
        });
    }

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('auto_print') === '1') {
        setTimeout(function() {
            window.print();
        }, 500);
    }
});
