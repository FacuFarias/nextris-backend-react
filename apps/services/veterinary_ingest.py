"""Idempotent RIS-only ingestion of available PACS studies for the simple workflow."""
import hashlib
import json
import logging
import unicodedata
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import re
import os

from psycopg2.extras import Json, RealDictCursor
from apps.services import veterinary as vet
from apps.services.simple_veterinary import enabled
from apps.services.veterinary_image_reference import reference_with_cursor, _name

log = logging.getLogger(__name__)
SOURCE = 'primary-pacs'


def normalized_name(value):
    return unicodedata.normalize('NFC', _name(value)).casefold()


def identity(reference):
    dicom = reference['dicom']
    name = normalized_name(dicom.get('patient_name'))
    patient_id = str(dicom.get('patient_id') or '').strip()
    issuer = str(dicom.get('issuer') or '').strip()
    if not name or not patient_id or patient_id.casefold() in ('unknown', 'n/a', 'none', 'null', '*'):
        return None
    key = hashlib.sha256(json.dumps([SOURCE, issuer, patient_id, name], ensure_ascii=False).encode()).hexdigest()
    return dict(key=key, patient_id=patient_id, issuer=issuer, name=name)


def _remember_identity(cursor, external, animal_id):
    if not external:
        return False
    cursor.execute('''INSERT INTO nextris.pacs_animal_identity
        (identity_key,source,patient_id,issuer,normalized_name,animal_guid)
        VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(identity_key) DO NOTHING''',
        (external['key'], SOURCE, external['patient_id'], external['issuer'], external['name'], animal_id))
    cursor.execute('SELECT animal_guid FROM nextris.pacs_animal_identity WHERE identity_key=%s', (external['key'],))
    return str(cursor.fetchone()['animal_guid']) != animal_id


def _metadata(cursor, study):
    try:
        return reference_with_cursor(cursor, study['pk'])
    except vet.VeterinaryError as error:
        if error.status != 422:
            raise
        # An unreadable optional attribute must not obstruct a valid received image.
        return {'initial': {'name': '', 'gender': 'O', 'reproductive_status': 'unknown'},
                'dicom': {'study_description': study['study_desc'] or ''}, 'metadata_error': True}


def _save_state(cursor, study, animal_id, exam_id, external, provisional, metadata):
    cursor.execute('''INSERT INTO nextris.pacs_auto_order
        (study_iuid,pacs_study_pk,animal_guid,examination_guid,identity_key,provisional,status,
         metadata,instance_count,source_updated_at,attempts)
        VALUES(%s,%s,%s,%s,%s,%s,'ready',%s,%s,%s,1)
        ON CONFLICT(study_iuid) DO UPDATE SET pacs_study_pk=excluded.pacs_study_pk,animal_guid=excluded.animal_guid,
          examination_guid=excluded.examination_guid,identity_key=excluded.identity_key,
          provisional=excluded.provisional,status='ready',metadata=excluded.metadata,
          instance_count=excluded.instance_count,source_updated_at=excluded.source_updated_at,
          attempts=nextris.pacs_auto_order.attempts+1,last_error=NULL,retry_at=NULL,updated_at=now()''',
        (study['study_iuid'], study['pk'], animal_id, exam_id, external['key'] if external else None,
         provisional, Json(metadata), study['instance_count'], study['source_updated_at']))


def _refresh_missing(cursor, state, reference, order):
    """Only fill unreviewed placeholders created by us; never overwrite human work."""
    previous = state['metadata'] if state else {}
    if not previous.get('created_animal') or order['isexecuted'] or order['isreported']:
        return
    cursor.execute('SELECT 1 FROM nextris.tbreport WHERE idexamination=%s AND wassaved LIMIT 1', (order['guid'],))
    if cursor.fetchone():
        return
    animal = vet.animal(cursor, order['idpatient'], lock=True)
    changes = {}
    initial = reference['initial']
    if state['provisional'] and animal['name'] == previous.get('display_name') and initial.get('name') and len(initial['name']) <= 100:
        changes['name'] = initial['name']
    if not previous.get('initial', {}).get('birthdate') and not animal['birthdate'] and initial.get('birthdate'):
        changes['birthdate'] = initial['birthdate']
    if previous.get('initial', {}).get('gender', 'O') == 'O' and animal['sexcode'] == 'O' and initial.get('gender') in ('M', 'F'):
        changes['gender'] = initial['gender']
    veterinary = {}
    if not previous.get('initial', {}).get('species_id') and not animal['species_id'] and initial.get('species_id'):
        veterinary['species_id'] = initial['species_id']
        if initial.get('breed_id'):
            veterinary['breed_id'] = initial['breed_id']
    if veterinary:
        changes['veterinary'] = veterinary
    if changes:
        vet.save_animal(cursor, changes, None, str(order['idpatient']))


