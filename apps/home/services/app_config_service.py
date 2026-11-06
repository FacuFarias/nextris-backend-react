# -*- encoding: utf-8 -*-
"""
Servicio de configuración global de la aplicación (single-tenant)
Reemplaza la lógica de tbfacility con una tabla app_config de una sola fila.
"""

import psycopg2
import uuid
from datetime import datetime
from apps.home.services.config_service import ConfigService


def get_db_config():
    """Obtiene la configuración de la base de datos"""
    return ConfigService.get_db_config()


def _column_exists(cursor, table_name, column_name):
    """Verifica si una columna existe en la tabla."""
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'nextris'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    return cursor.fetchone() is not None


def _table_exists(cursor, table_name):
    """Verifica si una tabla existe en el schema nextris."""
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'nextris'
          AND table_name = %s
        LIMIT 1
        """,
        (table_name,),
    )
    return cursor.fetchone() is not None


def ensure_app_config_table(connection):
    """Crea la tabla app_config si no existe y migra datos de tbfacility."""
    cursor = connection.cursor()
    try:
        if _table_exists(cursor, 'tbfacility'):
            cursor.execute('SELECT count(*) FROM nextris.tbfacility')
            if cursor.fetchone()[0] > 1:
                raise ValueError('Multiple institutions: apply the explicit single-institution migration first')

        # Crear tabla app_config
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.app_config (
                id                      INTEGER PRIMARY KEY DEFAULT 1,
                name                    VARCHAR(255) NOT NULL DEFAULT 'NextRIS',
                code                    VARCHAR(50),
                email                   VARCHAR(150),
                contact_person          VARCHAR(150),
                description             TEXT,
                address                 VARCHAR(255),
                city                    VARCHAR(100),
                country                 VARCHAR(100),
                phone                   VARCHAR(50),
                smtp_server             VARCHAR(255),
                smtp_port               INTEGER,
                smtp_user               VARCHAR(150),
                smtp_password           VARCHAR(255),
                smtp_from               VARCHAR(150),
                smtp_from_name          VARCHAR(150),
                use_tls                 BOOLEAN DEFAULT TRUE,
                whatsapp_api_url            VARCHAR(500),
                whatsapp_api_token          VARCHAR(500),
                whatsapp_phone_number_id    VARCHAR(100),
                whatsapp_business_account_id VARCHAR(100),
                whatsapp_webhook_verify_token VARCHAR(255),
                whatsapp_is_active          BOOLEAN DEFAULT FALSE,
                plan_id                 VARCHAR(50),
                hl7_enable_orm BOOLEAN NOT NULL DEFAULT FALSE,
                hl7_enable_report_sending BOOLEAN NOT NULL DEFAULT FALSE,
                hl7_bearer_token_orm TEXT,
                hl7_report_send_mode VARCHAR(20) NOT NULL DEFAULT 'text',
                created_at              TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                updated_at              TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
                CONSTRAINT single_row CHECK (id = 1)
            )
            """
        )

        cursor.execute("""
            ALTER TABLE nextris.app_config
                ADD COLUMN IF NOT EXISTS hl7_enable_orm BOOLEAN NOT NULL DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS hl7_enable_report_sending BOOLEAN NOT NULL DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS hl7_bearer_token_orm TEXT,
                ADD COLUMN IF NOT EXISTS hl7_report_send_mode VARCHAR(20) NOT NULL DEFAULT 'text'
        """)

        # Insertar registro por defecto si no existe
        cursor.execute(
            """
            INSERT INTO nextris.app_config (id, name, code)
            VALUES (1, 'NextRIS', 'NRIS')
            ON CONFLICT (id) DO NOTHING
            """
        )

        connection.commit()
    finally:
        cursor.close()


