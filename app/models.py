from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from sqlalchemy.orm import validates
import re
import base64
import json
import random

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    photos = db.Column(db.Text)  # JSON array of photo paths

    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')

    def set_photos(self, photo_paths):
        """Almacena las rutas de las fotos como JSON"""
        self.photos = json.dumps(photo_paths)

    def get_photos(self):
        """Obtiene la lista de rutas de fotos"""
        return json.loads(self.photos) if self.photos else []

    @property
    def is_photo_message(self):
        """Verifica si el mensaje contiene fotos"""
        return bool(self.photos)

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
    remember_token = db.Column(db.String(100))
    permanent_session = db.Column(db.Boolean, default=False)  # Nueva columna

    # Relationships
    assigned_jobs = db.relationship('Job', foreign_keys='Job.designer_id', backref='designer')
    registered_jobs = db.relationship('Job', foreign_keys='Job.registered_by_id', backref='registered_by')
    activities = db.relationship('ActivityLog', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    webauthn_credentials = db.relationship('WebAuthnCredential', backref='user')

    def get_unread_messages_count(self):
        """Obtiene el número de mensajes no leídos"""
        return Message.query.filter_by(recipient_id=self.id, is_read=False).count()

    def get_messages(self):
        """Obtiene todos los mensajes del usuario"""
        return Message.query.filter(
            (Message.recipient_id == self.id) | (Message.sender_id == self.id)
        ).order_by(Message.created_at.desc()).all()

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
    deposit_amount = db.Column(db.Numeric(10, 2))  # Nuevo campo para el abono
    qr_code = db.Column(db.String(100), unique=True)  # Identificador único para el QR

    @validates('phone_number')
    def validate_phone_number(self, key, phone_number):
        if not phone_number:
            return phone_number

        # Eliminar cualquier caracter que no sea número
        cleaned_number = re.sub(r'[^\d]', '', phone_number)

        # Si el número no empieza con 1, agregar el código de área
        if len(cleaned_number) == 10:
            cleaned_number = '1' + cleaned_number
        elif len(cleaned_number) > 11 or len(cleaned_number) < 10:
            raise ValueError('El número de teléfono debe tener 10 dígitos')

        # Validar que empiece con 1
        if not cleaned_number.startswith('1'):
            raise ValueError('El número debe incluir el código de área (+1)')

        # Formatear el número para almacenamiento: +1-XXX-XXXXXXX
        formatted_number = f'+{cleaned_number[0]}-{cleaned_number[1:4]}-{cleaned_number[4:]}'
        return formatted_number

    def generate_qr_code(self):
        """Genera un identificador único para el código QR"""
        if not self.qr_code:
            # Generar un identificador único basado en timestamp y random
            unique_id = f"{int(datetime.utcnow().timestamp())}-{self.id}-{random.randint(1000, 9999)}"
            self.qr_code = base64.urlsafe_b64encode(unique_id.encode()).decode()
        return self.qr_code

    def to_qr_data(self):
        """Convierte los datos del trabajo en un formato adecuado para el QR"""
        # Generamos una URL pública para el trabajo
        public_url = f"/jobs/public/{self.qr_code}"
        return {
            'id': self.id,
            'invoice': self.invoice_number,
            'client': self.client_name,
            'description': self.description,
            'deposit': float(self.deposit_amount) if self.deposit_amount else 0,
            'created': self.created_at.isoformat(),
            'qr_code': self.qr_code,
            'url': public_url
        }

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
    tags = db.Column(db.String(200))
    qr_code = db.Column(db.String(100), unique=True)  # Nuevo campo

    # Relationships
    designer = db.relationship('User', foreign_keys=[designer_id])
    registered_by = db.relationship('User', foreign_keys=[registered_by_id])

    def generate_qr_code(self):
        """Genera un identificador único para el código QR"""
        if not self.qr_code:
            unique_id = f"{int(datetime.utcnow().timestamp())}-{self.id}-{random.randint(1000, 9999)}"
            self.qr_code = base64.urlsafe_b64encode(unique_id.encode()).decode()
        return self.qr_code

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
    tags = db.Column(db.String(200))
    qr_code = db.Column(db.String(100))  # Nuevo campo
    delivery_method = db.Column(db.String(50), default='manual')  # 'manual' o 'qr'

    # Relationships
    designer = db.relationship('User', foreign_keys=[designer_id])
    registered_by = db.relationship('User', foreign_keys=[registered_by_id])

class PendingJob(db.Model):
    __tablename__ = 'pending_jobs'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    designer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    registered_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invoice_number = db.Column(db.String(50))
    client_name = db.Column(db.String(100))
    phone_number = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    qr_code = db.Column(db.String(100), unique=True)
    total_amount = db.Column(db.Numeric(10, 2))
    deposit_amount = db.Column(db.Numeric(10, 2))
    pending_type = db.Column(db.String(50), default='new_job')
    photos = db.Column(db.Text)  # Para almacenar rutas de fotos en JSON

    # Relationships
    designer = db.relationship('User', foreign_keys=[designer_id])
    registered_by = db.relationship('User', foreign_keys=[registered_by_id])

    @validates('phone_number')
    def validate_phone_number(self, key, phone_number):
        if not phone_number:
            return phone_number

        # Eliminar cualquier caracter que no sea número
        cleaned_number = re.sub(r'[^\d]', '', phone_number)

        # Si el número no empieza con 1, agregar el código de área
        if len(cleaned_number) == 10:
            cleaned_number = '1' + cleaned_number
        elif len(cleaned_number) > 11 or len(cleaned_number) < 10:
            raise ValueError('El número de teléfono debe tener 10 dígitos')

        # Validar que empiece con 1
        if not cleaned_number.startswith('1'):
            raise ValueError('El número debe incluir el código de área (+1)')

        # Formatear el número para almacenamiento: +1-XXX-XXXXXXX
        formatted_number = f'+{cleaned_number[0]}-{cleaned_number[1:4]}-{cleaned_number[4:]}'
        return formatted_number

    def generate_qr_code(self):
        """Genera un identificador único para el código QR"""
        if not self.qr_code:
            unique_id = f"{int(datetime.utcnow().timestamp())}-{self.id}-{random.randint(1000, 9999)}"
            self.qr_code = base64.urlsafe_b64encode(unique_id.encode()).decode()
        return self.qr_code

    def to_job(self):
        """Convierte el trabajo pendiente en un trabajo regular"""
        return Job(
            description=self.description,
            designer_id=self.designer_id,
            registered_by_id=self.registered_by_id,
            invoice_number=self.invoice_number,
            client_name=self.client_name,
            phone_number=self.phone_number,
            created_at=self.created_at
        )