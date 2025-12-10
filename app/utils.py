from flask import current_app
from datetime import datetime, timedelta
from .models import Usuario, Departamento, Resposta
from .extensions import db
from sqlalchemy import func, case, or_

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def format_datetime_local(valor_utc):
    """Filtro para converter uma data UTC para o fuso local (UTC-3)."""
    if not valor_utc:
        return ""
    fuso_local = valor_utc - timedelta(hours=3)
    return fuso_local.strftime('%d/%m/%Y às %H:%M')

def otimizar_img_filter(url):
    """Insere parâmetros do Cloudinary para reduzir tamanho."""
    if not url:
        return ""
    if 'cloudinary.com' in url and '/upload/' in url:
        return url.replace('/upload/', '/upload/w_800,q_auto,f_auto/')
    return url

def get_texto_da_opcao(pergunta, opcao):
    if opcao == 'a': return pergunta.opcao_a
    if opcao == 'b': return pergunta.opcao_b
    if opcao == 'c': return pergunta.opcao_c
    if opcao == 'd': return pergunta.opcao_d
    if opcao == 'v': return "Verdadeiro"
    if opcao == 'f': return "Falso"
    return ""

def validar_linha(row):
    """Valida uma linha da planilha de importação."""
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

def _gerar_dados_relatorio(departamento_id=None):
    """Função auxiliar para relatórios."""
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