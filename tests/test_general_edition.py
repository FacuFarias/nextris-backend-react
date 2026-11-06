"""Integration checks. Requires a disposable dcm4chee PostgreSQL and explicit opt-in.

NEXTRIS_GENERAL_TESTS=1 DB_HOST=127.0.0.1 DB_PORT=55432 DB_NAME=nextris_test \
DB_USER=nextris_test DB_PASS=nextris_test python -m unittest discover -s tests -p test_general_edition.py
"""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ENABLED = os.getenv('NEXTRIS_GENERAL_TESTS') == '1'


@unittest.skipUnless(ENABLED, 'Explicit isolated database opt-in required')
class GeneralEditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('DB_NAME', '').endswith('_test'):
            raise RuntimeError('DB_NAME must end in _test; never point this suite at clinical data')
        os.environ['ANALYTICS_ENABLED'] = 'false'
        os.environ['ANALYTICS_GEO_LOOKUP'] = 'false'
        import psycopg2
        from apps.home.services.config_service import ConfigService
        cls.db = psycopg2.connect(**ConfigService.get_db_config())
        spec = importlib.util.spec_from_file_location('general_migration', ROOT / 'deployment/migrate_general.py')
        cls.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.migration)
        cls.migration.migrate(cls.db, initialize=True)
        from apps import create_app
        from apps.config import DebugConfig
        cls.app = create_app(DebugConfig)
        cls.app.config.update(TESTING=True, JWT_SECRET_KEY='test-only-key-for-isolated-general-edition')
        cls.client = cls.app.test_client()
        from apps.authentication.util import hash_pass
        cls.doctor, cls.patient, cls.portal, cls.other_portal, cls.exam, cls.draft, cls.location, cls.equipment = [str(uuid.uuid4()) for _ in range(8)]
        with cls.db.cursor() as cursor:
            cursor.execute("SELECT guid FROM nextris.isrole WHERE lower(description)='sysadmin' LIMIT 1")
            role = cursor.fetchone()[0]
            cursor.execute('INSERT INTO nextris.tbuser(guid,username,password,idrole,isactive,first_login,name,surname) VALUES(%s,%s,%s,%s,1,0,%s,%s)',
                (cls.doctor, 'general-test-' + cls.doctor, hash_pass('test-only-password'), role, 'Synthetic', 'Doctor'))
            cursor.execute("INSERT INTO nextris.tbuser_medical_data(user_id,aclaracion_firma,matricula_nacional,firma_habilitada) VALUES(%s,'Synthetic Doctor','TEST-123',true)", (cls.doctor,))
            cursor.execute("INSERT INTO nextris.datapatient(guid,patientid,name,surname) VALUES(%s,%s,'Synthetic','Patient')", (cls.patient,'TEST-'+cls.patient[:8]))
            for portal, patient in [(cls.portal, cls.patient),(cls.other_portal, cls.patient)]:
                cursor.execute("INSERT INTO nextris.tbuser_patient(guid,username,password,datapatient_id,firstlogin) VALUES(%s,%s,%s,%s,0)",
                    (portal, portal, hash_pass('test-only-password'), patient))
            cursor.execute("INSERT INTO nextris.tblocation(guid,name,code,require_execution_before_reporting) VALUES(%s,'Synthetic Institution','TEST',false)",(cls.location,))
            cursor.execute("INSERT INTO nextris.isequipment(guid,description,location_id) VALUES(%s,'Synthetic Equipment',%s)",(cls.equipment,cls.location))
            cursor.execute('INSERT INTO nextris.rel_user_location(user_id,location_id) VALUES(%s,%s)',(cls.doctor,cls.location))
            for exam, finalized in [(cls.exam,1),(cls.draft,0)]:
                cursor.execute("INSERT INTO nextris.tbexamination(guid,idpatient,location_id,idequipment,localacc,isreported,isexecuted,\"w-order\") VALUES(%s,%s,%s,%s,%s,%s,1,1)",
                    (exam,cls.patient,cls.location,cls.equipment,'TEST-'+exam,finalized))
                cursor.execute("INSERT INTO nextris.tbreport(guid,idexamination,idpatient,iduser,study_reason,content,conclusion,date) VALUES(%s,%s,%s,%s,'Synthetic reason','Synthetic findings','Synthetic conclusion',now())",(str(uuid.uuid4()),exam,cls.patient,cls.doctor))
        cls.db.commit()
        from flask_jwt_extended import create_access_token
        with cls.app.app_context():
            cls.staff_headers = {'Authorization':'Bearer '+create_access_token(identity=cls.doctor,additional_claims={'user_type':'Sysadmin'})}
            cls.patient_headers = {'Authorization':'Bearer '+create_access_token(identity=cls.portal,additional_claims={'user_type':'patient'})}
            cls.stranger_headers = {'Authorization':'Bearer '+create_access_token(identity=str(uuid.uuid4()),additional_claims={'user_type':'patient'})}
        cls.network_patch = patch('requests.sessions.Session.request', side_effect=AssertionError('Unexpected network request'))
        cls.network_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.network_patch.stop()
        cls.db.close()

    def get(self,path,headers=None):
        return self.client.get(path,headers=headers or self.staff_headers)

    def test_01_health_and_no_vendor_routes_or_schema(self):
        self.assertEqual(self.client.get('/api/health').status_code,200)
        paths = [str(rule) for rule in self.app.url_map.iter_rules()]
        self.assertFalse(any('clinicaparque' in path.lower() or 'infoparque' in path.lower() for path in paths))
        with self.db.cursor() as cursor:
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='nextris' AND (table_name ILIKE '%clinicaparque%' OR table_name ILIKE '%cp_other%')")
            self.assertEqual(cursor.fetchall(),[])
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='nextris' AND column_name ILIKE '%clinicaparque%'")
            self.assertEqual(cursor.fetchall(),[])

    def test_02_local_report_and_pdf(self):
        response=self.get('/api/reports/'+self.exam+'/view')
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(response.json['data']['source'],'nextris')
        self.assertIn('Synthetic findings',response.json['data']['report']['textos']['content']['contenido'])
        pdf=self.get('/api/reports/'+self.exam+'/pdf')
        self.assertEqual(pdf.status_code,200,pdf.get_json())
        self.assertEqual(pdf.mimetype,'application/pdf')
        self.assertTrue(pdf.data.startswith(b'%PDF-'))
        self.assertEqual(self.get('/api/reports/'+self.draft+'/view').status_code,404)
        self.assertEqual(self.client.get('/api/pdfs/by-exam/'+self.exam).status_code,401)

    def test_03_patient_ownership_and_visibility(self):
        path='/api/patient-portal/examinations/'+self.exam+'/report'
        self.assertEqual(self.get(path,self.patient_headers).status_code,200)
        self.assertEqual(self.get(path,self.stranger_headers).status_code,404)
        self.assertEqual(self.get('/api/reports/'+self.exam+'/view',self.stranger_headers).status_code,404)
        with self.db.cursor() as cursor:
            cursor.execute('UPDATE nextris.tbexamination SET hidden_in_portal=1 WHERE guid=%s',(self.exam,))
        self.db.commit()
        try:
            self.assertEqual(self.get(path,self.patient_headers).status_code,404)
        finally:
            with self.db.cursor() as cursor:
                cursor.execute('UPDATE nextris.tbexamination SET hidden_in_portal=0 WHERE guid=%s',(self.exam,))
            self.db.commit()

    def test_04_smoke_general_apis(self):
        for path in ['/api/app-config','/api/config/me/modules','/api/patients','/api/patients/'+self.patient+'/history/combined',
            '/api/examinations/for-reporting','/api/examinations/'+self.exam+'/report','/api/executions/orders',
            '/api/executions/examination/'+self.exam+'/details','/api/examinations/distribution','/api/tags']:
            with self.subTest(path=path):
                response=self.get(path)
                self.assertEqual(response.status_code,200,response.get_json())

    def test_05_sign_and_hl7(self):
        with patch('apps.api.integration.hl7_oru.send_report_hl7') as send:
            response=self.client.post('/api/reports/'+self.draft+'/sign',headers=self.staff_headers,json={})
        self.assertEqual(response.status_code,200,response.get_json())
        send.assert_called_once_with(self.draft)
        self.assertNotIn('report_send',response.json)
        self.assertEqual(self.get('/api/reports/'+self.draft+'/view').status_code,200)
        response=self.client.post('/api/reports/'+self.draft+'/unsign',headers=self.staff_headers,json={})
        self.assertEqual(response.status_code,200,response.get_json())

    def test_06_migration_refuses_multiple_institutions_without_mutation(self):
        with self.db.cursor() as cursor:
            cursor.execute('CREATE TABLE nextris.tbfacility(guid text,name text)')
            cursor.execute("INSERT INTO nextris.tbfacility VALUES('one','One'),('two','Two')")
        self.db.commit()
        try:
            with self.assertRaises(ValueError):
                self.migration.preflight(self.db)
        finally:
            self.db.rollback()
            with self.db.cursor() as cursor:
                cursor.execute('DROP TABLE nextris.tbfacility')
            self.db.commit()
        self.migration.migrate(self.db)

    def test_07_login_and_single_institution_configuration(self):
        response = self.client.post('/api/auth/login', json={'username':'general-test-'+self.doctor,'password':'test-only-password','user_type':'staff'})
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertIn('*',response.json['data']['user']['permissions'])
        self.assertEqual(self.get('/api/app-config/settings',self.patient_headers).status_code,403)
        response = self.client.put('/api/app-config',headers=self.staff_headers,json={'hl7_enable_orm':'invalid'})
        self.assertEqual(response.status_code,400,response.get_json())
        response = self.client.put('/api/app-config',headers=self.staff_headers,json={
            'name':'Synthetic Institution','smtp_port':None,'hl7_enable_orm':True,'hl7_enable_report_sending':True,
            'hl7_bearer_token_orm':'synthetic-machine-token','smtp_password':'synthetic-smtp-password'})
        self.assertEqual(response.status_code,200,response.get_json())
        public = self.client.get('/api/app-config').get_json()['data']
        self.assertNotIn('smtp_password',public)
        self.assertNotIn('hl7_bearer_token_orm',public)
        private = self.get('/api/app-config/settings').get_json()['data']
        self.assertNotIn('smtp_password',private)
        self.assertNotIn('hl7_bearer_token_orm',private)

    def test_08_orm_and_oru_use_local_institution(self):
        body = {'patient':{'id':'TEST-'+self.patient[:8],'name':'Patient, Synthetic'},
                'order':{'procedure_code':'GENERALTEST','accessionNumber':'TEST-'+self.exam[:8]},
                'location_name':'Synthetic Institution'}
        self.assertEqual(self.client.post('/api/integration/orders',json=body).status_code,401)
        with self.db.cursor() as cursor:
            cursor.execute("INSERT INTO nextris.isstudytype(guid,code,description) VALUES(%s,'GENERALTEST','Synthetic Procedure')",(str(uuid.uuid4()),))
        self.db.commit()
        response=self.client.post('/api/integration/orders',json=body,headers={'Authorization':'Bearer synthetic-machine-token'})
        self.assertEqual(response.status_code,201,response.get_json())
        self.assertEqual(response.json['data']['patient_id'],self.patient)
        with self.db.cursor() as cursor:
            cursor.execute('SELECT "w-order" FROM nextris.tbexamination WHERE guid=%s',(response.json['data']['examination_guid'],))
            self.assertEqual(cursor.fetchone()[0],1)
        self.db.rollback()
        from apps.api.integration.hl7_oru import send_report_hl7
        from apps.api.integration.hl7_execution import send_execution_hl7
        with patch('apps.home.services.HL7Service.send_report_oru',return_value=('synthetic-message',True)) as send:
            send_report_hl7(self.exam)
        self.assertEqual(send.call_args.kwargs['facility_name'],'Synthetic Institution')
        self.assertEqual(send.call_args.kwargs['report_data']['findings'],'Synthetic findings')
        with patch('apps.home.services.HL7Service.send_hl7_message',return_value=True) as send:
            send_execution_hl7(self.exam)
        self.assertIn('Synthetic Institution',send.call_args.args[0])
        self.assertEqual(send.call_args.kwargs['port'],9195)

    def test_09_cancellation_blocks_local_document_and_signing(self):
        response=self.client.post('/api/examinations/'+self.draft+'/cancel',headers=self.staff_headers,json={'reason_code':'PATIENT_ABSENT'})
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(self.get('/api/reports/'+self.draft+'/view').status_code,404)
        response=self.client.post('/api/reports/'+self.draft+'/sign',headers=self.staff_headers,json={})
        self.assertEqual(response.status_code,409,response.get_json())


    def test_10_permission_upgrade_preserves_aliases_and_respects_later_revocation(self):
        from apps.api.permissions import get_user_permission_codes
        spec=importlib.util.spec_from_file_location('permissions_upgrade',ROOT/'deployment/migrations/20261105_preserve_general_permissions.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        technician=str(uuid.uuid4())
        with self.db.cursor() as cursor:
            cursor.execute('DELETE FROM nextris.permission_policy_migration WHERE version=%s',(module.VERSION,))
            cursor.execute("SELECT guid FROM nextris.isrole WHERE lower(description)='tecnico' LIMIT 1")
            role=cursor.fetchone()[0]
            cursor.execute("INSERT INTO nextris.tbuser(guid,username,idrole,isactive) VALUES(%s,%s,%s,1)",(technician,technician,role))
            cursor.execute("INSERT INTO nextris.rel_user_permission(guid,user_id,permission_id,is_granted) SELECT %s,%s,guid,true FROM nextris.ispermission WHERE code='tabs.images.view'",(str(uuid.uuid4()),technician))
        module.migrate(self.db);self.db.commit()
        grants=get_user_permission_codes(technician)
        self.assertTrue({'patients.view','tabs.worklist.view','images.view'} <= set(grants))
        with self.db.cursor() as cursor:
            cursor.execute("UPDATE nextris.rel_user_permission SET is_granted=false WHERE user_id=%s AND permission_id=(SELECT guid FROM nextris.ispermission WHERE code='patients.view')",(technician,))
        self.db.commit()
        module.migrate(self.db);self.db.commit()
        self.assertNotIn('patients.view',get_user_permission_codes(technician))



if __name__=='__main__':
    unittest.main()
