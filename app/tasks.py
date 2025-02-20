from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from flask_sse import sse
from app import db
from app.models import User, Job, Notification

def send_notification(user_id, message, notification_type="info", job_id=None):
    """Envía una notificación al usuario a través de SSE"""
    notification_data = {
        "message": message,
        "type": notification_type,
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    sse.publish(notification_data, type='notification', channel=f'user.{user_id}')

def check_pending_jobs():
    """
    Verifica trabajos pendientes y envía notificaciones:
    - A cada diseñador con trabajos pendientes
    - A los administradores con un resumen de todos los trabajos pendientes
    """
    # Obtener todos los trabajos pendientes
    pending_jobs = Job.query.filter_by(is_completed=False).all()

    # Agrupar trabajos por diseñador
    designer_jobs = {}
    for job in pending_jobs:
        if job.designer_id not in designer_jobs:
            designer_jobs[job.designer_id] = []
        designer_jobs[job.designer_id].append(job)

    # Notificar a cada diseñador
    for designer_id, jobs in designer_jobs.items():
        designer = User.query.get(designer_id)
        for job in jobs:
            # Crear notificación en la base de datos
            notification = Notification.create_pending_job_notification(designer, job)
            # Enviar notificación en tiempo real
            send_notification(
                designer_id,
                f"Tienes un trabajo pendiente: {job.description}",
                "pending_job",
                job.id
            )

    # Notificar a los administradores
    admins = User.query.filter_by(is_admin=True).all()
    pending_count = len(pending_jobs)
    for admin in admins:
        # Crear notificación en la base de datos
        notification = Notification.create_admin_notification(admin, pending_count)
        # Enviar notificación en tiempo real
        send_notification(
            admin.id,
            f"Hay {pending_count} trabajos pendientes en el sistema",
            "admin_alert"
        )

def init_scheduler():
    """Inicializa el planificador de tareas"""
    scheduler = BackgroundScheduler()

    # Agregar tarea para verificar trabajos pendientes cada 40 minutos
    scheduler.add_job(
        func=check_pending_jobs,
        trigger="interval",
        minutes=40,
        id='check_pending_jobs',
        name='Verificar trabajos pendientes',
        replace_existing=True
    )

    scheduler.start()
    return scheduler