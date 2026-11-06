"""Persistent single-study uploads. Files are private; the database is the job journal."""
import hashlib
import logging
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import time
import uuid
import zipfile

import requests

import pydicom
from pydicom.uid import UID
from psycopg2.extras import Json, RealDictCursor
from apps.services import veterinary as vet
from apps.services.veterinary_integration import reconcile_dataset

MAX_FILES = int(os.getenv('NEXTRIS_UPLOAD_MAX_FILES', '10000'))
CHUNK_BYTES = 8*1024**2
BUSY = ('queued_analysis','analyzing','queued_transfer','transferring','verifying')


def root():
    path=Path(os.getenv('NEXTRIS_UPLOAD_ROOT',str(Path(__file__).resolve().parents[2]/'uploads_dicom'/'sessions')))
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    return path


def file_path(session_id, file_id, prepared=False):
    directory=root()/vet.identifier(session_id)
    directory.mkdir(mode=0o700,exist_ok=True)
    return directory/(vet.identifier(file_id)+('.prepared' if prepared else '.original'))


def safe_name(name):
    name=str(name).replace('\\','/')
    path=PurePosixPath(name)
    if not name or len(name)>1024 or path.is_absolute() or '..' in path.parts or ':' in name or '\x00' in name:
        raise vet.VeterinaryError('Ruta de archivo insegura')
    return name


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while chunk:=stream.read(1024*1024):value.update(chunk)
    return value.hexdigest()


def content_fingerprint(dataset):
    """Identity of an instance's content. PACS may legitimately coerce patient/study attributes, so only
    the UIDs, image geometry and (when stored with the same transfer syntax) the pixel bytes are compared."""
    meta=getattr(dataset,'file_meta',None)
    result={attribute:str(getattr(dataset,attribute,'')) for attribute in
            ['SOPClassUID','SOPInstanceUID','SeriesInstanceUID','StudyInstanceUID','Rows','Columns','NumberOfFrames']}
    result['transfer_syntax']=str(getattr(meta,'TransferSyntaxUID',''))
    pixels=dataset.get('PixelData')
    result['pixels']=hashlib.sha256(pixels).hexdigest() if isinstance(pixels,(bytes,bytearray)) else ''
    return result


def same_content(first, second):
    keys=[key for key in first if key not in ('transfer_syntax','pixels')]
    if any(first[key]!=second[key] for key in keys):return False
    return first['transfer_syntax']!=second['transfer_syntax'] or first['pixels']==second['pixels']


def text(value, limit):
    """DICOM text for a bounded RIS column, keeping the end of file paths and never a NUL byte."""
    return str(value or '').replace('\x00','')[-limit:]


def session(cursor, key, *, lock=False):
    cursor.execute('SELECT * FROM nextris.veterinary_upload_session WHERE id=%s'+(' FOR UPDATE' if lock else ''),(vet.identifier(key),))
    row=cursor.fetchone()
    if not row:raise vet.VeterinaryError('Carga no encontrada',404)
    return dict(row)


def state(key, value, *, error=None, summary=None, result=None):
    with vet.database() as connection,connection.cursor() as q:
        q.execute('''UPDATE nextris.veterinary_upload_session SET state=%s,error=%s,
            summary=COALESCE(%s,summary),result=COALESCE(%s,result),updated_at=now() WHERE id=%s''',
            (value,error,Json(summary) if summary is not None else None,Json(result) if result is not None else None,key))


def dto(cursor, row):
    cursor.execute('''SELECT count(*) AS files,count(*) FILTER(WHERE kind='dicom') AS instances,
        count(*) FILTER(WHERE sent) AS sent,count(*) FILTER(WHERE verified) AS verified,
        COALESCE(sum(received_bytes) FILTER(WHERE kind IN ('input','zip')),0) AS received_bytes
        FROM nextris.veterinary_upload_file WHERE session_id=%s''',(row['id'],))
    progress=dict(cursor.fetchone())
    result={key:row[key] for key in ['id','state','total_bytes','summary','result','error','created_at','updated_at','transfer_started']}
    result.update(progress)
    result['selection']={key:row['selection'].get(key) for key in ['mode','patient_id','exam_id','study_type_id']}
    result['limits']={'max_files':MAX_FILES,'chunk_bytes':CHUNK_BYTES}
    return vet.plain(result)


