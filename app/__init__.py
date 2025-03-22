import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate 
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timedelta
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

def create_app():
    app = Flask(__name__)

    # Enable debug mode for detailed error tracing
    app.config["DEBUG"] = True
    app.config["ENV"] = "development"

    # Configure Flask app
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 5
    }

    # Configure session
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Sesión dura 7 días
    app.config['SESSION_PERMANENT'] = True
    app.config['SESSION_TYPE'] = 'filesystem'

    # Configure upload folder
    app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Ensure secret key is set
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-key-temporary")

    app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379")

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Configure login
    login_manager.login_view = 'main.login'
    login_manager.session_protection = "strong"

    # Register blueprints
    app.register_blueprint(sse, url_prefix='/stream')

    with app.app_context():
        # Import models here to avoid circular imports
        from app import models

        # Import and register routes blueprint
        from app.routes import bp as main_blueprint
        app.register_blueprint(main_blueprint)

        # Exclude public routes from login requirement
        @app.before_request
        def check_route():
            from flask import request
            if request.endpoint and 'public' in request.endpoint:
                return None
            return None

        try:
            # Create tables
            db.create_all()

            # Configure user loader
            @login_manager.user_loader
            def load_user(user_id):
                try:
                    return models.User.query.get(int(user_id))
                except Exception as e:
                    logging.error(f"Error loading user: {str(e)}")
                    return None

            # Add default admin user if not exists
            admin_user = models.User.query.filter_by(username='admin').first()
            if not admin_user:
                admin = models.User(
                    username='admin',
                    name='Administrador',
                    is_admin=True,
                    can_edit=True
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                logging.info("Usuario administrador creado exitosamente")

        except Exception as e:
            logging.error(f"Error during app initialization: {str(e)}")
            raise

    return app

# Create the app instance only once
app = create_app()