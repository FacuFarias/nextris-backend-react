# -*- encoding: utf-8 -*-
"""
API General - Endpoints REST generales del sistema
"""

from flask import jsonify, request, render_template_string, Response, redirect, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import psycopg2
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import uuid
from datetime import datetime, timedelta
import hashlib
import hmac
import secrets
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from apps.api import api_blueprint
from urllib.parse import urlencode
from apps.api.viewer_share_service import (
    create_for_exam as create_share_for_exam,
    default_expiration_hours,
    short_share_url as build_share_url,
    token_hash as hash_share_token,
)

# Cache temporal en memoria para tokens de visor (en producción usar Redis)
viewer_tokens_cache = {}

# Cache para sesiones activas del visor con permisos validados
viewer_sessions_cache = {}


def get_db_config():
    """Obtiene la configuración de la base de datos"""
    from apps.home.services import ConfigService
    db_config = ConfigService.get_db_config()
    return db_config


def _get_client_ip():
    """Obtiene la IP cliente respetando reverse proxy."""
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.remote_addr


def _hash_share_token(raw_token):
    """Genera hash HMAC SHA-256 del token opaco para no persistir token plano."""
    return hash_share_token(raw_token)


def _get_public_api_url():
    """Obtiene la URL pública de la API NextRIS para construir enlaces externos."""
    public_url = current_app.config.get('PUBLIC_API_URL', '').strip()
    if public_url:
        return public_url.rstrip('/')
    forwarded_proto = request.headers.get('X-Forwarded-Proto', request.scheme)
    forwarded_host = request.headers.get('X-Forwarded-Host', request.host)
    return f"{forwarded_proto}://{forwarded_host}"


def _get_viewer_base_url():
    """Obtiene la URL base del visor DICOM (esquema + host + puerto)."""
    dicom_url = current_app.config.get('DICOM_VIEWER_URL', '')
    if dicom_url:
        url = dicom_url.strip().rstrip('/')
        idx = url.find('://')
        if idx > 0:
            after_scheme = url[idx + 3:]
            slash_idx = after_scheme.find('/')
            if slash_idx >= 0:
                return url[:idx + 3 + slash_idx]
            return url
    return 'https://clinicacp.ddns.net:3000'


