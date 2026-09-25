# -*- encoding: utf-8 -*-
"""
Utilidades de permisos para API JWT.
"""

from functools import wraps
import uuid
import unicodedata

import psycopg2
from flask import jsonify
from flask_jwt_extended import get_jwt_identity

from apps.api.utils import get_db_config


PERMISSION_CATALOG = [
    # Permisos de pestañas/módulos
    {'code': 'tabs.patients.view', 'module': 'patients', 'action': 'view', 'description': 'Ver pestaña Pacientes'},
    {'code': 'tabs.appointments.view', 'module': 'appointments', 'action': 'view', 'description': 'Ver pestaña Citas'},
    {'code': 'tabs.admissions.view', 'module': 'admissions', 'action': 'view', 'description': 'Ver pestaña Admisión'},
    {'code': 'tabs.worklist.view', 'module': 'worklist', 'action': 'view', 'description': 'Ver Lista de trabajo'},
    {'code': 'tabs.distribution.view', 'module': 'distribution', 'action': 'view', 'description': 'Ver pestaña Distribución'},
    {'code': 'tabs.config.view', 'module': 'config', 'action': 'view', 'description': 'Ver pestaña Configuración'},
    {'code': 'tabs.gestion.view', 'module': 'gestion', 'action': 'view', 'description': 'Ver pestaña Gestión'},
    {'code': 'tabs.images.view', 'module': 'images', 'action': 'view', 'description': 'Ver pestaña Imágenes'},
    # structured_reports — deshabilitado temporalmente
    # {'code': 'tabs.structured_reports.view', 'module': 'structured_reports', 'action': 'view', 'description': 'Ver pestaña Reportes estructurados'},
    # nexi — deshabilitado temporalmente
    # {'code': 'tabs.nexi.view', 'module': 'nexi', 'action': 'view', 'description': 'Ver pestaña Nexi'},
    # Permisos de acciones
    {'code': 'reports.sign', 'module': 'reports', 'action': 'sign', 'description': 'Firmar informe'},
    {'code': 'reports.unsign', 'module': 'reports', 'action': 'unsign', 'description': 'Desfirmar informe'},
    {'code': 'distribution.send_report', 'module': 'distribution', 'action': 'send_report', 'description': 'Enviar informe por email'},
    {'code': 'distribution.send_report_whatsapp', 'module': 'distribution', 'action': 'send_report_whatsapp', 'description': 'Enviar informe por WhatsApp'},
    {'code': 'distribution.update_email', 'module': 'distribution', 'action': 'update_email', 'description': 'Actualizar email para distribución'},
    {'code': 'users.manage', 'module': 'users', 'action': 'manage', 'description': 'Gestionar usuarios'},
    {'code': 'users.impersonate', 'module': 'users', 'action': 'impersonate', 'description': 'Conectarse como otro usuario del personal'},
    {'code': 'users.permissions.manage', 'module': 'users', 'action': 'manage_permissions', 'description': 'Gestionar permisos de usuarios'},

    # Permisos solicitados para flujo operativo
    {'code': 'admissions.view', 'module': 'admissions', 'action': 'view', 'description': 'Ver admisiones'},
    {'code': 'admissions.create_spontaneous', 'module': 'admissions', 'action': 'create_spontaneous', 'description': 'Generar admisión espontánea'},
    {'code': 'admissions.admit_appointments', 'module': 'admissions', 'action': 'admit_appointments', 'description': 'Admisionar citas'},

    {'code': 'appointments.view', 'module': 'appointments', 'action': 'view', 'description': 'Ver citas'},
    {'code': 'appointments.create', 'module': 'appointments', 'action': 'create', 'description': 'Generar citas'},

    {'code': 'distribution.view', 'module': 'distribution', 'action': 'view', 'description': 'Ver pestaña Distribución'},
    {'code': 'distribution.perform', 'module': 'distribution', 'action': 'perform', 'description': 'Hacer la distribución'},

    {'code': 'worklist.confirm_execute', 'module': 'worklist', 'action': 'confirm_execute', 'description': 'Confirmar o ejecutar estudios'},
    {'code': 'worklist.link_missing_images', 'module': 'worklist', 'action': 'link_missing_images', 'description': 'Vincular imágenes faltantes desde la Lista de trabajo'},

    {'code': 'patients.view', 'module': 'patients', 'action': 'view', 'description': 'Ver pacientes'},
    {'code': 'patients.manage', 'module': 'patients', 'action': 'manage', 'description': 'Generar nuevos pacientes / editar pacientes'},

    {'code': 'images.view', 'module': 'images', 'action': 'view', 'description': 'Ver imágenes DICOM'},
    {'code': 'images.share_link', 'module': 'images', 'action': 'share_link', 'description': 'Generar enlace compartido de imágenes'},

    {'code': 'reports.write', 'module': 'reports', 'action': 'write', 'description': 'Redactar informes'},
    {'code': 'templates.manage', 'module': 'templates', 'action': 'manage', 'description': 'Gestionar informes predefinidos'},
    {'code': 'dicom.studies.manage', 'module': 'dicom', 'action': 'manage_studies', 'description': 'Cargar, vincular y desvincular estudios DICOM'},
    {'code': 'reports.assign', 'module': 'reports', 'action': 'assign', 'description': 'Asignar estudio a un usuario'},
    {'code': 'reports.notes.delete', 'module': 'reports', 'action': 'delete_notes', 'description': 'Eliminar notas de estudios'},
]


