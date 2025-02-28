from app import app
import logging
import sys

# Configurar logging detallado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    try:
        logger.info("Iniciando servidor Flask...")
        logger.debug("Configuración actual: DEBUG=%s", app.config.get('DEBUG'))
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Error crítico al iniciar el servidor: {str(e)}", exc_info=True)
        raise