def process_study(study_pk):
    if not enabled():
        raise RuntimeError('Automatic orders require simple_veterinary workflow')
    with vet.database() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
        # Match the lock used by explicit animal reassignment, outside PACS ingestion transactions.
        cursor.execute('''SELECT s.*,GREATEST(s.updated_time,p.updated_time) AS source_updated_at,
            (SELECT count(*) FROM nextris.available_pacs_series sr
             JOIN nextris.available_pacs_instance i ON i.series_fk=sr.pk WHERE sr.study_fk=s.pk) AS instance_count
            FROM public.study s JOIN nextris.available_pacs_study a ON a.pk=s.pk
            JOIN public.patient p ON p.pk=s.patient_fk WHERE s.pk=%s FOR UPDATE OF s''', (study_pk,))
        study = cursor.fetchone()
        if not study or not study['instance_count']:
            return None
        uid = study['study_iuid']
        cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('auto-dicom-study:' + uid,))
        cursor.execute('SELECT * FROM nextris.pacs_auto_order WHERE study_iuid=%s FOR UPDATE', (uid,))
        state = cursor.fetchone()
        cursor.execute('''SELECT e.* FROM nextris.tbexamination e WHERE EXISTS(
            SELECT 1 FROM nextris.examination_pacs_study ep
            WHERE ep.examination_guid=e.guid AND ep.study_iuid=%s) ORDER BY e.guid FOR UPDATE OF e''', (uid,))
        orders = cursor.fetchall()
        if len(orders) > 1:
            raise vet.VeterinaryError('El estudio tiene varias órdenes; requiere revisión manual', 409)
        if not orders and state and state['examination_guid']:
            # Respect an explicit manual unlink instead of reattaching the old order.
            _save_state(cursor, study, state['animal_guid'], state['examination_guid'], None,
                        state['provisional'], {**state['metadata'], 'manually_detached': True})
            return dict(examination_guid=state['examination_guid'], preserved=True)
        reference = _metadata(cursor, study)
        external = identity(reference)
        original = (state['metadata'].get('original_reference') or {
            'initial': state['metadata'].get('initial', {}), 'dicom': state['metadata'].get('dicom', {})}) if state else reference
        identity_changed = bool(state and state['identity_key'] and (not external or external['key'] != state['identity_key']))
        if identity_changed:
            # PACS patient attributes can be shared by several historical studies.
            # A changed name/ID on that shared row must not teach the old animal a new identity.
            cursor.execute('SELECT * FROM nextris.pacs_animal_identity WHERE identity_key=%s', (state['identity_key'],))
            known = cursor.fetchone()
            external = dict(key=state['identity_key'],patient_id=known['patient_id'],issuer=known['issuer'],
                            name=known['normalized_name']) if known else identity(original)
        if external:
            cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('auto-dicom-animal:' + external['key'],))
        metadata = {**reference, 'source': SOURCE, 'original_reference': original,
                    'created_animal': bool(state and state['metadata'].get('created_animal'))}
        if identity_changed:
            metadata['identity_changed_in_pacs'] = True
        order = orders[0] if orders else None
        provisional = not bool(external)
        if order:
            animal_id = str(order['idpatient'])
            vet.animal(cursor, animal_id)
            cursor.execute('UPDATE nextris.tbexamination SET isimage=1 WHERE guid=%s AND COALESCE(isimage,0)<>1', (order['guid'],))
            if not identity_changed:
                _refresh_missing(cursor, state, reference, order)
            if state:
                metadata['display_name'] = state['metadata'].get('display_name')
            # Already-linked records remain unchanged, including clinical context and signed reports.
        else:
            animal_id = None
            if external:
                cursor.execute('SELECT animal_guid FROM nextris.pacs_animal_identity WHERE identity_key=%s', (external['key'],))
                match = cursor.fetchone()
                if match:
                    animal_id = str(match['animal_guid'])
                else:
                    # Legacy identities can only match BOTH the actual identifier and name.
                    cursor.execute("""SELECT p.guid,p.name FROM nextris.datapatient p
                        WHERE p.patient_kind='animal' AND p.patientid=%s AND NOT EXISTS(
                            SELECT 1 FROM nextris.pacs_animal_identity other WHERE other.animal_guid=p.guid
                              AND (other.source<>%s OR other.issuer<>%s OR other.patient_id<>%s OR other.normalized_name<>%s))
                        ORDER BY p.guid""", (external['patient_id'], SOURCE, external['issuer'], external['patient_id'], external['name']))
                    matches = [row for row in cursor.fetchall() if normalized_name(row['name']) == external['name']]
                    if len(matches) == 1:
                        animal_id = str(matches[0]['guid'])
                    elif len(matches) > 1:
                        provisional = True
            if not animal_id:
                initial = reference['initial']
                name = initial.get('name', '')
                if not name or len(name) > 100:
                    name = 'Animal por revisar · ' + uid[-24:]
                    provisional = True
                animal = vet.save_animal(cursor, {'name': name, 'gender': initial.get('gender', 'O'),
                    'birthdate': initial.get('birthdate'), 'veterinary': {key: initial[key] for key in
                        ('species_id', 'breed_id', 'reproductive_status') if key in initial}}, None)
                animal_id = str(animal['guid'])
                metadata.update(created_animal=True, display_name=name)
                if initial.get('weight_kg'):
                    measured_at = datetime.now(timezone.utc)
                    note = 'PatientWeight DICOM; fecha de importación (sin fecha de estudio válida).'
                    try:
                        tm = re.sub(r'\D', '', reference['dicom'].get('study_time', ''))[:6].ljust(6, '0')
                        measured_at = datetime.strptime(reference['dicom'].get('study_date', '') + tm, '%Y%m%d%H%M%S').replace(
                            tzinfo=ZoneInfo(os.getenv('NEXTRIS_TIMEZONE', 'America/Argentina/Buenos_Aires')))
                        if measured_at.date() > datetime.now(measured_at.tzinfo).date():
                            raise ValueError('Future acquisition date')
                        note = 'PatientWeight DICOM; fecha del estudio original.'
                    except ValueError:
                        measured_at = datetime.now(timezone.utc)
                    cursor.execute("""INSERT INTO nextris.patient_clinical_entry
                        (id,patient_id,category,note,weight_kg,recorded_at,created_by)
                        VALUES(%s,%s,'weight',%s,%s,%s,NULL)""",
                        (str(uuid.uuid4()), animal_id, note, initial['weight_kg'], measured_at))
            else:
                vet.animal(cursor, animal_id)
            # Reuse an unambiguous reserved order only for this same animal and accession.
            accession = str(study['accession_no'] or '').strip()
            if accession and accession != '*':
                cursor.execute('''SELECT * FROM nextris.tbexamination WHERE idpatient=%s AND localacc=%s
                    AND COALESCE(isimage,0)=0 AND COALESCE(isreported,0)=0
                    AND COALESCE(workflow_state,'pending')<>'cancelled' ORDER BY guid FOR UPDATE''', (animal_id, accession))
                pending = cursor.fetchall()
                if len(pending) == 1:
                    order = pending[0]
                    cursor.execute('UPDATE nextris.tbexamination SET studyinstanceuid=%s,isimage=1 WHERE guid=%s', (uid, order['guid']))
            if not order:
                exam_id = str(uuid.uuid4())
                context = vet.protocol_context(cursor, animal_id)
                context['dicom_reference'] = reference['dicom']
                cursor.execute('''INSERT INTO nextris.tbexamination
                    (guid,idpatient,localacc,admisionnumber,studyinstanceuid,status,isexecuted,isreported,isimage,
                     createdon,"w-order",veterinary_context)
                    VALUES(%s,%s,%s,%s,%s,'Scheduled',0,0,1,now(),0,%s)''',
                    (exam_id, animal_id, accession if accession and accession != '*' else 'VT' + uuid.uuid4().hex[:12].upper(),
                     'ADM' + uuid.uuid4().hex[:12].upper(), uid, Json(context)))
                cursor.execute('INSERT INTO nextris.tbreport(guid,idexamination,idpatient,wassaved) VALUES(%s,%s,%s,false)',
                               (str(uuid.uuid4()), exam_id, animal_id))
                order = {'guid': exam_id, 'idpatient': animal_id}
        conflict = _remember_identity(cursor, external, animal_id)
        provisional = provisional or conflict
        if conflict:
            metadata['identity_conflict'] = True
        cursor.execute('''INSERT INTO nextris.tbpacs_study_link
            (pacs_study_pk,pacs_study_iuid,order_guid,order_study_uuid,source,linked_by_username)
            SELECT %s,%s,%s,%s,'auto','DICOM automático'
            WHERE NOT EXISTS(SELECT 1 FROM nextris.tbpacs_study_link
                WHERE link_status='linked' AND (pacs_study_iuid=%s OR order_guid=%s))
            ON CONFLICT DO NOTHING''', (study_pk, uid, order['guid'], uid, uid, order['guid']))
        _save_state(cursor, study, animal_id, str(order['guid']), external, provisional, metadata)
        return dict(examination_guid=str(order['guid']), animal_guid=animal_id, provisional=provisional)