def required_permissions(actor, mode='link', connection=None):
    from apps.api.permissions import user_has_permission_code
    required=['dicom.studies.manage','patients.view']
    if mode=='create':required+=['admissions.create_spontaneous','reports.write','images.view']
    for permission in required:
        if not user_has_permission_code(actor,permission,connection=connection):
            raise vet.VeterinaryError('Falta el permiso '+permission,403)


def validate_target(cursor, upload, selection, *, lock=False):
    patient=vet.animal(cursor,selection['patient_id'],lock=lock)
    context=vet.patient_context(cursor,selection['patient_id'])
    if not context.get('species_name'):raise vet.VeterinaryError('Defina la especie del animal antes de enviar las imágenes')
    key=selection['exam_id']
    cursor.execute('''SELECT guid,idpatient,localacc,studyinstanceuid,isreported,isimage,
        COALESCE(workflow_state,'pending') AS workflow_state FROM nextris.tbexamination WHERE guid=%s'''+(' FOR UPDATE' if lock else ''),(key,))
    exam=cursor.fetchone()
    if selection['mode']=='link':
        if not exam or str(exam['idpatient'])!=str(patient['guid']):raise vet.VeterinaryError('La orden no corresponde al animal',409)
        if exam['isreported'] or exam['workflow_state']=='cancelled':raise vet.VeterinaryError('La orden está informada o cancelada',409)
        if exam['isimage'] and exam['studyinstanceuid']!=upload['summary']['study_uid']:
            raise vet.VeterinaryError('La orden ya tiene otro estudio con imágenes',409)
        if exam['localacc']!=selection['accession']:raise vet.VeterinaryError('La orden cambió durante la carga; revise la selección',409)
    elif exam:
        raise vet.VeterinaryError('La orden reservada ya existe; revise el resultado de la carga',409)
    cursor.execute('''SELECT 1 FROM nextris.tbexamination WHERE studyinstanceuid=%s AND guid<>%s LIMIT 1''',
                   (upload['summary']['study_uid'],key))
    if cursor.fetchone():raise vet.VeterinaryError('El estudio ya pertenece a otra orden o animal',409)
    cursor.execute('''SELECT 1 FROM nextris.tbpacs_study_link WHERE link_status='linked'
        AND ((order_guid=%s AND pacs_study_iuid<>%s) OR (pacs_study_iuid=%s AND order_guid<>%s)) LIMIT 1''',
        (key,upload['summary']['study_uid'],upload['summary']['study_uid'],key))
    if cursor.fetchone():raise vet.VeterinaryError('La orden o el estudio ya tienen otra vinculación',409)
    return context


def choose_target(cursor, upload, payload, actor, *, preview=False):
    mode=payload.get('mode')
    if mode not in ('link','create'):raise vet.VeterinaryError('Seleccione Vincular o Generar reporte')
    required_permissions(actor,mode,cursor.connection)
    patient_id=vet.identifier(payload.get('patient_id'))
    old=upload['selection']
    identity={'mode':mode,'patient_id':patient_id,'exam_id':payload.get('exam_id') if mode=='link' else None,
              'study_type_id':payload.get('study_type_id') if mode=='create' else None}
    if old and upload['transfer_started']:
        if any(str(identity[key] or '')!=str(old.get(key) or '') for key in ['mode','patient_id','study_type_id']) or (mode=='link' and identity['exam_id']!=old['exam_id']):
            raise vet.VeterinaryError('La transferencia empezó; no se puede cambiar el animal o la orden',409)
        validate_target(cursor,upload,old)
        return old
    context=vet.protocol_context(cursor,patient_id,payload.get('protocol_id') or None,payload.get('study_type_id') or None)
    same=bool(old) and all(str(identity.get(field) or '')==str(old.get(field) or '') for field in ['mode','patient_id','study_type_id']) and (mode=='create' or identity['exam_id']==old.get('exam_id'))
    if mode=='link':
        key=vet.identifier(payload.get('exam_id'))
        cursor.execute('SELECT localacc FROM nextris.tbexamination WHERE guid=%s',(key,))
        row=cursor.fetchone()
        if not row or not row['localacc']:raise vet.VeterinaryError('Orden no encontrada o sin número de acceso',404)
        accession=row['localacc']
    else:
        study=vet.identifier(payload.get('study_type_id'))
        cursor.execute('SELECT guid FROM nextris.isstudytype WHERE guid=%s',(study,))
        if not cursor.fetchone():raise vet.VeterinaryError('Tipo de estudio inválido')
        key=old['exam_id'] if same else str(uuid.uuid4())
        accession=old['accession'] if same else 'VT'+uuid.uuid4().hex[:12].upper()
    selection={**identity,'exam_id':key,'accession':accession,'context':context,'actor':str(actor),
        'order_data':{key:payload.get(key) for key in ['study_type_id','protocol_id','clinical_question','history','requesting_veterinarian'] if payload.get(key)},
        'confirmed':vet.flag(payload.get('confirm_identity'))}
    validate_target(cursor,upload,selection)
    # Reuse the same explicit reconciliation as the existing upload flow, before queuing any STOW.
    cursor.execute("SELECT * FROM nextris.veterinary_upload_file WHERE session_id=%s AND kind='dicom'",(upload['id'],))
    for row in cursor.fetchall():
        dataset=pydicom.dcmread(file_path(upload['id'],row['id']),stop_before_pixels=True,force=True)
        reconcile_dataset(dataset,context,accession,True if preview else selection['confirmed'])
    return selection


