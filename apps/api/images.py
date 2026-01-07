# -*- encoding: utf-8 -*-
"""
API REST para gestión de imágenes DICOM
Endpoints para obtener imágenes clave de estudios
"""

from flask import request, jsonify, send_file, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from apps.api import api_blueprint
import os
import base64
from pathlib import Path
from functools import wraps


# Ruta base para imágenes clave
KEY_IMAGES_BASE_PATH = "/var/local/dcm4chee-arc/key-images"


def add_cors_headers(f):
    """
    Decorador para agregar headers CORS a las respuestas de imágenes
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)
        
        # Si es una tupla (response, status_code), convertir a Response object
        if isinstance(response, tuple):
            response = make_response(*response)
        
        # Agregar headers CORS específicos para imágenes
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length'
        
        return response
    return decorated_function


def jwt_optional_with_query(f):
    """
    Decorador que permite JWT en header o en query parameter 'token'
    Esto permite abrir las URLs directamente en el navegador
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Intentar obtener el token del query parameter
        token = request.args.get('token')
        
        if token:
            # Si hay token en query, agregarlo temporalmente al header
            from flask import g
            request.environ['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        
        try:
            verify_jwt_in_request(optional=True)
            return f(*args, **kwargs)
        except Exception as e:
            # Si falla la verificación, permitir acceso sin autenticación
            # (puedes cambiar esto si quieres que sea obligatorio)
            return f(*args, **kwargs)
    
    return decorated_function


@api_blueprint.route('/images/study/<study_uid>', methods=['GET'])
@jwt_required()
@add_cors_headers
def get_study_images(study_uid):
    """
    Obtiene las imágenes clave de un estudio específico
    
    Path Parameters:
    - study_uid: Study Instance UID del estudio
    
    Query Parameters:
    - format (optional): 'list' para lista de nombres, 'base64' para imágenes en base64 (default: 'list')
    
    Returns:
    {
        "success": true,
        "data": {
            "study_uid": "1.2.840...",
            "images_count": 5,
            "images": [
                {
                    "filename": "image001.jpg",
                    "path": "relative/path/to/image.jpg",
                    "size": 123456
                }
            ]
        }
    }
    
    O con format=base64:
    {
        "success": true,
        "data": {
            "study_uid": "1.2.840...",
            "images_count": 5,
            "images": [
                {
                    "filename": "image001.jpg",
                    "data": "base64_encoded_string",
                    "size": 123456
                }
            ]
        }
    }
    """
    try:
        # Validar que el study_uid no contenga caracteres peligrosos
        if not study_uid or '..' in study_uid or '/' in study_uid.replace('.', ''):
            return jsonify({
                'success': False,
                'message': 'Study UID inválido'
            }), 400
        
        # Construir la ruta de la carpeta
        study_path = os.path.join(KEY_IMAGES_BASE_PATH, study_uid)
        
        # Verificar que la carpeta existe
        if not os.path.exists(study_path):
            return jsonify({
                'success': False,
                'message': 'No se encontraron imágenes para este estudio'
            }), 404
        
        if not os.path.isdir(study_path):
            return jsonify({
                'success': False,
                'message': 'La ruta no es un directorio válido'
            }), 400
        
        # Obtener formato de respuesta
        response_format = request.args.get('format', 'list').lower()
        
        # Buscar archivos de imagen (JPG, JPEG, PNG)
        image_files = []
        for filename in os.listdir(study_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                file_path = os.path.join(study_path, filename)
                file_size = os.path.getsize(file_path)
                
                # Buscar archivo JSON asociado (mismo nombre, extensión .json)
                json_filename = os.path.splitext(filename)[0] + '.json'
                json_path = os.path.join(study_path, json_filename)
                metadata = None
                
                if os.path.exists(json_path):
                    try:
                        import json
                        with open(json_path, 'r') as f:
                            metadata = json.load(f)
                    except:
                        pass
                
                image_files.append({
                    'filename': filename,
                    'path': file_path,
                    'size': file_size,
                    'metadata': metadata
                })
        
        # Ordenar por nombre
        image_files.sort(key=lambda x: x['filename'])
        
        if not image_files:
            return jsonify({
                'success': False,
                'message': 'No se encontraron imágenes en este estudio'
            }), 404
        
        # Preparar respuesta según el formato
        if response_format == 'base64':
            # Devolver imágenes en base64
            images_data = []
            for img in image_files:
                try:
                    with open(img['path'], 'rb') as f:
                        img_bytes = f.read()
                        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                    
                    img_base64_data = {
                        'filename': img['filename'],
                        'data': img_base64,
                        'size': img['size']
                    }
                    
                    # Agregar metadata si existe
                    if img.get('metadata'):
                        img_base64_data['metadata'] = img['metadata']
                    
                    images_data.append(img_base64_data)
                except Exception as e:
                    # Si falla una imagen, continuar con las demás
                    continue
            
            return jsonify({
                'success': True,
                'data': {
                    'study_uid': study_uid,
                    'images_count': len(images_data),
                    'images': images_data
                }
            }), 200
        
        else:
            # Devolver solo lista de archivos con URL completa
            # Obtener la URL base (ej: http://148.230.72.8:5001)
            base_url = request.url_root.rstrip('/')
            
            images_list = []
            for img in image_files:
                img_data = {
                    'filename': img['filename'],
                    'path': f"{base_url}/api/images/study/{study_uid}/file/{img['filename']}",
                    'size': img['size']
                }
                
                # Agregar metadata si existe
                if img.get('metadata'):
                    img_data['metadata'] = img['metadata']
                
                images_list.append(img_data)
            
            return jsonify({
                'success': True,
                'data': {
                    'study_uid': study_uid,
                    'images_count': len(images_list),
                    'images': images_list
                }
            }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/images/study/<study_uid>/file/<filename>', methods=['GET'])
@jwt_optional_with_query
@add_cors_headers
def get_study_image_file(study_uid, filename):
    """
    Obtiene una imagen específica de un estudio
    
    Path Parameters:
    - study_uid: Study Instance UID del estudio
    - filename: Nombre del archivo de imagen
    
    Returns:
    - Archivo JPG de la imagen
    """
    try:
        # Validar que el study_uid no contenga caracteres peligrosos
        if not study_uid or '..' in study_uid or '/' in study_uid.replace('.', ''):
            return jsonify({
                'success': False,
                'message': 'Study UID inválido'
            }), 400
        
        # Validar que el filename no contenga caracteres peligrosos
        if not filename or '..' in filename or '/' in filename:
            return jsonify({
                'success': False,
                'message': 'Nombre de archivo inválido'
            }), 400
        
        # Verificar que sea un archivo de imagen válido
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            return jsonify({
                'success': False,
                'message': 'Solo se permiten archivos JPG, JPEG o PNG'
            }), 400
        
        # Construir la ruta completa
        file_path = os.path.join(KEY_IMAGES_BASE_PATH, study_uid, filename)
        
        # Verificar que el archivo existe
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': 'Imagen no encontrada'
            }), 404
        
        if not os.path.isfile(file_path):
            return jsonify({
                'success': False,
                'message': 'La ruta no corresponde a un archivo'
            }), 400
        
        # Determinar el mimetype según la extensión
        if filename.lower().endswith('.png'):
            mimetype = 'image/png'
        else:
            mimetype = 'image/jpeg'
        
        # Enviar el archivo
        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=False,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/images/study/<study_uid>/thumbnail/<filename>', methods=['GET'])
@jwt_optional_with_query
@add_cors_headers
def get_study_image_thumbnail(study_uid, filename):
    """
    Obtiene una miniatura de una imagen específica de un estudio
    Nota: Por ahora devuelve la imagen completa. Se puede implementar
    generación de thumbnails con PIL/Pillow si es necesario.
    
    Path Parameters:
    - study_uid: Study Instance UID del estudio
    - filename: Nombre del archivo de imagen
    
    Query Parameters:
    - size (optional): Tamaño máximo del thumbnail (default: 200)
    
    Returns:
    - Archivo JPG de la miniatura
    """
    try:
        # Por ahora, redirigir al endpoint de imagen completa
        # En el futuro se puede implementar generación de thumbnails
        return get_study_image_file(study_uid, filename)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
