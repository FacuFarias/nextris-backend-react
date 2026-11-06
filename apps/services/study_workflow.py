"""Local study cancellation rules shared by NextRIS endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any




WORKFLOW_PENDING = "pending"
WORKFLOW_CANCELLED = "cancelled"
TERMINAL_WORKFLOW_STATES = {WORKFLOW_CANCELLED}

DEFAULT_CANCELLATION_REASONS = (
    ("PATIENT_ABSENT", "Paciente ausente", 10),
    ("PATIENT_REFUSAL", "Rechazo del paciente", 20),
    ("CLINICAL_CONTRAINDICATION", "Contraindicación clínica", 30),
    ("INADEQUATE_PREPARATION", "Preparación inadecuada", 40),
    ("TECHNICAL_FAILURE", "Falla técnica o de equipo", 50),
    ("DUPLICATE_ORDER", "Orden duplicada", 60),
    ("INCORRECT_ORDER", "Orden incorrecta", 70),
    ("OTHER", "Otro", 80),
)


def ensure_workflow_schema(connection):
    """Ensure workflow columns/catalog exist for older installations."""
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS nextris.cancellation_reasons (
                guid VARCHAR(50) PRIMARY KEY,
                code VARCHAR(80) NOT NULL UNIQUE,
                description VARCHAR(255) NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            ALTER TABLE nextris.tbexamination
                ADD COLUMN IF NOT EXISTS workflow_state VARCHAR(20)
                    NOT NULL DEFAULT 'pending',
                ADD COLUMN IF NOT EXISTS workflow_state_at
                    TIMESTAMP WITHOUT TIME ZONE,
                ADD COLUMN IF NOT EXISTS workflow_state_source
                    VARCHAR(32),
                ADD COLUMN IF NOT EXISTS workflow_state_user_id
                    VARCHAR(100),
                ADD COLUMN IF NOT EXISTS cancellation_reason_id
                    VARCHAR(50),
                ADD COLUMN IF NOT EXISTS cancellation_detail TEXT
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tbexamination_workflow_state
            ON nextris.tbexamination (workflow_state)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tbexamination_cancel_reason
            ON nextris.tbexamination (cancellation_reason_id)
            """
        )
        for code, description, sort_order in DEFAULT_CANCELLATION_REASONS:
            cursor.execute(
                """
                INSERT INTO nextris.cancellation_reasons
                    (guid, code, description, sort_order, active)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (code) DO NOTHING
                """,
                (str(uuid.uuid4()), code, description, sort_order),
            )
        connection.commit()
    finally:
        cursor.close()


def _reason_row(cursor, code: Any):
    clean_code = str(code or "").strip().upper()
    if not clean_code:
        raise ValueError("cancellation_reason_code es requerido")
    cursor.execute(
        """
        SELECT guid, code, description
        FROM nextris.cancellation_reasons
        WHERE code = %s AND active = TRUE
        LIMIT 1
        """,
        (clean_code,),
    )
    row = cursor.fetchone()
    if not row:
        raise ValueError("El motivo de cancelación no existe o está inactivo")
    return row


def _ensure_pending_transition(cursor, exam_id: str, target_state: str):
    cursor.execute(
        """
        SELECT workflow_state, COALESCE(isreported, 0),
               cancellation_reason_id
        FROM nextris.tbexamination
        WHERE guid = %s
        FOR UPDATE
        """,
        (exam_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise LookupError("Examen no encontrado")
    current_state, is_reported, current_reason_id = row
    current_state = current_state or WORKFLOW_PENDING
    if current_state == target_state:
        return {"idempotent": True, "reason_id": current_reason_id}
    if current_state in TERMINAL_WORKFLOW_STATES:
        raise PermissionError("El estudio ya tiene una resolución terminal")
    if bool(is_reported):
        raise PermissionError("El estudio ya fue reportado en NextRIS")
    return {"idempotent": False, "reason_id": None}


def _set_state(cursor, exam_id: str, state: str, source: str, user_id: Any = None,
               reason_id: str | None = None, detail: str | None = None,
               state_at: datetime | None = None):
    cursor.execute(
        """
        UPDATE nextris.tbexamination
        SET workflow_state = %s,
            workflow_state_at = COALESCE(%s, NOW()),
            workflow_state_source = %s,
            workflow_state_user_id = %s,
            cancellation_reason_id = %s,
            cancellation_detail = %s
        WHERE guid = %s
        """,
        (state, state_at, source, str(user_id) if user_id else None,
         reason_id, detail, exam_id),
    )


def apply_cancel(connection, exam_id: str, reason_code: Any, detail: Any = None,
                 source: str = "nextris_ui", user_id: Any = None):
    ensure_workflow_schema(connection)
    cursor = connection.cursor()
    try:
        clean_detail = str(detail or "").strip() or None
        transition = _ensure_pending_transition(cursor, exam_id, WORKFLOW_CANCELLED)
        if transition["idempotent"]:
            cursor.execute(
                "SELECT code, description FROM nextris.cancellation_reasons WHERE guid = %s",
                (transition["reason_id"],),
            )
            existing_reason = cursor.fetchone()
            if not existing_reason or str(existing_reason[0]).upper() != str(reason_code or '').strip().upper():
                raise PermissionError("El estudio ya fue cancelado con otro motivo")
            return {"state": WORKFLOW_CANCELLED, "idempotent": True,
                    "reason_code": existing_reason[0], "reason": existing_reason[1]}

        reason = _reason_row(cursor, reason_code)
        if reason[1] == "OTHER" and not clean_detail:
            raise ValueError("El detalle es obligatorio para el motivo Otro")

        _set_state(cursor, exam_id, WORKFLOW_CANCELLED, source, user_id,
                   reason_id=reason[0], detail=clean_detail)
        cursor.execute(
            "UPDATE nextris.tbexamination SET status = 'Cancelled' WHERE guid = %s",
            (exam_id,),
        )
        return {"state": WORKFLOW_CANCELLED, "idempotent": False,
                "reason_code": reason[1], "reason": reason[2]}
    finally:
        cursor.close()


