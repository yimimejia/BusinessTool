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
    app.secret_key = os.environ.get("SESSION_SECRET", "default-secret-key")
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Configuración de la base de datos
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 280,
        "pool_timeout": 30,
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 2,
        "connect_args": {
            "connect_timeout": 10,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5
        }
    }
    app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379")

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Registrar blueprint para SSE
    app.register_blueprint(sse, url_prefix='/stream')

    with app.app_context():
        # Importar modelos y rutas
        from app import models
        from app.tasks import init_scheduler

        # Crear tablas
        db.create_all()

        # Inicializar el planificador de tareas
        scheduler = init_scheduler()

        return app

app = create_app()

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))