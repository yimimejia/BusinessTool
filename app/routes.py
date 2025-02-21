from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response, send_from_directory, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from functools import wraps
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from app import db
from app.models import User, Job, CompletedJob, ActivityLog, DeliveredJob, PendingJob, Message
from app.utils.notifications import send_notification
from flask_sse import sse
from datetime import datetime
import json
import logging
import os
import base64
import qrcode
import urllib.parse
from werkzeug.utils import secure_filename
import io
import time
import re

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
    """Decorator para requerir que el usuario sea admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_manage_users:
            flash('No tienes permiso para acceder a esta página', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def retry_on_db_error(max_retries=3, delay=1):
    """Decorator para reintentar operaciones de base de datos"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return f(*args, **kwargs)
                except (OperationalError, SQLAlchemyError) as e:
                    retries += 1
                    if retries == max_retries:
                        logging.error(f"Max retries reached for database operation: {str(e)}")
                        raise
                    logging.warning(f"Database operation failed, retrying ({retries}/{max_retries})")
                    time.sleep(delay)
                    db.session.rollback()
            return f(*args, **kwargs)
        return wrapper
    return decorator

def log_activity(action, details=None):
    """Registra una actividad en el log"""
    try:
        activity = ActivityLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            details=details,
            ip_address=request.remote_addr,
            timestamp=datetime.utcnow()
        )
        db.session.add(activity)
        db.session.commit()

        # Enviar notificación en tiempo real si es una acción importante
        if action in ['nuevo_trabajo', 'trabajo_completado', 'trabajo_eliminado', 'trabajo_entregado']:
            sse.publish({
                "message": f"{action}: {details}",
                "type": "info"
            }, type='message')
    except Exception as e:
        logger.error(f"Error al registrar actividad: {str(e)}")

@bp.route('/jobs/<int:job_id>/send-photos', methods=['POST'])
@login_required
@retry_on_db_error()
def send_job_photos(job_id):
    """Enviar fotos para un trabajo completado"""
    try:
        job = CompletedJob.query.get_or_404(job_id)

        if 'photos' not in request.files:
            flash('No se seleccionaron fotos', 'error')
            return redirect(url_for('main.completed_jobs'))

        photos = request.files.getlist('photos')
        if not photos or photos[0].filename == '':
            flash('No se seleccionaron fotos', 'error')
            return redirect(url_for('main.completed_jobs'))

        # Crear directorio para las fotos si no existe
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], str(job_id))
        os.makedirs(upload_folder, exist_ok=True)

        # Guardar las fotos
        photo_paths = []
        for photo in photos:
            if photo and photo.filename:
                filename = secure_filename(photo.filename)
                filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                photo_path = os.path.join('uploads', str(job_id), filename)
                full_path = os.path.join(current_app.static_folder, photo_path)
                photo.save(full_path)
                photo_paths.append(photo_path)

        # Crear un PendingJob para la verificación de fotos
        pending_job = PendingJob(
            original_job_id=job.id,
            description=f"Verificación de fotos - Trabajo #{job.id}",
            designer_id=job.designer_id,
            registered_by_id=current_user.id,
            invoice_number=job.invoice_number,
            client_name=job.client_name,
            phone_number=job.phone_number,
            photos=json.dumps(photo_paths),
            pending_type='photo_verification',
            message=request.form.get('message', '')
        )

        db.session.add(pending_job)
        db.session.commit()

        log_activity(
            'enviar_fotos',
            f"Fotos enviadas para verificación - Trabajo #{job.id}, Cliente: {job.client_name}"
        )

        flash('Fotos enviadas para verificación', 'success')
        return redirect(url_for('main.completed_jobs'))

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error al procesar fotos: {str(e)}")
        flash('Error al procesar la solicitud. Por favor, inténtelo de nuevo.', 'error')
        return redirect(url_for('main.completed_jobs'))

@bp.route('/messages/<int:message_id>/approve-photos', methods=['POST'])
@login_required
@admin_required
def approve_photos(message_id):
    """Aprobar y enviar fotos por WhatsApp"""
    message = Message.query.get_or_404(message_id)

    if not message.photos:
        flash('Este mensaje no contiene fotos', 'error')
        return redirect(url_for('main.completed_jobs'))

    # Extraer el ID del trabajo desde el contenido del mensaje
    job_id_match = re.search(r'trabajo #(\d+)', message.content)
    if not job_id_match:
        flash('No se pudo identificar el trabajo asociado', 'error')
        return redirect(url_for('main.completed_jobs'))

    job_id = int(job_id_match.group(1))
    job = CompletedJob.query.get_or_404(job_id)

    # Preparar enlace de WhatsApp con las fotos
    clean_phone = job.phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    photos = json.loads(message.photos)
    photo_urls = [
        f"{request.url_root.rstrip('/')}/static/{photo}"
        for photo in photos
    ]

    # Crear mensaje de WhatsApp con los enlaces de las fotos
    whatsapp_message = f"Hola {job.client_name}, aquí están las fotos de su trabajo:\n\n"
    whatsapp_message += "\n".join(photo_urls)

    # Marcar mensaje como aprobado
    message.is_approved = True
    db.session.commit()

    log_activity(
        'fotos_aprobadas',
        f"Fotos aprobadas y enviadas - Trabajo #{job.id}, Cliente: {job.client_name}"
    )

    # Redirigir a WhatsApp con el mensaje
    whatsapp_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(whatsapp_message)}"
    return redirect(whatsapp_url)

@bp.route('/stream')
def stream():
    return Response(sse.stream(), mimetype='text/event-stream')

@bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            # Si es diseñador, establecer sesión permanente
            if not user.is_admin and not user.is_supervisor:
                user.permanent_session = True
                session.permanent = True
            login_user(user, remember=user.permanent_session)
            log_activity('login', f'Inicio de sesión exitoso - Usuario: {user.username}')
            flash('¡Bienvenido!', 'success')
            return redirect(url_for('main.dashboard'))

        flash('Usuario o contraseña incorrectos', 'error')
        log_activity('login_failed', f'Intento de inicio de sesión fallido - Usuario: {username}')
    return render_template('login.html')

# Nuevas rutas para mensajería

@bp.route('/messages')
@login_required
def messages():
    """Ver mensajes"""
    messages = current_user.get_messages()
    return render_template('messages.html', messages=messages)

