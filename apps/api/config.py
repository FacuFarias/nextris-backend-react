# -*- encoding: utf-8 -*-
"""
API REST para Configuración del Sistema
Endpoints para gestión de configuraciones, tipos de estudio, equipos, ubicaciones, etc.
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
from apps.api import api_blueprint
import uuid
import os
import smtplib
import secrets
import string
from werkzeug.utils import secure_filename
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.routes import config
        return config
    except:
        return None


def ensure_user_medical_table(connection):
    """Ensure tbuser_medical_data exists."""
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS nextris.tbuser_medical_data (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL UNIQUE,
            aclaracion_firma VARCHAR(255) NOT NULL,
            matricula_nacional VARCHAR(100) NOT NULL,
            firma_digital VARCHAR(500),
            firma_habilitada BOOLEAN DEFAULT FALSE,
            fecha_creacion TIMESTAMP DEFAULT NOW(),
            fecha_actualizacion TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES nextris.tbuser(guid) ON DELETE CASCADE
        );
        """
    )
    connection.commit()
    cursor.close()


def generate_temporary_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def send_new_user_credentials_email(connection, email, username, temporary_password, full_name):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT smtp_server, smtp_port, smtp_user, smtp_password, smtp_from, smtp_from_name, use_tls
        FROM nextris.tbfacility
        LIMIT 1
        """
    )
    smtp_result = cursor.fetchone()
    cursor.close()

    smtp_server = (smtp_result[0] if smtp_result else None) or os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = (smtp_result[1] if smtp_result else None) or int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = (smtp_result[2] if smtp_result else None) or os.environ.get('SMTP_USER')
    smtp_password = (smtp_result[3] if smtp_result else None) or os.environ.get('SMTP_PASSWORD')
    smtp_from = (smtp_result[4] if smtp_result else None) or smtp_user or os.environ.get('SMTP_FROM')
    smtp_from_name = (smtp_result[5] if smtp_result else None) or os.environ.get('SMTP_FROM_NAME', 'NextRIS')
    use_tls = (smtp_result[6] if smtp_result and smtp_result[6] is not None else True)

    if not smtp_user or not smtp_password:
        raise Exception('Configuración SMTP incompleta para enviar credenciales')

    msg = MIMEMultipart()
    msg['From'] = f"{smtp_from_name} <{smtp_from}>"
    msg['To'] = email
    msg['Subject'] = 'Credenciales de acceso - NextRIS'

    body = f"""
Hola {full_name},

Tu usuario fue creado correctamente en NextRIS.

Usuario: {username}
Contraseña temporal: {temporary_password}

Por seguridad, en tu primer inicio de sesión deberás cambiar esta contraseña.

