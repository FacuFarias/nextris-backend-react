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
        from apps.home.routes import config
        return config
    except:
        return None


@api_blueprint.route('/institutional/info', methods=['GET'])
@jwt_required()
def get_institutional_info():
    """
    Obtiene la información institucional
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid",
            "name": "Nombre de la institución",
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
        
        query = """
            SELECT guid, name, mail, address, phone, logo_path 
            FROM nextris.isbasicinformation 
            ORDER BY guid ASC 
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
                    'guid': result[0],
                    'name': result[1],
                    'mail': result[2],
                    'address': result[3],
                    'phone': result[4],
                    'logo_path': result[5]
                }
            }), 200
        else:
            return jsonify({
                'success': True,
                'data': None
            }), 200
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/institutional/info', methods=['POST', 'PUT'])
@jwt_required()
def update_institutional_info():
    """
    Actualiza o crea la información institucional
    
    Content-Type: multipart/form-data
    
    Form Data:
    - name: string (required) - Nombre de la institución
    - mail: string (optional) - Email institucional
    - address: string (optional) - Dirección
    - phone: string (optional) - Teléfono
    - logo: file (optional) - Archivo de imagen para el logo
    
    Returns:
    {
        "success": true,
        "message": "Información institucional actualizada exitosamente",
        "data": {
            "guid": "uuid",
            "logo_path": "/ruta/al/logo.png" (si se actualizó)
        }
    }
    """
    try:
        # Validar campos requeridos
        name = request.form.get('name')
        if not name:
            return jsonify({
                'success': False,
                'message': 'El nombre de la institución es requerido'
            }), 400
        
        mail = request.form.get('mail')
        address = request.form.get('address')
        phone = request.form.get('phone')
        logo_file = request.files.get('logo')
        logo_path = None
        
        # Procesar logo si se envió
        if logo_file and logo_file.filename:
            logo_path = _process_institutional_logo(logo_file)
            if not logo_path:
                return jsonify({
                    'success': False,
                    'message': 'Error al procesar el logo'
                }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar si ya existe un registro
        check_query = "SELECT guid, logo_path FROM nextris.isbasicinformation LIMIT 1"
        cursor.execute(check_query)
        existing = cursor.fetchone()
        
        if existing:
            # Actualizar registro existente
            guid = existing[0]
            
            if logo_path:
                update_query = """
                    UPDATE nextris.isbasicinformation 
                    SET name=%s, mail=%s, address=%s, phone=%s, logo_path=%s 
                    WHERE guid=%s
                """
                cursor.execute(update_query, (name, mail, address, phone, logo_path, guid))
            else:
                # Si no se envió nuevo logo, mantener el existente
                update_query = """
                    UPDATE nextris.isbasicinformation 
                    SET name=%s, mail=%s, address=%s, phone=%s 
                    WHERE guid=%s
                """
                cursor.execute(update_query, (name, mail, address, phone, guid))
                logo_path = existing[1]  # Usar logo existente para respuesta
        else:
            # Crear nuevo registro
            guid = str(uuid.uuid4())
            insert_query = """
                INSERT INTO nextris.isbasicinformation 
                (guid, name, mail, address, phone, logo_path) 
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (guid, name, mail, address, phone, logo_path))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        response_data = {'guid': guid}
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
        
        user_id = get_jwt_identity()
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener ubicaciones del usuario
        query = """
            SELECT 
                l.guid,
                l.name,
                l.code,
                COALESCE(rul.is_default, false) as is_default
            FROM nextris.tblocation l
            LEFT JOIN nextris.rel_user_location rul ON l.guid = rul.location_id AND rul.user_id = %s
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
                'is_default': row[3]
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