@bp.route('/messages/send', methods=['POST'])
@login_required
def send_message():
    """Enviar un mensaje"""
    recipient_id = request.form.get('recipient_id')
    content = request.form.get('content')

    if not recipient_id or not content:
        flash('Por favor complete todos los campos', 'error')
        return redirect(url_for('main.messages'))

    recipient = User.query.get(recipient_id)
    if not recipient:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('main.messages'))

    message = Message(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        content=content
    )
    db.session.add(message)
    db.session.commit()

    log_activity(
        'enviar_mensaje',
        f"Mensaje enviado a {recipient.username}"
    )

    flash('Mensaje enviado exitosamente', 'success')
    return redirect(url_for('main.messages'))

@bp.route('/messages/<int:message_id>/read', methods=['POST'])
@login_required
def mark_message_read(message_id):
    """Marcar un mensaje como leído"""
    message = Message.query.get_or_404(message_id)
    if message.recipient_id != current_user.id:
        flash('No tienes permiso para acceder a este mensaje', 'error')
        return redirect(url_for('main.messages'))

    message.is_read = True
    db.session.commit()
    return jsonify({'status': 'success'})

@bp.route('/messages/unread')
@login_required
def unread_messages_count():
    """Obtener el número de mensajes no leídos"""
    count = current_user.get_unread_messages_count()
    return jsonify({'count': count})

@bp.route('/logout')
@login_required
def logout():
    if current_user.is_authenticated:
        log_activity('logout', f'Cierre de sesión - Usuario: {current_user.username}')
    logout_user()
    return redirect(url_for('main.login'))

@bp.route('/send_whatsapp/<int:job_id>')
@login_required
def send_whatsapp(job_id):
    job = Job.query.get_or_404(job_id)
    
    if not job.phone_number:
        flash('No hay número de teléfono registrado para este cliente', 'error')
        return redirect(url_for('main.dashboard'))

    # Generar enlace de factura
    invoice_url = url_for('main.generate_job_pdf', job_id=job.id, _external=True)
    
    # Obtener enlace de WhatsApp con la factura
    whatsapp_link = job.get_whatsapp_link(with_invoice=True, invoice_url=invoice_url)
    
    # Registrar actividad
    log_activity(
        'enviar_whatsapp',
        f"Mensaje WhatsApp enviado a {job.client_name} (Factura: {job.invoice_number})"
    )
    
    return redirect(whatsapp_link)

@bp.route('/generate_invoice/<int:job_id>')
@login_required
def generate_invoice(job_id):
    job = Job.query.get_or_404(job_id)
    
    # Generate QR code with job info
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"https://{request.host}/job/{job.id}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert QR to base64 for embedding in HTML
    buffered = io.BytesIO()
    qr_img.save(buffered, format="PNG")
    qr_code = base64.b64encode(buffered.getvalue()).decode()
    
    # Render invoice template
    html = render_template('invoice_pdf.html', 
                         job=job,
                         qr_code=f"data:image/png;base64,{qr_code}")
                         
    return html

@bp.route('/dashboard')
@login_required
def dashboard():
    """Vista del dashboard con estadísticas por rol"""
    if current_user.is_admin:
        # Vista de administrador
        jobs = Job.query.order_by(Job.created_at.desc()).all()
        stats = {
            'total_jobs': len(jobs),
            'completed_jobs': CompletedJob.query.count(),
            'pending_jobs': Job.query.filter_by(status='pending').count(),
            'designers_count': User.query.filter_by(is_designer=True).count()
        }
    elif current_user.is_supervisor:
        # Vista de supervisor
        jobs = Job.query.order_by(Job.created_at.desc()).all()
        stats = {
            'total_jobs': len(jobs),
            'completed_jobs': CompletedJob.query.count(),
            'pending_jobs': Job.query.filter_by(status='pending').count(),
            'designers_count': User.query.filter_by(is_designer=True).count()
        }
    else:
        # Vista de diseñador
        jobs = Job.query.filter_by(designer_id=current_user.id).order_by(Job.created_at.desc()).all()
        stats = {
            'total_jobs': len(jobs),
            'completed_jobs': CompletedJob.query.filter_by(designer_id=current_user.id).count(),
            'pending_jobs': Job.query.filter_by(designer_id=current_user.id, status='pending').count(),
            'delivered_jobs': DeliveredJob.query.filter_by(designer_id=current_user.id).count()
        }

    if current_user.is_admin:
        # Vista de administrador
        jobs = Job.query.order_by(Job.created_at.desc()).all()
        pending_jobs = PendingJob.query.order_by(PendingJob.created_at.desc()).all()
        return render_template('dashboard_admin.html', 
                             jobs=jobs, 
                             pending_jobs=pending_jobs,
                             stats=stats)

    elif current_user.is_supervisor:
        # Vista de supervisor
        pending_jobs = PendingJob.query.order_by(PendingJob.created_at.desc()).all()
        pending_verification_count = PendingJob.query.filter_by(pending_type='new_job').count()
        pending_photos_count = PendingJob.query.filter_by(pending_type='photo_verification').count()

        return render_template('dashboard_supervisor.html',
                             pending_jobs=pending_jobs,
                             pending_verification_count=pending_verification_count,
                             pending_photos_count=pending_photos_count,
                             stats=stats)

    else:
        # Vista de diseñador
        jobs = Job.query.filter_by(designer_id=current_user.id).order_by(Job.created_at.desc()).all()
        stats = {
            'total_jobs': len(jobs),
            'completed_jobs': CompletedJob.query.filter_by(designer_id=current_user.id).count(),
            'pending_jobs': Job.query.filter_by(designer_id=current_user.id, status='pending').count(),
            'delivered_jobs': DeliveredJob.query.filter_by(designer_id=current_user.id).count()
        }
        return render_template('dashboard_designer.html', jobs=jobs, stats=stats)

@bp.route('/manage-users')
@login_required
@admin_required
def manage_users():
    users = User.query.all()
    return render_template('manage_users.html', users=users)

@bp.route('/users/create', methods=['POST'])
@login_required
@admin_required
def create_user():
    if not current_user.is_admin:
        flash('Solo los administradores pueden crear usuarios', 'error')
        return redirect(url_for('main.dashboard'))

    name = request.form.get('name')
    username = request.form.get('username')
    password = request.form.get('password')
    user_type = request.form.get('user_type', 'designer')

    if User.query.filter_by(username=username).first():
        flash('El nombre de usuario ya existe', 'error')
        return redirect(url_for('main.manage_users'))

    try:
        user = User(
            name=name,
            username=username,
            is_admin=user_type == 'admin',
            is_supervisor=user_type == 'supervisor',
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        log_activity(
            'crear_usuario',
            f'Usuario creado: {username} (Tipo: {user_type})'
        )

        flash('Usuario creado exitosamente', 'success')
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('main.manage_users'))

    return redirect(url_for('main.manage_users'))

