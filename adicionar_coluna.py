from app import app, db
from sqlalchemy import text

# Script para adicionar a coluna 'explicacao' sem resetar o banco
with app.app_context():
    print("Iniciando migração do banco de dados...")
    try:
        with db.engine.connect() as conn:
            # Comando SQL compatível com SQLite e PostgreSQL
            conn.execute(text("ALTER TABLE pergunta ADD COLUMN explicacao TEXT"))
            conn.commit()
        print("SUCESSO: Coluna 'explicacao' criada na tabela 'pergunta'!")
    except Exception as e:
        # Se der erro, geralmente é porque a coluna já existe
        print(f"AVISO: Não foi possível criar a coluna (ela provavelmente já existe). Detalhes: {e}")