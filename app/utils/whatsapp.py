import os
from urllib.parse import quote
from datetime import datetime
from app.models import Job

def get_pending_jobs_text():
    """Genera el texto del reporte de trabajos pendientes"""
    jobs = Job.query.filter_by(status='pending').all()

    if not jobs:
        return "No hay trabajos pendientes"

    text = "*FOTO VIDEO MOJICA - Trabajos Pendientes*\n\n"
    for job in jobs:
        text += f"*Cliente:* {job.client_name}\n"
        text += f"*Factura:* {job.invoice_number}\n"
        text += f"*Descripción:* {job.description}\n"
        text += f"*Teléfono:* {job.phone_number}\n\n"

    text += f"_Reporte generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"
    return text

def get_whatsapp_url(phone_number, message):
    """Genera una URL de WhatsApp con mensaje personalizado"""
    clean_number = ''.join(filter(str.isdigit, phone_number))
    if not clean_number.startswith('1'):
        clean_number = '1' + clean_number
    return f"https://wa.me/{clean_number}?text={quote(message)}"

def send_invoice_whatsapp(job, invoice_url):
    """Genera URL de WhatsApp para enviar factura"""
    return job.get_whatsapp_link(with_invoice=True, invoice_url=invoice_url)
import urllib.parse

def generate_whatsapp_link(phone_number, message):
    """
    Generate WhatsApp link with pre-filled message
    """
    # Remove any non-numeric characters from phone number
    clean_number = ''.join(filter(str.isdigit, phone_number))
    
    # Encode message for URL
    encoded_message = urllib.parse.quote(message)
    
    # Generate WhatsApp link
    return f"https://wa.me/{clean_number}?text={encoded_message}"