@bp.route('/users/<int:user_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit_user(user_id):
    if not current_user.is_admin:
        flash('Solo los administradores pueden editar usuarios', 'error')
        return redirect(url_for('main.dashboard'))

    user = User.query.get_or_404(user_id)

    # Verificar contraseña de administrador
    admin_password = request.form.get('admin_password')
    if not current_user.check_password(admin_password):
        flash('Contraseña de administrador incorrecta', 'error')
        return redirect(url_for('main.manage_users'))

    name = request.form.get('name')
    user_type = request.form.get('user_type')
    new_password = request.form.get('new_password')

    try:
        user.name = name
        user.is_admin = user_type == 'admin'
        user.is_supervisor = user_type == 'supervisor'

        if new_password:
            user.set_password(new_password)

        db.session.commit()
        log_activity(
            'editar_usuario',
            f'Usuario editado: {user.username}'
        )
        flash('Usuario actualizado exitosamente', 'success')
    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('main.manage_users'))

@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Solo los administradores pueden eliminar usuarios', 'error')
        return redirect(url_for('main.dashboard'))

    # Verificar contraseña de administrador
    admin_password = request.form.get('admin_password')
    if not current_user.check_password(admin_password):
        flash('Contraseña de administrador incorrecta', 'error')
        return redirect(url_for('main.manage_users'))

    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        flash('No se puede eliminar el usuario administrador principal', 'error')
        return redirect(url_for('main.manage_users'))

    # Verificar si el usuario tiene trabajos completados
    has_completed_jobs = CompletedJob.query.filter_by(designer_id=user_id).first() is not None
    has_active_jobs = Job.query.filter_by(designer_id=user_id).first() is not None

    if has_completed_jobs or has_active_jobs:
        flash('No se puede eliminar el usuario porque tiene trabajos asociados. ' +
              'Por favor, reasigne o elimine los trabajos antes de eliminar el usuario.', 'error')
        return redirect(url_for('main.manage_users'))

    try:
        log_activity(
            'eliminar_usuario',
            f'Usuario eliminado: {user.username}'
        )

        db.session.delete(user)
        db.session.commit()
        flash('Usuario eliminado exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al eliminar usuario: {str(e)}")
        flash('Error al eliminar el usuario. Por favor, inténtelo de nuevo.', 'error')

    return redirect(url_for('main.manage_users'))

@bp.route('/jobs/new', methods=['GET', 'POST'])
@login_required
def new_job():
    """Crear nuevo trabajo"""
    if request.method == 'POST':
        try:
            # Formatear número de teléfono
            phone_number = request.form.get('phone_number', '').strip()
            if phone_number and not phone_number.startswith('+1'):
                phone_number = f'+1{phone_number}' if phone_number.startswith('1') else f'+1{phone_number}'

            # Procesar etiquetas
            tags = request.form.get('tags', '').strip()
            if tags:
                tags = ','.join([tag.strip() for tag in tags.split(',') if tag.strip()])

            # Si no es staff, siempre usar el ID del usuario actual como diseñador
            designer_id = request.form.get('designer_id') if current_user.is_staff else current_user.id

            # Crear el trabajo
            job = Job(
                description=request.form.get('description'),
                designer_id=designer_id,
                registered_by_id=current_user.id,
                invoice_number=request.form.get('invoice_number'),
                client_name=request.form.get('client_name'),
                phone_number=phone_number,
                tags=tags,
                total_amount=float(request.form.get('total_amount', 0))
            )

            db.session.add(job)
            db.session.commit()

            log_activity(
                'nuevo_trabajo',
                f"Trabajo creado para {job.client_name} (Factura: {job.invoice_number})"
            )

            flash('Trabajo creado exitosamente', 'success')
            return redirect(url_for('main.dashboard'))

        except ValueError as e:
            flash(str(e), 'error')
            db.session.rollback()
        except Exception as e:
            logger.error(f"Error al crear trabajo: {str(e)}")
            flash('Error al crear el trabajo', 'error')
            db.session.rollback()

    # Solo obtener diseñadores si el usuario es staff
    designers = User.query.filter_by(is_admin=False, is_supervisor=False).all() if current_user.is_staff else None
    return render_template('new_job.html', designers=designers)

@bp.route('/jobs/<int:job_id>/qr')
@login_required
def show_job_qr(job_id):
    """Muestra la página con el QR del trabajo"""
    job = Job.query.get_or_404(job_id)

    # Generar el QR si no existe
    if not job.qr_code:
        job.generate_qr_code()
        db.session.commit()

    # Crear QR con mejor calidad y tamaño
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=15,
        border=4
    )

    # Usar solo la URL en el QR para simplicidad
    qr_data = f"{request.url_root.rstrip('/')}/jobs/public/{job.qr_code}"
    qr.add_data(qr_data)
    qr.make(fit=True)

    # Crear imagen con mejor contraste
    img = qr.make_image(fill_color="black", back_color="white")

    # Convertir a base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG", quality=100)
    qr_image = base64.b64encode(buffered.getvalue()).decode()

    return render_template('job_qr.html', job=job, qr_image=qr_image)


