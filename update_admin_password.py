from werkzeug.security import generate_password_hash
from app import create_app
from app.models import db, User

app = create_app()

with app.app_context():
    # Buscar el usuario admin
    admin = User.query.filter_by(username='admin').first()
    if admin:
        # Actualizar la contraseña
        admin.password_hash = generate_password_hash('admin123')
        db.session.commit()
        print("Contraseña de administrador actualizada exitosamente")
    else:
        # Crear usuario admin si no existe
        admin = User(
            username='admin',
            name='Admin',
            is_admin=True,
            is_supervisor=False,
            is_designer=False
        )
        admin.password_hash = generate_password_hash('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Usuario administrador creado exitosamente")
