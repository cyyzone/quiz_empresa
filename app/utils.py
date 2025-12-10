from flask_mail import Message
from flask import current_app, url_for
from .extensions import mail
from threading import Thread
from datetime import datetime, timedelta
from .models import Usuario, Departamento, Resposta
from .extensions import db
from sqlalchemy import func, case, or_

def enviar_emails_em_lote(app, usuarios, pergunta_texto, link_acesso):
    """
    Função que roda em segundo plano.
    Recebe o 'link_acesso' já pronto para não precisar de usar url_for aqui.
    """
    with app.app_context():
        with mail.connect() as conn:
            for usuario in usuarios:
                if not usuario.email:
                    continue
                
                try:
                    # Tratamento do Assunto
                    assunto_curto = (pergunta_texto[:50] + '...') if len(pergunta_texto) > 50 else pergunta_texto

                    msg = Message(
                        subject=f"Nova Pergunta: {assunto_curto}",
                        recipients=[usuario.email]
                    )
                    
                    msg.body = f"""
                    Olá, {usuario.nome}!
                    
                    Uma nova pergunta acabou de ser liberada no Quiz:
                    
                    "{pergunta_texto}"
                    
                    Entre agora para responder e garantir seus pontos!
                    Link: {link_acesso}
                    
                    Atenciosamente,
                    Equipe de Treinamento
                    """
                    
                    conn.send(msg)
                    print(f"Notificação enviada para: {usuario.nome}")
                    
                except Exception as e:
                    print(f"Falha ao enviar para {usuario.nome}: {e}")

def enviar_notificacao_nova_pergunta(usuarios, pergunta_texto):
    """
    Função chamada pela rota. Gera o link e inicia a Thread.
    """
    app = current_app._get_current_object()
    
    # CORREÇÃO: Geramos o link AQUI, onde ainda temos o contexto da requisição
    link_acesso = url_for('auth.pagina_login', _external=True)
    
    # Passamos o link pronto como argumento para a thread
    Thread(target=enviar_emails_em_lote, args=(app, usuarios, pergunta_texto, link_acesso)).start()


def enviar_emails_resumo_thread(app, usuarios, titulos, link_acesso):
    with app.app_context():
        with mail.connect() as conn:
            for usuario in usuarios:
                try:
                    qtd = len(titulos)
                    msg = Message(
                        subject=f"Temos {qtd} Novas Perguntas no Quiz!",
                        recipients=[usuario.email]
                    )
                    
                    # Cria a lista em formato HTML (com quebras de linha <br>)
                    lista_txt = "<br>".join([f"• {t[:60]}..." for t in titulos])
                    
                    # URL do GIF (Você pode trocar por qualquer link da internet)
                    # Exemplo: Um sino tocando ou um foguete
                    url_gif = "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif" 

                    # Define o corpo em HTML para suportar imagens/gifs
                    msg.html = f"""
                    <div style="font-family: Arial, sans-serif; color: #333;">
                        <h2>Olá, {usuario.nome}! 👋</h2>
                        
                        <p>Temos novidades! Hoje foram liberadas <strong>{qtd} novas perguntas</strong> para você testar seus conhecimentos:</p>
                        
                        <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #17a2b8; margin: 20px 0;">
                            {lista_txt}
                        </div>

                        <div style="text-align: center; margin: 20px 0;">
                            <img src="{url_gif}" alt="Novidade" width="300" style="border-radius: 8px;">
                        </div>

                        <p>Acesse agora e garanta sua pontuação:</p>
                        
                        <a href="{link_acesso}" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                            🚀 Responder Agora
                        </a>
                        
                        <br><br>
                        <p style="font-size: 12px; color: #999;">Boa sorte!<br>Equipe de Treinamento</p>
                    </div>
                    """
                    
                    # Mantemos o body (texto puro) como backup para e-mails antigos que não abrem HTML
                    msg.body = f"Olá {usuario.nome}, temos {qtd} novas perguntas! Acesse: {link_acesso}"

                    conn.send(msg)
                except Exception as e:
                    print(f"Erro ao enviar para {usuario.nome}: {e}")

# 2. E atualize esta também para aceitar 'link_acesso' e passá-lo para a thread
def enviar_email_resumo_do_dia(usuarios, titulos_perguntas, link_acesso): 
    app = current_app._get_current_object()
    # Adicionamos o link_acesso na lista de argumentos (args)
    Thread(target=enviar_emails_resumo_thread, args=(app, usuarios, titulos_perguntas, link_acesso)).start()

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

def enviar_lembrete_pendencias_thread(app, dados_usuarios, link_acesso):
    """
    Envia e-mails de lembrete para usuários com pendências.
    dados_usuarios: Lista de tuplas (usuario, qtd_pendente)
    """
    with app.app_context():
        with mail.connect() as conn:
            for usuario, qtd in dados_usuarios:
                if not usuario.email:
                    continue
                
                try:
                    msg = Message(
                        subject=f"⏳ Ops! Você tem {qtd} perguntas pendentes...",
                        recipients=[usuario.email]
                    )
                    
                    # GIF divertido de "Esperando" (Mr. Bean olhando o relógio)
                    url_gif = "https://media.giphy.com/media/tXL4FHPSnVJ0A/giphy.gif"
                    
                    msg.html = f"""
                    <div style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #d63384;">Toc toc, {usuario.nome}! 👻</h2>
                        
                        <p>Notamos que você deixou passar algumas atividades...</p>
                        
                        <div style="background-color: #fff3cd; padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #ffeeba;">
                            <span style="font-size: 40px; display: block; margin-bottom: 10px;">😱</span>
                            <strong style="font-size: 18px; color: #856404;">
                                Você tem {qtd} perguntas esperando sua resposta!
                            </strong>
                        </div>

                        <div style="text-align: center; margin: 30px 0;">
                            <img src="{url_gif}" alt="Esperando" width="100%" style="max-width: 350px; border-radius: 8px;">
                            <p style="font-size: 12px; color: #888; margin-top: 5px;"><i>Nós esperando você responder para atualizar o Ranking...</i></p>
                        </div>

                        <p>Não deixe acumular! Responda rapidinho e garanta seus pontos:</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{link_acesso}" style="background-color: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 50px; font-weight: bold; font-size: 16px;">
                                🏃‍♂️ Correr para o Quiz
                            </a>
                        </div>
                        
                        <hr style="border: 0; border-top: 1px solid #eee;">
                        <p style="font-size: 12px; color: #999; text-align: center;">Vamos lá! Você consegue!<br>Equipe de Treinamento</p>
                    </div>
                    """
                    
                    # Texto puro como backup
                    msg.body = f"Oi {usuario.nome}! Você tem {qtd} perguntas pendentes. Acesse agora: {link_acesso}"

                    conn.send(msg)
                    print(f"Lembrete divertido enviado para: {usuario.nome}")
                    
                except Exception as e:
                    print(f"Erro ao enviar para {usuario.nome}: {e}")

def disparar_lembretes_pendencias(dados_usuarios, link_acesso):
    app = current_app._get_current_object()
    Thread(target=enviar_lembrete_pendencias_thread, args=(app, dados_usuarios, link_acesso)).start()