from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func, case
from collections import defaultdict
from datetime import date, datetime, timedelta
from flask_mail import Mail, Message
import os
from threading import Thread

app = Flask(__name__)

# --- CONFIGURAÇÕES GERAIS ---
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- CONFIGURAÇÕES DE E-MAIL (Exemplo com SendGrid e porta TLS) ---
app.config['MAIL_SERVER'] = 'smtp.sendgrid.net'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
# Certifique-se de ter um e-mail verificado no SendGrid para usar como remetente
app.config['MAIL_DEFAULT_SENDER'] = ('Quiz Produtivo', os.environ.get('MAIL_SENDER_EMAIL', 'jenycds@hotmail.com'))


# --- INICIALIZAÇÕES ---
db = SQLAlchemy(app)
mail = Mail(app)

SENHA_ADMIN = "admin123"

# --- MODELOS DO BANCO DE DADOS ---
class Departamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    usuarios = db.relationship('Usuario', backref='departamento', lazy=True)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    codigo_acesso = db.Column(db.String(4), unique=True, nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamento.id'), nullable=False)
    respostas = db.relationship('Resposta', backref='usuario', lazy=True)

class Pergunta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False, default='multipla_escolha')
    texto = db.Column(db.String(500), nullable=False)
    opcao_a = db.Column(db.String(100), nullable=True)
    opcao_b = db.Column(db.String(100), nullable=True)
    opcao_c = db.Column(db.String(100), nullable=True)
    opcao_d = db.Column(db.String(100), nullable=True)
    resposta_correta = db.Column(db.String(1), nullable=False)
    data_liberacao = db.Column(db.Date, nullable=False)
    tempo_limite = db.Column(db.Integer, nullable=False, default=30)

