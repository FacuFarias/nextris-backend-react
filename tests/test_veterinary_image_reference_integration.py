"""Live HTTP checks of DICOM-derived suggestions; requires a disposable DB clone.

Run with DB_NAME=cdivet_vetimages_*_test and its API on localhost:5003.
Synthetic metadata exists only in that clone; no PACS API is contacted.
"""
import io
import os
import uuid
from datetime import timedelta

import psycopg2
import pydicom
import requests
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
from pydicom.dataset import Dataset
from pydicom.filebase import DicomBytesIO
from pydicom.filewriter import write_dataset
from pydicom.sequence import Sequence


def run():
    database = os.environ['DB_NAME']
    assert database.startswith('cdivet_vetimages_') and database.endswith('_test')
    connection = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ.get('DB_PORT', '5432'),
        dbname=database, user=os.environ['DB_USER'], password=os.environ['DB_PASS'])
    connection.autocommit = True
    cursor = connection.cursor()
    cursor.execute("SELECT guid FROM nextris.tbuser WHERE username='admin'")
    actor = str(cursor.fetchone()[0])
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY') or os.environ['SECRET_KEY']
    JWTManager(app)

    def auth(identity=actor, user_type='staff'):
        with app.app_context():
            token = create_access_token(identity=identity, expires_delta=timedelta(minutes=15),
                                        additional_claims={'user_type': user_type})
        return {'Authorization': 'Bearer ' + token}

    def snapshot():
        result = {}
        for schema, tables in [('public', ['patient', 'person_name', 'dicomattrs', 'study', 'series', 'instance', 'location']),
                               ('nextris', ['datapatient', 'tbexamination', 'tbreport', 'responsible_party', 'patient_responsibility'])]:
            for table in tables:
                cursor.execute(f"SELECT count(*),md5(COALESCE(string_agg(row_to_json(t)::text,'' ORDER BY row_to_json(t)::text),'')) FROM {schema}.{table} t")
                result[schema + '.' + table] = cursor.fetchone()
        return result

    checks = 0
    credentials = auth()
    cursor.execute('''SELECT s.pk,p.dicomattrs_fk,s.dicomattrs_fk,pa.attrs,da.attrs,s.study_iuid
        FROM nextris.available_pacs_study s JOIN public.patient p ON p.pk=s.patient_fk
        JOIN public.dicomattrs pa ON pa.pk=p.dicomattrs_fk JOIN public.dicomattrs da ON da.pk=s.dicomattrs_fk
        ORDER BY s.pk DESC LIMIT 1''')
    pk, patient_attrs_id, study_attrs_id, patient_raw, study_raw, study_uid = cursor.fetchone()
    endpoint = f'http://127.0.0.1:5003/api/veterinary/image-studies/{pk}/animal-reference'

    def get(expected=200, headers=None, url=endpoint):
        nonlocal checks
        before = snapshot()
        response = requests.get(url, headers=credentials if headers is None else headers, timeout=30)
        assert response.status_code == expected, (response.status_code, response.text[:200])
        assert snapshot() == before, 'Reading suggestions changed PACS or clinical records'
        checks += 1
        return response.json().get('data')

    def save(dataset, key):
        buffer = DicomBytesIO()
        buffer.is_implicit_VR = False
        buffer.is_little_endian = True
        write_dataset(buffer, dataset)
        cursor.execute('UPDATE public.dicomattrs SET attrs=%s WHERE pk=%s', (buffer.getvalue(), key))

    try:
        get(headers={}, expected=401)
        get(headers=auth(user_type='patient'), expected=403)
        get(headers=auth(str(uuid.uuid4())), expected=403)
        get(expected=404, url=endpoint.replace(f'/{pk}/', '/2147483647/'))
        get()
        patient = pydicom.dcmread(io.BytesIO(bytes(patient_raw)), force=True)
        study = pydicom.dcmread(io.BytesIO(bytes(study_raw)), force=True)
        patient.SpecificCharacterSet = 'ISO_IR 192'
        patient.PatientName = 'ÑANDÚ^LUNA^^'
        patient.PatientID = 'DICOM-REFERENCE-QA'
        patient.PatientBirthDate = '20210405'
        patient.PatientSex = 'F'
        species_id, breed_id = str(uuid.uuid4()), str(uuid.uuid4())
        cursor.execute('''INSERT INTO nextris.veterinary_species(id,name,code_value,coding_scheme)
            VALUES(%s,'Especie DICOM QA','QASPECIES','99QA')''', (species_id,))
        cursor.execute('''INSERT INTO nextris.veterinary_breed(id,species_id,name,code_value,coding_scheme)
            VALUES(%s,%s,'Raza DICOM QA','QABREED','99QA')''', (breed_id, species_id))
        patient.PatientSpeciesDescription = 'especie dicom qa'
        patient.PatientBreedDescription = 'RAZA DICOM QA'
        patient.PatientSexNeutered = 'ALTERED'
        patient.ResponsiblePerson = 'RESPONSABLE^DICOM'
        study.PatientWeight = '8.75'
        save(patient, patient_attrs_id)
        save(study, study_attrs_id)
        result = get()
        assert result['initial'] == {'name': 'ÑANDÚ LUNA', 'gender': 'F', 'birthdate': '2021-04-05',
            'reproductive_status': 'neutered', 'weight_kg': '8.75', 'species_id': species_id, 'breed_id': breed_id}
        assert result['dicom']['responsible_name'] == 'RESPONSABLE DICOM'
        assert result['dicom']['patient_id'] == 'DICOM-REFERENCE-QA'
        assert 'patientid' not in result['initial'] and 'responsible_id' not in result['initial']
        patient.PatientSpeciesDescription = 'Unmatched description'
        patient.PatientBreedDescription = 'Unmatched breed'
        for attribute, code in [('PatientSpeciesCodeSequence', 'QASPECIES'), ('PatientBreedCodeSequence', 'QABREED')]:
            coded = Dataset(); coded.CodeValue = code; coded.CodingSchemeDesignator = '99QA'; coded.CodeMeaning = 'QA'
            setattr(patient, attribute, Sequence([coded]))
        save(patient, patient_attrs_id)
        result = get()
        assert result['initial']['species_id'] == species_id and result['initial']['breed_id'] == breed_id
        del patient.PatientSpeciesCodeSequence
        del patient.PatientBreedCodeSequence
        patient.PatientBirthDate = '99999999'
        study.PatientWeight = '0'
        save(patient, patient_attrs_id); save(study, study_attrs_id)
        result = get()
        assert not {'species_id', 'breed_id', 'birthdate', 'weight_kg'}.intersection(result['initial'])
        assert result['dicom']['species'] == 'Unmatched description'
        # Leave a fully populated reference available for the browser integration.
        patient.PatientSpeciesDescription = 'Especie DICOM QA'
        patient.PatientBreedDescription = 'Raza DICOM QA'
        patient.PatientBirthDate = '20210405'
        study.PatientWeight = '8.75'
        save(patient, patient_attrs_id); save(study, study_attrs_id)
        cursor.execute("UPDATE nextris.tbpacs_study_link SET link_status='unlinked' WHERE pacs_study_iuid=%s", (study_uid,))
        cursor.execute('UPDATE nextris.tbmanual_uploads SET islinked=0 WHERE study_instance_uid=%s', (study_uid,))
        cursor.execute('UPDATE nextris.tbexamination SET studyinstanceuid=%s WHERE studyinstanceuid=%s', ('2.25.' + str(uuid.uuid4().int), study_uid))
        print(f'PASS: {checks} live HTTP checks: authentication, permissions, missing studies, unchanged PACS/clinical data, Unicode names, original birth/sex/weight, exact catalogs/codes and unknown/invalid metadata.')
    finally:
        connection.close()


if __name__ == '__main__':
    run()
