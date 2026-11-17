"""Live viewer handoff regression, including a server running outside UTC.

Set VIEWER_TEST_ACCESS_TOKEN to a staff JWT with images.view. Optionally set
VIEWER_TEST_API_URL (default https://cdivet.cloud/api). DB_* must refer to that
server's database. Creates only temporary viewer handoffs; never changes images
or clinical records. Expiration is simulated only on a handoff this test creates.
"""
import hashlib
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from dotenv import load_dotenv
import psycopg2
import requests


def run():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    token = os.environ.get('VIEWER_TEST_ACCESS_TOKEN')
    if not token:
        raise SystemExit('Set VIEWER_TEST_ACCESS_TOKEN to run this live integration test.')
    base = os.environ.get('VIEWER_TEST_API_URL', 'https://cdivet.cloud/api').rstrip('/')
    session = requests.Session()
    session.headers['Authorization'] = 'Bearer ' + token
    response = session.get(base + '/dicom/studies-by-location/all', timeout=30)
    assert response.status_code == 200
    studies = response.json()['data']['data']
    assert studies, 'A study with available images is required'
    study = studies[0]['study_iuid']
    wrong_study = '2.25.1' if study != '2.25.1' else '2.25.2'
    connection = psycopg2.connect(
        host=os.environ['DB_HOST'], port=os.environ.get('DB_PORT', '5432'),
        dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASS'])
    connection.autocommit = True
    try:
        def create():
            response = session.post(base + '/general/viewer-url-by-iuid',
                                    json={'study_iuid': study}, timeout=30)
            assert response.status_code == 200
            data = response.json()['data']
            assert data['expires_in'] == 60
            query = parse_qs(urlsplit(data['viewer_url']).query)
            code = query['handoff_code'][0]
            assert query['study_uid'] == [study]
            digest = hashlib.sha256(code.encode()).hexdigest()
            with connection.cursor() as cursor:
                cursor.execute('SELECT EXTRACT(EPOCH FROM expires_at-created_on), '
                               'expires_at > NOW(), consumed_at FROM nextris.tb_viewer_handoff '
                               'WHERE code_hash=%s', (digest,))
                lifetime, valid, consumed = cursor.fetchone()
            assert 59 <= lifetime <= 61, 'Handoff lifetime must be 60 seconds regardless of server timezone'
            assert valid and consumed is None
            return code, digest

        code, digest = create()
        response = requests.post(base + '/viewer/session/exchange',
                                 json={'code': code, 'studyInstanceUID': wrong_study}, timeout=30)
        assert response.status_code == 401, 'A code cannot authorize another study'
        response = requests.post(base + '/viewer/session/exchange',
                                 json={'code': code, 'studyInstanceUID': study}, timeout=30)
        assert response.status_code == 200, 'A freshly issued handoff must be valid'
        data = response.json()['data']
        assert data['dicomAccessToken'] and data['viewerAccessToken'] and data['clinicalAccess']
        response = requests.post(base + '/viewer/session/exchange',
                                 json={'code': code, 'studyInstanceUID': study}, timeout=30)
        assert response.status_code == 401, 'A consumed handoff cannot be reused'
        expired_code, expired_digest = create()
        with connection.cursor() as cursor:
            cursor.execute("UPDATE nextris.tb_viewer_handoff SET expires_at=NOW()-INTERVAL '1 second' "
                           'WHERE code_hash=%s AND consumed_at IS NULL', (expired_digest,))
            assert cursor.rowcount == 1
        response = requests.post(base + '/viewer/session/exchange',
                                 json={'code': expired_code, 'studyInstanceUID': study}, timeout=30)
        assert response.status_code == 401, 'An expired handoff must be rejected'
        print('PASS: UTC-independent 60-second lifetime, successful exchange, study scope, one-use enforcement and expiration.')
    finally:
        connection.close()
        session.close()


if __name__ == '__main__':
    run()
