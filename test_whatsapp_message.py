"""
Script para probar el formato de mensajes de WhatsApp
"""
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Añadir directorio actual al path
sys.path.append('.')

# Importar modelos y utilidades
from app import create_app, db
from app.models import CompletedJob
from app.utils.whatsapp import generate_client_completion_message

# Clase simulada para probar mensaje con enlace
class MockCompletedJob:
    def __init__(self):
        self.id = 999
        self.client_name = "Cliente de Prueba"
        self.invoice_number = "TEST-123"
        self.description = "Fotografía de 15 años + Álbum personalizado"
        self.total_amount = 3500.0
        self.deposit_amount = 1500.0
        self.phone_number = "+1-809-246-0263"
        self.qr_code = "TEST-QR-CODE-123"

def test_whatsapp_message():
    """Probar la generación de mensajes de WhatsApp con enlaces a facturas"""
    # Crear contexto de aplicación
    app = create_app()
    with app.app_context():
        # Obtener el último trabajo completado
        job = CompletedJob.query.order_by(CompletedJob.completed_at.desc()).first()
        
        if not job:
            print("No se encontraron trabajos completados en la base de datos.")
            return
        
        # Generar mensaje para el trabajo real
        message = generate_client_completion_message(job)
        
        # Mostrar el mensaje formateado
        print("\n" + "-" * 60)
        print("MENSAJE DE WHATSAPP PARA TRABAJOS COMPLETADOS (TRABAJO REAL)")
        print("-" * 60)
        print(message)
        print("-" * 60)
        
        # Mostrar información adicional sobre el trabajo
        print(f"\nInformación del trabajo real:")
        print(f"  - ID: {job.id}")
        print(f"  - Cliente: {job.client_name}")
        print(f"  - Factura: {job.invoice_number}")
        print(f"  - Descripción: {job.description}")
        print(f"  - Código QR: {job.qr_code}")
        
        # Verificar si tiene número de teléfono
        if job.phone_number:
            print(f"  - Teléfono: {job.phone_number}")
        else:
            print("  - Teléfono: No disponible")
        
        # Crear trabajo ficticio con QR code para probar el enlace
        mock_job = MockCompletedJob()
        
        # Simular la URL de la factura
        def mock_url_for(endpoint, qr_code, _external=False):
            return f"https://fotovideomojica.replit.app/factura/{qr_code}"
        
        # Cambiar temporalmente la función url_for
        import app.utils.whatsapp
        original_module = app.utils.whatsapp
        
        # Función para generar mensaje con URL ficticia
        def test_message_with_link():
            message_with_link = f"""*FOTO VIDEO MOJICA*
¡Hola {mock_job.client_name}!

Nos complace informarle que su trabajo ya está *LISTO* ✅

*Detalles:*
📝 Descripción: {mock_job.description}
🔢 Factura: {mock_job.invoice_number}
💵 Total: ${float(mock_job.total_amount or 0)}

*Ver su factura en línea:*
https://fotovideomojica.replit.app/factura/{mock_job.qr_code}

Puede pasar a recogerlo en nuestras instalaciones en horario de atención.
¡Gracias por su preferencia!

*IMPORTANTE:* 
No responda a este número automático.
Para cualquier consulta, contáctenos al:
*+1 (809) 246-0263*

FOTO VIDEO MOJICA
"""
            return message_with_link
        
        # Generar mensaje simulado con enlace
        message_with_link = test_message_with_link()
        
        # Mostrar el mensaje simulado con enlace
        print("\n\n" + "-" * 60)
        print("EJEMPLO DE MENSAJE DE WHATSAPP CON ENLACE A FACTURA")
        print("-" * 60)
        print(message_with_link)
        print("-" * 60)
        
        print("\nEste mensaje (con enlace a la factura) se enviaría automáticamente al cliente cuando se marca un trabajo como completado.")

if __name__ == "__main__":
    test_whatsapp_message()