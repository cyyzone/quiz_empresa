from flask import Blueprint, render_template, redirect, url_for, request, session, flash
from app.models import Usuario
from app.extensions import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def pagina_login():
    if 'usuario_id' in session: return redirect(url_for('user.dashboard'))
    return render_template('login.html')

@auth_bp.route('/login', methods=['POST'])
def processa_login():
    codigo_inserido = request.form['codigo']
    usuario = Usuario.query.filter_by(codigo_acesso=codigo_inserido).first()
    if usuario:
        session['usuario_id'], session['usuario_nome'] = usuario.id, usuario.nome
        return redirect(url_for('user.dashboard'))
    else:
        flash('Código de acesso inválido!', 'danger')
        return redirect(url_for('auth.pagina_login'))

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.pagina_login'))