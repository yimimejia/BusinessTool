import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from queue import Queue
from flask import Response
from flask import stream_with_context

db = SQLAlchemy()
login_manager = LoginManager()
message_queue = Queue()

def create_app():
    app = Flask(__name__)

    # Configuración básica
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'


    @app.route('/stream')
    def stream():
        def event_stream():
            while True:
                message = message_queue.get()
                yield f'data: {message}\n\n'

        return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

    with app.app_context():
        from app.models import User

        # Crear todas las tablas
        db.create_all()

        # Registrar el blueprint principal
        from app.routes import bp as main_bp
        app.register_blueprint(main_bp)

        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))

        return app