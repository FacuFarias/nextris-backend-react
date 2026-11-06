"""Patient pagination contracts; optional PostgreSQL checks use synthetic TEMP tables.

CONFIG_PATIENTS_DB_TESTS=1 venv/bin/python tests/test_config_patients_pagination.py
"""
import ast
import json
import os
from pathlib import Path
import types
import unittest
from unittest.mock import MagicMock

from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
import psycopg2
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT / 'apps/api/config.py').read_text())
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'get_config_patients')
function.decorator_list = []
namespace = dict(request=request, jsonify=jsonify, json=json,
                 psycopg2=types.SimpleNamespace(connect=MagicMock()), get_db_config=lambda: {'synthetic': True})
exec(compile(ast.Module(body=[function], type_ignores=[]), 'apps/api/config.py', 'exec'), namespace)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, root_path=str(ROOT), instance_path=str(ROOT / 'instance'))
        self.app.config.update(TESTING=True, JWT_SECRET_KEY='synthetic-pagination-test-secret-key')
        JWTManager(self.app)
        self.app.add_url_rule('/patients', view_func=jwt_required()(namespace['get_config_patients']))
        self.client = self.app.test_client()
        with self.app.app_context():
            self.headers = {'Authorization': 'Bearer ' + create_access_token(identity='synthetic-operator')}
        self.db = MagicMock()
        self.cursor = self.db.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = (23,)
        self.cursor.fetchall.return_value = [('id', 'Paciente Sintético', None, None, 'synthetic', 'Active', None)]
        namespace['psycopg2'].connect.reset_mock(side_effect=True)
        namespace['psycopg2'].connect.return_value = self.db

    def get(self, **params):
        return self.client.get('/patients', query_string=params, headers=self.headers)

    def test_authentication_precedes_database(self):
        self.assertEqual(self.client.get('/patients').status_code, 401)
        namespace['psycopg2'].connect.assert_not_called()

    def test_defaults_are_bounded_and_count_does_not_join_personal_data(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual({key: response.json[key] for key in ['total', 'page', 'per_page', 'pages']},
                         dict(total=23, page=1, per_page=8, pages=3))
        count, query = self.cursor.execute.call_args_list
        self.assertNotIn('JOIN', count.args[0])
        self.assertIn("p.status = 'Active'", count.args[0])
        self.assertIn('ORDER BY p.guid ASC', query.args[0])
        self.assertIn('LIMIT %s OFFSET %s', query.args[0])
        self.assertEqual(query.args[1], [8, 0])
        self.db.close.assert_called_once()

    def test_requested_page_size_offset_and_out_of_range_page(self):
        self.assertEqual(self.get(page=3, per_page=5).json['page'], 3)
        self.assertEqual(self.cursor.execute.call_args.args[1], [5, 10])
        response = self.get(page=999, per_page=5)
        self.assertEqual(response.json['page'], 5)
        self.assertEqual(self.cursor.execute.call_args.args[1], [5, 20])
        self.cursor.fetchone.return_value = (0,)
        response = self.get(page=3, per_page=5)
        self.assertEqual((response.json['page'], response.json['pages']), (1, 0))
        self.assertEqual(self.cursor.execute.call_args.args[1], [5, 0])

    def test_filters_apply_to_count_and_page_before_limit_with_safe_sort(self):
        self.get(page=2, per_page=5, include_inactive='true', sort_column='name', sort_direction='desc',
                 column_filters=json.dumps({'username': "  a%'_\\  ", 'name': 'Prueba'}))
        count, query = self.cursor.execute.call_args_list
        self.assertIn('LEFT JOIN', count.args[0])
        self.assertNotIn("p.status = 'Active'", query.args[0])
        self.assertNotIn("a%'", query.args[0])
        self.assertIn('p.username::text ILIKE %s', count.args[0])
        self.assertIn("CONCAT(dp.surname, ' ', dp.name) DESC NULLS LAST, p.guid ASC", query.args[0])
        self.assertEqual(query.args[1][:-2], count.args[1])
        self.assertEqual(count.args[1], ["%a\\%'\\_\\\\%", '%Prueba%'])

    def test_invalid_or_unbounded_requests_never_query_database(self):
        for params in [dict(page=0), dict(page='x'), dict(per_page=0), dict(per_page=-1),
                       dict(per_page=101), dict(per_page='all'), dict(column_filters='[]'),
                       dict(column_filters='{'), dict(column_filters='{"unknown":"x"}'),
                       dict(column_filters='{"name":{}}'), dict(sort_column='p.guid; SELECT 1'),
                       dict(sort_direction='asc; SELECT 1')]:
            with self.subTest(params=params):
                self.assertEqual(self.get(**params).status_code, 400)
        namespace['psycopg2'].connect.assert_not_called()

    def test_query_failure_closes_database_connection(self):
        self.cursor.execute.side_effect = RuntimeError('Synthetic query failure')
        self.assertEqual(self.get().status_code, 500)
        self.db.close.assert_called_once()


class TempCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cursor.close()

    def execute(self, sql, params=None):
        # Explicit pg_temp qualification prevents access to real patient tables.
        return self.cursor.execute(sql.replace('nextris.', 'pg_temp.'), params)

    def __getattr__(self, name):
        return getattr(self.cursor, name)


@unittest.skipUnless(os.getenv('CONFIG_PATIENTS_DB_TESTS') == '1', 'PostgreSQL TEMP-table tests opt in')
class DatabaseTests(unittest.TestCase):
    def test_real_sql_pagination_filters_sort_and_empty_results(self):
        load_dotenv(ROOT / '.env')
        db = psycopg2.connect(user=os.getenv('DB_USER'), password=os.getenv('DB_PASS'),
                             host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'), dbname=os.getenv('DB_NAME'))
        self.addCleanup(db.close)
        with db.cursor() as cursor:
            cursor.execute('''CREATE TEMP TABLE tbuser_patient (
                guid TEXT PRIMARY KEY, datapatient_id TEXT, username TEXT, status TEXT, lastlogin TIMESTAMP)''')
            cursor.execute('''CREATE TEMP TABLE datapatient (
                guid TEXT PRIMARY KEY, surname TEXT, name TEXT, nationalcode TEXT,
                birthdate DATE, email TEXT, phone TEXT, sexcode TEXT)''')
            cursor.execute('''INSERT INTO pg_temp.datapatient
                SELECT i::text, CASE WHEN i <= 4 THEN 'Subset' ELSE 'Other' END,
                       'Synthetic ' || i, i::text, '2000-01-01'::date, '', '', 'O'
                FROM generate_series(1, 23) i''')
            cursor.execute('''INSERT INTO pg_temp.tbuser_patient
                SELECT lpad(i::text, 3, '0'), i::text, 'synthetic-' || lpad(i::text, 3, '0'),
                       CASE WHEN i = 23 THEN 'Inactive' ELSE 'Active' END, NULL
                FROM generate_series(1, 23) i''')
        proxy = types.SimpleNamespace(cursor=lambda: TempCursor(db.cursor()), close=lambda: None)
        namespace['psycopg2'].connect.return_value = proxy
        app = Flask(__name__, root_path=str(ROOT), instance_path=str(ROOT / 'instance'))

        def get(**params):
            with app.test_request_context(query_string=params):
                response, status = namespace['get_config_patients']()
                self.assertEqual(status, 200, response.json)
                return response.json

        first = get()
        self.assertEqual((len(first['data']), first['total']), (8, 22))
        second = get(page=2)
        self.assertEqual(len(second['data']), 8)
        self.assertTrue({row['guid'] for row in first['data']}.isdisjoint(row['guid'] for row in second['data']))
        last = get(page=99, per_page=5, include_inactive='true')
        self.assertEqual((last['page'], last['total'], len(last['data'])), (5, 23, 3))
        subset = get(per_page=2, column_filters=json.dumps({'name': 'Subset'}),
                     sort_column='username', sort_direction='desc')
        self.assertEqual((subset['total'], len(subset['data'])), (4, 2))
        self.assertEqual([row['username'] for row in subset['data']], ['synthetic-004', 'synthetic-003'])
        self.assertEqual(get(column_filters='{"name":"missing"}')['total'], 0)
        # Literal wildcard characters must not match all rows.
        self.assertEqual(get(column_filters='{"name":"%"}')['total'], 0)
        self.assertEqual(get(column_filters='{"name":"_"}')['total'], 0)
        for column in ['name', 'national_number', 'email', 'phone', 'birthdate', 'gender', 'is_active']:
            self.assertEqual(len(get(sort_column=column)['data']), 8)


if __name__ == '__main__':
    unittest.main()
