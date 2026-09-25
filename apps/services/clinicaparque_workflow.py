"""Shared workflow state and report handling for Clínica Parque studies.

The UI and the external Clínica Parque callbacks must apply exactly the same
transition rules.  This module deliberately receives an open psycopg2
connection so callers can commit the study transition and its audit log as one
transaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Mapping

from apps.services.timezone_utils import DEFAULT_TIMEZONE, to_utc_naive

from apps.services.report_fields import has_value, normalize_report_payload


WORKFLOW_PENDING = "pending"
WORKFLOW_CANCELLED = "cancelled"
WORKFLOW_ALREADY_READ = "already_read"
TERMINAL_WORKFLOW_STATES = {WORKFLOW_CANCELLED, WORKFLOW_ALREADY_READ}

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
            CREATE TABLE IF NOT EXISTS nextris.clinicaparque_cancellation_reasons (
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
                ADD COLUMN IF NOT EXISTS clinicaparque_workflow_state VARCHAR(20)
                    NOT NULL DEFAULT 'pending',
                ADD COLUMN IF NOT EXISTS clinicaparque_workflow_state_at
                    TIMESTAMP WITHOUT TIME ZONE,
                ADD COLUMN IF NOT EXISTS clinicaparque_workflow_state_source
                    VARCHAR(32),
                ADD COLUMN IF NOT EXISTS clinicaparque_workflow_state_user_id
                    VARCHAR(100),
                ADD COLUMN IF NOT EXISTS clinicaparque_cancellation_reason_id
                    VARCHAR(50),
                ADD COLUMN IF NOT EXISTS clinicaparque_cancellation_detail TEXT
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tbexamination_cp_workflow_state
            ON nextris.tbexamination (clinicaparque_workflow_state)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tbexamination_cp_cancel_reason
            ON nextris.tbexamination (clinicaparque_cancellation_reason_id)
            """
        )
        for code, description, sort_order in DEFAULT_CANCELLATION_REASONS:
            cursor.execute(
                """
                INSERT INTO nextris.clinicaparque_cancellation_reasons
                    (guid, code, description, sort_order, active)
                VALUES (%s, %s, %s, %s, TRUE)
                ON CONFLICT (code) DO NOTHING
                """,
                (str(uuid.uuid4()), code, description, sort_order),
            )
        connection.commit()
    finally:
        cursor.close()


def parse_external_timestamp(value: Any) -> datetime | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if len(text) == 10:
        try:
            return datetime.strptime(text, "%Y-%m-%d")
        except ValueError as error:
            raise ValueError("La fecha externa debe ser ISO 8601 válida") from error
    try:
        # Clínica Parque opera en Argentina. Un timestamp sin offset es hora
        # local argentina; si trae Z u otro offset, se respeta como instante.
        return to_utc_naive(text, DEFAULT_TIMEZONE)
    except ValueError as error:
        raise ValueError("La fecha externa debe ser ISO 8601 válida") from error


def _reason_row(cursor, code: Any):
    clean_code = str(code or "").strip().upper()
    if not clean_code:
        raise ValueError("cancellation_reason_code es requerido")
    cursor.execute(
        """
        SELECT guid, code, description
        FROM nextris.clinicaparque_cancellation_reasons
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
        SELECT clinicaparque_workflow_state, COALESCE(isreported, 0),
               clinicaparque_cancellation_reason_id
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
        SET clinicaparque_workflow_state = %s,
            clinicaparque_workflow_state_at = COALESCE(%s, NOW()),
            clinicaparque_workflow_state_source = %s,
            clinicaparque_workflow_state_user_id = %s,
            clinicaparque_cancellation_reason_id = %s,
            clinicaparque_cancellation_detail = %s
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
                "SELECT code, description FROM nextris.clinicaparque_cancellation_reasons WHERE guid = %s",
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


def _upsert_optional_report(cursor, exam_id: str, report_payload: Mapping[str, Any],
                            rad_id: Any = None):
    normalized = normalize_report_payload(report_payload)
    has_content = any(has_value(normalized.get(key)) for key in
                      ("study_reason", "content", "conclusion"))
    clean_rad_id = str(rad_id or "").strip() or None
    user_id = None
    if clean_rad_id:
        cursor.execute(
            """
            SELECT guid FROM nextris.tbuser
            WHERE username = %s OR nationalnumber = %s
            LIMIT 1
            """,
            (clean_rad_id, clean_rad_id),
        )
        physician = cursor.fetchone()
        if not physician:
            raise ValueError("rad_id no corresponde a un médico existente")
        user_id = physician[0]

    cursor.execute(
        """
        SELECT guid, study_reason, content, conclusion
        FROM nextris.tbreport
        WHERE idexamination = %s
        LIMIT 1
        """,
        (exam_id,),
    )
    existing = cursor.fetchone()
    if not existing and not has_content:
        return None

    if existing:
        report_id = existing[0]
        updates = []
        values = []
        for key, column in (("study_reason", "study_reason"),
                            ("content", "content"), ("conclusion", "conclusion")):
            if key in normalized:
                updates.append(f"{column} = %s")
                values.append(normalized[key])
        updates.extend(["wassaved = TRUE", "date = COALESCE(date, NOW())"])
        if user_id:
            updates.append("iduser = %s")
            values.append(user_id)
        values.append(report_id)
        cursor.execute(
            f"UPDATE nextris.tbreport SET {', '.join(updates)} WHERE guid = %s",
            values,
        )
    else:
        report_id = str(uuid.uuid4())
        cursor.execute(
            """
            SELECT idpatient, localacc FROM nextris.tbexamination WHERE guid = %s
            """,
            (exam_id,),
        )
        exam_row = cursor.fetchone()
        cursor.execute(
            """
            INSERT INTO nextris.tbreport
                (guid, idexamination, idpatient, admnumber,
                 study_reason, content, conclusion, wassaved, createdon, date, iduser)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW(), %s)
            """,
            (report_id, exam_id, exam_row[0] if exam_row else None,
             exam_row[1] if exam_row else None,
             normalized.get("study_reason", ""), normalized.get("content", ""),
             normalized.get("conclusion", ""), user_id),
        )
    return str(report_id)


def apply_already_read(connection, exam_id: str, report_payload: Mapping[str, Any] | None = None,
                       rad_id: Any = None,
                       read_at: Any = None, source: str = "nextris_ui",
                       user_id: Any = None):
    ensure_workflow_schema(connection)
    cursor = connection.cursor()
    try:
        transition = _ensure_pending_transition(cursor, exam_id, WORKFLOW_ALREADY_READ)
        report_id = None
        if report_payload:
            report_id = _upsert_optional_report(cursor, exam_id, report_payload,
                                                rad_id=rad_id)
        if not transition["idempotent"]:
            parsed_read_at = parse_external_timestamp(read_at) if read_at else None
            _set_state(cursor, exam_id, WORKFLOW_ALREADY_READ, source, user_id,
                       state_at=parsed_read_at)
            cursor.execute(
                """
                UPDATE nextris.tbexamination
                SET isreported = 1,
                    reportdate = COALESCE(%s, reportdate, CURRENT_TIMESTAMP)
                WHERE guid = %s
                """,
                (parsed_read_at, exam_id),
            )
        return {"state": WORKFLOW_ALREADY_READ, "idempotent": transition["idempotent"],
                "report_id": report_id}
    finally:
        cursor.close()
