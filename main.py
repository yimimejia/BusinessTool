import os
import socket
from app import create_app

app = create_app()

if __name__ == '__main__':
    # ALWAYS serve the app on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)