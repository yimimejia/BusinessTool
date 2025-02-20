from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from sqlalchemy.orm import validates
import re
import base64
import json

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    is_supervisor = db.Column(db.Boolean, default=False)
    can_edit = db.Column(db.Boolean, default=True)
    is_service = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    remember_token = db.Column(db.String(100))  # Para "mantener sesión iniciada"

    # Relationships with explicit foreign keys
    assigned_jobs = db.relationship('Job', 
                                  foreign_keys='Job.designer_id',
                                  backref='designer')
    registered_jobs = db.relationship('Job', 
                                    foreign_keys='Job.registered_by_id',
                                    backref='registered_by')
    activities = db.relationship('ActivityLog', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')

    def set_password(self, password):
        if len(password) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not any(c.isupper() for c in password):
            raise ValueError("La contraseña debe contener al menos una mayúscula")
        if not any(c.isdigit() for c in password):
            raise ValueError("La contraseña debe contener al menos un número")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_staff(self):
        return self.is_admin or self.is_supervisor

    @property
    def can_manage_users(self):
        return self.is_admin

    @property
    def can_delete_jobs(self):
        return self.is_admin

    def get_pending_jobs(self):
        """Obtiene los trabajos pendientes del diseñador"""
        return Job.query.filter_by(designer_id=self.id, is_completed=False).all()

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'pending_job', 'admin_alert', etc.
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=True)

    @classmethod
    def create_pending_job_notification(cls, user, job):
        """Crea una notificación para un trabajo pendiente"""
        message = f"Tienes un trabajo pendiente: {job.description}"
        notification = cls(
            user_id=user.id,
            message=message,
            type='pending_job',
            job_id=job.id
        )
        db.session.add(notification)
        db.session.commit()
        return notification

    @classmethod
    def create_admin_notification(cls, admin, pending_count):
        """Crea una notificación para administradores sobre trabajos pendientes"""
        message = f"Hay {pending_count} trabajos pendientes en el sistema"
        notification = cls(
            user_id=admin.id,
            message=message,
            type='admin_alert'
        )
        db.session.add(notification)
        db.session.commit()
        return notification

class WebAuthnCredential(db.Model):
    __tablename__ = 'webauthn_credentials'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    credential_id = db.Column(db.String(250), unique=True, nullable=False)
    public_key = db.Column(db.Text, nullable=False)
    sign_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    name = db.Column(db.String(100))  # Nombre del dispositivo

    def get_credential_data(self):
        return {
            'credentialId': self.credential_id,
            'publicKey': self.public_key,
            'signCount': self.sign_count,
        }

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))

class Job(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    designer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    registered_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invoice_number = db.Column(db.String(50))
    client_name = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    is_completed = db.Column(db.Boolean, default=False)
    tags = db.Column(db.String(200))  # Comma-separated tags

    @validates('phone_number')
    def validate_phone_number(self, key, phone_number):
        if not phone_number:
            return phone_number

        # Eliminar espacios y guiones para normalizar
        cleaned_number = re.sub(r'[\s-]', '', phone_number)

        # Validar formato: +1 seguido de 10 dígitos
        if not re.match(r'^\+1\d{10}$', cleaned_number):
            raise ValueError('El número de teléfono debe incluir el código de área (+1) y 10 dígitos')

        # Formatear el número para almacenamiento
        formatted_number = f'+1-{cleaned_number[2:5]}-{cleaned_number[5:]}'
        return formatted_number

class CompletedJob(db.Model):
    __tablename__ = 'completed_jobs'
    id = db.Column(db.Integer, primary_key=True)
    original_job_id = db.Column(db.Integer)
    description = db.Column(db.String(255), nullable=False)
    designer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    registered_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invoice_number = db.Column(db.String(50))
    client_name = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    called_at = db.Column(db.DateTime)
    is_called = db.Column(db.Boolean, default=False)
    tags = db.Column(db.String(200))  # Comma-separated tags

    # Relationships
    designer = db.relationship('User', foreign_keys=[designer_id])
    registered_by = db.relationship('User', foreign_keys=[registered_by_id])

class DeliveredJob(db.Model):
    __tablename__ = 'delivered_jobs'
    id = db.Column(db.Integer, primary_key=True)
    original_job_id = db.Column(db.Integer)
    completed_job_id = db.Column(db.Integer)
    description = db.Column(db.String(255), nullable=False)
    designer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    registered_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invoice_number = db.Column(db.String(50))
    client_name = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime)
    called_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime, default=datetime.utcnow)
    tags = db.Column(db.String(200))  # Comma-separated tags

    # Relationships
    designer = db.relationship('User', foreign_keys=[designer_id])
    registered_by = db.relationship('User', foreign_keys=[registered_by_id])