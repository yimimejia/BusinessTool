#!/usr/bin/env python3
"""
Script para probar las notificaciones Firebase
"""
import os
import requests
import json

def test_firebase_notification():
    """Probar envío de notificación Firebase directamente"""
    
    # Configuración
    server_key = os.environ.get('GOOGLE_API_KEY')
    if not server_key:
        print("Error: GOOGLE_API_KEY no está configurada")
        return False
    
    fcm_url = 'https://fcm.googleapis.com/fcm/send'
    
    headers = {
        'Authorization': f'key={server_key}',
        'Content-Type': 'application/json',
    }
    
    # Enviar a un topic para probar (legacy API)
    payload = {
        'to': '/topics/all_users',
        'notification': {
            'title': 'Prueba de Firebase',
            'body': 'Si ves esto, Firebase está funcionando correctamente',
            'icon': '/static/icons/logo-192x192.png',
            'tag': 'test-notification',
            'click_action': 'FCM_PLUGIN_ACTIVITY',
            'sound': 'default'
        },
        'data': {
            'type': 'test',
            'timestamp': '2025-08-05T18:53:00Z'
        }
    }
    
    try:
        print(f"Enviando notificación a FCM...")
        print(f"URL: {fcm_url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(fcm_url, headers=headers, json=payload)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Notificación enviada exitosamente: {result}")
            return True
        else:
            print(f"Error al enviar notificación: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Error al enviar notificación Firebase: {str(e)}")
        return False

if __name__ == "__main__":
    print("=== Test de Notificaciones Firebase ===")
    success = test_firebase_notification()
    if success:
        print("✅ Test exitoso")
    else:
        print("❌ Test falló")