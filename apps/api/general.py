# -*- encoding: utf-8 -*-
"""
API General - Endpoints REST generales del sistema
"""

from flask import jsonify, request, render_template_string, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
import requests
import uuid
from datetime import datetime, timedelta
from apps.api import api_blueprint
from urllib.parse import urlencode

# Cache temporal en memoria para tokens de visor (en producción usar Redis)
viewer_tokens_cache = {}

# Cache para sesiones activas del visor con permisos validados
viewer_sessions_cache = {}


def get_db_config():
    """Obtiene la configuración de la base de datos"""
    from apps.home.routes import config as db_config
    return db_config


# ===========================
# ENDPOINTS DE VISOR
# ===========================

@api_blueprint.route('/general/viewer-url', methods=['POST'])
@jwt_required()
def get_viewer_url():
    """
    Obtener URL del visor para un estudio específico
    Valida que el usuario tenga permisos sobre la location del estudio
    
    Body JSON:
    {
        "user_id": "...",
        "examination_id": "..."
    }
    
    Response:
    {
        "success": true,
        "data": {
            "viewer_url": "https://viewer.nextris.cloud/viewer?StudyInstanceUIDs=..."
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
        
        user_id = data.get('user_id')
        examination_id = data.get('examination_id')
        
        if not user_id or not examination_id:
            return jsonify({
                'success': False,
                'message': 'user_id y examination_id son requeridos'
            }), 400
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener location_id y studyinstanceuid del examen
        cursor.execute("""
            SELECT location_id, studyinstanceuid
            FROM nextris.tbexamination
            WHERE guid = %s
        """, (examination_id,))
        
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        location_id = result[0]
        study_uid = result[1]
        
        if not location_id:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'El examen no tiene una ubicación asignada'
            }), 400
        
        if not study_uid:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'El examen no tiene un Study UID asignado'
            }), 400
        
        # Verificar que el usuario tenga acceso a esa location
        cursor.execute("""
            SELECT 1
            FROM nextris.rel_user_location
            WHERE user_id = %s AND location_id = %s
        """, (user_id, location_id))
        
        has_permission = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not has_permission:
            return jsonify({
                'success': False,
                'message': 'No tiene permisos para ver las imágenes de esta ubicación'
            }), 403
        
        # Obtener token de Keycloak usando credenciales del usuario genérico del visor
        keycloak_url = "http://localhost:8090/auth/realms/dcm4che/protocol/openid-connect/token"
        
        keycloak_data = {
            'client_id': 'dcm4chee-arc-ui',
            'grant_type': 'password',
            'username': 'userviewer',
            'password': 'uvnr123',
            'scope': 'openid profile email'
        }
        
        try:
            keycloak_response = requests.post(
                keycloak_url,
                data=keycloak_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if keycloak_response.status_code != 200:
                print(f"[API VIEWER URL] Error obteniendo token de Keycloak: {keycloak_response.text}")
                return jsonify({
                    'success': False,
                    'message': 'Error al generar token de acceso al visor'
                }), 500
            
            keycloak_token_data = keycloak_response.json()
            access_token = keycloak_token_data.get('access_token')
            expires_in = keycloak_token_data.get('expires_in', 300)  # Default 5 minutos
            
            # Generar un ID único para este acceso y una sesión
            access_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())
            
            # Guardar en cache temporal (expira en 5 minutos)
            viewer_tokens_cache[access_id] = {
                'study_uid': study_uid,
                'access_token': access_token,
                'expires_at': datetime.now() + timedelta(seconds=expires_in),
                'user_id': user_id,
                'examination_id': examination_id,
                'session_id': session_id
            }
            
            # Crear sesión con permisos específicos para este usuario
            # Esta sesión permite acceder SOLO al estudio autorizado
            viewer_sessions_cache[session_id] = {
                'user_id': user_id,
                'location_id': location_id,
                'study_uid': study_uid,  # Solo puede ver este estudio
                'examination_id': examination_id,
                'access_token': access_token,
                'expires_at': datetime.now() + timedelta(seconds=expires_in),
                'created_at': datetime.now()
            }
            
            # URL de acceso directo que sirve el HTML con el token
            viewer_url = f"https://nextris.cloud/api/general/open-viewer/{access_id}"
            
            # Generar página HTML embebida que el frontend puede abrir
            html_page = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Abriendo visor DICOM...</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .loader {{
            text-align: center;
            background: rgba(255,255,255,0.1);
            padding: 40px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }}
        .spinner {{
            border: 4px solid rgba(255,255,255,0.3);
            border-top: 4px solid white;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div class="loader">
        <div class="spinner"></div>
        <h2>Abriendo visor DICOM...</h2>
        <p>Configurando autenticación...</p>
    </div>
    
    <script>
        // Token de Keycloak
        const tokenData = {{
            access_token: "{access_token}",
            token_type: "Bearer",
            expires_in: {expires_in},
            timestamp: Date.now()
        }};
        
        // Guardar token en diferentes formatos para compatibilidad con OHIF
        localStorage.setItem('keycloak_token', "{access_token}");
        localStorage.setItem('access_token', "{access_token}");
        localStorage.setItem('token', JSON.stringify(tokenData));
        
        // Guardar session_id para validación de permisos en el proxy
        localStorage.setItem('nextris_session_id', "{session_id}");
        
        // Redirigir al visor a través del proxy de NextRIS
        setTimeout(function() {{
            window.location.href = "https://viewer.nextris.cloud/viewer?StudyInstanceUIDs={study_uid}&session_id={session_id}";
        }}, 1500);
    </script>
</body>
</html>
            """
            
            return jsonify({
                'success': True,
                'data': {
                    'study_uid': study_uid,
                    'viewer_url': viewer_url,
                    'html_page': html_page,
                    'direct_url': f"https://viewer.nextris.cloud/viewer?StudyInstanceUIDs={study_uid}",
                    'access_token': access_token,
                    'expires_in': expires_in
                }
            }), 200
            
        except requests.exceptions.RequestException as req_error:
            print(f"[API VIEWER URL] Error de conexión con Keycloak: {str(req_error)}")
            return jsonify({
                'success': False,
                'message': 'Error de conexión con el servicio de autenticación'
            }), 500
        
    except Exception as e:
        print(f"[API VIEWER URL] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/general/open-viewer/<access_id>', methods=['GET'])
def open_viewer(access_id):
    """
    Redirige al visor OHIF estableciendo automáticamente el token de Keycloak
    El token se guarda en localStorage y luego redirige al visor
    """
    try:
        # Buscar el token en cache
        token_data = viewer_tokens_cache.get(access_id)
        
        if not token_data:
            return """
            <html>
                <body>
                    <h1>Error: Enlace inválido o expirado</h1>
                    <p>Por favor, solicite un nuevo enlace de acceso al visor.</p>
                </body>
            </html>
            """, 404
        
        # Verificar que no haya expirado
        if datetime.now() > token_data['expires_at']:
            del viewer_tokens_cache[access_id]
            return """
            <html>
                <body>
                    <h1>Error: Enlace expirado</h1>
                    <p>Este enlace ha expirado. Por favor, solicite un nuevo enlace de acceso al visor.</p>
                </body>
            </html>
            """, 410
        
        study_uid = token_data['study_uid']
        access_token = token_data['access_token']
        
        # Eliminar del cache después de usarlo (un solo uso)
        del viewer_tokens_cache[access_id]
        
        # Página HTML que establece el token y redirige
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Abriendo visor DICOM...</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: #f0f0f0;
                }
                .loader {
                    text-align: center;
                }
                .spinner {
                    border: 4px solid #f3f3f3;
                    border-top: 4px solid #3498db;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 20px;
                }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        </head>
        <body>
            <div class="loader">
                <div class="spinner"></div>
                <h2>Abriendo visor DICOM...</h2>
                <p>Será redirigido automáticamente.</p>
            </div>
            
            <script>
                // Guardar el token en localStorage para que OHIF lo use
                const tokenData = {
                    access_token: "{{ access_token }}",
                    token_type: "Bearer",
                    expires_in: 300,
                    timestamp: Date.now()
                };
                
                // OHIF busca el token en diferentes formatos
                localStorage.setItem('keycloak_token', "{{ access_token }}");
                localStorage.setItem('access_token', "{{ access_token }}");
                localStorage.setItem('token', JSON.stringify(tokenData));
                
                // Redirigir al visor después de guardar el token
                setTimeout(function() {
                    window.location.href = "https://viewer.nextris.cloud/viewer?StudyInstanceUIDs={{ study_uid }}";
                }, 1000);
            </script>
        </body>
        </html>
        """
        
        return render_template_string(html_template, 
                                     access_token=access_token, 
                                     study_uid=study_uid)
        
    except Exception as e:
        print(f"[API OPEN VIEWER] Error: {str(e)}")
        return f"""
        <html>
            <body>
                <h1>Error al abrir el visor</h1>
                <p>Ha ocurrido un error: {str(e)}</p>
            </body>
        </html>
        """, 500


@api_blueprint.route('/general/validate-session', methods=['POST'])
def validate_viewer_session():
    """
    Valida que una sesión del visor sea válida y tenga acceso a un Study UID específico
    Usado por el frontend para verificar permisos antes de abrir estudios
    """
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        study_uid = data.get('study_uid')
        
        if not session_id:
            return jsonify({
                'success': False,
                'message': 'session_id requerido'
            }), 400
        
        # Buscar sesión en cache
        session = viewer_sessions_cache.get(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'message': 'Sesión no encontrada o expirada'
            }), 403
        
        # Verificar expiración
        if datetime.now() > session['expires_at']:
            del viewer_sessions_cache[session_id]
            return jsonify({
                'success': False,
                'message': 'Sesión expirada'
            }), 403
        
        # Si se proporciona study_uid, validar que sea el autorizado
        if study_uid:
            if study_uid != session['study_uid']:
                print(f"[VALIDATE SESSION] Access denied to study {study_uid}, only allowed: {session['study_uid']}")
                return jsonify({
                    'success': False,
                    'message': 'No tiene permisos para este estudio'
                }), 403
        
        return jsonify({
            'success': True,
            'data': {
                'session_id': session_id,
                'user_id': session['user_id'],
                'location_id': session['location_id'],
                'study_uid': session['study_uid'],
                'examination_id': session['examination_id'],
                'expires_at': session['expires_at'].isoformat()
            }
        }), 200
        
    except Exception as e:
        print(f"[VALIDATE SESSION] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
