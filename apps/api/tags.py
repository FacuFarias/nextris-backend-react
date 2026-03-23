"""
Tags API — CRUD de tags por facility y asignación a examinations.

Tabla nextris.tbtags: guid, facility_id, description (varchar 20), is_active, created_at, updated_at

Endpoints:
  GET    /api/tags/all                         Lista todos los tags activos (todas las facilities)
  GET    /api/tags?facility_id=<id>            Lista tags de una facility
  POST   /api/tags                             Crea un tag
  PUT    /api/tags/<tag_id>                    Actualiza un tag
  DELETE /api/tags/<tag_id>                    Elimina un tag
  PATCH  /api/examinations/<exam_id>/tag_ids   Actualiza tags asignados a un examen
"""

import psycopg2
from flask import jsonify, request
from flask_jwt_extended import jwt_required

from apps.api import api_blueprint


ALLOWED_FLAG_COLORS = {'red', 'green', 'blue', 'yellow'}


def get_db_config():
    try:
        from apps.home.services import ConfigService
        config = ConfigService.get_db_config()
        return config
    except Exception:
        return None


def _row_to_tag(row):
    return {
        'guid': str(row[0]),
        'facility_id': str(row[1]),
        'description': row[2],
        'is_active': row[3],
        'created_at': row[4].isoformat() if row[4] else None,
        'updated_at': row[5].isoformat() if row[5] else None,
    }


