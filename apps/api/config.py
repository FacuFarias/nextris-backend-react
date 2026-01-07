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


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.routes import config
        return config
    except:
        return None


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
            FROM nextris.config_workflow
            ORDER BY fecha_actualizacion DESC
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
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT st.guid, st.code, st.description, stg.description as studygroup, 
                   ap.description as bodypart, md.externalcode as modality, 
                   st.rvu, st.nofviews
            FROM nextris.isstudytype as st
            INNER JOIN nextris.isstudytypegroup stg on stg.guid=st.studygroup_id
            INNER JOIN nextris.isanatomicalpart ap on ap.guid=st.bodypart_id
            INNER JOIN nextris.ismodality md on md.guid=st.modality_id
            ORDER BY st.description ASC
        """
        
        cursor.execute(query)
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


# ====================================================================
# EQUIPOS (MÁQUINAS)
# ====================================================================

@api_blueprint.route('/config/equipment', methods=['GET'])
@jwt_required()
def get_equipment():
    """
    Obtiene equipos/máquinas filtrados por ubicación y opcionalmente por modalidad
    
    Query Parameters:
    - location_id (OBLIGATORIO): Filtrar equipos por ubicación
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
        # Obtener parámetro location_id (OBLIGATORIO)
        location_id = request.args.get('location_id')
        
        if not location_id:
            return jsonify({
                'success': False,
                'message': 'El parámetro location_id es obligatorio'
            }), 400
        
        # Obtener parámetro modality_id (OPCIONAL)
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
            WHERE e.location_id = %s
        """
        
        params = [location_id]
        
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
    Obtiene todas las ubicaciones
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "...",
                "address": "...",
                "phone": "..."
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
        
        query = "SELECT guid, name, code, address, phone FROM nextris.tblocation ORDER BY name"
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        locations = []
        for row in results:
            locations.append({
                'guid': row[0],
                'name': row[1],
                'code': row[2],
                'address': row[3],
                'phone': row[4]
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
        "description": "string" (required),
        "address": "string" (optional),
        "phone": "string" (optional)
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
        code = data.get('code', '')
        
        if not name:
            return jsonify({
                'success': False,
                'message': 'name es requerido'
            }), 400
        
        address = data.get('address', '')
        phone = data.get('phone', '')
        
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
            INSERT INTO nextris.tblocation(guid, name, code, address, phone) 
            VALUES (%s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (new_guid, name, code, address, phone))
        
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
    Obtiene todas las instituciones/facilities
    
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
                "status": "..."
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
            SELECT guid, name, code, email, contact_person, status
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
                'status': row[5]
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
                address, city, country, phone, status
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            new_guid, name, code, email, contact_person, description,
            address, city, country, phone, status
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
