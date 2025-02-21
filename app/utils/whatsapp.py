import os
from urllib.parse import quote
from datetime import datetime
from app.models import Job, CompletedJob

def get_whatsapp_link(phone_number, message):
    """Genera un enlace de WhatsApp con un mensaje predefinido"""
    clean_phone = phone_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    return f"https://wa.me/{clean_phone}?text={urllib.parse.quote(message)}"

def get_whatsapp_report_url(phone_number):
    """Genera un enlace de WhatsApp con el reporte de trabajos pendientes"""
    pending_jobs = Job.query.filter_by(status='pending').all()
    completed_jobs = CompletedJob.query.filter(CompletedJob.is_called == False).all()

    message = "*FOTO VIDEO MOJICA - Reporte de Trabajos*\n\n"

    if pending_jobs:
        message += "*Trabajos Pendientes:*\n"
        for job in pending_jobs:
            message += f"- {job.client_name}: {job.description}\n"

    if completed_jobs:
        message += "\n*Trabajos Listos para Entrega:*\n"
        for job in completed_jobs:
            message += f"- {job.client_name}: {job.description}\n"

    message += f"\nReporte generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    return get_whatsapp_link(phone_number, message)

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


def send_invoice_whatsapp(job, invoice_url):
    """Genera URL de WhatsApp para enviar factura"""
    return job.get_whatsapp_link(with_invoice=True, invoice_url=invoice_url)