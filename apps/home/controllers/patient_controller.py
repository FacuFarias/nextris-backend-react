"""
Controlador de pacientes para el sistema RIS
Maneja rutas relacionadas con gestión de pacientes
"""

from flask import jsonify, request, session
import psycopg2
import uuid
from datetime import datetime
from apps.home import blueprint
from apps.home.services import DatabaseService, ConfigService
from apps.home.models import Cita
from apps.authentication.util import hash_pass

# Obtener configuración de BD
config = ConfigService.get_db_config()


@blueprint.route('/agregar_paciente_rapido', methods=['POST'])
def agregar_paciente_rapido():
    """Endpoint para agregar un paciente de forma rápida y crear su usuario"""
    try:
        data = request.get_json()
        print(f"[DEBUG] Datos recibidos en agregar_paciente_rapido: {data}")
        
        # Mapear los campos del frontend a los campos de la BD
        nombre = data.get('nombre', '')
        apellido = data.get('apellido', '')
        dni = data.get('dni', '')
        fecha_nac = data.get('fecha_nac', None)
        sexo = data.get('sexo', 'I')  # Por defecto 'I' si no se especifica
        
        # Generar un PatientId único basado en el DNI (o alguna lógica de negocio)
        patient_id = dni if dni else str(uuid.uuid4())[:8]
        
        query = """
            INSERT INTO nextris.datapatient (Guid, PatientId, Surname, Name, NationalCode, SexCode, BirthDate)
            VALUES (uuid_generate_v4(), %s, %s, %s, %s, %s, %s)
            RETURNING Guid
        """
        
        params = (
            patient_id,    # PatientId
            apellido,      # Surname
            nombre,        # Name
            dni,           # NationalCode
            sexo,          # SexCode
            fecha_nac      # BirthDate
        )
        
        result = DatabaseService.execute_query(query, params, commit=True)
        
        # Obtener el GUID generado
        guid = None
        if result and len(result) > 0:
            guid = result[0][0]
        
        # === CREAR USUARIO EN TBUSER_PATIENT ===
        if guid and nombre and apellido:
            try:
                # Generar username: primera letra del nombre + apellido
                base_username = (nombre[0] + apellido).lower().strip()
                
                # Verificar si el username ya existe y agregar número si es necesario
                check_query = """
                    SELECT username FROM nextris.tbuser_patient 
                    WHERE username LIKE %s 
                    ORDER BY username
                """
                existing_users = DatabaseService.execute_query(check_query, (f"{base_username}%",))
                
                username = base_username
                if existing_users and len(existing_users) > 0:
                    # Buscar el siguiente número disponible
                    counter = 1
                    while True:
                        test_username = f"{base_username}{counter:02d}"
                        if not any(user[0] == test_username for user in existing_users):
                            username = test_username
                            break
                        counter += 1
                
                # Hashear contraseña temporal 'next'
                hashed_password = hash_pass('next')
                
                # Crear usuario en tbuser_patient
                insert_user_query = """
                    INSERT INTO nextris.tbuser_patient (
                        guid, username, password, datapatient_id, status, firstlogin
                    ) VALUES (
                        uuid_generate_v4(), %s, %s, %s, 'Active', 1
                    )
                """
                DatabaseService.execute_query(
                    insert_user_query, 
                    (username, hashed_password, str(guid)), 
                    commit=True
                )
                
                print(f"[DEBUG] Usuario '{username}' creado exitosamente para paciente {guid}")
                
            except Exception as user_error:
                print(f"[ERROR] Error al crear usuario para paciente: {str(user_error)}")
                # No fallar la creación del paciente si falla la creación del usuario
        
        return jsonify({
            "success": True, 
            "message": "Paciente agregado correctamente",
            "guid": str(guid) if guid else None
        })
        
    except Exception as e:
        print(f"[ERROR] Error en agregar_paciente_rapido: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500




@blueprint.route('/agregar_pacientes', methods=['POST'])
def agregar_pacientes():
    """Endpoint para agregar un paciente completo con todos los datos"""
    try:
        # Obtener datos del formulario
        r = request.form.to_dict()

        print(f"[DEBUG] Datos recibidos: {r}")

        # Query usando DatabaseService - RETURNING para obtener el GUID generado
        query = """
        INSERT INTO nextris.DataPatient(
            Guid, Surname, Name, NationalCode, BirthDate, PatientId, SexCode, 
            Phone, Email, HealthCard) 
        VALUES (
            uuid_generate_v4(), %s, %s, %s, %s, %s, %s, 
            %s, %s, %s) 
        RETURNING Guid 
        """
        
        params = (
            r.get('p_surname', ''),
            r.get('p_name', ''),
            r.get('p_dni', ''),
            r.get('fecha_nacimiento', None),
            r.get('p_id', ''),
            r.get('sex', ''),
            r.get('telefono', ''),
            r.get('mail', ''),
            r.get('p_healthcard', '')
        )
        
        # Ejecutar usando DatabaseService - ahora retorna el GUID
        result = DatabaseService.execute_query(query, params, commit=True)
        
        # Obtener el GUID del paciente creado
        patient_guid = result[0][0] if result and len(result) > 0 else None
        
        print(f"[DEBUG] Paciente creado con GUID: {patient_guid}")
        
        # Crear usuario para el paciente en tbuser_patient
        if patient_guid:
            nombre = r.get('p_name', '').strip()
            apellido = r.get('p_surname', '').strip()
            
            # Generar username: primera letra del nombre + apellido
            if nombre and apellido:
                base_username = (nombre[0] + apellido).lower().replace(' ', '')
                
                # Verificar si el username ya existe y agregar número si es necesario
                check_username_query = """
                    SELECT COUNT(*) FROM nextris.tbuser_patient 
                    WHERE username LIKE %s
                """
                
                # Buscar cuántos usuarios existen con ese patrón
                existing_count = DatabaseService.execute_query(
                    check_username_query, 
                    (f"{base_username}%",)
                )
                
                count = existing_count[0][0] if existing_count else 0
                
                # Si ya existe, agregar número secuencial
                if count > 0:
                    # Buscar el siguiente número disponible
                    for i in range(1, 100):
                        test_username = f"{base_username}{i:02d}"
                        check_exact = DatabaseService.execute_query(
                            "SELECT COUNT(*) FROM nextris.tbuser_patient WHERE username = %s",
                            (test_username,)
                        )
                        if check_exact[0][0] == 0:
                            username = test_username
                            break
                    else:
                        username = base_username + str(count + 1).zfill(2)
                else:
                    username = base_username
                
                print(f"[DEBUG] Username generado: {username}")
                
                # Hashear la contraseña temporal
                hashed_password = hash_pass('next')
                
                # Insertar el usuario del paciente
                insert_user_query = """
                    INSERT INTO nextris.tbuser_patient (
                        guid, username, password, status, datapatient_id
                    ) VALUES (
                        uuid_generate_v4(), %s, %s, %s, %s
                    )
                """
                
                user_params = (
                    username,
                    hashed_password,  # password hasheada
                    'Active',
                    patient_guid
                )
                
                DatabaseService.execute_query(insert_user_query, user_params, commit=True)
                print(f"[DEBUG] Usuario paciente creado: {username}")
        
        # Crear la devolución como arreglo para mantener el orden
        devolucion = [
            r.get('p_name', ''),        # nombre
            r.get('p_surname', ''),     # apellido  
            r.get('p_dni', ''),         # dni
            r.get('sex', ''),           # sexo
            r.get('fecha_nacimiento', ''), # fecha_de_nac
            r.get('telefono', ''),      # telefono
            r.get('mail', ''),          # mail
            r.get('p_healthcard', '')   # p_healthcard
        ]
        
        return jsonify(devolucion)
        
    except Exception as e:
        print(f"[ERROR] Error agregando paciente: {e}")
        return jsonify({"error": str(e)}), 500

@blueprint.route('/buscar_pacientes', methods=['POST'])
def buscar_pacientes():
    """Endpoint para buscar pacientes"""
    try:
        data = request.get_json()
        search_term = data.get('search_term', '')
        
        # Obtener user_id de la sesión
        user_id = session.get('_user_id')
        if not user_id:
            return jsonify({"error": "Usuario no autenticado"}), 401
        
        query = """
            SELECT dp.Guid, dp.PatientId, dp.Surname, dp.Name, dp.NationalCode, dp.SexCode, dp.BirthDate
            FROM nextris.datapatient dp
            INNER JOIN nextris.rel_user_patientdomain rup 
                ON dp.id_patientdomain = rup.patientdomain_id
            WHERE rup.user_id = %s
              AND (LOWER(dp.Name) LIKE LOWER(%s) 
               OR LOWER(dp.Surname) LIKE LOWER(%s) 
               OR dp.NationalCode LIKE %s
               OR dp.PatientId LIKE %s)
            ORDER BY dp.Surname, dp.Name
            LIMIT 100
        """
        
        search_pattern = f"%{search_term}%"
        params = (user_id, search_pattern, search_pattern, search_pattern, search_pattern)
        
        results = DatabaseService.execute_query(query, params)
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/buscar_pacientes2', methods=['POST'])
def buscar_pacientes2():
    """Endpoint alternativo para buscar pacientes con criterios específicos"""
    try:
        data = request.get_json()
        criteria = data.get('criteria', {})
        
        # Obtener user_id de la sesión
        user_id = session.get('_user_id')
        if not user_id:
            return jsonify({"error": "Usuario no autenticado"}), 401
        
        conditions = ["rup.user_id = %s"]
        params = [user_id]
        
        if criteria.get('name'):
            conditions.append("LOWER(dp.Name) LIKE LOWER(%s)")
            params.append(f"%{criteria['name']}%")
            
        if criteria.get('surname'):
            conditions.append("LOWER(dp.Surname) LIKE LOWER(%s)")
            params.append(f"%{criteria['surname']}%")
            
        if criteria.get('national_code'):
            conditions.append("dp.NationalCode = %s")
            params.append(criteria['national_code'])
            
        if criteria.get('patient_id'):
            conditions.append("dp.PatientId = %s")
            params.append(criteria['patient_id'])
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT dp.Guid, dp.PatientId, dp.Surname, dp.Name, dp.NationalCode, dp.SexCode, dp.BirthDate
            FROM nextris.datapatient dp
            INNER JOIN nextris.rel_user_patientdomain rup 
                ON dp.id_patientdomain = rup.patientdomain_id
            WHERE {where_clause}
            ORDER BY dp.Surname, dp.Name
            LIMIT 50
        """
        
        results = DatabaseService.execute_query(query, params)
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/get_patients', methods=['GET'])
def get_patients():
    """Endpoint para obtener todos los pacientes con conteo de estudios reportados"""
    try:
        # Obtener user_id de la sesión
        user_id = session.get('_user_id')
        print(f"[DEBUG get_patients] user_id from session: {user_id}")
        if not user_id:
            print(f"[DEBUG get_patients] ERROR: No user_id in session, returning 401")
            return jsonify({"error": "Usuario no autenticado"}), 401
        
        query = """
            SELECT 
                dp.Guid,
                dp.Name,
                dp.Surname, 
                dp.NationalCode, 
                dp.SexCode, 
                dp.BirthDate,
                dp.phone,
                dp.email,
                dp.patientid,
                COALESCE(COUNT(CASE 
                    WHEN tbex.isreported = 1 
                    AND EXISTS (
                        SELECT 1 
                        FROM nextris.rel_user_location rul 
                        WHERE rul.user_id = %s 
                        AND rul.location_id = tbex.location_id
                    ) 
                    THEN 1 
                END), 0) as study_count
            FROM nextris.datapatient dp
            INNER JOIN nextris.rel_user_patientdomain rup 
                ON dp.id_patientdomain = rup.patientdomain_id
            LEFT JOIN nextris.tbexamination tbex ON tbex.idpatient = dp.patientid
            WHERE rup.user_id = %s
            GROUP BY dp.Guid, dp.Name, dp.Surname, dp.NationalCode, dp.SexCode, 
                     dp.BirthDate, dp.phone, dp.email, dp.patientid
            ORDER BY dp.Surname, dp.Name
            LIMIT 1000
        """
        
        raw_results = DatabaseService.execute_query(query, (user_id, user_id))
        
        # Reorganizar para que patientid no se muestre pero study_count sí
        # Orden final: Guid, Name, Surname, NationalCode, SexCode, BirthDate, phone, email, patientid (oculto en lógica), study_count
        # Mantenemos patientid en índice 8 para no romper la lógica existente
        results = []
        for row in raw_results:
            # row = [Guid, Name, Surname, NationalCode, SexCode, BirthDate, phone, email, patientid, study_count]
            results.append(row)  # Mantenemos el mismo orden
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Se usa para autocompletar en el frontend en citas
@blueprint.route('/get_patients_min', methods=['GET'])
def get_patients_min():
    """Endpoint para obtener información mínima de pacientes"""
    try:
        # Obtener user_id de la sesión
        user_id = session.get('_user_id')
        if not user_id:
            return jsonify({"error": "Usuario no autenticado"}), 401
        
        query = """
            SELECT dp.Guid, dp.Name, dp.Surname, dp.SexCode, 
                   TO_CHAR(dp.BirthDate, 'DD/MM/YYYY') as BirthDate, 
                   dp.NationalCode
            FROM nextris.datapatient dp
            INNER JOIN nextris.rel_user_patientdomain rup 
                ON dp.id_patientdomain = rup.patientdomain_id
            WHERE rup.user_id = %s
            ORDER BY dp.Surname, dp.Name
            LIMIT 500
        """
        
        results = DatabaseService.execute_query(query, (user_id,))
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/get_patient_history_for_report', methods=['POST'])
def get_patient_history_for_report():
    """Endpoint para obtener el historial de un paciente para reportes"""
    try:
        print("[DEBUG] Received request for patient history")
        data = request.get_json()
        patient_guid = data.get('id')
        
        if not patient_guid:
            return jsonify({'error': 'No se proporcionó el guid del paciente'}), 400

        # Buscar el patientid real a partir del guid
        patient_data = DatabaseService.get_patient_by_guid(patient_guid)
        if not patient_data:
            return jsonify([])
            
        patient_id = patient_data[0]
        print(f"[DEBUG] Patient ID for guid {patient_guid}: {patient_id}")

        # Traer historial de estudios previos
        query = '''
            SELECT ex.guid, st.description AS estudio, ex.reportdate
            FROM nextris.tbexamination ex
            INNER JOIN nextris.isstudytype st ON ex.studytype_id = st.guid
            WHERE ex.idpatient = %s AND ex.isreported = true
            ORDER BY ex.reportdate DESC
            LIMIT 10
        '''
        
        results = DatabaseService.execute_query(query, (patient_id,))
        
        # Convertir a formato JSON amigable
        history = []
        for row in results:
            history.append({
                'guid': row[0],
                'estudio': row[1],
                'fecha': row[2].strftime('%d/%m/%Y') if row[2] else None
            })
        
        return jsonify(history)
        
    except Exception as e:
        print(f"[ERROR] Error getting patient history: {str(e)}")
        return jsonify({"error": str(e)}), 500


@blueprint.route('/get_patient_cardio_history', methods=['POST'])
def get_patient_cardio_history():
    """Endpoint para obtener el historial cardiovascular de un paciente"""
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        
        if not patient_id:
            return jsonify({'error': 'No se proporcionó el ID del paciente'}), 400

        query = '''
            SELECT ex.guid, st.description, ex.createdon, ex.findings, ex.conclusions
            FROM nextris.tbexamination ex
            INNER JOIN nextris.isstudytype st ON ex.studytype_id = st.guid
            INNER JOIN nextris.ismodality m ON st.modality_id = m.guid
            WHERE ex.idpatient = %s 
            AND m.externalcode IN ('ECG', 'ECHO', 'CARDIO')
            ORDER BY ex.createdon DESC
            LIMIT 20
        '''
        
        results = DatabaseService.execute_query(query, (patient_id,))
        
        history = []
        for row in results:
            history.append({
                'guid': row[0],
                'description': row[1],
                'date': row[2].strftime('%d/%m/%Y %H:%M') if row[2] else None,
                'findings': row[3],
                'conclusions': row[4]
            })
        
        return jsonify(history)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/set_patient', methods=['GET'])
def set_patient():
    """Endpoint para establecer un paciente en la sesión"""
    try:
        patient_id = request.args.get('id')
        dni = request.args.get('dni')
        
        cita_data = session.get('cita', {})
        cita = Cita.from_dict(cita_data)
        cita.paciente_id = patient_id
        cita.paciente_dni = dni
        
        session['cita'] = cita.to_dict()
        
        print(f"Patient set: {cita.paciente_id}")
        return jsonify(cita.to_dict())
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/get_cantidad_estudios', methods=['POST'])
def get_cantidad_estudios():
    """Endpoint para obtener la cantidad de estudios de un paciente"""
    try:
        data = request.get_json()
        patient_id = data.get('id')
        
        if not patient_id:
            return jsonify({'error': 'No se proporcionó el ID del paciente'}), 400

        query = """
            SELECT COUNT(*) as cantidad
            FROM nextris.tbexamination 
            WHERE idpatient = %s
        """
        
        result = DatabaseService.execute_query(query, (patient_id,))
        cantidad = result[0][0] if result else 0
        
        return jsonify({"cantidad": cantidad})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/eliminar_paciente', methods=['POST'])
def eliminar_paciente():
    """Endpoint para eliminar un paciente"""
    try:
        data = request.get_json()
        print(f"[DEBUG] Data received for eliminar_paciente: {data}")
        patient_id = data.get('id')
        
        if not patient_id:
            return jsonify({'error': 'No se proporcionó el ID del paciente'}), 400

        # Verificar que no tenga estudios
        count_query = "SELECT COUNT(*) FROM nextris.tbexamination WHERE idpatient = %s"
        result = DatabaseService.execute_query(count_query, (patient_id,))
        count = result[0][0] if result else 0
        
        if count > 0:
            return jsonify({"success": False, "message": "No se puede eliminar el paciente porque tiene estudios asociados"}), 400

        # Eliminar el paciente
        delete_query = "DELETE FROM nextris.datapatient WHERE guid = %s"
        DatabaseService.execute_query(delete_query, (patient_id,), commit=True)
        
        return jsonify({"success": True, "message": "Paciente eliminado correctamente"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@blueprint.route('/get_patient_history', methods=['POST'])
def get_patient_history():
    """Endpoint para obtener el historial de estudios de un paciente"""
    try:
        data = request.get_json()
        patient_id = data.get('id')
        
        if not patient_id:
            return jsonify({'error': 'No se proporcionó el ID del paciente'}), 400

        query = """
            SELECT 
                ex.guid, 
                st.description AS estudio, 
                ex.createdon, 
                ex.isreported,
                CONCAT(us_reporter.name,' ',us_reporter.surname) as medico_autor, 
                ex.isimage, 
                mod.externalcode as modality,
                CONCAT(us_referring.name,' ',us_referring.surname) as medico_referente
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.isstudytype st ON ex.studytype_id = st.guid
			LEFT JOIN nextris.datapatient data on data.patientid=ex.idpatient
			LEFT JOIN nextris.tbreport rep on rep.idexamination=ex.guid
			LEFT JOIN nextris.tbuser us_reporter on us_reporter.guid=rep.idreporterphysician
			LEFT JOIN nextris.tbuser us_referring on us_referring.guid=rep.idreferringphysician
			LEFT JOIN nextris.ismodality mod on mod.guid=st.modality_id
            WHERE data.guid = %s and ex.isreported=1
            ORDER BY ex.createdon DESC
        """
        
        results = DatabaseService.execute_query(query, (patient_id,))
        
        # Formatear los resultados para el frontend
        history = []
        for row in results:
            history.append({
                'guid': row[0],
                'estudio': row[1] or 'Sin descripción',
                'medico_autor': row[4] or 'No asignado',
                'medico_referente': row[7] or 'No asignado',
                'fecha': row[2].strftime('%d/%m/%Y %H:%M') if row[2] else 'Sin fecha',
                'modalidad': row[6] or 'N/A',
                'con_imagen': 'Sí' if row[5] == 1 else 'No',
                'isreported': row[3]
            })
        
        return jsonify(history)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/editar_paciente', methods=['POST'])
def editar_paciente():
    """Endpoint para editar los datos de un paciente"""
    try:
        # Obtener datos del formulario
        r = request.form.to_dict()
        patient_id = r.get('id_np')  # ID del paciente a editar
        
        if not patient_id:
            return jsonify({'error': 'No se proporcionó el ID del paciente'}), 400

        # Query para actualizar el paciente
        query = """
            UPDATE nextris.DataPatient SET 
                Surname = %s, Name = %s, NationalCode = %s, BirthDate = %s, 
                SexCode = %s, Phone = %s, Email = %s, HealthCard = %s
            WHERE guid = %s
        """
        
        params = (
            r.get('p_surname', ''),
            r.get('p_name', ''),
            r.get('p_dni', ''),
            r.get('fecha_nacimiento', None),
            r.get('sex', ''),
            r.get('telefono', ''),
            r.get('mail', ''),
            r.get('p_healthcard', ''),
            patient_id
        )
        
        # Ejecutar la actualización
        rows_affected = DatabaseService.execute_query(query, params, fetch_all=False, commit=True)
        
        if rows_affected > 0:
            # Crear la devolución como arreglo para mantener el orden
            devolucion = [
                r.get('p_name', ''),        # nombre
                r.get('p_surname', ''),     # apellido  
                r.get('p_dni', ''),         # dni
                r.get('sex', ''),           # sexo
                r.get('fecha_nacimiento', ''), # fecha_de_nac
                r.get('telefono', ''),      # telefono
                r.get('mail', ''),          # mail
                r.get('p_healthcard', '')   # p_healthcard
            ]
            
            return jsonify(devolucion)
        else:
            return jsonify({"error": "No se pudo actualizar el paciente"}), 400
        
    except Exception as e:
        print(f"[ERROR] Error editando paciente: {e}")
        return jsonify({"error": str(e)}), 500


@blueprint.route('/unificar_paciente', methods=['POST'])
def unificar_paciente():
    """Endpoint para unificar datos de pacientes duplicados"""

    print("[DEBUG] Received request to unify patients")
    try:
        data = request.get_json()
        print(f"[DEBUG] Data received: {data}")
        
        # El JS envía GUIDs (id_correcto e id_eliminar)
        patient_master_guid = data.get('id_correcto')
        patient_duplicate_guid = data.get('id_eliminar')
        
        print(f"[DEBUG] Unifying patients: master_guid={patient_master_guid}, duplicate_guid={patient_duplicate_guid}")
        
        if not patient_master_guid or not patient_duplicate_guid:
            return jsonify({'error': 'Se requieren los IDs de ambos pacientes'}), 400

        # Obtener los PatientId correspondientes a los GUIDs
        patient_query = """
            SELECT PatientId FROM nextris.datapatient WHERE Guid = %s
        """
        
        # Obtener PatientId del paciente maestro
        master_result = DatabaseService.execute_query(patient_query, (patient_master_guid,))
        if not master_result:
            return jsonify({'error': 'No se encontró el paciente maestro'}), 400
        patient_master_id = master_result[0][0]
        
        # Obtener PatientId del paciente duplicado
        duplicate_result = DatabaseService.execute_query(patient_query, (patient_duplicate_guid,))
        if not duplicate_result:
            return jsonify({'error': 'No se encontró el paciente duplicado'}), 400
        patient_duplicate_id = duplicate_result[0][0]
        
        print(f"[DEBUG] Converting GUIDs to PatientIds: master={patient_master_id}, duplicate={patient_duplicate_id}")

        # Actualizar todas las referencias al paciente duplicado usando PatientId
        queries = [
            ("UPDATE nextris.tbexamination SET idpatient = %s WHERE idpatient = %s", 
             (patient_master_id, patient_duplicate_id)),
            ("UPDATE nextris.tbreport SET idpatient = %s WHERE idpatient = %s", 
             (patient_master_id, patient_duplicate_id)),
            ("DELETE FROM nextris.datapatient WHERE Guid = %s", 
             (patient_duplicate_guid,))
        ]
        
        DatabaseService.execute_transaction(queries)
        
        return jsonify({"success": True, "message": "Pacientes unificados correctamente"})
        
    except Exception as e:
        print(f"[ERROR] Error unifying patients: {str(e)}")
        return jsonify({"error": str(e)}), 500


@blueprint.route('/get_image_link', methods=['POST'])
def get_image_link():
    """Endpoint para obtener el enlace de imágenes de un estudio"""
    try:
        data = request.get_json()
        exam_id = data.get('id')
        
        if not exam_id:
            return jsonify(['', 0]), 400

        # Buscar el studyInstanceUID del examen
        query = """
            SELECT studyinstanceuid
            FROM nextris.tbexamination 
            WHERE guid = %s
        """
        
        result = DatabaseService.execute_query(query, (exam_id,))
        
        if result and len(result) > 0:
            study_uid = result[0][0]
            if study_uid:
                return jsonify([study_uid, 1])
        
        return jsonify(['', 0])
        
    except Exception as e:
        return jsonify(['', 0])
    

@blueprint.route('/get_estudios_reasignar', methods=['GET']) 
def get_estudios_reasignar():
    # Modificamos la consulta para incluir un JOIN con la tabla isstudytype
    query = """
        SELECT ex.guid,ex.createdon, ex.localacc, pat.patientid as patid, CONCAT(pat.surname, ' ',pat.name) as nombre, pat.birthdate as dob,st.description as estudio, ex.status
        FROM nextris.tbexamination ex
        LEFT JOIN datapatient as pat on pat.patientid=ex.idpatient
        LEFT JOIN isstudytype as st on st.guid=ex.studytype_id
        ORDER BY ex.createdon ASC LIMIT 100
    """

    result = DatabaseService.execute_query(query, commit=True)
    return jsonify(result)


@blueprint.route('/get_pacientes_reasignar', methods=['GET']) 
def get_pacientes_reasignar():
    try:
        # Obtener user_id de la sesión
        user_id = session.get('_user_id')
        if not user_id:
            return jsonify({"error": "Usuario no autenticado"}), 401
        
        query = """
            SELECT dp.Guid, dp.name, dp.surname, dp.NationalCode, dp.Sexcode, 
                   dp.BirthDate, dp.phone, dp.email, dp.healthcard 
            FROM nextris.datapatient dp
            INNER JOIN nextris.rel_user_patientdomain rup 
                ON dp.id_patientdomain = rup.patientdomain_id
            WHERE rup.user_id = %s
        """
        result = DatabaseService.execute_query(query, (user_id,), commit=True)

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@blueprint.route('/reasignar_estudio', methods=['POST'])
def reasignar_estudio():
    """Endpoint para reasignar un estudio a otro paciente"""
    try:
        data = request.get_json()
        estudio_id = data.get('estudio_id')
        paciente_guid = data.get('paciente_id')  # Este es un GUID
        
        print(f"[DEBUG] Reasignando estudio {estudio_id} a paciente {paciente_guid}")
        
        if not estudio_id or not paciente_guid:
            return jsonify({'success': False, 'message': 'Faltan datos: estudio_id y paciente_id son requeridos'}), 400
        
        # Obtener el PatientId correspondiente al GUID del paciente
        patient_query = "SELECT patientid FROM nextris.datapatient WHERE guid = %s"
        patient_result = DatabaseService.execute_query(patient_query, (paciente_guid,))
        
        if not patient_result:
            return jsonify({'success': False, 'message': 'No se encontró el paciente especificado'}), 400
        
        patient_id = patient_result[0][0]
        print(f"[DEBUG] PatientId obtenido: {patient_id}")
        
        # Verificar que el estudio existe
        exam_query = "SELECT guid FROM nextris.tbexamination WHERE guid = %s"
        exam_result = DatabaseService.execute_query(exam_query, (estudio_id,))
        
        if not exam_result:
            return jsonify({'success': False, 'message': 'No se encontró el estudio especificado'}), 400
        
        # Actualizar el estudio con el nuevo paciente
        update_query = "UPDATE nextris.tbexamination SET idpatient = %s WHERE guid = %s"
        DatabaseService.execute_query(update_query, (patient_id, estudio_id), commit=True)
        
        print(f"[DEBUG] Estudio reasignado exitosamente")
        
        return jsonify({
            'success': True, 
            'message': f'Estudio reasignado correctamente al paciente {patient_id}'
        })
        
    except Exception as e:
        print(f"[ERROR] Error reasignando estudio: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@blueprint.route('/edit_mail', methods=['POST'])
def edit_mail():
    """Endpoint para editar el email de un paciente"""
    try:
        data = request.get_json()
        data_id_examination = data.get('id_order')
        mail = data.get('mail')
        
        print(f"[DEBUG] Editando email para examen: {data_id_examination}, nuevo email: {mail}")
        
        # Actualizar el email del paciente asociado al examen
        query = """
            UPDATE nextris.datapatient
            SET email = %s
            WHERE patientid = (
                SELECT idpatient 
                FROM nextris.tbexamination 
                WHERE guid = %s
            )
        """
        
        DatabaseService.execute_query(query, (mail, data_id_examination), commit=True)
        
        print(f"[DEBUG] Email actualizado exitosamente")
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"[ERROR] Error editando email: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@blueprint.route('/get_user_locations', methods=['GET'])
def get_user_locations():
    """Endpoint para obtener las ubicaciones del usuario autenticado"""
    try:
        # Obtener user_id de la sesión
        user_id = session.get('_user_id')
        if not user_id:
            return jsonify({"error": "Usuario no autenticado"}), 401
        
        query = """
            SELECT 
                loc.guid,
                loc.name,
                loc.code,
                loc.facility_id,
                rul.is_default
            FROM nextris.tblocation loc
            INNER JOIN nextris.rel_user_location rul 
                ON loc.guid = rul.location_id
            WHERE rul.user_id = %s
            AND loc.status = 'Active'
            ORDER BY rul.is_default DESC, loc.name
        """
        
        results = DatabaseService.execute_query(query, (user_id,))
        
        return jsonify(results)
        
    except Exception as e:
        print(f"[ERROR] Error obteniendo ubicaciones del usuario: {str(e)}")
        return jsonify({"error": str(e)}), 500


@blueprint.route('/get_patients_by_location', methods=['POST'])
def get_patients_by_location():
    """Endpoint para obtener pacientes filtrados por ubicación"""
    try:
        data = request.get_json()
        location_id = data.get('location_id')
        
        if not location_id:
            return jsonify({"error": "location_id requerido"}), 400
        
        print(f"[DEBUG get_patients_by_location] location_id recibido: {location_id}")
        
        # Obtener el id_patientdomain de la ubicación
        domain_query = """
            SELECT id_patientdomain 
            FROM nextris.tblocation 
            WHERE guid = %s
        """
        domain_result = DatabaseService.execute_query(domain_query, (location_id,))
        
        print(f"[DEBUG get_patients_by_location] domain_result: {domain_result}")
        
        if not domain_result or not domain_result[0][0]:
            print(f"[DEBUG get_patients_by_location] No se encontró dominio para esta ubicación")
            return jsonify([])
        
        patientdomain_id = domain_result[0][0]
        print(f"[DEBUG get_patients_by_location] patientdomain_id: {patientdomain_id}")
        
        # Traer todos los pacientes con ese id_patientdomain
        query = """
            SELECT dp.Guid, dp.Name, dp.Surname, dp.SexCode, 
                   TO_CHAR(dp.BirthDate, 'DD/MM/YYYY') as BirthDate, 
                   dp.NationalCode
            FROM nextris.datapatient dp
            WHERE dp.id_patientdomain = %s
            ORDER BY dp.Surname, dp.Name
            LIMIT 500
        """
        
        results = DatabaseService.execute_query(query, (patientdomain_id,))
        print(f"[DEBUG get_patients_by_location] Pacientes encontrados: {len(results) if results else 0}")
        
        return jsonify(results)
        
    except Exception as e:
        print(f"[ERROR] Error obteniendo pacientes por ubicación: {str(e)}")
        return jsonify({"error": str(e)}), 500