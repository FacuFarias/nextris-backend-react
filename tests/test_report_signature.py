"""Reglas de firma de informes: matrícula opcional y datos de prueba para admins. Sin base de datos ni servidor."""
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
import psycopg2

from apps.api import api_blueprint
from apps.services.signature_policy import signature_problem

# run.app se conecta a la base al arrancar; aquí solo hace falta la API.
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = 'test-only-signing-key-with-enough-length'
JWTManager(app)
app.register_blueprint(api_blueprint)


class FakeDb:
    """Answers signer role and signing data; the exam is not found, so signing stops right after the checks."""

    def __init__(self, role, medical):
        self.role, self.medical, self.sql, self.last = role, medical, [], ''

    def cursor(self, *_args, **_kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.last = sql
        self.sql.append((sql, params))

    def executemany(self, sql, params):
        self.execute(sql, params)

    def fetchone(self):
        if 'r.description' in self.last:
            return (self.role,)
        if 'tbuser_medical_data' in self.last:
            return self.medical
        return None

    def fetchall(self):
        return [('reports.sign',)] if 'rel_user_permission' in self.last else []

    def commit(self):
        pass

    rollback = close = commit

    @property
    def inserted(self):
        return [params for sql, params in self.sql if 'INSERT INTO nextris.tbuser_medical_data' in sql]


def sign(role, medical, body=None):
    db = FakeDb(role, medical)
    with app.app_context():
        headers = {'Authorization': 'Bearer ' + create_access_token(identity='user-1', additional_claims={'user_type': 'staff'})}
    with mock.patch.object(psycopg2, 'connect', return_value=db):
        response = app.test_client().post('/api/reports/exam-1/sign', headers=headers, json=body or {})
    return response, db


class PolicyTests(unittest.TestCase):
    def test_registration_is_not_required(self):
        self.assertIsNone(signature_problem((True, 'Dra. Pérez')))

    def test_clarification_and_enabled_are_required(self):
        self.assertEqual(signature_problem(None)[0], 'MEDICAL_DATA_MISSING')
        self.assertEqual(signature_problem((False, 'Dra. Pérez'))[0], 'SIGNATURE_NOT_ENABLED')
        self.assertEqual(signature_problem((True, '  '))[0], 'SIGNATURE_DATA_INCOMPLETE')


class SignRouteTests(unittest.TestCase):
    def test_admin_without_data_passes_with_test_signature(self):
        for role in ('Sysadmin', 'Admin', 'Administrador'):
            with self.subTest(role=role):
                response, db = sign(role, None)
                self.assertEqual(response.status_code, 404, response.get_json())
                self.assertEqual(db.inserted, [('user-1', '[PRUEBA] Administrador', 'PRUEBA')])

    def test_doctor_who_is_admin_keeps_own_data(self):
        response, db = sign('Sysadmin', (True, 'Dra. Pérez'))
        self.assertEqual(response.status_code, 404, response.get_json())
        self.assertEqual(db.inserted, [])

    def test_doctor_without_data_is_still_rejected(self):
        response, db = sign('Medico', None)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()['error_code'], 'MEDICAL_DATA_MISSING')
        self.assertEqual(db.inserted, [])

    def test_admin_never_writes_test_data_for_another_professional(self):
        response, db = sign('Sysadmin', None, {'reporter_physician_id': 'other-doctor'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(db.inserted, [])


if __name__ == '__main__':
    unittest.main()
