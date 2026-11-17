"""Real HTTP/SQL cache tests against a disposable DB, without mocks.

DB_NAME must be cdivet_storage_cache_*_test and CACHE_TEST_API_URL must target
its isolated server. That server must have PACS_STOW_URL and the token URL
pointing to http://127.0.0.1:1 to prohibit archive operations on cloned studies.
"""
import datetime as dt
import os
import sys
import uuid
from pathlib import Path

import psycopg2
import requests
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.services.storage_cache import retention, policy  # noqa: E402


def run():
    db = os.environ['DB_NAME']
    assert db.startswith('cdivet_storage_cache_') and db.endswith('_test')
    base = os.environ['CACHE_TEST_API_URL']
    assert base.startswith('http://127.0.0.1:5005/')
    conn = psycopg2.connect(host=os.environ['DB_HOST'], port=os.getenv('DB_PORT', '5432'),
        dbname=db, user=os.environ['DB_USER'], password=os.environ['DB_PASS'])
    conn.autocommit = True
    cur = conn.cursor()
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY') or os.environ['SECRET_KEY']
    JWTManager(app)
    cur.execute("SELECT guid FROM nextris.tbuser WHERE username='admin'")
    actor = str(cur.fetchone()[0])

    def auth(identity=actor, **claims):
        with app.app_context():
            return {'Authorization': 'Bearer ' + create_access_token(identity=identity,
                additional_claims={'user_type': 'staff', **claims})}

    checks = 0

    def call(method, path, expected=200, headers=None, body=None):
        nonlocal checks
        r = requests.request(method, base + path, headers=headers if headers is not None else auth(),
                             json=body, timeout=30)
        assert r.status_code == expected, (method, path, r.status_code, r.text[:300])
        checks += 1
        return r.json().get('data')

    # Verify policy boundaries using the same live config the timer reads.
    config = policy()
    entered = dt.datetime(2026, 11, 10, 2, 30, tzinfo=dt.timezone.utc)  # November 9 in Argentina
    row = dict(entered_at=entered, last_write_at=entered, storage='fs1', study_date='20261109',
               deleting=False, all_backed_up=True)
    now = entered + dt.timedelta(hours=3)
    assert retention(row, config, now)['ttl_seconds'] == 5 * 86400
    assert retention({**row, 'study_date': '20261110'}, config, now)['ttl_seconds'] == 5 * 86400
    assert retention({**row, 'study_date': ''}, config, now)['ttl_seconds'] == 5 * 86400
    assert retention({**row, 'storage': 'fs1-retrieve'}, config, now)['ttl_seconds'] == 86400
    assert retention({**row, 'all_backed_up': False}, config, now)['can_remove'] is False
    assert retention({**row, 'last_write_at': now}, config, now)['can_remove'] is False
    assert retention({**row, 'deleting': True}, config, now)['can_remove'] is False
    assert retention(row, config, entered + dt.timedelta(days=5, seconds=-1))['expired'] is False
    assert retention(row, config, entered + dt.timedelta(days=5))['expired'] is True

    cur.execute('SELECT pk,study_iuid FROM public.study ORDER BY pk LIMIT 2')
    first, second = cur.fetchall()
    cur.execute('SELECT coalesce(max(pk),0)+100 FROM public.location')
    location_pk = cur.fetchone()[0]
    for index, (study, storage) in enumerate([(first, 'fs1'), (first, 'fs1-retrieve'), (second, 'fs1')]):
        cur.execute("""INSERT INTO public.location(pk,created_time,digest,multi_ref,object_type,object_size,
                   status,storage_id,storage_path,tsuid,uidmap_fk,instance_fk)
            SELECT %s,(now() AT TIME ZONE 'UTC')-interval '1 hour',l.digest,l.multi_ref,l.object_type,
                   l.object_size + %s,0,%s,'synthetic/test-cache',l.tsuid,l.uidmap_fk,l.instance_fk
            FROM public.location l JOIN public.instance i ON i.pk=l.instance_fk
            JOIN public.series se ON se.pk=i.series_fk
            WHERE se.study_fk=%s AND l.storage_id='b2' AND l.status=0 AND l.object_type=0 LIMIT 1""",
                    (location_pk + index, 1 if index == 0 else 0, storage, study[0]))
        assert cur.rowcount == 1
    cur.execute("UPDATE public.instance SET updated_time=(now() AT TIME ZONE 'UTC') WHERE pk IN "
                "(SELECT instance_fk FROM public.location WHERE pk IN (%s,%s))", (location_pk, location_pk + 1))
    limited = str(uuid.uuid4())
    cur.execute("SELECT guid FROM nextris.isrole WHERE lower(description)<>'sysadmin' LIMIT 1")
    role = cur.fetchone()[0]
    cur.execute('INSERT INTO nextris.tbuser(guid,username,password,idrole,isactive,first_login) VALUES(%s,%s,%s,%s,1,0)',
                (limited, 'synthetic-cache-' + uuid.uuid4().hex[:8], 'unusable-password', role))
    cur.execute("INSERT INTO nextris.rel_user_permission(guid,user_id,permission_id,is_granted) "
                "SELECT %s,%s,guid,true FROM nextris.ispermission WHERE code='storage.view'", (str(uuid.uuid4()), limited))

    call('GET', '/storage/cache/studies', 401, headers={})
    call('GET', '/storage/cache/studies', 403, headers=auth(token_use='viewer'))
    call('GET', '/storage/cache/studies', 403, headers=auth(user_type='patient'))
    overview = call('GET', '/storage/overview')
    assert overview['local_cache']['studies'] == 2  # three local copies, two studies
    cur.execute("SELECT count(DISTINCT se.study_fk) FROM public.location l JOIN public.instance i ON i.pk=l.instance_fk "
                "JOIN public.series se ON se.pk=i.series_fk WHERE l.status=0 AND l.storage_id='b2' AND l.object_type=0")
    assert overview['b2']['studies'] == cur.fetchone()[0]
    result = call('GET', '/storage/cache/studies')
    assert result['total'] == 2 and len(result['items']) == 2
    item = next(s for s in result['items'] if s['study_pk'] == first[0])
    assert len(item['copies']) == 2 and all(not c['can_remove'] for c in item['copies'])
    assert all(c['expires_at'] and c['entered_at'] and c['ttl_seconds'] for c in item['copies'])
    assert any('B2' in c['blocked_reason'] for c in item['copies'])
    assert any('recibiendo' in c['blocked_reason'] for c in item['copies'])
    assert call('GET', '/storage/cache/studies?per_page=1&page=2')['page'] == 2
    assert len(call('GET', '/storage/cache/studies?per_page=1')['items']) == 1
    assert call('GET', '/storage/cache/studies?search=' + first[1])['total'] == 1
    assert call('GET', '/storage/cache/studies?search=no-such-cache-study')['total'] == 0
    call('GET', '/storage/cache/studies?page=bad', 400)
    path = '/storage/cache/studies/' + str(first[0])
    call('DELETE', path, 400, body={'storage': 'fs1'})
    call('DELETE', path, 400, body={'storage': 'b2', 'confirm': True})
    call('DELETE', path, 400, body={'storage': [], 'confirm': True})
    call('DELETE', path, 403, headers=auth(limited), body={'storage': 'fs1', 'confirm': True})
    call('DELETE', path, 403, headers=auth(token_use='viewer'), body={'storage': 'fs1', 'confirm': True})
    call('DELETE', path, 409, body={'storage': 'fs1', 'confirm': True})
    call('DELETE', path, 409, body={'storage': 'fs1-retrieve', 'confirm': True})
    call('DELETE', '/storage/cache/studies/2147483647', 404, body={'storage': 'fs1', 'confirm': True})
    call('DELETE', '/storage/cache/studies/2147483648', 400, body={'storage': 'fs1', 'confirm': True})
    cur.execute('UPDATE public.study SET study_deleting=true WHERE pk=%s', (second[0],))
    call('DELETE', '/storage/cache/studies/' + str(second[0]), 409, body={'storage': 'fs1', 'confirm': True})
    cur.execute('UPDATE public.study SET study_deleting=false WHERE pk=%s', (second[0],))
    cur.execute("SELECT pk FROM public.task WHERE study_iuid=%s AND exporter_id='TTLRemoveInitial' ORDER BY created_time DESC,pk DESC LIMIT 1", (second[1],))
    task_pk = cur.fetchone()[0]
    cur.execute("UPDATE public.task SET task_status=0,created_time=(now() AT TIME ZONE 'UTC') WHERE pk=%s", (task_pk,))
    copy = call('GET', '/storage/cache/studies?search=' + second[1])['items'][0]['copies'][0]
    assert copy['queue_status'] == 'queued' and not copy['can_remove']
    cur.execute('UPDATE public.task SET task_status=4 WHERE pk=%s', (task_pk,))
    copy = call('GET', '/storage/cache/studies?search=' + second[1])['items'][0]['copies'][0]
    assert copy['queue_status'] == 'failed' and copy['can_remove']
    print(f'PASS: {checks} real HTTP checks; distinct counts, copies, deadlines, pagination, search, permissions and protected removals.')
    cur.close()
    conn.close()


if __name__ == '__main__':
    run()
