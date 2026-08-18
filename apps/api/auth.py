# -*- encoding: utf-8 -*-
"""
API de Autenticación - Endpoints JWT para React
"""

from flask import jsonify, request
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token, 
    jwt_required, 
    get_jwt_identity
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import psycopg2
import uuid
import os
import re
import secrets
import hashlib
from datetime import datetime, timedelta
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from apps.api import api_blueprint
from apps.api.permissions import get_user_permission_codes, get_default_permissions_for_role, replace_user_permissions
from apps.authentication.models import Users, PatientUser
from apps import db


def _get_db_config():
    from apps.home.services import ConfigService
    return ConfigService.get_db_config()


def _ensure_user_medical_table(connection):
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.tbuser_medical_data (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) UNIQUE NOT NULL,
                aclaracion_firma VARCHAR(255) NOT NULL,
                matricula_nacional VARCHAR(100) NOT NULL,
                firma_digital VARCHAR(500),
                firma_habilitada BOOLEAN DEFAULT FALSE,
                fecha_creacion TIMESTAMP DEFAULT NOW(),
                fecha_actualizacion TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES nextris.tbuser(guid) ON DELETE CASCADE
            )
            """
        )
        connection.commit()
    finally:
        cursor.close()


def _column_exists(connection, schema_name, table_name, column_name):
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
            (schema_name, table_name, column_name),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def _get_table_columns(connection, schema_name, table_name):
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            """,
            (schema_name, table_name),
        )
        return {row[0] for row in cursor.fetchall()}
    finally:
        cursor.close()


