from app import app, db
from app.models import User
from werkzeug.security import generate_password_hash

def update_designer_passwords():
    with app.app_context():
        try:
            # Obtener todos los usuarios diseñadores (no admin, no supervisor)
            designers = User.query.filter_by(is_admin=False, is_supervisor=False).all()

            # Actualizar contraseñas
            for designer in designers:
                designer.password_hash = generate_password_hash("1245")

            # Guardar cambios
            db.session.commit()
            print(f"Se actualizaron las contraseñas de {len(designers)} usuarios diseñadores")
            return True
        except Exception as e:
            print(f"Error actualizando contraseñas: {str(e)}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    update_designer_passwords()