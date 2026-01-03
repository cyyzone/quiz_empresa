from run import app 
from app.extensions import db 
from sqlalchemy import text

# Script para adicionar a coluna 'categoria' na tabela 'pergunta'
with app.app_context():
    print("Iniciando atualização do banco de dados...")
    try:
        with db.engine.connect() as conn:
            # Adiciona a coluna com um valor padrão 'Geral' para as perguntas antigas não ficarem vazias
            conn.execute(text("ALTER TABLE pergunta ADD COLUMN categoria VARCHAR(50) DEFAULT 'Geral'"))
            conn.commit()
        print("SUCESSO: Coluna 'categoria' criada na tabela 'pergunta'!")
    except Exception as e:
        # Se cair aqui, é porque provavelmente a coluna já existe ou houve outro erro
        print(f"AVISO ou ERRO: {e}")