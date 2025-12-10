from run import app
from app.models import Usuario, Pergunta, Resposta, Departamento
from app.utils import disparar_lembretes_pendencias # Importa a nova função divertida
from app.extensions import db
from sqlalchemy import or_
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO ---
LINK_DO_SITE = "https://quiz-empresa.onrender.com"

def verificar_e_lembrar_pendencias():
    with app.app_context():
        print("--- 🕵️ Iniciando Caça às Pendências ---")
        
        # 1. Data de Hoje (UTC-3)
        hoje = (datetime.utcnow() - timedelta(hours=3)).date()
        
        # 2. Busca todos os usuários com e-mail
        usuarios = Usuario.query.filter(Usuario.email != None).all()
        
        lista_devedores = []
        
        print(f"Analisando {len(usuarios)} usuários...")

        for usuario in usuarios:
            # A) Quais perguntas este usuário JÁ respondeu?
            # sq_respondidas = lista de IDs
            respondidas_ids = [r.pergunta_id for r in Resposta.query.filter_by(usuario_id=usuario.id).all()]
            
            # B) Quantas perguntas DISPONÍVEIS (até hoje) ele NÃO respondeu?
            # Filtra por data, exclui as respondidas e verifica o setor
            pendencias_count = Pergunta.query.filter(
                Pergunta.data_liberacao <= hoje,           # Já liberada
                ~Pergunta.id.in_(respondidas_ids),         # Não respondida
                or_(
                    Pergunta.para_todos_setores == True,   # Para todos
                    Pergunta.departamentos.any(id=usuario.departamento_id) # Ou do setor dele
                )
            ).count()
            
            if pendencias_count > 0:
                print(f"-> {usuario.nome} tem {pendencias_count} pendências.")
                lista_devedores.append((usuario, pendencias_count))
        
        # 3. Envia os e-mails se houver alguém com pendência
        if lista_devedores:
            print(f"Enviando e-mails para {len(lista_devedores)} usuários atrasados...")
            disparar_lembretes_pendencias(lista_devedores, LINK_DO_SITE)
            print("Disparos iniciados com sucesso! (O envio ocorre em segundo plano)")
        else:
            print("🎉 Ninguém tem pendências! Tudo em dia.")

if __name__ == '__main__':
    verificar_e_lembrar_pendencias()