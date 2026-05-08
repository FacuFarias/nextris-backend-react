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
from apps.api.facility_plan_usage import ensure_plan_management_schema


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


def _create_patient_domain_for_facility(connection, cursor, institution_name, facility_code):
    if not _table_exists(connection, 'nextris', 'ispatientdomain'):
        return None

    domain_columns = _get_table_columns(connection, 'nextris', 'ispatientdomain')
    if 'guid' not in domain_columns:
        return None

    domain_guid = str(uuid.uuid4())
    domain_data = {'guid': domain_guid}

    if 'description' in domain_columns:
        domain_data['description'] = institution_name
    if 'code' in domain_columns:
        domain_data['code'] = (facility_code or '').replace('-', '')[:8] or None
    if 'note' in domain_columns:
        domain_data['note'] = 'Dominio autogenerado por registro gratuito'

    _dynamic_insert(cursor, 'nextris', 'ispatientdomain', domain_data)
    return domain_guid


def _assign_user_patientdomain(connection, cursor, user_id, patientdomain_id):
    if not patientdomain_id:
        return
    if not _table_exists(connection, 'nextris', 'rel_user_patientdomain'):
        return

    rel_columns = _get_table_columns(connection, 'nextris', 'rel_user_patientdomain')
    if 'user_id' not in rel_columns or 'patientdomain_id' not in rel_columns:
        return

    cursor.execute(
        """
        DELETE FROM nextris.rel_user_patientdomain
        WHERE user_id = %s AND patientdomain_id = %s
        """,
        (user_id, patientdomain_id),
    )

    rel_data = {
        'user_id': user_id,
        'patientdomain_id': patientdomain_id,
    }
    if 'guid' in rel_columns:
        rel_data['guid'] = str(uuid.uuid4())
    if 'is_default' in rel_columns:
        rel_data['is_default'] = True

    _dynamic_insert(cursor, 'nextris', 'rel_user_patientdomain', rel_data)


def _institution_initials(name):
    tokens = [tok for tok in re.split(r'\s+', (name or '').strip()) if tok]
    if len(tokens) >= 2:
        return (tokens[0][0] + tokens[1][0]).upper()
    if len(tokens) == 1 and len(tokens[0]) >= 2:
        return tokens[0][:2].upper()
    if len(tokens) == 1:
        return (tokens[0][0] + 'X').upper()
    return 'IN'


def _next_facility_code(cursor, institution_name):
    initials = _institution_initials(institution_name)
    try:
        cursor.execute(
            """
            SELECT code
            FROM nextris.tbfacility
            WHERE code LIKE %s
            """,
            (f"{initials}-%",),
        )
        rows = cursor.fetchall()
    except Exception:
        return f"{initials}-001"

    max_seq = 0
    for row in rows:
        code = row[0] or ''
        if '-' not in code:
            continue
        tail = code.split('-', 1)[1]
        if tail.isdigit():
            max_seq = max(max_seq, int(tail))

    return f"{initials}-{max_seq + 1:03d}"


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


def _ensure_verification_table(connection):
    """Crea la tabla de verificaciones de email para el registro gratuito si no existe."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.tbfree_signup_verification (
                id SERIAL PRIMARY KEY,
                facility_id VARCHAR(50) NOT NULL,
                email VARCHAR(255) NOT NULL,
                code_hash VARCHAR(64) NOT NULL,
                attempts INTEGER DEFAULT 0,
                verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                verified_at TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tbfree_signup_verif_lookup
                ON nextris.tbfree_signup_verification(facility_id, email, verified)
            """
        )
        connection.commit()
    finally:
        cursor.close()


def _send_code_email(connection, to_email, code, facility_id=None):
    """Envía código de verificación de 6 dígitos al email indicado usando configuración SMTP disponible."""
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

    if connection and facility_id:
        try:
            cur = connection.cursor()
            cur.execute(
                """
                SELECT smtp_server, smtp_port, smtp_user, smtp_password,
                       smtp_from, smtp_from_name, use_tls
                FROM nextris.tbfacility
                WHERE guid = %s
                  AND COALESCE(TRIM(smtp_user), '') <> ''
                  AND COALESCE(TRIM(smtp_password), '') <> ''
                LIMIT 1
                """,
                (facility_id,),
            )
            row = cur.fetchone()
            cur.close()
            if row:
                smtp_server = row[0] or smtp_server
                smtp_port = _safe_port(row[1] or smtp_port, 587)
                smtp_user = row[2] or smtp_user
                smtp_password = row[3] or smtp_password
                smtp_from = row[4] or smtp_user or smtp_from
                smtp_from_name = row[5] or smtp_from_name
                if row[6] is not None:
                    use_tls = bool(row[6])
        except Exception:
            pass

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


