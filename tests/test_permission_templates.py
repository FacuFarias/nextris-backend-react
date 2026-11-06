"""Permission contracts; optional PostgreSQL tests use only a disposable schema.

NEXTRIS_PERMISSION_DB_TESTS=1 venv/bin/python tests/test_permission_templates.py
"""
import ast
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import uuid

from flask import Flask, Blueprint, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token
import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = load('permission_policy_contract', 'apps/permission_policy.py')
utils = types.ModuleType('apps.api.utils')
utils.get_db_config = lambda: {}
with patch.dict(sys.modules, {'apps.permission_policy': policy, 'apps.api.utils': utils}):
    permissions = load('permission_subject', 'apps/api/permissions.py')
migration = load('permission_migration_subject', 'deployment/migrations/20261021_permission_templates.py')
share_migration = load('share_permission_migration', 'deployment/migrations/20261102_worklist_share.py')
clinical_migration = load('clinical_permission_migration', 'deployment/migrations/20261021_clinical_role_adjustments.py')


class PolicyTest(unittest.TestCase):
    def test_defaults_match_the_five_operational_profiles(self):
        self.assertEqual(policy.get_default_permissions_for_role('Sysadmin'), ['*'])
        self.assertEqual(set(policy.get_default_permissions_for_role('Médico')), {
            'patients.view', 'tabs.worklist.view', 'reports.write', 'reports.sign',
            'templates.manage', 'images.view', 'images.share_link', 'reports.unsign', 'worklist.share'})
        self.assertEqual(set(policy.get_default_permissions_for_role('Técnico')), {
            'patients.view', 'tabs.worklist.view', 'worklist.confirm_execute', 'images.view', 'dicom.studies.manage', 'worklist.share'})
        self.assertNotIn('tabs.gestion.view', policy.get_default_permissions_for_role('Médico'))
        self.assertIn('users.permissions.manage', policy.get_default_permissions_for_role('Administrador'))
        self.assertIn('distribution.send_report_whatsapp', policy.get_default_permissions_for_role('Administrativo'))
        for role in ['Administrador', 'Administrativo', 'Médico', 'Técnico']:
            self.assertFalse({'images.delete','reports.notes.delete','users.impersonate'}
                             & set(policy.get_default_permissions_for_role(role)))

    def test_share_defaults_include_custom_staff_roles_and_exclude_patients(self):
        for role in ['Administrador', 'Administrativo', 'Médico', 'Técnico', 'Custom staff']:
            self.assertIn('worklist.share', policy.get_default_permissions_for_role(role))
        self.assertNotIn('worklist.share', policy.get_default_permissions_for_role('patient'))

    def test_share_endpoints_authorize_new_and_existing_grants(self):
        tree = ast.parse((ROOT/'apps/api/general.py').read_text())
        app = Flask(__name__, root_path=str(ROOT), instance_path=str(ROOT/'instance'))
        app.config['JWT_SECRET_KEY'] = 'isolated-sharing-contract-secret-32bytes'
        JWTManager(app)
        for name in ['create_viewer_share_link', 'create_staff_case_link']:
            node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            decorator = next(d for d in node.decorator_list if isinstance(d, ast.Call)
                             and isinstance(d.func, ast.Name) and d.func.id == 'require_any_permission')
            # Use the real endpoint's authorization expression without clinical writes.
            authorize = eval(compile(ast.Expression(decorator), '<sharing-auth>', 'eval'),
                             {'require_any_permission': permissions.require_any_permission})
            protected = authorize(lambda: jsonify(success=True))
            for grants, user_type, expected in [
                (['worklist.share'], 'staff', 200), (['images.share_link'], 'staff', 200),
                (['*'], 'staff', 200), ([], 'staff', 403),
                (['images.view'], 'staff', 403), (['worklist.share'], 'patient', 403),
            ]:
                with self.subTest(endpoint=name, grants=grants, user_type=user_type):
                    with app.test_request_context(), patch.object(permissions, 'get_jwt_identity', return_value='synthetic'), patch.object(permissions, 'get_jwt', return_value={'user_type': user_type}), patch.object(permissions, 'get_user_permission_codes', return_value=grants):
                        response = protected()
                        self.assertEqual(response[1] if isinstance(response, tuple) else response.status_code, expected)

    def test_catalog_excludes_disabled_and_duplicate_permissions(self):
        self.assertFalse(any(item['module'] in policy.DISABLED_MODULES for item in policy.PERMISSION_CATALOG))
        self.assertFalse(policy.VALID_PERMISSION_CODES & set(policy.DEPRECATED_PERMISSION_ALIASES))
        self.assertEqual(policy.validate_permission_codes(['tabs.patients.view','patients.view']), ['patients.view'])
        self.assertEqual(policy.validate_permission_codes([]), [])
        for invalid in ['*','missing']:
            with self.assertRaises(ValueError): policy.validate_permission_codes([invalid])
        self.assertEqual(policy.validate_permission_codes(['tabs.nexi.view','admissions.view']), ['tabs.nexi.view','admissions.view'])
        for invalid in [None, {}, 'patients.view', [42]]:
            with self.assertRaises(ValueError): policy.validate_permission_codes(invalid)

    def test_decorator_uses_saved_permission_not_role_and_excludes_patients(self):
        app=Flask(__name__,root_path=str(ROOT),instance_path=str(ROOT/"instance")); app.config['JWT_SECRET_KEY']='isolated-permissions-test-secret-32bytes'
        JWTManager(app)
        @app.get('/protected')
        @permissions.require_admin_permission('worklist.link_missing_images')
        def protected(): return jsonify(success=True)
        with app.test_request_context():
            # This decorator expects an already verified JWT, like the production @jwt_required.
            with patch.object(permissions,'get_jwt_identity',return_value='technician'), patch.object(permissions,'get_jwt',return_value={'user_type':'staff'}), patch.object(permissions,'get_user_permission_codes',return_value=['worklist.link_missing_images']):
                self.assertEqual(protected().status_code,200)
            with patch.object(permissions,'get_jwt_identity',return_value='doctor'), patch.object(permissions,'get_jwt',return_value={'user_type':'staff'}), patch.object(permissions,'get_user_permission_codes',return_value=[]):
                self.assertEqual(protected()[1],403)
            with patch.object(permissions,'get_jwt_identity',return_value='patient'), patch.object(permissions,'get_jwt',return_value={'user_type':'patient'}), patch.object(permissions,'get_user_permission_codes',return_value=['*']):
                self.assertEqual(protected()[1],403)


