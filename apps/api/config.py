# -*- encoding: utf-8 -*-
"""
API REST para Configuración del Sistema
Endpoints para gestión de configuraciones, tipos de estudio, equipos, ubicaciones, etc.
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import psycopg2
from apps.api import api_blueprint
from apps.api.permissions import (
    ensure_permissions_schema,
    seed_permissions,
    get_permission_catalog,
    get_user_permission_codes,
    get_default_permissions_for_role,
    replace_user_permissions,
    normalize_permission_codes,
    require_permission,
)
import uuid
import os
import smtplib
import secrets
import string
import hashlib
import json
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from PIL import Image
from apps.api.facility_plan_usage import (
    ensure_plan_management_schema,
    get_global_plan_snapshot,
    append_plan_change_audit,
)
from apps.home.services.app_config_service import (
    ensure_app_config_table,
    get_app_config,
    update_app_config,
    get_app_modules,
    update_app_module,
)


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.routes import config
        return config
    except:
        return None


def normalize_user_id(identity):
    if isinstance(identity, dict):
        return identity.get('id') or identity.get('guid') or identity.get('user_id')
    return identity


def _get_default_smtp_settings():
    """Resolve default SMTP settings from environment variables.

    Resend defaults are used when SMTP-specific env vars are not defined.
    """
    smtp_password = os.environ.get('SMTP_PASSWORD') or os.environ.get('RESEND_API_KEY')
    smtp_from = os.environ.get('SMTP_FROM') or os.environ.get('RESEND_FROM_EMAIL') or 'no-reply@nextris.cloud'
    smtp_from_name = os.environ.get('SMTP_FROM_NAME') or os.environ.get('RESEND_FROM_NAME') or 'NextRIS'

    return {
        'smtp_server': os.environ.get('SMTP_SERVER', 'smtp.resend.com'),
        'smtp_port': int(os.environ.get('SMTP_PORT', '587')),
        'smtp_user': os.environ.get('SMTP_USER', 'resend'),
        'smtp_password': smtp_password,
        'smtp_from': smtp_from,
        'smtp_from_name': smtp_from_name,
        'use_tls': os.environ.get('SMTP_USE_TLS', 'true').strip().lower() in ('1', 'true', 'yes', 'on'),
    }


def _column_exists(connection, schema_name, table_name, column_name):
    """Check if a column exists to keep API compatible across schema versions."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s AND column_name = %s
            LIMIT 1
            """,
            (schema_name, table_name, column_name),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def _table_exists(connection, schema_name, table_name):
    """Check if a table exists before using it in joins."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
            LIMIT 1
            """,
            (schema_name, table_name),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def ensure_location_status_column(connection):
    """Ensure tblocation has status column and initialize legacy rows as Active."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            ALTER TABLE nextris.tblocation
            ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'Active'
            """
        )
        cursor.execute(
            """
            UPDATE nextris.tblocation
            SET status = 'Active'
            WHERE status IS NULL OR BTRIM(status) = ''
            """
        )
        connection.commit()
    finally:
        cursor.close()


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


def parse_bool_value(value, default=None):
    """Parse bool values sent as bool/int/string from JSON or multipart payloads."""
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


def _normalize_active_status(value, default='Active'):
    normalized = str(value if value is not None else default).strip().lower()
    return 'Inactive' if normalized == 'inactive' else 'Active'


def _process_location_logo(logo_file, location_id):
    """Procesa y guarda el logo de una location y devuelve la ruta relativa."""
    try:
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
        safe_name = secure_filename(logo_file.filename or '')
        ext = os.path.splitext(safe_name)[1].lower()

        if ext not in allowed_extensions:
            return None

        logo_dir = os.path.join('apps', 'static', 'assets', 'img', 'location_logos')
        os.makedirs(logo_dir, exist_ok=True)

        logo_filename = f"location_{location_id}{ext}"
        logo_full_path = os.path.join(logo_dir, logo_filename)

        img = Image.open(logo_file)

        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        size = (200, 200)
        canvas = Image.new('RGBA', size, (255, 255, 255, 0))
        ratio = min(size[0] / img.width, size[1] / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

        paste_pos = ((size[0] - new_size[0]) // 2, (size[1] - new_size[1]) // 2)
        canvas.paste(img, paste_pos)

        if ext in ['.jpg', '.jpeg']:
            rgb_img = Image.new('RGB', size, (255, 255, 255))
            rgb_img.paste(canvas, mask=canvas.split()[3])
            rgb_img.save(logo_full_path, quality=95)
        else:
            canvas.save(logo_full_path)

        return logo_full_path.replace('\\', '/')
    except Exception:
        return None


def _get_signature_upload_dir():
    """Build an absolute upload path for user signatures under project media/firmas."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    return os.path.join(project_root, 'media', 'firmas')


