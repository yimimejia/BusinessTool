import os
from datetime import datetime
from app.models import Job
from urllib.parse import quote
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def generate_pdf_report():
    """Genera un archivo PDF con el reporte de trabajos pendientes"""
    pdf_path = 'static/reports/pending_jobs.pdf'
    os.makedirs('static/reports', exist_ok=True)

    # Crear PDF
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "TRABAJOS PENDIENTES")

    jobs = Job.query.filter_by(is_completed=False).all()
    y = 700

    for job in jobs:
        if y < 100:  # Nueva página si no hay espacio
            c.showPage()
            y = 750

        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"Cliente: {job.client_name}")
        c.setFont("Helvetica", 10)
        y -= 20
        c.drawString(50, y, f"Factura: {job.invoice_number}")
        y -= 20
        c.drawString(50, y, f"Descripción: {job.description}")
        y -= 20
        c.drawString(50, y, f"Teléfono: {job.phone_number}")
        y -= 40

    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, 50, f"Reporte generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.save()

    return pdf_path

def get_whatsapp_report_url(phone_number):
    """Genera una URL de WhatsApp con el archivo adjunto"""
    # Generar el PDF
    pdf_path = generate_pdf_report()

    # Mensaje simple para acompañar el archivo
    message = "Reporte de trabajos pendientes adjunto."
    encoded_message = quote(message)

    # Limpiar el número de teléfono
    clean_number = ''.join(filter(str.isdigit, phone_number))

    # Retornar la URL de WhatsApp
    # Nota: WhatsApp Web no permite adjuntar archivos directamente por URL,
    # por lo que incluiremos un enlace al PDF en el mensaje
    base_url = os.environ.get('BASE_URL', 'https://fotovideomojica.com')
    pdf_url = f"{base_url}/{pdf_path}"

    return f"https://wa.me/{clean_number}?text={encoded_message}%0A%0ADescargar%20PDF:%20{quote(pdf_url)}"

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

def get_pending_jobs_text():
    """Genera el texto del reporte de trabajos pendientes"""
    jobs = Job.query.filter_by(is_completed=False).all()

    if not jobs:
        return "No hay trabajos pendientes"

    text = "*TRABAJOS PENDIENTES*\n\n"
    for job in jobs:
        text += f"*Cliente:* {job.client_name}\n"
        text += f"*Factura:* {job.invoice_number}\n"
        text += f"*Descripción:* {job.description}\n"
        text += f"*Teléfono:* {job.phone_number}\n\n"

    text += "_Reporte generado: " + datetime.now().strftime('%d/%m/%Y %H:%M') + "_"
    return text