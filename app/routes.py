from flask import Blueprint, render_template, flash, redirect, url_for, current_app, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import secrets
import json
import os
import re
import urllib.parse
from app import db, logger
from app.helpers import staff_required, log_activity
from app.models import PendingJob, CompletedJob

# Crear el Blueprint
bp = Blueprint('main', __name__)

# Crear directorio job_photos si no existe
photos_dir = os.path.join(current_app.static_folder, 'job_photos')
os.makedirs(photos_dir, exist_ok=True)
logger.info(f"Directorio principal de fotos verificado: {photos_dir}")

@bp.route('/')
def index():
    """Página principal"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('login.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal"""
    if current_user.is_admin:
        return render_template('dashboard_admin.html')
    elif current_user.is_staff:
        return render_template('dashboard_supervisor.html')
    else:
        return render_template('dashboard_designer.html')

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
            logger.info(f"Fotos cargadas del trabajo pendiente: {photos}")

            # Verificar que las fotos existen físicamente
            verified_photos = []
            for photo_path in photos:
                full_path = os.path.join(current_app.static_folder, photo_path)
                logger.info(f"Verificando foto: {full_path}")
                if os.path.exists(full_path):
                    verified_photos.append(photo_path)
                    logger.info(f"Foto verificada: {photo_path}")
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

        # Eliminar el trabajo pendiente después de preparar todo
        db.session.delete(pending_job)
        db.session.commit()

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


@bp.route('/photos/view/<token>')
def view_approved_photos(token):
    """Ver fotos aprobadas con token temporal"""
    try:
        logger.info(f"Accediendo a fotos con token: {token}")
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
                logger.info(f"Contenido de job.photos: {job.photos}")
                saved_photos = json.loads(job.photos)
                logger.info(f"JSON decodificado: {saved_photos}")

                for photo_path in saved_photos:
                    # Asegurarse de que no estamos duplicando el prefijo job_photos/
                    if photo_path.startswith('job_photos/'):
                        clean_path = photo_path
                    else:
                        clean_path = f'job_photos/{photo_path}'

                    full_path = os.path.join(current_app.static_folder, clean_path)
                    logger.info(f"Verificando foto: {full_path}")

                    if os.path.exists(full_path):
                        photos.append(clean_path)
                        logger.info(f"Foto verificada y agregada: {clean_path}")
                    else:
                        logger.warning(f"Foto no encontrada: {full_path}")

                logger.info(f"Total de fotos encontradas: {len(photos)}")

            except json.JSONDecodeError as e:
                logger.error(f"Error decodificando JSON de fotos: {str(e)}")
                photos = []
            except Exception as e:
                logger.error(f"Error procesando fotos: {str(e)}")
                photos = []

        if not photos:
            logger.warning("No se encontraron fotos válidas para mostrar")

        return render_template('photos_gallery.html', 
                          photos=photos,
                          expired=False,
                          error=None)

    except Exception as e:
        logger.error(f"Error al mostrar fotos aprobadas: {str(e)}")
        return render_template('photos_gallery.html', 
                          photos=[],
                          expired=True, 
                          error="Error al cargar las fotos")



