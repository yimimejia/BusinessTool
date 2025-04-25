#!/usr/bin/env python3
"""
Utilidad para probar la configuración de Twilio
Este script verifica que las credenciales de Twilio estén bien configuradas.
"""

import os
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_twilio_config():
    """
    Verifica que las credenciales de Twilio estén configuradas correctamente
    y que se pueda conectar a la API de Twilio.
    """
    # Credenciales de Twilio
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    phone_number = os.environ.get("TWILIO_PHONE_NUMBER")
    
    # Verificar que existan todas las credenciales
    if not all([account_sid, auth_token, phone_number]):
        logger.error("❌ Error: Faltan credenciales de Twilio")
        missing = []
        if not account_sid:
            missing.append("TWILIO_ACCOUNT_SID")
        if not auth_token:
            missing.append("TWILIO_AUTH_TOKEN")
        if not phone_number:
            missing.append("TWILIO_PHONE_NUMBER")
        logger.error(f"   Credenciales faltantes: {', '.join(missing)}")
        return False
    
    # Verificar la conexión a Twilio
    try:
        client = Client(account_sid, auth_token)
        
        # Obtener información de la cuenta para verificar conexión
        account = client.api.accounts(account_sid).fetch()
        logger.info(f"✅ Conexión exitosa a la cuenta Twilio: {account.friendly_name}")
        
        # Verificar que el número de teléfono exista en la cuenta
        try:
            # Eliminar el "+" inicial si existe
            if phone_number.startswith('+'):
                phone_to_check = phone_number
            else:
                phone_to_check = f"+{phone_number}"
                
            # Intentar obtener detalles del número
            incoming_phone = client.incoming_phone_numbers.list(
                phone_number=phone_to_check
            )
            
            if incoming_phone:
                logger.info(f"✅ Número de teléfono Twilio verificado: {phone_number}")
            else:
                logger.warning(f"⚠️ El número {phone_number} no parece estar en tu cuenta Twilio.")
                logger.warning("   Esto podría causar errores al enviar mensajes.")
                
        except TwilioRestException as phone_err:
            logger.warning(f"⚠️ No se pudo verificar el número de teléfono: {str(phone_err)}")
        
        return True
        
    except TwilioRestException as e:
        logger.error(f"❌ Error al conectar con Twilio: {str(e)}")
        if "authenticate" in str(e).lower():
            logger.error("   Las credenciales de Twilio son incorrectas.")
        return False
    
    except Exception as e:
        logger.error(f"❌ Error desconocido: {str(e)}")
        return False

if __name__ == "__main__":
    print("Verificando configuración de Twilio...")
    if verify_twilio_config():
        print("\n✅ La configuración de Twilio parece correcta. WhatsApp debería funcionar.")
    else:
        print("\n❌ Hay problemas con la configuración de Twilio. Revisa los errores arriba.")