def candidates(limit=100):
    with vet.database() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute('''SELECT s.pk FROM nextris.available_pacs_study s JOIN public.patient p ON p.pk=s.patient_fk
            LEFT JOIN nextris.pacs_auto_order a ON a.study_iuid=s.study_iuid
            WHERE (a.study_iuid IS NULL OR (a.status='error' AND a.retry_at<=now()) OR
                (a.status='ready' AND (a.source_updated_at IS DISTINCT FROM GREATEST(s.updated_time,p.updated_time)
                    OR a.instance_count<>(SELECT count(*) FROM nextris.available_pacs_series sr
                      JOIN nextris.available_pacs_instance i ON i.series_fk=sr.pk WHERE sr.study_fk=s.pk))))
            ORDER BY CASE WHEN EXISTS(SELECT 1 FROM nextris.examination_pacs_study ep
                         WHERE ep.study_iuid=s.study_iuid) THEN 0 ELSE 1 END,s.pk LIMIT %s''', (limit,))
        return [row['pk'] for row in cursor.fetchall()]


def record_failure(study_pk, error):
    with vet.database() as connection, connection.cursor() as cursor:
        cursor.execute('''INSERT INTO nextris.pacs_auto_order(study_iuid,pacs_study_pk,status,attempts,last_error,retry_at)
            SELECT study_iuid,pk,'error',1,%s,now()+interval '5 seconds' FROM public.study WHERE pk=%s
            ON CONFLICT(study_iuid) DO UPDATE SET status='error',attempts=nextris.pacs_auto_order.attempts+1,
              last_error=excluded.last_error,retry_at=now()+least(300,5*power(2,least(nextris.pacs_auto_order.attempts,6)))*interval '1 second',
              updated_at=now() ''', (type(error).__name__ + ': ' + str(error)[:500], study_pk))


def run_once():
    if not enabled():
        raise RuntimeError('Automatic orders require simple_veterinary workflow')
    processed = failed = 0
    for pk in candidates():
        try:
            if process_study(pk):
                processed += 1
        except Exception as error:
            record_failure(pk, error)
            failed += 1
            log.error('DICOM ingestion failed for PACS study %s (%s)', pk, type(error).__name__)
    return {'processed': processed, 'failed': failed}
