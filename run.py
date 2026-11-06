# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import requests
import os
from   flask_migrate import Migrate
# from   flask_minify  import Minify  # Disabled: incompatible with Python 3.14
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

# Configurar handlers de JWT para devolver JSON en API endpoints
from flask_jwt_extended import JWTManager
from flask import jsonify
from apps import jwt

# Handlers personalizados para JWT
@jwt.unauthorized_loader
def unauthorized_callback(callback):
    """Cuando no hay token o es inválido"""
    return jsonify({
        'success': False,
        'error': 'Token de autenticación requerido',
        'msg': 'Missing Authorization Header'
    }), 401

@jwt.invalid_token_loader
def invalid_token_callback(callback):
    """Cuando el token es inválido"""
    return jsonify({
        'success': False,
        'error': 'Token de autenticación inválido',
        'msg': 'Invalid token'
    }), 422

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    """Cuando el token ha expirado"""
    return jsonify({
        'success': False,
        'error': 'Token de autenticación expirado',
        'msg': 'Token has expired'
    }), 401

@jwt.revoked_token_loader
def revoked_token_callback(jwt_header, jwt_payload):
    """Cuando el token ha sido revocado"""
    return jsonify({
        'success': False,
        'error': 'Token de autenticación revocado',
        'msg': 'Token has been revoked'
    }), 401

# Configurar CORS para permitir peticiones desde React y portal de pacientes
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

if not DEBUG:
    pass  # Minify disabled: incompatible with Python 3.14
    
if DEBUG:
    app.logger.info('DEBUG            = ' + str(DEBUG)             )
    app.logger.info('Page Compression = ' + 'FALSE' if DEBUG else 'TRUE' )
    app.logger.info('DBMS             = ' + app_config.SQLALCHEMY_DATABASE_URI)
    app.logger.info('ASSETS_ROOT      = ' + app_config.ASSETS_ROOT )

# PACS patient listener (DISABLED)
# Uncomment to re-enable automatic portal user creation via NOTIFY/LISTEN.
# try:
#     from apps.home.services.pacs_patient_listener import start_pacs_listener
#     start_pacs_listener()
# except Exception as e:
#     print(f"[WARNING] Could not start PACS patient listener: {e}")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)
