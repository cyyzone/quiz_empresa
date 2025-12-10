from flask import Blueprint, render_template, redirect, url_for, request, session, flash, send_file
from app.models import Usuario, Departamento, Administrador, Pergunta, Resposta, ImagemPergunta, AnexoResposta
from app.extensions import db
from app.utils import validar_linha, allowed_file, _gerar_dados_relatorio, get_texto_da_opcao
from sqlalchemy import or_, func, case, desc, extract
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import io
import cloudinary.uploader
from app.utils import enviar_notificacao_nova_pergunta
from app.models import Usuario

# Cria o Blueprint com o prefixo '/admin'
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- DASHBOARD PRINCIPAL (SEM PERGUNTAS) ---
@admin_bp.route('/', methods=['GET', 'POST'])
def pagina_admin():
    # Limpeza de sessão de CSV
    if 'csv_data' in session:
        session.pop('csv_data', None)
        session.pop('has_valid_rows', None)
        session.pop('csv_headers', None)

    esta_logado = session.get('admin_logged_in', False)
    
    # Lógica de Login
    if request.method == 'POST' and not esta_logado:
        email = request.form.get('email')
        senha = request.form.get('senha')
        admin = Administrador.query.filter_by(email=email).first()
        if admin and admin.check_senha(senha):
            session['admin_logged_in'] = True
            session['admin_nome'] = admin.nome
            session['admin_id'] = admin.id
            esta_logado = True
            flash(f'Bem-vindo, {admin.nome}!', 'success')
        else:
            flash('E-mail ou senha incorretos.', 'danger')
    
    # Variáveis para a dashboard
    usuarios = []
    departamentos = []
    admins = [] 
    contagem_pendentes = 0

    if esta_logado:
        usuarios = Usuario.query.options(joinedload(Usuario.departamento)).order_by(Usuario.nome).all()
        departamentos = Departamento.query.order_by(Departamento.nome).all()
        admins = Administrador.query.order_by(Administrador.nome).all()
        contagem_pendentes = Resposta.query.join(Pergunta).filter(Pergunta.tipo == 'discursiva', Resposta.status_correcao == 'pendente').count()

    return render_template('admin.html', 
                           senha_correta=esta_logado, 
                           usuarios=usuarios, 
                           departamentos=departamentos,
                           admins=admins,
                           contagem_pendentes=contagem_pendentes)

# --- NOVA ROTA: GESTÃO DE PERGUNTAS ---
# Em app/routes/admin.py

