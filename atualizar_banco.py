from app import app, db

with app.app_context():
    db.create_all()
    print("Novas tabelas (ImagemPergunta e AnexoResposta) criadas com sucesso! Dados antigos preservados.")