def get_app_config():
    """Obtiene la configuración global de la aplicación."""
    db_config = get_db_config()
    connection = psycopg2.connect(**db_config)
    cursor = connection.cursor()
    try:
        ensure_app_config_table(connection)

        cursor.execute(
            """
            SELECT
                id, name, code, email, contact_person, description,
                address, city, country, phone,
                smtp_server, smtp_port, smtp_user, smtp_from, smtp_from_name, use_tls,
                whatsapp_api_url, whatsapp_phone_number_id,
                whatsapp_business_account_id, whatsapp_is_active,
                plan_id, hl7_enable_orm, hl7_enable_report_sending, created_at, updated_at
            FROM nextris.app_config
            WHERE id = 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            'id': row[0],
            'name': row[1],
            'code': row[2],
            'email': row[3],
            'contact_person': row[4],
            'description': row[5],
            'address': row[6],
            'city': row[7],
            'country': row[8],
            'phone': row[9],
            'smtp_server': row[10],
            'smtp_port': row[11],
            'smtp_user': row[12],
            'smtp_from': row[13],
            'smtp_from_name': row[14],
            'use_tls': row[15],
            'whatsapp_api_url': row[16],
            'whatsapp_phone_number_id': row[17],
            'whatsapp_business_account_id': row[18],
            'whatsapp_is_active': row[19],
            'plan_id': row[20],
            'hl7_enable_orm': row[21],
            'hl7_enable_report_sending': row[22],
            'created_at': row[23].isoformat() if row[23] else None,
            'updated_at': row[24].isoformat() if row[24] else None,
        }
    finally:
        cursor.close()
        connection.close()


def update_app_config(data):
    """Actualiza la configuración global de la aplicación."""
    if 'name' in data and (not isinstance(data['name'], str) or not data['name'].strip()):
        raise ValueError('El nombre de la institución es requerido')
    for key in ('hl7_enable_orm', 'hl7_enable_report_sending', 'use_tls'):
        if key in data and not isinstance(data[key], bool):
            raise ValueError(f'{key} debe ser booleano')
    if 'smtp_port' in data and (isinstance(data['smtp_port'], bool) or not isinstance(data['smtp_port'], int) or not 1 <= data['smtp_port'] <= 65535):
        raise ValueError('El puerto SMTP debe estar entre 1 y 65535')
    db_config = get_db_config()
    connection = psycopg2.connect(**db_config)
    cursor = connection.cursor()
    try:
        ensure_app_config_table(connection)

        allowed_fields = [
            'name', 'code', 'email', 'contact_person', 'description',
            'address', 'city', 'country', 'phone',
            'smtp_server', 'smtp_port', 'smtp_user', 'smtp_password',
            'smtp_from', 'smtp_from_name', 'use_tls',
            'whatsapp_api_url', 'whatsapp_api_token', 'whatsapp_phone_number_id',
            'whatsapp_business_account_id', 'whatsapp_webhook_verify_token',
            'whatsapp_is_active', 'plan_id',
            'hl7_enable_orm', 'hl7_enable_report_sending', 'hl7_bearer_token_orm', 'hl7_report_send_mode',
        ]

        updates = []
        values = []
        for field in allowed_fields:
            if field in data:
                updates.append(f"{field} = %s")
                values.append(data[field])

        if not updates:
            return get_app_config()

        updates.append("updated_at = NOW()")
        query = f"""
            UPDATE nextris.app_config
            SET {', '.join(updates)}
            WHERE id = 1
        """
        cursor.execute(query, values)
        connection.commit()

        return get_app_config()
    finally:
        cursor.close()
        connection.close()


def get_app_modules():
    """Obtiene el estado de los módulos globales."""
    db_config = get_db_config()
    connection = psycopg2.connect(**db_config)
    cursor = connection.cursor()
    try:
        if not _table_exists(cursor, 'app_modules'):
            return []

        cursor.execute(
            """
            SELECT module_id, is_active, updated_at
            FROM nextris.app_modules
            ORDER BY module_id
            """
        )
        modules = []
        for row in cursor.fetchall():
            modules.append({
                'module_id': row[0],
                'is_active': row[1],
                'updated_at': row[2].isoformat() if row[2] else None,
            })
        return modules
    finally:
        cursor.close()
        connection.close()


def update_app_module(module_id, is_active):
    """Actualiza el estado de un módulo global."""
    db_config = get_db_config()
    connection = psycopg2.connect(**db_config)
    cursor = connection.cursor()
    try:
        if not _table_exists(cursor, 'app_modules'):
            # Crear tabla si no existe
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS nextris.app_modules (
                    module_id       VARCHAR(50) PRIMARY KEY,
                    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
                    updated_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
                )
                """
            )

        cursor.execute(
            """
            INSERT INTO nextris.app_modules (module_id, is_active, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (module_id) DO UPDATE SET
                is_active = EXCLUDED.is_active,
                updated_at = NOW()
            """,
            (module_id, is_active),
        )
        connection.commit()

        return {'module_id': module_id, 'is_active': is_active}
    finally:
        cursor.close()
        connection.close()


def get_plan_info():
    """Obtiene información del plan global actual."""
    config = get_app_config()
    if not config or not config.get('plan_id'):
        return None

    db_config = get_db_config()
    connection = psycopg2.connect(**db_config)
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT guid, code, name, description,
                   max_receive_monthly, max_read_monthly, max_distribute_monthly,
                   dicom_retention_days, max_users
            FROM nextris.isplan
            WHERE guid = %s
            """,
            (config['plan_id'],),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            'guid': row[0],
            'code': row[1],
            'name': row[2],
            'description': row[3],
            'max_receive_monthly': row[4],
            'max_read_monthly': row[5],
            'max_distribute_monthly': row[6],
            'dicom_retention_days': row[7],
            'max_users': row[8],
        }
    finally:
        cursor.close()
        connection.close()
