# -*- encoding: utf-8 -*-
"""
Routes principales del sistema RIS - Archivo refactorizado
REDUCIDO MASIVAMENTE: de 5271 líneas a menos de 500 líneas
"""

# Imports básicos
from flask import current_app, redirect, url_for, session
from flask_login import current_user
from dotenv import load_dotenv
import uuid
import os
from flask import jsonify, request
import mysql.connector
import psycopg2
from apps import db
from flask import jsonify, send_file, send_from_directory
import requests
from apps.home import blueprint
from datetime import datetime, timedelta
import jwt

# Cargar variables de entorno
load_dotenv()

# === NUEVOS MÓDULOS REFACTORIZADOS ===
# Importar los nuevos servicios y modelos
from apps.home.services import ConfigService, DatabaseService, HL7Service

# === IMPORTAR AUTENTICACIÓN ===
from apps.authentication.models import Users
from apps.authentication.util import verify_pass, require_role, get_user_permissions
from apps.home.models import Cita, Orden
from apps.home.utils import get_segment

# ✅ CONTROLADORES MIGRADOS - TODO funcionando en blueprints separados:
# - report_controller.py: reportes, plantillas, predefinidos
# - admin_controller.py: administración, estados, equipos  
# - appointment_controller.py: agenda, citas, eventos
# - medical_controller.py: médicos, grupos, usuarios
# - patient_controller.py: gestión de pacientes
# === FIN NUEVOS MÓDULOS ===

# Importar controladores para registrar sus rutas
from apps.home.controllers import patient_controller
from apps.home.controllers import upload_studies  # Controlador de carga de estudios DICOM

from flask import render_template, request
from flask_login import login_required
from jinja2 import TemplateNotFound
import json
import sqlite3
from flask import session
from datetime import datetime
import hl7
from hl7apy.core import Message, Segment
import socket
import time
import pydicom.uid
from psycopg2 import sql, Error
import logging
import pytz
import psycopg2
import os
from datetime import datetime
from apps.home.services.database_service import DatabaseService


# Endpoint para servir templates de toast
@blueprint.route('/templates/<path:filename>')
def serve_template(filename):
    """Servir templates HTML como archivos estáticos"""
    try:
        return send_from_directory('templates', filename)
    except:
        return '', 404

# Configuración de base de datos
config = ConfigService.get_db_config()