@bp.route('/jobs/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
@staff_required
def edit_job(job_id):
    job = Job.query.get_or_404(job_id)

    if request.method == 'POST':
        job.description = request.form.get('description')
        job.designer_id = request.form.get('designer_id')
        job.invoice_number = request.form.get('invoice_number')
        job.client_name = request.form.get('client_name')
        job.phone_number = request.form.get('phone_number')
        db.session.commit()
        flash('Trabajo actualizado exitosamente', 'success')
        return redirect(url_for('main.dashboard'))

    designers = User.query.filter_by(is_admin=False, is_supervisor=False).all()
    return render_template('edit_job.html', job=job, designers=designers)

@bp.route('/completed-jobs/<int:job_id>/mark-called', methods=['POST'])
@login_required
@staff_required
def mark_called(job_id):
    job = CompletedJob.query.get_or_404(job_id)
    job.is_called = True
    job.called_at = datetime.utcnow()
    db.session.commit()
    flash('Cliente marcado como notificado', 'success')
    return redirect(url_for('main.completed_jobs'))

@bp.route('/completed-jobs/<int:job_id>/mark-delivered', methods=['POST'])
@login_required
@staff_required
def mark_delivered(job_id):
    job = CompletedJob.query.get_or_404(job_id)

    # Crear un nuevo trabajo entregado
    delivered_job = DeliveredJob(
        original_job_id=job.original_job_id,
        completed_job_id=job.id,
        description=job.description,
        designer_id=job.designer_id,
        registered_by_id=job.registered_by_id,  # Mantener el usuario que registró
        invoice_number=job.invoice_number,
        client_name=job.client_name,
        phone_number=job.phone_number,
        created_at=job.created_at,
        completed_at=job.completed_at,
        called_at=job.called_at,
        delivered_at=datetime.utcnow(),
        tags=job.tags
    )

    # Agregar el nuevo trabajo entregado y eliminar el trabajo completado
    db.session.add(delivered_job)
    db.session.delete(job)
    db.session.commit()

    log_activity(
        'trabajo_entregado',
        f"Trabajo entregado: {delivered_job.client_name} (Factura: {delivered_job.invoice_number})"
    )

    flash('Trabajo marcado como entregado', 'success')
    return redirect(url_for('main.completed_jobs'))

@bp.route('/jobs/<int:job_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_job(job_id):
    password = request.form.get('admin_password')
    if not password:
        flash('Se requiere contraseña para eliminar', 'error')
        return redirect(url_for('main.dashboard'))

    # Verificar si la contraseña coincide con algún admin solamente
    admins = User.query.filter_by(is_admin=True).all()

    valid_password = False
    for admin in admins:
        if admin.check_password(password):
            valid_password = True
            break

    if not valid_password:
        flash('Contraseña incorrecta. Se requiere contraseña de administrador.', 'error')
        return redirect(url_for('main.dashboard'))

    job = Job.query.get_or_404(job_id)
    db.session.delete(job)
    db.session.commit()

    log_activity(
        'trabajo_eliminado',
        f"Trabajo eliminado: {job.client_name} (Factura: {job.invoice_number})"
    )

    flash('Trabajo eliminado exitosamente', 'success')
    return redirect(url_for('main.dashboard'))

@bp.route('/completed-jobs')
@login_required
def completed_jobs():
    """Ver trabajos completados"""
    if current_user.is_staff:
        # Si es staff (admin o supervisor) ve todos los trabajos
        jobs = CompletedJob.query.order_by(CompletedJob.completed_at.desc()).all()
    else:
        # Si es diseñador, solo ve sus trabajos completados
        jobs = CompletedJob.query.filter_by(designer_id=current_user.id).order_by(CompletedJob.completed_at.desc()).all()

    return render_template('completed_jobs.html', jobs=jobs)

@bp.route('/jobs/<int:job_id>/complete', methods=['POST'])
@login_required
def complete_job(job_id):
    """Completar un trabajo y moverlo a la tabla de trabajos completados"""
    # Obtener contraseña del admin (ya sea de JSON o form data)
    data = request.get_json() or request.form
    admin_password = data.get('admin_password')

    if not admin_password:
        return jsonify({'success': False, 'message': 'Se requiere contraseña de administrador'})

    job = Job.query.get_or_404(job_id)

    # Verificar que el usuario tenga permiso para completar este trabajo
    if not current_user.is_staff and job.designer_id != current_user.id:
        return jsonify({'success': False, 'message': 'No tienes permiso para completar este trabajo'})

    # Verificar contraseña de administrador
    admins = User.query.filter_by(is_admin=True).all()
    valid_admin = False
    for admin in admins:
        if admin.check_password(admin_password):
            valid_admin = True
            break

    if not valid_admin:
        return jsonify({'success': False, 'message': 'Contraseña de administrador incorrecta'})

    try:
        # Crear trabajo completado
        completed_job = CompletedJob(
            original_job_id=job.id,
            description=job.description,
            designer_id=job.designer_id,
            registered_by_id=job.registered_by_id,
            invoice_number=job.invoice_number,
            client_name=job.client_name,
            phone_number=job.phone_number,
            created_at=job.created_at,
            completed_at=datetime.utcnow(),
            tags=job.tags
        )

        # Agregar el trabajo completado y eliminar el trabajo original
        db.session.add(completed_job)
        db.session.delete(job)
        db.session.commit()

        log_activity(
            'trabajo_completado',
            f"Trabajo completado para {completed_job.client_name} (Factura: {completedjob.invoice_number})"
        )

        return jsonify({'success': True, 'message': 'Trabajo completado exitosamente'})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al completar trabajo: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al procesar la solicitud'})

@bp.route('/setup')
def setup():
    if User.query.first() is not None:
        flash('La configuración inicial ya se realizó', 'warning')
        return redirect(url_for('main.login'))

    # Crear admin
    admin = User(
        username='admin',
        name='Administrador',
        is_admin=True,
        is_supervisor=False,
        is_designer=False
    )
    admin.set_password('admin123')
    db.session.add(admin)

    # Crear usuario supervisor
    supervisor = User(
        username='supervisor',
        name='Supervisor',
        is_admin=False,
        is_supervisor=True,
        is_designer=False
    )
    supervisor.set_password('super123')
    db.session.add(supervisor)

    # Crear usuarios PC01-PC09 (diseñadores)
    for i in range(1, 10):
        username = f'pc{i:02d}'
        user = User(
            username=username,
            name=f'PC{i:02d}',
            is_admin=False,
            is_supervisor=False,
            is_designer=True
        )
        user.set_password('1245')
        db.session.add(user)

    db.session.commit()
    flash('Usuarios creados exitosamente', 'success')
    return redirect(url_for('main.login'))

@bp.route('/static/reports/<path:filename>')
def serve_report(filename):
    """Servir archivos de reporte"""
    return send_from_directory('static/reports', filename)

@bp.route('/send-report', methods=['POST'])
@login_required
@staff_required
def send_manual_report():
    from app.utils.whatsapp import get_whatsapp_report_url

    # Lista de números de WhatsApp a los que enviar el reporte
    whatsapp_numbers = ['+18492653436', '+18097162675']

    # Generar enlaces para cada número
    report_links = []
    for number in whatsapp_numbers:
        try:
            url = get_whatsapp_report_url(number)
            report_links.append(url)
        except Exception as e:
            print(f"Error generando URL para {number}: {str(e)}")

    # Registrar la actividad
    log_activity(
        'reporte_generado',
        f"Enlaces de reporte de trabajos pendientes generados"
    )

    # Devolver los enlaces como JSON
    return jsonify({
        'success': True,
        'message': 'Enlaces de WhatsApp generados',
        'links': report_links
    })

@bp.route('/jobs/export/<format>')
@login_required
@staff_required
def export_jobs(format):
    """Exportar trabajos a Excel o PDF"""
    if format not in ['excel', 'pdf']:
        flash('Formato no soportado', 'error')
        return redirect(url_for('main.dashboard'))

    jobs = Job.query.all()

    if format == 'excel':
        # Crear un nuevo libro de Excel
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Trabajos"

        # Encabezados
        headers = ['ID', 'Descripción', 'Cliente', 'Factura', 'Teléfono', 'Diseñador', 'Estado', 'Fecha Creación']
        ws.append(headers)

        # Datos
        for job in jobs:
            ws.append([
                job.id,
                job.description,
                job.client_name,
                job.invoice_number,
                job.phone_number,
                job.designer.name,
                'Completado' if job.is_completed else 'Pendiente',
                job.created_at.strftime('%Y-%m-%d %H:%M')
            ])

        # Crear el archivo en memoria
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return Response(
                        output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',            headers={'Content-Disposition': f'attachment;filename=trabajos_{datetime.now().strftime("%Y%m%d")}.xlsx'}
        )

    else:  # PDF
        html = render_template(
            'export_pdf.html',
            jobs=jobs,
            current_time=datetime.now().strftime('%Y-%m-%d %H:%M')
        )

        return Response(
            html,
            mimetype='text/html',
            headers={'Content-Disposition': f'attachment;filename=trabajos_{datetime.now().strftime("%Ym%d")}.pdf'}
        )

@bp.route('/jobs/search', methods=['GET'])
@login_required
def search_jobs():
    query = request.args.get('q', '')
    status = request.args.get('status')
    designer = request.args.get('designer')
    tag = request.args.get('tag')

    jobs_query = Job.query

    if query:
        jobs_query = jobs_query.filter(
            (Job.description.ilike(f'%{query}%')) |
            (Job.client_name.ilike(f'%{query}%')) |
            (Job.invoice_number.ilike(f'%{query}%'))
        )

    if status:
        jobs_query = jobs_query.filter_by(is_completed=(status == 'completed'))

    if designer and current_user.is_staff:
        jobs_query = jobs_query.filter_by(designer_id=designer)

    if tag:
        jobs_query = jobs_query.filter(Job.tags.ilike(f'%{tag}%'))

    jobs = jobs_query.all()
    return jsonify([{
        'id': job.id,
        'description': job.description,
        'client_name': job.client_name,
        'invoice_number': job.invoice_number,
        'designer': job.designer.name,
        'status': 'Completado' if job.is_completed else 'Pendiente'
    } for job in jobs])

@bp.route('/delivered-jobs')
@login_required
@staff_required
def delivered_jobs():
    jobs = DeliveredJob.query.all()
    return render_template('delivered_jobs.html', jobs=jobs)

@bp.route('/webauthn/status', methods=['POST'])
def webauthn_status():
    """Verifica si el usuario tiene credenciales biométricas registradas"""
    try:
        username = request.json.get('username')
        if not username:
            return jsonify({'error': 'Se requiere nombre de usuario'}), 400

        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'enabled': False})

        has_credentials = WebAuthnCredential.query.filter_by(user_id=user.id).first() is not None
        return jsonify({
            'enabled': has_credentials,
            'credentials': [
                {
                    'id': cred.id,
                    'name': cred.name,
                    'created_at': cred.created_at.isoformat(),
                    'last_used_at': cred.last_used_at.isoformat() if cred.last_used_at else None
                }
                for cred in user.webauthn_credentials
            ] if has_credentials else []
        })
    except Exception as e:
        logging.error(f"Error verificando estado biométrico: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/webauthn/register/begin', methods=['POST'])
@login_required
def webauthn_register_begin():
    """Inicia el proceso de registro de credenciales biométricas"""
    try:
        device_name = request.json.get('device_name', 'Dispositivo sin nombre')

        # Detectar si es un dispositivo iOS
        user_agent = request.headers.get('User-Agent', '').lower()
        is_ios = 'iphone' in user_agent or 'ipad' in user_agent

        # Configuración optimizada para iOS/Face ID
        registration_options = generate_registration_options(
            rp_id=request.host.split(':')[0],
            rp_name="FOTO VIDEO MOJICA",
            user_id=str(current_user.id),
            user_name=current_user.username,
            user_display_name=current_user.name,
            authenticator_selection=AuthenticatorSelectionCriteria(
                authenticator_attachment="platform",  # Forzar autenticador de plataforma para Face ID
                require_resident_key=False,
                user_verification=UserVerificationRequirement.PREFERRED if is_ios else UserVerificationRequirement.DISCOURAGED
            ),
            timeout=30000,  # 30 segundos es suficiente para iOS
            attestation="none"
        )

        # Guardar datos en la sesión
        session['webauthn_registration_challenge'] = registration_options.challenge
        session['webauthn_device_name'] = device_name

        logger.info(f"Iniciando registro biométrico para usuario {current_user.username} en {'iOS' if is_ios else 'otro dispositivo'}")

        # Convertir opciones a JSON
        options_json = options_to_json(registration_options)
        return jsonify(options_json)

    except Exception as e:
        logger.error(f"Error en registro biométrico: {str(e)}")
        error_message = str(e)
        if "did not match the expected pattern" in error_message:
            error_message = "Por favor, asegúrese de que Face ID esté habilitado y configurado en su dispositivo"
        elif "timeout" in error_message.lower():
            error_message = "No se recibió respuesta de Face ID. Por favor, intente nuevamente"
        return jsonify({'error': error_message}), 400

@bp.route('/webauthn/register/complete', methods=['POST'])
@login_required
def webauthn_register_complete():
    """Completa el proceso de registro de credenciales biométricas"""
    try:
        challenge = session.pop('webauthn_registration_challenge', None)
        device_name = session.pop('webauthn_device_name', 'Dispositivo sin nombre')

        if not challenge:
            raise ValueError("No se encontró el challenge de registro")

        credential = RegistrationCredential.from_json(request.json)

        verification = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=request.host.split(':')[0],
            expected_origin=request.url_root.rstrip('/'),
            require_user_verification=False  # Más permisivo para móviles
        )

        # Guardar credencial
        # Guardar credencial en la base de datos
        new_credential = WebAuthnCredential(
            user_id=current_user.id,
            credential_id=base64.b64encode(verification.credential_id).decode(),
            public_key=verification.credential_public_key.hex(),
            sign_count=verification.sign_count,
            name=device_name
        )
        db.session.add(new_credential)
        db.session.commit()

        log_activity('registro_biometrico', f'Registro biométrico exitoso - Usuario: {current_user.username}')
        return jsonify({'status': 'success'})

    except Exception as e:
        logging.error(f"Error en registro biométrico: {str(e)}")
        error_msg = str(e)
        if "did not match the expected pattern" in error_msg:
            error_msg = "Error de compatibilidad con el dispositivo. Por favor, intente con otro método de autenticación."
        return jsonify({'status': 'error', 'message': error_msg}), 400

