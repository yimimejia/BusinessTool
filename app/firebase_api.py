from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app import db
import logging

logger = logging.getLogger(__name__)

firebase_bp = Blueprint('firebase', __name__, url_prefix='/api')

@firebase_bp.route('/save-fcm-token', methods=['POST'])
@login_required
def save_fcm_token():
    """Guardar token FCM del usuario"""
    try:
        data = request.get_json()
        token = data.get('token')
        
        if not token:
            return jsonify({'success': False, 'message': 'Token requerido'}), 400
        
        # Actualizar token del usuario actual
        current_user.fcm_token = token
        db.session.commit()
        
        logger.info(f"Token FCM guardado para usuario {current_user.username}")
        return jsonify({'success': True, 'message': 'Token guardado exitosamente'})
        
    except Exception as e:
        logger.error(f"Error al guardar token FCM: {str(e)}")
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@firebase_bp.route('/mark-job-ready', methods=['POST'])
@login_required
def mark_job_ready():
    """Marcar trabajo como listo desde el dashboard del diseñador"""
    try:
        from app.models import Job, PendingJob
        from app.utils.firebase_notifications import firebase_notifications
        from app.routes import log_activity
        
        data = request.get_json()
        job_id = data.get('job_id')
        
        if not job_id:
            return jsonify({'success': False, 'message': 'ID de trabajo requerido'}), 400
        
        job = Job.query.get_or_404(job_id)
        
        # Verificar que el usuario sea el diseñador asignado
        if job.designer_id != current_user.id:
            return jsonify({'success': False, 'message': 'No autorizado'}), 403
        
        # Crear trabajo pendiente de verificación
        pending_job = PendingJob(
            original_job_id=job.id,
            description=job.description,
            designer_id=job.designer_id,
            registered_by_id=job.registered_by_id,
            invoice_number=job.invoice_number,
            client_name=job.client_name,
            phone_number=job.phone_number,
            total_amount=job.total_amount,
            deposit_amount=job.deposit_amount,
            tags=job.tags,
            pending_type='verification',
            created_at=job.created_at
        )
        
        db.session.add(pending_job)
        db.session.delete(job)
        db.session.commit()
        
        # Registrar actividad
        log_activity(
            'trabajo_listo',
            f"Trabajo marcado como listo por diseñador: {job.client_name} (Factura: {job.invoice_number})"
        )
        
        # Enviar notificación a supervisores
        firebase_notifications.send_to_role(
            'supervisor',
            'Trabajo Listo para Verificación',
            f'Nuevo trabajo listo: {job.client_name} ({job.description})',
            {
                'type': 'job_ready',
                'job_id': pending_job.id,
                'client_name': job.client_name,
                'description': job.description
            }
        )
        
        logger.info(f"Trabajo {job_id} marcado como listo por {current_user.username}")
        return jsonify({'success': True, 'message': 'Trabajo marcado como listo'})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al marcar trabajo como listo: {str(e)}")
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500