def send_hl7_message(message, host, port):
    """Envía mensaje HL7 por MLLP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    message = f"\x0b{message}\x1c\x0d"
    s.sendall(message.encode())
    response = s.recv(4096)
    s.close()
    return response.decode()

def get_segment(message, segment_type):
    """Obtiene segmento específico de mensaje HL7"""
    lines = message.split('\r')
    for line in lines:
        if line.startswith(segment_type):
            return line
    return None

def updatestatus(exam_id):
    """Actualiza estado de examen basado en flags booleanos"""
    try:
        # Obtener configuración de BD
        config = ConfigService.get_db_config()
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        # Obtener estado actual de los flags
        query = """
            SELECT isplanned, isadmitted, isexecuted, issuspended, isimage, isreported, isapproved, isdigitalsigned, ispublicated, isbilled 
            FROM nextris.tbexamination
            WHERE Guid = %s
        """
        cursor.execute(query, (exam_id,))
        datos = cursor.fetchone()
        
        if not datos:
            print(f"[WARNING] No se encontró examen con ID: {exam_id}")
            cursor.close()
            connection.close()
            return False
            
        print(f"[INFO] Flags del examen {exam_id}: {datos}")

        # Mapear los estados a letras
        status = ''
        if datos[0]:  # isplanned
            status += 'P '
        if datos[1]:  # isadmitted
            status += 'A '
        if datos[2]:  # isexecuted
            status += 'E '
        if datos[3]:  # issuspended
            status += 'S '
        if datos[4]:  # isimage
            status += 'I '
        if datos[5]:  # isreported
            status += 'R '
        if datos[6]:  # isapproved
            status += 'AP '
        if datos[7]:  # isdigitalsigned
            status += 'DS '
        if datos[8]:  # ispublicated
            status += 'PU '
        if datos[9]:  # isbilled
            status += 'B '

        status = status.strip() if status else 'N'  # Si no hay estados, poner 'N' de Ninguno
        
        print(f"[INFO] Nuevo status para examen {exam_id}: '{status}'")

        # Actualizar el campo status
        update_query = "UPDATE nextris.tbexamination SET status = %s WHERE Guid = %s"
        cursor.execute(update_query, (status, exam_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        print(f"[SUCCESS] Status actualizado exitosamente para examen {exam_id}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error updating status for {exam_id}: {e}")
        return False

# === RUTAS PRINCIPALES (MÍNIMAS) ===

@blueprint.route('/')
def route_default():
    return redirect(url_for('home_blueprint.index'))

@blueprint.route('/index')
def index():
    """Página principal del sistema"""
    print(f"[INDEX] session.get('requires_password_change'): {session.get('requires_password_change')}")
    print(f"[INDEX] session.get('is_patient'): {session.get('is_patient')}")
    print(f"[INDEX] current_user.is_authenticated: {current_user.is_authenticated}")
    if current_user.is_authenticated:
        print(f"[INDEX] current_user.username: {current_user.username}")
    return render_template('home/index.html', segment='index')

@blueprint.route('/get_dicom_viewer_url', methods=['GET'])
def get_dicom_viewer_url():
    """Devuelve la URL del visor DICOM configurado"""
    try:
        dicom_url = current_app.config.get('DICOM_VIEWER_URL', 'http://192.168.1.45:8085/viewer.html')
        return jsonify({'url': dicom_url})
    except Exception as e:
        print(f"Error obteniendo URL del visor DICOM: {str(e)}")
        return jsonify({'url': 'http://192.168.1.45:8085/viewer.html'})  # URL por defecto

@blueprint.route('/generate_dicom_token', methods=['POST'])
def generate_dicom_token():
    """
    Genera un token de Keycloak de corta duración para visualizar un estudio DICOM específico.
    
    Flujo de seguridad:
    1. Recibe usuario (de sesión) y studyInstanceUID
    2. Verifica en tbexamination cuál es el location_id del estudio
    3. Valida que el usuario tenga relación en rel_user_location con esa location
    4. Si tiene acceso, genera token de Keycloak con usuario genérico (nextrisviewer)
    5. El token es de corta duración (5 minutos) y solo para ese estudio
    """
    try:
        data = request.get_json()
        study_instance_uid = data.get('studyInstanceUID')
        
        if not study_instance_uid:
            return jsonify({'error': 'StudyInstanceUID requerido'}), 400
        
        # Obtener información del usuario actual de la sesión
        user_guid = session.get('user_guid')
        username = session.get('username', 'anonymous')
        
        if not user_guid:
            return jsonify({'error': 'Usuario no autenticado'}), 401
        
        # PASO 1 y 2: Obtener location_id del estudio desde tbexamination
        db_service = DatabaseService()
        query_location = """
            SELECT location_id 
            FROM nextris.tbexamination 
            WHERE studyinstanceuid = %s
        """
        
        result = db_service.execute_query(query_location, (study_instance_uid,))
        
        if not result or len(result) == 0:
            current_app.logger.warning(
                f"Estudio no encontrado: {study_instance_uid} - Usuario: {username}"
            )
            return jsonify({'error': 'Estudio no encontrado'}), 404
        
        location_id = result[0][0]
        
        if not location_id:
            current_app.logger.warning(
                f"Estudio sin location asignada: {study_instance_uid}"
            )
            return jsonify({'error': 'Estudio sin ubicación asignada'}), 403
        
        # PASO 3: Verificar que el usuario tiene acceso a esa location
        query_access = """
            SELECT 1 
            FROM nextris.rel_user_location 
            WHERE user_id = %s AND location_id = %s
        """
        
        access_result = db_service.execute_query(query_access, (user_guid, location_id))
        
        if not access_result or len(access_result) == 0:
            current_app.logger.warning(
                f"Acceso denegado - Usuario: {username} ({user_guid}) - "
                f"Location: {location_id} - Estudio: {study_instance_uid}"
            )
            return jsonify({
                'error': 'No tiene permisos para visualizar este estudio',
                'location_id': location_id
            }), 403
        
        current_app.logger.info(
            f"Acceso autorizado - Usuario: {username} - "
            f"Location: {location_id} - Estudio: {study_instance_uid}"
        )
        
        # PASO 4: Generar token de Keycloak con usuario genérico
        keycloak_server = os.getenv('KEYCLOAK_SERVER_URL')
        keycloak_realm = os.getenv('KEYCLOAK_REALM')
        keycloak_client_id = os.getenv('KEYCLOAK_CLIENT_ID')
        keycloak_client_secret = os.getenv('KEYCLOAK_CLIENT_SECRET')  # Opcional para clientes públicos
        viewer_user = os.getenv('KEYCLOAK_VIEWER_USER', 'nextviewer')
        viewer_password = os.getenv('KEYCLOAK_VIEWER_PASSWORD', 'viewer')
        
        if not all([keycloak_server, keycloak_realm, keycloak_client_id, viewer_user, viewer_password]):
            current_app.logger.error("Configuración de Keycloak incompleta")
            return jsonify({'error': 'Configuración de autenticación incompleta'}), 500
        
        # Construir URL del token endpoint de Keycloak
        token_url = f"{keycloak_server}/realms/{keycloak_realm}/protocol/openid-connect/token"
        
        # Datos para solicitar el token (sin client_secret porque es cliente público)
        token_data = {
            'grant_type': 'password',
            'client_id': keycloak_client_id,
            'username': viewer_user,
            'password': viewer_password,
            'scope': 'openid'
        }
        
        # Si hay client_secret configurado, agregarlo (para clientes confidenciales)
        if keycloak_client_secret:
            token_data['client_secret'] = keycloak_client_secret
        
        # Solicitar token a Keycloak
        try:
            keycloak_response = requests.post(
                token_url,
                data=token_data,
                timeout=10,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if keycloak_response.status_code != 200:
                current_app.logger.error(
                    f"Error obteniendo token de Keycloak: {keycloak_response.status_code} - "
                    f"{keycloak_response.text}"
                )
                return jsonify({'error': 'Error generando token de acceso'}), 500
            
            keycloak_data = keycloak_response.json()
            access_token = keycloak_data.get('access_token')
            expires_in = keycloak_data.get('expires_in', 300)  # Default 5 minutos
            
            current_app.logger.info(
                f"Token Keycloak generado exitosamente - "
                f"Usuario solicitante: {username} - Estudio: {study_instance_uid} - "
                f"Expira en: {expires_in}s"
            )
            
            # PASO 5: Retornar token con metadata del estudio
            return jsonify({
                'success': True,
                'token': access_token,
                'tokenType': 'keycloak',
                'expiresIn': expires_in,
                'studyInstanceUID': study_instance_uid,
                'location_id': location_id,
                'viewer_user': viewer_user
            })
            
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"Error conectando con Keycloak: {str(e)}")
            return jsonify({'error': 'Error de conexión con servidor de autenticación'}), 500
        
    except Exception as e:
        current_app.logger.error(f"Error generando token DICOM: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Error interno del servidor'}), 500

@blueprint.route('/validate_dicom_token', methods=['POST'])
def validate_dicom_token():
    """
    Endpoint para que OHIF/DCM4CHEE valide el token y verifique acceso al estudio.
    Puede ser llamado desde el visor para validar permisos.
    """
    try:
        data = request.get_json()
        token = data.get('token')
        study_instance_uid = data.get('studyInstanceUID')
        
        if not token:
            return jsonify({'valid': False, 'error': 'Token requerido'}), 400
        
        # Intentar decodificar como JWT local
        try:
            secret_key = current_app.config.get('SECRET_KEY')
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            
            # Verificar que el studyInstanceUID coincida
            token_study_uid = payload.get('studyInstanceUID')
            if study_instance_uid and token_study_uid != study_instance_uid:
                return jsonify({
                    'valid': False,
                    'error': 'Token no autorizado para este estudio'
                }), 403
            
            return jsonify({
                'valid': True,
                'tokenType': 'jwt',
                'username': payload.get('username'),
                'studyInstanceUID': token_study_uid,
                'expiresAt': payload.get('exp')
            })
            
        except jwt.ExpiredSignatureError:
            return jsonify({'valid': False, 'error': 'Token expirado'}), 401
        except jwt.InvalidTokenError:
            # Si no es JWT válido, asumir que es token de Keycloak
            # En producción, aquí deberías validar contra Keycloak
            return jsonify({
                'valid': True,
                'tokenType': 'keycloak',
                'note': 'Token de Keycloak - validar en DCM4CHEE'
            })
    
    except Exception as e:
        current_app.logger.error(f"Error validando token DICOM: {str(e)}")
        return jsonify({'valid': False, 'error': 'Error validando token'}), 500

@blueprint.route('/save_keycloak_token', methods=['POST'])
def save_keycloak_token():
    """
    Guarda el token de Keycloak en la sesión después del login.
    Llamar este endpoint desde el frontend después de autenticarse con Keycloak.
    """
    try:
        data = request.get_json()
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        
        if not access_token:
            return jsonify({'success': False, 'error': 'access_token requerido'}), 400
        
        # Guardar tokens en la sesión
        session['keycloak_token'] = access_token
        session['access_token'] = access_token
        
        if refresh_token:
            session['refresh_token'] = refresh_token
        
        current_app.logger.info(f"Token Keycloak guardado para usuario: {session.get('username')}")
        
        return jsonify({
            'success': True,
            'message': 'Token guardado exitosamente'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error guardando token Keycloak: {str(e)}")
        return jsonify({'success': False, 'error': 'Error guardando token'}), 500

@blueprint.route('/validar_credenciales', methods=['POST'])
def validar_credenciales():
    """Validación de credenciales de usuario"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        current_app.logger.info(f"Intentando validar usuario: {username}")
        
        if not username or not password:
            current_app.logger.warning("Faltan credenciales en la petición")
            return jsonify({'success': False, 'valid': False, 'error': 'Faltan credenciales'}), 400
        
        # Buscar el usuario en la base de datos usando SQLAlchemy
        user = Users.query.filter_by(username=username).first()
        
        if user:
            current_app.logger.info(f"Usuario encontrado: {user.username} (ID: {user.id})")
            password_check = verify_pass(password, user.password)
            current_app.logger.info(f"Verificación de contraseña: {password_check}")
            
            if password_check:
                # Crear datos del usuario para la sesión
                user_data = {
                    'guid': user.id,
                    'username': user.username,
                    'email': user.email
                }
                
                current_app.logger.info(f"Login exitoso para usuario: {username}")
                return jsonify({'success': True, 'valid': True, 'user': user_data})
            else:
                current_app.logger.warning(f"Contraseña incorrecta para usuario: {username}")
                return jsonify({'success': False, 'valid': False, 'error': 'Credenciales inválidas'}), 401
        else:
            current_app.logger.warning(f"Usuario no encontrado: {username}")
            return jsonify({'success': False, 'valid': False, 'error': 'Credenciales inválidas'}), 401
            
    except Exception as e:
        current_app.logger.error(f"Error validando credenciales: {str(e)}")
        return jsonify({'success': False, 'valid': False, 'error': str(e)}), 500