@admin_bp.route('/perguntas', methods=['GET'])
def pagina_admin_perguntas():
    if not session.get('admin_logged_in'): 
        return redirect(url_for('admin.pagina_admin'))
        
    departamentos = Departamento.query.order_by(Departamento.nome).all()
    
    # Dicionário para manter os filtros ativos na paginação
    filtros_ativos = {}
    
    query_perguntas = Pergunta.query

    # --- FILTRO 1: Setor ---
    filtro_setor_id = request.args.get('filtro_setor', type=int)
    if filtro_setor_id:
        query_perguntas = query_perguntas.filter(
            or_(
                Pergunta.para_todos_setores == True,
                Pergunta.departamentos.any(Departamento.id == filtro_setor_id)
            )
        )
        filtros_ativos['filtro_setor'] = filtro_setor_id

    # --- FILTRO 2: Tipo de Pergunta
    filtro_tipo = request.args.get('filtro_tipo')
    if filtro_tipo:
        query_perguntas = query_perguntas.filter(Pergunta.tipo == filtro_tipo)
        filtros_ativos['filtro_tipo'] = filtro_tipo

    # --- PAGINAÇÃO ---
    page = request.args.get('page', 1, type=int)
    per_page = 10 
    
    # Ordena por data (mais recente primeiro) e depois por ID
    perguntas_pagination = query_perguntas.order_by(
        Pergunta.data_liberacao.desc(), 
        Pergunta.id.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('admin_perguntas.html', 
                           perguntas=perguntas_pagination, 
                           departamentos=departamentos,
                           filtros=filtros_ativos) # Passamos os filtros para o HTML

# --- CRUD: ADMINISTRADORES ---
@admin_bp.route('/add_admin', methods=['POST'])
def adicionar_admin():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    
    nome = request.form.get('nome')
    email = request.form.get('email')
    senha = request.form.get('senha')
    
    if Administrador.query.filter_by(email=email).first():
        flash('Erro: Este e-mail já é um administrador.', 'danger')
    else:
        novo_admin = Administrador(nome=nome, email=email)
        novo_admin.set_senha(senha)
        db.session.add(novo_admin)
        db.session.commit()
        flash(f'Administrador {nome} adicionado com sucesso!', 'success')
        
    return redirect(url_for('admin.pagina_admin'))  

@admin_bp.route('/edit_admin/<int:admin_id>', methods=['GET', 'POST'])
def editar_admin(admin_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    admin = Administrador.query.get_or_404(admin_id)

    if request.method == 'POST':
        novo_nome = request.form.get('nome')
        novo_email = request.form.get('email')
        nova_senha = request.form.get('senha')

        email_existente = Administrador.query.filter(Administrador.email == novo_email, Administrador.id != admin_id).first()
        if email_existente:
            flash('Erro: Este e-mail já está em uso por outro administrador.', 'danger')
            return render_template('edit_admin.html', admin=admin)

        admin.nome = novo_nome
        admin.email = novo_email
        if nova_senha:
            admin.set_senha(nova_senha)
            flash(f'Dados e senha de "{admin.nome}" atualizados com sucesso!', 'success')
        else:
            flash(f'Dados de "{admin.nome}" atualizados com sucesso!', 'success')

        db.session.commit()
        return redirect(url_for('admin.pagina_admin'))

    return render_template('edit_admin.html', admin=admin)   

@admin_bp.route('/delete_admin/<int:admin_id>', methods=['POST'])
def excluir_admin(admin_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    if admin_id == session.get('admin_id'):
        flash('Erro: Você não pode excluir sua própria conta enquanto está logado.', 'danger')
        return redirect(url_for('admin.pagina_admin'))

    admin = Administrador.query.get_or_404(admin_id)
    try:
        db.session.delete(admin)
        db.session.commit()
        flash(f'Administrador "{admin.nome}" excluído com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir administrador: {e}', 'danger')

    return redirect(url_for('admin.pagina_admin'))                   

# --- CRUD: SETORES ---
@admin_bp.route('/add_department', methods=['POST'])
def adicionar_setor():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    nome_setor = request.form.get('nome')
    if nome_setor and not Departamento.query.filter_by(nome=nome_setor).first():
        novo_depto = Departamento(nome=nome_setor)
        db.session.add(novo_depto)
        db.session.commit()
        flash(f'Setor "{nome_setor}" adicionado com sucesso!', 'success')
    else:
        flash(f'Erro: O nome do setor não pode ser vazio ou já existe.', 'danger')
    return redirect(url_for('admin.pagina_admin'))

@admin_bp.route('/delete_department/<int:departamento_id>', methods=['POST'])
def excluir_setor(departamento_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    depto = Departamento.query.get_or_404(departamento_id)
    if depto.usuarios:
        flash(f'Não é possível excluir o setor "{depto.nome}" pois ele possui usuários.', 'danger')
    else:
        db.session.delete(depto)
        db.session.commit()
        flash(f'Setor "{depto.nome}" excluído com sucesso.', 'success')
    return redirect(url_for('admin.pagina_admin'))

# --- CRUD: USUÁRIOS ---
@admin_bp.route('/add_user', methods=['POST'])
def adicionar_usuario():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    
    codigo = request.form['codigo_acesso']
    email = request.form.get('email')

    if Usuario.query.filter_by(codigo_acesso=codigo).first():
        flash(f'Erro: O código de acesso "{codigo}" já está em uso.', 'danger')
        return redirect(url_for('admin.pagina_admin'))
    
    if email and Usuario.query.filter_by(email=email).first():
        flash(f'Erro: O e-mail "{email}" já está em uso.', 'danger')
        return redirect(url_for('admin.pagina_admin'))
        
    novo_usuario = Usuario(
        nome=request.form['nome'],
        email=email or None,
        codigo_acesso=codigo,
        departamento_id=request.form['departamento_id']
    )
    db.session.add(novo_usuario)
    db.session.commit()
    flash('Usuário adicionado com sucesso!', 'success')
    return redirect(url_for('admin.pagina_admin'))

@admin_bp.route('/edit_user/<int:usuario_id>', methods=['GET'])
def editar_usuario(usuario_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    usuario = Usuario.query.get_or_404(usuario_id)
    departamentos = Departamento.query.order_by(Departamento.nome).all()
    return render_template('edit_user.html', usuario=usuario, departamentos=departamentos)

@admin_bp.route('/edit_user/<int:usuario_id>', methods=['POST'])
def atualizar_usuario(usuario_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    
    usuario = Usuario.query.get_or_404(usuario_id)
    novo_codigo = request.form['codigo_acesso']
    novo_email = request.form.get('email')

    codigo_existente = Usuario.query.filter(Usuario.id != usuario_id, Usuario.codigo_acesso == novo_codigo).first()
    if codigo_existente:
        flash(f'Erro: O código de acesso "{novo_codigo}" já está em uso por outro usuário.', 'danger')
        return redirect(url_for('admin.editar_usuario', usuario_id=usuario_id))

    if novo_email and Usuario.query.filter(Usuario.id != usuario_id, Usuario.email == novo_email).first():
        flash(f'Erro: O e-mail "{novo_email}" já está em uso por outro usuário.', 'danger')
        return redirect(url_for('admin.editar_usuario', usuario_id=usuario_id))

    usuario.nome = request.form['nome']
    usuario.email = novo_email or None
    usuario.codigo_acesso = novo_codigo
    usuario.departamento_id = request.form['departamento_id']
    
    db.session.commit()
    flash(f'Usuário "{usuario.nome}" atualizado com sucesso!', 'success')
    return redirect(url_for('admin.pagina_admin'))

@admin_bp.route('/delete_user/<int:usuario_id>', methods=['POST'])
def excluir_usuario(usuario_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    
    usuario = Usuario.query.get_or_404(usuario_id)
    
    try:
        # 1. Buscar todas as respostas desse usuário
        respostas = Resposta.query.filter_by(usuario_id=usuario_id).all()
        
        for resposta in respostas:
            # 2. Para cada resposta, verifica se tem anexo e apaga-o primeiro
            anexos = AnexoResposta.query.filter_by(resposta_id=resposta.id).all()
            for anexo in anexos:
                # Opcional: Tentar apagar do Cloudinary para não deixar lixo lá
                try:
                    # Extrai o ID público da URL (lógica simples)
                    public_id = anexo.url.split('/')[-1].split('.')[0]
                    cloudinary.uploader.destroy(public_id, resource_type="raw") 
                except Exception as e:
                    print(f"Erro ao apagar anexo do Cloudinary: {e}")
                
                # Apaga o registro do anexo no banco
                db.session.delete(anexo)
            
            # 3. Agora que está sem anexos, podemos apagar a resposta
            db.session.delete(resposta)
            
        # 4. Finalmente, apaga o usuário
        db.session.delete(usuario)
        db.session.commit()
        
        flash(f'Usuário "{usuario.nome}" e todos os seus dados foram excluídos.', 'success')
        
    except Exception as e:
        db.session.rollback() # Cancela se der erro no meio
        flash(f'Erro ao excluir usuário: {e}', 'danger')

    return redirect(url_for('admin.pagina_admin'))
    
# --- CRUD: PERGUNTAS (REDIRECIONA PARA 'admin.pagina_admin_perguntas') ---
@admin_bp.route('/edit_question/<int:pergunta_id>', methods=['GET'])
def editar_pergunta(pergunta_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    pergunta = Pergunta.query.get_or_404(pergunta_id)
    todos_departamentos = Departamento.query.order_by(Departamento.nome).all()
    return render_template('edit_question.html', pergunta=pergunta, todos_departamentos=todos_departamentos)

@admin_bp.route('/add_question', methods=['POST'])
def adicionar_pergunta():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    
    tipo = request.form.get('tipo')
    data_str = request.form.get('data_liberacao')
    
    try:
        data_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Data inválida.', 'danger')
        return redirect(url_for('admin.pagina_admin_perguntas'))

    nova_pergunta = Pergunta(
        tipo=tipo,
        texto=request.form.get('texto'),
        explicacao=request.form.get('explicacao'),
        data_liberacao=data_obj
    )

    db.session.add(nova_pergunta)
    db.session.commit()

    arquivos = request.files.getlist('imagem_pergunta') 
    for file in arquivos:
        if file and file.filename != '' and allowed_file(file.filename):
            upload_result = cloudinary.uploader.upload(file, folder="perguntas")
            imagem_url = upload_result.get('secure_url')
            if not nova_pergunta.imagem_pergunta:
                nova_pergunta.imagem_pergunta = imagem_url
            nova_imagem_banco = ImagemPergunta(url=imagem_url, pergunta=nova_pergunta)
            db.session.add(nova_imagem_banco)

    if 'para_todos_setores' in request.form:
        nova_pergunta.para_todos_setores = True
    else:
        nova_pergunta.para_todos_setores = False
        departamento_ids = request.form.getlist('departamentos')
        if departamento_ids:
            departamentos_selecionados = Departamento.query.filter(Departamento.id.in_(departamento_ids)).all()
            nova_pergunta.departamentos = departamentos_selecionados
    
    if tipo in ['multipla_escolha', 'verdadeiro_falso']:
        nova_pergunta.resposta_correta = request.form.get('resposta_correta')
        nova_pergunta.tempo_limite = request.form.get('tempo_limite')
        
        if tipo == 'multipla_escolha':
            nova_pergunta.opcao_a = request.form.get('opcao_a')
            nova_pergunta.opcao_b = request.form.get('opcao_b')
            nova_pergunta.opcao_c = request.form.get('opcao_c')
            nova_pergunta.opcao_d = request.form.get('opcao_d')
    else: 
        nova_pergunta.tempo_limite = None
        nova_pergunta.resposta_correta = None
        nova_pergunta.opcao_a = None
        nova_pergunta.opcao_b = None
        nova_pergunta.opcao_c = None
        nova_pergunta.opcao_d = None

    db.session.commit()

    # --- INÍCIO DA LÓGICA DE NOTIFICAÇÃO ---
#    try:
 #       usuarios_alvo = []
        
  #      if nova_pergunta.para_todos_setores:
 #           # Se for para todos, pega todos os usuários que têm e-mail
   #         usuarios_alvo = Usuario.query.filter(Usuario.email != None).all()
  #      else:
            # Se for para setores específicos, faz um JOIN para achar os usuários desses setores
            # Filtrando apenas pelos departamentos vinculados à pergunta recém-criada
 #           usuarios_alvo = Usuario.query.join(Departamento).filter(
  #              Departamento.perguntas.any(id=nova_pergunta.id),
   #             Usuario.email != None
  #          ).all()

        # Chama a função que dispara os e-mails em segundo plano (Thread)
#        enviar_notificacao_nova_pergunta(usuarios_alvo, nova_pergunta.texto)
        
  #      flash('Pergunta adicionada e notificação enviada com sucesso!', 'success')

  #  except Exception as e:
  #      # Se der erro no e-mail, não queremos que pareça que a pergunta não foi salva
   #     flash(f'Pergunta salva, mas ocorreu um erro ao enviar as notificações: {e}', 'warning')
    # --- FIM DA LÓGICA DE NOTIFICAÇÃO ---
   # flash('Pergunta adicionada com sucesso!', 'success') 
    
    return redirect(url_for('admin.pagina_admin_perguntas'))
# Em app/routes/admin.py

@admin_bp.route('/notificar_lote', methods=['POST'])
def notificar_lote():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    
    # 1. Busca perguntas liberadas HOJE
    hoje = (datetime.utcnow() - timedelta(hours=3)).date()
    perguntas_hoje = Pergunta.query.filter_by(data_liberacao=hoje).all()
    
    if not perguntas_hoje:
        flash('Nenhuma pergunta encontrada com a data de hoje para notificar.', 'warning')
        return redirect(url_for('admin.pagina_admin_perguntas'))

    # 2. Busca usuários
    usuarios = Usuario.query.filter(Usuario.email != None).all()
    
    # 3. Dispara o envio
    from app.utils import enviar_email_resumo_do_dia
    
    # GERA O LINK AQUI (Enquanto ainda estamos na requisição ativa)
    link_acesso = url_for('auth.pagina_login', _external=True)
    
    titulos_perguntas = [p.texto for p in perguntas_hoje]
    
    # Passa o link_acesso para a função
    enviar_email_resumo_do_dia(usuarios, titulos_perguntas, link_acesso)
    
    flash(f'Processo de notificação iniciado para {len(perguntas_hoje)} perguntas de hoje!', 'success')
    return redirect(url_for('admin.pagina_admin_perguntas'))

@admin_bp.route('/edit_question/<int:pergunta_id>', methods=['POST'])
def atualizar_pergunta(pergunta_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    pergunta = Pergunta.query.get_or_404(pergunta_id)
    
    pergunta.tipo = request.form.get('tipo')
    pergunta.texto = request.form.get('texto')
    pergunta.explicacao = request.form.get('explicacao')
    
    try:
        pergunta.data_liberacao = datetime.strptime(request.form.get('data_liberacao'), '%Y-%m-%d').date()
    except ValueError:
        flash('Data inválida.', 'danger')
        return redirect(url_for('admin.editar_pergunta', pergunta_id=pergunta_id))

    arquivos = request.files.getlist('imagem_pergunta')
    for file in arquivos:
        if file and file.filename != '' and allowed_file(file.filename):
            upload_result = cloudinary.uploader.upload(file, folder="perguntas_quiz")
            imagem_url = upload_result.get('secure_url')
            if not pergunta.imagem_pergunta:
                pergunta.imagem_pergunta = imagem_url
            nova_img = ImagemPergunta(url=imagem_url, pergunta=pergunta)
            db.session.add(nova_img)

    pergunta.departamentos.clear()
    if 'para_todos_setores' in request.form:
        pergunta.para_todos_setores = True
    else:
        pergunta.para_todos_setores = False
        departamento_ids = request.form.getlist('departamentos')
        if departamento_ids:
            departamentos_selecionados = Departamento.query.filter(Departamento.id.in_(departamento_ids)).all()
            pergunta.departamentos = departamentos_selecionados

    if pergunta.tipo in ['multipla_escolha', 'verdadeiro_falso']:
        pergunta.resposta_correta = request.form.get('resposta_correta')
        pergunta.tempo_limite = request.form.get('tempo_limite')
        if pergunta.tipo == 'multipla_escolha':
            pergunta.opcao_a = request.form.get('opcao_a')
            pergunta.opcao_b = request.form.get('opcao_b')
            pergunta.opcao_c = request.form.get('opcao_c')
            pergunta.opcao_d = request.form.get('opcao_d')
        else:
            pergunta.opcao_a, pergunta.opcao_b, pergunta.opcao_c, pergunta.opcao_d = None, None, None, None
    else:
        pergunta.resposta_correta, pergunta.tempo_limite = None, None
        pergunta.opcao_a, pergunta.opcao_b, pergunta.opcao_c, pergunta.opcao_d = None, None, None, None
        
    db.session.commit()
    flash('Pergunta atualizada com sucesso!', 'success')
    return redirect(url_for('admin.pagina_admin_perguntas'))

@admin_bp.route('/delete_question/<int:pergunta_id>', methods=['POST'])
def excluir_pergunta(pergunta_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
        
    pergunta = Pergunta.query.get_or_404(pergunta_id)
    try:
        if pergunta.imagem_pergunta:
            public_id = pergunta.imagem_pergunta.split('/')[-1].split('.')[0]
            cloudinary.uploader.destroy(public_id)

        respostas_para_excluir = Resposta.query.filter_by(pergunta_id=pergunta.id).all()
        for resposta in respostas_para_excluir:
            if resposta.anexo_resposta:
                public_id_anexo = resposta.anexo_resposta.split('/')[-1].split('.')[0]
                cloudinary.uploader.destroy(public_id_anexo, resource_type="raw")
    except Exception:
        pass

    Resposta.query.filter_by(pergunta_id=pergunta.id).delete()
    db.session.delete(pergunta)
    db.session.commit()
    flash('Pergunta e todas as suas respostas foram excluídas com sucesso.', 'success')
    return redirect(url_for('admin.pagina_admin_perguntas'))

# --- UPLOAD E CSV ---
@admin_bp.route('/upload_planilha', methods=['POST'])
def upload_planilha():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    
    arquivo = request.files.get('arquivo_planilha')
    if not arquivo or not (arquivo.filename.lower().endswith(('.xls', '.xlsx', '.csv'))):
        flash('Arquivo inválido. Envie uma planilha Excel (.xls, .xlsx) ou CSV (.csv).', 'danger')
        return redirect(url_for('admin.pagina_admin_perguntas'))
    
    try:
        if arquivo.filename.lower().endswith('.csv'):
            df = pd.read_csv(arquivo, sep=None, engine='python', encoding='utf-8')
        else:
            df = pd.read_excel(arquivo)
            
        df = df.fillna('')
        if 'data_liberacao' in df.columns:
            df['data_liberacao'] = pd.to_datetime(df['data_liberacao'], errors='coerce').dt.strftime('%d/%m/%Y').fillna(df['data_liberacao'])

        for col in df.columns:
            df[col] = df[col].astype(str).str.replace(r'\.0$', '', regex=True)

        headers = df.columns.tolist()
        dados_da_planilha = df.to_dict(orient='records')
        
        validated_data = []
        has_valid_rows = False
        for row in dados_da_planilha:
            is_valid, errors = validar_linha(row)
            if is_valid: has_valid_rows = True
            validated_data.append({'data': row, 'is_valid': is_valid, 'errors': errors})
            
        session['csv_headers'] = headers
        session['csv_data'] = validated_data
        session['has_valid_rows'] = has_valid_rows
        
        return redirect(url_for('admin.preview_csv'))
        
    except Exception as e:
        flash(f"Ocorreu um erro ao processar o arquivo: {e}", "danger")
        return redirect(url_for('admin.pagina_admin_perguntas'))

@admin_bp.route('/preview_csv')
def preview_csv():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    validated_data = session.get('csv_data', [])
    has_valid_rows = session.get('has_valid_rows', False)
    headers = session.get('csv_headers', [])
    return render_template('preview_csv.html', data=validated_data, has_valid_rows=has_valid_rows, headers=headers)

@admin_bp.route('/processar_edicao_csv', methods=['POST'])
def processar_edicao_csv():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))

    rows_data = defaultdict(dict)
    for key, value in request.form.items():
        if key.startswith('row-'):
            parts = key.split('-', 2)
            row_index = int(parts[1])
            col_name = parts[2]
            rows_data[row_index][col_name] = value

    success_count = 0
    error_count = 0
    
    for row_index in sorted(rows_data.keys()):
        row = rows_data[row_index]
        is_valid, errors = validar_linha(row) 
        
        if is_valid:
            try:
                data_obj = datetime.strptime(row['data_liberacao'], '%d/%m/%Y').date()
                nova_pergunta = Pergunta(
                    tipo=row['tipo'], 
                    texto=row['texto'],
                    explicacao=row.get('explicacao'),
                    opcao_a=row.get('opcao_a') or None, 
                    opcao_b=row.get('opcao_b') or None,
                    opcao_c=row.get('opcao_c') or None, 
                    opcao_d=row.get('opcao_d') or None,
                    resposta_correta=row.get('resposta_correta') or None, 
                    data_liberacao=data_obj,
                    tempo_limite=int(float(row['tempo_limite'])) if row.get('tempo_limite') else None
                )
                campo_setor = row.get('setor', '').strip()
                if not campo_setor or campo_setor.lower() == 'todos':
                    nova_pergunta.para_todos_setores = True
                else:
                    nova_pergunta.para_todos_setores = False
                    nomes_setores = [s.strip() for s in campo_setor.split(',') if s.strip()]
                    if nomes_setores:
                        deptos = Departamento.query.filter(Departamento.nome.in_(nomes_setores)).all()
                        nova_pergunta.departamentos = deptos
                
                db.session.add(nova_pergunta)
                db.session.commit()
                success_count += 1
            except Exception:
                db.session.rollback()
                error_count += 1
        else:
            error_count += 1

    session.pop('csv_data', None)
    session.pop('has_valid_rows', None)
    session.pop('csv_headers', None)
    
    if error_count > 0:
        flash(f'Importação parcial: {success_count} salvas. {error_count} ignoradas.', 'warning')
    else:
        flash(f'Importação concluída! {success_count} perguntas importadas.', 'success')
        
    return redirect(url_for('admin.pagina_admin_perguntas'))

# --- CORREÇÕES E RELATÓRIOS ---
@admin_bp.route('/correcoes')
def pagina_correcoes():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    
    usuarios_disponiveis = Usuario.query.order_by(Usuario.nome).all()
    usuario_selecionado_id = request.args.get('usuario_id', type=int)
    status_selecionado = request.args.get('status', 'pendente')
    page = request.args.get('page', 1, type=int)
    per_page = 10 
    
    query = Resposta.query.join(Pergunta).filter(Pergunta.tipo == 'discursiva')
    if status_selecionado != 'todos': query = query.filter(Resposta.status_correcao == status_selecionado)
    if usuario_selecionado_id: query = query.filter(Resposta.usuario_id == usuario_selecionado_id)
    
    respostas_pagination = query.join(Usuario).order_by(Resposta.data_resposta.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('correcoes.html', 
                           respostas=respostas_pagination, 
                           usuarios_disponiveis=usuarios_disponiveis, 
                           usuario_selecionado_id=usuario_selecionado_id,
                           status_selecionado=status_selecionado)

@admin_bp.route('/corrigir/<int:resposta_id>', methods=['POST'])
def corrigir_resposta(resposta_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    resposta = Resposta.query.get_or_404(resposta_id)
    novo_status = request.form.get('status')
    feedback_texto = request.form.get('feedback', '')
    
    if novo_status in ['correto', 'incorreto', 'parcialmente_correto']:
        resposta.status_correcao = novo_status
        resposta.feedback_admin = feedback_texto
        if novo_status == 'correto': resposta.pontos = 100
        elif novo_status == 'parcialmente_correto': resposta.pontos = 50
        else: resposta.pontos = 0
        db.session.commit()
        flash('Resposta avaliada com sucesso!', 'success')
    return redirect(url_for('admin.pagina_correcoes'))

@admin_bp.route('/relatorios')
def pagina_relatorios():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    depto_selecionado_id = request.args.get('departamento_id', type=int)
    departamentos = Departamento.query.order_by(Departamento.nome).all()
    dados_relatorio = _gerar_dados_relatorio(depto_selecionado_id)
    return render_template('relatorios.html', 
                           relatorios=dados_relatorio, 
                           departamentos=departamentos, 
                           depto_selecionado_id=depto_selecionado_id)

@admin_bp.route('/relatorios/exportar')
def exportar_relatorios():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    depto_selecionado_id = request.args.get('departamento_id', type=int)
    dados_relatorio = _gerar_dados_relatorio(depto_selecionado_id)
    if not dados_relatorio:
        flash("Nenhum dado para exportar.", "warning")
        return redirect(url_for('admin.pagina_relatorios'))

    df = pd.DataFrame(dados_relatorio)
    df = df.rename(columns={'nome': 'Colaborador', 'setor': 'Setor', 'total_respostas': 'Respostas Totais', 'respostas_corretas': 'Respostas Corretas', 'aproveitamento': 'Aproveitamento (%)', 'pontuacao_total': 'Pontuação Total'})
    df['Aproveitamento (%)'] = df['Aproveitamento (%)'].map('{:.1f}%'.format)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio de Desempenho')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='relatorio_desempenho_quiz.xlsx')

@admin_bp.route('/relatorios/exportar_detalhado')
def exportar_respostas_detalhado():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))

    # Captura filtros
    depto_selecionado_id = request.args.get('departamento_id', type=int)
    usuario_selecionado_id = request.args.get('usuario_id', type=int)
    filtro_tipo = request.args.get('filtro_tipo', 'todos')
    filtro_acertos = request.args.get('filtro_acertos', 'erros')

    query = Resposta.query.join(Usuario).join(Departamento).join(Pergunta)

    # Aplica filtros
    if depto_selecionado_id: query = query.filter(Usuario.departamento_id == depto_selecionado_id)
    if usuario_selecionado_id: query = query.filter(Resposta.usuario_id == usuario_selecionado_id)
    
    if filtro_tipo and filtro_tipo != 'todos':
        query = query.filter(Pergunta.tipo == filtro_tipo)

    if filtro_acertos == 'acertos':
        query = query.filter(or_(Resposta.pontos > 0, Resposta.status_correcao.in_(['correto', 'parcialmente_correto'])))
    elif filtro_acertos == 'erros':
        query = query.filter(or_(Resposta.pontos == 0, Resposta.status_correcao == 'incorreto'))

    todas_as_respostas = query.order_by(Departamento.nome, Usuario.nome, Resposta.data_resposta).all()

    if not todas_as_respostas:
        flash("Nenhuma resposta encontrada para exportar com os filtros selecionados.", "warning")
        return redirect(url_for('admin.pagina_analytics'))

    # Gera Excel (Igual ao anterior)
    dados_para_planilha = []
    for r in todas_as_respostas:
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
        
    df = pd.DataFrame(dados_para_planilha)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio_Completo')
    output.seek(0)

    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name='relatorio_completo_respostas.xlsx')

@admin_bp.route('/analytics')
def pagina_analytics():
    if not session.get('admin_logged_in'): return redirect(url_for('admin.pagina_admin'))
    
    usuarios_disponiveis = Usuario.query.order_by(Usuario.nome).all()
    departamentos = Departamento.query.order_by(Departamento.nome).all()
    
    usuario_selecionado_id = request.args.get('usuario_id', type=int)
    depto_selecionado_id = request.args.get('departamento_id', type=int)
    
    # NOVOS PADRÕES:
    # Se não vier nada na URL, o padrão do acerto continua sendo 'erros' (foco em correção)
    # Mas agora aceita 'todos'.
    filtro_acertos = request.args.get('filtro_acertos', 'erros') 
    filtro_tipo = request.args.get('filtro_tipo', 'todos') # Padrão agora é 'todos' se não especificado

    # --- PARTE 1: ESTATÍSTICAS ---
    query_stats = db.session.query(
        Pergunta.texto,
        func.count(Resposta.id).label('total'),
        func.sum(case((Resposta.pontos == 0, 1), else_=0)).label('erros')
    ).join(Resposta).join(Usuario)
    
    # Lógica de Filtro Tipo (Atualizada para aceitar 'todos')
    if filtro_tipo and filtro_tipo != 'todos':
        query_stats = query_stats.filter(Pergunta.tipo == filtro_tipo)
    
    if depto_selecionado_id: query_stats = query_stats.filter(Usuario.departamento_id == depto_selecionado_id)
    if usuario_selecionado_id: query_stats = query_stats.filter(Resposta.usuario_id == usuario_selecionado_id)
    
    resultados_agrupados = query_stats.group_by(Pergunta.id).all()
    
    stats_perguntas = []
    for row in resultados_agrupados:
        percentual = (row.erros / row.total * 100) if row.total > 0 else 0
        stats_perguntas.append({'texto': row.texto, 'total': row.total, 'erros': row.erros, 'percentual': percentual})
    stats_perguntas.sort(key=lambda x: x['percentual'], reverse=True)

    # --- PARTE 2: ANÁLISE DETALHADA ---
    query_detalhada = Resposta.query.join(Pergunta).join(Usuario).join(Departamento)

    # Filtro Tipo
    if filtro_tipo and filtro_tipo != 'todos':
        query_detalhada = query_detalhada.filter(Pergunta.tipo == filtro_tipo)

    # Filtro Acertos/Erros (Atualizado com opção 'todos')
    if filtro_acertos == 'acertos':
        query_detalhada = query_detalhada.filter(or_(Resposta.pontos > 0, Resposta.status_correcao.in_(['correto', 'parcialmente_correto'])))
    elif filtro_acertos == 'erros':
        query_detalhada = query_detalhada.filter(or_(Resposta.pontos == 0, Resposta.status_correcao == 'incorreto'))
    # Se for 'todos', não aplicamos nenhum filtro extra aqui (mostra tudo)
        
    if usuario_selecionado_id: query_detalhada = query_detalhada.filter(Resposta.usuario_id == usuario_selecionado_id)
    if depto_selecionado_id: query_detalhada = query_detalhada.filter(Usuario.departamento_id == depto_selecionado_id)
    
    # Paginação
    page = request.args.get('page', 1, type=int)
    per_page = 10 
    
    respostas_pagination = query_detalhada.order_by(Departamento.nome, Usuario.nome, Resposta.data_resposta.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    # Agrupamento Visual
    dados_agrupados = defaultdict(lambda: defaultdict(list))
    for r in respostas_pagination.items:
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
                           respostas_pagination=respostas_pagination,
                           usuarios_disponiveis=usuarios_disponiveis,
                           departamentos=departamentos,
                           usuario_selecionado_id=usuario_selecionado_id,
                           depto_selecionado_id=depto_selecionado_id,
                           filtro_acertos=filtro_acertos,
                           filtro_tipo=filtro_tipo)
                           
@admin_bp.route('/init_db/<secret_key>')
def init_db(secret_key):
    if secret_key != 'resetar-banco-123': return "Chave secreta inválida.", 403
    try:
        from app.models import Departamento, Usuario, Pergunta, Resposta, Administrador
        db.drop_all()
        db.create_all()
        return "<h1>Banco de dados reinicializado com sucesso!</h1>"
    except Exception as e:
        return f"<h1>Ocorreu um erro:</h1><p>{e}</p>", 500