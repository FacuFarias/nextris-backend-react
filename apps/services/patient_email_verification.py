"""Patient email ownership: expiring, bounded, single-use verification codes."""
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone


class VerificationError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def normalize_email(value):
    if not isinstance(value, str):
        raise VerificationError('Ingrese un email válido')
    email = value.strip().lower()
    if len(email) > 150 or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', email):
        raise VerificationError('Ingrese un email válido')
    return email


def lock_patient(cursor, user_id):
    if os.getenv('NEXTRIS_PATIENT_MODE', 'human') == 'veterinary':
        cursor.execute('''SELECT rp.email FROM nextris.responsible_party rp
            JOIN nextris.tbuser_patient up ON up.responsible_party_id=rp.id
            WHERE up.guid=%s FOR UPDATE OF rp''', (user_id,))
        responsible = cursor.fetchone()
        if responsible:
            cursor.execute('''SELECT verified_email,email_code_hash,email_code_address,email_code_expires,
                email_code_sent_at,email_code_attempts FROM nextris.tbuser_patient WHERE guid=%s FOR UPDATE''',(user_id,))
            return responsible[0], cursor.fetchone()
    # Same lock order as profile updates: patient first, then portal account.
    cursor.execute('''SELECT dp.email FROM nextris.datapatient dp
        JOIN nextris.tbuser_patient up ON up.datapatient_id = dp.guid
        WHERE up.guid = %s FOR UPDATE OF dp''', (user_id,))
    patient = cursor.fetchone()
    if not patient:
        raise VerificationError('Paciente no encontrado', 404)
    cursor.execute('''SELECT verified_email, email_code_hash, email_code_address,
        email_code_expires, email_code_sent_at, email_code_attempts
        FROM nextris.tbuser_patient WHERE guid = %s FOR UPDATE''', (user_id,))
    return patient[0], cursor.fetchone()


def require_verified_email(cursor, user_id):
    email, state = lock_patient(cursor, user_id)
    if not email or not state[0] or email.strip().lower() != state[0]:
        raise VerificationError('Debe validar su email en Mis Datos antes de cambiar la contraseña', 403)


def email_verification_enabled():
    return os.getenv('PATIENT_EMAIL_VERIFICATION_ENABLED', 'false').strip().lower() in ('true', '1', 'yes')


def require_password_change_email(cursor, user_id):
    if email_verification_enabled():
        return require_verified_email(cursor, user_id)
    email, _ = lock_patient(cursor, user_id)
    try:
        normalize_email(email)
    except VerificationError:
        raise VerificationError('Debe guardar un email válido en Mis Datos antes de cambiar la contraseña', 403)


def send_verification(cursor, user_id, send_email):
    address, state = lock_patient(cursor, user_id)
    email = normalize_email(address)
    now = datetime.now(timezone.utc)
    if state[0] == email:
        raise VerificationError('El email ya está validado')
    if state[4] and now - state[4] < timedelta(seconds=60):
        raise VerificationError('Espere un minuto antes de solicitar otro código', 429)
    code = f'{secrets.randbelow(1000000):06d}'
    cursor.execute('''UPDATE nextris.tbuser_patient SET email_code_hash = %s,
        email_code_address = %s, email_code_expires = %s, email_code_sent_at = %s,
        email_code_attempts = 0 WHERE guid = %s''',
        (hashlib.sha256(code.encode()).hexdigest(), email, now + timedelta(minutes=30), now, user_id))
    send_email(email, code)


def confirm_verification(cursor, user_id, code):
    address, state = lock_patient(cursor, user_id)
    email = normalize_email(address)
    _, digest, code_email, expires, _, attempts = state
    if not digest or code_email != email or not expires or expires <= datetime.now(timezone.utc):
        raise VerificationError('El código venció o no es válido. Solicite uno nuevo')
    if attempts >= 5:
        raise VerificationError('Se agotaron los intentos. Solicite un nuevo código', 429)
    if not isinstance(code, str) or not re.fullmatch(r'\d{6}', code) or not hmac.compare_digest(
        digest, hashlib.sha256(code.encode()).hexdigest()
    ):
        cursor.execute('''UPDATE nextris.tbuser_patient
            SET email_code_attempts = email_code_attempts + 1 WHERE guid = %s''', (user_id,))
        # Caller commits failed attempts too, so retries cannot bypass the limit.
        raise VerificationError('Código incorrecto')
    cursor.execute('''UPDATE nextris.tbuser_patient SET verified_email = %s,
        email_code_hash = NULL, email_code_address = NULL, email_code_expires = NULL,
        email_code_attempts = 0 WHERE guid = %s''', (email, user_id))
