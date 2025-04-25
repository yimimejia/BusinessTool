import os
import logging
from twilio.rest import Client
from urllib.parse import quote

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
        
        # Enviar mensaje por WhatsApp
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


def generate_client_completion_message(job):
    """
    Genera un mensaje de WhatsApp para avisar que un trabajo está completado
    
    Args:
        job (CompletedJob): Trabajo completado
        
    Returns:
        str: Mensaje formateado para WhatsApp
    """
    try:
        message = f"""*FOTO VIDEO MOJICA*
¡Hola {job.client_name}!

Nos complace informarle que su trabajo ya está *LISTO* ✅

*Detalles:*
📝 Descripción: {job.description}
🔢 Factura: {job.invoice_number}
💵 Total: ${float(job.total_amount or 0)}

Puede pasar a recogerlo en nuestras instalaciones en horario de atención.
¡Gracias por su preferencia!

FOTO VIDEO MOJICA
"""
        return message
    except Exception as e:
        logger.error(f"Error al generar mensaje de finalización: {str(e)}")
        return "Su trabajo en FOTO VIDEO MOJICA está listo. ¡Gracias por su preferencia!"