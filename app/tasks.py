
from flask import render_template
from flask_mail import Message
from app import mail, db
from app.models import User, Job
from datetime import datetime

def send_daily_notification():
    admin_users = User.query.filter(User.is_admin == True).all()
    pending_jobs = Job.query.filter_by(is_completed=False).all()
    
    if admin_users and pending_jobs:
        for admin in admin_users:
            msg = Message(
                subject="Resumen Diario de Trabajos Pendientes",
                recipients=[admin.email],
                body=f"Hay {len(pending_jobs)} trabajos pendientes.\n\n" + 
                     "\n".join([f"- {job.description} ({job.created_at.strftime('%Y-%m-%d')})" for job in pending_jobs])
            )
            mail.send(msg)