DEPRECATED_PERMISSION_ALIASES = {
    # Backward compatibility for renamed permissions.
    'tabs.preferences.view': 'tabs.gestion.view',
    'tabs.execution.view': 'tabs.worklist.view',
    'execution.view_pending': 'tabs.worklist.view',
    'execution.execute': 'worklist.confirm_execute',
    'tabs.reports.view': 'tabs.worklist.view',
    'reports.view_writing': 'reports.write',
    'reports.view_reports': 'templates.manage',
}


def normalize_permission_code(code):
    if not code:
        return code
    return DEPRECATED_PERMISSION_ALIASES.get(code, code)


def normalize_permission_codes(permission_codes):
    normalized = []
    seen = set()

    for code in permission_codes or []:
        normalized_code = normalize_permission_code(code)
        if normalized_code == '*':
            # '*' es un permiso efectivo por rol, no un permiso personalizado persistible.
            continue
        if not normalized_code or normalized_code in seen:
            continue
        seen.add(normalized_code)
        normalized.append(normalized_code)

    return normalized


ROLE_BASED_PERMISSIONS = {
    'sysadmin': {'*'},
    'administrativo': {
        'tabs.patients.view',
        'tabs.appointments.view',
        'tabs.admissions.view',
        'tabs.distribution.view',
        'tabs.worklist.view',
        'images.view',
        'images.share_link',
    },
    'administrador': {
        'images.view',
        'images.share_link',
        'worklist.link_missing_images',
    },
    'admin': {
        'worklist.link_missing_images',
    },
    'tecnico': {
        'tabs.patients.view',
        'patients.view',
        'tabs.worklist.view',
        'worklist.confirm_execute',
        'tabs.images.view',
        'images.view',
    },
    'medico': {
        'tabs.patients.view',
        'patients.view',
        'patients.manage',
        'tabs.admissions.view',
        'admissions.view',
        'admissions.create_spontaneous',
        'tabs.worklist.view',
        'reports.write',
        'templates.manage',
        'dicom.studies.manage',
        'tabs.gestion.view',
        'reports.sign',
        'reports.assign',
        'tabs.images.view',
        'images.view',
        'tabs.distribution.view',
        'distribution.view',
        'distribution.perform',
        'distribution.send_report',
        'distribution.send_report_whatsapp',
        'distribution.update_email',
    },
}


def normalize_role_name(role_name):
    if not role_name:
        return ''

    normalized = unicodedata.normalize('NFD', str(role_name))
    normalized = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')
    return normalized.strip().lower()


def get_default_permissions_for_role(role_name):
    normalized_role = normalize_role_name(role_name)
    return sorted(ROLE_BASED_PERMISSIONS.get(normalized_role, set()))


