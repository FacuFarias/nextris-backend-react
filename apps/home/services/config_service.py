"""
Servicio de configuración para el sistema RIS
Maneja variables de entorno y configuración de la base de datos
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

ENV_FILE = ".env"

class ConfigService:
    """Servicio para gestión de configuración del sistema"""
    
    @staticmethod
    def get_db_config():
        """Obtiene la configuración de la DB desde variables de entorno"""
        return {
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASS', 'postgres'),
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'postgres'),
        }

    @staticmethod
    def get_base_folder():
        """Obtiene la carpeta base para archivos PDF"""
        return os.getenv('BASE_FOLDER', '/app/output_pdfs')

    @staticmethod
    def get_ipserver():
        """Obtiene la IP del servidor HL7"""
        return os.getenv('IPSERVER', '127.0.0.1')
    
    @staticmethod
    def get_fhir_server_url():
        """Obtiene la URL del servidor FHIR"""
        return os.getenv('FHIR_SERVER_URL', 'http://localhost:8080/fhir')

    @staticmethod
    def get_all_config():
        """Obtiene toda la configuración actual"""
        return {
            'config': ConfigService.get_db_config(),
            'BASE_FOLDER': ConfigService.get_base_folder(),
            'IPSERVER': ConfigService.get_ipserver(),
            'FHIR_SERVER_URL': ConfigService.get_fhir_server_url()
        }

    @staticmethod
    def write_env_file(updates: dict):
        """Reescribe el archivo .env con los valores actualizados"""
        env_vars = {}

        # 1. Leer contenido actual del .env si existe
        if os.path.exists(ENV_FILE):
            with open(ENV_FILE, "r") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        key, val = line.strip().split("=", 1)
                        env_vars[key] = val

        # 2. Aplicar actualizaciones
        env_vars.update(updates)

        # 3. Reescribir archivo completo
        with open(ENV_FILE, "w") as f:
            for k, v in env_vars.items():
                f.write(f"{k}={v}\n")

    @staticmethod
    def update_config(data: dict):
        """Actualiza la configuración y la persiste en el archivo .env"""
        updates = {}

        if 'config' in data:
            for k, v in data['config'].items():
                key = f"DB_{k.upper()}"
                os.environ[key] = str(v)
                updates[key] = str(v)

        if 'BASE_FOLDER' in data:
            os.environ['BASE_FOLDER'] = data['BASE_FOLDER']
            updates['BASE_FOLDER'] = data['BASE_FOLDER']

        if 'IPSERVER' in data:
            os.environ['IPSERVER'] = data['IPSERVER']
            updates['IPSERVER'] = data['IPSERVER']

        if 'FHIR_SERVER_URL' in data:
            os.environ['FHIR_SERVER_URL'] = data['FHIR_SERVER_URL']
            updates['FHIR_SERVER_URL'] = data['FHIR_SERVER_URL']

        # Guardar en el archivo .env
        ConfigService.write_env_file(updates)
        
        return ConfigService.get_all_config()


# Variables globales de configuración para compatibilidad
config = ConfigService.get_db_config()
BASE_FOLDER = ConfigService.get_base_folder()
IPSERVER = ConfigService.get_ipserver()
server_url = ConfigService.get_fhir_server_url()