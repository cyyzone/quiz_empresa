from .extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Tabela de Associação (Muitos-para-Muitos)
pergunta_departamento_association = db.Table('pergunta_departamento',
    db.Column('pergunta_id', db.Integer, db.ForeignKey('pergunta.id'), primary_key=True),
    db.Column('departamento_id', db.Integer, db.ForeignKey('departamento.id'), primary_key=True)
)

class Departamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    usuarios = db.relationship('Usuario', backref='departamento', lazy=True)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    codigo_acesso = db.Column(db.String(4), unique=True, nullable=False)
    departamento_id = db.Column(db.Integer, db.ForeignKey('departamento.id'), nullable=False)
    respostas = db.relationship('Resposta', backref='usuario', lazy=True)

class Administrador(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

class Pergunta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False, default='multipla_escolha', index=True)
    texto = db.Column(db.Text, nullable=False)
    opcao_a = db.Column(db.Text, nullable=True)
    opcao_b = db.Column(db.Text, nullable=True)
    opcao_c = db.Column(db.Text, nullable=True)
    opcao_d = db.Column(db.Text, nullable=True)
    resposta_correta = db.Column(db.String(1), nullable=True)
    explicacao = db.Column(db.Text, nullable=True)
    data_liberacao = db.Column(db.Date, nullable=False, index=True)
    tempo_limite = db.Column(db.Integer, nullable=True)
    imagem_pergunta = db.Column(db.String(300), nullable=True)
    categoria = db.Column(db.String(50), nullable=True, default='Geral', index=True)
    para_todos_setores = db.Column(db.Boolean, default=False, nullable=False)
    departamentos = db.relationship('Departamento', secondary=pergunta_departamento_association, lazy='subquery',
        backref=db.backref('perguntas', lazy=True))

class Resposta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pontos = db.Column(db.Integer, nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False, index=True)
    pergunta_id = db.Column(db.Integer, db.ForeignKey('pergunta.id'), nullable=False, index=True)
    resposta_dada = db.Column(db.String(1), nullable=True)
    data_resposta = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    pergunta = db.relationship('Pergunta')
    texto_discursivo = db.Column(db.Text, nullable=True)
    anexo_resposta = db.Column(db.String(300), nullable=True)
    status_correcao = db.Column(db.String(20), nullable=False, default='nao_respondido', index=True)
    feedback_admin = db.Column(db.Text, nullable=True)
    feedback_visto = db.Column(db.Boolean, default=False, nullable=False)

class ImagemPergunta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(300), nullable=False)
    pergunta_id = db.Column(db.Integer, db.ForeignKey('pergunta.id'), nullable=False)
    pergunta = db.relationship('Pergunta', backref=db.backref('imagens_extra', lazy=True, cascade='all, delete-orphan'))

class AnexoResposta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(300), nullable=False)
    resposta_id = db.Column(db.Integer, db.ForeignKey('resposta.id'), nullable=False)
    resposta = db.relationship('Resposta', backref=db.backref('anexos_extra', lazy=True, cascade='all, delete-orphan'))