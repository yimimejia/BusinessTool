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

# Initialize extensions first
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate()

# Create app factory
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

    # Ensure secret key is set
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-key-temporary")

    app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379")

    # Create uploads directory
    upload_folder = os.path.join(app.static_folder, 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_folder

    # Create temp directory for file uploads
    temp_folder = os.path.join(app.static_folder, 'temp')
    os.makedirs(temp_folder, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Configure login
    login_manager.login_view = 'main.login'

    # Register blueprints
    app.register_blueprint(sse, url_prefix='/stream')

    with app.app_context():
        # Import models
        from app import models

        # Import and register routes blueprint
        from app.routes import bp as main_blueprint
        app.register_blueprint(main_blueprint)

        try:
            # Create tables
            db.create_all()

            # Set up login manager
            @login_manager.user_loader
            def load_user(user_id):
                try:
                    return models.User.query.get(int(user_id))
                except Exception as e:
                    logging.error(f"Error loading user: {str(e)}")
                    return None

            # Adding admin user creation if not exists
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

        return app

# Create the app instance
app = create_app()