def _table_exists(connection, schema_name, table_name):
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name = %s
            LIMIT 1
            """,
            (schema_name, table_name),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def _dynamic_insert(cursor, schema_name, table_name, values_by_column):
    columns = list(values_by_column.keys())
    placeholders = ', '.join(['%s'] * len(columns))
    columns_sql = ', '.join(columns)
    query = f"INSERT INTO {schema_name}.{table_name} ({columns_sql}) VALUES ({placeholders})"
    cursor.execute(query, tuple(values_by_column[col] for col in columns))


def _save_uploaded_image(file_storage, prefix, max_bytes, subfolder):
    if not file_storage or not file_storage.filename:
        return None

    allowed_extensions = {'.png', '.jpg', '.jpeg'}
    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions:
        raise ValueError('Formato de archivo inválido. Use PNG/JPG/JPEG')

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > max_bytes:
        raise ValueError(f'Archivo excede el tamaño máximo de {max_bytes // (1024 * 1024)}MB')

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    upload_dir = os.path.join(project_root, subfolder)
    os.makedirs(upload_dir, exist_ok=True)

    unique_name = f"{prefix}_{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(upload_dir, unique_name)
    file_storage.save(file_path)
    return unique_name


def _send_code_email(to_email, code):
    env_smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    env_smtp_port_raw = os.environ.get('SMTP_PORT', '587')
    env_smtp_user = os.environ.get('SMTP_USER')
    env_smtp_password = os.environ.get('SMTP_PASSWORD')
    env_smtp_from = os.environ.get('SMTP_FROM')
    env_smtp_from_name = os.environ.get('SMTP_FROM_NAME', 'NextRIS')
    resend_api_key = os.environ.get('RESEND_API_KEY')

    def _safe_port(value, default=587):
        try:
            return int(value)
        except Exception:
            return int(default)

    smtp_server = env_smtp_server
    smtp_port = _safe_port(env_smtp_port_raw, 587)
    smtp_user = env_smtp_user
    smtp_password = env_smtp_password
    smtp_from = env_smtp_from or smtp_user
    smtp_from_name = env_smtp_from_name
    use_tls = True

    body_text = (
        f"Su código de verificación NextRIS es: {code}\n\n"
        "Este código expira en 30 minutos.\n"
        "Si no solicitó este código, ignore este mensaje.\n\n"
        "NextRIS"
    )
    body_html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"/><title>Verificación NextRIS</title></head>
<body style="margin:0;padding:0;background:#0f1226;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
                 style="background:#0f1226;padding:24px 12px;">
        <tr><td align="center">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
                         style="max-width:480px;background:#161a33;border:1px solid #2a2f57;border-radius:14px;overflow:hidden;">
                <tr>
                    <td style="padding:20px 24px;background:linear-gradient(135deg,#7b2cff 0%,#4e1cd2 100%);color:#ffffff;">
                        <div style="font-size:22px;font-weight:700;">NextRIS</div>
                        <div style="font-size:13px;opacity:0.9;margin-top:4px;">Verificación de email</div>
                    </td>
                </tr>
                <tr>
                    <td style="padding:28px 24px;color:#e8ebff;text-align:center;">
                        <p style="margin:0 0 8px 0;font-size:15px;color:#cdd3ff;">Su código de verificación es:</p>
                        <div style="margin:16px auto;letter-spacing:10px;font-size:36px;font-weight:700;
                                                color:#a78bfa;background:#11152d;border:1px solid #4e1cd2;
                                                border-radius:10px;padding:14px 20px;display:inline-block;">{code}</div>
                        <p style="margin:18px 0 0 0;font-size:13px;color:#97a0d6;">
                            Este código expira en <strong style="color:#e8ebff;">30 minutos</strong>.<br/>
                            Si no solicitó este código, ignore este mensaje.
                        </p>
                    </td>
                </tr>
                <tr>
                    <td style="padding:12px 24px 20px;text-align:center;font-size:11px;color:#585f89;">
                        Mensaje automático de NextRIS. No responder.
                    </td>
                </tr>
            </table>
        </td></tr>
    </table>
</body>
</html>"""

    if resend_api_key and env_smtp_from:
        response = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {resend_api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'from': env_smtp_from,
                'to': [to_email],
                'subject': 'Código de verificación - NextRIS',
                'html': body_html,
                'text': body_text,
            },
            timeout=20,
        )
        if response.ok:
            return
        raise RuntimeError(f'No se pudo enviar el email de verificación: {response.text}')

    if not smtp_user or not smtp_password:
        raise RuntimeError(
            'No hay un proveedor de email configurado para validación. '
            'Configure RESEND_API_KEY o SMTP_USER/SMTP_PASSWORD en el backend.'
        )

    msg = MIMEMultipart('alternative')
    msg['From'] = f"{smtp_from_name} <{smtp_from}>"
    msg['To'] = to_email
    msg['Subject'] = 'Código de verificación - NextRIS'
    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
    msg.attach(MIMEText(body_html, 'html', 'utf-8'))

    with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
        if use_tls:
            server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_from, [to_email], msg.as_string())


