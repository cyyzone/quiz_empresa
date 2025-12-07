# --- INÍCIO DAS IMPORTAÇÕES: Ferramentas que meu projeto precisa ---
from flask import Flask, render_template, request, redirect, url_for, session, flash # Importo as ferramentas principais do Flask para criar as páginas,lidar com formulários, redirecionar usuários e gerenciar sessões. 
from flask_sqlalchemy import SQLAlchemy # Importo o SQLAlchemy para conectar e conversar com meu banco de dados usando Python.
from sqlalchemy.sql import func, case # Importo funções específicas do SQLAlchemy para fazer cálculos (como somas e contagens), e criar lógicas condicionais (case) e de OU (or_) nas buscas ao banco.
from sqlalchemy import or_
from collections import defaultdict # Importo o defaultdict, uma ferramenta útil para agrupar dados (como os erros por setor).
from datetime import date, datetime, timedelta # Importo as ferramentas de data e hora do Python para lidar com agendamentos e timestamps.
import os # Importo o módulo 'os' para interagir com o sistema de arquivos (ex: criar caminhos de pastas).
import io # Importo 'io' para manipular arquivos em memória, essencial para a exportação para Excel.
import pandas as pd # Importo a biblioteca 'pandas' para ler e criar as planilhas Excel (.xlsx) na importação/exportação.
from werkzeug.utils import secure_filename # Importo uma função de segurança para garantir que os nomes de arquivos enviados sejam seguros.
import cloudinary # Importo a biblioteca do Cloudinary para fazer o upload de imagens e anexos para a nuvem.
import cloudinary.uploader
from flask import send_file # Importo a função 'send_file', que é a ferramenta especial do Flask  para enviar arquivos (como a minha planilha Excel) para o navegador do usuário,  forçando o início de um download.
# --- FIM DAS IMPORTAÇÕES ---

app = Flask(__name__) # Crio a instância principal da minha aplicação Flask. A variável 'app' é o coração do meu projeto.


# --- CONFIGURAÇÕES GERAIS ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma-chave-secreta-local-muito-dificil') # Configuro uma chave secreta para a minha aplicação. Ela é usada pelo Flask para proteger os dados da sessão do usuário (como o login) contra manipulação. O código primeiro tenta pegar uma chave segura do ambiente do servidor (no Render).Se não encontrar, ele usa uma chave padrão para o meu ambiente local.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///quiz.db') # Defino onde meu banco de dados está. Da mesma forma, ele primeiro procura uma URL de banco de dados no ambiente do servidor (o PostgreSQL do Render).Se não encontrar, ele usa o arquivo 'quiz.db' local (SQLite) como padrão.Isso faz com que o mesmo código funcione tanto na nuvem quanto no meu computador.
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False #Desativo uma funcionalidade do SQLAlchemy que rastreia modificações e emite sinais. Fazer isso economiza recursos e é a configuração recomendada.
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'xls', 'xlsx'} # Crio uma "lista branca" de extensões de arquivo que eu permito que sejam enviadas para a minha aplicação. Isso aumenta a segurança, impedindo o upload de arquivos perigosos.
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
# A opção 'pool_pre_ping' ajuda a manter a conexão com o banco de dados estável, verificando se a conexão ainda está ativa antes de usá-la. Isso é especialmente útil em ambientes de nuvem onde conexões podem expirar.
# --- CONFIGURAÇÃO DO CLOUDINARY (Lê das Variáveis de Ambiente) ---
# Aqui, eu preparo a conexão da minha aplicação com o serviço do Cloudinary,que é o "HD externo na nuvem" onde eu guardo minhas imagens e anexos.
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'), # Eu digo ao Cloudinary qual é o "nome da minha nuvem", ou seja, minha conta. A instrução 'os.environ.get(...)' busca essa informação de forma segura das Variáveis de Ambiente do meu servidor (como o Render).
    api_key = os.environ.get('CLOUDINARY_API_KEY'), # Esta é a minha "chave de acesso pública". É como se fosse o meu nome de usuário para a API do Cloudinary. Também a busco de forma segura do ambiente.
    api_secret = os.environ.get('CLOUDINARY_API_SECRET') # Esta é a minha "chave secreta". É a senha que prova para o Cloudinary que sou eu mesmo, autorizando minha aplicação a enviar e apagar arquivos. É a informação mais sensível, e por isso é essencial que ela venha do ambiente.
)

# --- INICIALIZAÇÕES ---
db = SQLAlchemy(app) # Crio a instância principal do SQLAlchemy e a conecto com a minha aplicação Flask (app). A variável 'db' se torna a minha principal ferramenta para interagir com o banco de dados:criar tabelas, buscar dados, salvar informações, etc.
SENHA_ADMIN = "admin123"

# --- TABELA DE LIGAÇÃO (MUITOS-PARA-MUITOS) ---
pergunta_departamento_association = db.Table('pergunta_departamento', # Aqui eu crio uma "tabela de ligação" especial, que não tem uma classe de modelo própria.A função dela é servir como uma ponte entre as minhas perguntas e os meus departamentos,permitindo que uma única pergunta possa ser associada a vários departamentos, e que um departamento possa ter várias perguntas (uma relação "muitos-para-muitos").
    db.Column('pergunta_id', db.Integer, db.ForeignKey('pergunta.id'), primary_key=True),  # A primeira coluna guarda o ID da pergunta. É uma "chave estrangeira" que aponta para a tabela 'pergunta'.
    db.Column('departamento_id', db.Integer, db.ForeignKey('departamento.id'), primary_key=True)  # A segunda coluna guarda o ID do departamento. É uma "chave estrangeira" que aponta para a tabela 'departamento'.
)

# --- MODELOS DO BANCO DE DADOS ---
# Nesta seção, eu defino a "planta" de cada tabela do meu banco de dados. Cada classe representa uma tabela e cada atributo dentro dela representa uma coluna.
class Departamento(db.Model): # Crio a tabela para guardar os setores da empresa.
    id = db.Column(db.Integer, primary_key=True) # A chave primária, um número único para cada setor.
    nome = db.Column(db.String(100), unique=True, nullable=False) # O nome do setor (ex: "Suporte"), não pode repetir nem ser vazio.
    usuarios = db.relationship('Usuario', backref='departamento', lazy=True) # Crio a relação com a tabela de usuários. Isso me permite acessar `departamento.usuarios` para ver uma lista de todos os usuários neste setor.

class Usuario(db.Model): # Crio a tabela para guardar as informações dos colaboradores.
    id = db.Column(db.Integer, primary_key=True) # A chave primária para cada usuário.
    nome = db.Column(db.String(100), nullable=False) # O nome do usuário, campo obrigatório.
    email = db.Column(db.String(120), unique=True, nullable=True) # O e-mail, que não pode se repetir, mas pode ser deixado em branco.
    codigo_acesso = db.Column(db.String(4), unique=True, nullable=False) # O código de 4 dígitos para login, não pode repetir.
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamento.id'), nullable=False) # Crio a "chave estrangeira" que conecta cada usuário a um departamento. Isso garante que todo usuário pertença a um setor.
    respostas = db.relationship('Resposta', backref='usuario', lazy=True) # Crio a relação com a tabela de respostas. Isso me permite acessar `usuario.respostas` para ver todas as respostas que este usuário já deu. O `backref='usuario'` cria o atalho `resposta.usuario` para acessar o usuário a partir de uma resposta.