def _get_user_primary_location_context(connection, user_id):
    """Obtiene la ubicación/facility principal del usuario para el flujo de verificación."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT l.facility_id, l.guid
            FROM nextris.rel_user_location rul
            INNER JOIN nextris.tblocation l ON l.guid = rul.location_id
            WHERE rul.user_id = %s
            ORDER BY COALESCE(rul.is_default, FALSE) DESC, l.guid
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None, None
        return row[0], row[1]
    finally:
        cursor.close()


def _user_requires_email_verification(connection, facility_id, email):
    """Determina si el usuario pertenece a una facility FREE y aún no verificó su email."""
    if not facility_id or not email:
        return False

    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT 1
            FROM nextris.tbfacility f
            INNER JOIN nextris.isplan p ON p.guid = f.plan_id
            WHERE f.guid = %s
              AND LOWER(COALESCE(p.code, '')) = 'free'
            LIMIT 1
            """,
            (facility_id,),
        )
        is_free_plan = cursor.fetchone() is not None
        if not is_free_plan:
            return False

        if not _table_exists(connection, 'nextris', 'tbfree_signup_verification'):
            return True

        cursor.execute(
            """
            SELECT 1
            FROM nextris.tbfree_signup_verification
            WHERE facility_id = %s
              AND email = %s
              AND verified = TRUE
            ORDER BY verified_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """,
            (facility_id, email.lower()),
        )
        return cursor.fetchone() is None
    finally:
        cursor.close()