@bp.route('/webauthn/authenticate/begin', methods=['POST'])
def webauthn_authenticate_begin():
    """Inicia el proceso de autenticación biométrica"""
    try:
        username = request.json.get('username')
        if not username:
            raise ValueError("Se requiere el nombre de usuario")

        user = User.query.filter_by(username=username).first()
        if not user:
            raise ValueError("Usuario no encontrado")

        credentials = WebAuthnCredential.query.filter_by(user_id=user.id).all()
        if not credentials:
            raise ValueError("El usuario no tiene credenciales biométricas registradas")

        allowed_credentials = [
            {"type": "public-key", "id": base64url_to_bytes(cred.credential_id)}
            for cred in credentials
        ]

        # Configuración más flexible para autenticación
        authentication_options = generate_authentication_options(
            rp_id=request.host.split(':')[0],
            allow_credentials=allowed_credentials,
            user_verification=UserVerificationRequirement.PREFERRED,
            timeout=180000  # 3 minutos
        )

        session['webauthn_authentication_challenge'] = authentication_options.challenge
        session['webauthn_authentication_username'] = username

        logger.info(f"Iniciando autenticación biométrica para usuario {username}")
        return jsonify(options_to_json(authentication_options))

    except Exception as e:
        logger.error(f"Error iniciando autenticación biométrica: {str(e)}")
        error_message = str(e)
        if "no credentials" in error_message.lower():
            error_message = "No se encontraron credenciales biométricas. Por favor, registre su dispositivo primero."
        elif "timeout" in error_message.lower():
            error_message = "El proceso tomó demasiado tiempo. Por favor, intente nuevamente."
        return jsonify({'error': error_message}), 400