class Pergunta(db.Model):  # Crio a tabela principal, que armazena todas as perguntas do quiz.
    id = db.Column(db.Integer, primary_key=True) # A chave primária para cada pergunta.
    tipo = db.Column(db.String(20), nullable=False, default='multipla_escolha') # O tipo da pergunta (ex: 'discursiva'), o padrão é múltipla escolha.
    texto = db.Column(db.Text, nullable=False) # O enunciado da pergunta.
    opcao_a = db.Column(db.Text, nullable=True)
    opcao_b = db.Column(db.Text, nullable=True)
    opcao_c = db.Column(db.Text, nullable=True)
    opcao_d = db.Column(db.Text, nullable=True)
    resposta_correta = db.Column(db.String(1), nullable=True) # A resposta correta ('a', 'b', 'v', etc.). Pode ser nula para perguntas discursivas.
    explicacao = db.Column(db.Text, nullable=True) # Explicação que aparece após responder
    data_liberacao = db.Column(db.Date, nullable=False) # A data a partir da qual a pergunta fica disponível.
    tempo_limite = db.Column(db.Integer, nullable=True) # O tempo limite para responder (em segundos). Pode ser nulo para perguntas discursivas.
    imagem_pergunta = db.Column(db.String(300), nullable=True) # O link da imagem da pergunta (do Cloudinary).
    para_todos_setores = db.Column(db.Boolean, default=False, nullable=False)     # Um campo booleano para marcar se a pergunta é para todos ou para setores específicos.
    departamentos = db.relationship('Departamento', secondary=pergunta_departamento_association, lazy='subquery', # Crio a relação "muitos-para-muitos" com a tabela de Departamentos, usando a 'tabela de ligação' que defini antes. Isso me permite acessar `pergunta.departamentos` para ver a lista de setores aos quais esta pergunta foi designada.
        backref=db.backref('perguntas', lazy=True))

class Resposta(db.Model): # Crio a tabela que guarda todas as respostas dadas pelos usuários.
    id = db.Column(db.Integer, primary_key=True) # A chave primária para cada resposta.
    pontos = db.Column(db.Integer, nullable=True) # A pontuação obtida na resposta. Pode ser nula para perguntas discursivas que ainda não foram corrigidas.
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False) # A "chave estrangeira" que conecta a resposta ao usuário que a deu.
    pergunta_id = db.Column(db.Integer, db.ForeignKey('pergunta.id'), nullable=False) # A "chave estrangeira" que conecta a resposta à pergunta correspondente.
    resposta_dada = db.Column(db.String(1), nullable=True)  # A resposta dada pelo usuário ('a', 'b', 'v', etc.). Pode ser nula para perguntas discursivas.
    data_resposta = db.Column(db.DateTime, default=datetime.utcnow) # A data e hora em que a resposta foi dada. O padrão é o momento atual (UTC).
    pergunta = db.relationship('Pergunta') # Crio a relação com a tabela de perguntas. Isso me permite acessar `resposta.pergunta` para ver os detalhes da pergunta associada a esta resposta.
    texto_discursivo = db.Column(db.Text, nullable=True)    # O texto da resposta para perguntas discursivas. Pode ser nulo para perguntas objetivas.
    anexo_resposta = db.Column(db.String(300), nullable=True) # O link do anexo da resposta (do Cloudinary). Pode ser nulo se não houver anexo.
    status_correcao = db.Column(db.String(20), nullable=False, default='nao_respondido') # O status da correção para perguntas discursivas. Pode ser 'pendente', 'correto', 'incorreto', etc.
    feedback_admin = db.Column(db.Text, nullable=True) # O feedback escrito pelo admin após corrigir uma pergunta discursiva. Pode ser nulo se ainda não foi corrigido.
    feedback_visto = db.Column(db.Boolean, default=False, nullable=False) # Um campo booleano para marcar se o usuário já viu o feedback do admin. O padrão é False (não visto).

# --- NOVOS MODELOS PARA MÚLTIPLOS ARQUIVOS ---

# No arquivo app.py

class ImagemPergunta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(300), nullable=False)
    pergunta_id = db.Column(db.Integer, db.ForeignKey('pergunta.id'), nullable=False)
    
    pergunta = db.relationship('Pergunta', backref=db.backref('imagens_extra', lazy=True, cascade='all, delete-orphan'))

class AnexoResposta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(300), nullable=False)
    resposta_id = db.Column(db.Integer, db.ForeignKey('resposta.id'), nullable=False)
    
    resposta = db.relationship('Resposta', backref=db.backref('anexos_extra', lazy=True, cascade='all, delete-orphan'))

# --- FUNÇÕES AUXILIARES ---
# Criei esta seção para agrupar pequenas funções que são reutilizadas em várias partes do meu projeto.

def allowed_file(filename):# Criei esta função para verificar se um arquivo que o usuário enviou tem uma extensão permitida.Ela checa se o nome do arquivo contém um '.' e se a extensão (a parte depois do último '.')está na minha lista 'ALLOWED_EXTENSIONS' que defini nas configurações. Isso é uma medida de segurança.
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS'] 

@app.template_filter('datetime_local')  #Criei este filtro personalizado para os meus templates HTML. A função dele é receber uma data que está no horário universal (UTC), subtrair 3 horas para ajustar para o meu fuso horário local (de Curitiba),e formatá-la de um jeito amigável (ex: '07/10/2025 às 19:50').O '@app.template_filter' me permite usar isso no HTML com a sintaxe 'minha_data | datetime_local'.
def format_datetime_local(valor_utc):
    """Filtro para converter uma data UTC para o fuso local (UTC-3) e formatá-la."""
    if not valor_utc:
        return ""
    # Subtrai 3 horas do tempo UTC
    fuso_local = valor_utc - timedelta(hours=3)
    return fuso_local.strftime('%d/%m/%Y às %H:%M')

def get_texto_da_opcao(pergunta, opcao): # Esta função recebe uma pergunta e uma letra de opção ('a', 'b', 'v', etc.) e retorna o texto completo daquela opção.É útil para mostrar tanto a resposta dada pelo usuário quanto a resposta correta em um formato legível.
    if opcao == 'a': return pergunta.opcao_a
    if opcao == 'b': return pergunta.opcao_b
    if opcao == 'c': return pergunta.opcao_c
    if opcao == 'd': return pergunta.opcao_d
    if opcao == 'v': return "Verdadeiro"
    if opcao == 'f': return "Falso"
    return ""

@app.context_processor #Este bloco torna a minha função 'get_texto_da_opcao' disponível para todos os meus arquivos HTML (templates) automaticamente. Assim, eu não preciso enviá-la manualmente em cada 'render_template'. Isso me permite chamar a função diretamente no HTML.
def utility_processor():
    return dict(get_texto_da_opcao=get_texto_da_opcao)

def validar_linha(row): # Esta é a função de validação para a importação de planilhas. Ela recebe uma linha da planilha (como um dicionário), verifica cada campo para garantir que os dados estão corretos (tipo válido, data no formato certo, etc.) e retorna se a linha é válida ou não, junto com um dicionário de erros apontando as células problemáticas.
    errors = {}
    if not row.get('texto'): errors['texto'] = "O texto não pode ser vazio."
    tipo = str(row.get('tipo') or '').lower()
    if tipo not in ['multipla_escolha', 'verdadeiro_falso', 'discursiva']:
        errors['tipo'] = "Tipo inválido."
    resposta = str(row.get('resposta_correta') or '').lower()
    if tipo == 'multipla_escolha' and resposta not in ['a', 'b', 'c', 'd']:
        errors['resposta_correta'] = "Deve ser a, b, c ou d."
    elif tipo == 'verdadeiro_falso' and resposta not in ['v', 'f']:
        errors['resposta_correta'] = "Deve ser v ou f."
    try:
        if isinstance(row.get('data_liberacao'), datetime):
             row['data_liberacao'] = row['data_liberacao'].strftime('%d/%m/%Y')
        datetime.strptime(str(row.get('data_liberacao', '')), '%d/%m/%Y').date()
    except (ValueError, TypeError):
        errors['data_liberacao'] = "Formato inválido. Use DD/MM/AAAA."
    if tipo != 'discursiva':
        try:
            int(float(row.get('tempo_limite', '')))
        except (ValueError, TypeError):
            errors['tempo_limite'] = "Deve ser um número."
    is_valid = not errors
    return is_valid, errors

