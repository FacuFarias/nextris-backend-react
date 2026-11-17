"""Read editable animal-registration suggestions from the PACS DICOM attributes."""
import io
import re
from datetime import date, datetime

import pydicom
from psycopg2.extras import RealDictCursor

from apps.services import veterinary as vet


def _text(value):
    return str(value or '').replace('\x00', '').strip()


def _name(value):
    representation = next((part for part in _text(value).split('=') if part.strip()), '')
    return ' '.join(representation.replace('^', ' ').split())


def _catalog_match(rows, description, code, scheme):
    if code and scheme:
        matches = [row for row in rows if row['code_value'] == code and row['coding_scheme'] == scheme]
        if len(matches) == 1:
            return matches[0]
    normalized = ' '.join(description.split()).casefold()
    matches = [row for row in rows if normalized and ' '.join(row['name'].split()).casefold() == normalized]
    return matches[0] if len(matches) == 1 else None


def animal_reference(study_pk):
    with vet.database() as connection:
        connection.set_session(readonly=True)
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            return reference_with_cursor(cursor, study_pk)


def reference_with_cursor(cursor, study_pk):
    cursor.execute('''SELECT pn.alphabetic_name AS patient_name, pa.attrs AS patient_attrs,
        da.attrs AS study_attrs, sample.series_attrs, sample.instance_attrs
        FROM nextris.available_pacs_study s
        JOIN public.patient p ON p.pk=s.patient_fk
        LEFT JOIN public.person_name pn ON pn.pk=p.pat_name_fk
        LEFT JOIN public.dicomattrs pa ON pa.pk=p.dicomattrs_fk
        LEFT JOIN public.dicomattrs da ON da.pk=s.dicomattrs_fk
        LEFT JOIN LATERAL (
            SELECT sa.attrs AS series_attrs, ia.attrs AS instance_attrs
            FROM nextris.available_pacs_series sr
            JOIN nextris.available_pacs_instance i ON i.series_fk=sr.pk
            LEFT JOIN public.dicomattrs sa ON sa.pk=sr.dicomattrs_fk
            LEFT JOIN public.dicomattrs ia ON ia.pk=i.dicomattrs_fk
            WHERE sr.study_fk=s.pk ORDER BY sr.pk,i.pk LIMIT 1
        ) sample ON true WHERE s.pk=%s''', (study_pk,))
    row = cursor.fetchone()
    if not row:
        raise vet.VeterinaryError('Estudio no encontrado o sin imágenes disponibles', 404)
    datasets = []
    for key in ('patient_attrs', 'study_attrs', 'series_attrs', 'instance_attrs'):
        if row[key]:
            try:
                datasets.append(pydicom.dcmread(io.BytesIO(bytes(row[key])), force=True, stop_before_pixels=True))
            except Exception:
                raise vet.VeterinaryError('No se pudieron leer los datos de referencia del DICOM', 422)
    # DCM4CHEE splits attributes by level; the character set may live at study level.
    charset = next((ds.SpecificCharacterSet for ds in datasets if 'SpecificCharacterSet' in ds), None)
    if charset:
        for ds in datasets:
            if 'SpecificCharacterSet' not in ds:
                ds.SpecificCharacterSet = charset

    def value(keyword):
        return next((_text(ds.get(keyword)) for ds in datasets if _text(ds.get(keyword))), '')

    def coded(keyword):
        sequence = next((ds.get(keyword) for ds in datasets if ds.get(keyword)), [])
        item = sequence[0] if sequence else None
        return (_text(item.get('CodeValue')), _text(item.get('CodingSchemeDesignator')),
                _text(item.get('CodeMeaning'))) if item is not None else ('', '', '')

    name = _name(value('PatientName') or row['patient_name'])
    if name.casefold() in ('unknown', 'n/a', 'none', 'null'):
        name = ''
    initial = {'name': name, 'gender': 'O', 'reproductive_status': 'unknown'}
    sex = value('PatientSex').upper()
    if sex in ('M', 'F', 'O'):
        initial['gender'] = sex
    birthdate = value('PatientBirthDate')
    if re.fullmatch(r'\d{8}', birthdate):
        try:
            parsed = datetime.strptime(birthdate, '%Y%m%d').date()
            if parsed <= date.today():
                initial['birthdate'] = parsed.isoformat()
        except ValueError:
            pass
    reproductive = value('PatientSexNeutered').upper()
    initial['reproductive_status'] = {'ALTERED': 'neutered', 'UNALTERED': 'intact'}.get(reproductive, 'unknown')
    weight = value('PatientWeight')
    if weight:
        try:
            initial['weight_kg'] = str(vet.weight(weight))
        except vet.VeterinaryError:
            pass
    species_code, species_scheme, species_meaning = coded('PatientSpeciesCodeSequence')
    breed_code, breed_scheme, breed_meaning = coded('PatientBreedCodeSequence')
    species_description = value('PatientSpeciesDescription') or species_meaning
    breed_description = value('PatientBreedDescription') or breed_meaning
    cursor.execute('SELECT id,name,code_value,coding_scheme FROM nextris.veterinary_species WHERE is_active')
    species = _catalog_match(cursor.fetchall(), species_description, species_code, species_scheme)
    if species:
        initial['species_id'] = str(species['id'])
        cursor.execute('''SELECT id,name,code_value,coding_scheme FROM nextris.veterinary_breed
            WHERE is_active AND species_id=%s''', (species['id'],))
        breed = _catalog_match(cursor.fetchall(), breed_description, breed_code, breed_scheme)
        if breed:
            initial['breed_id'] = str(breed['id'])
    return {'initial': initial, 'dicom': {
        'patient_name': name, 'patient_name_raw': value('PatientName'),
        'patient_id': value('PatientID'), 'birthdate': birthdate,
        'issuer': value('IssuerOfPatientID'), 'study_description': value('StudyDescription'),
        'study_date': value('StudyDate'), 'study_time': value('StudyTime'), 'modality': value('Modality'),
        'accession_number': value('AccessionNumber'),
        'gender': sex, 'species': species_description, 'breed': breed_description,
        'weight_kg': weight, 'reproductive_status': reproductive,
        'responsible_name': _name(value('ResponsiblePerson')),
        'responsible_organization': value('ResponsibleOrganization'),
    }}
