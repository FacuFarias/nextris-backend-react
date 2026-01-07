# -*- encoding: utf-8 -*-
"""
API REST para transcripción de audio médico usando Whisper
Endpoints para grabar y transcribir dictados médicos
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from apps.api import api_blueprint
import requests
import os
from werkzeug.utils import secure_filename

# URL del servicio Whisper local
WHISPER_SERVICE_URL = os.environ.get('WHISPER_SERVICE_URL', 'http://localhost:9001')

# Configuración de archivos de audio permitidos
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'webm', 'm4a', 'mp4', 'flac', 'aac'}
MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25 MB


def allowed_audio_file(filename):
    """
    Verifica si el archivo tiene una extensión de audio permitida
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS


@api_blueprint.route('/transcription/upload', methods=['POST'])
@jwt_required()
def transcribe_audio():
    """
    Transcribe un archivo de audio usando el servicio Whisper
    
    Multipart Form Data:
    - audio: Archivo de audio (mp3, wav, ogg, webm, m4a, flac, aac)
    - language (optional): Idioma del audio (default: 'es' para español)
    - task (optional): 'transcribe' o 'translate' (default: 'transcribe')
    
    Returns:
    {
        "success": true,
        "data": {
            "text": "Transcripción completa del audio",
            "language": "es",
            "duration": 12.5,
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.2,
                    "text": "Primer segmento de texto"
                },
                ...
            ]
        }
    }
    """
    try:
        # Obtener el usuario actual
        current_user = get_jwt_identity()
        
        # Verificar que se envió un archivo
        if 'audio' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No se proporcionó ningún archivo de audio'
            }), 400
        
        audio_file = request.files['audio']
        
        # Verificar que el archivo tiene nombre
        if audio_file.filename == '':
            return jsonify({
                'success': False,
                'message': 'El archivo no tiene nombre'
            }), 400
        
        # Verificar extensión permitida
        if not allowed_audio_file(audio_file.filename):
            return jsonify({
                'success': False,
                'message': f'Formato de audio no permitido. Formatos aceptados: {", ".join(ALLOWED_AUDIO_EXTENSIONS)}'
            }), 400
        
        # Verificar tamaño del archivo
        audio_file.seek(0, os.SEEK_END)
        file_size = audio_file.tell()
        audio_file.seek(0)
        
        if file_size > MAX_AUDIO_SIZE:
            return jsonify({
                'success': False,
                'message': f'El archivo es demasiado grande. Tamaño máximo: {MAX_AUDIO_SIZE / (1024*1024)} MB'
            }), 400
        
        # Obtener parámetros opcionales
        language = request.form.get('language', 'es')
        task = request.form.get('task', 'transcribe')
        
        # Preparar los archivos y datos para enviar a Whisper
        files = {
            'audio_file': (
                secure_filename(audio_file.filename),
                audio_file.stream,
                audio_file.content_type
            )
        }
        
        # Parámetros de query para Whisper
        params = {
            'encode': 'true',
            'task': task,
            'language': language,
            'output': 'json'
        }
        
        # Enviar al servicio Whisper
        try:
            whisper_response = requests.post(
                f'{WHISPER_SERVICE_URL}/asr',
                files=files,
                params=params,
                timeout=300  # 5 minutos de timeout para archivos largos
            )
            
            # Verificar respuesta del servicio
            if whisper_response.status_code != 200:
                return jsonify({
                    'success': False,
                    'message': 'Error en el servicio de transcripción',
                    'details': whisper_response.text
                }), 500
            
            # Obtener la transcripción
            transcription_data = whisper_response.json()
            
            # Registrar la transcripción (opcional - puedes guardar en BD)
            # TODO: Implementar registro en base de datos si es necesario
            
            return jsonify({
                'success': True,
                'data': transcription_data,
                'message': 'Audio transcrito exitosamente'
            }), 200
            
        except requests.exceptions.Timeout:
            return jsonify({
                'success': False,
                'message': 'El servicio de transcripción tardó demasiado en responder'
            }), 504
        
        except requests.exceptions.ConnectionError:
            return jsonify({
                'success': False,
                'message': 'No se pudo conectar al servicio de transcripción. Verifique que Whisper esté ejecutándose.'
            }), 503
        
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error al comunicarse con el servicio de transcripción: {str(e)}'
            }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error al procesar la solicitud: {str(e)}'
        }), 500


@api_blueprint.route('/transcription/stream', methods=['POST'])
@jwt_required()
def transcribe_audio_stream():
    """
    Transcribe audio en tiempo real (streaming)
    
    Binary Body: Datos de audio en formato RAW o WAV
    
    Headers:
    - Content-Type: audio/wav o audio/webm
    - X-Language: Idioma del audio (opcional, default: 'es')
    
    Returns:
    {
        "success": true,
        "data": {
            "text": "Transcripción del audio",
            "is_final": false
        }
    }
    """
    try:
        # Obtener el usuario actual
        current_user = get_jwt_identity()
        
        # Obtener los datos de audio del cuerpo de la solicitud
        audio_data = request.get_data()
        
        if not audio_data:
            return jsonify({
                'success': False,
                'message': 'No se recibieron datos de audio'
            }), 400
        
        # Obtener parámetros de headers
        content_type = request.headers.get('Content-Type', 'audio/wav')
        language = request.headers.get('X-Language', 'es')
        
        # Enviar al servicio Whisper
        try:
            whisper_response = requests.post(
                f'{WHISPER_SERVICE_URL}/asr',
                data=audio_data,
                headers={
                    'Content-Type': content_type
                },
                params={
                    'language': language,
                    'task': 'transcribe',
                    'output': 'json'
                },
                timeout=60
            )
            
            if whisper_response.status_code != 200:
                return jsonify({
                    'success': False,
                    'message': 'Error en el servicio de transcripción'
                }), 500
            
            transcription_data = whisper_response.json()
            
            return jsonify({
                'success': True,
                'data': transcription_data
            }), 200
            
        except requests.exceptions.ConnectionError:
            return jsonify({
                'success': False,
                'message': 'No se pudo conectar al servicio de transcripción'
            }), 503
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/transcription/status', methods=['GET'])
@jwt_required()
def transcription_service_status():
    """
    Verifica el estado del servicio de transcripción Whisper
    
    Returns:
    {
        "success": true,
        "data": {
            "service": "available",
            "url": "http://localhost:9000",
            "version": "whisper-1.0"
        }
    }
    """
    try:
        # Intentar hacer ping al servicio
        try:
            response = requests.get(
                f'{WHISPER_SERVICE_URL}/health',
                timeout=5
            )
            
            if response.status_code == 200:
                service_info = response.json() if response.headers.get('Content-Type', '').startswith('application/json') else {}
                
                return jsonify({
                    'success': True,
                    'data': {
                        'service': 'available',
                        'url': WHISPER_SERVICE_URL,
                        'info': service_info
                    }
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'data': {
                        'service': 'unavailable',
                        'url': WHISPER_SERVICE_URL,
                        'error': 'Service returned non-200 status'
                    }
                }), 200
                
        except requests.exceptions.ConnectionError:
            return jsonify({
                'success': False,
                'data': {
                    'service': 'unavailable',
                    'url': WHISPER_SERVICE_URL,
                    'error': 'Cannot connect to service'
                }
            }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
