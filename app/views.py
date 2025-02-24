from flask import Blueprint

bp = Blueprint('main', __name__)

# Import routes after creating blueprint to avoid circular imports
from app import routes
