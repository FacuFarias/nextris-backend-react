# -*- encoding: utf-8 -*-
"""
API REST para gestión de reportes médicos y plantillas predefinidas
Endpoints para CRUD de reportes, plantillas y generación de PDFs
"""

from flask import request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
from apps.api import api_blueprint
import uuid
import os


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.routes import config
        return config
    except:
        return None


@api_blueprint.route('/report-templates/<template_id>', methods=['GET'])
@jwt_required()
def get_report_template(template_id):
    """
    Obtiene los textos de una plantilla de reporte
    
    Path:
    - template_id: GUID de la plantilla
    
    Returns:
    {
        "success": true,
        "data": {
            "report": "Contenido de la plantilla"
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
        
        cursor.execute("SELECT report FROM nextris.isreporttemplate WHERE guid=%s", (template_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if result:
            return jsonify({
                'success': True,
                'data': {
                    'report': result[0] or ''
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Plantilla no encontrada'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/study-types/<study_type_id>/default-template', methods=['GET'])
@jwt_required()
def get_default_template_for_study_type(study_type_id):
    """
    Obtiene el ID de plantilla predefinida por defecto para un tipo de estudio
    
    Path:
    - study_type_id: GUID del tipo de estudio
    
    Returns:
    {
        "success": true,
        "data": {
            "default_template_id": "uuid"
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
        
        cursor.execute("SELECT default_predef_id FROM nextris.isstudytype WHERE guid=%s", (study_type_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'default_template_id': result[0] if result and result[0] else None
            }
        }), 200
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/predefined-reports', methods=['GET'])
@jwt_required()
def get_predefined_reports():
    """
    Obtiene lista de todos los reportes predefinidos
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "title": "Título",
                "study_type": "Descripción del tipo de estudio"
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
            SELECT ip.guid, ip.tittle, ist.description
            FROM nextris.tbinfpredef ip
            LEFT JOIN nextris.isstudytype ist ON ip.studytype_id = ist.guid
            ORDER BY ip.tittle ASC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        predefined = []
        for row in results:
            predefined.append({
                'guid': row[0],
                'title': row[1] or '',
                'study_type': row[2] or ''
            })
        
        return jsonify({
            'success': True,
            'data': predefined
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/predefined-reports/<predef_id>', methods=['GET'])
@jwt_required()
def get_predefined_report(predef_id):
    """
    Obtiene datos de un reporte predefinido específico
    
    Path:
    - predef_id: GUID del reporte predefinido
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid",
            "title": "Título",
            "findings": "Hallazgos",
            "impression": "Impresión",
            "technique": "Técnica",
            "conclusion": "Conclusión",
            "study_type_id": "uuid"
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
            SELECT guid, tittle, findings, impression, technique, conclusion, studytype_id
            FROM nextris.tbinfpredef 
            WHERE guid=%s
        """
        
        cursor.execute(query, (predef_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if result:
            return jsonify({
                'success': True,
                'data': {
                    'guid': result[0],
                    'title': result[1] or '',
                    'findings': result[2] or '',
                    'impression': result[3] or '',
                    'technique': result[4] or '',
                    'conclusion': result[5] or '',
                    'study_type_id': result[6]
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Reporte predefinido no encontrado'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/predefined-reports', methods=['POST'])
@jwt_required()
def create_predefined_report():
    """
    Crea un nuevo reporte predefinido
    
    Body JSON:
    {
        "title": "string" (required),
        "study_type_id": "uuid" (required),
        "findings": "string" (optional),
        "technique": "string" (optional),
        "impression": "string" (optional),
        "conclusion": "string" (optional),
        "is_default": boolean (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte predefinido creado exitosamente",
        "data": {
            "predef_id": "uuid"
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
        
        title = data.get('title')
        study_type_id = data.get('study_type_id')
        
        if not title or not study_type_id:
            return jsonify({
                'success': False,
                'message': 'title y study_type_id son campos requeridos'
            }), 400
        
        findings = data.get('findings', '')
        technique = data.get('technique', '')
        impression = data.get('impression', '')
        conclusion = data.get('conclusion', '')
        is_default = data.get('is_default', False)
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Generar nuevo GUID
        new_guid = str(uuid.uuid4())
        
        # Si este debe ser el predefinido por defecto, actualizar el tipo de estudio
        if is_default:
            update_query = "UPDATE nextris.isstudytype SET default_predef_id=%s WHERE guid=%s"
            cursor.execute(update_query, (new_guid, study_type_id))
        
        # Insertar el nuevo predefinido
        insert_query = """
            INSERT INTO nextris.tbinfpredef 
            (guid, tittle, findings, impression, technique, conclusion, studytype_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            new_guid, title, findings, impression, technique, conclusion, study_type_id
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Reporte predefinido creado exitosamente',
            'data': {
                'predef_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/predefined-reports/<predef_id>', methods=['PATCH', 'PUT'])
@jwt_required()
def update_predefined_report(predef_id):
    """
    Actualiza un reporte predefinido existente
    
    Path:
    - predef_id: GUID del reporte predefinido
    
    Body JSON (todos opcionales):
    {
        "title": "string",
        "findings": "string",
        "technique": "string",
        "impression": "string",
        "conclusion": "string"
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte predefinido actualizado exitosamente"
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
        cursor.execute("SELECT 1 FROM nextris.tbinfpredef WHERE guid=%s", (predef_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Reporte predefinido no encontrado'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'title' in data:
            updates.append("tittle = %s")
            params.append(data['title'])
        if 'findings' in data:
            updates.append("findings = %s")
            params.append(data['findings'])
        if 'technique' in data:
            updates.append("technique = %s")
            params.append(data['technique'])
        if 'impression' in data:
            updates.append("impression = %s")
            params.append(data['impression'])
        if 'conclusion' in data:
            updates.append("conclusion = %s")
            params.append(data['conclusion'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(predef_id)
        query = f"UPDATE nextris.tbinfpredef SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Reporte predefinido actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/<exam_id>', methods=['PATCH', 'PUT'])
@jwt_required()
def save_report(exam_id):
    """
    Guarda o actualiza los datos de un reporte médico
    
    Path:
    - exam_id: GUID del examen
    
    Body JSON:
    {
        "findings": "string" (required),
        "techniques": "string" (required),
        "impressions": "string" (required),
        "conclusions": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte guardado exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        findings = data.get('findings')
        techniques = data.get('techniques')
        impressions = data.get('impressions')
        conclusions = data.get('conclusions')
        
        if findings is None or techniques is None or impressions is None or conclusions is None:
            return jsonify({
                'success': False,
                'message': 'findings, techniques, impressions y conclusions son campos requeridos'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            UPDATE nextris.tbreport 
            SET findings=%s, techniques=%s, impressions=%s, conclusions=%s, wassaved=true 
            WHERE idexamination=%s
        """
        
        cursor.execute(query, (findings, techniques, impressions, conclusions, exam_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Reporte guardado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/<exam_id>/sign', methods=['POST'])
@jwt_required()
def sign_report(exam_id):
    """
    Firma un reporte médico (marca como reportado)
    
    Path:
    - exam_id: GUID del examen
    
    Body JSON (opcional):
    {
        "reporter_physician_id": "uuid" (opcional, se usa JWT identity si no se provee)
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte firmado exitosamente"
    }
    """
    try:
        data = request.get_json() or {}
        
        # Obtener ID del médico que firma
        reporter_physician_id = data.get('reporter_physician_id')
        if not reporter_physician_id:
            # Usar el ID del usuario autenticado
            reporter_physician_id = get_jwt_identity()
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Marcar el examen como reportado
        query = "UPDATE nextris.tbexamination SET isreported=1 WHERE guid=%s"
        cursor.execute(query, (exam_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # Actualizar estado (si existe la función)
        try:
            from apps.home.routes import updatestatus
            updatestatus(exam_id)
        except:
            pass
        
        return jsonify({
            'success': True,
            'message': 'Reporte firmado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/<exam_id>/unsign', methods=['POST'])
@jwt_required()
def unsign_report(exam_id):
    """
    Quita la firma de un reporte (desmarca como reportado)
    
    Path:
    - exam_id: GUID del examen
    
    Returns:
    {
        "success": true,
        "message": "Firma removida exitosamente"
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
        
        query = "UPDATE nextris.tbexamination SET isreported=0 WHERE guid=%s"
        cursor.execute(query, (exam_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # Actualizar estado (si existe la función)
        try:
            from apps.home.routes import updatestatus
            updatestatus(exam_id)
        except:
            pass
        
        return jsonify({
            'success': True,
            'message': 'Firma removida exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/<exam_id>/pdf', methods=['GET'])
@jwt_required()
def get_report_pdf(exam_id):
    """
    Obtiene el PDF de un reporte
    
    Path:
    - exam_id: GUID del examen
    
    Returns:
    - Archivo PDF del reporte
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
        
        query = "SELECT pdfpath FROM nextris.tbreport WHERE idexamination = %s"
        cursor.execute(query, (exam_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not result or not result[0]:
            return jsonify({
                'success': False,
                'message': 'PDF no disponible'
            }), 404
        
        pdf_path = os.path.normpath(result[0])
        absolute_path = os.path.abspath(pdf_path)
        
        if not os.path.exists(absolute_path):
            return jsonify({
                'success': False,
                'message': 'Archivo PDF no encontrado en el sistema'
            }), 404
        
        return send_file(absolute_path, as_attachment=False, mimetype='application/pdf')
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