def ensure_permissions_schema(connection):
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.ispermission (
                guid VARCHAR(50) PRIMARY KEY,
                code VARCHAR(100) UNIQUE NOT NULL,
                module VARCHAR(50) NOT NULL,
                action VARCHAR(50) NOT NULL,
                description VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_on TIMESTAMP DEFAULT NOW()
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.rel_user_permission (
                guid VARCHAR(50) PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                permission_id VARCHAR(50) NOT NULL,
                is_granted BOOLEAN DEFAULT TRUE,
                created_on TIMESTAMP DEFAULT NOW(),
                updated_on TIMESTAMP DEFAULT NOW(),
                CONSTRAINT uq_user_permission UNIQUE (user_id, permission_id),
                CONSTRAINT fk_user_permission_user FOREIGN KEY (user_id)
                    REFERENCES nextris.tbuser(guid) ON DELETE CASCADE,
                CONSTRAINT fk_user_permission_permission FOREIGN KEY (permission_id)
                    REFERENCES nextris.ispermission(guid) ON DELETE CASCADE
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_rel_user_permission_user
            ON nextris.rel_user_permission(user_id);
            """
        )
        connection.commit()
    except Exception:
        connection.rollback()
    finally:
        cursor.close()


def seed_permissions(connection):
    cursor = connection.cursor()
    try:
        values = [
            (
                str(uuid.uuid4()),
                permission['code'],
                permission['module'],
                permission['action'],
                permission['description'],
            )
            for permission in PERMISSION_CATALOG
        ]
        cursor.executemany(
            """
            INSERT INTO nextris.ispermission (guid, code, module, action, description, is_active)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (code)
            DO UPDATE SET
                module = EXCLUDED.module,
                action = EXCLUDED.action,
                description = EXCLUDED.description,
                is_active = TRUE
            """,
            values,
        )

        deprecated_codes = list(DEPRECATED_PERMISSION_ALIASES.keys())
        if deprecated_codes:
            cursor.execute(
                """
                UPDATE nextris.ispermission
                SET is_active = FALSE
                WHERE code = ANY(%s)
                """,
                (deprecated_codes,),
            )

        connection.commit()
    except Exception:
        connection.rollback()
    finally:
        cursor.close()


def get_permission_catalog(connection=None):
    own_connection = connection is None
    if own_connection:
        config = get_db_config()
        if not config:
            return []
        connection = psycopg2.connect(**config)

    try:
        ensure_permissions_schema(connection)
        seed_permissions(connection)
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT code, module, action, description
                FROM nextris.ispermission
                WHERE is_active = TRUE
                ORDER BY module, action, code
                """
            )
            rows = cursor.fetchall()
        except Exception:
            rows = [
                (item['code'], item['module'], item['action'], item['description'])
                for item in PERMISSION_CATALOG
            ]
        finally:
            cursor.close()
        return [
            {
                'code': row[0],
                'module': row[1],
                'action': row[2],
                'description': row[3],
            }
            for row in rows
        ]
    finally:
        if own_connection and connection:
            connection.close()


def _get_user_role_name(user_id, connection):
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT r.description
        FROM nextris.tbuser u
        LEFT JOIN nextris.isrole r ON r.guid = u.idrole
        WHERE u.guid = %s
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    return row[0] if row and row[0] else None


def get_user_permission_codes(user_id, connection=None, include_role_permissions=False):
    own_connection = connection is None
    if own_connection:
        config = get_db_config()
        if not config:
            return []
        connection = psycopg2.connect(**config)

    try:
        ensure_permissions_schema(connection)
        seed_permissions(connection)

        permissions = set()
        if include_role_permissions:
            role_name = _get_user_role_name(user_id, connection)
            permissions.update(get_default_permissions_for_role(role_name))

        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT p.code
                FROM nextris.rel_user_permission up
                INNER JOIN nextris.ispermission p ON p.guid = up.permission_id
                WHERE up.user_id = %s
                  AND up.is_granted = TRUE
                  AND p.is_active = TRUE
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
        except Exception:
            rows = []
        finally:
            cursor.close()

        permissions.update(normalize_permission_code(row[0]) for row in rows)
        return sorted(permissions)
    finally:
        if own_connection and connection:
            connection.close()


def user_has_permission_code(user_id, permission_code, connection=None, include_role_permissions=False):
    codes = get_user_permission_codes(
        user_id,
        connection=connection,
        include_role_permissions=include_role_permissions,
    )
    return '*' in codes or permission_code in codes


def user_has_administrator_role(user_id, connection=None):
    """Indica si el usuario pertenece a un rol administrativo privilegiado."""
    own_connection = connection is None
    if own_connection:
        config = get_db_config()
        if not config:
            return False
        connection = psycopg2.connect(**config)

    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT r.description
                FROM nextris.tbuser u
                LEFT JOIN nextris.isrole r ON r.guid = u.idrole
                WHERE u.guid = %s
                LIMIT 1
                """,
                (str(user_id),),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
        return normalize_role_name(row[0] if row else '') in {'sysadmin', 'admin', 'administrador'}
    except Exception:
        return False
    finally:
        if own_connection and connection:
            connection.close()


def require_admin_permission(permission_code):
    """Exige el permiso indicado y además un rol administrativo."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            if not user_id:
                return jsonify({'success': False, 'message': 'No autenticado'}), 401

            if not user_has_administrator_role(user_id):
                return jsonify({
                    'success': False,
                    'message': 'Esta acción solo está disponible para administradores',
                }), 403

            if not user_has_permission_code(
                user_id,
                permission_code,
                include_role_permissions=True,
            ):
                return jsonify({
                    'success': False,
                    'message': f'No tiene permiso: {permission_code}',
                }), 403

            return func(*args, **kwargs)

        return wrapper
    return decorator


def replace_user_permissions(user_id, permission_codes, connection=None):
    own_connection = connection is None
    if own_connection:
        config = get_db_config()
        if not config:
            raise RuntimeError('Error de configuración de base de datos')
        connection = psycopg2.connect(**config)

    try:
        ensure_permissions_schema(connection)
        seed_permissions(connection)

        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid = %s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            raise ValueError('Usuario no encontrado')

        normalized_codes = normalize_permission_codes(permission_codes)
        if normalized_codes:
            cursor.execute(
                """
                SELECT code, guid
                FROM nextris.ispermission
                WHERE code = ANY(%s)
                  AND is_active = TRUE
                """,
                (normalized_codes,),
            )
            permission_map = {row[0]: row[1] for row in cursor.fetchall()}
            missing_codes = [code for code in normalized_codes if code not in permission_map]
            if missing_codes:
                cursor.close()
                raise ValueError(f'Permisos no válidos: {", ".join(missing_codes)}')
        else:
            permission_map = {}

        cursor.execute(
            "DELETE FROM nextris.rel_user_permission WHERE user_id = %s",
            (user_id,),
        )

        if permission_map:
            cursor.executemany(
                """
                INSERT INTO nextris.rel_user_permission (
                    guid, user_id, permission_id, is_granted, created_on, updated_on
                ) VALUES (%s, %s, %s, TRUE, NOW(), NOW())
                """,
                [
                    (str(uuid.uuid4()), user_id, permission_map[code])
                    for code in normalized_codes
                ],
            )

        connection.commit()
        cursor.close()
        return normalized_codes
    except Exception:
        connection.rollback()
        raise
    finally:
        if own_connection and connection:
            connection.close()


def require_permission(permission_code, include_role_permissions=False):
    """
    Decorador para validar permisos API por usuario.

    Nota: este decorador asume que la ruta ya tiene @jwt_required().
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            if not user_id:
                return jsonify({
                    'success': False,
                    'message': 'No autenticado'
                }), 401

            has_permission = user_has_permission_code(
                user_id,
                permission_code,
                include_role_permissions=include_role_permissions,
            )
            if not has_permission:
                return jsonify({
                    'success': False,
                    'message': f'No tiene permiso: {permission_code}'
                }), 403

            return func(*args, **kwargs)

        return wrapper

    return decorator
