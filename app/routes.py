from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response
from flask_login import login_required, current_user, login_user, logout_user
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

def admin_required(f):
    """Decorator para requerir que el usuario sea administrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('No tienes permiso para acceder a esta página', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
def index():
    """Ruta principal que redirige al dashboard o login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Vista de login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    logout_user()
    return redirect(url_for('main.login'))

@bp.route('/dashboard')
@login_required
def dashboard():
    """Vista del dashboard"""
    return render_template('dashboard.html')

@bp.route('/pending-verification')
@login_required
@staff_required
def pending_verification():
    """Vista de trabajos pendientes de verificación"""
    jobs = PendingJob.query.filter_by(pending_type='new_job').all()
    return render_template('pending_verification.html', jobs=jobs)

@bp.route('/pending-photos')
@login_required
@staff_required
def pending_photos():
    """Vista de fotos pendientes de aprobación"""
    jobs = PendingJob.query.filter_by(pending_type='photo_verification').all()
    return render_template('pending_photos.html', jobs=jobs)

@bp.route('/delivered-jobs')
@login_required
@staff_required
def delivered_jobs():
    """Vista de trabajos entregados"""
    jobs = DeliveredJob.query.order_by(DeliveredJob.delivered_at.desc()).all()
    return render_template('delivered_jobs.html', jobs=jobs)

@bp.route('/qr-scanner')
@login_required
def qr_scanner():
    """Vista del escáner QR"""
    return render_template('qr_scanner.html')

@bp.route('/manage-users')
@login_required
@admin_required
def manage_users():
    """Vista de gestión de usuarios"""
    users = User.query.all()
    return render_template('manage_users.html', users=users)

@bp.route('/messages')
@login_required
def messages():
    """Vista de mensajes"""
    messages = Message.query.filter_by(recipient_id=current_user.id).order_by(Message.created_at.desc()).all()
    return render_template('messages.html', messages=messages)

@bp.route('/messages/unread')
@login_required
def unread_messages():
    """Obtener cantidad de mensajes no leídos"""
    count = Message.query.filter_by(recipient_id=current_user.id, read=False).count()
    return jsonify({'count': count})

# Funciones auxiliares para el contexto global
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

# Contexto global para las plantillas
@bp.context_processor
def utility_processor():
    return dict(
        pending_jobs_count=get_pending_jobs_count(),
        pending_photos_count=get_pending_photos_count()
    )

@bp.route('/new-pending-job', methods=['GET', 'POST'])
@login_required
def new_pending_job():
    """Crear nuevo trabajo pendiente"""
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            description = request.form.get('description')
            client_name = request.form.get('client_name')
            phone_number = request.form.get('phone_number')

            # Crear nuevo trabajo pendiente
            new_job = PendingJob(
                description=description,
                designer_id=current_user.id,
                registered_by_id=current_user.id,
                client_name=client_name,
                phone_number=phone_number,
                pending_type='new_job'
            )

            db.session.add(new_job)
            db.session.commit()

            flash('Trabajo pendiente creado exitosamente', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el trabajo: {str(e)}', 'error')
            return redirect(url_for('main.new_pending_job'))

    return render_template('new_pending_job.html')

@bp.route('/pending-jobs')
@login_required
@staff_required
def view_pending_jobs():
    """Ver trabajos pendientes"""
    jobs = PendingJob.query.filter_by(pending_type='new_job').order_by(PendingJob.created_at.desc()).all()
    return render_template('pending_jobs.html', jobs=jobs)

@bp.route('/completed-jobs')
@login_required
def completed_jobs():
    """Vista de trabajos completados"""
    jobs = CompletedJob.query.order_by(CompletedJob.completed_at.desc()).all()
    return render_template('completed_jobs.html', jobs=jobs)

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