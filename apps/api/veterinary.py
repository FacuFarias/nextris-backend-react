"""Veterinary extensions to the existing RIS, protected by saved staff permissions."""
import hashlib
import secrets
import uuid
from functools import wraps
from datetime import timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity, create_access_token, create_refresh_token
from psycopg2 import IntegrityError, DataError
from psycopg2.extras import RealDictCursor, Json
from werkzeug.security import check_password_hash, generate_password_hash
from apps.services import veterinary as vet
from apps.services.report_view_service import ReportViewUnavailable

blueprint=Blueprint('veterinary',__name__,url_prefix='/api/veterinary')


@blueprint.errorhandler(ReportViewUnavailable)
def unavailable_report(error):
    return jsonify(success=False,data=None,message=str(error),code=error.code),error.status


@blueprint.errorhandler(IntegrityError)
def relation_error(error):
    return jsonify(success=False,data=None,message='Registro duplicado o referencia no válida'),409


@blueprint.errorhandler(DataError)
def invalid_value(error):
    return jsonify(success=False,data=None,message='Datos inválidos'),400


def reply(data=None,message='',status=200):
    return jsonify(success=True,data=vet.plain(data),message=message),status


def staff(permission):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            verify_jwt_in_request()
            if vet.mode()!='veterinary':
                return jsonify(success=False,message='Modo veterinario no habilitado'),404
            from apps.api.permissions import user_has_permission_code
            if get_jwt().get('user_type','').lower()=='patient' or not user_has_permission_code(get_jwt_identity(),permission):
                return jsonify(success=False,message='Acceso denegado'),403
            return fn(*args,**kwargs)
        return wrapped
    return decorate