@api_blueprint.route('/auth/login', methods=['POST'])
def api_login():
    """
    Login endpoint que retorna JWT token
    
    Body JSON:
    {
        "username": "usuario",
        "password": "contraseña",
        "user_type": "staff" o "patient"
    }
    
    Respuesta exitosa:
    {
        "success": true,
        "data": {
            "access_token": "...",
            "refresh_token": "...",
            "user": {
                "id": "...",
                "username": "...",
                "user_type": "...",
                "requires_password_change": false
            }
        },
        "message": "Login exitoso"
    }
    """
    try:
        data = request.get_json(force=True, silent=True)
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON en la petición'
            }), 400
        
        username = data.get('username')
        password = data.get('password')
        user_type = data.get('user_type', 'staff')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Usuario y contraseña requeridos'
            }), 400
        
        user = None
        user_data = {}
        
        if user_type == 'patient':
            try:
                from apps.home.services import ConfigService
                db_config = ConfigService.get_db_config()
                if not db_config:
                    return jsonify({
                        'success': False,
                        'message': 'Error de configuración de base de datos'
                    }), 500
                
                connection = psycopg2.connect(**db_config)
                cursor = connection.cursor()
                
                cursor.execute("""
                    SELECT up.guid, up.username, up.password, dp.name, dp.surname, 
                           dp.email, up.status, up.firstlogin
                    FROM nextris.tbuser_patient up
                    LEFT JOIN nextris.datapatient dp ON up.datapatient_id = dp.guid
                    WHERE up.username = %s
                """, (username,))
                
                patient_row = cursor.fetchone()
                cursor.close()
                connection.close()
                
                if not patient_row:
                    return jsonify({
                        'success': False,
                        'message': 'Credenciales inválidas'
                    }), 401
                
                patient_guid, db_username, db_password, name, surname, email, status, firstlogin = patient_row
                
                if not check_password_hash(db_password, password):
                    return jsonify({
                        'success': False,
                        'message': 'Credenciales inválidas'
                    }), 401
                
                is_active = False
                if isinstance(status, (int, bool)):
                    is_active = bool(status)
                elif isinstance(status, str):
                    is_active = status.lower() in ['active', '1', 'true', 'activo']
                
                if not is_active:
                    return jsonify({
                        'success': False,
                        'message': 'Usuario inactivo'
                    }), 401
                
                user_data = {
                    'id': patient_guid,
                    'username': db_username,
                    'name': name or db_username,
                    'surname': surname or '',
                    'email': email or '',
                    'user_type': 'patient',
                    'requires_password_change': bool(firstlogin)
                }
                
            except Exception as e:
                print(f"[API LOGIN] Error en autenticación de paciente: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': f'Error en la autenticación: {str(e)}'
                }), 500
        
        else:
            user = Users.query.filter_by(username=username, is_active=1).first()
            
            if not user or not check_password_hash(user.password, password):
                return jsonify({
                    'success': False,
                    'message': 'Credenciales inválidas'
                }), 401
            
            user_data = {
                'id': user.id,
                'username': user.username,
                'name': user.name or user.username,
                'surname': user.surname or '',
                'email': user.email or '',
                'user_type': user.user_type,
                'role_id': user.role_id,
                'role_name': (user.user_type or '').lower(),
                'permissions': get_user_permission_codes(user.id, include_role_permissions=True),
                'requires_password_change': bool(user.first_login)
            }
        
        additional_claims = {
            'user_type': user_data['user_type'],
            'username': user_data['username']
        }
        
        access_token = create_access_token(
            identity=user_data['id'],
            additional_claims=additional_claims
        )
        refresh_token = create_refresh_token(
            identity=user_data['id'],
            additional_claims=additional_claims
        )
        
        return jsonify({
            'success': True,
            'data': {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': user_data
            },
            'message': 'Login exitoso'
        }), 200
        
    except Exception as e:
        print(f"[API LOGIN] Error general: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error en el servidor: {str(e)}'
        }), 500


