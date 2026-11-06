"""Offline tests. No app startup, database, sockets, PACS or clinical data.

Run: venv/bin/python tests/test_image_deletions.py
"""
import ast
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
import uuid

from flask import Blueprint, Flask, jsonify
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, get_jwt
from functools import wraps
import psycopg2
import requests

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


service = load('deletion_subject', 'apps/services/image_deletions.py')


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.cur = MagicMock()
        self.conn = MagicMock()
        self.conn.cursor.return_value.__enter__.return_value = self.cur

        @contextmanager
        def fake_db():
            yield self.conn
        self.db_patch = patch.object(service, 'database', fake_db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.op = dict(id=str(uuid.uuid4()), study_pk=1, study_iuid='1.2.3', created_by='user',
                       status='preview', selection={'level': 'study'}, snapshot_hash='',
                       expires_at=datetime.now(timezone.utc) + timedelta(minutes=10))
        self.target = dict(series_iuid='1.2.3.4', sop_iuid='1.2.3.4.5', attempts=0)
        self.pacs = MagicMock()
        self.pacs.reasons.return_value = [{'codeValue': '113001'}]
        self.body = dict(rejection_code='113001', justification='Duplicación comprobada')
        self.cur.fetchone.return_value = self.op

    def test_foreign_instance_and_series_are_rejected(self):
        self.cur.fetchall.return_value = [{'series_iuid': 's1', 'sop_iuid': 'i1'}]
        for selection in ({'level': 'instances', 'instances': [{'series_uid': 's2', 'sop_uid': 'i1'}]},
                          {'level': 'series', 'series_uids': ['s2']}):
            with self.assertRaises(service.DeletionError) as caught:
                service.manifest(self.cur, 1, selection)
            self.assertEqual(caught.exception.status, 409)

    def test_selection_deduplicates_and_preserves_exact_uids(self):
        selected = service.normalize_selection({'level': 'instances', 'instances': [
            {'series_uid': 's', 'sop_uid': 'i'}, {'series_uid': 's', 'sop_uid': 'i'}]})
        self.assertEqual(selected['instances'], [{'series_uid': 's', 'sop_uid': 'i'}])
        self.cur.fetchall.return_value = [{'series_iuid': 's', 'sop_iuid': 'i'}, {'series_iuid': 's', 'sop_iuid': 'new'}]
        self.assertEqual(service.manifest(self.cur, 1, selected), [('s', 'i')])

    def test_expired_preview_cannot_execute(self):
        self.op['deletion_mode'] = 'permanent'
        self.body['permanent'] = True
        self.op['expires_at'] = datetime.now(timezone.utc) - timedelta(seconds=1)
        with self.assertRaises(service.DeletionError) as caught:
            service.execute(self.op['id'], self.body, 'user', pacs=self.pacs)
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.cur.execute.call_count, 1)

    def test_changed_content_or_exam_requires_new_preview(self):
        self.op['deletion_mode'] = 'permanent'
        self.body['permanent'] = True
        self.op['snapshot_hash'] = service.fingerprint([('s','i')], [])
        for targets, exams in ([('s','i'), ('s','new')], []), ([('s','i')], [{'guid': 'new-exam'}]):
            with patch.object(service, 'manifest', return_value=targets), patch.object(service, 'affected_examinations', return_value=exams):
                with self.assertRaises(service.DeletionError) as caught:
                    service.execute(self.op['id'], self.body, 'user', pacs=self.pacs)
                self.assertEqual(caught.exception.status, 409)

    def test_double_confirmation_is_idempotent(self):
        self.op['status'] = 'queued'
        service.execute(self.op['id'], self.body, 'user', pacs=self.pacs)
        self.assertEqual(self.cur.execute.call_count, 1)  # No new targets or execution.

    def test_operation_is_owned_by_creator_or_sysadmin(self):
        with self.assertRaises(service.DeletionError):
            service.load_operation(self.cur, self.op['id'], 'someone-else')
        self.assertEqual(service.load_operation(self.cur, self.op['id'], 'admin', True)['id'], self.op['id'])

    def test_retention_and_restore_are_not_permitted(self):
        for code in ('113039', 'REVOKE_REJECTION', 'invented'):
            with self.assertRaises(service.DeletionError):
                service.execute(self.op['id'], {**self.body, 'rejection_code': code}, 'user', pacs=self.pacs)
        self.pacs.reasons.assert_not_called()

    def test_timeout_after_success_is_confirmed_without_duplicate_rejection(self):
        self.op['rejection_code'] = '113001'
        self.pacs.reject.side_effect = requests.Timeout()
        with patch.object(service, 'target_state', side_effect=[(False, True), (True, True)]):
            state = service.process_target(self.op, self.target, self.pacs)
        self.assertEqual(state, 'completed')
        self.pacs.reject.assert_called_once_with('1.2.3', '1.2.3.4', '1.2.3.4.5', '113001')

    def test_purge_or_already_rejected_is_idempotent_on_restart(self):
        for remote in ((True, True), (False, False)):
            with patch.object(service, 'target_state', return_value=remote):
                self.assertEqual(service.process_target(self.op, self.target, self.pacs), 'completed')
        self.pacs.reject.assert_not_called()

    def test_failed_rejection_has_bounded_retry_and_partial_results(self):
        self.op['rejection_code'] = '113001'
        self.pacs.reject.side_effect = requests.Timeout()
        with patch.object(service, 'target_state', return_value=(False, True)):
            self.assertEqual(service.process_target(self.op, self.target, self.pacs), 'pending')
            self.assertEqual(service.process_target(self.op, {**self.target, 'attempts': 2}, self.pacs), 'failed')

    def test_database_failure_after_pacs_commit_is_recoverable(self):
        self.op['rejection_code'] = '113001'
        self.cur.execute.side_effect = psycopg2.OperationalError('DB unavailable')
        with patch.object(service, 'target_state', side_effect=[(False, True), (True, True)]):
            with self.assertRaises(psycopg2.OperationalError):
                service.process_target(self.op, self.target, self.pacs)
        self.cur.execute.side_effect = None
        with patch.object(service, 'target_state', return_value=(True, True)):
            self.assertEqual(service.process_target(self.op, self.target, self.pacs), 'completed')
        self.assertEqual(self.pacs.reject.call_count, 1)

    def test_database_context_rolls_back_and_closes(self):
        self.db_patch.stop()
        with patch.object(service.psycopg2, 'connect', return_value=self.conn):
            with self.assertRaises(RuntimeError):
                with service.database():
                    raise RuntimeError('failure')
        self.conn.rollback.assert_called_once()
        self.conn.close.assert_called_once()
        self.conn.commit.assert_not_called()

    def test_permanent_delete_requires_explicit_confirmation(self):
        self.op['deletion_mode'] = 'permanent'
        with self.assertRaises(service.DeletionError) as caught:
            service.execute(self.op['id'], self.body, 'user', pacs=self.pacs)
        self.assertEqual(caught.exception.status, 409)

    def test_old_preview_cannot_silently_become_a_permanent_delete(self):
        for status in ('preview', 'failed', 'partial'):
            self.op.update(deletion_mode='logical', status=status)
            with self.assertRaises(service.DeletionError) as caught:
                service.execute(self.op['id'], {**self.body, 'permanent': True}, 'user', pacs=self.pacs)
            self.assertEqual(caught.exception.status, 409)

    def permanent(self):
        return ({**self.op, 'deletion_mode': 'permanent'},
                {**self.target, 'instance_pk': 123, 'storage_location_pks': [456]})

    def test_logical_rejection_is_not_permanent_completion(self):
        op, target = self.permanent()
        with patch.object(service, 'permanent_target_state', return_value=(True, True, True)):
            self.assertEqual(service.process_target(op, target, self.pacs), 'pending')
        self.pacs.purge_permanent.assert_called_once()
        self.pacs.reject.assert_not_called()

    def test_successful_http_without_index_removal_has_bounded_retries(self):
        op, target = self.permanent()
        with patch.object(service, 'permanent_target_state', return_value=(True, True, True)):
            self.assertEqual(service.process_target(op, {**target, 'attempts': 2}, self.pacs), 'failed')

    def test_waits_for_physical_storage_cleanup_without_consuming_retries(self):
        op, target = self.permanent()
        with patch.object(service, 'permanent_target_state', return_value=(False, False, True)):
            self.assertEqual(service.process_target(op, {**target, 'attempts': 2}, self.pacs), 'pending')
        self.pacs.mark_permanent.assert_not_called()
        self.pacs.purge_permanent.assert_not_called()
        self.assertEqual(self.cur.execute.call_args_list[0].args[1][1], 2)

    def test_permanent_timeout_after_commit_is_successful(self):
        op, target = self.permanent()
        self.pacs.purge_permanent.side_effect = requests.Timeout()
        with patch.object(service, 'permanent_target_state', side_effect=[
                (True, False, True), (True, True, True), (False, False, False)]):
            self.assertEqual(service.process_target(op, target, self.pacs), 'completed')
        self.pacs.mark_permanent.assert_called_once_with('1.2.3', '1.2.3.4', '1.2.3.4.5')

    def test_finished_original_never_deletes_a_reupload_with_same_uids(self):
        op, target = self.permanent()
        with patch.object(service, 'permanent_target_state', return_value=(False, False, False)):
            self.assertEqual(service.process_target(op, target, self.pacs), 'completed')
        self.pacs.mark_permanent.assert_not_called()
        self.pacs.purge_permanent.assert_not_called()

    def test_permanent_request_failure_has_bounded_retries(self):
        op, target = self.permanent()
        self.pacs.mark_permanent.side_effect = requests.Timeout()
        with patch.object(service, 'permanent_target_state', return_value=(True, False, True)):
            self.assertEqual(service.process_target(op, target, self.pacs), 'pending')
            self.assertEqual(service.process_target(op, {**target, 'attempts': 2}, self.pacs), 'failed')

    def test_missing_original_identity_fails_without_deleting_anything(self):
        op, target = self.permanent()
        target['instance_pk'] = None
        self.assertEqual(service.process_target(op, target, self.pacs), 'failed')
        self.pacs.mark_permanent.assert_not_called()

    def test_new_arrival_after_confirmation_prevents_whole_study_deletion(self):
        op, _ = self.permanent()
        op['pacs_instance_pks'] = [123]
        self.cur.fetchone.return_value = (True,)
        self.cur.fetchall.return_value = [(123,), (999,)]
        self.assertFalse(service.process_permanent_study(op, self.pacs))
        self.pacs.delete_study.assert_not_called()

    def test_whole_study_timeout_after_commit_does_not_repeat_deletion(self):
        op, _ = self.permanent()
        op['pacs_instance_pks'] = [123]
        self.cur.fetchone.side_effect = [(True,), (False,)]
        self.cur.fetchall.return_value = [(123,)]
        self.pacs.delete_study.side_effect = requests.Timeout()
        self.assertTrue(service.process_permanent_study(op, self.pacs))
        self.pacs.delete_study.assert_called_once_with('1.2.3')

    def test_whole_study_reupload_is_never_deleted_by_an_old_operation(self):
        op, _ = self.permanent()
        self.cur.fetchone.return_value = (False,)
        self.assertTrue(service.process_permanent_study(op, self.pacs))
        self.pacs.delete_study.assert_not_called()

    def test_purge_uses_only_the_private_code_and_also_removes_notes(self):
        client = service.PacsClient()
        with patch.object(client, 'request') as request:
            client.purge_permanent()
        request.assert_called_once_with('DELETE', client.root + '/reject/NEXTDEL^99NEXTRIS',
                                        params={'keepRejectionNote': 'false'})