Este es un mensaje automático, por favor no responder.
"""

    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP(smtp_server, smtp_port)
    if use_tls:
        server.starttls()
    server.login(smtp_user, smtp_password)
    server.sendmail(smtp_from, email, msg.as_string())
    server.quit()


# ====================================================================
# CONFIGURACIÓN DEL SISTEMA
# ====================================================================

@api_blueprint.route('/config/system', methods=['GET'])
@jwt_required()
def get_system_config():
    """
    Obtiene la configuración general del sistema
    
    Returns:
    {
        "success": true,
        "data": {
            "config_key": "config_value"
        }
    }
    """
    try:
        # Importar ConfigService
        from apps.home.services import ConfigService
        config_data = ConfigService.get_all_config()
        
        return jsonify({
            'success': True,
            'data': config_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/system', methods=['PUT', 'PATCH'])
@jwt_required()
def update_system_config():
    """
    Actualiza la configuración del sistema
    
    Body JSON:
    {
        "config_key": "new_value",
        ...
    }
    
    Returns:
    {
        "success": true,
        "message": "Configuración actualizada",
        "data": {...}
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        from apps.home.services import ConfigService
        updated_config = ConfigService.update_config(data)
        
        return jsonify({
            'success': True,
            'message': 'Configuración actualizada exitosamente',
            'data': updated_config
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/workflow', methods=['GET'])
@jwt_required()
def get_workflow_config():
    """
    Obtiene la configuración de workflow
    
    Returns:
    {
        "success": true,
        "data": {
            "agenda_tipo": "...",
            "agenda_estudios": "..."
        }
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT agenda_tipo, agenda_estudios
            FROM nextris.tbfacility
            LIMIT 1
        """
        
        cursor.execute(query)
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if result:
            return jsonify({
                'success': True,
                'data': {
                    'agenda_tipo': result[0],
                    'agenda_estudios': result[1]
                }
            }), 200
        else:
            return jsonify({
                'success': True,
                'data': {
                    'agenda_tipo': None,
                    'agenda_estudios': None
                }
            }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# TIPOS DE ESTUDIO
# ====================================================================

@api_blueprint.route('/config/study-types', methods=['GET'])
@jwt_required()
def get_study_types_config():
    """
    Obtiene todos los tipos de estudio con sus relaciones
    
    Query Parameters:
    - modality_id (OPCIONAL): Filtrar tipos de estudio por modalidad
    - bodypart_id (OPCIONAL): Filtrar tipos de estudio por parte del cuerpo
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "code": "...",
                "description": "...",
                "studygroup": "...",
                "bodypart": "...",
                "modality": "...",
                "rvu": 0,
                "nofviews": 0
            }
        ]
    }
    """
    try:
        # Obtener parámetros opcionales
        modality_id = request.args.get('modality_id')
        bodypart_id = request.args.get('bodypart_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Construir query base
        query = """
            SELECT st.guid, st.code, st.description, stg.description as studygroup, 
                   ap.description as bodypart, md.externalcode as modality, 
                   st.rvu, st.nofviews
            FROM nextris.isstudytype as st
            INNER JOIN nextris.isstudytypegroup stg on stg.guid=st.studygroup_id
            INNER JOIN nextris.isanatomicalpart ap on ap.guid=st.bodypart_id
            INNER JOIN nextris.ismodality md on md.guid=st.modality_id
            WHERE 1=1
        """
        
        params = []
        
        # Agregar filtro de modalidad si se proporciona
        if modality_id:
            query += " AND st.modality_id = %s"
            params.append(modality_id)
        
        # Agregar filtro de parte del cuerpo si se proporciona
        if bodypart_id:
            query += " AND st.bodypart_id = %s"
            params.append(bodypart_id)
        
        query += " ORDER BY st.description ASC"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        study_types = []
        for row in results:
            study_types.append({
                'guid': row[0],
                'code': row[1],
                'description': row[2],
                'studygroup': row[3],
                'bodypart': row[4],
                'modality': row[5],
                'rvu': row[6],
                'nofviews': row[7]
            })
        
        return jsonify({
            'success': True,
            'data': study_types
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-types', methods=['POST'])
@jwt_required()
def create_study_type():
    """
    Crea un nuevo tipo de estudio
    
    Body JSON:
    {
        "code": "string" (required),
        "description": "string" (required),
        "studygroup_id": "uuid" (required),
        "bodypart_id": "uuid" (required),
        "modality_id": "uuid" (required),
        "rvu": number (optional),
        "nofviews": number (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Tipo de estudio creado",
        "data": {
            "study_type_id": "uuid"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        code = data.get('code')
        description = data.get('description')
        studygroup_id = data.get('studygroup_id')
        bodypart_id = data.get('bodypart_id')
        modality_id = data.get('modality_id')
        
        if not all([code, description, studygroup_id, bodypart_id, modality_id]):
            return jsonify({
                'success': False,
                'message': 'code, description, studygroup_id, bodypart_id y modality_id son requeridos'
            }), 400
        
        rvu = data.get('rvu')
        nofviews = data.get('nofviews')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isstudytype(
                guid, code, description, studygroup_id, bodypart_id, modality_id, rvu, nofviews
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            new_guid, code, description, studygroup_id, bodypart_id, modality_id, rvu, nofviews
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Tipo de estudio creado exitosamente',
            'data': {
                'study_type_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-types/<study_type_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_study_type(study_type_id):
    """
    Actualiza un tipo de estudio existente
    
    Path:
    - study_type_id: GUID del tipo de estudio
    
    Body JSON (todos opcionales):
    {
        "code": "string",
        "description": "string",
        "studygroup_id": "uuid",
        "bodypart_id": "uuid",
        "modality_id": "uuid",
        "rvu": number,
        "nofviews": number
    }
    
    Returns:
    {
        "success": true,
        "message": "Tipo de estudio actualizado"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isstudytype WHERE guid=%s", (study_type_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Tipo de estudio no encontrado'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'code' in data:
            updates.append("code = %s")
            params.append(data['code'])
        if 'description' in data:
            updates.append("description = %s")
            params.append(data['description'])
        if 'studygroup_id' in data:
            updates.append("studygroup_id = %s")
            params.append(data['studygroup_id'])
        if 'bodypart_id' in data:
            updates.append("bodypart_id = %s")
            params.append(data['bodypart_id'])
        if 'modality_id' in data:
            updates.append("modality_id = %s")
            params.append(data['modality_id'])
        if 'rvu' in data:
            updates.append("rvu = %s")
            params.append(data['rvu'])
        if 'nofviews' in data:
            updates.append("nofviews = %s")
            params.append(data['nofviews'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(study_type_id)
        query = f"UPDATE nextris.isstudytype SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Tipo de estudio actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-types/<study_type_id>', methods=['DELETE'])
@jwt_required()
def delete_study_type(study_type_id):
    """
    Elimina un tipo de estudio
    
    Path:
    - study_type_id: GUID del tipo de estudio
    
    Returns:
    {
        "success": true,
        "message": "Tipo de estudio eliminado"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isstudytype WHERE guid=%s", (study_type_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Tipo de estudio no encontrado'
            }), 404
        
        query = "DELETE FROM nextris.isstudytype WHERE guid = %s"
        cursor.execute(query, (study_type_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Tipo de estudio eliminado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# MODALIDADES, PARTES DEL CUERPO, GRUPOS
# ====================================================================

@api_blueprint.route('/config/modalities', methods=['GET'])
@jwt_required()
def get_modalities():
    """
    Obtiene todas las modalidades
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "externalcode": "...",
                "description": "..."
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = "SELECT guid, externalcode, description FROM nextris.ismodality ORDER BY description"
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        modalities = []
        for row in results:
            modalities.append({
                'guid': row[0],
                'externalcode': row[1],
                'description': row[2]
            })
        
        return jsonify({
            'success': True,
            'data': modalities
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/modalities', methods=['POST'])
@jwt_required()
def create_modality():
    """
    Crea una nueva modalidad
    
    Body JSON:
    {
        "externalcode": "string" (required),
        "description": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Modalidad creada",
        "data": {
            "modality_id": "uuid"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        externalcode = data.get('externalcode')
        description = data.get('description')
        
        if not all([externalcode, description]):
            return jsonify({
                'success': False,
                'message': 'externalcode y description son requeridos'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.ismodality(guid, externalcode, description) 
            VALUES (%s, %s, %s)
        """
        
        cursor.execute(query, (new_guid, externalcode, description))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Modalidad creada exitosamente',
            'data': {
                'modality_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/modalities/<modality_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_modality(modality_id):
    """
    Actualiza una modalidad existente
    
    Path:
    - modality_id: GUID de la modalidad
    
    Body JSON (todos opcionales):
    {
        "externalcode": "string",
        "description": "string"
    }
    
    Returns:
    {
        "success": true,
        "message": "Modalidad actualizada"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.ismodality WHERE guid=%s", (modality_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Modalidad no encontrada'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'externalcode' in data:
            updates.append("externalcode = %s")
            params.append(data['externalcode'])
        if 'description' in data:
            updates.append("description = %s")
            params.append(data['description'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(modality_id)
        query = f"UPDATE nextris.ismodality SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Modalidad actualizada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/modalities/<modality_id>', methods=['DELETE'])
@jwt_required()
def delete_modality(modality_id):
    """
    Elimina una modalidad
    
    Path:
    - modality_id: GUID de la modalidad
    
    Returns:
    {
        "success": true,
        "message": "Modalidad eliminada"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.ismodality WHERE guid=%s", (modality_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Modalidad no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.ismodality WHERE guid = %s"
        cursor.execute(query, (modality_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Modalidad eliminada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/body-parts', methods=['GET'])
@jwt_required()
def get_body_parts():
    """
    Obtiene todas las partes del cuerpo
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "..."
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = "SELECT guid, description FROM nextris.isanatomicalpart ORDER BY description"
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        body_parts = []
        for row in results:
            body_parts.append({
                'guid': row[0],
                'description': row[1]
            })
        
        return jsonify({
            'success': True,
            'data': body_parts
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/body-parts', methods=['POST'])
@jwt_required()
def create_body_part():
    """
    Crea una nueva parte del cuerpo
    
    Body JSON:
    {
        "description": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Parte del cuerpo creada",
        "data": {
            "body_part_id": "uuid"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        description = data.get('description')
        
        if not description:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isanatomicalpart(guid, description) 
            VALUES (%s, %s)
        """
        
        cursor.execute(query, (new_guid, description))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Parte del cuerpo creada exitosamente',
            'data': {
                'body_part_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/body-parts/<body_part_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_body_part(body_part_id):
    """
    Actualiza una parte del cuerpo existente
    
    Path:
    - body_part_id: GUID de la parte del cuerpo
    
    Body JSON:
    {
        "description": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Parte del cuerpo actualizada"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        description = data.get('description')
        
        if not description:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isanatomicalpart WHERE guid=%s", (body_part_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Parte del cuerpo no encontrada'
            }), 404
        
        query = "UPDATE nextris.isanatomicalpart SET description = %s WHERE guid = %s"
        
        cursor.execute(query, (description, body_part_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Parte del cuerpo actualizada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/body-parts/<body_part_id>', methods=['DELETE'])
@jwt_required()
def delete_body_part(body_part_id):
    """
    Elimina una parte del cuerpo
    
    Path:
    - body_part_id: GUID de la parte del cuerpo
    
    Returns:
    {
        "success": true,
        "message": "Parte del cuerpo eliminada"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isanatomicalpart WHERE guid=%s", (body_part_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Parte del cuerpo no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.isanatomicalpart WHERE guid = %s"
        cursor.execute(query, (body_part_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Parte del cuerpo eliminada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-groups', methods=['GET'])
@jwt_required()
def get_study_groups():
    """
    Obtiene todos los grupos de estudio
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "..."
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = "SELECT guid, description FROM nextris.isstudytypegroup ORDER BY description"
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        groups = []
        for row in results:
            groups.append({
                'guid': row[0],
                'description': row[1]
            })
        
        return jsonify({
            'success': True,
            'data': groups
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-groups', methods=['POST'])
@jwt_required()
def create_study_group():
    """
    Crea un nuevo grupo de estudio
    
    Body JSON:
    {
        "description": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Grupo de estudio creado",
        "data": {
            "study_group_id": "uuid"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        description = data.get('description')
        
        if not description:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isstudytypegroup(guid, description) 
            VALUES (%s, %s)
        """
        
        cursor.execute(query, (new_guid, description))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Grupo de estudio creado exitosamente',
            'data': {
                'study_group_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-groups/<study_group_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_study_group(study_group_id):
    """
    Actualiza un grupo de estudio existente
    
    Path:
    - study_group_id: GUID del grupo de estudio
    
    Body JSON:
    {
        "description": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Grupo de estudio actualizado"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        description = data.get('description')
        
        if not description:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isstudytypegroup WHERE guid=%s", (study_group_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Grupo de estudio no encontrado'
            }), 404
        
        query = "UPDATE nextris.isstudytypegroup SET description = %s WHERE guid = %s"
        
        cursor.execute(query, (description, study_group_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Grupo de estudio actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-groups/<study_group_id>', methods=['DELETE'])
@jwt_required()
def delete_study_group(study_group_id):
    """
    Elimina un grupo de estudio
    
    Path:
    - study_group_id: GUID del grupo de estudio
    
    Returns:
    {
        "success": true,
        "message": "Grupo de estudio eliminado"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isstudytypegroup WHERE guid=%s", (study_group_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Grupo de estudio no encontrado'
            }), 404
        
        query = "DELETE FROM nextris.isstudytypegroup WHERE guid = %s"
        cursor.execute(query, (study_group_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Grupo de estudio eliminado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# EQUIPOS (MÁQUINAS)
# ====================================================================

@api_blueprint.route('/config/equipment', methods=['GET'])
@jwt_required()
def get_equipment():
    """
    Obtiene equipos/máquinas filtrados opcionalmente por ubicación y/o modalidad
    
    Query Parameters:
    - location_id (OPCIONAL): Filtrar equipos por ubicación
    - modality_id (OPCIONAL): Filtrar equipos por modalidad
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "...",
                "aeTitle": "...",
                "externalcode": "...",
                "modality": "..."
            }
        ]
    }
    """
    try:
        # Obtener parámetros opcionales
        location_id = request.args.get('location_id')
        modality_id = request.args.get('modality_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Construir query base
        query = """
            SELECT e.guid, e.description, e.aetitle, e.externalcode, m.description as modality
            FROM nextris.isequipment e
            LEFT JOIN nextris.ismodality m ON e.idmodality = m.guid
            WHERE 1=1
        """
        
        params = []
        
        # Agregar filtro de ubicación si se proporciona
        if location_id:
            query += " AND e.location_id = %s"
            params.append(location_id)
        
        # Agregar filtro de modalidad si se proporciona
        if modality_id:
            query += " AND e.idmodality = %s"
            params.append(modality_id)
        
        query += " ORDER BY e.description"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        equipment_list = []
        for row in results:
            equipment_list.append({
                'guid': row[0],
                'description': row[1],
                'aeTitle': row[2],
                'externalcode': row[3],
                'modality': row[4]
            })
        
        return jsonify({
            'success': True,
            'data': equipment_list
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/equipment', methods=['POST'])
@jwt_required()
def create_equipment():
    """
    Crea un nuevo equipo
    
    Body JSON:
    {
        "name": "string" (required),
        "aetitle": "string" (required),
        "location_id": "uuid" (required),
        "modality_id": "uuid" (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Equipo creado",
        "data": {
            "equipment_id": "uuid"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        description = data.get('description')
        aetitle = data.get('aetitle')
        modality_id = data.get('modality_id')
        
        if not all([description, aetitle]):
            return jsonify({
                'success': False,
                'message': 'description y aetitle son requeridos'
            }), 400
        
        externalcode = data.get('externalcode', '')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isequipment(guid, description, aetitle, externalcode, idmodality, isactive) 
            VALUES (%s, %s, %s, %s, %s, 1)
        """
        
        cursor.execute(query, (new_guid, description, aetitle, externalcode, modality_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Equipo creado exitosamente',
            'data': {
                'equipment_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/equipment/<equipment_id>', methods=['DELETE'])
@jwt_required()
def delete_equipment(equipment_id):
    """
    Elimina un equipo
    
    Path:
    - equipment_id: GUID del equipo
    
    Returns:
    {
        "success": true,
        "message": "Equipo eliminado"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isequipment WHERE guid=%s", (equipment_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Equipo no encontrado'
            }), 404
        
        query = "DELETE FROM nextris.isequipment WHERE guid = %s"
        cursor.execute(query, (equipment_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Equipo eliminado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# UBICACIONES (LOCATIONS)
# ====================================================================

@api_blueprint.route('/config/locations', methods=['GET'])
@jwt_required()
def get_locations():
    """
    Obtiene todas las ubicaciones con todos sus datos
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "facility_id": "...",
                "name": "...",
                "code": "...",
                "address": "...",
                "phone": "...",
                "status": "...",
                "created_at": "...",
                "updated_at": "...",
                "id_patientdomain": "...",
                "mail": "...",
                "logo_path": "...",
                "geographic_location": "...",
                "timezone": "..."
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT l.guid, l.facility_id, l.name, l.code, l.address, l.phone, l.status, 
                   l.created_at, l.updated_at, l.id_patientdomain, l.mail, l.logo_path, 
                   l.geographic_location, l.timezone, f.name as facility_name
            FROM nextris.tblocation l
            LEFT JOIN nextris.tbfacility f ON l.facility_id = f.guid
            ORDER BY l.name
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        locations = []
        for row in results:
            locations.append({
                'guid': row[0],
                'facility_id': row[1],
                'facility_name': row[14],
                'name': row[2],
                'code': row[3],
                'address': row[4],
                'phone': row[5],
                'status': row[6],
                'created_at': row[7].isoformat() if row[7] else None,
                'updated_at': row[8].isoformat() if row[8] else None,
                'id_patientdomain': row[9],
                'mail': row[10],
                'logo_path': row[11],
                'geographic_location': row[12],
                'timezone': row[13]
            })
        
        return jsonify({
            'success': True,
            'data': locations
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/locations', methods=['POST'])
@jwt_required()
def create_location():
    """
    Crea una nueva ubicación
    
    Body JSON:
    {
        "name": "string" (required),
        "code": "string" (optional),
        "facility_id": "uuid" (optional),
        "address": "string" (optional),
        "phone": "string" (optional),
        "status": "string" (optional, default: 'Active'),
        "id_patientdomain": "string" (optional),
        "mail": "string" (optional),
        "geographic_location": "string" (optional),
        "timezone": "string" (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Ubicación creada",
        "data": {
            "location_id": "uuid"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        name = data.get('name')
        
        if not name:
            return jsonify({
                'success': False,
                'message': 'name es requerido'
            }), 400
        
        # Obtener todos los campos opcionales
        facility_id = data.get('facility_id')
        code = data.get('code', '')
        address = data.get('address', '')
        phone = data.get('phone', '')
        status = data.get('status', 'Active')
        id_patientdomain = data.get('id_patientdomain', '')
        mail = data.get('mail', '')
        geographic_location = data.get('geographic_location', '')
        timezone = data.get('timezone', '')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.tblocation(
                guid, facility_id, name, code, address, phone, status,
                created_at, updated_at, id_patientdomain, mail, 
                geographic_location, timezone
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            new_guid, facility_id, name, code, address, phone, status,
            id_patientdomain, mail, geographic_location, timezone
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Ubicación creada exitosamente',
            'data': {
                'location_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/locations/<location_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_location(location_id):
    """
    Actualiza una ubicación existente
    
    Path:
    - location_id: GUID de la ubicación
    
    Body JSON (todos opcionales):
    {
        "name": "string",
        "code": "string",
        "facility_id": "uuid",
        "address": "string",
        "phone": "string",
        "status": "string",
        "id_patientdomain": "string",
        "mail": "string",
        "geographic_location": "string",
        "timezone": "string"
    }
    
    Returns:
    {
        "success": true,
        "message": "Ubicación actualizada"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (location_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'name' in data:
            updates.append("name = %s")
            params.append(data['name'])
        if 'code' in data:
            updates.append("code = %s")
            params.append(data['code'])
        if 'facility_id' in data:
            updates.append("facility_id = %s")
            params.append(data['facility_id'])
        if 'address' in data:
            updates.append("address = %s")
            params.append(data['address'])
        if 'phone' in data:
            updates.append("phone = %s")
            params.append(data['phone'])
        if 'status' in data:
            updates.append("status = %s")
            params.append(data['status'])
        if 'id_patientdomain' in data:
            updates.append("id_patientdomain = %s")
            params.append(data['id_patientdomain'])
        if 'mail' in data:
            updates.append("mail = %s")
            params.append(data['mail'])
        if 'geographic_location' in data:
            updates.append("geographic_location = %s")
            params.append(data['geographic_location'])
        if 'timezone' in data:
            updates.append("timezone = %s")
            params.append(data['timezone'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        # Agregar updated_at
        updates.append("updated_at = NOW()")
        
        params.append(location_id)
        query = f"UPDATE nextris.tblocation SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Ubicación actualizada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/locations/<location_id>', methods=['DELETE'])
@jwt_required()
def delete_location(location_id):
    """
    Elimina una ubicación
    
    Path:
    - location_id: GUID de la ubicación
    
    Returns:
    {
        "success": true,
        "message": "Ubicación eliminada"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (location_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.tblocation WHERE guid = %s"
        cursor.execute(query, (location_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Ubicación eliminada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# FACILITIES (INSTITUCIONES)
# ====================================================================

@api_blueprint.route('/config/facilities', methods=['GET'])
@jwt_required()
def get_facilities():
    """
    Obtiene todas las instituciones/facilities con sus configuraciones
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "name": "...",
                "code": "...",
                "email": "...",
                "contact_person": "...",
                "status": "...",
                "smtp_config": {...},
                "backend_config": {...},
                "whatsapp_config": {...}
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT guid, name, code, email, contact_person, status,
                   smtp_server, smtp_port, smtp_user, smtp_password, smtp_from, smtp_from_name, use_tls,
                   db_user, db_password, db_host, db_port, db_name, base_folder, ipserver,
                   whatsapp_api_url, whatsapp_api_token, whatsapp_phone_number_id, 
                   whatsapp_business_account_id, whatsapp_webhook_verify_token, whatsapp_is_active
            FROM nextris.tbfacility
            ORDER BY name
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        facilities = []
        for row in results:
            facilities.append({
                'guid': row[0],
                'name': row[1],
                'code': row[2],
                'email': row[3],
                'contact_person': row[4],
                'status': row[5],
                'smtp_config': {
                    'smtp_server': row[6],
                    'smtp_port': row[7],
                    'smtp_user': row[8],
                    'smtp_password': row[9],
                    'smtp_from': row[10],
                    'smtp_from_name': row[11],
                    'use_tls': row[12]
                },
                'backend_config': {
                    'db_user': row[13],
                    'db_password': row[14],
                    'db_host': row[15],
                    'db_port': row[16],
                    'db_name': row[17],
                    'base_folder': row[18],
                    'ipserver': row[19]
                },
                'whatsapp_config': {
                    'api_url': row[20],
                    'api_token': row[21],
                    'phone_number_id': row[22],
                    'business_account_id': row[23],
                    'webhook_verify_token': row[24],
                    'is_active': row[25]
                }
            })
        
        return jsonify({
            'success': True,
            'data': facilities
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/facilities', methods=['POST'])
@jwt_required()
def create_facility():
    """
    Crea una nueva institución/facility
    
    Body JSON:
    {
        "name": "string" (required),
        "code": "string" (required),
        "email": "string" (optional),
        "contact_person": "string" (optional),
        "description": "string" (optional),
        "address": "string" (optional),
        "city": "string" (optional),
        "country": "string" (optional),
        "phone": "string" (optional),
        "status": "string" (optional, default: "Active")
    }
    
    Returns:
    {
        "success": true,
        "message": "Facility creada",
        "data": {
            "facility_id": "uuid"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        name = data.get('name')
        code = data.get('code')
        
        if not all([name, code]):
            return jsonify({
                'success': False,
                'message': 'name y code son requeridos'
            }), 400
        
        email = data.get('email', '')
        contact_person = data.get('contact_person', '')
        description = data.get('description', '')
        address = data.get('address', '')
        city = data.get('city', '')
        country = data.get('country', '')
        phone = data.get('phone', '')
        status = data.get('status', 'Active')
        
        # Configuración SMTP (opcional)
        smtp_server = data.get('smtp_server')
        smtp_port = data.get('smtp_port', 587)
        smtp_user = data.get('smtp_user')
        smtp_password = data.get('smtp_password')
        smtp_from = data.get('smtp_from')
        smtp_from_name = data.get('smtp_from_name')
        use_tls = data.get('use_tls', True)
        
        # Configuración Backend (opcional)
        db_user = data.get('db_user')
        db_password = data.get('db_password')
        db_host = data.get('db_host')
        db_port = data.get('db_port', 5432)
        db_name = data.get('db_name')
        base_folder = data.get('base_folder')
        ipserver = data.get('ipserver')
        
        # Configuración WhatsApp (opcional)
        whatsapp_api_url = data.get('whatsapp_api_url')
        whatsapp_api_token = data.get('whatsapp_api_token')
        whatsapp_phone_number_id = data.get('whatsapp_phone_number_id')
        whatsapp_business_account_id = data.get('whatsapp_business_account_id')
        whatsapp_webhook_verify_token = data.get('whatsapp_webhook_verify_token')
        whatsapp_is_active = data.get('whatsapp_is_active', False)
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.tbfacility(
                guid, name, code, email, contact_person, description, 
                address, city, country, phone, status,
                smtp_server, smtp_port, smtp_user, smtp_password, smtp_from, smtp_from_name, use_tls,
                db_user, db_password, db_host, db_port, db_name, base_folder, ipserver,
                whatsapp_api_url, whatsapp_api_token, whatsapp_phone_number_id,
                whatsapp_business_account_id, whatsapp_webhook_verify_token, whatsapp_is_active
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            new_guid, name, code, email, contact_person, description,
            address, city, country, phone, status,
            smtp_server, smtp_port, smtp_user, smtp_password, smtp_from, smtp_from_name, use_tls,
            db_user, db_password, db_host, db_port, db_name, base_folder, ipserver,
            whatsapp_api_url, whatsapp_api_token, whatsapp_phone_number_id,
            whatsapp_business_account_id, whatsapp_webhook_verify_token, whatsapp_is_active
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Facility creada exitosamente',
            'data': {
                'facility_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/facilities/<facility_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_facility(facility_id):
    """
    Actualiza una facility existente
    
    Path:
    - facility_id: GUID de la facility
    
    Body JSON (todos opcionales):
    {
        "name": "string",
        "code": "string",
        "email": "string",
        "contact_person": "string",
        "description": "string",
        "address": "string",
        "city": "string",
        "country": "string",
        "phone": "string",
        "status": "string"
    }
    
    Returns:
    {
        "success": true,
        "message": "Facility actualizada"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tbfacility WHERE guid=%s", (facility_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Facility no encontrada'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'name' in data:
            updates.append("name = %s")
            params.append(data['name'])
        if 'code' in data:
            updates.append("code = %s")
            params.append(data['code'])
        if 'email' in data:
            updates.append("email = %s")
            params.append(data['email'])
        if 'contact_person' in data:
            updates.append("contact_person = %s")
            params.append(data['contact_person'])
        if 'description' in data:
            updates.append("description = %s")
            params.append(data['description'])
        if 'address' in data:
            updates.append("address = %s")
            params.append(data['address'])
        if 'city' in data:
            updates.append("city = %s")
            params.append(data['city'])
        if 'country' in data:
            updates.append("country = %s")
            params.append(data['country'])
        if 'phone' in data:
            updates.append("phone = %s")
            params.append(data['phone'])
        if 'status' in data:
            updates.append("status = %s")
            params.append(data['status'])
        
        # Configuración SMTP
        if 'smtp_server' in data:
            updates.append("smtp_server = %s")
            params.append(data['smtp_server'])
        if 'smtp_port' in data:
            updates.append("smtp_port = %s")
            params.append(data['smtp_port'])
        if 'smtp_user' in data:
            updates.append("smtp_user = %s")
            params.append(data['smtp_user'])
        if 'smtp_password' in data:
            updates.append("smtp_password = %s")
            params.append(data['smtp_password'])
        if 'smtp_from' in data:
            updates.append("smtp_from = %s")
            params.append(data['smtp_from'])
        if 'smtp_from_name' in data:
            updates.append("smtp_from_name = %s")
            params.append(data['smtp_from_name'])
        if 'use_tls' in data:
            updates.append("use_tls = %s")
            params.append(data['use_tls'])
        
        # Configuración Backend
        if 'db_user' in data:
            updates.append("db_user = %s")
            params.append(data['db_user'])
        if 'db_password' in data:
            updates.append("db_password = %s")
            params.append(data['db_password'])
        if 'db_host' in data:
            updates.append("db_host = %s")
            params.append(data['db_host'])
        if 'db_port' in data:
            updates.append("db_port = %s")
            params.append(data['db_port'])
        if 'db_name' in data:
            updates.append("db_name = %s")
            params.append(data['db_name'])
        if 'base_folder' in data:
            updates.append("base_folder = %s")
            params.append(data['base_folder'])
        if 'ipserver' in data:
            updates.append("ipserver = %s")
            params.append(data['ipserver'])
        
        # Configuración WhatsApp
        if 'whatsapp_api_url' in data:
            updates.append("whatsapp_api_url = %s")
            params.append(data['whatsapp_api_url'])
        if 'whatsapp_api_token' in data:
            updates.append("whatsapp_api_token = %s")
            params.append(data['whatsapp_api_token'])
        if 'whatsapp_phone_number_id' in data:
            updates.append("whatsapp_phone_number_id = %s")
            params.append(data['whatsapp_phone_number_id'])
        if 'whatsapp_business_account_id' in data:
            updates.append("whatsapp_business_account_id = %s")
            params.append(data['whatsapp_business_account_id'])
        if 'whatsapp_webhook_verify_token' in data:
            updates.append("whatsapp_webhook_verify_token = %s")
            params.append(data['whatsapp_webhook_verify_token'])
        if 'whatsapp_is_active' in data:
            updates.append("whatsapp_is_active = %s")
            params.append(data['whatsapp_is_active'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(facility_id)
        query = f"UPDATE nextris.tbfacility SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Facility actualizada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/facilities/<facility_id>', methods=['DELETE'])
@jwt_required()
def delete_facility(facility_id):
    """
    Elimina una facility
    
    Path:
    - facility_id: GUID de la facility
    
    Returns:
    {
        "success": true,
        "message": "Facility eliminada"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tbfacility WHERE guid=%s", (facility_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Facility no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.tbfacility WHERE guid = %s"
        cursor.execute(query, (facility_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Facility eliminada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# AGENDAS DE EQUIPOS
# ====================================================================

@api_blueprint.route('/config/equipment/<equipment_id>/schedule', methods=['GET'])
@jwt_required()
def get_equipment_schedule(equipment_id):
    """
    Obtiene la agenda de un equipo específico
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "day": 1,
                "time_from": "08:00",
                "time_to": "17:00"
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT guid, day, timefrom, timeto
            FROM nextris.isagendaequip 
            WHERE idequipment = %s
            ORDER BY day, timefrom
        """
        cursor.execute(query, (equipment_id,))
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        schedule = []
        for row in results:
            schedule.append({
                'guid': row[0],
                'day': row[1],
                'time_from': row[2].strftime('%H:%M') if row[2] else None,
                'time_to': row[3].strftime('%H:%M') if row[3] else None
            })
        
        return jsonify({
            'success': True,
            'data': schedule
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/equipment/<equipment_id>/schedule', methods=['POST'])
@jwt_required()
def create_equipment_schedule(equipment_id):
    """
    Agrega un día de agenda para un equipo
    
    Body JSON:
    {
        "day": number (required, 0-6 donde 0=Domingo),
        "time_from": "HH:MM" (required),
        "time_to": "HH:MM" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Agenda creada",
        "data": {
            "schedule_id": "uuid",
            "day": 1,
            "time_from": "08:00",
            "time_to": "17:00"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        day = data.get('day')
        time_from = data.get('time_from')
        time_to = data.get('time_to')
        
        if day is None or not time_from or not time_to:
            return jsonify({
                'success': False,
                'message': 'day, time_from y time_to son requeridos'
            }), 400
        
        # Validar día (0-6)
        if not isinstance(day, int) or day < 0 or day > 6:
            return jsonify({
                'success': False,
                'message': 'day debe ser un número entre 0 (Domingo) y 6 (Sábado)'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el equipo existe
        cursor.execute("SELECT 1 FROM nextris.isequipment WHERE guid=%s", (equipment_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Equipo no encontrado'
            }), 404
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isagendaequip (guid, idequipment, day, timefrom, timeto)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING guid, day, timefrom, timeto
        """
        
        cursor.execute(query, (new_guid, equipment_id, day, time_from, time_to))
        result = cursor.fetchone()
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Agenda creada exitosamente',
            'data': {
                'schedule_id': result[0],
                'day': result[1],
                'time_from': result[2].strftime('%H:%M') if result[2] else None,
                'time_to': result[3].strftime('%H:%M') if result[3] else None
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/equipment/<equipment_id>/schedule/<schedule_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_equipment_schedule(equipment_id, schedule_id):
    """
    Actualiza un día de agenda de un equipo
    
    Body JSON (todos opcionales):
    {
        "day": number,
        "time_from": "HH:MM",
        "time_to": "HH:MM"
    }
    
    Returns:
    {
        "success": true,
        "message": "Agenda actualizada"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute(
            "SELECT 1 FROM nextris.isagendaequip WHERE guid=%s AND idequipment=%s", 
            (schedule_id, equipment_id)
        )
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Agenda no encontrada'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'day' in data:
            if not isinstance(data['day'], int) or data['day'] < 0 or data['day'] > 6:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'day debe ser un número entre 0 y 6'
                }), 400
            updates.append("day = %s")
            params.append(data['day'])
        
        if 'time_from' in data:
            updates.append("timefrom = %s")
            params.append(data['time_from'])
        
        if 'time_to' in data:
            updates.append("timeto = %s")
            params.append(data['time_to'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(schedule_id)
        query = f"UPDATE nextris.isagendaequip SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Agenda actualizada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/equipment/<equipment_id>/schedule/<schedule_id>', methods=['DELETE'])
@jwt_required()
def delete_equipment_schedule(equipment_id, schedule_id):
    """
    Elimina un día de agenda de un equipo
    
    Returns:
    {
        "success": true,
        "message": "Agenda eliminada"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute(
            "SELECT 1 FROM nextris.isagendaequip WHERE guid=%s AND idequipment=%s", 
            (schedule_id, equipment_id)
        )
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Agenda no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.isagendaequip WHERE guid = %s"
        cursor.execute(query, (schedule_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Agenda eliminada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# GESTIÓN DE USUARIOS
# ====================================================================

@api_blueprint.route('/config/users', methods=['GET'])
@jwt_required()
def get_config_users():
    """
    Obtiene todos los usuarios del sistema
    
    Query Parameters:
    - include_inactive: true/false (opcional, default: false)
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "username": "...",
                "role": "...",
                "name": "...",
                "surname": "...",
                "national_number": "...",
                "email": "...",
                "is_active": true
            }
        ]
    }
    """
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        if include_inactive:
            query = """
                SELECT u.guid, u.username, r.description, u.name, u.surname, 
                       u.nationalnumber, u.mail, u.isactive
                FROM nextris.tbuser u
                INNER JOIN nextris.isrole r ON r.guid = u.idrole
                ORDER BY u.isactive DESC, u.username
            """
        else:
            query = """
                SELECT u.guid, u.username, r.description, u.name, u.surname, 
                       u.nationalnumber, u.mail, u.isactive
                FROM nextris.tbuser u
                INNER JOIN nextris.isrole r ON r.guid = u.idrole
                WHERE u.isactive = 1
                ORDER BY u.username
            """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        users = []
        for row in results:
            users.append({
                'guid': row[0],
                'username': row[1],
                'role': row[2],
                'name': row[3],
                'surname': row[4],
                'national_number': row[5],
                'email': row[6],
                'is_active': bool(row[7])
            })
        
        return jsonify({
            'success': True,
            'data': users
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users', methods=['POST'])
@jwt_required()
def create_config_user():
    """
    Crea un nuevo usuario
    
    Body JSON:
    {
        "username": "string" (required),
        "email": "string" (required),
        "name": "string" (required),
        "surname": "string" (required),
        "national_number": "string" (optional),
        "role_id": "uuid" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Usuario creado",
        "data": {
            "user_id": "uuid",
            "username": "..."
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        username = data.get('username')
        email = data.get('email')
        name = data.get('name')
        surname = data.get('surname')
        role_id = data.get('role_id')
        
        if not all([username, email, name, surname, role_id]):
            return jsonify({
                'success': False,
                'message': 'username, email, name, surname y role_id son requeridos'
            }), 400
        
        national_number = data.get('national_number', '')
        temporary_password = generate_temporary_password()
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar si el username ya existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'El nombre de usuario ya existe'
            }), 400
        
        # Verificar que el rol existe
        cursor.execute("SELECT 1 FROM nextris.isrole WHERE guid = %s", (role_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Rol no encontrado'
            }), 404
        
        # Hashear contraseña
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(temporary_password)
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.tbuser(
                guid, username, mail, password, name, surname, 
                nationalnumber, idrole, isactive, first_login
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, 1)
            RETURNING guid, username
        """
        
        cursor.execute(query, (
            new_guid, username, email, password_hash, name, surname,
            national_number, role_id
        ))
        
        result = cursor.fetchone()

        full_name = f"{name} {surname}".strip()
        send_new_user_credentials_email(
            connection=connection,
            email=email,
            username=username,
            temporary_password=temporary_password,
            full_name=full_name
        )
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuario creado exitosamente',
            'data': {
                'user_id': result[0],
                'username': result[1]
            }
        }), 201
        
    except Exception as e:
        try:
            connection.rollback()
            cursor.close()
            connection.close()
        except Exception:
            pass
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_config_user(user_id):
    """
    Actualiza un usuario existente
    
    Body JSON (todos opcionales):
    {
        "username": "string",
        "email": "string",
        "name": "string",
        "surname": "string",
        "national_number": "string",
        "role_id": "uuid"
    }
    
    Returns:
    {
        "success": true,
        "message": "Usuario actualizado"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el usuario existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'username' in data:
            # Verificar que el nuevo username no esté en uso por otro usuario
            cursor.execute(
                "SELECT 1 FROM nextris.tbuser WHERE username = %s AND guid != %s",
                (data['username'], user_id)
            )
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'El nombre de usuario ya está en uso'
                }), 400
            updates.append("username = %s")
            params.append(data['username'])
        
        if 'email' in data:
            updates.append("mail = %s")
            params.append(data['email'])
        
        if 'name' in data:
            updates.append("name = %s")
            params.append(data['name'])
        
        if 'surname' in data:
            updates.append("surname = %s")
            params.append(data['surname'])
        
        if 'national_number' in data:
            updates.append("nationalnumber = %s")
            params.append(data['national_number'])
        
        if 'role_id' in data:
            # Verificar que el rol existe
            cursor.execute("SELECT 1 FROM nextris.isrole WHERE guid = %s", (data['role_id'],))
            if not cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'Rol no encontrado'
                }), 404
            updates.append("idrole = %s")
            params.append(data['role_id'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(user_id)
        query = f"UPDATE nextris.tbuser SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuario actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/deactivate', methods=['POST'])
@jwt_required()
def deactivate_user(user_id):
    """
    Desactiva un usuario (no lo elimina)
    
    Returns:
    {
        "success": true,
        "message": "Usuario desactivado"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        
        query = "UPDATE nextris.tbuser SET isactive = 0 WHERE guid = %s"
        cursor.execute(query, (user_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuario desactivado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/activate', methods=['POST'])
@jwt_required()
def activate_user(user_id):
    """
    Activa un usuario previamente desactivado
    
    Returns:
    {
        "success": true,
        "message": "Usuario activado"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        
        query = "UPDATE nextris.tbuser SET isactive = 1 WHERE guid = %s"
        cursor.execute(query, (user_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuario activado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/reset-password', methods=['POST'])
@jwt_required()
def reset_user_password(user_id):
    """
    Resetea la contraseña de un usuario
    
    Body JSON:
    {
        "new_password": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Contraseña reseteada"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'new_password' not in data:
            return jsonify({
                'success': False,
                'message': 'new_password es requerido'
            }), 400
        
        new_password = data.get('new_password')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el usuario existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        
        # Hashear la nueva contraseña
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(new_password)
        
        # Actualizar contraseña y marcar como primer login
        query = """
            UPDATE nextris.tbuser 
            SET password = %s, first_login = 1 
            WHERE guid = %s
        """
        cursor.execute(query, (password_hash, user_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Contraseña reseteada exitosamente. El usuario deberá cambiarla en su primer inicio de sesión.'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>', methods=['DELETE'])
@jwt_required()
def delete_config_user(user_id):
    """
    Elimina permanentemente un usuario (usar con precaución)
    Recomendado usar deactivate en su lugar
    
    Returns:
    {
        "success": true,
        "message": "Usuario eliminado"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        
        query = "DELETE FROM nextris.tbuser WHERE guid = %s"
        cursor.execute(query, (user_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuario eliminado permanentemente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# DATOS MEDICOS DEL USUARIO (FIRMA DIGITAL)
# ====================================================================

@api_blueprint.route('/config/users/<user_id>/medical-data', methods=['GET'])
@jwt_required()
def get_user_medical_data(user_id):
    """
    Obtiene datos medicos de un usuario
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuracion de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        ensure_user_medical_table(connection)
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT aclaracion_firma, matricula_nacional, firma_digital, firma_habilitada
            FROM nextris.tbuser_medical_data
            WHERE user_id = %s
            """,
            (user_id,)
        )
        result = cursor.fetchone()

        cursor.close()
        connection.close()

        if result:
            return jsonify({
                'success': True,
                'data': {
                    'aclaracion_firma': result[0],
                    'matricula_nacional': result[1],
                    'firma_digital': result[2],
                    'firma_habilitada': bool(result[3])
                }
            }), 200

        return jsonify({
            'success': True,
            'data': {
                'aclaracion_firma': '',
                'matricula_nacional': '',
                'firma_digital': None,
                'firma_habilitada': False
            }
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/medical-data', methods=['POST'])
@jwt_required()
def save_user_medical_data(user_id):
    """
    Crea o actualiza datos medicos de un usuario

    Body (multipart/form-data):
    - aclaracion_firma (required)
    - matricula_nacional (required)
    - firma_habilitada (optional, true/false)
    - firma_digital (optional file: png/jpg/jpeg)
    """
    try:
        aclaracion_firma = request.form.get('aclaracion_firma')
        matricula_nacional = request.form.get('matricula_nacional')
        firma_habilitada = request.form.get('firma_habilitada', 'false').lower() == 'true'

        if not aclaracion_firma or not matricula_nacional:
            return jsonify({
                'success': False,
                'message': 'aclaracion_firma y matricula_nacional son requeridos'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuracion de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        ensure_user_medical_table(connection)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        firma_filename = None
        if 'firma_digital' in request.files:
            file = request.files['firma_digital']
            if file and file.filename:
                allowed_extensions = {'png', 'jpg', 'jpeg'}
                file_extension = file.filename.rsplit('.', 1)[1].lower()
                if file_extension not in allowed_extensions:
                    cursor.close()
                    connection.close()
                    return jsonify({
                        'success': False,
                        'message': 'Tipo de archivo no permitido'
                    }), 400

                upload_dir = os.path.join(os.getcwd(), 'media', 'firmas')
                os.makedirs(upload_dir, exist_ok=True)

                safe_name = secure_filename(file.filename)
                unique_filename = f"{user_id}_{uuid.uuid4().hex}_{safe_name}"
                firma_path = os.path.join(upload_dir, unique_filename)
                file.save(firma_path)

                firma_filename = unique_filename

        cursor.execute(
            "SELECT 1 FROM nextris.tbuser_medical_data WHERE user_id = %s",
            (user_id,)
        )
        exists = cursor.fetchone()

        if exists:
            if firma_filename:
                cursor.execute(
                    """
                    UPDATE nextris.tbuser_medical_data
                    SET aclaracion_firma = %s,
                        matricula_nacional = %s,
                        firma_digital = %s,
                        firma_habilitada = %s,
                        fecha_actualizacion = NOW()
                    WHERE user_id = %s
                    """,
                    (aclaracion_firma, matricula_nacional, firma_filename, firma_habilitada, user_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE nextris.tbuser_medical_data
                    SET aclaracion_firma = %s,
                        matricula_nacional = %s,
                        firma_habilitada = %s,
                        fecha_actualizacion = NOW()
                    WHERE user_id = %s
                    """,
                    (aclaracion_firma, matricula_nacional, firma_habilitada, user_id),
                )
        else:
            cursor.execute(
                """
                INSERT INTO nextris.tbuser_medical_data
                    (user_id, aclaracion_firma, matricula_nacional, firma_digital, firma_habilitada, fecha_creacion, fecha_actualizacion)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (user_id, aclaracion_firma, matricula_nacional, firma_filename, firma_habilitada),
            )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Datos medicos guardados correctamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# RELACIÓN USUARIOS - UBICACIONES
# ====================================================================

@api_blueprint.route('/config/users/<user_id>/locations', methods=['GET'])
@jwt_required()
def get_config_user_locations(user_id):
    """
    Obtiene las ubicaciones asociadas a un usuario

    Path:
    - user_id: GUID del usuario
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        cursor.execute(
            """
            SELECT rul.location_id, l.name, rul.is_default
            FROM nextris.rel_user_location rul
            LEFT JOIN nextris.tblocation l ON l.guid = rul.location_id
            WHERE rul.user_id = %s
            ORDER BY l.name
            """,
            (user_id,)
        )

        results = cursor.fetchall()

        cursor.close()
        connection.close()

        locations = [
            {
                'location_id': row[0],
                'location_name': row[1],
                'is_default': bool(row[2]),
            }
            for row in results
        ]

        return jsonify({
            'success': True,
            'data': locations
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/locations', methods=['PUT', 'PATCH'])
@jwt_required()
def set_config_user_locations(user_id):
    """
    Reemplaza las ubicaciones asociadas a un usuario

    Path:
    - user_id: GUID del usuario

    Body JSON:
    {
        "location_ids": ["guid-1", "guid-2", ...] (required)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        location_ids = data.get('location_ids')

        if not isinstance(location_ids, list):
            return jsonify({
                'success': False,
                'message': 'location_ids debe ser una lista'
            }), 400

        normalized_location_ids = [location_id for location_id in dict.fromkeys(location_ids) if location_id]

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        if normalized_location_ids:
            cursor.execute(
                "SELECT guid FROM nextris.tblocation WHERE guid = ANY(%s)",
                (normalized_location_ids,)
            )
            existing_location_ids = {row[0] for row in cursor.fetchall()}
            missing_location_ids = [location_id for location_id in normalized_location_ids if location_id not in existing_location_ids]

            if missing_location_ids:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'Una o más ubicaciones no existen',
                    'missing_location_ids': missing_location_ids
                }), 400

        cursor.execute(
            "DELETE FROM nextris.rel_user_location WHERE user_id = %s",
            (user_id,)
        )

        if normalized_location_ids:
            insert_query = """
                INSERT INTO nextris.rel_user_location (user_id, location_id, is_default)
                VALUES (%s, %s, %s)
            """
            insert_values = [
                (user_id, location_id, False)
                for location_id in normalized_location_ids
            ]
            cursor.executemany(insert_query, insert_values)

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicaciones de usuario actualizadas exitosamente',
            'data': {
                'user_id': user_id,
                'location_ids': normalized_location_ids,
                'count': len(normalized_location_ids)
            }
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@api_blueprint.route('/config/users/<user_id>/locations', methods=['POST'])
@jwt_required()
def add_user_location(user_id):
    """
    Crea la relación entre un usuario y una ubicación

    Body JSON:
    {
        "location_id": "uuid" (required),
        "is_default": true/false (optional, default: false)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        location_id = data.get('location_id')
        is_default = bool(data.get('is_default', False))

        if not location_id:
            return jsonify({
                'success': False,
                'message': 'location_id es requerido'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (location_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404

        cursor.execute(
            "SELECT 1 FROM nextris.rel_user_location WHERE user_id=%s AND location_id=%s",
            (user_id, location_id)
        )
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'La relación ya existe'
            }), 409

        if is_default:
            cursor.execute(
                "UPDATE nextris.rel_user_location SET is_default = false WHERE user_id = %s",
                (user_id,)
            )

        cursor.execute(
            """
            INSERT INTO nextris.rel_user_location (user_id, location_id, is_default)
            VALUES (%s, %s, %s)
            """,
            (user_id, location_id, is_default)
        )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicación asociada exitosamente',
            'data': {
                'user_id': user_id,
                'location_id': location_id,
                'is_default': is_default
            }
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/locations/<location_id>', methods=['DELETE'])
@jwt_required()
def remove_user_location(user_id, location_id):
    """
    Elimina la relación entre un usuario y una ubicación

    Path:
    - user_id: GUID del usuario
    - location_id: GUID de la ubicación
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute(
            "SELECT 1 FROM nextris.rel_user_location WHERE user_id=%s AND location_id=%s",
            (user_id, location_id)
        )
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Relación no encontrada'
            }), 404

        cursor.execute(
            "DELETE FROM nextris.rel_user_location WHERE user_id = %s AND location_id = %s",
            (user_id, location_id)
        )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicación desasociada exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# ROLES
# ====================================================================

@api_blueprint.route('/config/roles', methods=['GET'])
@jwt_required()
def get_roles():
    """
    Obtiene todos los roles del sistema
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "..."
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = "SELECT guid, description FROM nextris.isrole ORDER BY description"
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        roles = []
        for row in results:
            roles.append({
                'guid': row[0],
                'description': row[1]
            })
        
        return jsonify({
            'success': True,
            'data': roles
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# GESTIÓN DE PACIENTES
# ====================================================================

@api_blueprint.route('/config/patients', methods=['GET'])
@jwt_required()
def get_config_patients():
    """
    Obtiene todos los pacientes del sistema
    
    Query Parameters:
    - include_inactive: true/false (opcional, default: false)
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "name": "...",
                "national_code": "...",
                "birthdate": "...",
                "username": "...",
                "status": "...",
                "last_login": "..."
            }
        ]
    }
    """
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        if include_inactive:
            query = """
                SELECT p.guid, CONCAT(dp.surname, ' ', dp.name) as name, 
                       dp.nationalcode, dp.birthdate, p.username, p.status, p.lastlogin
                FROM nextris.tbuser_patient as p
                LEFT JOIN nextris.datapatient dp on dp.guid=p.datapatient_id
                ORDER BY p.guid ASC
            """
        else:
            query = """
                SELECT p.guid, CONCAT(dp.surname, ' ', dp.name) as name, 
                       dp.nationalcode, dp.birthdate, p.username, p.status, p.lastlogin
                FROM nextris.tbuser_patient as p
                LEFT JOIN nextris.datapatient dp on dp.guid=p.datapatient_id
                WHERE p.status = 'Active'
                ORDER BY p.guid ASC
            """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        patients = []
        for row in results:
            patients.append({
                'guid': row[0],
                'name': row[1],
                'national_code': row[2],
                'birthdate': row[3].strftime('%d/%m/%Y') if row[3] else None,
                'username': row[4],
                'status': row[5],
                'last_login': row[6].isoformat() if row[6] else None
            })
        
        return jsonify({
            'success': True,
            'data': patients
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patients/<patient_id>', methods=['GET'])
@jwt_required()
def get_config_patient(patient_id):
    """
    Obtiene los datos completos de un paciente
    
    Returns:
    {
        "success": true,
        "data": {
            "patient_id": "...",
            "username": "...",
            "status": "...",
            "name": "...",
            "surname": "...",
            "national_code": "...",
            "birthdate": "...",
            "patient_id_number": "...",
            "sex_code": "...",
            "phone": "...",
            "email": "..."
        }
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener datos de tbuser_patient
        user_query = """
            SELECT username, datapatient_id, status
            FROM nextris.tbuser_patient
            WHERE guid = %s
        """
        cursor.execute(user_query, (patient_id,))
        user_result = cursor.fetchone()
        
        if not user_result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        username = user_result[0]
        datapatient_id = user_result[1]
        status = user_result[2]
        
        # Obtener datos de datapatient
        patient_query = """
            SELECT name, surname, nationalcode, birthdate, patientid, 
                   sexcode, phone, email
            FROM nextris.datapatient
            WHERE guid = %s
        """
        cursor.execute(patient_query, (datapatient_id,))
        patient_result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not patient_result:
            return jsonify({
                'success': False,
                'message': 'Datos del paciente no encontrados'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'patient_id': patient_id,
                'username': username,
                'status': status,
                'name': patient_result[0],
                'surname': patient_result[1],
                'national_code': patient_result[2],
                'birthdate': patient_result[3].strftime('%Y-%m-%d') if patient_result[3] else None,
                'patient_id_number': patient_result[4],  # CUIL
                'sex_code': patient_result[5],
                'phone': patient_result[6],
                'email': patient_result[7]
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patients', methods=['POST'])
@jwt_required()
def create_config_patient():
    """
    Crea un nuevo paciente
    
    Body JSON:
    {
        "name": "string" (required),
        "surname": "string" (required),
        "national_code": "string" (required),
        "birthdate": "YYYY-MM-DD" (required),
        "sex_code": "string" (required),
        "patient_id_number": "string" (optional, CUIL),
        "phone": "string" (optional),
        "email": "string" (optional),
        "username": "string" (optional, se genera automáticamente si no se proporciona),
        "health_card": "string" (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Paciente creado",
        "data": {
            "patient_id": "uuid",
            "username": "...",
            "default_password": "next"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        name = data.get('name')
        surname = data.get('surname')
        national_code = data.get('national_code')
        birthdate = data.get('birthdate')
        sex_code = data.get('sex_code')
        
        if not all([name, surname, national_code, birthdate, sex_code]):
            return jsonify({
                'success': False,
                'message': 'name, surname, national_code, birthdate y sex_code son requeridos'
            }), 400
        
        patient_id_number = data.get('patient_id_number', '')
        phone = data.get('phone', '')
        email = data.get('email', '')
        health_card = data.get('health_card', '')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Insertar en datapatient
        datapatient_guid = str(uuid.uuid4())
        
        insert_datapatient = """
            INSERT INTO nextris.datapatient(
                guid, surname, name, nationalcode, birthdate, patientid, 
                sexcode, phone, email, healthcard
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING guid
        """
        
        cursor.execute(insert_datapatient, (
            datapatient_guid, surname, name, national_code, birthdate, 
            patient_id_number, sex_code, phone, email, health_card
        ))
        
        # Generar username
        custom_username = data.get('username', '').strip()
        
        if custom_username:
            base_username = custom_username.lower().replace(' ', '')
        else:
            # Generar automáticamente: primera letra del nombre + apellido
            base_username = (name[0] + surname).lower().replace(' ', '')
        
        # Verificar si el username ya existe
        cursor.execute(
            "SELECT COUNT(*) FROM nextris.tbuser_patient WHERE username LIKE %s",
            (f"{base_username}%",)
        )
        count = cursor.fetchone()[0]
        
        if count > 0:
            # Buscar el siguiente número disponible
            for i in range(1, 100):
                test_username = f"{base_username}{i:02d}"
                cursor.execute(
                    "SELECT COUNT(*) FROM nextris.tbuser_patient WHERE username = %s",
                    (test_username,)
                )
                if cursor.fetchone()[0] == 0:
                    username = test_username
                    break
            else:
                username = f"{base_username}{count + 1:02d}"
        else:
            username = base_username
        
        # Hashear contraseña
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash('next')
        
        # Insertar en tbuser_patient
        user_patient_guid = str(uuid.uuid4())
        
        insert_user_patient = """
            INSERT INTO nextris.tbuser_patient (
                guid, username, password, status, datapatient_id
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING guid
        """
        
        cursor.execute(insert_user_patient, (
            user_patient_guid, username, password_hash, 'Active', datapatient_guid
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Paciente creado exitosamente',
            'data': {
                'patient_id': user_patient_guid,
                'username': username,
                'default_password': 'next'
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patients/<patient_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_config_patient(patient_id):
    """
    Actualiza un paciente existente
    
    Body JSON (todos opcionales):
    {
        "username": "string",
        "name": "string",
        "surname": "string",
        "national_code": "string",
        "birthdate": "YYYY-MM-DD",
        "patient_id_number": "string",
        "sex_code": "string",
        "phone": "string",
        "email": "string"
    }
    
    Returns:
    {
        "success": true,
        "message": "Paciente actualizado"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener datapatient_id
        cursor.execute(
            "SELECT datapatient_id FROM nextris.tbuser_patient WHERE guid = %s",
            (patient_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        datapatient_id = result[0]
        
        # Actualizar username si se proporciona
        if 'username' in data:
            cursor.execute(
                "UPDATE nextris.tbuser_patient SET username = %s WHERE guid = %s",
                (data['username'], patient_id)
            )
        
        # Actualizar datos del paciente
        patient_updates = []
        patient_params = []
        
        if 'name' in data:
            patient_updates.append("name = %s")
            patient_params.append(data['name'])
        
        if 'surname' in data:
            patient_updates.append("surname = %s")
            patient_params.append(data['surname'])
        
        if 'national_code' in data:
            patient_updates.append("nationalcode = %s")
            patient_params.append(data['national_code'])
        
        if 'birthdate' in data:
            patient_updates.append("birthdate = %s")
            patient_params.append(data['birthdate'])
        
        if 'patient_id_number' in data:
            patient_updates.append("patientid = %s")
            patient_params.append(data['patient_id_number'])
        
        if 'sex_code' in data:
            patient_updates.append("sexcode = %s")
            patient_params.append(data['sex_code'])
        
        if 'phone' in data:
            patient_updates.append("phone = %s")
            patient_params.append(data['phone'])
        
        if 'email' in data:
            patient_updates.append("email = %s")
            patient_params.append(data['email'])
        
        if patient_updates:
            patient_params.append(datapatient_id)
            query = f"UPDATE nextris.datapatient SET {', '.join(patient_updates)} WHERE guid = %s"
            cursor.execute(query, patient_params)
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Paciente actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patients/<patient_id>/deactivate', methods=['POST'])
@jwt_required()
def deactivate_patient(patient_id):
    """
    Desactiva un paciente
    
    Returns:
    {
        "success": true,
        "message": "Paciente desactivado"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tbuser_patient WHERE guid=%s", (patient_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        query = "UPDATE nextris.tbuser_patient SET status = 'Inactive' WHERE guid = %s"
        cursor.execute(query, (patient_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Paciente desactivado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patients/<patient_id>/activate', methods=['POST'])
@jwt_required()
def activate_patient(patient_id):
    """
    Activa un paciente previamente desactivado
    
    Returns:
    {
        "success": true,
        "message": "Paciente activado"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tbuser_patient WHERE guid=%s", (patient_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        query = "UPDATE nextris.tbuser_patient SET status = 'Active' WHERE guid = %s"
        cursor.execute(query, (patient_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Paciente activado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patients/<patient_id>/reset-password', methods=['POST'])
@jwt_required()
def reset_patient_password(patient_id):
    """
    Resetea la contraseña de un paciente
    
    Body JSON:
    {
        "new_password": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Contraseña reseteada"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'new_password' not in data:
            return jsonify({
                'success': False,
                'message': 'new_password es requerido'
            }), 400
        
        new_password = data.get('new_password')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el paciente existe
        cursor.execute("SELECT 1 FROM nextris.tbuser_patient WHERE guid=%s", (patient_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        # Hashear la nueva contraseña
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(new_password)
        
        query = "UPDATE nextris.tbuser_patient SET password = %s WHERE guid = %s"
        cursor.execute(query, (password_hash, patient_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Contraseña reseteada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# GESTIÓN DE MÉDICOS SOLICITANTES (REQUESTING PHYSICIANS)
# ====================================================================

@api_blueprint.route('/config/requesting-physicians', methods=['GET'])
@jwt_required()
def get_requesting_physicians():
    """
    Obtiene todos los médicos solicitantes
    
    Query Parameters:
    - location_id: filtrar por localización (opcional)
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "...",
                "phone": "...",
                "mail": "...",
                "note": "...",
                "location_id": "...",
                "location_name": "..."
            }
        ]
    }
    """
    try:
        location_id = request.args.get('location_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT 
                p.guid,
                p.description,
                p.phone,
                p.mail,
                p.note,
                p.location_id,
                l.name as location_name
            FROM nextris.isrequestingphysician p
            LEFT JOIN nextris.tblocation l ON p.location_id = l.guid
        """
        
        params = []
        if location_id:
            query += " WHERE p.location_id = %s"
            params.append(location_id)
        
        query += " ORDER BY p.description"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        physicians = []
        for row in rows:
            physicians.append({
                'guid': row[0],
                'description': row[1],
                'phone': row[2],
                'mail': row[3],
                'note': row[4],
                'location_id': row[5],
                'location_name': row[6]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': physicians
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/requesting-physicians/<physician_id>', methods=['GET'])
@jwt_required()
def get_requesting_physician(physician_id):
    """
    Obtiene un médico solicitante por ID
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "...",
            "description": "...",
            "phone": "...",
            "mail": "...",
            "note": "...",
            "location_id": "...",
            "location_name": "..."
        }
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT 
                p.guid,
                p.description,
                p.phone,
                p.mail,
                p.note,
                p.location_id,
                l.name as location_name
            FROM nextris.isrequestingphysician p
            LEFT JOIN nextris.tblocation l ON p.location_id = l.guid
            WHERE p.guid = %s
        """
        
        cursor.execute(query, (physician_id,))
        row = cursor.fetchone()
        
        if not row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Médico solicitante no encontrado'
            }), 404
        
        physician = {
            'guid': row[0],
            'description': row[1],
            'phone': row[2],
            'mail': row[3],
            'note': row[4],
            'location_id': row[5],
            'location_name': row[6]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': physician
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/requesting-physicians', methods=['POST'])
@jwt_required()
def create_requesting_physician():
    """
    Crea un nuevo médico solicitante
    
    Request Body:
    {
        "description": "Dr. Juan Pérez",  // requerido
        "phone": "+1234567890",           // opcional
        "mail": "juan.perez@example.com", // opcional
        "note": "Especialidad",           // opcional
        "location_id": "guid"             // opcional
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "...",
            "description": "...",
            ...
        },
        "message": "Médico solicitante creado exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'description' not in data:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400
        
        description = data.get('description', '').strip()
        phone = data.get('phone', '').strip()
        mail = data.get('mail', '').strip()
        note = data.get('note', '').strip()
        location_id = data.get('location_id')
        
        if not description:
            return jsonify({
                'success': False,
                'message': 'description no puede estar vacío'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar si el location_id existe (si se proporciona)
        if location_id:
            cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (location_id,))
            if not cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'La localización especificada no existe'
                }), 400
        
        # Generar GUID
        import uuid
        physician_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isrequestingphysician 
            (guid, description, phone, mail, note, location_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            physician_guid,
            description,
            phone if phone else None,
            mail if mail else None,
            note if note else None,
            location_id if location_id else None
        ))
        
        connection.commit()
        
        # Obtener el médico creado con información de localización
        cursor.execute("""
            SELECT 
                p.guid,
                p.description,
                p.phone,
                p.mail,
                p.note,
                p.location_id,
                l.name as location_name
            FROM nextris.isrequestingphysician p
            LEFT JOIN nextris.tblocation l ON p.location_id = l.guid
            WHERE p.guid = %s
        """, (physician_guid,))
        
        row = cursor.fetchone()
        physician = {
            'guid': row[0],
            'description': row[1],
            'phone': row[2],
            'mail': row[3],
            'note': row[4],
            'location_id': row[5],
            'location_name': row[6]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': physician,
            'message': 'Médico solicitante creado exitosamente'
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/requesting-physicians/<physician_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_requesting_physician(physician_id):
    """
    Actualiza un médico solicitante existente
    
    Request Body:
    {
        "description": "Dr. Juan Pérez",  // opcional
        "phone": "+1234567890",           // opcional
        "mail": "juan.perez@example.com", // opcional
        "note": "Especialidad",           // opcional
        "location_id": "guid"             // opcional (null para quitar)
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "...",
            "description": "...",
            ...
        },
        "message": "Médico solicitante actualizado exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No se proporcionaron datos para actualizar'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el médico existe
        cursor.execute("SELECT 1 FROM nextris.isrequestingphysician WHERE guid=%s", (physician_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Médico solicitante no encontrado'
            }), 404
        
        # Verificar location_id si se proporciona
        if 'location_id' in data and data['location_id']:
            cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (data['location_id'],))
            if not cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'La localización especificada no existe'
                }), 400
        
        # Construir query de actualización
        update_fields = []
        params = []
        
        if 'description' in data:
            update_fields.append("description = %s")
            params.append(data['description'].strip())
        
        if 'phone' in data:
            update_fields.append("phone = %s")
            params.append(data['phone'].strip() if data['phone'] else None)
        
        if 'mail' in data:
            update_fields.append("mail = %s")
            params.append(data['mail'].strip() if data['mail'] else None)
        
        if 'note' in data:
            update_fields.append("note = %s")
            params.append(data['note'].strip() if data['note'] else None)
        
        if 'location_id' in data:
            update_fields.append("location_id = %s")
            params.append(data['location_id'] if data['location_id'] else None)
        
        if not update_fields:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No se proporcionaron campos válidos para actualizar'
            }), 400
        
        params.append(physician_id)
        query = f"UPDATE nextris.isrequestingphysician SET {', '.join(update_fields)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        # Obtener el médico actualizado
        cursor.execute("""
            SELECT 
                p.guid,
                p.description,
                p.phone,
                p.mail,
                p.note,
                p.location_id,
                l.name as location_name
            FROM nextris.isrequestingphysician p
            LEFT JOIN nextris.tblocation l ON p.location_id = l.guid
            WHERE p.guid = %s
        """, (physician_id,))
        
        row = cursor.fetchone()
        physician = {
            'guid': row[0],
            'description': row[1],
            'phone': row[2],
            'mail': row[3],
            'note': row[4],
            'location_id': row[5],
            'location_name': row[6]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': physician,
            'message': 'Médico solicitante actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/requesting-physicians/<physician_id>', methods=['DELETE'])
@jwt_required()
def delete_requesting_physician(physician_id):
    """
    Elimina un médico solicitante
    
    Returns:
    {
        "success": true,
        "message": "Médico solicitante eliminado exitosamente"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el médico existe
        cursor.execute("SELECT 1 FROM nextris.isrequestingphysician WHERE guid=%s", (physician_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Médico solicitante no encontrado'
            }), 404
        
        query = "DELETE FROM nextris.isrequestingphysician WHERE guid = %s"
        cursor.execute(query, (physician_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Médico solicitante eliminado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# GESTIÓN DE AGENDAS DE MÉDICOS
# ====================================================================

@api_blueprint.route('/config/physician-schedules', methods=['GET'])
@jwt_required()
def get_physician_schedules():
    """
    Obtiene todas las agendas de médicos
    
    Query Parameters:
    - physician_id: filtrar por médico (opcional)
    - location_id: filtrar por localización (opcional)
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "physician_id": "...",
                "physician_name": "...",
                "day": "Lunes",
                "time_from": "08:00",
                "time_to": "12:00",
                "init_day": "2024-01-01",
                "finish_day": "2024-12-31",
                "location_id": "...",
                "location_name": "..."
            }
        ]
    }
    """
    try:
        physician_id = request.args.get('physician_id')
        location_id = request.args.get('location_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT 
                a.guid,
                a.idmed as physician_id,
                CONCAT(u.name, ' ', u.surname) as physician_name,
                a.day,
                a.timefrom,
                a.timeto,
                a.initday,
                a.finishday,
                a.location_id,
                l.name as location_name
            FROM nextris.isagendameditem a
            LEFT JOIN nextris.tbuser u ON a.idmed = u.guid
            LEFT JOIN nextris.tblocation l ON a.location_id = l.guid
            WHERE 1=1
        """
        
        params = []
        if physician_id:
            query += " AND a.idmed = %s"
            params.append(physician_id)
        
        if location_id:
            query += " AND a.location_id = %s"
            params.append(location_id)
        
        query += " ORDER BY u.name, u.surname, a.day, a.timefrom"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        schedules = []
        for row in rows:
            schedules.append({
                'guid': row[0],
                'physician_id': row[1],
                'physician_name': row[2],
                'day': row[3],
                'time_from': str(row[4]) if row[4] else None,
                'time_to': str(row[5]) if row[5] else None,
                'init_day': str(row[6]) if row[6] else None,
                'finish_day': str(row[7]) if row[7] else None,
                'location_id': row[8],
                'location_name': row[9]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': schedules
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/physician-schedules', methods=['POST'])
@jwt_required()
def create_physician_schedule():
    """
    Crea una nueva agenda para un médico
    
    Request Body:
    {
        "physician_id": "guid",    // requerido
        "day": "Lunes",            // requerido
        "time_from": "08:00",      // requerido
        "time_to": "12:00",        // requerido
        "init_day": "2024-01-01",  // opcional
        "finish_day": "2024-12-31",// opcional
        "location_id": "guid"      // opcional
    }
    
    Returns:
    {
        "success": true,
        "data": {...},
        "message": "Agenda creada exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        required_fields = ['physician_id', 'day', 'time_from', 'time_to']
        for field in required_fields:
            if not data or field not in data:
                return jsonify({
                    'success': False,
                    'message': f'{field} es requerido'
                }), 400
        
        physician_id = data.get('physician_id')
        day = data.get('day', '').strip()
        time_from = data.get('time_from', '').strip()
        time_to = data.get('time_to', '').strip()
        init_day = data.get('init_day')
        finish_day = data.get('finish_day')
        location_id = data.get('location_id')
        
        # Validar día de la semana
        valid_days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        if day not in valid_days:
            return jsonify({
                'success': False,
                'message': f'Día inválido. Debe ser uno de: {", ".join(valid_days)}'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el médico existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (physician_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Médico no encontrado'
            }), 404
        
        # Verificar location_id si se proporciona
        if location_id:
            cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (location_id,))
            if not cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'La localización especificada no existe'
                }), 400
        
        # Generar GUID
        import uuid
        schedule_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isagendameditem 
            (guid, idmed, day, timefrom, timeto, initday, finishday, location_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            schedule_guid,
            physician_id,
            day,
            time_from,
            time_to,
            init_day if init_day else None,
            finish_day if finish_day else None,
            location_id if location_id else None
        ))
        
        connection.commit()
        
        # Obtener la agenda creada
        cursor.execute("""
            SELECT 
                a.guid,
                a.idmed as physician_id,
                CONCAT(u.name, ' ', u.surname) as physician_name,
                a.day,
                a.timefrom,
                a.timeto,
                a.initday,
                a.finishday,
                a.location_id,
                l.name as location_name
            FROM nextris.isagendameditem a
            LEFT JOIN nextris.tbuser u ON a.idmed = u.guid
            LEFT JOIN nextris.tblocation l ON a.location_id = l.guid
            WHERE a.guid = %s
        """, (schedule_guid,))
        
        row = cursor.fetchone()
        schedule = {
            'guid': row[0],
            'physician_id': row[1],
            'physician_name': row[2],
            'day': row[3],
            'time_from': str(row[4]) if row[4] else None,
            'time_to': str(row[5]) if row[5] else None,
            'init_day': str(row[6]) if row[6] else None,
            'finish_day': str(row[7]) if row[7] else None,
            'location_id': row[8],
            'location_name': row[9]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': schedule,
            'message': 'Agenda creada exitosamente'
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/physician-schedules/<schedule_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_physician_schedule(schedule_id):
    """
    Actualiza una agenda de médico existente
    
    Request Body:
    {
        "day": "Lunes",            // opcional
        "time_from": "08:00",      // opcional
        "time_to": "12:00",        // opcional
        "init_day": "2024-01-01",  // opcional
        "finish_day": "2024-12-31",// opcional
        "location_id": "guid"      // opcional
    }
    
    Returns:
    {
        "success": true,
        "data": {...},
        "message": "Agenda actualizada exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No se proporcionaron datos para actualizar'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que la agenda existe
        cursor.execute("SELECT 1 FROM nextris.isagendameditem WHERE guid=%s", (schedule_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Agenda no encontrada'
            }), 404
        
        # Validar día si se proporciona
        if 'day' in data:
            valid_days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
            if data['day'] not in valid_days:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': f'Día inválido. Debe ser uno de: {", ".join(valid_days)}'
                }), 400
        
        # Verificar location_id si se proporciona
        if 'location_id' in data and data['location_id']:
            cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (data['location_id'],))
            if not cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'La localización especificada no existe'
                }), 400
        
        # Construir query de actualización
        update_fields = []
        params = []
        
        if 'day' in data:
            update_fields.append("day = %s")
            params.append(data['day'])
        
        if 'time_from' in data:
            update_fields.append("timefrom = %s")
            params.append(data['time_from'])
        
        if 'time_to' in data:
            update_fields.append("timeto = %s")
            params.append(data['time_to'])
        
        if 'init_day' in data:
            update_fields.append("initday = %s")
            params.append(data['init_day'] if data['init_day'] else None)
        
        if 'finish_day' in data:
            update_fields.append("finishday = %s")
            params.append(data['finish_day'] if data['finish_day'] else None)
        
        if 'location_id' in data:
            update_fields.append("location_id = %s")
            params.append(data['location_id'] if data['location_id'] else None)
        
        if not update_fields:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No se proporcionaron campos válidos para actualizar'
            }), 400
        
        params.append(schedule_id)
        query = f"UPDATE nextris.isagendameditem SET {', '.join(update_fields)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        # Obtener la agenda actualizada
        cursor.execute("""
            SELECT 
                a.guid,
                a.idmed as physician_id,
                CONCAT(u.name, ' ', u.surname) as physician_name,
                a.day,
                a.timefrom,
                a.timeto,
                a.initday,
                a.finishday,
                a.location_id,
                l.name as location_name
            FROM nextris.isagendameditem a
            LEFT JOIN nextris.tbuser u ON a.idmed = u.guid
            LEFT JOIN nextris.tblocation l ON a.location_id = l.guid
            WHERE a.guid = %s
        """, (schedule_id,))
        
        row = cursor.fetchone()
        schedule = {
            'guid': row[0],
            'physician_id': row[1],
            'physician_name': row[2],
            'day': row[3],
            'time_from': str(row[4]) if row[4] else None,
            'time_to': str(row[5]) if row[5] else None,
            'init_day': str(row[6]) if row[6] else None,
            'finish_day': str(row[7]) if row[7] else None,
            'location_id': row[8],
            'location_name': row[9]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': schedule,
            'message': 'Agenda actualizada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/physician-schedules/<schedule_id>', methods=['DELETE'])
@jwt_required()
def delete_physician_schedule(schedule_id):
    """
    Elimina una agenda de médico
    
    Returns:
    {
        "success": true,
        "message": "Agenda eliminada exitosamente"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que la agenda existe
        cursor.execute("SELECT 1 FROM nextris.isagendameditem WHERE guid=%s", (schedule_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Agenda no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.isagendameditem WHERE guid = %s"
        cursor.execute(query, (schedule_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Agenda eliminada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# GESTIÓN DE GRUPOS DE ESTUDIO POR MÉDICO
# ====================================================================

@api_blueprint.route('/config/physicians/<physician_id>/study-groups', methods=['GET'])
@jwt_required()
def get_physician_study_groups(physician_id):
    """
    Obtiene los grupos de estudio que lee un médico
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "studygroup_id": "...",
                "studygroup_name": "..."
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT 
                r.guid,
                r.studygroup_id,
                g.description as studygroup_name
            FROM nextris.rel_medico_studygroup r
            LEFT JOIN nextris.isstudytypegroup g ON r.studygroup_id = g.guid
            WHERE r.med_id = %s
            ORDER BY g.description
        """
        
        cursor.execute(query, (physician_id,))
        rows = cursor.fetchall()
        
        study_groups = []
        for row in rows:
            study_groups.append({
                'guid': row[0],
                'studygroup_id': row[1],
                'studygroup_name': row[2]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': study_groups
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/physicians/<physician_id>/study-groups', methods=['POST'])
@jwt_required()
def add_physician_study_group(physician_id):
    """
    Agrega un grupo de estudio a un médico
    
    Request Body:
    {
        "studygroup_id": "guid"  // requerido
    }
    
    Returns:
    {
        "success": true,
        "data": {...},
        "message": "Grupo de estudio agregado exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'studygroup_id' not in data:
            return jsonify({
                'success': False,
                'message': 'studygroup_id es requerido'
            }), 400
        
        studygroup_id = data.get('studygroup_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el médico existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (physician_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Médico no encontrado'
            }), 404
        
        # Verificar que el grupo de estudio existe
        cursor.execute("SELECT 1 FROM nextris.isstudytypegroup WHERE guid=%s", (studygroup_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Grupo de estudio no encontrado'
            }), 404
        
        # Verificar que la relación no existe ya
        cursor.execute(
            "SELECT 1 FROM nextris.rel_medico_studygroup WHERE med_id=%s AND studygroup_id=%s",
            (physician_id, studygroup_id)
        )
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'El médico ya tiene asignado este grupo de estudio'
            }), 400
        
        # Generar GUID
        import uuid
        relation_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.rel_medico_studygroup 
            (guid, med_id, studygroup_id)
            VALUES (%s, %s, %s)
        """
        
        cursor.execute(query, (relation_guid, physician_id, studygroup_id))
        connection.commit()
        
        # Obtener la relación creada
        cursor.execute("""
            SELECT 
                r.guid,
                r.studygroup_id,
                g.description as studygroup_name
            FROM nextris.rel_medico_studygroup r
            LEFT JOIN nextris.isstudytypegroup g ON r.studygroup_id = g.guid
            WHERE r.guid = %s
        """, (relation_guid,))
        
        row = cursor.fetchone()
        relation = {
            'guid': row[0],
            'studygroup_id': row[1],
            'studygroup_name': row[2]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': relation,
            'message': 'Grupo de estudio agregado exitosamente'
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/physicians/<physician_id>/study-groups/<relation_id>', methods=['DELETE'])
@jwt_required()
def remove_physician_study_group(physician_id, relation_id):
    """
    Elimina un grupo de estudio de un médico
    
    Returns:
    {
        "success": true,
        "message": "Grupo de estudio eliminado exitosamente"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que la relación existe y pertenece al médico
        cursor.execute(
            "SELECT 1 FROM nextris.rel_medico_studygroup WHERE guid=%s AND med_id=%s",
            (relation_id, physician_id)
        )
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Relación no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.rel_medico_studygroup WHERE guid = %s"
        cursor.execute(query, (relation_id,))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Grupo de estudio eliminado exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# OBRAS SOCIALES (HEALTH INSURANCES)
# ====================================================================

@api_blueprint.route('/config/insurances', methods=['GET'])
@jwt_required()
def get_insurances():
    """
    Obtiene todas las obras sociales

    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "OSDE",
                "isactive": 1,
                "externalcode": "...",
                "headerdescription": "..."
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        query = """
            SELECT guid, description, isactive, externalcode, headerdescription
            FROM nextris.ishealthinsurances
            ORDER BY description
        """
        cursor.execute(query)
        results = cursor.fetchall()

        cursor.close()
        connection.close()

        insurances = []
        for row in results:
            insurances.append({
                'guid': row[0],
                'description': row[1],
                'isactive': row[2],
                'externalcode': row[3],
                'headerdescription': row[4]
            })

        return jsonify({
            'success': True,
            'data': insurances
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/insurances', methods=['POST'])
@jwt_required()
def create_insurance():
    """
    Crea una nueva obra social

    Body JSON:
    {
        "description": "string" (required),
        "externalcode": "string" (optional),
        "headerdescription": "string" (optional)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        description = data.get('description')

        if not description:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        new_guid = str(uuid.uuid4())

        query = """
            INSERT INTO nextris.ishealthinsurances (guid, description, isactive, externalcode, headerdescription)
            VALUES (%s, %s, 1, %s, %s)
        """

        cursor.execute(query, (
            new_guid,
            description,
            data.get('externalcode'),
            data.get('headerdescription')
        ))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Obra social creada exitosamente',
            'data': {
                'guid': new_guid
            }
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/insurances/<insurance_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_insurance(insurance_id):
    """
    Actualiza una obra social existente

    Path:
    - insurance_id: GUID de la obra social

    Body JSON:
    {
        "description": "string",
        "isactive": 1|0,
        "externalcode": "string",
        "headerdescription": "string"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.ishealthinsurances WHERE guid=%s", (insurance_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Obra social no encontrada'
            }), 404

        update_fields = []
        values = []

        allowed_fields = {
            'description': 'description',
            'isactive': 'isactive',
            'externalcode': 'externalcode',
            'headerdescription': 'headerdescription'
        }

        for json_field, db_field in allowed_fields.items():
            if json_field in data:
                update_fields.append(f"{db_field} = %s")
                values.append(data[json_field])

        if not update_fields:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400

        values.append(insurance_id)
        query = f"UPDATE nextris.ishealthinsurances SET {', '.join(update_fields)} WHERE guid = %s"

        cursor.execute(query, values)
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Obra social actualizada exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/insurances/<insurance_id>', methods=['DELETE'])
@jwt_required()
def delete_insurance(insurance_id):
    """
    Elimina una obra social y sus relaciones con ubicaciones

    Path:
    - insurance_id: GUID de la obra social
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.ishealthinsurances WHERE guid=%s", (insurance_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Obra social no encontrada'
            }), 404

        # Eliminar relaciones con ubicaciones
        cursor.execute("DELETE FROM nextris.rel_insurance_location WHERE insurance_id = %s", (insurance_id,))

        # Eliminar la obra social
        cursor.execute("DELETE FROM nextris.ishealthinsurances WHERE guid = %s", (insurance_id,))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Obra social eliminada exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# RELACIÓN OBRAS SOCIALES - UBICACIONES
# ====================================================================

@api_blueprint.route('/config/insurances/<insurance_id>/locations', methods=['GET'])
@jwt_required()
def get_insurance_locations(insurance_id):
    """
    Obtiene las ubicaciones asociadas a una obra social

    Path:
    - insurance_id: GUID de la obra social

    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "rel-guid",
                "location_id": "...",
                "location_name": "...",
                "is_default": false
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        query = """
            SELECT ril.guid, ril.location_id, l.name as location_name, ril.is_default
            FROM nextris.rel_insurance_location ril
            LEFT JOIN nextris.tblocation l ON l.guid = ril.location_id
            WHERE ril.insurance_id = %s
            ORDER BY l.name
        """
        cursor.execute(query, (insurance_id,))
        results = cursor.fetchall()

        cursor.close()
        connection.close()

        locations = []
        for row in results:
            locations.append({
                'guid': row[0],
                'location_id': row[1],
                'location_name': row[2],
                'is_default': row[3]
            })

        return jsonify({
            'success': True,
            'data': locations
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/insurances/<insurance_id>/locations', methods=['POST'])
@jwt_required()
def add_insurance_location(insurance_id):
    """
    Agrega una relación entre una obra social y una ubicación

    Path:
    - insurance_id: GUID de la obra social

    Body JSON:
    {
        "location_id": "string" (required),
        "is_default": false (optional)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        location_id = data.get('location_id')

        if not location_id:
            return jsonify({
                'success': False,
                'message': 'location_id es requerido'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        # Verificar que la obra social existe
        cursor.execute("SELECT 1 FROM nextris.ishealthinsurances WHERE guid=%s", (insurance_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Obra social no encontrada'
            }), 404

        # Verificar que no exista ya la relación
        cursor.execute(
            "SELECT 1 FROM nextris.rel_insurance_location WHERE insurance_id=%s AND location_id=%s",
            (insurance_id, location_id)
        )
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'La relación ya existe'
            }), 409

        new_guid = str(uuid.uuid4())
        is_default = data.get('is_default', False)

        query = """
            INSERT INTO nextris.rel_insurance_location (guid, insurance_id, location_id, is_default)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (new_guid, insurance_id, location_id, is_default))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicación asociada exitosamente',
            'data': {
                'guid': new_guid
            }
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/insurances/<insurance_id>/locations', methods=['PUT', 'PATCH'])
@jwt_required()
def set_insurance_locations(insurance_id):
    """
    Reemplaza las ubicaciones asociadas a una obra social

    Path:
    - insurance_id: GUID de la obra social

    Body JSON:
    {
        "location_ids": ["guid-1", "guid-2", ...] (required)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        location_ids = data.get('location_ids')

        if not isinstance(location_ids, list):
            return jsonify({
                'success': False,
                'message': 'location_ids debe ser una lista'
            }), 400

        normalized_location_ids = [location_id for location_id in dict.fromkeys(location_ids) if location_id]

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.ishealthinsurances WHERE guid=%s", (insurance_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Obra social no encontrada'
            }), 404

        if normalized_location_ids:
            cursor.execute(
                "SELECT guid FROM nextris.tblocation WHERE guid = ANY(%s)",
                (normalized_location_ids,)
            )
            existing_location_ids = {row[0] for row in cursor.fetchall()}
            missing_location_ids = [location_id for location_id in normalized_location_ids if location_id not in existing_location_ids]

            if missing_location_ids:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'Una o más ubicaciones no existen',
                    'missing_location_ids': missing_location_ids
                }), 400

        cursor.execute(
            "DELETE FROM nextris.rel_insurance_location WHERE insurance_id = %s",
            (insurance_id,)
        )

        if normalized_location_ids:
            insert_query = """
                INSERT INTO nextris.rel_insurance_location (guid, insurance_id, location_id, is_default)
                VALUES (%s, %s, %s, %s)
            """
            insert_values = [
                (str(uuid.uuid4()), insurance_id, location_id, False)
                for location_id in normalized_location_ids
            ]
            cursor.executemany(insert_query, insert_values)

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicaciones actualizadas exitosamente',
            'data': {
                'insurance_id': insurance_id,
                'location_ids': normalized_location_ids,
                'count': len(normalized_location_ids)
            }
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/insurances/<insurance_id>/locations/<relation_id>', methods=['DELETE'])
@jwt_required()
def remove_insurance_location(insurance_id, relation_id):
    """
    Elimina la relación entre una obra social y una ubicación

    Path:
    - insurance_id: GUID de la obra social
    - relation_id: GUID de la relación en rel_insurance_location
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute(
            "SELECT 1 FROM nextris.rel_insurance_location WHERE guid=%s AND insurance_id=%s",
            (relation_id, insurance_id)
        )
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Relación no encontrada'
            }), 404

        cursor.execute("DELETE FROM nextris.rel_insurance_location WHERE guid = %s", (relation_id,))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicación desasociada exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# DOMINIOS DE PACIENTES (PATIENT DOMAINS)
# ====================================================================

@api_blueprint.route('/config/patient-domains', methods=['GET'])
@jwt_required()
def get_patient_domains():
    """
    Obtiene todos los dominios de pacientes

    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "GENERAL",
                "note": "...",
                "code": "GEN"
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        query = "SELECT guid, description, note, code FROM nextris.ispatientdomain ORDER BY description"
        cursor.execute(query)
        results = cursor.fetchall()

        cursor.close()
        connection.close()

        domains = []
        for row in results:
            domains.append({
                'guid': row[0],
                'description': row[1],
                'note': row[2],
                'code': row[3]
            })

        return jsonify({
            'success': True,
            'data': domains
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patient-domains', methods=['POST'])
@jwt_required()
def create_patient_domain():
    """
    Crea un nuevo dominio de pacientes

    Body JSON:
    {
        "description": "string" (required),
        "code": "string" (optional, max 8 chars),
        "note": "string" (optional)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        description = data.get('description')

        if not description:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        new_guid = str(uuid.uuid4())

        query = """
            INSERT INTO nextris.ispatientdomain (guid, description, code, note)
            VALUES (%s, %s, %s, %s)
        """

        cursor.execute(query, (
            new_guid,
            description,
            data.get('code'),
            data.get('note')
        ))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Dominio de pacientes creado exitosamente',
            'data': {
                'guid': new_guid
            }
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patient-domains/<domain_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_patient_domain(domain_id):
    """
    Actualiza un dominio de pacientes existente

    Path:
    - domain_id: GUID del dominio

    Body JSON:
    {
        "description": "string",
        "code": "string",
        "note": "string"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.ispatientdomain WHERE guid=%s", (domain_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Dominio de pacientes no encontrado'
            }), 404

        update_fields = []
        values = []

        allowed_fields = {
            'description': 'description',
            'code': 'code',
            'note': 'note'
        }

        for json_field, db_field in allowed_fields.items():
            if json_field in data:
                update_fields.append(f"{db_field} = %s")
                values.append(data[json_field])

        if not update_fields:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400

        values.append(domain_id)
        query = f"UPDATE nextris.ispatientdomain SET {', '.join(update_fields)} WHERE guid = %s"

        cursor.execute(query, values)
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Dominio de pacientes actualizado exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patient-domains/<domain_id>', methods=['DELETE'])
@jwt_required()
def delete_patient_domain(domain_id):
    """
    Elimina un dominio de pacientes.
    Las relaciones en rel_user_patientdomain se eliminan en cascada (FK ON DELETE CASCADE).
    No se permite eliminar si hay pacientes asignados a este dominio.

    Path:
    - domain_id: GUID del dominio
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.ispatientdomain WHERE guid=%s", (domain_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Dominio de pacientes no encontrado'
            }), 404

        # Verificar que no haya pacientes asignados a este dominio
        cursor.execute("SELECT COUNT(*) FROM nextris.datapatient WHERE id_patientdomain = %s", (domain_id,))
        count = cursor.fetchone()[0]

        if count > 0:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'No se puede eliminar: hay {count} pacientes asignados a este dominio'
            }), 400

        cursor.execute("DELETE FROM nextris.ispatientdomain WHERE guid = %s", (domain_id,))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Dominio de pacientes eliminado exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
