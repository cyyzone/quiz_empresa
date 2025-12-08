document.addEventListener('DOMContentLoaded', function () {
    
    // --- 1. Lógica para Fechar Alertas Automaticamente ---
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function (alert) {
        const autoDismiss = setTimeout(function () {
            alert.classList.add('fade-out');
            setTimeout(() => { if(alert) alert.style.display = 'none'; }, 500);
        }, 5000);
        const closeButton = alert.querySelector('.close-alert-btn');
        if (closeButton) {
            closeButton.addEventListener('click', function () {
                clearTimeout(autoDismiss);
                alert.classList.add('fade-out');
                setTimeout(() => { if(alert) alert.style.display = 'none'; }, 500);
            });
        }
    });

    // --- 2. Lógica do Modal de Ajuda ---
    const modal = document.getElementById('help-modal');
    if (modal) {
        const modalContent = document.getElementById('modal-text-content');
        const closeModalBtn = modal.querySelector('.close-modal-btn');

        function closeModal() {
            if(modal) modal.style.display = 'none';
        }

        document.querySelectorAll('.open-help-modal').forEach(button => {
            button.addEventListener('click', function() {
                const helpText = this.dataset.helpText;
                modalContent.textContent = helpText;
                modal.style.display = 'flex';
            });
        });

        if(closeModalBtn) closeModalBtn.addEventListener('click', closeModal);
        modal.addEventListener('click', function(event) {
            if (event.target === modal) {
                closeModal();
            }
        });
    }

    // --- 3. Feedback de Carregamento (Loading) ---
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const btn = form.querySelector('button[type="submit"]');
            if (btn && !btn.classList.contains('no-loading')) {
                // Evita clique duplo
                setTimeout(() => { btn.disabled = true; }, 0); 
                
                // Muda o texto e estilo
                btn.dataset.originalText = btn.innerText;
                btn.innerText = "Processando... ⌛";
                btn.style.opacity = "0.7";
                btn.style.cursor = "wait";
            }
        });
    });

});