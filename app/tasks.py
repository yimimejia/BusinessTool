"""
Tareas programadas y funciones de utilidad para el sistema
"""
import os
import logging
from datetime import datetime, timedelta
from app import db, create_app
from app.models import CompletedJob
from app.utils.whatsapp import generate_client_completion_message, send_whatsapp_message
from app.routes import log_activity

# Configuración de logging
logger = logging.getLogger(__name__)

def notify_pending_completed_jobs():
    """
    Verifica si hay trabajos completados sin notificar (llamar) y les envía 
    un mensaje de WhatsApp automáticamente
    """
    app = create_app()
    
    with app.app_context():
        try:
            # Buscar trabajos completados en las últimas 24 horas que no estén marcados como llamados
            cutoff_time = datetime.utcnow() - timedelta(hours=24)  # Solo últimas 24 horas
            
            # Obtener todos los trabajos completados no llamados con número de teléfono
            pending_jobs = CompletedJob.query.filter(
                CompletedJob.is_called == False,
                CompletedJob.completed_at >= cutoff_time,
                CompletedJob.phone_number != None
            ).all()
            
            if not pending_jobs:
                logger.info("No hay trabajos completados pendientes por notificar")
                return
            
            logger.info(f"Encontrados {len(pending_jobs)} trabajos completados pendientes por notificar")
            
            # Verificar credenciales de Twilio
            if not all([os.environ.get("TWILIO_ACCOUNT_SID"), 
                      os.environ.get("TWILIO_AUTH_TOKEN"), 
                      os.environ.get("TWILIO_PHONE_NUMBER")]):
                logger.warning("No se pueden enviar notificaciones por WhatsApp: faltan credenciales de Twilio")
                return
            
            # Procesar cada trabajo
            for job in pending_jobs:
                try:
                    # Generar mensaje para el cliente
                    whatsapp_message = generate_client_completion_message(job)
                    
                    # Enviar mensaje
                    whatsapp_sent = send_whatsapp_message(
                        job.phone_number,
                        whatsapp_message
                    )
                    
                    # Actualizar estado si se envió correctamente
                    if whatsapp_sent:
                        job.is_called = True
                        job.called_at = datetime.utcnow()
                        db.session.commit()
                        
                        # Registrar actividad
                        log_activity(
                            'notificacion_whatsapp_automatica',
                            f"Notificación automática enviada a {job.client_name} (Factura: {job.invoice_number})"
                        )
                        
                        logger.info(f"Enviada notificación automática a trabajo #{job.id} - {job.client_name}")
                    else:
                        logger.warning(f"No se pudo enviar notificación a trabajo #{job.id} - {job.client_name}")
                        
                except Exception as job_error:
                    logger.error(f"Error procesando trabajo #{job.id}: {str(job_error)}")
                    continue
            
        except Exception as e:
            logger.error(f"Error verificando trabajos pendientes por notificar: {str(e)}")

def setup_scheduler(app):
    """
    Configura el programador de tareas para ejecutar funciones periódicamente
    Args:
        app: Instancia de la aplicación Flask
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        
        scheduler = BackgroundScheduler()
        
        # Verificar trabajos completados sin notificar cada 15 minutos
        scheduler.add_job(
            func=notify_pending_completed_jobs,
            trigger=IntervalTrigger(minutes=15),
            id='check_completed_jobs',
            name='Verificar trabajos completados sin notificar',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info("Scheduler iniciado con tareas programadas")
        
    except Exception as e:
        logger.error(f"Error al configurar scheduler: {str(e)}")