# ─────────────────────────────────────────────────────────────
# GET /api/tags/all
# ─────────────────────────────────────────────────────────────
@api_blueprint.route('/tags/all', methods=['GET'])
@jwt_required()
def get_all_tags():
    """
    Devuelve todos los tags activos de todas las facilities.
    Útil para el worklist donde se necesitan resolver GUIDs a descripción.
    """
    config = get_db_config()
    if not config:
        return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT guid, facility_id, description, is_active, created_at, updated_at
            FROM nextris.tbtags
            WHERE is_active = TRUE
            ORDER BY description
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        return jsonify({'success': True, 'data': [_row_to_tag(r) for r in rows]}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────
# GET /api/tags?facility_id=<id>[&include_inactive=true]
# ─────────────────────────────────────────────────────────────
@api_blueprint.route('/tags', methods=['GET'])
@jwt_required()
def get_tags():
    """
    Lista los tags de una facility.

    Query params:
      - facility_id (requerido)
      - include_inactive (opcional, default false)
    """
    facility_id = request.args.get('facility_id')
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'

    if not facility_id:
        return jsonify({'success': False, 'message': 'El parámetro facility_id es requerido'}), 400

    config = get_db_config()
    if not config:
        return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        if include_inactive:
            cursor.execute(
                """
                SELECT guid, facility_id, description, is_active, created_at, updated_at
                FROM nextris.tbtags
                WHERE facility_id = %s
                ORDER BY description
                """,
                (facility_id,)
            )
        else:
            cursor.execute(
                """
                SELECT guid, facility_id, description, is_active, created_at, updated_at
                FROM nextris.tbtags
                WHERE facility_id = %s AND is_active = TRUE
                ORDER BY description
                """,
                (facility_id,)
            )

        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        return jsonify({'success': True, 'data': [_row_to_tag(r) for r in rows]}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────
# POST /api/tags
# ─────────────────────────────────────────────────────────────
@api_blueprint.route('/tags', methods=['POST'])
@jwt_required()
def create_tag():
    """
    Crea un nuevo tag.

    Body JSON:
      {
        "facility_id": "uuid" (requerido),
        "description": "string max 20 chars" (requerido),
        "is_active": bool (opcional, default true)
      }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Se requiere un cuerpo JSON'}), 400

    facility_id = data.get('facility_id')
    description = (data.get('description') or '').strip()[:20]

    if not facility_id or not description:
        return jsonify({'success': False, 'message': 'facility_id y description son requeridos'}), 400

    is_active = data.get('is_active', True)

    config = get_db_config()
    if not config:
        return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO nextris.tbtags (facility_id, description, is_active)
            VALUES (%s, %s, %s)
            RETURNING guid
            """,
            (facility_id, description, is_active)
        )
        new_guid = cursor.fetchone()[0]
        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({'success': True, 'data': {'guid': str(new_guid)}}), 201

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────
# PUT /api/tags/<tag_id>
# ─────────────────────────────────────────────────────────────
@api_blueprint.route('/tags/<tag_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_tag(tag_id):
    """
    Actualiza un tag existente.

    Body JSON (todos opcionales): { "description", "is_active" }
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Se requiere un cuerpo JSON'}), 400

    config = get_db_config()
    if not config:
        return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.tbtags WHERE guid = %s", (tag_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Tag no encontrado'}), 404

        updates = []
        params = []

        if 'description' in data:
            updates.append("description = %s")
            params.append(str(data['description']).strip()[:20])
        if 'is_active' in data:
            updates.append("is_active = %s")
            params.append(data['is_active'])

        if not updates:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'No hay campos para actualizar'}), 400

        updates.append("updated_at = NOW()")
        params.append(tag_id)

        cursor.execute(
            f"UPDATE nextris.tbtags SET {', '.join(updates)} WHERE guid = %s",
            params
        )
        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({'success': True, 'message': 'Tag actualizado exitosamente'}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────
# DELETE /api/tags/<tag_id>
# ─────────────────────────────────────────────────────────────
@api_blueprint.route('/tags/<tag_id>', methods=['DELETE'])
@jwt_required()
def delete_tag(tag_id):
    """
    Elimina un tag. Si está asignado a algún examen, retorna 409.
    """
    config = get_db_config()
    if not config:
        return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.tbtags WHERE guid = %s", (tag_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Tag no encontrado'}), 404

        cursor.execute(
            "SELECT COUNT(*) FROM nextris.tbexamination WHERE %s = ANY(tag_ids)",
            (tag_id,)
        )
        count = cursor.fetchone()[0]
        if count > 0:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'El tag está asignado a {count} estudio(s). Desactívelo en su lugar.'
            }), 409

        cursor.execute("DELETE FROM nextris.tbtags WHERE guid = %s", (tag_id,))
        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({'success': True, 'message': 'Tag eliminado exitosamente'}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────
# PATCH /api/examinations/<exam_id>/tag_ids
# ─────────────────────────────────────────────────────────────
@api_blueprint.route('/examinations/<exam_id>/tag_ids', methods=['PATCH'])
@jwt_required()
def update_examination_tag_ids(exam_id):
    """
    Actualiza los tags asignados a un examen.

    Body JSON: { "tag_ids": ["guid1", "guid2"] }
    """
    data = request.get_json()
    if data is None or 'tag_ids' not in data:
        return jsonify({'success': False, 'message': 'El campo "tag_ids" es requerido'}), 400

    tag_ids = data['tag_ids']
    if not isinstance(tag_ids, list):
        return jsonify({'success': False, 'message': '"tag_ids" debe ser una lista'}), 400

    config = get_db_config()
    if not config:
        return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE nextris.tbexamination SET tag_ids = %s WHERE Guid = %s",
            (tag_ids, exam_id)
        )
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({'success': True, 'tag_ids': tag_ids}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────
# PATCH /api/examinations/<exam_id>/flags
# ─────────────────────────────────────────────────────────────
@api_blueprint.route('/examinations/<exam_id>/flags', methods=['PATCH'])
@jwt_required()
def update_examination_flags(exam_id):
    """
    Actualiza las banderas visuales de un examen.

    Body JSON: { "flags": ["red", "green", "blue", "yellow"] }
    """
    data = request.get_json()
    if data is None or 'flags' not in data:
        return jsonify({'success': False, 'message': 'El campo "flags" es requerido'}), 400

    flags = data['flags']
    if not isinstance(flags, list):
        return jsonify({'success': False, 'message': '"flags" debe ser una lista'}), 400

    normalized_flags = []
    for flag in flags:
        if flag is None:
            continue
        value = str(flag).strip().lower()
        if not value:
            continue
        if value not in ALLOWED_FLAG_COLORS:
            return jsonify({
                'success': False,
                'message': f'Bandera inválida: {value}. Permitidas: red, green, blue, yellow'
            }), 400
        if value not in normalized_flags:
            normalized_flags.append(value)

    config = get_db_config()
    if not config:
        return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE nextris.tbexamination SET flags = %s WHERE Guid = %s RETURNING Guid",
            (normalized_flags, exam_id)
        )
        updated = cursor.fetchone()
        connection.commit()

        cursor.close()
        connection.close()

        if not updated:
            return jsonify({'success': False, 'message': 'Examen no encontrado'}), 404

        return jsonify({'success': True, 'flags': normalized_flags}), 200

    except Exception as e:
        message = str(e)
        if 'column "flags"' in message and 'does not exist' in message:
            return jsonify({
                'success': False,
                'message': 'La columna flags no existe en tbexamination. Ejecuta migración de esquema.'
            }), 500
        return jsonify({'success': False, 'message': f'Error: {message}'}), 500
