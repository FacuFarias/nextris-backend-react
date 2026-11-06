"""Real PACS test with exclusively synthetic DICOM: --synthetic to opt in.

Exercises the real management blueprint with isolated JWT and permission stubs;
authorization is tested separately in test_image_deletions.py. No real user is
impersonated. The production worker processes three confirmed operations in
parallel, including physical file purge and re-upload of the exact same SOP UIDs.
"""
import argparse
from datetime import datetime
from io import BytesIO
import importlib.util
from pathlib import Path
import secrets
import sys
import time
import types
from unittest.mock import patch
import uuid

from dotenv import load_dotenv
from flask import Blueprint, Flask
from flask_jwt_extended import JWTManager, create_access_token
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run():
    load_dotenv(ROOT / '.env')
    service = load('permanent_validation_service', 'apps/services/image_deletions.py')
    api_module = types.ModuleType('apps.api')
    api_module.api_blueprint = Blueprint('permanent_validation_api', __name__, url_prefix='/api')
    permissions = types.ModuleType('apps.api.permissions')
    permissions.require_permission = lambda *a, **kw: lambda f: f
    permissions.user_has_permission_code = lambda *a, **kw: True
    services = types.ModuleType('apps.services'); services.image_deletions = service
    with patch.dict(sys.modules, {'apps.api': api_module, 'apps.api.permissions': permissions,
                                 'apps.services': services}):
        load('permanent_validation_routes', 'apps/api/image_deletions.py')
    app = Flask(__name__, root_path=str(ROOT), instance_path=str(ROOT / 'instance'))
    app.config.update(JWT_SECRET_KEY=secrets.token_hex(32), TESTING=True)
    JWTManager(app); app.register_blueprint(api_module.api_blueprint)
    client = app.test_client()
    with app.app_context():
        headers = {'Authorization': 'Bearer ' + create_access_token(identity='synthetic-' + uuid.uuid4().hex)}
    pacs = service.PacsClient()
    assert pacs.permanent_deletion_available(), 'Configure private deletion policy first'
    marker = 'NRDEL' + uuid.uuid4().hex[:8].upper()
    with service.database() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO nextris.datapatient (guid,patientid,name,surname)
            VALUES (%s,%s,'SYNTHETIC PERMANENT DELETION','NEXTRIS')""", (str(uuid.uuid4()), marker))

    def api(method, path, body=None, expected=200):
        response = client.open('/api' + path, method=method, headers=headers, json=body)
        assert response.status_code == expected, (path, response.status_code, response.get_json())
        return response.get_json().get('data')

    def store(content):
        boundary = 'SyntheticPermanentDeletion'
        data = (f'--{boundary}\r\nContent-Type: application/dicom\r\n\r\n'.encode()
                + content + f'\r\n--{boundary}--\r\n'.encode())
        response = pacs.request('POST', pacs.base + '/studies', data=data,
            headers={'Content-Type': f'multipart/related; type="application/dicom"; boundary={boundary}',
                     'Accept': 'application/dicom+json'})
        assert response.status_code in (200, 202), ('STOW', response.status_code, response.text[:400])
        assert '00081198' not in response.json(), ('Failed SOP sequence', response.text[:400])

    def make_image(study, series, number, accession, frames=1):
        meta = FileMetaDataset()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        meta.MediaStorageSOPClassUID = ('1.2.840.10008.5.1.4.1.1.7.2' if frames > 1 else '1.2.840.10008.5.1.4.1.1.7')
        meta.MediaStorageSOPInstanceUID = generate_uid()
        ds = FileDataset(None, {}, file_meta=meta, preamble=b'\0' * 128)
        ds.is_little_endian, ds.is_implicit_VR = True, False
        ds.SOPClassUID, ds.SOPInstanceUID = meta.MediaStorageSOPClassUID, meta.MediaStorageSOPInstanceUID
        ds.PatientID, ds.PatientName, ds.PatientSex = marker, 'NEXTRIS^SYNTHETIC^PERMANENT DELETE', 'O'
        ds.PatientBirthDate = '20000101'
        ds.StudyInstanceUID, ds.SeriesInstanceUID = study, series
        ds.StudyDate, ds.StudyTime = datetime.now().strftime('%Y%m%d'), datetime.now().strftime('%H%M%S')
        ds.AccessionNumber, ds.StudyDescription = accession, 'SYNTHETIC PERMANENT DELETION VALIDATION'
        ds.Modality, ds.SeriesNumber, ds.InstanceNumber = 'OT', number, number
        ds.Rows, ds.Columns, ds.SamplesPerPixel = 8, 8, 1
        ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 8, 8, 7, 0
        ds.PhotometricInterpretation = 'MONOCHROME2'
        if frames > 1:
            ds.NumberOfFrames, ds.FrameTime = frames, '100'; ds.FrameIncrementPointer = [0x00181063]
        ds.PixelData = bytes(range(64)) * frames
        output = BytesIO(); pydicom.dcmwrite(output, ds, write_like_original=False)
        content = output.getvalue(); store(content)
        return {'series': series, 'sop': str(ds.SOPInstanceUID), 'content': content}

    cases = []
    try:
        for idx, level in enumerate(('instances', 'series', 'study')):
            uid, series_a, series_b = generate_uid(), generate_uid(), generate_uid()
            case = {'uid': uid, 'level': level, 'objects': []}; cases.append(case)
            for series, num, frames in ((series_a, 1, 1), (series_a, 2, 1), (series_b, 3, 2)):
                case['objects'].append(make_image(uid, series, num, marker + str(idx), frames))
            with service.database() as conn, conn.cursor() as cur:
                cur.execute('SELECT pk FROM public.study WHERE study_iuid=%s', (uid,)); case['pk'] = cur.fetchone()[0]
                cur.execute('SELECT guid,idpatient FROM nextris.tbexamination WHERE studyinstanceuid=%s', (uid,))
                exam, patient = cur.fetchone(); case['exams'] = [exam]
                cur.execute('UPDATE nextris.tbexamination SET isreported=1,isexecuted=1 WHERE guid=%s', (exam,))
                cur.execute("UPDATE nextris.tbreport SET findings='SYNTHETIC REPORT - NOT FOR CLINICAL USE',wassaved=TRUE WHERE idexamination=%s", (exam,))
                cur.execute('SELECT row_to_json(r) FROM nextris.tbreport r WHERE idexamination=%s', (exam,))
                case['report'] = cur.fetchone()[0]
                if level == 'study':
                    for association in ('linked', 'manual'):
                        extra = str(uuid.uuid4()); case['exams'].append(extra)
                        cur.execute("INSERT INTO nextris.tbexamination (guid,idpatient,studyinstanceuid,localacc,isimage) VALUES (%s,%s,%s,%s,1)",
                                    (extra, patient, generate_uid(), marker + association))
                        if association == 'linked':
                            cur.execute("INSERT INTO nextris.tbpacs_study_link (pacs_study_pk,pacs_study_iuid,order_guid,source) VALUES (%s,%s,%s,'manual')", (case['pk'], uid, extra))
                        else:
                            obj = case['objects'][2]
                            cur.execute("""INSERT INTO nextris.tbmanual_uploads
                                (filename,filepath,study_instance_uid,series_instance_uid,sop_instance_uid,
                                 linked_examination_guid,islinked,pacs_status,patient_id,patient_name)
                                VALUES (%s,'/synthetic/no-file',%s,%s,%s,%s,1,'success',%s,'NEXTRIS SYNTHETIC')""",
                                (marker+'.dcm', uid, obj['series'], obj['sop'], extra, marker))
            selection = {'level': level}
            if level == 'instances': selection['instances'] = [{'series_uid': series_a, 'sop_uid': case['objects'][0]['sop']}]
            if level == 'series': selection['series_uids'] = [series_a]
            case['deleted'] = case['objects'][:{'instances': 1, 'series': 2, 'study': 3}[level]]
            case['remaining'] = 3 - len(case['deleted'])
            preview = api('POST', '/dicom/image-deletions/preview', {'study_pk': case['pk'], **selection}, 201)
            assert preview['deletion_mode'] == 'permanent'
            case['operation'] = preview['id']
            # A pre-existing client cannot silently approve stronger semantics.
            payload = {'rejection_code': '113038', 'justification': 'SYNTHETIC VALIDATION ' + marker}
            api('POST', f"/dicom/image-deletions/{preview['id']}/execute", payload, 409)
            payload['permanent'] = True
            api('POST', f"/dicom/image-deletions/{preview['id']}/execute", payload, 202)
            api('POST', f"/dicom/image-deletions/{preview['id']}/execute", payload, 202)
            print('CONFIRMED:', level, len(case['deleted']), 'synthetic objects', flush=True)

        deadline = time.monotonic() + 660
        while time.monotonic() < deadline:
            statuses = [api('GET', f"/dicom/image-deletions/{case['operation']}") for case in cases]
            assert not any(s['status'] in ('partial', 'failed') for s in statuses), statuses
            print('PURGE:', [(c['level'], s['status'], s['progress']) for c, s in zip(cases, statuses)], flush=True)
            if all(s['status'] == 'completed' for s in statuses): break
            time.sleep(15)
        else: raise AssertionError('Physical PACS purge did not finish within 11 minutes')

        for case in cases:
            with service.database() as conn, conn.cursor() as cur:
                cur.execute('SELECT guid,isimage FROM nextris.tbexamination WHERE guid=ANY(%s)', (case['exams'],))
                flags = cur.fetchall(); assert len(flags) == len(case['exams']) and all(r[1] == int(bool(case['remaining'])) for r in flags), flags
                cur.execute('SELECT row_to_json(r) FROM nextris.tbreport r WHERE idexamination=%s', (case['exams'][0],))
                assert cur.fetchone()[0] == case['report'], 'Saved report changed'
                cur.execute('SELECT isreported,isexecuted FROM nextris.tbexamination WHERE guid=%s', (case['exams'][0],))
                assert cur.fetchone() == (1, 1), 'Clinical flags changed'
                cur.execute('SELECT count(*) FROM public.rejected_instance WHERE study_iuid=%s', (case['uid'],))
                assert cur.fetchone()[0] == 0, 'Rejection tombstone remains'
                cur.execute('SELECT storage_location_pks FROM nextris.tbimage_deletion_target WHERE operation_id=%s', (case['operation'],))
                for (locations,) in cur.fetchall():
                    cur.execute('SELECT count(*) FROM public.location WHERE pk=ANY(%s)', (locations,))
                    assert cur.fetchone()[0] == 0, 'Original storage locations remain'
                if case['level'] == 'study':
                    cur.execute('SELECT count(*) FROM public.study WHERE study_iuid=%s', (case['uid'],))
                    assert cur.fetchone()[0] == 0, 'Whole study still indexed'
            for obj in case['deleted']: store(obj['content'])
            service.reconcile(case['uid'])
            with service.database() as conn, conn.cursor() as cur:
                cur.execute('SELECT nextris.available_image_count_for_exam(%s)', (case['exams'][0],))
                assert cur.fetchone()[0] == 3, 'Exact UID re-upload was not accepted'
                # Re-creating a PACS study invokes the existing accession-based
                # trigger, which may replace a manual link to a different order.
                # Availability must follow the resulting associations.
                cur.execute('SELECT isimage,nextris.available_image_count_for_exam(guid) '
                            'FROM nextris.tbexamination WHERE guid=ANY(%s)', (case['exams'],))
                assert all(flag == int(count > 0) for flag, count in cur.fetchall()), 'Re-upload availability is stale'
                cur.execute('SELECT count(*) FROM nextris.tbexamination WHERE studyinstanceuid=%s', (case['uid'],))
                assert cur.fetchone()[0] == 1, 'Re-upload duplicated the original NextRIS order'
            print('PASS:', case['level'], 'physical purge, orders/reports preserved, exact SOP UID re-upload', flush=True)
    finally:
        # Scope cleanup only to the newly generated studies; retain NextRIS test
        # audit records. dcm4chee's storage scheduler removes their physical files.
        for case in cases:
            response = pacs.delete_study(case['uid'])
            assert response.status_code in (204, 404), ('Synthetic cleanup failed', response.status_code)
            service.reconcile(case['uid'])
        print('SYNTHETIC CLEANUP: PACS studies removed; storage purge scheduled.', marker, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic', action='store_true')
    if not parser.parse_args().synthetic: parser.error('Explicit --synthetic is required')
    run()
