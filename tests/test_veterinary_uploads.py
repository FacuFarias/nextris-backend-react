"""Live integration tests for persistent uploads on a disposable *_test database.

The API runs on VETERINARY_TEST_URL; the worker step runs in-process against FakePacs, so faults can be
injected and nothing ever reaches a real PACS. Requires NEXTRIS_VETERINARY_TESTS=1.
"""
import concurrent.futures
import io
import os
from pathlib import Path
import sys
import unittest
from unittest import mock
import uuid
import zipfile

import numpy
import psycopg2
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
import requests
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'.env')
BASE=os.getenv('VETERINARY_TEST_URL','http://127.0.0.1:5003/api')
CT='1.2.840.10008.5.1.4.1.1.2'


def dicom_bytes(study,series=None,sop=None,*,patient='DICOM-ID',name='Scanner^Name',seed=1,preamble=True):
    meta=FileMetaDataset();sop=sop or generate_uid()
    meta.MediaStorageSOPClassUID=CT;meta.MediaStorageSOPInstanceUID=sop;meta.TransferSyntaxUID=ExplicitVRLittleEndian
    ds=FileDataset('x',{},file_meta=meta,preamble=b'\0'*128 if preamble else None)
    ds.is_little_endian=True;ds.is_implicit_VR=False
    ds.SOPClassUID=CT;ds.SOPInstanceUID=sop;ds.StudyInstanceUID=study;ds.SeriesInstanceUID=series or generate_uid()
    ds.PatientID=patient;ds.PatientName=name;ds.AccessionNumber='SCAN1';ds.Modality='CT';ds.StudyDescription='Synthetic thorax'
    ds.StudyDate='20261106';ds.StudyTime='120000';ds.SeriesNumber=1;ds.InstanceNumber=1
    ds.Rows=4;ds.Columns=4;ds.BitsAllocated=8;ds.BitsStored=8;ds.HighBit=7;ds.PixelRepresentation=0
    ds.SamplesPerPixel=1;ds.PhotometricInterpretation='MONOCHROME2'
    ds.PixelData=numpy.full((4,4),seed,dtype=numpy.uint8).tobytes()
    stream=io.BytesIO();ds.save_as(stream,write_like_original=True);return stream.getvalue()


def archive(members):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for name,data in members.items():z.writestr(name,data)
    return stream.getvalue()


def insert_row(cursor, table, values):
    """Minimal row for a dcm4chee table: NOT NULL columns not provided get a neutral value of their type."""
    cursor.execute("""SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=%s
        AND is_nullable='NO' AND column_default IS NULL""",(table,))
    neutral={'bigint':0,'integer':0,'smallint':0,'boolean':False,'bytea':b''}
    row={'pk':uuid.uuid4().int>>66}
    for column,kind in cursor.fetchall():
        row.setdefault(column,('2026-01-01' if kind.startswith('timestamp') else neutral.get(kind,'*')))
    row.update(values)
    cursor.execute(f"INSERT INTO public.{table}({','.join(row)}) VALUES({','.join(['%s']*len(row))}) RETURNING pk",list(row.values()))
    return cursor.fetchone()[0]


class FakePacs:
    """In-memory DICOMweb stand-in that also mirrors what dcm4chee indexes in the shared database."""
    studies={}
    db=None

    def instances(self,study):
        return [{'00080018':{'Value':[sop]},'00100020':{'Value':[pydicom.dcmread(io.BytesIO(raw),stop_before_pixels=True).get('PatientID','')]}}
                for sop,raw in self.studies.get(study,{}).items()]

    def retrieve(self,study,_series,sop):
        return self.studies[study][sop]

    def frame_available(self,study,_series,sop):
        return sop in self.studies.get(study,{})

    def store(self,path):
        raw=Path(path).read_bytes();ds=pydicom.dcmread(io.BytesIO(raw),stop_before_pixels=True)
        study=str(ds.StudyInstanceUID);series=str(ds.SeriesInstanceUID);sop=str(ds.SOPInstanceUID)
        with self.db.cursor() as q:
            q.execute('SELECT pk FROM public.study WHERE study_iuid=%s',(study,));row=q.fetchone()
            study_pk=row[0] if row else None
            if not study_pk:
                patient=insert_row(q,'patient',{'dicomattrs_fk':insert_row(q,'dicomattrs',{})})
                study_pk=insert_row(q,'study',{'study_iuid':study,'patient_fk':patient,'dicomattrs_fk':insert_row(q,'dicomattrs',{})})
            q.execute('SELECT pk FROM public.series WHERE series_iuid=%s AND study_fk=%s',(series,study_pk));row=q.fetchone()
            series_pk=row[0] if row else insert_row(q,'series',{'series_iuid':series,'study_fk':study_pk,'dicomattrs_fk':insert_row(q,'dicomattrs',{})})
            insert_row(q,'instance',{'sop_iuid':sop,'sop_cuid':str(ds.SOPClassUID),'series_fk':series_pk,'dicomattrs_fk':insert_row(q,'dicomattrs',{})})
        self.studies.setdefault(study,{})[sop]=raw


class VeterinaryUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('NEXTRIS_VETERINARY_TESTS')!='1' or not os.environ['DB_NAME'].endswith('_test'):
            raise unittest.SkipTest('Explicit disposable database opt-in required')
        cls.db=psycopg2.connect(host=os.environ['DB_HOST'],port=os.environ['DB_PORT'],dbname=os.environ['DB_NAME'],user=os.environ['DB_USER'],password=os.environ['DB_PASS'])
        cls.db.autocommit=True
        FakePacs.db=cls.db
        patcher=mock.patch('apps.services.pacs_client.PacsClient',FakePacs);patcher.start();cls.addClassCleanup(patcher.stop)
        cls.staff_id=str(uuid.uuid4());cls.study_type=str(uuid.uuid4());cls.password=uuid.uuid4().hex;cls.username='upload-'+cls.staff_id
        cls.limited_id=str(uuid.uuid4());limited_name='upload-limited-'+cls.limited_id
        with cls.db.cursor() as q:
            q.execute("SELECT guid FROM nextris.isrole WHERE lower(description)='sysadmin' LIMIT 1");role=q.fetchone()[0]
            for key,name in [(cls.staff_id,cls.username),(cls.limited_id,limited_name)]:
                q.execute("INSERT INTO nextris.tbuser(guid,username,password,idrole,isactive,first_login,name,surname) VALUES(%s,%s,%s,%s,1,0,'Synthetic','Staff')",(key,name,generate_password_hash(cls.password),role if key==cls.staff_id else None))
            q.execute("INSERT INTO nextris.isstudytype(guid,description,code) VALUES(%s,'Synthetic thorax',%s)",(cls.study_type,cls.study_type[:8]))
        cls.headers=cls.login(cls.username)
        cls.limited=cls.login(limited_name)
        cls.dog=next(x['id'] for x in requests.get(BASE+'/veterinary/species',headers=cls.headers,timeout=20).json()['data'] if x['name']=='Canino')

    @classmethod
    def login(cls,username):
        r=requests.post(BASE+'/auth/login',json={'username':username,'password':cls.password,'user_type':'staff'},timeout=20)
        assert r.status_code==200,r.text
        return {'Authorization':'Bearer '+r.json()['data']['access_token']}

    def call(self,method,path,data=None,headers=None):
        return requests.request(method,BASE+path,json=data,headers=self.headers if headers is None else headers,timeout=30)

    def setUp(self):
        from apps.services import veterinary_uploads as uploads
        self.uploads=uploads

    def drain(self):
        while self.uploads.process_one():pass

    def animal(self,name='Synthetic animal'):
        r=self.call('POST','/patients',{'name':name,'gender':'O','veterinary':{'species_id':self.dog}});self.assertEqual(r.status_code,201,r.text);return r.json()['data']

    def send(self,files):
        session=self.call('POST','/veterinary/uploads',{}).json()['data'];key=session['id']
        for name,data in files.items():
            created=self.call('POST',f'/veterinary/uploads/{key}/files',{'name':name,'size':len(data)});self.assertIn(created.status_code,(200,201),created.text)
            fid=created.json()['data']['id'];step=session['limits']['chunk_bytes']
            for offset in range(0,len(data),step):
                r=requests.put(BASE+f'/veterinary/uploads/{key}/files/{fid}',params={'offset':offset},data=data[offset:offset+step],headers=self.headers,timeout=30);self.assertEqual(r.status_code,200,r.text)
        r=self.call('POST',f'/veterinary/uploads/{key}/analyze',{});self.assertEqual(r.status_code,202,r.text)
        self.drain()
        return self.detail(key)

    def detail(self,key):
        r=self.call('GET','/veterinary/uploads/'+key);self.assertEqual(r.status_code,200,r.text);return r.json()['data']

    def create_target(self,patient,**extra):
        return {'mode':'create','patient_id':patient['guid'],'study_type_id':self.study_type,'confirm_identity':True,**extra}

    def finalize(self,key,target):
        r=self.call('POST',f'/veterinary/uploads/{key}/finalize',target);self.assertEqual(r.status_code,202,r.text);return r

    def exams(self,patient):
        with self.db.cursor() as q:
            q.execute('SELECT guid,localacc,studyinstanceuid,isimage FROM nextris.tbexamination WHERE idpatient=%s',(patient['guid'],));return q.fetchall()

    def test_01_folder_multiple_series_ignored_and_duplicates(self):
        study=generate_uid();series=generate_uid();sop=generate_uid();same=dicom_bytes(study,series,sop)
        dicomdir=FileDataset('d',{},file_meta=FileMetaDataset(),preamble=b'\0'*128)
        dicomdir.file_meta.MediaStorageSOPClassUID='1.2.840.10008.1.3.10';dicomdir.file_meta.MediaStorageSOPInstanceUID=generate_uid();dicomdir.file_meta.TransferSyntaxUID=ExplicitVRLittleEndian
        dicomdir.is_little_endian=True;dicomdir.is_implicit_VR=False;dicomdir.FileSetID='X';buffer=io.BytesIO();dicomdir.save_as(buffer,write_like_original=True)
        result=self.send({'carpeta/a/IM0001':same,'carpeta/copia/IM0001.dcm':same,'carpeta/b/sub/IM0002':dicom_bytes(study,seed=2),
                          'carpeta/notas.pdf':b'%PDF not dicom','carpeta/DICOMDIR':buffer.getvalue()})
        self.assertEqual(result['state'],'ready',result['error']);summary=result['summary']
        self.assertEqual((summary['series_count'],summary['instance_count'],summary['duplicate_count'],summary['ignored_count']),(2,2,1,2))
        self.assertEqual({item['reason'] for item in summary['ignored']},{'Archivo no DICOM','Índice DICOMDIR'})
        self.assertFalse(result['transfer_started'])

    def test_02_rejections_happen_before_pacs(self):
        with mock.patch('apps.services.pacs_client.PacsClient') as pacs:
            mixed=self.send({'a':dicom_bytes(generate_uid()),'b':dicom_bytes(generate_uid())})
            self.assertEqual(mixed['state'],'rejected');self.assertIn('varios estudios',mixed['error'])
            study=generate_uid();sop=generate_uid()
            collision=self.send({'a':dicom_bytes(study,sop=sop,seed=1),'b':dicom_bytes(study,sop=sop,seed=2)})
            self.assertEqual(collision['state'],'rejected');self.assertIn('SOP Instance UID',collision['error'])
            nested=self.send({'x.zip':archive({'inner.zip':archive({'a':b'1'})})});self.assertEqual(nested['state'],'rejected');self.assertIn('anidados',nested['error'])
            unsafe=self.send({'x.zip':archive({'../../fuera.dcm':dicom_bytes(generate_uid())})});self.assertEqual(unsafe['state'],'rejected');self.assertIn('insegura',unsafe['error'])
            nothing=self.send({'nota.txt':b'hola'});self.assertEqual(nothing['state'],'rejected')
            pacs.assert_not_called()
        self.assertEqual(self.call('POST','/veterinary/uploads/'+nested['id']+'/preview',{}).status_code,409)

    def test_03_generate_report_zip_end_to_end_single_order(self):
        animal=self.animal();study=generate_uid();series=generate_uid()
        result=self.send({'estudio.zip':archive({'S1/IM1':dicom_bytes(study,series,seed=1),'S1/IM2':dicom_bytes(study,series,seed=2),'S2/IM1':dicom_bytes(study,seed=3,preamble=False)})})
        self.assertEqual(result['state'],'ready',result['error']);key=result['id'];self.assertEqual(result['summary']['instance_count'],3)
        unconfirmed=self.call('POST',f'/veterinary/uploads/{key}/finalize',self.create_target(animal,confirm_identity=False));self.assertEqual(unconfirmed.status_code,409);self.assertIn('Confirme',unconfirmed.json()['message'])
        preview=self.call('POST',f'/veterinary/uploads/{key}/preview',self.create_target(animal,confirm_identity=False));self.assertEqual(preview.status_code,200,preview.text)
        self.assertEqual({d['field'] for d in preview.json()['data']['differences']},{'Animal ID','Nombre','Acceso'})
        self.assertEqual(self.exams(animal),[])
        target=self.create_target(animal,clinical_question='Tos')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            codes=[r.status_code for r in pool.map(lambda _:self.call('POST',f'/veterinary/uploads/{key}/finalize',target),range(4))]
        self.assertEqual(set(codes),{202},codes)
        self.drain();done=self.detail(key);self.assertEqual(done['state'],'completed',done['error']);self.assertEqual(done['sent'],3);self.assertEqual(done['verified'],3)
        exams=self.exams(animal);self.assertEqual(len(exams),1);exam=exams[0];self.assertEqual((exam[0],exam[2],exam[3]),(done['result']['exam_id'],study,1))
        self.assertEqual(preview.json()['data']['accession'],done['result']['accession'])
        self.assertEqual(self.call('POST',f'/veterinary/uploads/{key}/finalize',target).status_code,200)
        with self.db.cursor() as q:
            q.execute("SELECT count(*) FROM nextris.tbreport WHERE idexamination=%s",(exam[0],));self.assertEqual(q.fetchone()[0],1)
            q.execute("SELECT count(*) FROM nextris.tbpacs_study_link WHERE order_guid=%s AND link_status='linked'",(exam[0],));self.assertEqual(q.fetchone()[0],1)
            q.execute("SELECT count(*) FROM nextris.tbmanual_uploads WHERE linked_examination_guid=%s AND linked_at IS NOT NULL",(exam[0],));self.assertEqual(q.fetchone()[0],3)
        # What the PACS stored carries RIS identity; the received original on disk is untouched.
        from apps.services.pacs_client import PacsClient
        stored=PacsClient().instances(study);self.assertEqual(len(stored),3);self.assertEqual({r['00100020']['Value'][0] for r in stored},{animal['patientid']})
        originals=sorted(self.uploads.root().joinpath(key).glob('*.original'))
        self.assertTrue(any(pydicom.dcmread(p,force=True).get('PatientID')=='DICOM-ID' for p in originals if not zipfile.is_zipfile(p)))
        # The report editor and viewer resolve this exam.
        self.assertEqual(self.call('POST',f'/examinations/{exam[0]}/block',{}).status_code,200)
        viewer=self.call('POST','/general/viewer-url',{'user_id':self.staff_id,'examination_id':exam[0]});self.assertEqual(viewer.status_code,200,viewer.text);self.assertEqual(viewer.json()['data']['study_uid'],study)
        # A second upload of the same study cannot reach another animal.
        other=self.animal();again=self.send({'a':dicom_bytes(study)})
        self.assertEqual(self.call('POST',f"/veterinary/uploads/{again['id']}/preview",self.create_target(other)).status_code,409)

    def test_04_link_existing_order_rules(self):
        animal=self.animal();other=self.animal()
        order=self.call('POST',f"/veterinary/patients/{animal['guid']}/orders",{'study_type_id':self.study_type});self.assertEqual(order.status_code,201,order.text);exam=order.json()['data']
        study=generate_uid();result=self.send({'a':dicom_bytes(study)});key=result['id']
        link={'mode':'link','patient_id':other['guid'],'exam_id':exam['guid'],'confirm_identity':True}
        self.assertEqual(self.call('POST',f'/veterinary/uploads/{key}/finalize',link).status_code,409)
        link['patient_id']=animal['guid'];self.finalize(key,link);self.drain()
        done=self.detail(key);self.assertEqual(done['state'],'completed',done['error']);self.assertEqual(done['result']['exam_id'],exam['guid'])
        exams=self.exams(animal);self.assertEqual(len(exams),1);self.assertEqual(exams[0][2],study)
        stored=done['result']['accession'];self.assertEqual(stored,exam['accession_number'])
        busy=self.send({'a':dicom_bytes(generate_uid())})
        self.assertEqual(self.call('POST',f"/veterinary/uploads/{busy['id']}/finalize",{**link}).status_code,409)
        with self.db.cursor() as q:
            order2=self.call('POST',f"/veterinary/patients/{animal['guid']}/orders",{'study_type_id':self.study_type}).json()['data']
            q.execute("UPDATE nextris.tbexamination SET isreported=1 WHERE guid=%s",(order2['guid'],))
        self.assertEqual(self.call('POST',f"/veterinary/uploads/{busy['id']}/preview",{**link,'exam_id':order2['guid']}).status_code,409)

    def test_05_partial_pacs_failure_resumes_without_duplicates(self):
        from apps.services.pacs_client import PacsClient
        animal=self.animal();study=generate_uid();series=generate_uid()
        result=self.send({str(n):dicom_bytes(study,series,seed=n) for n in range(4)});key=result['id'];target=self.create_target(animal)
        self.finalize(key,target);real=PacsClient.store;calls=[]
        def flaky(client,path):
            calls.append(path)
            if len(calls)==3:raise requests.ConnectionError('pacs-internal-host down')
            return real(client,path)
        with mock.patch.object(PacsClient,'store',flaky):self.drain()
        failed=self.detail(key);self.assertEqual(failed['state'],'retryable');self.assertEqual(failed['sent'],2);self.assertTrue(failed['transfer_started'])
        self.assertNotIn('pacs-internal-host',failed['error']);self.assertEqual(self.exams(animal),[])
        self.assertEqual(self.call('POST',f'/veterinary/uploads/{key}/cancel',{}).status_code,409)
        changed=self.call('POST',f'/veterinary/uploads/{key}/finalize',{**target,'patient_id':self.animal()['guid']});self.assertEqual(changed.status_code,409)
        calls.clear();self.finalize(key,target)
        with mock.patch.object(PacsClient,'store',lambda client,path:(calls.append(path),real(client,path))[1]):self.drain()
        done=self.detail(key);self.assertEqual(done['state'],'completed',done['error']);self.assertEqual(len(calls),2,'only missing instances are resent')
        self.assertEqual(len(PacsClient().instances(study)),4);self.assertEqual(len(self.exams(animal)),1)

    def test_06_interrupted_worker_recovers_and_content_collision_blocks(self):
        from apps.services.pacs_client import PacsClient
        animal=self.animal();study=generate_uid();series=generate_uid();sop=generate_uid()
        result=self.send({'a':dicom_bytes(study,series,sop,seed=7)});key=result['id'];target=self.create_target(animal)
        self.finalize(key,target)
        with self.db.cursor() as q:q.execute("UPDATE nextris.veterinary_upload_session SET state='transferring' WHERE id=%s",(key,))
        self.drain();self.assertEqual(self.detail(key)['state'],'completed')
        # Same SOP UID, different pixels and a new study reservation on another session.
        with self.db.cursor() as q:
            q.execute("UPDATE nextris.tbexamination SET studyinstanceuid=%s WHERE studyinstanceuid=%s",(generate_uid(),study))
            q.execute("UPDATE nextris.tbpacs_study_link SET link_status='unlinked' WHERE pacs_study_iuid=%s",(study,))
        again=self.send({'a':dicom_bytes(study,series,sop,seed=8)});self.finalize(again['id'],target);self.drain()
        blocked=self.detail(again['id']);self.assertEqual(blocked['state'],'retryable');self.assertIn('contenido diferente',blocked['error'])
        # Unchanged content re-links after an unlink instead of being blocked forever.
        with self.db.cursor() as q:q.execute("UPDATE nextris.veterinary_upload_session SET state='cancelled' WHERE id=%s",(again['id'],))
        relink=self.send({'a':dicom_bytes(study,series,sop,seed=7)});self.finalize(relink['id'],target);self.drain()
        self.assertEqual(self.detail(relink['id'])['state'],'completed',self.detail(relink['id'])['error'])

    def test_07_study_of_other_patient_in_pacs_is_not_taken(self):
        from apps.services.pacs_client import PacsClient
        owner=self.animal();other=self.animal();study=generate_uid();series=generate_uid();sop=generate_uid();data=dicom_bytes(study,series,sop)
        first=self.send({'a':data});self.finalize(first['id'],self.create_target(owner));self.drain();self.assertEqual(self.detail(first['id'])['state'],'completed')
        with self.db.cursor() as q:
            q.execute("UPDATE nextris.tbexamination SET studyinstanceuid=%s WHERE studyinstanceuid=%s",(generate_uid(),study))
            q.execute("UPDATE nextris.tbpacs_study_link SET link_status='unlinked' WHERE pacs_study_iuid=%s",(study,))
        second=self.send({'a':data});self.finalize(second['id'],self.create_target(other));self.drain()
        blocked=self.detail(second['id']);self.assertEqual(blocked['state'],'retryable');self.assertIn('otro PatientID',blocked['error']);self.assertEqual(self.exams(other),[])
        self.assertEqual({r['00100020']['Value'][0] for r in PacsClient().instances(study)},{owner['patientid']})

    def test_08_permissions_and_ownership(self):
        result=self.send({'a':dicom_bytes(generate_uid())});key=result['id']
        for method,path in [('GET','/veterinary/uploads'),('POST','/veterinary/uploads'),('GET','/veterinary/uploads/'+key),('POST',f'/veterinary/uploads/{key}/cancel')]:
            self.assertEqual(self.call(method,path,{} if method=='POST' else None,headers=self.limited).status_code,403,path)
        self.assertIn(self.call('GET','/veterinary/uploads/'+key,headers={}).status_code,(401,422))
        # Report generation is also enforced server-side for an operator who can only upload and link.
        from apps.api import permissions
        animal=self.animal()
        granted={'dicom.studies.manage','patients.view'}
        with mock.patch.object(permissions,'user_has_permission_code',lambda _user,code,**_:code in granted):
            from apps.services import veterinary as vet
            with vet.database() as connection,connection.cursor() as q:
                self.uploads.required_permissions(self.limited_id,'link',connection)
                with self.assertRaises(vet.VeterinaryError):self.uploads.required_permissions(self.limited_id,'create',connection)

    def test_09_chunk_resume_and_abandoned_cleanup(self):
        data=dicom_bytes(generate_uid())
        session=self.call('POST','/veterinary/uploads',{}).json()['data'];key=session['id']
        fid=self.call('POST',f'/veterinary/uploads/{key}/files',{'name':'a','size':len(data)}).json()['data']['id']
        put=lambda offset,body:requests.put(BASE+f'/veterinary/uploads/{key}/files/{fid}',params={'offset':offset},data=body,headers=self.headers,timeout=30)
        self.assertEqual(put(0,data[:100]).status_code,200)
        self.assertEqual(self.call('POST',f'/veterinary/uploads/{key}/analyze',{}).status_code,409)
        self.assertEqual(put(500,data[500:600]).status_code,409)
        self.assertEqual(put(0,b'x'*100).status_code,409)
        self.assertEqual(put(0,data[:100]).status_code,200)
        self.assertEqual(put(100,data[100:]).status_code,200)
        self.assertEqual(self.call('POST',f'/veterinary/uploads/{key}/files',{'name':'a','size':len(data)}).json()['data']['received_bytes'],len(data))
        self.assertEqual(self.call('POST',f'/veterinary/uploads/{key}/files',{'name':'../b','size':1}).status_code,400)
        with self.db.cursor() as q:q.execute("UPDATE nextris.veterinary_upload_session SET updated_at=now()-interval '25 hours' WHERE id=%s",(key,))
        directory=self.uploads.root()/key;self.assertTrue(directory.exists())
        self.uploads.expire_abandoned();self.assertFalse(directory.exists());self.assertEqual(self.detail(key)['state'],'expired')

    def test_10_guarded_downgrade(self):
        sys.path.insert(0,str(ROOT/'deployment'))
        import migrate_veterinary_uploads as migration
        connection=psycopg2.connect(host=os.environ['DB_HOST'],port=os.environ['DB_PORT'],dbname=os.environ['DB_NAME'],user=os.environ['DB_USER'],password=os.environ['DB_PASS'])
        try:
            with self.assertRaises(psycopg2.Error):migration.migrate(connection,down=True)
        finally:
            connection.rollback();connection.close()


if __name__=='__main__':
    unittest.main(verbosity=2)
