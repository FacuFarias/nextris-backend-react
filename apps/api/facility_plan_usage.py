# -*- encoding: utf-8 -*-
"""Utilidades para planes por facility y métricas mensuales de uso."""

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


def _current_year_month():
    now = datetime.utcnow()
    return now.year, now.month


def _count_active_users_by_facility(cursor, facility_id):
    cursor.execute(
        """
        SELECT COUNT(DISTINCT u.guid)
        FROM nextris.tbuser u
        INNER JOIN nextris.rel_user_location rul ON rul.user_id = u.guid
        INNER JOIN nextris.tblocation l ON l.guid = rul.location_id
        WHERE l.facility_id = %s
          AND COALESCE(u.isactive, 1) = 1
        """,
        (facility_id,),
    )
    row = cursor.fetchone()
    return int(row[0] or 0) if row else 0


def ensure_plan_management_schema(connection):
    """Crea tablas/columnas de planes y uso mensual de forma idempotente."""
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

        cursor.execute(
            """
            ALTER TABLE nextris.tbfacility
            ADD COLUMN IF NOT EXISTS plan_id VARCHAR(50)
            """
        )

        cursor.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'fk_tbfacility_plan_id'
                ) THEN
                    ALTER TABLE nextris.tbfacility
                    ADD CONSTRAINT fk_tbfacility_plan_id
                    FOREIGN KEY (plan_id)
                    REFERENCES nextris.isplan(guid)
                    ON DELETE RESTRICT;
                END IF;
            END $$;
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.facility_plan_usage_monthly (
                guid VARCHAR(50) PRIMARY KEY,
                facility_id VARCHAR(50) NOT NULL,
                usage_year INTEGER NOT NULL,
                usage_month INTEGER NOT NULL,
                received_count INTEGER NOT NULL DEFAULT 0,
                read_count INTEGER NOT NULL DEFAULT 0,
                distributed_count INTEGER NOT NULL DEFAULT 0,
                users_count_snapshot INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                CONSTRAINT fk_facility_plan_usage_monthly_facility
                    FOREIGN KEY (facility_id) REFERENCES nextris.tbfacility(guid) ON DELETE CASCADE,
                CONSTRAINT uq_facility_plan_usage_monthly UNIQUE (facility_id, usage_year, usage_month)
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_facility_plan_usage_monthly_facility_period
            ON nextris.facility_plan_usage_monthly (facility_id, usage_year DESC, usage_month DESC)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.audit_facility_plan_change (
                id BIGSERIAL PRIMARY KEY,
                guid VARCHAR(50) NOT NULL UNIQUE,
                facility_id VARCHAR(50) NOT NULL,
                previous_plan_id VARCHAR(50),
                new_plan_id VARCHAR(50) NOT NULL,
                previous_plan_code VARCHAR(50),
                new_plan_code VARCHAR(50),
                action VARCHAR(20) NOT NULL,
                changed_by_user_id VARCHAR(50),
                reason TEXT,
                request_ip VARCHAR(64),
                changed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                CONSTRAINT fk_audit_facility_plan_change_facility
                    FOREIGN KEY (facility_id) REFERENCES nextris.tbfacility(guid) ON DELETE CASCADE,
                CONSTRAINT fk_audit_facility_plan_change_previous_plan
                    FOREIGN KEY (previous_plan_id) REFERENCES nextris.isplan(guid) ON DELETE SET NULL,
                CONSTRAINT fk_audit_facility_plan_change_new_plan
                    FOREIGN KEY (new_plan_id) REFERENCES nextris.isplan(guid) ON DELETE RESTRICT,
                CONSTRAINT ck_audit_facility_plan_change_action
                    CHECK (action IN ('activated', 'upgraded', 'downgraded', 'changed'))
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_facility_plan_change_facility_changed_at
            ON nextris.audit_facility_plan_change (facility_id, changed_at DESC)
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

        # Política FREE: retención DICOM de 30 días por ubicación (si existe la columna).
        cursor.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'nextris'
                      AND table_name = 'tblocation'
                      AND column_name = 'retention_days'
                ) THEN
                    UPDATE nextris.tblocation l
                    SET retention_days = 30
                    FROM nextris.tbfacility f
                    JOIN nextris.isplan p ON p.guid = f.plan_id
                    WHERE l.facility_id = f.guid
                      AND LOWER(COALESCE(p.code, '')) = 'free'
                      AND COALESCE(l.retention_days, 0) <> 30;
                END IF;
            END $$;
            """
        )

        cursor.execute("SELECT guid FROM nextris.isplan WHERE code = 'free' LIMIT 1")
        free_plan_row = cursor.fetchone()
        if free_plan_row:
            cursor.execute(
                """
                UPDATE nextris.tbfacility
                SET plan_id = %s
                WHERE plan_id IS NULL
                """,
                (free_plan_row[0],),
            )

        connection.commit()
    finally:
        cursor.close()


def get_facility_plan_snapshot(cursor, facility_id):
    """Obtiene el plan actual de la facility con sus límites."""
    cursor.execute(
        """
        SELECT f.plan_id,
               p.code,
               p.name,
               p.max_receive_monthly,
             p.max_read_monthly,
               p.max_distribute_monthly,
             p.dicom_retention_days,
               p.max_users
        FROM nextris.tbfacility f
        LEFT JOIN nextris.isplan p ON p.guid = f.plan_id
        WHERE f.guid = %s
        LIMIT 1
        """,
        (facility_id,),
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


def get_current_usage(cursor, facility_id):
    """Obtiene el uso del mes actual por facility."""
    usage_year, usage_month = _current_year_month()
    cursor.execute(
        """
        SELECT received_count, read_count, distributed_count, users_count_snapshot
        FROM nextris.facility_plan_usage_monthly
        WHERE facility_id = %s
          AND usage_year = %s
          AND usage_month = %s
        LIMIT 1
        """,
        (facility_id, usage_year, usage_month),
    )
    row = cursor.fetchone()
    if not row:
        return {
            'usage_year': usage_year,
            'usage_month': usage_month,
            'received_count': 0,
            'read_count': 0,
            'distributed_count': 0,
            'users_count_snapshot': 0,
        }

    return {
        'usage_year': usage_year,
        'usage_month': usage_month,
        'received_count': int(row[0] or 0),
        'read_count': int(row[1] or 0),
        'distributed_count': int(row[2] or 0),
        'users_count_snapshot': int(row[3] or 0),
    }


def refresh_users_snapshot(connection, facility_id):
    """Actualiza snapshot de usuarios activos para el mes actual."""
    usage_year, usage_month = _current_year_month()
    cursor = connection.cursor()
    try:
        users_count = _count_active_users_by_facility(cursor, facility_id)
        cursor.execute(
            """
            INSERT INTO nextris.facility_plan_usage_monthly (
                guid, facility_id, usage_year, usage_month,
                users_count_snapshot, updated_at
            ) VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (facility_id, usage_year, usage_month)
            DO UPDATE SET
                users_count_snapshot = EXCLUDED.users_count_snapshot,
                updated_at = NOW()
            """,
            (str(uuid.uuid4()), facility_id, usage_year, usage_month, users_count),
        )
        return users_count
    finally:
        cursor.close()


def increment_usage_counter(connection, facility_id, counter_name, delta=1):
    """Incrementa de forma atómica un contador mensual de uso por facility."""
    counter_map = {
        'received': 'received_count',
        'read': 'read_count',
        'distributed': 'distributed_count',
    }
    if counter_name not in counter_map:
        raise ValueError(f'Contador inválido: {counter_name}')

    column_name = counter_map[counter_name]
    usage_year, usage_month = _current_year_month()

    cursor = connection.cursor()
    try:
        users_count = _count_active_users_by_facility(cursor, facility_id)
        cursor.execute(
            f"""
            INSERT INTO nextris.facility_plan_usage_monthly (
                guid,
                facility_id,
                usage_year,
                usage_month,
                {column_name},
                users_count_snapshot,
                updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (facility_id, usage_year, usage_month)
            DO UPDATE SET
                {column_name} = nextris.facility_plan_usage_monthly.{column_name} + EXCLUDED.{column_name},
                users_count_snapshot = EXCLUDED.users_count_snapshot,
                updated_at = NOW()
            """,
            (str(uuid.uuid4()), facility_id, usage_year, usage_month, int(delta), users_count),
        )
    finally:
        cursor.close()


def check_limit_before_action(connection, facility_id, action):
    """Valida si una acción de negocio supera límites del plan."""
    if action not in ('receive', 'read', 'distribute'):
        raise ValueError(f'Acción inválida: {action}')

    cursor = connection.cursor()
    try:
        plan = get_facility_plan_snapshot(cursor, facility_id)
        if not plan or not plan.get('plan_id'):
            return True, None

        usage = get_current_usage(cursor, facility_id)
        users_count = _count_active_users_by_facility(cursor, facility_id)

        max_users = plan.get('max_users')
        if max_users is not None and users_count >= max_users:
            return False, {
                'reason': 'USER_LIMIT_REACHED',
                'message': f'Límite de usuarios alcanzado ({users_count}/{max_users})',
                'usage': usage,
                'limits': plan,
            }

        if action == 'receive':
            max_receive = plan.get('max_receive_monthly')
            if max_receive is not None and usage['received_count'] >= max_receive:
                return False, {
                    'reason': 'RECEIVE_LIMIT_REACHED',
                    'message': f'Límite mensual de estudios recibidos alcanzado ({usage["received_count"]}/{max_receive})',
                    'usage': usage,
                    'limits': plan,
                }

        if action == 'read':
            max_read = plan.get('max_read_monthly')
            if max_read is not None and usage['read_count'] >= max_read:
                return False, {
                    'reason': 'READ_LIMIT_REACHED',
                    'message': f'Límite mensual de estudios redactados alcanzado ({usage["read_count"]}/{max_read})',
                    'usage': usage,
                    'limits': plan,
                }

        if action == 'distribute':
            max_distribute = plan.get('max_distribute_monthly')
            if max_distribute is not None and usage['distributed_count'] >= max_distribute:
                return False, {
                    'reason': 'DISTRIBUTE_LIMIT_REACHED',
                    'message': f'Límite mensual de estudios distribuidos alcanzado ({usage["distributed_count"]}/{max_distribute})',
                    'usage': usage,
                    'limits': plan,
                }

        return True, None
    finally:
        cursor.close()


def get_exam_facility_id(cursor, exam_id):
    """Obtiene facility_id desde un examen."""
    cursor.execute(
        """
        SELECT l.facility_id
        FROM nextris.tbexamination ex
        LEFT JOIN nextris.isequipment eq ON ex.idequipment = eq.guid
        LEFT JOIN nextris.tblocation l ON eq.location_id = l.guid
        WHERE ex.guid = %s
        LIMIT 1
        """,
        (exam_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return row[0]


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


def append_plan_change_audit(connection, facility_id, previous_plan_id, new_plan_id, changed_by_user_id=None, reason=None, request_ip=None):
    """Registra auditoría de cambios de plan cuando hay transición real."""
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
            INSERT INTO nextris.audit_facility_plan_change (
                guid,
                facility_id,
                previous_plan_id,
                new_plan_id,
                previous_plan_code,
                new_plan_code,
                action,
                changed_by_user_id,
                reason,
                request_ip
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                facility_id,
                previous_plan_id,
                new_plan_id,
                previous_plan_code,
                new_plan_code,
                action,
                changed_by_user_id,
                reason,
                request_ip,
            ),
        )
        return True
    finally:
        cursor.close()