def analyse_archive(upload, row):
    path=file_path(upload['id'],row['id'])
    with zipfile.ZipFile(path) as archive:
        members=[member for member in archive.infolist() if not member.is_dir()]
        with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
            q.execute('SELECT count(*) AS n FROM nextris.veterinary_upload_file WHERE session_id=%s AND id<>%s AND kind<>\'zip\'',(upload['id'],row['id']))
            current=q.fetchone()
            if len(members)+current['n']>MAX_FILES:raise vet.VeterinaryError('La carga supera el límite de archivos')
            if shutil.disk_usage(root()).free<sum(member.file_size for member in members)*2+1024**3:
                raise vet.VeterinaryError('No hay espacio suficiente para procesar y conservar los originales',507)
            for index,member in enumerate(members):
                name=safe_name(member.filename)
                if member.flag_bits&1 or stat.S_ISLNK(member.external_attr>>16):raise vet.VeterinaryError('No se admiten ZIP cifrados ni enlaces simbólicos')
                key=str(uuid.uuid5(uuid.UUID(str(row['id'])),str(index)+':'+name))
                target=file_path(upload['id'],key)
                with archive.open(member) as source,target.open('wb') as output:
                    copied=0
                    while chunk:=source.read(1024*1024):
                        copied+=len(chunk)
                        if copied>member.file_size:raise vet.VeterinaryError('Tamaño ZIP inconsistente')
                        output.write(chunk)
                target.chmod(0o600)
                if copied!=member.file_size:raise vet.VeterinaryError('ZIP incompleto')
                if zipfile.is_zipfile(target):raise vet.VeterinaryError('No se admiten ZIP anidados')
                q.execute('''INSERT INTO nextris.veterinary_upload_file(id,session_id,name,expected_bytes,received_bytes)
                    VALUES(%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING''',(key,upload['id'],name,copied,copied))
            q.execute("UPDATE nextris.veterinary_upload_file SET kind='zip',sha256=%s WHERE id=%s",(digest(path),row['id']))


