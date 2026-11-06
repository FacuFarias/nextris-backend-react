"""Durable permanent deletions of exact instances, through the PACS API."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import time
import threading
from urllib.parse import quote
import uuid

import psycopg2
from psycopg2.extras import Json, RealDictCursor, execute_values
import requests

log = logging.getLogger(__name__)
REJECTION_CODES = {'113001', '113037', '113038'}
PERMANENT_CODE = 'NEXTDEL'
PERMANENT_SCHEME = '99NEXTRIS'


class DeletionError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


@contextmanager
def database():
    # Keep the standalone worker independent of API blueprint initialization.
    conn = psycopg2.connect(host=os.getenv('DB_HOST', 'localhost'), port=os.getenv('DB_PORT', '5432'),
                           dbname=os.getenv('DB_NAME', 'postgres'), user=os.getenv('DB_USER', 'postgres'),
                           password=os.getenv('DB_PASS', 'postgres'))
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


class PacsClient:
    def __init__(self):
        studies = os.getenv('PACS_STOW_URL', 'https://localhost:8080/dcm4chee-arc/aets/DCM4CHEE/rs/studies')
        self.base = studies.rstrip('/').removesuffix('/studies')
        self.root = self.base.split('/aets/')[0]
        self.verify = os.getenv('PACS_VERIFY_TLS', 'false').lower() == 'true'
        if not self.verify:
            requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        self.token = None
        self.token_until = 0

    def request(self, method, path, **kwargs):
        if not self.token or time.monotonic() >= self.token_until:
            response = requests.post(
                os.getenv('PACS_KEYCLOAK_TOKEN_URL', os.getenv('VIEWER_KEYCLOAK_TOKEN_URL', '')),
                data={'grant_type': 'client_credentials',
                      'client_id': os.getenv('PACS_KEYCLOAK_CLIENT_ID', ''),
                      'client_secret': os.getenv('PACS_KEYCLOAK_CLIENT_SECRET', '')},
                timeout=(10, 30), verify=self.verify)
            response.raise_for_status()
            token = response.json()
            self.token = token['access_token']
            self.token_until = time.monotonic() + max(1, token.get('expires_in', 60) - 20)
        headers = {**kwargs.pop('headers', {}), 'Authorization': f'Bearer {self.token}'}
        response = requests.request(method, path, headers=headers,
                                    timeout=(10, 30), verify=self.verify, **kwargs)
        if response.status_code == 401:
            self.token = None
            self.token_until = 0
        return response

    def reasons(self):
        response = self.request('GET', self.root + '/reject')
        response.raise_for_status()
        return [r for r in response.json()
                if r.get('codeValue') in REJECTION_CODES and r.get('codingSchemeDesignator') == 'DCM']

    def instance_url(self, study, series, sop):
        return (self.base + '/studies/' + quote(study, safe='') + '/series/'
                + quote(series, safe='') + '/instances/' + quote(sop, safe=''))

    def reject(self, study, series, sop, code):
        return self.request('POST', self.instance_url(study, series, sop) + '/reject/' + code + '^DCM')

    def permanent_deletion_available(self):
        response = self.request('GET', self.root + '/reject')
        response.raise_for_status()
        return any(r.get('codeValue') == PERMANENT_CODE
                   and r.get('codingSchemeDesignator') == PERMANENT_SCHEME for r in response.json())

    def mark_permanent(self, study, series, sop):
        return self.request('POST', self.instance_url(study, series, sop)
                            + '/reject/' + PERMANENT_CODE + '^' + PERMANENT_SCHEME)

    def purge_permanent(self):
        # Never purge a standard clinical rejection code: this private code is
        # reserved exclusively for confirmed permanent NextRIS operations.
        return self.request('DELETE', self.root + '/reject/' + PERMANENT_CODE + '^' + PERMANENT_SCHEME,
                            params={'keepRejectionNote': 'false'})

    def delete_study(self, study):
        return self.request('DELETE', self.base + '/studies/' + quote(study, safe=''),
                            params={'retainObj': 'false'})


def affected_examinations(cur, study_uid):
    cur.execute("""
        SELECT DISTINCT e.guid, e.localacc AS accession_number,
               CASE WHEN COALESCE(e.isreported, 0) = 1 OR EXISTS (
                   SELECT 1 FROM nextris.tbreport r WHERE r.idexamination=e.guid AND r.wassaved
               ) THEN 1 ELSE 0 END AS is_reported,
               COALESCE(e.isreported, 0) AS is_signed
        FROM nextris.tbexamination e
        JOIN nextris.examination_pacs_study ep ON ep.examination_guid = e.guid
        WHERE ep.study_iuid = %s ORDER BY e.guid
    """, (study_uid,))
    return [dict(r) for r in cur.fetchall()]


def normalize_selection(body):
    level = body.get('level')
    if level not in {'study', 'series', 'instances'}:
        raise DeletionError('Nivel de eliminación inválido')
    series = body.get('series_uids', [])
    instances = body.get('instances', [])
    if not isinstance(series, list) or not isinstance(instances, list):
        raise DeletionError('Selección inválida')
    if level == 'series' and (not series or not all(isinstance(s, str) and s for s in series)):
        raise DeletionError('Seleccione al menos una serie')
    if level == 'instances' and (not instances or not all(
            isinstance(i, dict) and isinstance(i.get('series_uid'), str) and i['series_uid']
            and isinstance(i.get('sop_uid'), str) and i['sop_uid'] for i in instances)):
        raise DeletionError('Seleccione al menos una imagen')
    return {'level': level, 'series_uids': sorted(set(series)) if level == 'series' else [],
            'instances': [dict(series_uid=s, sop_uid=i) for s, i in sorted(set(
                (x['series_uid'], x['sop_uid']) for x in instances))] if level == 'instances' else []}


def manifest(cur, study_pk, selection):
    cur.execute("""SELECT sr.series_iuid, i.sop_iuid FROM nextris.available_pacs_instance i
                   JOIN public.series sr ON sr.pk = i.series_fk
                   WHERE sr.study_fk = %s ORDER BY sr.series_iuid, i.sop_iuid""", (study_pk,))
    all_targets = [(r['series_iuid'], r['sop_iuid']) for r in cur.fetchall()]
    if selection['level'] == 'series':
        if not set(selection['series_uids']) <= {s for s, _ in all_targets}:
            raise DeletionError('Una serie ya no está disponible o no pertenece al estudio', 409)
        targets = [(s, i) for s, i in all_targets if s in selection['series_uids']]
    elif selection['level'] == 'instances':
        targets = [(x['series_uid'], x['sop_uid']) for x in selection['instances']]
        if not set(targets) <= set(all_targets):
            raise DeletionError('Una imagen ya no está disponible o no pertenece al estudio', 409)
    else:
        targets = all_targets
    if not targets:
        raise DeletionError('El estudio no tiene imágenes disponibles', 409)
    return targets


def fingerprint(targets, exams):
    return hashlib.sha256(json.dumps({'targets': targets, 'examinations': exams},
                                    sort_keys=True, default=str).encode()).hexdigest()


def preview(body, user_id):
    try:
        study_pk = int(body.get('study_pk'))
    except (ValueError, TypeError):
        raise DeletionError('study_pk es requerido')
    selection = normalize_selection(body)
    operation_id = str(uuid.uuid4())
    with database() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT study_iuid FROM nextris.available_pacs_study WHERE pk = %s', (study_pk,))
        study = cur.fetchone()
        if not study:
            raise DeletionError('Estudio sin imágenes disponibles', 404)
        targets = manifest(cur, study_pk, selection)
        exams = affected_examinations(cur, study['study_iuid'])
        cur.execute("""INSERT INTO nextris.tbimage_deletion
            (id, study_pk, study_iuid, created_by, selection, snapshot_hash, affected_examinations, deletion_mode)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'permanent')""",
            (operation_id, study_pk, study['study_iuid'], user_id, Json(selection),
             fingerprint(targets, exams), Json(exams, dumps=lambda x: json.dumps(x, default=str))))
        execute_values(cur, """INSERT INTO nextris.tbimage_deletion_target
                        (operation_id, series_iuid, sop_iuid) VALUES %s""",
                       [(operation_id, s, i) for s, i in targets])
        # Keep database identities and storage locations, so a later re-upload
        # using the same DICOM UIDs is never mistaken for an unfinished deletion.
        cur.execute("""UPDATE nextris.tbimage_deletion_target t
            SET instance_pk=i.pk, storage_location_pks=ARRAY(
                SELECT l.pk FROM public.location l WHERE l.instance_fk=i.pk ORDER BY l.pk)
            FROM public.instance i JOIN public.series sr ON sr.pk=i.series_fk
            WHERE t.operation_id=%s AND sr.study_fk=%s
              AND t.series_iuid=sr.series_iuid AND t.sop_iuid=i.sop_iuid""", (operation_id, study_pk))
        cur.execute("""UPDATE nextris.tbimage_deletion SET pacs_instance_pks=ARRAY(
            SELECT i.pk FROM public.instance i JOIN public.series sr ON sr.pk=i.series_fk
            WHERE sr.study_fk=%s ORDER BY i.pk) WHERE id=%s""", (study_pk, operation_id))
    return operation_id


def load_operation(cur, operation_id, user_id=None, wildcard=False, lock=False):
    try:
        operation_id = str(uuid.UUID(str(operation_id)))
    except ValueError:
        raise DeletionError('Operación no encontrada', 404)
    cur.execute('SELECT * FROM nextris.tbimage_deletion WHERE id = %s' + (' FOR UPDATE' if lock else ''),
                (operation_id,))
    op = cur.fetchone()
    if not op or (user_id is not None and str(op['created_by']) != str(user_id) and not wildcard):
        raise DeletionError('Operación no encontrada', 404)
    return dict(op)


def execute(operation_id, body, user_id, wildcard=False, pacs=None):
    code = body.get('rejection_code')
    justification = body.get('justification', '')
    if code not in REJECTION_CODES or not isinstance(justification, str) or not justification.strip():
        raise DeletionError('Seleccione un motivo DICOM y escriba una justificación')
    if len(justification.strip()) > 2000:
        raise DeletionError('La justificación admite hasta 2000 caracteres')
    # No open database transaction during remote configuration reads.
    pacs = pacs or PacsClient()
    reasons = pacs.reasons()
    if code not in {r['codeValue'] for r in reasons}:
        raise DeletionError('El motivo de rechazo no está configurado en PACS', 409)
    permanent_available = pacs.permanent_deletion_available() if body.get('permanent') is True else False
    with database() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        op = load_operation(cur, operation_id, user_id, wildcard, lock=True)
        if op['status'] in {'queued', 'running', 'completed'}:
            return
        if op.get('deletion_mode') == 'permanent':
            if body.get('permanent') is not True:
                raise DeletionError('Confirme la eliminación permanente; esta acción no se puede deshacer', 409)
            if not permanent_available:
                raise DeletionError('La eliminación permanente no está configurada en el PACS', 409)
        else:
            raise DeletionError('Revise la selección nuevamente para confirmar la eliminación permanente', 409)
        if op['status'] == 'preview':
            if op['expires_at'] <= datetime.now(timezone.utc):
                raise DeletionError('La previsualización venció; revise la selección nuevamente', 409)
            targets = manifest(cur, op['study_pk'], op['selection'])
            exams = affected_examinations(cur, op['study_iuid'])
            if fingerprint(targets, exams) != op['snapshot_hash']:
                raise DeletionError('El contenido o los exámenes vinculados cambiaron; revise la selección', 409)
        elif code != op['rejection_code'] or justification.strip() != op['justification']:
            raise DeletionError('Los reintentos deben conservar el motivo y la justificación originales', 409)
        # The unique partial index also prevents races between confirmations.
        try:
            cur.execute("""UPDATE nextris.tbimage_deletion SET status='queued', rejection_code=%s,
                           justification=%s, updated_at=now(), finished_at=NULL, error=NULL WHERE id=%s""",
                        (code, justification.strip(), operation_id))
        except psycopg2.errors.UniqueViolation:
            raise DeletionError('Ya hay una eliminación en curso para este estudio', 409)
        cur.execute("""UPDATE nextris.tbimage_deletion_target SET status='pending', attempts=0, error=NULL
                       WHERE operation_id=%s AND status='failed'""", (operation_id,))


def status(operation_id, user_id, wildcard=False, page=1):
    with database() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        op = load_operation(cur, operation_id, user_id, wildcard)
        cur.execute("""SELECT count(*) AS total,
                       count(*) FILTER (WHERE status='completed') AS completed,
                       count(*) FILTER (WHERE status='failed') AS failed
                       FROM nextris.tbimage_deletion_target WHERE operation_id=%s""", (operation_id,))
        op['progress'] = dict(cur.fetchone())
        cur.execute("""SELECT series_iuid, sop_iuid, status, attempts, error
                       FROM nextris.tbimage_deletion_target WHERE operation_id=%s
                       ORDER BY series_iuid, sop_iuid LIMIT 50 OFFSET %s""", (operation_id, (page-1)*50))
        op['targets'] = [dict(r) for r in cur.fetchall()]
        cur.execute("""SELECT count(*) AS count FROM nextris.available_pacs_instance i
                       JOIN public.series sr ON sr.pk=i.series_fk
                       JOIN public.study s ON s.pk=sr.study_fk WHERE s.study_iuid=%s""", (op['study_iuid'],))
        op['remaining_instances'] = cur.fetchone()['count']
        op['has_images'] = op['remaining_instances'] > 0
        op['target_page'] = page
        for k in ('created_at', 'updated_at', 'expires_at', 'finished_at'):
            op[k] = op[k].isoformat() if op[k] else None
        op['id'] = str(op['id'])
        return op


def target_state(study, series, sop):
    with database() as conn, conn.cursor() as cur:
        cur.execute("""SELECT EXISTS (SELECT 1 FROM public.rejected_instance
                       WHERE study_iuid=%s AND series_iuid=%s AND sop_iuid=%s),
                       EXISTS (SELECT 1 FROM public.instance i
                         JOIN public.series sr ON sr.pk=i.series_fk JOIN public.study s ON s.pk=sr.study_fk
                         WHERE s.study_iuid=%s AND sr.series_iuid=%s AND i.sop_iuid=%s)""",
                    (study, series, sop, study, series, sop))
        rejected, exists = cur.fetchone()
        return rejected, exists


def reconcile(study_uid=None):
    with database() as conn, conn.cursor() as cur:
        cur.execute('SELECT nextris.reconcile_image_availability(%s::varchar)', (study_uid,))


def study_has_images(study_uid):
    with database() as conn, conn.cursor() as cur:
        cur.execute('SELECT EXISTS (SELECT 1 FROM nextris.available_pacs_study WHERE study_iuid=%s)', (study_uid,))
        return cur.fetchone()[0]


def process_target(op, target, pacs):
    if op.get('deletion_mode') == 'permanent':
        return process_permanent_target(op, target, pacs)
    series, sop = target['series_iuid'], target['sop_iuid']
    rejected, exists = target_state(op['study_iuid'], series, sop)
    completed = rejected or not exists  # Also handles a purge after a successful request.
    error, retryable = None, False
    if not completed:
        try:
            response = pacs.reject(op['study_iuid'], series, sop, op['rejection_code'])
            rejected, exists = target_state(op['study_iuid'], series, sop)
            completed = rejected or not exists
            if not completed:
                error = f'PACS HTTP {response.status_code}; rechazo aún no confirmado'
                retryable = response.status_code >= 500 or response.status_code in {200, 202, 401, 409, 429}
        except requests.RequestException:
            # Never assume that a timeout means the PACS did not commit.
            rejected, exists = target_state(op['study_iuid'], series, sop)
            completed = rejected or not exists
            error = None if completed else 'No se pudo confirmar la respuesta del PACS'
            retryable = True
    attempts = target['attempts'] + 1
    state = 'completed' if completed else ('pending' if retryable and attempts < 3 else 'failed')
    with database() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE nextris.tbimage_deletion_target
                       SET status=%s, attempts=%s, error=%s, updated_at=now()
                       WHERE operation_id=%s AND series_iuid=%s AND sop_iuid=%s""",
                    (state, attempts, None if completed else error, str(op['id']), series, sop))
        cur.execute('SELECT nextris.reconcile_image_availability(%s::varchar)', (op['study_iuid'],))
        cur.execute('UPDATE nextris.tbimage_deletion SET updated_at=now(), error=NULL WHERE id=%s', (str(op['id']),))
    return state


