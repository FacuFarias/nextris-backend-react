"""Key image API contract and PDF placement. Database and PACS are isolated."""
import importlib.util
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch
import uuid

from flask import Blueprint, Flask
from flask_jwt_extended import JWTManager, create_access_token
from PIL import Image
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apps.services.report_letterhead_pdf import _report_blocks, render
from apps.services.report_view_service import plain_report_text

LETTERHEAD = ROOT / 'apps/static/assets/img/report/cdivet-letterhead.png'
blueprint = Blueprint('key_image_contract', __name__)
api_stub = types.ModuleType('apps.api'); api_stub.api_blueprint = blueprint
permissions = types.ModuleType('apps.api.permissions')
permissions.get_user_permission_codes = MagicMock()
def require_permission(_code):
    def decorator(func):
        return func
    return decorator
permissions.require_permission = require_permission
presentation = types.ModuleType('apps.api.presentation_states')
class PRError(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status
presentation.PRError = PRError
presentation._uid = lambda value: value
presentation._connection = MagicMock()
presentation._actor = MagicMock(return_value=('alice', 'Alice Vet', ['images.view']))
spec = importlib.util.spec_from_file_location('key_image_contract_subject', ROOT / 'apps/api/key_images.py')
subject = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'apps.api': api_stub, 'apps.api.permissions': permissions, 'apps.api.presentation_states': presentation}):
    spec.loader.exec_module(subject)


def png(size=(40, 30), color=(200, 30, 30)):
    output = BytesIO(); Image.new('RGB', size, color).save(output, 'PNG')
    return output.getvalue()


