import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import DeclarativeBase

# Initialize extensions first
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()

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
    login_manager.login_view = 'main.login'

    with app.app_context():
        # Import models and create tables
        from app import models

        try:
            print("Creando tablas en la base de datos...")
            db.drop_all()  # Limpiar tablas existentes
            db.create_all()
            print("Tablas creadas exitosamente")

            # Set up login manager
            @login_manager.user_loader
            def load_user(user_id):
                return models.User.query.get(int(user_id))

            # Register blueprints
            from app.routes import bp
            app.register_blueprint(bp)

            # Create initial users if they don't exist
            admin_user = models.User.query.filter_by(username='admin').first()
            if not admin_user:
                print("Creando usuarios iniciales...")
                # Create admin user
                admin = models.User(
                    username='admin',
                    name='Administrador',
                    is_admin=True,
                    can_edit=True
                )
                admin.set_password('admin123')
                db.session.add(admin)

                # Create PC users
                for i in range(1, 10):
                    username = f'pc{i:02d}'
                    user = models.User(
                        username=username,
                        name=f'PC{i:02d}',
                        is_admin=False,
                        can_edit=True
                    )
                    user.set_password('1245')
                    db.session.add(user)

                db.session.commit()
                print("Usuarios creados exitosamente")

        except Exception as e:
            print(f"Error en la inicialización: {str(e)}")
            db.session.rollback()
            raise e

        return app