"""Shared veterinary domain services. Existing patient/examination identity remains authoritative."""
import os
import re
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from html import escape

import psycopg2
from psycopg2.extras import RealDictCursor, Json


_ANIMAL_FIELD_RE = re.compile(r'\{\{\s*([^{}<>]+?)\s*\}\}')


class VeterinaryError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def mode():
    value = os.getenv('NEXTRIS_PATIENT_MODE', 'human')
    if value not in ('human', 'veterinary'):
        raise RuntimeError('NEXTRIS_PATIENT_MODE must be human or veterinary')
    return value


@contextmanager
def database():
    c = psycopg2.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT', '5432'),
                         dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'), password=os.getenv('DB_PASS'))
    try:
        with c:
            yield c
    finally:
        c.close()


def plain(value):
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if isinstance(value, (uuid.UUID, date, datetime)):
        return str(value) if isinstance(value, uuid.UUID) else value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def identifier(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise VeterinaryError('Identificador inválido')


def weight(value, *, optional=True, allow_zero=False):
    if optional and value in (None, ''):
        return None
    if isinstance(value, bool):
        raise VeterinaryError('El peso debe ser un número positivo en kg')
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise VeterinaryError('Peso inválido')
    if not result.is_finite() or result < 0 or (result == 0 and not allow_zero) or result >= Decimal('1000000000'):
        raise VeterinaryError('El peso debe ser positivo y finito')
    if result.as_tuple().exponent < -3:
        raise VeterinaryError('El peso admite hasta tres decimales en kg')
    return result


def flag(value, default=False):
    if value is None:
        return default
    if not isinstance(value, bool):
        raise VeterinaryError('Se esperaba un valor booleano')
    return value


def animal(cursor, patient_id, *, lock=False):
    cursor.execute('SELECT * FROM nextris.datapatient WHERE guid=%s AND patient_kind=\'animal\'' + (' FOR UPDATE' if lock else ''), (str(patient_id),))
    row = cursor.fetchone()
    if not row:
        raise VeterinaryError('Animal no encontrado', 404)
    return row


def patient_context(cursor, patient_id):
    cursor.execute('''SELECT p.guid,p.patientid,p.name,p.surname,p.birthdate,p.sexcode AS gender,
        p.birthdate_estimated,p.reproductive_status,p.species_id,p.breed_id,
        s.name AS species_name,b.name AS breed_name,s.code_value AS species_code_value,s.coding_scheme AS species_coding_scheme,
        b.code_value AS breed_code_value,b.coding_scheme AS breed_coding_scheme,
        (SELECT weight_kg FROM nextris.patient_clinical_entry ce WHERE ce.patient_id=p.guid
          AND ce.weight_kg IS NOT NULL ORDER BY ce.recorded_at DESC,ce.created_at DESC,ce.id DESC LIMIT 1) AS weight_kg
        FROM nextris.datapatient p LEFT JOIN nextris.veterinary_species s ON s.id=p.species_id
        LEFT JOIN nextris.veterinary_breed b ON b.id=p.breed_id WHERE p.guid=%s AND p.patient_kind='animal' ''', (str(patient_id),))
    row = cursor.fetchone()
    if not row:
        return None
    result = dict(row)
    cursor.execute('''SELECT r.id,r.name,r.kind,r.organization,pr.role,pr.is_primary
        FROM nextris.patient_responsibility pr JOIN nextris.responsible_party r ON r.id=pr.responsible_id
        WHERE pr.patient_id=%s AND pr.valid_from<=now() AND (pr.valid_to IS NULL OR pr.valid_to>now())
        ORDER BY pr.is_primary DESC,pr.valid_from''', (str(patient_id),))
    result['responsibles'] = cursor.fetchall()
    return plain(result)


def animal_dict(cursor, patient_id):
    context = patient_context(cursor, patient_id)
    if not context:
        raise VeterinaryError('Animal no encontrado', 404)
    cursor.execute('SELECT count(*) AS count FROM nextris.tbexamination WHERE idpatient=%s', (str(patient_id),))
    count = cursor.fetchone()['count']
    veterinary = {key: context.get(key) for key in ('species_id','breed_id','species_name','breed_name','birthdate_estimated','reproductive_status','weight_kg')}
    return dict(guid=context['guid'], patientid=context['patientid'], name=context['name'], surname=context['surname'] or '',
                birthdate=context['birthdate'], gender=context['gender'], patient_kind='animal', veterinary=veterinary,
                responsibles=context['responsibles'], study_count=count, nationalcode=None, email=None, phone=None)


def save_animal(cursor, payload, actor, patient_id=None):
    if not isinstance(payload, dict):
        raise VeterinaryError('Se requiere un objeto de paciente')
    existing = animal(cursor, patient_id, lock=True) if patient_id else {}
    if payload.get('patient_kind', 'animal') != 'animal':
        raise VeterinaryError('Esta instalación admite altas veterinarias')
    name = str(payload.get('name', payload.get('nombre', existing.get('name', ''))) or '').strip()
    if not name or len(name) > 100:
        raise VeterinaryError('El nombre del animal es obligatorio (máximo 100 caracteres)')
    if patient_id and 'patientid' in payload and payload['patientid'] != existing['patientid']:
        raise VeterinaryError('El identificador del animal no puede cambiarse')
    vet = payload.get('veterinary') or {}
    if not isinstance(vet, dict):
        raise VeterinaryError('Datos veterinarios inválidos')
    species = vet.get('species_id', existing.get('species_id')) or None
    breed = vet.get('breed_id', existing.get('breed_id')) or None
    if species:
        species = identifier(species)
        cursor.execute('SELECT id FROM nextris.veterinary_species WHERE id=%s AND is_active', (species,))
        if not cursor.fetchone():
            raise VeterinaryError('Especie no válida')
    if breed:
        breed = identifier(breed)
        cursor.execute('SELECT id FROM nextris.veterinary_breed WHERE id=%s AND species_id=%s AND is_active', (breed,species))
        if not cursor.fetchone():
            raise VeterinaryError('La raza no corresponde a la especie')
    birth = payload.get('birthdate',payload.get('fecha_nac', existing.get('birthdate'))) or None
    if birth:
        try:
            birth = date.fromisoformat(str(birth))
        except ValueError:
            raise VeterinaryError('Fecha de nacimiento inválida')
        if birth > date.today():
            raise VeterinaryError('La fecha de nacimiento no puede ser futura')
    estimated = flag(vet.get('birthdate_estimated'), existing.get('birthdate_estimated',False))
    if estimated and not birth:
        raise VeterinaryError('Indique la fecha estimada o deje ambos campos vacíos')
    reproductive = vet.get('reproductive_status', existing.get('reproductive_status','unknown'))
    if reproductive not in ('unknown','intact','neutered'):
        raise VeterinaryError('Estado reproductivo inválido')
    sex = payload.get('gender',payload.get('sexo', existing.get('sexcode','O')))
    sex = {'Otro':'O','':'O',None:'O'}.get(sex,sex)
    if sex not in ('M','F','O'):
        raise VeterinaryError('Sexo inválido')
    measured_weight = weight(vet.get('weight_kg'))
    if patient_id:
        cursor.execute('''UPDATE nextris.datapatient SET name=%s,birthdate=%s,sexcode=%s,species_id=%s,
            breed_id=%s,birthdate_estimated=%s,reproductive_status=%s WHERE guid=%s''',
            (name,birth,sex,species,breed,estimated,reproductive,str(patient_id)))
    else:
        patient_id = str(uuid.uuid4())
        cursor.execute("SELECT 'VT'||lpad(nextval('nextris.veterinary_patient_number')::text,8,'0') AS patientid")
        patientid = cursor.fetchone()['patientid']
        cursor.execute('''INSERT INTO nextris.datapatient(guid,patientid,name,surname,birthdate,sexcode,patient_kind,species_id,
            breed_id,birthdate_estimated,reproductive_status) VALUES(%s,%s,%s,'',%s,%s,'animal',%s,%s,%s,%s)''',
            (patient_id,patientid,name,birth,sex,species,breed,estimated,reproductive))
    if measured_weight is not None:
        add_clinical_entry(cursor,patient_id,{'category':'weight','weight_kg':str(measured_weight)},actor)
    return animal_dict(cursor,patient_id)


def add_clinical_entry(cursor, patient_id, data, actor):
    animal(cursor,patient_id)
    category = data.get('category','history')
    if category not in ('history','alert','weight','correction'):
        raise VeterinaryError('Tipo de antecedente inválido')
    measured = weight(data.get('weight_kg'), optional=category!='weight')
    note = str(data.get('note','')).strip()
    if category!='weight' and not note:
        raise VeterinaryError('El antecedente no puede estar vacío')
    recorded = data.get('recorded_at') or None
    if recorded:
        try:
            parsed = datetime.fromisoformat(recorded.replace('Z','+00:00'))
            if parsed.date()>date.today():
                raise ValueError()
        except (ValueError,TypeError):
            raise VeterinaryError('Fecha del antecedente inválida')
    corrects = data.get('corrects_id') or None
    if corrects:
        corrects=identifier(corrects)
        cursor.execute('SELECT id FROM nextris.patient_clinical_entry WHERE id=%s AND patient_id=%s',(corrects,str(patient_id)))
        if not cursor.fetchone():
            raise VeterinaryError('El antecedente a corregir no pertenece al animal')
    key=str(uuid.uuid4())
    cursor.execute('''INSERT INTO nextris.patient_clinical_entry(id,patient_id,category,note,weight_kg,recorded_at,created_by,corrects_id)
        VALUES(%s,%s,%s,%s,%s,COALESCE(%s::timestamptz,now()),%s,%s) RETURNING *''',
        (key,str(patient_id),category,note,measured,recorded,str(actor),corrects))
    return plain(cursor.fetchone())


def responsible_account(cursor, account_id):
    cursor.execute('''SELECT up.guid,up.username,up.firstlogin,up.status,up.responsible_party_id,up.portal_auth_version,
        rp.name,rp.email,rp.phone,rp.address,rp.is_active FROM nextris.tbuser_patient up
        JOIN nextris.responsible_party rp ON rp.id=up.responsible_party_id WHERE up.guid=%s''',(str(account_id),))
    return cursor.fetchone()


def can_access_animal(cursor, account_id, patient_id):
    cursor.execute('''SELECT 1 FROM nextris.tbuser_patient up JOIN nextris.responsible_party rp ON rp.id=up.responsible_party_id
        JOIN nextris.patient_responsibility pr ON pr.responsible_id=rp.id
        WHERE up.guid=%s AND pr.patient_id=%s AND rp.is_active AND COALESCE(up.firstlogin,1)=0 AND lower(up.status::text) IN ('active','activo','true','1')
        AND pr.portal_authorized AND pr.valid_from<=now() AND (pr.valid_to IS NULL OR pr.valid_to>now())''',(str(account_id),str(patient_id)))
    return bool(cursor.fetchone())


def assert_portal_exam(cursor, account_id, exam_id):
    cursor.execute('SELECT idpatient FROM nextris.tbexamination WHERE guid=%s AND COALESCE(hidden_in_portal,0)=0',(str(exam_id),))
    row=cursor.fetchone()
    if not row or not can_access_animal(cursor,account_id,row['idpatient']):
        raise VeterinaryError('Estudio no encontrado',404)
    return row['idpatient']


def portal_share(cursor, account_id, exam_id):
    import secrets
    import hashlib
    patient_id=assert_portal_exam(cursor,account_id,exam_id)
    cursor.execute('''SELECT studyinstanceuid FROM nextris.tbexamination WHERE guid=%s
        AND studyinstanceuid IN (SELECT study_iuid FROM nextris.available_pacs_study)''',(str(exam_id),))
    row=cursor.fetchone()
    if not row:
        raise VeterinaryError('El estudio no tiene imágenes disponibles',404)
    raw=secrets.token_urlsafe(32);code=secrets.token_urlsafe(12)
    cursor.execute('''INSERT INTO nextris.tbviewer_share_link(guid,token_hash,short_code,study_iuid,created_by_user_id,
        expires_at,share_type,portal_account_id,patient_id) VALUES(%s,%s,%s,%s,%s,now()+interval '15 minutes','image_share',%s,%s)''',
        (str(uuid.uuid4()),hashlib.sha256(raw.encode()).hexdigest(),code,row['studyinstanceuid'],str(account_id),str(account_id),patient_id))
    from urllib.parse import urlencode
    return {'viewer_url':os.getenv('DICOM_VIEWER_URL','').rstrip('/')+'/viewer?'+urlencode({'StudyInstanceUIDs':row['studyinstanceuid'],'share_token':code})}


def share_access_valid(connection, share_guid):
    """Called on every proxy request, including requests using a previously issued link."""
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute('SELECT portal_account_id,patient_id FROM nextris.tbviewer_share_link WHERE guid=%s',(str(share_guid),))
        row=cursor.fetchone()
        return not row or not row['portal_account_id'] or can_access_animal(cursor,row['portal_account_id'],row['patient_id'])


def protocol_context(cursor, patient_id, protocol_id=None, study_type_id=None):
    context=patient_context(cursor,patient_id)
    if not context:
        return None
    if protocol_id:
        cursor.execute('SELECT * FROM nextris.veterinary_protocol WHERE id=%s AND is_active',(identifier(protocol_id),))
        protocol=cursor.fetchone()
        if not protocol:
            raise VeterinaryError('Protocolo no encontrado',404)
        if protocol['species_id'] and str(protocol['species_id'])!=str(context['species_id']):
            raise VeterinaryError('El protocolo no corresponde a la especie')
        if protocol['study_type_id'] and str(protocol['study_type_id'])!=str(study_type_id):
            raise VeterinaryError('El protocolo no corresponde al tipo de estudio')
        cursor.execute('SELECT modality_id,bodypart_id FROM nextris.isstudytype WHERE guid=%s',(study_type_id,))
        study=cursor.fetchone()
        for key in ('modality_id','bodypart_id'):
            if protocol[key] and (not study or str(protocol[key])!=str(study[key])):
                raise VeterinaryError('El protocolo no corresponde a la modalidad o región anatómica')
        measured=context['weight_kg']
        if protocol['min_weight_kg'] is not None or protocol['max_weight_kg'] is not None:
            if measured is None:
                raise VeterinaryError('Registre el peso antes de aplicar este protocolo')
            if (protocol['min_weight_kg'] is not None and measured<float(protocol['min_weight_kg'])) or (protocol['max_weight_kg'] is not None and measured>float(protocol['max_weight_kg'])):
                raise VeterinaryError('El peso no es compatible con el protocolo')
        context['protocol']=plain(dict(protocol))
    return context


def _birth_date(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _age_text(born, estimated):
    today = date.today()
    months = (today.year - born.year) * 12 + today.month - born.month - (today.day < born.day)
    if months < 0:
        return None
    years, months = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} {'año' if years == 1 else 'años'}")
    if months:
        parts.append(f"{months} {'mes' if months == 1 else 'meses'}")
    if not parts:
        days = (today - born).days
        parts.append(f"{days} {'día' if days == 1 else 'días'}")
    return ('aprox. ' if estimated else '') + ' y '.join(parts)


def animal_fields(context):
    """Values for the template fields; None marks a datum the animal does not have."""
    context = context or {}
    gender = context.get('gender')
    ending = {'M': 'o', 'F': 'a'}.get(gender, 'o/a')
    reproductive = {'intact': f'Enter{ending}', 'neutered': f'Castrad{ending}'}.get(context.get('reproductive_status'))
    born = _birth_date(context.get('birthdate'))
    estimated = bool(context.get('birthdate_estimated'))
    birth_text = born.strftime('%d/%m/%Y') + (' (estimada)' if estimated else '') if born else None
    weight_kg = context.get('weight_kg')
    weight_text = f"{float(weight_kg):g} kg".replace('.', ',') if weight_kg is not None else None
    responsibles = ', '.join(r['name'] for r in context.get('responsibles') or [] if r.get('name'))
    name = ' '.join(part for part in (context.get('name'), context.get('surname')) if part)
    return {
        'Nombre': name or None,
        'ID animal': context.get('patientid') or None,
        'Especie': context.get('species_name') or None,
        'Raza': context.get('breed_name') or None,
        'Sexo': {'M': 'Macho', 'F': 'Hembra'}.get(gender),
        'Estado reproductivo': reproductive,
        'Fecha de nacimiento': birth_text,
        'Edad': _age_text(born, estimated) if born else None,
        'Peso': weight_text,
        'Responsable': responsibles or None,
    }


def fill_animal_fields(html, fields):
    """Replace {{Campo}} in a template. A missing datum becomes [[ ]]: the editor jumps to it and signing is blocked."""
    if not html or '{{' not in html:
        return html
    by_name = {key.lower(): value for key, value in fields.items()}
    def replace(match):
        key = ' '.join(match.group(1).split()).lower()
        if key not in by_name:
            return match.group(0)
        return escape(by_name[key], quote=False) if by_name[key] else '[[ ]]'
    return _ANIMAL_FIELD_RE.sub(replace, html)


def report_context(connection, exam_id, *, freeze=False):
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute('''SELECT e.idpatient,e.veterinary_context AS order_context,r.veterinary_context AS report_context
            FROM nextris.tbexamination e LEFT JOIN LATERAL (SELECT veterinary_context FROM nextris.tbreport
            WHERE idexamination=e.guid ORDER BY date DESC NULLS LAST,guid DESC LIMIT 1) r ON true WHERE e.guid=%s''',(str(exam_id),))
        row=cursor.fetchone()
        if not row:
            return None
        context=row['report_context'] or row['order_context'] or patient_context(cursor,row['idpatient'])
        if context and freeze and not row['report_context']:
            current=patient_context(cursor,row['idpatient'])
            if current:
                if row['order_context'] and row['order_context'].get('protocol'):
                    current['protocol']=row['order_context']['protocol']
                context=current
            cursor.execute('UPDATE nextris.tbreport SET veterinary_context=%s WHERE idexamination=%s AND veterinary_context IS NULL',(Json(context),str(exam_id)))
        return context
