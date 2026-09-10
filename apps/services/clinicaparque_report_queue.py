"""Persistent queue for delayed Clínica Parque report transmissions.

The queue lives in PostgreSQL so it is safe to use with multiple Gunicorn
workers and survives an application restart.
"""

import threading
import time
import uuid
from datetime import datetime, timedelta

import psycopg2

from apps.home.services.config_service import ConfigService


DEFAULT_DELAY_MINUTES = 15
POLL_INTERVAL_SECONDS = 10
MAX_ATTEMPTS = 5

_worker_started = False
_worker_lock = threading.Lock()


def _db_config():
    return ConfigService.get_db_config()


def ensure_report_queue_table(connection):
    """Create the queue table and indexes when the deployment has not run SQL yet."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.clinicaparque_report_queue (
                id UUID PRIMARY KEY,
                exam_id VARCHAR(100) NOT NULL,
                scheduled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                locked_at TIMESTAMP WITHOUT TIME ZONE,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                sent_at TIMESTAMP WITHOUT TIME ZONE
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cp_report_queue_pending
            ON nextris.clinicaparque_report_queue (scheduled_at)
            WHERE status = 'pending'
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cp_report_queue_exam_status
            ON nextris.clinicaparque_report_queue (exam_id, status)
            """
        )
        connection.commit()
    finally:
        cursor.close()


def _get_delay_minutes(connection):
    """Read the configured delay, falling back safely for older databases."""
    cursor = connection.cursor()
    try:
        try:
            cursor.execute("SAVEPOINT report_delay_read")
            cursor.execute(
                """
                SELECT report_send_delay_minutes
                FROM nextris.app_config
                WHERE id = 1
                """
            )
            value = cursor.fetchone()
            value = value[0] if value else DEFAULT_DELAY_MINUTES
            cursor.execute("RELEASE SAVEPOINT report_delay_read")
        except psycopg2.Error:
            cursor.execute("ROLLBACK TO SAVEPOINT report_delay_read")
            cursor.execute("RELEASE SAVEPOINT report_delay_read")
            value = DEFAULT_DELAY_MINUTES

        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return DEFAULT_DELAY_MINUTES
    finally:
        cursor.close()


def enqueue_report_send(exam_id, connection=None):
    """Schedule the report transmission after the configured delay.

    When a connection is supplied, the queue row is written in the caller's
    transaction. This makes signing and scheduling atomic.
    """
    owns_connection = connection is None
    if owns_connection:
        connection = psycopg2.connect(**_db_config())

    try:
        if owns_connection:
            ensure_report_queue_table(connection)
        # ensure_report_queue_table commits its DDL. The caller's transaction
        # is intentionally restarted before the queue row is written.
        delay_minutes = _get_delay_minutes(connection)
        scheduled_at = datetime.now() + timedelta(minutes=delay_minutes)
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT id
                FROM nextris.clinicaparque_report_queue
                WHERE exam_id = %s AND status IN ('pending', 'processing')
                FOR UPDATE
                """,
                (str(exam_id),),
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    """
                    UPDATE nextris.clinicaparque_report_queue
                    SET scheduled_at = %s,
                        status = 'pending',
                        attempts = 0,
                        last_error = NULL,
                        locked_at = NULL,
                        sent_at = NULL
                    WHERE id = %s
                    """,
                    (scheduled_at, existing[0]),
                )
                queue_id = existing[0]
            else:
                queue_id = uuid.uuid4()
                cursor.execute(
                    """
                    INSERT INTO nextris.clinicaparque_report_queue
                        (id, exam_id, scheduled_at)
                    VALUES (%s, %s, %s)
                    """,
                    (queue_id, str(exam_id), scheduled_at),
                )
            if owns_connection:
                connection.commit()
            return {
                'queue_id': str(queue_id),
                'delay_minutes': delay_minutes,
                'scheduled_at': scheduled_at.isoformat(),
            }
        finally:
            cursor.close()
    except Exception:
        if owns_connection:
            connection.rollback()
        raise
    finally:
        if owns_connection:
            connection.close()


def _claim_next(connection):
    cursor = connection.cursor()
    try:
        # Allow another worker to retry an item if the process that claimed it
        # disappeared while the external request was in flight.
        cursor.execute(
            """
            UPDATE nextris.clinicaparque_report_queue
            SET status = 'pending', locked_at = NULL
            WHERE status = 'processing'
              AND locked_at < NOW() - INTERVAL '15 minutes'
            """
        )
        cursor.execute(
            """
            UPDATE nextris.clinicaparque_report_queue AS queue
            SET status = 'processing',
                attempts = queue.attempts + 1,
                locked_at = NOW()
            WHERE queue.id = (
                SELECT id
                FROM nextris.clinicaparque_report_queue
                WHERE status = 'pending' AND scheduled_at <= NOW()
                ORDER BY scheduled_at, created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING queue.id, queue.exam_id
            """
        )
        row = cursor.fetchone()
        connection.commit()
        return row
    finally:
        cursor.close()


def _finish(connection, queue_id, success, error=None):
    cursor = connection.cursor()
    try:
        if success:
            cursor.execute(
                """
                UPDATE nextris.clinicaparque_report_queue
                SET status = 'sent', sent_at = NOW(), locked_at = NULL,
                    last_error = NULL
                WHERE id = %s
                """,
                (queue_id,),
            )
        else:
            cursor.execute(
                """
                UPDATE nextris.clinicaparque_report_queue
                SET status = CASE WHEN attempts >= %s THEN 'failed' ELSE 'pending' END,
                    scheduled_at = CASE WHEN attempts >= %s THEN scheduled_at
                        ELSE NOW() + INTERVAL '5 minutes' END,
                    locked_at = NULL,
                    last_error = %s
                WHERE id = %s
                """,
                (MAX_ATTEMPTS, MAX_ATTEMPTS, str(error or 'Error desconocido'), queue_id),
            )
        connection.commit()
    finally:
        cursor.close()


def _process_one():
    connection = psycopg2.connect(**_db_config())
    try:
        ensure_report_queue_table(connection)
        row = _claim_next(connection)
        if not row:
            return False

        queue_id, exam_id = row
        try:
            from apps.api.clinicaparque import _send_report_to_external

            result = _send_report_to_external(str(exam_id))
            _finish(connection, queue_id, bool(result.get('success')), result.get('error'))
        except Exception as error:
            _finish(connection, queue_id, False, error)
        return True
    finally:
        connection.close()


def _worker_loop():
    while True:
        try:
            _process_one()
        except Exception as error:
            print(f"[CLINICAPARQUE QUEUE] Error procesando cola: {error}")
        time.sleep(POLL_INTERVAL_SECONDS)


def start_report_queue_worker():
    """Start one daemon worker per application process.

    PostgreSQL row locking makes multiple Gunicorn workers safe: only one
    worker can claim a pending queue item.
    """
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        try:
            connection = psycopg2.connect(**_db_config())
            try:
                from apps.home.services.app_config_service import ensure_app_config_table

                ensure_app_config_table(connection)
                ensure_report_queue_table(connection)
            finally:
                connection.close()
        except Exception as error:
            # The worker will retry on its next loop once PostgreSQL is ready.
            print(f"[CLINICAPARQUE QUEUE] No se pudo inicializar la cola: {error}")
        _worker_started = True
        worker = threading.Thread(
            target=_worker_loop,
            name='clinicaparque-report-queue',
            daemon=True,
        )
        worker.start()
