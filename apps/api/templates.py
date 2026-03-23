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
        from apps.home.services import ConfigService
        config = ConfigService.get_db_config()
        return config
    except:
        return None


VALID_REPORT_TYPES = {'simple', 'inteligente'}


def normalize_report_type(value, default='simple'):
    """Normaliza el tipo de informe a un valor permitido."""
    normalized = (value or default).strip().lower()
    return normalized


def ensure_report_type_schema(conn):
    """Garantiza columna report_type y normaliza datos históricos."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'nextris'
                  AND table_name = 'tbinfpredef'
                  AND column_name = 'report_type'
            )
            """
        )
        report_type_exists = bool(cur.fetchone()[0])

        if not report_type_exists:
            cur.execute(
                """
                ALTER TABLE nextris.tbinfpredef
                ADD COLUMN report_type VARCHAR(20) NOT NULL DEFAULT 'simple'
                """
            )

        # Backfill y saneamiento para plantillas existentes.
        cur.execute(
            """
            UPDATE nextris.tbinfpredef
            SET report_type = LOWER(TRIM(COALESCE(report_type, '')))
            """
        )
        cur.execute(
            """
            UPDATE nextris.tbinfpredef
            SET report_type = 'simple'
            WHERE report_type = '' OR report_type IS NULL
            """
        )
        cur.execute(
            """
            UPDATE nextris.tbinfpredef
            SET report_type = 'simple'
            WHERE report_type NOT IN ('simple', 'inteligente')
            """
        )

        conn.commit()
    finally:
        cur.close()


def ensure_template_location_schema(conn):
    """Garantiza tabla de relación plantilla-location para informes inteligentes."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.rel_infpredef_location (
                guid VARCHAR(45) PRIMARY KEY,
                template_id VARCHAR(45) NOT NULL,
                location_id VARCHAR(45) NOT NULL,
                created_on TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_rel_infpredef_location UNIQUE (template_id, location_id)
            )
            """
        )
        conn.commit()
    finally:
        cur.close()


def normalize_location_ids(raw_location_ids):
    """Normaliza lista de location IDs eliminando vacíos y duplicados."""
    if raw_location_ids is None:
        return []

    if not isinstance(raw_location_ids, list):
        raise ValueError('location_ids debe ser una lista')

    normalized = []
    seen = set()
    for value in raw_location_ids:
        location_id = str(value).strip()
        if not location_id:
            continue
        if location_id in seen:
            continue
        seen.add(location_id)
        normalized.append(location_id)

    return normalized