def ensure_user_medical_table(connection):
    """Ensure tbuser_medical_data exists."""
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS nextris.tbuser_medical_data (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL UNIQUE,
            aclaracion_firma VARCHAR(255) NOT NULL,
            matricula_nacional VARCHAR(100) NOT NULL,
            firma_digital VARCHAR(500),
            firma_habilitada BOOLEAN DEFAULT FALSE,
            fecha_creacion TIMESTAMP DEFAULT NOW(),
            fecha_actualizacion TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES nextris.tbuser(guid) ON DELETE CASCADE
        );
        """
    )
    connection.commit()
    cursor.close()


def generate_temporary_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


DEFAULT_OPTIONAL_MODULES = [
    {
        'code': 'appointments',
        'name': 'Citas',
        'description': 'Creacion de citas, admision por cita, agendas por medico o maquina.',
    },
    # structured_reports — deshabilitado temporalmente
    # {
    #     'code': 'structured_reports',
    #     'name': 'Reportes estructurados',
    #     'description': 'Parsers, mapeo de variables, conceptos y criterios, plantillas inteligentes.',
    # },
    # nexi — deshabilitado temporalmente
    # {
    #     'code': 'nexi',
    #     'name': 'Nexi',
    #     'description': 'Asistente Nexi y sus vistas de interaccion.',
    # },
    {
        'code': 'patient_portal',
        'name': 'Portal de pacientes',
        'description': 'Acceso para pacientes a sus estudios y reportes.',
    },
]


def _build_module_change_hash(prev_hash, payload_dict):
    """Build a deterministic SHA-256 hash for tamper-evident audit records."""
    envelope = {
        'prev_hash': prev_hash or '',
        **payload_dict,
    }
    serialized = json.dumps(envelope, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def ensure_facility_module_tables(connection):
    """Ensure module catalog and facility-module relation tables exist and are seeded."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.ismodule (
                guid VARCHAR(50) PRIMARY KEY,
                code VARCHAR(50) NOT NULL UNIQUE,
                name VARCHAR(120) NOT NULL,
                description TEXT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.rel_facility_module (
                guid VARCHAR(50) PRIMARY KEY,
                facility_id VARCHAR(50) NOT NULL,
                module_id VARCHAR(50) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_rel_facility_module UNIQUE (facility_id, module_id),
                CONSTRAINT fk_rel_facility_module_module
                    FOREIGN KEY (module_id) REFERENCES nextris.ismodule(guid) ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.audit_facility_module_change (
                id BIGSERIAL PRIMARY KEY,
                guid VARCHAR(50) NOT NULL UNIQUE,
                facility_id VARCHAR(50) NOT NULL,
                module_id VARCHAR(50) NOT NULL,
                module_code VARCHAR(50) NOT NULL,
                action VARCHAR(20) NOT NULL,
                previous_is_active BOOLEAN NOT NULL,
                new_is_active BOOLEAN NOT NULL,
                changed_by_user_id VARCHAR(50) NOT NULL,
                changed_by_username VARCHAR(150),
                changed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                reason TEXT,
                request_ip VARCHAR(64),
                user_agent TEXT,
                prev_hash VARCHAR(64),
                row_hash VARCHAR(64) NOT NULL,
                CONSTRAINT fk_audit_facility_module_change_module
                    FOREIGN KEY (module_id) REFERENCES nextris.ismodule(guid),
                CONSTRAINT ck_audit_facility_module_change_action
                    CHECK (action IN ('enabled', 'disabled'))
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_facility_module_change_facility_changed_at
            ON nextris.audit_facility_module_change (facility_id, changed_at DESC)
            """
        )

        cursor.execute(
            """
            CREATE OR REPLACE FUNCTION nextris.prevent_audit_facility_module_change_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'audit_facility_module_change es append-only y no permite UPDATE/DELETE';
            END;
            $$
            """
        )

        cursor.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_trigger
                    WHERE tgname = 'trg_prevent_audit_facility_module_change_mutation'
                ) THEN
                    CREATE TRIGGER trg_prevent_audit_facility_module_change_mutation
                    BEFORE UPDATE OR DELETE ON nextris.audit_facility_module_change
                    FOR EACH ROW
                    EXECUTE FUNCTION nextris.prevent_audit_facility_module_change_mutation();
                END IF;
            END $$;
            """
        )

        cursor.executemany(
            """
            INSERT INTO nextris.ismodule (guid, code, name, description, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                updated_at = NOW()
            """,
            [
                (str(uuid.uuid4()), module['code'], module['name'], module['description'])
                for module in DEFAULT_OPTIONAL_MODULES
            ],
        )

        connection.commit()
    finally:
        cursor.close()


def send_new_user_credentials_email(connection, email, username, temporary_password, full_name):
    default_smtp = _get_default_smtp_settings()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT smtp_server, smtp_port, smtp_user, smtp_password, smtp_from, smtp_from_name, use_tls
        FROM nextris.app_config
        WHERE id = 1
        """
    )
    smtp_result = cursor.fetchone()
    cursor.close()

    smtp_server = (smtp_result[0] if smtp_result else None) or default_smtp['smtp_server']
    smtp_port = (smtp_result[1] if smtp_result else None) or default_smtp['smtp_port']
    smtp_user = (smtp_result[2] if smtp_result else None) or default_smtp['smtp_user']
    smtp_password = (smtp_result[3] if smtp_result else None) or default_smtp['smtp_password']
    smtp_from = (smtp_result[4] if smtp_result else None) or default_smtp['smtp_from'] or smtp_user
    smtp_from_name = (smtp_result[5] if smtp_result else None) or default_smtp['smtp_from_name']
    use_tls = (smtp_result[6] if smtp_result and smtp_result[6] is not None else default_smtp['use_tls'])

    if not smtp_user or not smtp_password:
        raise Exception('Configuración SMTP incompleta para enviar credenciales')

    msg = MIMEMultipart()
    msg['From'] = f"{smtp_from_name} <{smtp_from}>"
    msg['To'] = email
    msg['Subject'] = 'Credenciales de acceso - NextRIS'

    body = f"""
Hola {full_name},

Tu usuario fue creado correctamente en NextRIS.

Usuario: {username}
Contraseña temporal: {temporary_password}

Por seguridad, en tu primer inicio de sesión deberás cambiar esta contraseña.

Este es un mensaje automático, por favor no responder.
"""

    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP(smtp_server, smtp_port)
    if use_tls:
        server.starttls()
    server.login(smtp_user, smtp_password)
    server.sendmail(smtp_from, email, msg.as_string())
    server.quit()


# ====================================================================
# CONFIGURACIÓN DEL SISTEMA
# ====================================================================

@api_blueprint.route('/config/system', methods=['GET'])
@jwt_required()
def get_system_config():
    """
    Obtiene la configuración general del sistema
    
    Returns:
    {
        "success": true,
        "data": {
            "config_key": "config_value"
        }
    }
    """
    try:
        # Importar ConfigService
        from apps.home.services import ConfigService
        config_data = ConfigService.get_all_config()
        
        return jsonify({
            'success': True,
            'message': 'Ubicación desasociada exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/system', methods=['PUT', 'PATCH'])
@jwt_required()
def update_system_config():
    """
    Actualiza la configuración del sistema
    
    Body JSON:
    {
        "config_key": "new_value",
        ...
    }
    
    Returns:
    {
        "success": true,
        "message": "Configuración actualizada",
        "data": {...}
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        from apps.home.services import ConfigService
        updated_config = ConfigService.update_config(data)
        
        return jsonify({
            'success': True,
            'message': 'Configuración actualizada exitosamente',
            'data': updated_config
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/workflow', methods=['GET', 'PUT'])
@jwt_required()
def workflow_config():
    """
    Obtiene o actualiza la configuración de workflow para el envío diferido
    de reportes firmados a Clínica Parque.
    
    Returns:
    {
        "success": true,
        "data": {
            "report_send_delay_minutes": 15
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
        ensure_app_config_table(connection)

        if request.method == 'PUT':
            payload = request.get_json(silent=True) or {}
            raw_delay = payload.get('report_send_delay_minutes')
            if isinstance(raw_delay, bool) or not isinstance(raw_delay, int):
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'El retardo debe ser un número entero'}), 400
            delay_minutes = raw_delay
            if delay_minutes < 0 or delay_minutes > 1440:
                cursor.close()
                connection.close()
                return jsonify({'success': False, 'message': 'El retardo debe estar entre 0 y 1440 minutos'}), 400

            cursor.execute(
                """
                UPDATE nextris.app_config
                SET report_send_delay_minutes = %s, updated_at = NOW()
                WHERE id = 1
                """,
                (delay_minutes,),
            )
            connection.commit()

        cursor.execute(
            """
            SELECT COALESCE(report_send_delay_minutes, 15)
            FROM nextris.app_config
            WHERE id = 1
            """
        )
        result = cursor.fetchone()
        delay_minutes = int(result[0]) if result else 15

        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'data': {'report_send_delay_minutes': delay_minutes},
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# TIPOS DE ESTUDIO
# ====================================================================

@api_blueprint.route('/config/study-types', methods=['GET'])
@jwt_required()
def get_study_types_config():
    """
    Obtiene todos los tipos de estudio con sus relaciones
    
    Query Parameters:
    - modality_id (OPCIONAL): Filtrar tipos de estudio por modalidad (GUID)
    - modality_code (OPCIONAL): Filtrar tipos de estudio por código externo de modalidad (ej: CT, RX, US)
    - bodypart_id (OPCIONAL): Filtrar tipos de estudio por parte del cuerpo
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "code": "...",
                "description": "...",
                "studygroup": "...",
                "bodypart": "...",
                "modality": "...",
                "rvu": 0,
                "nofviews": 0
            }
        ]
    }
    """
    try:
        # Obtener parámetros opcionales
        modality_id = request.args.get('modality_id')
        modality_code = request.args.get('modality_code')
        bodypart_id = request.args.get('bodypart_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Construir query base
        query = """
            SELECT st.guid, st.code, st.description, stg.description as studygroup, 
                   ap.description as bodypart, md.externalcode as modality, 
                   st.rvu, st.nofviews
            FROM nextris.isstudytype as st
            LEFT JOIN nextris.isstudytypegroup stg on stg.guid=st.studygroup_id
            LEFT JOIN nextris.isanatomicalpart ap on ap.guid=st.bodypart_id
            LEFT JOIN nextris.ismodality md on md.guid=st.modality_id
            WHERE 1=1
        """
        
        params = []
        
        # Agregar filtro de modalidad por GUID si se proporciona
        if modality_id:
            query += " AND st.modality_id = %s"
            params.append(modality_id)
        
        # Agregar filtro de modalidad por código externo (DICOM) si se proporciona
        if modality_code:
            # DX, CR y RX son variantes de radiografía — mostrar los mismos tipos de estudio
            xray_modalities = {'DX', 'CR', 'RX'}
            if modality_code.upper() in xray_modalities:
                placeholders = ','.join(['%s'] * len(xray_modalities))
                query += f" AND md.externalcode IN ({placeholders})"
                params.extend(sorted(xray_modalities))
            else:
                query += " AND md.externalcode = %s"
                params.append(modality_code.upper())
        
        # Agregar filtro de parte del cuerpo si se proporciona
        if bodypart_id:
            query += " AND st.bodypart_id = %s"
            params.append(bodypart_id)
        
        query += " ORDER BY st.description ASC"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        study_types = []
        for row in results:
            study_types.append({
                'guid': row[0],
                'code': row[1],
                'description': row[2],
                'studygroup': row[3],
                'bodypart': row[4],
                'modality': row[5],
                'rvu': row[6],
                'nofviews': row[7]
            })
        
        return jsonify({
            'success': True,
            'data': study_types
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-types', methods=['POST'])
@jwt_required()
def create_study_type():
    """
    Crea un nuevo tipo de estudio
    
    Body JSON:
    {
        "code": "string" (required),
        "description": "string" (required),
        "studygroup_id": "uuid" (required),
        "bodypart_id": "uuid" (required),
        "modality_id": "uuid" (required),
        "rvu": number (optional),
        "nofviews": number (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Tipo de estudio creado",
        "data": {
            "study_type_id": "uuid"
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
        
        code = data.get('code')
        description = data.get('description')
        studygroup_id = data.get('studygroup_id')
        bodypart_id = data.get('bodypart_id')
        modality_id = data.get('modality_id')
        
        if not all([code, description, studygroup_id, bodypart_id, modality_id]):
            return jsonify({
                'success': False,
                'message': 'code, description, studygroup_id, bodypart_id y modality_id son requeridos'
            }), 400
        
        rvu = data.get('rvu')
        nofviews = data.get('nofviews')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isstudytype(
                guid, code, description, studygroup_id, bodypart_id, modality_id, rvu, nofviews
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            new_guid, code, description, studygroup_id, bodypart_id, modality_id, rvu, nofviews
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Tipo de estudio creado exitosamente',
            'data': {
                'study_type_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-types/<study_type_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_study_type(study_type_id):
    """
    Actualiza un tipo de estudio existente
    
    Path:
    - study_type_id: GUID del tipo de estudio
    
    Body JSON (todos opcionales):
    {
        "code": "string",
        "description": "string",
        "studygroup_id": "uuid",
        "bodypart_id": "uuid",
        "modality_id": "uuid",
        "rvu": number,
        "nofviews": number
    }
    
    Returns:
    {
        "success": true,
        "message": "Tipo de estudio actualizado"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isstudytype WHERE guid=%s", (study_type_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Tipo de estudio no encontrado'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'code' in data:
            updates.append("code = %s")
            params.append(data['code'])
        if 'description' in data:
            updates.append("description = %s")
            params.append(data['description'])
        if 'studygroup_id' in data:
            updates.append("studygroup_id = %s")
            params.append(data['studygroup_id'])
        if 'bodypart_id' in data:
            updates.append("bodypart_id = %s")
            params.append(data['bodypart_id'])
        if 'modality_id' in data:
            updates.append("modality_id = %s")
            params.append(data['modality_id'])
        if 'rvu' in data:
            updates.append("rvu = %s")
            params.append(data['rvu'])
        if 'nofviews' in data:
            updates.append("nofviews = %s")
            params.append(data['nofviews'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(study_type_id)
        query = f"UPDATE nextris.isstudytype SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Tipo de estudio actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-types/<study_type_id>', methods=['DELETE'])
@jwt_required()
def delete_study_type(study_type_id):
    """
    Elimina un tipo de estudio
    
    Path:
    - study_type_id: GUID del tipo de estudio
    
    Returns:
    {
        "success": true,
        "message": "Tipo de estudio eliminado"
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
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isstudytype WHERE guid=%s", (study_type_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Tipo de estudio no encontrado'
            }), 404
        
        query = "DELETE FROM nextris.isstudytype WHERE guid = %s"
        cursor.execute(query, (study_type_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Tipo de estudio eliminado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# MODALIDADES, PARTES DEL CUERPO, GRUPOS
# ====================================================================

@api_blueprint.route('/config/modalities', methods=['GET'])
@jwt_required()
def get_modalities():
    """
    Obtiene todas las modalidades
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "externalcode": "...",
                "description": "..."
            }
        ]
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
        
        query = "SELECT guid, externalcode, description FROM nextris.ismodality ORDER BY description"
        try:
            cursor.execute(query)
            results = cursor.fetchall()
            has_custom_permissions_count = True
        except Exception:
            # Fallback para entornos donde la tabla de permisos aún no existe
            if include_inactive:
                fallback_query = """
                    SELECT u.guid, u.username, r.description, u.name, u.surname,
                           u.nationalnumber, u.mail, u.isactive
                    FROM nextris.tbuser u
                    INNER JOIN nextris.isrole r ON r.guid = u.idrole
                    ORDER BY u.isactive DESC, u.username
                """
            else:
                fallback_query = """
                    SELECT u.guid, u.username, r.description, u.name, u.surname,
                           u.nationalnumber, u.mail, u.isactive
                    FROM nextris.tbuser u
                    INNER JOIN nextris.isrole r ON r.guid = u.idrole
                    WHERE u.isactive = 1
                    ORDER BY u.username
                """
            cursor.execute(fallback_query)
            results = cursor.fetchall()
            has_custom_permissions_count = False
        
        cursor.close()
        connection.close()
        
        modalities = []
        for row in results:
            modalities.append({
                'guid': row[0],
                'externalcode': row[1],
                'description': row[2]
            })
        
        return jsonify({
            'success': True,
            'data': modalities
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/modalities', methods=['POST'])
@jwt_required()
def create_modality():
    """
    Crea una nueva modalidad
    
    Body JSON:
    {
        "externalcode": "string" (required),
        "description": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Modalidad creada",
        "data": {
            "modality_id": "uuid"
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
        
        externalcode = data.get('externalcode')
        description = data.get('description')
        
        if not all([externalcode, description]):
            return jsonify({
                'success': False,
                'message': 'externalcode y description son requeridos'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.ismodality(guid, externalcode, description) 
            VALUES (%s, %s, %s)
        """
        
        cursor.execute(query, (new_guid, externalcode, description))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Modalidad creada exitosamente',
            'data': {
                'modality_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/modalities/<modality_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_modality(modality_id):
    """
    Actualiza una modalidad existente
    
    Path:
    - modality_id: GUID de la modalidad
    
    Body JSON (todos opcionales):
    {
        "externalcode": "string",
        "description": "string"
    }
    
    Returns:
    {
        "success": true,
        "message": "Modalidad actualizada"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.ismodality WHERE guid=%s", (modality_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Modalidad no encontrada'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'externalcode' in data:
            updates.append("externalcode = %s")
            params.append(data['externalcode'])
        if 'description' in data:
            updates.append("description = %s")
            params.append(data['description'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(modality_id)
        query = f"UPDATE nextris.ismodality SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Modalidad actualizada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/modalities/<modality_id>', methods=['DELETE'])
@jwt_required()
def delete_modality(modality_id):
    """
    Elimina una modalidad
    
    Path:
    - modality_id: GUID de la modalidad
    
    Returns:
    {
        "success": true,
        "message": "Modalidad eliminada"
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
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.ismodality WHERE guid=%s", (modality_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Modalidad no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.ismodality WHERE guid = %s"
        cursor.execute(query, (modality_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Modalidad eliminada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/body-parts', methods=['GET'])
@jwt_required()
def get_body_parts():
    """
    Obtiene todas las partes del cuerpo
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "..."
            }
        ]
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
        
        query = "SELECT guid, description FROM nextris.isanatomicalpart ORDER BY description"
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        body_parts = []
        for row in results:
            body_parts.append({
                'guid': row[0],
                'description': row[1]
            })
        
        return jsonify({
            'success': True,
            'data': body_parts
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/body-parts', methods=['POST'])
@jwt_required()
def create_body_part():
    """
    Crea una nueva parte del cuerpo
    
    Body JSON:
    {
        "description": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Parte del cuerpo creada",
        "data": {
            "body_part_id": "uuid"
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
        
        description = data.get('description')
        
        if not description:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isanatomicalpart(guid, description) 
            VALUES (%s, %s)
        """
        
        cursor.execute(query, (new_guid, description))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Parte del cuerpo creada exitosamente',
            'data': {
                'body_part_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/body-parts/<body_part_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_body_part(body_part_id):
    """
    Actualiza una parte del cuerpo existente
    
    Path:
    - body_part_id: GUID de la parte del cuerpo
    
    Body JSON:
    {
        "description": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Parte del cuerpo actualizada"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        description = data.get('description')
        
        if not description:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isanatomicalpart WHERE guid=%s", (body_part_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Parte del cuerpo no encontrada'
            }), 404
        
        query = "UPDATE nextris.isanatomicalpart SET description = %s WHERE guid = %s"
        
        cursor.execute(query, (description, body_part_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Parte del cuerpo actualizada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/body-parts/<body_part_id>', methods=['DELETE'])
@jwt_required()
def delete_body_part(body_part_id):
    """
    Elimina una parte del cuerpo
    
    Path:
    - body_part_id: GUID de la parte del cuerpo
    
    Returns:
    {
        "success": true,
        "message": "Parte del cuerpo eliminada"
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
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isanatomicalpart WHERE guid=%s", (body_part_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Parte del cuerpo no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.isanatomicalpart WHERE guid = %s"
        cursor.execute(query, (body_part_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Parte del cuerpo eliminada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-groups', methods=['GET'])
@jwt_required()
def get_study_groups():
    """
    Obtiene todos los grupos de estudio
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "..."
            }
        ]
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
        
        query = "SELECT guid, description FROM nextris.isstudytypegroup ORDER BY description"
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        groups = []
        for row in results:
            groups.append({
                'guid': row[0],
                'description': row[1]
            })
        
        return jsonify({
            'success': True,
            'data': groups
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-groups', methods=['POST'])
@jwt_required()
def create_study_group():
    """
    Crea un nuevo grupo de estudio
    
    Body JSON:
    {
        "description": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Grupo de estudio creado",
        "data": {
            "study_group_id": "uuid"
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
        
        description = data.get('description')
        
        if not description:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isstudytypegroup(guid, description) 
            VALUES (%s, %s)
        """
        
        cursor.execute(query, (new_guid, description))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Grupo de estudio creado exitosamente',
            'data': {
                'study_group_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-groups/<study_group_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_study_group(study_group_id):
    """
    Actualiza un grupo de estudio existente
    
    Path:
    - study_group_id: GUID del grupo de estudio
    
    Body JSON:
    {
        "description": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Grupo de estudio actualizado"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        description = data.get('description')
        
        if not description:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isstudytypegroup WHERE guid=%s", (study_group_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Grupo de estudio no encontrado'
            }), 404
        
        query = "UPDATE nextris.isstudytypegroup SET description = %s WHERE guid = %s"
        
        cursor.execute(query, (description, study_group_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Grupo de estudio actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/study-groups/<study_group_id>', methods=['DELETE'])
@jwt_required()
def delete_study_group(study_group_id):
    """
    Elimina un grupo de estudio
    
    Path:
    - study_group_id: GUID del grupo de estudio
    
    Returns:
    {
        "success": true,
        "message": "Grupo de estudio eliminado"
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
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isstudytypegroup WHERE guid=%s", (study_group_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Grupo de estudio no encontrado'
            }), 404
        
        query = "DELETE FROM nextris.isstudytypegroup WHERE guid = %s"
        cursor.execute(query, (study_group_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Grupo de estudio eliminado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# EQUIPOS (MÁQUINAS)
# ====================================================================

@api_blueprint.route('/config/equipment', methods=['GET'])
@jwt_required()
def get_equipment():
    """
    Obtiene equipos/máquinas filtrados opcionalmente por ubicación y/o modalidad
    
    Query Parameters:
    - location_id (OPCIONAL): Filtrar equipos por ubicación
    - modality_id (OPCIONAL): Filtrar equipos por modalidad
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "...",
                "aeTitle": "...",
                "externalcode": "...",
                "modality": "..."
            }
        ]
    }
    """
    try:
        # Obtener parámetros opcionales
        location_id = request.args.get('location_id')
        modality_id = request.args.get('modality_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Construir query base
        query = """
            SELECT e.guid, e.description, e.aetitle, e.externalcode, m.description as modality
            FROM nextris.isequipment e
            LEFT JOIN nextris.ismodality m ON e.idmodality = m.guid
            WHERE 1=1
        """
        
        params = []
        
        # Agregar filtro de ubicación si se proporciona
        if location_id:
            query += " AND e.location_id = %s"
            params.append(location_id)
        
        # Agregar filtro de modalidad si se proporciona
        if modality_id:
            query += " AND e.idmodality = %s"
            params.append(modality_id)
        
        query += " ORDER BY e.description"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        equipment_list = []
        for row in results:
            equipment_list.append({
                'guid': row[0],
                'description': row[1],
                'aeTitle': row[2],
                'externalcode': row[3],
                'modality': row[4]
            })
        
        return jsonify({
            'success': True,
            'data': equipment_list
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/equipment', methods=['POST'])
@jwt_required()
def create_equipment():
    """
    Crea un nuevo equipo
    
    Body JSON:
    {
        "name": "string" (required),
        "aetitle": "string" (required),
        "location_id": "uuid" (required),
        "modality_id": "uuid" (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Equipo creado",
        "data": {
            "equipment_id": "uuid"
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
        
        description = data.get('description')
        aetitle = data.get('aetitle')
        modality_id = data.get('modality_id')
        
        if not all([description, aetitle]):
            return jsonify({
                'success': False,
                'message': 'description y aetitle son requeridos'
            }), 400
        
        externalcode = data.get('externalcode', '')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isequipment(guid, description, aetitle, externalcode, idmodality, isactive) 
            VALUES (%s, %s, %s, %s, %s, 1)
        """
        
        cursor.execute(query, (new_guid, description, aetitle, externalcode, modality_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Equipo creado exitosamente',
            'data': {
                'equipment_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/equipment/<equipment_id>', methods=['DELETE'])
@jwt_required()
def delete_equipment(equipment_id):
    """
    Elimina un equipo
    
    Path:
    - equipment_id: GUID del equipo
    
    Returns:
    {
        "success": true,
        "message": "Equipo eliminado"
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
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.isequipment WHERE guid=%s", (equipment_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Equipo no encontrado'
            }), 404
        
        query = "DELETE FROM nextris.isequipment WHERE guid = %s"
        cursor.execute(query, (equipment_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Equipo eliminado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# UBICACIONES (LOCATIONS)
# ====================================================================

@api_blueprint.route('/config/locations', methods=['GET'])
@jwt_required()
def get_locations():
    """
    Obtiene todas las ubicaciones con todos sus datos
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "facility_id": "...",
                "name": "...",
                "code": "...",
                "address": "...",
                "phone": "...",
                "status": "...",
                "created_at": "...",
                "updated_at": "...",
                "mail": "...",
                "logo_path": "...",
                "geographic_location": "...",
                "timezone": "..."
            }
        ]
    }
    """
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        ensure_location_status_column(connection)
        ensure_location_report_execution_column(connection)
        
        query = """
            SELECT l.guid, l.name, l.code, l.address, l.phone, l.status,
                   l.created_at, l.updated_at,
                   l.mail, l.logo_path,
                   l.geographic_location, l.timezone,
                   l.gateway_aet, l.gateway_ip, l.transmission_type, l.retention_days,
                   COALESCE(l.require_execution_before_reporting, TRUE)
            FROM nextris.tblocation l
        """

        if include_inactive:
            query += " ORDER BY l.name"
        else:
            query += " WHERE LOWER(COALESCE(NULLIF(BTRIM(l.status), ''), 'Active')) = 'active' ORDER BY l.name"

        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        locations = []
        for row in results:
            locations.append({
                'guid': row[0],
                'facility_id': None,
                'facility_name': None,
                'name': row[1],
                'code': row[2],
                'address': row[3],
                'phone': row[4],
                'status': row[5],
                'created_at': row[6].isoformat() if row[6] else None,
                'updated_at': row[7].isoformat() if row[7] else None,
                'mail': row[8],
                'logo_path': row[9],
                'geographic_location': row[10],
                'timezone': row[11],
                'gateway_aet': row[12],
                'gateway_ip': row[13],
                'transmission_type': row[14],
                'retention_days': row[15],
                'require_execution_before_reporting': bool(row[16])
            })
        
        return jsonify({
            'success': True,
            'data': locations
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/locations', methods=['POST'])
@jwt_required()
def create_location():
    """
    Crea una nueva ubicación
    
    Body JSON:
    {
        "name": "string" (required),
        "code": "string" (optional),
        "facility_id": "uuid" (optional),
        "address": "string" (optional),
        "phone": "string" (optional),
        "status": "string" (optional, default: 'Active'),
        "mail": "string" (optional),
        "geographic_location": "string" (optional),
        "timezone": "string" (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Ubicación creada",
        "data": {
            "location_id": "uuid"
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
        
        name = data.get('name')
        
        if not name:
            return jsonify({
                'success': False,
                'message': 'name es requerido'
            }), 400
        
        # Obtener todos los campos opcionales
        code = data.get('code', '')
        address = data.get('address', '')
        phone = data.get('phone', '')
        raw_status = data.get('status', 'Active')
        status = 'Inactive' if str(raw_status).strip().lower() == 'inactive' else 'Active'
        mail = data.get('mail', '')
        geographic_location = data.get('geographic_location', '')
        timezone = data.get('timezone', '')
        gateway_aet = data.get('gateway_aet')
        gateway_ip = data.get('gateway_ip')
        transmission_type = data.get('transmission_type', 'Manual')
        retention_days = data.get('retention_days')
        require_execution_before_reporting = parse_bool_value(
            data.get('require_execution_before_reporting'),
            default=True,
        )

        # Compatibilidad con frontend que envía email
        if 'email' in data and not mail:
            mail = data.get('email', '')

        if transmission_type not in ('Manual', 'Automatic'):
            return jsonify({
                'success': False,
                'message': "transmission_type debe ser 'Manual' o 'Automatic'"
            }), 400

        if retention_days in ('', None):
            retention_days = None
        elif str(retention_days).isdigit():
            retention_days = int(retention_days)
            if retention_days <= 0:
                return jsonify({
                    'success': False,
                    'message': 'retention_days debe ser mayor a 0'
                }), 400
        else:
            return jsonify({
                'success': False,
                'message': 'retention_days debe ser numérico'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        ensure_location_status_column(connection)
        ensure_location_report_execution_column(connection)

        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.tblocation(
                guid, name, code, address, phone, status,
                created_at, updated_at, mail, 
                geographic_location, timezone,
                gateway_aet, gateway_ip, transmission_type, retention_days,
                require_execution_before_reporting
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            new_guid, name, code, address, phone, status,
            mail, geographic_location, timezone,
            gateway_aet, gateway_ip, transmission_type, retention_days,
            require_execution_before_reporting
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Ubicación creada exitosamente',
            'data': {
                'location_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/locations/<location_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_location(location_id):
    """
    Actualiza una ubicación existente
    
    Path:
    - location_id: GUID de la ubicación
    
    Body JSON o multipart/form-data (todos opcionales):
    {
        "name": "string",
        "code": "string",
        "facility_id": "uuid",
        "address": "string",
        "phone": "string",
        "status": "string",
        "mail": "string",
        "geographic_location": "string",
        "timezone": "string",
        "logo": "file"
    }
    
    Returns:
    {
        "success": true,
        "message": "Ubicación actualizada"
    }
    """
    try:
        is_multipart = request.content_type and 'multipart/form-data' in request.content_type

        if is_multipart:
            data = request.form.to_dict()
        else:
            data = request.get_json() or {}

        logo_file = request.files.get('logo') if is_multipart else None

        if not data and not logo_file:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo con datos para actualizar'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        ensure_location_status_column(connection)
        ensure_location_report_execution_column(connection)
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (location_id,))
        existing_location_row = cursor.fetchone()
        if not existing_location_row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'name' in data:
            updates.append("name = %s")
            params.append(data['name'])
        if 'code' in data:
            updates.append("code = %s")
            params.append(data['code'])
        if 'address' in data:
            updates.append("address = %s")
            params.append(data['address'])
        if 'phone' in data:
            updates.append("phone = %s")
            params.append(data['phone'])
        requested_status = None
        if 'status' in data:
            updates.append("status = %s")
            status_value = _normalize_active_status(data['status'])
            requested_status = status_value
            params.append(status_value)
        if 'mail' in data or 'email' in data:
            updates.append("mail = %s")
            params.append(data.get('mail', data.get('email')))
        if 'geographic_location' in data:
            updates.append("geographic_location = %s")
            params.append(data['geographic_location'])
        if 'timezone' in data:
            updates.append("timezone = %s")
            params.append(data['timezone'])
        if 'gateway_aet' in data:
            updates.append("gateway_aet = %s")
            params.append(data['gateway_aet'])
        if 'gateway_ip' in data:
            updates.append("gateway_ip = %s")
            params.append(data['gateway_ip'])
        if 'transmission_type' in data:
            transmission_value = data['transmission_type']
            if transmission_value not in ('Manual', 'Automatic'):
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': "transmission_type debe ser 'Manual' o 'Automatic'"
                }), 400
            updates.append("transmission_type = %s")
            params.append(transmission_value)
        if 'retention_days' in data:
            retention_value = data.get('retention_days')
            if retention_value in ('', None):
                updates.append("retention_days = NULL")
            elif str(retention_value).isdigit():
                retention_value = int(retention_value)
                if retention_value <= 0:
                    cursor.close()
                    connection.close()
                    return jsonify({
                        'success': False,
                        'message': 'retention_days debe ser mayor a 0'
                    }), 400
                updates.append("retention_days = %s")
                params.append(retention_value)
            else:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'retention_days debe ser numérico'
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
            updates.append("require_execution_before_reporting = %s")
            params.append(require_execution_value)

        if logo_file and logo_file.filename:
            logo_path = _process_location_logo(logo_file, location_id)
            if not logo_path:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'Logo inválido. Use PNG, JPG, JPEG, GIF o BMP.'
                }), 400
            updates.append("logo_path = %s")
            params.append(logo_path)
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400

        # Agregar updated_at
        updates.append("updated_at = NOW()")
        
        params.append(location_id)
        query = f"UPDATE nextris.tblocation SET {', '.join(updates)} WHERE guid = %s"

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
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/locations/<location_id>/deactivate', methods=['POST'])
@jwt_required()
def deactivate_location(location_id):
    """Desactiva una ubicación sin eliminarla."""
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        ensure_location_status_column(connection)

        cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (location_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404

        cursor.execute(
            """
            UPDATE nextris.tblocation
            SET status = 'Inactive', updated_at = NOW()
            WHERE guid = %s
            """,
            (location_id,),
        )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicación desactivada exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/locations/<location_id>/activate', methods=['POST'])
@jwt_required()
def activate_location(location_id):
    """Activa una ubicación previamente desactivada."""
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        ensure_location_status_column(connection)

        cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (location_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404

        cursor.execute(
            """
            UPDATE nextris.tblocation
            SET status = 'Active', updated_at = NOW()
            WHERE guid = %s
            """,
            (location_id,),
        )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicación activada exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/locations/<location_id>', methods=['DELETE'])
@jwt_required()
def delete_location(location_id):
    """
    Elimina una ubicación
    
    Path:
    - location_id: GUID de la ubicación
    
    Returns:
    {
        "success": true,
        "message": "Ubicación eliminada"
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
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (location_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.tblocation WHERE guid = %s"
        cursor.execute(query, (location_id,))
        
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
            'message': f'Error: {str(e)}'
        }), 500

# ====================================================================
# AGENDAS DE EQUIPOS
# ====================================================================

@api_blueprint.route('/config/equipment/<equipment_id>/schedule', methods=['GET'])
@jwt_required()
def get_equipment_schedule(equipment_id):
    """
    Obtiene la agenda de un equipo específico
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "day": 1,
                "time_from": "08:00",
                "time_to": "17:00"
            }
        ]
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
            SELECT guid, day, timefrom, timeto
            FROM nextris.isagendaequip 
            WHERE idequipment = %s
            ORDER BY day, timefrom
        """
        cursor.execute(query, (equipment_id,))
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        schedule = []
        for row in results:
            schedule.append({
                'guid': row[0],
                'day': row[1],
                'time_from': row[2].strftime('%H:%M') if row[2] else None,
                'time_to': row[3].strftime('%H:%M') if row[3] else None
            })
        
        return jsonify({
            'success': True,
            'data': schedule
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/equipment/<equipment_id>/schedule', methods=['POST'])
@jwt_required()
def create_equipment_schedule(equipment_id):
    """
    Agrega un día de agenda para un equipo
    
    Body JSON:
    {
        "day": number (required, 0-6 donde 0=Domingo),
        "time_from": "HH:MM" (required),
        "time_to": "HH:MM" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Agenda creada",
        "data": {
            "schedule_id": "uuid",
            "day": 1,
            "time_from": "08:00",
            "time_to": "17:00"
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
        
        day = data.get('day')
        time_from = data.get('time_from')
        time_to = data.get('time_to')
        
        if day is None or not time_from or not time_to:
            return jsonify({
                'success': False,
                'message': 'day, time_from y time_to son requeridos'
            }), 400
        
        # Validar día (0-6)
        if not isinstance(day, int) or day < 0 or day > 6:
            return jsonify({
                'success': False,
                'message': 'day debe ser un número entre 0 (Domingo) y 6 (Sábado)'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el equipo existe
        cursor.execute("SELECT 1 FROM nextris.isequipment WHERE guid=%s", (equipment_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Equipo no encontrado'
            }), 404
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isagendaequip (guid, idequipment, day, timefrom, timeto)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING guid, day, timefrom, timeto
        """
        
        cursor.execute(query, (new_guid, equipment_id, day, time_from, time_to))
        result = cursor.fetchone()
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Agenda creada exitosamente',
            'data': {
                'schedule_id': result[0],
                'day': result[1],
                'time_from': result[2].strftime('%H:%M') if result[2] else None,
                'time_to': result[3].strftime('%H:%M') if result[3] else None
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/equipment/<equipment_id>/schedule/<schedule_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_equipment_schedule(equipment_id, schedule_id):
    """
    Actualiza un día de agenda de un equipo
    
    Body JSON (todos opcionales):
    {
        "day": number,
        "time_from": "HH:MM",
        "time_to": "HH:MM"
    }
    
    Returns:
    {
        "success": true,
        "message": "Agenda actualizada"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute(
            "SELECT 1 FROM nextris.isagendaequip WHERE guid=%s AND idequipment=%s", 
            (schedule_id, equipment_id)
        )
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Agenda no encontrada'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'day' in data:
            if not isinstance(data['day'], int) or data['day'] < 0 or data['day'] > 6:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'day debe ser un número entre 0 y 6'
                }), 400
            updates.append("day = %s")
            params.append(data['day'])
        
        if 'time_from' in data:
            updates.append("timefrom = %s")
            params.append(data['time_from'])
        
        if 'time_to' in data:
            updates.append("timeto = %s")
            params.append(data['time_to'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(schedule_id)
        query = f"UPDATE nextris.isagendaequip SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Agenda actualizada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/equipment/<equipment_id>/schedule/<schedule_id>', methods=['DELETE'])
@jwt_required()
def delete_equipment_schedule(equipment_id, schedule_id):
    """
    Elimina un día de agenda de un equipo
    
    Returns:
    {
        "success": true,
        "message": "Agenda eliminada"
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
        
        # Verificar que existe
        cursor.execute(
            "SELECT 1 FROM nextris.isagendaequip WHERE guid=%s AND idequipment=%s", 
            (schedule_id, equipment_id)
        )
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Agenda no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.isagendaequip WHERE guid = %s"
        cursor.execute(query, (schedule_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Agenda eliminada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# GESTIÓN DE USUARIOS
# ====================================================================

@api_blueprint.route('/config/users', methods=['GET'])
@jwt_required()
def get_config_users():
    """
    Obtiene todos los usuarios del sistema
    
    Query Parameters:
    - include_inactive: true/false (opcional, default: false)
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "username": "...",
                "role": "...",
                "name": "...",
                "surname": "...",
                "national_number": "...",
                "email": "...",
                "is_active": true
            }
        ]
    }
    """
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        has_custom_permissions_count = True

        try:
            if include_inactive:
                  query = """
                      SELECT u.guid, u.username, r.description, u.idrole, u.name, u.surname, 
                          u.nationalnumber, u.mail, u.isactive,
                          COALESCE(up.permissions_count, 0) AS custom_permissions_count
                    FROM nextris.tbuser u
                    INNER JOIN nextris.isrole r ON r.guid = u.idrole
                    LEFT JOIN (
                        SELECT user_id, COUNT(*) AS permissions_count
                        FROM nextris.rel_user_permission
                        WHERE is_granted = TRUE
                        GROUP BY user_id
                    ) up ON up.user_id = u.guid
                    ORDER BY u.isactive DESC, u.username
                """
            else:
                  query = """
                      SELECT u.guid, u.username, r.description, u.idrole, u.name, u.surname, 
                          u.nationalnumber, u.mail, u.isactive,
                          COALESCE(up.permissions_count, 0) AS custom_permissions_count
                    FROM nextris.tbuser u
                    INNER JOIN nextris.isrole r ON r.guid = u.idrole
                    LEFT JOIN (
                        SELECT user_id, COUNT(*) AS permissions_count
                        FROM nextris.rel_user_permission
                        WHERE is_granted = TRUE
                        GROUP BY user_id
                    ) up ON up.user_id = u.guid
                    WHERE u.isactive = 1
                    ORDER BY u.username
                """

            cursor.execute(query)
            results = cursor.fetchall()
        except Exception:
            connection.rollback()
            has_custom_permissions_count = False

            if include_inactive:
                  fallback_query = """
                      SELECT u.guid, u.username, r.description, u.idrole, u.name, u.surname,
                          u.nationalnumber, u.mail, u.isactive
                    FROM nextris.tbuser u
                    INNER JOIN nextris.isrole r ON r.guid = u.idrole
                    ORDER BY u.isactive DESC, u.username
                """
            else:
                fallback_query = """
                      SELECT u.guid, u.username, r.description, u.idrole, u.name, u.surname,
                          u.nationalnumber, u.mail, u.isactive
                    FROM nextris.tbuser u
                    INNER JOIN nextris.isrole r ON r.guid = u.idrole
                    WHERE u.isactive = 1
                    ORDER BY u.username
                """

            cursor.execute(fallback_query)
            results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        users = []
        for row in results:
            users.append({
                'guid': row[0],
                'username': row[1],
                'role': row[2],
                'role_id': row[3],
                'name': row[4],
                'surname': row[5],
                'national_number': row[6],
                'email': row[7],
                'is_active': bool(row[8]),
                'custom_permissions_count': int(row[9] or 0) if has_custom_permissions_count else 0
            })
        
        return jsonify({
            'success': True,
            'data': users
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users', methods=['POST'])
@jwt_required()
def create_config_user():
    """
    Crea un nuevo usuario
    
    Body JSON:
    {
        "username": "string" (required),
        "email": "string" (optional),
        "name": "string" (required),
        "surname": "string" (required),
        "national_number": "string" (optional),
        "role_id": "uuid" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Usuario creado",
        "data": {
            "user_id": "uuid",
            "username": "..."
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
        
        username = data.get('username')
        email = data.get('email')
        name = data.get('name')
        surname = data.get('surname')
        role_id = data.get('role_id')
        
        if not all([username, name, surname, role_id]):
            return jsonify({
                'success': False,
                'message': 'username, name, surname y role_id son requeridos'
            }), 400
        
        national_number = data.get('national_number', '')
        temporary_password = generate_temporary_password()
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar si el username ya existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'El nombre de usuario ya existe'
            }), 400
        
        # Verificar que el rol existe
        cursor.execute("SELECT description FROM nextris.isrole WHERE guid = %s", (role_id,))
        role_row = cursor.fetchone()
        if not role_row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Rol no encontrado'
            }), 404
        role_description = role_row[0]
        
        # Hashear contraseña
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(temporary_password)
        
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.tbuser(
                guid, username, mail, password, name, surname, 
                nationalnumber, idrole, isactive, first_login
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, 1)
            RETURNING guid, username
        """
        
        cursor.execute(query, (
            new_guid, username, email, password_hash, name, surname,
            national_number, role_id
        ))

        result = cursor.fetchone()

        # '*' representa permiso global por rol y no debe persistirse como permiso custom.
        default_permission_codes = [
            code for code in get_default_permissions_for_role(role_description)
            if code and code != '*'
        ]
        if default_permission_codes:
            replace_user_permissions(new_guid, default_permission_codes, connection=connection)

        connection.commit()

        email_error = None
        full_name = f"{name} {surname}".strip()
        try:
            send_new_user_credentials_email(
                connection=connection,
                email=email,
                username=username,
                temporary_password=temporary_password,
                full_name=full_name
            )
        except Exception as email_exc:
            # El usuario ya fue creado; no se revierte por un fallo de SMTP.
            email_error = str(email_exc)

        cursor.close()
        connection.close()

        message = 'Usuario creado exitosamente'
        if email_error:
            message = (
                'Usuario creado, pero no se pudo enviar el correo con credenciales. '
                f'Detalle: {email_error}'
            )
        
        return jsonify({
            'success': True,
            'message': message,
            'data': {
                'user_id': result[0],
                'username': result[1],
                'credentials_email_sent': email_error is None,
                'credentials_email_error': email_error
            }
        }), 201
        
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


@api_blueprint.route('/config/users/<user_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_config_user(user_id):
    """
    Actualiza un usuario existente
    
    Body JSON (todos opcionales):
    {
        "username": "string",
        "email": "string",
        "name": "string",
        "surname": "string",
        "national_number": "string",
        "role_id": "uuid"
    }
    
    Returns:
    {
        "success": true,
        "message": "Usuario actualizado"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el usuario existe y obtener rol actual
        cursor.execute(
            """
            SELECT u.idrole, r.description
            FROM nextris.tbuser u
            LEFT JOIN nextris.isrole r ON r.guid = u.idrole
            WHERE u.guid = %s
            """,
            (user_id,)
        )
        user_row = cursor.fetchone()
        if not user_row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        current_role_id = user_row[0]
        
        # Construir query dinámicamente
        updates = []
        params = []
        role_changed = False
        new_role_description = None
        
        if 'username' in data:
            # Verificar que el nuevo username no esté en uso por otro usuario
            cursor.execute(
                "SELECT 1 FROM nextris.tbuser WHERE username = %s AND guid != %s",
                (data['username'], user_id)
            )
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'El nombre de usuario ya está en uso'
                }), 400
            updates.append("username = %s")
            params.append(data['username'])
        
        if 'email' in data:
            updates.append("mail = %s")
            params.append(data['email'])
        
        if 'name' in data:
            updates.append("name = %s")
            params.append(data['name'])
        
        if 'surname' in data:
            updates.append("surname = %s")
            params.append(data['surname'])
        
        if 'national_number' in data:
            updates.append("nationalnumber = %s")
            params.append(data['national_number'])
        
        if 'role_id' in data:
            # Verificar que el rol existe
            cursor.execute("SELECT description FROM nextris.isrole WHERE guid = %s", (data['role_id'],))
            role_row = cursor.fetchone()
            if not role_row:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'Rol no encontrado'
                }), 404

            new_role_description = role_row[0]
            role_changed = data['role_id'] != current_role_id
            updates.append("idrole = %s")
            params.append(data['role_id'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(user_id)
        query = f"UPDATE nextris.tbuser SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)

        if role_changed:
            default_permission_codes = get_default_permissions_for_role(new_role_description)
            replace_user_permissions(user_id, default_permission_codes, connection=connection)

        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuario actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/deactivate', methods=['POST'])
@jwt_required()
def deactivate_user(user_id):
    """
    Desactiva un usuario (no lo elimina)
    
    Returns:
    {
        "success": true,
        "message": "Usuario desactivado"
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
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        
        query = "UPDATE nextris.tbuser SET isactive = 0 WHERE guid = %s"
        cursor.execute(query, (user_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuario desactivado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/activate', methods=['POST'])
@jwt_required()
def activate_user(user_id):
    """
    Activa un usuario previamente desactivado
    
    Returns:
    {
        "success": true,
        "message": "Usuario activado"
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
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        
        query = "UPDATE nextris.tbuser SET isactive = 1 WHERE guid = %s"
        cursor.execute(query, (user_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuario activado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/reset-password', methods=['POST'])
@jwt_required()
def reset_user_password(user_id):
    """
    Resetea la contraseña de un usuario
    
    Body JSON:
    {
        "new_password": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Contraseña reseteada"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'new_password' not in data:
            return jsonify({
                'success': False,
                'message': 'new_password es requerido'
            }), 400
        
        new_password = data.get('new_password')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el usuario existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        
        # Hashear la nueva contraseña
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(new_password)
        
        # Actualizar contraseña y marcar como primer login
        query = """
            UPDATE nextris.tbuser 
            SET password = %s, first_login = 1 
            WHERE guid = %s
        """
        cursor.execute(query, (password_hash, user_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Contraseña reseteada exitosamente. El usuario deberá cambiarla en su primer inicio de sesión.'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>', methods=['DELETE'])
@jwt_required()
def delete_config_user(user_id):
    """
    Elimina permanentemente un usuario (usar con precaución)
    Recomendado usar deactivate en su lugar
    
    Returns:
    {
        "success": true,
        "message": "Usuario eliminado"
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
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        
        query = "DELETE FROM nextris.tbuser WHERE guid = %s"
        cursor.execute(query, (user_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuario eliminado permanentemente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/permissions', methods=['GET'])
@jwt_required()
@require_permission('users.permissions.manage', include_role_permissions=True)
def get_permissions_catalog_endpoint():
    """
    Retorna catálogo de permisos disponibles para asignación.
    """
    try:
        permissions = get_permission_catalog()
        return jsonify({
            'success': True,
            'data': permissions
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/permissions', methods=['GET'])
@jwt_required()
@require_permission('users.permissions.manage', include_role_permissions=True)
def get_user_permissions_endpoint(user_id):
    """
    Obtiene permisos de un usuario.

    Respuesta:
    {
      "success": true,
      "data": {
        "user_id": "...",
        "custom_permissions": ["distribution.send_report"],
        "effective_permissions": [...],
        "catalog": [...]
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
        ensure_permissions_schema(connection)
        seed_permissions(connection)
        cursor = connection.cursor()

        resolved_user_id = user_id

        cursor.execute("SELECT guid FROM nextris.tbuser WHERE guid = %s", (user_id,))
        user_row = cursor.fetchone()

        if not user_row:
            cursor.execute("SELECT guid FROM nextris.tbuser WHERE username = %s", (user_id,))
            user_row = cursor.fetchone()

        if not user_row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        resolved_user_id = user_row[0]

        cursor.execute(
            """
            SELECT p.code
            FROM nextris.rel_user_permission up
            INNER JOIN nextris.ispermission p ON p.guid = up.permission_id
            WHERE up.user_id = %s
              AND up.is_granted = TRUE
              AND p.is_active = TRUE
            ORDER BY p.code
            """,
            (resolved_user_id,),
        )
        custom_permissions = normalize_permission_codes([row[0] for row in cursor.fetchall()])
        cursor.close()
        connection.close()

        effective_permissions = get_user_permission_codes(resolved_user_id, include_role_permissions=False)
        catalog = get_permission_catalog()

        return jsonify({
            'success': True,
            'data': {
                'user_id': resolved_user_id,
                'custom_permissions': custom_permissions,
                'effective_permissions': effective_permissions,
                'catalog': catalog,
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/permissions', methods=['PUT'])
@jwt_required()
@require_permission('users.permissions.manage', include_role_permissions=True)
def set_user_permissions_endpoint(user_id):
    """
    Reemplaza permisos personalizados de un usuario.

    Body JSON:
    {
      "permission_codes": ["distribution.send_report", "reports.sign"]
    }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        permission_codes = data.get('permission_codes')

        if not isinstance(permission_codes, list):
            return jsonify({
                'success': False,
                'message': 'permission_codes debe ser una lista'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT guid FROM nextris.tbuser WHERE guid = %s", (user_id,))
        user_row = cursor.fetchone()

        if not user_row:
            cursor.execute("SELECT guid FROM nextris.tbuser WHERE username = %s", (user_id,))
            user_row = cursor.fetchone()

        cursor.close()
        connection.close()

        if not user_row:
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        resolved_user_id = user_row[0]

        assigned_codes = replace_user_permissions(resolved_user_id, permission_codes)
        effective_permissions = get_user_permission_codes(resolved_user_id, include_role_permissions=False)

        return jsonify({
            'success': True,
            'message': 'Permisos actualizados exitosamente',
            'data': {
                'user_id': resolved_user_id,
                'custom_permissions': assigned_codes,
                'effective_permissions': effective_permissions,
            }
        }), 200
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# DATOS MEDICOS DEL USUARIO (FIRMA DIGITAL)
# ====================================================================

@api_blueprint.route('/config/users/<user_id>/medical-data', methods=['GET'])
@jwt_required()
def get_user_medical_data(user_id):
    """
    Obtiene datos medicos de un usuario
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuracion de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        ensure_user_medical_table(connection)
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT aclaracion_firma, matricula_nacional, firma_digital, firma_habilitada
            FROM nextris.tbuser_medical_data
            WHERE user_id = %s
            """,
            (user_id,)
        )
        result = cursor.fetchone()

        cursor.close()
        connection.close()

        if result:
            return jsonify({
                'success': True,
                'data': {
                    'aclaracion_firma': result[0],
                    'matricula_nacional': result[1],
                    'firma_digital': result[2],
                    'firma_habilitada': bool(result[3])
                }
            }), 200

        return jsonify({
            'success': True,
            'data': {
                'aclaracion_firma': '',
                'matricula_nacional': '',
                'firma_digital': None,
                'firma_habilitada': False
            }
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/medical-data', methods=['POST'])
@jwt_required()
def save_user_medical_data(user_id):
    """
    Crea o actualiza datos medicos de un usuario

    Body (multipart/form-data):
    - aclaracion_firma (required)
    - matricula_nacional (required)
    - firma_habilitada (optional, true/false)
    - firma_digital (optional file: png/jpg/jpeg)
    """
    try:
        aclaracion_firma = request.form.get('aclaracion_firma')
        matricula_nacional = request.form.get('matricula_nacional')
        firma_habilitada = request.form.get('firma_habilitada', 'false').lower() == 'true'

        if not aclaracion_firma or not matricula_nacional:
            return jsonify({
                'success': False,
                'message': 'aclaracion_firma y matricula_nacional son requeridos'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuracion de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        ensure_user_medical_table(connection)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        firma_filename = None
        if 'firma_digital' in request.files:
            file = request.files['firma_digital']
            if file and file.filename:
                allowed_extensions = {'png', 'jpg', 'jpeg'}
                if '.' not in file.filename:
                    cursor.close()
                    connection.close()
                    return jsonify({
                        'success': False,
                        'message': 'Nombre de archivo invalido'
                    }), 400

                file_extension = file.filename.rsplit('.', 1)[1].lower()
                if file_extension not in allowed_extensions:
                    cursor.close()
                    connection.close()
                    return jsonify({
                        'success': False,
                        'message': 'Tipo de archivo no permitido'
                    }), 400

                upload_dir = _get_signature_upload_dir()
                os.makedirs(upload_dir, exist_ok=True)

                safe_name = secure_filename(file.filename)
                unique_filename = f"{user_id}_{uuid.uuid4().hex}_{safe_name}"
                firma_path = os.path.join(upload_dir, unique_filename)
                try:
                    file.save(firma_path)
                except PermissionError:
                    cursor.close()
                    connection.close()
                    return jsonify({
                        'success': False,
                        'message': f'Sin permisos de escritura en carpeta de firmas: {upload_dir}'
                    }), 500

                firma_filename = unique_filename

        cursor.execute(
            "SELECT 1 FROM nextris.tbuser_medical_data WHERE user_id = %s",
            (user_id,)
        )
        exists = cursor.fetchone()

        if exists:
            if firma_filename:
                cursor.execute(
                    """
                    UPDATE nextris.tbuser_medical_data
                    SET aclaracion_firma = %s,
                        matricula_nacional = %s,
                        firma_digital = %s,
                        firma_habilitada = %s,
                        fecha_actualizacion = NOW()
                    WHERE user_id = %s
                    """,
                    (aclaracion_firma, matricula_nacional, firma_filename, firma_habilitada, user_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE nextris.tbuser_medical_data
                    SET aclaracion_firma = %s,
                        matricula_nacional = %s,
                        firma_habilitada = %s,
                        fecha_actualizacion = NOW()
                    WHERE user_id = %s
                    """,
                    (aclaracion_firma, matricula_nacional, firma_habilitada, user_id),
                )
        else:
            cursor.execute(
                """
                INSERT INTO nextris.tbuser_medical_data
                    (user_id, aclaracion_firma, matricula_nacional, firma_digital, firma_habilitada, fecha_creacion, fecha_actualizacion)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (user_id, aclaracion_firma, matricula_nacional, firma_filename, firma_habilitada),
            )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Datos medicos guardados correctamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# RELACIÓN USUARIOS - UBICACIONES
# ====================================================================

@api_blueprint.route('/config/users/<user_id>/locations', methods=['GET'])
@jwt_required()
def get_config_user_locations(user_id):
    """
    Obtiene las ubicaciones asociadas a un usuario

    Path:
    - user_id: GUID del usuario
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

        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        cursor.execute(
            """
            SELECT rul.location_id, l.name, rul.is_default
            FROM nextris.rel_user_location rul
            LEFT JOIN nextris.tblocation l ON l.guid = rul.location_id
            WHERE rul.user_id = %s
            ORDER BY l.name
            """,
            (user_id,)
        )

        results = cursor.fetchall()

        cursor.close()
        connection.close()

        locations = [
            {
                'location_id': row[0],
                'location_name': row[1],
                'is_default': bool(row[2]),
            }
            for row in results
        ]

        return jsonify({
            'success': True,
            'data': locations
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/locations', methods=['PUT', 'PATCH'])
@jwt_required()
def set_config_user_locations(user_id):
    """
    Reemplaza las ubicaciones asociadas a un usuario

    Path:
    - user_id: GUID del usuario

    Body JSON:
    {
        "location_ids": ["guid-1", "guid-2", ...] (required)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        location_ids = data.get('location_ids')

        if not isinstance(location_ids, list):
            return jsonify({
                'success': False,
                'message': 'location_ids debe ser una lista'
            }), 400

        normalized_location_ids = [location_id for location_id in dict.fromkeys(location_ids) if location_id]

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        if normalized_location_ids:
            cursor.execute(
                "SELECT guid FROM nextris.tblocation WHERE guid = ANY(%s)",
                (normalized_location_ids,)
            )
            existing_location_ids = {row[0] for row in cursor.fetchall()}
            missing_location_ids = [location_id for location_id in normalized_location_ids if location_id not in existing_location_ids]

            if missing_location_ids:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'Una o más ubicaciones no existen',
                    'missing_location_ids': missing_location_ids
                }), 400

        cursor.execute(
            "DELETE FROM nextris.rel_user_location WHERE user_id = %s",
            (user_id,)
        )

        if normalized_location_ids:
            insert_query = """
                INSERT INTO nextris.rel_user_location (user_id, location_id, is_default)
                VALUES (%s, %s, %s)
            """
            insert_values = [
                (user_id, location_id, False)
                for location_id in normalized_location_ids
            ]
            cursor.executemany(insert_query, insert_values)

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicaciones de usuario actualizadas exitosamente',
            'data': {
                'user_id': user_id,
                'location_ids': normalized_location_ids,
                'count': len(normalized_location_ids)
            }
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@api_blueprint.route('/config/users/<user_id>/locations', methods=['POST'])
@jwt_required()
def add_user_location(user_id):
    """
    Crea la relación entre un usuario y una ubicación

    Body JSON:
    {
        "location_id": "uuid" (required),
        "is_default": true/false (optional, default: false)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        location_id = data.get('location_id')
        is_default = bool(data.get('is_default', False))

        if not location_id:
            return jsonify({
                'success': False,
                'message': 'location_id es requerido'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (location_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Ubicación no encontrada'
            }), 404

        cursor.execute(
            "SELECT 1 FROM nextris.rel_user_location WHERE user_id=%s AND location_id=%s",
            (user_id, location_id)
        )
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'La relación ya existe'
            }), 409

        if is_default:
            cursor.execute(
                "UPDATE nextris.rel_user_location SET is_default = false WHERE user_id = %s",
                (user_id,)
            )

        cursor.execute(
            """
            INSERT INTO nextris.rel_user_location (user_id, location_id, is_default)
            VALUES (%s, %s, %s)
            """,
            (user_id, location_id, is_default)
        )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicación asociada exitosamente',
            'data': {
                'user_id': user_id,
                'location_id': location_id,
                'is_default': is_default
            }
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/users/<user_id>/locations/<location_id>', methods=['DELETE'])
@jwt_required()
def remove_user_location(user_id, location_id):
    """
    Elimina la relación entre un usuario y una ubicación

    Path:
    - user_id: GUID del usuario
    - location_id: GUID de la ubicación
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

        cursor.execute(
            "SELECT 1 FROM nextris.rel_user_location WHERE user_id=%s AND location_id=%s",
            (user_id, location_id)
        )
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Relación no encontrada'
            }), 404

        cursor.execute(
            "DELETE FROM nextris.rel_user_location WHERE user_id = %s AND location_id = %s",
            (user_id, location_id)
        )

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicación desasociada exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# ROLES
# ====================================================================

@api_blueprint.route('/config/roles', methods=['GET'])
@jwt_required()
def get_roles():
    """
    Obtiene todos los roles del sistema
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "..."
            }
        ]
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
        
        query = "SELECT guid, description FROM nextris.isrole ORDER BY description"
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        roles = []
        for row in results:
            roles.append({
                'guid': row[0],
                'description': row[1]
            })
        
        return jsonify({
            'success': True,
            'data': roles
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# GESTIÓN DE PACIENTES
# ====================================================================

@api_blueprint.route('/config/patients', methods=['GET'])
@jwt_required()
def get_config_patients():
    """
    Obtiene todos los pacientes del sistema
    
    Query Parameters:
    - include_inactive: true/false (opcional, default: false)
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "name": "...",
                "national_code": "...",
                "birthdate": "...",
                "username": "...",
                "status": "...",
                "last_login": "..."
            }
        ]
    }
    """
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        if include_inactive:
            query = """
                SELECT p.guid, CONCAT(dp.surname, ' ', dp.name) as name, 
                       dp.nationalcode, dp.birthdate, p.username, p.status, p.lastlogin
                FROM nextris.tbuser_patient as p
                LEFT JOIN nextris.datapatient dp on dp.guid=p.datapatient_id
                ORDER BY p.guid ASC
            """
        else:
            query = """
                SELECT p.guid, CONCAT(dp.surname, ' ', dp.name) as name, 
                       dp.nationalcode, dp.birthdate, p.username, p.status, p.lastlogin
                FROM nextris.tbuser_patient as p
                LEFT JOIN nextris.datapatient dp on dp.guid=p.datapatient_id
                WHERE p.status = 'Active'
                ORDER BY p.guid ASC
            """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        patients = []
        for row in results:
            patients.append({
                'guid': row[0],
                'name': row[1],
                'national_code': row[2],
                'birthdate': row[3].strftime('%d/%m/%Y') if row[3] else None,
                'username': row[4],
                'status': row[5],
                'last_login': row[6].isoformat() if row[6] else None
            })
        
        return jsonify({
            'success': True,
            'data': patients
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patients/<patient_id>', methods=['GET'])
@jwt_required()
def get_config_patient(patient_id):
    """
    Obtiene los datos completos de un paciente
    
    Returns:
    {
        "success": true,
        "data": {
            "patient_id": "...",
            "username": "...",
            "status": "...",
            "name": "...",
            "surname": "...",
            "national_code": "...",
            "birthdate": "...",
            "patient_id_number": "...",
            "sex_code": "...",
            "phone": "...",
            "email": "..."
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
        
        # Obtener datos de tbuser_patient
        user_query = """
            SELECT username, datapatient_id, status
            FROM nextris.tbuser_patient
            WHERE guid = %s
        """
        cursor.execute(user_query, (patient_id,))
        user_result = cursor.fetchone()
        
        if not user_result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        username = user_result[0]
        datapatient_id = user_result[1]
        status = user_result[2]
        
        # Obtener datos de datapatient
        patient_query = """
            SELECT name, surname, nationalcode, birthdate, patientid, 
                   sexcode, phone, email
            FROM nextris.datapatient
            WHERE guid = %s
        """
        cursor.execute(patient_query, (datapatient_id,))
        patient_result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not patient_result:
            return jsonify({
                'success': False,
                'message': 'Datos del paciente no encontrados'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'patient_id': patient_id,
                'username': username,
                'status': status,
                'name': patient_result[0],
                'surname': patient_result[1],
                'national_code': patient_result[2],
                'birthdate': patient_result[3].strftime('%Y-%m-%d') if patient_result[3] else None,
                'patient_id_number': patient_result[4],  # CUIL
                'sex_code': patient_result[5],
                'phone': patient_result[6],
                'email': patient_result[7]
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patients', methods=['POST'])
@jwt_required()
def create_config_patient():
    """
    Crea un nuevo paciente
    
    Body JSON:
    {
        "name": "string" (required),
        "surname": "string" (required),
        "national_code": "string" (required),
        "birthdate": "YYYY-MM-DD" (required),
        "sex_code": "string" (required),
        "patient_id_number": "string" (optional, CUIL),
        "phone": "string" (optional),
        "email": "string" (optional),
        "username": "string" (optional, se genera automáticamente si no se proporciona),
        "health_card": "string" (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Paciente creado",
        "data": {
            "patient_id": "uuid",
            "username": "...",
            "default_password": "next"
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
        
        name = data.get('name')
        surname = data.get('surname')
        national_code = data.get('national_code')
        birthdate = data.get('birthdate')
        sex_code = data.get('sex_code')
        
        if not all([name, surname, national_code, birthdate, sex_code]):
            return jsonify({
                'success': False,
                'message': 'name, surname, national_code, birthdate y sex_code son requeridos'
            }), 400
        
        patient_id_number = data.get('patient_id_number', '')
        phone = data.get('phone', '')
        email = data.get('email', '')
        health_card = data.get('health_card', '')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Insertar en datapatient
        datapatient_guid = str(uuid.uuid4())
        
        insert_datapatient = """
            INSERT INTO nextris.datapatient(
                guid, surname, name, nationalcode, birthdate, patientid, 
                sexcode, phone, email, healthcard
            ) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING guid
        """
        
        cursor.execute(insert_datapatient, (
            datapatient_guid, surname, name, national_code, birthdate, 
            patient_id_number, sex_code, phone, email, health_card
        ))
        
        # Generar username
        custom_username = data.get('username', '').strip()
        
        if custom_username:
            base_username = custom_username.lower().replace(' ', '')
        else:
            # Generar automáticamente: primera letra del nombre + apellido
            base_username = (name[0] + surname).lower().replace(' ', '')
        
        # Verificar si el username ya existe
        cursor.execute(
            "SELECT COUNT(*) FROM nextris.tbuser_patient WHERE username LIKE %s",
            (f"{base_username}%",)
        )
        count = cursor.fetchone()[0]
        
        if count > 0:
            # Buscar el siguiente número disponible
            for i in range(1, 100):
                test_username = f"{base_username}{i:02d}"
                cursor.execute(
                    "SELECT COUNT(*) FROM nextris.tbuser_patient WHERE username = %s",
                    (test_username,)
                )
                if cursor.fetchone()[0] == 0:
                    username = test_username
                    break
            else:
                username = f"{base_username}{count + 1:02d}"
        else:
            username = base_username
        
        # Hashear contraseña
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash('next')
        
        # Insertar en tbuser_patient
        user_patient_guid = str(uuid.uuid4())
        
        insert_user_patient = """
            INSERT INTO nextris.tbuser_patient (
                guid, username, password, status, datapatient_id
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING guid
        """
        
        cursor.execute(insert_user_patient, (
            user_patient_guid, username, password_hash, 'Active', datapatient_guid
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Paciente creado exitosamente',
            'data': {
                'patient_id': user_patient_guid,
                'username': username,
                'default_password': 'next'
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patients/<patient_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_config_patient(patient_id):
    """
    Actualiza un paciente existente
    
    Body JSON (todos opcionales):
    {
        "username": "string",
        "name": "string",
        "surname": "string",
        "national_code": "string",
        "birthdate": "YYYY-MM-DD",
        "patient_id_number": "string",
        "sex_code": "string",
        "phone": "string",
        "email": "string"
    }
    
    Returns:
    {
        "success": true,
        "message": "Paciente actualizado"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener datapatient_id
        cursor.execute(
            "SELECT datapatient_id FROM nextris.tbuser_patient WHERE guid = %s",
            (patient_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        datapatient_id = result[0]
        
        # Actualizar username si se proporciona
        if 'username' in data:
            cursor.execute(
                "UPDATE nextris.tbuser_patient SET username = %s WHERE guid = %s",
                (data['username'], patient_id)
            )
        
        # Actualizar datos del paciente
        patient_updates = []
        patient_params = []
        
        if 'name' in data:
            patient_updates.append("name = %s")
            patient_params.append(data['name'])
        
        if 'surname' in data:
            patient_updates.append("surname = %s")
            patient_params.append(data['surname'])
        
        if 'national_code' in data:
            patient_updates.append("nationalcode = %s")
            patient_params.append(data['national_code'])
        
        if 'birthdate' in data:
            patient_updates.append("birthdate = %s")
            patient_params.append(data['birthdate'])
        
        if 'patient_id_number' in data:
            patient_updates.append("patientid = %s")
            patient_params.append(data['patient_id_number'])
        
        if 'sex_code' in data:
            patient_updates.append("sexcode = %s")
            patient_params.append(data['sex_code'])
        
        if 'phone' in data:
            patient_updates.append("phone = %s")
            patient_params.append(data['phone'])
        
        if 'email' in data:
            patient_updates.append("email = %s")
            patient_params.append(data['email'])
        
        if patient_updates:
            patient_params.append(datapatient_id)
            query = f"UPDATE nextris.datapatient SET {', '.join(patient_updates)} WHERE guid = %s"
            cursor.execute(query, patient_params)
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Paciente actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patients/<patient_id>/deactivate', methods=['POST'])
@jwt_required()
def deactivate_patient(patient_id):
    """
    Desactiva un paciente
    
    Returns:
    {
        "success": true,
        "message": "Paciente desactivado"
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
        
        # Verificar que existe (patient_id es datapatient.guid)
        cursor.execute("SELECT 1 FROM nextris.tbuser_patient WHERE datapatient_id=%s", (patient_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        query = "UPDATE nextris.tbuser_patient SET status = 'Inactive' WHERE datapatient_id = %s"
        cursor.execute(query, (patient_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Paciente desactivado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patients/<patient_id>/activate', methods=['POST'])
@jwt_required()
def activate_patient(patient_id):
    """
    Activa un paciente. Si no tiene usuario portal, lo crea automáticamente.
    
    Returns:
    {
        "success": true,
        "message": "Paciente activado exitosamente"
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
        
        # patient_id es datapatient.guid
        # Verificar que el paciente existe en datapatient
        cursor.execute("""
            SELECT guid, name, surname FROM nextris.datapatient WHERE guid = %s
        """, (patient_id,))
        patient = cursor.fetchone()
        if not patient:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        # Verificar si ya tiene usuario en tbuser_patient
        cursor.execute(
            "SELECT guid, status FROM nextris.tbuser_patient WHERE datapatient_id=%s",
            (patient_id,)
        )
        user_row = cursor.fetchone()
        
        if user_row:
            # Ya tiene usuario: solo activar
            query = "UPDATE nextris.tbuser_patient SET status = 'Active' WHERE datapatient_id = %s"
            cursor.execute(query, (patient_id,))
            connection.commit()
            cursor.close()
            connection.close()
            return jsonify({
                'success': True,
                'message': 'Paciente activado exitosamente'
            }), 200
        else:
            # No tiene usuario: crearlo y activarlo
            nombre = patient[1].strip() if patient[1] else ''
            apellido = patient[2].strip() if patient[2] else ''
            if not nombre or not apellido:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'El paciente no tiene nombre o apellido registrado'
                }), 400

            base_username = (nombre[0] + apellido).lower().replace(' ', '')
            
            cursor.execute(
                "SELECT username FROM nextris.tbuser_patient WHERE username LIKE %s ORDER BY username",
                (f"{base_username}%",)
            )
            existing_users = cursor.fetchall()
            username = base_username
            if existing_users:
                counter = 1
                while True:
                    test_username = f"{base_username}{counter:02d}"
                    if not any(u[0] == test_username for u in existing_users):
                        username = test_username
                        break
                    counter += 1
            
            from werkzeug.security import generate_password_hash
            password_hash = generate_password_hash('next')
            user_guid = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO nextris.tbuser_patient (guid, username, password, datapatient_id, status, firstlogin)
                VALUES (%s, %s, %s, %s, 'Active', 1)
            """, (user_guid, username, password_hash, patient_id))
            
            connection.commit()
            cursor.close()
            connection.close()
            
            return jsonify({
                'success': True,
                'message': f"Usuario '{username}' creado y activado correctamente",
                'username': username
            }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/patients/<patient_id>/reset-password', methods=['POST'])
@jwt_required()
def reset_patient_password(patient_id):
    """
    Resetea la contraseña de un paciente
    
    Body JSON:
    {
        "new_password": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Contraseña reseteada"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'new_password' not in data:
            return jsonify({
                'success': False,
                'message': 'new_password es requerido'
            }), 400
        
        new_password = data.get('new_password')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el paciente existe
        cursor.execute("SELECT 1 FROM nextris.tbuser_patient WHERE guid=%s", (patient_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        # Hashear la nueva contraseña
        from werkzeug.security import generate_password_hash
        password_hash = generate_password_hash(new_password)
        
        query = "UPDATE nextris.tbuser_patient SET password = %s WHERE guid = %s"
        cursor.execute(query, (password_hash, patient_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Contraseña reseteada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# GESTIÓN DE MÉDICOS SOLICITANTES (REQUESTING PHYSICIANS)
# ====================================================================

@api_blueprint.route('/config/requesting-physicians', methods=['GET'])
@jwt_required()
def get_requesting_physicians():
    """
    Obtiene todos los médicos solicitantes
    
    Query Parameters:
    - location_id: filtrar por localización (opcional)
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "...",
                "phone": "...",
                "mail": "...",
                "note": "...",
                "location_id": "...",
                "location_name": "..."
            }
        ]
    }
    """
    try:
        location_id = request.args.get('location_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT 
                p.guid,
                p.description,
                p.phone,
                p.mail,
                p.note,
                p.location_id,
                l.name as location_name
            FROM nextris.isrequestingphysician p
            LEFT JOIN nextris.tblocation l ON p.location_id = l.guid
        """
        
        params = []
        if location_id:
            query += " WHERE p.location_id = %s"
            params.append(location_id)
        
        query += " ORDER BY p.description"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        physicians = []
        for row in rows:
            physicians.append({
                'guid': row[0],
                'description': row[1],
                'phone': row[2],
                'mail': row[3],
                'note': row[4],
                'location_id': row[5],
                'location_name': row[6]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': physicians
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/requesting-physicians/<physician_id>', methods=['GET'])
@jwt_required()
def get_requesting_physician(physician_id):
    """
    Obtiene un médico solicitante por ID
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "...",
            "description": "...",
            "phone": "...",
            "mail": "...",
            "note": "...",
            "location_id": "...",
            "location_name": "..."
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
            SELECT 
                p.guid,
                p.description,
                p.phone,
                p.mail,
                p.note,
                p.location_id,
                l.name as location_name
            FROM nextris.isrequestingphysician p
            LEFT JOIN nextris.tblocation l ON p.location_id = l.guid
            WHERE p.guid = %s
        """
        
        cursor.execute(query, (physician_id,))
        row = cursor.fetchone()
        
        if not row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Médico solicitante no encontrado'
            }), 404
        
        physician = {
            'guid': row[0],
            'description': row[1],
            'phone': row[2],
            'mail': row[3],
            'note': row[4],
            'location_id': row[5],
            'location_name': row[6]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': physician
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/requesting-physicians', methods=['POST'])
@jwt_required()
def create_requesting_physician():
    """
    Crea un nuevo médico solicitante
    
    Request Body:
    {
        "description": "Dr. Juan Pérez",  // requerido
        "phone": "+1234567890",           // opcional
        "mail": "juan.perez@example.com", // opcional
        "note": "Especialidad",           // opcional
        "location_id": "guid"             // opcional
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "...",
            "description": "...",
            ...
        },
        "message": "Médico solicitante creado exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'description' not in data:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400
        
        description = data.get('description', '').strip()
        phone = data.get('phone', '').strip()
        mail = data.get('mail', '').strip()
        note = data.get('note', '').strip()
        location_id = data.get('location_id')
        
        if not description:
            return jsonify({
                'success': False,
                'message': 'description no puede estar vacío'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar si el location_id existe (si se proporciona)
        if location_id:
            cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (location_id,))
            if not cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'La localización especificada no existe'
                }), 400
        
        # Generar GUID
        import uuid
        physician_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isrequestingphysician 
            (guid, description, phone, mail, note, location_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            physician_guid,
            description,
            phone if phone else None,
            mail if mail else None,
            note if note else None,
            location_id if location_id else None
        ))
        
        connection.commit()
        
        # Obtener el médico creado con información de localización
        cursor.execute("""
            SELECT 
                p.guid,
                p.description,
                p.phone,
                p.mail,
                p.note,
                p.location_id,
                l.name as location_name
            FROM nextris.isrequestingphysician p
            LEFT JOIN nextris.tblocation l ON p.location_id = l.guid
            WHERE p.guid = %s
        """, (physician_guid,))
        
        row = cursor.fetchone()
        physician = {
            'guid': row[0],
            'description': row[1],
            'phone': row[2],
            'mail': row[3],
            'note': row[4],
            'location_id': row[5],
            'location_name': row[6]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': physician,
            'message': 'Médico solicitante creado exitosamente'
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/requesting-physicians/<physician_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_requesting_physician(physician_id):
    """
    Actualiza un médico solicitante existente
    
    Request Body:
    {
        "description": "Dr. Juan Pérez",  // opcional
        "phone": "+1234567890",           // opcional
        "mail": "juan.perez@example.com", // opcional
        "note": "Especialidad",           // opcional
        "location_id": "guid"             // opcional (null para quitar)
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "...",
            "description": "...",
            ...
        },
        "message": "Médico solicitante actualizado exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No se proporcionaron datos para actualizar'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el médico existe
        cursor.execute("SELECT 1 FROM nextris.isrequestingphysician WHERE guid=%s", (physician_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Médico solicitante no encontrado'
            }), 404
        
        # Verificar location_id si se proporciona
        if 'location_id' in data and data['location_id']:
            cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (data['location_id'],))
            if not cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'La localización especificada no existe'
                }), 400
        
        # Construir query de actualización
        update_fields = []
        params = []
        
        if 'description' in data:
            update_fields.append("description = %s")
            params.append(data['description'].strip())
        
        if 'phone' in data:
            update_fields.append("phone = %s")
            params.append(data['phone'].strip() if data['phone'] else None)
        
        if 'mail' in data:
            update_fields.append("mail = %s")
            params.append(data['mail'].strip() if data['mail'] else None)
        
        if 'note' in data:
            update_fields.append("note = %s")
            params.append(data['note'].strip() if data['note'] else None)
        
        if 'location_id' in data:
            update_fields.append("location_id = %s")
            params.append(data['location_id'] if data['location_id'] else None)
        
        if not update_fields:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No se proporcionaron campos válidos para actualizar'
            }), 400
        
        params.append(physician_id)
        query = f"UPDATE nextris.isrequestingphysician SET {', '.join(update_fields)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        # Obtener el médico actualizado
        cursor.execute("""
            SELECT 
                p.guid,
                p.description,
                p.phone,
                p.mail,
                p.note,
                p.location_id,
                l.name as location_name
            FROM nextris.isrequestingphysician p
            LEFT JOIN nextris.tblocation l ON p.location_id = l.guid
            WHERE p.guid = %s
        """, (physician_id,))
        
        row = cursor.fetchone()
        physician = {
            'guid': row[0],
            'description': row[1],
            'phone': row[2],
            'mail': row[3],
            'note': row[4],
            'location_id': row[5],
            'location_name': row[6]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': physician,
            'message': 'Médico solicitante actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/requesting-physicians/<physician_id>', methods=['DELETE'])
@jwt_required()
def delete_requesting_physician(physician_id):
    """
    Elimina un médico solicitante
    
    Returns:
    {
        "success": true,
        "message": "Médico solicitante eliminado exitosamente"
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
        
        # Verificar que el médico existe
        cursor.execute("SELECT 1 FROM nextris.isrequestingphysician WHERE guid=%s", (physician_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Médico solicitante no encontrado'
            }), 404
        
        query = "DELETE FROM nextris.isrequestingphysician WHERE guid = %s"
        cursor.execute(query, (physician_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Médico solicitante eliminado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# GESTIÓN DE AGENDAS DE MÉDICOS
# ====================================================================

@api_blueprint.route('/config/physician-schedules', methods=['GET'])
@jwt_required()
def get_physician_schedules():
    """
    Obtiene todas las agendas de médicos
    
    Query Parameters:
    - physician_id: filtrar por médico (opcional)
    - location_id: filtrar por localización (opcional)
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "physician_id": "...",
                "physician_name": "...",
                "day": "Lunes",
                "time_from": "08:00",
                "time_to": "12:00",
                "init_day": "2024-01-01",
                "finish_day": "2024-12-31",
                "location_id": "...",
                "location_name": "..."
            }
        ]
    }
    """
    try:
        physician_id = request.args.get('physician_id')
        location_id = request.args.get('location_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT 
                a.guid,
                a.idmed as physician_id,
                CONCAT(u.name, ' ', u.surname) as physician_name,
                a.day,
                a.timefrom,
                a.timeto,
                a.initday,
                a.finishday,
                a.location_id,
                l.name as location_name
            FROM nextris.isagendameditem a
            LEFT JOIN nextris.tbuser u ON a.idmed = u.guid
            LEFT JOIN nextris.tblocation l ON a.location_id = l.guid
            WHERE 1=1
        """
        
        params = []
        if physician_id:
            query += " AND a.idmed = %s"
            params.append(physician_id)
        
        if location_id:
            query += " AND a.location_id = %s"
            params.append(location_id)
        
        query += " ORDER BY u.name, u.surname, a.day, a.timefrom"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        schedules = []
        for row in rows:
            schedules.append({
                'guid': row[0],
                'physician_id': row[1],
                'physician_name': row[2],
                'day': row[3],
                'time_from': str(row[4]) if row[4] else None,
                'time_to': str(row[5]) if row[5] else None,
                'init_day': str(row[6]) if row[6] else None,
                'finish_day': str(row[7]) if row[7] else None,
                'location_id': row[8],
                'location_name': row[9]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': schedules
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/physician-schedules', methods=['POST'])
@jwt_required()
def create_physician_schedule():
    """
    Crea una nueva agenda para un médico
    
    Request Body:
    {
        "physician_id": "guid",    // requerido
        "day": "Lunes",            // requerido
        "time_from": "08:00",      // requerido
        "time_to": "12:00",        // requerido
        "init_day": "2024-01-01",  // opcional
        "finish_day": "2024-12-31",// opcional
        "location_id": "guid"      // opcional
    }
    
    Returns:
    {
        "success": true,
        "data": {...},
        "message": "Agenda creada exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        required_fields = ['physician_id', 'day', 'time_from', 'time_to']
        for field in required_fields:
            if not data or field not in data:
                return jsonify({
                    'success': False,
                    'message': f'{field} es requerido'
                }), 400
        
        physician_id = data.get('physician_id')
        day = data.get('day', '').strip()
        time_from = data.get('time_from', '').strip()
        time_to = data.get('time_to', '').strip()
        init_day = data.get('init_day')
        finish_day = data.get('finish_day')
        location_id = data.get('location_id')
        
        # Validar día de la semana
        valid_days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        if day not in valid_days:
            return jsonify({
                'success': False,
                'message': f'Día inválido. Debe ser uno de: {", ".join(valid_days)}'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el médico existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (physician_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Médico no encontrado'
            }), 404
        
        # Verificar location_id si se proporciona
        if location_id:
            cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (location_id,))
            if not cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'La localización especificada no existe'
                }), 400
        
        # Generar GUID
        import uuid
        schedule_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.isagendameditem 
            (guid, idmed, day, timefrom, timeto, initday, finishday, location_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            schedule_guid,
            physician_id,
            day,
            time_from,
            time_to,
            init_day if init_day else None,
            finish_day if finish_day else None,
            location_id if location_id else None
        ))
        
        connection.commit()
        
        # Obtener la agenda creada
        cursor.execute("""
            SELECT 
                a.guid,
                a.idmed as physician_id,
                CONCAT(u.name, ' ', u.surname) as physician_name,
                a.day,
                a.timefrom,
                a.timeto,
                a.initday,
                a.finishday,
                a.location_id,
                l.name as location_name
            FROM nextris.isagendameditem a
            LEFT JOIN nextris.tbuser u ON a.idmed = u.guid
            LEFT JOIN nextris.tblocation l ON a.location_id = l.guid
            WHERE a.guid = %s
        """, (schedule_guid,))
        
        row = cursor.fetchone()
        schedule = {
            'guid': row[0],
            'physician_id': row[1],
            'physician_name': row[2],
            'day': row[3],
            'time_from': str(row[4]) if row[4] else None,
            'time_to': str(row[5]) if row[5] else None,
            'init_day': str(row[6]) if row[6] else None,
            'finish_day': str(row[7]) if row[7] else None,
            'location_id': row[8],
            'location_name': row[9]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': schedule,
            'message': 'Agenda creada exitosamente'
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/physician-schedules/<schedule_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_physician_schedule(schedule_id):
    """
    Actualiza una agenda de médico existente
    
    Request Body:
    {
        "day": "Lunes",            // opcional
        "time_from": "08:00",      // opcional
        "time_to": "12:00",        // opcional
        "init_day": "2024-01-01",  // opcional
        "finish_day": "2024-12-31",// opcional
        "location_id": "guid"      // opcional
    }
    
    Returns:
    {
        "success": true,
        "data": {...},
        "message": "Agenda actualizada exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No se proporcionaron datos para actualizar'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que la agenda existe
        cursor.execute("SELECT 1 FROM nextris.isagendameditem WHERE guid=%s", (schedule_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Agenda no encontrada'
            }), 404
        
        # Validar día si se proporciona
        if 'day' in data:
            valid_days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
            if data['day'] not in valid_days:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': f'Día inválido. Debe ser uno de: {", ".join(valid_days)}'
                }), 400
        
        # Verificar location_id si se proporciona
        if 'location_id' in data and data['location_id']:
            cursor.execute("SELECT 1 FROM nextris.tblocation WHERE guid=%s", (data['location_id'],))
            if not cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'La localización especificada no existe'
                }), 400
        
        # Construir query de actualización
        update_fields = []
        params = []
        
        if 'day' in data:
            update_fields.append("day = %s")
            params.append(data['day'])
        
        if 'time_from' in data:
            update_fields.append("timefrom = %s")
            params.append(data['time_from'])
        
        if 'time_to' in data:
            update_fields.append("timeto = %s")
            params.append(data['time_to'])
        
        if 'init_day' in data:
            update_fields.append("initday = %s")
            params.append(data['init_day'] if data['init_day'] else None)
        
        if 'finish_day' in data:
            update_fields.append("finishday = %s")
            params.append(data['finish_day'] if data['finish_day'] else None)
        
        if 'location_id' in data:
            update_fields.append("location_id = %s")
            params.append(data['location_id'] if data['location_id'] else None)
        
        if not update_fields:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No se proporcionaron campos válidos para actualizar'
            }), 400
        
        params.append(schedule_id)
        query = f"UPDATE nextris.isagendameditem SET {', '.join(update_fields)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        # Obtener la agenda actualizada
        cursor.execute("""
            SELECT 
                a.guid,
                a.idmed as physician_id,
                CONCAT(u.name, ' ', u.surname) as physician_name,
                a.day,
                a.timefrom,
                a.timeto,
                a.initday,
                a.finishday,
                a.location_id,
                l.name as location_name
            FROM nextris.isagendameditem a
            LEFT JOIN nextris.tbuser u ON a.idmed = u.guid
            LEFT JOIN nextris.tblocation l ON a.location_id = l.guid
            WHERE a.guid = %s
        """, (schedule_id,))
        
        row = cursor.fetchone()
        schedule = {
            'guid': row[0],
            'physician_id': row[1],
            'physician_name': row[2],
            'day': row[3],
            'time_from': str(row[4]) if row[4] else None,
            'time_to': str(row[5]) if row[5] else None,
            'init_day': str(row[6]) if row[6] else None,
            'finish_day': str(row[7]) if row[7] else None,
            'location_id': row[8],
            'location_name': row[9]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': schedule,
            'message': 'Agenda actualizada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/physician-schedules/<schedule_id>', methods=['DELETE'])
@jwt_required()
def delete_physician_schedule(schedule_id):
    """
    Elimina una agenda de médico
    
    Returns:
    {
        "success": true,
        "message": "Agenda eliminada exitosamente"
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
        
        # Verificar que la agenda existe
        cursor.execute("SELECT 1 FROM nextris.isagendameditem WHERE guid=%s", (schedule_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Agenda no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.isagendameditem WHERE guid = %s"
        cursor.execute(query, (schedule_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Agenda eliminada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# GESTIÓN DE GRUPOS DE ESTUDIO POR MÉDICO
# ====================================================================

@api_blueprint.route('/config/physicians/<physician_id>/study-groups', methods=['GET'])
@jwt_required()
def get_physician_study_groups(physician_id):
    """
    Obtiene los grupos de estudio que lee un médico
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "studygroup_id": "...",
                "studygroup_name": "..."
            }
        ]
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
            SELECT 
                r.guid,
                r.studygroup_id,
                g.description as studygroup_name
            FROM nextris.rel_medico_studygroup r
            LEFT JOIN nextris.isstudytypegroup g ON r.studygroup_id = g.guid
            WHERE r.med_id = %s
            ORDER BY g.description
        """
        
        cursor.execute(query, (physician_id,))
        rows = cursor.fetchall()
        
        study_groups = []
        for row in rows:
            study_groups.append({
                'guid': row[0],
                'studygroup_id': row[1],
                'studygroup_name': row[2]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': study_groups
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/physicians/<physician_id>/study-groups', methods=['POST'])
@jwt_required()
def add_physician_study_group(physician_id):
    """
    Agrega un grupo de estudio a un médico
    
    Request Body:
    {
        "studygroup_id": "guid"  // requerido
    }
    
    Returns:
    {
        "success": true,
        "data": {...},
        "message": "Grupo de estudio agregado exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'studygroup_id' not in data:
            return jsonify({
                'success': False,
                'message': 'studygroup_id es requerido'
            }), 400
        
        studygroup_id = data.get('studygroup_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el médico existe
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid=%s", (physician_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Médico no encontrado'
            }), 404
        
        # Verificar que el grupo de estudio existe
        cursor.execute("SELECT 1 FROM nextris.isstudytypegroup WHERE guid=%s", (studygroup_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Grupo de estudio no encontrado'
            }), 404
        
        # Verificar que la relación no existe ya
        cursor.execute(
            "SELECT 1 FROM nextris.rel_medico_studygroup WHERE med_id=%s AND studygroup_id=%s",
            (physician_id, studygroup_id)
        )
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'El médico ya tiene asignado este grupo de estudio'
            }), 400
        
        # Generar GUID
        import uuid
        relation_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.rel_medico_studygroup 
            (guid, med_id, studygroup_id)
            VALUES (%s, %s, %s)
        """
        
        cursor.execute(query, (relation_guid, physician_id, studygroup_id))
        connection.commit()
        
        # Obtener la relación creada
        cursor.execute("""
            SELECT 
                r.guid,
                r.studygroup_id,
                g.description as studygroup_name
            FROM nextris.rel_medico_studygroup r
            LEFT JOIN nextris.isstudytypegroup g ON r.studygroup_id = g.guid
            WHERE r.guid = %s
        """, (relation_guid,))
        
        row = cursor.fetchone()
        relation = {
            'guid': row[0],
            'studygroup_id': row[1],
            'studygroup_name': row[2]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': relation,
            'message': 'Grupo de estudio agregado exitosamente'
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/physicians/<physician_id>/study-groups/<relation_id>', methods=['DELETE'])
@jwt_required()
def remove_physician_study_group(physician_id, relation_id):
    """
    Elimina un grupo de estudio de un médico
    
    Returns:
    {
        "success": true,
        "message": "Grupo de estudio eliminado exitosamente"
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
        
        # Verificar que la relación existe y pertenece al médico
        cursor.execute(
            "SELECT 1 FROM nextris.rel_medico_studygroup WHERE guid=%s AND med_id=%s",
            (relation_id, physician_id)
        )
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Relación no encontrada'
            }), 404
        
        query = "DELETE FROM nextris.rel_medico_studygroup WHERE guid = %s"
        cursor.execute(query, (relation_id,))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Grupo de estudio eliminado exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# OBRAS SOCIALES (HEALTH INSURANCES)
# ====================================================================

@api_blueprint.route('/config/insurances', methods=['GET'])
@jwt_required()
def get_insurances():
    """
    Obtiene todas las obras sociales

    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "OSDE",
                "isactive": 1,
                "externalcode": "...",
                "headerdescription": "..."
            }
        ]
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
            SELECT guid, description, isactive, externalcode, headerdescription
            FROM nextris.ishealthinsurances
            ORDER BY description
        """
        cursor.execute(query)
        results = cursor.fetchall()

        cursor.close()
        connection.close()

        insurances = []
        for row in results:
            insurances.append({
                'guid': row[0],
                'description': row[1],
                'isactive': row[2],
                'externalcode': row[3],
                'headerdescription': row[4]
            })

        return jsonify({
            'success': True,
            'data': insurances
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/insurances', methods=['POST'])
@jwt_required()
def create_insurance():
    """
    Crea una nueva obra social

    Body JSON:
    {
        "description": "string" (required),
        "externalcode": "string" (optional),
        "headerdescription": "string" (optional)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        description = data.get('description')

        if not description:
            return jsonify({
                'success': False,
                'message': 'description es requerido'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        new_guid = str(uuid.uuid4())

        query = """
            INSERT INTO nextris.ishealthinsurances (guid, description, isactive, externalcode, headerdescription)
            VALUES (%s, %s, 1, %s, %s)
        """

        cursor.execute(query, (
            new_guid,
            description,
            data.get('externalcode'),
            data.get('headerdescription')
        ))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Obra social creada exitosamente',
            'data': {
                'guid': new_guid
            }
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/insurances/<insurance_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_insurance(insurance_id):
    """
    Actualiza una obra social existente

    Path:
    - insurance_id: GUID de la obra social

    Body JSON:
    {
        "description": "string",
        "isactive": 1|0,
        "externalcode": "string",
        "headerdescription": "string"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.ishealthinsurances WHERE guid=%s", (insurance_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Obra social no encontrada'
            }), 404

        update_fields = []
        values = []

        allowed_fields = {
            'description': 'description',
            'isactive': 'isactive',
            'externalcode': 'externalcode',
            'headerdescription': 'headerdescription'
        }

        for json_field, db_field in allowed_fields.items():
            if json_field in data:
                update_fields.append(f"{db_field} = %s")
                values.append(data[json_field])

        if not update_fields:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400

        values.append(insurance_id)
        query = f"UPDATE nextris.ishealthinsurances SET {', '.join(update_fields)} WHERE guid = %s"

        cursor.execute(query, values)
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Obra social actualizada exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/insurances/<insurance_id>', methods=['DELETE'])
@jwt_required()
def delete_insurance(insurance_id):
    """
    Elimina una obra social y sus relaciones con ubicaciones

    Path:
    - insurance_id: GUID de la obra social
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

        cursor.execute("SELECT 1 FROM nextris.ishealthinsurances WHERE guid=%s", (insurance_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Obra social no encontrada'
            }), 404

        # Eliminar relaciones con ubicaciones
        cursor.execute("DELETE FROM nextris.rel_insurance_location WHERE insurance_id = %s", (insurance_id,))

        # Eliminar la obra social
        cursor.execute("DELETE FROM nextris.ishealthinsurances WHERE guid = %s", (insurance_id,))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Obra social eliminada exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# RELACIÓN OBRAS SOCIALES - UBICACIONES
# ====================================================================

@api_blueprint.route('/config/insurances/<insurance_id>/locations', methods=['GET'])
@jwt_required()
def get_insurance_locations(insurance_id):
    """
    Obtiene las ubicaciones asociadas a una obra social

    Path:
    - insurance_id: GUID de la obra social

    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "rel-guid",
                "location_id": "...",
                "location_name": "...",
                "is_default": false
            }
        ]
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
            SELECT ril.guid, ril.location_id, l.name as location_name, ril.is_default
            FROM nextris.rel_insurance_location ril
            LEFT JOIN nextris.tblocation l ON l.guid = ril.location_id
            WHERE ril.insurance_id = %s
            ORDER BY l.name
        """
        cursor.execute(query, (insurance_id,))
        results = cursor.fetchall()

        cursor.close()
        connection.close()

        locations = []
        for row in results:
            locations.append({
                'guid': row[0],
                'location_id': row[1],
                'location_name': row[2],
                'is_default': row[3]
            })

        return jsonify({
            'success': True,
            'data': locations
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/insurances/<insurance_id>/locations', methods=['POST'])
@jwt_required()
def add_insurance_location(insurance_id):
    """
    Agrega una relación entre una obra social y una ubicación

    Path:
    - insurance_id: GUID de la obra social

    Body JSON:
    {
        "location_id": "string" (required),
        "is_default": false (optional)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        location_id = data.get('location_id')

        if not location_id:
            return jsonify({
                'success': False,
                'message': 'location_id es requerido'
            }), 400

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        # Verificar que la obra social existe
        cursor.execute("SELECT 1 FROM nextris.ishealthinsurances WHERE guid=%s", (insurance_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Obra social no encontrada'
            }), 404

        # Verificar que no exista ya la relación
        cursor.execute(
            "SELECT 1 FROM nextris.rel_insurance_location WHERE insurance_id=%s AND location_id=%s",
            (insurance_id, location_id)
        )
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'La relación ya existe'
            }), 409

        new_guid = str(uuid.uuid4())
        is_default = data.get('is_default', False)

        query = """
            INSERT INTO nextris.rel_insurance_location (guid, insurance_id, location_id, is_default)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (new_guid, insurance_id, location_id, is_default))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicación asociada exitosamente',
            'data': {
                'guid': new_guid
            }
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/insurances/<insurance_id>/locations', methods=['PUT', 'PATCH'])
@jwt_required()
def set_insurance_locations(insurance_id):
    """
    Reemplaza las ubicaciones asociadas a una obra social

    Path:
    - insurance_id: GUID de la obra social

    Body JSON:
    {
        "location_ids": ["guid-1", "guid-2", ...] (required)
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        location_ids = data.get('location_ids')

        if not isinstance(location_ids, list):
            return jsonify({
                'success': False,
                'message': 'location_ids debe ser una lista'
            }), 400

        normalized_location_ids = [location_id for location_id in dict.fromkeys(location_ids) if location_id]

        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500

        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        cursor.execute("SELECT 1 FROM nextris.ishealthinsurances WHERE guid=%s", (insurance_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Obra social no encontrada'
            }), 404

        if normalized_location_ids:
            cursor.execute(
                "SELECT guid FROM nextris.tblocation WHERE guid = ANY(%s)",
                (normalized_location_ids,)
            )
            existing_location_ids = {row[0] for row in cursor.fetchall()}
            missing_location_ids = [location_id for location_id in normalized_location_ids if location_id not in existing_location_ids]

            if missing_location_ids:
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'Una o más ubicaciones no existen',
                    'missing_location_ids': missing_location_ids
                }), 400

        cursor.execute(
            "DELETE FROM nextris.rel_insurance_location WHERE insurance_id = %s",
            (insurance_id,)
        )

        if normalized_location_ids:
            insert_query = """
                INSERT INTO nextris.rel_insurance_location (guid, insurance_id, location_id, is_default)
                VALUES (%s, %s, %s, %s)
            """
            insert_values = [
                (str(uuid.uuid4()), insurance_id, location_id, False)
                for location_id in normalized_location_ids
            ]
            cursor.executemany(insert_query, insert_values)

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicaciones actualizadas exitosamente',
            'data': {
                'insurance_id': insurance_id,
                'location_ids': normalized_location_ids,
                'count': len(normalized_location_ids)
            }
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/config/insurances/<insurance_id>/locations/<relation_id>', methods=['DELETE'])
@jwt_required()
def remove_insurance_location(insurance_id, relation_id):
    """
    Elimina la relación entre una obra social y una ubicación

    Path:
    - insurance_id: GUID de la obra social
    - relation_id: GUID de la relación en rel_insurance_location
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

        cursor.execute(
            "SELECT 1 FROM nextris.rel_insurance_location WHERE guid=%s AND insurance_id=%s",
            (relation_id, insurance_id)
        )
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Relación no encontrada'
            }), 404

        cursor.execute("DELETE FROM nextris.rel_insurance_location WHERE guid = %s", (relation_id,))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Ubicación desasociada exitosamente'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# APP CONFIG (GLOBAL CONFIGURATION)
# ====================================================================

@api_blueprint.route('/app-config', methods=['GET'])
def get_app_config_endpoint():
    try:
        config_data = get_app_config()
        if not config_data:
            return jsonify({
                'success': False,
                'message': 'Configuración no encontrada'
            }), 404

        return jsonify({
            'success': True,
            'data': config_data
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/app-config', methods=['PUT'])
@jwt_required()
def update_app_config_endpoint():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400

        updated = update_app_config(data)

        return jsonify({
            'success': True,
            'message': 'Configuración actualizada exitosamente',
            'data': updated
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500



# =============================================================
# ENDPOINTS FALTANTES PARA FRONTEND
# =============================================================

@api_blueprint.route('/config/me/modules', methods=['GET'])
@jwt_required()
def get_user_modules():
    """Retorna los módulos activos del usuario actual."""
    try:
        current_user = get_jwt_identity()
        user_id = normalize_user_id(current_user)
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener todos los módulos activos (simplificado - sin facility check)
        cursor.execute("""
            SELECT code FROM nextris.ismodule WHERE is_active = TRUE
        """)
        module_codes = [row[0] for row in cursor.fetchall()]
        
        # Obtener locations del usuario
        cursor.execute("""
            SELECT location_id FROM nextris.rel_user_location WHERE user_id = %s
        """, (user_id,))
        facility_ids = [str(row[0]) for row in cursor.fetchall()]
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'module_codes': module_codes,
                'facility_ids': facility_ids,
                'user_facilities_count': len(facility_ids),
                'total_facilities': len(facility_ids),
                'has_all_facilities': False
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_blueprint.route('/config/dashboard/plan-usage-summary', methods=['GET'])
@jwt_required()
def get_dashboard_plan_usage_summary():
    """Retorna resumen de uso del plan para el dashboard."""
    try:
        return jsonify({
            'success': True,
            'data': {
                'received': {'used': 0, 'limit': None, 'percentage': 0},
                'read': {'used': 0, 'limit': None, 'percentage': 0},
                'distributed': {'used': 0, 'limit': None, 'percentage': 0},
                'plan_name': 'Sin plan',
                'plan_code': 'none'
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_blueprint.route('/config/facilities/<facility_id>/plan', methods=['GET'])
@jwt_required()
def get_facility_plan(facility_id):
    """Retorna el plan de una facility."""
    try:
        return jsonify({
            'success': True,
            'data': {
                'facility_id': facility_id,
                'plan': {
                    'code': 'free',
                    'name': 'Free',
                    'description': 'Plan gratuito',
                    'max_receive_monthly': 50,
                    'max_read_monthly': 30,
                    'max_distribute_monthly': 30,
                    'dicom_retention_days': 30,
                    'max_users': 5
                },
                'usage': {
                    'received': 0,
                    'read': 0,
                    'distributed': 0
                }
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