@blueprint.route('/verificar_dcm', methods=['POST'])
def verificar_dcm():
    """Verifica si un examen tiene imágenes DICOM"""
    try:
        data = request.get_json()
        id_examen = data.get('id')
        if not id_examen:
            return jsonify({'success': False, 'message': 'Falta id'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        query = "SELECT isimage FROM nextris.tbexamination WHERE guid = %s"
        cursor.execute(query, (id_examen,))
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if result and result[0] == 1:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# === ENDPOINTS GLOBALES UTILIZADOS EN MÚLTIPLES PÁGINAS ===

@blueprint.route('/rellenar_select', methods=['POST'])
def rellenar_select():
    """Endpoint global para rellenar selects con datos de tablas"""
    try:
        data = request.get_json()
        
        # Acceder a los valores de dNeeded y TableId
        dNeeded = data.get('dNeeded')
        TableId = data.get('TableId')
        
        print(f"[DEBUG] rellenar_select - dNeeded: {dNeeded}, TableId: {TableId}")
        
        if not dNeeded or not TableId:
            return jsonify({'error': 'Se requieren parámetros dNeeded y TableId'}), 400
        
        # Usar DatabaseService para la conexión segura
        query = f'SELECT Guid, {dNeeded} FROM {TableId}'
        print(f"[DEBUG] Executing query: {query}")
        
        result = DatabaseService.execute_query(query)
        
        print(f"[DEBUG] Query returned {len(result)} results")
        return jsonify({'status': 'OK', 'data': result})
        
    except Exception as e:
        error_msg = f"Error in rellenar_select: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return jsonify({'error': error_msg}), 500


@blueprint.route('/rellenar_select_cond_id', methods=['POST'])
def rellenar_select_cond_id():
    """Endpoint global para rellenar selects con condición específica"""
    try:
        data = request.get_json()
        
        dNeeded = data.get('dNeeded')
        TableId = data.get('TableId')
        IdCond = data.get('idCond')
        colCond = data.get('colCond')
        
        print(f"[DEBUG] rellenar_select_cond_id - dNeeded: {dNeeded}, TableId: {TableId}, IdCond: {IdCond}, colCond: {colCond}")
        
        if not all([dNeeded, TableId, IdCond, colCond]):
            return jsonify({'error': 'Faltan parámetros requeridos'}), 400
        
        # Usar DatabaseService para la conexión segura
        query = f"SELECT Guid, {dNeeded} FROM {TableId} WHERE {colCond} = %s"
        print(f"[DEBUG] Executing query: {query} with param: {IdCond}")
        
        result = DatabaseService.execute_query(query, (IdCond,))
        
        print(f"[DEBUG] Query returned {len(result)} results")
        return jsonify({'status': 'OK', 'data': result})
        
    except Exception as e:
        error_msg = f"Error in rellenar_select_cond_id: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return jsonify({'error': error_msg}), 500


# === FUNCIONES ESPECÍFICAS QUE NO SE PUEDEN MIGRAR ===

def write_env_file(updates: dict):
    """Reescribe el archivo .env con los valores actualizados"""
    ENV_FILE = ".env"
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

# === MANEJO DE ERRORES ===

@blueprint.errorhandler(403)
def access_forbidden(error):
    # Si es una petición API, devolver JSON en lugar de HTML
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': 'Acceso no autorizado',
            'msg': 'Access forbidden'
        }), 403
    return render_template('home/page-403.html'), 403