class ManagementPermissionTests(unittest.TestCase):
    def setUp(self):
        self.allowed = False
        api_stub = types.ModuleType('apps.api')
        api_stub.api_blueprint = Blueprint('api', __name__, url_prefix='/api')
        permission_stub = types.ModuleType('apps.api.permissions')
        permission_stub.__dict__.update(wraps=wraps, get_jwt_identity=get_jwt_identity, jsonify=jsonify,
                                       get_jwt=get_jwt, normalize_permission_code=lambda code: code,
                                       get_user_permission_codes=lambda *args: ['images.delete'] if self.allowed else [],
                                       user_has_permission_code=lambda *args, **kwargs: self.allowed)
        tree = ast.parse((ROOT / 'apps/api/permissions.py').read_text())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in {'require_any_permission', 'require_permission'}]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'permissions.py', 'exec'), permission_stub.__dict__)
        services_stub = types.ModuleType('apps.services')
        services_stub.image_deletions = service
        with patch.dict(sys.modules, {'apps.api': api_stub, 'apps.api.permissions': permission_stub, 'apps.services': services_stub}):
            load('management_routes_subject', 'apps/api/image_deletions.py')
        app = Flask(__name__, instance_path=str(ROOT / 'instance'))
        app.config['JWT_SECRET_KEY'] = 'offline-test-secret-with-at-least-32-bytes'
        JWTManager(app)
        app.register_blueprint(api_stub.api_blueprint)
        self.client = app.test_client()
        with app.app_context():
            self.headers = {'Authorization': 'Bearer ' + create_access_token(identity='test-user')}
        self.urls = [
            ('GET', '/dicom/studies/1/series'), ('GET', '/dicom/studies/1/series/1.2/instances'),
            ('GET', '/dicom/studies/1/series/1.2/instances/1.2.3/thumbnail'),
            ('GET', '/dicom/rejection-reasons'), ('POST', '/dicom/image-deletions/preview'),
            ('POST', '/dicom/image-deletions/' + str(uuid.uuid4()) + '/execute'),
            ('GET', '/dicom/image-deletions/' + str(uuid.uuid4()))]

    def test_every_management_endpoint_requires_authentication(self):
        for method, path in self.urls:
            with self.subTest(path=path):
                self.assertEqual(self.client.open('/api' + path, method=method, json={}).status_code, 401)

    def test_every_management_endpoint_requires_special_permission(self):
        with patch.object(service, 'database', side_effect=AssertionError('must not reach database')):
            for method, path in self.urls:
                with self.subTest(path=path):
                    self.assertEqual(self.client.open('/api' + path, method=method, json={}, headers=self.headers).status_code, 403)


if __name__ == '__main__':
    unittest.main()
