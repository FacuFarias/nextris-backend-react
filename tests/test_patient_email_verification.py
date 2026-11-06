"""Transactional integration tests: synthetic patients, rollback, no real emails.
Run from backend root: venv/bin/python tests/test_patient_email_verification.py
"""
import importlib.util
from pathlib import Path
import os
import unittest
import uuid
from unittest.mock import Mock, patch
import sys

from dotenv import load_dotenv
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('verification', ROOT / 'apps/services/patient_email_verification.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class VerificationTests(unittest.TestCase):
    def setUp(self):
        load_dotenv(ROOT / '.env')
        self.connection = psycopg2.connect(user=os.getenv('DB_USER'), password=os.getenv('DB_PASS'),
            host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'), dbname=os.getenv('DB_NAME'))
        self.addCleanup(self.connection.close)
        self.addCleanup(self.connection.rollback)
        self.cursor = self.connection.cursor()
        self.addCleanup(self.cursor.close)
        self.user = str(uuid.uuid4())
        self.patient = str(uuid.uuid4())
        self.cursor.execute('INSERT INTO nextris.datapatient (guid, patientid, email) VALUES (%s,%s,%s)',
                            (self.patient, self.patient, 'verify@example.invalid'))
        self.cursor.execute('''INSERT INTO nextris.tbuser_patient
            (guid, username, password, datapatient_id) VALUES (%s,%s,%s,%s)''',
            (self.user, self.user, 'test-only', self.patient))
        self.sender = Mock()

    def send(self):
        service.send_verification(self.cursor, self.user, self.sender)
        return self.sender.call_args.args[1]

    def test_password_requires_verification_and_code_is_single_use(self):
        with self.assertRaises(service.VerificationError) as error:
            service.require_verified_email(self.cursor, self.user)
        self.assertEqual(error.exception.status, 403)
        code = self.send()
        self.assertEqual(self.sender.call_args.args[0], 'verify@example.invalid')
        self.assertEqual(len(code), 6)
        self.cursor.execute('SELECT email_code_hash FROM nextris.tbuser_patient WHERE guid = %s', (self.user,))
        self.assertNotEqual(code, self.cursor.fetchone()[0])
        service.confirm_verification(self.cursor, self.user, code)
        service.require_verified_email(self.cursor, self.user)
        with self.assertRaises(service.VerificationError):
            service.confirm_verification(self.cursor, self.user, code)

    def test_incorrect_attempts_are_bounded(self):
        code = self.send()
        wrong = '000001' if code == '000000' else '000000'
        for _ in range(5):
            with self.assertRaises(service.VerificationError):
                service.confirm_verification(self.cursor, self.user, wrong)
        with self.assertRaises(service.VerificationError) as error:
            service.confirm_verification(self.cursor, self.user, code)
        self.assertEqual(error.exception.status, 429)

    def test_expired_code_and_resend_cooldown(self):
        code = self.send()
        with self.assertRaises(service.VerificationError) as error:
            self.send()
        self.assertEqual(error.exception.status, 429)
        self.cursor.execute("UPDATE nextris.tbuser_patient SET email_code_expires=now()-interval '1 second' WHERE guid=%s", (self.user,))
        with self.assertRaises(service.VerificationError):
            service.confirm_verification(self.cursor, self.user, code)

    def test_email_change_invalidates_verified_and_pending_codes(self):
        code = self.send()
        service.confirm_verification(self.cursor, self.user, code)
        self.cursor.execute('UPDATE nextris.datapatient SET email=%s WHERE guid=%s', ('other@example.invalid', self.patient))
        with self.assertRaises(service.VerificationError):
            service.require_verified_email(self.cursor, self.user)
        self.cursor.execute("UPDATE nextris.tbuser_patient SET email_code_sent_at=now()-interval '2 minutes' WHERE guid=%s", (self.user,))
        code = self.send()
        self.cursor.execute('UPDATE nextris.datapatient SET email=%s WHERE guid=%s', ('third@example.invalid', self.patient))
        with self.assertRaises(service.VerificationError):
            service.confirm_verification(self.cursor, self.user, code)
        # Reverting to a previously verified address must not restore validation.
        self.cursor.execute('UPDATE nextris.datapatient SET email=%s WHERE guid=%s', ('verify@example.invalid', self.patient))
        with self.assertRaises(service.VerificationError):
            service.require_verified_email(self.cursor, self.user)

    def test_missing_malformed_email_and_unknown_patient(self):
        for value in ['', 'a', 'a@b', 'x\n@example.com', None]:
            with self.assertRaises(service.VerificationError):
                service.normalize_email(value)
        self.assertEqual(service.normalize_email(' A@Example.com '), 'a@example.com')
        with self.assertRaises(service.VerificationError) as error:
            service.require_verified_email(self.cursor, 'unknown')
        self.assertEqual(error.exception.status, 404)

    def test_delivery_failure_can_rollback_code(self):
        self.cursor.execute('SAVEPOINT delivery')
        self.sender.side_effect = RuntimeError('provider unavailable')
        with self.assertRaises(RuntimeError):
            self.send()
        self.cursor.execute('ROLLBACK TO SAVEPOINT delivery')
        self.cursor.execute('SELECT email_code_hash, email_code_sent_at FROM nextris.tbuser_patient WHERE guid=%s', (self.user,))
        self.assertEqual(self.cursor.fetchone(), (None, None))


class VerificationEndpointTests(VerificationTests):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT))
        from run import app
        from apps.api import patient_portal, auth
        cls.app = app
        cls.portal = patient_portal
        cls.auth = auth

    def setUp(self):
        super().setUp()
        enabled = patch.dict(os.environ, {'PATIENT_EMAIL_VERIFICATION_ENABLED': 'true'})
        enabled.start()
        self.addCleanup(enabled.stop)

    def test_verification_disabled_requires_only_saved_valid_email(self):
        from flask_jwt_extended import create_access_token
        from werkzeug.security import generate_password_hash
        self.cursor.execute('UPDATE nextris.tbuser_patient SET password=%s WHERE guid=%s',
                            (generate_password_hash('current-password'), self.user))
        connection_proxy = Mock()
        connection_proxy.cursor.side_effect = self.connection.cursor
        with self.app.app_context():
            token = create_access_token(identity=self.user, additional_claims={'user_type': 'patient'})
        headers = {'Authorization': f'Bearer {token}'}
        payload = {'current_password': 'current-password', 'new_password': 'new-password', 'confirm_password': 'new-password'}
        client = self.app.test_client()
        with patch.dict(os.environ, {'PATIENT_EMAIL_VERIFICATION_ENABLED': 'false'}), \
             patch.object(self.portal, 'psycopg2', Mock(connect=Mock(return_value=connection_proxy))), \
             patch.object(self.auth, '_send_code_email') as sender:
            for endpoint in ['send', 'confirm']:
                response = client.post('/api/patient-portal/email-verification/' + endpoint, headers=headers, json={'code': '123456'})
                self.assertEqual(response.status_code, 403)
            sender.assert_not_called()
            self.cursor.execute('UPDATE nextris.datapatient SET email=NULL WHERE guid=%s', (self.patient,))
            self.assertEqual(client.post('/api/patient-portal/change-password', headers=headers, json=payload).status_code, 403)
            response = client.put('/api/patient-portal/my-profile', headers=headers, json={'email': 'invalid'})
            self.assertEqual(response.status_code, 400)
            response = client.put('/api/patient-portal/my-profile', headers=headers, json={'email': 'saved@example.invalid'})
            self.assertEqual(response.status_code, 200, response.json)
            self.assertFalse(response.json['data']['email_verification_enabled'])
            self.assertFalse(response.json['data']['email_verified'])
            self.assertTrue(response.json['data']['can_change_password'])
            response = client.post('/api/patient-portal/change-password', headers=headers, json=payload)
            self.assertEqual(response.status_code, 200, response.json)
            sender.assert_not_called()

    def test_resend_provider_payload_and_error(self):
        with patch.dict(os.environ, {'RESEND_API_KEY': 'synthetic-key', 'RESEND_FROM_EMAIL': 'NextRIS <no-reply@example.invalid>'}), \
             patch.object(self.auth.requests, 'post') as send:
            send.return_value.ok = True
            self.auth._send_code_email('patient@example.invalid', '123456')
            args, kwargs = send.call_args
            self.assertEqual(args, ('https://api.resend.com/emails',))
            self.assertEqual(kwargs['headers']['Authorization'], 'Bearer synthetic-key')
            self.assertEqual(kwargs['json']['from'], 'NextRIS <no-reply@example.invalid>')
            self.assertEqual(kwargs['json']['to'], ['patient@example.invalid'])
            self.assertIn('123456', kwargs['json']['text'])
            send.return_value.ok = False
            send.return_value.text = 'Provider rejected request'
            with self.assertRaises(RuntimeError):
                self.auth._send_code_email('patient@example.invalid', '123456')

    def test_http_flow_and_alternative_password_route(self):
        from flask_jwt_extended import create_access_token
        from werkzeug.security import generate_password_hash, check_password_hash
        self.cursor.execute('UPDATE nextris.tbuser_patient SET password=%s WHERE guid=%s',
                            (generate_password_hash('current-password'), self.user))
        connection_proxy = Mock()
        connection_proxy.cursor.side_effect = self.connection.cursor
        with self.app.app_context():
            token = create_access_token(identity=self.user, additional_claims={'user_type': 'patient'})
            staff_token = create_access_token(identity=self.user, additional_claims={'user_type': 'staff'})
        headers = {'Authorization': f'Bearer {token}'}
        client = self.app.test_client()
        payload = {'current_password': 'current-password', 'new_password': 'new-password', 'confirm_password': 'new-password'}
        with patch.object(self.portal, 'psycopg2', Mock(connect=Mock(return_value=connection_proxy))), \
             patch.object(self.auth, 'psycopg2', Mock(connect=Mock(return_value=connection_proxy))), \
             patch.object(self.auth, '_send_code_email', self.sender):
            self.assertEqual(client.post('/api/patient-portal/email-verification/send').status_code, 401)
            self.assertEqual(client.post('/api/patient-portal/email-verification/send', headers={'Authorization': f'Bearer {staff_token}'}).status_code, 403)
            self.assertEqual(client.post('/api/patient-portal/change-password', headers=headers, json=payload).status_code, 403)
            self.assertEqual(client.post('/api/auth/change-password', headers=headers, json={'new_password': 'new-password'}).status_code, 403)
            profile = client.get('/api/patient-portal/my-profile', headers=headers)
            self.assertFalse(profile.json['data']['email_verified'])
            response = client.post('/api/patient-portal/email-verification/send', headers=headers)
            self.assertEqual(response.status_code, 200, response.json)
            code = self.sender.call_args.args[1]
            response = client.post('/api/patient-portal/email-verification/confirm', headers=headers, json={'code': code})
            self.assertEqual(response.status_code, 200, response.json)
            self.assertTrue(client.get('/api/patient-portal/my-profile', headers=headers).json['data']['email_verified'])
            response = client.post('/api/patient-portal/change-password', headers=headers, json=payload)
            self.assertEqual(response.status_code, 200, response.json)
            self.cursor.execute('SELECT password, firstlogin FROM nextris.tbuser_patient WHERE guid=%s', (self.user,))
            password, firstlogin = self.cursor.fetchone()
            self.assertTrue(check_password_hash(password, 'new-password'))
            self.assertEqual(firstlogin, 0)
            response = client.put('/api/patient-portal/my-profile', headers=headers, json={'email': 'new@example.invalid'})
            self.assertEqual(response.status_code, 200, response.json)
            self.assertFalse(response.json['data']['email_verified'])
            self.assertEqual(client.post('/api/patient-portal/change-password', headers=headers, json=payload).status_code, 403)


if __name__ == '__main__':
    unittest.main()