def analyse(key):
    state(key,'analyzing')
    while True:
        with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
            upload=session(q,key)
            q.execute("SELECT * FROM nextris.veterinary_upload_file WHERE session_id=%s AND kind='input' ORDER BY created_at,id LIMIT 1",(key,))
            row=q.fetchone()
        if not row:break
        if row['received_bytes']!=row['expected_bytes']:raise vet.VeterinaryError('Hay archivos incompletos')
        path=file_path(key,row['id'])
        if zipfile.is_zipfile(path):
            analyse_archive(upload,row);continue
        metadata={};kind='ignored';sop=None;series=None
        try:
            dataset=pydicom.dcmread(path,stop_before_pixels=True,force=True)
            media=str(getattr(getattr(dataset,'file_meta',None),'MediaStorageSOPClassUID',''))
            if media=='1.2.840.10008.1.3.10' or 'DirectoryRecordSequence' in dataset:
                metadata={'reason':'Índice DICOMDIR'}
            else:
                for attribute in ['StudyInstanceUID','SeriesInstanceUID','SOPInstanceUID','SOPClassUID']:
                    if not UID(str(getattr(dataset,attribute,''))).is_valid:raise ValueError('UID DICOM ausente o inválido')
                kind='dicom';sop=str(dataset.SOPInstanceUID);series=str(dataset.SeriesInstanceUID)
                from apps.services.veterinary_integration import read_veterinary_metadata
                metadata={attribute:str(getattr(dataset,attribute,'')).replace('\x00','') for attribute in ['StudyInstanceUID','PatientID','PatientName','AccessionNumber','Modality','StudyDescription','StudyDate']}
                metadata['veterinary']={field:value.replace('\x00','') for field,value in read_veterinary_metadata(dataset).items()}
                metadata['image']=bool(getattr(dataset,'Rows',0) and getattr(dataset,'Columns',0))
        except Exception:
            if Path(row['name']).suffix.lower() in ('.dcm','.dic','.dicom'):
                raise vet.VeterinaryError('Archivo DICOM inválido: '+row['name'])
            metadata={'reason':'Archivo no DICOM'}
        sha=digest(path)
        with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
            if sop:
                q.execute("SELECT sha256 FROM nextris.veterinary_upload_file WHERE session_id=%s AND kind='dicom' AND sop_uid=%s",(key,sop))
                duplicate=q.fetchone()
                if duplicate:
                    if duplicate['sha256']!=sha:raise vet.VeterinaryError('Un mismo SOP Instance UID contiene archivos diferentes')
                    kind='duplicate'
            q.execute('''UPDATE nextris.veterinary_upload_file SET kind=%s,sha256=%s,sop_uid=%s,series_uid=%s,metadata=%s WHERE id=%s''',
                      (kind,sha,sop,series,Json(metadata),row['id']))
            q.execute('UPDATE nextris.veterinary_upload_session SET updated_at=now() WHERE id=%s',(key,))
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        q.execute('SELECT * FROM nextris.veterinary_upload_file WHERE session_id=%s',(key,));rows=q.fetchall()
    dicoms=[r for r in rows if r['kind']=='dicom']
    studies={r['metadata']['StudyInstanceUID'] for r in dicoms}
    if not dicoms:raise vet.VeterinaryError('No se encontraron instancias DICOM válidas')
    if len(studies)!=1:raise vet.VeterinaryError('La carga contiene varios estudios. Separe los StudyInstanceUID en cargas diferentes.')
    for field in ['PatientID','PatientName']:
        if len({r['metadata'].get(field,'').strip() for r in dicoms if r['metadata'].get(field,'').strip()})>1:
            raise vet.VeterinaryError('El estudio contiene identidades discordantes; revise los archivos antes de cargarlo')
    if not any(r['metadata'].get('image') for r in dicoms):raise vet.VeterinaryError('El estudio no contiene imágenes DICOM')
    first=dicoms[0]['metadata']
    summary={'study_uid':next(iter(studies)),'patient_id':first.get('PatientID',''),'patient_name':first.get('PatientName',''),
        'accession':first.get('AccessionNumber',''),'description':first.get('StudyDescription',''),'study_date':first.get('StudyDate',''),
        'veterinary':first.get('veterinary',{}),'modalities':sorted({r['metadata']['Modality'] for r in dicoms}),
        'series_count':len({r['series_uid'] for r in dicoms}),'instance_count':len(dicoms),
        'ignored_count':sum(r['kind']=='ignored' for r in rows),'duplicate_count':sum(r['kind']=='duplicate' for r in rows),
        'ignored':[{'name':r['name'],'reason':r['metadata'].get('reason','')} for r in rows if r['kind']=='ignored'][:200]}
    state(key,'ready',summary=summary)


def dicom_json_value(row, tag):
    values=row.get(tag,{}).get('Value',[])
    return str(values[0]) if values else ''