@api_blueprint.route('/auth/free-signup/institution', methods=['POST'])
def free_signup_create_institution():
    """Crea institución+ubicación gratuita (paso 1)."""
    connection = None
    cursor = None
    try:
        institution_mode = str(request.form.get('institution_mode', '')).strip().lower()
        if institution_mode not in ('new', 'existing'):
            return jsonify({'success': False, 'message': 'institution_mode debe ser new o existing'}), 400

        if institution_mode == 'existing':
            return jsonify({
                'success': False,
                'message': 'Consulte la creacion de usuarios con el administrador de sistemas de su institución.'
            }), 400

        institution_name = str(request.form.get('name', '')).strip()
        institution_email = str(request.form.get('email', '')).strip()
        institution_address = str(request.form.get('address', '')).strip()
        institution_city = str(request.form.get('city', '')).strip()
        institution_country = str(request.form.get('country', '')).strip()
        institution_phone = str(request.form.get('phone', '')).strip()

        required_fields = [institution_name, institution_email, institution_address, institution_phone]
        if not all(required_fields):
            return jsonify({'success': False, 'message': 'Faltan datos requeridos de la institución'}), 400

        db_config = _get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        connection.autocommit = False
        ensure_plan_management_schema(connection)

        cursor = connection.cursor()

        cursor.execute("SELECT guid FROM nextris.isplan WHERE LOWER(code) = 'free' LIMIT 1")
        free_plan_row = cursor.fetchone()
        if not free_plan_row:
            return jsonify({'success': False, 'message': 'No se encontró el plan FREE en el sistema'}), 500
        free_plan_id = free_plan_row[0]

        facility_guid = str(uuid.uuid4())
        facility_code = _next_facility_code(cursor, institution_name)
        patientdomain_id = _create_patient_domain_for_facility(
            connection,
            cursor,
            institution_name,
            facility_code,
        )

        facility_columns = _get_table_columns(connection, 'nextris', 'tbfacility')
        if 'guid' not in facility_columns:
            return jsonify({'success': False, 'message': 'Esquema no soportado: tbfacility.guid no existe'}), 500

        facility_data = {'guid': facility_guid}
        if 'name' in facility_columns:
            facility_data['name'] = institution_name
        if 'code' in facility_columns:
            facility_data['code'] = facility_code
        if 'email' in facility_columns:
            facility_data['email'] = institution_email
        if 'contact_person' in facility_columns:
            facility_data['contact_person'] = ''
        if 'description' in facility_columns:
            facility_data['description'] = institution_name
        if 'address' in facility_columns:
            facility_data['address'] = institution_address
        if 'city' in facility_columns:
            facility_data['city'] = institution_city
        if 'country' in facility_columns:
            facility_data['country'] = institution_country
        if 'phone' in facility_columns:
            facility_data['phone'] = institution_phone
        if 'status' in facility_columns:
            facility_data['status'] = 'Active'
        if 'plan_id' in facility_columns:
            facility_data['plan_id'] = free_plan_id
        if patientdomain_id and 'id_patientdomain' in facility_columns:
            facility_data['id_patientdomain'] = patientdomain_id

        _dynamic_insert(cursor, 'nextris', 'tbfacility', facility_data)

        logo_file = request.files.get('logo')
        logo_filename = None
        if logo_file and logo_file.filename:
            logo_filename = _save_uploaded_image(
                logo_file,
                prefix='institution_logo',
                max_bytes=2 * 1024 * 1024,
                subfolder=os.path.join('apps', 'static', 'assets', 'img', 'location_logos'),
            )

        location_guid = str(uuid.uuid4())
        location_code = f"{facility_code}-LOC"

        location_columns = _get_table_columns(connection, 'nextris', 'tblocation')
        if 'guid' not in location_columns:
            return jsonify({'success': False, 'message': 'Esquema no soportado: tblocation.guid no existe'}), 500
        if 'facility_id' not in location_columns:
            return jsonify({'success': False, 'message': 'Esquema no soportado: tblocation.facility_id no existe'}), 500

        location_data = {
            'guid': location_guid,
            'facility_id': facility_guid,
        }
        if 'name' in location_columns:
            location_data['name'] = institution_name
        if 'code' in location_columns:
            location_data['code'] = location_code
        if 'address' in location_columns:
            location_data['address'] = institution_address
        if 'phone' in location_columns:
            location_data['phone'] = institution_phone
        if 'status' in location_columns:
            location_data['status'] = 'Active'
        if 'id_patientdomain' in location_columns:
            location_data['id_patientdomain'] = patientdomain_id
        if 'mail' in location_columns:
            location_data['mail'] = institution_email
        if 'logo_path' in location_columns:
            location_data['logo_path'] = logo_filename
        if 'require_execution_before_reporting' in location_columns:
            location_data['require_execution_before_reporting'] = True
        if 'retention_days' in location_columns:
            location_data['retention_days'] = 30

        _dynamic_insert(cursor, 'nextris', 'tblocation', location_data)

        connection.commit()

        return jsonify({
            'success': True,
            'message': 'Institución gratuita creada exitosamente',
            'data': {
                'facility_id': facility_guid,
                'location_id': location_guid,
                'facility_code': facility_code,
                'plan_code': 'free',
                'patientdomain_id': patientdomain_id,
            }
        }), 201
    except ValueError as e:
        if connection:
            connection.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        if connection:
            try:
                connection.rollback()
            except Exception:
                pass
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if connection:
            try:
                connection.close()
            except Exception:
                pass


