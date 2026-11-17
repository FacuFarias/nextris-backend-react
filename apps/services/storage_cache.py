"""Inspect and retire local copies through the existing safe PACS exporters.

The live TTL policy is shared with dcm4chee-cache-ttl, including its timezone.
SQL is read-only. The PACS owns export queues, location updates and file removal.
"""
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from psycopg2.extras import RealDictCursor
from apps.home.services.database_service import DatabaseService
from apps.services.image_deletions import PacsClient

log = logging.getLogger(__name__)
UTC = dt.timezone.utc
EXPORTERS = {'fs1': 'TTLRemoveInitial', 'fs1-retrieve': 'TTLRemoveRetrieved'}
TERMINAL = {'COMPLETED', 'FAILED', 'WARNING', 'CANCELED', 'CANCELLED'}


class CacheError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def policy():
    # Missing/unreadable policy must not silently invent expiration dates.
    try:
        config = json.loads(Path(os.getenv('NEXTRIS_CACHE_POLICY_PATH',
            '/opt/dcm4chee/backblaze/cache-policy.json')).read_text())
        if (config['initial_storage'], config['retrieval_storage'], config['remote_storage']) != ('fs1', 'fs1-retrieve', 'b2'):
            raise ValueError('Unsupported storages')
        ZoneInfo(config['timezone'])
        for key in ('same_day_initial_seconds', 'other_initial_seconds', 'retrieval_seconds', 'quiet_write_seconds', 'timer_seconds'):
            if not isinstance(config[key], int) or config[key] <= 0:
                raise ValueError('Invalid interval')
        return config
    except (OSError, KeyError, ValueError) as exc:
        raise CacheError('No se pudo leer la política de caché del PACS', 503) from exc


def as_utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def retention(row, config, now):
    entered = as_utc(row['entered_at'])
    if row['storage'] == config['retrieval_storage']:
        seconds = config['retrieval_seconds']
    else:
        same_day = row['study_date'] == entered.astimezone(ZoneInfo(config['timezone'])).strftime('%Y%m%d')
        seconds = config['same_day_initial_seconds'] if same_day else config['other_initial_seconds']
    expires = entered + dt.timedelta(seconds=seconds)
    reason = None
    if row['deleting']:
        reason = 'El PACS está procesando una eliminación del estudio.'
    elif not row['all_backed_up']:
        reason = 'Hay imágenes sin copia válida del mismo tamaño en B2.'
    elif (now - as_utc(row['last_write_at'])).total_seconds() < config['quiet_write_seconds']:
        reason = 'El estudio está recibiendo imágenes. Esperá a que finalice la recepción.'
    return dict(entered_at=entered.isoformat(), expires_at=expires.isoformat(), ttl_seconds=seconds,
                expired=now >= expires, can_remove=reason is None, blocked_reason=reason)


CACHE_ROWS = """SELECT st.pk AS study_pk, st.study_iuid AS study_uid, st.study_date,
        st.study_time, st.study_desc AS description, st.accession_no AS accession,
        st.study_deleting AS deleting, coalesce(pn.alphabetic_name,'') AS patient_name,
        l.storage_id AS storage, min(l.created_time) AS entered_at,
        greatest(max(i.updated_time), max(l.created_time)) AS last_write_at,
        count(DISTINCT i.pk) FILTER (WHERE l.object_type=0) AS instances,
        count(*) AS objects, sum(l.object_size) AS bytes,
        array_agg(l.pk ORDER BY l.pk) AS location_ids,
        bool_and(EXISTS(SELECT 1 FROM public.location b
            WHERE b.instance_fk=l.instance_fk AND b.storage_id='b2' AND b.status=0
              AND b.object_type=l.object_type AND b.object_size=l.object_size)) AS all_backed_up
    FROM public.location l
    JOIN public.instance i ON i.pk=l.instance_fk
    JOIN public.series se ON se.pk=i.series_fk
    JOIN public.study st ON st.pk=se.study_fk
    JOIN public.patient p ON p.pk=st.patient_fk
    LEFT JOIN public.person_name pn ON pn.pk=p.pat_name_fk
    WHERE l.status=0 AND l.storage_id IN ('fs1','fs1-retrieve') {scope}
    GROUP BY st.pk, pn.alphabetic_name, l.storage_id
"""


def rows(cursor, study_pk=None):
    cursor.execute(CACHE_ROWS.format(scope='AND st.pk=%s' if study_pk is not None else '') +
                   ' ORDER BY min(l.created_time), st.pk, l.storage_id',
                   (study_pk,) if study_pk is not None else ())
    return [dict(row) for row in cursor.fetchall()]


