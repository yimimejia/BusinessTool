import os
import json
import requests
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

class FirebaseNotifications:
    def __init__(self):
        self.server_key = os.environ.get('GOOGLE_API_KEY')
        self.fcm_url = 'https://fcm.googleapis.com/fcm/send'
        
    def send_notification(self, tokens: List[str], title: str, body: str, data: Optional[dict] = None):
        """Enviar notificación a múltiples tokens"""
        if not self.server_key:
            logger.error("GOOGLE_API_KEY no está configurada")
            return False
            
        if not tokens:
            logger.warning("No hay tokens para enviar notificaciones")
            return False
            
        headers = {
            'Authorization': f'key={self.server_key}',
            'Content-Type': 'application/json',
        }
        
        # Preparar datos
        payload = {
            'registration_ids': tokens,
            'notification': {
                'title': title,
                'body': body,
                'icon': '/static/icons/logo-192x192.png',
                'tag': 'foto-video-mojica'
            }
        }
        
        if data:
            payload['data'] = data
            
        try:
            response = requests.post(self.fcm_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Notificación enviada exitosamente: {result}")
                return True
            else:
                logger.error(f"Error al enviar notificación: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error al enviar notificación Firebase: {str(e)}")
            return False
    
    def send_to_user(self, user_id: int, title: str, body: str, data: Optional[dict] = None):
        """Enviar notificación a un usuario específico"""
        from app.models import User
        
        user = User.query.get(user_id)
        if not user or not user.fcm_token:
            logger.warning(f"Usuario {user_id} no tiene token FCM")
            return False
            
        return self.send_notification([user.fcm_token], title, body, data)
    
    def send_to_role(self, role: str, title: str, body: str, data: Optional[dict] = None):
        """Enviar notificación a todos los usuarios con un rol específico"""
        from app.models import User
        
        if role == 'supervisor':
            users = User.query.filter_by(is_supervisor=True).all()
        elif role == 'admin':
            users = User.query.filter_by(is_admin=True).all()
        elif role == 'designer':
            users = User.query.filter_by(is_admin=False, is_supervisor=False).all()
        else:
            logger.warning(f"Rol desconocido: {role}")
            return False
            
        tokens = [user.fcm_token for user in users if user.fcm_token]
        
        if not tokens:
            logger.warning(f"No hay tokens FCM para rol: {role}")
            return False
            
        return self.send_notification(tokens, title, body, data)
    
    def notify_pending_work(self, user_id: int, client_name: str, description: str):
        """Notificar trabajo pendiente a diseñador"""
        title = "¿Ya terminaste el trabajo?"
        body = f"Ya terminaste el trabajo de: {client_name} ({description})"
        
        data = {
            'type': 'pending_work',
            'client_name': client_name,
            'description': description
        }
        
        return self.send_to_user(user_id, title, body, data)
    
    def notify_job_approved(self, job_id: int, client_name: str, description: str, designer_id: int):
        """Notificar que un trabajo ha sido aprobado"""
        title = "¡Trabajo Verificado!"
        body = f"Tu trabajo ha sido verificado: {client_name} ({description})"
        
        data = {
            'type': 'job_completed',
            'job_id': job_id,
            'client_name': client_name,
            'description': description
        }
        
        # Notificar al diseñador
        self.send_to_user(designer_id, title, body, data)
        
        # Notificar a supervisores
        supervisor_title = "Trabajo Aprobado"
        supervisor_body = f"Trabajo verificado y completado: {client_name} ({description})"
        self.send_to_role('supervisor', supervisor_title, supervisor_body, data)
    
    def send_to_all_users(self, title: str, body: str, data: Optional[dict] = None):
        """Enviar notificación a todos los usuarios autenticados"""
        from app.models import User
        
        users = User.query.all()
        tokens = [user.fcm_token for user in users if user.fcm_token]
        
        if not tokens:
            logger.warning("No hay tokens FCM para ningún usuario")
            return False
            
        return self.send_notification(tokens, title, body, data)

# Instancia global
firebase_notifications = FirebaseNotifications()

# Funciones de conveniencia
def send_firebase_notification_to_all(title: str, body: str, data: Optional[dict] = None):
    """Función de conveniencia para enviar notificación a todos los usuarios"""
    return firebase_notifications.send_to_all_users(title, body, data)

def send_firebase_notification(token: str, title: str, body: str, data: Optional[dict] = None):
    """Función de conveniencia para enviar notificación a un token específico"""
    if not token:
        return False
    return firebase_notifications.send_notification([token], title, body, data)