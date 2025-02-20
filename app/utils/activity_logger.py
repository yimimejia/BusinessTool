import logging
from datetime import datetime
from flask import request
from flask_login import current_user
from app import db
from app.models import ActivityLog
from flask_sse import sse

logger = logging.getLogger(__name__)

def log_activity(action, details=None):
    """
    Registra una actividad en el log y envía notificación SSE si es necesario
    
    Args:
        action (str): Tipo de acción realizada
        details (str, optional): Detalles adicionales de la acción
    """
    try:
        activity = ActivityLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            details=details,
            ip_address=request.remote_addr,
            timestamp=datetime.utcnow()
        )
        db.session.add(activity)
        db.session.commit()

        # Enviar notificación en tiempo real para acciones importantes
        if action in ['nuevo_trabajo', 'trabajo_completado', 'trabajo_eliminado', 
                     'trabajo_entregado', 'trabajo_entregado_qr']:
            sse.publish({
                "message": f"{action}: {details}",
                "type": "info"
            }, type='message')
            
    except Exception as e:
        logger.error(f"Error al registrar actividad: {str(e)}")
        db.session.rollback()