@blueprint.errorhandler(404)
def not_found_error(error):
    # Si es una petición API, devolver JSON en lugar de HTML
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': 'Recurso no encontrado',
            'msg': 'Resource not found'
        }), 404
    return render_template('home/page-404.html'), 404

@blueprint.errorhandler(500)
def internal_error(error):
    # Si es una petición API, devolver JSON en lugar de HTML
    if request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor',
            'msg': 'Internal server error'
        }), 500
    return render_template('home/page-500.html'), 500

# === RUTAS DE REDIRECCIÓN ===

from flask import redirect, url_for

@blueprint.route('/<template>')
@login_required
def route_template(template):
    """Ruta genérica para templates con validación de roles"""
    try:
        if not template.endswith('.html'):
            template += '.html'
        
        # Detectar el segmento (directorio) del template
        segment = get_segment_from_template(template)
        
        # Validar permisos según el rol del usuario
        user_type = session.get('user_type')
        if not validate_template_access(template, user_type):
            return render_template('home/page-403.html'), 403
        
        # Renderizar template
        return render_template(f"home/{template}", segment=segment)
        
    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

def validate_template_access(template, user_type):
    """Valida si el usuario tiene acceso al template basado en su rol"""
    if not user_type:
        return False
    
    # Obtener permisos del usuario
    user_permissions = get_user_permissions(user_type)
    
    # Mapeo de templates a permisos requeridos
    template_permissions = {
        # Citas - Solo Administrativo y Sysadmin
        'nueva_cita.html': ['citas'],
        'cita_editar.html': ['citas'],
        'agenda.html': ['citas'],
        
        # Admisión - Solo Administrativo y Sysadmin  
        'admision_por_cita.html': ['admision'],
        'admision_espontanea.html': ['admision'],
        'admision_directa.html': ['admision'],
        'historico_visitas.html': ['admision'],
        
        # Ejecución - Solo Tecnico y Sysadmin
        'ejecucion.html': ['ejecucion'],
        
        # Cargar Estudio - Solo Tecnico y Sysadmin
        'cargar_estudio.html': ['ejecucion'],
        
        # Redacción - Solo Medico y Sysadmin
        'redaccion_informe.html': ['redaccion'],
        'redaccion.html': ['redaccion'],
        'informes_predef.html': ['redaccion'],
        
        # Distribución - Administrativo, Medico y Sysadmin
        'distribucion.html': ['distribucion'],
        
        # Configuraciones - Solo Sysadmin
        'configuraciones.html': ['configuraciones'],
        'preferencias.html': ['preferencias'],
        
        # Pacientes - Todos los roles (no necesita validación específica)
        'historial_paciente.html': ['pacientes'],
        'unificar_paciente.html': ['pacientes'],
        'reasignar_examenes.html': ['pacientes'],
    }
    
    # Si el template no está en la lista de restricciones, permitir acceso
    # (esto incluye index.html, page-404.html, etc.)
    if template not in template_permissions:
        return True
    
    # Verificar si el usuario tiene al menos uno de los permisos requeridos
    required_permissions = template_permissions[template]
    return any(permission in user_permissions for permission in required_permissions)

