# -*- encoding: utf-8 -*-
"""
Listener for PACS new patient notifications.

When a new patient is inserted into public.patient (dcm4chee PACS),
the PostgreSQL trigger sends a NOTIFY on channel 'pacs_new_patient'.
This listener receives those notifications and creates the portal user
(nextris.tbuser_patient) with the correct werkzeug password hash.

Usage:
    from apps.home.services.pacs_patient_listener import start_pacs_listener
    start_pacs_listener()  # starts in a background daemon thread
"""

import json
import select
import threading
import time
import uuid

import psycopg2
import psycopg2.extensions

from apps.authentication.util import hash_pass
from apps.home.services.config_service import ConfigService

_CHANNEL = 'pacs_new_patient'
_RECONNECT_DELAY = 5
_POLL_TIMEOUT = 60


def _create_connection():
    """Create a new non-autocommit connection for LISTEN/NOTIFY."""
    db_config = ConfigService.get_db_config()
    conn = psycopg2.connect(**db_config)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def _create_portal_user(nationalcode, patient_guid):
    """Create portal user for a newly created patient."""
    if not nationalcode:
        print("[PACS-LISTENER] No nationalcode provided, skipping portal user creation")
        return

    db_config = ConfigService.get_db_config()
    conn = psycopg2.connect(**db_config)
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT guid FROM nextris.tbuser_patient WHERE datapatient_id = %s LIMIT 1",
            (patient_guid,),
        )
        if cursor.fetchone():
            print(f"[PACS-LISTENER] Portal user already exists for {patient_guid}")
            return

        username = nationalcode.strip()
        password_raw = username[-3:] if len(username) >= 3 else username
        hashed_password = hash_pass(password_raw)

        cursor.execute(
            """
            INSERT INTO nextris.tbuser_patient
                (guid, username, password, datapatient_id, status, firstlogin)
            VALUES (%s, %s, %s, %s, 'Active', 0)
            """,
            (str(uuid.uuid4()), username, hashed_password, patient_guid),
        )
        conn.commit()
        print(f"[PACS-LISTENER] Portal user created: {username} for patient {patient_guid}")

    except Exception as e:
        print(f"[PACS-LISTENER] Error creating portal user: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cursor.close()
        conn.close()


def _handle_notification(payload_str):
    """Process a NOTIFY payload from the pacs_new_patient channel."""
    try:
        data = json.loads(payload_str)
        nationalcode = data.get('nationalcode')
        patient_guid = data.get('guid')
        patientid = data.get('patientid', 'unknown')
        name = data.get('name', '')

        print(f"[PACS-LISTENER] New patient notification: {patientid} ({name})")

        if patient_guid and nationalcode:
            _create_portal_user(nationalcode, patient_guid)
        else:
            print(f"[PACS-LISTENER] Incomplete payload, skipping: {data}")

    except json.JSONDecodeError as e:
        print(f"[PACS-LISTENER] Invalid JSON payload: {e}")
    except Exception as e:
        print(f"[PACS-LISTENER] Error handling notification: {e}")


def _listener_loop():
    """Main listener loop with automatic reconnection."""
    print(f"[PACS-LISTENER] Starting listener on channel '{_CHANNEL}'...")

    conn = None
    while True:
        try:
            if conn is None or conn.closed:
                print("[PACS-LISTENER] Connecting to database...")
                conn = _create_connection()
                cursor = conn.cursor()
                cursor.execute(f"LISTEN {_CHANNEL};")
                cursor.close()
                print(f"[PACS-LISTENER] Listening on '{_CHANNEL}'")

            if select.select([conn], [], [], _POLL_TIMEOUT) == ([], [], []):
                continue

            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                _handle_notification(notify.payload)

        except psycopg2.OperationalError as e:
            print(f"[PACS-LISTENER] Connection lost: {e}")
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = None
            print(f"[PACS-LISTENER] Reconnecting in {_RECONNECT_DELAY}s...")
            time.sleep(_RECONNECT_DELAY)

        except Exception as e:
            print(f"[PACS-LISTENER] Unexpected error: {e}")
            time.sleep(_RECONNECT_DELAY)


_listener_thread = None


def start_pacs_listener():
    """Start the PACS patient listener in a background daemon thread."""
    global _listener_thread

    if _listener_thread is not None and _listener_thread.is_alive():
        print("[PACS-LISTENER] Listener already running")
        return

    _listener_thread = threading.Thread(target=_listener_loop, daemon=True)
    _listener_thread.start()
    print("[PACS-LISTENER] Background thread started")
