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
    try:
        logger.info("Initializing Flask application...")
        app = Flask(__name__)

        # Configure Flask app
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
        if not app.config["SQLALCHEMY_DATABASE_URI"]:
            raise ValueError("DATABASE_URL environment variable is not set")

        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": 10,
            "max_overflow": 5
        }

        # Set secret key
        app.secret_key = os.environ.get("SESSION_SECRET")
        if not app.secret_key:
            logger.warning("SESSION_SECRET not set, using development key")
            app.secret_key = 'dev-key-temporary'

        # Redis configuration
        app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379")
        logger.info(f"Redis URL configured: {app.config['REDIS_URL']}")

        # Create uploads directory
        upload_folder = os.path.join(app.static_folder, 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        app.config['UPLOAD_FOLDER'] = upload_folder
        logger.info(f"Upload folder created at: {upload_folder}")

        # Create temp directory for file uploads
        temp_folder = os.path.join(app.static_folder, 'temp')
        os.makedirs(temp_folder, exist_ok=True)
        logger.info(f"Temp folder created at: {temp_folder}")

        # Initialize extensions
        logger.info("Initializing Flask extensions...")
        db.init_app(app)
        login_manager.init_app(app)
        migrate.init_app(app, db)
        csrf.init_app(app)

        # Configure login
        login_manager.login_view = 'main.login'
        logger.info("Login manager configured")

        # Register blueprints
        logger.info("Registering blueprints...")
        app.register_blueprint(sse, url_prefix='/stream')

        with app.app_context():
            # Import models
            logger.info("Importing models...")
            from app import models

            # Import and register routes blueprint
            logger.info("Registering routes blueprint...")
            from app.routes import bp as main_blueprint
            app.register_blueprint(main_blueprint)

            try:
                # Create tables
                logger.info("Creating database tables...")
                db.create_all()

                # Set up login manager
                @login_manager.user_loader
                def load_user(user_id):
                    try:
                        return models.User.query.get(int(user_id))
                    except Exception as e:
                        logger.error(f"Error loading user: {str(e)}")
                        return None

                # Adding admin user creation if not exists
                admin_user = models.User.query.filter_by(username='admin').first()
                if not admin_user:
                    logger.info("Creating admin user...")
                    admin = models.User(
                        username='admin',
                        name='Administrador',
                        is_admin=True,
                        can_edit=True
                    )
                    admin.set_password('admin123')
                    db.session.add(admin)
                    db.session.commit()
                    logger.info("Admin user created successfully")
            except Exception as e:
                logger.error(f"Error during database initialization: {str(e)}")
                raise

        logger.info("Flask application initialized successfully")
        return app

    except Exception as e:
        logger.error(f"Critical error during app initialization: {str(e)}")
        raise

# Create the app instance
app = create_app()