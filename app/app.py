import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_sse import sse
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET")
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    # Database configuration
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 280,
        "pool_timeout": 30,
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 2,
        "connect_args": {
            "connect_timeout": 30,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
            "application_name": "mojica_photos_app"
        },
        "execution_options": {
            "isolation_level": "READ COMMITTED"
        },
        "retry_on_timeout": True,
        "echo_pool": True
    }

    # Configuración de Redis para SSE
    app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379")

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Register blueprint for SSE
    app.register_blueprint(sse, url_prefix='/stream')

    with app.app_context():
        from app import models
        db.create_all()

        from app.routes import bp as routes_bp
        app.register_blueprint(routes_bp)

        return app

app = create_app()

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))