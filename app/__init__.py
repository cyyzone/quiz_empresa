from flask import Flask, render_template
from .extensions import db
from .utils import format_datetime_local, otimizar_img_filter, get_texto_da_opcao
import cloudinary
from .extensions import db, mail

def create_app():
    app = Flask(__name__)
    # Carrega configurações
    app.config.from_object('config.Config')

    # Inicializa BD
    db.init_app(app)
    mail.init_app(app)

    # Configura Cloudinary
    cloudinary.config(
        cloud_name = app.config['CLOUDINARY_CLOUD_NAME'],
        api_key = app.config['CLOUDINARY_API_KEY'],
        api_secret = app.config['CLOUDINARY_API_SECRET']
    )

    # Registra Filtros
    app.template_filter('datetime_local')(format_datetime_local)
    app.template_filter('otimizar_img')(otimizar_img_filter)
    
    # Context Processor
    @app.context_processor
    def utility_processor():
        return dict(get_texto_da_opcao=get_texto_da_opcao)

    # Registra Blueprints
    from .routes.auth import auth_bp
    from .routes.user import user_bp
    from .routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)

    # Error Handlers
    @app.errorhandler(404)
    def pagina_nao_encontrada(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def erro_servidor(e):
        return render_template('500.html'), 500

    return app