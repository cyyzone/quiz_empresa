from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from app.models import Usuario, Pergunta, Resposta, Departamento, AnexoResposta
from app.extensions import db
from app.utils import allowed_file
from sqlalchemy import or_, func, desc
from datetime import date
import cloudinary.uploader
from datetime import datetime, timedelta

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session: return redirect(url_for('auth.pagina_login'))

    usuario_id = session['usuario_id']
    usuario = Usuario.query.get(usuario_id)
    hoje = (datetime.utcnow() - timedelta(hours=3)).date()
    
    # OTIMIZAÇÃO: Subquery
    sq_respondidas = db.session.query(Resposta.pergunta_id).filter(Resposta.usuario_id == usuario_id).subquery()

    contagem_quiz_pendente = Pergunta.query.filter(
        Pergunta.tipo != 'discursiva',
        Pergunta.data_liberacao <= hoje,
        ~Pergunta.id.in_(sq_respondidas),
        or_(Pergunta.para_todos_setores == True, Pergunta.departamentos.any(Departamento.id == usuario.departamento_id))
    ).count()

    contagem_atividades_pendentes = Pergunta.query.filter(
        Pergunta.tipo == 'discursiva',
        Pergunta.data_liberacao <= hoje,
        ~Pergunta.id.in_(sq_respondidas),
        or_(Pergunta.para_todos_setores == True, Pergunta.departamentos.any(Departamento.id == usuario.departamento_id))
    ).count()

    contagem_novos_feedbacks = Resposta.query.join(Pergunta).filter(
        Resposta.usuario_id == usuario_id,
        Pergunta.tipo == 'discursiva',
        Resposta.status_correcao.in_(['correto', 'incorreto']),
        Resposta.feedback_visto == False
    ).count()
    
    return render_template('dashboard.html', 
                           nome=session['usuario_nome'],
                           contagem_quiz=contagem_quiz_pendente,
                           contagem_atividades=contagem_atividades_pendentes,
                           contagem_feedbacks=contagem_novos_feedbacks)

@user_bp.route('/quiz')
@user_bp.route('/quiz/<categoria>')
def pagina_quiz(categoria=None):
    if 'usuario_id' not in session: return redirect(url_for('auth.pagina_login'))
    usuario_id = session['usuario_id']
    usuario = Usuario.query.get(usuario_id)
    hoje = (datetime.utcnow() - timedelta(hours=3)).date()
    
    sq_respondidas = db.session.query(Resposta.pergunta_id).filter(Resposta.usuario_id == usuario_id).subquery()

    # Monta a busca básica
    query = Pergunta.query.filter(
        Pergunta.tipo != 'discursiva',
        Pergunta.data_liberacao <= hoje,
        ~Pergunta.id.in_(sq_respondidas),
        or_(Pergunta.para_todos_setores == True, Pergunta.departamentos.any(Departamento.id == usuario.departamento_id))
    )

    if categoria:
        # --- CORREÇÃO AQUI ---
        # Verifica se é "Sem Classificação" para tratar nulos OU texto,
        # e usa func.lower() para garantir que "duvidas_atividades" encontre "Duvidas_Atividades"
        if categoria == "Sem Classificação":
             query = query.filter(or_(
                 Pergunta.categoria.is_(None), 
                 Pergunta.categoria == '',
                 func.lower(Pergunta.categoria) == 'sem classificação' # Caso esteja escrito no banco
             ))
        else:
             # Compara transformando tudo em minúsculo
             query = query.filter(func.lower(Pergunta.categoria) == categoria.lower())
        # ---------------------

    proxima_pergunta = query.order_by(Pergunta.data_liberacao).first()

    if proxima_pergunta:
        return render_template('quiz.html', pergunta=proxima_pergunta, categoria_atual=categoria)
    else:
        msg = f'Você finalizou o módulo {categoria}!' if categoria else 'Parabéns, todas as perguntas respondidas!'
        flash(msg, 'success')
        return redirect(url_for('user.dashboard'))