def _gerar_dados_relatorio(departamento_id=None): # Esta é a função que gera os dados do relatório de desempenho dos usuários.Recebe um ID de departamento opcional para filtrar os resultados por setor.Se nenhum ID for fornecido, ela gera o relatório para todos os setores.
    """Função auxiliar que busca e processa os dados para o relatório."""
    query = db.session.query(
        Usuario.nome,
        Departamento.nome.label('setor_nome'),
        func.count(Resposta.id).label('total_respostas'),
        func.sum(case((or_(Resposta.pontos > 0, Resposta.status_correcao.in_(['correto', 'parcialmente_correto'])), 1), else_=0)).label('respostas_corretas'),
        func.coalesce(func.sum(Resposta.pontos), 0).label('pontuacao_total')
    ).select_from(Usuario).join(Departamento).outerjoin(Resposta).group_by(
        Usuario.id, Departamento.nome
    )

    if departamento_id:
        query = query.filter(Usuario.departamento_id == departamento_id)

    resultados = query.order_by(Usuario.nome).all()

    relatorios_finais = []
    for resultado in resultados:
        aproveitamento = (resultado.respostas_corretas / resultado.total_respostas) * 100 if resultado.total_respostas > 0 else 0
        relatorios_finais.append({
            'nome': resultado.nome,
            'setor': resultado.setor_nome,
            'total_respostas': resultado.total_respostas,
            'respostas_corretas': resultado.respostas_corretas,
            'aproveitamento': aproveitamento,
            'pontuacao_total': resultado.pontuacao_total
        })
    return relatorios_finais

# --- ROTAS PRINCIPAIS DO USUÁRIO ---
# Nesta seção, eu defino as páginas principais que os colaboradores podem acessar, como a tela de login, o painel principal (dashboard) e a tela do quiz.
@app.route('/') # Esta é a minha página inicial. Eu verifico se o usuário já está logado (olhando se o 'usuario_id' está na sessão). Se estiver, eu o redireciono para o dashboard. Se não, eu mostro a página de login.
def pagina_login():
    if 'usuario_id' in session: return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST']) # Esta rota processa o formulário de login. Eu pego o código de acesso que o usuário digitou, procuro no banco de dados por um usuário com esse código e, se encontrar, salvo o ID e o nome do usuário na sessão (para manter o login) e redireciono para o dashboard. Se não encontrar, mostro uma mensagem de erro e redireciono de volta para a página de login.
def processa_login():
    codigo_inserido = request.form['codigo']
    usuario = Usuario.query.filter_by(codigo_acesso=codigo_inserido).first()
    if usuario:
        session['usuario_id'], session['usuario_nome'] = usuario.id, usuario.nome
        return redirect(url_for('dashboard'))
    else:
        flash('Código de acesso inválido!', 'danger')
        return redirect(url_for('pagina_login'))


@app.route('/dashboard') # Esta é a rota para o painel principal (dashboard) do usuário. Eu verifico se o usuário está logado e, se não estiver, redireciono para a página de login.Se estiver logado, eu busco no banco de dados as contagens de perguntas pendentes (quiz rápido e atividades discursivas) e a contagem de novos feedbacks (respostas corrigidas que o usuário ainda não viu).Essas contagens são então passadas para o template 'dashboard.html' para serem exibidas ao usuário.
def dashboard():
    if 'usuario_id' not in session: 
        return redirect(url_for('pagina_login'))

    usuario_id = session['usuario_id']
    usuario = Usuario.query.get(usuario_id)
    hoje = date.today()
    
    perguntas_respondidas_ids = [r.pergunta_id for r in Resposta.query.filter_by(usuario_id=usuario_id).all()]
    # Contagem de Quizzes Rápidos Pendentes
    contagem_quiz_pendente = Pergunta.query.filter(
        Pergunta.tipo != 'discursiva',
        Pergunta.data_liberacao <= hoje,
        Pergunta.id.notin_(perguntas_respondidas_ids),
        or_(
            Pergunta.para_todos_setores == True,
            Pergunta.departamentos.any(Departamento.id == usuario.departamento_id)
        )
    ).count()

    # Contagem de Atividades Discursivas Pendentes 
    contagem_atividades_pendentes = Pergunta.query.filter(
        Pergunta.tipo == 'discursiva',
        Pergunta.data_liberacao <= hoje,
        Pergunta.id.notin_(perguntas_respondidas_ids),
        or_(
            Pergunta.para_todos_setores == True,
            Pergunta.departamentos.any(Departamento.id == usuario.departamento_id)
        )
    ).count()

    # Contagem de feedbacks agora verifica a nova coluna 'feedback_visto'
    contagem_novos_feedbacks = Resposta.query.join(Pergunta).filter(
        Resposta.usuario_id == usuario_id,
        Pergunta.tipo == 'discursiva',
        Resposta.status_correcao.in_(['correto', 'incorreto']),
        Resposta.feedback_visto == False  # Só conta se ainda não foi visto
    ).count()
    
    return render_template('dashboard.html', 
                           nome=session['usuario_nome'],
                           contagem_quiz=contagem_quiz_pendente,
                           contagem_atividades=contagem_atividades_pendentes,
                           contagem_feedbacks=contagem_novos_feedbacks)

@app.route('/logout') # Esta rota faz o logout do usuário. Ela simplesmente limpa a sessão (removendo o 'usuario_id' e 'usuario_nome') e redireciona de volta para a página de login.
def logout():
    session.clear()
    return redirect(url_for('pagina_login'))

@app.route('/quiz') # Esta é a rota para a página do quiz rápido. Eu verifico se o usuário está logado e, se não estiver, redireciono para a página de login.Se estiver logado, eu busco a próxima pergunta disponível que o usuário ainda não respondeu (considerando o setor dele e a data de liberação).Se encontrar uma pergunta, eu a passo para o template 'quiz.html' para ser exibida. Se não houver mais perguntas disponíveis, eu mostro uma mensagem de parabéns e redireciono de volta para o dashboard.
def pagina_quiz():
    if 'usuario_id' not in session: return redirect(url_for('pagina_login'))
    usuario_id = session['usuario_id']
    usuario = Usuario.query.get(usuario_id)
    hoje = date.today()
    perguntas_respondidas_ids = [r.pergunta_id for r in Resposta.query.filter_by(usuario_id=usuario_id).all()]
    proxima_pergunta = Pergunta.query.filter(
        Pergunta.tipo != 'discursiva',
        Pergunta.data_liberacao <= hoje,
        Pergunta.id.notin_(perguntas_respondidas_ids),
        or_(
            Pergunta.para_todos_setores == True,
            Pergunta.departamentos.any(Departamento.id == usuario.departamento_id)
        )
    ).order_by(Pergunta.data_liberacao).first()
    if proxima_pergunta:
        return render_template('quiz.html', pergunta=proxima_pergunta)
    else:
        flash('Parabéns, você respondeu todas as perguntas de quiz rápido disponíveis para o seu setor!', 'success')
        return redirect(url_for('dashboard'))

@app.route('/atividades')  # Esta é a rota para a página de atividades discursivas. Eu verifico se o usuário está logado e, se não estiver, redireciono para a página de login.Se estiver logado, eu busco todas as perguntas do tipo 'discursiva' que já foram liberadas e que o usuário ainda não respondeu (considerando o setor dele).Eu também busco todas as respostas que o usuário já deu para essas perguntas, para poder mostrar o status (respondida ou não) na página.Então, eu passo as atividades e as respostas dadas para o template 'atividades.html' para serem exibidas ao usuário.
def pagina_atividades():
    if 'usuario_id' not in session: return redirect(url_for('pagina_login'))
    hoje = date.today()
    usuario_id = session['usuario_id']
    usuario = Usuario.query.get(usuario_id)
    atividades = Pergunta.query.filter(
        Pergunta.tipo == 'discursiva',
        Pergunta.data_liberacao <= hoje,
        or_(
            Pergunta.para_todos_setores == True,
            Pergunta.departamentos.any(Departamento.id == usuario.departamento_id)
        )
    ).order_by(Pergunta.data_liberacao.desc()).all()
    respostas_dadas = {r.pergunta_id: r for r in Resposta.query.filter_by(usuario_id=usuario_id).all()}
    return render_template('atividades.html', atividades=atividades, respostas_dadas=respostas_dadas)

