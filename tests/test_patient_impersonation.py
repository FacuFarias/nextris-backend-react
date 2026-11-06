"""Session switching with real JWTs and an isolated Flask app; no database writes."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from flask import Blueprint, Flask
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token, decode_token


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = load('impersonation_policy', 'apps/permission_policy.py')
utils = types.ModuleType('apps.api.utils')
utils.get_db_config = lambda: {}
with patch.dict(sys.modules, {'apps.permission_policy': policy, 'apps.api.utils': utils}):
    permissions = load('impersonation_permissions', 'apps/api/permissions.py')

blueprint = Blueprint('impersonation_contract', __name__)
api = types.ModuleType('apps.api')
api.api_blueprint = blueprint
apps = types.ModuleType('apps')
apps.db = MagicMock()
models = types.ModuleType('apps.authentication.models')
models.Users = MagicMock()
models.PatientUser = lambda guid, username, name, surname, email, active, first: types.SimpleNamespace(
    id=guid, username=username, name=name, surname=surname, email=email, role_id=None, first_login=first)
audit = types.ModuleType('apps.services.impersonation')
audit.is_token_revoked = MagicMock(return_value=False)
audit.revoke_jwt = MagicMock()
with patch.dict(sys.modules, {'apps': apps, 'apps.api': api, 'apps.api.permissions': permissions,
                             'apps.authentication.models': models, 'apps.services.impersonation': audit}):
    subject = load('patient_impersonation_subject', 'apps/api/auth.py')


class PatientImpersonationTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, root_path=str(ROOT), instance_path=str(ROOT / 'instance'))
        self.app.config.update(TESTING=True, JWT_SECRET_KEY='synthetic-impersonation-contract-secret-key')
        JWTManager(self.app)
        self.app.register_blueprint(blueprint)
        self.client = self.app.test_client()
        self.actor = types.SimpleNamespace(id='operator-id', username='operator', is_active=1)
        subject.Users.reset_mock()
        subject.Users.query.filter_by.return_value.first.return_value = self.actor
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = ('portal-account-id', 'synthetic-patient', 'Paciente', 'Prueba', '', 1)
        self.grants = patch.object(permissions, 'get_user_permission_codes', return_value=['users.impersonate']).start()
        patch.object(subject, '_get_db_config', return_value={}).start()
        patch.object(subject.psycopg2, 'connect', return_value=self.connection).start()
        patch.object(subject, 'get_user_permission_codes', return_value=['patients.view']).start()
        subject.revoke_jwt.reset_mock()
        subject.is_token_revoked.reset_mock(return_value=True, side_effect=True)
        subject.is_token_revoked.return_value = False
        self.addCleanup(patch.stopall)
        self.access, self.refresh = self.tokens()

    def tokens(self, identity='operator-id', user_type='Sysadmin', session='current', **claims):
        with self.app.app_context():
            claims = dict(user_type=user_type, auth_session_id=session, **claims)
            return (create_access_token(identity=identity, additional_claims=claims),
                    create_refresh_token(identity=identity, additional_claims=claims))

    def switch(self, **body):
        return self.client.post('/auth/impersonate', json={
            'target_user_id': 'portal-account-id', 'target_type': 'patient',
            'refresh_token': self.refresh, **body,
        }, headers={'Authorization': f'Bearer {self.access}'})

    def test_patient_identity_permissions_audit_and_original_session_revocation(self):
        response = self.switch()
        self.assertEqual(response.status_code, 200)
        data = response.get_json()['data']
        self.assertEqual(data['user']['id'], 'portal-account-id')
        self.assertEqual(data['user']['user_type'], 'patient')
        self.assertEqual(data['user']['permissions'], [])
        self.assertIsNone(data['user']['role_id'])
        self.assertTrue(data['user']['requires_password_change'])
        self.assertEqual(data['user']['impersonation']['actor_id'], self.actor.id)
        with self.app.app_context():
            for key in ['access_token', 'refresh_token']:
                token = decode_token(data[key])
                self.assertEqual(token['sub'], 'portal-account-id')
                self.assertEqual(token['user_type'], 'patient')
                self.assertEqual(token['impersonator_id'], self.actor.id)
                self.assertEqual(token['impersonation_id'], data['user']['impersonation']['session_id'])
        self.assertEqual(subject.revoke_jwt.call_count, 2)
        queries = self.cursor.execute.call_args_list
        self.assertTrue(any('tb_impersonation_session' in call.args[0]
                            and call.args[1][3] == 'portal-account-id' for call in queries))
        self.connection.commit.assert_called_once()

    def test_missing_or_inactive_patient_does_not_revoke_current_session(self):
        self.cursor.fetchone.return_value = None
        self.assertEqual(self.switch().status_code, 404)
        subject.revoke_jwt.assert_not_called()
        self.connection.commit.assert_not_called()
        self.assertIn("LOWER(up.status::text)", self.cursor.execute.call_args.args[0])

    def test_saved_permission_required(self):
        self.grants.return_value = ['tabs.config.view']
        self.assertEqual(self.switch().status_code, 403)
        subject.revoke_jwt.assert_not_called()

    def test_patient_cannot_switch_even_with_wildcard_grant(self):
        self.grants.return_value = ['*']
        self.access, self.refresh = self.tokens(user_type='patient')
        self.assertEqual(self.switch().status_code, 403)

    def test_nested_impersonation_rejected(self):
        self.access, self.refresh = self.tokens(impersonation_id='existing-session')
        self.assertEqual(self.switch().status_code, 403)

    def test_mismatched_or_revoked_refresh_rejected(self):
        for kwargs in [{'identity': 'someone-else'}, {'session': 'another-session'}]:
            with self.subTest(kwargs=kwargs):
                _, self.refresh = self.tokens(**kwargs)
                self.assertEqual(self.switch().status_code, 401)
        self.access, self.refresh = self.tokens()
        subject.is_token_revoked.return_value = True
        self.assertEqual(self.switch().status_code, 401)
        subject.revoke_jwt.assert_not_called()

    def test_unknown_target_type_rejected(self):
        self.assertEqual(self.switch(target_type='unknown').status_code, 400)

    def test_audit_failure_rolls_back_and_returns_no_tokens(self):
        self.connection.commit.side_effect = RuntimeError('synthetic audit error')
        response = self.switch()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('data', response.get_json())
        self.connection.rollback.assert_called_once()

    def test_staff_switch_remains_compatible_without_target_type(self):
        staff = types.SimpleNamespace(id='staff-id', username='doctor', name='Doctor', surname='',
                                      email='', user_type='Medico', role_id='doctor-role', first_login=0)
        subject.Users.query.filter_by.return_value.first.side_effect = [self.actor, staff]
        response = self.client.post('/auth/impersonate', json={
            'target_user_id': staff.id, 'refresh_token': self.refresh,
        }, headers={'Authorization': f'Bearer {self.access}'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data']['user']['user_type'], 'Medico')
        self.assertEqual(response.get_json()['data']['user']['permissions'], ['patients.view'])


if __name__ == '__main__':
    unittest.main()
