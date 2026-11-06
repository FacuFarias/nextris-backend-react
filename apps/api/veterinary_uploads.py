"""Authenticated receiving/analysis/confirmation API for the veterinary upload journal."""
import os
import shutil
import uuid
from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity
from psycopg2 import IntegrityError
from psycopg2.extras import Json, RealDictCursor
from apps.api.veterinary import staff, reply
from apps.services import veterinary as vet
from apps.services import veterinary_uploads as uploads

blueprint=Blueprint('veterinary_uploads',__name__,url_prefix='/api/veterinary/uploads')


@blueprint.errorhandler(IntegrityError)
def conflict(_error):
    return reply(None,'El estudio ya está reservado por otra carga o tiene una vinculación incompatible',409)


def accessible(cursor,key):
    row=uploads.session(cursor,key,lock=request.method!='GET')
    actor=str(get_jwt_identity())
    uploads.required_permissions(actor,connection=cursor.connection)
    if str(row['created_by'])!=actor:
        from apps.api.permissions import get_user_permission_codes
        if '*' not in get_user_permission_codes(actor,connection=cursor.connection):
            raise vet.VeterinaryError('Carga no encontrada',404)
    return row


@blueprint.route('',methods=['GET','POST'])
@staff('dicom.studies.manage')
def collection():
    actor=str(get_jwt_identity())
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        uploads.required_permissions(actor,connection=connection)
        if request.method=='GET':
            from apps.api.permissions import get_user_permission_codes
            admin='*' in get_user_permission_codes(actor,connection=connection)
            q.execute('''SELECT * FROM nextris.veterinary_upload_session WHERE (%s OR created_by=%s)
                ORDER BY created_at DESC LIMIT 20''',(admin,actor))
            return reply([uploads.dto(q,row) for row in q.fetchall()])
        key=str(uuid.uuid4())
        q.execute('INSERT INTO nextris.veterinary_upload_session(id,created_by) VALUES(%s,%s) RETURNING *',(key,actor))
        return reply(uploads.dto(q,q.fetchone()),status=201)


@blueprint.route('/<key>',methods=['GET'])
@staff('dicom.studies.manage')
def detail(key):
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        return reply(uploads.dto(q,accessible(q,key)))


@blueprint.route('/<key>/files',methods=['POST'])
@staff('dicom.studies.manage')
def add_file(key):
    data=request.get_json(silent=True) or {}
    name=uploads.safe_name(data.get('name',''));size=data.get('size')
    if isinstance(size,bool) or not isinstance(size,int) or size<=0:
        raise vet.VeterinaryError('Tamaño de archivo inválido')
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        upload=accessible(q,key)
        if upload['state']!='receiving':raise vet.VeterinaryError('La carga ya no acepta archivos',409)
        q.execute('SELECT * FROM nextris.veterinary_upload_file WHERE session_id=%s AND name=%s',(key,name))
        existing=q.fetchone()
        if existing:
            if existing['expected_bytes']!=size:raise vet.VeterinaryError('El archivo cambió; inicie una carga nueva',409)
            return reply({'id':existing['id'],'received_bytes':existing['received_bytes'],'size':size})
        q.execute('SELECT count(*) AS n,COALESCE(sum(received_bytes),0) AS stored FROM nextris.veterinary_upload_file WHERE session_id=%s',(key,))
        current=q.fetchone()
        if current['n']>=uploads.MAX_FILES:
            raise vet.VeterinaryError('La carga supera el límite de archivos',413)
        # Original, prepared copy and PACS copy; what was already received is no longer part of the free space.
        if shutil.disk_usage(uploads.root()).free+current['stored']<(upload['total_bytes']+size)*3+1024**3:
            raise vet.VeterinaryError('No hay espacio suficiente para conservar los archivos de esta carga',507)
        file_id=str(uuid.uuid4())
        q.execute('INSERT INTO nextris.veterinary_upload_file(id,session_id,name,expected_bytes) VALUES(%s,%s,%s,%s)',(file_id,key,name,size))
        q.execute('UPDATE nextris.veterinary_upload_session SET total_bytes=total_bytes+%s,updated_at=now() WHERE id=%s',(size,key))
        return reply({'id':file_id,'received_bytes':0,'size':size},status=201)