@app.route('/atividade/<int:pergunta_id>', methods=['GET', 'POST'])
def responder_atividade(pergunta_id):
    if 'usuario_id' not in session: 
        return redirect(url_for('pagina_login'))

    pergunta = Pergunta.query.get_or_404(pergunta_id)

    if request.method == 'POST':
        texto_resposta = request.form['texto_discursivo']
        
        # 1. Cria e salva a resposta PRIMEIRO para gerar o ID
        # Precisamos do ID da resposta para vincular os anexos na tabela auxiliar
        nova_resposta = Resposta(
            usuario_id=session['usuario_id'],
            pergunta_id=pergunta.id,
            texto_discursivo=texto_resposta,
            status_correcao='pendente'
        )
        db.session.add(nova_resposta)
        db.session.commit()

        # ====================================================================
        # NOVA LÓGICA PARA MÚLTIPLOS ANEXOS
        # ====================================================================
        
        # Pega a LISTA de arquivos enviados (note o .getlist)
        arquivos = request.files.getlist('anexo_resposta')
        
        for file in arquivos:
            if file and file.filename != '' and allowed_file(file.filename):
                # Envia o arquivo para o Cloudinary
                upload_result = cloudinary.uploader.upload(file, resource_type="auto")
                anexo_url = upload_result.get('secure_url')
                
                # A) Compatibilidade: Se for o primeiro anexo, salva no campo antigo também
                # Isso garante que o sistema antigo continue mostrando pelo menos um anexo
                if not nova_resposta.anexo_resposta:
                    nova_resposta.anexo_resposta = anexo_url
                
                # B) Nova Tabela: Salva na tabela auxiliar de anexos
                novo_anexo = AnexoResposta(url=anexo_url, resposta=nova_resposta)
                db.session.add(novo_anexo)
        
        # Salva os anexos no banco
        db.session.commit()
        
        flash('Sua resposta foi enviada para avaliação!', 'success')
        return redirect(url_for('pagina_atividades'))

    # Se a requisição for GET, apenas mostra a página.
    return render_template('atividade_responder.html', pergunta=pergunta)

@app.route('/responder', methods=['POST'])
def processa_resposta():
    if 'usuario_id' not in session: return redirect(url_for('pagina_login'))
    
    pergunta_id = request.form['pergunta_id']
    resposta_usuario = request.form.get('resposta', '')
    
    pergunta = Pergunta.query.get(pergunta_id)
    pontos = 0
    resultado = '' # 'correto', 'incorreto' ou 'esgotado'

    # Verifica se o tempo esgotou
    if resposta_usuario == 'esgotado':
        resultado = 'esgotado'
        pontos = 0
    else:
        if pergunta.resposta_correta == resposta_usuario:
            tempo_restante = float(request.form['tempo_restante'])
            pontos = 100 + int(tempo_restante * 5)
            resultado = 'correto'
        else:
            resultado = 'incorreto'
            pontos = 0
    
    # Salva a resposta no banco
    nova_resposta = Resposta(
        pontos=pontos, 
        usuario_id=session['usuario_id'], 
        pergunta_id=pergunta_id, 
        resposta_dada=resposta_usuario, 
        status_correcao='correto' if pontos > 0 else 'incorreto'
    )
    db.session.add(nova_resposta)
    db.session.commit()
    
    # EM VEZ DE REDIRECIONAR, RENDERIZAMOS A TELA DE FEEDBACK
    # Passamos as variáveis necessárias para o template feedback_quiz.html
    return render_template('feedback_quiz.html', 
                           resultado=resultado, 
                           pontos=pontos, 
                           pergunta=pergunta)

@app.route('/minhas-respostas')
def minhas_respostas():
    if 'usuario_id' not in session: 
        return redirect(url_for('pagina_login'))

    usuario_id = session['usuario_id']

    # --- Lógica: Marcar feedbacks como vistos ---
    feedbacks_nao_vistos = Resposta.query.join(Pergunta).filter(
        Resposta.usuario_id == usuario_id,
        Pergunta.tipo == 'discursiva',
        Resposta.status_correcao.in_(['correto', 'incorreto', 'parcialmente_correto']),
        Resposta.feedback_visto == False
    ).all()

    if feedbacks_nao_vistos:
        for resposta in feedbacks_nao_vistos:
            resposta.feedback_visto = True
        db.session.commit()
    
    # Filtros
    filtro_tipo = request.args.get('filtro_tipo', '')
    filtro_resultado = request.args.get('filtro_resultado', '')

    query = Resposta.query.filter_by(usuario_id=usuario_id)

    if filtro_tipo:
        query = query.join(Pergunta).filter(Pergunta.tipo == filtro_tipo)

    if filtro_resultado == 'corretas':
        query = query.filter(or_(Resposta.pontos > 0, Resposta.status_correcao == 'correto'))
    elif filtro_resultado == 'parcialmente_corretas':
        query = query.filter(Resposta.status_correcao == 'parcialmente_correto')
    elif filtro_resultado == 'incorretas':
        query = query.filter(or_(Resposta.pontos == 0, Resposta.status_correcao == 'incorreto'))
    elif filtro_resultado == 'pendentes':
        query = query.filter(Resposta.status_correcao == 'pendente')
    
    respostas_usuario = query.order_by(Resposta.data_resposta.desc()).all()

    return render_template('minhas_respostas.html', 
                           respostas=respostas_usuario,
                           filtro_tipo=filtro_tipo,
                           filtro_resultado=filtro_resultado)


@app.route('/admin/relatorios/exportar_detalhado')
def exportar_respostas_detalhado():
    if not session.get('admin_logged_in'): 
        return redirect(url_for('pagina_admin'))

    depto_selecionado_id = request.args.get('departamento_id', type=int)
    usuario_selecionado_id = request.args.get('usuario_id', type=int)

    # Busca base de TODAS as respostas, juntando as informações necessárias
    query = Resposta.query.join(Usuario).join(Departamento).join(Pergunta)

    # Aplica os filtros de setor e/ou colaborador, se foram selecionados
    if depto_selecionado_id:
        query = query.filter(Usuario.departamento_id == depto_selecionado_id)
    if usuario_selecionado_id:
        query = query.filter(Resposta.usuario_id == usuario_selecionado_id)

    todas_as_respostas = query.order_by(Departamento.nome, Usuario.nome, Resposta.data_resposta).all()

    if not todas_as_respostas:
        flash("Nenhuma resposta encontrada para exportar com os filtros selecionados.", "warning")
        return redirect(url_for('pagina_analytics'))

    # Processa os dados para um formato unificado
    dados_para_planilha = []
    for r in todas_as_respostas:
        # Lógica para unificar as colunas de resposta e status
        if r.pergunta.tipo == 'discursiva':
            resposta_dada = r.texto_discursivo
            resposta_correta = '(Avaliação Manual)'
            status = r.status_correcao
        else:
            resposta_dada = get_texto_da_opcao(r.pergunta, r.resposta_dada)
            resposta_correta = get_texto_da_opcao(r.pergunta, r.pergunta.resposta_correta)
            status = "Correto" if (r.pontos or 0) > 0 else "Incorreto"

        dados_para_planilha.append({
            'Colaborador': r.usuario.nome,
            'Setor': r.usuario.departamento.nome,
            'Data da Resposta': (r.data_resposta - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M'),
            'Pergunta': r.pergunta.texto,
            'Tipo de Pergunta': r.pergunta.tipo,
            'Resposta Dada': resposta_dada,
            'Resposta Correta': resposta_correta,
            'Status/Resultado': status,
            'Pontos': r.pontos or 0,
            'Feedback do Admin': r.feedback_admin or ''
        })
        
    # Define a ordem final das colunas
    colunas = [
        'Colaborador', 'Setor', 'Data da Resposta', 'Pergunta', 'Tipo de Pergunta', 
        'Resposta Dada', 'Resposta Correta', 'Status/Resultado', 'Pontos', 'Feedback do Admin'
    ]
    
    df = pd.DataFrame(dados_para_planilha, columns=colunas)
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio_Completo')
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='relatorio_completo_respostas.xlsx'
    )
