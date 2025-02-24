from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user
from app import db
from app.models import ActivityLog

def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_staff:
            flash('No tienes permiso para acceder a esta página.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def log_activity(action, details=None):
    """
    Registra una actividad en el sistema
    """
    try:
        activity = ActivityLog(
            user_id=current_user.id if not current_user.is_anonymous else None,
            action=action,
            details=details
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error al registrar actividad: {str(e)}")
