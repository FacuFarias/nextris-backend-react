"""
API de Ubicaciones y Zonas Horarias
Gestiona las ubicaciones geográficas de los equipos DICOM y sus zonas horarias asociadas
"""

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from apps.api import api_blueprint
import psycopg2
import pytz
from datetime import datetime
from apps.home.services.config_service import ConfigService


def parse_bool_value(value, default=None):
    """Parse bool values sent as bool/int/string from JSON payloads."""
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    normalized = str(value).strip().lower()
    if normalized in ('true', '1', 'yes', 'y', 'on'):
        return True
    if normalized in ('false', '0', 'no', 'n', 'off'):
        return False

    return default


def ensure_location_report_execution_column(connection):
    """Ensure tblocation has workflow execution requirement flag."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            ALTER TABLE nextris.tblocation
            ADD COLUMN IF NOT EXISTS require_execution_before_reporting BOOLEAN NOT NULL DEFAULT TRUE
            """
        )
        connection.commit()
    finally:
        cursor.close()


def get_db_config():
    """Obtiene la configuración de la base de datos"""
    return ConfigService.get_db_config()


@api_blueprint.route('/locations', methods=['GET'])
@jwt_required()
def get_locations():
    """
    Obtener todas las ubicaciones con sus zonas horarias
    
    Query params:
    - facility_id: (opcional) Filtrar por facility
    - timezone: (opcional) Filtrar por zona horaria
    """
    try:
        user_id = get_jwt_identity()
        facility_id = request.args.get('facility_id')
        timezone = request.args.get('timezone')
        
        config = get_db_config()
        connection = psycopg2.connect(**config)
        ensure_location_report_execution_column(connection)
        cursor = connection.cursor()
        
        query = """
            SELECT 
                guid, facility_id, name, code, address, phone, 
                status, geographic_location, timezone, created_at, updated_at,
                gateway_aet, gateway_ip, transmission_type, retention_days,
                COALESCE(require_execution_before_reporting, TRUE)
            FROM nextris.tblocation
            WHERE 1=1
        """
        params = []
        
        if facility_id:
            query += " AND facility_id = %s"
            params.append(facility_id)
        
        if timezone:
            query += " AND timezone = %s"
            params.append(timezone)
        
        query += " ORDER BY name ASC"
        
        cursor.execute(query, params)
        locations = cursor.fetchall()
        
        result = []
        for loc in locations:
            result.append({
                'guid': loc[0],
                'facility_id': loc[1],
                'name': loc[2],
                'code': loc[3],
                'address': loc[4],
                'phone': loc[5],
                'status': loc[6],
                'geographic_location': loc[7],
                'timezone': loc[8],
                'created_at': loc[9].isoformat() if loc[9] else None,
                'updated_at': loc[10].isoformat() if loc[10] else None,
                'gateway_aet': loc[11],
                'gateway_ip': loc[12],
                'transmission_type': loc[13],
                'retention_days': loc[14],
                'require_execution_before_reporting': bool(loc[15])
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': result,
            'total': len(result)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_blueprint.route('/locations/<guid>', methods=['GET'])
@jwt_required()
def get_location(guid):
    """Obtener una ubicación específica con su zona horaria"""
    try:
        config = get_db_config()
        connection = psycopg2.connect(**config)
        ensure_location_report_execution_column(connection)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT 
                guid, facility_id, name, code, address, phone, 
                status, geographic_location, timezone, created_at, updated_at,
                gateway_aet, gateway_ip, transmission_type, retention_days,
                COALESCE(require_execution_before_reporting, TRUE)
            FROM nextris.tblocation
            WHERE guid = %s
        """, (guid,))
        
        location = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not location:
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'guid': location[0],
                'facility_id': location[1],
                'name': location[2],
                'code': location[3],
                'address': location[4],
                'phone': location[5],
                'status': location[6],
                'geographic_location': location[7],
                'timezone': location[8],
                'created_at': location[9].isoformat() if location[9] else None,
                'updated_at': location[10].isoformat() if location[10] else None,
                'gateway_aet': location[11],
                'gateway_ip': location[12],
                'transmission_type': location[13],
                'retention_days': location[14],
                'require_execution_before_reporting': bool(location[15])
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_blueprint.route('/locations', methods=['POST'])
@jwt_required()
def create_location():
    """
    Crear una nueva ubicación
    
    Body JSON:
    {
        "facility_id": "...",
        "name": "...",
        "code": "...",
        "address": "...",
        "phone": "...",
        "geographic_location": "lat,lng o descripción",
        "timezone": "America/Argentina/Buenos_Aires",
        "status": "Active"
    }
    """
    try:
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['facility_id', 'name', 'code']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'El campo {field} es requerido'
                }), 400
        
        # Validar que la zona horaria sea válida si se proporciona
        timezone = data.get('timezone')
        if timezone:
            try:
                pytz.timezone(timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                return jsonify({
                    'success': False,
                    'message': f'Zona horaria inválida: {timezone}'
                }), 400
        
        # Validar transmission_type si se proporciona
        transmission_type = data.get('transmission_type', 'Manual')
        if transmission_type not in ('Manual', 'Automatic'):
            return jsonify({
                'success': False,
                'message': "transmission_type debe ser 'Manual' o 'Automatic'"
            }), 400

        require_execution_before_reporting = parse_bool_value(
            data.get('require_execution_before_reporting'),
            default=True,
        )
        
        config = get_db_config()
        connection = psycopg2.connect(**config)
        ensure_location_report_execution_column(connection)
        cursor = connection.cursor()
        
        # Verificar que facility_id exista
        cursor.execute("""
            SELECT guid FROM nextris.tbfacility WHERE guid = %s
        """, (data.get('facility_id'),))
        
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'facility_id no existe'
            }), 400
        
        # Crear la ubicación
        cursor.execute("""
            INSERT INTO nextris.tblocation 
            (facility_id, name, code, address, phone, geographic_location, timezone, status,
             gateway_aet, gateway_ip, transmission_type, retention_days,
             require_execution_before_reporting)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING guid, created_at
        """, (
            data.get('facility_id'),
            data.get('name'),
            data.get('code'),
            data.get('address', ''),
            data.get('phone', ''),
            data.get('geographic_location', ''),
            timezone,
            data.get('status', 'Active'),
            data.get('gateway_aet'),
            data.get('gateway_ip'),
            transmission_type,
            data.get('retention_days'),
            require_execution_before_reporting
        ))
        
        result = cursor.fetchone()
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Ubicación creada exitosamente',
            'data': {
                'guid': result[0],
                'created_at': result[1].isoformat() if result[1] else None
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_blueprint.route('/locations/<guid>', methods=['PUT'])
@jwt_required()
def update_location(guid):
    """
    Actualizar una ubicación
    
    Body JSON: campos a actualizar
    """
    try:
        data = request.get_json()
        
        # Validar zona horaria si se proporciona
        timezone = data.get('timezone')
        if timezone:
            try:
                pytz.timezone(timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                return jsonify({
                    'success': False,
                    'message': f'Zona horaria inválida: {timezone}'
                }), 400
        
        config = get_db_config()
        connection = psycopg2.connect(**config)
        ensure_location_report_execution_column(connection)
        cursor = connection.cursor()
        
        # Verificar que la ubicación exista
        cursor.execute("SELECT guid FROM nextris.tblocation WHERE guid = %s", (guid,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404
        
        # Construir query dinámico
        update_fields = []
        params = []
        
        # Validar transmission_type si se proporciona
        if 'transmission_type' in data and data['transmission_type'] not in ('Manual', 'Automatic'):
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': "transmission_type debe ser 'Manual' o 'Automatic'"
            }), 400

        if 'require_execution_before_reporting' in data:
            require_execution_value = parse_bool_value(
                data.get('require_execution_before_reporting'),
                default=None,
            )
            if require_execution_value is None:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'require_execution_before_reporting debe ser booleano'
                }), 400
            data['require_execution_before_reporting'] = require_execution_value
        
        allowed_fields = {
            'name': 'name',
            'code': 'code',
            'address': 'address',
            'phone': 'phone',
            'geographic_location': 'geographic_location',
            'timezone': 'timezone',
            'status': 'status',
            'gateway_aet': 'gateway_aet',
            'gateway_ip': 'gateway_ip',
            'transmission_type': 'transmission_type',
            'retention_days': 'retention_days',
            'require_execution_before_reporting': 'require_execution_before_reporting'
        }
        
        for key, db_field in allowed_fields.items():
            if key in data:
                update_fields.append(f"{db_field} = %s")
                params.append(data[key])
        
        if not update_fields:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        # Agregar updated_at
        update_fields.append("updated_at = now()")
        params.append(guid)
        
        query = f"UPDATE nextris.tblocation SET {', '.join(update_fields)} WHERE guid = %s"
        
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
            'message': str(e)
        }), 500


@api_blueprint.route('/locations/<guid>', methods=['DELETE'])
@jwt_required()
def delete_location(guid):
    """Eliminar una ubicación"""
    try:
        config = get_db_config()
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT guid FROM nextris.tblocation WHERE guid = %s", (guid,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404
        
        # Eliminar
        cursor.execute("DELETE FROM nextris.tblocation WHERE guid = %s", (guid,))
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
            'message': str(e)
        }), 500


@api_blueprint.route('/locations/timezone/current', methods=['POST'])
@jwt_required()
def get_current_timezone():
    """
    Obtener la hora actual en la zona horaria de una ubicación
    
    Body JSON:
    {
        "location_guid": "..."
    }
    """
    try:
        data = request.get_json()
        location_guid = data.get('location_guid')
        
        if not location_guid:
            return jsonify({
                'success': False,
                'message': 'location_guid es requerido'
            }), 400
        
        config = get_db_config()
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT timezone FROM nextris.tblocation WHERE guid = %s
        """, (location_guid,))
        
        result = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if not result:
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404
        
        timezone_str = result[0]
        if not timezone_str:
            return jsonify({
                'success': False,
                'message': 'La ubicación no tiene zona horaria configurada'
            }), 400
        
        # Obtener la hora actual en esa zona horaria
        tz = pytz.timezone(timezone_str)
        current_time = datetime.now(tz)
        
        return jsonify({
            'success': True,
            'data': {
                'timezone': timezone_str,
                'current_time': current_time.isoformat(),
                'utc_offset': current_time.strftime('%z')
            }
        }), 200
        
    except pytz.exceptions.UnknownTimeZoneError as e:
        return jsonify({
            'success': False,
            'message': f'Zona horaria inválida: {str(e)}'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_blueprint.route('/locations/timezones/list', methods=['GET'])
@jwt_required()
def list_timezones():
    """Obtener lista de todas las zonas horarias disponibles"""
    try:
        timezones = sorted(pytz.all_timezones)
        
        # Agrupar por región
        grouped = {}
        for tz in timezones:
            region = tz.split('/')[0]
            if region not in grouped:
                grouped[region] = []
            grouped[region].append(tz)
        
        return jsonify({
            'success': True,
            'data': grouped,
            'total': len(timezones)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