def permanent_target_state(op, target):
    """Confirm both index removal and PACS-managed physical storage cleanup."""
    with database() as conn, conn.cursor() as cur:
        cur.execute("""SELECT
            EXISTS (SELECT 1 FROM public.instance WHERE pk=%s),
            EXISTS (SELECT 1 FROM public.rejected_instance r JOIN public.code c ON c.pk=r.reject_code_fk
                WHERE r.study_iuid=%s AND r.series_iuid=%s AND r.sop_iuid=%s
                  AND c.code_value=%s AND c.code_designator=%s),
            EXISTS (SELECT 1 FROM public.location WHERE pk=ANY(%s::bigint[]))""",
            (target['instance_pk'], op['study_iuid'], target['series_iuid'], target['sop_iuid'],
             PERMANENT_CODE, PERMANENT_SCHEME, target['storage_location_pks']))
        return cur.fetchone()


def process_permanent_target(op, target, pacs):
    attempts, error, retryable = target['attempts'], None, False
    if target.get('instance_pk') is None:
        # Never guess the scope of a destructive operation after an upgrade.
        state, error = 'failed', 'Falta la identidad original de la imagen; revise la selección nuevamente'
    else:
        exists, marked, stored = permanent_target_state(op, target)
        if exists or marked:
            attempts += 1
            try:
                if exists and not marked:
                    response = pacs.mark_permanent(op['study_iuid'], target['series_iuid'], target['sop_iuid'])
                    exists, marked, stored = permanent_target_state(op, target)
                    if exists and not marked:
                        response.raise_for_status()
                        raise requests.RequestException('PACS did not confirm permanent deletion marker')
                if marked:
                    response = pacs.purge_permanent()
                    response.raise_for_status()
            except requests.RequestException as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                retryable = status_code is None or status_code >= 500 or status_code in {401, 409, 429}
                error = f'PACS HTTP {status_code}' if status_code else 'No se pudo confirmar la eliminación en PACS'
            # Re-read after ambiguous responses: a timeout can follow a commit.
            exists, marked, stored = permanent_target_state(op, target)
            if (exists or marked) and error is None:
                error, retryable = 'La purga del índice del PACS aún no se confirmó', True
        completed = not exists and not marked and not stored
        if completed:
            state, error = 'completed', None
        elif error:
            state = 'pending' if retryable and attempts < 3 else 'failed'
        else:
            # Storage purge is asynchronous; waiting is not a failed attempt.
            state = 'pending'
    with database() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE nextris.tbimage_deletion_target
            SET status=%s, attempts=%s, error=%s, updated_at=now()
            WHERE operation_id=%s AND series_iuid=%s AND sop_iuid=%s""",
            (state, attempts, error, str(op['id']), target['series_iuid'], target['sop_iuid']))
        cur.execute('SELECT nextris.reconcile_image_availability(%s::varchar)', (op['study_iuid'],))
        cur.execute('UPDATE nextris.tbimage_deletion SET updated_at=now(), error=NULL WHERE id=%s', (str(op['id']),))
    return state


def process_permanent_study(op, pacs):
    """Whole-study deletion includes hidden images and old rejection notes.

    A captured study PK prevents deleting a subsequent upload of the same UID.
    New arrivals after confirmation require another preview; they are not added
    silently to a destructive operation.
    """
    def original_instances():
        with database() as conn, conn.cursor() as cur:
            cur.execute('SELECT EXISTS (SELECT 1 FROM public.study WHERE pk=%s AND study_iuid=%s)',
                        (op['study_pk'], op['study_iuid']))
            if not cur.fetchone()[0]:
                return None
            cur.execute('SELECT i.pk FROM public.instance i JOIN public.series sr ON sr.pk=i.series_fk '
                        'WHERE sr.study_fk=%s', (op['study_pk'],))
            return {r[0] for r in cur.fetchall()}

    current = original_instances()
    if current is None:
        return True
    snapshot = set(op.get('pacs_instance_pks') or [])
    error, retryable = None, False
    if not snapshot or not current <= snapshot:
        error = 'El estudio recibió nuevos objetos; revise la selección nuevamente'
    else:
        try:
            response = pacs.delete_study(op['study_iuid'])
            if original_instances() is None:
                return True
            error = f'PACS HTTP {response.status_code}; eliminación aún no confirmada'
            retryable = response.status_code >= 500 or response.status_code in {200, 202, 204, 401, 409, 429}
        except requests.RequestException as exc:
            if original_instances() is None:
                return True
            code = exc.response.status_code if exc.response is not None else None
            error = f'PACS HTTP {code}' if code else 'No se pudo confirmar la respuesta del PACS'
            retryable = code is None or code >= 500 or code in {401, 409, 429}
    with database() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE nextris.tbimage_deletion_target SET attempts=attempts+1,
            status=CASE WHEN %s AND attempts<2 THEN 'pending' ELSE 'failed' END,
            error=%s, updated_at=now() WHERE operation_id=%s AND status='pending'""",
            (retryable, error, str(op['id'])))
    return False


