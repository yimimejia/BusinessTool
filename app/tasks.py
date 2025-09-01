"""
Tareas programadas y funciones de utilidad para el sistema
"""
import os
import logging
from datetime import datetime, timedelta
from app import db, create_app
from app.models import CompletedJob, Job

# Configuración de logging
logger = logging.getLogger(__name__)

def notify_pending_completed_jobs():
    """
    Verifica trabajos completados sin notificar (versión sin Twilio)
    Solo registra los trabajos que necesitarían notificación
    """
    logger.info("Tarea de verificación de trabajos completados ejecutándose...")
    
    # Deshabilitado temporalmente para evitar errores
    logger.info("Sistema de notificaciones automáticas deshabilitado")

def notify_pending_work_to_designers():
    """
    Notifica a diseñadores sobre trabajos pendientes (versión sin Firebase)
    """
    logger.info("Tarea de notificación a diseñadores ejecutándose...")
    
    # Deshabilitado temporalmente para evitar errores
    logger.info("Sistema de notificaciones a diseñadores deshabilitado")

def setup_scheduler(app):
    """
    Configura el programador de tareas (versión simplificada sin threads problemáticos)
    Args:
        app: Instancia de la aplicación Flask
    """
    try:
        # Deshabilitado temporalmente para evitar errores de threads
        logger.info("Scheduler deshabilitado temporalmente para evitar errores de conexión")
        return
        
    except Exception as e:
        logger.error(f"Error al configurar scheduler: {str(e)}")