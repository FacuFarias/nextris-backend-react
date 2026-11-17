"""Exercise real HTTP filtering against a disposable copy of the PACS database.

DB_NAME must start with cdivet_unlinked_; start the backend using that database
on port 5003. Never writes to production or sends requests to the PACS archive.
"""
import os
from datetime import timedelta
import uuid

import psycopg2
import requests
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token


def run():
    assert os.environ['DB_NAME'].startswith('cdivet_unlinked_'), 'Disposable database required'
    connection = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ.get('DB_PORT', '5432'),
        dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASS'])
    connection.autocommit = True
    cursor = connection.cursor()
    cursor.execute("SELECT guid FROM nextris.tbuser WHERE username='admin'")
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY') or os.environ['SECRET_KEY']
    JWTManager(app)
    with app.app_context():
        token = create_access_token(identity=str(cursor.fetchone()[0]), expires_delta=timedelta(minutes=5),
                                    additional_claims={'user_type': 'staff'})
    session = requests.Session()
    session.headers['Authorization'] = 'Bearer ' + token
    url = 'http://127.0.0.1:5003/api/dicom/studies-by-location/all'

    def listing(enabled=None, **params):
        if enabled is not None:
            params['unlinked_only'] = str(enabled).lower()
        response = session.get(url, params={'per_page': 100, **params}, timeout=30)
        assert response.status_code == 200, response.text[:200]
        return response.json()['data']

    try:
        original = listing()
        studies = original['data']
        assert len(studies) >= 2
        first, second = studies[:2]
        cursor.execute("UPDATE nextris.tbpacs_study_link SET link_status='unlinked' "
                       'WHERE pacs_study_iuid=ANY(%s) OR pacs_study_pk=ANY(%s)',
                       ([s['study_iuid'] for s in studies], [s['pk'] for s in studies]))
        cursor.execute('UPDATE nextris.tbexamination SET isimage=0 WHERE studyinstanceuid=ANY(%s)',
                       ([s['study_iuid'] for s in studies],))
        assert listing(True)['total'] == original['total']
        exam = str(uuid.uuid4())
        cursor.execute('INSERT INTO nextris.tbexamination (guid,studyinstanceuid,isimage) VALUES (%s,%s,1)',
                       (exam, first['study_iuid']))
        assert listing(False)['total'] == original['total']
        assert listing()['total'] == original['total'], 'Existing clients retain the unfiltered API default'
        filtered = listing(True)
        assert filtered['total'] == original['total'] - 1
        assert all(not s['is_linked'] and s['pk'] != first['pk'] for s in filtered['data'])
        for sort in ['study_datetime', 'patient_id', 'is_linked', 'num_series']:
            page = listing(True, page=1, per_page=1, sort_column=sort)
            assert page['total'] == filtered['total'] and len(page['data']) == 1
            assert not page['data'][0]['is_linked'], 'Filter must apply before pagination'
        assert listing(True, search=first['study_iuid'])['total'] == 0
        cursor.execute('UPDATE nextris.tbexamination SET isimage=0 WHERE guid=%s', (exam,))
        assert listing(True)['total'] == original['total']
        cursor.execute('UPDATE nextris.tbexamination SET studyinstanceuid=%s WHERE guid=%s', ('2.25.' + str(uuid.uuid4().int), exam))
        cursor.execute("INSERT INTO nextris.tbpacs_study_link (pacs_study_pk,pacs_study_iuid,order_guid,source) "
                       "VALUES (%s,%s,%s,'manual') RETURNING id", (first['pk'], first['study_iuid'], exam))
        link = cursor.fetchone()[0]
        assert listing(True)['total'] == original['total'] - 1, 'Active manual links must be excluded'
        cursor.execute("UPDATE nextris.tbpacs_study_link SET link_status='unlinked' WHERE id=%s", (link,))
        assert listing(True)['total'] == original['total'], 'Historical links must not exclude a study'
        cursor.execute("UPDATE nextris.tbpacs_study_link SET link_status='linked',pacs_study_pk=%s WHERE id=%s",
                       (second['pk'], link))
        result = listing(True)
        assert result['total'] == original['total'] - 2, 'Both study UID and PACS primary-key associations count'
        assert listing(True, search=first['study_iuid'])['data'] == []
        assert listing(True, search=second['study_iuid'])['total'] == 0
        print('PASS: default API compatibility, linked/unlinked selection, direct and manual links, historical links, search, counts and pagination across sort modes.')
    finally:
        session.close()
        connection.close()


if __name__ == '__main__':
    run()
