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

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize extensions first
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

# Create app factory
def create_app():
    logger.info("Iniciando creación de la aplicación Flask")

    try:
        app = Flask(__name__)
        logger.info("Instancia Flask creada")

        # Configure Flask app
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_timeout": 30,
            "pool_size": 10,
            "max_overflow": 5
        }
        app.secret_key = os.environ.get("SESSION_SECRET", "dev-key-temporary")
        app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379")

        logger.info("Configuración básica completada")

        # Create required directories
        static_folder = app.static_folder
        required_dirs = ['uploads', 'temp']
        for dir_name in required_dirs:
            dir_path = os.path.join(static_folder, dir_name)
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"Directorio creado/verificado: {dir_path}")

        # Initialize extensions
        db.init_app(app)
        login_manager.init_app(app)
        migrate.init_app(app, db)
        login_manager.login_view = 'main.login'
        logger.info("Extensiones inicializadas")

        # Register blueprints
        app.register_blueprint(sse, url_prefix='/stream')

        with app.app_context():
            # Import models and routes
            from app import models
            from app.routes import bp as main_blueprint
            app.register_blueprint(main_blueprint)
            logger.info("Blueprints registrados")

            # Create tables
            db.create_all()
            logger.info("Tablas de base de datos creadas/verificadas")

            #Set up login manager
            @login_manager.user_loader
            def load_user(user_id):
                try:
                    return models.User.query.get(int(user_id))
                except Exception as e:
                    logger.error(f"Error loading user: {str(e)}")
                    return None

            logger.info("Aplicación Flask creada exitosamente")
            return app

    except Exception as e:
        logger.error(f"Error durante la creación de la aplicación: {str(e)}")
        raise

# Create the app instance
app = create_app()