class CursorProxy:
    def __init__(self, cursor, schema): self.cursor=cursor; self.schema=schema
    def execute(self, query, params=None):
        if isinstance(query,str): query=query.replace('nextris.', '"'+self.schema+'".')
        return self.cursor.execute(query,params)
    def executemany(self, query, params):
        return self.cursor.executemany(query.replace('nextris.', '"'+self.schema+'".'),params)
    def __getattr__(self,name): return getattr(self.cursor,name)
    def __enter__(self): return self
    def __exit__(self,*args): self.cursor.close()


class ConnectionProxy:
    def __init__(self, connection, schema): self.connection=connection; self.schema=schema; self.commits=0
    def cursor(self,*args,**kwargs): return CursorProxy(self.connection.cursor(*args,**kwargs),self.schema)
    def commit(self): self.commits+=1; self.connection.commit()
    def rollback(self): self.connection.rollback()
    def close(self): pass


@unittest.skipUnless(os.getenv('NEXTRIS_PERMISSION_DB_TESTS') == '1','enable isolated PostgreSQL tests explicitly')
class DatabaseContractTest(unittest.TestCase):
    def setUp(self):
        from dotenv import load_dotenv
        load_dotenv(ROOT/'.env')
        self.connection=psycopg2.connect(user=os.getenv('DB_USER'),password=os.getenv('DB_PASS'),
            host=os.getenv('DB_HOST'),port=os.getenv('DB_PORT'),dbname=os.getenv('DB_NAME'))
        self.schema='permission_test_'+uuid.uuid4().hex
        with self.connection.cursor() as c:
            c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
            c.execute(sql.SQL('SET search_path TO {}, public').format(sql.Identifier(self.schema)))
            c.execute('''CREATE TABLE isrole(guid varchar(50) PRIMARY KEY,description text);
                CREATE TABLE tbuser(guid varchar(50) PRIMARY KEY,username text UNIQUE,mail text,password text,
                    name text,surname text,nationalnumber text,idrole varchar(50) REFERENCES isrole(guid),
                    isactive smallint,first_login smallint);
                CREATE TABLE ispermission(guid varchar(50) PRIMARY KEY,code varchar(100) UNIQUE,module text,
                    action text,description text,is_active boolean,created_on timestamp DEFAULT NOW());
                CREATE TABLE rel_user_permission(guid varchar(50) PRIMARY KEY,user_id varchar(50) REFERENCES tbuser(guid),
                    permission_id varchar(50) REFERENCES ispermission(guid),is_granted boolean DEFAULT TRUE,
                    created_on timestamp DEFAULT NOW(),updated_on timestamp DEFAULT NOW(),UNIQUE(user_id,permission_id));''')
            for role in ['Sysadmin','Administrador','Administrativo','Medico','Tecnico']:
                c.execute('INSERT INTO isrole VALUES (%s,%s)',(role.lower(),role))
                c.execute('INSERT INTO tbuser(guid,username,idrole,isactive) VALUES (%s,%s,%s,1)',(role.lower(),role.lower(),role.lower()))
            for code in ['tabs.patients.view','tabs.images.view','tabs.nexi.view','reports.unsign']:
                c.execute('INSERT INTO ispermission(guid,code,module,action,description,is_active) VALUES (%s,%s,%s,%s,%s,TRUE)',(code,code,code.split('.')[0],'view',code))
            c.execute("INSERT INTO rel_user_permission(guid,user_id,permission_id) VALUES ('custom','tecnico','reports.unsign')")
        self.connection.commit()
        self.proxy=ConnectionProxy(self.connection,self.schema)

    def tearDown(self):
        self.connection.rollback()
        with self.connection.cursor() as c:
            c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.connection.commit();self.connection.close()

    def migrate(self):
        audit=migration.migrate(self.connection,True,self.schema)
        self.connection.commit()
        return audit

    def test_migration_preserves_legacy_access_and_is_idempotent_after_revocation(self):
        before=migration.migrate(self.connection,False,self.schema)
        self.connection.rollback()
        self.assertEqual(before['status'],'preview')
        audit=self.migrate()
        user=next(user for user in audit['users'] if user['user_id']=='tecnico')
        self.assertIn('reports.unsign',user['after_permissions'])
        self.assertIn('images.view',user['after_permissions'])
        self.assertFalse(any('admissions' in code for code in user['after_permissions']))
        permissions.replace_user_permissions('tecnico',[],self.proxy)
        self.connection.commit()
        again=migration.migrate(self.connection,True,self.schema)
        self.assertEqual(again['status'],'already_applied')
        current=next(user for user in again['current'] if user['user_id']=='tecnico')
        self.assertEqual(current['custom_permissions'],[])

    def test_share_migration_preserves_grants_rolls_back_and_respects_revocation(self):
        self.migrate()
        with self.connection.cursor() as c:
            c.execute("INSERT INTO isrole VALUES ('patient','Patient')")
            c.execute("INSERT INTO tbuser(guid,username,idrole,isactive) VALUES ('patient','patient','patient',1)")
            c.execute("DELETE FROM ispermission WHERE code='worklist.share'")
        self.connection.commit()
        before = migration.snapshot(self.connection, self.schema)
        preview = share_migration.migrate(self.connection, False, self.schema)
        self.assertEqual(preview['status'], 'preview')
        self.assertEqual(migration.snapshot(self.connection, self.schema), before)
        share_migration.migrate(self.connection, True, self.schema)
        self.connection.rollback()
        self.assertEqual(migration.snapshot(self.connection, self.schema), before)
        share_migration.migrate(self.connection, True, self.schema)
        self.connection.commit()
        after = migration.snapshot(self.connection, self.schema)
        original = {u['user_id']: set(u['custom_permissions']) for u in before}
        for user in after:
            added = set() if user['role'] == 'Patient' else {'worklist.share'}
            self.assertEqual(set(user['custom_permissions']), original[user['user_id']] | added)
        permissions.replace_user_permissions('tecnico', [], self.proxy)
        self.connection.commit()
        rerun = share_migration.migrate(self.connection, True, self.schema)
        self.assertEqual(rerun['status'], 'already_applied')
        self.assertEqual(next(u for u in rerun['current'] if u['user_id'] == 'tecnico')['custom_permissions'], [])

    def test_migration_rolls_back_all_changes(self):
        before=migration.snapshot(self.connection,self.schema)
        migration.migrate(self.connection,True,self.schema)
        self.connection.rollback()
        self.assertEqual(migration.snapshot(self.connection,self.schema),before)
        with self.connection.cursor() as c:
            c.execute('SELECT to_regclass(%s)',(self.schema+'.permission_policy_migration',))
            self.assertIsNone(c.fetchone()[0])

    def test_empty_permissions_stay_empty_and_sysadmin_is_global(self):
        self.migrate()
        permissions.replace_user_permissions('medico',[],self.proxy)
        with patch.object(permissions,'get_db_config',return_value={'unused':True}), patch.object(permissions.psycopg2,'connect',return_value=self.proxy):
            self.assertEqual(permissions.get_user_permission_codes('medico',include_role_permissions=True),[])
            self.assertIn('*',permissions.get_user_permission_codes('sysadmin',include_role_permissions=False))
        self.assertEqual(self.proxy.commits,0,'shared helpers must not commit the caller transaction')

    def make_client(self, identity="sysadmin"):
        """Compile actual endpoint functions without importing application startup workers."""
        source=ast.parse((ROOT/'apps/api/config.py').read_text())
        selected={'create_config_user','update_config_user','get_roles'}
        endpoint_ast=ast.Module(body=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in selected],type_ignores=[])
        blueprint=Blueprint('permission_contract',__name__)
        scope=dict(api_blueprint=blueprint,request=request,jsonify=jsonify,uuid=uuid,
                   get_db_config=lambda:{'unused':True},psycopg2=psycopg2,
                   generate_temporary_password=lambda:'test-password-not-delivered',
                   send_new_user_credentials_email=lambda **kwargs:None)
        from flask_jwt_extended import jwt_required,get_jwt_identity
        scope.update(jwt_required=jwt_required,get_jwt_identity=get_jwt_identity)
        for name in ['require_permission','require_any_permission','user_has_permission_code',
                     'get_default_permissions_for_role','replace_user_permissions']:
            scope[name]=getattr(permissions,name)
        exec(compile(endpoint_ast,'actual_config_endpoints','exec'),scope)
        app=Flask(__name__,root_path=str(ROOT),instance_path=str(ROOT/"instance"));app.config.update(TESTING=True,JWT_SECRET_KEY='isolated-permissions-test-secret-32bytes')
        JWTManager(app);app.register_blueprint(blueprint)
        with app.app_context(): token=create_access_token(identity=identity,additional_claims={'user_type':'staff'})
        return app.test_client(),{'Authorization':'Bearer '+token}

    def test_account_and_permissions_are_atomic_and_role_change_uses_final_selection(self):
        self.migrate(); client,headers=self.make_client()
        with patch.object(permissions,'get_db_config',return_value={'unused':True}),patch.object(psycopg2,'connect',return_value=self.proxy):
            response=client.post('/config/users',headers=headers,json=dict(username='new-user',name='Test',surname='User',role_id='medico',permission_codes=['invalid']))
            self.assertEqual(response.status_code,400)
            with self.connection.cursor() as c:
                c.execute("SELECT count(*) FROM tbuser WHERE username='new-user'");self.assertEqual(c.fetchone()[0],0)
            self.assertEqual(self.proxy.commits,0)
            response=client.post('/config/users',headers=headers,json=dict(username='new-user',name='Test',surname='User',role_id='medico',permission_codes=[]))
            self.assertEqual(response.status_code,201,response.get_json())
            user_id=response.get_json()['data']['user_id'];self.assertEqual(self.proxy.commits,1)
            response=client.put('/config/users/'+user_id,headers=headers,json=dict(role_id='tecnico',permission_codes=['reports.write']))
            self.assertEqual(response.status_code,200,response.get_json())
            self.assertEqual(permissions.get_user_permission_codes(user_id),['reports.write'])
            response=client.put('/config/users/'+user_id,headers=headers,json=dict(role_id='medico',permission_codes=['bad']))
            self.assertEqual(response.status_code,400)
            with self.connection.cursor() as c:
                c.execute('SELECT idrole FROM tbuser WHERE guid=%s',(user_id,));self.assertEqual(c.fetchone()[0],'tecnico')
            response=client.put('/config/users/'+user_id,headers=headers,json=dict(name='Renamed'))
            self.assertEqual(response.status_code,200)
            self.assertEqual(permissions.get_user_permission_codes(user_id),['reports.write'])
            response=client.put('/config/users/'+user_id,headers=headers,json=dict(role_id='medico'))
            self.assertEqual(response.status_code,200)
            self.assertEqual(permissions.get_user_permission_codes(user_id),policy.get_default_permissions_for_role('medico'))
            response=client.get('/config/roles',headers=headers)
            self.assertEqual(response.status_code,200)
            self.assertTrue(all('default_permissions' in role for role in response.get_json()['data']))

    def test_clinical_adjustments_preserve_other_grants_and_do_not_reapply(self):
        self.migrate()
        before = migration.snapshot(self.connection,self.schema)
        preview = clinical_migration.migrate(self.connection,False,self.schema)
        self.assertEqual(preview['status'],'preview')
        self.assertEqual(migration.snapshot(self.connection,self.schema),before)
        clinical_migration.migrate(self.connection,True,self.schema)
        self.connection.rollback()
        self.assertEqual(migration.snapshot(self.connection,self.schema),before)
        clinical_migration.migrate(self.connection,True,self.schema)
        self.connection.commit()
        actual = {u['user_id']:set(u['custom_permissions']) for u in migration.snapshot(self.connection,self.schema)}
        original = {u['user_id']:set(u['custom_permissions']) for u in before}
        self.assertEqual(actual['medico'], (original['medico'] - {'tabs.gestion.view'}) | {'reports.unsign'})
        self.assertEqual(actual['tecnico'], original['tecnico'] | {'dicom.studies.manage'})
        self.assertEqual(actual['administrativo'],original['administrativo'])
        permissions.replace_user_permissions('medico',[],self.proxy)
        self.connection.commit()
        rerun = clinical_migration.migrate(self.connection,True,self.schema)
        self.assertEqual(rerun['status'],'already_applied')
        current = next(u for u in rerun['current'] if u['user_id']=='medico')
        self.assertEqual(current['custom_permissions'],[])

    def test_user_management_does_not_allow_role_or_permission_changes(self):
        self.migrate()
        permissions.replace_user_permissions('tecnico',['users.manage'],self.proxy)
        self.connection.commit()
        client,headers=self.make_client('tecnico')
        with patch.object(permissions,'get_db_config',return_value={'unused':True}),patch.object(psycopg2,'connect',return_value=self.proxy):
            response=client.put('/config/users/medico',headers=headers,json={'name':'Profile edit'})
            self.assertEqual(response.status_code,200)
            response=client.put('/config/users/medico',headers=headers,json={'role_id':'sysadmin'})
            self.assertEqual(response.status_code,403)
            response=client.put('/config/users/medico',headers=headers,json={'permission_codes':['users.permissions.manage']})
            self.assertEqual(response.status_code,403)
            response=client.post('/config/users',headers=headers,json={'username':'forbidden','name':'Test','surname':'User','role_id':'sysadmin'})
            self.assertEqual(response.status_code,403)



if __name__ == '__main__':
    unittest.main(verbosity=2)
