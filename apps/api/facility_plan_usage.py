# -*- encoding: utf-8 -*-
"""Utilidades para gestión global de planes."""

from datetime import datetime
import uuid


DEFAULT_FACILITY_PLANS = [
    {
        'code': 'free',
        'name': 'Free',
        'description': 'Plan gratuito',
        'max_receive_monthly': 50,
        'max_read_monthly': 30,
        'max_distribute_monthly': 30,
        'dicom_retention_days': 30,
        'max_users': 5,
    },
    {
        'code': 'standard',
        'name': 'Standard',
        'description': 'Plan estándar',
        'max_receive_monthly': 5000,
        'max_read_monthly': 5000,
        'max_distribute_monthly': 3000,
        'dicom_retention_days': None,
        'max_users': 25,
    },
    {
        'code': 'pro',
        'name': 'Pro',
        'description': 'Plan profesional',
        'max_receive_monthly': 150,
        'max_read_monthly': 100,
        'max_distribute_monthly': 120,
        'dicom_retention_days': None,
        'max_users': 80,
    },
    {
        'code': 'enterprise',
        'name': 'Enterprise',
        'description': 'Plan empresarial sin límites',
        'max_receive_monthly': None,
        'max_read_monthly': None,
        'max_distribute_monthly': None,
        'dicom_retention_days': None,
        'max_users': None,
    },
]


def ensure_plan_management_schema(connection):
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.isplan (
                guid VARCHAR(50) PRIMARY KEY,
                code VARCHAR(50) NOT NULL UNIQUE,
                name VARCHAR(120) NOT NULL,
                description TEXT,
                max_receive_monthly INTEGER,
                max_read_monthly INTEGER,
                max_distribute_monthly INTEGER,
                dicom_retention_days INTEGER,
                max_users INTEGER,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            )
            """
        )

        cursor.execute(
            """
            ALTER TABLE nextris.isplan
            ADD COLUMN IF NOT EXISTS max_read_monthly INTEGER
            """
        )

        cursor.execute(
            """
            ALTER TABLE nextris.isplan
            ADD COLUMN IF NOT EXISTS dicom_retention_days INTEGER
            """
        )

        cursor.executemany(
            """
            INSERT INTO nextris.isplan (
                guid, code, name, description,
                max_receive_monthly, max_read_monthly, max_distribute_monthly,
                dicom_retention_days, max_users, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                max_receive_monthly = EXCLUDED.max_receive_monthly,
                max_read_monthly = EXCLUDED.max_read_monthly,
                max_distribute_monthly = EXCLUDED.max_distribute_monthly,
                dicom_retention_days = EXCLUDED.dicom_retention_days,
                max_users = EXCLUDED.max_users,
                updated_at = NOW()
            """,
            [
                (
                    str(uuid.uuid4()),
                    plan['code'],
                    plan['name'],
                    plan['description'],
                    plan['max_receive_monthly'],
                    plan['max_read_monthly'],
                    plan['max_distribute_monthly'],
                    plan['dicom_retention_days'],
                    plan['max_users'],
                )
                for plan in DEFAULT_FACILITY_PLANS
            ],
        )

        connection.commit()
    finally:
        cursor.close()


def get_global_plan_snapshot(cursor):
    cursor.execute(
        """
        SELECT ac.plan_id,
               p.code,
               p.name,
               p.max_receive_monthly,
               p.max_read_monthly,
               p.max_distribute_monthly,
               p.dicom_retention_days,
               p.max_users
        FROM nextris.app_config ac
        LEFT JOIN nextris.isplan p ON p.guid = ac.plan_id
        WHERE ac.id = 1
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        'plan_id': row[0],
        'plan_code': row[1],
        'plan_name': row[2],
        'max_receive_monthly': row[3],
        'max_read_monthly': row[4],
        'max_distribute_monthly': row[5],
        'dicom_retention_days': row[6],
        'max_users': row[7],
    }


def check_limit_before_action(connection, action):
    if action not in ('receive', 'read', 'distribute'):
        raise ValueError(f'Acción inválida: {action}')

    cursor = connection.cursor()
    try:
        plan = get_global_plan_snapshot(cursor)
        if not plan or not plan.get('plan_id'):
            return True, None

        return True, None
    finally:
        cursor.close()


def _plan_rank(plan_code):
    if not plan_code:
        return 0
    ranks = {
        'free': 1,
        'standard': 2,
        'pro': 3,
        'enterprise': 4,
    }
    return ranks.get(str(plan_code).strip().lower(), 0)


def append_plan_change_audit(connection, previous_plan_id, new_plan_id, changed_by_user_id=None, reason=None, request_ip=None):
    if not new_plan_id:
        return False

    if previous_plan_id and str(previous_plan_id) == str(new_plan_id):
        return False

    cursor = connection.cursor()
    try:
        previous_plan_code = None
        if previous_plan_id:
            cursor.execute("SELECT code FROM nextris.isplan WHERE guid = %s LIMIT 1", (previous_plan_id,))
            previous_row = cursor.fetchone()
            previous_plan_code = previous_row[0] if previous_row else None

        cursor.execute("SELECT code FROM nextris.isplan WHERE guid = %s LIMIT 1", (new_plan_id,))
        new_row = cursor.fetchone()
        new_plan_code = new_row[0] if new_row else None

        if previous_plan_id is None:
            action = 'activated'
        else:
            old_rank = _plan_rank(previous_plan_code)
            new_rank = _plan_rank(new_plan_code)
            if new_rank > old_rank:
                action = 'upgraded'
            elif new_rank < old_rank:
                action = 'downgraded'
            else:
                action = 'changed'

        cursor.execute(
            """
            UPDATE nextris.app_config
            SET plan_id = %s, updated_at = NOW()
            WHERE id = 1
            """,
            (new_plan_id,),
        )
        return True
    finally:
        cursor.close()
