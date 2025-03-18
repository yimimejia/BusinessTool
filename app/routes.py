from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, Response, send_from_directory, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from functools import wraps
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import or_, desc, literal_column
from app import db
from app.models import User, Job, CompletedJob, ActivityLog, DeliveredJob, PendingJob, Message, Invoice
from app.utils.notifications import send_notification
from flask_sse import sse
from datetime import datetime, timedelta
import secrets
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
from PIL import Image
from apscheduler.schedulers.background import BackgroundScheduler
from weasyprint import HTML
from pdf2image import convert_from_path

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login route"""
    if current_user.is_authenticated:
        logger.debug(f"Usuario ya autenticado: {current_user.username}")
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        logger.debug(f"Intento de login para usuario: {username}")

        if not username or not password:
            flash('Por favor ingrese usuario y contraseña', 'error')
            return redirect(url_for('main.login'))

        try:
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password):
                # Si es diseñador, establecer sesión permanente 
                if not user.is_admin and not user.is_supervisor:
                    user.permanent_session = True
                    session.permanent = True
                login_user(user, remember=user.permanent_session)
                
                # Log successful login
                log_activity('login', f"Usuario {user.username} inició sesión")
                logger.debug(f"Login exitoso para usuario: {username}")
                
                # Get the next page from args
                next_page = request.args.get('next')
                if not next_page or not next_page.startswith('/'):
                    next_page = url_for('main.dashboard')
                
                return redirect(next_page)
            else:
                logger.warning(f"Credenciales incorrectas para usuario: {username}")
                flash('Usuario o contraseña incorrectos', 'error')
                return redirect(url_for('main.login'))

        except Exception as e:
            logger.error(f"Error durante el login: {str(e)}")
            flash('Error al procesar el login', 'error')
            return redirect(url_for('main.login'))

    return render_template('login.html')

@bp.context_processor
def inject_urgent_jobs():
    """Inject urgent jobs into all templates"""
    if not current_user.is_authenticated:
        return {'urgent_jobs': []}
        
    try:
        # Solo mostrar trabajos urgentes a admin y supervisores
        if current_user.is_admin or current_user.is_supervisor:
            # Buscar trabajos con la etiqueta "Urgente"
            urgent_jobs = Job.query.filter(
                Job.tags.ilike('%Urgente%'),
                Job.status == 'pending'
            ).order_by(Job.created_at.desc()).all()
            
            return {'urgent_jobs': urgent_jobs}
        else:
            return {'urgent_jobs': []}
            
    except Exception as e:
        logger.error(f"Error al obtener trabajos urgentes: {str(e)}")
        return {'urgent_jobs': []}

def notify_staff(message, title="Notificación"):
    """Enviar notificación a admin y supervisores"""
    try:
        # Obtener todos los usuarios admin y supervisores
        staff_users = User.query.filter(
            or_(User.is_admin == True, User.is_supervisor == True)
        ).all()

        # Crear mensaje para cada usuario staff
        for user in staff_users:
            new_message = Message(
                user_id=user.id,
                title=title,
                content=message,
                is_read=False
            )
            db.session.add(new_message)
        
        db.session.commit()
        
        # Enviar notificación en tiempo real
        sse.publish({
            "message": message,
            "type": "notification"
        }, type='message')
        
    except Exception as e:
        logger.error(f"Error al enviar notificación: {str(e)}")
        db.session.rollback()

@bp.route('/jobs/pending/new', methods=['GET', 'POST'])
@login_required
def new_pending_job():
    """Crear un nuevo trabajo pendiente"""
    if request.method == 'POST':
        description = request.form.get('description')
        client_name = request.form.get('client_name')
        phone_number = request.form.get('phone_number')
        designer_id = current_user.id

        if not all([description, client_name, phone_number]):
            flash('Por favor complete todos los campos requeridos', 'error')
            return redirect(url_for('main.new_pending_job'))

        try:
            # Formatear número de teléfono
            if not phone_number.startswith('+1'):
                phone_number = f'+1{phone_number}' if phone_number.startswith('1') else f'+1{phone_number}'

            # Crear trabajo pendiente
            pending_job = PendingJob(
                description=description,
                designer_id=designer_id,
                registered_by_id=current_user.id,
                client_name=client_name,
                phone_number=phone_number,
                pending_type='new_job'
            )
            
            db.session.add(pending_job)
            db.session.commit()
            
            # Enviar notificación a admin y supervisores
            notify_staff(
                f"Nuevo trabajo pendiente de aprobación - Cliente: {client_name}",
                "Trabajo Pendiente"
            )
            
            flash('Trabajo pendiente creado exitosamente', 'success')
            return redirect(url_for('main.dashboard'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al crear trabajo pendiente: {str(e)}")
            flash('Error al crear el trabajo pendiente', 'error')
            return redirect(url_for('main.new_pending_job'))

    return render_template('new_pending_job.html')

def staff_required(f):
    """Decorator para requerir que el usuario sea admin o supervisor"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_admin or current_user.is_supervisor):
            flash('No tienes permiso para acceder a esta página', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator para requerir que el usuario sea admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('No tienes permiso para acceder a esta página', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/jobs/<int:job_id>/view-invoice', methods=['GET'])
@login_required
def view_invoice_pdf(job_id):
    """Ver factura en formato tradicional"""
    try:
        job, qr_code_image, total_amount, deposit_amount, remaining_amount = get_job_invoice_data(job_id=job_id)
        if not job:
            flash('Trabajo no encontrado', 'error')
            return redirect(url_for('main.dashboard'))
            
        # Preparar mensaje de WhatsApp
        whatsapp_message = f"""*FOTO VIDEO MOJICA*
¡Saludos estimado(a) {job.client_name}!

Le enviamos su factura:
📋 Número: {job.invoice_number}
💰 Total: RD${float(total_amount):.2f}
💵 Abono: RD${float(deposit_amount):.2f}
🔸 Restante: RD${float(remaining_amount):.2f}

¡Gracias por su preferencia!"""
        
        return render_template(
            'invoice_view.html',
            job=job,
            qr_image=qr_code_image,
            total_amount=total_amount,
            deposit_amount=deposit_amount,
            remaining_amount=remaining_amount,
            whatsapp_message=whatsapp_message
        )
    except Exception as e:
        logger.error(f"Error al mostrar factura: {str(e)}")
        flash('Error al mostrar la factura', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/jobs/<int:job_id>/invoice', methods=['GET'])
@login_required
def view_job_invoice_details(job_id):
    """Ver factura de un trabajo"""
    # Redirigir a la vista principal de factura
    return redirect(url_for('main.view_invoice_pdf', job_id=job_id))

@bp.route('/jobs/<int:job_id>/send-whatsapp-invoice', methods=['GET'])
@login_required 
def send_whatsapp_invoice(job_id):
    """Enviar factura por WhatsApp"""
    try:
        # Obtener el trabajo completado
        job = CompletedJob.query.get_or_404(job_id)
        
        if not job.phone_number:
            flash('No hay número de teléfono registrado para este cliente', 'error')
            return redirect(url_for('main.completed_jobs'))

        # Limpiar número de teléfono - remover todos los caracteres no numéricos
        clean_phone = re.sub(r'[^\d]', '', job.phone_number)
        if not clean_phone.startswith('1'):
            clean_phone = '1' + clean_phone
        
        # Generar el PDF de la factura
        job, qr_code_image, total_amount, deposit_amount, remaining_amount = get_job_invoice_data(job_id)
        if not job:
            flash('Error al generar la factura', 'error')
            return redirect(url_for('main.completed_jobs'))

        # Preparar mensaje de WhatsApp
        whatsapp_message = f"""*FOTO VIDEO MOJICA*
¡Saludos estimado(a) {job.client_name}!

Le enviamos su factura:
📋 Número: {job.invoice_number}
💰 Total: RD${float(total_amount):.2f}
💵 Abono: RD${float(deposit_amount):.2f}
🔸 Restante: RD${float(remaining_amount):.2f}

¡Gracias por su preferencia!"""
        
        # Crear enlace de WhatsApp usando wa.me
        whatsapp_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(whatsapp_message)}"

        log_activity(
            'enviar_whatsapp_factura',
            f"Factura enviada por WhatsApp a {job.client_name} (Factura: {job.invoice_number})"
        )

        return redirect(whatsapp_url)

    except Exception as e:
        logger.error(f"Error al enviar factura por WhatsApp: {str(e)}")
        flash('Error al procesar la solicitud', 'error')
        return redirect(url_for('main.completed_jobs'))

def get_job_invoice_data(job_id=None, qr_code=None):
    """Función interna para obtener datos de factura"""
    try:
        # Primero buscar el trabajo
        job = None
        
        if job_id:
            logger.info(f"Buscando trabajo por ID: {job_id}")
            # Buscar en trabajos activos primero
            job = Job.query.get(job_id)
            if not job:
                logger.info(f"No se encontró en trabajos activos, buscando en completados: {job_id}")
                job = CompletedJob.query.get(job_id)
                
        elif qr_code:
            logger.info(f"Buscando trabajo por código QR: {qr_code}")
            try:
                # El QR ahora contendrá la URL completa, extraer el ID del trabajo
                if '/jobs/' in qr_code:
                    job_id = int(qr_code.split('/jobs/')[-1].split('/')[0])
                    logger.info(f"ID extraído de URL: {job_id}")
                    
                    # Buscar primero en trabajos activos
                    job = Job.query.get(job_id)
                    if not job:
                        logger.info(f"Buscando en trabajos completados: {job_id}")
                        job = CompletedJob.query.get(job_id)
                else:
                    logger.warning(f"Formato de URL inválido: {qr_code}")
                    return None, None, 0, 0, 0
                    
            except Exception as e:
                logger.error(f"Error procesando URL del QR: {str(e)}")
                return None, None, 0, 0, 0

        if not job:
            logger.warning("No se encontró el trabajo")
            return None, None, 0, 0, 0

        logger.info(f"Trabajo encontrado: ID={job.id}, Cliente={job.client_name}")

        # Generar URL para el QR
        job_url = url_for('main.view_invoice_pdf', job_id=job.id, _external=True)
        logger.info(f"URL generada para QR: {job_url}")

        # Generar QR code con la URL
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=5
        )

        qr.add_data(job_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Convert QR to base64
        buffered = io.BytesIO()
        qr_img.save(buffered, format="PNG")
        qr_code_image = base64.b64encode(buffered.getvalue()).decode()

        # Buscar o crear factura
        invoice = Invoice.query.filter_by(
            job_id=job.id,
            job_type='completed_job' if isinstance(job, CompletedJob) else 'job'
        ).first()

        if not invoice:
            logger.info(f"Creando nueva factura para trabajo {job.id}")
            invoice = Invoice(
                job_id=job.id,
                job_type='completed_job' if isinstance(job, CompletedJob) else 'job',
                invoice_number=job.invoice_number,
                total_amount=float(job.total_amount or 0),
                deposit_amount=float(getattr(job, 'deposit_amount', 0) or 0),
                created_at=job.created_at
            )
            
            try:
                db.session.add(invoice)
                db.session.commit()
                logger.info("Nueva factura creada exitosamente")
            except Exception as e:
                logger.error(f"Error al crear factura: {str(e)}")
                db.session.rollback()
                invoice = Invoice.query.filter_by(invoice_number=job.invoice_number).first()
                if not invoice:
                    return None, None, 0, 0, 0

        logger.info(f"QR generado exitosamente para factura {invoice.invoice_number}")
        return job, qr_code_image, float(invoice.total_amount), float(invoice.deposit_amount), float(invoice.remaining_amount)

    except Exception as e:
        logger.error(f"Error en get_job_invoice_data: {str(e)}")
        return None, None, 0, 0, 0

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

                # Guardar la imagen original
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
            message=request.form.get('message', ''),
            total_amount=float(job.total_amount or 0),
            deposit_amount=float(job.deposit_amount or 0)
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

@bp.route('/jobs/<int:job_id>/send-whatsapp-photos', methods=['GET'])
@login_required
def send_whatsapp_photos(job_id):
    """Enviar mensaje de WhatsApp para fotos"""
    try:
        job = CompletedJob.query.get_or_404(job_id)
        
        if not job.phone_number:
            flash('No hay número de teléfono registrado para este cliente', 'error')
            return redirect(url_for('main.completed_jobs'))

        # Limpiar número de teléfono y asegurar formato internacional
        clean_phone = re.sub(r'[^\d+]', '', job.phone_number)
        # Si no tiene código de país, agregar +1 (República Dominicana)
        if not clean_phone.startswith('+'):
            if clean_phone.startswith('1'):
                clean_phone = '+' + clean_phone
            else:
                clean_phone = '+1' + clean_phone
        # Eliminar el + para la URL de WhatsApp
        whatsapp_phone = clean_phone.replace('+', '')
        
        # Mensaje básico
        message = f"""*FOTO VIDEO MOJICA*
¡Hola {job.client_name}!

Sus fotos están listas para ser revisadas.
Factura: {job.invoice_number}

¡Gracias por su preferencia!"""

        # Crear enlace de WhatsApp con mensaje codificado correctamente
        whatsapp_url = f"https://api.whatsapp.com/send?phone={whatsapp_phone}&text={urllib.parse.quote(message)}"
        
        log_activity(
            'enviar_whatsapp',
            f"Mensaje WhatsApp enviado a {job.client_name} (Factura: {job.invoice_number})"
        )

        return redirect(whatsapp_url)

    except Exception as e:
        logger.error(f"Error al enviar WhatsApp: {str(e)}")
        flash('Error al procesar la solicitud', 'error')
        return redirect(url_for('main.completed_jobs'))

def cleanup_temp_files(*file_paths):
    """Eliminar archivos temporales"""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Error eliminando archivo temporal {file_path}: {str(e)}")

@bp.route('/jobs/<int:job_id>/approve', methods=['GET'])
@login_required
@staff_required
def approve_job_form(job_id):
    """Mostrar formulario de aprobación de trabajo"""
    try:
        job = PendingJob.query.get_or_404(job_id)
        
        if job.pending_type != 'new_job':
            flash('Tipo de trabajo pendiente incorrecto', 'error')
            return redirect(url_for('main.pending_verification'))
            
        return render_template('approve_job.html', job=job)
    except Exception as e:
        logger.error(f"Error al mostrar formulario de aprobación: {str(e)}")
        flash('Error al cargar el formulario', 'error')
        return redirect(url_for('main.pending_verification'))

@bp.route('/jobs/<int:job_id>/process-pending', methods=['POST'])
@login_required
def process_pending_job(job_id):
    """Procesar trabajo pendiente"""
    try:
        # Obtener el trabajo pendiente
        pending_job = PendingJob.query.get_or_404(job_id)
        
        if pending_job.pending_type != 'new_job':
            flash('Tipo de trabajo pendiente incorrecto', 'error')
            return redirect(url_for('main.pending_verification'))

        # Crear el trabajo activo
        active_job = Job(
            description=pending_job.description,
            designer_id=pending_job.designer_id,
            registered_by_id=current_user.id,
            invoice_number=request.form.get('invoice_number'),
            client_name=pending_job.client_name,
            phone_number=pending_job.phone_number,
            total_amount=request.form.get('total_amount'),
            deposit_amount=request.form.get('deposit_amount'),
            tags=request.form.get('tags'),
            created_at=pending_job.created_at,
            status='pending'
        )

        # Generar QR code con el formato FVM-{id}
        db.session.add(active_job)
        db.session.flush()  # Para obtener el ID
        active_job.generate_qr_code()
        
        # Crear factura
        invoice = Invoice(
            job_id=active_job.id,
            job_type='job',
            invoice_number=request.form.get('invoice_number'),
            total_amount=request.form.get('total_amount'),
            deposit_amount=request.form.get('deposit_amount'),
            created_at=pending_job.created_at,
            issued_at=datetime.utcnow()
        )
        
        db.session.add(invoice)
        db.session.delete(pending_job)
        db.session.commit()

        logger.info(f"Trabajo creado con QR: {active_job.qr_code}")
        
        flash('Trabajo aprobado exitosamente', 'success')
        return redirect(url_for('main.pending_jobs'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al procesar trabajo pendiente: {str(e)}")
        flash('Error al procesar la solicitud. Por favor, inténtelo de nuevo.', 'error')
        return redirect(url_for('main.pending_verification'))

@bp.route('/jobs/<int:job_id>/reject-photos', methods=['POST'])
@login_required
@staff_required
def reject_pending_photos(job_id):
    """Rechazar fotos de un trabajo pendiente"""
    try:
        pending_job = PendingJob.query.get_or_404(job_id)
        
        if pending_job.pending_type != 'photo_verification':
            flash('Tipo de trabajo pendiente incorrecto', 'error')
            return redirect(url_for('main.jobs_pending_photos'))

        # Borrar fotos del sistema de archivos
        if pending_job.photos:
            photos = json.loads(pending_job.photos)
            for photo in photos:
                try:
                    photo_path = os.path.join(current_app.static_folder, photo)
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                except Exception as e:
                    logger.error(f"Error borrando foto {photo}: {str(e)}")

        # Registrar el rechazo
        log_activity(
            'rechazar_fotos',
            f"Fotos rechazadas - Trabajo #{pending_job.original_job_id}, Cliente: {pending_job.client_name}"
        )

        # Eliminar el trabajo pendiente
        db.session.delete(pending_job)
        db.session.commit()

        flash('Fotos rechazadas exitosamente', 'success')
        return redirect(url_for('main.jobs_pending_photos'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al rechazar fotos: {str(e)}")
        flash('Error al procesar la solicitud', 'error')
        return redirect(url_for('main.jobs_pending_photos'))
        
        # Crear enlace para ver las fotos
        photos_url = url_for('main.view_approved_photos', 
                        token=token, 
                        _external=True)

        # Preparar mensaje de WhatsApp
        clean_phone = re.sub(r'[^\d+]', '', job.phone_number)
        if not clean_phone.startswith('+'):
            if clean_phone.startswith('1'):
                clean_phone = '+' + clean_phone
            else:
                clean_phone = '+1' + clean_phone
        whatsapp_phone = clean_phone.replace('+', '')
        
        whatsapp_message = f"""*FOTO VIDEO MOJICA*
¡Sus fotos están listas!

Cliente: {job.client_name}
Factura: {job.invoice_number}

Para ver y descargar sus fotos, use este enlace (válido por 48 horas):
{photos_url}

¡Gracias por su preferencia!"""

        # Eliminar el trabajo pendiente después de preparar todo
        db.session.delete(pending_job)
        db.session.commit()

        log_activity(
            'fotos_aprobadas',
            f"Fotos aprobadas y enlace enviado - Trabajo #{job.id}, Cliente: {job.client_name}"
        )

        # Redirigir a WhatsApp con el mensaje
        whatsapp_url = f"https://wa.me/{whatsapp_phone}?text={urllib.parse.quote(whatsapp_message)}"
        return redirect(whatsapp_url)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al aprobar fotos: {str(e)}")
        flash('Error al procesar la solicitud. Por favor, inténtelo de nuevo.', 'error')
        return redirect(url_for('main.jobs_pending_photos'))

def save_photos_to_job_folder(job_id, photos):
    """Guardar fotos en la carpeta del trabajo específico"""
    try:
        # Crear directorio para las fotos del trabajo si no existe
        upload_folder = os.path.join(current_app.static_folder, 'uploads', str(job_id))
        os.makedirs(upload_folder, exist_ok=True)

        photo_paths = []
        for photo in photos:
            if photo and photo.filename:
                # Generar nombre único para la foto
                filename = secure_filename(photo.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp}_{filename}"
                
                # Guardar la foto
                photo_path = os.path.join('uploads', str(job_id), unique_filename)
                full_path = os.path.join(current_app.static_folder, photo_path)
                photo.save(full_path)
                
                # Añadir la ruta relativa a la lista
                photo_paths.append(photo_path)

        return photo_paths
    except Exception as e:
        logger.error(f"Error al guardar fotos: {str(e)}")
        raise

@bp.route('/photos/view/<token>')
def view_approved_photos(token):
    """Vista pública para ver fotos aprobadas con token temporal"""
    try:
        # Buscar el trabajo completado por token
        job = CompletedJob.query.filter_by(temp_token=token).first()
        
        if not job or not job.temp_token or job.temp_token != token:
            logger.error(f"Token no encontrado o inválido: {token}")
            return render_template('photos_gallery.html', photos=[], expired=True)
            
        # Verificar expiración
        now = datetime.utcnow()
        if not job.token_expiry:
            logger.error(f"Fecha de expiración no encontrada para trabajo {job.id}")
            return render_template('photos_gallery.html', photos=[], expired=True)
            
        if now > job.token_expiry:
            logger.error(f"Token expirado para trabajo {job.id}. Expira: {job.token_expiry}, Ahora: {now}")
            return render_template('photos_gallery.html', photos=[], expired=True)
            
        # Verificar y cargar las fotos
        photos = []
        if job.photos:
            try:
                saved_photos = json.loads(job.photos)
                for photo_path in saved_photos:
                    full_path = os.path.join(current_app.static_folder, photo_path)
                    if os.path.exists(full_path):
                        photos.append(photo_path)
                    else:
                        logger.warning(f"Foto no encontrada: {full_path}")
            except json.JSONDecodeError:
                logger.error(f"Error decodificando JSON de fotos para trabajo {job.id}")
                photos = []

        logger.info(f"Mostrando {len(photos)} fotos para trabajo {job.id}, expira en: {job.token_expiry}")
        return render_template('photos_gallery.html', 
                           photos=photos,
                           expired=False,
                           job=job)

    except Exception as e:
        logger.error(f"Error al mostrar fotos aprobadas: {str(e)}")
        return render_template('photos_gallery.html', 
                           photos=[],
                           expired=True, 
                           error="Error al cargar las fotos")

@bp.route('/jobs/<int:job_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_job(job_id):
    """Eliminar un trabajo"""
    try:
        # Buscar el trabajo en las tablas Job y CompletedJob
        job = Job.query.get(job_id)
        if not job:
            job = CompletedJob.query.get(job_id)
        
        if not job:
            return jsonify({'success': False, 'message': 'Trabajo no encontrado'}), 404
        
        # Registrar actividad antes de eliminar
        log_activity(
            'eliminar_trabajo',
            f"Trabajo eliminado - Cliente: {job.client_name}, Factura: {job.invoice_number}"
        )

        # Eliminar fotos asociadas si existen
        if hasattr(job, 'photos') and job.photos:
            photos = json.loads(job.photos) if isinstance(job.photos, str) else job.photos
            for photo_path in photos:
                try:
                    full_path = os.path.join(current_app.static_folder, photo_path)
                    if os.path.exists(full_path):
                        os.remove(full_path)
                except Exception as e:
                    logger.error(f"Error eliminando foto {photo_path}: {str(e)}")

        # Eliminar el trabajo
        db.session.delete(job)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Trabajo eliminado exitosamente'})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al eliminar trabajo: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al eliminar el trabajo'}), 500

@bp.route('/search', methods=['GET'])
@login_required
def search_jobs():
    """Búsqueda de trabajos""" 
    query = request.args.get('query', '').strip()
    results = []
    
    if query:
        try:
            # Buscar en trabajos activos
            active_jobs = Job.query.filter(
                or_(
                    Job.client_name.ilike(f'%{query}%'),
                    Job.invoice_number.ilike(f'%{query}%'), 
                    Job.phone_number.ilike(f'%{query}%')
                )
            ).all()
            
            # Buscar en trabajos completados
            completed_jobs = CompletedJob.query.filter(
                or_(
                    CompletedJob.client_name.ilike(f'%{query}%'),
                    CompletedJob.invoice_number.ilike(f'%{query}%'),
                    CompletedJob.phone_number.ilike(f'%{query}%')
                )
            ).all()
            
            # Combinar y procesar resultados
            for job in active_jobs + completed_jobs:
                results.append({
                    'id': job.id,
                    'invoice_number': job.invoice_number,
                    'client_name': job.client_name,
                    'phone_number': job.phone_number,
                    'total_amount': float(job.total_amount or 0),
                    'deposit_amount': float(job.deposit_amount or 0),
                    'created_at': job.created_at,
                    'status': 'Completado' if isinstance(job, CompletedJob) else 'Pendiente'
                })
                
        except Exception as e:
            logger.error(f"Error en búsqueda: {str(e)}")
            flash('Error al realizar la búsqueda', 'error')
            results = []
    
    # Renderizar template con resultados
    return render_template('search_invoices.html', results=results, query=query)


@bp.route('/jobs/<int:job_id>/approve-with-pin', methods=['POST'])
@login_required
def approve_job_with_pin(job_id):
    """Aprobar trabajo usando PIN predeterminado"""
    try:
        pin = request.form.get('pin')
        
        # Verificar PIN
        if pin != '0372':
            flash('PIN incorrecto', 'error')
            return redirect(url_for('main.pending_verification'))

        pending_job = PendingJob.query.get_or_404(job_id)
        
        if pending_job.pending_type != 'new_job':
            flash('Tipo de trabajo pendiente incorrecto', 'error')
            return redirect(url_for('main.pending_verification'))

        # Verificar campos requeridos
        required_fields = [
            ('invoice_number', 'número de factura'),
            ('client_name', 'nombre del cliente'),
            ('description', 'descripción'),
            ('designer_id', 'diseñador')
        ]
        
        for field, name in required_fields:
            if not getattr(pending_job, field):
                flash(f'Error: Falta el {name}', 'error')
                return redirect(url_for('main.pending_verification'))

        try:
            # Iniciar transacción explícita
            db.session.begin_nested()

            # Crear el trabajo activo
            active_job = Job(
                description=pending_job.description,
                designer_id=pending_job.designer_id,
                registered_by_id=current_user.id,
                invoice_number=pending_job.invoice_number,
                client_name=pending_job.client_name,
                phone_number=pending_job.phone_number,
                total_amount=float(pending_job.total_amount or 0),
                deposit_amount=float(pending_job.deposit_amount or 0),
                created_at=pending_job.created_at,
                status='pending'
            )

            # Generar QR code
            active_job.generate_qr_code()
            db.session.add(active_job)
            db.session.flush()

            # Crear factura
            invoice = Invoice(
                job_id=active_job.id,
                job_type='job',
                invoice_number=pending_job.invoice_number,
                total_amount=float(pending_job.total_amount or 0),
                deposit_amount=float(pending_job.deposit_amount or 0),
                created_at=pending_job.created_at,
                issued_at=datetime.utcnow()
            )

            db.session.add(invoice)
            db.session.delete(pending_job)
            db.session.commit()

            log_activity(
                'aprobar_trabajo_pin',
                f"Trabajo aprobado: {active_job.client_name} - {active_job.invoice_number}"
            )

            flash('Trabajo aprobado exitosamente', 'success')
            # Redireccionar directamente a la vista de factura
            return redirect(url_for('main.view_job_invoice', job_id=active_job.id))

        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error de base de datos al aprobar trabajo: {str(e)}")
            flash('Error al procesar el trabajo. Por favor, inténtelo de nuevo.', 'error')
            return redirect(url_for('main.pending_verification'))

    except Exception as e:
        logger.error(f"Error al aprobar trabajo con PIN: {str(e)}")
        flash('Error al procesar la solicitud', 'error')
        return redirect(url_for('main.pending_verification'))

@bp.route('/messages/<int:message_id>/approve-photos', methods=['POST'])
@login_required
@staff_required
def approve_photos_for_job(message_id):
    """Aprobar y enviar fotos por WhatsApp"""
    try:
        # Obtener el trabajo pendiente
        pending_job = PendingJob.query.get_or_404(message_id)
        
        if pending_job.pending_type != 'photo_verification':
            flash('Tipo de trabajo pendiente incorrecto', 'error')
            return redirect(url_for('main.jobs_pending_photos'))
            
        # Obtener el trabajo original
        job = CompletedJob.query.get_or_404(pending_job.original_job_id)

        # Generar token único para el enlace temporal
        token = secrets.token_urlsafe(32)
        expiry_date = datetime.utcnow() + timedelta(days=2)
        
        # Asegurarse de que las fotos sean un JSON válido
        try:
            photos = json.loads(pending_job.photos) if pending_job.photos else []
            # Verificar que las fotos existen físicamente
            verified_photos = []
            for photo_path in photos:
                full_path = os.path.join(current_app.static_folder, photo_path)
                if os.path.exists(full_path):
                    verified_photos.append(photo_path)
                else:
                    logger.warning(f"Foto no encontrada: {full_path}")
            
            # Actualizar el trabajo completado con las fotos verificadas
            job.photos = json.dumps(verified_photos)
            job.temp_token = token
            job.token_expiry = expiry_date
            
            logger.info(f"Configurando trabajo {job.id} con {len(verified_photos)} fotos verificadas")
            logger.info(f"Token: {token}")
            logger.info(f"Expira en: {expiry_date}")
            
            db.session.commit()
            logger.info(f"Token y fotos guardados correctamente para trabajo {job.id}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Error decodificando JSON de fotos: {str(e)}")
            flash('Error al procesar las fotos', 'error')
            return redirect(url_for('main.jobs_pending_photos'))
        
        # Crear enlace para ver las fotos
        photos_url = url_for('main.view_approved_photos', 
                        token=token, 
                        _external=True)

        # Preparar mensaje de WhatsApp
        clean_phone = re.sub(r'[^\d+]', '', job.phone_number)
        if not clean_phone.startswith('+'):
            if clean_phone.startswith('1'):
                clean_phone = '+' + clean_phone
            else:
                clean_phone = '+1' + clean_phone
        whatsapp_phone = clean_phone.replace('+', '')
        
        whatsapp_message = f"""*FOTO VIDEO MOJICA*
¡Sus fotos están listas!

Cliente: {job.client_name}
Factura: {job.invoice_number}

Para ver y descargar sus fotos, use este enlace (válido por 48 horas):
{photos_url}

¡Gracias por su preferencia!"""

        # Eliminar el trabajo pendiente después de preparar todo
        db.session.delete(pending_job)
        db.session.commit()

        log_activity(
            'fotos_aprobadas',
            f"Fotos aprobadas y enlace enviado - Trabajo #{job.id}, Cliente: {job.client_name}"
        )

        # Redirigir a WhatsApp con el mensaje
        whatsapp_url = f"https://wa.me/{whatsapp_phone}?text={urllib.parse.quote(whatsapp_message)}"
        return redirect(whatsapp_url)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al aprobar fotos: {str(e)}")
        flash('Error al procesar la solicitud. Por favor, inténtelo de nuevo.', 'error')
        return redirect(url_for('main.jobs_pending_photos'))

@bp.route('/stream')
def stream():
    return Response(sse.stream(), mimetype='text/event-stream')


@bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('main.login'))



# Nuevas rutas para mensajería

@bp.route('/messages')
@login_required
def messages():
    """Ver mensajes"""
    messages = current_user.get_messages()
    users = User.query.filter(User.id != current_user.id).all()
    return render_template('messages.html', messages=messages, users=users)

@bp.route('/messages/send', methods=['POST'])
@login_required
def send_message():
    """Enviar un mensaje a uno o todos los diseñadores"""
    send_to_all = request.form.get('send_to_all') == 'true'
    recipient_id = request.form.get('recipient_id')
    content = request.form.get('content')

    if not content:
        flash('Por favor escriba un mensaje', 'error')
        return redirect(url_for('main.messages'))

    if send_to_all:
        # Enviar a todos los diseñadores
        designers = User.query.filter_by(is_designer=True).all()
        for designer in designers:
            message = Message(
                sender_id=current_user.id,
                recipient_id=designer.id,
                content=content
            )
            db.session.add(message)
            send_notification(designer.id, "Nuevo mensaje", content)
            
        log_activity('enviar_mensaje', "Mensaje enviado a todos los diseñadores")
    else:
        if not recipient_id:
            flash('Por favor seleccione un destinatario', 'error')
            return redirect(url_for('main.messages'))

        recipient = User.query.get(recipient_id)
        message = Message(
            sender_id=current_user.id,
            recipient_id=recipient_id,
            content=content
        )
        db.session.add(message)
        send_notification(recipient_id, "Nuevo mensaje", content)
        log_activity('enviar_mensaje', f"Mensaje enviado a {recipient.username}")

    db.session.commit()
    flash('Mensaje enviado exitosamente', 'success')
    return redirect(url_for('main.messages'))

@bp.route('/api/messages/mark_as_read/<int:user_id>', methods=['POST'])
@login_required
def mark_messages_as_read(user_id):
    """Marcar todos los mensajes de un usuario como leídos"""
    try:
        messages = Message.query.filter_by(
            recipient_id=current_user.id,
            sender_id=user_id,
            is_read=False
        ).all()
        
        for message in messages:
            message.is_read = True
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/messages/unread')
@login_required
def unread_messages_count():
    """Obtener el número de mensajes no leídos"""
    count = current_user.get_unread_messages_count()
    return jsonify({'count': count})

@bp.route('/jobs/pending/photos')
@login_required
@staff_required  # Ya modificado para incluir supervisores
def jobs_pending_photos():
    """Ver trabajos pendientes de aprobación de fotos"""
    try:
        # Obtener todos los trabajos pendientes de tipo photo_verification
        jobs = PendingJob.query.filter_by(pending_type='photo_verification').order_by(PendingJob.created_at.desc()).all()
        
        # Log para debugging
        logger.info(f"Obtenidos {len(jobs)} trabajos pendientes de aprobación de fotos")
        logger.info(f"Usuario actual: {current_user.username}, Es admin: {current_user.is_admin}, Es supervisor: {current_user.is_supervisor}")
        
        return render_template('pending_photos.html', jobs=jobs)
    except Exception as e:
        logger.error(f"Error al obtener trabajos pendientes de fotos: {str(e)}")
        flash('Error al cargar los trabajos pendientes', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/search/invoices')
@login_required
def search_invoices():
    """Búsqueda de facturas"""
    try:
        query = request.args.get('query', '')
        logger.info(f"Iniciando búsqueda de facturas con query: '{query}'")
        
        if not query:
            return render_template('search_invoices.html', results=[], query=None)

        # Buscar primero en la tabla de facturas
        invoices = Invoice.query.filter(
            Invoice.invoice_number.ilike(f'%{query}%')
        ).order_by(Invoice.created_at.desc()).all()

        logger.info(f"Encontradas {len(invoices)} facturas")
        
        results = []
        for invoice in invoices:
            try:
                # Obtener el trabajo relacionado
                work = invoice.get_job()
                if work:
                    # Calcular montos
                    total = float(invoice.total_amount or 0)
                    deposit = float(invoice.deposit_amount or 0)
                    remaining = total - deposit
                    
                    result = {
                        'id': work.id,  # ID del trabajo para el enlace de la factura
                        'invoice_number': invoice.invoice_number,
                        'client_name': work.client_name,
                        'description': work.description if hasattr(work, 'description') else '',
                        'created_at': invoice.created_at,
                        'total_amount': total,
                        'deposit_amount': deposit,
                        'remaining_amount': remaining,
                        'status': 'Completado' if isinstance(work, CompletedJob) else 'Pendiente'
                    }
                    results.append(result)
                    logger.info(f"Procesada factura {invoice.invoice_number} para cliente {work.client_name}")
            except Exception as e:
                logger.error(f"Error procesando factura {invoice.id}: {str(e)}")
                continue

        logger.info(f"Total de resultados procesados: {len(results)}")
        return render_template('search_invoices.html', results=results, query=query)

    except Exception as e:
        logger.error(f"Error en búsqueda de facturas: {str(e)}")
        flash('Error al realizar la búsqueda', 'error')
        return render_template('search_invoices.html', results=[], query=query, error=True)

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
    invoice_url = url_for('main.generate_invoice_view', job_id=job.id, _external=True)

    # Obtener enlace de WhatsApp con la factura
    whatsapp_link = job.get_whatsapp_link(with_invoice=True, invoice_url=invoice_url)

    # Registrar actividad
    log_activity(
        'enviar_whatsapp',
        f"Mensaje WhatsApp enviado a {job.client_name} (Factura: {job.invoice_number})"
    )

    return redirect(whatsapp_link)


@bp.route('/jobs/<int:job_id>/invoice')
@login_required
def view_job_invoice(job_id):
    """Ver factura de un trabajo"""
    try:
        job, qr_code_image, total_amount, deposit_amount, remaining_amount = get_job_invoice_data(job_id=job_id)
        if not job:
            flash('Factura no encontrada', 'error')
            return redirect(url_for('main.dashboard'))

        logger.info(f"Renderizando factura - Total: {total_amount}, Abono: {deposit_amount}, Restante: {remaining_amount}")

        return render_template('invoice_pdf.html',
                           job=job,
                           qr_code=qr_code_image,
                           total_amount=total_amount,
                           deposit_amount=deposit_amount,
                           remaining_amount=remaining_amount)
    except Exception as e:
        logger.error(f"Error mostrando factura: {str(e)}")
        flash('Error al mostrar la factura', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/jobs/view/<int:job_id>')
@login_required
def view_job_details(job_id):
    """Ver detalles del trabajo sin generar factura"""
    try:
        job = Job.query.get(job_id)
        if not job:
            job = CompletedJob.query.get(job_id)
        if not job:
            job = PendingJob.query.get_or_404(job_id)
            
        return render_template('job_details.html', job=job)
    except Exception as e:
        logger.error(f"Error mostrando detalles del trabajo: {str(e)}")
        flash('Error al mostrar los detalles del trabajo', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/jobs/public/<string:qr_code>')
def view_public_invoice(qr_code):
    """Vista pública de factura accesible por QR"""
    try:
        job, qr_code_image, total_amount, deposit_amount, remaining_amount = get_job_invoice_data(qr_code=qr_code)
        if not job:
            return "Factura no encontrada", 404

        return render_template('invoice_pdf.html',
                           job=job,
                           qr_code=qr_code_image,
                           total_amount=total_amount,
                           deposit_amount=deposit_amount,
                           remaining_amount=remaining_amount)
    except Exception as e:
        logger.error(f"Error mostrando factura pública: {str(e)}")
        return "Error al mostrar la factura", 500

@bp.route('/jobs/pending/verification')
@login_required
@staff_required  # Ya modificado para incluir supervisores
def pending_verification():
    """Ver trabajos pendientes de verificación"""
    try:
        jobs = PendingJob.query.filter_by(pending_type='new_job').order_by(PendingJob.created_at.desc()).all()
        return render_template('pending_verification.html', jobs=jobs)
    except Exception as e:
        logger.error(f"Error al obtener trabajos pendientes: {str(e)}")
        flash('Error al cargar los trabajos pendientes', 'error')
        return redirect(url_for('main.dashboard'))



@bp.route('/search')
@login_required
def search():
    """Buscar facturas por nombre de cliente o número de factura"""
    query = request.args.get('query', '').strip()
    if query:
        # Buscar en trabajos activos, completados y pendientes
        active_jobs = Job.query.filter(
            or_(
                Job.client_name.ilike(f'%{query}%'),
                Job.invoice_number.ilike(f'%{query}%')
            )
        ).all()

        completed_jobs = CompletedJob.query.filter(
            or_(
                CompletedJob.client_name.ilike(f'%{query}%'),
                CompletedJob.invoice_number.ilike(f'%{query}%')
            )
        ).all()

        pending_jobs = PendingJob.query.filter(
            or_(
                PendingJob.client_name.ilike(f'%{query}%'),
                PendingJob.invoice_number.ilike(f'%{query}%')
            )
        ).all()

        # Combinar y ordenar todos los trabajos por fecha
        all_jobs = active_jobs + completed_jobs + pending_jobs
        jobs = sorted(all_jobs, key=lambda x: x.created_at, reverse=True)
    else:
        jobs = []

    return render_template('search_invoices.html', jobs=jobs, query=query)


@bp.route('/dashboard')
@login_required
def dashboard():
    """Vista del dashboard con estadísticas por rol"""
    if current_user.is_admin or current_user.is_supervisor:
        # Vista de administrador y supervisor
        jobs = Job.query.order_by(Job.created_at.desc()).all()
        pending_jobs = PendingJob.query.order_by(PendingJob.created_at.desc()).all()
        pending_verification_count = PendingJob.query.filter_by(pending_type='new_job').count()
        pending_photos_count = PendingJob.query.filter_by(pending_type='photo_verification').count()

        stats = {
            'total_jobs': len(jobs),
            'completed_jobs': CompletedJob.query.count(),
            'pending_jobs': len(pending_jobs),
            'designers_count': User.query.filter_by(is_designer=True).count(),
            'pending_verification_count': pending_verification_count,
            'pending_photos_count': pending_photos_count
        }
        
        template = 'dashboard_admin.html' if current_user.is_admin else 'dashboard_supervisor.html'
        return render_template(template, 
                          jobs=jobs,
                          pending_jobs=pending_jobs,
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

            total_amount = float(request.form.get('total_amount', 0))
            deposit_amount = float(request.form.get('deposit_amount', 0))
            invoice_number = request.form.get('invoice_number')

            # Crear el trabajo
            job = Job(
                description=request.form.get('description'),
                designer_id=designer_id,
                registered_by_id=current_user.id,
                invoice_number=invoice_number,
                client_name=request.form.get('client_name'),
                phone_number=phone_number,
                tags=tags,
                total_amount=total_amount,
                deposit_amount=deposit_amount
            )

            db.session.add(job)
            db.session.flush()  # Para obtener el ID del trabajo

            # Crear la factura automáticamente
            invoice = Invoice(
                job_id=job.id,
                job_type='job',
                invoice_number=invoice_number,
                total_amount=total_amount,
                deposit_amount=deposit_amount,
                created_at=datetime.utcnow()
            )
            
            db.session.add(invoice)
            db.session.commit()

            log_activity(
                'nuevo_trabajo',
                f"Trabajo y factura creados para {job.client_name} (Factura: {job.invoice_number})"
            )

            flash('Trabajo y factura creados exitosamente', 'success')
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
    try:
        job = Job.query.get_or_404(job_id)

        # Asegurar que los montos sean números flotantes
        total_amount = float(job.total_amount if job.total_amount else 0)
        deposit_amount = float(job.deposit_amount if job.deposit_amount else 0)
        remaining_amount = total_amount - deposit_amount

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

        # Log para debugging
        logger.info(f"Montos en show_job_qr - Total: {total_amount}, Abono:{deposit_amount}, Restante: {remaining_amount}")

        return render_template('job_qr.html', 
                             job=job, 
                             qr_image=qr_image,
                             total_amount=total_amount,
                             deposit_amount=deposit_amount,
                             remaining_amount=remaining_amount)

    except Exception as e:
        logger.error(f"Error en show_job_qr: {str(e)}")
        flash('Error al generar el código QR', 'error')
        return redirect(url_for('main.dashboard'))



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
    delivered_job= DeliveredJob(
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
        tags=job.tags    )

    # Agregar el nuevo trabajo entregado y eliminar el trabajocompletado
    db.session.add(delivered_job)
    db.session.delete(job)
    db.session.commit()

    log_activity(
        'trabajo_entregado',
        f"Trabajo entregado: {delivered_job.client_name} (Factura: {delivered_job.invoice_number})"
    )

    flash('Trabajo marcado como entregado', 'success')
    return redirect(url_for('main.completed_jobs'))



@bp.route('/jobs/<int:job_id>/remove', methods=['POST'])
@login_required
@admin_required
def remove_job(job_id):
    data = request.get_json() or request.form
    password = data.get('admin_password')

    if not password:
        return jsonify({'success': False, 'message': 'Se requiere contraseña para eliminar'})

    # Verificar si la contraseña coincide con algún admin solamente
    admins = User.query.filter_by(is_admin=True).all()
    valid_password = False
    for admin in admins:
        if admin.check_password(password):
            valid_password = True
            break

    if not valid_password:
        return jsonify({'success': False, 'message': 'Contraseña incorrecta. Se requiere contraseña de administrador.'})

    try:
        job = Job.query.get_or_404(job_id)
        db.session.delete(job)
        db.session.commit()

        log_activity(
            'trabajo_eliminado',
            f"Trabajo eliminado: {job.client_name} (Factura: {job.invoice_number})"
        )

        return jsonify({'success': True, 'message': 'Trabajo eliminado exitosamente'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al eliminar trabajo: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al eliminar el trabajo'})

@bp.route('/completed-jobs')
@login_required
def completed_jobs():
    """Ver trabajos completados"""
    if current_user.is_staff:
        # Si es staff (admin o supervisor) ve todos los trabajos
        jobs = CompletedJob.query.order_by(CompletedJob.completed_at.desc()).all()
    else:
        # Si es diseñador,        # Si es diseñador, solo ve sus trabajos completados
        jobs = CompletedJob.query.filter_by(designer_id=current_user.id).order_by(CompletedJob.completed_at.desc()).all()

    return render_template('completed_jobs.html', jobs=jobs)

@bp.route('/jobs/<int:job_id>/invoice')
@login_required
def display_job_invoice(job_id):
    """Ver factura de un trabajo"""
    try:
        job, qr_code_image = get_job_invoice_data(job_id=job_id)
        if not job:
            flash('Factura no encontrada', 'error')
            return redirect(url_for('main.dashboard'))

        # Asegurar que los montos sean float y estén formateados correctamente
        total_amount = float(job.total_amount if job.total_amount else 0)
        deposit_amount = float(job.deposit_amount if hasattr(job, 'deposit_amount') and job.deposit_amount else 0)
        remaining_amount = total_amount - deposit_amount

        logger.info(f"Montos de factura - Total: {total_amount}, Abono: {deposit_amount}, Restante: {remaining_amount}")

        return render_template('invoice_pdf.html',
                           job=job,
                           qr_code=qr_code_image,
                           total_amount=total_amount,
                           deposit_amount=deposit_amount,
                           remaining_amount=remaining_amount)
    except Exception as e:
        logger.error(f"Error mostrando factura: {str(e)}")
        flash('Error al mostrar la factura', 'error')
        return redirect(url_for('main.dashboard'))


@bp.route('/jobs/<int:job_id>/complete', methods=['POST'])
@login_required
def complete_job(job_id):
    """Completar un trabajo y moverlo a trabajos completados"""
    try:
        data = request.get_json()
        admin_password = data.get('admin_password')

        if not admin_password:
            return jsonify({
                'success': False,
                'message': 'Se requiere la contraseña de administrador'
            }), 400

        # Verificar si la contraseña coincide con algún admin o supervisor
        authorized_users = User.query.filter(
            (User.is_admin == True) | (User.is_supervisor == True)
        ).all()

        valid_password = False
        authorized_user = None
        for user in authorized_users:
            if user.check_password(admin_password):
                valid_password = True
                authorized_user = user
                break

        if not valid_password:
            logger.warning(f"Intento de autorización fallido para completar trabajo {job_id}")
            return jsonify({
                'success': False,
                'message': 'Contraseña incorrecta. Se requiere contraseña de administrador o supervisor.'
            }), 401

        # Buscar el trabajo
        job = Job.query.get_or_404(job_id)

        try:
            # Crear un trabajo completado
            completed_job = CompletedJob(
                original_job_id=job.id,
                description=job.description,
                designer_id=job.designer_id,
                registered_by_id=authorized_user.id if authorized_user else current_user.id,
                invoice_number=job.invoice_number,
                client_name=job.client_name,
                phone_number=job.phone_number,
                created_at=job.created_at,
                tags=job.tags,
                total_amount=job.total_amount,
                deposit_amount=job.deposit_amount if hasattr(job, 'deposit_amount') else None,
                qr_code=job.qr_code,  # Mantener el mismo código QR
                completed_at=datetime.utcnow()
            )

            # Agregar el trabajo completado y eliminar el trabajo original
            db.session.add(completed_job)
            db.session.delete(job)
            db.session.commit()

            # Registrar la actividad
            log_activity(
                'trabajo_completado',
                f"Trabajo completado por {authorized_user.username if authorized_user else current_user.username}: {completed_job.client_name} (Factura: {completed_job.invoice_number})"
            )

            return jsonify({
                'success': True,
                'message': 'Trabajo completado exitosamente'
            })

        except Exception as e:
            db.session.rollback()
            error_msg = str(e)
            logger.error(f"Error al guardar trabajo completado {job_id}: {error_msg}")
            return jsonify({
                'success': False,
                'message': f'Error al completar el trabajo: {error_msg}'
            }), 500

    except Exception as e:
        logger.error(f"Error al procesar la solicitud para completar trabajo {job_id}: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al procesar la solicitud: {str(e)}'
        }), 500

@bp.route('/clean-database', methods=['POST'])
@login_required
@admin_required
def clean_database():
    """Limpiar todas las tablas de trabajos"""
    try:
        # Verificar contraseña de administrador
        password = request.form.get('admin_password')
        if not password:
            flash('Se requiere contraseña de administrador', 'error')
            return redirect(url_for('main.dashboard'))

        # Verificar si la contraseña coincide con algún admin
        admins = User.query.filter_by(is_admin=True).all()
        valid_password = False
        for admin in admins:
            if admin.check_password(password):
                valid_password = True
                break

        if not valid_password:
            flash('Contraseña de administrador incorrecta', 'error')
            return redirect(url_for('main.dashboard'))

        # Limpiar todas las tablas
        Job.query.delete()
        CompletedJob.query.delete()
        DeliveredJob.query.delete()
        PendingJob.query.delete()
        Message.query.delete()

        db.session.commit()

        log_activity('limpiar_base_datos', 'Base de datos limpiada exitosamente')
        flash('Todas las tablas han sido limpiadas exitosamente', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al limpiar las tablas: {str(e)}', 'error')

    return redirect(url_for('main.dashboard'))

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
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment;filename=trabajos_{datetime.now().strftime("%Y%m%d")}.xlsx'}
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
@login_required
def generate_job_pdf(job_id):
    """Generar PDF para un trabajo"""
    try:
        # Buscar primero en trabajos activos
        job = Job.query.get(job_id)
        if not job:
            # Si no está en activos, buscar en completados
            job = CompletedJob.query.get_or_404(job_id)

        # Asegurar que los montos sean números
        total_amount = float(job.total_amount) if hasattr(job, 'total_amount') and job.total_amount else 0.0
        deposit_amount = float(job.deposit_amount) if hasattr(job, 'deposit_amount') and job.deposit_amount else 0.0
        remaining_amount = total_amount - deposit_amount

        # Generar QR si no existe
        if not job.qr_code:
            job.generate_qr_code()
            db.session.commit()

        qr_url = url_for('main.public_job', qr_code=job.qr_code, _external=True)

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=5
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Convert QR to base64
        buffered = io.BytesIO()
        qr_img.save(buffered, format="PNG")
        qr_code_image = base64.b64encode(buffered.getvalue()).decode()

        # Render invoice template with explicit amount values
        return render_template('invoice_pdf.html',
                              job=job,
                              qr_code=qr_code_image,
                              total_amount="{:.2f}".format(total_amount),
                              deposit_amount="{:.2f}".format(deposit_amount),
                              remaining_amount="{:.2f}".format(remaining_amount))

    except Exception as e:
        logger.error(f"Error generando PDF del trabajo: {str(e)}")
        flash('Error al generar el PDF. Por favor, inténtelo de nuevo.', 'error')
        return redirect(url_for('main.dashboard'))

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

@bp.route('/jobs/public/<string:qr_code>')
def public_job(qr_code):
    """Vista pública de un trabajo accesible por QR"""
    try:
        # Buscar primero en trabajos activos
        job = Job.query.filter_by(qr_code=qr_code).first()
        if not job:
            # Si no está en activos, buscar en completados
            job = CompletedJob.query.filter_by(qr_code=qr_code).first()
            if not job:
                # Si no está en completados, buscar en pendientes
                job = PendingJob.query.filter_by(qr_code=qr_code).first()
                if not job:
                    return "Trabajo no encontrado", 404

        # Asegurar que los montos sean números
        total_amount = float(job.total_amount) if job.total_amount else 0.0
        deposit_amount = float(job.deposit_amount) if hasattr(job, 'deposit_amount') and job.deposit_amount else 0.0
        remaining_amount = total_amount - deposit_amount

        # Generar URL pública para el QR si no existe
        if not job.qr_code:
            job.generate_qr_code()
            db.session.commit()

        qr_url = url_for('main.public_job', qr_code=job.qr_code, _external=True)

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=5
        )
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Convert QR to base64
        buffered = io.BytesIO()
        qr_img.save(buffered, format="PNG")
        qr_code_image = base64.b64encode(buffered.getvalue()).decode()

        return render_template('invoice_pdf.html',
                              job=job,
                              qr_code=qr_code_image,
                              total_amount="{:.2f}".format(total_amount),
                              deposit_amount="{:.2f}".format(deposit_amount),
                              remaining_amount="{:.2f}".format(remaining_amount))

    except Exception as e:
        logger.error(f"Error mostrando trabajo público: {str(e)}")
        return "Error al mostrar el trabajo", 500



@bp.route('/jobs/pending/verification', methods=['GET', 'POST'])
@login_required
@staff_required
def pendingverification():
    """Vista de trabajos pendientes por verificar"""
    try:
        jobs = PendingJob.query.filter_by(pending_type='new_job').all()
        return render_template('pendingverification.html', jobs=jobs)
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

@bp.route('/jobs/<int:job_id>/approve', methods=['POST'])
@login_required
@staff_required
def approve_pending_job(job_id):
    """Aprobar un trabajo pendiente"""
    try:
        pending_job = PendingJob.query.get_or_404(job_id)

        # Crear el trabajo completado
        completed_job = CompletedJob(
            original_job_id=pending_job.original_job_id,
            description=pending_job.description,
            designer_id=pending_job.designer_id,
            registered_by_id=pending_job.registered_by_id,
            invoice_number=pending_job.invoice_number,
            client_name=pending_job.client_name,
            phone_number=pending_job.phone_number,  # Fixed: changed from phonenumber to phone_number
            total_amount=float(pending_job.total_amount or 0),
            deposit_amount=float(pending_job.deposit_amount or 0),
            completed_at=datetime.utcnow(),
            tags=pending_job.tags
        )

        # Eliminar el trabajo pendiente y agregar el completado
        db.session.delete(pending_job)
        db.session.add(completed_job)
        db.session.commit()

        log_activity(
            'trabajo_aprobado',
            f"Trabajo aprobado: {completed_job.client_name} (Factura: {completed_job.invoice_number})"
        )

        flash('Trabajo aprobado exitosamente', 'success')
        return redirect(url_for('main.pending_verification'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error al aprobar trabajo pendiente: {str(e)}")
        flash('Error al aprobar el trabajo. Por favor, inténtelo de nuevo.', 'error')
        return redirect(url_for('main.pending_verification'))

@bp.route('/jobs/<int:job_id>/approve', methods=['POST'])
@login_required
def approve_job(job_id):
    """Aprobar un trabajo pendiente o completar un trabajo activo"""
    try:
        # Verificar si es un trabajo pendiente o activo
        pending_job = PendingJob.query.get(job_id)
        if pending_job:
            job = pending_job.to_job()
        else:
            job = Job.query.get_or_404(job_id)

        # Verificar si el usuario está autorizado
        if not current_user.can_authorize_jobs:
            flash('No tienes permiso para aprobar trabajos', 'error')
            return jsonify({'success': False, 'message': 'No autorizado'}), 403

        # Verificar la contraseña
        data = request.get_json() or request.form
        admin_password = data.get('admin_password')
        if not admin_password:
            return jsonify({'success': False, 'message': 'Se requiere contraseña'})

        # Verificar la contraseña con usuarios autorizados
        staff = User.query.filter(User.can_authorize_jobs).all()
        valid_auth = False
        for user in staff:
            if user and user.check_password(admin_password):
                valid_auth = True
                break

        if not valid_auth:
            return jsonify({'success': False, 'message': 'Contraseña incorrecta o usuario no autorizado'})

        # Crear trabajo completado
        completed_job = CompletedJob(
            description=job.description,
            designer_id=job.designer_id,
            registered_by_id=job.registered_by_id,
            invoice_number=job.invoice_number,
            client_name=job.client_name,
            phone_number=job.phone_number,
            created_at=job.created_at,
            completed_at=datetime.utcnow(),
            tags=job.tags,
            total_amount=job.total_amount,
            deposit_amount=job.deposit_amount
        )

        db.session.add(completed_job)

        # Eliminar el trabajo original
        if pending_job:
            db.session.delete(pending_job)
        else:
            db.session.delete(job)

        db.session.commit()

        log_activity(
            'trabajo_completado',
            f"Trabajo completado: {completed_job.client_name} (Factura: {completed_job.invoice_number})"
        )

        return jsonify({'success': True, 'message': 'Trabajo aprobado exitosamente'})

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error al aprobar trabajo: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al procesar la solicitud'})

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

@bp.route('/jobs/public/<string:qr_code>')
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
    else:
        delivered_job = create_delivered_job_from_pending(pending_job)
        db.session.delete(pending_job)

    db.session.add(delivered_job)
    db.session.commit()

    log_activity(
        'trabajo_entregado_qr',
        f"Trabajo entregado por escaneo QR: {delivered_job.client_name} (Factura: {delivered_job.invoice_number})"
    )

    flash('¡Trabajo marcado como entregado exitosamente!', 'success')
    return redirect(url_for('main.dashboard'))

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

import json

@bp.app_template_filter('fromjson')
def fromjson_filter(value):
    return json.loads(value)

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
        flash(f'Error al cargar trabajos pendientes: {str(e)}', '`error')
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
            tags=job.tags,
            total_amount=job.total_amount,
            deposit_amount=job.deposit_amount
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

@bp.route('/public/invoice/<string:qr_code>')
def public_invoice(qr_code):
    return generate_invoice_view(qr_code=qr_code)

@bp.route('/pending-jobs/<int:job_id>/view-invoice')
@login_required
def view_pending_job_invoice(job_id):
    """Ver factura desde lista de trabajos pendientes"""
    try:
        job = PendingJob.query.get_or_404(job_id)

        # Asegurar que los montos sean números flotantes
        total_amount = float(job.total_amount if job.total_amount else 0)
        deposit_amount = float(job.deposit_amount if job.deposit_amount else 0)
        remaining_amount = total_amount - deposit_amount

        # Generar URL pública para el QR si no existe
        if not job.qr_code:
            job.generate_qr_code()
            db.session.commit()

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=5
        )

        qr_url = url_for('main.view_public_invoice', qr_code=job.qr_code, _external=True)
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Convert QR to base64
        buffered = io.BytesIO()
        qr_img.save(buffered, format="PNG")
        qr_code_image = base64.b64encode(buffered.getvalue()).decode()

        # Log para debugging
        logger.info(f"Montos de factura pendiente - Total: {total_amount}, Abono: {deposit_amount}, Restante: {remaining_amount}")

        # Render invoice template with amount values
        return render_template('invoice_pdf.html',
                              job=job,
                              qr_code=qr_code_image,
                              total_amount=total_amount,
                              deposit_amount=deposit_amount,
                              remaining_amount=remaining_amount)

    except Exception as e:
        logger.error(f"Error generando factura pendiente: {str(e)}")
        flash('Error al generar la factura. Por favor, inténtelo de nuevo.', 'error')
        return redirect(url_for('main.pending_jobs'))

# Route updated to use new display_job_invoice function name
@bp.route('/jobs/<int:job_id>/view-invoice')
@login_required
def get_job_invoice(job_id):
    """Ver factura desde lista de trabajos"""
    try:
        job, qr_code_image = get_job_invoice_data(job_id=job_id)
        if not job:
            flash('Trabajo no encontrado', 'error')
            return redirect(url_for('main.dashboard'))

        return render_template('invoice_pdf.html',
                           job=job,
                           qr_code=qr_code_image,
                           total_amount=job.total_amount,
                           deposit_amount=job.deposit_amount,
                           remaining_amount=job.remaining_amount)

    except Exception as e:
        logger.error(f"Error generando factura: {str(e)}")
        flash('Error al generar la factura. Por favor, inténtelo de nuevo.', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/jobs/pending/verify/<int:job_id>', methods=['POST'])
@login_required
@staff_required
def verify_pending_job(job_id):
    """Verificar y aprobar un trabajo pendiente"""
    try:
        # Obtener y verificar la contraseña
        data = request.get_json() or {}
        admin_password = data.get('admin_password')

        if not admin_password:
            return jsonify({
                'success': False,
                'message': 'Se requiere contraseña de administrador'
            }), 400

        # Verificar si la contraseña coincide con algún admin o supervisor
        authorized_users = User.query.filter(
            (User.is_admin == True) | (User.is_supervisor == True)
        ).all()

        valid_password = False
        authorized_user = None
        for user in authorized_users:
            if user.check_password(admin_password):
                valid_password = True
                authorized_user = user
                break

        if not valid_password:
            logger.warning(f"Intento de autorización fallido para verificar trabajo {job_id}")
            return jsonify({
                'success': False,
                'message': 'Contraseña incorrecta. Se requiere contraseña de administrador o supervisor.'
            }), 401

        # Obtener el trabajo pendiente
        pending_job = PendingJob.query.get_or_404(job_id)

        try:
            # Crear un nuevo trabajo activo
            new_job = Job(
                description=pending_job.description,
                designer_id=pending_job.designer_id,
                registered_by_id=authorized_user.id if authorized_user else current_user.id,
                invoice_number=pending_job.invoice_number,
                client_name=pending_job.client_name,
                phone_number=pending_job.phone_number,
                total_amount=pending_job.total_amount,
                deposit_amount=pending_job.deposit_amount if hasattr(pending_job, 'deposit_amount') else None,
                created_at=pending_job.created_at,
                tags=pending_job.tags
            )

            # Agregar el nuevo trabajo y eliminar el pendiente
            db.session.add(new_job)
            db.session.delete(pending_job)
            db.session.commit()

            # Registrar la actividad
            log_activity(
                'verificar_trabajo',
                f"Trabajo verificado por {authorized_user.username if authorized_user else current_user.username}: {new_job.client_name} (Factura: {new_job.invoice_number})"
            )

            return jsonify({
                'success': True,
                'message': 'Trabajo verificado y aprobado exitosamente',
                'redirect_url': url_for('main.view_job_invoice', job_id=new_job.id)
            })

        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Error de base de datos al verificar trabajo: {str(db_error)}")
            return jsonify({
                'success': False,
                'message': f'Error al guardar los cambios: {str(db_error)}'
            }), 500

    except Exception as e:
        logger.error(f"Error al verificar trabajo pendiente: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al procesar la solicitud: {str(e)}'
        }), 500

@bp.route('/public/invoice/<string:qr_code>')
def generate_invoice_view(qr_code=None):
    try:
        job, qr_code_image = get_job_invoice_data(qr_code=qr_code)
        if not job:
            return "Factura no encontrada", 404

        return render_template('invoice_pdf.html', job=job, qr_code=qr_code_image,
                               total_amount=job.total_amount, deposit_amount=job.deposit_amount,
                               remaining_amount=job.remaining_amount)
    except Exception as e:
        logger.error(f"Error generando vista de factura: {str(e)}")
        return "Error al generar la vista de factura", 500

