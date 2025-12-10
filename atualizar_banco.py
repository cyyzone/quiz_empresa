from run import app          
from app.extensions import db # Importa o db das extensões

with app.app_context():
    db.create_all()
    print("Novas tabelas (ImagemPergunta e AnexoResposta) criadas com sucesso! Dados antigos preservados.")