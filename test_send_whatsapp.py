"""
Script para probar el envío real de un mensaje de WhatsApp usando Twilio
"""
import os
import sys
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Añadir directorio actual al path
sys.path.append('.')

def test_send_whatsapp():
    """Prueba el envío de un mensaje de WhatsApp usando Twilio"""
    try:
        # Importar función de envío
        from app.utils.whatsapp import send_whatsapp_message
        
        # Verificar credenciales
        twilio_account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        twilio_auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        twilio_phone_number = os.environ.get("TWILIO_PHONE_NUMBER")
        
        if not all([twilio_account_sid, twilio_auth_token, twilio_phone_number]):
            logger.error("Faltan credenciales de Twilio. Verifica las variables de entorno.")
            return
        
        # Número de teléfono para prueba (debe estar en formato E.164)
        test_phone_number = input("Ingresa el número de teléfono para la prueba (formato E.164, ej: +18091234567): ")
        if not test_phone_number:
            logger.error("No se ingresó un número de teléfono para la prueba")
            return
        
        # Mensaje de prueba
        test_message = f"""*FOTO VIDEO MOJICA - MENSAJE DE PRUEBA*
¡Hola!

Este es un mensaje de prueba enviado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}.

*Detalles técnicos:*
📱 Enviado a: {test_phone_number}
📝 Método: Twilio WhatsApp API
🔧 Propósito: Verificar que se reciba como un único mensaje

*IMPORTANTE:* 
No responda a este número automático.
Para cualquier consulta, contáctenos al:
*+1 (809) 246-0263*

FOTO VIDEO MOJICA
"""
        
        # Enviar mensaje
        logger.info(f"Enviando mensaje de prueba a {test_phone_number}...")
        result = send_whatsapp_message(test_phone_number, test_message)
        
        if result:
            logger.info("✅ Mensaje enviado exitosamente")
            print("\n¡Mensaje enviado! Verifica en tu teléfono si se recibió correctamente como un solo mensaje.")
        else:
            logger.error("❌ Error al enviar el mensaje")
            print("\nHubo un error al enviar el mensaje. Revisa los logs para más detalles.")
            
    except Exception as e:
        logger.error(f"Error al ejecutar la prueba: {str(e)}")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    print("Test de envío de WhatsApp usando Twilio")
    print("-" * 50)
    test_send_whatsapp()