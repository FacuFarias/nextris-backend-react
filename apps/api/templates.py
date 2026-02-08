# -*- encoding: utf-8 -*-
"""
API REST para gestión de plantillas de informes predefinidos
Endpoints para CRUD de templates/plantillas de reportes médicos
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
import uuid
from apps.api import api_blueprint


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.routes import config
        return config
    except:
        return None


# ====================================================================
# ENDPOINTS PARA PLANTILLAS DE INFORMES PREDEFINIDOS
# ====================================================================

@api_blueprint.route('/templates', methods=['GET'])
@jwt_required()
def get_templates():
    """
    Obtiene lista de todas las plantillas de informes predefinidos
    
    Headers:
    - Authorization: Bearer <token>
    
    Query Parameters:
    - study_type_id (optional): Filtrar por tipo de estudio
    - modality_id (optional): Filtrar por modalidad
    - bodypart_id (optional): Filtrar por parte del cuerpo
    - simple (optional): Si es true, devuelve solo guid, title y study_type_description
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "title": "Plantilla de RX Tórax",
                "study_type_id": "uuid",
                "study_type_description": "RX Tórax",
                "modality_id": "uuid",
                "modality_description": "Radiografía",
                "bodypart_id": "uuid",
                "bodypart_description": "Tórax",
                "findings": "...",
                "technique": "...",
                "impression": "...",
                "conclusion": "..."
            }
        ]
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de BD'
            }), 500
        
        study_type_id = request.args.get('study_type_id')
        modality_id = request.args.get('modality_id')
        bodypart_id = request.args.get('bodypart_id')
        simple = request.args.get('simple', 'false').lower() == 'true'
        
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        
        # Construir query con filtros dinámicos
        query = """
            SELECT 
                ip.guid, 
                ip.tittle, 
                ip.studytype_id,
                ist.description as study_type_description,
                ist.modality_id,
                im.description as modality_description,
                ist.bodypart_id,
                iap.description as bodypart_description,
                ip.findings,
                ip.technique,
                ip.impression,
                ip.conclusion
            FROM nextris.tbinfpredef ip
            LEFT JOIN nextris.isstudytype ist ON ip.studytype_id = ist.guid
            LEFT JOIN nextris.ismodality im ON ist.modality_id = im.guid
            LEFT JOIN nextris.isanatomicalpart iap ON ist.bodypart_id = iap.guid
            WHERE 1=1
        """
        
        params = []
        
        if study_type_id:
            query += " AND ip.studytype_id = %s"
            params.append(study_type_id)
        
        if modality_id:
            query += " AND ist.modality_id = %s"
            params.append(modality_id)
        
        if bodypart_id:
            query += " AND ist.bodypart_id = %s"
            params.append(bodypart_id)
        
        query += " ORDER BY ip.tittle ASC"
        
        cur.execute(query, params)
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        templates = []
        for row in results:
            if simple:
                templates.append({
                    'guid': row[0],
                    'title': row[1] or '',
                    'study_type_description': row[3] or ''
                })
            else:
                templates.append({
                    'guid': row[0],
                    'title': row[1] or '',
                    'study_type_id': row[2],
                    'study_type_description': row[3] or '',
                    'modality_id': row[4],
                    'modality_description': row[5] or '',
                    'bodypart_id': row[6],
                    'bodypart_description': row[7] or '',
                    'findings': row[8] or '',
                    'technique': row[9] or '',
                    'impression': row[10] or '',
                    'conclusion': row[11] or ''
                })
        
        return jsonify({
            'success': True,
            'data': templates
        }), 200
        
    except Exception as e:
        print(f"[API TEMPLATES] Error en get_templates: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/templates/<template_id>', methods=['GET'])
@jwt_required()
def get_template(template_id):
    """
    Obtiene una plantilla específica por su ID
    
    Headers:
    - Authorization: Bearer <token>
    
    Path Parameters:
    - template_id: GUID de la plantilla
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid",
            "title": "Plantilla de RX Tórax",
            "study_type_id": "uuid",
            "study_type_description": "RX Tórax",
            "modality_id": "uuid",
            "modality_description": "Radiografía",
            "bodypart_id": "uuid",
            "bodypart_description": "Tórax",
            "findings": "...",
            "technique": "...",
            "impression": "...",
            "conclusion": "..."
        }
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de BD'
            }), 500
        
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        
        query = """
            SELECT 
                ip.guid, 
                ip.tittle, 
                ip.studytype_id,
                ist.description as study_type_description,
                ist.modality_id,
                im.description as modality_description,
                ist.bodypart_id,
                iap.description as bodypart_description,
                ip.findings,
                ip.technique,
                ip.impression,
                ip.conclusion
            FROM nextris.tbinfpredef ip
            LEFT JOIN nextris.isstudytype ist ON ip.studytype_id = ist.guid
            LEFT JOIN nextris.ismodality im ON ist.modality_id = im.guid
            LEFT JOIN nextris.isanatomicalpart iap ON ist.bodypart_id = iap.guid
            WHERE ip.guid = %s
        """
        
        cur.execute(query, (template_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if result:
            template = {
                'guid': result[0],
                'title': result[1] or '',
                'study_type_id': result[2],
                'study_type_description': result[3] or '',
                'modality_id': result[4],
                'modality_description': result[5] or '',
                'bodypart_id': result[6],
                'bodypart_description': result[7] or '',
                'findings': result[8] or '',
                'technique': result[9] or '',
                'impression': result[10] or '',
                'conclusion': result[11] or ''
            }
            
            return jsonify({
                'success': True,
                'data': template
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Plantilla no encontrada'
            }), 404
            
    except Exception as e:
        print(f"[API TEMPLATES] Error en get_template: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/templates', methods=['POST'])
@jwt_required()
def create_template():
    """
    Crea una nueva plantilla de informe predefinido
    
    Headers:
    - Authorization: Bearer <token>
    
    Body:
    {
        "title": "Nombre de la plantilla",
        "study_type_id": "uuid del tipo de estudio",
        "findings": "Texto de hallazgos",
        "technique": "Texto de técnica",
        "impression": "Texto de impresión diagnóstica",
        "conclusion": "Texto de conclusión",
        "is_default": false
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid-generado",
            "message": "Plantilla creada exitosamente"
        }
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de BD'
            }), 500
        
        data = request.get_json()
        
        # Validar campos requeridos
        if not data.get('title'):
            return jsonify({
                'success': False,
                'message': 'El título es requerido'
            }), 400
        
        if not data.get('study_type_id'):
            return jsonify({
                'success': False,
                'message': 'El tipo de estudio es requerido'
            }), 400
        
        # Extraer datos
        title = data.get('title', '').strip()
        study_type_id = data.get('study_type_id')
        findings = data.get('findings', '').strip()
        technique = data.get('technique', '').strip()
        impression = data.get('impression', '').strip()
        conclusion = data.get('conclusion', '').strip()
        is_default = data.get('is_default', False)
        
        # Generar nuevo GUID
        new_guid = str(uuid.uuid4())
        
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        
        # Insertar plantilla
        insert_query = """
            INSERT INTO nextris.tbinfpredef 
            (guid, tittle, findings, impression, technique, conclusion, studytype_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cur.execute(insert_query, (
            new_guid,
            title,
            findings,
            impression,
            technique,
            conclusion,
            study_type_id
        ))
        
        # Si es default, actualizar el tipo de estudio
        if is_default:
            update_query = """
                UPDATE nextris.isstudytype 
                SET default_predef_id = %s 
                WHERE guid = %s
            """
            cur.execute(update_query, (new_guid, study_type_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[API TEMPLATES] Plantilla creada exitosamente - GUID: {new_guid}")
        
        return jsonify({
            'success': True,
            'data': {
                'guid': new_guid,
                'message': 'Plantilla creada exitosamente'
            }
        }), 201
        
    except Exception as e:
        print(f"[API TEMPLATES] Error en create_template: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/templates/<template_id>', methods=['PUT'])
@jwt_required()
def edit_template(template_id):
    """
    Edita una plantilla de informe existente
    
    Headers:
    - Authorization: Bearer <token>
    
    Path Parameters:
    - template_id: GUID de la plantilla
    
    Body:
    {
        "title": "Nombre actualizado",
        "study_type_id": "uuid del tipo de estudio",
        "findings": "Texto actualizado",
        "technique": "Texto actualizado",
        "impression": "Texto actualizado",
        "conclusion": "Texto actualizado"
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid",
            "message": "Plantilla actualizada exitosamente"
        }
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de BD'
            }), 500
        
        data = request.get_json()
        
        # Validar que la plantilla existe
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        
        check_query = "SELECT guid FROM nextris.tbinfpredef WHERE guid = %s"
        cur.execute(check_query, (template_id,))
        
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Plantilla no encontrada'
            }), 404
        
        # Extraer datos para actualizar
        title = data.get('title', '').strip()
        study_type_id = data.get('study_type_id')
        findings = data.get('findings', '').strip()
        technique = data.get('technique', '').strip()
        impression = data.get('impression', '').strip()
        conclusion = data.get('conclusion', '').strip()
        
        # Actualizar plantilla
        update_query = """
            UPDATE nextris.tbinfpredef 
            SET tittle = %s,
                findings = %s,
                impression = %s,
                technique = %s,
                conclusion = %s,
                studytype_id = %s
            WHERE guid = %s
        """
        
        cur.execute(update_query, (
            title,
            findings,
            impression,
            technique,
            conclusion,
            study_type_id,
            template_id
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[API TEMPLATES] Plantilla actualizada exitosamente - GUID: {template_id}")
        
        return jsonify({
            'success': True,
            'data': {
                'guid': template_id,
                'message': 'Plantilla actualizada exitosamente'
            }
        }), 200
        
    except Exception as e:
        print(f"[API TEMPLATES] Error en edit_template: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/templates/<template_id>', methods=['DELETE'])
@jwt_required()
def delete_template(template_id):
    """
    Elimina una plantilla de informe
    
    Headers:
    - Authorization: Bearer <token>
    
    Path Parameters:
    - template_id: GUID de la plantilla
    
    Returns:
    {
        "success": true,
        "data": {
            "message": "Plantilla eliminada exitosamente"
        }
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de BD'
            }), 500
        
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        
        # Verificar que la plantilla existe
        check_query = "SELECT guid FROM nextris.tbinfpredef WHERE guid = %s"
        cur.execute(check_query, (template_id,))
        
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Plantilla no encontrada'
            }), 404
        
        # Verificar si está siendo usada como default en algún tipo de estudio
        default_check = """
            SELECT guid, description 
            FROM nextris.isstudytype 
            WHERE default_predef_id = %s
        """
        cur.execute(default_check, (template_id,))
        default_usage = cur.fetchall()
        
        if default_usage:
            # Opcional: podrías eliminar la referencia o rechazar la eliminación
            # Por ahora, solo limpiaremos la referencia
            clear_default = """
                UPDATE nextris.isstudytype 
                SET default_predef_id = NULL 
                WHERE default_predef_id = %s
            """
            cur.execute(clear_default, (template_id,))
            print(f"[API TEMPLATES] Referencias de default eliminadas para la plantilla {template_id}")
        
        # Eliminar la plantilla
        delete_query = "DELETE FROM nextris.tbinfpredef WHERE guid = %s"
        cur.execute(delete_query, (template_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[API TEMPLATES] Plantilla eliminada exitosamente - GUID: {template_id}")
        
        return jsonify({
            'success': True,
            'data': {
                'message': 'Plantilla eliminada exitosamente'
            }
        }), 200
        
    except Exception as e:
        print(f"[API TEMPLATES] Error en delete_template: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/templates/set-default', methods=['POST'])
@jwt_required()
def set_default_template():
    """
    Establece una plantilla como predeterminada para un tipo de estudio
    
    Headers:
    - Authorization: Bearer <token>
    
    Body:
    {
        "study_type_id": "uuid del tipo de estudio",
        "template_id": "uuid de la plantilla"
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "message": "Plantilla establecida como predeterminada exitosamente"
        }
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de BD'
            }), 500
        
        data = request.get_json()
        
        # Validar campos requeridos
        study_type_id = data.get('study_type_id')
        template_id = data.get('template_id')
        
        if not study_type_id:
            return jsonify({
                'success': False,
                'message': 'El ID del tipo de estudio es requerido'
            }), 400
        
        if not template_id:
            return jsonify({
                'success': False,
                'message': 'El ID de la plantilla es requerido'
            }), 400
        
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        
        # Verificar que el tipo de estudio existe
        check_study_type = "SELECT guid FROM nextris.isstudytype WHERE guid = %s"
        cur.execute(check_study_type, (study_type_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Tipo de estudio no encontrado'
            }), 404
        
        # Verificar que la plantilla existe y pertenece al tipo de estudio
        check_template = "SELECT guid FROM nextris.tbinfpredef WHERE guid = %s AND studytype_id = %s"
        cur.execute(check_template, (template_id, study_type_id))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Plantilla no encontrada o no pertenece al tipo de estudio especificado'
            }), 404
        
        # Limpiar isdefault de todas las plantillas del mismo tipo de estudio
        clear_defaults = """
            UPDATE nextris.tbinfpredef 
            SET isdefault = 0 
            WHERE studytype_id = %s
        """
        cur.execute(clear_defaults, (study_type_id,))
        
        # Establecer la plantilla como default en tbinfpredef
        update_template = """
            UPDATE nextris.tbinfpredef 
            SET isdefault = 1 
            WHERE guid = %s
        """
        cur.execute(update_template, (template_id,))
        
        # Establecer la referencia en isstudytype
        update_study_type = """
            UPDATE nextris.isstudytype 
            SET default_predef_id = %s 
            WHERE guid = %s
        """
        cur.execute(update_study_type, (template_id, study_type_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[API TEMPLATES] Plantilla {template_id} establecida como default para tipo de estudio {study_type_id}")
        
        return jsonify({
            'success': True,
            'data': {
                'message': 'Plantilla establecida como predeterminada exitosamente'
            }
        }), 200
        
    except Exception as e:
        print(f"[API TEMPLATES] Error en set_default_template: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
