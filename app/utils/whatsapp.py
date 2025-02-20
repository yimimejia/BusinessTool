import os
from datetime import datetime
from app.models import Job
from urllib.parse import quote

def get_pending_jobs_text():
    """Genera el texto del reporte de trabajos pendientes"""
    jobs = Job.query.filter_by(is_completed=False).all()

    if not jobs:
        return "No hay trabajos pendientes"

    text = "*TRABAJOS PENDIENTES* 📋\n\n"
    for job in jobs:
        text += f"*Cliente:* {job.client_name}\n"
        text += f"*Factura:* {job.invoice_number}\n"
        text += f"*Descripción:* {job.description}\n"
        text += f"*Teléfono:* {job.phone_number}\n"
        text += "-------------------\n\n"

    text += f"\n_Reporte generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"
    return text

def get_whatsapp_report_url(phone_number):
    """Genera una URL de WhatsApp con el reporte de trabajos pendientes"""
    message = get_pending_jobs_text()
    # Codificar el mensaje para URL
    encoded_message = quote(message)
    # Limpiar el número de teléfono (eliminar +, espacios y guiones)
    clean_number = ''.join(filter(str.isdigit, phone_number))
    return f"https://wa.me/{clean_number}?text={encoded_message}"

def send_whatsapp_report(to_numbers):
    """Envía el reporte por WhatsApp generando una URL"""
    sent_urls = []
    for number in to_numbers:
        try:
            url = get_whatsapp_report_url(number)
            sent_urls.append(url)
        except Exception as e:
            print(f"Error generando URL para {number}: {str(e)}")
    return len(sent_urls) > 0