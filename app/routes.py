from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from app import db
from app.models import User, Job, CompletedJob # Added CompletedJob import
from datetime import datetime
from functools import wraps

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
            login_user(user)
            flash('¡Bienvenido!', 'success')
            return redirect(url_for('main.dashboard'))

        flash('Usuario o contraseña incorrectos', 'error')
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_staff:
        jobs = Job.query.all()
    else:
        jobs = Job.query.filter_by(designer_id=current_user.id).all()
    return render_template('dashboard.html', jobs=jobs)

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
    name = request.form.get('name')
    username = request.form.get('username')
    password = request.form.get('password')
    user_type = request.form.get('user_type', 'designer')

    if User.query.filter_by(username=username).first():
        flash('El nombre de usuario ya existe', 'error')
        return redirect(url_for('main.manage_users'))

    user = User(
        name=name,
        username=username,
        is_admin=user_type == 'admin',
        is_supervisor=user_type == 'supervisor',
        can_edit=True
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flash('Usuario creado exitosamente', 'success')
    return redirect(url_for('main.manage_users'))

@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        flash('No se puede eliminar el usuario administrador principal', 'error')
        return redirect(url_for('main.manage_users'))

    db.session.delete(user)
    db.session.commit()
    flash('Usuario eliminado exitosamente', 'success')
    return redirect(url_for('main.manage_users'))

@bp.route('/jobs/new', methods=['GET', 'POST'])
@login_required
@staff_required
def new_job():
    if request.method == 'POST':
        job = Job(
            description=request.form.get('description'),
            designer_id=request.form.get('designer_id'),
            invoice_number=request.form.get('invoice_number'),
            client_name=request.form.get('client_name'),
            phone_number=request.form.get('phone_number')
        )
        db.session.add(job)
        db.session.commit()
        flash('Trabajo creado exitosamente', 'success')
        return redirect(url_for('main.dashboard'))

    designers = User.query.filter_by(is_admin=False, is_supervisor=False).all()
    return render_template('new_job.html', designers=designers)

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
    job.is_delivered = True
    job.delivered_at = datetime.utcnow()
    db.session.commit()
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

    # Verificar si la contraseña coincide con algún admin o supervisor
    admins = User.query.filter(
        (User.is_admin == True) | (User.is_supervisor == True)
    ).all()

    valid_password = False
    for admin in admins:
        if admin.check_password(password):
            valid_password = True
            break

    if not valid_password:
        flash('Contraseña incorrecta', 'error')
        return redirect(url_for('main.dashboard'))

    job = Job.query.get_or_404(job_id)
    db.session.delete(job)
    db.session.commit()
    flash('Trabajo eliminado exitosamente', 'success')
    return redirect(url_for('main.dashboard'))

@bp.route('/completed-jobs')
@login_required
@staff_required
def completed_jobs():
    jobs = CompletedJob.query.all()
    return render_template('completed_jobs.html', jobs=jobs)

@bp.route('/jobs/<int:job_id>/complete', methods=['POST'])
@login_required
def complete_job(job_id):
    job = Job.query.get_or_404(job_id)
    verification_code = request.form.get('verification_code')

    if not current_user.is_staff and job.designer_id != current_user.id:
        flash('No tienes permiso para completar este trabajo', 'error')
        return redirect(url_for('main.dashboard'))

    if not job.invoice_number or verification_code != job.invoice_number:
        flash('Número de factura inválido', 'error')
        return redirect(url_for('main.dashboard'))

    # Crear trabajo completado
    completed_job = CompletedJob(
        original_job_id=job.id,
        description=job.description,
        designer_id=job.designer_id,
        invoice_number=job.invoice_number,
        client_name=job.client_name,
        phone_number=job.phone_number,
        created_at=job.created_at,
        completed_at=datetime.utcnow()
    )
    db.session.add(completed_job)
    db.session.delete(job)
    db.session.commit()

    flash('Trabajo marcado como completado exitosamente', 'success')
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
        can_edit=True
    )
    admin.set_password('admin123')
    db.session.add(admin)

    # Crear usuarios PC01-PC09
    for i in range(1, 10):
        username = f'pc{i:02d}'
        user = User(
            username=username,
            name=f'PC{i:02d}',  # Nombre también como PC01, PC02, etc.
            is_admin=False,
            can_edit=True
        )
        user.set_password('1245')
        db.session.add(user)

    db.session.commit()
    flash('Usuarios creados exitosamente', 'success')
    return redirect(url_for('main.login'))