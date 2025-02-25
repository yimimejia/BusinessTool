import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_sse import sse
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)

    # Configuración básica
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Configuración de Redis para SSE - Cambiado a localhost
    app.config["REDIS_URL"] = "redis://localhost:6379"

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)  # Initialize CSRF protection
    login_manager.login_view = 'main.login'

    # Registrar blueprints
    app.register_blueprint(sse, url_prefix='/stream')

    with app.app_context():
        from app.models import User

        # Crear todas las tablas
        db.create_all()

        # Registrar el blueprint principal
        from app.routes import bp as main_bp
        app.register_blueprint(main_bp)

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))

        return app

from app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)