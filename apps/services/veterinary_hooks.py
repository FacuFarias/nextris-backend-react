"""Connect veterinary services to existing routes without changing human contracts."""
from flask import jsonify, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity
from psycopg2 import IntegrityError, DataError
from psycopg2.extras import RealDictCursor
from apps.services import veterinary as vet


def register_veterinary(app):
    vet.mode()  # Refuse an invalid mode at startup.
    if vet.mode()=='veterinary':
        with vet.database() as c,c.cursor() as q:
            q.execute("SELECT to_regclass('nextris.veterinary_schema_migration')")
            if not q.fetchone()[0]:
                raise RuntimeError('Apply deployment/migrate_veterinary.py before enabling veterinary mode')
            q.execute("SELECT 1 FROM nextris.veterinary_schema_migration WHERE version='20261106_veterinary'")
            if not q.fetchone():raise RuntimeError('Veterinary migration has not been applied')
    from apps.api import veterinary as api
    app.register_blueprint(api.blueprint)
    from apps.api.veterinary_uploads import blueprint as upload_blueprint
    app.register_blueprint(upload_blueprint)

    @app.errorhandler(vet.VeterinaryError)
    def domain_error(error):
        return jsonify(success=False,data=None,message=str(error)),error.status

    @app.before_request
    def veterinary_request():
        if vet.mode()!='veterinary' or not request.path.startswith('/api/'):
            return None
        if request.path.startswith('/api/veterinary/') and request.is_json and not isinstance(request.get_json(silent=True),dict):
            raise vet.VeterinaryError('Se requiere un objeto JSON')
        if request.path=='/api/auth/login' and request.method=='POST':
            data=request.get_json(silent=True) or {}
            if data.get('user_type')=='patient':
                return api.login_responsible(data)
        if request.headers.get('Authorization','').startswith('Bearer '):
            verify_jwt_in_request(optional=True,refresh=request.path=='/api/auth/refresh')
            claims=get_jwt()
            if claims.get('user_type','').lower()=='patient':
                with vet.database() as c,c.cursor(cursor_factory=RealDictCursor) as q:
                    account=vet.responsible_account(q,get_jwt_identity())
                if account:
                    if not account['is_active'] or str(account['status']).lower() not in ('active','activo','true','1'):
                        raise vet.VeterinaryError('Cuenta inactiva',403)
                    if claims.get('portal_auth_version',0)!=account['portal_auth_version']:
                        raise vet.VeterinaryError('La sesión venció; vuelva a ingresar',401)
                    allowed=request.path.startswith('/api/veterinary/portal/') or request.path.startswith('/api/patient-portal/email-verification/') or request.path in (
                        '/api/auth/me','/api/auth/refresh','/api/auth/logout','/api/auth/change-password','/api/auth/refresh-permissions','/api/patient-portal/change-password','/api/config/me/modules','/api/app-config','/api/health')
                    if not allowed:raise vet.VeterinaryError('El portal no permite acceder a APIs del personal',403)
                    if request.path=='/api/auth/me':return api.reply(api.portal_user(account))
                    if request.path=='/api/auth/refresh-permissions':return api.reply(api.portal_user(account))
                    if request.path=='/api/auth/refresh':return api.token_response(account, session_id=claims.get('auth_session_id'))
                    if request.path=='/api/config/me/modules':
                        from apps.permission_policy import DISABLED_MODULES
                        return api.reply({'module_codes':['patient_portal'],'disabled_modules':sorted(DISABLED_MODULES),'facility_ids':[]})
        if request.endpoint in ('api.get_patients','api.get_patient','api.create_patient','api.create_patient_quick','api.update_patient'):
            try:return api.patient_dispatch()
            except (IntegrityError,DataError):raise vet.VeterinaryError('Referencia veterinaria inválida o identificador duplicado',409)
        if request.endpoint=='api.create_worklist' and request.method=='POST':
            verify_jwt_in_request()
            data=request.get_json(silent=True) or {};created=[]
            if not data.get('patientId') or not data.get('exams'):raise vet.VeterinaryError('Animal y estudios requeridos')
            for item in data['exams']:
                response,status=api.orders(data['patientId'],payload={'study_type_id':item.get('studyTypeId'),'protocol_id':item.get('protocolId'),'clinical_question':item.get('clinicalQuestion','')})
                if status!=201:return response,status
                created.append(response.get_json()['data']['guid'])
            return jsonify(success=True,created_exams=created,total_created=len(created),total_requested=len(created),data={'created_exams':created}),200
        if request.endpoint=='api.update_examination_report' and request.is_json:
            data=request.get_json(silent=True) or {}
            template=data.get('template_id',data.get('applied_template_id'))
            if template:
                verify_jwt_in_request()
                with vet.database() as c,c.cursor() as q:
                    q.execute('''SELECT 1 FROM nextris.tbinfpredef t JOIN nextris.tbexamination e ON e.guid=%s
                        JOIN nextris.datapatient p ON p.guid=e.idpatient
                        WHERE t.guid=%s AND p.patient_kind='animal' AND t.patient_kind IN ('animal','any')
                        AND (t.species_id IS NULL OR t.species_id=p.species_id)
                        AND (t.studytype_id IS NULL OR t.studytype_id=e.studytype_id)''',
                        ((request.view_args or {}).get('exam_id'),vet.identifier(template)))
                    if not q.fetchone():raise vet.VeterinaryError('Plantilla incompatible con el animal o estudio')
        if request.endpoint in ('api.create_predefined_report','api.update_predefined_report'):
            verify_jwt_in_request()
            from apps.api.permissions import user_has_permission_code
            if not user_has_permission_code(get_jwt_identity(),'templates.manage'):
                raise vet.VeterinaryError('No tiene permiso para gestionar plantillas',403)
        if request.endpoint in ('api.merge_patients','api.delete_patient','api.create_user_for_patient'):
            verify_jwt_in_request()
            raise vet.VeterinaryError('La identidad y el historial veterinario se conservan; esta operación no está disponible',409)

    @app.after_request
    def veterinary_response(response):
        if request.path=='/api/app-config' and request.method=='GET' and response.status_code==200 and response.is_json:
            data=response.get_json()
            if isinstance(data.get('data'),dict):
                data['data']['patient_mode']=vet.mode()
                import os
                data['data']['mwl_enabled']=os.getenv('NEXTRIS_MWL_ENABLED','false').lower()=='true' if vet.mode()=='veterinary' else None
                response.set_data(app.json.dumps(data))
        return response