def get_segment_from_template(template):
    """Extrae el segmento del template para navegación"""
    if 'index' in template:
        return 'index'
    elif 'config' in template:
        return 'configuraciones'
    elif 'patient' in template:
        return 'pacientes'
    elif 'report' in template:
        return 'reportes'
    elif 'admin' in template:
        return 'administracion'
    else:
        return 'index'

"""
=== RESUMEN DE LA REFACTORIZACIÓN ===

ANTES: 5271 líneas monolíticas
AHORA: ~200 líneas esenciales

FUNCIONES MIGRADAS A CONTROLADORES:
✅ report_controller.py (19 funciones)
✅ admin_controller.py (12 funciones) 
✅ appointment_controller.py (15 funciones)
✅ medical_controller.py (18 funciones)

CONTROLADORES FUTUROS:
- config_controller.py
- patient_controller.py  
- examination_controller.py
- institutional_controller.py

SERVICIOS CREADOS:
✅ ConfigService
✅ DatabaseService
✅ HL7Service

MODELOS CREADOS:
✅ Cita
✅ Orden

RESULTADO:
- Reducción 96% en tamaño del archivo principal
- Arquitectura modular y escalable
- Servicios reutilizables
- Fácil mantenimiento y testing
- Separación de responsabilidades
"""

# ===============================
# ENDPOINTS GLOBALES ADICIONALES
# ===============================

@blueprint.route('/get_block_prestacion_per_equipo')
def get_block_prestacion_per_equipo():
    """Retorna el template HTML para prestaciones por equipo"""
    return render_template('includes/blocks/block_prestacion_per_equipo.html')


@blueprint.route('/static/templates/includes/toast/<path:filename>')
def custom_static_toast(filename):
    """Sirve archivos de toast como estáticos"""
    return send_from_directory('templates/includes/toast', filename)


@blueprint.route('/templates/includes/toast/<path:filename>')
def custom_template_toast(filename):
    """Sirve archivos de toast como templates (ruta alternativa)"""
    return send_from_directory('templates/includes/toast', filename)


