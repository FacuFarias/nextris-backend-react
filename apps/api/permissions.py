# -*- encoding: utf-8 -*-
"""
Utilidades de permisos para API JWT.
"""

from functools import wraps
import uuid

import psycopg2
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, get_jwt

from apps.api.utils import get_db_config


from apps.permission_policy import (
    PERMISSION_CATALOG, VALID_PERMISSION_CODES, DISABLED_MODULES,
    DEPRECATED_PERMISSION_ALIASES, ROLE_BASED_PERMISSIONS,
    normalize_permission_code, normalize_permission_codes, normalize_role_name,
    get_default_permissions_for_role, validate_permission_codes,
)


def ensure_permissions_schema(connection, commit=True):
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
        if commit:
            connection.commit()
    except Exception:
        if commit:
            connection.rollback()
        raise
    finally:
        cursor.close()


def seed_permissions(connection, commit=True):
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

        cursor.execute(
            "UPDATE nextris.ispermission SET is_active = FALSE WHERE NOT (code = ANY(%s))",
            (list(VALID_PERMISSION_CODES),),
        )

        if commit:
            connection.commit()
    except Exception:
        if commit:
            connection.rollback()
        raise
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
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT code, module, action, description
                FROM nextris.ispermission
                WHERE is_active = TRUE AND code = ANY(%s)
                ORDER BY module, action, code
                """, (list(VALID_PERMISSION_CODES),)
            )
            rows = cursor.fetchall()
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


def user_is_admin(user_id, connection):
    return normalize_role_name(_get_user_role_name(user_id, connection)) in ('sysadmin', 'admin', 'administrador')


def get_user_permission_codes(user_id, connection=None, include_role_permissions=False):
    own_connection = connection is None
    if own_connection:
        config = get_db_config()
        if not config:
            return []
        connection = psycopg2.connect(**config)

    try:

        permissions = set()
        # Roles are editable templates, never runtime grants. Only Sysadmin is global.
        role_name = _get_user_role_name(user_id, connection)
        if normalize_role_name(role_name) == 'sysadmin':
            permissions.add('*')

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

        permissions.update(code for row in rows if (code := normalize_permission_code(row[0])) in VALID_PERMISSION_CODES)
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
    return '*' in codes or normalize_permission_code(permission_code) in codes


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
    """Compatibility name: explicit staff permissions determine authorization."""
    return require_permission(permission_code)


def replace_user_permissions(user_id, permission_codes, connection=None):
    own_connection = connection is None
    if own_connection:
        config = get_db_config()
        if not config:
            raise RuntimeError('Error de configuración de base de datos')
        connection = psycopg2.connect(**config)

    try:

        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM nextris.tbuser WHERE guid = %s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            raise ValueError('Usuario no encontrado')

        normalized_codes = validate_permission_codes(permission_codes)
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

        if own_connection:
            connection.commit()
        cursor.close()
        return normalized_codes
    except Exception:
        if own_connection:
            connection.rollback()
        raise
    finally:
        if own_connection and connection:
            connection.close()


def require_any_permission(*permission_codes):
    """Authorize staff using the exact same saved grants as the session API."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            if not user_id:
                return jsonify(success=False, message='No autenticado'), 401
            if get_jwt().get('user_type', '').lower() == 'patient':
                return jsonify(success=False, message='Acceso exclusivo del personal'), 403
            codes = get_user_permission_codes(user_id)
            if '*' not in codes and not any(normalize_permission_code(code) in codes for code in permission_codes):
                return jsonify(success=False, message='No tiene permiso: ' + ', '.join(permission_codes)), 403
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(permission_code, include_role_permissions=False):
    # Keep the argument for source compatibility; roles no longer add permissions.
    return require_any_permission(permission_code)
