"""Opt-in real PACS validation using newly generated synthetic DICOM only.

venv/bin/python tests/test_image_deletions_integration.py --synthetic

Uses the real API blueprint in an isolated Flask test client, with its own JWT
secret. It does not log in as a real person or issue production credentials.
All created records are visibly synthetic and retained as rejected audit data.
"""
import argparse
from datetime import datetime
from io import BytesIO
from pathlib import Path
import secrets
import sys
import time
import uuid

from dotenv import load_dotenv
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    load_dotenv(ROOT / '.env')
    from apps.services.image_deletions import PacsClient, database, reconcile
    from apps.api import api_blueprint

    app = Flask('synthetic_image_validation', root_path=str(ROOT), instance_path=str(ROOT / 'instance'))
    app.config.update(JWT_SECRET_KEY=secrets.token_hex(32), SECRET_KEY=secrets.token_hex(32), TESTING=True)
    JWTManager(app)
    app.register_blueprint(api_blueprint)
    client = app.test_client()
    with database() as conn, conn.cursor() as cur:
        cur.execute("""SELECT u.guid FROM nextris.tbuser u JOIN nextris.isrole r ON r.guid=u.idrole
                       WHERE lower(r.description)='sysadmin' LIMIT 1""")
        user_id = cur.fetchone()[0]
    with app.app_context():
        headers = {'Authorization': 'Bearer ' + create_access_token(identity=str(user_id))}

    marker = 'NRDELTEST' + uuid.uuid4().hex[:6].upper()
    study_uid, series_a, series_b = generate_uid(), generate_uid(), generate_uid()
    # Patient auto-creation can be disabled independently of study reconciliation.
    with database() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO nextris.datapatient (guid,patientid,name,surname)
                       VALUES (%s,%s,'SYNTHETIC DELETE TEST','NEXTRIS')""", (str(uuid.uuid4()), marker))
    pacs = PacsClient()
    objects = []

    def upload(series, number, frames=1):
        meta = FileMetaDataset()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        meta.MediaStorageSOPClassUID = ('1.2.840.10008.5.1.4.1.1.7.2' if frames > 1 else '1.2.840.10008.5.1.4.1.1.7')
        meta.MediaStorageSOPInstanceUID = generate_uid()
        ds = FileDataset(None, {}, file_meta=meta, preamble=b'\0' * 128)
        ds.is_little_endian, ds.is_implicit_VR = True, False
        ds.SOPClassUID, ds.SOPInstanceUID = meta.MediaStorageSOPClassUID, meta.MediaStorageSOPInstanceUID
        ds.PatientID, ds.PatientName, ds.PatientSex = marker, 'NEXTRIS^SYNTHETIC^DELETE TEST', 'O'
        ds.PatientBirthDate = '20000101'
        ds.StudyInstanceUID, ds.SeriesInstanceUID = study_uid, series
        ds.StudyDate, ds.StudyTime = datetime.now().strftime('%Y%m%d'), datetime.now().strftime('%H%M%S')
        ds.AccessionNumber, ds.StudyDescription = marker, 'SYNTHETIC IMAGE DELETION VALIDATION'
        ds.Modality, ds.SeriesNumber, ds.InstanceNumber = 'OT', (1 if series == series_a else 2), number
        ds.SeriesDescription = 'SYNTHETIC VALIDATION SERIES'
        ds.Rows, ds.Columns, ds.SamplesPerPixel = 8, 8, 1
        ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 8, 8, 7, 0
        ds.PhotometricInterpretation = 'MONOCHROME2'
        if frames > 1:
            ds.NumberOfFrames, ds.FrameTime = frames, '100'
            ds.FrameIncrementPointer = [0x00181063]
        ds.PixelData = bytes(range(64)) * frames
        buffer = BytesIO()
        pydicom.dcmwrite(buffer, ds, write_like_original=False)
        boundary = 'SyntheticDicomBoundary'
        data = (f'--{boundary}\r\nContent-Type: application/dicom\r\n\r\n'.encode()
                + buffer.getvalue() + f'\r\n--{boundary}--\r\n'.encode())
        response = pacs.request('POST', pacs.base + '/studies', data=data,
                                headers={'Content-Type': f'multipart/related; type="application/dicom"; boundary={boundary}'})
        assert response.status_code in (200, 202), ('Synthetic STOW failed', response.status_code)
        objects.append((series, str(ds.SOPInstanceUID)))
        return str(ds.SOPInstanceUID)

    def api(method, path, json=None, expected=200):
        response = client.open('/api' + path, method=method, headers=headers, json=json)
        assert response.status_code == expected, (path, response.status_code, response.get_json())
        return response.get_json()['data']

    upload(series_a, 1)
    upload(series_a, 2)
    upload(series_b, 1, frames=2)
    print('Synthetic study created:', marker, study_uid, flush=True)

    with database() as conn, conn.cursor() as cur:
        cur.execute('SELECT pk FROM public.study WHERE study_iuid=%s', (study_uid,))
        study_pk = cur.fetchone()[0]
        cur.execute('SELECT guid,idpatient FROM nextris.tbexamination WHERE studyinstanceuid=%s', (study_uid,))
        exam, patient = cur.fetchone()
        cur.execute("""UPDATE nextris.tbexamination SET isreported=1, reportdate=now(), isexecuted=1
                       WHERE guid=%s AND studyinstanceuid=%s""", (exam, study_uid))
        cur.execute("""UPDATE nextris.tbreport SET findings='SYNTHETIC REPORT - DO NOT USE CLINICALLY', wassaved=TRUE
                       WHERE idexamination=%s""", (exam,))
        cur.execute('SELECT row_to_json(r) FROM nextris.tbreport r WHERE idexamination=%s', (exam,))
        report_before = cur.fetchone()[0]
        linked_exam, manual_exam = str(uuid.uuid4()), str(uuid.uuid4())
        for test_exam in (linked_exam, manual_exam):
            cur.execute("""INSERT INTO nextris.tbexamination (guid,idpatient,localacc,studyinstanceuid,isimage)
                           VALUES (%s,%s,%s,%s,1)""", (test_exam, patient, marker + '-' + test_exam[:4], generate_uid()))
        cur.execute("""INSERT INTO nextris.tbpacs_study_link
                       (pacs_study_pk,pacs_study_iuid,order_guid,source) VALUES (%s,%s,%s,'manual')""",
                    (study_pk, study_uid, linked_exam))
        cur.execute("""INSERT INTO nextris.tbmanual_uploads
                       (filename,filepath,study_instance_uid,series_instance_uid,sop_instance_uid,
                        linked_examination_guid,islinked,pacs_status,patient_id,patient_name)
                       VALUES (%s,%s,%s,%s,%s,%s,1,'success',%s,'NEXTRIS SYNTHETIC DELETE TEST')""",
                    (marker+'.dcm', '/synthetic/no-local-file', study_uid, series_b, objects[2][1], manual_exam, marker))
        cur.execute('SELECT guid FROM nextris.tbmanual_uploads WHERE study_instance_uid=%s', (study_uid,))
        manual_guid = str(cur.fetchone()[0])
    reconcile(study_uid)

    def verify_flags(expected):
        with database() as conn, conn.cursor() as cur:
            cur.execute('SELECT guid,isimage FROM nextris.tbexamination WHERE guid=ANY(%s)', ([exam,linked_exam,manual_exam],))
            flags = cur.fetchall()
            assert len(flags) == 3 and all(r[1] == expected for r in flags), flags
            cur.execute('SELECT isreported,isexecuted FROM nextris.tbexamination WHERE guid=%s', (exam,))
            assert cur.fetchone() == (1,1)
            cur.execute('SELECT row_to_json(r) FROM nextris.tbreport r WHERE idexamination=%s', (exam,))
            assert cur.fetchone()[0] == report_before, 'Synthetic signed report changed'

    series = api('GET', f'/dicom/studies/{study_pk}/series')
    assert series['total'] == 2
    instances = api('GET', f'/dicom/studies/{study_pk}/series/{series_b}/instances')
    assert instances['items'][0]['num_frames'] == 2
    thumbnail = client.get(f'/api/dicom/studies/{study_pk}/series/{series_a}/instances/{objects[0][1]}/thumbnail', headers=headers)
    assert thumbnail.status_code == 200, ('thumbnail', thumbnail.status_code)
    print('PASS: series, instance navigation and multiframe thumbnail', flush=True)

    def delete(selection, remaining):
        preview = api('POST', '/dicom/image-deletions/preview', {'study_pk': study_pk, **selection}, 201)
        assert len(preview['affected_examinations']) == 3
        operation = preview['id']
        payload = {'rejection_code': '113001', 'justification': 'SYNTHETIC VALIDATION ' + marker}
        api('POST', f'/dicom/image-deletions/{operation}/execute', payload, 202)
        api('POST', f'/dicom/image-deletions/{operation}/execute', payload, 202)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            result = api('GET', f'/dicom/image-deletions/{operation}')
            if result['status'] in ('completed','partial','failed'):
                assert result['status'] == 'completed', result
                assert result['remaining_instances'] == remaining, result
                verify_flags(1 if remaining else 0)
                print('PASS:', selection['level'], 'remaining', remaining, flush=True)
                return
            time.sleep(1)
        raise AssertionError('Worker did not complete synthetic operation in time')

    delete({'level': 'instances', 'instances': [{'series_uid': series_a, 'sop_uid': objects[0][1]}]}, 2)
    delete({'level': 'series', 'series_uids': [series_a]}, 1)

    # A new arrival invalidates a whole-study preview, but is never added silently.
    old = api('POST', '/dicom/image-deletions/preview', {'study_pk': study_pk, 'level': 'study'}, 201)
    upload(series_b, 2)
    rejected_preview = client.post(f"/api/dicom/image-deletions/{old['id']}/execute", headers=headers,
                                  json={'rejection_code':'113001', 'justification':'SYNTHETIC VALIDATION ' + marker})
    assert rejected_preview.status_code == 409
    print('PASS: changed study requires a new preview', flush=True)

    with app.app_context():
        from apps.api.viewer_share_service import create_for_exam
        image_link = create_for_exam(exam, user_id, share_type='image_share')
        case_link = create_for_exam(exam, user_id, share_type='case_link')
        from apps.api.general import _create_viewer_handoff
        _create_viewer_handoff(user_id, study_uid)

    forbidden = client.post(f"/api/general/share-dicom/{case_link['short_code']}/dcm4chee-arc/aets/DCM4CHEE/rs/studies/{study_uid}/reject/113001^DCM")
    assert forbidden.status_code == 405, 'Public viewer gateway must never authorize IOCM writes'

    delete({'level': 'study'}, 0)
    listing = api('GET', '/dicom/studies-by-location/all?search=' + marker)
    assert listing['total'] == 0
    assert api('GET', f'/studies/{exam}/image-link')['has_images'] == 0
    assert client.post('/api/general/viewer-url-by-iuid', headers=headers, json={'study_iuid':study_uid}).status_code == 404
    case = api('GET', f"/s/{case_link['short_code']}/case")
    assert case['study']['image_count'] == 0 and case['viewer_url'] is None and case['report_available']
    with database() as conn, conn.cursor() as cur:
        cur.execute('SELECT revoked FROM nextris.tbviewer_share_link WHERE guid=%s', (image_link['guid'],))
        assert cur.fetchone()[0]
        cur.execute('SELECT revoked FROM nextris.tbviewer_share_link WHERE guid=%s', (case_link['guid'],))
        assert not cur.fetchone()[0]
        cur.execute('SELECT pacs_status FROM nextris.tbmanual_uploads WHERE guid=%s', (manual_guid,))
        assert cur.fetchone()[0] == 'rejected'
        cur.execute('SELECT count(*) FROM nextris.tb_viewer_handoff WHERE study_iuid=%s AND expires_at>now()', (study_uid,))
        assert cur.fetchone()[0] == 0
    print('PASS: no images, three associations, signed report preserved, manual uploads, share links and handoffs', flush=True)

    restored_series, restored_sop = objects[0]
    # Rejected instances are deliberately invisible through DCM4CHEE's normal AE.
    recovery_base = pacs.base.split('/aets/')[0] + '/aets/IOCM_QUALITY/rs'
    restore_url = pacs.instance_url(study_uid, restored_series, restored_sop).replace(pacs.base, recovery_base, 1)
    response = pacs.request('POST', restore_url + '/reject/REVOKE_REJECTION^99DCM4CHEE')
    response.raise_for_status()
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        with database() as conn, conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM nextris.tbexamination WHERE guid=ANY(%s) AND isimage=1', ([exam,linked_exam,manual_exam],))
            if cur.fetchone()[0] == 3:
                break
        time.sleep(1)
    verify_flags(1)
    print('PASS: external restoration recalculates availability', flush=True)
    delete({'level':'study'}, 0)
    print('PASS: integration finished; synthetic records retained for audit:', marker, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic', action='store_true', help='Create dedicated synthetic study and exercise logical rejection')
    if not parser.parse_args().synthetic:
        parser.error('Explicit --synthetic is required')
    run()