@bp.route('/jobs/<int:job_id>/send-photos', methods=['POST'])
@login_required
def send_job_photos(job_id):
    """Enviar fotos para un trabajo completado"""
    try:
        job = CompletedJob.query.get_or_404(job_id)
        if 'photos' not in request.files:
            flash('No se seleccionaron fotos', 'error')
            return redirect(url_for('main.completed_jobs'))

        # Crear directorio para las fotos si no existe
        photos_dir = os.path.join(current_app.static_folder, 'job_photos', str(job.id))
        os.makedirs(photos_dir, exist_ok=True)
        logger.info(f"Directorio de fotos creado: {photos_dir}")

        photo_paths = []
        photos = request.files.getlist('photos')

        for photo in photos:
            if photo.filename:
                # Generar nombre de archivo seguro
                filename = secure_filename(photo.filename)
                # Ruta relativa para guardar en la base de datos
                relative_path = os.path.join('job_photos', str(job.id), filename)
                # Ruta completa para guardar el archivo
                photo_path = os.path.join(current_app.static_folder, relative_path)

                logger.info(f"Guardando foto en: {photo_path}")
                photo.save(photo_path)
                photo_paths.append(relative_path)

        # Crear un PendingJob para la verificación de fotos
        pending_job = PendingJob(
            original_job_id=job.id,
            description=f"Verificación de fotos - Trabajo #{job.id}",
            designer_id=current_user.id,
            registered_by_id=job.registered_by_id,
            invoice_number=job.invoice_number,
            client_name=job.client_name,
            phone_number=job.phone_number,
            created_at=job.created_at,
            photos=json.dumps(photo_paths),
            pending_type='photo_verification',
            message=request.form.get('message', ''),
            total_amount=float(job.total_amount or 0),
            deposit_amount=float(job.deposit_amount or 0)
        )

        db.session.add(pending_job)
        db.session.commit()
        logger.info(f"Trabajo pendiente creado con {len(photo_paths)} fotos")

        flash('Fotos enviadas para verificación', 'success')
        return redirect(url_for('main.completed_jobs'))

    except Exception as e:
        logger.error(f"Error al enviar fotos: {str(e)}")
        db.session.rollback()
        flash('Error al procesar las fotos', 'error')
        return redirect(url_for('main.completed_jobs'))

@bp.route('/completed_jobs')
@login_required
def completed_jobs():
    """Ver trabajos completados"""
    try:
        jobs = CompletedJob.query.filter(
            CompletedJob.is_delivered.is_(False)
        ).order_by(CompletedJob.created_at.desc()).all()

        return render_template('completed_jobs.html', jobs=jobs)
    except Exception as e:
        logger.error(f"Error al cargar trabajos completados: {str(e)}")
        flash('Error al cargar los trabajos completados', 'error')
        return redirect(url_for('main.dashboard'))

@bp.route('/jobs/<int:job_id>/mark-called', methods=['POST'])
@login_required
def mark_called(job_id):
    """Marcar trabajo como llamado"""
    try:
        job = CompletedJob.query.get_or_404(job_id)
        job.is_called = True
        job.called_at = datetime.utcnow()
        job.called_by_id = current_user.id
        db.session.commit()

        flash('Trabajo marcado como llamado', 'success')
    except Exception as e:
        logger.error(f"Error al marcar trabajo como llamado: {str(e)}")
        flash('Error al actualizar el trabajo', 'error')

    return redirect(url_for('main.completed_jobs'))

@bp.route('/jobs/<int:job_id>/mark-delivered', methods=['POST'])
@login_required
def mark_delivered(job_id):
    """Marcar trabajo como entregado"""
    try:
        job = CompletedJob.query.get_or_404(job_id)
        job.is_delivered = True
        job.delivered_at = datetime.utcnow()
        job.delivered_by_id = current_user.id
        db.session.commit()

        flash('Trabajo marcado como entregado', 'success')
    except Exception as e:
        logger.error(f"Error al marcar trabajo como entregado: {str(e)}")
        flash('Error al actualizar el trabajo', 'error')

    return redirect(url_for('main.completed_jobs'))

@bp.route('/jobs/pending-photos')
@login_required
@staff_required
def jobs_pending_photos():
    """Ver trabajos con fotos pendientes por aprobar"""
    try:
        jobs = PendingJob.query.filter_by(
            pending_type='photo_verification'
        ).order_by(PendingJob.created_at.desc()).all()

        return render_template('pending_photos.html', jobs=jobs)
    except Exception as e:
        logger.error(f"Error al cargar trabajos pendientes: {str(e)}")
        flash('Error al cargar los trabajos pendientes', 'error')
        return redirect(url_for('main.dashboard'))