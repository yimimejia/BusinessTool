import os
import logging
from urllib.parse import quote
import json
from datetime import datetime

# Configuración de logging
logger = logging.getLogger(__name__)


def send_whatsapp_message(to_phone_number, message):
    """
    Sistema de WhatsApp simplificado sin Twilio
    Retorna False ya que no hay integración API
    
    Args:
        to_phone_number (str): Número de teléfono del destinatario
        message (str): Mensaje a enviar
        
    Returns:
        bool: Siempre False (sin Twilio)
    """
    logger.info(f"WhatsApp deshabilitado - Mensaje para {to_phone_number}: {message[:50]}...")
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


def generate_client_completion_message(completed_job):
    """
    Genera un mensaje de WhatsApp personalizado para notificar al cliente
    sobre la finalización de su trabajo.
    
    Args:
        completed_job: Instancia de CompletedJob con información del trabajo completado
        
    Returns:
        str: Mensaje personalizado con formato WhatsApp
    """
    try:
        # Información básica del trabajo
        client_name = completed_job.client_name or "Cliente"
        invoice_number = completed_job.invoice_number or "N/A"
        description = completed_job.description or "Trabajo de fotografía/video"
        
        # Horarios de atención completos
        business_hours = (
            "Lunes a Viernes: 8:00 AM - 6:00 PM\n"
            "Sábado y Domingo: 8:00 AM - 5:00 PM"
        )
        
        # Crear mensaje de finalización (sin contactos comerciales)
        completion_message = f"""¡Hola {client_name}! 👋

Su trabajo ya está listo para entregar.

📋 *Detalles del trabajo:*
• Factura: {invoice_number}
• Descripción: {description}

📍 *Recoger en:*
FOTO VIDEO MOJICA

⏰ *Horarios de atención:*
{business_hours}

¡Esperamos verle pronto!"""

        return completion_message
        
    except Exception as e:
        logger.error(f"Error generando mensaje de finalización: {str(e)}")
        return "Su trabajo está listo para recoger en FOTO VIDEO MOJICA. ¡Gracias!"


def generate_invoice_whatsapp_message(invoice):
    """
    Genera un mensaje de WhatsApp personalizado para envío de factura
    
    Args:
        invoice: Instancia de Invoice con información de la factura
        
    Returns:
        str: Mensaje personalizado para envío de factura
    """
    try:
        # Información básica de la factura
        client_name = invoice.client_name or "Cliente"
        invoice_number = invoice.invoice_number or "N/A"
        total_amount = invoice.total_amount or 0
        
        # Horarios de atención y contactos comerciales
        business_hours = (
            "Lunes a Viernes: 8:00 AM - 6:00 PM\n"
            "Sábado y Domingo: 8:00 AM - 5:00 PM"
        )
        
        contacts = (
            "📞 Teléfonos: (506) 2440-0000 / (506) 8888-0000\n"
            "📧 Email: info@fotovideomojica.com"
        )
        
        # Crear mensaje de factura con información comercial
        invoice_message = f"""¡Hola {client_name}! 👋

Le enviamos su factura digital.

📋 *Detalles de la factura:*
• Número: {invoice_number}
• Total: ₡{total_amount:,.2f}

📄 *Nota importante:*
Esta es una copia virtual de su factura para su conveniencia.

📍 *FOTO VIDEO MOJICA*

⏰ *Horarios de atención:*
{business_hours}

📞 *Contacto:*
{contacts}

¡Gracias por su preferencia!"""

        return invoice_message
        
    except Exception as e:
        logger.error(f"Error generando mensaje de factura: {str(e)}")
        return "Su factura ha sido generada. Gracias por su preferencia en FOTO VIDEO MOJICA."