"""PR ownership API contract. All PACS writes and database operations are isolated."""
import importlib.util
from io import BytesIO
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from flask import Blueprint, Flask
from flask_jwt_extended import JWTManager, create_access_token
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset

ROOT = Path(__file__).resolve().parents[1]
blueprint = Blueprint('pr_contract', __name__)
api_stub = types.ModuleType('apps.api'); api_stub.api_blueprint = blueprint
permissions = types.ModuleType('apps.api.permissions'); permissions.get_user_permission_codes = MagicMock()
config = types.ModuleType('apps.home.services'); config.ConfigService = MagicMock()
images = types.ModuleType('apps.services.image_deletions'); images.PacsClient = MagicMock()
spec = importlib.util.spec_from_file_location('pr_contract_subject', ROOT / 'apps/api/presentation_states.py')
subject = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'apps.api': api_stub, 'apps.api.permissions': permissions,
                             'apps.home.services': config, 'apps.services.image_deletions': images}):
    spec.loader.exec_module(subject)


def dicom_pr():
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'
    meta.MediaStorageSOPClassUID = subject.GSPS; meta.MediaStorageSOPInstanceUID = '1.2.3.5'
    ds = FileDataset(None, {}, file_meta=meta, preamble=b'\0' * 128)
    ds.is_little_endian = True; ds.is_implicit_VR = False
    ds.SOPClassUID = subject.GSPS; ds.SOPInstanceUID = '1.2.3.5'
    ds.Modality = 'PR'; ds.StudyInstanceUID = '1.2.3'; ds.SeriesInstanceUID = '1.2.3.6'
    ds.ContentCreatorName = 'FORGED^AUTHOR'
    series = pydicom.dataset.Dataset(); series.SeriesInstanceUID = '1.2.3.7'
    image = pydicom.dataset.Dataset(); image.ReferencedSOPInstanceUID = '1.2.3.8'
    series.ReferencedImageSequence = [image]; ds.ReferencedSeriesSequence = [series]
    output = BytesIO(); pydicom.dcmwrite(output, ds, write_like_original=False)
    return output.getvalue()


class PresentationStateTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__, root_path=str(ROOT), instance_path=str(ROOT / 'instance'))
        app.config.update(TESTING=True, JWT_SECRET_KEY='isolated-presentation-state-contract-key-32-bytes')
        JWTManager(app); app.register_blueprint(blueprint)
        self.app, self.client = app, app.test_client()
        self.connection = MagicMock()
        self.cur = self.connection.cursor.return_value.__enter__.return_value
        self.user = dict(guid='alice', username='alice', name='Alice', surname='Radiologist')
        self.target = dict(sop_iuid='1.2.3.5', series_iuid='1.2.3.6', sop_cuid=subject.GSPS, modality='PR')
        self.owned = dict(sop_iuid='1.2.3.5', study_iuid='1.2.3', series_iuid='1.2.3.6', owner_id='alice',
                          author_name='Alice Radiologist', deleted_at=None, saved_at=None)
        self.pacs = MagicMock(); self.pacs.base = 'https://pacs.invalid/rs'
        self.pacs.request.return_value.ok = True
        self.pacs.request.return_value.json.return_value = {'00081199': {'Value': [{'00081155': {'Value': ['1.2.3.5']}}]}}
        self.pacs.reject.return_value.ok = True
        self.grants = ['images.view']
        for p in [patch.object(subject, '_connection', return_value=self.connection),
                  patch.object(subject, 'PacsClient', return_value=self.pacs),
                  patch.object(subject, 'get_user_permission_codes', side_effect=lambda *a, **kw: self.grants)]:
            p.start(); self.addCleanup(p.stop)

    def headers(self, **changes):
        claims = dict(token_use='nextviewer', scopes=['viewer-session'], user_type='staff', study_iuid='1.2.3')
        claims.update(changes)
        with self.app.app_context(): token = create_access_token(identity='alice', additional_claims=claims)
        return {'Authorization': 'Bearer ' + token}

    def delete(self, owner='alice', grants=None):
        if grants is not None: self.grants = grants
        owned = {**self.owned, 'owner_id': owner} if owner is not None else None
        self.cur.fetchone.side_effect = [self.user, self.target, owned]
        return self.client.delete('/viewer/presentation-states/1.2.3/1.2.3.5', headers=self.headers())

    def test_owner_can_delete_only_exact_pr(self):
        self.assertEqual(self.delete().status_code, 200)
        self.pacs.reject.assert_called_once_with('1.2.3', '1.2.3.6', '1.2.3.5', '113001')

    def test_another_user_cannot_delete(self):
        self.assertEqual(self.delete(owner='bob').status_code, 403)
        self.pacs.reject.assert_not_called()

    def test_sysadmin_and_explicit_grant_can_delete_other_and_legacy_prs(self):
        for grants in [['*'], ['images.view', subject.DELETE_PERMISSION]]:
            for owner in ['bob', None]:
                with self.subTest(grants=grants, owner=owner):
                    self.assertEqual(self.delete(owner=owner, grants=grants).status_code, 200)

    def test_unknown_author_is_not_claimed_by_the_current_user(self):
        self.assertEqual(self.delete(owner=None).status_code, 403)
        self.pacs.reject.assert_not_called()

    def test_patient_mismatched_study_and_wrong_scope_are_denied(self):
        for claims in [dict(user_type='patient'), dict(study_iuid='9.9'), dict(token_use='access'), dict(scopes=[])]:
            response = self.client.delete('/viewer/presentation-states/1.2.3/1.2.3.5', headers=self.headers(**claims))
            self.assertEqual(response.status_code, 403)
        self.pacs.reject.assert_not_called()

    def test_inactive_user_and_revoked_permission_are_denied(self):
        self.cur.fetchone.side_effect = [None]
        self.assertEqual(self.client.get('/viewer/presentation-states/1.2.3', headers=self.headers()).status_code, 403)
        self.grants = []
        self.cur.fetchone.side_effect = [self.user]
        self.assertEqual(self.client.get('/viewer/presentation-states/1.2.3', headers=self.headers()).status_code, 403)

    def test_cannot_delete_image_even_with_sysadmin_permission(self):
        self.grants = ['*']
        self.cur.fetchone.side_effect = [self.user, {**self.target, 'modality': 'DX', 'sop_cuid': '1.2.3'}]
        self.assertEqual(self.client.delete('/viewer/presentation-states/1.2.3/1.2.3.5', headers=self.headers()).status_code, 404)
        self.pacs.reject.assert_not_called()

    def test_failed_pacs_delete_does_not_record_success(self):
        self.pacs.reject.return_value.ok = False
        self.assertEqual(self.delete().status_code, 502)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_list_includes_author_and_per_record_delete_permission(self):
        self.cur.fetchone.side_effect = [self.user]
        self.cur.fetchall.return_value = [self.owned, {**self.owned, 'owner_id': 'bob'},
                                        dict(sop_iuid='1.2.3.9', owner_id=None, author_name=None, deleted_at=None)]
        response = self.client.get('/viewer/presentation-states/1.2.3', headers=self.headers())
        rows = response.get_json()['data']
        self.assertEqual([r['canDelete'] for r in rows], [True, False, False])
        self.assertEqual(rows[2]['authorName'], 'Autor no registrado')

    def save(self):
        return self.client.post('/viewer/presentation-states/1.2.3', headers={**self.headers(), 'Content-Type': 'application/dicom'}, data=dicom_pr())

    def test_save_stamps_authenticated_author_and_confirms_exact_sop(self):
        self.cur.fetchone.side_effect = [self.user, {'exists': True}, None, None]
        response = self.save()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['data']['authorName'], 'Alice Radiologist')
        body = self.pacs.request.call_args.kwargs['data']
        raw = body.split(b'\r\n\r\n', 1)[1].rsplit(b'\r\n--', 1)[0]
        ds = pydicom.dcmread(BytesIO(raw))
        self.assertEqual(str(ds.ContentCreatorName), 'Alice Radiologist')
        self.assertNotIn(b'FORGED', raw)

    def test_cannot_claim_existing_pr_or_reference_another_study(self):
        self.cur.fetchone.side_effect = [self.user, {'exists': True}, {'exists': True}, None]
        self.assertEqual(self.save().status_code, 409)
        self.cur.fetchone.side_effect = [self.user, None]
        self.assertEqual(self.save().status_code, 403)
        self.pacs.request.assert_not_called()

    def test_partial_stow_failure_is_not_reported_as_saved(self):
        self.cur.fetchone.side_effect = [self.user, {'exists': True}, None, None]
        self.pacs.request.return_value.json.return_value = {'00081198': {'Value': [{}]}}
        self.assertEqual(self.save().status_code, 502)


if __name__ == '__main__': unittest.main()