@blueprint.route('/<key>/files/<file_id>',methods=['PUT'])
@staff('dicom.studies.manage')
def chunk(key,file_id):
    try:offset=int(request.args.get('offset','-1'))
    except ValueError:raise vet.VeterinaryError('Desplazamiento inválido')
    data=request.stream.read(uploads.CHUNK_BYTES+1)
    if not data or len(data)>uploads.CHUNK_BYTES or offset<0:raise vet.VeterinaryError('Bloque inválido',413)
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        upload=accessible(q,key)
        if upload['state']!='receiving':raise vet.VeterinaryError('La carga no acepta bloques',409)
        q.execute('SELECT * FROM nextris.veterinary_upload_file WHERE id=%s AND session_id=%s FOR UPDATE',(vet.identifier(file_id),key))
        row=q.fetchone()
        if not row:raise vet.VeterinaryError('Archivo no encontrado',404)
        if offset+len(data)>row['expected_bytes'] or offset>row['received_bytes']:
            raise vet.VeterinaryError('El bloque no coincide con el progreso del archivo',409)
        path=uploads.file_path(key,file_id)
        with path.open('r+b' if path.exists() else 'w+b') as stream:
            if offset<row['received_bytes']:
                stream.seek(offset)
                if offset+len(data)>row['received_bytes'] or stream.read(len(data))!=data:
                    raise vet.VeterinaryError('El contenido cambió; inicie una carga nueva',409)
                return reply({'received_bytes':row['received_bytes']})
            stream.truncate(row['received_bytes']);stream.seek(offset);stream.write(data);stream.flush();os.fsync(stream.fileno())
        path.chmod(0o600)
        q.execute('UPDATE nextris.veterinary_upload_file SET received_bytes=%s WHERE id=%s',(offset+len(data),file_id))
        q.execute('UPDATE nextris.veterinary_upload_session SET updated_at=now() WHERE id=%s',(key,))
        return reply({'received_bytes':offset+len(data)})


@blueprint.route('/<key>/analyze',methods=['POST'])
@staff('dicom.studies.manage')
def analyze(key):
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        upload=accessible(q,key)
        if upload['state'] in ('queued_analysis','analyzing','ready'):return reply(uploads.dto(q,upload),status=202)
        if upload['state']!='receiving':raise vet.VeterinaryError('Inicie una carga nueva para corregir estos archivos',409)
        q.execute('SELECT count(*) AS n,count(*) FILTER(WHERE expected_bytes<>received_bytes) AS incomplete FROM nextris.veterinary_upload_file WHERE session_id=%s',(key,))
        result=q.fetchone()
        if not result['n'] or result['incomplete']:raise vet.VeterinaryError('Debe completar la transferencia de todos los archivos',409)
        q.execute("UPDATE nextris.veterinary_upload_session SET state='queued_analysis',error=NULL,updated_at=now() WHERE id=%s",(key,))
        return reply(uploads.dto(q,uploads.session(q,key)),status=202)


@blueprint.route('/<key>/preview',methods=['POST'])
@blueprint.route('/<key>/finalize',methods=['POST'])
@staff('dicom.studies.manage')
def finalize(key):
    preview=request.path.endswith('/preview')
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        upload=accessible(q,key)
        if upload['state']=='completed':return reply(uploads.dto(q,upload))
        if upload['state'] in ('queued_transfer','transferring','verifying'):return reply(uploads.dto(q,upload),status=202)
        if upload['state'] not in ('ready','retryable'):raise vet.VeterinaryError('El análisis debe terminar antes de asociar el estudio',409)
        selection=uploads.choose_target(q,upload,request.get_json(silent=True) or {},get_jwt_identity(),preview=preview)
        q.execute('UPDATE nextris.veterinary_upload_session SET selection=%s,updated_at=now() WHERE id=%s',(Json(selection),key))
        if preview:
            original=upload['summary'];context=selection['context']
            fields=[('Animal ID',original.get('patient_id',''),context['patientid']),('Nombre',original.get('patient_name',''),context['name']),
                    ('Acceso',original.get('accession',''),selection['accession'])]
            for label,source,target in [('Especie','species','species_name'),('Raza','breed','breed_name')]:
                before=original.get('veterinary',{}).get(source,'');after=context.get(target) or ''
                if before and after:fields.append((label,before,after))
            differences=[{'field':label,'dicom':before,'ris':after} for label,before,after in fields if str(before).strip().casefold()!=str(after).strip().casefold()]
            return reply({'differences':differences,'exam_id':selection['exam_id'],'accession':selection['accession']})
        q.execute("UPDATE nextris.veterinary_upload_session SET state='queued_transfer',error=NULL,updated_at=now() WHERE id=%s",(key,))
        return reply(uploads.dto(q,uploads.session(q,key)),status=202)


@blueprint.route('/<key>/cancel',methods=['POST'])
@staff('dicom.studies.manage')
def cancel(key):
    with vet.database() as connection,connection.cursor(cursor_factory=RealDictCursor) as q:
        upload=accessible(q,key)
        if upload['transfer_started'] or upload['state'] in ('queued_transfer','transferring','verifying','completed'):
            raise vet.VeterinaryError('La transferencia al PACS ya empezó o está confirmada; se conserva para recuperación',409)
        if upload['state']=='analyzing':raise vet.VeterinaryError('Espere a que termine el análisis para cancelar',409)
        q.execute("UPDATE nextris.veterinary_upload_session SET state='cancelled',updated_at=now() WHERE id=%s",(key,))
        return reply(uploads.dto(q,uploads.session(q,key)))