def studies(page=1, per_page=25, search=''):
    config = policy()
    now = dt.datetime.now(UTC)
    with DatabaseService.get_db_cursor() as (cursor, connection):
        # Page at study level so copies in different stores stay together.
        cursor.execute("""SELECT count(DISTINCT st.pk) FROM public.study st
            JOIN public.patient p ON p.pk=st.patient_fk
            LEFT JOIN public.person_name pn ON pn.pk=p.pat_name_fk
            WHERE EXISTS (SELECT 1 FROM public.series se JOIN public.instance i ON i.series_fk=se.pk
                JOIN public.location l ON l.instance_fk=i.pk WHERE se.study_fk=st.pk
                AND l.status=0 AND l.storage_id IN ('fs1','fs1-retrieve'))
            AND (%s='' OR concat_ws(' ',pn.alphabetic_name,st.study_desc,st.accession_no,st.study_iuid) ILIKE %s)""",
                       (search, '%' + search + '%'))
        total = int(cursor.fetchone()[0])
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""SELECT st.pk FROM public.study st
                JOIN public.patient p ON p.pk=st.patient_fk
                LEFT JOIN public.person_name pn ON pn.pk=p.pat_name_fk
                JOIN public.series se ON se.study_fk=st.pk JOIN public.instance i ON i.series_fk=se.pk
                JOIN public.location l ON l.instance_fk=i.pk
                WHERE l.status=0 AND l.storage_id IN ('fs1','fs1-retrieve')
                AND (%s='' OR concat_ws(' ',pn.alphabetic_name,st.study_desc,st.accession_no,st.study_iuid) ILIKE %s)
                GROUP BY st.pk ORDER BY min(l.created_time),st.pk LIMIT %s OFFSET %s""",
                        (search, '%' + search + '%', per_page, (page - 1) * per_page))
            ids = [row['pk'] for row in cur.fetchall()]
            cur.execute(CACHE_ROWS.format(scope='AND st.pk=ANY(%s)') +
                        ' ORDER BY min(l.created_time),st.pk,l.storage_id', (ids,))
            groups = {}
            for raw in cur.fetchall():
                row = dict(raw)
                group = groups.setdefault(row['study_pk'], {key: row[key] for key in
                    ('study_pk', 'study_uid', 'study_date', 'study_time', 'description', 'accession', 'patient_name')})
                copy = {key: row[key] for key in ('storage', 'instances', 'objects', 'bytes', 'all_backed_up')}
                for key in ('instances', 'objects', 'bytes'):
                    copy[key] = int(copy[key])
                copy.update(retention(row, config, now))
                group.setdefault('copies', []).append(copy)
            cur.execute("""SELECT DISTINCT ON (study_iuid,exporter_id)
                    study_iuid,exporter_id,task_status,created_time
                FROM public.task WHERE study_iuid=ANY(%s) AND exporter_id=ANY(%s)
                ORDER BY study_iuid,exporter_id,created_time DESC,pk DESC""",
                        ([group['study_uid'] for group in groups.values()], list(EXPORTERS.values())))
            tasks = {(r['study_iuid'], r['exporter_id']): r for r in cur.fetchall()}
            for group in groups.values():
                for copy in group['copies']:
                    task = tasks.get((group['study_uid'], EXPORTERS[copy['storage']]))
                    copy['queue_status'] = None
                    if task and as_utc(task['created_time']) >= dt.datetime.fromisoformat(copy['entered_at']):
                        # dcm4chee 5.35.2 Task.Status: 0 scheduled, 1 in process,
                        # 6 retry; 3 warning and 4 failed are terminal and retryable.
                        if task['task_status'] in (0, 1, 6):
                            copy.update(queue_status='queued', can_remove=False)
                        elif task['task_status'] in (3, 4):
                            copy['queue_status'] = 'failed'
        connection.rollback()
    return dict(items=list(groups.values()), total=total, page=page, per_page=per_page,
                timezone=config['timezone'], policy_enabled=bool(config['enabled']),
                poll_seconds=config['timer_seconds'], generated_at=now.isoformat())


def pending(pacs, study_uid, exporter):
    response = pacs.request('GET', pacs.root + '/monitor/export', params={
        'StudyInstanceUID': study_uid, 'ExporterID': exporter, 'limit': 100})
    response.raise_for_status()
    return any(task['status'] not in TERMINAL for task in response.json())


def remove(study_pk, storage, actor):
    if not isinstance(storage, str) or storage not in EXPORTERS:
        raise CacheError('Almacenamiento local inválido')
    config = policy()
    with DatabaseService.get_db_cursor() as (cursor, connection):
        # Serializes clicks from separate Gunicorn workers. The archive revalidates
        # the actual removal after its B2 export has completed successfully.
        cursor.execute('SELECT pg_try_advisory_xact_lock(%s, %s)', (731025, study_pk))
        if not cursor.fetchone()[0]:
            raise CacheError('Ya se está procesando una solicitud para este estudio', 409)
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            before = next((r for r in rows(cur, study_pk) if r['storage'] == storage), None)
            if before is None:
                raise CacheError('El estudio ya no está disponible en esa caché', 404)
            state = retention(before, config, dt.datetime.now(UTC))
            if not state['can_remove']:
                raise CacheError(state['blocked_reason'], 409)
            pacs = PacsClient()
            exporter = EXPORTERS[storage]
            if pending(pacs, before['study_uid'], exporter):
                return dict(status='queued', already_queued=True)
            fresh = next((r for r in rows(cur, study_pk) if r['storage'] == storage), None)
            if fresh is None or fresh['location_ids'] != before['location_ids']:
                raise CacheError('La caché cambió. Actualizá el listado antes de continuar.', 409)
            state = retention(fresh, config, dt.datetime.now(UTC))
            if not state['can_remove']:
                raise CacheError(state['blocked_reason'], 409)
            response = pacs.request('POST', pacs.root + '/aets/AS_RECEIVED/rs/studies/' +
                                    quote(fresh['study_uid'], safe='') + '/export/' + exporter)
            if response.status_code not in (200, 202):
                raise CacheError('El PACS no pudo programar la eliminación de la copia local', 502)
            log.info('Cache removal queued actor=%s study_hash=%s storage=%s', actor,
                     hashlib.sha256(fresh['study_uid'].encode()).hexdigest()[:12], storage)
        connection.rollback()
    return dict(status='queued', already_queued=False)
