# Plataforma de Quiz & Treino Corporativo 🏆

Esta aplicação web, desenvolvida em **Python** (Flask), é uma solução de *gamification* para empresas. O sistema permite criar trilhas de conhecimento, quizzes competitivos entre departamentos e atividades discursivas com correção manual, fomentando a aprendizagem contínua e o espírito de equipa.

## 🚀 Funcionalidades Principais

O sistema divide-se em dois perfis de acesso:

### 👤 Área do Colaborador (Utilizador)
* **Dashboard Personalizada:** Visualização de tarefas pendentes (Quizzes e Atividades) e *feedbacks* não lidos.
* **Quizzes Gamificados:** Perguntas de escolha múltipla ou verdadeiro/falso com temporizador.
* **Atividades Discursivas:** Respostas de texto com suporte para envio de anexos (imagens/documentos).
* **Ranking em Tempo Real:** Tabela de classificação competitiva entre Departamentos (Pontuação Proporcional).
* **Histórico:** Visualização das próprias respostas e *feedbacks* recebidos.

### 🛡️ Área Administrativa (Gestão)
* **Gestão de Conteúdos:** CRUD completo de perguntas com suporte a imagens (via Cloudinary) e categorias.
* **Importação em Massa:** Carregamento de perguntas via ficheiros Excel ou CSV.
* **Correção de Atividades:** Interface para avaliar respostas discursivas, atribuir notas e enviar *feedback* individual.
* **Gestão de Pessoas:** Controlo de Utilizadores, Departamentos e Administradores.
* **Analytics e Relatórios:** Gráficos de desempenho e exportação de dados detalhados em Excel.
* **Notificações:** Envio de alertas por e-mail sobre novos conteúdos.

## 🛠️ Tecnologias Utilizadas

* **Backend:** Python 3, Flask, SQLAlchemy.
* **Base de Dados:** SQLite (padrão local) ou PostgreSQL/MySQL.
* **Armazenamento de Arquivos:** Cloudinary (para imagens de perguntas e anexos).
* **Frontend:** HTML5, CSS3, JavaScript (Jinja2 Templates).
* **Bibliotecas:** `pandas` (manipulação de dados), `flask-mail` (envio de e-mails).

## ⚙️ Instalação e Configuração

### 1. Preparar o Ambiente

Clone o repositório e instale as dependências:

```bash
git clone https://teu-repositorio/quiz-empresa.git
cd quiz-empresa
pip install -r requirements.txt
```
### 2. Variáveis de Ambiente
O projeto utiliza o ficheiro `config.py`. Podes definir as variáveis de ambiente ou editar os valores padrão no ficheiro `config.py` (para testes locais).
As principais variáveis são:

* **DATABASE_URL:** Caminho do banco de dados (ex: `sqlite:///quiz.db`).
* **CLOUDINARY_...:** Credenciais (`CLOUD_NAME`, `API_KEY`, `API_SECRET`).
* **MAIL_...:** Configurações SMTP para notificações.
* **SECRET_KEY:** Chave de segurança da aplicação.

### 3. Inicialização da Base de Dados
Antes de executar a aplicação, é necessário criar a estrutura do banco e popular com dados iniciais. Execute os scripts na ordem:

1.  **Criar tabelas e departamentos:**
    ```bash
    python inicializar_banco.py
    ```

2.  **Criar o primeiro Administrador:**
    ```bash
    python criar_primeiro_admin.py
    ```

## ▶️ Como Executar
Após a configuração, inicie o servidor:

```bash
python run.py

Aceda ao navegador em: `http://127.0.0.1:5000`
```
## 📂 Estrutura do Projeto
* `app/`: Código fonte (Models, Routes, Templates).
    * `routes/admin.py`: Painel administrativo.
    * `routes/user.py`: Área do colaborador.
* `config.py`: Configurações gerais.
* `inicializar_banco.py`: Script de setup da BD.
* `criar_primeiro_admin.py`: Script de criação de admin.
* `requirements.txt`: Dependências do projeto.
