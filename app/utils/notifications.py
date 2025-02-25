
from datetime import datetime
from flask import current_app
from flask_sse import sse

def send_notification(user_id, title, message, notification_type='info', retry_count=3):
    """Envía una notificación en tiempo real con reintentos"""
    for attempt in range(retry_count):
        try:
            notification = {
                'title': title,
                'message': message,
                'type': notification_type,
                'timestamp': datetime.utcnow().isoformat(),
                'user_id': user_id,
                'attempt': attempt + 1
            }
            sse.publish(notification, type='notification', channel=f'user_{user_id}')
            current_app.logger.info(f"Notificación enviada exitosamente a usuario {user_id}")
            return True
        except Exception as e:
            current_app.logger.error(f"Intento {attempt + 1} fallido: {str(e)}")
            if attempt == retry_count - 1:
                current_app.logger.error(f"Error enviando notificación después de {retry_count} intentos")
                return Falselse