def transfer(key):
    from apps.services.pacs_client import PacsClient
    from apps.services.veterinary_orders import create_order
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        upload=session(q,key)
        selection=upload['selection'];required_permissions(selection['actor'],selection['mode'],connection)
        validate_target(q,upload,selection)
        q.execute("SELECT * FROM nextris.veterinary_upload_file WHERE session_id=%s AND kind='dicom' ORDER BY id",(key,));files=q.fetchall()
    uid=upload['summary']['study_uid'];client=PacsClient()
    # Never permit an existing SOP UID to be repurposed into another study/series.
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        q.execute('''SELECT i.sop_iuid,s.series_iuid,st.study_iuid FROM public.instance i JOIN public.series s ON s.pk=i.series_fk
            JOIN public.study st ON st.pk=s.study_fk WHERE i.sop_iuid=ANY(%s)''',([f['sop_uid'] for f in files],))
        own={f['sop_uid']:f['series_uid'] for f in files}
        for existing in q.fetchall():
            if existing['study_iuid']!=uid or own[existing['sop_iuid']]!=existing['series_iuid']:
                raise vet.VeterinaryError('Un SOP Instance UID ya pertenece a otro estudio PACS',409)
    stored=client.instances(uid)
    existing={dicom_json_value(r,'00080018') for r in stored}
    if existing-{f['sop_uid'] for f in files}:raise vet.VeterinaryError('El estudio PACS ya contiene otras instancias; no se modificará',409)
    if any(dicom_json_value(r,'00100020').strip()!=selection['context']['patientid'] for r in stored):
        raise vet.VeterinaryError('El estudio ya existe en el PACS con otro PatientID; no se modificará ni se asociará a este animal',409)
    state(key,'transferring')
    for row in files:
        target=file_path(key,row['id'],prepared=True)
        if not target.exists():
            dataset=pydicom.dcmread(file_path(key,row['id']),force=True)
            reconcile_dataset(dataset,selection['context'],selection['accession'],selection['confirmed'])
            temporary=target.with_suffix('.tmp')
            dataset.save_as(temporary,write_like_original=False)
            temporary.chmod(0o600);os.replace(temporary,target)
        dataset=pydicom.dcmread(target)
        fingerprint=content_fingerprint(dataset)
        if row['sop_uid'] in existing:
            import io
            raw=client.retrieve(uid,row['series_uid'],row['sop_uid'])
            if not same_content(fingerprint,content_fingerprint(pydicom.dcmread(io.BytesIO(raw)))):
                raise vet.VeterinaryError('El SOP Instance UID ya existe en PACS con contenido diferente; no se sobrescribirá',409)
        elif not row['sent']:
            with vet.database() as connection,connection.cursor() as q:
                q.execute('UPDATE nextris.veterinary_upload_session SET transfer_started=true,updated_at=now() WHERE id=%s',(key,))
            client.store(target)
        else:
            # A previously acknowledged instance disappearing from PACS requires investigation, not automatic recreation.
            raise vet.VeterinaryError('Una instancia ya enviada no está disponible en PACS; revise la transferencia',409)
        with vet.database() as connection,connection.cursor() as q:
            q.execute('UPDATE nextris.veterinary_upload_file SET sent=true,prepared_sha256=%s WHERE id=%s',(digest(target),row['id']))
            q.execute('UPDATE nextris.veterinary_upload_session SET updated_at=now() WHERE id=%s',(key,))
    state(key,'verifying')
    expected={f['sop_uid'] for f in files};deadline=time.monotonic()+int(os.getenv('NEXTRIS_UPLOAD_VERIFY_SECONDS','120'))
    while True:
        available={dicom_json_value(r,'00080018') for r in client.instances(uid)}
        if expected<=available:break
        if time.monotonic()>=deadline:raise vet.VeterinaryError('PACS está indexando las imágenes. Reintente la verificación; no se duplicarán instancias.',409)
        time.sleep(2)
    image=next(f for f in files if f['metadata']['image'])
    if not client.frame_available(uid,image['series_uid'],image['sop_uid']):
        raise vet.VeterinaryError('PACS todavía no permite leer las imágenes. Reintente la verificación.',409)
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        upload=session(q,key,lock=True)
        required_permissions(selection['actor'],selection['mode'],connection)
        validate_target(q,upload,selection,lock=True)
        q.execute('SELECT pk FROM nextris.available_pacs_study WHERE study_iuid=%s',(uid,));pacs=q.fetchone()
        if not pacs:raise vet.VeterinaryError('El estudio aún no está disponible en el índice RIS/PACS',409)
        exam_id=selection['exam_id'];original_uid=None
        if selection['mode']=='create':
            create_order(q,selection['patient_id'],selection['order_data'],key=exam_id,
                accession=selection['accession'],study_uid=uid,context=selection['context'])
        else:
            q.execute('SELECT studyinstanceuid FROM nextris.tbexamination WHERE guid=%s',(exam_id,));original_uid=q.fetchone()['studyinstanceuid']
        first_upload=None
        for row in files:
            metadata=row['metadata'];manual_id=str(uuid.uuid5(uuid.UUID(str(row['id'])),'manual-upload'))
            first_upload=first_upload or manual_id
            q.execute('''INSERT INTO nextris.tbmanual_uploads(guid,filename,filepath,file_size,patient_name,patient_id,
                study_date,study_description,modality,study_instance_uid,series_instance_uid,sop_instance_uid,accession_number,
                uploaded_by_user_guid,uploaded_by_username,pacs_status,pacs_message,pacs_sent_date,islinked,linked_examination_guid,
                linked_by_user_guid,linked_by_username,linked_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                (SELECT username FROM nextris.tbuser WHERE guid=%s),'success','Carga veterinaria verificada',now(),1,%s,
                %s,(SELECT username FROM nextris.tbuser WHERE guid=%s),now())
                ON CONFLICT(guid) DO NOTHING''',
                (manual_id,text(row['name'],255),str(file_path(key,row['id'],prepared=True)),row['expected_bytes'],text(selection['context']['name'],255),
                 selection['context']['patientid'],text(metadata['StudyDate'],20),text(metadata['StudyDescription'],255),text(metadata['Modality'],20),uid,
                 row['series_uid'],row['sop_uid'],selection['accession'],selection['actor'],selection['actor'],exam_id,selection['actor'],selection['actor']))
        q.execute("SELECT 1 FROM nextris.tbpacs_study_link WHERE order_guid=%s AND pacs_study_iuid=%s AND link_status='linked'",(exam_id,uid))
        if not q.fetchone():
            q.execute('''INSERT INTO nextris.tbpacs_study_link(pacs_study_pk,pacs_study_iuid,order_guid,order_study_uuid,
                manual_upload_guid,source,linked_by_user_guid,linked_by_username) VALUES(%s,%s,%s,%s,%s,'manual',%s,
                (SELECT username FROM nextris.tbuser WHERE guid=%s))''',
                (pacs['pk'],uid,exam_id,original_uid,first_upload,selection['actor'],selection['actor']))
        q.execute('UPDATE nextris.tbexamination SET studyinstanceuid=%s,isimage=1 WHERE guid=%s',(uid,exam_id))
        q.execute("UPDATE nextris.veterinary_upload_file SET verified=true WHERE session_id=%s AND kind='dicom'",(key,))
        result={'exam_id':exam_id,'patient_id':selection['patient_id'],'study_uid':uid,'mode':selection['mode'],'accession':selection['accession']}
        q.execute("UPDATE nextris.veterinary_upload_session SET state='completed',result=%s,error=NULL,updated_at=now() WHERE id=%s",(Json(result),key))