@bp.route('/webauthn/authenticate/complete', methods=['POST'])
def webauthn_authenticate_complete():
    """Completa el proceso de autenticación biométrica"""
    try:
        challenge = session.pop('webauthn_authentication_challenge', None)
        username = session.pop('webauthn_authentication_username', None)

        if not challenge or not username:
            raise ValueError("Datos de autenticación no encontrados. Por favor, inicie el proceso nuevamente.")

        user = User.query.filter_by(username=username).first()
        if not user:            raise ValueError("Usuario no encontrado")

        credential = AuthenticationCredential.from_json(request.json)

        # Buscar la credencial en la base de datos
        db_credential = WebAuthnCredential.query.filter_by(
            credential_id=base64.b64encode(credential.raw_id).decode()
        ).first()

        if not db_credential:
            raise ValueError("Credencial no encontrada. Por favor, registre su dispositivo nuevamente.")

        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=request.host.split(':')[0],
            expected_origin=request.url_root.rstrip('/'),
            credential_public_key=bytes.fromhex(db_credential.public_key),
            credential_current_sign_count=db_credential.sign_count,
            require_user_verification=True
        )

        # Actualizar el contador de firmas y última vez usado
        db_credential.sign_count = verification.new_sign_count
        db_credential.last_used_at = datetime.utcnow()

        # Iniciar sesión del usuario
        login_user(user)
        log_activity('login_biometrico', f'Inicio de sesión biométrico exitoso - Usuario: {user.username}')

        db.session.commit()
        logger.info(f"Autenticación biométrica exitosa para usuario {username}")
        return jsonify({'status': 'success'})

    except Exception as e:
        logger.error(f"Error completando autenticación biométrica: {str(e)}")
        error_message = str(e)
        if "user verification" in error_message.lower():
            error_message = "La verificación biométrica falló. Por favor, intente nuevamente."
        elif "challenge" in error_message.lower():
            error_message = "La sesión ha expirado. Por favor, inicie el proceso nuevamente."
        return jsonify({'status': 'error', 'message': error_message}), 400

@bp.route('/jobs/<int:job_id>/pdf')
def generate_job_pdf(job_id):
    """Genera un PDF de la factura con código QR - accesible públicamente"""
    job = Job.query.get_or_404(job_id)
    
    # Generar QR si no existe
    if not job.qr_code:
        job.generate_qr_code()
        db.session.commit()
        
    # Crear QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4
    )
    
    # Agregar URL pública
    qr_url = f"{request.url_root.rstrip('/')}/jobs/public/{job.qr_code}"
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    # Crear imagen QR
    img_buffer = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(img_buffer, format='PNG')
    qr_image = base64.b64encode(img_buffer.getvalue()).decode()
    
    # Generar el QR si no existe
    if not job.qr_code:
        job.generate_qr_code()
        db.session.commit()
    
    # Generar QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=15,
        border=4
    )
    qr.add_data(json.dumps(job.to_qr_data()))
    qr.make(fit=True)
    
    # Crear imagen con mejor contraste
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir a base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG", quality=100)
    qr_image = base64.b64encode(buffered.getvalue()).decode()
    
    # Renderizar el HTML
    html = render_template('invoice_pdf.html', job=job, qr_image=qr_image)
    
    # Convertir a PDF usando WeasyPrint
    from weasyprint import HTML
    pdf = HTML(string=html).write_pdf()
    
    return Response(
        pdf,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename=factura_{job.invoice_number}.pdf',
            'Content-Type': 'application/pdf'
        }
    )