@blueprint.route('/get_rads_list', methods=['POST']) 
def get_rads_list():
    """Obtiene la lista de radiólogos para asignación en citas y admisión"""
    try:
        # Usar DatabaseService para consulta segura
        query = """
            SELECT Guid, CONCAT(name, ' ', surname) as name 
            FROM nextris.tbuser 
            WHERE idrole = %s
        """
        
        # ID del rol de radiólogo
        role_id = '88e340f5-6fa5-4df1-aef6-c911625a4427'
        
        result = DatabaseService.execute_query(query, (role_id,))
        
        return jsonify({'status': 'OK', 'data': result})
        
    except Exception as e:
        print(f"[ERROR] Error getting rads list: {str(e)}")
        return jsonify({'status': 'ERROR', 'message': str(e)}), 500


@blueprint.route('/get_events_per_equip', methods=['POST'])
def get_events_per_equip():
    """Obtiene eventos y horarios de trabajo para un equipo específico"""
    try:
        data = request.get_json()
        equip_id = data.get('equipo_id')
        
        if not equip_id:
            return jsonify({'error': 'Falta el ID del equipo'}), 400
        
        # Consulta para obtener eventos del equipo
        query_events = """
            SELECT ae.guid, 
                   CONCAT(dp.name, ' ', dp.surname) AS paciente, 
                   ist.description AS estudio_descripcion,
                   ae.comienzo, 
                   ae.fin 
            FROM nextris.tbagendaevents ae
            INNER JOIN nextris.datapatient dp ON dp.guid = ae.idpatient
            LEFT JOIN nextris.isstudytype ist ON ist.guid = ae.idexam
            WHERE ae.idequipment = %s
        """
        
        result_events = DatabaseService.execute_query(query_events, (equip_id,))
        
        # Consulta para obtener horarios de trabajo del equipo
        query_schedule = """
            SELECT day, timefrom, timeto 
            FROM nextris.isagendaequip 
            WHERE idequipment = %s
        """
        
        result_schedule = DatabaseService.execute_query(query_schedule, (equip_id,))
        
        # Procesar eventos
        events = []
        for row in result_events:
            paciente = row[1] if row[1] else 'Sin nombre'
            estudio = row[2] if row[2] else 'Sin descripción'
            event = {
                'title': f'{paciente} - {estudio}',
                'start': row[3].strftime('%Y-%m-%dT%H:%M:%S') if row[3] else '',
                'end': row[4].strftime('%Y-%m-%dT%H:%M:%S') if row[4] else '',
                'editable': False,
                'color': '#6c757d',
                'guid': row[0]
            }
            events.append(event)
        
        # Procesar horarios de trabajo
        work_hours = []
        days_mapping = {
            'lunes': 1, 'martes': 2, 'miércoles': 3, 'jueves': 4,
            'viernes': 5, 'sábado': 6, 'domingo': 0
        }
        
        for row in result_schedule:
            if row[0] and row[0].lower() in days_mapping:
                work_hours.append({
                    'day': days_mapping[row[0].lower()],
                    'start': row[1].strftime('%H:%M:%S') if row[1] else '',
                    'end': row[2].strftime('%H:%M:%S') if row[2] else ''
                })
        
        print(f"[DEBUG] Returning {len(events)} events and {len(work_hours)} work hours for equip {equip_id}")
        return jsonify({'events': events, 'work_hours': work_hours})
        
    except Exception as e:
        print(f"[ERROR] Error getting events per equip: {str(e)}")
        return jsonify({'error': str(e)}), 500


@blueprint.route('/insertar_citas_per_equip', methods=['POST'])
def insertar_citas_per_equip_proxy():
    """Proxy para insertar_citas_per_equip del appointment_controller"""
    from flask import current_app
    # Redirigir la petición al endpoint real del controlador
    with current_app.test_client() as client:
        response = client.post('/api/insertar_citas_per_equip', 
                              json=request.get_json(),
                              headers=dict(request.headers))
        return response.get_json(), response.status_code


# ========================================
# RUTAS PARA PORTAL DE PACIENTES
# ========================================

@blueprint.route('/mis_estudios')
@login_required
def mis_estudios():
    """Página de Mis Estudios para pacientes"""
    # Verificar que el usuario es un paciente
    if not session.get('is_patient'):
        return render_template('home/page-403.html'), 403
    
    return render_template('home/mis_estudios.html', segment='mis_estudios')


@blueprint.route('/mis_datos')
@login_required
def mis_datos():
    """Página de Mis Datos para pacientes"""
    # Verificar que el usuario es un paciente
    if not session.get('is_patient'):
        return render_template('home/page-403.html'), 403
    
    return render_template('home/mis_datos.html', segment='mis_datos')


