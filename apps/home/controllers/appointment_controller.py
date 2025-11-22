"""
Controller para gestión de agenda, citas y eventos
Migrado masivamente desde routes.py para reducir el archivo principal
"""

from flask import Blueprint, request, jsonify
import psycopg2
import pydicom
import time
from datetime import datetime, timedelta
from apps.home.services.database_service import DatabaseService
from apps.home.services.config_service import ConfigService
from apps.home.services.hl7_service import HL7Service
from apps.home.controllers.admin_controller import updatestatus

# Crear blueprint para citas y agenda
appointment_bp = Blueprint('appointment', __name__, url_prefix='/api')

# Blueprint adicional sin prefijo para rutas legacy
appointment_legacy_bp = Blueprint('appointment_legacy', __name__, url_prefix='')

# Obtener configuración de BD
config = ConfigService.get_db_config()

@appointment_bp.route('/get_events_para_editar', methods=['POST'])
def get_events_para_editar():
    """Obtiene eventos de agenda para editar"""
    try:
        data = request.get_json()
        guid = data.get('guid')
        equipo = data.get('equipo')
        
        if not equipo:
            return jsonify({'error': 'Falta parámetro equipo'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Traer todos los eventos del equipo
        query = """
            SELECT tba.guid, tba.comienzo, tba.fin, tba.idmed, st.description as exam, 
                   tba.idmed_sol, CONCAT(pat.surname, ' ', pat.name)
            FROM nextris.tbagendaevents tba
            INNER JOIN nextris.isequipment equip ON equip.guid = tba.idequipment
            INNER JOIN nextris.isstudytype st ON st.guid = tba.idexam
            INNER JOIN nextris.datapatient pat ON pat.guid = tba.idpatient
            WHERE equip.aetitle = %s
        """
        
        cursor.execute(query, (equipo,))
        eventos = cursor.fetchall()
        
        result = []
        for ev in eventos:
            start = (ev[1] + timedelta(hours=3)) if ev[1] else None
            end = (ev[2] + timedelta(hours=3)) if ev[2] else None
            
            evento = {
                'guid': str(ev[0]),
                'start': start.isoformat() if start else '',
                'end': end.isoformat() if end else '',
                'idmed': ev[3],
                'exam': ev[4] or 'Sin examen',
                'idmed_sol': ev[5],
                'nombre': ev[6] or 'Sin nombre',
                'title': f"{ev[6] or 'Sin nombre'} - {ev[4] or 'Sin examen'}",
                'editable': str(ev[0]) == str(guid) if guid else False
            }
            result.append(evento)
        
        # Obtener horarios de trabajo del equipo
        work_hours = []
        wh_query = """
            SELECT ae.day, ae.timefrom, ae.timeto
            FROM nextris.isagendaequip ae
            INNER JOIN nextris.isequipment equip ON equip.guid = ae.idequipment
            WHERE equip.aetitle = %s
        """
        cursor.execute(wh_query, (equipo,))
        whs = cursor.fetchall()
        
        days_mapping = {
            'lunes': 1,
            'martes': 2,
            'miércoles': 3,
            'jueves': 4,
            'viernes': 5,
            'sábado': 6,
            'domingo': 0
        }
        
        for row in whs:
            work_hours.append({
                'day': days_mapping.get(row[0].lower(), 1),
                'start': row[1].strftime('%H:%M:%S') if row[1] else '08:00:00',
                'end': row[2].strftime('%H:%M:%S') if row[2] else '17:00:00'
            })
        
        cursor.close()
        connection.close()
        
        print(f"[DEBUG] GUID recibido: {guid}")
        print(f"[DEBUG] Equipo: {equipo}")
        print(f"[DEBUG] Eventos encontrados: {len(result)}")
        print(f"[DEBUG] Horarios de trabajo: {len(work_hours)}")
        if result:
            print(f"[DEBUG] Primer evento: {result[0]}")
            # Verificar cuántos eventos son editables
            editables = [e for e in result if e['editable']]
            print(f"[DEBUG] Eventos editables: {len(editables)}")
            if editables:
                print(f"[DEBUG] Evento editable: {editables[0]}")
        
        return jsonify({
            'events': result,
            'work_hours': work_hours
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@appointment_bp.route('/actualizar_evento_cita', methods=['POST'])
def actualizar_evento_cita():
    """Actualiza las fechas de un evento cuando se mueve en el calendario"""
    try:
        data = request.get_json()
        print(f"[DEBUG] actualizar_evento_cita - datos: {data}")
        
        if not data.get('guid') or not data.get('start') or not data.get('end'):
            return jsonify({'error': 'Faltan parámetros requeridos'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Zona horaria local
        import pytz
        local_tz = pytz.timezone("America/Argentina/Buenos_Aires")
        
        # Convertir las fechas del frontend
        init_utc = datetime.fromisoformat(data['start'].replace('Z', '+00:00')).astimezone(pytz.utc)
        finish_utc = datetime.fromisoformat(data['end'].replace('Z', '+00:00')).astimezone(pytz.utc)
        
        # Convertir a zona horaria local y ajustar
        init_local = init_utc.astimezone(local_tz) - timedelta(hours=5)
        finish_local = finish_utc.astimezone(local_tz) - timedelta(hours=5)
        
        # Convertir a formato para la base de datos
        init_str_adjusted = init_local.strftime('%Y-%m-%dT%H:%M:%S')
        finish_str_adjusted = finish_local.strftime('%Y-%m-%dT%H:%M:%S')
        
        # Actualizar el evento en la base de datos
        query_events = """
            UPDATE nextris.tbagendaevents 
            SET comienzo = %s, fin = %s 
            WHERE guid = %s
        """
        
        cursor.execute(query_events, (init_str_adjusted, finish_str_adjusted, data['guid']))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        print(f"[DEBUG] Evento actualizado: {data['guid']} -> {init_str_adjusted} to {finish_str_adjusted}")
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"[ERROR] actualizar_evento_cita: {str(e)}")
        return jsonify({'error': str(e)}), 500


@appointment_bp.route('/insertar_citas_per_med', methods=['POST'])
def insertar_citas_per_med():
    """Inserta citas para un médico específico"""
    try:
        data = request.get_json()
        medico_id = data.get('medico_id')
        fecha = data.get('fecha')
        hora_inicio = data.get('hora_inicio')
        hora_fin = data.get('hora_fin')
        paciente_id = data.get('paciente_id')
        examen_id = data.get('examen_id')
        
        if not all([medico_id, fecha, hora_inicio, hora_fin, paciente_id, examen_id]):
            return jsonify({'error': 'Faltan parámetros requeridos'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Insertar cita
        import uuid
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.tbagendaevents 
            (guid, comienzo, fin, idmed, idpatient, idexam, createdon)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        fecha_inicio = f"{fecha} {hora_inicio}"
        fecha_fin = f"{fecha} {hora_fin}"
        
        cursor.execute(query, (
            new_guid, fecha_inicio, fecha_fin, medico_id, 
            paciente_id, examen_id, datetime.now()
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'cita_id': new_guid})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@appointment_bp.route('/insertar_citas_per_equip', methods=['POST'])
def insertar_citas_per_equip():
    """Inserta citas para un equipo específico"""
    try:
        data = request.get_json()
        equipo_id = data.get('equipo_id')
        fecha = data.get('fecha')
        hora_inicio = data.get('hora_inicio')
        hora_fin = data.get('hora_fin')
        paciente_id = data.get('paciente_id')
        examen_id = data.get('examen_id')
        medico_id = data.get('medico_id')
        
        if not all([equipo_id, fecha, hora_inicio, hora_fin, paciente_id, examen_id]):
            return jsonify({'error': 'Faltan parámetros requeridos'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Insertar cita
        import uuid
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.tbagendaevents 
            (guid, comienzo, fin, idequipment, idpatient, idexam, idmed, createdon)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        fecha_inicio = f"{fecha} {hora_inicio}"
        fecha_fin = f"{fecha} {hora_fin}"
        
        cursor.execute(query, (
            new_guid, fecha_inicio, fecha_fin, equipo_id,
            paciente_id, examen_id, medico_id, datetime.now()
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'cita_id': new_guid})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@appointment_bp.route('/crear_visita', methods=['POST'])
def crear_visita():
    """Crea una nueva visita/consulta"""
    try:
        data = request.get_json()
        paciente_id = data.get('paciente_id')
        medico_id = data.get('medico_id')
        fecha = data.get('fecha')
        tipo_visita = data.get('tipo_visita', 'consulta')
        
        if not all([paciente_id, medico_id, fecha]):
            return jsonify({'error': 'Faltan parámetros requeridos'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        import uuid
        new_guid = str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.tbvisitas 
            (guid, idpatient, idmed, fecha, tipo, createdon)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            new_guid, paciente_id, medico_id, fecha, tipo_visita, datetime.now()
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'visita_id': new_guid})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@appointment_bp.route('/admisionar_cita', methods=['POST'])
def admisionar_cita():
    """Admisiona una cita y crea la worklist DICOM"""
    try:
        data = request.get_json()
        cita_id = data.get('cita_id')
        equipo_id = data.get('equipo_id')  # Puede venir del modal o de la cita
        
        if not cita_id:
            return jsonify({'error': 'Falta cita_id'}), 400
        
        print(f"[INFO] Iniciando admisión de cita: {cita_id}")
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # 1. Obtener datos de la cita
        query_cita = """
            SELECT idpatient, idexam, idequipment 
            FROM nextris.tbagendaevents 
            WHERE guid = %s
        """
        cursor.execute(query_cita, (cita_id,))
        cita_data = cursor.fetchone()
        
        if not cita_data:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Cita no encontrada'}), 404
        
        patient_id, exam_id, cita_equipo_id = cita_data
        
        # Usar el equipo del modal si se proporcionó, sino el de la cita
        final_equipo_id = equipo_id if equipo_id else cita_equipo_id
        
        if not final_equipo_id:
            cursor.close()
            connection.close()
            return jsonify({'error': 'No se especificó equipo'}), 400
        
        print(f"[INFO] Datos de cita - Paciente: {patient_id}, Examen: {exam_id}, Equipo: {final_equipo_id}")
        
        # 2. Obtener datos del paciente
        patient_data = DatabaseService.get_patient_by_guid(patient_id)
        if not patient_data:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Paciente no encontrado'}), 404
        
        # 3. Obtener último número de admisión y acceso
        query_last_adm = "SELECT MAX(CAST(SUBSTRING(AdmisionNumber, 4) AS INTEGER)) FROM nextris.tbexamination WHERE AdmisionNumber LIKE 'ADM%'"
        cursor.execute(query_last_adm)
        last_adm = cursor.fetchone()
        
        query_last_acc = "SELECT MAX(CAST(SUBSTRING(LocalAcc, 4) AS INTEGER)) FROM nextris.tbexamination WHERE LocalAcc LIKE 'ACC%'"
        cursor.execute(query_last_acc)
        last_acc = cursor.fetchone()
        
        parte_numerica_adm = str(last_adm[0]) if last_adm and last_adm[0] else "000"
        parte_numerica_acc = str(last_acc[0]) if last_acc and last_acc[0] else "000"
        
        NewAdm = f"ADM{int(parte_numerica_adm) + 1:03d}"
        newAcc = f"ACC{int(parte_numerica_acc) + 1:03d}"
        
        print(f"[INFO] Números generados - Admisión: {NewAdm}, Acceso: {newAcc}")
        
        # 4. Obtener datos del equipo y modalidad
        equipo_data = DatabaseService.get_equipment_by_guid(final_equipo_id)
        if not equipo_data:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Equipo no encontrado'}), 404
        
        query_modality = "SELECT Guid, ExternalCode FROM nextris.ismodality WHERE Guid = %s"
        cursor.execute(query_modality, (equipo_data[3],))
        modalidad = cursor.fetchone()
        
        # 5. Obtener descripción del examen
        exam_desc = DatabaseService.get_study_type_description(exam_id)
        
        print(f"[INFO] Descripción del examen: {exam_desc}")
        
        # ===================================================================
        # 🚨 PASO CRÍTICO: ENVIAR HL7 PRIMERO - SI FALLA, NO CONTINUAR 🚨
        # ===================================================================
        print(f"[CRITICAL] Enviando HL7 a worklist...")
        study_instance_uid, hl7_success = HL7Service.send_exam_to_worklist(
            patient_data, exam_desc, equipo_data, modalidad[1] if modalidad else "",
            NewAdm, newAcc
        )
        
        if not hl7_success:
            print(f"[ERROR] ❌ HL7 falló - Abortando proceso de admisión")
            cursor.close()
            connection.close()
            return jsonify({'error': 'Error enviando a worklist HL7 - Proceso abortado'}), 500
        
        print(f"[SUCCESS] ✅ HL7 enviado exitosamente - StudyInstanceUID: {study_instance_uid}")
        print(f"[INFO] ⚠️  IMPORTANTE: Usando el mismo StudyInstanceUID para BD: {study_instance_uid}")
        print(f"[INFO] Continuando con proceso de admisión...")
        
        # 6. Marcar cita como admitida (solo después de HL7 exitoso)
        query_update = """
            UPDATE nextris.tbagendaevents 
            SET isadmitted = TRUE
            WHERE guid = %s
        """
        cursor.execute(query_update, (cita_id,))
        connection.commit()
        
        print(f"[INFO] Cita marcada como admitida")
        
        # 8. Insertar en tbexamination
        DatabaseService.set_timezone()
        
        print(f"[DATABASE] 📊 Insertando en tbexamination con StudyInstanceUID: {study_instance_uid}")
        
        insert_exam_query = """
            INSERT INTO nextris.tbexamination (
                Guid, StudyInstanceUID, IdPatient, StudyType_Id, IdEquipment,
                AdmisionNumber, LocalAcc, createdon, Status, IsExecuted, IsAdmitted
            ) VALUES (
                uuid_generate_v4(), %s, (SELECT patientid from nextris.datapatient WHERE guid = %s), %s, %s, %s, %s, NOW(), 'A', 0, 1
            )
        """
        
        cursor.execute(insert_exam_query, (
            study_instance_uid, patient_id, exam_id, final_equipo_id, NewAdm, newAcc
        ))
        connection.commit()
        
        print(f"[SUCCESS] ✅ Examen creado en tbexamination con StudyInstanceUID: {study_instance_uid}")
        print(f"[DATABASE] 📋 Verificación - NewAdm: {NewAdm}, newAcc: {newAcc}")
        
        # Verificar que se insertó correctamente
        verify_query = "SELECT StudyInstanceUID FROM nextris.tbexamination WHERE AdmisionNumber = %s"
        cursor.execute(verify_query, (NewAdm,))
        verify_result = cursor.fetchone()
        if verify_result:
            saved_uid = verify_result[0]
            print(f"[VERIFY] ✅ StudyInstanceUID guardado en BD: {saved_uid}")
            if saved_uid == study_instance_uid:
                print(f"[VERIFY] ✅ ¡MATCH! Los UIDs coinciden correctamente")
            else:
                print(f"[VERIFY] ❌ ¡ERROR! Los UIDs NO coinciden:")
                print(f"[VERIFY]     HL7: {study_instance_uid}")
                print(f"[VERIFY]     BD:  {saved_uid}")
        else:
            print(f"[VERIFY] ❌ No se pudo verificar el UID guardado")
        
        # 9. Obtener el GUID del examen recién creado
        query_guid = "SELECT Guid FROM nextris.tbexamination WHERE AdmisionNumber = %s"
        cursor.execute(query_guid, (NewAdm,))
        exam_guid_result = cursor.fetchone()
        
        if exam_guid_result:
            exam_guid = exam_guid_result[0]
            
            # 10. Crear fila en tbReport
            insert_report_query = """
                INSERT INTO nextris.tbReport(
                    Guid, admnumber, idexamination, IdPatient, Date
                ) VALUES (
                    uuid_generate_v4(), %s, %s, %s, NOW()
                )
            """
            
            cursor.execute(insert_report_query, (NewAdm, exam_guid, patient_id))
            connection.commit()
            
            print(f"[SUCCESS] tbReport creado para examen {exam_guid}")
        else:
            print(f"[WARNING] No se pudo obtener GUID del examen con admisión {NewAdm}")
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True, 
            'message': 'Cita admisionada y worklist creada exitosamente',
            'admision': NewAdm,
            'acceso': newAcc
        })
        
    except Exception as e:
        print(f"[ERROR] Error en admisionar_cita: {str(e)}")
        return jsonify({'error': str(e)}), 500


@appointment_bp.route('/obtener_agenda', methods=['GET', 'POST'])
def obtener_agenda():
    """Obtiene agenda de citas por fecha y/o médico"""
    try:
        # Manejar tanto GET como POST
        if request.method == 'POST':
            data = request.get_json()
        else:
            data = request.args.to_dict()
            
        fecha = data.get('fecha')
        medico_id = data.get('medico_id')
        equipo_id = data.get('equipo_id')
        machine = data.get('machine')  # Para compatibilidad con scriptsCitas.js
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT 
                tba.guid, tba.comienzo, tba.fin,
                CONCAT(pat.surname, ' ', pat.name) as paciente,
                st.description as examen,
                CONCAT(med.surname, ' ', med.name) as medico,
                tba.status
            FROM nextris.tbagendaevents tba
            LEFT JOIN nextris.datapatient pat ON pat.guid = tba.idpatient
            LEFT JOIN nextris.isstudytype st ON st.guid = tba.idexam
            LEFT JOIN nextris.datauser med ON med.guid = tba.idmed
            WHERE 1=1
        """
        
        params = []
        if fecha:
            query += " AND DATE(tba.comienzo) = %s"
            params.append(fecha)
        if medico_id:
            query += " AND tba.idmed = %s"
            params.append(medico_id)
        if equipo_id:
            query += " AND tba.idequipment = %s"
            params.append(equipo_id)
        
        query += " ORDER BY tba.comienzo"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        agenda = []
        for row in results:
            agenda.append({
                'guid': row[0],
                'comienzo': row[1].isoformat() if row[1] else '',
                'fin': row[2].isoformat() if row[2] else '',
                'paciente': row[3] or '',
                'examen': row[4] or '',
                'medico': row[5] or '',
                'status': row[6] or 'pendiente'
            })
        
        return jsonify(agenda)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@appointment_bp.route('/get_citas', methods=['GET']) 
def get_citas():
    """Obtiene todas las citas no admitidas"""
    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT tba.guid, 
                   COALESCE(pat.name || ' ' || pat.surname, 'Sin paciente') as fullname, 
                   tba.comienzo,
                   COALESCE(us.name || ' ' || us.surname, 'Sin médico') as medref, 
                   COALESCE(st.description, 'Sin examen') as description,
                   COALESCE(equip.aetitle, 'Sin equipo') as equipo, 
                   COALESCE(rp.description, 'Sin médico solicitante') as med_solicitante
            FROM nextris.tbagendaevents tba
            LEFT JOIN nextris.datapatient pat on tba.idpatient=pat.guid
            LEFT JOIN nextris.isrequestingphysician rp on tba.idmed_sol=rp.guid
            LEFT JOIN nextris.tbuser us on tba.idmed=us.guid
            LEFT JOIN nextris.isstudytype st on tba.idexam=st.guid
            LEFT JOIN nextris.isequipment equip on equip.guid=tba.idequipment
            WHERE isadmitted=false
            ORDER BY tba.comienzo DESC
        """
        
        cursor.execute(query)
        result = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@appointment_bp.route('/get_citas_for_today', methods=['GET']) 
def get_citas_for_today():
    """Obtiene las citas del día actual no admitidas, filtradas por ubicaciones del usuario"""
    try:
        from flask import session
        
        # Obtener el user_id de la sesión
        user_id = session.get('_user_id')
        
        if not user_id:
            return jsonify({'error': 'Usuario no autenticado'}), 401
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Primero, obtener las ubicaciones del usuario
        query_locations = """
            SELECT location_id 
            FROM nextris.rel_user_location 
            WHERE user_id = %s
        """
        cursor.execute(query_locations, (user_id,))
        user_locations = cursor.fetchall()
        
        if not user_locations:
            # Si no tiene ubicaciones asignadas, no mostrar citas
            cursor.close()
            connection.close()
            return jsonify([])
        
        # Extraer los location_ids
        location_ids = [loc[0] for loc in user_locations]
        
        # Query para obtener citas con ubicación
        query = """
            SELECT tba.guid, 
                   pat.name || ' ' || pat.surname as fullname,
                   us.name || ' ' || us.surname as med_ref, 
                   ex.description, 
                   rp.description as med_sol,
                   loc.name || ' (' || loc.code || ')' as ubicacion
            FROM nextris.tbagendaevents tba
            LEFT JOIN nextris.datapatient pat on tba.idpatient=pat.guid
            LEFT JOIN nextris.isrequestingphysician rp on tba.idmed_sol=rp.guid
            LEFT JOIN nextris.tbuser us on tba.idmed=us.guid
            LEFT JOIN nextris.isstudytype ex on tba.idexam=ex.guid
            LEFT JOIN nextris.tblocation loc on tba.location_id=loc.guid
            WHERE DATE(tba.comienzo) = current_date 
              AND isadmitted=false
              AND tba.location_id = ANY(%s)
            ORDER BY tba.comienzo
        """
        
        cursor.execute(query, (location_ids,))
        result = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return jsonify(result)
        
    except Exception as e:
        print(f"[ERROR] get_citas_for_today: {str(e)}")
        return jsonify({'error': str(e)}), 500


@appointment_bp.route('/actualizar_datos_cita', methods=['POST']) 
def actualizar_datos_cita():
    """Actualiza una cita existente"""
    try:
        # Obtener datos del formulario
        respuesta = request.form.to_dict()
        print(f"[DEBUG] actualizar_datos_cita - datos recibidos: {respuesta}")
        
        # Si s_msol es 'default', dejarlo vacío
        if respuesta.get('s_msol') == 'default':
            respuesta['s_msol'] = ''
            
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Construir query según si se actualiza el examen o no
        if not respuesta.get('id_est'):
            query = """
                UPDATE nextris.tbagendaevents 
                SET idmed = %s, idmed_sol = %s 
                WHERE Guid = %s
            """
            params = (respuesta['s_mref'], respuesta['s_msol'], respuesta['id_ec'])
        else:
            query = """
                UPDATE nextris.tbagendaevents 
                SET idmed = %s, idmed_sol = %s, idexam = %s 
                WHERE Guid = %s
            """
            params = (respuesta['s_mref'], respuesta['s_msol'], respuesta['id_est'], respuesta['id_ec'])
        
        cursor.execute(query, params)
        connection.commit()
        
        # Obtener nombre del médico referente actualizado
        query_mref = "SELECT name || ' ' || surname as medref FROM nextris.tbuser WHERE guid = %s"
        cursor.execute(query_mref, (respuesta['s_mref'],))
        result_mref = cursor.fetchone()
        mref = result_mref[0] if result_mref else ''
        
        # Obtener nombre del médico solicitante actualizado
        msol = ''
        if respuesta.get('s_msol'):
            query_msol = "SELECT description FROM nextris.isrequestingphysician WHERE guid = %s"
            cursor.execute(query_msol, (respuesta['s_msol'],))
            result_msol = cursor.fetchone()
            msol = result_msol[0] if result_msol else ''
        
        # Obtener datos actuales de la cita para mantener los valores que no cambian
        query_current = """
            SELECT CONCAT(pat.surname, ' ', pat.name) as paciente,
                   TO_CHAR(tba.comienzo, 'YYYY-MM-DD') || ' ' || TO_CHAR(tba.comienzo, 'HH24:MI:SS') as turno,
                   COALESCE(equip.aetitle, 'Sin equipo') as equipo,
                   COALESCE(st.description, '') as examen
            FROM nextris.tbagendaevents tba
            LEFT JOIN nextris.datapatient pat ON pat.guid = tba.idpatient
            LEFT JOIN nextris.isequipment equip ON equip.guid = tba.idequipment
            LEFT JOIN nextris.isstudytype st ON st.guid = tba.idexam
            WHERE tba.guid = %s
        """
        cursor.execute(query_current, (respuesta['id_ec'],))
        current_data = cursor.fetchone()
        
        # Obtener el examen actualizado si se modificó, sino usar el actual de BD
        examen_actual = current_data[3] if current_data[3] else respuesta.get('ex_old', '')
        if respuesta.get('id_est'):
            query_examen = "SELECT description FROM nextris.isstudytype WHERE guid = %s"
            cursor.execute(query_examen, (respuesta['id_est'],))
            result_examen = cursor.fetchone()
            examen_actual = result_examen[0] if result_examen else examen_actual
        
        cursor.close()
        connection.close()
        
        # Crear respuesta con datos actualizados manteniendo los que no cambian
        response = [
            current_data[0],    # Paciente (mantener original)
            current_data[1],    # Turno (mantener original)
            mref,              # Médico Referente (actualizado)
            examen_actual,     # Examen (actualizado si se cambió)
            current_data[2],   # Equipo (mantener original)
            msol               # Médico Solicitante (actualizado)
        ]
        
        response_data = {
            "success": True, 
            'message': 'Cita actualizada exitosamente', 
            'data': response
        }
        print(f"[DEBUG] Cita actualizada: {response_data}")
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@appointment_bp.route('/eliminar_cita', methods=['POST']) 
def eliminar_cita():
    """Elimina una cita de la agenda"""
    try:
        data = request.get_json()
        cita_id = data.get('id_cita')
        print(f"[DEBUG] eliminar_cita - id_cita recibido: {cita_id}")
        if not cita_id:
            return jsonify({'error': 'Falta id_cita'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que la cita existe antes de eliminar
        check_query = "SELECT guid FROM nextris.tbagendaevents WHERE guid = %s"
        cursor.execute(check_query, (cita_id,))
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({'error': 'Cita no encontrada'}), 404
        
        # Eliminar la cita
        query = "DELETE FROM nextris.tbagendaevents WHERE guid = %s"
        cursor.execute(query, (cita_id,))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        print(f"[DEBUG] Cita eliminada: {cita_id}")
        
        return jsonify({"success": True, "message": "Cita eliminada exitosamente"})
        
    except Exception as e:
        print(f"[ERROR] eliminar_cita: {str(e)}")
        return jsonify({'error': str(e)}), 500


def get_admision_accesion_number():
    """Genera nuevo número de admisión y acceso"""
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT LocalAcc, AdmisionNumber FROM tbExamination ORDER BY CreatedOn DESC LIMIT 1 """
    cursor.execute(query)
    dato = cursor.fetchone()
    
    if dato:
        lastAcc = dato[0]
        lastAdm = dato[1]

        # Extraer parte numérica del LocalAcc
        parte_numerica_acc = ''.join(filter(str.isdigit, lastAcc))

        # Extraer parte numérica del AdmisionNumber
        parte_numerica_adm = ''.join(filter(str.isdigit, lastAdm))
        # Convertir la parte numérica a entero y aumentar en 1
        NewAdm = f"ADM{int(parte_numerica_adm) + 1:03d}"
    else:
        parte_numerica_acc = "000"
        NewAdm = "ADM001"
    newAcc = f"ACC{int(parte_numerica_acc) + 1 }"

    connection.close()
    return newAcc, NewAdm