@api_blueprint.route('/auth/free-signup/medical-user', methods=['POST'])
def free_signup_create_medical_user():
    """Crea usuario médico para institución ya creada (paso 2)."""
    connection = None
    cursor = None
    try:
        facility_id = str(request.form.get('facility_id', '')).strip()
        location_id = str(request.form.get('location_id', '')).strip()
        username = str(request.form.get('username', '')).strip()
        password = str(request.form.get('password', '')).strip()
        email = str(request.form.get('email', '')).strip()
        name = str(request.form.get('name', '')).strip()
        surname = str(request.form.get('surname', '')).strip()
        national_number = str(request.form.get('national_number', '')).strip()
        aclaracion_firma = str(request.form.get('aclaracion_firma', '')).strip()
        matricula_nacional = str(request.form.get('matricula_nacional', '')).strip()

        required_fields = [facility_id, location_id, username, password, email, name, surname, aclaracion_firma, matricula_nacional]
        if not all(required_fields):
            return jsonify({'success': False, 'message': 'Faltan datos requeridos del usuario médico'}), 400

        if len(password) < 6:
            return jsonify({'success': False, 'message': 'La contraseña debe tener al menos 6 caracteres'}), 400

        db_config = _get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        connection.autocommit = False
        _ensure_user_medical_table(connection)
        _ensure_verification_table(connection)
        cursor = connection.cursor()

        cursor.execute("SELECT name FROM nextris.tbfacility WHERE guid = %s LIMIT 1", (facility_id,))
        facility_row = cursor.fetchone()
        if not facility_row:
            return jsonify({'success': False, 'message': 'La institución indicada no existe'}), 404

        cursor.execute(
            "SELECT 1 FROM nextris.tblocation WHERE guid = %s AND facility_id = %s LIMIT 1",
            (location_id, facility_id),
        )
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': 'La ubicación indicada no pertenece a la institución'}), 400

        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'El nombre de usuario ya existe'}), 400

        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE mail = %s", (email,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': 'El email ya está asociado a un usuario'}), 400

        cursor.execute(
            """
            SELECT guid, description
            FROM nextris.isrole
            WHERE LOWER(COALESCE(description, '')) LIKE '%medic%'
            ORDER BY description
            LIMIT 1
            """
        )
        role_row = cursor.fetchone()
        if not role_row:
            return jsonify({'success': False, 'message': 'No se encontró un rol médico en la configuración'}), 500
        medico_role_id = role_row[0]
        medico_role_description = role_row[1] or 'Medico'

        user_guid = str(uuid.uuid4())
        password_hash = generate_password_hash(password)
        cursor.execute(
            """
            INSERT INTO nextris.tbuser (
                guid, username, mail, password, name, surname,
                nationalnumber, idrole, isactive, first_login
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, 0)
            """,
            (
                user_guid,
                username,
                email,
                password_hash,
                name,
                surname,
                national_number,
                medico_role_id,
            ),
        )

        cursor.execute(
            """
            INSERT INTO nextris.rel_user_location (user_id, location_id, is_default)
            VALUES (%s, %s, %s)
            """,
            (user_guid, location_id, True),
        )

        patientdomain_id = None
        if _column_exists(connection, 'nextris', 'tbfacility', 'id_patientdomain'):
            cursor.execute(
                "SELECT id_patientdomain FROM nextris.tbfacility WHERE guid = %s LIMIT 1",
                (facility_id,),
            )
            row = cursor.fetchone()
            patientdomain_id = (row[0] if row else None) or None

        if not patientdomain_id and _column_exists(connection, 'nextris', 'tblocation', 'id_patientdomain'):
            cursor.execute(
                "SELECT id_patientdomain FROM nextris.tblocation WHERE guid = %s LIMIT 1",
                (location_id,),
            )
            row = cursor.fetchone()
            patientdomain_id = (row[0] if row else None) or None

        _assign_user_patientdomain(connection, cursor, user_guid, patientdomain_id)

        default_permission_codes = [
            code for code in get_default_permissions_for_role(medico_role_description)
            if code and code != '*'
        ]
        if default_permission_codes:
            replace_user_permissions(user_guid, default_permission_codes, connection=connection)

        signature_file = request.files.get('signature')
        signature_filename = None
        if signature_file and signature_file.filename:
            signature_filename = _save_uploaded_image(
                signature_file,
                prefix='signature',
                max_bytes=1 * 1024 * 1024,
                subfolder=os.path.join('media', 'firmas'),
            )

        cursor.execute(
            """
            INSERT INTO nextris.tbuser_medical_data
                (user_id, aclaracion_firma, matricula_nacional, firma_digital, firma_habilitada, fecha_creacion, fecha_actualizacion)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (user_guid, aclaracion_firma, matricula_nacional, signature_filename, True),
        )

        contact_person = f"{name} {surname}".strip()
        cursor.execute(
            """
            UPDATE nextris.tbfacility
            SET contact_person = %s
            WHERE guid = %s
            """,
            (contact_person, facility_id),
        )

        connection.commit()

        return jsonify({
            'success': True,
            'message': 'Usuario médico creado exitosamente. Ya puede iniciar sesión.',
            'data': {
                'user_id': user_guid,
                'facility_id': facility_id,
                'location_id': location_id,
                'patientdomain_id': patientdomain_id,
                'role': 'Medico',
            }
        }), 201
    except ValueError as e:
        if connection:
            connection.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        if connection:
            try:
                connection.rollback()
            except Exception:
                pass
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if connection:
            try:
                connection.close()
            except Exception:
                pass


@api_blueprint.route('/auth/free-signup/send-verification', methods=['POST'])
def free_signup_send_verification():
    """Genera y envía un código de 6 dígitos al email del usuario médico en proceso de registro gratuito."""
    connection = None
    try:
        facility_id = str(request.form.get('facility_id', '')).strip()
        email = str(request.form.get('email', '')).strip().lower()

        if not facility_id or not email:
            return jsonify({'success': False, 'message': 'Faltan datos requeridos'}), 400

        email_re = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
        if not email_re.match(email):
            return jsonify({'success': False, 'message': 'El formato del email no es válido'}), 400

        db_config = _get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        connection.autocommit = False
        _ensure_verification_table(connection)
        cursor = connection.cursor()

        cursor.execute("SELECT guid FROM nextris.tbfacility WHERE guid = %s LIMIT 1", (facility_id,))
        if not cursor.fetchone():
            cursor.close()
            return jsonify({'success': False, 'message': 'La institución indicada no existe'}), 404

        # Rate limiting: máximo 3 envíos en los últimos 30 minutos por facility+email
        cursor.execute(
            """
            SELECT COUNT(*) FROM nextris.tbfree_signup_verification
            WHERE facility_id = %s AND email = %s
              AND created_at > NOW() - INTERVAL '30 minutes'
            """,
            (facility_id, email),
        )
        if cursor.fetchone()[0] >= 3:
            cursor.close()
            return jsonify({
                'success': False,
                'message': 'Demasiados intentos de envío. Espere 30 minutos antes de solicitar un nuevo código.',
            }), 429

        code = str(secrets.randbelow(900000) + 100000)
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(minutes=30)

        cursor.execute(
            """
            INSERT INTO nextris.tbfree_signup_verification
                (facility_id, email, code_hash, attempts, verified, created_at, expires_at)
            VALUES (%s, %s, %s, 0, FALSE, NOW(), %s)
            """,
            (facility_id, email, code_hash, expires_at),
        )

        # Enviamos el email ANTES del commit; si falla, el rollback revierte el INSERT
        _send_code_email(connection, email, code, facility_id=facility_id)

        connection.commit()
        cursor.close()

        return jsonify({
            'success': True,
            'message': f'Código enviado a {email}. Válido por 30 minutos.',
        }), 200

    except RuntimeError as e:
        if connection:
            try:
                connection.rollback()
            except Exception:
                pass
        return jsonify({'success': False, 'message': str(e)}), 500
    except Exception as e:
        if connection:
            try:
                connection.rollback()
            except Exception:
                pass
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        if connection:
            try:
                connection.close()
            except Exception:
                pass


@api_blueprint.route('/auth/free-signup/verify-code', methods=['POST'])
def free_signup_verify_code():
    """Valida el código de 6 dígitos enviado al email del usuario médico."""
    connection = None
    try:
        facility_id = str(request.form.get('facility_id', '')).strip()
        email = str(request.form.get('email', '')).strip().lower()
        code = str(request.form.get('code', '')).strip()

        if not facility_id or not email or not code:
            return jsonify({'success': False, 'message': 'Faltan datos requeridos'}), 400

        db_config = _get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración de base de datos'}), 500

        connection = psycopg2.connect(**db_config)
        connection.autocommit = False
        _ensure_verification_table(connection)
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id, code_hash, attempts, expires_at
            FROM nextris.tbfree_signup_verification
            WHERE facility_id = %s AND email = %s AND verified = FALSE
            ORDER BY created_at DESC
            """,
            (facility_id, email),
        )
        rows = cursor.fetchall()
        if not rows:
            cursor.close()
            return jsonify({
                'success': False,
                'message': 'No se encontró un código activo. Solicite uno nuevo.',
            }), 404

        from datetime import timezone
        latest_id, _latest_hash, latest_attempts, latest_expires_at = rows[0]
        now_utc = datetime.now(timezone.utc) if latest_expires_at.tzinfo else datetime.utcnow()

        active_rows = [row for row in rows if now_utc <= row[3]]
        if not active_rows:
            cursor.close()
            return jsonify({
                'success': False,
                'message': 'El código ha expirado. Solicite uno nuevo.',
                'expired': True,
            }), 400

        if latest_attempts >= 5:
            cursor.close()
            return jsonify({
                'success': False,
                'message': 'Demasiados intentos incorrectos. Solicite un nuevo código.',
                'max_attempts': True,
            }), 400

        input_hash = hashlib.sha256(code.encode()).hexdigest()
        matched_id = None
        for rec_id, stored_hash, _attempts, _expires_at in active_rows:
            if input_hash == stored_hash:
                matched_id = rec_id
                break

        if not matched_id:
            cursor.execute(
                "UPDATE nextris.tbfree_signup_verification SET attempts = attempts + 1 WHERE id = %s",
                (latest_id,),
            )
            connection.commit()
            remaining = max(0, 4 - latest_attempts)
            cursor.close()
            return jsonify({
                'success': False,
                'message': f'Código incorrecto. Intentos restantes: {remaining}.',
                'remaining_attempts': remaining,
            }), 400

        cursor.execute(
            """
            UPDATE nextris.tbfree_signup_verification
            SET verified = TRUE, verified_at = NOW()
            WHERE facility_id = %s AND email = %s AND verified = FALSE
            """,
            (facility_id, email),
        )
        connection.commit()
        cursor.close()

        return jsonify({'success': True, 'message': 'Email verificado correctamente.'}), 200

    except Exception as e:
        if connection:
            try:
                connection.rollback()
            except Exception:
                pass
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        if connection:
            try:
                connection.close()
            except Exception:
                pass


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
            # Autenticación de paciente
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
                
                # Buscar paciente
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
                
                # Verificar contraseña
                if not check_password_hash(db_password, password):
                    return jsonify({
                        'success': False,
                        'message': 'Credenciales inválidas'
                    }), 401
                
                # Verificar que esté activo
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
            # Autenticación de staff
            user = Users.query.filter_by(username=username, is_active=1).first()
            
            if not user or not check_password_hash(user.password, password):
                return jsonify({
                    'success': False,
                    'message': 'Credenciales inválidas'
                }), 401
            
            facility_id = None
            location_id = None
            email_verification_required = False

            db_config = _get_db_config()
            if db_config:
                connection = psycopg2.connect(**db_config)
                try:
                    facility_id, location_id = _get_user_primary_location_context(connection, user.id)
                    email_verification_required = _user_requires_email_verification(
                        connection,
                        facility_id,
                        user.email or '',
                    )
                finally:
                    connection.close()

            user_data = {
                'id': user.id,
                'username': user.username,
                'name': user.name or user.username,
                'surname': user.surname or '',
                'email': user.email or '',
                'user_type': user.user_type,
                'role_id': user.role_id,
                'role_name': (user.user_type or '').lower(),
                'facility_id': facility_id,
                'location_id': location_id,
                'email_verification_required': email_verification_required,
                'email_verified': not email_verification_required,
                'permissions': get_user_permission_codes(user.id, include_role_permissions=False),
                'requires_password_change': bool(user.first_login)
            }
        
        # Crear tokens JWT
        # Incluir información adicional en el token (user_type)
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
        
        # Obtener claims adicionales del token
        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        user_type = claims.get('user_type', 'staff')
        
        if user_type == 'patient':
            # Buscar paciente
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
            # Buscar staff
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
                    'permissions': get_user_permission_codes(user.id, include_role_permissions=False)
                }
            }), 200
    
    except Exception as e:
        print(f"[API ME] Error general: {str(e)}")
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
        
        # Obtener claims del refresh token
        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        
        # Crear nuevo access token con los mismos claims
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
    # En JWT stateless no necesitamos hacer nada en el servidor
    # El frontend debe eliminar el token del localStorage
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


