from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from app import db
from app.models import User, Job
from datetime import datetime

bp = Blueprint('main', __name__)

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
    if current_user.is_admin:
        jobs = Job.query.all()
    else:
        jobs = current_user.assigned_jobs
    return render_template('dashboard.html', jobs=jobs)

# Ruta para crear usuarios iniciales
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
            name=f'PC{i:02d}',
            is_admin=False,
            can_edit=True  # Todos pueden editar
        )
        user.set_password('1245')
        db.session.add(user)

    db.session.commit()
    flash('Usuarios creados exitosamente', 'success')
    return redirect(url_for('main.login'))

@bp.route('/jobs/new', methods=['GET', 'POST'])
@login_required
def new_job():
    if not current_user.is_admin and not current_user.can_edit:
        flash('No tienes permiso para esta acción', 'error')
        return redirect(url_for('main.dashboard'))

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

    designers = User.query.filter_by(is_admin=False).all()
    return render_template('new_job.html', designers=designers)

@bp.route('/jobs/<int:job_id>/complete', methods=['POST'])
@login_required
def complete_job(job_id):
    job = Job.query.get_or_404(job_id)

    # Verificar que el usuario tenga permiso para completar este trabajo
    if not current_user.is_admin and job.designer_id != current_user.id:
        flash('No tienes permiso para completar este trabajo', 'error')
        return redirect(url_for('main.dashboard'))

    job.is_completed = True
    job.completed_at = datetime.utcnow()
    db.session.commit()

    flash('Trabajo marcado como completado exitosamente', 'success')
    return redirect(url_for('main.dashboard'))