class ApiTest(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, JWT_SECRET_KEY='isolated-key-image-contract-key-32-bytes-long')
        JWTManager(app); app.register_blueprint(blueprint)
        self.app, self.client = app, app.test_client()
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.connection = MagicMock()
        self.cur = self.connection.cursor.return_value.__enter__.return_value
        self.cur.fetchone.return_value = {'exists': 1}
        presentation._actor.side_effect = None
        subject._actor.return_value = ('alice', 'Alice Vet', ['images.view'])
        subject.get_user_permission_codes.return_value = ['images.view']
        for item in [patch.object(subject, '_connection', return_value=self.connection),
                     patch.object(subject, 'key_image_path', side_effect=lambda image_id: Path(self.folder.name) / f'{image_id}.png')]:
            item.start(); self.addCleanup(item.stop)

    def headers(self, **claims):
        with self.app.app_context():
            return {'Authorization': 'Bearer ' + create_access_token(identity='alice', additional_claims=claims)}

    def post(self, data=None, content_type='image/png', query='?series=1.2.3.4&sop=1.2.3.5'):
        return self.client.post('/viewer/key-images/1.2.3' + query, data=png() if data is None else data,
                                headers={**self.headers(token_use='nextviewer'), 'Content-Type': content_type})

    def files(self):
        return list(Path(self.folder.name).iterdir())

    def test_staff_viewer_session_creates_image_with_authenticated_author(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['data']['author_name'], 'Alice Vet')
        self.assertEqual(len(self.files()), 1)
        self.connection.commit.assert_called_once()

    def test_denied_session_stores_nothing(self):
        subject._actor.side_effect = PRError('denegado', 403)
        self.addCleanup(lambda: setattr(subject._actor, 'side_effect', None))
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.files(), [])

    def test_rejects_non_png_oversized_and_corrupt_uploads(self):
        output = BytesIO(); Image.new('RGB', (10, 10)).save(output, 'JPEG')
        self.assertEqual(self.post(output.getvalue(), 'image/jpeg').status_code, 415)
        self.assertEqual(self.post(output.getvalue()).status_code, 400)
        self.assertEqual(self.post(b'not a png').status_code, 400)
        self.assertEqual(self.post(b'\x89PNG' + b'0' * (5 * 1024 * 1024 + 1)).status_code, 400)
        self.assertEqual(self.files(), [])

    def test_rejects_instance_of_another_study(self):
        self.cur.fetchone.return_value = None
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.files(), [])

    def test_failed_insert_removes_the_file(self):
        self.cur.execute.side_effect = [None, subject.psycopg2.Error('fallo')]
        self.assertEqual(self.post().status_code, 500)
        self.assertEqual(self.files(), [])
        self.connection.commit.assert_not_called()

    def test_viewer_token_cannot_use_ris_routes(self):
        headers = self.headers(token_use='nextviewer')
        image = str(uuid.uuid4())
        self.assertEqual(self.client.get('/key-images/study/1.2.3', headers=headers).status_code, 403)
        self.assertEqual(self.client.get(f'/key-images/{image}/file', headers=headers).status_code, 403)
        self.assertEqual(self.client.delete(f'/key-images/{image}', headers=headers).status_code, 403)

    def test_routes_require_authentication(self):
        image = str(uuid.uuid4())
        self.assertEqual(self.client.get(f'/key-images/{image}/file').status_code, 401)
        self.assertEqual(self.client.get('/key-images/study/1.2.3').status_code, 401)

    def test_deleted_image_file_is_still_served_after_soft_delete(self):
        image = str(uuid.uuid4())
        (Path(self.folder.name) / f'{image}.png').write_bytes(png())
        self.cur.fetchone.return_value = {'owner_id': 'alice', 'deleted_at': None}
        self.assertEqual(self.client.delete(f'/key-images/{image}', headers=self.headers()).status_code, 200)
        self.assertTrue((Path(self.folder.name) / f'{image}.png').exists())
        response = self.client.get(f'/key-images/{image}/file', headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/png')
        response.close()

    def test_only_author_or_admin_can_delete(self):
        image = str(uuid.uuid4())
        self.cur.fetchone.return_value = {'owner_id': 'bob', 'deleted_at': None}
        self.assertEqual(self.client.delete(f'/key-images/{image}', headers=self.headers()).status_code, 403)
        subject.get_user_permission_codes.return_value = ['*']
        self.assertEqual(self.client.delete(f'/key-images/{image}', headers=self.headers()).status_code, 200)

    def test_malformed_id_is_not_found(self):
        self.assertEqual(self.client.get('/key-images/..%2Fsecret/file', headers=self.headers()).status_code, 404)


def view(**fields):
    return {'report': {'id_informe': 'exam-1', 'fecha': '2026-11-06', 'procedimientos': 'TC', 'accession_number': 'A1', 'modalidad': 'CT',
                       'textos': {key: {'as': key, 'contenido': value} for key, value in fields.items()}},
            'document': {'patient': {'name': '[PRUEBA] Luna', 'identifier': 'VT1'}, 'study': {'date': '2026-11-06'},
                         'institution': {'name': 'CDIVET'}, 'signatures': []}}


class PdfTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'known.png'
        self.path.write_bytes(png((800, 600)))

    def pdf(self, known=True, **fields):
        return PdfReader(BytesIO(render(view(**fields), LETTERHEAD, plain_report_text, key_images={'known': self.path} if known else {})))

    def embedded(self, reader):
        # The letterhead background is an image on every page.
        return sum(len(page.images) - 1 for page in reader.pages)

    def text(self, reader):
        return ' '.join(page.extract_text() for page in reader.pages)

    def test_image_appears_in_each_field(self):
        tag = '<img data-key-image-id="known" alt="x">'
        for field in ('study_reason', 'content', 'conclusion'):
            with self.subTest(field=field):
                self.assertEqual(self.embedded(self.pdf(**{field: f'<p>Texto</p>{tag}'})), 1)

    def test_section_with_only_an_image_is_kept(self):
        reader = self.pdf(content='<img data-key-image-id="known">')
        self.assertEqual(self.embedded(reader), 1)
        self.assertIn('CONTENT', self.text(reader))

    def test_same_image_can_repeat_across_fields(self):
        tag = '<img data-key-image-id="known">'
        self.assertEqual(self.embedded(self.pdf(content=tag, conclusion=tag)), 2)

    def test_image_of_another_study_is_not_embedded(self):
        reader = self.pdf(known=False, content='<p>Antes</p><img data-key-image-id="known"><p>Después</p>')
        self.assertEqual(self.embedded(reader), 0)
        self.assertIn('[imagen no disponible]', self.text(reader))
        self.assertIn('Después', self.text(reader))

    def test_missing_file_does_not_stop_the_report(self):
        self.path.unlink()
        self.assertIn('[imagen no disponible]', self.text(self.pdf(content='<img data-key-image-id="known">')))

    def test_text_order_and_bold_survive_around_an_image(self):
        blocks = _report_blocks('<p>Uno <strong>dos</strong></p><img data-key-image-id="a"><p><b>tres</b> &lt;x&gt;</p>')
        self.assertEqual([kind for kind, _ in blocks], ['text', 'image', 'text'])
        self.assertIn('<b>dos</b>', blocks[0][1])
        self.assertIn('<b>tres</b> &lt;x&gt;', blocks[2][1])

    def test_image_without_key_reference_and_empty_fields_add_nothing(self):
        self.assertEqual(_report_blocks('<p></p><img src="data:image/png;base64,AAAA">'), [])


if __name__ == '__main__':
    unittest.main()
