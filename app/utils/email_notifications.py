import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from app.models import Job, CompletedJob
from datetime import datetime

def get_pending_jobs_html():
    jobs = Job.query.filter_by(is_completed=False).all()

    if not jobs:
        return "<p>No hay trabajos pendientes</p>"

    html = """
    <h2>Trabajos Pendientes</h2>
    <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f8f9fa;">
            <th>Cliente</th>
            <th>Descripción</th>
            <th>Diseñador</th>
            <th>Factura</th>
        </tr>
    """

    for job in jobs:
        html += f"""
        <tr>
            <td>{job.client_name}</td>
            <td>{job.description}</td>
            <td>{job.designer.name if job.designer else 'No asignado'}</td>
            <td>{job.invoice_number}</td>
        </tr>
        """

    html += "</table>"
    return html

def get_pending_calls_html():
    jobs = CompletedJob.query.filter_by(is_called=False).all()

    if not jobs:
        return "<p>No hay trabajos pendientes por llamar</p>"

    html = """
    <h2>Trabajos Pendientes por Llamar</h2>
    <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
        <tr style="background-color: #f8f9fa;">
            <th>Cliente</th>
            <th>Teléfono</th>
            <th>Descripción</th>
            <th>Completado</th>
        </tr>
    """

    for job in jobs:
        completed_date = job.completed_at.strftime('%Y-%m-%d') if job.completed_at else 'N/A'
        html += f"""
        <tr>
            <td>{job.client_name}</td>
            <td>{job.phone_number}</td>
            <td>{job.description}</td>
            <td>{completed_date}</td>
        </tr>
        """

    html += "</table>"
    return html

def send_daily_report():
    try:
        api_key = os.environ.get('SENDGRID_API_KEY')
        if not api_key:
            print("Error: SENDGRID_API_KEY no está configurada")
            return False

        sg = SendGridAPIClient(api_key)

        # Destinatarios
        recipients = ['fotovideomojica29@gmail.com', 'yimimejia30@gmail.com']

        # Contenido del correo
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h1 style="color: #333;">Reporte Diario de Trabajos - {datetime.now().strftime('%Y-%m-%d')}</h1>

            {get_pending_jobs_html()}

            <br><br>

            {get_pending_calls_html()}

            <p style="color: #666; font-size: 0.9em; margin-top: 20px;">
                Este es un correo automático, por favor no responder.
            </p>
        </body>
        </html>
        """

        # Enviar a cada destinatario
        for recipient in recipients:
            message = Mail(
                from_email=Email('notificaciones@fotovideomojica.com', 'FOTO VIDEO MOJICA'),
                to_emails=To(recipient),
                subject='Reporte Diario de Trabajos Pendientes',
                html_content=html_content
            )

            response = sg.send(message)
            if response.status_code not in [200, 201, 202]:
                print(f"Error enviando a {recipient}: Status code {response.status_code}")
                return False

        return True
    except Exception as e:
        print(f"Error enviando notificación: {str(e)}")
        return False