# --- ROTAS DE RANKING ---
@app.route('/ranking')
def pagina_ranking():
    if 'usuario_id' not in session: return redirect(url_for('pagina_login'))
    # Consulta para obter os pontos totais por departamento
    pontos_por_depto = db.session.query(
        Departamento.nome,
        func.coalesce(func.sum(Resposta.pontos), 0).label('pontos_totais')
    ).join(Usuario, Departamento.id == Usuario.departamento_id).join(Resposta, Usuario.id == Resposta.usuario_id).group_by(Departamento.nome).all()

    usuarios_por_depto = db.session.query(
        Departamento.id, 
        Departamento.nome,
        func.count(Usuario.id).label('num_usuarios')
    ).join(Usuario, Departamento.id == Usuario.departamento_id).group_by(Departamento.id, Departamento.nome).all()

    ranking_final = []
    pontos_dict = dict(pontos_por_depto)
    
    for depto_id, depto_nome, num_usuarios in usuarios_por_depto:
        # Agora, a busca a partir de 'pontos_dict' sempre retornará um número
        pontos_totais = pontos_dict.get(depto_nome, 0)
        pontuacao_proporcional = pontos_totais / num_usuarios if num_usuarios > 0 else 0
        
        ranking_final.append({
            'id': depto_id, 
            'nome': depto_nome, 
            'pontos_totais': pontos_totais, 
            'num_usuarios': num_usuarios, 
            'pontuacao_proporcional': round(pontuacao_proporcional)
        })
        
    ranking_final.sort(key=lambda x: x['pontuacao_proporcional'], reverse=True)
    
    return render_template('ranking.html', ranking=ranking_final)

@app.route('/ranking/<int:departamento_id>')
def pagina_ranking_detalhe(departamento_id):
    if 'usuario_id' not in session: return redirect(url_for('pagina_login'))
    departamento = Departamento.query.get_or_404(departamento_id)
    ranking_individual_query = db.session.query(Usuario.nome, func.coalesce(func.sum(Resposta.pontos), 0).label('pontos_totais'), func.coalesce(func.count(Resposta.id), 0).label('total_respostas'), func.coalesce(func.sum(case((Resposta.pontos > 0, 1), else_=0)), 0).label('total_acertos')).select_from(Usuario).outerjoin(Resposta).filter(Usuario.departamento_id == departamento_id).group_by(Usuario.nome).all()
    ranking_final = []
    for membro in ranking_individual_query:
        total_respostas = membro.total_respostas
        total_acertos = membro.total_acertos
        percentual = (total_acertos / total_respostas) * 100 if total_respostas > 0 else 0
        ranking_final.append({'nome': membro.nome, 'pontos_totais': membro.pontos_totais, 'total_respostas': total_respostas, 'total_acertos': total_acertos, 'percentual_acertos': round(percentual, 1)})
    ranking_final.sort(key=lambda x: x['nome'])
    return render_template('ranking_detalhe.html', departamento=departamento, ranking=ranking_final)

# --- ROTAS DE ADMIN ---


@app.route('/admin', methods=['GET', 'POST'])
def pagina_admin():
    if 'csv_data' in session:
        session.pop('csv_data', None)
        session.pop('has_valid_rows', None)
        session.pop('csv_headers', None)

    senha_correta = session.get('admin_logged_in', False)
    if request.method == 'POST' and not senha_correta:
        if request.form.get('senha') == SENHA_ADMIN:
            session['admin_logged_in'] = True
            senha_correta = True
        else:
            flash('Senha incorreta!', 'danger')
    
    perguntas, usuarios, departamentos = [], [], []
    contagem_pendentes = 0
    
    # Dicionário para passar os valores dos filtros de volta para o template
    filtros_ativos = {}

    if senha_correta:
        # Busca inicial de dados para os formulários
        usuarios = Usuario.query.join(Departamento).order_by(Departamento.nome, Usuario.nome).all()
        departamentos = Departamento.query.order_by(Departamento.nome).all()
        contagem_pendentes = Resposta.query.join(Pergunta).filter(Pergunta.tipo == 'discursiva', Resposta.status_correcao == 'pendente').count()

        # --- INÍCIO DA NOVA LÓGICA DE FILTRAGEM DE PERGUNTAS ---
        
        # 1. Começa com uma busca base para todas as perguntas
        query_perguntas = Pergunta.query

        # 2. Pega os valores dos filtros da URL (se existirem)
        filtro_mes = request.args.get('filtro_mes') # Ex: '2025-10'
        filtro_setor_id = request.args.get('filtro_setor', type=int)
        filtro_tipo = request.args.get('filtro_tipo')

        # 3. Aplica os filtros na busca, um por um
        if filtro_mes:
            try:
                ano, mes = map(int, filtro_mes.split('-'))
                query_perguntas = query_perguntas.filter(
                    db.extract('year', Pergunta.data_liberacao) == ano,
                    db.extract('month', Pergunta.data_liberacao) == mes
                )
                filtros_ativos['mes'] = filtro_mes
            except:
                pass # Ignora filtro de data mal formatado

        if filtro_setor_id:
            query_perguntas = query_perguntas.filter(
                or_(
                    Pergunta.para_todos_setores == True,
                    Pergunta.departamentos.any(Departamento.id == filtro_setor_id)
                )
            )
            filtros_ativos['setor_id'] = filtro_setor_id

        if filtro_tipo:
            query_perguntas = query_perguntas.filter(Pergunta.tipo == filtro_tipo)
            filtros_ativos['tipo'] = filtro_tipo

        # 4. Executa a busca final com os filtros aplicados
        perguntas = query_perguntas.order_by(Pergunta.data_liberacao.desc(), Pergunta.id.desc()).all()
        # --- FIM DA NOVA LÓGICA DE FILTRAGEM DE PERGUNTAS ---

    return render_template('admin.html', 
                           senha_correta=senha_correta, 
                           perguntas=perguntas, 
                           usuarios=usuarios, 
                           departamentos=departamentos,
                           contagem_pendentes=contagem_pendentes,
                           filtros=filtros_ativos) # Envia os filtros ativos para o template

@app.route('/admin/add_department', methods=['POST'])
def adicionar_setor():
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    nome_setor = request.form.get('nome')
    if nome_setor and not Departamento.query.filter_by(nome=nome_setor).first():
        novo_depto = Departamento(nome=nome_setor)
        db.session.add(novo_depto)
        db.session.commit()
        flash(f'Setor "{nome_setor}" adicionado com sucesso!', 'success')
    else:
        flash(f'Erro: O nome do setor não pode ser vazio ou já existe.', 'danger')
    return redirect(url_for('pagina_admin'))

@app.route('/admin/delete_department/<int:departamento_id>', methods=['POST'])
def excluir_setor(departamento_id):
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    depto = Departamento.query.get_or_404(departamento_id)
    if depto.usuarios:
        flash(f'Não é possível excluir o setor "{depto.nome}" pois ele possui usuários.', 'danger')
    else:
        db.session.delete(depto)
        db.session.commit()
        flash(f'Setor "{depto.nome}" excluído com sucesso.', 'success')
    return redirect(url_for('pagina_admin'))

@app.route('/admin/add_user', methods=['POST'])
def adicionar_usuario():
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    
    codigo = request.form['codigo_acesso']
    email = request.form.get('email') # Usamos .get() para não dar erro se for vazio

    if Usuario.query.filter_by(codigo_acesso=codigo).first():
        flash(f'Erro: O código de acesso "{codigo}" já está em uso.', 'danger')
        return redirect(url_for('pagina_admin'))
    
    # A verificação de e-mail agora só acontece se um e-mail for digitado
    if email and Usuario.query.filter_by(email=email).first():
        flash(f'Erro: O e-mail "{email}" já está em uso.', 'danger')
        return redirect(url_for('pagina_admin'))
        
    novo_usuario = Usuario(
        nome=request.form['nome'],
        email=email or None, # Salva None se o campo estiver vazio
        codigo_acesso=codigo,
        departamento_id=request.form['departamento_id']
    )
    db.session.add(novo_usuario)
    db.session.commit()
    flash('Usuário adicionado com sucesso!', 'success')
    return redirect(url_for('pagina_admin'))

@app.route('/admin/edit_user/<int:usuario_id>', methods=['GET'])
def editar_usuario(usuario_id):
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    usuario = Usuario.query.get_or_404(usuario_id)
    departamentos = Departamento.query.order_by(Departamento.nome).all()
    return render_template('edit_user.html', usuario=usuario, departamentos=departamentos)

