from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from sqlalchemy.orm import validates
import re
import base64
import json
import random
import urllib.parse

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256))
    is_admin = db.Column(db.Boolean, default=False)
    is_supervisor = db.Column(db.Boolean, default=False)
    is_designer = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    remember_token = db.Column(db.String(100))
    permanent_session = db.Column(db.Boolean, default=False)

    assigned_jobs = db.relationship('Job', 
                                  foreign_keys='Job.designer_id',
                                  backref='designer',
                                  lazy='dynamic')
    registered_jobs = db.relationship('Job', 
                                    foreign_keys='Job.registered_by_id',
                                    backref='registered_by')
    activities = db.relationship('ActivityLog', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    webauthn_credentials = db.relationship('WebAuthnCredential', backref='user')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_staff(self):
        return self.is_admin or self.is_supervisor

    def get_unread_messages_count(self):
        return Message.query.filter_by(recipient_id=self.id, is_read=False).count()

    def get_unread_messages_count_from(self, sender_id):
        return Message.query.filter_by(
            recipient_id=self.id,
            sender_id=sender_id,
            is_read=False
        ).count()

    def get_messages(self):
        return Message.query.filter(
            (Message.recipient_id == self.id) | (Message.sender_id == self.id)
        ).order_by(Message.created_at.desc()).all()

    @property
    def can_manage_users(self):
        return self.is_admin

    @property
    def can_delete_jobs(self):
        return self.is_admin

    @property
    def can_authorize_jobs(self):
        """Determina si el usuario puede autorizar trabajos"""
        return self.is_admin or self.is_supervisor

    def get_pending_jobs(self):
        return Job.query.filter_by(designer_id=self.id, status='pending').all()

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, nullable=False)  # ID del trabajo relacionado
    job_type = db.Column(db.String(20), nullable=False)  # 'job' o 'completed_job'
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    deposit_amount = db.Column(db.Numeric(10, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    issued_at = db.Column(db.DateTime)
    qr_code = db.Column(db.String(100), unique=True)
    access_token = db.Column(db.String(100), unique=True)
    token_expiry = db.Column(db.DateTime)

    def is_valid_token(self):
        """Verifica si el token de acceso es válido"""
        if not self.access_token or not self.token_expiry:
            return False
        return datetime.utcnow() <= self.token_expiry

    def generate_qr_code(self):
        if not self.qr_code:
            unique_id = f"invoice-{self.id}-{self.invoice_number}-{int(datetime.utcnow().timestamp())}"
            self.qr_code = base64.urlsafe_b64encode(unique_id.encode()).decode()
        return self.qr_code

    def get_job(self):
        """Obtiene el trabajo relacionado basado en job_type"""
        if self.job_type == 'job':
            return Job.query.get(self.job_id)
        elif self.job_type == 'completed_job':
            return CompletedJob.query.get(self.job_id)
        return None

    @property
    def remaining_amount(self):
        """Calcula el monto restante"""
        return float(self.total_amount or 0) - float(self.deposit_amount or 0)

class WebAuthnCredential(db.Model):
    __tablename__ = 'webauthn_credentials'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    credential_id = db.Column(db.String(250), unique=True, nullable=False)
    public_key = db.Column(db.Text, nullable=False)
    sign_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    name = db.Column(db.String(100))

    def get_credential_data(self):
        return {
            'credentialId': self.credential_id,
            'publicKey': self.public_key,
            'signCount': self.sign_count,
        }

class Job(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    client_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20))
    description = db.Column(db.Text, nullable=False)
    designer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    registered_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')  # pending, completed, delivered
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    deposit_amount = db.Column(db.Numeric(10, 2), default=0)
    qr_code = db.Column(db.String(100), unique=True)
    tags = db.Column(db.String(200))

    @validates('phone_number')
    def validate_phone_number(self, key, phone_number):
        if not phone_number:
            return phone_number

        cleaned_number = re.sub(r'[^\d]', '', phone_number)

        if len(cleaned_number) == 10:
            cleaned_number = '1' + cleaned_number
        elif len(cleaned_number) > 11 or len(cleaned_number) < 10:
            raise ValueError('El número de teléfono debe tener 10 dígitos')

        if not cleaned_number.startswith('1'):
            raise ValueError('El número debe incluir el código de área (+1)')

        formatted_number = f'+{cleaned_number[0]}-{cleaned_number[1:4]}-{cleaned_number[4:]}'
        return formatted_number

    def generate_qr_code(self):
        """Genera un código QR único para el trabajo"""
        if not self.qr_code:
            # Usar FVM como prefijo seguido del ID del trabajo
            unique_id = f"FVM-{self.id}"
            self.qr_code = base64.urlsafe_b64encode(unique_id.encode()).decode()
        return self.qr_code

    def get_whatsapp_link(self, with_invoice=False, invoice_url=None):
        if not self.phone_number:
            return None

        phone = re.sub(r'[^\d]', '', self.phone_number)

        if with_invoice and invoice_url:
            message = f"""*FOTO VIDEO MOJICA*
¡Gracias por su preferencia!

*Detalles de su trabajo:*
Cliente: {self.client_name}
Factura: {self.invoice_number}
Descripción: {self.description}
Total: ${self.total_amount if self.total_amount else '0'}
Abono: ${self.deposit_amount if self.deposit_amount else '0'}

Para ver su factura digital y código QR, haga clic aquí:
{invoice_url}"""
        else:
            message = f"Hola {self.client_name}, sus fotos están listas para ser revisadas."

        return f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"

    @property
    def can_send_photos(self):
        return self.total_amount and self.deposit_amount and self.total_amount <= self.deposit_amount

    def to_qr_data(self):
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

class Photo(db.Model):
    __tablename__ = 'photos'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime)

    job = db.relationship('Job', backref='photos')