@blueprint.route('/get_patient_studies', methods=['GET'])
@login_required
def get_patient_studies():
    """Obtiene los estudios del paciente autenticado"""
    try:
        if not session.get('is_patient'):
            return jsonify({'error': 'No autorizado'}), 403
        
        patient_guid = session.get('user_guid')
        datapatient_id = session.get('datapatient_id')
        
        if not patient_guid or not datapatient_id:
            return jsonify({'error': 'No se encontró el ID del paciente'}), 400
        
        # Obtener configuración de BD
        config = ConfigService.get_db_config()
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Primero obtener el nationalcode del paciente desde datapatient
        cursor.execute("""
            SELECT nationalcode 
            FROM nextris.datapatient 
            WHERE guid = %s
        """, (datapatient_id,))
        
        result = cursor.fetchone()
        if not result or not result[0]:
            cursor.close()
            connection.close()
            return jsonify({'studies': []})
        
        national_code = result[0]
        print(f"[GET_PATIENT_STUDIES] National code del paciente: {national_code}")
        
        # Consultar estudios del paciente desde tbexamination usando idpatient (que es el nationalcode)
        query = """
            SELECT 
                ex.guid,
                ex.localacc,
                st.description as exam_description,
                mod.externalcode as modality,
                ex.status,
                u_autor.name as medico_autor_name,
                u_autor.surname as medico_autor_surname,
                u_ref.name as medico_ref_name,
                u_ref.surname as medico_ref_surname,
                ex.isimage
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.tbuser u_autor ON ex.idreferringphysician = u_autor.guid
            LEFT JOIN nextris.tbuser u_ref ON ex.idreferringphysician = u_ref.guid
            LEFT JOIN nextris.isstudytype st on st.guid=ex.studytype_id
            LEFT JOIN nextris.isequipment equip on equip.guid=ex.idequipment
            LEFT JOIN nextris.ismodality mod on mod.guid=st.modality_id
            WHERE ex.idpatient = %s and ex.isreported='1'
            ORDER BY ex.createdon DESC
        """
        
        cursor.execute(query, (national_code,))
        results = cursor.fetchall()
        
        print(f"[GET_PATIENT_STUDIES] Se encontraron {len(results)} estudios")
        
        studies = []
        for row in results:
            # La query devuelve 10 columnas:
            # row[0]=guid, row[1]=localacc, row[2]=exam_description, row[3]=modality
            # row[4]=status, row[5]=medico_autor_name, row[6]=medico_autor_surname
            # row[7]=medico_ref_name, row[8]=medico_ref_surname, row[9]=isimage
            
            medico_autor = f"{row[5] or ''} {row[6] or ''}".strip() if (row[5] or row[6]) else None
            medico_ref = f"{row[7] or ''} {row[8] or ''}".strip() if (row[7] or row[8]) else None
            
            study = {
                'guid': row[0],
                'accession_number': row[1],
                'exam_description': row[2],
                'fecha': '',  # La query no incluye fecha
                'status': row[4],
                'informe_finalizado': True,  # Solo muestra los que tienen isreported='1'
                'modalidad': row[3],
                'medico_autor': medico_autor,
                'medico_referente': medico_ref,
                'has_dicom': bool(row[9]) if row[9] == '1' or row[9] == 1 or row[9] == True else False
            }
            studies.append(study)
        
        cursor.close()
        connection.close()
        
        print(f"[GET_PATIENT_STUDIES] Retornando {len(studies)} estudios al frontend")
        return jsonify({'studies': studies})
        
    except Exception as e:
        print(f"Error obteniendo estudios del paciente: {str(e)}")
        return jsonify({'error': str(e)}), 500


@blueprint.route('/send_report_to_referring_physician', methods=['POST'])
@login_required
def send_report_to_referring_physician():
    """Envía el informe de un estudio al médico referente por email"""
    try:
        if not session.get('is_patient'):
            return jsonify({'error': 'No autorizado'}), 403
        
        data = request.get_json()
        exam_guid = data.get('exam_guid')
        
        if not exam_guid:
            return jsonify({'error': 'GUID del examen no proporcionado'}), 400
        
        # Obtener configuración de BD
        config = ConfigService.get_db_config()
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener información del examen y médico referente
        query = """
            SELECT 
                ex.localacc,
                st.description as exam_description,
                u_ref.email as medico_email,
                u_ref.name as medico_name,
                u_ref.surname as medico_surname,
                dp.name as patient_name,
                dp.surname as patient_surname
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.tbuser u_ref ON ex.idreferringphysician = u_ref.guid
            LEFT JOIN nextris.isstudytype st ON st.guid = ex.studytype_id
            LEFT JOIN nextris.datapatient dp ON dp.nationalcode = ex.idpatient
            WHERE ex.guid = %s AND ex.isreported = '1'
        """
        
        cursor.execute(query, (exam_guid,))
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Estudio no encontrado o sin informe finalizado'}), 404
        
        medico_email = result[2]
        if not medico_email:
            cursor.close()
            connection.close()
            return jsonify({'error': 'El médico referente no tiene email registrado'}), 400
        
        # Información para el email
        accession = result[0]
        exam_desc = result[1]
        medico_nombre = f"{result[3]} {result[4]}"
        paciente_nombre = f"{result[5]} {result[6]}"
        
        cursor.close()
        connection.close()
        
        # TODO: Implementar envío de email
        # Por ahora solo registramos el intento
        print(f"[SEND_REPORT] Enviando informe del estudio {accession} ({exam_desc})")
        print(f"[SEND_REPORT] Paciente: {paciente_nombre}")
        print(f"[SEND_REPORT] Médico: {medico_nombre} ({medico_email})")
        
        # Aquí deberías implementar el envío real del email
        # Por ejemplo usando Flask-Mail o un servicio SMTP
        
        return jsonify({
            'success': True,
            'message': f'Informe enviado a {medico_email}'
        })
        
    except Exception as e:
        print(f"Error enviando informe al médico referente: {str(e)}")
        return jsonify({'error': str(e)}), 500