@app.route('/admin/edit_user/<int:usuario_id>', methods=['POST'])
def atualizar_usuario(usuario_id):
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    
    usuario = Usuario.query.get_or_404(usuario_id)
    novo_codigo = request.form['codigo_acesso']
    novo_email = request.form.get('email')

    codigo_existente = Usuario.query.filter(Usuario.id != usuario_id, Usuario.codigo_acesso == novo_codigo).first()
    if codigo_existente:
        flash(f'Erro: O código de acesso "{novo_codigo}" já está em uso por outro usuário.', 'danger')
        return redirect(url_for('editar_usuario', usuario_id=usuario_id))

    # A verificação de e-mail agora só acontece se um e-mail for digitado
    if novo_email and Usuario.query.filter(Usuario.id != usuario_id, Usuario.email == novo_email).first():
        flash(f'Erro: O e-mail "{novo_email}" já está em uso por outro usuário.', 'danger')
        return redirect(url_for('editar_usuario', usuario_id=usuario_id))

    usuario.nome = request.form['nome']
    usuario.email = novo_email or None # Salva None se o campo estiver vazio
    usuario.codigo_acesso = novo_codigo
    usuario.departamento_id = request.form['departamento_id']
    
    db.session.commit()
    flash(f'Usuário "{usuario.nome}" atualizado com sucesso!', 'success')
    return redirect(url_for('pagina_admin'))

@app.route('/admin/delete_user/<int:usuario_id>', methods=['POST'])
def excluir_usuario(usuario_id):
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    usuario = Usuario.query.get_or_404(usuario_id)
    Resposta.query.filter_by(usuario_id=usuario_id).delete()
    db.session.delete(usuario)
    db.session.commit()
    flash(f'Usuário "{usuario.nome}" e todas as suas respostas foram excluídos.', 'success')
    return redirect(url_for('pagina_admin'))

@app.route('/admin/edit_question/<int:pergunta_id>', methods=['GET'])
def editar_pergunta(pergunta_id):
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    pergunta = Pergunta.query.get_or_404(pergunta_id)
    todos_departamentos = Departamento.query.order_by(Departamento.nome).all()
    return render_template('edit_question.html', pergunta=pergunta, todos_departamentos=todos_departamentos)

@app.route('/admin/add_question', methods=['POST'])
def adicionar_pergunta():
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    
    tipo = request.form.get('tipo')
    data_str = request.form.get('data_liberacao')
    
    try:
        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Data inválida.', 'danger')
        return redirect(url_for('pagina_admin'))

    # 1. Cria o objeto da pergunta com os dados básicos
    nova_pergunta = Pergunta(
        tipo=tipo,
        texto=request.form.get('texto'),
        explicacao=request.form.get('explicacao'),
        data_liberacao=data_obj
    )

    # 2. Salvamos IMEDIATAMENTE para gerar o ID da pergunta (necessário para as imagens)
    db.session.add(nova_pergunta)
    db.session.commit()

    # 3. Processamento de Múltiplas Imagens
    # 'getlist' pega todos os arquivos enviados no input com multiple
    arquivos = request.files.getlist('imagem_pergunta') 
    
    for file in arquivos:
        if file and file.filename != '' and allowed_file(file.filename):
            # Envia para o Cloudinary
            upload_result = cloudinary.uploader.upload(file, folder="perguntas")
            imagem_url = upload_result.get('secure_url')
            
            # A) Compatibilidade: Se for a primeira imagem, salva no campo antigo também
            if not nova_pergunta.imagem_pergunta:
                nova_pergunta.imagem_pergunta = imagem_url
            
            # B) Nova Lógica: Salva na tabela de imagens extras vinculada a esta pergunta
            nova_imagem_banco = ImagemPergunta(url=imagem_url, pergunta=nova_pergunta)
            db.session.add(nova_imagem_banco)

    # 4. Configuração dos Setores (Atualiza a pergunta já criada)
    if 'para_todos_setores' in request.form:
        nova_pergunta.para_todos_setores = True
    else:
        nova_pergunta.para_todos_setores = False
        departamento_ids = request.form.getlist('departamentos')
        if departamento_ids:
            departamentos_selecionados = Departamento.query.filter(Departamento.id.in_(departamento_ids)).all()
            nova_pergunta.departamentos = departamentos_selecionados
    
    # 5. Configuração das Opções (Múltipla Escolha / V ou F)
    if tipo in ['multipla_escolha', 'verdadeiro_falso']:
        nova_pergunta.resposta_correta = request.form.get('resposta_correta')
        nova_pergunta.tempo_limite = request.form.get('tempo_limite')
        
        if tipo == 'multipla_escolha':
            nova_pergunta.opcao_a = request.form.get('opcao_a')
            nova_pergunta.opcao_b = request.form.get('opcao_b')
            nova_pergunta.opcao_c = request.form.get('opcao_c')
            nova_pergunta.opcao_d = request.form.get('opcao_d')
    else: 
        # Discursiva (garante que campos desnecessários fiquem vazios)
        nova_pergunta.tempo_limite = None
        nova_pergunta.resposta_correta = None
        nova_pergunta.opcao_a = None
        nova_pergunta.opcao_b = None
        nova_pergunta.opcao_c = None
        nova_pergunta.opcao_d = None

    # 6. Salva todas as alterações finais (imagens, setores, opções)
    db.session.commit()
    
    flash('Pergunta adicionada com sucesso!', 'success')
    return redirect(url_for('pagina_admin'))

@app.route('/admin/edit_question/<int:pergunta_id>', methods=['POST'])
def atualizar_pergunta(pergunta_id):
    if not session.get('admin_logged_in'): 
        return redirect(url_for('pagina_admin'))
    
    pergunta = Pergunta.query.get_or_404(pergunta_id)
    
    # 1. Atualiza os campos básicos
    pergunta.tipo = request.form.get('tipo')
    pergunta.texto = request.form.get('texto')
    pergunta.explicacao = request.form.get('explicacao')
    
    try:
        pergunta.data_liberacao = datetime.strptime(request.form.get('data_liberacao'), '%Y-%m-%d').date()
    except ValueError:
        flash('Data inválida.', 'danger')
        return redirect(url_for('editar_pergunta', pergunta_id=pergunta_id))

    # 2. Nova Lógica: Upload de Múltiplas Imagens (Adiciona à galeria)
    # Pega todos os arquivos enviados
    arquivos = request.files.getlist('imagem_pergunta')
    
    for file in arquivos:
        if file and file.filename != '' and allowed_file(file.filename):
            # Envia para o Cloudinary
            upload_result = cloudinary.uploader.upload(file, folder="perguntas_quiz")
            imagem_url = upload_result.get('secure_url')
            
            # Compatibilidade: Se a pergunta ainda não tem capa (campo antigo), usa a primeira nova
            if not pergunta.imagem_pergunta:
                pergunta.imagem_pergunta = imagem_url
            
            # Salva na nova tabela de galeria
            nova_img = ImagemPergunta(url=imagem_url, pergunta=pergunta)
            db.session.add(nova_img)

    # 3. Atualiza os departamentos associados
    pergunta.departamentos.clear()
    if 'para_todos_setores' in request.form:
        pergunta.para_todos_setores = True
    else:
        pergunta.para_todos_setores = False
        departamento_ids = request.form.getlist('departamentos')
        if departamento_ids:
            departamentos_selecionados = Departamento.query.filter(Departamento.id.in_(departamento_ids)).all()
            pergunta.departamentos = departamentos_selecionados

    # 4. Atualiza as opções (conforme o tipo)
    if pergunta.tipo in ['multipla_escolha', 'verdadeiro_falso']:
        pergunta.resposta_correta = request.form.get('resposta_correta')
        pergunta.tempo_limite = request.form.get('tempo_limite')
        if pergunta.tipo == 'multipla_escolha':
            pergunta.opcao_a, pergunta.opcao_b, pergunta.opcao_c, pergunta.opcao_d = request.form.get('opcao_a'), request.form.get('opcao_b'), request.form.get('opcao_c'), request.form.get('opcao_d')
        else:
            pergunta.opcao_a, pergunta.opcao_b, pergunta.opcao_c, pergunta.opcao_d = None, None, None, None
    else: # Discursiva
        pergunta.resposta_correta, pergunta.tempo_limite = None, None
        pergunta.opcao_a, pergunta.opcao_b, pergunta.opcao_c, pergunta.opcao_d = None, None, None, None
        
    db.session.commit()
    flash('Pergunta atualizada com sucesso!', 'success')
    return redirect(url_for('pagina_admin'))

