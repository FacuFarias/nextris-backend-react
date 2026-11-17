"""Real HTTP veterinary registration/assignment tests on a disposable DB copy.

Requires DB_NAME=cdivet_vetimages_*_test and the veterinary API on localhost:5003.
Never contacts the archive API or changes production/PACS records.
"""
import os
import uuid
from datetime import timedelta

import psycopg2
import requests
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token


def run():
    assert os.environ['DB_NAME'].startswith('cdivet_vetimages_') and os.environ['DB_NAME'].endswith('_test')
    connection = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ.get('DB_PORT','5432'),
        dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'], password=os.environ['DB_PASS'])
    connection.autocommit = True
    cursor = connection.cursor()
    cursor.execute("SELECT guid FROM nextris.tbuser WHERE username='admin'")
    actor = str(cursor.fetchone()[0])
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY') or os.environ['SECRET_KEY']
    JWTManager(app)
    def headers(identity=actor):
        with app.app_context():
            token = create_access_token(identity=identity, expires_delta=timedelta(minutes=15), additional_claims={'user_type':'staff'})
        return {'Authorization':'Bearer '+token}
    auth = headers()
    base = 'http://127.0.0.1:5003/api'
    checks = 0
    def call(method, path, data=None, expected=200, credentials=None):
        nonlocal checks
        response = requests.request(method,base+path,json=data,headers=credentials or auth,timeout=30)
        assert response.status_code == expected, (path,response.status_code,response.text[:300])
        checks += 1
        return response.json().get('data')
    def pacs_snapshot():
        result = {}
        for table in ['patient','person_name','dicomattrs','study','series','instance','location','rejected_instance']:
            cursor.execute(f"SELECT count(*),md5(COALESCE(string_agg(row_to_json(t)::text,'' ORDER BY pk),'')) FROM public.{table} t")
            result[table] = cursor.fetchone()
        return result
    def scalar(sql, values=None):
        cursor.execute(sql,values)
        return cursor.fetchone()[0]
    def clear_assignments(uid):
        cursor.execute("UPDATE nextris.tbpacs_study_link SET link_status='unlinked' WHERE pacs_study_iuid=%s",(uid,))
        cursor.execute('UPDATE nextris.tbmanual_uploads SET islinked=0 WHERE study_instance_uid=%s',(uid,))
        cursor.execute('UPDATE nextris.tbexamination SET studyinstanceuid=%s WHERE studyinstanceuid=%s',('2.25.'+str(uuid.uuid4().int),uid))
    try:
        snapshot = pacs_snapshot()
        cursor.execute('SELECT pk,study_iuid FROM nextris.available_pacs_study ORDER BY pk LIMIT 2')
        studies = cursor.fetchall()
        assert len(studies)==2
        (study_pk,uid),(other_pk,other_uid) = studies
        for _,study_uid in studies: clear_assignments(study_uid)
        history_count = scalar("SELECT count(*) FROM nextris.tbpacs_study_link WHERE pacs_study_iuid=%s AND link_status='unlinked'",(uid,))
        marker = uuid.uuid4().hex[:10]
        owner = call('POST','/veterinary/responsibles',{'kind':'person','name':'Synthetic Owner '+marker,'document':'DOC-'+marker,'email':marker+'@example.invalid'},201)
        first = call('POST','/patients',{'patient_kind':'animal','name':'Synthetic Pet '+marker,'gender':'F','responsible_id':owner['id']},201)
        second = call('POST','/patients',{'name':'Second Pet '+marker,'gender':'M'},201)
        assert first['patientid'].startswith('VT') and first['surname']=='' and first['nationalcode'] is None
        assert first['responsibles'][0]['id']==owner['id'] and second['responsibles']==[]
        relation = call('GET','/veterinary/patients/'+first['guid']+'/responsibles')[0]
        assert relation['is_primary'] and not relation['portal_authorized']
        for query in [owner['name'],owner['document']]:
            result = call('GET','/patients?paginated=true&search='+requests.utils.quote(query))
            assert first['guid'] in {animal['guid'] for animal in result['data']}
        count = scalar('SELECT count(*) FROM nextris.datapatient')
        call('POST','/patients',{'name':'Must roll back','responsible_id':str(uuid.uuid4())},404)
        assert scalar('SELECT count(*) FROM nextris.datapatient')==count
        inactive = call('POST','/veterinary/responsibles',{'kind':'person','name':'Inactive '+marker},201)
        call('PUT','/veterinary/responsibles/'+inactive['id'],{'name':inactive['name'],'kind':'person','is_active':False})
        call('POST','/patients',{'name':'Must roll back','responsible_id':inactive['id']},404)
        assert scalar('SELECT count(*) FROM nextris.datapatient')==count
        limited = str(uuid.uuid4())
        role = scalar("SELECT guid FROM nextris.isrole WHERE lower(description)<>'sysadmin' LIMIT 1")
        cursor.execute('INSERT INTO nextris.tbuser(guid,username,password,idrole,isactive,first_login) VALUES(%s,%s,%s,%s,1,0)',
                       (limited,'synthetic-limited-'+marker,uuid.uuid4().hex,role))
        permission = scalar("SELECT guid FROM nextris.ispermission WHERE code='patients.manage'")
        cursor.execute('INSERT INTO nextris.rel_user_permission(guid,user_id,permission_id,is_granted) VALUES(%s,%s,%s,true)',
                       (str(uuid.uuid4()),limited,permission))
        call('POST','/patients',{'name':'Unauthorized owner link','responsible_id':owner['id']},403,headers(limited))
        assert scalar('SELECT count(*) FROM nextris.datapatient')==count
        human = str(uuid.uuid4())
        cursor.execute("INSERT INTO nextris.datapatient(guid,patientid,name,surname,patient_kind) VALUES(%s,%s,'Human fixture','Synthetic','human')",(human,'H'+marker))
        payload = {'study_pk':study_pk,'animal_guid':first['guid'],'confirm_identity':True}
        call('POST','/dicom/studies/reassign',{**payload,'confirm_identity':False},409)
        call('POST','/dicom/studies/reassign',{**payload,'animal_guid':human},404)
        call('POST','/dicom/studies/reassign',{**payload,'modify_dicom':True},400)
        call('POST','/dicom/studies/reassign',{**payload,'new_patient':{'nombre':'Human','apellido':'Wrong'}},400)
        call('POST','/dicom/studies/reassign',payload,403,headers(limited))
        assigned = call('POST','/dicom/studies/reassign',payload)
        exam = assigned['examination_guid']
        assert call('POST','/dicom/studies/reassign',payload)['examination_guid']==exam
        assert scalar('SELECT count(*) FROM nextris.tbexamination WHERE studyinstanceuid=%s',(uid,))==1
        assert scalar('SELECT count(*) FROM nextris.tbreport WHERE idexamination=%s',(exam,))==1
        context = scalar('SELECT veterinary_context FROM nextris.tbexamination WHERE guid=%s',(exam,))
        assert context['name']==first['name'] and context['responsibles'][0]['id']==owner['id']
        assert not any(s['pk']==study_pk for s in call('GET','/dicom/studies-by-location/all?unlinked_only=true')['data'])
        def move(animal):
            return call('POST','/dicom/studies/reassign',{**payload,'animal_guid':animal['guid']})
        assert move(second)['examination_guid']==exam
        assert scalar('SELECT idpatient FROM nextris.tbreport WHERE idexamination=%s',(exam,))==second['guid']
        assert scalar("SELECT count(*) FROM nextris.tbpacs_study_link WHERE pacs_study_iuid=%s AND link_status='unlinked'",(uid,))==history_count+1
        # Direct, active-link and manual-upload associations all resolve to the same order.
        cursor.execute("UPDATE nextris.tbpacs_study_link SET link_status='unlinked' WHERE pacs_study_iuid=%s",(uid,))
        assert move(first)['examination_guid']==exam
        cursor.execute('UPDATE nextris.tbexamination SET studyinstanceuid=%s WHERE guid=%s',('2.25.'+str(uuid.uuid4().int),exam))
        assert move(second)['examination_guid']==exam
        cursor.execute("UPDATE nextris.tbpacs_study_link SET link_status='unlinked' WHERE pacs_study_iuid=%s",(uid,))
        cursor.execute('UPDATE nextris.tbexamination SET studyinstanceuid=%s WHERE guid=%s',('2.25.'+str(uuid.uuid4().int),exam))
        cursor.execute("INSERT INTO nextris.tbmanual_uploads(guid,filename,filepath,study_instance_uid,series_instance_uid,sop_instance_uid,linked_examination_guid,islinked,pacs_status) VALUES(%s,'synthetic.dcm','/synthetic/no-file',%s,'2.25.1','2.25.2',%s,1,'success')",(str(uuid.uuid4()),uid,exam))
        assert move(first)['examination_guid']==exam
        cursor.execute('UPDATE nextris.tbexamination SET isreported=1 WHERE guid=%s',(exam,))
        call('POST','/dicom/studies/reassign',{**payload,'animal_guid':second['guid']},409)
        cursor.execute('UPDATE nextris.tbexamination SET isreported=0 WHERE guid=%s',(exam,))
        cursor.execute('UPDATE nextris.tbreport SET wassaved=true WHERE idexamination=%s',(exam,))
        call('POST','/dicom/studies/reassign',{**payload,'animal_guid':second['guid']},409)
        assert scalar('SELECT idpatient FROM nextris.tbexamination WHERE guid=%s',(exam,))==first['guid']
        cursor.execute('UPDATE nextris.tbreport SET wassaved=false WHERE idexamination=%s',(exam,))
        cursor.execute('UPDATE nextris.tbexamination SET studyinstanceuid=%s WHERE guid=%s',(other_uid,exam))
        call('POST','/dicom/studies/reassign',{**payload,'animal_guid':second['guid']},409)
        assert pacs_snapshot()==snapshot,'PACS index, identity, metadata or storage rows were modified'
        # Leave PACS studies unlinked for browser tests in this disposable database.
        for _,study_uid in studies: clear_assignments(study_uid)
        print(f'PASS: {checks} live HTTP checks: veterinary identity, atomic owner registration, owner search, permissions, assignment, idempotency, all association types, saved/signed report guards and unchanged PACS data.')
    finally:
        connection.close()


if __name__=='__main__': run()
