
from datetime import datetime
from flask import current_app
from flask_sse import sse

def send_notification(user_id, title, message, notification_type='info'):
    """Envía una notificación en tiempo real"""
    try:
        notification = {
            'title': title,
            'message': message,
            'type': notification_type,
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id
        }
        sse.publish(notification, type='notification', channel=f'user_{user_id}')
        return True
    except Exception as e:
        current_app.logger.error(f"Error enviando notificación: {str(e)}")
        return False