def _request_viewer_keycloak_token():
    """Obtiene el token técnico sin credenciales embebidas en el código."""
    response = requests.post(
        os.environ['VIEWER_KEYCLOAK_TOKEN_URL'],
        data={
            'client_id': os.environ['VIEWER_KEYCLOAK_CLIENT_ID'],
            'grant_type': 'password',
            'username': os.environ['VIEWER_KEYCLOAK_USERNAME'],
            'password': os.environ['VIEWER_KEYCLOAK_PASSWORD'],
            'scope': 'openid profile email',
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=10,
        verify=os.environ.get('VIEWER_KEYCLOAK_VERIFY_TLS', 'false').lower() == 'true',
    )
    response.raise_for_status()
    return response.json()


def _create_viewer_handoff(user_id, study_iuid, user_type='staff'):
    """Crea el handoff de un solo uso para personal o pacientes.

    ``user_id`` es un identificador polimórfico: el personal pertenece a
    ``tbuser`` y los pacientes a ``tbuser_patient``. La tabla de handoff no
    puede imponer una FK a una sola de esas tablas; ``user_type`` conserva el
    espacio de nombres que debe usarse al intercambiar la sesión.
    """
    if os.environ.get('VIEWER_HANDOFF_MODE', 'exchange').lower() == 'legacy':
        token_data = _request_viewer_keycloak_token()
        params = urlencode({'access_token': token_data['access_token'], 'study_uid': study_iuid})
        return f"{_get_viewer_base_url()}/set-token.html?{params}", token_data.get('expires_in', 300)

    handoff_code = secrets.token_urlsafe(48)
    code_hash = hashlib.sha256(handoff_code.encode()).hexdigest()
    connection = psycopg2.connect(**get_db_config())
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM nextris.tb_viewer_handoff WHERE expires_at < NOW() - INTERVAL '1 hour'")
            cursor.execute("""
                INSERT INTO nextris.tb_viewer_handoff
                    (code_hash, user_id, study_iuid, user_type, expires_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (code_hash, user_id, study_iuid, user_type or 'staff', datetime.now() + timedelta(seconds=60)))
            connection.commit()
    finally:
        connection.close()
    params = urlencode({'handoff_code': handoff_code, 'study_uid': study_iuid})
    return f"{_get_viewer_base_url()}/set-token.html?{params}", 60


def _build_public_share_url(raw_token):
    """Construye URL absoluta del enlace temporal compartible."""
    return build_share_url(raw_token)


def _send_share_link_email(patient_email, share_url, expires_at, patient_name, study_desc, reason,
                           smtp_server, smtp_port, smtp_user, smtp_password,
                           smtp_from, smtp_from_name, use_tls):
    """Envía el enlace temporal al destinatario por SMTP con HTML estilizado."""
    if not smtp_user or not smtp_password:
        raise Exception("Configuración SMTP incompleta")

    exp_str = (
        expires_at.strftime('%d/%m/%Y %H:%M') + ' UTC'
        if hasattr(expires_at, 'strftime') else str(expires_at)
    )

    reason_row = (
        f'<tr>'
        f'<td style="padding:4px 0;color:#6b7280;font-size:13px;width:110px;vertical-align:top;">Motivo</td>'
        f'<td style="padding:4px 0;color:#111827;font-size:13px;font-weight:600;">{reason}</td>'
        f'</tr>'
        if reason else ""
    )

    html = (
        '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#f3f4f6;font-family:\'Segoe UI\',Arial,sans-serif;">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 16px;">'
        '<tr><td align="center">'
        '<table width="600" cellpadding="0" cellspacing="0"'
        ' style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;'
        'overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">'

        # Header
        '<tr><td style="background:linear-gradient(135deg,#2D1B4E 0%,#440f6d 60%,#1a0f2e 100%);'
        'padding:32px 40px;text-align:center;">'
        '<p style="margin:0;font-size:28px;font-weight:800;color:#ffffff;'
        'letter-spacing:2px;text-transform:uppercase;text-shadow:0 2px 8px rgba(0,0,0,0.3);">'
        'Next<span style="color:#c084fc;">RIS</span></p>'
        '<p style="margin:8px 0 0;font-size:12px;color:#c4b5fd;letter-spacing:1px;text-transform:uppercase;">'
        'Sistema de Información Radiológica</p>'
        '</td></tr>'

        # Body
        '<tr><td style="padding:36px 40px 28px;">'
        '<p style="margin:0 0 6px;font-size:15px;color:#6b7280;">Estimado/a,</p>'
        '<p style="margin:0 0 24px;font-size:15px;color:#374151;line-height:1.6;">'
        'Se ha generado un <strong>enlace temporal seguro</strong> para que pueda '
        'visualizar el siguiente estudio médico en el visor de imágenes NextRIS.</p>'

        # Study card
        '<table width="100%" cellpadding="0" cellspacing="0"'
        ' style="background:#faf5ff;border:1px solid #e9d5ff;border-radius:8px;'
        'padding:20px 24px;margin-bottom:28px;">'
        '<tr><td>'
        '<p style="margin:0 0 14px;font-size:11px;font-weight:700;color:#7c3aed;'
        'letter-spacing:1px;text-transform:uppercase;">Detalle del estudio</p>'
        '<table cellpadding="0" cellspacing="0" style="width:100%;">'
        f'<tr><td style="padding:4px 0;color:#6b7280;font-size:13px;width:110px;vertical-align:top;">Paciente</td>'
        f'<td style="padding:4px 0;color:#111827;font-size:13px;font-weight:600;">{patient_name or "—"}</td></tr>'
        f'<tr><td style="padding:4px 0;color:#6b7280;font-size:13px;vertical-align:top;">Estudio</td>'
        f'<td style="padding:4px 0;color:#111827;font-size:13px;font-weight:600;">{study_desc or "—"}</td></tr>'
        f'<tr><td style="padding:4px 0;color:#6b7280;font-size:13px;vertical-align:top;">Válido hasta</td>'
        f'<td style="padding:4px 0;color:#111827;font-size:13px;font-weight:600;">{exp_str}</td></tr>'
        f'{reason_row}'
        '</table></td></tr></table>'

        # CTA button
        '<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">'
        '<tr><td align="center">'
        f'<a href="{share_url}"'
        ' style="display:inline-block;background:linear-gradient(135deg,#440f6d,#7c3aed);'
        'color:#ffffff;text-decoration:none;font-size:15px;font-weight:700;'
        'padding:14px 36px;border-radius:8px;'
        'box-shadow:0 4px 14px rgba(68,15,109,0.35);letter-spacing:0.5px;">'
        '&#128302;&nbsp; Abrir visor de imágenes</a>'
        '</td></tr></table>'

        # Fallback link
        '<p style="margin:0 0 6px;font-size:12px;color:#9ca3af;text-align:center;">'
        'Si el botón no funciona, copie y pegue este enlace en su navegador:</p>'
        f'<p style="margin:0 0 24px;font-size:11px;color:#7c3aed;text-align:center;'
        f'word-break:break-all;line-height:1.5;">'
        f'<a href="{share_url}" style="color:#7c3aed;">{share_url}</a></p>'

        # Warning box
        '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
        '<td style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:12px 16px;">'
        f'<p style="margin:0;font-size:12px;color:#92400e;line-height:1.5;">'
        f'&#9888;&#65039;&nbsp;<strong>Uso personal.</strong> '
        f'Este enlace es de acceso único para usted. No lo comparta con terceros. '
        f'Vence el <strong>{exp_str}</strong>.</p>'
        '</td></tr></table>'

        '</td></tr>'

        # Footer
        '<tr><td style="background:#f9fafb;border-top:1px solid #e5e7eb;'
        'padding:20px 40px;text-align:center;">'
        f'<p style="margin:0 0 4px;font-size:12px;color:#9ca3af;">'
        f'Este es un mensaje automático generado por '
        f'<strong style="color:#440f6d;">{smtp_from_name}</strong>.</p>'
        '<p style="margin:0;font-size:11px;color:#d1d5db;">Por favor no responda a este correo.</p>'
        '</td></tr>'

        '</table></td></tr></table>'
        '</body></html>'
    )

    plain = (
        f"Enlace de acceso a imágenes - NextRIS\n\n"
        f"Paciente : {patient_name or '-'}\n"
        f"Estudio  : {study_desc or '-'}\n"
        f"Válido   : {exp_str}\n"
        + (f"Motivo   : {reason}\n" if reason else "")
        + f"\n{share_url}\n\n"
        f"IMPORTANTE: Enlace de uso personal. No comparta con terceros.\n\n"
        f"{smtp_from_name}"
    )

    msg = MIMEMultipart('alternative')
    msg['From'] = f"{smtp_from_name} <{smtp_from}>"
    msg['To'] = patient_email
    msg['Subject'] = 'Acceso a imágenes médicas — NextRIS'
    msg.attach(MIMEText(plain, 'plain', 'utf-8'))
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        if use_tls:
            server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_from, patient_email, msg.as_string())


def _insert_share_access_log(cursor, share_guid, success, ip_address, user_agent=None, reason=None, failure_reason=None):
    cursor.execute(
        """
        INSERT INTO nextris.tbviewer_share_link_access (
            share_guid,
            opened_at,
            success,
            failure_reason,
            ip_address,
            user_agent,
            reason
        ) VALUES (%s, NOW(), %s, %s, %s, %s, %s)
        """,
        (share_guid, success, failure_reason, ip_address, user_agent, reason)
    )


def _load_share_scope(raw_token):
    """Devuelve el enlace válido y su único StudyInstanceUID."""
    connection = psycopg2.connect(**get_db_config())
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT guid, study_iuid, expires_at, revoked
            FROM nextris.tbviewer_share_link
            WHERE token_hash = %s OR short_code = %s
            LIMIT 1
            """,
            (_hash_share_token(raw_token), raw_token),
        )
        row = cursor.fetchone()
        if not row or row[3] or not row[2] or datetime.utcnow() >= row[2]:
            return None
        return {'guid': row[0], 'study_iuid': str(row[1]), 'expires_at': row[2]}
    finally:
        cursor.close()
        connection.close()


def _requested_study_uid(dicom_path):
    """Extrae el UID solicitado de una ruta DICOMweb o de sus parámetros."""
    import re
    query_uid = request.args.get('StudyInstanceUID') or request.args.get('studyUID')
    if query_uid:
        return query_uid
    match = re.search(r'/studies/([^/]+)', dicom_path or '', re.IGNORECASE)
    return match.group(1) if match else None


@api_blueprint.route('/general/share-dicom/<raw_token>/<path:dicom_path>', methods=['GET', 'POST', 'OPTIONS'])
def share_dicom_gateway(raw_token, dicom_path):
    """Gateway DICOMweb para enlaces públicos, estrictamente study-scoped."""
    if request.method == 'OPTIONS':
        return Response(status=204)

    try:
        scope = _load_share_scope(raw_token)
        if not scope:
            return jsonify({'success': False, 'message': 'Enlace inválido o expirado'}), 403

        requested_uid = _requested_study_uid(dicom_path)
        if requested_uid != scope['study_iuid']:
            return jsonify({'success': False, 'message': 'Estudio no autorizado'}), 403

        try:
            access_token = _request_viewer_keycloak_token().get('access_token')
        except (KeyError, requests.RequestException):
            return jsonify({'success': False, 'message': 'No se pudo autenticar el visor'}), 502
        internal_base = current_app.config.get(
            'DICOMWEB_INTERNAL_URL', os.getenv('DICOMWEB_INTERNAL_URL', 'http://127.0.0.1:8088')
        ).rstrip('/')
        target_url = f"{internal_base}/{dicom_path}"
        forwarded_headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': request.headers.get('Accept', '*/*'),
            # dcm4chee valida el virtual host aun cuando el gateway conecta
            # contra 127.0.0.1; sin este encabezado responde 403.
            'Host': request.host.split(':', 1)[0],
            'X-Forwarded-Host': request.host,
            'X-Forwarded-Proto': 'https',
        }
        if request.content_type:
            forwarded_headers['Content-Type'] = request.content_type
        upstream = requests.request(
            request.method,
            target_url,
            params=request.args,
            data=request.get_data(),
            headers=forwarded_headers,
            timeout=60,
            verify=False,
        )
        response_headers = {}
        for header in ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges'):
            if upstream.headers.get(header):
                response_headers[header] = upstream.headers[header]
        return Response(upstream.content, status=upstream.status_code, headers=response_headers)
    except requests.RequestException as exc:
        print(f"[SHARE DICOM] Error de gateway: {exc}")
        return jsonify({'success': False, 'message': 'No se pudo consultar la imagen'}), 502
    except Exception as exc:
        print(f"[SHARE DICOM] Error interno: {exc}")
        return jsonify({'success': False, 'message': 'No se pudo consultar la imagen'}), 500


def _ensure_share_link_raw_token_column(connection):
    """Compatibilidad con instalaciones antiguas; no agrega tokens planos."""
    return None


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
            "viewer_url": f"{_get_viewer_base_url()}/viewer?StudyInstanceUIDs=..."
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
        
        token_user_id = get_jwt_identity()
        user_id = token_user_id
        requested_user_id = data.get('user_id')
        examination_id = data.get('examination_id')
        
        if not examination_id:
            return jsonify({
                'success': False,
                'message': 'examination_id es requerido'
            }), 400

        # Seguridad: si viene user_id en el body, no se usa para permisos.
        # Se conserva solo para detectar discrepancias de clientes antiguos.
        if requested_user_id and requested_user_id != token_user_id:
            print(
                f"[API VIEWER URL] Advertencia: user_id body ({requested_user_id}) "
                f"no coincide con JWT ({token_user_id})"
            )
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener studyinstanceuid del examen
        cursor.execute("""
            SELECT studyinstanceuid
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
        
        study_uid = result[0]
        
        if not study_uid:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'El examen no tiene un Study UID asignado'
            }), 400
        
        cursor.close()
        connection.close()

        try:
            viewer_url, expires_in = _create_viewer_handoff(
                user_id, study_uid, get_jwt().get('user_type', 'staff')
            )
            return jsonify({'success': True, 'data': {
                'study_uid': study_uid,
                'viewer_url': viewer_url,
                'direct_url': f"{_get_viewer_base_url()}/viewer?StudyInstanceUIDs={study_uid}",
                'expires_in': expires_in,
            }}), 200
        except (KeyError, requests.RequestException):
            return jsonify({'success': False, 'message': 'No se pudo iniciar la sesión del visor'}), 502
        
        # Obtener token de Keycloak usando credenciales del usuario genérico del visor
        keycloak_url = os.environ['VIEWER_KEYCLOAK_TOKEN_URL']
        
        keycloak_data = {
            'client_id': os.environ['VIEWER_KEYCLOAK_CLIENT_ID'],
            'grant_type': 'password',
            'username': os.environ['VIEWER_KEYCLOAK_USERNAME'],
            'password': os.environ['VIEWER_KEYCLOAK_PASSWORD'],
            'scope': 'openid profile email'
        }
        
        try:
            keycloak_response = requests.post(
                keycloak_url,
                data=keycloak_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                verify=False
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
                'study_uid': study_uid,
                'examination_id': examination_id,
                'access_token': access_token,
                'expires_at': datetime.now() + timedelta(seconds=expires_in),
                'created_at': datetime.now()
            }
            
            # URL directa a set-token.html en viewer.nextris.cloud
            # Esto evita el problema de múltiples workers de gunicorn con cache en memoria
            viewer_params = urlencode({'access_token': access_token, 'study_uid': study_uid})
            viewer_url = f"{_get_viewer_base_url()}/set-token.html?{viewer_params}"
            
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
            window.location.href = "{_get_viewer_base_url()}/viewer?StudyInstanceUIDs={study_uid}&session_id={session_id}";
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
                    'direct_url': f"{_get_viewer_base_url()}/viewer?StudyInstanceUIDs={study_uid}",
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

        # Redirigir a set-token.html en viewer.nextris.cloud para que el token se guarde
        # en el localStorage correcto (mismo dominio que OHIF)
        from urllib.parse import urlencode, quote_plus
        params = urlencode({'access_token': access_token, 'study_uid': study_uid})
        return redirect(f"{_get_viewer_base_url()}/set-token.html?{params}", code=302)
        
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
                'location_id': session.get('location_id'),
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


@api_blueprint.route('/general/viewer-url-by-iuid', methods=['POST'])
@jwt_required()
def get_viewer_url_by_iuid():
    """
    Obtener URL del visor DICOM usando study_iuid de PACS directamente.
    Verifica que el estudio exista en public.study y que el usuario tenga
    acceso a la location asignada (si tiene location_id asignada).

    Body JSON:
    {
        "study_iuid": "1.2.3.4.5..."
    }
    """
    try:
        data = request.get_json()
        if not data or not data.get('study_iuid'):
            return jsonify({'success': False, 'message': 'study_iuid es requerido'}), 400

        study_iuid = data['study_iuid']
        user_id = get_jwt_identity()

        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        # Buscar el estudio en PACS
        cursor.execute(
            "SELECT pk, location_id FROM public.study WHERE study_iuid = %s",
            (study_iuid,)
        )
        result = cursor.fetchone()

        if not result:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Estudio no encontrado en PACS'}), 404

        location_id = result[1]

        user_type = get_jwt().get('user_type', '').lower()

        if user_type == 'patient':
            # Verificar que el estudio pertenece al paciente autenticado
            cursor.execute("""
                SELECT 1 FROM nextris.tbuser_patient up
                INNER JOIN nextris.tbexamination ex ON ex.idpatient = up.datapatient_id
                WHERE up.guid = %s AND ex.studyinstanceuid = %s
            """, (user_id, study_iuid))
            has_permission = cursor.fetchone()
            cursor.close()
            connection.close()

            if not has_permission:
                return jsonify({
                    'success': False,
                    'message': 'No tiene permisos para ver las imágenes de este estudio'
                }), 403
        elif location_id:
            cursor.execute(
                "SELECT 1 FROM nextris.rel_user_location WHERE user_id = %s AND location_id = %s",
                (user_id, str(location_id))
            )
            has_permission = cursor.fetchone()
            cursor.close()
            connection.close()

            if not has_permission:
                return jsonify({
                    'success': False,
                    'message': 'No tiene permisos para ver las imágenes de esta ubicación'
                }), 403
        else:
            cursor.close()
            connection.close()

        # Handoff opaco por defecto; modo legacy disponible sólo para rollback.
        viewer_url, expires_in = _create_viewer_handoff(user_id, study_iuid, user_type)
        return jsonify({
            'success': True,
            'data': {
                'study_uid': study_iuid,
                'viewer_url': viewer_url,
                'direct_url': f"{_get_viewer_base_url()}/viewer?StudyInstanceUIDs={study_iuid}",
                'expires_in': expires_in
            }
        }), 200

    except Exception as e:
        print(f"[VIEWER BY IUID] Error: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@api_blueprint.route('/general/viewer-share-links', methods=['POST'])
@jwt_required()
def create_viewer_share_link():
    """
    Crea un enlace temporal para compartir acceso al visor de un estudio PACS.
    El enlace es de uso ilimitado hasta su expiración.

    Body JSON:
    {
        "study_iuid": "1.2.840....",
        "expires_hours": 24,
        "reason": "opcional",
        "patient_email": "opcional"
    }
    """
    try:
        data = request.get_json() or {}
        study_iuid = (data.get('study_iuid') or '').strip()
        reason = (data.get('reason') or '').strip() or None
        patient_email = (data.get('patient_email') or '').strip() or None
        expires_hours = data.get('expires_hours', default_expiration_hours())

        if not study_iuid:
            return jsonify({'success': False, 'message': 'study_iuid es requerido'}), 400

        try:
            expires_hours = int(expires_hours)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'expires_hours debe ser numérico'}), 400

        if expires_hours < 1 or expires_hours > 8760:
            return jsonify({'success': False, 'message': 'expires_hours debe estar entre 1 y 8760'}), 400

        user_id = str(get_jwt_identity())
        db_config = get_db_config()

        connection = psycopg2.connect(**db_config)
        _ensure_share_link_raw_token_column(connection)
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT s.pk, s.location_id, s.study_desc, COALESCE(pn.alphabetic_name, '')
            FROM public.study s
            LEFT JOIN public.patient p ON p.pk = s.patient_fk
            LEFT JOIN public.person_name pn ON pn.pk = p.pat_name_fk
            WHERE s.study_iuid = %s
            """,
            (study_iuid,)
        )
        study_row = cursor.fetchone()

        if not study_row:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Estudio no encontrado en PACS'}), 404

        location_id = study_row[1]
        study_desc = study_row[2] or ''
        patient_name = study_row[3] or ''

        if location_id:
            cursor.execute(
                "SELECT 1 FROM nextris.rel_user_location WHERE user_id = %s AND location_id = %s",
                (user_id, str(location_id))
            )
            has_permission = cursor.fetchone()

            if not has_permission:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'No tiene permisos para compartir estudios de esta ubicación'
                }), 403

        raw_token = secrets.token_urlsafe(32)
        short_code = secrets.token_urlsafe(7)
        token_hash = _hash_share_token(raw_token)
        share_guid = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        ip_address = _get_client_ip()

        # Solo un enlace activo por estudio: regenerar invalida el anterior.
        cursor.execute(
            """
            UPDATE nextris.tbviewer_share_link
            SET revoked = TRUE, revoked_at = NOW()
            WHERE study_iuid = %s AND revoked = FALSE
            """,
            (study_iuid,),
        )

        cursor.execute(
            """
            INSERT INTO nextris.tbviewer_share_link (
                guid,
                token_hash,
                short_code,
                study_iuid,
                location_id,
                created_by_user_id,
                created_at,
                expires_at,
                revoked,
                open_count,
                reason,
                patient_email,
                created_ip
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, FALSE, 0, %s, %s, %s)
            RETURNING short_code
            """,
            (
                share_guid,
                token_hash,
                short_code,
                study_iuid,
                str(location_id) if location_id else None,
                user_id,
                expires_at,
                reason,
                patient_email,
                ip_address,
            )
        )
        stored_short_code = cursor.fetchone()
        if not stored_short_code or not stored_short_code[0]:
            raise RuntimeError('El código corto del enlace no se pudo guardar')

        # Leer config SMTP antes de cerrar la conexión (solo si hay email destino)
        smtp_cfg = None
        if patient_email:
            cursor.execute(
                "SELECT smtp_server, smtp_port, smtp_user, smtp_password, smtp_from, smtp_from_name, use_tls "
                "FROM nextris.tbfacility LIMIT 1"
            )
            smtp_row = cursor.fetchone() or ()
            smtp_cfg = {
                'smtp_server': (smtp_row[0] if smtp_row else None) or os.environ.get('SMTP_SERVER', 'smtp.gmail.com'),
                'smtp_port':   (smtp_row[1] if smtp_row else None) or int(os.environ.get('SMTP_PORT', '587')),
                'smtp_user':   (smtp_row[2] if smtp_row else None) or os.environ.get('SMTP_USER'),
                'smtp_password': (smtp_row[3] if smtp_row else None) or os.environ.get('SMTP_PASSWORD'),
                'smtp_from':   (smtp_row[4] if smtp_row else None) or os.environ.get('SMTP_FROM'),
                'smtp_from_name': (smtp_row[5] if smtp_row else None) or os.environ.get('SMTP_FROM_NAME', 'NextRIS'),
                'use_tls':     (smtp_row[6] if smtp_row and smtp_row[6] is not None else True),
            }
            if not smtp_cfg['smtp_from']:
                smtp_cfg['smtp_from'] = smtp_cfg['smtp_user']

        connection.commit()
        cursor.close()
        connection.close()

        share_url = _build_public_share_url(str(stored_short_code[0]))

        email_sent = False
        email_error = None
        if patient_email and smtp_cfg:
            try:
                _send_share_link_email(
                    patient_email=patient_email,
                    share_url=share_url,
                    expires_at=expires_at,
                    patient_name=patient_name,
                    study_desc=study_desc,
                    reason=reason,
                    **smtp_cfg
                )
                email_sent = True
            except Exception as mail_err:
                email_error = str(mail_err)
                print(f"[VIEWER SHARE] Error enviando email: {mail_err}")

        response_data = {
            'success': True,
            'message': 'Enlace temporal generado exitosamente',
            'data': {
                'guid': share_guid,
                'study_iuid': study_iuid,
                'location_id': str(location_id) if location_id else None,
                'share_url': share_url,
                'expires_at': expires_at.isoformat() + 'Z',
                'expires_hours': expires_hours,
                'reason': reason,
                'patient_email': patient_email,
                'email_sent': email_sent,
            }
        }
        if email_error:
            response_data['email_error'] = email_error

        return jsonify(response_data), 201

    except Exception as e:
        print(f"[VIEWER SHARE] Error creando enlace: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@api_blueprint.route('/general/viewer-share-links/active', methods=['GET'])
@jwt_required()
def get_active_viewer_share_links():
    """
    Retorna links activos por study_iuid para estudios a los que el usuario tiene acceso.

    Query params:
      - study_iuids: lista separada por comas

    Respuesta:
    {
      "success": true,
      "data": {
        "<study_iuid>": {
          "is_active": true,
          "share_url": "https://.../open-shared-viewer/<token>",
          "expires_at": "..."
        }
      }
    }
    """
    connection = None
    cursor = None

    try:
        raw_study_iuids = (request.args.get('study_iuids') or '').strip()
        study_iuids = [item.strip() for item in raw_study_iuids.split(',') if item.strip()]

        if not study_iuids:
            return jsonify({'success': True, 'data': {}}), 200

        user_id = str(get_jwt_identity())
        db_config = get_db_config()

        connection = psycopg2.connect(**db_config)
        _ensure_share_link_raw_token_column(connection)
        cursor = connection.cursor()

        cursor.execute(
            """
            WITH allowed_studies AS (
                SELECT DISTINCT s.study_iuid
                FROM public.study s
                INNER JOIN nextris.rel_user_location rul
                    ON rul.location_id::text = s.location_id::text
                WHERE rul.user_id = %s
                  AND s.study_iuid = ANY(%s)
            )
            SELECT DISTINCT ON (sl.study_iuid)
                sl.study_iuid,
                sl.expires_at
            FROM nextris.tbviewer_share_link sl
            INNER JOIN allowed_studies a ON a.study_iuid = sl.study_iuid
            WHERE sl.revoked = FALSE
              AND sl.expires_at > NOW()
            ORDER BY sl.study_iuid, sl.created_at DESC
            """,
            (user_id, study_iuids),
        )

        active_map = {study_iuid: {'is_active': False} for study_iuid in study_iuids}

        for row in cursor.fetchall():
            study_iuid = row[0]
            expires_at = row[1]

            active_map[study_iuid] = {
                'is_active': True,
                # No se reconstruye el token: solo se entrega al crearlo.
                'share_url': None,
                'expires_at': expires_at.isoformat() + 'Z' if expires_at else None,
            }

        return jsonify({'success': True, 'data': active_map}), 200

    except Exception as e:
        print(f"[VIEWER SHARE ACTIVE] Error: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@api_blueprint.route('/general/open-shared-viewer/<raw_token>', methods=['GET'])
@api_blueprint.route('/s/<short_code>', methods=['GET'])
def open_shared_viewer(raw_token=None, short_code=None):
    """Abre visor usando enlace temporal sin requerir sesión RIS."""
    connection = None
    cursor = None
    ip_address = _get_client_ip()
    user_agent = request.headers.get('User-Agent')

    try:
        share_key = short_code or raw_token
        if not share_key:
            return "<h1>Enlace inválido</h1>", 400

        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT guid, study_iuid, reason, expires_at, revoked
            FROM nextris.tbviewer_share_link
            WHERE token_hash = %s OR short_code = %s
            """,
            (_hash_share_token(share_key), share_key)
        )
        share_row = cursor.fetchone()

        if not share_row:
            return "<h1>Enlace no válido o expirado</h1>", 404

        share_guid = share_row[0]
        study_iuid = share_row[1]
        reason = share_row[2]
        expires_at = share_row[3]
        revoked = share_row[4]

        if revoked:
            _insert_share_access_log(cursor, share_guid, False, ip_address, user_agent, reason, 'link_revocado')
            connection.commit()
            return "<h1>Este enlace fue revocado</h1>", 410

        if datetime.utcnow() > expires_at:
            _insert_share_access_log(cursor, share_guid, False, ip_address, user_agent, reason, 'link_expirado')
            connection.commit()
            return "<h1>Este enlace ha expirado</h1>", 410

        cursor.execute(
            """
            UPDATE nextris.tbviewer_share_link
            SET open_count = COALESCE(open_count, 0) + 1,
                last_opened_at = NOW(),
                last_opened_ip = %s
            WHERE guid = %s
            """,
            (ip_address, share_guid)
        )
        _insert_share_access_log(cursor, share_guid, True, ip_address, user_agent, reason)
        connection.commit()

        viewer_params = urlencode({
            'StudyInstanceUIDs': study_iuid,
            'share_token': share_key,
        })
        return redirect(f"{_get_viewer_base_url()}/viewer?{viewer_params}", code=302)

    except Exception as e:
        print(f"[VIEWER SHARE OPEN] Error: {str(e)}")
        return "<h1>Error al abrir el visor compartido</h1>", 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def _report_share_row(report_id, user_id, cursor):
    cursor.execute(
        """
        SELECT ex.studyinstanceuid, ex.location_id
        FROM nextris.tbexamination ex
        WHERE ex.guid = %s
        LIMIT 1
        """,
        (str(report_id),),
    )
    row = cursor.fetchone()
    if not row or not row[0]:
        return None
    if row[1]:
        cursor.execute(
            """
            SELECT 1 FROM nextris.rel_user_location
            WHERE user_id = %s AND location_id = %s
            LIMIT 1
            """,
            (str(user_id), str(row[1])),
        )
        if not cursor.fetchone():
            return False
    return row


@api_blueprint.route('/reports/<report_id>/share-link', methods=['POST'])
@jwt_required()
def create_report_share_link(report_id):
    """Genera un enlace público persistente y acotado al estudio del reporte."""
    connection = None
    try:
        connection = psycopg2.connect(**get_db_config())
        cursor = connection.cursor()
        row = _report_share_row(report_id, get_jwt_identity(), cursor)
        if row is False:
            return jsonify({'success': False, 'message': 'No tiene permisos para compartir este estudio'}), 403
        if not row:
            return jsonify({'success': False, 'message': 'Reporte o estudio no encontrado'}), 404
        result = create_share_for_exam(
            report_id,
            created_by=get_jwt_identity(),
            connection=connection,
        )
        connection.commit()
        result['expires_at'] = result['expires_at'].isoformat() + 'Z'
        return jsonify({'success': True, 'data': result}), 201
    except Exception as exc:
        if connection:
            connection.rollback()
        print(f"[REPORT SHARE] Error creando enlace: {exc}")
        return jsonify({'success': False, 'message': 'No se pudo generar el enlace'}), 500
    finally:
        if connection:
            connection.close()


@api_blueprint.route('/reports/<report_id>/share-link', methods=['GET'])
@jwt_required()
def get_report_share_link(report_id):
    connection = None
    try:
        connection = psycopg2.connect(**get_db_config())
        cursor = connection.cursor()
        row = _report_share_row(report_id, get_jwt_identity(), cursor)
        if row is False:
            return jsonify({'success': False, 'message': 'No tiene permisos para consultar este estudio'}), 403
        if not row:
            return jsonify({'success': False, 'message': 'Reporte o estudio no encontrado'}), 404
        cursor.execute(
            """
            SELECT guid, study_iuid, expires_at, revoked, open_count,
                   last_opened_at, created_at
            FROM nextris.tbviewer_share_link
            WHERE study_iuid = %s AND revoked = FALSE AND expires_at > NOW()
            ORDER BY created_at DESC LIMIT 1
            """,
            (row[0],),
        )
        link = cursor.fetchone()
        if not link:
            return jsonify({'success': True, 'data': {'is_active': False}}), 200
        return jsonify({'success': True, 'data': {
            'is_active': True,
            'guid': str(link[0]),
            'study_iuid': link[1],
            'expires_at': link[2].isoformat() + 'Z',
            'open_count': link[4],
            'last_opened_at': link[5].isoformat() + 'Z' if link[5] else None,
            'created_at': link[6].isoformat() + 'Z' if link[6] else None,
        }}), 200
    finally:
        if connection:
            connection.close()


@api_blueprint.route('/reports/<report_id>/share-link', methods=['DELETE'])
@jwt_required()
def revoke_report_share_link(report_id):
    connection = None
    try:
        connection = psycopg2.connect(**get_db_config())
        cursor = connection.cursor()
        row = _report_share_row(report_id, get_jwt_identity(), cursor)
        if row is False:
            return jsonify({'success': False, 'message': 'No tiene permisos para revocar este estudio'}), 403
        if not row:
            return jsonify({'success': False, 'message': 'Reporte o estudio no encontrado'}), 404
        cursor.execute(
            """
            UPDATE nextris.tbviewer_share_link
            SET revoked = TRUE, revoked_at = NOW()
            WHERE study_iuid = %s AND revoked = FALSE
            """,
            (row[0],),
        )
        connection.commit()
        return jsonify({'success': True, 'message': 'Enlace revocado'}), 200
    except Exception:
        if connection:
            connection.rollback()
        return jsonify({'success': False, 'message': 'No se pudo revocar el enlace'}), 500
    finally:
        if connection:
            connection.close()


@api_blueprint.route('/share-links/<share_guid>/revoke', methods=['POST'])
@jwt_required()
def revoke_share_link_by_guid(share_guid):
    """Revoca un enlace concreto usando su identificador interno."""
    connection = None
    try:
        connection = psycopg2.connect(**get_db_config())
        cursor = connection.cursor()
        user_id = str(get_jwt_identity())
        cursor.execute(
            """
            SELECT sl.location_id
            FROM nextris.tbviewer_share_link sl
            WHERE sl.guid = %s
            LIMIT 1
            """,
            (share_guid,),
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Enlace no encontrado'}), 404
        if row[0]:
            cursor.execute(
                """
                SELECT 1 FROM nextris.rel_user_location
                WHERE user_id = %s AND location_id = %s LIMIT 1
                """,
                (user_id, str(row[0])),
            )
            if not cursor.fetchone():
                return jsonify({'success': False, 'message': 'No tiene permisos para revocar este enlace'}), 403
        cursor.execute(
            """
            UPDATE nextris.tbviewer_share_link
            SET revoked = TRUE, revoked_at = NOW()
            WHERE guid = %s
            """,
            (share_guid,),
        )
        connection.commit()
        return jsonify({'success': True, 'message': 'Enlace revocado'}), 200
    except Exception:
        if connection:
            connection.rollback()
        return jsonify({'success': False, 'message': 'No se pudo revocar el enlace'}), 500
    finally:
        if connection:
            connection.close()
