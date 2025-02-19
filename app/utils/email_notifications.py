import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email
from app.models import Job, CompletedJob
from datetime import datetime

def get_pending_jobs_html():
    jobs = Job.query.filter_by(is_completed=False).all()
    
    html = """
    <h2>Trabajos Pendientes</h2>
    <table border="1" cellpadding="5" style="border-collapse: collapse;">
        <tr>
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
            <td>{job.designer.name}</td>
            <td>{job.invoice_number}</td>
        </tr>
        """
    
    html += "</table>"
    return html

def get_pending_calls_html():
    jobs = CompletedJob.query.filter_by(is_called=False).all()
    
    html = """
    <h2>Trabajos Pendientes por Llamar</h2>
    <table border="1" cellpadding="5" style="border-collapse: collapse;">
        <tr>
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
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        
        # Destinatarios
        recipients = ['fotovideomojica29@gmail.com', 'yimimejia30@gmail.com']
        
        # Contenido del correo
        html_content = f"""
        <html>
        <body>
            <h1>Reporte Diario de Trabajos - {datetime.now().strftime('%Y-%m-%d')}</h1>
            {get_pending_jobs_html()}
            <br><br>
            {get_pending_calls_html()}
        </body>
        </html>
        """
        
        # Enviar a cada destinatario
        for recipient in recipients:
            message = Mail(
                from_email=Email('notificaciones@fotovideomojica.com', 'FOTO VIDEO MOJICA'),
                to_emails=recipient,
                subject='Reporte Diario de Trabajos Pendientes',
                html_content=html_content
            )
            
            sg.send(message)
            
        return True
    except Exception as e:
        print(f"Error enviando notificación: {str(e)}")
        return False
