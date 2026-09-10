"""Utilities for durable, study-scoped viewer share links."""

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta

import psycopg2
from flask import current_app, has_request_context, request


def db_config():
    from apps.home.services import ConfigService
    return ConfigService.get_db_config()


def token_hash(raw_token):
    secret = current_app.config.get("SECRET_KEY") or os.getenv(
        "SECRET_KEY", "nextris-viewer-share-secret"
    )
    return hmac.new(secret.encode(), raw_token.encode(), hashlib.sha256).hexdigest()


def public_base_url():
    configured = current_app.config.get("PUBLIC_API_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    if not has_request_context():
        return (current_app.config.get("SERVER_NAME") or os.getenv("PUBLIC_API_URL", "http://localhost")).rstrip("/")
    proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    host = request.headers.get("X-Forwarded-Host", request.host)
    return f"{proto}://{host}"


def short_share_url(short_code):
    """URL pública corta; el código funciona como credencial temporal."""
    if not short_code:
        raise ValueError("No se puede construir un enlace compartido sin short_code")
    return f"{public_base_url()}/api/s/{short_code}"


def default_expiration_hours():
    try:
        configured = current_app.config.get("VIEWER_SHARE_EXPIRATION_HOURS", os.getenv("VIEWER_SHARE_EXPIRATION_HOURS", "720"))
        return max(1, int(configured))
    except ValueError:
        return 720


def client_ip():
    if not has_request_context():
        return None
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() if forwarded else request.remote_addr


def create_for_exam(examination_id, created_by=None, connection=None, share_type="image_share"):
    """Create a new link and return its raw URL while it is still in memory.

    The raw token is never written to PostgreSQL. Existing active links for the
    same study are revoked so a regenerated PDF invalidates the previous QR.
    """
    if share_type not in ("case_link", "image_share"):
        raise ValueError("Tipo de enlace compartido inválido")

    owns_connection = connection is None
    connection = connection or psycopg2.connect(**db_config())
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT ex.studyinstanceuid, loc.guid
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.isequipment eq ON eq.guid = ex.idequipment
            LEFT JOIN nextris.tblocation loc
                ON loc.guid = COALESCE(ex.location_id, eq.location_id)
            WHERE ex.guid = %s
            LIMIT 1
            """,
            (str(examination_id),),
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            raise ValueError("El examen no tiene StudyInstanceUID")

        study_iuid, location_id = str(row[0]), row[1]
        cursor.execute(
            """
            UPDATE nextris.tbviewer_share_link
            SET revoked = TRUE, revoked_at = NOW()
            WHERE study_iuid = %s
              AND share_type = %s
              AND revoked = FALSE
              AND expires_at > NOW()
            """,
            (study_iuid, share_type),
        )

        raw_token = secrets.token_urlsafe(32)
        short_code = secrets.token_urlsafe(7)
        expires_at = datetime.utcnow() + timedelta(hours=default_expiration_hours())
        guid = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO nextris.tbviewer_share_link (
                guid, token_hash, short_code, study_iuid, location_id,
                created_by_user_id, created_at, expires_at, revoked,
                open_count, created_ip, share_type
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, FALSE, 0, %s, %s)
            """,
            (
                guid,
                token_hash(raw_token),
                short_code,
                study_iuid,
                str(location_id) if location_id else None,
                str(created_by or "system"),
                expires_at,
                client_ip(),
                share_type,
            ),
        )
        # No devolvemos un enlace que no haya quedado asociado a la fila.
        # Esto evita generar PDFs con QR que contienen códigos inexistentes.
        cursor.execute(
            """
            SELECT short_code
            FROM nextris.tbviewer_share_link
            WHERE guid = %s
            LIMIT 1
            """,
            (guid,),
        )
        stored_short_code = cursor.fetchone()
        if not stored_short_code or not stored_short_code[0]:
            raise RuntimeError("El short_code del enlace no se pudo guardar")
        if owns_connection:
            connection.commit()
        return {
            "guid": guid,
            "study_iuid": study_iuid,
            "expires_at": expires_at,
            "expires_hours": default_expiration_hours(),
            "share_type": share_type,
            "short_code": str(stored_short_code[0]),
            "share_url": short_share_url(str(stored_short_code[0])),
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        if owns_connection:
            connection.close()


def get_or_create_active_for_exam(examination_id, created_by=None, connection=None, share_type="image_share"):
    """Return an active reusable share link, creating it only when needed."""
    if share_type not in ("case_link", "image_share"):
        raise ValueError("Tipo de enlace compartido inválido")

    owns_connection = connection is None
    connection = connection or psycopg2.connect(**db_config())
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT short_code, study_iuid, expires_at, guid
            FROM nextris.tbviewer_share_link
            WHERE study_iuid = (
                SELECT studyinstanceuid
                FROM nextris.tbexamination
                WHERE guid = %s
                LIMIT 1
            )
              AND share_type = %s
              AND revoked = FALSE
              AND expires_at > NOW()
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (str(examination_id), share_type),
        )
        row = cursor.fetchone()
        if row and row[0]:
            if owns_connection:
                connection.commit()
            return {
                "guid": row[3],
                "study_iuid": str(row[1]),
                "expires_at": row[2],
                "expires_hours": default_expiration_hours(),
                "share_type": share_type,
                "short_code": str(row[0]),
                "share_url": short_share_url(str(row[0])),
            }
    finally:
        cursor.close()
        if owns_connection:
            connection.close()

    return create_for_exam(
        examination_id,
        created_by=created_by,
        connection=connection if not owns_connection else None,
        share_type=share_type,
    )
