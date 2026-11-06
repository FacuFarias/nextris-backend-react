"""Live HTTP integration tests. Only run against a disposable database ending in _test."""
import concurrent.futures
from datetime import date, timedelta
import importlib.util
import os
from pathlib import Path
import sys
import unittest
import uuid

import psycopg2
import requests
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'.env')
BASE=os.getenv('VETERINARY_TEST_URL','http://127.0.0.1:5003/api')


class VeterinaryApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('NEXTRIS_VETERINARY_TESTS')!='1' or not os.environ['DB_NAME'].endswith('_test'):
            raise unittest.SkipTest('Explicit disposable database opt-in required')
        cls.db=psycopg2.connect(host=os.environ['DB_HOST'],port=os.environ['DB_PORT'],dbname=os.environ['DB_NAME'],user=os.environ['DB_USER'],password=os.environ['DB_PASS'])
        cls.staff_id=str(uuid.uuid4());cls.username='vet-test-'+cls.staff_id;cls.password=uuid.uuid4().hex
        cls.study_type=str(uuid.uuid4())
        with cls.db.cursor() as q:
            q.execute("SELECT guid FROM nextris.isrole WHERE lower(description)='sysadmin' LIMIT 1");role=q.fetchone()[0]
            q.execute("INSERT INTO nextris.tbuser(guid,username,password,idrole,isactive,first_login,name,surname) VALUES(%s,%s,%s,%s,1,0,'Synthetic','Veterinarian')",(cls.staff_id,cls.username,generate_password_hash(cls.password),role))
            q.execute("INSERT INTO nextris.tbuser_medical_data(user_id,aclaracion_firma,matricula_nacional,firma_habilitada) VALUES(%s,'Synthetic Veterinarian','TEST-VET',true)",(cls.staff_id,))
            q.execute("INSERT INTO nextris.isstudytype(guid,description,code) VALUES(%s,'Synthetic veterinary imaging',%s)",(cls.study_type,cls.study_type[:8]))
        cls.db.commit()
        r=requests.post(BASE+'/auth/login',json={'username':cls.username,'password':cls.password,'user_type':'staff'},timeout=20)
        assert r.status_code==200,r.text
        cls.headers={'Authorization':'Bearer '+r.json()['data']['access_token']}
        cls.species=cls.call('GET','/veterinary/species').json()['data'];cls.dog=next(x['id'] for x in cls.species if x['name']=='Canino');cls.cat=next(x['id'] for x in cls.species if x['name']=='Felino')

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    @classmethod
    def call(cls,method,path,data=None,headers=None):
        return requests.request(method,BASE+path,json=data,headers=headers if headers is not None else cls.headers,timeout=25)

    def new_animal(self,**overrides):
        payload={'name':'Synthetic animal','gender':'O','veterinary':{'species_id':self.dog},**overrides}
        r=self.call('POST','/patients',payload);self.assertEqual(r.status_code,201,r.text);return r.json()['data']

    def test_01_identity_validation_and_concurrency(self):
        a=self.new_animal();self.assertTrue(a['patientid'].startswith('VT'));self.assertIsNone(a['birthdate']);self.assertFalse(a['veterinary']['birthdate_estimated'])
        self.assertEqual(self.call('PUT','/patients/'+a['guid'],{'patientid':'OTHER'}).status_code,400)
        for extra in [{'birthdate':(date.today()+timedelta(days=1)).isoformat()},{'veterinary':{'weight_kg':-1}},{'veterinary':{'weight_kg':'NaN'}},{'veterinary':{'weight_kg':True}},{'veterinary':{'birthdate_estimated':True}}]:
            self.assertEqual(self.call('POST','/patients',{'name':'Invalid',**extra}).status_code,400)
        breed=self.call('POST','/veterinary/breeds',{'species_id':self.cat,'name':'Synthetic breed '+uuid.uuid4().hex}).json()['data']['id']
        self.assertEqual(self.call('POST','/patients',{'name':'Wrong breed','veterinary':{'species_id':self.dog,'breed_id':breed}}).status_code,400)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            animals=list(pool.map(lambda _:self.new_animal(),range(8)))
        self.assertEqual(len({x['patientid'] for x in animals}),8)
        quick=self.call('POST','/patients/quick',{'nombre':'Synthetic quick','sexo':'F'});self.assertEqual(quick.status_code,201,quick.text)

    def test_02_responsibles_portal_and_revocation(self):
        a=self.new_animal();b=self.new_animal()
        party=self.call('POST','/veterinary/responsibles',{'name':'Synthetic Responsible','kind':'person','email':'synthetic@example.invalid'}).json()['data']
        relations=[]
        for patient in [a,b]:
            r=self.call('POST','/veterinary/patients/'+patient['guid']+'/responsibles',{'responsible_id':party['id'],'role':'owner','is_primary':True,'portal_authorized':True});self.assertEqual(r.status_code,201,r.text);relations.append(r.json()['data'])
        username='responsible-'+uuid.uuid4().hex
        r=self.call('POST','/veterinary/responsibles/'+party['id']+'/account',{'username':username});self.assertEqual(r.status_code,201,r.text);credential=r.json()['data']
        r=self.call('POST','/auth/login',{'username':username,'password':credential['initial_password'],'user_type':'patient'},headers={});self.assertEqual(r.status_code,200,r.text);session=r.json()['data'];owner={'Authorization':'Bearer '+session['access_token']}
        self.assertEqual(session['user']['portal_subject'],'responsible')
        self.assertEqual(self.call('GET','/veterinary/portal/animals',headers=owner).status_code,403)
        r=self.call('POST','/auth/change-password',{'new_password':uuid.uuid4().hex},headers=owner);self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(len(self.call('GET','/veterinary/portal/animals',headers=owner).json()['data']),2)
        for path in ['/patients','/veterinary/responsibles','/general/viewer-url-by-iuid','/viewer/session/refresh']:
            self.assertEqual(self.call('GET' if path in ['/patients','/veterinary/responsibles'] else 'POST',path,{},headers=owner).status_code,403,path)
        self.assertEqual(self.call('GET','/veterinary/portal/animals/'+str(uuid.uuid4())+'/studies',headers=owner).status_code,404)
        r=self.call('POST','/veterinary/patients/'+a['guid']+'/orders',{'study_type_id':self.study_type});self.assertEqual(r.status_code,201,r.text);exam=r.json()['data']['guid']
        report={'study_reason':'Synthetic reason','content':'Synthetic veterinary findings','conclusion':'Synthetic conclusion'}
        r=self.call('PUT','/examinations/'+exam+'/report',report);self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.call('GET','/veterinary/portal/reports/'+exam,headers=owner).status_code,404)
        r=self.call('POST','/reports/'+exam+'/sign',{});self.assertEqual(r.status_code,200,r.text)
        r=self.call('GET','/veterinary/portal/reports/'+exam,headers=owner);self.assertEqual(r.status_code,200,r.text)
        # A bearer link issued to a responsible must also recheck the live relationship.
        import hashlib
        code=uuid.uuid4().hex[:12];share=str(uuid.uuid4())
        with self.db.cursor() as q:
            q.execute('SELECT studyinstanceuid FROM nextris.tbexamination WHERE guid=%s',(exam,));uid=q.fetchone()[0]
            q.execute("INSERT INTO nextris.tbviewer_share_link(guid,token_hash,short_code,study_iuid,created_by_user_id,expires_at,share_type,portal_account_id,patient_id) VALUES(%s,%s,%s,%s,%s,now()+interval '15 minutes','case_link',%s,%s)",(share,hashlib.sha256(uuid.uuid4().bytes).hexdigest(),code,uid,session['user']['id'],session['user']['id'],a['guid']))
        self.db.commit()
        self.assertEqual(self.call('GET','/s/'+code+'/report',headers={}).status_code,200)
        for pdf_path,pdf_headers in [('/s/'+code+'/report.pdf',{}),('/reports/'+exam+'/pdf',None)]:
            document=self.call('GET',pdf_path,headers=pdf_headers);self.assertEqual(document.status_code,200,document.text[:200]);self.assertTrue(document.content.startswith(b'%PDF-'))
        self.assertEqual(self.call('GET','/s/'+uuid.uuid4().hex[:12]+'/report.pdf',headers={}).status_code,404)
        card=self.call('GET','/s/'+code+'/case',headers={});self.assertEqual(card.status_code,200,card.text)
        self.assertEqual(card.json()['data']['responsibles'],[{'name':'Synthetic Responsible','role':'owner','phone':None,'email':'synthetic@example.invalid'}])
        pdf=self.call('GET','/veterinary/portal/reports/'+exam+'/pdf',headers=owner);self.assertEqual(pdf.status_code,200,pdf.text[:200]);self.assertTrue(pdf.content.startswith(b'%PDF-'))
        r=self.call('PUT','/patients/'+a['guid'],{'name':'Changed synthetic name'});self.assertEqual(r.status_code,200,r.text)
        r=self.call('GET','/veterinary/portal/reports/'+exam,headers=owner);self.assertEqual(r.json()['data']['document']['patient']['name'],'Synthetic animal')
        self.assertEqual(self.call('POST','/veterinary/relationships/'+relations[0]['id']+'/end',{}).status_code,200)
        self.assertEqual(self.call('GET','/veterinary/portal/reports/'+exam,headers=owner).status_code,404)
        with self.db.cursor() as q:q.execute('UPDATE nextris.tbviewer_share_link SET revoked=false WHERE guid=%s',(share,))
        self.db.commit()
        self.assertEqual(self.call('GET','/s/'+code+'/report',headers={}).status_code,404)
        self.assertEqual(len(self.call('GET','/veterinary/portal/animals',headers=owner).json()['data']),1)
        refresh={'Authorization':'Bearer '+session['refresh_token']};r=self.call('POST','/auth/refresh',{},headers=refresh);self.assertEqual(r.status_code,200,r.text)
        import jwt
        self.assertEqual(jwt.decode(session['access_token'],options={'verify_signature':False})['auth_session_id'],jwt.decode(r.json()['data']['access_token'],options={'verify_signature':False})['auth_session_id'])
        fresh={'Authorization':'Bearer '+r.json()['data']['access_token']};self.assertEqual(self.call('GET','/veterinary/portal/reports/'+exam,headers=fresh).status_code,404)
        other=self.call('POST','/veterinary/responsibles',{'name':'Synthetic New Responsible','kind':'person','email':'new@example.invalid'}).json()['data']
        r=self.call('POST','/veterinary/patients/'+a['guid']+'/responsibles',{'responsible_id':other['id'],'role':'owner','portal_authorized':True});self.assertEqual(r.status_code,201,r.text)
        new_name='responsible-'+uuid.uuid4().hex
        credentials=self.call('POST','/veterinary/responsibles/'+other['id']+'/account',{'username':new_name}).json()['data']
        session2=self.call('POST','/auth/login',{'username':new_name,'password':credentials['initial_password'],'user_type':'patient'},headers={}).json()['data']
        new_owner={'Authorization':'Bearer '+session2['access_token']}
        self.assertEqual(self.call('POST','/auth/change-password',{'new_password':uuid.uuid4().hex},headers=new_owner).status_code,200)
        self.assertEqual(self.call('GET','/veterinary/portal/reports/'+exam,headers=new_owner).status_code,200)
        account=self.call('GET','/veterinary/responsibles/'+other['id']+'/accounts').json()['data'][0]
        reset=self.call('POST','/veterinary/responsibles/'+other['id']+'/accounts/'+account['guid']+'/reset-password',{})
        self.assertEqual(reset.status_code,200,reset.text)
        self.assertEqual(self.call('GET','/veterinary/portal/animals',headers=new_owner).status_code,401)
        # No identity or examination is reassigned by a transfer.
        self.assertEqual(self.call('GET','/patients/'+a['guid']).json()['data']['patientid'],a['patientid'])

    def test_03_protocol_history_agenda_templates_and_snapshot(self):
        a=self.new_animal(veterinary={'species_id':self.dog,'weight_kg':12.5,'birthdate_estimated':True},birthdate='2020-01-01')
        p=self.call('POST','/veterinary/protocols',{'name':'Synthetic protocol','species_id':self.dog,'study_type_id':self.study_type,'min_weight_kg':10,'max_weight_kg':15,'preparation':'Synthetic preparation','checklist':['Synthetic step']});self.assertEqual(p.status_code,201,p.text);protocol=p.json()['data']
        order={'study_type_id':self.study_type,'protocol_id':protocol['id'],'scheduled_start':'2030-01-01T10:00','scheduled_end':'2030-01-01T10:30'}
        r=self.call('POST','/veterinary/patients/'+a['guid']+'/orders',order);self.assertEqual(r.status_code,201,r.text);exam=r.json()['data']['guid']
        self.assertEqual(r.json()['data']['veterinary_context']['weight_kg'],12.5)
        self.call('POST','/veterinary/patients/'+a['guid']+'/history',{'category':'weight','weight_kg':22})
        self.assertEqual(self.call('POST','/veterinary/patients/'+a['guid']+'/orders',order).status_code,400)
        with self.db.cursor() as q:
            q.execute('SELECT veterinary_context FROM nextris.tbexamination WHERE guid=%s',(exam,));self.assertEqual(q.fetchone()[0]['weight_kg'],12.5)
            q.execute('SELECT count(*) FROM nextris.tbagendaevents WHERE idexam=%s',(exam,));self.assertEqual(q.fetchone()[0],1)
        self.db.rollback()
        template={'title':'Synthetic veterinary template','species_id':self.dog,'study_type_id':self.study_type,'study_reason':'Synthetic reason','content':'Synthetic template findings','conclusion':'Synthetic conclusion'}
        r=self.call('POST','/veterinary/templates',template);self.assertEqual(r.status_code,201,r.text)
        r=self.call('GET','/examinations/'+exam+'/report');self.assertEqual(r.status_code,200,r.text);self.assertFalse(r.json()['data']['structured_reports_enabled']);self.assertEqual(r.json()['data']['sr_variables'],[])
        compatible=self.call('POST','/veterinary/templates',template).json()['data']['guid']
        self.assertEqual(self.call('PUT','/examinations/'+exam+'/report',{'template_id':compatible}).status_code,200)
        incompatible=self.call('POST','/veterinary/templates',{**template,'species_id':self.cat}).json()['data']['guid']
        self.assertEqual(self.call('PUT','/examinations/'+exam+'/report',{'template_id':incompatible}).status_code,400)
        self.assertTrue(self.call('GET','/veterinary/patients/'+a['guid']+'/history').json()['data'])

    def test_04_serialization_manual_validation_and_disabled_mwl(self):
        from apps.services.veterinary_integration import veterinary_dataset,send_veterinary_worklist,read_veterinary_metadata,prepare_manual_upload
        from apps.services.veterinary import VeterinaryError
        import io
        import pydicom
        from pydicom.dataset import FileDataset,FileMetaDataset
        from pydicom.uid import generate_uid,ExplicitVRLittleEndian
        context={'patientid':'VTTEST','name':'Synthetic Animal','species_name':'Canino','reproductive_status':'neutered','weight_kg':2.5,'responsibles':[{'name':'Synthetic Owner','kind':'person','role':'owner','is_primary':True}]}
        ds=veterinary_dataset(context,accession='VTTEST',study_uid=generate_uid());self.assertEqual(str(ds.PatientName),'Synthetic Animal');self.assertEqual(str(ds.ResponsiblePerson),'Synthetic Owner');self.assertEqual(str(ds.PatientSexNeutered),'ALTERED')
        self.assertEqual(read_veterinary_metadata(ds)['species'],'Canino')
        with self.assertRaises(VeterinaryError):send_veterinary_worklist(ds,session=None,base_url='',aet='',access_token='')
        a=self.new_animal(veterinary={'species_id':self.dog});r=self.call('POST','/veterinary/patients/'+a['guid']+'/orders',{'study_type_id':self.study_type});exam=r.json()['data']['guid']
        metadata=FileMetaDataset();metadata.TransferSyntaxUID=ExplicitVRLittleEndian;metadata.MediaStorageSOPClassUID=pydicom.uid.SecondaryCaptureImageStorage;metadata.MediaStorageSOPInstanceUID=generate_uid()
        ds=FileDataset(None,{},file_meta=metadata,preamble=b'\0'*128);ds.is_little_endian=True;ds.is_implicit_VR=False;ds.SOPClassUID=metadata.MediaStorageSOPClassUID;ds.SOPInstanceUID=metadata.MediaStorageSOPInstanceUID;ds.StudyInstanceUID=generate_uid();ds.SeriesInstanceUID=generate_uid();ds.PatientID='WRONG';ds.PatientName='Synthetic original'
        ds.PatientWeight='7.75';ds.PatientSexNeutered='UNALTERED'
        stream=io.BytesIO();ds.save_as(stream,write_like_original=False);stream.seek(0)
        from werkzeug.datastructures import FileStorage
        file=FileStorage(stream=stream,filename='synthetic.dcm')
        with self.assertRaises(VeterinaryError):prepare_manual_upload(file,a['guid'],exam,False,self.staff_id)
        prepare_manual_upload(file,a['guid'],exam,True,self.staff_id);updated=pydicom.dcmread(file.stream)
        self.assertEqual(str(updated.PatientID),a['patientid']);self.assertEqual(str(updated.PatientName),a['name']);self.assertEqual(len(updated.OriginalAttributesSequence),1)
        self.assertEqual(float(updated.PatientWeight),7.75);self.assertEqual(str(updated.PatientSexNeutered),'UNALTERED')

    def test_08_worklist_responsible_search_filter_and_revocation(self):
        prefix='Worklist-'+uuid.uuid4().hex[:10]
        a=self.new_animal(name=prefix+' Animal A');b=self.new_animal(name=prefix+' Animal B')
        owners=[]
        for patient,suffix in [(a,'Alpha'),(b,'Beta')]:
            party=self.call('POST','/veterinary/responsibles',{'name':prefix+' '+suffix,'kind':'person'}).json()['data']
            rel=self.call('POST','/veterinary/patients/'+patient['guid']+'/responsibles',{'responsible_id':party['id'],'role':'owner','is_primary':True}).json()['data']
            order=self.call('POST','/veterinary/patients/'+patient['guid']+'/orders',{'study_type_id':self.study_type})
            self.assertEqual(order.status_code,201,order.text);owners.append((party,rel,order.json()['data']['guid']))
        path='/examinations/for-reporting?show_ready=true&show_no_image=true&show_without_order=true&search='+prefix
        r=self.call('GET',path+'&per_page=1&sort_column=responsible_name&sort_direction=asc');self.assertEqual(r.status_code,200,r.text)
        data=r.json()['data'];self.assertEqual(data['total'],2);self.assertEqual(data['data'][0]['responsible_name'],owners[0][0]['name'])
        import json
        r=self.call('GET',path+'&column_filters='+requests.utils.quote(json.dumps({'responsible_query':'Beta'})))
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['data']['total'],1);self.assertEqual(r.json()['data']['data'][0]['guid'],owners[1][2])
        r=self.call('GET','/examinations/for-reporting?show_ready=true&show_no_image=true&show_without_order=true&search='+requests.utils.quote(owners[0][0]['name']))
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['data']['total'],1)
        self.assertEqual(self.call('POST','/veterinary/relationships/'+owners[0][1]['id']+'/end',{}).status_code,200)
        r=self.call('GET',path+'&column_filters='+requests.utils.quote(json.dumps({'responsible_name':'Alpha'})))
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['data']['total'],0)

    def test_07_patient_and_responsible_directory_filters(self):
        prefix='Directory-'+uuid.uuid4().hex[:10]
        dog=self.new_animal(name=prefix+' Alpha',veterinary={'species_id':self.dog})
        cat=self.new_animal(name=prefix+' Beta',veterinary={'species_id':self.cat})
        owner=self.call('POST','/veterinary/responsibles',{'name':prefix+' Owner','kind':'person','email':prefix.lower()+'@example.invalid'}).json()['data']
        self.assertEqual(self.call('POST','/veterinary/patients/'+dog['guid']+'/responsibles',{'responsible_id':owner['id'],'role':'owner'}).status_code,201)
        result=self.call('GET','/patients?search='+prefix+'&per_page=1&sort_column=name&sort_direction=desc').json()['data']
        self.assertEqual(result['total'],2);self.assertEqual(result['data'][0]['guid'],cat['guid'])
        page2=self.call('GET','/patients?search='+prefix+'&per_page=1&page=2&sort_column=name&sort_direction=desc').json()['data']
        self.assertEqual(page2['data'][0]['guid'],dog['guid'])
        for query,expected in [('species_id='+self.dog,dog),('responsible_status=pending',cat),('responsible_status=linked',dog),('filter_name=Beta',cat),('filter_responsible_names=Owner',dog)]:
            result=self.call('GET','/patients?search='+prefix+'&'+query).json()['data']
            self.assertEqual(result['total'],1);self.assertEqual(result['data'][0]['guid'],expected['guid'])
        result=self.call('GET','/veterinary/responsibles?paginated=true&search='+prefix.lower()+'@example.invalid&kind=person&is_active=true').json()['data']
        self.assertEqual(result['total'],1);self.assertEqual(result['data'][0]['id'],owner['id'])
        self.assertIsInstance(self.call('GET','/veterinary/responsibles?search='+prefix).json()['data'],list)
        self.assertEqual(self.call('GET','/patients?page=invalid').status_code,400)

    def test_06_saved_permissions_are_required(self):
        key=str(uuid.uuid4());username='vet-readonly-'+key;password=uuid.uuid4().hex
        with self.db.cursor() as q:
            q.execute("SELECT guid FROM nextris.isrole WHERE lower(description)<>'sysadmin' LIMIT 1");role=q.fetchone()[0]
            q.execute("INSERT INTO nextris.tbuser(guid,username,password,idrole,isactive,first_login) VALUES(%s,%s,%s,%s,1,0)",(key,username,generate_password_hash(password),role))
            q.execute("INSERT INTO nextris.rel_user_permission(guid,user_id,permission_id,is_granted) SELECT %s,%s,guid,true FROM nextris.ispermission WHERE code='patients.view'",(str(uuid.uuid4()),key))
        self.db.commit()
        response=self.call('POST','/auth/login',{'username':username,'password':password,'user_type':'staff'},headers={});self.assertEqual(response.status_code,200,response.text)
        headers={'Authorization':'Bearer '+response.json()['data']['access_token']}
        self.assertEqual(self.call('GET','/patients',headers=headers).status_code,200)
        for path,data in [('/patients',{'name':'Forbidden'}),('/veterinary/species',{'name':'Forbidden'}),('/veterinary/protocols',{'name':'Forbidden'}),('/veterinary/templates',{'title':'Forbidden'}),('/predefined-reports',{'title':'Forbidden','study_type_id':self.study_type})]:
            self.assertEqual(self.call('POST',path,data,headers=headers).status_code,403,path)

    def test_05_guarded_downgrade_and_no_disabled_modules(self):
        spec=importlib.util.spec_from_file_location('vet_migration',ROOT/'deployment/migrate_veterinary.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.new_animal()
        with self.assertRaises(psycopg2.Error):module.migrate(self.db,down=True)
        self.db.rollback()
        with self.db.cursor() as q:
            q.execute("SELECT 1 FROM nextris.veterinary_schema_migration WHERE version=%s",(module.VERSION,));self.assertTrue(q.fetchone())
        self.db.rollback()
        for path in ['/nexi/directives','/structured-reports/parsers']:
            self.assertEqual(self.call('GET',path).status_code,404)


if __name__=='__main__':unittest.main(verbosity=2)