@app.route('/admin/delete_question/<int:pergunta_id>', methods=['POST'])
def excluir_pergunta(pergunta_id):
    if not session.get('admin_logged_in'): 
        return redirect(url_for('pagina_admin'))
        
    pergunta = Pergunta.query.get_or_404(pergunta_id)
    # --- INÍCIO DA NOVA LÓGICA PARA EXCLUIR ARQUIVOS DO CLOUDINARY ---
    try:
        # 1. Apaga a imagem da pergunta, se existir
        if pergunta.imagem_pergunta:
            # Extrai o "public_id" da URL do Cloudinary
            public_id = pergunta.imagem_pergunta.split('/')[-1].split('.')[0]
            cloudinary.uploader.destroy(public_id)
            app.logger.info(f"Imagem {public_id} excluída do Cloudinary.")

        # 2. Busca todas as respostas da pergunta para apagar os anexos
        respostas_para_excluir = Resposta.query.filter_by(pergunta_id=pergunta.id).all()
        for resposta in respostas_para_excluir:
            if resposta.anexo_resposta:
                public_id_anexo = resposta.anexo_resposta.split('/')[-1].split('.')[0]
                # Usa 'destroy' com resource_type="raw" para arquivos como PDF, DOC
                cloudinary.uploader.destroy(public_id_anexo, resource_type="raw")
                app.logger.info(f"Anexo {public_id_anexo} excluído do Cloudinary.")

    except Exception as e:
        app.logger.error(f"Erro ao tentar excluir arquivos do Cloudinary: {e}")
        # Mesmo que falhe em apagar do Cloudinary, continua para apagar do banco
    # --- FIM DA NOVA LÓGICA ---

    # Apaga todas as respostas ligadas a esta pergunta no banco
    Resposta.query.filter_by(pergunta_id=pergunta.id).delete()
    
    # Apaga a pergunta do banco
    db.session.delete(pergunta)
    db.session.commit()
    
    flash('Pergunta e todas as suas respostas foram excluídas com sucesso.', 'success')
    return redirect(url_for('pagina_admin'))

@app.route('/admin/correcoes')
def pagina_correcoes():
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    usuarios_disponiveis = Usuario.query.order_by(Usuario.nome).all()
    usuario_selecionado_id = request.args.get('usuario_id', type=int)
    status_selecionado = request.args.get('status', 'pendente')
    query = Resposta.query.join(Pergunta).filter(Pergunta.tipo == 'discursiva')
    if status_selecionado != 'todos':
        query = query.filter(Resposta.status_correcao == status_selecionado)
    if usuario_selecionado_id:
        query = query.filter(Resposta.usuario_id == usuario_selecionado_id)
    respostas_filtradas = query.join(Usuario).order_by(Resposta.data_resposta.desc()).all()
    return render_template('correcoes.html', 
                           respostas=respostas_filtradas, 
                           usuarios_disponiveis=usuarios_disponiveis, 
                           usuario_selecionado_id=usuario_selecionado_id,
                           status_selecionado=status_selecionado)


@app.route('/admin/relatorios')
def pagina_relatorios():
    if not session.get('admin_logged_in'): 
        return redirect(url_for('pagina_admin'))

    depto_selecionado_id = request.args.get('departamento_id', type=int)
    departamentos = Departamento.query.order_by(Departamento.nome).all()

    # Agora apenas chama a função auxiliar para obter os dados
    dados_relatorio = _gerar_dados_relatorio(depto_selecionado_id)

    return render_template('relatorios.html', 
                           relatorios=dados_relatorio, 
                           departamentos=departamentos, 
                           depto_selecionado_id=depto_selecionado_id)


@app.route('/admin/relatorios/exportar')
def exportar_relatorios():
    if not session.get('admin_logged_in'): 
        return redirect(url_for('pagina_admin'))

    depto_selecionado_id = request.args.get('departamento_id', type=int)

    # 1. Reutiliza a mesma lógica de busca de dados
    dados_relatorio = _gerar_dados_relatorio(depto_selecionado_id)

    if not dados_relatorio:
        flash("Nenhum dado para exportar com os filtros selecionados.", "warning")
        return redirect(url_for('pagina_relatorios'))

    # 2. Converte os dados para um formato que o pandas entende
    df = pd.DataFrame(dados_relatorio)

    # 3. Renomeia e reordena as colunas para a planilha
    df = df.rename(columns={
        'nome': 'Colaborador',
        'setor': 'Setor',
        'total_respostas': 'Respostas Totais',
        'respostas_corretas': 'Respostas Corretas',
        'aproveitamento': 'Aproveitamento (%)',
        'pontuacao_total': 'Pontuação Total'
    })
    df['Aproveitamento (%)'] = df['Aproveitamento (%)'].map('{:.1f}%'.format)

    # 4. Cria o arquivo Excel em memória
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio de Desempenho')
    output.seek(0)

    # 5. Envia o arquivo para download
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='relatorio_desempenho_quiz.xlsx'
    )

@app.route('/admin/corrigir/<int:resposta_id>', methods=['POST'])
def corrigir_resposta(resposta_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('pagina_admin'))
        
    resposta = Resposta.query.get_or_404(resposta_id)
    
    novo_status = request.form.get('status')
    feedback_texto = request.form.get('feedback', '')
    
    if novo_status in ['correto', 'incorreto', 'parcialmente_correto']:
        resposta.status_correcao = novo_status
        resposta.feedback_admin = feedback_texto
        
        if novo_status == 'correto':
            resposta.pontos = 100
        elif novo_status == 'parcialmente_correto':
            resposta.pontos = 50 # Pontuação intermediária
        else: # Incorreto
            resposta.pontos = 0
            
        db.session.commit()
        flash('Resposta avaliada com sucesso!', 'success')
    else:
        flash('Ação de correção inválida.', 'danger')
        
    return redirect(url_for('pagina_correcoes'))

@app.route('/admin/analytics')
def pagina_analytics():
    if not session.get('admin_logged_in'): 
        return redirect(url_for('pagina_admin'))
    
    usuarios_disponiveis = Usuario.query.order_by(Usuario.nome).all()
    departamentos = Departamento.query.order_by(Departamento.nome).all()
    
    usuario_selecionado_id = request.args.get('usuario_id', type=int)
    depto_selecionado_id = request.args.get('departamento_id', type=int)
    filtro_acertos = request.args.get('filtro_acertos', 'erros')
    filtro_tipo = request.args.get('filtro_tipo')

    # --- Lógica para "Percentual de Erros por Pergunta" ---
    base_query_stats = Resposta.query.join(Pergunta)
    
    if filtro_tipo:
        base_query_stats = base_query_stats.filter(Pergunta.tipo == filtro_tipo)
    else:
        base_query_stats = base_query_stats.filter(Pergunta.tipo != 'discursiva')
        
    if depto_selecionado_id:
        base_query_stats = base_query_stats.join(Usuario).filter(Usuario.departamento_id == depto_selecionado_id)
    if usuario_selecionado_id:
        base_query_stats = base_query_stats.filter(Resposta.usuario_id == usuario_selecionado_id)
    
    todas_as_respostas = base_query_stats.all()
    stats_perguntas_raw = defaultdict(lambda: {'total': 0, 'erros': 0})
    for resposta in todas_as_respostas:
        stats_perguntas_raw[resposta.pergunta_id]['total'] += 1
        if resposta.pontos == 0:
            stats_perguntas_raw[resposta.pergunta_id]['erros'] += 1
    
    stats_perguntas = []
    for pergunta_id, data in stats_perguntas_raw.items():
        pergunta = Pergunta.query.get(pergunta_id)
        if pergunta:
            percentual = (data['erros'] / data['total']) * 100 if data['total'] > 0 else 0
            stats_perguntas.append({'texto': pergunta.texto, 'total': data['total'], 'erros': data['erros'], 'percentual': percentual})
    stats_perguntas.sort(key=lambda x: x['percentual'], reverse=True)

    # --- Lógica para "Análise Detalhada" (Acertos ou Erros) ---
    query_detalhada = Resposta.query.join(Pergunta).join(Usuario).join(Departamento)

    if filtro_tipo:
        query_detalhada = query_detalhada.filter(Pergunta.tipo == filtro_tipo)
    else:
        query_detalhada = query_detalhada.filter(Pergunta.tipo != 'discursiva')

    if filtro_acertos == 'acertos':
        query_detalhada = query_detalhada.filter(or_(Resposta.pontos > 0, Resposta.status_correcao.in_(['correto', 'parcialmente_correto'])))
    else: # 'erros'
        query_detalhada = query_detalhada.filter(or_(Resposta.pontos == 0, Resposta.status_correcao == 'incorreto'))
        
    if usuario_selecionado_id:
        query_detalhada = query_detalhada.filter(Resposta.usuario_id == usuario_selecionado_id)
    if depto_selecionado_id:
        query_detalhada = query_detalhada.filter(Usuario.departamento_id == depto_selecionado_id)
    
    respostas_detalhadas = query_detalhada.order_by(Departamento.nome, Usuario.nome).all()
    
    dados_agrupados = defaultdict(lambda: defaultdict(list))
    for r in respostas_detalhadas:
        setor_nome = r.usuario.departamento.nome
        usuario_nome = r.usuario.nome
        dados_agrupados[setor_nome][usuario_nome].append({
            'pergunta_texto': r.pergunta.texto,
            'data_liberacao': r.pergunta.data_liberacao.strftime('%d/%m/%Y'),
            'resposta_dada': r.resposta_dada,
            'texto_resposta_dada': get_texto_da_opcao(r.pergunta, r.resposta_dada),
            'resposta_correta': r.pergunta.resposta_correta,
            'texto_resposta_correta': get_texto_da_opcao(r.pergunta, r.pergunta.resposta_correta)
        })

    return render_template('analytics.html', 
                           stats_perguntas=stats_perguntas, 
                           dados_agrupados=dados_agrupados,
                           usuarios_disponiveis=usuarios_disponiveis,
                           departamentos=departamentos,
                           usuario_selecionado_id=usuario_selecionado_id,
                           depto_selecionado_id=depto_selecionado_id,
                           filtro_acertos=filtro_acertos,
                           filtro_tipo=filtro_tipo)

