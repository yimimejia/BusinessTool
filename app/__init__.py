import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import redis
from flask_sse import sse

# Initialize extensions first
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate()
scheduler = BackgroundScheduler()

def create_app():
    app = Flask(__name__)

    # Configure Flask app
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-key-temporary")
    app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379")

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    app.register_blueprint(sse, url_prefix='/stream')
    login_manager.login_view = 'main.login'

    with app.app_context():
        # Import models and create tables
        from app import models

        try:
            print("Inicializando la base de datos...")
            # Importar los modelos aquí para que Flask-Migrate los detecte
            from app.models import User, Job, ActivityLog # ActivityLog added here
            from app.utils.email_notifications import send_daily_report

            # Set up login manager
            @login_manager.user_loader
            def load_user(user_id):
                return models.User.query.get(int(user_id))

            # Register blueprints
            from app.routes import bp
            app.register_blueprint(bp)

            # Crear usuario admin si no existe
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

            # Configurar el programador de tareas
            if not scheduler.running:
                scheduler.add_job(
                    send_daily_report,
                    'cron',
                    hour=8,
                    minute=0,
                    timezone=pytz.timezone('America/Bogota')
                )
                scheduler.start()

            print("Inicialización completada exitosamente")

        except Exception as e:
            print(f"Error en la inicialización: {str(e)}")
            db.session.rollback()
            raise e

        return app

def send_daily_notification():
    from app.utils.email_notifications import send_daily_report
    send_daily_report()