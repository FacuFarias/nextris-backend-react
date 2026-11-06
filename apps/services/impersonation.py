"""Persistent JWT revocation and impersonation session audit."""

import psycopg2
from apps.api.utils import get_db_config


def is_token_revoked(jwt_payload):
    config = get_db_config()
    if not config:
        return True
    connection = None
    try:
        connection = psycopg2.connect(**config)
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM nextris.tb_revoked_jwt WHERE jti = %s",
                    (jwt_payload.get('jti'),),
                )
                if cursor.fetchone():
                    return True
                impersonation_id = jwt_payload.get('impersonation_id')
                if impersonation_id:
                    cursor.execute(
                        """
                        SELECT 1 FROM nextris.tb_impersonation_session
                        WHERE id = %s AND ended_at IS NULL
                        """,
                        (impersonation_id,),
                    )
                    return cursor.fetchone() is None
        return False
    except Exception:
        # Auth fails closed if the revocation store cannot be checked.
        return True
    finally:
        if connection:
            connection.close()


def revoke_jwt(cursor, payload):
    cursor.execute(
        """
        INSERT INTO nextris.tb_revoked_jwt (jti, expires_at)
        VALUES (%s, to_timestamp(%s))
        ON CONFLICT (jti) DO NOTHING
        """,
        (payload['jti'], payload['exp']),
    )


def record_impersonated_request(jwt_payload, path, method, status):
    """Append a minimal action trail without storing request bodies or secrets."""
    impersonation_id = jwt_payload.get('impersonation_id')
    if not impersonation_id:
        return
    connection = None
    try:
        connection = psycopg2.connect(**get_db_config())
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO nextris.tb_impersonation_request_audit
                        (impersonation_id, actor_guid, target_guid,
                         request_path, http_method, http_status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (impersonation_id, jwt_payload.get('impersonator_id'),
                     jwt_payload.get('sub'), path, method, status),
                )
    except Exception as error:
        print(f'[IMPERSONATION] No se pudo auditar la petición: {error}')
    finally:
        if connection:
            connection.close()