@bp.route('/process-qr', methods=['POST'])
def process_qr():
    """Procesa un código QR escaneado sin requerir autenticación"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No se recibieron datos'}), 400

        # Obtener el código QR
        qr_code = data.get('qr_code')
        if not qr_code:
            return jsonify({'success': False, 'message': 'Código QR inválido'}), 400

        # Buscar el trabajo por el código QR
        job = Job.query.filter_by(qr_code=qr_code).first()
        if not job:
            return jsonify({'success': False, 'message': 'Trabajo no encontrado'}), 404

        # Redirigir a la vista pública del trabajo
        return jsonify({
            'success': True,
            'message': 'Trabajo encontrado',
            'redirect_url': url_for('main.generate_job_pdf', job_id=job.id)
        })

    except Exception as e:
        logger.error(f"Error procesando QR: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/qr-scanner')
def qr_scanner():
    """Página pública para escanear códigos QR"""
    return render_template('qr_scanner.html')

@bp.route('/jobs/public/<qr_code>')
def public_job(qr_code):
    job = Job.query.filter_by(qr_code=qr_code).first()
    if not job:
        return "Trabajo no encontrado", 404
    return render_template('public_job.html', job=job)

@bp.route('/jobs/pending/new', methods=['GET', 'POST'])
@login_required
def new_pending_job():
    try:
        if request.method == 'POST':
            try:
                phone_number = request.form.get('phone_number')
                if not phone_number.startswith('+1'):
                    phone_number = f'+1{phone_number}' if phone_number.startswith('1') else f'+1{phone_number}'

                pending_job = PendingJob(
                    description=request.form.get('description'),
                    designer_id=request.form.get('designer_id'),
                    registered_by_id=current_user.id,
                    invoice_number=request.form.get('invoice_number'),
                    client_name=request.form.get('client_name'),
                    phone_number=phone_number
                )

                db.session.add(pending_job)
                db.session.commit()

                log_activity(
                    'nuevo_trabajo_pendiente',
                    f"Trabajo pendiente creado para {pending_job.client_name} (Factura: {pending_job.invoice_number})"
                )

                flash('Trabajo enviado para verificación', 'success')
                return redirect(url_for('main.dashboard'))

            except ValueError as e:
                flash(str(e), 'error')
                db.session.rollback()
            except Exception as e:
                flash('Error al crear el trabajo. Verifica el formato del número telefónico (+1-XXX-XXXXXXX)', 'error')
                db.session.rollback()

        designers = User.query.filter_by(is_admin=False, is_supervisor=False).all()
        return render_template('new_pending_job.html', designers=designers)
    except Exception as e:
        flash(f'Error al cargar la página: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/jobs/pending/verification', methods=['GET', 'POST'])
@login_required
@staff_required
def pending_verification():
    """Vista de trabajos pendientes por verificar"""
    try:
        jobs = PendingJob.query.filter_by(pending_type='new_job').all()
        return render_template('pending_verification.html', jobs=jobs)
    except Exception as e:
        flash(f'Error al cargar trabajos pendientes: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/jobs/pending/photos')
@login_required
@staff_required
def pending_photos():
    """Vista de fotos pendientes por aprobar"""
    try:
        jobs = PendingJob.query.filter_by(pending_type='photo_verification').all()
        return render_template('pending_photos.html', jobs=jobs)
    except Exception as e:
        flash(f'Error al cargar fotos pendientes: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/jobs/pending/<int:job_id>/approve', methods=['POST'])
@login_required
@staff_required
def approve_pending_job(job_id):
    """Aprobar un trabajo pendiente"""
    try:
        pending_job = PendingJob.query.get_or_404(job_id)

        if pending_job.pending_type == 'photo_verification':
            # Si es verificación de fotos, aprobar y enviar por WhatsApp
            photos = json.loads(pending_job.photos) if pending_job.photos else []

            # Preparar mensaje de WhatsApp con las fotos
            clean_phone = pending_job.phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            photo_urls = [
                f"{request.url_root.rstrip('/')}/static/{photo}"
                for photo in photos
            ]

            whatsapp_message = f"Hola {pending_job.client_name}, aquí están las fotos de su trabajo:\n\n"
            whatsapp_message += "\n".join(photo_urls)

            # Eliminar el trabajo pendiente
            db.session.delete(pending_job)
            db.session.commit()

            log_activity(
                'fotos_aprobadas',
                f"Fotos aprobadas y enviadas - Trabajo #{pending_job.original_job_id}, Cliente: {pending_job.client_name}"
            )

            # Redirigir a WhatsApp con el mensaje
            whatsapp_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(whatsapp_message)}"
            return redirect(whatsapp_url)

        else:
            # Crear el trabajo regular
            job = Job(
                description=pending_job.description,
                designer_id=pending_job.designer_id,
                registered_by_id=current_user.id,
                invoice_number=request.form.get('invoice_number'),
                client_name=pending_job.client_name,
                phone_number=pending_job.phone_number,
                total_amount=request.form.get('total_amount', type=float),
                deposit_amount=request.form.get('deposit_amount', type=float),
                tags=request.form.get('tags', '').strip()
            )

            # Generar código QR
            job.generate_qr_code()

            db.session.add(job)
            db.session.delete(pending_job)
            db.session.commit()

            log_activity(
                'trabajo_aprobado',
                f"Trabajo aprobado: {job.client_name} (Factura: {job.invoice_number})"
            )

            flash('Trabajo aprobado exitosamente', 'success')
            return redirect(url_for('main.pending_jobs'))

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error al aprobar trabajo pendiente: {str(e)}")
        flash('Error al procesar la solicitud. Por favor, inténtelo de nuevo.', 'error')
        return redirect(url_for('main.pending_jobs'))

@bp.route('/jobs/pending/<int:job_id>/reject', methods=['POST'])
@login_required
@staff_required
def reject_pending_job(job_id):
    """Rechazar un trabajo pendiente"""
    pending_job = PendingJob.query.get_or_404(job_id)

    try:
        log_activity(
            'trabajo_rechazado',
            f"Trabajo rechazado para {pending_job.client_name} (Factura: {pending_job.invoice_number})"
        )

        db.session.delete(pending_job)
        db.session.commit()

        flash('Trabajo rechazado', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al rechazar el trabajo: {str(e)}', 'error')

    return redirect(url_for('main.pending_jobs'))

@bp.route('/jobs/public/<qr_code>')
def verify_job_qr(qr_code):
    """Ruta pública para verificar un trabajo mediante QR"""
    job = Job.query.filter_by(qr_code=qr_code).first()
    completed_job = CompletedJob.query.filter_by(qr_code=qr_code).first()
    pending_job = PendingJob.query.filter_by(qr_code=qr_code).first()

    if not any([job, completed_job, pending_job]):
        flash('Código QR no válido', 'error')
        return redirect(url_for('main.login'))

    # Determinar qué tipo de trabajo es y procesarlo
    if job:
        delivered_job = create_delivered_job_from_job(job)
        db.session.delete(job)
    elif completed_job:
        delivered_job = create_delivered_job_from_completed(completed_job)
        db.session.delete(completed_job)
    elif pending_job:
        delivered_job = create_delivered_job_from_pending(pending_job)
        db.session.delete(pending_job)

    db.session.add(delivered_job)
    db.session.commit()

    log_activity(
        'trabajo_entregado_qr',
        f"Trabajo entregado por escaneo QR: {delivered_job.client_name} (Factura: {delivered_job.invoice_number})"
    )

    flash('¡Trabajo marcado como entregado exitosamente!', 'success')
    return render_template('job_delivered.html', job=delivered_job)

def create_delivered_job_from_job(job):
    """Crea un trabajo entregado a partir de un trabajo regular"""
    return DeliveredJob(
        original_job_id=job.id,
        description=job.description,
        designer_id=job.designer_id,
        registered_by_id=job.registered_by_id,
        invoice_number=job.invoice_number,
        client_name=job.client_name,
        phone_number=job.phone_number,
        created_at=job.created_at,
        completed_at=datetime.utcnow(),
        called_at=datetime.utcnow(),
        delivered_at=datetime.utcnow(),
        qr_code=job.qr_code,
        tags=job.tags
    )

def create_delivered_job_from_completed(completed_job):
    """Crea un trabajo entregado a partir de un trabajo completado"""
    return DeliveredJob(
        original_job_id=completed_job.original_job_id,
        completed_job_id=completed_job.id,
        description=completed_job.description,
        designer_id=completed_job.designer_id,
        registered_by_id=completed_job.registered_by_id,
        invoice_number=completed_job.invoice_number,
        client_name=completed_job.client_name,
        phone_number=completed_job.phone_number,
        created_at=completed_job.created_at,
        completed_at=completed_job.completed_at,
        called_at=completed_job.called_at if completed_job.called_at else datetime.utcnow(),
        delivered_at=datetime.utcnow(),
        qr_code=completed_job.qr_code,
        tags=completed_job.tags
    )

def create_delivered_job_from_pending(pending_job):
    """Crea un trabajo entregado a partir de un trabajo pendiente"""
    return DeliveredJob(
        original_job_id=pending_job.id,
        description=pending_job.description,
        designer_id=pending_job.designer_id,
        registered_by_id=pending_job.registered_by_id,
        invoice_number=pending_job.invoice_number,
        client_name=pending_job.client_name,
        phone_number=pending_job.phone_number,
        created_at=pending_job.created_at,
        completed_at=datetime.utcnow(),
        called_at=datetime.utcnow(),
        delivered_at=datetime.utcnow(),
        qr_code=pending_job.qr_code,
        tags=pending_job.tags
    )

def get_job_photos(job_id):
    """Obtiene los mensajes con fotos para un trabajo específico"""
    return Message.query.filter(
        Message.content.like(f'%trabajo #{job_id}%'),
        Message.photos.isnot(None)
    ).order_by(Message.created_at.desc()).all()

@bp.context_processor
def utility_processor():
    def get_pending_jobs_count():
        if current_user.is_authenticated and current_user.is_staff:
            return PendingJob.query.filter_by(pending_type='new_job').count()
        return 0

    def get_pending_photos_count():
        if current_user.is_authenticated and current_user.is_staff:
            return PendingJob.query.filter_by(pending_type='photo_verification').count()
        return 0

    return dict(
        get_job_photos=get_job_photos,
        pending_jobs_count=get_pending_jobs_count(),
        pending_photos_count=get_pending_photos_count()
    )

@bp.route('/jobs/pending')
@login_required
@staff_required
def pending_jobs():
    """Ver trabajos pendientes"""
    try:
        jobs = PendingJob.query.order_by(PendingJob.created_at.desc()).all()
        return render_template('pending_jobs.html', jobs=jobs)
    except Exception as e:
        flash(f'Error al cargar trabajos pendientes: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/jobs/<int:job_id>/approve', methods=['GET', 'POST'])
@login_required
@staff_required
def approve_job(job_id):
    """Vista para aprobarun trabajo pendiente"""
    try:
        job = PendingJob.query.get_or_404(job_id)

        if request.method == 'POST':
            try:
                # Procesar el formulario de aprobación
                approved_job = Job(
                    description=request.form.get('description'),
                    designer_id=request.form.get('designer_id'),
                    registered_by_id=current_user.id,
                    invoice_number=request.form.get('invoice_number'),
                    client_name=request.form.get('client_name'),
                    phone_number=request.form.get('phone_number'),
                    total_amount=float(request.form.get('total_amount', 0)),
                    deposit_amount=float(request.form.get('deposit_amount', 0)),
                    tags=request.form.get('tags')
                )

                # Generar código QR
                approved_job.generate_qr_code()

                db.session.add(approved_job)
                db.session.delete(job)  # Eliminar el trabajo pendiente
                db.session.commit()

                flash('Trabajo aprobado exitosamente', 'success')
                return redirect(url_for('main.show_job_qr', job_id=approved_job.id))

            except Exception as e:
                db.session.rollback()
                flash(f'Error al aprobar el trabajo: {str(e)}', 'error')
                return redirect(url_for('main.dashboard'))

        # GET: Mostrar formulario de aprobación
        designers = User.query.filter_by(is_designer=True).all()
        return render_template('approve_job.html', job=job, designers=designers)

    except Exception as e:
        flash(f'Error al cargar el trabajo: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/api/complete_job', methods=['POST'])
@login_required
def api_complete_job():
    """API endpoint para completar un trabajo"""
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        auth_password = data.get('auth_password')

        if not job_id or not auth_password:
            return jsonify({'success': False, 'message': 'Faltan datos requeridos'})

        job = Job.query.get_or_404(job_id)

        # Verificar si el usuario tiene permiso
        if not current_user.is_staff and job.designer_id != current_user.id:
            return jsonify({'success': False, 'message': 'No tienes permiso para completar este trabajo'})

        # Verificar contraseña de administrador
        valid_admin = False
        admins = User.query.filter_by(is_admin=True).all()
        for admin in admins:
            if admin.check_password(auth_password):
                valid_admin = True
                break

        if not valid_admin:
            return jsonify({'success': False, 'message': 'Contraseña de administrador incorrecta'})

        # Crear trabajo completado
        completed_job = CompletedJob(
            original_job_id=job.id,
            description=job.description,
            designer_id=job.designer_id,
            registered_by_id=job.registered_by_id,
            invoice_number=job.invoice_number,
            client_name=job.client_name,
            phone_number=job.phone_number,
            created_at=job.created_at,
            completed_at=datetime.utcnow(),
            tags=job.tags
        )

        db.session.add(completed_job)
        db.session.delete(job)
        db.session.commit()

        log_activity(
            'trabajo_completado',
            f"Trabajo completado para {completed_job.client_name} (Factura: {completed_job.invoice_number})"
        )

        return jsonify({'success': True, 'message': 'Trabajo completado exitosamente'})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al completar trabajo: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al procesar la solicitud'})