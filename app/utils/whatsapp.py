import os
import logging
from twilio.rest import Client
from urllib.parse import quote
import json
from datetime import datetime

# Configuración de logging
logger = logging.getLogger(__name__)

# Credenciales de Twilio
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")


def send_whatsapp_message(to_phone_number, message):
    """
    Envía un mensaje de WhatsApp usando Twilio
    
    Args:
        to_phone_number (str): Número de teléfono del destinatario en formato E.164 (+1XXXXXXXXXX)
        message (str): Mensaje a enviar
        
    Returns:
        bool: True si se envió correctamente, False en caso contrario
    """
    try:
        # Verificar que existan las credenciales
        if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
            logger.error("Faltan credenciales de Twilio para enviar mensajes por WhatsApp")
            return False
        
        # Verificar y limpiar el número de teléfono del destinatario
        if not to_phone_number:
            logger.error("Número de teléfono del destinatario es nulo o vacío")
            return False
            
        clean_to_number = to_phone_number.strip() if to_phone_number else ""
        if not clean_to_number:
            logger.error("Número de teléfono del destinatario está vacío después de limpieza")
            return False
            
        if not clean_to_number.startswith('+'):
            clean_to_number = f"+{clean_to_number}"
        
        # Verificar y limpiar el número de origen (Twilio)
        if not TWILIO_PHONE_NUMBER:
            logger.error("Número de teléfono de Twilio es nulo o vacío")
            return False
            
        clean_from_number = TWILIO_PHONE_NUMBER.strip() if TWILIO_PHONE_NUMBER else ""
        if not clean_from_number:
            logger.error("Número de teléfono de Twilio está vacío después de limpieza")
            return False
            
        if not clean_from_number.startswith('+'):
            clean_from_number = f"+{clean_from_number}"
        
        # Asegurarse de que el prefijo "whatsapp:" se use correctamente
        whatsapp_from = f"whatsapp:{clean_from_number}"
        whatsapp_to = f"whatsapp:{clean_to_number}"
        
        # Crear cliente de Twilio
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Log para debugging
        logger.info(f"Intentando enviar WhatsApp desde {whatsapp_from} a {whatsapp_to}")
        
        # Enviar mensaje por WhatsApp
        message_obj = client.messages.create(
            from_=whatsapp_from,
            body=message,
            to=whatsapp_to
        )
        
        logger.info(f"Mensaje de WhatsApp enviado, SID: {message_obj.sid}")
        return True
        
    except Exception as e:
        logger.error(f"Error al enviar mensaje por WhatsApp: {str(e)}")
        return False


def generate_whatsapp_link(phone_number, message):
    """
    Genera un enlace directo a WhatsApp
    
    Args:
        phone_number (str): Número de teléfono en formato E.164 (sin el +)
        message (str): Mensaje predefinido
        
    Returns:
        str: URL para abrir WhatsApp con el mensaje predefinido
    """
    try:
        # Verificar que el número de teléfono sea válido
        if not phone_number:
            logger.error("Número de teléfono es nulo o vacío")
            return ""
            
        # Limpiar y formatear el número de teléfono
        clean_number = phone_number.strip() if phone_number else ""
        if not clean_number:
            logger.error("Número de teléfono está vacío después de limpieza")
            return ""
            
        # Eliminar el "+" inicial si existe
        if clean_number.startswith('+'):
            clean_number = clean_number[1:]
            
        # Codificar el mensaje para URL
        encoded_message = quote(message)
        
        # Construir la URL
        whatsapp_url = f"https://wa.me/{clean_number}?text={encoded_message}"
        logger.info(f"Generado enlace WhatsApp: wa.me/{clean_number}")
        return whatsapp_url
        
    except Exception as e:
        logger.error(f"Error al generar enlace de WhatsApp: {str(e)}")
        return ""


def generate_client_completion_message(job, include_invoice_url=True):
    """
    Genera un mensaje de WhatsApp para avisar que un trabajo está completado
    
    Args:
        job (CompletedJob): Trabajo completado
        include_invoice_url (bool): Indica si se debe incluir el enlace a la factura
        
    Returns:
        str: Mensaje formateado para WhatsApp
    """
    try:
        # URL pública de la factura si existe un QR code
        invoice_url = ""
        if include_invoice_url and job.qr_code:
            from flask import url_for
            from app import create_app
            
            # Crear un contexto de aplicación para generar URLs
            with create_app().test_request_context():
                invoice_url = url_for('main.view_public_invoice', qr_code=job.qr_code, _external=True)
        
        # Construir el mensaje como un solo texto (sin concatenación)
        message = f"""*FOTO VIDEO MOJICA*

Estimado/a {job.client_name},

Nos complace informarle que su trabajo ya está *LISTO* para recoger.

*Detalles del trabajo:*
📝 Descripción: {job.description}
🔢 No. Factura: {job.invoice_number}
💵 Total: ${float(job.total_amount or 0)}"""

        # Agregar enlace a la factura si está disponible
        if invoice_url:
            message += f"""

*Acceder a su factura digital:*
{invoice_url}"""

        message += f"""

*Horario de atención:*
🕐 Lunes a Viernes: 8:00 AM - 6:00 PM
🕐 Sábados y Domingos: 8:00 AM - 5:00 PM

Puede pasar a recoger su trabajo en nuestras instalaciones durante nuestro horario de atención.

Gracias por confiar en nosotros.
Que Dios le bendiga.

*FOTO VIDEO MOJICA*"""
        return message
    except Exception as e:
        logger.error(f"Error al generar mensaje de finalización: {str(e)}")
        return "Su trabajo en FOTO VIDEO MOJICA está listo. Para verlo online o contactarnos llame al +1 (809) 246-0263. ¡Gracias por su preferencia!"


def get_whatsapp_report_url(phone_number):
    """
    Genera una URL para enviar un reporte de trabajos pendientes por WhatsApp
    
    Args:
        phone_number (str): Número de teléfono en formato E.164
        
    Returns:
        str: URL de WhatsApp para enviar el reporte
    """
    try:
        from flask import current_app as app
        from app.models import Job, CompletedJob, PendingJob
        
        # Contar los diferentes tipos de trabajos
        pending_count = Job.query.filter_by(status='pending').count()
        completed_count = CompletedJob.query.count()
        approval_count = PendingJob.query.count()
        
        # Generar fecha actual formateada
        current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        # Mensaje con el reporte resumido
        message = f"""*FOTO VIDEO MOJICA - REPORTE DE ESTADO*
Fecha: {current_date}

*Resumen:*
📝 Trabajos en proceso: {pending_count}
✅ Trabajos completados: {completed_count}
⏳ Pendientes de aprobación: {approval_count}

*IMPORTANTE:* 
No responda a este número automático.
Para cualquier consulta, contacte directamente:
*+1 (809) 246-0263*

FOTO VIDEO MOJICA
"""
        
        # Generar el enlace
        return generate_whatsapp_link(phone_number, message)
        
    except Exception as e:
        logger.error(f"Error al generar URL de reporte: {str(e)}")
        return ""