def portal(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        if vet.mode()!='veterinary':
            raise vet.VeterinaryError('Modo veterinario no habilitado',404)
        verify_jwt_in_request()
        with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
            account=vet.responsible_account(q,get_jwt_identity())
            if not account or not account['is_active'] or str(account['status']).lower() not in ('active','activo','true','1'):
                raise vet.VeterinaryError('Acceso denegado',403)
            if account['firstlogin'] and request.path!='/api/veterinary/portal/profile':
                raise vet.VeterinaryError('Debe cambiar su contraseña inicial',403)
        return fn(*args,**kwargs)
    return wrapped


@blueprint.route('/species',methods=['GET','POST'])
@blueprint.route('/species/<record_id>',methods=['PUT'])
@staff('patients.view')
def species(record_id=None):
    return catalog('veterinary_species',record_id)


@blueprint.route('/breeds',methods=['GET','POST'])
@blueprint.route('/breeds/<record_id>',methods=['PUT'])
@staff('patients.view')
def breeds(record_id=None):
    return catalog('veterinary_breed',record_id)


def catalog(table,record_id=None):
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        if request.method=='GET':
            if table=='veterinary_breed' and request.args.get('species_id'):
                q.execute('SELECT * FROM nextris.veterinary_breed WHERE is_active AND species_id=%s ORDER BY name',(vet.identifier(request.args['species_id']),))
            else:
                q.execute('SELECT * FROM nextris.'+table+' WHERE is_active ORDER BY name')
            return reply(q.fetchall())
        from apps.api.permissions import user_has_permission_code
        if not user_has_permission_code(get_jwt_identity(),'veterinary.catalogs.manage'):
            raise vet.VeterinaryError('No tiene permiso para administrar catálogos',403)
        d=request.get_json(silent=True) or {};name=str(d.get('name','')).strip()
        if not name or len(name)>100:
            raise vet.VeterinaryError('Nombre requerido (máximo 100 caracteres)')
        code=d.get('code_value') or None;scheme=d.get('coding_scheme') or None
        if bool(code)!=bool(scheme):
            raise vet.VeterinaryError('Código y sistema de codificación deben informarse juntos')
        if code and (len(str(code))>16 or len(str(scheme))>16 or any(ord(ch)<32 or ch=='\\' for ch in str(code)+str(scheme))):
            raise vet.VeterinaryError('Código y sistema admiten hasta 16 caracteres sin separadores ni caracteres de control')
        key=str(uuid.uuid4())
        if record_id:
            q.execute('UPDATE nextris.'+table+' SET name=%s,code_value=%s,coding_scheme=%s WHERE id=%s RETURNING *',(name,code,scheme,vet.identifier(record_id)))
            row=q.fetchone()
            if not row:raise vet.VeterinaryError('Registro no encontrado',404)
            return reply(row)
        if table=='veterinary_breed':
            q.execute('INSERT INTO nextris.veterinary_breed(id,species_id,name,code_value,coding_scheme) VALUES(%s,%s,%s,%s,%s) RETURNING *',(key,vet.identifier(d.get('species_id')),name,code,scheme))
        else:
            q.execute('INSERT INTO nextris.veterinary_species(id,name,code_value,coding_scheme) VALUES(%s,%s,%s,%s) RETURNING *',(key,name,code,scheme))
        return reply(q.fetchone(),status=201)


@blueprint.route('/responsibles',methods=['GET','POST'])
@blueprint.route('/responsibles/<party_id>',methods=['PUT'])
@staff('veterinary.responsibles.manage')
def responsibles(party_id=None):
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        if request.method=='GET':
            search='%'+request.args.get('search','').strip()+'%'
            q.execute('SELECT * FROM nextris.responsible_party WHERE name ILIKE %s OR document ILIKE %s ORDER BY name LIMIT 200',(search,search))
            return reply(q.fetchall())
        d=request.get_json(silent=True) or {};name=str(d.get('name','')).strip();kind=d.get('kind','person')
        if not name or len(name)>200 or kind not in ('person','organization'):
            raise vet.VeterinaryError('Nombre o tipo de responsable inválido')
        email=str(d.get('email','') or '').strip().lower() or None
        if email:
            from apps.services.patient_email_verification import normalize_email
            try:email=normalize_email(email)
            except Exception:raise vet.VeterinaryError('Email inválido')
        values=(kind,name,d.get('document') or None,email,d.get('phone') or None,d.get('address') or None,d.get('organization') or None)
        if party_id:
            q.execute('''UPDATE nextris.responsible_party SET kind=%s,name=%s,document=%s,email=%s,phone=%s,address=%s,
                organization=%s,updated_at=now(),is_active=%s WHERE id=%s RETURNING *''',values+(vet.flag(d.get('is_active'),True),vet.identifier(party_id)))
        else:
            q.execute('''INSERT INTO nextris.responsible_party(kind,name,document,email,phone,address,organization,id)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',values+(str(uuid.uuid4()),))
        row=q.fetchone()
        if not row:raise vet.VeterinaryError('Responsable no encontrado',404)
        return reply(row,status=200 if party_id else 201)


@blueprint.route('/responsibles/<party_id>/account',methods=['POST'])
@staff('veterinary.portal.manage')
def create_account(party_id):
    d=request.get_json(silent=True) or {};username=str(d.get('username','')).strip().lower()
    password=secrets.token_urlsafe(18)
    if not username or len(username)>150:
        raise vet.VeterinaryError('Indique un usuario de portal válido')
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        q.execute('SELECT id FROM nextris.responsible_party WHERE id=%s AND is_active',(vet.identifier(party_id),))
        if not q.fetchone():raise vet.VeterinaryError('Responsable no encontrado',404)
        q.execute('SELECT email FROM nextris.responsible_party WHERE id=%s',(party_id,))
        if not q.fetchone()['email']:raise vet.VeterinaryError('Complete el email del responsable antes de crear la cuenta')
        q.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('portal-username:'+username,))
        q.execute('SELECT 1 FROM nextris.tbuser_patient WHERE lower(username)=%s',(username,))
        if q.fetchone():raise vet.VeterinaryError('El usuario ya existe',409)
        q.execute('''INSERT INTO nextris.tbuser_patient(guid,username,password,responsible_party_id,status,firstlogin)
            VALUES(%s,%s,%s,%s,'Active',1)''',(str(uuid.uuid4()),username,generate_password_hash(password),party_id))
    return reply({'username':username,'initial_password':password,'requires_password_change':True},'Guarde la contraseña inicial; no volverá a mostrarse.',201)


@blueprint.route('/responsibles/<party_id>/accounts',methods=['GET'])
@staff('veterinary.portal.manage')
def accounts(party_id):
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        q.execute('SELECT guid,username,status,firstlogin FROM nextris.tbuser_patient WHERE responsible_party_id=%s',(vet.identifier(party_id),))
        return reply(q.fetchall())


@blueprint.route('/responsibles/<party_id>/accounts/<account_id>/reset-password',methods=['POST'])
@staff('veterinary.portal.manage')
def reset_password(party_id,account_id):
    password=secrets.token_urlsafe(18)
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        q.execute('''UPDATE nextris.tbuser_patient SET password=%s,firstlogin=1,portal_auth_version=portal_auth_version+1
            WHERE guid=%s AND responsible_party_id=%s RETURNING username''',(generate_password_hash(password),account_id,vet.identifier(party_id)))
        row=q.fetchone()
        if not row:raise vet.VeterinaryError('Cuenta no encontrada',404)
        q.execute('UPDATE nextris.tbviewer_share_link SET revoked=true,revoked_at=now() WHERE portal_account_id=%s',(account_id,))
    return reply({'username':row['username'],'initial_password':password,'requires_password_change':True})


@blueprint.route('/patients/<patient_id>/responsibles',methods=['GET','POST'])
@staff('veterinary.responsibles.manage')
def relationships(patient_id):
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        vet.animal(q,patient_id,lock=request.method=='POST')
        if request.method=='GET':
            q.execute('''SELECT pr.*,rp.name,rp.email,rp.phone FROM nextris.patient_responsibility pr JOIN nextris.responsible_party rp ON rp.id=pr.responsible_id WHERE patient_id=%s ORDER BY valid_from DESC''',(patient_id,))
            return reply(q.fetchall())
        d=request.get_json(silent=True) or {};authorized=vet.flag(d.get('portal_authorized'))
        if authorized:
            from apps.api.permissions import user_has_permission_code
            if not user_has_permission_code(get_jwt_identity(),'veterinary.portal.manage'):
                raise vet.VeterinaryError('No tiene permiso para autorizar acceso al portal',403)
        role=d.get('role','owner')
        if role not in ('owner','guardian','custodian','veterinarian'):raise vet.VeterinaryError('Relación inválida')
        responsible=vet.identifier(d.get('responsible_id'))
        q.execute('SELECT id FROM nextris.responsible_party WHERE id=%s AND is_active',(responsible,))
        if not q.fetchone():raise vet.VeterinaryError('Responsable no encontrado',404)
        primary=vet.flag(d.get('is_primary'))
        if primary:q.execute('UPDATE nextris.patient_responsibility SET is_primary=false WHERE patient_id=%s AND valid_to IS NULL',(patient_id,))
        q.execute('''INSERT INTO nextris.patient_responsibility(id,patient_id,responsible_id,role,is_primary,portal_authorized,created_by)
            VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *''',(str(uuid.uuid4()),patient_id,responsible,role,primary,authorized,str(get_jwt_identity())))
        return reply(q.fetchone(),status=201)


@blueprint.route('/relationships/<relation_id>/end',methods=['POST'])
@staff('veterinary.responsibles.manage')
def end_relationship(relation_id):
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        q.execute('''UPDATE nextris.patient_responsibility SET valid_to=now(),ended_by=%s,reason=%s
            WHERE id=%s AND valid_to IS NULL RETURNING patient_id,responsible_id''',
            (str(get_jwt_identity()),str((request.get_json(silent=True) or {}).get('reason','')),vet.identifier(relation_id)))
        row=q.fetchone()
        if not row:raise vet.VeterinaryError('Relación activa no encontrada',404)
        q.execute('''UPDATE nextris.tbviewer_share_link sl SET revoked=true,revoked_at=now()
            FROM nextris.tbuser_patient up WHERE sl.portal_account_id=up.guid AND up.responsible_party_id=%s AND sl.patient_id=%s''',(row['responsible_id'],row['patient_id']))
        q.execute('''UPDATE nextris.tb_viewer_handoff h SET consumed_at=now() FROM nextris.tbuser_patient up
            WHERE h.user_id=up.guid AND up.responsible_party_id=%s AND h.study_iuid IN
            (SELECT studyinstanceuid FROM nextris.tbexamination WHERE idpatient=%s)''',(row['responsible_id'],row['patient_id']))
    return reply(message='Relación finalizada. Historial conservado y acceso revocado.')


@blueprint.route('/patients/<patient_id>/history',methods=['GET','POST'])
@staff('patients.view')
def history(patient_id):
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        vet.animal(q,patient_id)
        if request.method=='GET':
            q.execute('SELECT * FROM nextris.patient_clinical_entry WHERE patient_id=%s ORDER BY recorded_at DESC,created_at DESC',(patient_id,))
            return reply(q.fetchall())
        from apps.api.permissions import user_has_permission_code
        if not user_has_permission_code(get_jwt_identity(),'veterinary.history.manage'):
            raise vet.VeterinaryError('No tiene permiso para registrar antecedentes',403)
        return reply(vet.add_clinical_entry(q,patient_id,request.get_json(silent=True) or {},get_jwt_identity()),status=201)


@blueprint.route('/protocols',methods=['GET','POST'])
@blueprint.route('/protocols/<protocol_id>',methods=['PUT'])
@staff('patients.view')
def protocols(protocol_id=None):
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        if request.method=='GET':
            q.execute('SELECT * FROM nextris.veterinary_protocol WHERE is_active ORDER BY name')
            return reply(q.fetchall())
        from apps.api.permissions import user_has_permission_code
        if not user_has_permission_code(get_jwt_identity(),'veterinary.protocols.manage'):
            raise vet.VeterinaryError('No tiene permiso para administrar protocolos',403)
        d=request.get_json(silent=True) or {};name=str(d.get('name','')).strip()
        if not name:raise vet.VeterinaryError('Nombre de protocolo requerido')
        low=vet.weight(d.get('min_weight_kg'),allow_zero=True);high=vet.weight(d.get('max_weight_kg'))
        if low and high and low>high:raise vet.VeterinaryError('Rango de peso inválido')
        checklist=d.get('checklist',[])
        if not isinstance(checklist,list) or any(not isinstance(s,str) for s in checklist):raise vet.VeterinaryError('Checklist inválido')
        values=(name,d.get('species_id') or None,d.get('study_type_id') or None,d.get('modality_id') or None,d.get('bodypart_id') or None,low,high,str(d.get('preparation','')),Json(checklist))
        if protocol_id:
            q.execute('''UPDATE nextris.veterinary_protocol SET name=%s,species_id=%s,study_type_id=%s,modality_id=%s,bodypart_id=%s,min_weight_kg=%s,max_weight_kg=%s,preparation=%s,checklist=%s,updated_at=now(),is_active=%s WHERE id=%s RETURNING *''',values+(vet.flag(d.get('is_active'),True),vet.identifier(protocol_id)))
        else:
            q.execute('''INSERT INTO nextris.veterinary_protocol(name,species_id,study_type_id,modality_id,bodypart_id,min_weight_kg,max_weight_kg,preparation,checklist,id,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',values+(str(uuid.uuid4()),str(get_jwt_identity())))
        return reply(q.fetchone(),status=200 if protocol_id else 201)


@blueprint.route('/patients/<patient_id>/orders',methods=['GET','POST'])
@staff('patients.view')
def orders(patient_id,payload=None):
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        vet.animal(q,patient_id)
        if request.method=='GET':
            q.execute('''SELECT e.guid,e.localacc,e.createdon,e.studyinstanceuid,e.isreported,e.workflow_state,e.veterinary_context,
                st.description AS study_type FROM nextris.tbexamination e LEFT JOIN nextris.isstudytype st ON st.guid=e.studytype_id WHERE e.idpatient=%s ORDER BY createdon DESC''',(patient_id,))
            return reply(q.fetchall())
        from apps.api.permissions import user_has_permission_code
        if not user_has_permission_code(get_jwt_identity(),'admissions.create_spontaneous'):
            raise vet.VeterinaryError('No tiene permiso para crear órdenes',403)
        d=payload or request.get_json(silent=True) or {};study=d.get('study_type_id') or None;protocol=d.get('protocol_id') or None
        context=vet.protocol_context(q,patient_id,protocol,study)
        if not study:raise vet.VeterinaryError('Seleccione el tipo de estudio')
        key=str(uuid.uuid4());accession='VT'+uuid.uuid4().hex[:12].upper()
        from pydicom.uid import generate_uid
        study_uid=generate_uid()
        q.execute('''INSERT INTO nextris.tbexamination(guid,idpatient,studytype_id,localacc,admisionnumber,studyinstanceuid,
            history,clinicalquestion,requestingphysician_name,"w-order",veterinary_protocol_id,veterinary_context)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s)''',
                (key,patient_id,study,accession,accession,study_uid,d.get('history',''),d.get('clinical_question',''),d.get('requesting_veterinarian',''),protocol,Json(context)))
        q.execute('INSERT INTO nextris.tbreport(guid,idexamination,idpatient) VALUES(%s,%s,%s)',(str(uuid.uuid4()),key,patient_id))
        if d.get('scheduled_start'):
            if not d.get('scheduled_end'):raise vet.VeterinaryError('Indique el fin del turno')
            from datetime import datetime
            try:
                start=datetime.fromisoformat(d['scheduled_start']);end=datetime.fromisoformat(d['scheduled_end'])
                if end<=start:raise ValueError()
            except (ValueError,TypeError):raise vet.VeterinaryError('Horario de turno inválido')
            q.execute('''INSERT INTO nextris.tbagendaevents(guid,comienzo,fin,idpatient,idexam,title,medico_solicitante,veterinary_protocol_id,veterinary_context)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',(str(uuid.uuid4()),start,end,patient_id,key,context['name'],d.get('requesting_veterinarian',''),protocol,Json(context)))
        return reply({'guid':key,'accession_number':accession,'study_instance_uid':study_uid,'veterinary_context':context},status=201)


@blueprint.route('/portal/profile',methods=['GET','PUT'])
@portal
def profile():
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        if request.method=='PUT':
            d=request.get_json(silent=True) or {};account=vet.responsible_account(q,get_jwt_identity())
            from apps.services.patient_email_verification import normalize_email,VerificationError
            try:email=normalize_email(d.get('email',account['email']))
            except VerificationError as error:raise vet.VeterinaryError(str(error),error.status)
            q.execute('UPDATE nextris.responsible_party SET email=%s,phone=%s,address=%s,updated_at=now() WHERE id=%s',
                (email,d.get('phone',account['phone']),d.get('address',account['address']),account['responsible_party_id']))
            if email!=account['email']:
                q.execute('''UPDATE nextris.tbuser_patient SET verified_email=NULL,email_code_hash=NULL,email_code_address=NULL,
                    email_code_expires=NULL WHERE responsible_party_id=%s''',(account['responsible_party_id'],))
        return reply(portal_user(vet.responsible_account(q,get_jwt_identity())))


@blueprint.route('/templates',methods=['GET','POST'])
@blueprint.route('/templates/<template_id>',methods=['PUT'])
@staff('templates.manage')
def templates(template_id=None):
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        if request.method=='GET':
            q.execute("SELECT guid,tittle AS title,studytype_id AS study_type_id,species_id,study_reason,content,conclusion FROM nextris.tbinfpredef WHERE patient_kind IN ('animal','any') ORDER BY tittle")
            return reply(q.fetchall())
        d=request.get_json(silent=True) or {};title=str(d.get('title','')).strip()
        if not title or not d.get('study_type_id'):raise vet.VeterinaryError('Título y tipo de estudio requeridos')
        key=template_id or str(uuid.uuid4())
        values=(title,d['study_type_id'],d.get('species_id') or None,str(d.get('study_reason','')),str(d.get('content','')),str(d.get('conclusion','')))
        if template_id:
            q.execute("UPDATE nextris.tbinfpredef SET tittle=%s,studytype_id=%s,species_id=%s,study_reason=%s,content=%s,conclusion=%s WHERE guid=%s AND patient_kind IN ('animal','any') RETURNING guid",values+(key,))
            if not q.fetchone():raise vet.VeterinaryError('Plantilla no encontrada',404)
        else:
            q.execute("INSERT INTO nextris.tbinfpredef(tittle,studytype_id,species_id,study_reason,content,conclusion,guid,patient_kind,report_type) VALUES(%s,%s,%s,%s,%s,%s,%s,'animal','simple')",values+(key,))
        return reply({'guid':key},status=200 if template_id else 201)


def portal_user(account):
    return dict(id=str(account['guid']),username=account['username'],name=account['name'],surname='',email=account['email'] or '',phone=account['phone'] or '',address=account['address'] or '',
        user_type='patient',portal_subject='responsible',requires_password_change=bool(account['firstlogin']),permissions=[])


@blueprint.route('/portal/animals',methods=['GET'])
@portal
def my_animals():
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        q.execute('''SELECT DISTINCT pr.patient_id FROM nextris.patient_responsibility pr
            JOIN nextris.tbuser_patient up ON up.responsible_party_id=pr.responsible_id
            WHERE up.guid=%s AND pr.portal_authorized AND pr.valid_from<=now() AND (pr.valid_to IS NULL OR pr.valid_to>now())''',(str(get_jwt_identity()),))
        ids=[r['patient_id'] for r in q.fetchall()];animals=[]
        for key in ids:
            item=vet.animal_dict(q,key);item.pop('responsibles',None)
            q.execute("SELECT count(*) AS count FROM nextris.tbexamination WHERE idpatient=%s AND COALESCE(hidden_in_portal,0)=0 AND COALESCE(workflow_state,'')<>'cancelled'",(key,))
            item['study_count']=q.fetchone()['count'];animals.append(item)
        return reply(animals)


@blueprint.route('/portal/animals/<patient_id>/studies',methods=['GET'])
@portal
def my_studies(patient_id):
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        if not vet.can_access_animal(q,get_jwt_identity(),patient_id):raise vet.VeterinaryError('Animal no encontrado',404)
        q.execute('''SELECT e.guid,e.createdon,e.localacc,e.isreported,st.description AS study_type,
            (nextris.available_study_for_exam(e.guid) IS NOT NULL) AS has_images
            FROM nextris.tbexamination e LEFT JOIN nextris.isstudytype st ON st.guid=e.studytype_id
            WHERE e.idpatient=%s AND COALESCE(e.hidden_in_portal,0)=0 AND COALESCE(e.workflow_state,'')<>'cancelled' ORDER BY e.createdon DESC''',(patient_id,))
        return reply(q.fetchall())


@blueprint.route('/portal/reports/<exam_id>',methods=['GET'])
@blueprint.route('/portal/reports/<exam_id>/pdf',methods=['GET'])
@portal
def my_report(exam_id):
    from apps.services.report_view_service import resolve_report_view
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        vet.assert_portal_exam(q,get_jwt_identity(),exam_id)
        data=resolve_report_view(exam_id,connection=c)
        if request.path.endswith('/pdf'):
            from apps.services.report_pdf_service import render_report_pdf
            from flask import Response
            return Response(render_report_pdf(exam_id,view=data).content,mimetype='application/pdf',headers={'Cache-Control':'no-store'})
        return reply(data)


@blueprint.route('/portal/images/<exam_id>',methods=['POST'])
@portal
def my_images(exam_id):
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        return reply(vet.portal_share(q,get_jwt_identity(),exam_id))


def login_responsible(data):
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        q.execute('''SELECT up.guid,up.password FROM nextris.tbuser_patient up JOIN nextris.responsible_party rp ON rp.id=up.responsible_party_id WHERE lower(up.username)=%s''',(str(data.get('username','')).strip().lower(),))
        row=q.fetchone()
        if not row:
            return None
        if not check_password_hash(row['password'],str(data.get('password',''))):
            raise vet.VeterinaryError('Credenciales inválidas',401)
        account=vet.responsible_account(q,row['guid'])
        if not account['is_active'] or str(account['status']).lower() not in ('active','activo','true','1'):
            raise vet.VeterinaryError('Credenciales inválidas',401)
        return token_response(account)


def token_response(account, session_id=None):
    claims={'user_type':'patient','portal_subject':'responsible','username':account['username'],'auth_session_id':session_id or str(uuid.uuid4()),'portal_auth_version':account['portal_auth_version']}
    return reply({'access_token':create_access_token(identity=str(account['guid']),additional_claims=claims),
                  'refresh_token':create_refresh_token(identity=str(account['guid']),additional_claims=claims),'user':portal_user(account)})


def patient_dispatch():
    """Extend existing patient resources, keeping human endpoints and payloads unchanged."""
    from apps.api.permissions import user_has_permission_code
    verify_jwt_in_request()
    permission='patients.view' if request.method=='GET' else 'patients.manage'
    if get_jwt().get('user_type','').lower()=='patient' or not user_has_permission_code(get_jwt_identity(),permission):
        raise vet.VeterinaryError('Acceso denegado',403)
    patient_id=(request.view_args or {}).get('guid')
    with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
        if request.method in ('POST','PUT'):
            result=vet.save_animal(q,request.get_json(silent=True),get_jwt_identity(),patient_id)
            return reply(result,'Animal actualizado' if patient_id else 'Animal creado',200 if patient_id else 201)
        if patient_id:return reply(vet.animal_dict(q,patient_id))
        term='%'+request.args.get('search','').strip()+'%'
        try:page=max(1,int(request.args.get('page',1)));per=min(100,max(1,int(request.args.get('per_page',10))))
        except ValueError:raise vet.VeterinaryError('Paginación inválida')
        query="FROM nextris.datapatient p WHERE patient_kind='animal' AND (p.name ILIKE %s OR p.patientid ILIKE %s OR EXISTS(SELECT 1 FROM nextris.patient_responsibility pr JOIN nextris.responsible_party rp ON rp.id=pr.responsible_id WHERE pr.patient_id=p.guid AND pr.valid_to IS NULL AND (rp.name ILIKE %s OR rp.document ILIKE %s)))"
        args=(term,term,term,term)
        q.execute('SELECT count(*) AS count '+query,args);total=q.fetchone()['count']
        q.execute('SELECT p.guid '+query+' ORDER BY p.name,p.guid LIMIT %s OFFSET %s',args+(per,(page-1)*per))
        ids=[r['guid'] for r in q.fetchall()]
        return reply({'data':[vet.animal_dict(q,key) for key in ids],'page':page,'per_page':per,'total':total})