class AdminAction(db.Model):
    __tablename__ = 'admin_actions'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)  # complete_job, send_photos, etc
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)

    job = db.relationship('Job')
    user = db.relationship('User')

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    photos = db.Column(db.Text)
    token = db.Column(db.String(100), unique=True)  # Para enlaces temporales
    token_expiry = db.Column(db.DateTime)  # Fecha de expiración del token

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='received_messages')

    def set_photos(self, photo_paths):
        self.photos = json.dumps(photo_paths)

    def get_photos(self):
        return json.loads(self.photos) if self.photos else []

    @property
    def is_photo_message(self):
        return bool(self.photos)

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
        message = f"Hay {pending_count} trabajos pendientes en el sistema"
        notification = cls(
            user_id=admin.id,
            message=message,
            type='admin_alert'
        )
        db.session.add(notification)
        db.session.commit()
        return notification

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))

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
    qr_code = db.Column(db.String(100), unique=True)
    total_amount = db.Column(db.Numeric(10, 2))
    deposit_amount = db.Column(db.Numeric(10, 2))
    photos = db.Column(db.Text)  # JSON string con las rutas de las fotos
    temp_token = db.Column(db.String(100))  # Token temporal para compartir fotos
    token_expiry = db.Column(db.DateTime)  # Fecha de expiración del token

    designer = db.relationship('User', foreign_keys=[designer_id])
    registered_by = db.relationship('User', foreign_keys=[registered_by_id])

    def generate_qr_code(self):
        """Genera un código QR único para el trabajo completado"""
        if not self.qr_code:
            # Usar FVM como prefijo seguido del ID del trabajo
            unique_id = f"FVM-{self.id}"
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
    qr_code = db.Column(db.String(100))  
    delivery_method = db.Column(db.String(50), default='manual')  # 'manual' o 'qr'

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
    photos = db.Column(db.Text)  
    original_job_id = db.Column(db.Integer)
    tags = db.Column(db.String(200))
    message = db.Column(db.Text)

    designer = db.relationship('User', foreign_keys=[designer_id])
    registered_by = db.relationship('User', foreign_keys=[registered_by_id])

    @validates('phone_number')
    def validate_phone_number(self, key, phone_number):
        if not phone_number:
            return phone_number

        cleaned_number = re.sub(r'[^\d]', '', phone_number)

        if len(cleaned_number) == 10:
            cleaned_number = '1' + cleaned_number
        elif len(cleaned_number) > 11 or len(cleaned_number) < 10:
            raise ValueError('El número de teléfono debe tener 10 dígitos')

        if not cleaned_number.startswith('1'):
            raise ValueError('El número debe incluir el código de área (+1)')

        formatted_number = f'+{cleaned_number[0]}-{cleaned_number[1:4]}-{cleaned_number[4:]}'
        return formatted_number

    def generate_qr_code(self):
        if not self.qr_code:
            unique_id = f"{int(datetime.utcnow().timestamp())}-{self.id}-{random.randint(1000, 9999)}"
            self.qr_code = base64.urlsafe_b64encode(unique_id.encode()).decode()
        return self.qr_code

    def to_job(self):
        return Job(
            description=self.description,
            designer_id=self.designer_id,
            registered_by_id=self.registered_by_id,
            invoice_number=self.invoice_number,
            client_name=self.client_name,
            phone_number=self.phone_number,
            created_at=self.created_at,
            tags=self.tags,
            total_amount=self.total_amount,
            deposit_amount=self.deposit_amount
        )