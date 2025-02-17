from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models import User, Job

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return redirect(url_for('main.login'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('main.dashboard'))

        flash('Usuario o contraseña incorrectos', 'error')
    return render_template('login.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        jobs = Job.query.all()
    else:
        jobs = Job.query.filter_by(designer_id=current_user.id).all()
    return render_template('dashboard.html', jobs=jobs)

@bp.route('/jobs/new', methods=['GET', 'POST'])
@login_required
def new_job():
    if not current_user.is_admin:
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