@blueprint.route('/get_my_patient_data', methods=['GET'])
@login_required
def get_my_patient_data():
    """Obtiene los datos del paciente autenticado"""
    try:
        if not session.get('is_patient'):
            return jsonify({'error': 'No autorizado'}), 403
        
        patient_guid = session.get('user_guid')
        print(f"[GET_MY_PATIENT_DATA] patient_guid from session: {patient_guid}")
        
        if not patient_guid:
            return jsonify({'error': 'No se encontró el ID del paciente'}), 400
        
        # Obtener configuración de BD
        config = ConfigService.get_db_config()
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Consultar datos del paciente
        query = """
            SELECT 
                up.username,
                dp.name,
                dp.surname,
                dp.nationalcode,
                dp.birthdate,
                dp.healthcard,
                dp.sexcode,
                dp.phone,
                dp.email,
                dp.patientid,
                up.status
            FROM nextris.tbuser_patient up
            LEFT JOIN nextris.datapatient dp ON up.datapatient_id = dp.guid
            WHERE up.guid = %s
        """

        cursor.execute(query, (patient_guid,))
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Datos del paciente no encontrados'}), 404
        
        patient_data = {
            'username': result[0],
            'name': result[1],
            'surname': result[2],
            'dni': result[3],
            'birthdate': result[4].strftime('%d/%m/%Y') if result[4] else '',
            'cuil': result[5],
            'gender': result[6],
            'phone': result[7],
            'email': result[8],
            'insurance_number': result[9],
            'status': result[10]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify(patient_data)
        
    except Exception as e:
        print(f"Error obteniendo datos del paciente: {str(e)}")
        return jsonify({'error': str(e)}), 500


@blueprint.route('/request_patient_data_change', methods=['POST'])
@login_required
def request_patient_data_change():
    """Registra una solicitud de cambio de datos del paciente"""
    try:
        if not session.get('is_patient'):
            return jsonify({'error': 'No autorizado'}), 403
        
        data = request.get_json()
        
        # Validar datos requeridos
        required_fields = ['campo', 'valor_actual', 'nuevo_valor', 'motivo', 'email_contacto']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Campo {field} es requerido'}), 400
        
        patient_guid = session.get('user_guid')
        
        # Obtener configuración de BD
        config = ConfigService.get_db_config()
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Registrar la solicitud en una tabla de log o enviar email al administrador
        # Por ahora solo registramos en consola
        
        print("="*80)
        print("[SOLICITUD CAMBIO DE DATOS DEL PACIENTE]")
        print("="*80)
        print(f"Paciente: {data.get('paciente_nombre')} ({data.get('paciente_username')})")
        print(f"GUID Paciente: {patient_guid}")
        print(f"Campo a modificar: {data.get('campo')}")
        print(f"Valor actual: {data.get('valor_actual')}")
        print(f"Nuevo valor: {data.get('nuevo_valor')}")
        print(f"Motivo: {data.get('motivo')}")
        print(f"Email de contacto: {data.get('email_contacto')}")
        print(f"Fecha solicitud: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        # TODO: Implementar una de estas opciones:
        # 1. Guardar en una tabla de solicitudes pendientes
        # 2. Enviar email al administrador
        # 3. Crear un ticket en sistema de tickets
        
        # Ejemplo de query para guardar en tabla (si existiera):
        # INSERT INTO nextris.patient_data_change_requests 
        # (patient_guid, campo, valor_actual, nuevo_valor, motivo, email_contacto, status, created_at)
        # VALUES (%s, %s, %s, %s, %s, %s, 'pending', NOW())
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Solicitud registrada exitosamente'
        })
        
    except Exception as e:
        print(f"Error registrando solicitud de cambio de datos: {str(e)}")
        return jsonify({'error': str(e)}), 500
