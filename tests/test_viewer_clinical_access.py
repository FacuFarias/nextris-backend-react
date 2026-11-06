"""Viewer session contract tests with isolated Flask/JWT and mocked DB/PACS."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from flask import Blueprint, Flask
from flask_jwt_extended import JWTManager, create_access_token, decode_token


ROOT = Path(__file__).resolve().parents[1]
blueprint = Blueprint('viewer_contract', __name__)
api_stub = types.ModuleType('apps.api')
api_stub.api_blueprint = blueprint
config_stub = types.ModuleType('apps.home.services')
config_stub.ConfigService = MagicMock()
images_stub = types.ModuleType('apps.services.image_deletions')
images_stub.study_has_images = lambda uid: True
spec = importlib.util.spec_from_file_location('viewer_contract_subject', ROOT / 'apps/api/hanging_protocols.py')
subject = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'apps.api': api_stub, 'apps.home.services': config_stub}):
    spec.loader.exec_module(subject)


class ViewerClinicalAccessTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, root_path=str(ROOT), instance_path=str(ROOT / 'instance'))
        self.app.config.update(TESTING=True, JWT_SECRET_KEY='isolated-viewer-contract-test-key-32-bytes')
        JWTManager(self.app)
        self.app.register_blueprint(blueprint)
        self.client = self.app.test_client()
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.handoff = dict(user_id='user-id', study_iuid='1.2.3', user_type='staff',
                            expires_at=datetime.now(timezone.utc) + timedelta(seconds=60), consumed_at=None)
        patches = [patch.object(subject, '_connection', return_value=self.connection),
                   patch.object(subject, '_request_dicom_token', return_value={'access_token': 'synthetic', 'expires_in': 300})]
        for mocked in patches:
            mocked.start()
            self.addCleanup(mocked.stop)

    def exchange(self):
        self.cursor.fetchone.side_effect = [self.handoff, {'available': True}]
        return self.client.post('/viewer/session/exchange', json={'code': 'x' * 48, 'studyInstanceUID': '1.2.3'})

    def test_staff_and_patient_receive_explicit_clinical_access(self):
        for user_type, expected in [('staff', True), ('sysadmin', True), ('patient', False), ('PATIENT', False), ('', False), (None, False)]:
            with self.subTest(user_type=user_type):
                self.handoff['user_type'] = user_type
                response = self.exchange()
                self.assertEqual(response.status_code, 200)
                data = response.get_json()['data']
                self.assertIs(data['clinicalAccess'], expected)
                with self.app.app_context():
                    self.assertEqual(decode_token(data['viewerAccessToken'])['user_type'], user_type)

    def test_expired_or_mismatched_handoff_is_rejected(self):
        for changes in [{'expires_at': datetime.now(timezone.utc) - timedelta(seconds=1)},
                        {'study_iuid': '9.9'}, {'consumed_at': datetime.now(timezone.utc)}]:
            original = self.handoff.copy()
            self.handoff.update(changes)
            self.assertEqual(self.exchange().status_code, 401)
            self.handoff = original

    def test_refresh_remains_compatible_with_staff_and_patient_sessions(self):
        for user_type in ['staff', 'patient']:
            with self.app.app_context():
                token = create_access_token(identity='user-id', additional_claims={
                    'token_use': 'nextviewer', 'scopes': ['viewer-session'],
                    'study_iuid': '1.2.3', 'user_type': user_type,
                })
            with patch.dict(sys.modules, {'apps.services.image_deletions': images_stub}):
                response = self.client.post('/viewer/session/refresh', json={'studyInstanceUID': '1.2.3'},
                                            headers={'Authorization': f'Bearer {token}'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['data']['dicomAccessToken'], 'synthetic')


if __name__ == '__main__':
    unittest.main()
