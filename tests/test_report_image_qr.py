"""QR de imágenes en el PDF del informe. No requiere base de datos ni servidor; solo pypdf para leer el PDF."""
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flask import Flask
from pypdf import PdfReader
from io import BytesIO

from apps.api import viewer_share_service as shares
from apps.services import report_image_qr
from apps.services.report_letterhead_pdf import render
from apps.services.report_view_service import plain_report_text

LETTERHEAD = ROOT / 'apps/static/assets/img/report/cdivet-letterhead.png'
URL = 'https://cdivet.cloud/api/s/AbCdEfGhIj'
LINK = {'share_url': URL, 'expires_at': datetime(2026, 12, 6), 'valid_days': 15}


def view(paragraphs=1, signatures=1):
    return {
        'report': {'id_informe': 'exam-1', 'fecha': '2026-11-06', 'procedimientos': 'TC', 'accession_number': 'A1', 'modalidad': 'CT',
                   'textos': {'content': {'as': 'Informe', 'contenido': '<p>Hallazgo sintético.</p>' * paragraphs}}},
        'document': {'patient': {'name': '[PRUEBA] Luna', 'identifier': 'VT1'}, 'study': {'date': '2026-11-06'},
                     'institution': {'name': 'CDIVET'},
                     'signatures': [{'professional': f'Profesional {n}', 'registration': '1'} for n in range(signatures)]},
    }


def pages(pdf):
    return PdfReader(BytesIO(pdf)).pages


def links(page):
    return [note.get_object()['/A']['/URI'] for note in page.get('/Annots', [])]


class FakeConnection:
    """Answers the study lookup and the latest-link lookup; the advisory lock returns nothing."""

    def __init__(self, study, latest):
        self.study, self.latest, self.committed, self.closed, self.sql = study, latest, False, False, []

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, _params=None):
        self.sql.append(sql)

    def fetchone(self):
        last = self.sql[-1]
        if 'available_pacs_study' in last:
            return (self.study,) if self.study else None
        return self.latest

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class LayoutTests(unittest.TestCase):
    def test_qr_stays_on_last_page_beside_signature(self):
        for paragraphs, signatures in [(1, 1), (60, 1), (140, 1), (1, 0)]:
            with self.subTest(paragraphs=paragraphs, signatures=signatures):
                plain = pages(render(view(paragraphs, signatures), LETTERHEAD, plain_report_text))
                result = pages(render(view(paragraphs, signatures), LETTERHEAD, plain_report_text, image_link=LINK))
                self.assertEqual(len(result), len(plain), 'el QR no debe agregar hojas')
                self.assertEqual(links(result[-1]), [URL])
                text = result[-1].extract_text()
                self.assertIn('Imágenes del estudio', text)
                self.assertIn('válido por 15 días', ' '.join(text.split()))
                self.assertIn('06/12/2026', text)
                if signatures:
                    self.assertIn('Profesional 0', text)

    def test_without_link_there_is_no_qr(self):
        result = pages(render(view(), LETTERHEAD, plain_report_text))
        self.assertEqual(links(result[-1]), [])
        self.assertNotIn('Imágenes del estudio', result[-1].extract_text())

    def test_failure_issuing_link_does_not_block_report(self):
        with mock.patch.object(shares, 'report_image_link', side_effect=RuntimeError('db down')):
            with self.assertLogs(report_image_qr.logger, 'ERROR'):
                self.assertIsNone(report_image_qr.image_link_for(view()))


class LinkRulesTests(unittest.TestCase):
    def resolve(self, study, latest):
        connection = FakeConnection(study, latest)
        app = Flask(__name__)
        app.config['PUBLIC_API_URL'] = 'https://cdivet.cloud'
        with app.app_context(), mock.patch.object(shares.psycopg2, 'connect', return_value=connection), \
                mock.patch.object(shares, 'create_for_exam', return_value={'share_url': 'https://cdivet.cloud/api/s/new'}) as create:
            return shares.report_image_link('exam-1'), create, connection

    def test_no_images_no_link(self):
        result, create, connection = self.resolve(None, None)
        self.assertIsNone(result)
        create.assert_not_called()
        self.assertTrue(connection.closed)

    def test_active_link_is_renewed_so_printed_copies_keep_working(self):
        result, create, connection = self.resolve('1.2.3', ('guid-1', 'code', datetime.utcnow() + timedelta(days=3), False))
        self.assertEqual(result['share_url'], 'https://cdivet.cloud/api/s/code')
        self.assertEqual(result['valid_days'], 15)
        self.assertAlmostEqual(result['expires_at'], datetime.utcnow() + timedelta(days=15), delta=timedelta(minutes=1))
        create.assert_not_called()
        self.assertIn('GREATEST(expires_at', connection.sql[-1])
        self.assertTrue(connection.committed)

    def test_revoked_expired_or_missing_link_gets_a_new_one_for_15_days(self):
        for latest in (('guid-1', 'code', datetime.utcnow() + timedelta(days=3), True),
                       ('guid-1', 'code', datetime.utcnow() - timedelta(days=1), False), None):
            with self.subTest(latest=latest):
                result, create, connection = self.resolve('1.2.3', latest)
                self.assertEqual(result['share_url'], 'https://cdivet.cloud/api/s/new')
                self.assertEqual(result['valid_days'], 15)
                self.assertEqual(create.call_args.kwargs['expires_hours'], 360)
                self.assertTrue(connection.committed)

    def test_portal_sessions_are_excluded_and_creation_is_serialized(self):
        _, _, connection = self.resolve('1.2.3', None)
        joined = ' '.join(connection.sql)
        self.assertIn('portal_account_id IS NULL', joined)
        self.assertIn('pg_advisory_xact_lock', joined)


if __name__ == '__main__':
    unittest.main()