def sync_template_locations(conn, template_id, location_ids):
    """Sincroniza las locations asociadas a una plantilla."""
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM nextris.rel_infpredef_location WHERE template_id = %s",
            (template_id,)
        )

        if location_ids:
            insert_query = """
                INSERT INTO nextris.rel_infpredef_location (guid, template_id, location_id)
                VALUES (%s, %s, %s)
            """
            rows = [(str(uuid.uuid4()), template_id, location_id) for location_id in location_ids]
            cur.executemany(insert_query, rows)

        conn.commit()
    finally:
        cur.close()


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
    - report_type (optional): Filtrar por tipo de informe (simple/inteligente)
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
        report_type = normalize_report_type(request.args.get('report_type')) if request.args.get('report_type') else None
        simple = request.args.get('simple', 'false').lower() == 'true'

        if report_type and report_type not in VALID_REPORT_TYPES:
            return jsonify({
                'success': False,
                'message': 'report_type invalido. Valores permitidos: simple, inteligente'
            }), 400
        
        conn = psycopg2.connect(**config)
        ensure_report_type_schema(conn)
        ensure_template_location_schema(conn)
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
                ip.conclusion,
                COALESCE(NULLIF(TRIM(LOWER(ip.report_type)), ''), 'simple') AS report_type,
                COALESCE(
                    (
                        SELECT ARRAY_AGG(rel.location_id ORDER BY rel.location_id)
                        FROM nextris.rel_infpredef_location rel
                        WHERE rel.template_id = ip.guid
                    ),
                    ARRAY[]::VARCHAR[]
                ) AS location_ids
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

        if report_type:
            query += " AND COALESCE(NULLIF(TRIM(LOWER(ip.report_type)), ''), 'simple') = %s"
            params.append(report_type)
        
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
                    'study_type_description': row[3] or '',
                    'report_type': row[12] or 'simple',
                    'location_ids': row[13] or []
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
                    'conclusion': row[11] or '',
                    'report_type': row[12] or 'simple',
                    'location_ids': row[13] or []
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
        ensure_report_type_schema(conn)
        ensure_template_location_schema(conn)
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
                ip.conclusion,
                COALESCE(NULLIF(TRIM(LOWER(ip.report_type)), ''), 'simple') AS report_type,
                COALESCE(
                    (
                        SELECT ARRAY_AGG(rel.location_id ORDER BY rel.location_id)
                        FROM nextris.rel_infpredef_location rel
                        WHERE rel.template_id = ip.guid
                    ),
                    ARRAY[]::VARCHAR[]
                ) AS location_ids
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
                'conclusion': result[11] or '',
                'report_type': result[12] or 'simple',
                'location_ids': result[13] or []
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
        "report_type": "simple",
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
        report_type = normalize_report_type(data.get('report_type'))
        is_default = data.get('is_default', False)

        try:
            location_ids = normalize_location_ids(data.get('location_ids', []))
        except ValueError as validation_error:
            return jsonify({
                'success': False,
                'message': str(validation_error)
            }), 400

        if report_type not in VALID_REPORT_TYPES:
            return jsonify({
                'success': False,
                'message': 'report_type invalido. Valores permitidos: simple, inteligente'
            }), 400
        
        # Generar nuevo GUID
        new_guid = str(uuid.uuid4())
        
        conn = psycopg2.connect(**config)
        ensure_report_type_schema(conn)
        ensure_template_location_schema(conn)
        cur = conn.cursor()
        
        # Insertar plantilla
        insert_query = """
            INSERT INTO nextris.tbinfpredef 
            (guid, tittle, findings, impression, technique, conclusion, studytype_id, report_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cur.execute(insert_query, (
            new_guid,
            title,
            findings,
            impression,
            technique,
            conclusion,
            study_type_id,
            report_type
        ))

        sync_template_locations(
            conn,
            new_guid,
            location_ids if report_type == 'inteligente' else []
        )
        
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
        ensure_report_type_schema(conn)
        ensure_template_location_schema(conn)
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
        report_type_raw = data.get('report_type')
        report_type = normalize_report_type(report_type_raw) if report_type_raw is not None else None

        try:
            location_ids = normalize_location_ids(data.get('location_ids', []))
        except ValueError as validation_error:
            return jsonify({
                'success': False,
                'message': str(validation_error)
            }), 400

        if report_type is not None and report_type not in VALID_REPORT_TYPES:
            return jsonify({
                'success': False,
                'message': 'report_type invalido. Valores permitidos: simple, inteligente'
            }), 400
        
        # Actualizar plantilla
        update_query = """
            UPDATE nextris.tbinfpredef 
            SET tittle = %s,
                findings = %s,
                impression = %s,
                technique = %s,
                conclusion = %s,
                studytype_id = %s,
                report_type = COALESCE(%s, report_type)
            WHERE guid = %s
        """
        
        cur.execute(update_query, (
            title,
            findings,
            impression,
            technique,
            conclusion,
            study_type_id,
            report_type,
            template_id
        ))

        effective_report_type = report_type
        if effective_report_type is None:
            cur.execute(
                """
                SELECT COALESCE(NULLIF(TRIM(LOWER(report_type)), ''), 'simple')
                FROM nextris.tbinfpredef
                WHERE guid = %s
                """,
                (template_id,)
            )
            report_type_row = cur.fetchone()
            effective_report_type = report_type_row[0] if report_type_row else 'simple'

        sync_template_locations(
            conn,
            template_id,
            location_ids if effective_report_type == 'inteligente' else []
        )
        
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
        ensure_report_type_schema(conn)
        ensure_template_location_schema(conn)
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
        
        # Eliminar relaciones de locations y luego la plantilla
        cur.execute(
            "DELETE FROM nextris.rel_infpredef_location WHERE template_id = %s",
            (template_id,)
        )

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
        ensure_report_type_schema(conn)
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
