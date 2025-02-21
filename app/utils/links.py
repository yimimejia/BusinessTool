
from datetime import datetime, timedelta
import jwt
from flask import current_app
import os

SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key')

def generate_temporary_link(photos, expiration_days=3):
    expiration = datetime.utcnow() + timedelta(days=expiration_days)
    payload = {
        'photos': photos,
        'exp': expiration
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token

def verify_temporary_link(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload['photos']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
