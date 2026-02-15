# -*- encoding: utf-8 -*-
"""
API de Filter Presets - Endpoints para gestión de presets de filtros por usuario
"""

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
import psycopg2.extras
from datetime import datetime
from apps.api import api_blueprint


def get_db_config():
    """Obtiene la configuración de la base de datos"""
    from apps.home.routes import config as db_config
    return db_config


# ==================== ENDPOINTS DE FILTER PRESETS ====================


@api_blueprint.route('/filter-presets', methods=['GET'])
@jwt_required()
def get_filter_presets():
    """
    Lista todos los presets de filtros del usuario autenticado.

    GET /api/filter-presets

    Response:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "name": "Cardiología",
                "filters": { ... },
                "sort_order": 0,
                "is_active": true,
                "created_on": "...",
                "updated_on": "..."
            }
        ]
    }
    """
    try:
        user_id = get_jwt_identity()
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute("""
            SELECT guid, name, filters, sort_order, is_active, created_on, updated_on
            FROM nextris.tb_filter_preset
            WHERE user_id = %s
            ORDER BY sort_order ASC, created_on ASC
        """, (user_id,))

        presets = cursor.fetchall()

        # Convertir UUIDs y datetimes a string
        result = []
        for preset in presets:
            result.append({
                'guid': str(preset['guid']),
                'name': preset['name'],
                'filters': preset['filters'],
                'sort_order': preset['sort_order'],
                'is_active': preset['is_active'],
                'created_on': preset['created_on'].isoformat() if preset['created_on'] else None,
                'updated_on': preset['updated_on'].isoformat() if preset['updated_on'] else None,
            })

        cursor.close()
        connection.close()

        return jsonify({'success': True, 'data': result}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/filter-presets', methods=['POST'])
@jwt_required()
def create_filter_preset():
    """
    Crea un nuevo preset de filtros.

    POST /api/filter-presets
    Body: { "name": "...", "filters": { ... } }

    Automáticamente desactiva los demás presets y activa el nuevo.
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        name = data.get('name', '').strip()
        filters = data.get('filters', {})

        if not name:
            return jsonify({'success': False, 'message': 'El nombre es requerido'}), 400

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Obtener el próximo sort_order
        cursor.execute("""
            SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order
            FROM nextris.tb_filter_preset
            WHERE user_id = %s
        """, (user_id,))
        next_order = cursor.fetchone()['next_order']

        # Desactivar todos los presets del usuario
        cursor.execute("""
            UPDATE nextris.tb_filter_preset
            SET is_active = false
            WHERE user_id = %s
        """, (user_id,))

        # Crear el nuevo preset como activo
        cursor.execute("""
            INSERT INTO nextris.tb_filter_preset (user_id, name, filters, sort_order, is_active)
            VALUES (%s, %s, %s::jsonb, %s, true)
            RETURNING guid, name, filters, sort_order, is_active, created_on, updated_on
        """, (user_id, name, psycopg2.extras.Json(filters), next_order))

        new_preset = cursor.fetchone()
        connection.commit()

        result = {
            'guid': str(new_preset['guid']),
            'name': new_preset['name'],
            'filters': new_preset['filters'],
            'sort_order': new_preset['sort_order'],
            'is_active': new_preset['is_active'],
            'created_on': new_preset['created_on'].isoformat() if new_preset['created_on'] else None,
            'updated_on': new_preset['updated_on'].isoformat() if new_preset['updated_on'] else None,
        }

        cursor.close()
        connection.close()

        return jsonify({'success': True, 'data': result, 'message': 'Preset creado exitosamente'}), 201

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/filter-presets/<guid>', methods=['PUT'])
@jwt_required()
def update_filter_preset(guid):
    """
    Actualiza un preset de filtros existente (nombre y/o filtros).

    PUT /api/filter-presets/<guid>
    Body: { "name": "...", "filters": { ... } }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Verificar que el preset pertenece al usuario
        cursor.execute("""
            SELECT guid FROM nextris.tb_filter_preset
            WHERE guid = %s AND user_id = %s
        """, (guid, user_id))

        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Preset no encontrado'}), 404

        # Construir la query de actualización dinámicamente
        updates = []
        params = []

        if 'name' in data:
            name = data['name'].strip()
            if not name:
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'El nombre no puede estar vacío'}), 400
            updates.append("name = %s")
            params.append(name)

        if 'filters' in data:
            updates.append("filters = %s::jsonb")
            params.append(psycopg2.extras.Json(data['filters']))

        if not updates:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'No hay campos para actualizar'}), 400

        updates.append("updated_on = NOW()")
        params.extend([guid, user_id])

        cursor.execute(f"""
            UPDATE nextris.tb_filter_preset
            SET {', '.join(updates)}
            WHERE guid = %s AND user_id = %s
            RETURNING guid, name, filters, sort_order, is_active, created_on, updated_on
        """, params)

        updated_preset = cursor.fetchone()
        connection.commit()

        result = {
            'guid': str(updated_preset['guid']),
            'name': updated_preset['name'],
            'filters': updated_preset['filters'],
            'sort_order': updated_preset['sort_order'],
            'is_active': updated_preset['is_active'],
            'created_on': updated_preset['created_on'].isoformat() if updated_preset['created_on'] else None,
            'updated_on': updated_preset['updated_on'].isoformat() if updated_preset['updated_on'] else None,
        }

        cursor.close()
        connection.close()

        return jsonify({'success': True, 'data': result, 'message': 'Preset actualizado exitosamente'}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/filter-presets/<guid>', methods=['DELETE'])
@jwt_required()
def delete_filter_preset(guid):
    """
    Elimina un preset de filtros.

    DELETE /api/filter-presets/<guid>
    """
    try:
        user_id = get_jwt_identity()

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        # Verificar que el preset pertenece al usuario
        cursor.execute("""
            SELECT guid FROM nextris.tb_filter_preset
            WHERE guid = %s AND user_id = %s
        """, (guid, user_id))

        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Preset no encontrado'}), 404

        cursor.execute("""
            DELETE FROM nextris.tb_filter_preset
            WHERE guid = %s AND user_id = %s
        """, (guid, user_id))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({'success': True, 'message': 'Preset eliminado exitosamente'}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/filter-presets/<guid>/activate', methods=['PUT'])
@jwt_required()
def activate_filter_preset(guid):
    """
    Marca un preset como activo y desactiva los demás.

    PUT /api/filter-presets/<guid>/activate
    """
    try:
        user_id = get_jwt_identity()

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        # Verificar que el preset pertenece al usuario
        cursor.execute("""
            SELECT guid FROM nextris.tb_filter_preset
            WHERE guid = %s AND user_id = %s
        """, (guid, user_id))

        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Preset no encontrado'}), 404

        # Desactivar todos los presets del usuario
        cursor.execute("""
            UPDATE nextris.tb_filter_preset
            SET is_active = false
            WHERE user_id = %s
        """, (user_id,))

        # Activar el preset seleccionado
        cursor.execute("""
            UPDATE nextris.tb_filter_preset
            SET is_active = true
            WHERE guid = %s AND user_id = %s
        """, (guid, user_id))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({'success': True, 'message': 'Preset activado exitosamente'}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/filter-presets/deactivate-all', methods=['PUT'])
@jwt_required()
def deactivate_all_filter_presets():
    """
    Desactiva todos los presets del usuario (cuando se selecciona la tab "Todos").

    PUT /api/filter-presets/deactivate-all
    """
    try:
        user_id = get_jwt_identity()

        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE nextris.tb_filter_preset
            SET is_active = false
            WHERE user_id = %s
        """, (user_id,))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({'success': True, 'message': 'Todos los presets desactivados'}), 200

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