@api_blueprint.route('/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Obtener información del usuario actual autenticado
    
    Headers:
    Authorization: Bearer <access_token>
    
    Respuesta:
    {
        "success": true,
        "data": {
            "id": "...",
            "username": "...",
            "name": "...",
            "email": "...",
            "user_type": "..."
        }
    }
    """
    try:
        user_id = get_jwt_identity()
        
        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        user_type = claims.get('user_type', 'staff')
        
        if user_type == 'patient':
            try:
                from apps.home.services import ConfigService
                db_config = ConfigService.get_db_config()
                connection = psycopg2.connect(**db_config)
                cursor = connection.cursor()
                
                cursor.execute("""
                    SELECT up.guid, up.username, dp.name, dp.surname, dp.email
                    FROM nextris.tbuser_patient up
                    LEFT JOIN nextris.datapatient dp ON up.datapatient_id = dp.guid
                    WHERE up.guid = %s
                """, (user_id,))
                
                patient_row = cursor.fetchone()
                cursor.close()
                connection.close()
                
                if not patient_row:
                    return jsonify({
                        'success': False,
                        'message': 'Usuario no encontrado'
                    }), 404
                
                patient_guid, username, name, surname, email = patient_row
                
                return jsonify({
                    'success': True,
                    'data': {
                        'id': patient_guid,
                        'username': username,
                        'name': name or username,
                        'surname': surname or '',
                        'email': email or '',
                        'user_type': 'patient'
                    }
                }), 200
                
            except Exception as e:
                print(f"[API ME] Error obteniendo paciente: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': f'Error: {str(e)}'
                }), 500
        
        else:
            user = Users.query.get(user_id)
            
            if not user:
                return jsonify({
                    'success': False,
                    'message': 'Usuario no encontrado'
                }), 404
            
            return jsonify({
                'success': True,
                'data': {
                    'id': user.id,
                    'username': user.username,
                    'name': user.name or user.username,
                    'surname': user.surname or '',
                    'email': user.email or '',
                    'user_type': user.user_type,
                    'role_id': user.role_id,
                    'permissions': get_user_permission_codes(user.id, include_role_permissions=True)
                }
            }), 200
    
    except Exception as e:
        print(f"[API ME] Error general: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/auth/refresh-permissions', methods=['POST'])
@jwt_required()
def refresh_permissions():
    """
    Refrescar los permisos del usuario actual.
    Útil después de que un administrador modifica los permisos del usuario.

    Headers:
    Authorization: Bearer <access_token>

    Respuesta:
    {
        "success": true,
        "data": {
            "permissions": [...]
        }
    }
    """
    try:
        user_id = get_jwt_identity()

        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        user_type = claims.get('user_type', 'staff')

        if user_type == 'patient':
            return jsonify({
                'success': False,
                'message': 'Pacientes no tienen permisos configurables'
            }), 400

        permissions = get_user_permission_codes(user_id, include_role_permissions=True)

        return jsonify({
            'success': True,
            'data': {
                'permissions': permissions
            }
        }), 200

    except Exception as e:
        print(f"[API REFRESH PERMISSIONS] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refrescar access token usando refresh token
    
    Headers:
    Authorization: Bearer <refresh_token>
    
    Respuesta:
    {
        "success": true,
        "data": {
            "access_token": "..."
        }
    }
    """
    try:
        user_id = get_jwt_identity()
        
        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        
        additional_claims = {
            'user_type': claims.get('user_type', 'staff'),
            'username': claims.get('username', '')
        }
        
        access_token = create_access_token(
            identity=user_id,
            additional_claims=additional_claims
        )
        
        return jsonify({
            'success': True,
            'data': {
                'access_token': access_token
            }
        }), 200
    
    except Exception as e:
        print(f"[API REFRESH] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Logout (en el frontend se debe eliminar el token)
    
    Respuesta:
    {
        "success": true,
        "message": "Logout exitoso"
    }
    """
    return jsonify({
        'success': True,
        'message': 'Logout exitoso'
    }), 200


@api_blueprint.route('/auth/change-password', methods=['POST'])
@jwt_required()
def change_password_first_login():
    """
    Cambia contraseña del usuario autenticado y desactiva bandera de primer login.

    Body JSON:
    {
        "new_password": "string" (required, min 6)
    }
    """
    try:
        data = request.get_json(force=True, silent=True)
        new_password = (data or {}).get('new_password')

        if not new_password:
            return jsonify({
                'success': False,
                'message': 'new_password es requerido'
            }), 400

        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'message': 'La contraseña debe tener al menos 6 caracteres'
            }), 400

        user_id = get_jwt_identity()

        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        user_type = claims.get('user_type', 'staff')

        hashed_password = generate_password_hash(new_password)

        from apps.home.services import ConfigService

        db_config = ConfigService.get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        if user_type == 'patient':
            cursor.execute(
                """
                UPDATE nextris.tbuser_patient
                SET password = %s,
                    firstlogin = 0
                WHERE guid = %s
                """,
                (hashed_password, user_id)
            )
        else:
            cursor.execute(
                """
                UPDATE nextris.tbuser
                SET password = %s,
                    first_login = 0
                WHERE guid = %s
                """,
                (hashed_password, user_id)
            )

        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Contraseña actualizada exitosamente'
        }), 200

    except Exception as e:
        try:
            connection.rollback()
            cursor.close()
            connection.close()
        except Exception:
            pass
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