class Resposta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pontos = db.Column(db.Integer, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    pergunta_id = db.Column(db.Integer, db.ForeignKey('pergunta.id'), nullable=False)
    resposta_dada = db.Column(db.String(1), nullable=False)
    data_resposta = db.Column(db.DateTime, default=datetime.utcnow)
    pergunta = db.relationship('Pergunta')

# --- FUNÇÕES AUXILIARES ---
def get_texto_da_opcao(pergunta, opcao):
    if opcao == 'a': return pergunta.opcao_a
    if opcao == 'b': return pergunta.opcao_b
    if opcao == 'c': return pergunta.opcao_c
    if opcao == 'd': return pergunta.opcao_d
    if opcao == 'v': return "Verdadeiro"
    if opcao == 'f': return "Falso"
    return ""

@app.context_processor
def utility_processor():
    return dict(get_texto_da_opcao=get_texto_da_opcao)
    
def send_email_async(app_context, msg):
    with app_context:
        try:
            mail.send(msg)
            print(f"E-mail enviado em segundo plano para {msg.recipients}")
        except Exception as e:
            print(f"Falha ao enviar e-mail em segundo plano: {e}")

# --- ROTAS PRINCIPAIS DO USUÁRIO ---
@app.route('/')
def pagina_login():
    if 'usuario_id' in session: return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def processa_login():
    codigo_inserido = request.form['codigo']
    usuario = Usuario.query.filter_by(codigo_acesso=codigo_inserido).first()
    if usuario:
        session['usuario_id'] = usuario.id
        session['usuario_nome'] = usuario.nome
        return redirect(url_for('dashboard'))
    else:
        flash('Código de acesso inválido!', 'danger')
        return redirect(url_for('pagina_login'))

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session: return redirect(url_for('pagina_login'))
    return render_template('dashboard.html', nome=session['usuario_nome'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('pagina_login'))

@app.route('/quiz')
def pagina_quiz():
    if 'usuario_id' not in session: return redirect(url_for('pagina_login'))
    usuario_id = session['usuario_id']
    hoje = date.today()
    perguntas_respondidas_ids = [r.pergunta_id for r in Resposta.query.filter_by(usuario_id=usuario_id).all()]
    proxima_pergunta = Pergunta.query.filter(
        Pergunta.data_liberacao <= hoje,
        Pergunta.id.notin_(perguntas_respondidas_ids)
    ).order_by(Pergunta.data_liberacao).first()
    if proxima_pergunta:
        return render_template('quiz.html', pergunta=proxima_pergunta)
    else:
        flash('Parabéns, você respondeu todas as perguntas disponíveis!', 'success')
        return redirect(url_for('pagina_ranking'))

@app.route('/responder', methods=['POST'])
def processa_resposta():
    if 'usuario_id' not in session: return redirect(url_for('pagina_login'))
    pergunta_id = request.form['pergunta_id']
    resposta_usuario = request.form.get('resposta', '')
    tempo_restante = float(request.form['tempo_restante'])
    pergunta = Pergunta.query.get(pergunta_id)
    pontos = 0
    if pergunta.resposta_correta == resposta_usuario:
        pontos = 100 + int(tempo_restante * 5)
        flash(f'Resposta correta! Você ganhou {pontos} pontos.', 'success')
    else:
        flash('Resposta incorreta. Sem pontos desta vez.', 'danger')
    nova_resposta = Resposta(pontos=pontos, usuario_id=session['usuario_id'], pergunta_id=pergunta_id, resposta_dada=resposta_usuario)
    db.session.add(nova_resposta)
    db.session.commit()
    return redirect(url_for('pagina_quiz'))

@app.route('/meus-erros')
def meus_erros():
    if 'usuario_id' not in session: return redirect(url_for('pagina_login'))
    usuario_id = session['usuario_id']
    respostas_erradas = Resposta.query.filter_by(usuario_id=usuario_id, pontos=0).join(Pergunta).order_by(Pergunta.id.desc()).all()
    erros_detalhados = []
    for r in respostas_erradas:
        erros_detalhados.append({
            'pergunta_texto': r.pergunta.texto,
            'sua_resposta_letra': r.resposta_dada,
            'sua_resposta_texto': get_texto_da_opcao(r.pergunta, r.resposta_dada),
            'resposta_correta_letra': r.pergunta.resposta_correta,
            'resposta_correta_texto': get_texto_da_opcao(r.pergunta, r.pergunta.resposta_correta)
        })
    return render_template('meus_erros.html', erros=erros_detalhados)

# --- ROTAS DE RANKING ---
@app.route('/ranking')
def pagina_ranking():
    if 'usuario_id' not in session: return redirect(url_for('pagina_login'))
    pontos_por_depto = db.session.query(Departamento.nome, func.sum(Resposta.pontos).label('pontos_totais')).join(Usuario, Departamento.id == Usuario.departamento_id).join(Resposta, Usuario.id == Resposta.usuario_id).group_by(Departamento.nome).all()
    usuarios_por_depto = db.session.query(Departamento.id, Departamento.nome, func.count(Usuario.id).label('num_usuarios')).join(Usuario, Departamento.id == Usuario.departamento_id).group_by(Departamento.id, Departamento.nome).all()
    ranking_final = []
    pontos_dict = dict(pontos_por_depto)
    for depto_id, depto_nome, num_usuarios in usuarios_por_depto:
        pontos_totais = pontos_dict.get(depto_nome, 0)
        pontuacao_proporcional = pontos_totais / num_usuarios if num_usuarios > 0 else 0
        ranking_final.append({'id': depto_id, 'nome': depto_nome, 'pontos_totais': pontos_totais, 'num_usuarios': num_usuarios, 'pontuacao_proporcional': round(pontuacao_proporcional)})
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
    senha_correta = session.get('admin_logged_in', False)
    if request.method == 'POST' and not senha_correta:
        if request.form.get('senha') == SENHA_ADMIN:
            session['admin_logged_in'] = True
            senha_correta = True
        else:
            flash('Senha incorreta!', 'danger')
    perguntas, usuarios, departamentos = [], [], []
    if senha_correta:
        perguntas = Pergunta.query.order_by(Pergunta.data_liberacao.desc(), Pergunta.id.desc()).all()
        usuarios = Usuario.query.join(Departamento).order_by(Departamento.nome, Usuario.nome).all()
        departamentos = Departamento.query.order_by(Departamento.nome).all()
    return render_template('admin.html', senha_correta=senha_correta, perguntas=perguntas, usuarios=usuarios, departamentos=departamentos)

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
        flash(f'Não é possível excluir o setor "{depto.nome}" pois ele possui usuários. Mova-os para outro setor primeiro.', 'danger')
    else:
        db.session.delete(depto)
        db.session.commit()
        flash(f'Setor "{depto.nome}" excluído com sucesso.', 'success')
    return redirect(url_for('pagina_admin'))

@app.route('/admin/add_user', methods=['POST'])
def adicionar_usuario():
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    codigo = request.form['codigo_acesso']
    email = request.form['email']
    if Usuario.query.filter_by(codigo_acesso=codigo).first():
        flash(f'Erro: O código de acesso "{codigo}" já está em uso.', 'danger')
        return redirect(url_for('pagina_admin'))
    if Usuario.query.filter_by(email=email).first():
        flash(f'Erro: O e-mail "{email}" já está em uso.', 'danger')
        return redirect(url_for('pagina_admin'))
    novo_usuario = Usuario(nome=request.form['nome'], email=email, codigo_acesso=codigo, departamento_id=request.form['departamento_id'])
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
    novo_email = request.form['email']
    codigo_existente = Usuario.query.filter(Usuario.id != usuario_id, Usuario.codigo_acesso == novo_codigo).first()
    if codigo_existente:
        flash(f'Erro: O código de acesso "{novo_codigo}" já está em uso por outro usuário.', 'danger')
        return redirect(url_for('editar_usuario', usuario_id=usuario_id))
    email_existente = Usuario.query.filter(Usuario.id != usuario_id, Usuario.email == novo_email).first()
    if email_existente:
        flash(f'Erro: O e-mail "{novo_email}" já está em uso por outro usuário.', 'danger')
        return redirect(url_for('editar_usuario', usuario_id=usuario_id))
    usuario.nome = request.form['nome']
    usuario.email = novo_email
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

@app.route('/admin/add_question', methods=['POST'])
def adicionar_pergunta():
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    tipo = request.form['tipo']
    data_str = request.form['data_liberacao']
    data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
    resposta_correta = request.form['resposta_correta']
    nova_pergunta = Pergunta(
        tipo=tipo,
        texto=request.form['texto'],
        data_liberacao=data_obj,
        resposta_correta=resposta_correta,
        opcao_a=request.form.get('opcao_a'),
        opcao_b=request.form.get('opcao_b'),
        opcao_c=request.form.get('opcao_c'),
        opcao_d=request.form.get('opcao_d'),
        tempo_limite=request.form['tempo_limite']
    )
    db.session.add(nova_pergunta)
    db.session.commit()
    flash('Pergunta adicionada com sucesso!', 'success')
    
    # --- INÍCIO: LÓGICA DE ENVIO DE E-MAIL EM SEGUNDO PLANO ---
    try:
        usuarios = Usuario.query.filter(Usuario.email.isnot(None)).all()
        if usuarios:
            data_formatada = nova_pergunta.data_liberacao.strftime('%d/%m/%Y')
            subject = "Fique atento: Nova pergunta agendada no Quiz!"
            
            for usuario in usuarios:
                body = (
                    f"Olá, {usuario.nome}!\n\n"
                    f"Uma nova pergunta de conhecimento foi cadastrada e está agendada para ser liberada no dia {data_formatada}.\n\n"
                    f"Prepare-se para testar seus conhecimentos!"
                )
                msg = Message(subject=subject, recipients=[usuario.email], body=body)
                thread = Thread(target=send_email_async, args=[app.app_context(), msg])
                thread.start()
            flash(f'Envio de notificação iniciado para {len(usuarios)} usuários.', 'success')
    except Exception as e:
        print(f"ERRO AO PREPARAR E-MAILS: {e}")
        flash('Pergunta salva, mas ocorreu um erro ao iniciar o envio de notificações.', 'danger')
    
    return redirect(url_for('pagina_admin'))

@app.route('/admin/edit_question/<int:pergunta_id>', methods=['GET', 'POST'])
def editar_pergunta(pergunta_id):
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    pergunta = Pergunta.query.get_or_404(pergunta_id)
    if request.method == 'POST':
        tipo = request.form['tipo']
        pergunta.tipo = tipo
        pergunta.texto = request.form['texto']
        pergunta.data_liberacao = datetime.strptime(request.form['data_liberacao'], '%Y-%m-%d').date()
        pergunta.resposta_correta = request.form['resposta_correta']
        pergunta.tempo_limite = request.form['tempo_limite']
        if tipo == 'multipla_escolha':
            pergunta.opcao_a = request.form.get('opcao_a')
            pergunta.opcao_b = request.form.get('opcao_b')
            pergunta.opcao_c = request.form.get('opcao_c')
            pergunta.opcao_d = request.form.get('opcao_d')
        else:
            pergunta.opcao_a = None
            pergunta.opcao_b = None
            pergunta.opcao_c = None
            pergunta.opcao_d = None
        db.session.commit()
        flash('Pergunta atualizada com sucesso!', 'success')
        return redirect(url_for('pagina_admin'))
    return render_template('edit_question.html', pergunta=pergunta)

@app.route('/admin/delete_question/<int:pergunta_id>', methods=['POST'])
def excluir_pergunta(pergunta_id):
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    pergunta = Pergunta.query.get_or_404(pergunta_id)
    Resposta.query.filter_by(pergunta_id=pergunta.id).delete()
    db.session.delete(pergunta)
    db.session.commit()
    flash('Pergunta e respostas associadas foram excluídas.', 'success')
    return redirect(url_for('pagina_admin'))

@app.route('/admin/analytics')
def pagina_analytics():
    if not session.get('admin_logged_in'): return redirect(url_for('pagina_admin'))
    stats_perguntas_raw = defaultdict(lambda: {'total': 0, 'erros': 0})
    todas_as_respostas = Resposta.query.all()
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
    erros_por_setor = defaultdict(lambda: defaultdict(list))
    respostas_erradas = Resposta.query.filter(Resposta.pontos == 0).join(Usuario).join(Departamento).order_by(Departamento.nome, Usuario.nome).all()
    for r in respostas_erradas:
        setor_nome = r.usuario.departamento.nome
        usuario_nome = r.usuario.nome
        erros_por_setor[setor_nome][usuario_nome].append({'pergunta_texto': r.pergunta.texto, 'data_liberacao': r.pergunta.data_liberacao.strftime('%d/%m/%Y'), 'resposta_dada': r.resposta_dada, 'texto_resposta_dada': get_texto_da_opcao(r.pergunta, r.resposta_dada), 'resposta_correta': r.pergunta.resposta_correta, 'texto_resposta_correta': get_texto_da_opcao(r.pergunta, r.pergunta.resposta_correta)})
    return render_template('analytics.html', stats_perguntas=stats_perguntas, erros_por_setor=erros_por_setor)

# --- ROTA DE INICIALIZAÇÃO DO BANCO DE DADOS ---
@app.route('/_init_db/sua-chave-secreta-dificil-de-adivinhar')
def init_db():
    try:
        print("Apagando e recriando o banco de dados...")
        db.drop_all()
        db.create_all()
        print("Inserindo departamentos e usuários...")
        dados_iniciais = {
            "Suporte": [
                {'nome': 'Ana Oliveira', 'codigo_acesso': '1234', 'email': 'ana.oliveira@empresa.com'},
                {'nome': 'Bruno Costa', 'codigo_acesso': '5678', 'email': 'bruno.costa@empresa.com'},
            ],
            "Vendas": [
                {'nome': 'Carlos Dias', 'codigo_acesso': '9012', 'email': 'carlos.dias@empresa.com'},
                {'nome': 'Daniela Lima', 'codigo_acesso': '3456', 'email': 'daniela.lima@empresa.com'},
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
        return "<h1>Banco de dados inicializado com sucesso!</h1>"
    except Exception as e:
        return f"<h1>Ocorreu um erro:</h1><p>{e}</p>", 500

if __name__ == '__main__':
    app.run(debug=True)