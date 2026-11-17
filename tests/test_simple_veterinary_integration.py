"""Real DB/HTTP integration, exclusively on cdivet_simple_*_test clones; no mocks."""
import concurrent.futures
import io
import json
import os
from pathlib import Path
import sys
import uuid
from datetime import timedelta

import psycopg2
from psycopg2.extras import Json
import pydicom
from pydicom.filebase import DicomBytesIO
from pydicom.filewriter import write_dataset
import requests
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.services.veterinary_ingest import process_study, run_once, candidates, record_failure


def run():
    db = os.environ['DB_NAME']
    assert db.startswith('cdivet_simple_') and db.endswith('_test')
    assert os.environ['NEXTRIS_WORKFLOW_PROFILE'] == 'simple_veterinary'
    c = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ.get('DB_PORT','5432'),
        dbname=db,user=os.environ['DB_USER'],password=os.environ['DB_PASS'])
    c.autocommit = True
    q = c.cursor()
    q.execute("SELECT guid FROM nextris.tbuser WHERE username='admin'"); actor = str(q.fetchone()[0])
    app = Flask(__name__); app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY') or os.environ['SECRET_KEY']; JWTManager(app)
    with app.app_context():
        token = create_access_token(identity=actor, expires_delta=timedelta(minutes=30), additional_claims={'user_type':'staff'})
    headers = {'Authorization':'Bearer '+token}
    base = 'http://127.0.0.1:5003/api'
    checks = 0
    marker = uuid.uuid4().hex[:9]
    def call(method,path,payload=None,expected=200):
        nonlocal checks
        r = requests.request(method,base+path,headers=headers,json=payload,timeout=60)
        assert r.status_code == expected,(path,r.status_code,r.text[:300])
        checks += 1
        return r.json().get('data')
    def scalar(sql,args=None):
        q.execute(sql,args);return q.fetchone()[0]
    def snapshot():
        result = {}
        for table in ['patient','person_name','dicomattrs','study','series','instance','location','rejected_instance']:
            q.execute(f"SELECT count(*),md5(COALESCE(string_agg(row_to_json(t)::text,'' ORDER BY pk),'')) FROM public.{table} t")
            result[table] = q.fetchone()
        return result
    def clone(table,pk,overrides):
        key = scalar('SELECT COALESCE(max(pk),0)+1 FROM public.'+table)
        q.execute('INSERT INTO public.'+table+' SELECT (jsonb_populate_record(NULL::public.'+table+',to_jsonb(t)||%s::jsonb)).* FROM public.'+table+' t WHERE pk=%s RETURNING pk', (Json({**overrides,'pk':key}),pk))
        return q.fetchone()[0]
    def attrs(pk,values):
        q.execute('SELECT attrs FROM public.dicomattrs WHERE pk=%s',(pk,)); ds=pydicom.dcmread(io.BytesIO(bytes(q.fetchone()[0])),force=True)
        ds.SpecificCharacterSet='ISO_IR 192'
        for key,value in values.items():setattr(ds,key,value)
        buf=DicomBytesIO();buf.is_implicit_VR=False;buf.is_little_endian=True;write_dataset(buf,ds)
        key=clone('dicomattrs',pk,{})
        q.execute('UPDATE public.dicomattrs SET attrs=%s WHERE pk=%s',(buf.getvalue(),key));return key
    q.execute('''SELECT s.pk,s.patient_fk,p.pat_name_fk,p.dicomattrs_fk,s.dicomattrs_fk,sr.pk,sr.dicomattrs_fk,i.pk,i.dicomattrs_fk
        FROM nextris.available_pacs_study s JOIN public.patient p ON p.pk=s.patient_fk
        JOIN nextris.available_pacs_series sr ON sr.study_fk=s.pk
        JOIN nextris.available_pacs_instance i ON i.series_fk=sr.pk WHERE s.study_iuid NOT LIKE '2.25.%' ORDER BY s.pk DESC,sr.pk,i.pk LIMIT 1''')
    sp,pp,pn,pa,sa,srp,sra,ip,ia=q.fetchone()
    lp=scalar('SELECT pk FROM public.location WHERE instance_fk=%s LIMIT 1',(ip,))
    created=[]
    def study(name='LÚNA QA',patient_id=None,issuer='QA-CENTER',with_image=True):
        patient_id = patient_id if patient_id is not None else 'QA-'+marker
        uid='2.25.'+str(uuid.uuid4().int);suid='2.25.'+str(uuid.uuid4().int);iuid='2.25.'+str(uuid.uuid4().int)
        patientattrs=attrs(pa,{'PatientName':name,'PatientID':patient_id,'IssuerOfPatientID':issuer,'PatientBirthDate':'20200102','PatientSex':'F'})
        person=clone('person_name',pn,{'alphabetic_name':name})
        patient=clone('patient',pp,{'dicomattrs_fk':patientattrs,'pat_name_fk':person})
        studyattrs=attrs(sa,{'StudyInstanceUID':uid,'StudyDescription':'QA DICOM '+marker,'StudyDate':'20251004','StudyTime':'123456','PatientWeight':'8.5'})
        accession='QA-'+uuid.uuid4().hex[:12]
        pk=clone('study',sp,{'study_iuid':uid,'accession_no':accession,'study_desc':'QA DICOM '+marker,
                             'study_date':'20251004','study_time':'123456','dicomattrs_fk':studyattrs,'patient_fk':patient})
        sr=instance=None
        if with_image:
            sr=clone('series',srp,{'study_fk':pk,'series_iuid':suid,'dicomattrs_fk':attrs(sra,{'SeriesInstanceUID':suid})})
            instance=clone('instance',ip,{'series_fk':sr,'sop_iuid':iuid,'dicomattrs_fk':attrs(ia,{'SOPInstanceUID':iuid})})
            if lp:clone('location',lp,{'instance_fk':instance})
        item={'pk':pk,'uid':uid,'series':sr,'instance':instance,'accession':accession,'attrs':patientattrs}
        created.append(item);return item
    def counts():return tuple(scalar('SELECT count(*) FROM nextris.'+table) for table in ['datapatient','tbexamination','tbreport','pacs_animal_identity','patient_clinical_entry'])
    try:
        before=snapshot();run_once();assert snapshot()==before;assert run_once()['processed']==0
        a=study();before=snapshot();first=process_study(a['pk']);assert snapshot()==before
        assert scalar('SELECT weight_kg FROM nextris.patient_clinical_entry WHERE patient_id=%s ORDER BY created_at DESC LIMIT 1',(first['animal_guid'],)) is not None
        assert process_study(a['pk'])['examination_guid']==first['examination_guid']
        b=study();second=process_study(b['pk']);assert second['animal_guid']==first['animal_guid']
        different_id=process_study(study(patient_id='QA-OTHER-'+marker)['pk']);assert different_id['animal_guid']!=first['animal_guid']
        different_name=process_study(study(name='Otra mascota QA')['pk']);assert different_name['animal_guid']!=first['animal_guid']
        different_issuer=process_study(study(issuer='QA-OTHER-CENTER')['pk']);assert different_issuer['animal_guid']!=first['animal_guid']
        legacy_id=str(uuid.uuid4());legacy_patient_id='QA-LEGACY-'+marker
        q.execute("INSERT INTO nextris.datapatient(guid,patientid,name,surname,sexcode,patient_kind) VALUES(%s,%s,'Legacy QA','','O','animal')",(legacy_id,legacy_patient_id))
        legacy=process_study(study(name='Legacy QA',patient_id=legacy_patient_id,issuer='QA-LEGACY-A')['pk'])
        assert legacy['animal_guid']==legacy_id
        other_issuer=process_study(study(name='Legacy QA',patient_id=legacy_patient_id,issuer='QA-LEGACY-B')['pk'])
        assert other_issuer['animal_guid']!=legacy_id
        missing=study(patient_id='');m=process_study(missing['pk']);assert m['provisional']
        upgraded=attrs(missing['attrs'],{'PatientID':'QA-UPGRADE-'+marker})
        q.execute('UPDATE public.patient SET dicomattrs_fk=%s WHERE pk=(SELECT patient_fk FROM public.study WHERE pk=%s)',(upgraded,missing['pk']))
        upgrade=process_study(missing['pk']);assert upgrade['animal_guid']==m['animal_guid'] and not upgrade['provisional']
        original_key=scalar('SELECT identity_key FROM nextris.pacs_auto_order WHERE study_iuid=%s',(missing['uid'],))
        changed_again=attrs(upgraded,{'PatientName':'Changed after provisional QA'})
        q.execute('UPDATE public.patient SET dicomattrs_fk=%s WHERE pk=(SELECT patient_fk FROM public.study WHERE pk=%s)',(changed_again,missing['pk']))
        process_study(missing['pk'])
        assert scalar('SELECT identity_key FROM nextris.pacs_auto_order WHERE study_iuid=%s',(missing['uid'],))==original_key
        no_name=study(name='',patient_id='');assert process_study(no_name['pk'])['provisional']
        empty=study(with_image=False);assert process_study(empty['pk']) is None
        rejected=study()
        clone('rejected_instance',scalar('SELECT pk FROM public.rejected_instance LIMIT 1'),{
            'study_iuid':rejected['uid'],
            'series_iuid':scalar('SELECT series_iuid FROM public.series WHERE pk=%s',(rejected['series'],)),
            'sop_iuid':scalar('SELECT sop_iuid FROM public.instance WHERE pk=%s',(rejected['instance'],))})
        assert process_study(rejected['pk']) is None
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            concurrent_results=list(pool.map(process_study,[b['pk']]*4))
        assert len({x['examination_guid'] for x in concurrent_results})==1
        race1=study(patient_id='QA-RACE-'+marker);race2=study(patient_id='QA-RACE-'+marker)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            raced=list(pool.map(process_study,[race1['pk'],race2['pk'],race1['pk'],race2['pk']]))
        assert len({x['animal_guid'] for x in raced})==1 and len({x['examination_guid'] for x in raced})==2
        extra_uid='2.25.'+str(uuid.uuid4().int)
        extra=clone('instance',ip,{'series_fk':a['series'],'sop_iuid':extra_uid,'dicomattrs_fk':attrs(ia,{'SOPInstanceUID':extra_uid})})
        if lp:clone('location',lp,{'instance_fk':extra})
        process_study(a['pk']);assert scalar('SELECT instance_count FROM nextris.pacs_auto_order WHERE study_iuid=%s',(a['uid'],))==2
        assert scalar('SELECT count(*) FROM nextris.tbexamination WHERE studyinstanceuid=%s',(a['uid'],))==1
        drift_old=study(name='Original drift QA',patient_id='QA-DRIFT-'+marker)
        drift_animal=process_study(drift_old['pk'])
        drift_new=study(name='New drift QA',patient_id='QA-DRIFT-'+marker)
        shared_patient=scalar('SELECT patient_fk FROM public.study WHERE pk=%s',(drift_old['pk'],))
        updated_attrs=attrs(drift_old['attrs'],{'PatientName':'New drift QA'})
        q.execute('UPDATE public.patient SET dicomattrs_fk=%s WHERE pk=%s',(updated_attrs,shared_patient))
        q.execute('UPDATE public.study SET patient_fk=%s WHERE pk=%s',(shared_patient,drift_new['pk']))
        process_study(drift_old['pk'])
        new_drift=process_study(drift_new['pk'])
        assert new_drift['animal_guid']!=drift_animal['animal_guid']
        assert scalar('SELECT name FROM nextris.datapatient WHERE guid=%s',(drift_animal['animal_guid'],))=='Original drift QA'
        # Human-cleared fields must stay cleared even before a report/confirmation is saved.
        untouched=study(patient_id='QA-CLEARED-'+marker);clear_animal=process_study(untouched['pk'])
        q.execute("UPDATE nextris.datapatient SET birthdate=NULL,sexcode='O' WHERE guid=%s",(clear_animal['animal_guid'],))
        process_study(untouched['pk'])
        assert scalar("SELECT birthdate IS NULL AND sexcode='O' FROM nextris.datapatient WHERE guid=%s",(clear_animal['animal_guid'],))
        # A real database failure halfway through creation must roll back animal, order and identity.
        failing=study(patient_id='QA-FAIL-'+marker);before_counts=counts()
        q.execute('ALTER TABLE nextris.tbexamination ADD CONSTRAINT qa_auto_ingest_failure CHECK(localacc<>%s) NOT VALID',(failing['accession'],))
        try:
            try:process_study(failing['pk']);raise AssertionError('Expected database constraint failure')
            except psycopg2.errors.CheckViolation as error:record_failure(failing['pk'],error)
            assert counts()==before_counts;assert failing['pk'] not in candidates()
        finally:q.execute('ALTER TABLE nextris.tbexamination DROP CONSTRAINT qa_auto_ingest_failure')
        q.execute('UPDATE nextris.pacs_auto_order SET retry_at=now() WHERE pacs_study_pk=%s',(failing['pk'],))
        assert run_once()['failed']==0
        config=call('GET','/app-config');assert config['workflow_profile']=='simple_veterinary'
        listing=call('GET','/examinations/for-reporting?show_ready=true&show_without_order=false&per_page=100')
        row=next(row for row in listing['data'] if row['guid']==first['examination_guid'])
        assert not row['is_executed'] and row['w_order']==0 and row['study_type']=='QA DICOM '+marker and row['applied_template_id']
        if row['modality_id']:
            filtered=call('GET','/examinations/for-reporting?show_ready=true&modality_id='+row['modality_id']+'&per_page=100')
            assert any(x['guid']==row['guid'] for x in filtered['data'])
        editor=call('GET','/examinations/'+row['guid']+'/report');assert editor['applied_template_id'] and editor['study_type_description']=='QA DICOM '+marker
        report={'study_reason':'<p>QA indication</p>','content':'<p>QA findings</p>','conclusion':'<p>QA conclusion</p>'}
        call('PUT','/examinations/'+row['guid']+'/report',report)
        call('POST','/reports/'+row['guid']+'/sign',{})
        assert scalar('SELECT isreported=1 AND isexecuted=0 FROM nextris.tbexamination WHERE guid=%s',(row['guid'],))
        saved=scalar('SELECT row_to_json(r)::text FROM nextris.tbreport r WHERE idexamination=%s',(row['guid'],))
        process_study(a['pk']);assert scalar('SELECT row_to_json(r)::text FROM nextris.tbreport r WHERE idexamination=%s',(row['guid'],))==saved
        # Confirm another unsigned study and preserve all clinical edits on subsequent ingestion.
        studytype=scalar('SELECT guid FROM nextris.isstudytype ORDER BY description LIMIT 1')
        call('POST','/examinations/'+second['examination_guid']+'/confirm-study',{'studytype_id':studytype,'clinical_question':'QA manual review'})
        process_study(b['pk']);assert scalar('SELECT isexecuted=1 AND clinicalquestion=%s FROM nextris.tbexamination WHERE guid=%s',('QA manual review',second['examination_guid']))
        # Explicit animal correction is never reversed by the worker.
        manual=study(patient_id='QA-MANUAL-'+marker);original=process_study(manual['pk'])
        call('POST','/dicom/studies/reassign',{'study_pk':manual['pk'],'animal_guid':different_name['animal_guid'],'confirm_identity':True})
        before=snapshot();after=process_study(manual['pk']);assert after['animal_guid']==different_name['animal_guid'] and snapshot()==before
        print(f'PASS: {checks} HTTP checks plus real PACS-clone ingestion: identity pairs/issuer, incomplete data, rejection/empty study, concurrency, extra instances, rollback/retry, worklist/type/modality/template, unconfirmed save/sign, explicit confirmation, manual corrections and unchanged PACS.')
    finally:
        c.close()


if __name__=='__main__':run()