@user_bp.route('/atividades')
@user_bp.route('/atividades/<categoria>')
def pagina_atividades(categoria=None):
    if 'usuario_id' not in session: return redirect(url_for('auth.pagina_login'))
    
    hoje = (datetime.utcnow() - timedelta(hours=3)).date()
    usuario_id = session['usuario_id']
    usuario = Usuario.query.get(usuario_id)
    page = request.args.get('page', 1, type=int)
    per_page = 5 

    sq_respondidas = db.session.query(Resposta.pergunta_id).filter(Resposta.usuario_id == usuario_id).subquery()

    # Busca básica
    query_atividades = Pergunta.query.filter(
        Pergunta.tipo == 'discursiva',
        Pergunta.data_liberacao <= hoje,
        ~Pergunta.id.in_(sq_respondidas),
        or_(Pergunta.para_todos_setores == True, Pergunta.departamentos.any(Departamento.id == usuario.departamento_id))
    )

    if categoria:
        # --- CORREÇÃO AQUI ---
        if categoria == "Sem Classificação":
            query_atividades = query_atividades.filter(or_(
                Pergunta.categoria.is_(None), 
                Pergunta.categoria == '',
                func.lower(Pergunta.categoria) == 'sem classificação'
            ))
        else:
            # Compara transformando tudo em minúsculo
            query_atividades = query_atividades.filter(func.lower(Pergunta.categoria) == categoria.lower())
        # ---------------------

    # Ordena e Pagina
    query_atividades = query_atividades.order_by(Pergunta.data_liberacao.desc())
    atividades_pagination = query_atividades.paginate(page=page, per_page=per_page, error_out=False)

    return render_template('atividades.html', 
                           atividades=atividades_pagination, 
                           respostas_dadas={},
                           categoria_atual=categoria)

@user_bp.route('/atividade/<int:pergunta_id>', methods=['GET', 'POST'])
def responder_atividade(pergunta_id):
    if 'usuario_id' not in session: return redirect(url_for('auth.pagina_login'))
    pergunta = Pergunta.query.get_or_404(pergunta_id)

    if request.method == 'POST':
        texto_resposta = request.form['texto_discursivo']
        nova_resposta = Resposta(
            usuario_id=session['usuario_id'],
            pergunta_id=pergunta.id,
            texto_discursivo=texto_resposta,
            status_correcao='pendente'
        )
        db.session.add(nova_resposta)
        db.session.commit()

        arquivos = request.files.getlist('anexo_resposta')
        for file in arquivos:
            if file and file.filename != '' and allowed_file(file.filename):
                upload_result = cloudinary.uploader.upload(file, resource_type="auto")
                anexo_url = upload_result.get('secure_url')
                if not nova_resposta.anexo_resposta:
                    nova_resposta.anexo_resposta = anexo_url
                novo_anexo = AnexoResposta(url=anexo_url, resposta=nova_resposta)
                db.session.add(novo_anexo)
        
        db.session.commit()
        flash('Sua resposta foi enviada para avaliação!', 'success')
        return redirect(url_for('user.pagina_atividades'))

    return render_template('atividade_responder.html', pergunta=pergunta)

@user_bp.route('/responder', methods=['POST'])
def processa_resposta():
    if 'usuario_id' not in session: return redirect(url_for('auth.pagina_login'))
    
    pergunta_id = request.form['pergunta_id']
    resposta_usuario = request.form.get('resposta', '')
    
    # --- NOVO: Captura a categoria que veio oculta do formulário ---
    categoria_recebida = request.form.get('categoria')
    if categoria_recebida == '': 
        categoria_recebida = None
    # ---------------------------------------------------------------

    pergunta = Pergunta.query.get(pergunta_id)
    pontos = 0
    resultado = ''

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
    
    nova_resposta = Resposta(
        pontos=pontos, 
        usuario_id=session['usuario_id'], 
        pergunta_id=pergunta_id, 
        resposta_dada=resposta_usuario, 
        status_correcao='correto' if pontos > 0 else 'incorreto'
    )
    db.session.add(nova_resposta)
    db.session.commit()
    
    # --- AJUSTE: Passamos a 'categoria_atual' para o template ---
    return render_template('feedback_quiz.html', 
                           resultado=resultado, 
                           pontos=pontos, 
                           pergunta=pergunta,
                           categoria_atual=categoria_recebida)