def process_one():
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        q.execute('''SELECT * FROM nextris.veterinary_upload_session WHERE state=ANY(%s) ORDER BY updated_at,id LIMIT 1''',
                  (list(BUSY),));upload=q.fetchone()
    if not upload:return False
    key=str(upload['id']);analysis=upload['state'] in ('queued_analysis','analyzing')
    try:
        if analysis:analyse(key)
        else:transfer(key)
    except vet.VeterinaryError as error:
        state(key,'rejected' if analysis else 'retryable',error=str(error)[:1000])
    except RuntimeError as error:
        # Controlled PACS rejection messages from PacsClient.
        state(key,'retryable',error=str(error)[:1000])
    except requests.RequestException:
        logging.exception('PACS communication failed for upload %s',key)
        state(key,'retryable',error='No se pudo comunicar con el PACS. Las instancias enviadas se conservan; reintente la transferencia.')
    except Exception:
        logging.exception('Upload %s failed',key)
        state(key,'rejected' if analysis else 'retryable',error='No se pudo procesar la carga. Revise el registro del servicio y reintente.')
    return True


def expire_abandoned():
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        q.execute('''SELECT id FROM nextris.veterinary_upload_session s WHERE state IN ('receiving','ready','rejected','cancelled')
            AND NOT transfer_started AND updated_at<now()-interval '24 hours'
            AND NOT EXISTS(SELECT 1 FROM nextris.veterinary_upload_file f WHERE f.session_id=s.id AND f.sent)
            FOR UPDATE SKIP LOCKED''')
        for row in q.fetchall():
            directory=root()/str(row['id'])
            if directory.exists():shutil.rmtree(directory)
            q.execute("UPDATE nextris.veterinary_upload_session SET state='expired',updated_at=now() WHERE id=%s",(row['id'],))