@app.route('/admin/upload_planilha', methods=['POST'])
def upload_planilha():
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    arquivo = request.files.get('arquivo_planilha')
    if not arquivo or not (arquivo.filename.lower().endswith('.xls') or arquivo.filename.lower().endswith('.xlsx')):
        flash('Arquivo inválido ou não selecionado. Envie uma planilha .xls ou .xlsx.', 'danger')
        return redirect(url_for('pagina_admin'))
    try:
        df = pd.read_excel(arquivo)
        df = df.fillna('')
        if 'data_liberacao' in df.columns:
            df['data_liberacao'] = pd.to_datetime(df['data_liberacao'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
        for col in df.columns:
            if col != 'data_liberacao':
                df[col] = df[col].astype(str).str.replace(r'\.0$', '', regex=True)
        headers = df.columns.tolist()
        dados_da_planilha = df.to_dict(orient='records')
        session['csv_headers'] = headers
        validated_data = []
        has_valid_rows = False
        for row in dados_da_planilha:
            is_valid, errors = validar_linha(row)
            if is_valid: has_valid_rows = True
            validated_data.append({'data': row, 'is_valid': is_valid, 'errors': errors})
        session['csv_data'] = validated_data
        session['has_valid_rows'] = has_valid_rows
        return redirect(url_for('preview_csv'))
    except Exception as e:
        app.logger.error(f"Erro ao ler a planilha Excel: {e}")
        flash(f"Ocorreu um erro inesperado ao processar a planilha: {e}", "danger")
        return redirect(url_for('pagina_admin'))

@app.route('/admin/preview_csv')
def preview_csv():
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    validated_data = session.get('csv_data', [])
    has_valid_rows = session.get('has_valid_rows', False)
    headers = session.get('csv_headers', [])
    return render_template('preview_csv.html', data=validated_data, has_valid_rows=has_valid_rows, headers=headers)

@app.route('/admin/processar_edicao_csv', methods=['POST'])
def processar_edicao_csv():
    if not session.get('admin_logged_in'): 
        return redirect(url_for('pagina_admin'))

    # 1. Reconstrói os dados da planilha a partir do formulário editado
    rows_data = defaultdict(dict)
    for key, value in request.form.items():
        if key.startswith('row-'):
            parts = key.split('-', 2)
            row_index = int(parts[1])
            col_name = parts[2]
            rows_data[row_index][col_name] = value

    success_count = 0
    error_count = 0
    
    # 2. Loop através das linhas corrigidas para salvar no banco
    for row_index in sorted(rows_data.keys()):
        row = rows_data[row_index]
        is_valid, errors = validar_linha(row) # Revalida a linha
        
        if is_valid:
            try:
                data_obj = datetime.strptime(row['data_liberacao'], '%d/%m/%Y').date()
                nova_pergunta = Pergunta(
                    tipo=row['tipo'], texto=row['texto'],
                    opcao_a=row.get('opcao_a') or None, opcao_b=row.get('opcao_b') or None,
                    opcao_c=row.get('opcao_c') or None, opcao_d=row.get('opcao_d') or None,
                    resposta_correta=row.get('resposta_correta') or None, 
                    data_liberacao=data_obj,
                    tempo_limite=int(float(row['tempo_limite'])) if row.get('tempo_limite') else None
                )
                db.session.add(nova_pergunta)
                
                db.session.commit()
                
                success_count += 1
            except Exception as e:
                # Se ocorrer um erro ao salvar esta linha específica, é desfeito a tentativa (rollback)
                # e continuamos para a próxima, sem quebrar toda a importação.
                db.session.rollback()
                error_count += 1
                app.logger.error(f"Erro ao salvar linha {row_index} (após correção): {e} | Dados: {row}")
        else:
            error_count += 1
            app.logger.error(f"Linha {row_index} ainda inválida após edição: {errors}")

    session.pop('csv_data', None)
    session.pop('has_valid_rows', None)
    session.pop('csv_headers', None)
    
    if error_count > 0:
        flash(f'Importação parcial: {success_count} perguntas salvas. {error_count} linhas continham erros e foram ignoradas.', 'warning')
    else:
        flash(f'Importação concluída! {success_count} perguntas foram importadas com sucesso!', 'success')
        
    return redirect(url_for('pagina_admin'))

# --- ROTA DE SERVIÇO PARA INICIALIZAR/RESETAR O BANCO DE DADOS LOCAL ---
@app.route('/_init_db/<secret_key>')
def init_db(secret_key):
    # Usar uma chave diferente da senha de admin para mais segurança
    if secret_key != 'resetar-banco-123':
        return "Chave secreta inválida.", 403
    try:
        app.logger.info("Iniciando a reinicialização do banco de dados...")
        db.drop_all()
        db.create_all()
        app.logger.info("Tabelas criadas. Inserindo dados iniciais...")
        
        # Dados iniciais para usuários e setores
        dados_iniciais = {
            "Suporte": [
                {'nome': 'Ana Oliveira', 'codigo_acesso': '1234', 'email': 'ana.oliveira@empresa.com'},
                {'nome': 'Bruno Costa', 'codigo_acesso': '5678', 'email': 'bruno.costa@empresa.com'}
            ],
            "Vendas": [
                {'nome': 'Carlos Dias', 'codigo_acesso': '9012', 'email': 'carlos.dias@empresa.com'},
                {'nome': 'Daniela Lima', 'codigo_acesso': '3456', 'email': 'daniela.lima@empresa.com'}
            ]
        }
        
        for nome_depto, lista_usuarios in dados_iniciais.items():
            novo_depto = Departamento(nome=nome_depto)
            db.session.add(novo_depto)
            for user_data in lista_usuarios:
                novo_usuario = Usuario(
                    nome=user_data['nome'], 
                    codigo_acesso=user_data['codigo_acesso'],
                    email=user_data['email'],
                    departamento=novo_depto
                )
                db.session.add(novo_usuario)
        
        db.session.commit()
        app.logger.info("Banco de dados inicializado com sucesso!")
        return "<h1>Banco de dados inicializado com sucesso!</h1>"
    except Exception as e:
        app.logger.error(f"Ocorreu um erro na inicialização do banco de dados: {e}")
        return f"<h1>Ocorreu um erro:</h1><p>{e}</p>", 500

if __name__ == '__main__':
    app.run(debug=True)
