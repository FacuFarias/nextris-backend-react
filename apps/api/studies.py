# -*- encoding: utf-8 -*-
"""
API de Estudios (Examinations) - Endpoints para gestión de estudios médicos
Migrado desde examination_controller.py - 19 endpoints REST
"""

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
import psycopg2
import pytz
from datetime import datetime, timedelta
from apps.api import api_blueprint


def get_db_config():
    """Obtiene la configuración de la base de datos"""
    from apps.home.routes import config as db_config
    return db_config


def get_user_locations(user_id, connection):
    """Obtiene las ubicaciones asignadas a un usuario"""
    cursor = connection.cursor()
    cursor.execute("""
        SELECT location_id 
        FROM nextris.rel_user_location 
        WHERE user_id = %s
    """, (user_id,))
    locations = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return locations


def null_if_no_clasifica(val):
    """Convierte 'no clasifica' a None para campos opcionales"""
    return None if val and val.lower().strip() == 'no clasifica' else val


# ==================== ENDPOINTS DE EXÁMENES ====================

@api_blueprint.route('/examinations/<guid>', methods=['GET'])
@jwt_required()
def get_examination_details(guid):
    """
    Obtiene detalles completos de un examen específico
    
    GET /api/examinations/<guid>
    
    Response:
    {
        "success": true,
        "data": {
            "guid": "...",
            "study_type": "...",
            "patient_id": "...",
            "patient_name": "...",
            "status": "...",
            "created_on": "...",
            "is_reported": 0/1,
            "study_instance_uid": "..."
        }
    }
    """
    try:
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener examen
        cursor.execute("""
            SELECT 
                e.Guid, e.studytype_id, e.IdPatient, e.Status, 
                e.CreatedOn, e.IsReported, e.StudyInstanceUID
            FROM nextris.tbexamination e
            WHERE e.Guid = %s
        """, (guid,))
        
        exam = cursor.fetchone()
        if not exam:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Examen no encontrado'}), 404
        
        # Obtener tipo de estudio
        cursor.execute("""
            SELECT Description 
            FROM nextris.isstudytype 
            WHERE Guid = %s
        """, (exam[1],))
        study_type_row = cursor.fetchone()
        study_type = study_type_row[0] if study_type_row else None
        
        # Obtener información del paciente
        cursor.execute("""
            SELECT Name, Surname 
            FROM nextris.datapatient 
            WHERE Guid = %s
        """, (exam[2],))
        patient_row = cursor.fetchone()
        patient_name = f"{patient_row[0]} {patient_row[1]}" if patient_row else ""
        
        cursor.close()
        connection.close()
        
        result = {
            'guid': exam[0],
            'study_type': study_type,
            'patient_id': exam[2],
            'patient_name': patient_name,
            'status': exam[3],
            'created_on': exam[4].strftime('%d/%m/%Y %H:%M') if exam[4] else None,
            'is_reported': 1 if exam[5] else 0,
            'study_instance_uid': exam[6]
        }
        
        return jsonify({'success': True, 'data': result}), 200
        
    except Exception as e:
        print(f"[API EXAMINATION DETAILS] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/examinations', methods=['GET'])
@jwt_required()
def get_examinations():
    """
    Obtiene lista de todos los exámenes (últimos 1000)
    
    GET /api/examinations
    
    Response:
    {
        "success": true,
        "data": [
            ["guid", "fecha", "nombre", "dni", "sexo", "estudio", "status", "severidad", "medico_ref"],
            ...
        ]
    }
    """
    try:
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT 
                e.Guid, e.CreatedOn, e.IdPatient, e.LocalAcc, 
                e.studytype_id, e.Status, e.IdSeverity, e.IdReferringPhysician,
                st.Description as study_type,
                sev.Description as severity,
                dp.Name, dp.Surname, dp.nationalcode, dp.sexcode
            FROM nextris.tbexamination e
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.IsSeverity sev ON e.IdSeverity = sev.Guid
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            ORDER BY e.CreatedOn DESC
            LIMIT 1000
        """)
        
        results = []
        for row in cursor.fetchall():
            nombre = f"{row[10]} {row[11]}" if row[10] and row[11] else ''
            dni = row[12] if row[12] else ''
            sex = row[13] if row[13] else ''
            study_type = row[8] if row[8] else ''
            severity = row[9] if row[9] else ''
            
            # Obtener médico referente (si existe)
            medico_ref = ''
            if row[7]:
                cursor.execute("""
                    SELECT username 
                    FROM nextris.tbuser 
                    WHERE guid = %s
                """, (row[7],))
                medico_row = cursor.fetchone()
                medico_ref = medico_row[0] if medico_row else ''
            
            results.append([
                row[0],  # guid
                row[1].strftime('%d/%m/%Y %H:%M') if row[1] else '',  # fecha
                nombre,
                dni,
                sex,
                study_type,
                row[5],  # status
                severity,
                medico_ref
            ])
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'data': results}), 200
        
    except Exception as e:
        print(f"[API EXAMINATIONS] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/examinations/filtered', methods=['POST'])
@jwt_required()
def get_examination_items_filtrado():
    """
    Obtiene exámenes filtrados según criterios específicos
    Filtra por ubicaciones del usuario
    
    POST /api/examinations/filtered
    Body:
    {
        "filters": { ... },
        "include_reported": false
    }
    
    Response:
    {
        "success": true,
        "data": [
            ["guid", "fecha", "nombre", "dni", "sexo", "estudio", "status", "severidad", "isreported", "isimage"],
            ...
        ]
    }
    """
    try:
        data = request.get_json()
        filters = data.get('filters', {})
        include_reported = data.get('include_reported', False)
        
        # Obtener usuario actual
        user_id = get_jwt_identity()
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        
        # Obtener ubicaciones del usuario
        user_locations = get_user_locations(user_id, connection)
        
        if not user_locations:
            connection.close()
            return jsonify({'success': True, 'data': []}), 200
        
        cursor = connection.cursor()
        
        # Construir query con filtros
        where_clauses = []
        params = []
        
        # Filtro por ubicaciones
        location_placeholders = ','.join(['%s'] * len(user_locations))
        where_clauses.append(f"eq.location_id IN ({location_placeholders})")
        params.extend(user_locations)
        
        # Filtro de reportados
        if not include_reported:
            where_clauses.append("(e.IsReported IS NULL OR e.IsReported != 1)")
        
        # Aplicar filtros adicionales del request
        # (aquí puedes agregar más filtros según necesites)
        
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        query = f"""
            SELECT 
                e.Guid, e.CreatedOn, 
                dp.Name, dp.Surname, dp.nationalcode, dp.sexcode,
                st.Description as study_type,
                e.Status,
                sev.Description as severity,
                COALESCE(e.IsReported, 0) as isreported,
                COALESCE(e.IsImage, 0) as isimage
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.IsSeverity sev ON e.IdSeverity = sev.Guid
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            {where_sql}
            ORDER BY e.CreatedOn DESC
            LIMIT 500
        """
        
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            nombre = f"{row[2]} {row[3]}" if row[2] and row[3] else ''
            results.append([
                row[0],  # guid
                row[1].strftime('%d/%m/%Y %H:%M') if row[1] else '',  # fecha
                nombre,
                row[4] if row[4] else '',  # dni
                row[5] if row[5] else '',  # sexo
                row[6] if row[6] else '',  # estudio
                row[7] if row[7] else '',  # status
                row[8] if row[8] else '',  # severidad
                row[9],  # isreported
                row[10]  # isimage
            ])
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'data': results}), 200
        
    except Exception as e:
        print(f"[API EXAMINATIONS FILTERED] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/examinations/assigned/<medico_id>', methods=['POST'])
@jwt_required()
def get_examination_items_asignados(medico_id):
    """
    Obtiene exámenes asignados a un médico específico
    
    POST /api/examinations/assigned/<medico_id>
    Body:
    {
        "include_reported": false
    }
    
    Response: Igual que /examinations/filtered
    """
    try:
        data = request.get_json()
        include_reported = data.get('include_reported', False)
        
        user_id = get_jwt_identity()
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        user_locations = get_user_locations(user_id, connection)
        
        if not user_locations:
            connection.close()
            return jsonify({'success': True, 'data': []}), 200
        
        cursor = connection.cursor()
        
        where_clauses = [f"eq.location_id IN ({','.join(['%s'] * len(user_locations))})"]
        params = list(user_locations)
        
        where_clauses.append("e.assignto = %s")
        params.append(medico_id)
        
        if not include_reported:
            where_clauses.append("(e.IsReported IS NULL OR e.IsReported != 1)")
        
        where_sql = "WHERE " + " AND ".join(where_clauses)
        
        query = f"""
            SELECT 
                e.Guid, e.CreatedOn, 
                dp.Name, dp.Surname, dp.nationalcode, dp.sexcode,
                st.Description as study_type,
                e.Status,
                sev.Description as severity,
                COALESCE(e.IsReported, 0) as isreported,
                COALESCE(e.IsImage, 0) as isimage
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.IsSeverity sev ON e.IdSeverity = sev.Guid
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            {where_sql}
            ORDER BY e.CreatedOn DESC
            LIMIT 500
        """
        
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            nombre = f"{row[2]} {row[3]}" if row[2] and row[3] else ''
            results.append([
                row[0], row[1].strftime('%d/%m/%Y %H:%M') if row[1] else '',
                nombre, row[4] if row[4] else '', row[5] if row[5] else '',
                row[6] if row[6] else '', row[7] if row[7] else '',
                row[8] if row[8] else '', row[9], row[10]
            ])
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'data': results}), 200
        
    except Exception as e:
        print(f"[API EXAMINATIONS ASSIGNED] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/worklist', methods=['POST'])
@jwt_required()
def create_worklist():
    """
    Crea elementos en el worklist DICOM
    
    POST /api/worklist
    Body:
    {
        "patientId": "...",
        "exams": [
            {
                "studyTypeId": "...",
                "equipmentId": "...",
                "severityId": "...",
                "referringPhysicianId": "...",
                "requestingPhysicianId": "..."
            },
            ...
        ]
    }
    
    Response:
    {
        "success": true,
        "message": "Se crearon X de Y exámenes en el worklist",
        "created_exams": ["guid1", "guid2", ...]
    }
    """
    try:
        data = request.get_json()
        patient_id = data.get('patientId')
        exams = data.get('exams', [])
        
        if not patient_id or not exams:
            return jsonify({
                'success': False,
                'message': 'patientId y exams son requeridos'
            }), 400
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        created_exams = []
        errors = []
        
        for exam in exams:
            try:
                # Generar admnumber
                cursor.execute("""
                    SELECT COALESCE(MAX(CAST(SUBSTRING(admnumber FROM 4) AS INTEGER)), 0) + 1
                    FROM nextris.tbexamination
                    WHERE admnumber LIKE 'ADM%'
                """)
                next_adm = cursor.fetchone()[0]
                adm_number = f"ADM{next_adm:03d}"
                
                # Generar LocalAcc
                cursor.execute("""
                    SELECT COALESCE(MAX(CAST(SUBSTRING(LocalAcc FROM 4) AS INTEGER)), 0) + 1
                    FROM nextris.tbexamination
                    WHERE LocalAcc LIKE 'ACC%'
                """)
                next_acc = cursor.fetchone()[0]
                local_acc = f"ACC{next_acc:03d}"
                
                # Insertar examen
                cursor.execute("""
                    INSERT INTO nextris.tbexamination (
                        IdPatient, studytype_id, IdEquipment, IdSeverity,
                        IdReferringPhysician, IdRequestingPhysician,
                        admisionnumber, LocalAcc, Status, CreatedOn, IsExecuted
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, 'Scheduled', NOW(), 0
                    ) RETURNING Guid
                """, (
                    patient_id,
                    exam.get('studyTypeId'),
                    exam.get('equipmentId'),
                    exam.get('severityId'),
                    exam.get('referringPhysicianId'),
                    exam.get('requestingPhysicianId'),
                    adm_number,
                    local_acc
                ))
                
                exam_guid = cursor.fetchone()[0]
                
                # Crear entrada en tbReport
                cursor.execute("""
                    INSERT INTO nextris.tbReport (
                        IdExamination, IdPatient, admnumber, 
                        CreatedOn, WasSaved
                    ) VALUES (
                        %s, %s, %s, NOW(), 0
                    )
                """, (exam_guid, patient_id, adm_number))
                
                created_exams.append(exam_guid)
                
                # Aquí se enviaría el mensaje HL7
                # HL7Service.send_worklist_message(exam_guid, patient_id, ...)
                
            except Exception as exam_error:
                errors.append(f"Error creando examen: {str(exam_error)}")
                continue
        
        connection.commit()
        cursor.close()
        connection.close()
        
        message = f"Se crearon {len(created_exams)} de {len(exams)} exámenes en el worklist"
        if errors:
            message += f". Errores: {'; '.join(errors)}"
        
        return jsonify({
            'success': True,
            'message': message,
            'created_exams': created_exams,
            'total_requested': len(exams),
            'total_created': len(created_exams)
        }), 200 if len(created_exams) > 0 else 500
        
    except Exception as e:
        print(f"[API WORKLIST CREATE] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/worklist/<exam_id>', methods=['DELETE'])
@jwt_required()
def cancel_worklist(exam_id):
    """
    Cancela un elemento del worklist DICOM
    
    DELETE /api/worklist/<exam_id>
    
    Response:
    {
        "success": true,
        "message": "Examen cancelado correctamente"
    }
    """
    try:
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Verificar que existe el examen
        cursor.execute("""
            SELECT Guid 
            FROM nextris.tbexamination 
            WHERE Guid = %s
        """, (exam_id,))
        
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Examen no encontrado'}), 404
        
        # Cancelar examen
        cursor.execute("""
            UPDATE nextris.tbexamination 
            SET Status = 'Cancelled', IsExecuted = 1
            WHERE Guid = %s
        """, (exam_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # Aquí se enviaría mensaje HL7 de cancelación
        # HL7Service.send_cancellation_message(exam_id)
        
        return jsonify({
            'success': True,
            'message': 'Examen cancelado correctamente'
        }), 200
        
    except Exception as e:
        print(f"[API WORKLIST CANCEL] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/examinations/orders', methods=['GET'])
@jwt_required()
def get_orders_ex():
    """
    Obtiene órdenes de exámenes pendientes (no ejecutadas)
    Filtradas por ubicaciones del usuario
    
    GET /api/examinations/orders
    
    Response:
    {
        "success": true,
        "data": [
            ["guid", "fecha", "apellido", "nombre", "descripción_examen", 
             "status", "equipo_desc", "adm_number", "local_acc"],
            ...
        ]
    }
    """
    try:
        user_id = get_jwt_identity()
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        user_locations = get_user_locations(user_id, connection)
        
        if not user_locations:
            connection.close()
            return jsonify({'success': True, 'data': []}), 200
        
        cursor = connection.cursor()
        
        location_placeholders = ','.join(['%s'] * len(user_locations))
        
        query = f"""
            SELECT 
                e.Guid, e.CreatedOn,
                dp.Surname, dp.Name,
                st.Description as study_type,
                e.Status,
                eq.Description as equipment,
                e.admisionnumber, e.LocalAcc
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            WHERE e.IsExecuted = 0
            AND eq.location_id IN ({location_placeholders})
            ORDER BY e.CreatedOn DESC
        """
        
        cursor.execute(query, user_locations)
        
        results = []
        for row in cursor.fetchall():
            results.append([
                row[0],  # guid
                row[1].strftime('%d/%m/%Y %H:%M') if row[1] else '',
                row[2] if row[2] else '',  # apellido
                row[3] if row[3] else '',  # nombre
                row[4] if row[4] else '',  # estudio
                row[5] if row[5] else '',  # status
                row[6] if row[6] else '',  # equipo
                row[7] if row[7] else '',  # adm_number
                row[8] if row[8] else ''   # local_acc
            ])
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'data': results}), 200
        
    except Exception as e:
        print(f"[API ORDERS] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/examinations/verify-assignability', methods=['POST'])
@jwt_required()
def verify_assignability():
    """
    Verifica si un médico puede ser asignado a un tipo de estudio
    
    POST /api/examinations/verify-assignability
    Body:
    {
        "medico_id": "...",
        "study_type_id": "..."
    }
    
    Response:
    {
        "success": true,
        "can_assign": true/false,
        "message": "..."
    }
    """
    try:
        data = request.get_json()
        medico_id = data.get('medico_id')
        study_type_id = data.get('study_type_id')
        
        if not medico_id or not study_type_id:
            return jsonify({
                'success': False,
                'message': 'medico_id y study_type_id son requeridos'
            }), 400
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener el studygroup_id del tipo de estudio
        cursor.execute("""
            SELECT studygroup_id 
            FROM nextris.isstudytype 
            WHERE Guid = %s
        """, (study_type_id,))
        
        study_group_row = cursor.fetchone()
        if not study_group_row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Tipo de estudio no encontrado'
            }), 404
        
        study_group_id = study_group_row[0]
        
        # Verificar si el médico está autorizado
        cursor.execute("""
            SELECT COUNT(*) 
            FROM nextris.tbmedico_estudio_grupo
            WHERE medico_id = %s AND studygroup_id = %s
        """, (medico_id, study_group_id))
        
        count = cursor.fetchone()[0]
        can_assign = count > 0
        
        cursor.close()
        connection.close()
        
        message = 'Asignación permitida' if can_assign else 'El médico no está autorizado para este tipo de estudio'
        
        return jsonify({
            'success': True,
            'can_assign': can_assign,
            'message': message
        }), 200
        
    except Exception as e:
        print(f"[API VERIFY ASSIGNABILITY] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/study-types', methods=['GET'])
@jwt_required()
def get_study_types():
    """
    Obtiene catálogo de tipos de estudios
    
    GET /api/study-types
    
    Response:
    {
        "success": true,
        "data": [
            ["guid", "code", "description", "modality_code", "bodypart_desc", "studygroup_desc", "modality_id"],
            ...
        ]
    }
    """
    try:
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT 
                st.Guid, st.Code, st.Description,
                m.externalcode as modality_code,
                bp.Description as bodypart,
                sg.Description as studygroup,
                st.modality_id
            FROM nextris.isstudytype st
            LEFT JOIN nextris.ismodality m ON st.modality_id = m.Guid
            LEFT JOIN nextris.isanatomicalpart bp ON st.bodypart_id = bp.Guid
            LEFT JOIN nextris.isstudytypegroup sg ON st.studygroup_id = sg.Guid
            ORDER BY st.Description
        """)
        
        results = []
        for row in cursor.fetchall():
            results.append([
                row[0],  # guid
                row[1] if row[1] else '',  # code
                row[2] if row[2] else '',  # description
                row[3] if row[3] else '',  # modality_code
                row[4] if row[4] else '',  # bodypart
                row[5] if row[5] else '',  # studygroup
                row[6] if row[6] else ''   # modality_id
            ])
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'data': results}), 200
        
    except Exception as e:
        print(f"[API STUDY TYPES] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/equipment', methods=['GET'])
@jwt_required()
def get_equipment_list():
    """
    Obtiene lista de equipos activos
    
    GET /api/equipment?location_id=xxx
    
    Response:
    {
        "success": true,
        "data": [
            ["guid", "aetitle", "description"],
            ...
        ]
    }
    """
    try:
        location_id = request.args.get('location_id')
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        query = """
            SELECT Guid, AETitle, Description
            FROM nextris.isequipment
            WHERE isactive = TRUE
        """
        params = []
        
        if location_id:
            query += " AND location_id = %s"
            params.append(location_id)
        
        query += " ORDER BY AETitle"
        
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            results.append([
                row[0],  # guid
                row[1] if row[1] else '',  # aetitle
                row[2] if row[2] else ''   # description
            ])
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'data': results}), 200
        
    except Exception as e:
        print(f"[API EQUIPMENT] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/equipment/by-modality', methods=['POST'])
@jwt_required()
def get_equipment_by_modality():
    """
    Obtiene equipos compatibles con la modalidad de un estudio
    
    POST /api/equipment/by-modality
    Body:
    {
        "study_type_id": "...",
        "location_id": "..." (opcional)
    }
    
    Response:
    {
        "success": true,
        "data": [
            ["guid", "aetitle", "description"],
            ...
        ]
    }
    """
    try:
        data = request.get_json()
        study_type_id = data.get('study_type_id')
        location_id = data.get('location_id')
        
        if not study_type_id:
            return jsonify({
                'success': False,
                'message': 'study_type_id es requerido'
            }), 400
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener modality_id del tipo de estudio
        cursor.execute("""
            SELECT modality_id 
            FROM nextris.isstudytype 
            WHERE Guid = %s
        """, (study_type_id,))
        
        modality_row = cursor.fetchone()
        if not modality_row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Tipo de estudio no encontrado'
            }), 404
        
        modality_id = modality_row[0]
        
        # Obtener equipos compatibles
        query = """
            SELECT Guid, AETitle, Description
            FROM nextris.isequipment
            WHERE idmodality = %s AND isactive = TRUE
        """
        params = [modality_id]
        
        if location_id:
            query += " AND location_id = %s"
            params.append(location_id)
        
        query += " ORDER BY AETitle"
        
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            results.append([
                row[0],
                row[1] if row[1] else '',
                row[2] if row[2] else ''
            ])
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'data': results}), 200
        
    except Exception as e:
        print(f"[API EQUIPMENT BY MODALITY] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/appointments/equipment', methods=['POST'])
@jwt_required()
def create_appointment_equipment():
    """
    Crea citas/eventos en agenda por equipo
    
    POST /api/appointments/equipment
    Body:
    {
        "patientId": "...",
        "exams": [
            {
                "title": "...",
                "id": "...",
                "profesional": "..." (equipment_id),
                "init": "...",
                "finish": "...",
                "medico_solicitante": "..." (opcional),
                "rads": "..." (opcional)
            },
            ...
        ]
    }
    
    Response:
    {
        "success": true,
        "message": "Citas creadas correctamente"
    }
    """
    try:
        data = request.get_json()
        patient_id = data.get('patientId')
        exams = data.get('exams', [])
        
        if not patient_id or not exams:
            return jsonify({
                'success': False,
                'message': 'patientId y exams son requeridos'
            }), 400
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Zona horaria Argentina
        tz_argentina = pytz.timezone('America/Argentina/Buenos_Aires')
        
        for exam in exams:
            try:
                # Convertir timestamps
                init_time = datetime.fromisoformat(exam.get('init').replace('Z', '+00:00'))
                finish_time = datetime.fromisoformat(exam.get('finish').replace('Z', '+00:00'))
                
                # Ajustar a zona horaria Argentina
                init_time = init_time - timedelta(hours=3)
                finish_time = finish_time - timedelta(hours=3)
                
                medico_solicitante = exam.get('medico_solicitante')
                rads = exam.get('rads')
                
                cursor.execute("""
                    INSERT INTO nextris.tbagendaevents (
                        title, idpatient, equipment_id, init, finish,
                        medico_solicitante, rads, examid
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    exam.get('title'),
                    patient_id,
                    exam.get('profesional'),  # equipment_id
                    init_time,
                    finish_time,
                    medico_solicitante if medico_solicitante else None,
                    rads if rads else None,
                    exam.get('id')
                ))
                
            except Exception as exam_error:
                print(f"[API APPOINTMENTS EQUIPMENT] Error en examen: {str(exam_error)}")
                continue
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Citas creadas correctamente'
        }), 200
        
    except Exception as e:
        print(f"[API APPOINTMENTS EQUIPMENT] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/appointments/medico', methods=['POST'])
@jwt_required()
def create_appointment_medico():
    """
    Crea citas/eventos en agenda por médico
    
    POST /api/appointments/medico
    Body: Igual que /appointments/equipment, pero 'profesional' es el médico
    
    Response:
    {
        "success": true,
        "message": "Citas creadas correctamente"
    }
    """
    try:
        data = request.get_json()
        patient_id = data.get('patientId')
        exams = data.get('exams', [])
        
        if not patient_id or not exams:
            return jsonify({
                'success': False,
                'message': 'patientId y exams son requeridos'
            }), 400
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        tz_argentina = pytz.timezone('America/Argentina/Buenos_Aires')
        
        for exam in exams:
            try:
                init_time = datetime.fromisoformat(exam.get('init').replace('Z', '+00:00'))
                finish_time = datetime.fromisoformat(exam.get('finish').replace('Z', '+00:00'))
                
                init_time = init_time - timedelta(hours=3)
                finish_time = finish_time - timedelta(hours=3)
                
                medico_solicitante = exam.get('medico_solicitante')
                rads = exam.get('rads')
                
                cursor.execute("""
                    INSERT INTO nextris.tbagendaevents (
                        title, idpatient, medico_id, init, finish,
                        medico_solicitante, rads, examid
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    exam.get('title'),
                    patient_id,
                    exam.get('profesional'),  # medico_id
                    init_time,
                    finish_time,
                    medico_solicitante if medico_solicitante else None,
                    rads if rads else None,
                    exam.get('id')
                ))
                
            except Exception as exam_error:
                print(f"[API APPOINTMENTS MEDICO] Error en examen: {str(exam_error)}")
                continue
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Citas creadas correctamente'
        }), 200
        
    except Exception as e:
        print(f"[API APPOINTMENTS MEDICO] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/examinations/<exam_id>/execute', methods=['POST'])
@jwt_required()
def execute_examination(exam_id):
    """
    Marca una orden como ejecutada y actualiza detalles clínicos
    
    POST /api/examinations/<exam_id>/execute
    Body:
    {
        "history": "..." (opcional),
        "clinicalquestion": "..." (opcional),
        "othersdetails": "..." (opcional),
        "stat": true/false,
        "numberofviews": "..." (opcional),
        "lateralidad": "..." (opcional)
    }
    
    Response:
    {
        "success": true,
        "message": "Orden ejecutada exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        history = null_if_no_clasifica(data.get('history'))
        clinicalquestion = null_if_no_clasifica(data.get('clinicalquestion'))
        othersdetails = null_if_no_clasifica(data.get('othersdetails'))
        stat = data.get('stat', False)
        numberofviews = null_if_no_clasifica(data.get('numberofviews'))
        lateralidad = null_if_no_clasifica(data.get('lateralidad'))
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        cursor.execute("""
            UPDATE nextris.tbexamination
            SET 
                IsExecuted = 1,
                history = %s,
                clinicalquestion = %s,
                othersdetails = %s,
                stat = %s,
                numberofviews = %s,
                lateralidad = %s,
                ExecutedOn = NOW()
            WHERE Guid = %s
        """, (
            history, clinicalquestion, othersdetails,
            1 if stat else 0, numberofviews, lateralidad, exam_id
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # Aquí se llamaría a updatestatus si fuera necesario
        # from apps.home.controllers.admin_controller import updatestatus
        # updatestatus(exam_id)
        
        return jsonify({
            'success': True,
            'message': 'Orden ejecutada exitosamente'
        }), 200
        
    except Exception as e:
        print(f"[API EXECUTE EXAMINATION] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/examinations/unreported', methods=['GET'])
@jwt_required()
def get_examination_items():
    """
    Obtiene exámenes NO reportados
    Filtrados por ubicaciones del usuario
    
    GET /api/examinations/unreported
    
    Response:
    {
        "success": true,
        "data": [
            ["guid", "fecha", "nombre", "dni", "sexo", "estudio", "status", "severidad", "isreported", "isimage"],
            ...
        ]
    }
    """
    try:
        user_id = get_jwt_identity()
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        user_locations = get_user_locations(user_id, connection)
        
        if not user_locations:
            connection.close()
            return jsonify({'success': True, 'data': []}), 200
        
        cursor = connection.cursor()
        
        location_placeholders = ','.join(['%s'] * len(user_locations))
        
        query = f"""
            SELECT 
                e.Guid, e.CreatedOn, 
                dp.Name, dp.Surname, dp.nationalcode, dp.sexcode,
                st.Description as study_type,
                e.Status,
                sev.Description as severity,
                COALESCE(e.IsReported, 0) as isreported,
                COALESCE(e.IsImage, 0) as isimage
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.IsSeverity sev ON e.IdSeverity = sev.Guid
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            WHERE (e.IsReported IS NULL OR e.IsReported != 1)
            AND eq.location_id IN ({location_placeholders})
            ORDER BY e.CreatedOn DESC
        """
        
        cursor.execute(query, user_locations)
        
        results = []
        for row in cursor.fetchall():
            nombre = f"{row[2]} {row[3]}" if row[2] and row[3] else ''
            results.append([
                row[0], row[1].strftime('%d/%m/%Y %H:%M') if row[1] else '',
                nombre, row[4] if row[4] else '', row[5] if row[5] else '',
                row[6] if row[6] else '', row[7] if row[7] else '',
                row[8] if row[8] else '', row[9], row[10]
            ])
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'data': results}), 200
        
    except Exception as e:
        print(f"[API UNREPORTED EXAMINATIONS] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/examinations/all', methods=['GET'])
@jwt_required()
def get_examination_items_all():
    """
    Obtiene TODOS los exámenes (reportados y no reportados)
    Filtrados por ubicaciones del usuario
    
    GET /api/examinations/all
    
    Response: Igual que /examinations/unreported
    """
    try:
        user_id = get_jwt_identity()
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        user_locations = get_user_locations(user_id, connection)
        
        if not user_locations:
            connection.close()
            return jsonify({'success': True, 'data': []}), 200
        
        cursor = connection.cursor()
        
        location_placeholders = ','.join(['%s'] * len(user_locations))
        
        query = f"""
            SELECT 
                e.Guid, e.CreatedOn, 
                dp.Name, dp.Surname, dp.nationalcode, dp.sexcode,
                st.Description as study_type,
                e.Status,
                sev.Description as severity,
                COALESCE(e.IsReported, 0) as isreported,
                COALESCE(e.IsImage, 0) as isimage
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.IsSeverity sev ON e.IdSeverity = sev.Guid
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            WHERE eq.location_id IN ({location_placeholders})
            ORDER BY e.CreatedOn DESC
        """
        
        cursor.execute(query, user_locations)
        
        results = []
        for row in cursor.fetchall():
            nombre = f"{row[2]} {row[3]}" if row[2] and row[3] else ''
            results.append([
                row[0], row[1].strftime('%d/%m/%Y %H:%M') if row[1] else '',
                nombre, row[4] if row[4] else '', row[5] if row[5] else '',
                row[6] if row[6] else '', row[7] if row[7] else '',
                row[8] if row[8] else '', row[9], row[10]
            ])
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'data': results}), 200
        
    except Exception as e:
        print(f"[API ALL EXAMINATIONS] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@api_blueprint.route('/examinations/<exam_id>/report-data', methods=['GET'])
@jwt_required()
def get_report_data(exam_id):
    """
    Obtiene datos completos para la interfaz de reportes médicos
    
    GET /api/examinations/<exam_id>/report-data
    
    Response:
    {
        "success": true,
        "data": {
            "report": [...],
            "isreported": 0/1,
            "isimage": 0/1,
            "study_instance_uid": "...",
            "predefinido": {...},
            "descripcion_predef": "...",
            "wassaved": 0/1,
            "fecha_examen": "...",
            "modality": "...",
            "numberofviews": "...",
            "stat": "...",
            "othersdetails": "...",
            "lateralidad": "...",
            "history": "...",
            "clinicalquestion": "..."
        }
    }
    """
    try:
        db_config = get_db_config()
        if not db_config:
            return jsonify({'success': False, 'message': 'Error de configuración'}), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener examen
        cursor.execute("""
            SELECT 
                e.Guid, e.IdPatient, e.admisionnumber, e.IdReferringPhysician,
                e.IsReported, e.IsImage, e.StudyInstanceUID, e.CreatedOn,
                e.numberofviews, e.stat, e.othersdetails, e.laterality_id,
                e.history, e.clinicalquestion, e.studytype_id
            FROM nextris.tbexamination e
            WHERE e.Guid = %s
        """, (exam_id,))
        
        exam = cursor.fetchone()
        if not exam:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Examen no encontrado'}), 404
        
        # Obtener reporte
        cursor.execute("""
            SELECT 
                Guid, IdExamination, IdPatient, admnumber,
                IdReferringPhysician, Findings, Impressions, Techniques,
                Conclusions, WasSaved
            FROM nextris.tbReport
            WHERE IdExamination = %s
        """, (exam_id,))
        
        report_row = cursor.fetchone()
        report = list(report_row) if report_row else []
        
        # Obtener tipo de estudio y modalidad
        cursor.execute("""
            SELECT st.default_predef_id, st.Description, m.Code as modality
            FROM nextris.isstudytype st
            LEFT JOIN nextris.ismodality m ON st.modality_id = m.Guid
            WHERE st.Guid = %s
        """, (exam[14],))
        
        study_info = cursor.fetchone()
        default_predef_id = study_info[0] if study_info else None
        descripcion_predef = study_info[1] if study_info else None
        modality = study_info[2] if study_info else None
        
        # Obtener información predefinida
        predefinido = {}
        if default_predef_id:
            cursor.execute("""
                SELECT Findings, Impressions, Techniques, Conclusions, Tittle
                FROM nextris.tbinfpredef
                WHERE Guid = %s
            """, (default_predef_id,))
            
            predef_row = cursor.fetchone()
            if predef_row:
                predefinido = {
                    'findings': predef_row[0] if predef_row[0] else '',
                    'impressions': predef_row[1] if predef_row[1] else '',
                    'techniques': predef_row[2] if predef_row[2] else '',
                    'conclusions': predef_row[3] if predef_row[3] else '',
                    'tittle': predef_row[4] if predef_row[4] else ''
                }
        
        # Obtener lateralidad
        lateralidad_desc = None
        if exam[11]:
            cursor.execute("""
                SELECT Description
                FROM nextris.islaterality
                WHERE Guid = %s
            """, (exam[11],))
            lat_row = cursor.fetchone()
            lateralidad_desc = lat_row[0] if lat_row else None
        
        cursor.close()
        connection.close()
        
        result = {
            'report': report,
            'isreported': 1 if exam[4] else 0,
            'isimage': 1 if exam[5] else 0,
            'study_instance_uid': exam[6] if exam[6] else '',
            'predefinido': predefinido,
            'descripcion_predef': descripcion_predef if descripcion_predef else '',
            'wassaved': report[9] if report and len(report) > 9 else 0,
            'fecha_examen': exam[7].strftime('%d/%m/%Y') if exam[7] else '',
            'modality': modality if modality else '',
            'numberofviews': exam[8] if exam[8] else '',
            'stat': exam[9] if exam[9] else '',
            'othersdetails': exam[10] if exam[10] else '',
            'lateralidad': lateralidad_desc if lateralidad_desc else '',
            'history': exam[12] if exam[12] else '',
            'clinicalquestion': exam[13] if exam[13] else ''
        }
        
        return jsonify({'success': True, 'data': result}), 200
        
    except Exception as e:
        print(f"[API REPORT DATA] Error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


# DEPRECATED: Movido a distribution.py
# @api_blueprint.route('/examinations/distribution', methods=['GET'])
# Este endpoint ha sido movido a apps/api/distribution.py con mejor estructura de paginación

