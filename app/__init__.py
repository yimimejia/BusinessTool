import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase
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

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

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

        # Set up login manager
        @login_manager.user_loader
        def load_user(user_id):
            try:
                return models.User.query.get(int(user_id))
            except Exception as e:
                logging.error(f"Error loading user: {str(e)}")
                return None

        return app

# Create the app instance
app = create_app()