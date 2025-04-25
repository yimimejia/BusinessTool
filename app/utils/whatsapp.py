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
            
        # Asegurar que el número tenga el formato correcto
        if not to_phone_number.startswith('+'):
            to_phone_number = f"+{to_phone_number}"
        
        # Crear cliente de Twilio
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Enviar mensaje por WhatsApp - asegurando que se envíe como un solo mensaje
        message = client.messages.create(
            from_=f"whatsapp:{TWILIO_PHONE_NUMBER}",
            body=message,
            to=f"whatsapp:{to_phone_number}"
        )
        
        logger.info(f"Mensaje de WhatsApp enviado, SID: {message.sid}")
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
        # Eliminar el "+" inicial si existe
        if phone_number.startswith('+'):
            phone_number = phone_number[1:]
            
        # Codificar el mensaje para URL
        encoded_message = quote(message)
        
        # Construir la URL
        whatsapp_url = f"https://wa.me/{phone_number}?text={encoded_message}"
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
¡Hola {job.client_name}!

Nos complace informarle que su trabajo ya está *LISTO* ✅

*Detalles:*
📝 Descripción: {job.description}
🔢 Factura: {job.invoice_number}
💵 Total: ${float(job.total_amount or 0)}"""

        # Agregar enlace a la factura si está disponible
        if invoice_url:
            message += f"""

*Ver su factura en línea:*
{invoice_url}"""

        message += f"""

Puede pasar a recogerlo en nuestras instalaciones en horario de atención.
¡Gracias por su preferencia!

*IMPORTANTE:* 
No responda a este número automático.
Para cualquier consulta, contáctenos al:
*+1 (809) 246-0263*

FOTO VIDEO MOJICA
"""
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