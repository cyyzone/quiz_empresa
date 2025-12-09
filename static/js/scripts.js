document.addEventListener('DOMContentLoaded', function () {

    // --- 1. Lógica para Fechar Alertas (Melhorada) ---
    // Usamos "Event Delegation" para funcionar também nos novos popups criados dinamicamente
    document.addEventListener('click', function (event) {
        // Verifica se clicou num botão de fechar (ou no X dentro dele)
        if (event.target.closest('.close-alert-btn')) {
            const alert = event.target.closest('.alert');
            if (alert) {
                alert.style.opacity = '0'; // Efeito visual de desaparecimento
                setTimeout(() => { alert.style.display = 'none'; }, 500);
            }
        }
    });

    // Auto-dismiss para alertas que já vieram do servidor (Sucesso/Erro)
    const existingAlerts = document.querySelectorAll('.alert');
    existingAlerts.forEach(function (alert) {
        // Só fecha automaticamente se NÃO for o de processando (opcional)
        if (!alert.classList.contains('alert-info')) {
            setTimeout(function () {
                alert.style.opacity = '0';
                setTimeout(() => { if (alert) alert.style.display = 'none'; }, 500);
            }, 5000);
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
            if (event.target === modal) closeModal();
        });
    }

    // --- 3. Feedback de Processamento (Popup Azul) ---
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            // Verifica se o formulário é válido antes de mostrar o aviso
            if (!form.checkValidity()) return;

            const alertContainer = document.querySelector('.alert-container');
            
            // Procura TODOS os botões de submit do formulário (importante para o Quiz)
            const btns = form.querySelectorAll('button[type="submit"]');
            
            // Se houver botões e não for uma ação silenciosa (no-loading)
            if (btns.length > 0 && !form.classList.contains('no-loading-form')) {
                
                // 1. Bloqueia todos os botões para evitar clique duplo
                // O setTimeout(0) garante que o dado do botão clicado (A, B, C...) seja enviado antes de desativar
                setTimeout(() => { 
                    btns.forEach(btn => btn.disabled = true);
                }, 0);

                // 2. Mostra o Popup se o container existir
                if (alertContainer) {
                    alertContainer.innerHTML = ''; // Limpa alertas anteriores

                    const loadingAlert = document.createElement('div');
                    loadingAlert.className = 'alert alert-info';
                    // Adicionamos explicitamente o botão "X" aqui
                    loadingAlert.innerHTML = `
                        <strong>Processando...</strong> Por favor, aguarde. ⌛
                        <button class="close-alert-btn" type="button" style="font-size: 24px; position: absolute; right: 15px; top: 50%; transform: translateY(-50%); border: none; background: none; cursor: pointer;">&times;</button>
                    `;
                    
                    alertContainer.appendChild(loadingAlert);
                }
            }
        });
    });

});