@api_blueprint.route('/auth/user/<user_id>/patientdomains', methods=['GET'])
@jwt_required()
def get_user_patientdomains(user_id):
    """
    Obtener los patientdomains asociados a un usuario
    
    Respuesta:
    {
        "success": true,
        "data": [
            {
                "patientdomain_id": "uuid",
                "patientdomain_name": "GENERAL",
                "created_at": "2024-01-01 10:00:00"
            }
        ]
    }
    """
    try:
        from apps.home.services import ConfigService
        db_config = ConfigService.get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener las relaciones con información del patientdomain
        query = """
            SELECT 
                rup.patientdomain_id,
                pd.description as patientdomain_name,
                rup.created_at
            FROM nextris.rel_user_patientdomain rup
            LEFT JOIN nextris.ispatientdomain pd ON pd.guid = rup.patientdomain_id
            WHERE rup.user_id = %s
            ORDER BY pd.description
        """
        
        cursor.execute(query, (user_id,))
        results = cursor.fetchall()
        
        patientdomains = []
        for row in results:
            patientdomains.append({
                'patientdomain_id': row[0],
                'patientdomain_name': row[1] or 'Sin nombre',
                'created_at': row[2].isoformat() if row[2] else None
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': patientdomains
        }), 200
        
    except Exception as e:
        print(f"[API USER PATIENTDOMAINS] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