@user_bp.route('/minhas-respostas')
def minhas_respostas():
    if 'usuario_id' not in session: return redirect(url_for('auth.pagina_login'))
    usuario_id = session['usuario_id']

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
    
    filtro_tipo = request.args.get('filtro_tipo', '')
    filtro_resultado = request.args.get('filtro_resultado', '')
    page = request.args.get('page', 1, type=int)
    per_page = 5 

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
    
    respostas_pagination = query.order_by(Resposta.data_resposta.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('minhas_respostas.html', respostas=respostas_pagination, filtro_tipo=filtro_tipo, filtro_resultado=filtro_resultado)

@user_bp.route('/ranking')
def pagina_ranking():
    if 'usuario_id' not in session: return redirect(url_for('auth.pagina_login'))
    
    # OTIMIZAÇÃO: Query Única
    ranking_query = db.session.query(
        Departamento.id,
        Departamento.nome,
        func.coalesce(func.sum(Resposta.pontos), 0).label('pontos_totais'),
        func.count(func.distinct(Usuario.id)).label('num_usuarios')
    ).join(Usuario, Departamento.id == Usuario.departamento_id)\
     .outerjoin(Resposta, Usuario.id == Resposta.usuario_id)\
     .group_by(Departamento.id, Departamento.nome).all()

    ranking_final = []
    for row in ranking_query:
        media = row.pontos_totais / row.num_usuarios if row.num_usuarios > 0 else 0
        ranking_final.append({
            'id': row.id, 
            'nome': row.nome, 
            'pontos_totais': row.pontos_totais, 
            'num_usuarios': row.num_usuarios, 
            'pontuacao_proporcional': round(media)
        })
        
    ranking_final.sort(key=lambda x: x['pontuacao_proporcional'], reverse=True)
    return render_template('ranking.html', ranking=ranking_final)

@user_bp.route('/ranking/<int:departamento_id>')
def pagina_ranking_detalhe(departamento_id):
    if 'usuario_id' not in session: return redirect(url_for('auth.pagina_login'))
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

# app/routes/user.py

# app/routes/user.py

# app/routes/user.py

@user_bp.route('/temas/<tipo_origem>')
def selecionar_tema(tipo_origem):
    if 'usuario_id' not in session: return redirect(url_for('auth.pagina_login'))
    
    usuario_id = session['usuario_id']
    usuario = Usuario.query.get(usuario_id)
    hoje = (datetime.utcnow() - timedelta(hours=3)).date()
    
    tipo_filtro = 'discursiva' if tipo_origem == 'atividades' else 'multipla_escolha'
    
    # 1. Busca as categorias cruas do banco
    query = db.session.query(
        Pergunta.categoria, 
        func.count(Pergunta.id)
    ).filter(
        Pergunta.tipo == tipo_filtro if tipo_origem == 'atividades' else Pergunta.tipo != 'discursiva',
        Pergunta.data_liberacao <= hoje,
        or_(Pergunta.para_todos_setores == True, Pergunta.departamentos.any(Departamento.id == usuario.departamento_id))
    ).group_by(Pergunta.categoria).all()
    
    # 2. Processamento Inteligente (Agrupa nomes parecidos)
    categorias_processadas = {}
    
    for nome, qtd in query:
        if nome: # Ignora vazios
            # Padroniza: Remove espaços extras e deixa tudo Capitalizado
            nome_limpo = nome.strip().title() 
            
            if nome_limpo in categorias_processadas:
                categorias_processadas[nome_limpo] += qtd
            else:
                categorias_processadas[nome_limpo] = qtd
    
    # Transforma de volta em lista para o template
    lista_categorias = [{'nome': k, 'qtd': v} for k, v in categorias_processadas.items()]

    # Ordena alfabeticamente
    lista_categorias = sorted(lista_categorias, key=lambda x: x['nome'])

    return render_template('selecao_temas.html', 
                           categorias=lista_categorias, 
                           origem=tipo_origem)