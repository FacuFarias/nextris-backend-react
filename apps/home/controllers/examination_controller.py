"""
Controlador de exámenes para el sistema RIS
Maneja rutas relacionadas con gestión de exámenes médicos
"""

from flask import jsonify, request
from apps.home import blueprint
from apps.home.services import DatabaseService, HL7Service
from apps.home.controllers.admin_controller import updatestatus
import pytz
from datetime import datetime, timedelta


@blueprint.route('/get_examination_details', methods=['POST'])
def get_examination_details():
    """Obtiene detalles de un examen específico"""
    try:
        data = request.get_json()
        exam_guid = data.get('id')
        
        if not exam_guid:
            return jsonify({'error': 'No se proporcionó el ID del examen'}), 400

        exam_data = DatabaseService.get_examination_by_guid(exam_guid)
        if not exam_data:
            return jsonify({'error': 'Examen no encontrado'}), 404

        # Obtener información adicional
        study_type_desc = DatabaseService.get_study_type_description(exam_data[1])
        patient_info = DatabaseService.get_patient_by_id(exam_data[2])
        
        result = {
            'guid': exam_data[0],
            'study_type': study_type_desc,
            'patient_id': exam_data[2],
            'patient_name': f"{patient_info[2]} {patient_info[1]}" if patient_info else "",
            'status': exam_data[5],
            'created_on': exam_data[6].strftime('%d/%m/%Y %H:%M') if exam_data[6] else None,
            'is_reported': exam_data[7],
            'study_instance_uid': exam_data[9]
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/get_examinations', methods=['GET'])
def get_examinations():
    """Obtiene lista de todos los exámenes"""
    try:
        query = """
            SELECT Guid, CreatedOn, IdPatient, LocalAcc, studytype_id, 
                   Status, IdSeverity, IdReferringPhysician 
            FROM nextris.tbexamination
            ORDER BY CreatedOn DESC
            LIMIT 1000
        """
        
        datos = DatabaseService.execute_query(query)
        to_send = []

        for dato in datos:
            # Obtener información adicional para cada examen
            est = DatabaseService.get_study_type_description(dato[4])
            sev = DatabaseService.get_severity_description(dato[6])
            mref = DatabaseService.get_user_by_guid(dato[7])
            patient_info = DatabaseService.get_patient_by_id(dato[2])
            
            nombre = f"{patient_info[2]} {patient_info[1]}" if patient_info else ''
            dni = patient_info[3] if patient_info else ''
            sex = patient_info[4] if patient_info else ''

            fila = [dato[0], dato[1], nombre, dni, sex, est, dato[5], sev, mref]
            to_send.append(fila)

        return jsonify(to_send)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/get_examination_items_filtrado', methods=['POST'])
def get_examination_items_filtrado():
    """Obtiene exámenes filtrados según criterios específicos (con opción de incluir reportados) y por ubicaciones del usuario"""
    try:
        from flask import session
        
        data = request.get_json()
        filters = data.get('filters', {})
        include_reported = data.get('include_reported', False)
        
        # Obtener ubicaciones del usuario
        user_id = session.get('_user_id')
        if not user_id:
            return jsonify({'error': 'Usuario no autenticado'}), 401
        
        query_locations = """
            SELECT location_id 
            FROM nextris.rel_user_location 
            WHERE user_id = %s
        """
        user_locations = DatabaseService.execute_query(query_locations, (user_id,))
        
        if not user_locations:
            print(f"[WARNING] Usuario {user_id} no tiene ubicaciones asignadas en get_examination_items_filtrado")
            return jsonify([])
        
        location_ids = [loc[0] for loc in user_locations]
        print(f"[DEBUG get_examination_items_filtrado] Usuario {user_id} tiene {len(location_ids)} ubicaciones")
        
        # Construir query dinámicamente basado en filtros
        base_query = """
            SELECT tbex.guid, tbex.createdon, tbex.idpatient, tbex.localacc,
                   tbex.studytype_id, tbex.Status, tbex.idseverity,
                   COALESCE(tbex.isreported, 0) as isreported,
                   COALESCE(tbex.isimage, 0) as isimage
            FROM nextris.tbexamination tbex
            INNER JOIN nextris.isequipment eq ON eq.Guid = tbex.IdEquipment
            WHERE eq.location_id = ANY(%s)
        """
        
        # Aplicar filtro de reportados solo si NO se solicita incluirlos
        if not include_reported:
            base_query += " AND (tbex.isreported IS NULL OR tbex.isreported != 1)"
        
        conditions = []
        params = [location_ids]
        
        if filters.get('status'):
            conditions.append("tbex.Status = %s")
            params.append(filters['status'])
            
        if filters.get('date_from'):
            conditions.append("tbex.createdon >= %s")
            params.append(filters['date_from'])
            
        if filters.get('date_to'):
            conditions.append("tbex.createdon <= %s")
            params.append(filters['date_to'])
            
        if filters.get('study_type'):
            conditions.append("tbex.studytype_id = %s")
            params.append(filters['study_type'])

        if conditions:
            base_query += " AND " + " AND ".join(conditions)
            
        base_query += " ORDER BY tbex.createdon DESC LIMIT 500"
        
        datos = DatabaseService.execute_query(base_query, params)
        to_send = []

        for dato in datos:
            est = DatabaseService.get_study_type_description(dato[4])
            sev = DatabaseService.get_severity_description(dato[6])
            patient_info = DatabaseService.get_patient_by_id(dato[2])
            
            nombre = f"{patient_info[2]} {patient_info[1]}" if patient_info else ''
            dni = patient_info[3] if patient_info else ''
            sex = patient_info[4] if patient_info else ''
            isreported = dato[7] if len(dato) > 7 else 0
            isimage = dato[8] if len(dato) > 8 else 0

            fila = [dato[0], dato[1], nombre, dni, sex, est, dato[5], sev, isreported, isimage]
            to_send.append(fila)

        return jsonify(to_send)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/get_examination_items_asignados', methods=['POST'])
def get_examination_items_asignados():
    """Obtiene exámenes asignados a un usuario específico (con opción de incluir reportados) y filtrados por ubicaciones del usuario"""
    try:
        from flask import session
        
        data = request.get_json()
        user_guid = data.get('user_guid')
        include_reported = data.get('include_reported', False)
        
        if not user_guid:
            return jsonify({'error': 'No se proporcionó el GUID del usuario'}), 400
        
        # Obtener ubicaciones del usuario de sesión
        user_id = session.get('_user_id')
        if not user_id:
            return jsonify({'error': 'Usuario no autenticado'}), 401
        
        query_locations = """
            SELECT location_id 
            FROM nextris.rel_user_location 
            WHERE user_id = %s
        """
        user_locations = DatabaseService.execute_query(query_locations, (user_id,))
        
        if not user_locations:
            print(f"[WARNING] Usuario {user_id} no tiene ubicaciones asignadas en get_examination_items_asignados")
            return jsonify([])
        
        location_ids = [loc[0] for loc in user_locations]
        print(f"[DEBUG get_examination_items_asignados] Usuario {user_id} - {len(location_ids)} ubicaciones")

        # Construir query con filtro condicional y filtro de ubicación
        query = """
            SELECT tbex.guid, tbex.createdon, tbex.idpatient, tbex.localacc,
                   tbex.studytype_id, tbex.Status, tbex.idseverity,
                   COALESCE(tbex.isreported, 0) as isreported,
                   COALESCE(tbex.isimage, 0) as isimage
            FROM nextris.tbexamination tbex
            INNER JOIN nextris.isequipment eq ON eq.Guid = tbex.IdEquipment
            WHERE tbex.assignto = %s AND eq.location_id = ANY(%s)
        """
        
        # Aplicar filtro de reportados solo si NO se solicita incluirlos
        if not include_reported:
            query += " AND (tbex.isreported IS NULL OR tbex.isreported != 1)"
        
        query += " ORDER BY tbex.createdon DESC"
        
        datos = DatabaseService.execute_query(query, (user_guid, location_ids))
        to_send = []

        for dato in datos:
            est = DatabaseService.get_study_type_description(dato[4])
            sev = DatabaseService.get_severity_description(dato[6])
            patient_info = DatabaseService.get_patient_by_id(dato[2])
            
            nombre = f"{patient_info[2]} {patient_info[1]}" if patient_info else ''
            dni = patient_info[3] if patient_info else ''
            sex = patient_info[4] if patient_info else ''
            isreported = dato[7] if len(dato) > 7 else 0
            isimage = dato[8] if len(dato) > 8 else 0

            fila = [dato[0], dato[1], nombre, dni, sex, est, dato[5], sev, isreported, isimage]
            to_send.append(fila)

        return jsonify(to_send)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/crear_worklist', methods=['POST'])
def crear_worklist():
    """Crea elementos en el worklist DICOM"""
    try:
        data = request.get_json()
        patient_id = data.get('patientId')
        exams = data.get('exams', [])
        print("Data received for crear_worklist a ver que onda:", data)
        
        if not patient_id or not exams:
            return jsonify({'error': 'Datos incompletos'}), 400

        # Obtener datos del paciente
        patient_data = DatabaseService.get_patient_by_guid(patient_id)
        if not patient_data:
            return jsonify({'error': 'Paciente no encontrado'}), 404

        # Obtener último número de admisión y acceso
        query_last_adm = "SELECT MAX(CAST(SUBSTRING(AdmisionNumber, 4) AS INTEGER)) FROM nextris.tbexamination WHERE AdmisionNumber LIKE 'ADM%'"
        last_adm = DatabaseService.execute_query(query_last_adm, fetch_one=True)
        
        query_last_acc = "SELECT MAX(CAST(SUBSTRING(LocalAcc, 4) AS INTEGER)) FROM nextris.tbexamination WHERE LocalAcc LIKE 'ACC%'"
        last_acc = DatabaseService.execute_query(query_last_acc, fetch_one=True)
        
        parte_numerica_adm = str(last_adm[0]) if last_adm and last_adm[0] else "000"
        parte_numerica_acc = str(last_acc[0]) if last_acc and last_acc[0] else "000"
        
        NewAdm = f"ADM{int(parte_numerica_adm) + 1:03d}"
        contador = 0
        success_count = 0

        DatabaseService.set_timezone()

        for exam in exams:
            try:
                newAcc = f"ACC{int(parte_numerica_acc) + 1 + contador:03d}"
                contador += 1

                examId = exam['examId']
                equipo = exam['equip']

                # Obtener datos del equipo y modalidad
                equipo_data = DatabaseService.get_equipment_by_guid(equipo)
                if not equipo_data:
                    continue

                query_modality = "SELECT Guid, ExternalCode FROM nextris.ismodality WHERE Guid = %s"
                modalidad = DatabaseService.execute_query(query_modality, (equipo_data[3],), fetch_one=True)
                
                exam_desc = DatabaseService.get_study_type_description(examId)

                # Enviar a worklist HL7
                study_instance_uid, hl7_success = HL7Service.send_exam_to_worklist(
                    patient_data, exam_desc, equipo_data, modalidad[1] if modalidad else "",
                    NewAdm, newAcc
                )

                if hl7_success:
                    # Insertar en tbexamination
                    insert_query = """
                        INSERT INTO nextris.tbexamination (
                            Guid, StudyInstanceUID, IdPatient, StudyType_Id, IdEquipment,
                            AdmisionNumber, LocalAcc, createdon, Status, IsExecuted
                        ) VALUES (
                            uuid_generate_v4(), %s, %s, %s, %s, %s, %s, NOW(), 'A', 0
                        )
                    """
                    
                    DatabaseService.execute_query(
                        insert_query, 
                        (study_instance_uid, patient_data[0], examId, equipo, NewAdm, newAcc),
                        commit=True
                    )
                    
                    # Obtener el GUID del examen recién creado
                    query_guid = "SELECT Guid FROM nextris.tbexamination WHERE AdmisionNumber = %s"
                    exam_guid_result = DatabaseService.execute_query(query_guid, (NewAdm,), fetch_one=True)
                    
                    if exam_guid_result:
                        exam_guid = exam_guid_result[0]
                        
                        # Crear fila en tbReport - SUMAMENTE IMPORTANTE
                        insert_report_query = """
                            INSERT INTO nextris.tbReport(
                                Guid, admnumber, idexamination, IdPatient, Date
                            ) VALUES (
                                uuid_generate_v4(), %s, %s, %s, NOW()
                            )
                        """
                        
                        DatabaseService.execute_query(
                            insert_report_query,
                            (NewAdm, exam_guid, patient_data[0]),
                            commit=True
                        )
                        
                        print(f"[SUCCESS] tbReport creado para examen {exam_guid} con admisión {NewAdm}")
                    else:
                        print(f"[ERROR] No se pudo obtener GUID del examen con admisión {NewAdm}")
                    
                    success_count += 1

            except Exception as e:
                print(f"Error procesando examen {exam.get('examId', 'unknown')}: {e}")
                continue

        return jsonify({
            "success": True, 
            "message": f"Se crearon {success_count} de {len(exams)} exámenes en el worklist"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/cancelar_worklist', methods=['POST'])
def cancelar_worklist():
    """Cancela un elemento del worklist"""
    try:
        data = request.get_json()
        exam_id = data.get('id')
        
        if not exam_id:
            return jsonify({'error': 'No se proporcionó el ID del examen'}), 400

        # Obtener información del examen
        query = "SELECT IdPatient, StudyInstanceUID FROM nextris.tbexamination WHERE Guid = %s"
        order = DatabaseService.execute_query(query, (exam_id,), fetch_one=True)
        
        if not order:
            return jsonify({'error': 'Examen no encontrado'}), 404

        # Enviar mensaje de cancelación HL7
        cancel_success = HL7Service.cancel_worklist_item(order[0], order[1])
        
        if cancel_success:
            # Actualizar estado en base de datos
            update_query = "UPDATE nextris.tbexamination SET IsExecuted = 1, Status = 'Cancelled' WHERE Guid = %s"
            DatabaseService.execute_query(update_query, (exam_id,), commit=True)
            
            return jsonify({"success": True, "message": "Examen cancelado correctamente"})
        else:
            return jsonify({"error": "Error al cancelar el examen en el worklist"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/get_orders_ex', methods=['GET'])
def get_orders_ex():
    """Obtiene órdenes de exámenes pendientes filtradas por ubicaciones del usuario"""
    try:
        from flask import session
        
        # Obtener el usuario de la sesión
        user_id = session.get('_user_id')
        if not user_id:
            return jsonify({'error': 'Usuario no autenticado'}), 401
        
        # Obtener las ubicaciones del usuario
        query_locations = """
            SELECT location_id 
            FROM nextris.rel_user_location 
            WHERE user_id = %s
        """
        user_locations = DatabaseService.execute_query(query_locations, (user_id,))
        
        if not user_locations:
            print(f"[WARNING] Usuario {user_id} no tiene ubicaciones asignadas en get_orders_ex")
            return jsonify([])
        
        location_ids = [loc[0] for loc in user_locations]
        print(f"[DEBUG get_orders_ex] Usuario {user_id} tiene {len(location_ids)} ubicaciones asignadas")
        
        query = """
            SELECT ex.Guid, ex.createdon, p.Surname, p.Name, exam.description,
                   ex.Status, equip.Description, ex.AdmisionNumber, ex.LocalAcc
            FROM nextris.tbexamination ex 
            INNER JOIN nextris.datapatient p ON ex.IdPatient = p.PatientId 
            INNER JOIN nextris.isstudytype exam ON exam.guid = ex.studytype_id
            INNER JOIN nextris.isequipment equip ON equip.Guid = ex.IdEquipment
            WHERE ex.IsExecuted = 0 AND equip.location_id = ANY(%s)
            ORDER BY ex.createdon DESC
        """
        
        results = DatabaseService.execute_query(query, (location_ids,))
        print(f"[DEBUG get_orders_ex] Se encontraron {len(results) if results else 0} órdenes pendientes")
        
        return jsonify(results)
        
    except Exception as e:
        print(f"[ERROR get_orders_ex] {str(e)}")
        return jsonify({"error": str(e)}), 500


@blueprint.route('/verificar_asignabilidad_estudio', methods=['POST'])
def verificar_asignabilidad_estudio():
    """Verifica si un estudio puede ser asignado a un médico"""
    try:
        data = request.get_json()
        medico_guid = data.get('medico_guid')
        estudio_tipo = data.get('estudio_tipo')
        
        if not medico_guid or not estudio_tipo:
            return jsonify({'error': 'Datos incompletos'}), 400

        # Verificar si el médico está autorizado para este tipo de estudio
        query = """
            SELECT COUNT(*) FROM nextris.tbmedico_estudio_grupo meg
            INNER JOIN nextris.isstudytype st ON meg.estudio_grupo_id = st.studygroup_id
            WHERE meg.medico_id = %s AND st.guid = %s
        """
        
        result = DatabaseService.execute_query(query, (medico_guid, estudio_tipo), fetch_one=True)
        
        can_assign = result[0] > 0 if result else False
        
        return jsonify({
            "can_assign": can_assign,
            "message": "Asignación permitida" if can_assign else "El médico no está autorizado para este tipo de estudio"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/get_exams_adm', methods=['GET'])
def get_exams_adm():
    """Obtiene lista de exámenes disponibles para administración"""
    try:
        print("[DEBUG] get_exams_adm endpoint called")
        
        # Consulta para obtener tipos de estudios/exámenes
        query = """
        SELECT st.guid, st.code, st.description, md.externalcode as modality, ap.description as bodypart, stg.description as studygroup 
        FROM nextris.isstudytype as st
        INNER JOIN nextris.isstudytypegroup stg on stg.guid=st.studygroup_id
        INNER JOIN nextris.isanatomicalpart ap on ap.guid=st.bodypart_id
        INNER JOIN nextris.ismodality md on md.guid=st.modality_id
        ORDER BY st.description ASC
        """
        
        result = DatabaseService.execute_query(query)
        print(f"[DEBUG] Query executed successfully, {len(result)} results found")
        
        examenes = []
        for row in result:
            examenes.append([
                row[0],  # guid
                row[1],  # code
                row[2],  # description
                row[3] if len(row) > 3 else None  # modality_id
                , row[4] if len(row) > 4 else None  # bodypart
                , row[5] if len(row) > 5 else None  # studygroup
            ])
        
        print(f"[DEBUG] Returning {len(examenes)} examenes")
        return jsonify(examenes)
        
    except Exception as e:
        print(f"[ERROR] Error getting exams_adm: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@blueprint.route('/get_lista_de_equipos', methods=['GET', 'POST']) 
def get_lista_de_equipos():
    """Obtiene lista de equipos, opcionalmente filtrados por location_id"""
    location_id = None
    
    # Aceptar location_id tanto por GET como por POST
    if request.method == 'POST':
        data = request.get_json()
        location_id = data.get('location_id') if data else None
    else:
        location_id = request.args.get('location_id')
    
    if location_id:
        print(f"[DEBUG get_lista_de_equipos] Filtrando por location_id: {location_id}")
        query = """
            SELECT guid, aetitle, description 
            FROM nextris.isequipment 
            WHERE location_id = %s AND isactive = true
            ORDER BY aetitle
        """
        result = DatabaseService.execute_query(query, (location_id,))
    else:
        print("[DEBUG get_lista_de_equipos] Sin filtro de ubicación")
        query = """
            SELECT guid, aetitle, description 
            FROM nextris.isequipment 
            WHERE isactive = true
            ORDER BY aetitle
        """
        result = DatabaseService.execute_query(query)
    
    print(f"[DEBUG get_lista_de_equipos] Equipos encontrados: {len(result) if result else 0}")
    return jsonify(result)

@blueprint.route('/get_equipos_por_modalidad', methods=['POST'])
def get_equipos_por_modalidad():
    """Obtiene lista de equipos filtrados por modalidad y location_id"""
    try:
        data = request.get_json()
        estudio_id = data.get('estudio_id')
        location_id = data.get('location_id')  # Obtener location_id del request
        
        if not estudio_id:
            return jsonify({'error': 'ID del estudio requerido'}), 400
        
        print(f"[DEBUG get_equipos_por_modalidad] estudio_id: {estudio_id}, location_id: {location_id}")
        
        # Primero obtener el modality_id del estudio seleccionado
        query_estudio = """
        SELECT modality_id 
        FROM nextris.isstudytype 
        WHERE guid = %s
        """
        resultado_estudio = DatabaseService.execute_query(query_estudio, (estudio_id,))
        
        if not resultado_estudio:
            print(f"[ERROR] No se encontró el estudio con ID: {estudio_id}")
            return jsonify({'error': 'Estudio no encontrado'}), 404
        
        modality_id = resultado_estudio[0][0]
        print(f"[DEBUG] Modality ID del estudio: {modality_id}")
        
        # Buscar equipos filtrando por modalidad Y location_id
        if location_id:
            query_equipos = """
            SELECT guid, aetitle, description
            FROM nextris.isequipment 
            WHERE idmodality = %s AND location_id = %s AND isactive = true
            ORDER BY aetitle ASC
            """
            result = DatabaseService.execute_query(query_equipos, (modality_id, location_id))
            print(f"[DEBUG] Filtrando equipos por modality_id: {modality_id} y location_id: {location_id}")
        else:
            query_equipos = """
            SELECT guid, aetitle, description
            FROM nextris.isequipment 
            WHERE idmodality = %s AND isactive = true
            ORDER BY aetitle ASC
            """
            result = DatabaseService.execute_query(query_equipos, (modality_id,))
            print(f"[DEBUG] Filtrando equipos solo por modality_id: {modality_id}")
        
        print(f"[DEBUG] Encontrados {len(result) if result else 0} equipos compatibles")
        
        equipos = []
        for row in result:
            equipos.append([
                row[0],  # guid
                row[1],  # aetitle
                row[2] if len(row) > 2 else None  # description
            ])
        
        return jsonify(equipos)
        
    except Exception as e:
        print(f"[ERROR] Error getting equipos por modalidad: {str(e)}")
        return jsonify({'error': str(e)}), 500

@blueprint.route('/debug_tables', methods=['GET'])
def debug_tables():
    """Endpoint temporal para verificar estructura de BD"""
    try:
        # Verificar qué tablas existen relacionadas con equipos
        query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE '%equip%' 
        ORDER BY table_name
        """
        tables = DatabaseService.execute_query(query)
        
        # También verificar columnas de isequipment
        query_columns = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'isequipment' 
        AND table_schema = 'public'
        ORDER BY ordinal_position
        """
        columns = DatabaseService.execute_query(query_columns)
        
        # Verificar un equipo de ejemplo
        query_sample = "SELECT * FROM nextris.isequipment LIMIT 2"
        sample = DatabaseService.execute_query(query_sample)
        
        return jsonify({
            'tables': [row[0] for row in tables],
            'columns': [(row[0], row[1]) for row in columns],
            'sample_data': [list(row) for row in sample]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@blueprint.route('/insertar_citas_per_equip', methods=['POST'])
def insertar_citas_per_equip():
    data = request.get_json()
    print(data)
    # Zona horaria local, ajusta esto según tu zona horaria
    local_tz = pytz.timezone("America/Argentina/Buenos_Aires")
    
    # Obtener location_id del request
    location_id = data.get('location_id')
    print("[DEBUG insertar_citas_per_equip] location_id recibido:", location_id)

    for exam in data['exams']:
        descrip = exam['title'][6:]
        print("descrip:", descrip)
        patient = data['patientId']
        print("examId:", exam['examId'])
        idexam = exam['examId']
        idequipment = exam['profesional']
        
        # Manejar medico_solicitante que puede no existir o estar vacío
        idmedsol = exam.get('medico_solicitante')
        if not idmedsol:
            idmedsol = None
        
        # Manejar el caso en que 'rads' no exista o sea vacío
        idrad = exam.get('rads')
        if not idrad:
            idrad = None
            
        print("idequipment:", idequipment)
        print("idmedsol:", idmedsol)
        print("idmedref:", idrad)

        # Quitar el sufijo .000Z antes de convertir
        init_str = exam['init'].replace('.000Z', '')
        finish_str = exam['finish'].replace('.000Z', '')

        # Convertir las horas a la zona horaria local y luego restar 3 horas
        init_local = local_tz.localize(datetime.strptime(init_str, '%Y-%m-%dT%H:%M:%S'))
        finish_local = local_tz.localize(datetime.strptime(finish_str, '%Y-%m-%dT%H:%M:%S'))

        init_adjusted = init_local - timedelta(hours=3)
        finish_adjusted = finish_local - timedelta(hours=3)

        # Convertir a formato ISO 8601
        init_str_adjusted = init_adjusted.strftime('%Y-%m-%dT%H:%M:%S')
        finish_str_adjusted = finish_adjusted.strftime('%Y-%m-%dT%H:%M:%S')

        # Preparar valores para la query (manejar None apropiadamente)
        idmedsol_sql = f"'{idmedsol}'" if idmedsol else 'NULL'
        idrad_sql = f"'{idrad}'" if idrad else 'NULL'
        location_id_sql = f"'{location_id}'" if location_id else 'NULL'

        query_events = f"""INSERT INTO nextris.tbagendaevents(guid,idequipment,idpatient,idexam,comienzo,fin,idmed,idmed_sol,location_id,createdon)
                            VALUES (uuid_generate_v4(),'{idequipment}','{patient}','{idexam}','{init_str_adjusted}','{finish_str_adjusted}',{idrad_sql},{idmedsol_sql},{location_id_sql}, NOW()) """
        print(query_events)
        result = DatabaseService.execute_query(query_events, commit=True)
    print(data)
    return jsonify({"success": True})


@blueprint.route('/insertar_citas_per_med', methods=['POST'])
def insertar_citas_per_med():
    """Insertar citas para agenda por médico"""
    data = request.get_json()
    print(data)
    # Zona horaria local, ajusta esto según tu zona horaria
    local_tz = pytz.timezone("America/Argentina/Buenos_Aires")
    
    # Obtener location_id del request
    location_id = data.get('location_id')
    print("[DEBUG insertar_citas_per_med] location_id recibido:", location_id)

    for exam in data['exams']:
        descrip = exam['title'][6:]
        print("descrip:", descrip)
        patient = data['patientId']
        print("examId:", exam['examId'])
        idexam = exam['examId']
        idmed = exam['profesional']  # En agenda por médico, profesional es el médico
        
        # Manejar medico_solicitante que puede no existir o estar vacío
        idmedsol = exam.get('medico_solicitante')
        if not idmedsol:
            idmedsol = None
        
        # Manejar el caso en que 'rads' no exista o sea vacío
        idrad = exam.get('rads')
        if not idrad:
            idrad = None
            
        print("idmed:", idmed)
        print("idmedsol:", idmedsol)
        print("idmedref:", idrad)

        # Quitar el sufijo .000Z antes de convertir
        init_str = exam['init'].replace('.000Z', '')
        finish_str = exam['finish'].replace('.000Z', '')

        # Convertir las horas a la zona horaria local y luego restar 3 horas
        init_local = local_tz.localize(datetime.strptime(init_str, '%Y-%m-%dT%H:%M:%S'))
        finish_local = local_tz.localize(datetime.strptime(finish_str, '%Y-%m-%dT%H:%M:%S'))

        init_adjusted = init_local - timedelta(hours=3)
        finish_adjusted = finish_local - timedelta(hours=3)

        # Convertir a formato ISO 8601
        init_str_adjusted = init_adjusted.strftime('%Y-%m-%dT%H:%M:%S')
        finish_str_adjusted = finish_adjusted.strftime('%Y-%m-%dT%H:%M:%S')

        # Preparar valores para la query (manejar None apropiadamente)
        idmedsol_sql = f"'{idmedsol}'" if idmedsol else 'NULL'
        idrad_sql = f"'{idrad}'" if idrad else 'NULL'
        location_id_sql = f"'{location_id}'" if location_id else 'NULL'

        # Para agenda por médico, usamos idmed en lugar de idequipment
        query_events = f"""INSERT INTO nextris.tbagendaevents(guid,idmed,idpatient,idexam,comienzo,fin,idmed_sol,location_id,createdon)
                            VALUES (uuid_generate_v4(),'{idmed}','{patient}','{idexam}','{init_str_adjusted}','{finish_str_adjusted}',{idmedsol_sql},{location_id_sql}, NOW()) """
        print(query_events)
        result = DatabaseService.execute_query(query_events, commit=True)
    print(data)
    return jsonify({"success": True})


@blueprint.route('/ejecutar_orden', methods=['POST']) 
def ejecutar_orden():
    """Ejecuta una orden de examen actualizando su estado y detalles"""
    try:
        data = request.get_json()
        data_id = data.get('id')
        
        def null_if_no_clasifica(val):
            return None if val == 'no clasifica' else val

        historia = null_if_no_clasifica(data.get('historia', ''))
        pregunta = null_if_no_clasifica(data.get('pregunta', ''))
        lateralidad = null_if_no_clasifica(data.get('lateralidad', ''))
        stat = data.get('stat', '')
        num_vistas = null_if_no_clasifica(data.get('num_vistas', ''))
        detalle_tecnico = null_if_no_clasifica(data.get('detalle_tecnico', ''))

        if not data_id:
            return jsonify({'success': False, 'error': 'No se proporcionó el ID'}), 400

        # Ejecutar query usando DatabaseService
        query = """
            UPDATE nextris.tbexamination
            SET IsExecuted = 1,
                history = %s,
                clinicalquestion = %s,
                laterality_id = %s,
                stat = %s::boolean,
                numberofviews = %s,
                othersdetails = %s
            WHERE Guid = %s
        """
        
        result = DatabaseService.execute_query(
            query, 
            (historia, pregunta, lateralidad, stat, num_vistas, detalle_tecnico, data_id),
            commit=True
        )
        
        # Actualizar estado
        status = updatestatus(data_id)

        return jsonify({'success': True, 'message': 'Orden ejecutada exitosamente'})
        
    except Exception as err:
        print(f"[ERROR] ejecutar_orden: {str(err)}")
        return jsonify({'success': False, 'error': str(err)}), 500


@blueprint.route('/get_examination_items', methods=['GET']) 
def get_examination_items():
    """Obtiene todos los elementos de exámenes NO reportados (isreported != 1) filtrados por ubicaciones del usuario"""
    try:
        from flask import session
        
        # Obtener ubicaciones del usuario
        user_id = session.get('_user_id')
        if not user_id:
            return jsonify({'error': 'Usuario no autenticado'}), 401
        
        query_locations = """
            SELECT location_id 
            FROM nextris.rel_user_location 
            WHERE user_id = %s
        """
        user_locations = DatabaseService.execute_query(query_locations, (user_id,))
        
        if not user_locations:
            print(f"[WARNING] Usuario {user_id} no tiene ubicaciones asignadas en get_examination_items")
            return jsonify([])
        
        location_ids = [loc[0] for loc in user_locations]
        print(f"[DEBUG get_examination_items] Usuario {user_id} - {len(location_ids)} ubicaciones")
        
        query = """
            SELECT e.Guid, e.createdon, e.idpatient, e.localacc, e.studytype_id, 
                   e.Status, e.idseverity,
                   st.description as estudio_desc,
                   sev.Description as severidad_desc,
                   p.Surname, p.Name, p.NationalCode, p.SexCode,
                   COALESCE(e.isreported, 0) as isreported,
                   COALESCE(e.isimage, 0) as isimage
            FROM nextris.tbexamination e
            LEFT JOIN nextris.isstudytype st ON st.Guid = e.studytype_id
            LEFT JOIN nextris.IsSeverity sev ON sev.Guid = e.idseverity  
            LEFT JOIN nextris.datapatient p ON p.PatientId = e.idpatient
            INNER JOIN nextris.isequipment eq ON eq.Guid = e.IdEquipment
            WHERE p.PatientId IS NOT NULL
              AND (e.isreported IS NULL OR e.isreported != 1)
              AND eq.location_id = ANY(%s)
        """
        
        results = DatabaseService.execute_query(query, (location_ids,))
        
        to_send = []
        for dato in results:
            # dato: [Guid, createdon, idpatient, localacc, studytype_id, Status, idseverity, estudio_desc, severidad_desc, Surname, Name, NationalCode, SexCode, isreported, isimage]
            nombre = f"{dato[10]} {dato[9]}" if dato[10] and dato[9] else "Sin nombre"
            dni = dato[11] if dato[11] else "Sin DNI"
            sex = dato[12] if dato[12] else "Sin especificar"
            estudio = dato[7] if dato[7] else "Sin especificar"
            severidad = dato[8] if dato[8] else "Sin especificar"
            isreported = dato[13] if len(dato) > 13 else 0
            isimage = dato[14] if len(dato) > 14 else 0
            
            fila = [dato[0], dato[1], nombre, dni, sex, estudio, dato[5], severidad, isreported, isimage]
            to_send.append(fila)
        
        return jsonify(to_send)
        
    except Exception as e:
        print(f"[ERROR] get_examination_items: {str(e)}")
        return jsonify({'error': str(e)}), 500


@blueprint.route('/get_examination_items_all', methods=['GET']) 
def get_examination_items_all():
    """Obtiene TODOS los elementos de exámenes (incluye reportados y no reportados) filtrados por ubicaciones del usuario"""
    try:
        from flask import session
        
        # Obtener ubicaciones del usuario
        user_id = session.get('_user_id')
        if not user_id:
            return jsonify({'error': 'Usuario no autenticado'}), 401
        
        query_locations = """
            SELECT location_id 
            FROM nextris.rel_user_location 
            WHERE user_id = %s
        """
        user_locations = DatabaseService.execute_query(query_locations, (user_id,))
        
        if not user_locations:
            print(f"[WARNING] Usuario {user_id} no tiene ubicaciones asignadas en get_examination_items_all")
            return jsonify([])
        
        location_ids = [loc[0] for loc in user_locations]
        print(f"[DEBUG get_examination_items_all] Usuario {user_id} - {len(location_ids)} ubicaciones")
        
        query = """
            SELECT e.Guid, e.createdon, e.idpatient, e.localacc, e.studytype_id, 
                   e.Status, e.idseverity,
                   st.description as estudio_desc,
                   sev.Description as severidad_desc,
                   p.Surname, p.Name, p.NationalCode, p.SexCode,
                   COALESCE(e.isreported, 0) as isreported,
                   COALESCE(e.isimage, 0) as isimage
            FROM nextris.tbexamination e
            LEFT JOIN nextris.isstudytype st ON st.Guid = e.studytype_id
            LEFT JOIN nextris.IsSeverity sev ON sev.Guid = e.idseverity  
            LEFT JOIN nextris.datapatient p ON p.PatientId = e.idpatient
            INNER JOIN nextris.isequipment eq ON eq.Guid = e.IdEquipment
            WHERE p.PatientId IS NOT NULL
              AND eq.location_id = ANY(%s)
            ORDER BY e.createdon DESC
        """
        
        results = DatabaseService.execute_query(query, (location_ids,))
        
        to_send = []
        for dato in results:
            # dato: [Guid, createdon, idpatient, localacc, studytype_id, Status, idseverity, estudio_desc, severidad_desc, Surname, Name, NationalCode, SexCode, isreported, isimage]
            nombre = f"{dato[10]} {dato[9]}" if dato[10] and dato[9] else "Sin nombre"
            dni = dato[11] if dato[11] else "Sin DNI"
            sex = dato[12] if dato[12] else "Sin especificar"
            estudio = dato[7] if dato[7] else "Sin especificar"
            severidad = dato[8] if dato[8] else "Sin especificar"
            isreported = dato[13] if len(dato) > 13 else 0
            isimage = dato[14] if len(dato) > 14 else 0
            
            fila = [dato[0], dato[1], nombre, dni, sex, estudio, dato[5], severidad, isreported, isimage]
            to_send.append(fila)
        
        return jsonify(to_send)
        
    except Exception as e:
        print(f"[ERROR] get_examination_items_all: {str(e)}")
        return jsonify({'error': str(e)}), 500


@blueprint.route('/get_data_report', methods=['POST'])
def get_data_report():
    """
    Obtiene datos completos del reporte médico para la interfaz de redacción.
    Incluye información del examen, reporte asociado, y datos predefinidos.
    """
    try:
        data = request.get_json()
        guid = data.get('id')
        
        if not guid:
            return jsonify({'error': 'No se proporcionó el ID del examen'}), 400

        # Obtener el estado de IsReported desde tbexamination
        query = """
            SELECT isreported, isimage, studyinstanceuid, studytype_id, 
                   TO_CHAR(createdon, 'DD/MM/YYYY'), numberofviews, status, 
                   othersdetails, 
                   (SELECT description FROM nextris.islaterality WHERE guid=laterality_id) as lateralidad, 
                   history, clinicalquestion 
            FROM nextris.tbexamination 
            WHERE Guid = %s
        """
        exam_results = DatabaseService.execute_query(query, (guid,))
        
        if not exam_results:
            return jsonify({'error': 'Examen no encontrado'}), 404
            
        exam_items = exam_results[0]
        isreported = exam_items[0] if exam_items else None
        isimage = exam_items[1] if exam_items else None
        study_instance_uid = exam_items[2] if exam_items else None
        studytype_id = exam_items[3] if exam_items else None
        fecha_examen = exam_items[4] if exam_items else None
        number_of_views = exam_items[5] if exam_items else None
        stat = exam_items[6] if exam_items else None
        others_details = exam_items[7] if exam_items else None
        lateralidad = exam_items[8] if exam_items else None
        history = exam_items[9] if exam_items else None
        clinical_question = exam_items[10] if exam_items else None

        # Obtener modalidad
        modality = None
        if studytype_id:
            query_modality = """
                SELECT m.externalcode 
                FROM nextris.isstudytype st 
                INNER JOIN nextris.ismodality m ON m.guid=st.modality_id 
                WHERE st.guid = %s
            """
            modality_results = DatabaseService.execute_query(query_modality, (studytype_id,))
            modality = modality_results[0][0] if modality_results else None

        # Obtener los datos del reporte asociado a la tbexamination
        query_report = """
            SELECT guid, idpatient, admnumber, idreferringphysician, 
                   findings, impressions, techniques, conclusions, wassaved 
            FROM nextris.tbreport 
            WHERE idexamination = %s
        """
        report_results = DatabaseService.execute_query(query_report, (guid,))
        report = report_results[0] if report_results else None
        wassaved = report[8] if report else None

        # Buscar default_predef_id si existe para el studytype
        predef_data = None
        descripcion_predef = None
        if studytype_id:
            query_predef = """
                SELECT default_predef_id, description 
                FROM nextris.isstudytype 
                WHERE guid = %s
            """
            predef_results = DatabaseService.execute_query(query_predef, (studytype_id,))
            
            if predef_results:
                row_predef = predef_results[0]
                default_predef_id = row_predef[0] if row_predef[0] else None
                descripcion_predef = row_predef[1] if row_predef[1] else None
                
                if default_predef_id:
                    query_infpredef = """
                        SELECT findings, impression, technique, conclusion, tittle 
                        FROM nextris.tbinfpredef 
                        WHERE guid = %s
                    """
                    infpredef_results = DatabaseService.execute_query(query_infpredef, (default_predef_id,))
                    
                    if infpredef_results:
                        infpredef = infpredef_results[0]
                        predef_data = {
                            'findings': infpredef[0],
                            'impressions': infpredef[1],
                            'techniques': infpredef[2],
                            'conclusions': infpredef[3],
                            'tittle': infpredef[4]
                        }

        # Crear una respuesta combinada
        response = {
            'report': report,
            'isreported': isreported,
            'isimage': isimage,
            'study_instance_uid': study_instance_uid,
            'predefinido': predef_data,
            'descripcion_predef': descripcion_predef,
            'wassaved': wassaved,
            'fecha_examen': fecha_examen,
            'modality': modality,
            'numberofviews': number_of_views,
            'stat': stat,
            'others_details': others_details,
            'lateralidad': lateralidad,
            'history': history,
            'clinical_question': clinical_question
        }
        
        print(f"[DEBUG] get_data_report response: {response}")
        return jsonify(response)
        
    except Exception as e:
        print(f"[ERROR] get_data_report: {str(e)}")
        return jsonify({'error': str(e)}), 500


@blueprint.route('/get_orders_to_distribution', methods=['GET'])
def get_orders_to_distribution():
    """Obtiene órdenes de examen listas para distribución (reportadas y opcionalmente publicadas) filtradas por ubicaciones del usuario"""
    try:
        from flask import session
        
        # Obtener ubicaciones del usuario
        user_id = session.get('_user_id')
        if not user_id:
            return jsonify({'error': 'Usuario no autenticado'}), 401
        
        query_locations = """
            SELECT location_id 
            FROM nextris.rel_user_location 
            WHERE user_id = %s
        """
        user_locations = DatabaseService.execute_query(query_locations, (user_id,))
        
        if not user_locations:
            print(f"[WARNING] Usuario {user_id} no tiene ubicaciones asignadas en get_orders_to_distribution")
            return jsonify([])
        
        location_ids = [loc[0] for loc in user_locations]
        print(f"[DEBUG get_orders_to_distribution] Usuario {user_id} tiene {len(location_ids)} ubicaciones")
        
        # Obtener parámetro para incluir ya enviados
        incluir_enviados = request.args.get('incluir_enviados', 'false').lower() == 'true'
        
        print(f"[INFO] Obteniendo órdenes para distribución (incluir_enviados={incluir_enviados})...")
        
        # Modificar la condición según el parámetro
        if incluir_enviados:
            # Mostrar todos los reportados, sin importar si están publicados o no
            condicion_publicado = "ex.isreported=1"
        else:
            # Mostrar solo los reportados que NO están publicados (comportamiento original)
            condicion_publicado = "ex.ispublicated=0 AND ex.isreported=1"
        
        query = f"""
            SELECT 
                ex.Guid, 
                TO_CHAR(ex.createdon, 'DD/MM/YYYY'),
                exam.description,
                p.Surname || ' ' || p.Name AS FullName,
                p.email,
                ex.Status, 
                ex.idrequestingphysician,
                ex.idreferringphysician,
                ex.idseverity,
                ex.ispublicated
            FROM nextris.tbexamination ex 
            INNER JOIN nextris.datapatient p ON ex.IdPatient = p.PatientId 
            LEFT JOIN nextris.isstudytype exam on exam.Guid=ex.studytype_id
            INNER JOIN nextris.isequipment equip on equip.Guid=ex.IdEquipment
            WHERE {condicion_publicado} AND equip.location_id = ANY(%s)
            ORDER BY ex.createdon DESC
        """
        
        result = DatabaseService.execute_query(query, (location_ids,))
        
        print(f"[SUCCESS] Se encontraron {len(result) if result else 0} órdenes para distribución")
        return jsonify(result)
        
    except Exception as e:
        print(f"[ERROR] Error en get_orders_to_distribution: {str(e)}")
        return jsonify({'error': str(e)}), 500
