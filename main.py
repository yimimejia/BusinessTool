import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    from app import app
    logger.info("Aplicación Flask importada correctamente")
except Exception as e:
    logger.error(f"Error al importar la aplicación: {str(e)}")
    raise

if __name__ == '__main__':
    try:
        logger.info("Iniciando servidor Flask en puerto 5000...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Error al iniciar el servidor: {str(e)}")
        raise