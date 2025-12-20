# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import requests
import os
from   flask_migrate import Migrate
from   flask_minify  import Minify
from   flask_cors import CORS
from   sys import exit
import mysql.connector
from dotenv import load_dotenv

# Cargar las variables de entorno desde .env ANTES de importar la configuración
load_dotenv()

from apps.config import config_dict
from apps import create_app, db

# WARNING: Don't run with debug turned on in production!
DEBUG = (os.getenv('DEBUG', 'False') == 'True')

# The configuration
get_config_mode = 'Debug' if DEBUG else 'Production'

try:

    # Load the configuration using the default values
    app_config = config_dict[get_config_mode.capitalize()]

except KeyError:
    exit('Error: Invalid <config_mode>. Expected values [Debug, Production] ')

app = create_app(app_config)
Migrate(app, db)

# Configurar CORS para permitir peticiones desde React
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5173", "http://127.0.0.1:5173", "http://148.230.72.8:5173"],
        "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

if not DEBUG:
    Minify(app=app, html=True, js=False, cssless=False)
    
if DEBUG:
    app.logger.info('DEBUG            = ' + str(DEBUG)             )
    app.logger.info('Page Compression = ' + 'FALSE' if DEBUG else 'TRUE' )
    app.logger.info('DBMS             = ' + app_config.SQLALCHEMY_DATABASE_URI)
    app.logger.info('ASSETS_ROOT      = ' + app_config.ASSETS_ROOT )

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)
