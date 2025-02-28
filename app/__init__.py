import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate 
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import pytz
import redis
from flask_sse import sse
import logging

# Initialize logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize extensions first
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    try:
        logger.info("Iniciando creación de la aplicación Flask...")
        app = Flask(__name__)

        # Enable debug mode for detailed error tracing
        app.config["DEBUG"] = True
        app.config["ENV"] = "development"
        logger.debug("Modo debug activado")

        # Configure Flask app
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": 10,
            "max_overflow": 5
        }
        logger.debug("Configuración de base de datos establecida")

        # Configure upload folder
        app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        logger.debug("Directorio de uploads configurado")

        # Ensure secret key is set
        app.secret_key = os.environ.get("SESSION_SECRET", "dev-key-temporary")
        app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379")

        # Initialize extensions
        logger.info("Inicializando extensiones...")
        db.init_app(app)
        login_manager.init_app(app)
        migrate.init_app(app, db)
        logger.debug("Extensiones inicializadas correctamente")

        # Configure login
        login_manager.login_view = 'main.login'

        # Register blueprints
        app.register_blueprint(sse, url_prefix='/stream')

        with app.app_context():
            # Import models here to avoid circular imports
            from app import models

            # Import and register routes blueprint
            from app.routes import bp as main_blueprint
            app.register_blueprint(main_blueprint)
            logger.debug("Blueprints registrados")

            try:
                # Create tables
                db.create_all()
                logger.debug("Tablas creadas exitosamente")

                # Configure user loader
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
                logger.error(f"Error durante la inicialización de la base de datos: {str(e)}")
                raise

    except Exception as e:
        logger.error(f"Error crítico durante la creación de la aplicación: {str(e)}")
        raise

# Create the app instance only once
try:
    logger.info("Creando instancia de la aplicación...")
    app = create_app()
    logger.info("Aplicación creada exitosamente")
except Exception as e:
    logger.error(f"Error al crear la instancia de la aplicación: {str(e)}")
    raise