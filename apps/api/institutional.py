"""
API REST para gestión de información institucional
Endpoints para obtener y actualizar datos institucionales (nombre, dirección, logo, etc.)
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required
import os
import uuid
from PIL import Image
from apps.api import api_blueprint
import psycopg2


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.services import ConfigService
        config = ConfigService.get_db_config()
        return config
    except:
        return None


def normalize_user_id(identity):
    if isinstance(identity, dict):
        return identity.get('id') or identity.get('guid') or identity.get('user_id')
    return identity


@api_blueprint.route('/institutional/info', methods=['GET'])
@api_blueprint.route('/institutional/info/<location_id>', methods=['GET'])
@jwt_required()
def get_institutional_info(location_id=None):
    """
    Obtiene la información institucional de una ubicación.
    Si no se pasa location_id, retorna la primera ubicación del usuario.

    Path Parameters:
    - location_id (opcional): GUID de la ubicación

    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid",
            "name": "Nombre de la ubicación",
            "mail": "email@ejemplo.com",
            "address": "Dirección",
            "phone": "Teléfono",
            "logo_path": "/ruta/al/logo.png"
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

        if location_id:
            query = """
                SELECT guid, name, mail, address, phone, logo_path, COALESCE(require_signature_password, TRUE) as require_signature_password
                FROM nextris.tblocation
                WHERE guid = %s
            """
            cursor.execute(query, (location_id,))
        else:
            from flask_jwt_extended import get_jwt_identity
            user_id = normalize_user_id(get_jwt_identity())
            query = """
                SELECT l.guid, l.name, l.mail, l.address, l.phone, l.logo_path, COALESCE(l.require_signature_password, TRUE) as require_signature_password
                FROM nextris.tblocation l
                INNER JOIN nextris.rel_user_location rul ON l.guid = rul.location_id
                WHERE rul.user_id = %s
                ORDER BY rul.is_default DESC, l.name
                LIMIT 1
            """
            cursor.execute(query, (user_id,))

        result = cursor.fetchone()

        cursor.close()
        connection.close()

        if result:
            return jsonify({
                'success': True,
                'data': {
                    'guid': result[0],
                    'name': result[1],
                    'mail': result[2],
                    'address': result[3],
                    'phone': result[4],
                    'logo_path': result[5],
                    'require_signature_password': False
                }
            }), 200
        else:
            return jsonify({
                'success': True,
                'data': {
                    'require_signature_password': False
                }
            }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/institutional/info/<location_id>', methods=['POST', 'PUT'])
@jwt_required()
def update_institutional_info(location_id):
    """
    Actualiza la información institucional de una ubicación

    Path Parameters:
    - location_id: GUID de la ubicación

    Content-Type: multipart/form-data

    Form Data:
    - name: string (optional) - Nombre de la ubicación
    - mail: string (optional) - Email
    - address: string (optional) - Dirección
    - phone: string (optional) - Teléfono
    - logo: file (optional) - Archivo de imagen para el logo
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

        # Verificar que la ubicación existe
        cursor.execute("SELECT guid, logo_path FROM nextris.tblocation WHERE guid=%s", (location_id,))
        existing = cursor.fetchone()

        if not existing:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404

        name = request.form.get('name')
        mail = request.form.get('mail')
        address = request.form.get('address')
        phone = request.form.get('phone')
        require_signature_password = request.form.get('require_signature_password')
        logo_file = request.files.get('logo')
        logo_path = None

        # Procesar logo si se envió
        if logo_file and logo_file.filename:
            logo_path = _process_institutional_logo(logo_file)
            if not logo_path:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'Error al procesar el logo'
                }), 400

        update_fields = []
        values = []

        if name is not None:
            update_fields.append("name = %s")
            values.append(name)
        if mail is not None:
            update_fields.append("mail = %s")
            values.append(mail)
        if address is not None:
            update_fields.append("address = %s")
            values.append(address)
        if phone is not None:
            update_fields.append("phone = %s")
            values.append(phone)
        if require_signature_password is not None:
            update_fields.append("require_signature_password = %s")
            values.append(require_signature_password.lower() == 'true' if require_signature_password else True)
        if logo_path:
            update_fields.append("logo_path = %s")
            values.append(logo_path)

        if not update_fields:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400

        update_fields.append("updated_at = now()")
        values.append(location_id)
        query = f"UPDATE nextris.tblocation SET {', '.join(update_fields)} WHERE guid = %s"

        cursor.execute(query, values)
        connection.commit()

        if not logo_path:
            logo_path = existing[1]

        cursor.close()
        connection.close()

        response_data = {'guid': location_id}
        if logo_path:
            response_data['logo_path'] = logo_path

        return jsonify({
            'success': True,
            'message': 'Información institucional actualizada exitosamente',
            'data': response_data
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


def _process_institutional_logo(logo_file):
    """
    Procesa y guarda el logo institucional
    Redimensiona a 100x100px y maneja diferentes formatos
    
    Args:
        logo_file: Archivo de imagen desde request.files
        
    Returns:
        str: Ruta del archivo guardado o None si hay error
    """
    try:
        # Validar extensión
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
        ext = os.path.splitext(logo_file.filename)[1].lower()
        
        if ext not in allowed_extensions:
            print(f"Extensión no permitida: {ext}")
            return None
        
        # Configurar directorios
        logo_filename = f"logo_institucional{ext}"
        logo_dir = os.path.join('apps', 'static', 'assets', 'img')
        os.makedirs(logo_dir, exist_ok=True)
        logo_full_path = os.path.join(logo_dir, logo_filename)
        
        # Procesar imagen
        img = Image.open(logo_file)
        
        # Convertir a RGBA para manipulación
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Redimensionar manteniendo aspecto a 100x100px
        size = (100, 100)
        new_img = Image.new('RGBA', size, (255, 255, 255, 0))
        ratio = min(size[0] / img.width, size[1] / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Centrar imagen
        paste_pos = ((size[0] - new_size[0]) // 2, (size[1] - new_size[1]) // 2)
        new_img.paste(img, paste_pos)
        
        # Guardar según formato
        if ext in ['.jpg', '.jpeg']:
            # Para JPG, convertir a RGB con fondo blanco
            rgb_img = Image.new('RGB', size, (255, 255, 255))
            rgb_img.paste(new_img, mask=new_img.split()[3])
            rgb_img.save(logo_full_path, quality=95)
        else:
            # Para PNG mantener transparencia
            new_img.save(logo_full_path)
        
        # Normalizar ruta para BD (usar ruta relativa)
        logo_path = logo_full_path.replace('\\', '/')
        
        return logo_path
        
    except Exception as e:
        print(f"Error procesando logo institucional: {e}")
        return None


@api_blueprint.route('/institutional/locations', methods=['GET'])
@jwt_required()
def get_institutional_locations():
    """
    Obtiene las ubicaciones asignadas al usuario autenticado
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "name": "Nombre de ubicación",
                "code": "Código",
                "facility_id": "UUID de la facility",
                "facility_name": "Nombre de la facility",
                "facility_code": "Código de la facility",
                "address": "Dirección",
                "city": "Ciudad",
                "phone": "Teléfono",
                "is_default": true/false
            }
        ]
    }
    """
    try:
        from flask_jwt_extended import get_jwt_identity
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        user_id = normalize_user_id(get_jwt_identity())
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener ubicaciones del usuario
        query = """
            SELECT 
                l.guid,
                l.name,
                l.code,
                l.facility_id,
                COALESCE(f.name, '') as facility_name,
                COALESCE(f.code, '') as facility_code,
                COALESCE(rul.is_default, false) as is_default
            FROM nextris.tblocation l
            LEFT JOIN nextris.rel_user_location rul ON l.guid = rul.location_id AND rul.user_id = %s
            LEFT JOIN nextris.app_config f ON f.id::varchar = l.facility_id
            WHERE rul.user_id = %s
            ORDER BY COALESCE(rul.is_default, false) DESC, l.name
        """
        
        cursor.execute(query, (user_id, user_id))
        rows = cursor.fetchall()
        
        locations = []
        for row in rows:
            locations.append({
                'guid': row[0],
                'name': row[1],
                'code': row[2],
                'facility_id': row[3],
                'facility_name': row[4],
                'facility_code': row[5],
                'is_default': row[6]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': locations
        }), 200
        
    except Exception as e:
        print(f"[API INSTITUTIONAL LOCATIONS] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al obtener ubicaciones: {str(e)}'
        }), 500
