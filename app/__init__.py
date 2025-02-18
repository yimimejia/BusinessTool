import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import DeclarativeBase

# Initialize extensions first
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)

    # Configure Flask app
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-key-temporary")

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    login_manager.login_view = 'main.login'

    # Configuración de email
    mail = Mail(app)
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'tu-email@gmail.com'  # Actualizar con tu email
    app.config['MAIL_PASSWORD'] = 'tu-password'  # Actualizar con tu password

    # Inicializar scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=send_daily_notification, trigger="cron", hour=8)  # Enviar a las 8 AM
    scheduler.start()

    with app.app_context():
        # Import models and create tables
        from app import models

        try:
            print("Inicializando la base de datos...")
            # Importar los modelos aquí para que Flask-Migrate los detecte
            from app.models import User, Job # Assuming Job model exists

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

            print("Inicialización completada exitosamente")

        except Exception as e:
            print(f"Error en la inicialización: {str(e)}")
            db.session.rollback()
            raise e

        return app

def send_daily_notification():
    # Implementar la lógica para enviar la notificación diaria
    pass # Replace with actual notification sending logic