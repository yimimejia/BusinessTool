from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response
from flask_login import login_required, current_user, login_user
from flask import session
from app import db
from app.models import (
    PendingJob, Job, DeliveredJob, CompletedJob, 
    WebAuthnCredential, User, Message
)
from datetime import datetime
import logging
import io
import json
import qrcode
import base64
import urllib.parse
from functools import wraps

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)

def staff_required(f):
    """Decorator para requerir que el usuario sea admin o supervisor"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_staff:
            flash('No tienes permiso para acceder a esta página', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def get_pending_jobs_count():
    """Obtiene el número de trabajos pendientes de verificación"""
    if current_user.is_authenticated and current_user.is_staff:
        return PendingJob.query.filter_by(pending_type='new_job').count()
    return 0

def get_pending_photos_count():
    """Obtiene el número de fotos pendientes de verificación"""
    if current_user.is_authenticated and current_user.is_staff:
        return PendingJob.query.filter_by(pending_type='photo_verification').count()
    return 0

@bp.route('/')
def index():
    """Ruta principal que redirige al dashboard o login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

@bp.route('/dashboard')
@login_required
def dashboard():
    """Vista del dashboard"""
    return render_template('dashboard.html')

@bp.route('/completed-jobs')
@login_required
def completed_jobs():
    """Vista de trabajos completados"""
    jobs = CompletedJob.query.order_by(CompletedJob.completed_at.desc()).all()
    return render_template('completed_jobs.html', jobs=jobs)

@bp.route('/pending-jobs')
@login_required
@staff_required
def view_pending_jobs():
    """Ver trabajos pendientes"""
    jobs = PendingJob.query.order_by(PendingJob.created_at.desc()).all()
    return render_template('pending_jobs.html', jobs=jobs)

@bp.route('/pending-jobs/<int:job_id>/approve', methods=['POST'])
@login_required
@staff_required
def approve_pending_work(job_id):
    """Aprobar un trabajo pendiente"""
    job = PendingJob.query.get_or_404(job_id)

    if request.method == 'POST':
        invoice_number = request.form.get('invoice_number')
        total_amount = request.form.get('total_amount')
        deposit_amount = request.form.get('deposit_amount')
        tags = request.form.get('tags', '').strip()

        try:
            # Crear nuevo trabajo
            new_job = Job(
                description=job.description,
                designer_id=job.designer_id,
                registered_by_id=current_user.id,
                invoice_number=invoice_number,
                client_name=job.client_name,
                phone_number=job.phone_number,
                deposit_amount=deposit_amount,
                tags=tags
            )

            # Generar QR para el nuevo trabajo
            new_job.generate_qr_code()

            # Guardar el nuevo trabajo y eliminar el pendiente
            db.session.add(new_job)
            db.session.delete(job)
            db.session.commit()

            flash('Trabajo aprobado exitosamente', 'success')
            return redirect(url_for('main.view_pending_jobs'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al aprobar el trabajo: {str(e)}', 'error')
            return redirect(url_for('main.view_pending_jobs'))

@bp.route('/pending-jobs/<int:job_id>/reject', methods=['POST'])
@login_required
@staff_required
def reject_pending_work(job_id):
    """Rechazar un trabajo pendiente"""
    job = PendingJob.query.get_or_404(job_id)

    try:
        # Eliminar el trabajo pendiente
        db.session.delete(job)
        db.session.commit()
        flash('Trabajo rechazado exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al rechazar el trabajo: {str(e)}', 'error')

    return redirect(url_for('main.view_pending_jobs'))

# Contexto global para las plantillas
@bp.context_processor
def utility_processor():
    return dict(
        pending_jobs_count=get_pending_jobs_count(),
        pending_photos_count=get_pending_photos_count()
    )

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Vista de login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('login.html')