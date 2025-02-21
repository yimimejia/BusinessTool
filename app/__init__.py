import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import pytz
import redis
from flask_sse import sse
import logging

# Initialize extensions first
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

# Create app factory
def create_app():
    app = Flask(__name__)

    # Configure Flask app
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    # Mejorar configuración de conexión
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,  # Verificar conexión antes de usar
        "pool_recycle": 300,    # Reciclar conexiones cada 5 minutos
        "pool_timeout": 30,     # Timeout de conexión de 30 segundos
        "pool_size": 10,        # Tamaño máximo del pool
        "max_overflow": 5,      # Conexiones adicionales permitidas
        "connect_args": {
            "connect_timeout": 10,  # Timeout de conexión inicial
            "keepalives": 1,        # Mantener conexiones vivas
            "keepalives_idle": 30,  # Tiempo de inactividad antes de keepalive
            "keepalives_interval": 10,  # Intervalo entre keepalives
            "keepalives_count": 5    # Número de reintentos de keepalive
        }
    }
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-key-temporary")
    app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379")
    app.config['WTF_CSRF_ENABLED'] = True

    # Create uploads directory
    upload_folder = os.path.join(app.static_folder, 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_folder

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Register blueprints
    app.register_blueprint(sse, url_prefix='/stream')

    # Configure login
    login_manager.login_view = 'main.login'

    with app.app_context():
        # Import models
        from app import models

        # Import and register routes blueprint
        from app.routes import bp as main_blueprint
        app.register_blueprint(main_blueprint)

        # Create tables
        db.create_all()

        #Set up login manager
        @login_manager.user_loader
        def load_user(user_id):
            try:
                return models.User.query.get(int(user_id))
            except Exception as e:
                logging.error(f"Error loading user: {str(e)}")
                return None

        #Adding admin user creation
        try:
            admin_user = models.User.query.filter_by(username='admin').first()
            if not admin_user:
                print("Creando usuario administrador inicial...")
                admin = models.User(
                    username='admin',
                    name='Administrador',
                    is_admin=True,
                    can_edit=True
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print("Usuario administrador creado exitosamente")
        except Exception as e:
            logging.error(f"Error creating admin user: {str(e)}")

        return app

# Create the app instance
app = create_app()