def work_once(pacs=None):
    pacs = pacs or PacsClient()
    with database() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT * FROM nextris.tbimage_deletion WHERE status IN ('queued','running')
                       ORDER BY updated_at, created_at LIMIT 50""")
        candidates = [dict(r) for r in cur.fetchall()]
    for op in candidates:
        # Session lock survives commits; closing this dedicated connection releases it.
        with database() as lock_conn, lock_conn.cursor() as lock:
            lock.execute('SELECT pg_try_advisory_lock(hashtextextended(%s, 71020))', (op['study_iuid'],))
            if not lock.fetchone()[0]:
                continue
            lock_conn.commit()
            with database() as conn, conn.cursor() as cur:
                cur.execute('SELECT status FROM nextris.tbimage_deletion WHERE id=%s', (str(op['id']),))
                if cur.fetchone()[0] not in {'queued', 'running'}:
                    continue
                cur.execute("UPDATE nextris.tbimage_deletion SET status='running', updated_at=now() WHERE id=%s",
                            (str(op['id']),))
            # One bounded batch, so periodic reconciliation is never starved by a large study.
            with database() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""SELECT * FROM nextris.tbimage_deletion_target
                               WHERE operation_id=%s AND status='pending'
                               ORDER BY attempts, series_iuid, sop_iuid LIMIT 10""", (str(op['id']),))
                targets = [dict(r) for r in cur.fetchall()]
            ready = (op.get('deletion_mode') != 'permanent' or op['selection']['level'] != 'study'
                     or process_permanent_study(op, pacs))
            if ready:
                for target in targets:
                    process_target(op, target, pacs)
            with database() as conn, conn.cursor() as cur:
                cur.execute("""SELECT count(*) FILTER (WHERE status='pending'),
                               count(*) FILTER (WHERE status='completed'), count(*) FILTER (WHERE status='failed')
                               FROM nextris.tbimage_deletion_target WHERE operation_id=%s""", (str(op['id']),))
                pending, completed, failed = cur.fetchone()
                cur.execute('SELECT nextris.reconcile_image_availability(%s::varchar)', (op['study_iuid'],))
                if not pending:
                    state = 'completed' if not failed else ('partial' if completed else 'failed')
                    cur.execute("""UPDATE nextris.tbimage_deletion SET status=%s, updated_at=now(),
                                   finished_at=now(), error=%s WHERE id=%s""",
                                (state, 'Hay imágenes cuya eliminación no se pudo confirmar' if failed else None, str(op['id'])))
            return True
    return False


def run_worker():
    def reconcile_loop():
        while True:
            try:
                reconcile()
            except Exception:
                log.exception('Image availability reconciliation will retry')
            time.sleep(30)

    threading.Thread(target=reconcile_loop, name='image-availability', daemon=True).start()
    pacs = PacsClient()
    while True:
        try:
            busy = work_once(pacs)
            time.sleep(1 if busy else 2)
        except Exception:
            log.exception('Image deletion worker will retry persisted work')
            time.sleep(5)
