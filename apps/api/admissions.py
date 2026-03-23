# -*- encoding: utf-8 -*-
"""
API REST para gestión de admisiones y worklist DICOM
Endpoints para crear admisiones, obtener datos y gestionar órdenes de admisión
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
from apps.api import api_blueprint
from datetime import datetime


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.services import ConfigService
        config = ConfigService.get_db_config()
        return config
    except:
        return None


def get_user_locations(user_id, connection):
    """Obtener ubicaciones del usuario"""
    cursor = connection.cursor()
    cursor.execute(
        "SELECT location_id FROM nextris.rel_user_location WHERE user_id = %s",
        (user_id,)
    )
    locations = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return locations


@api_blueprint.route('/admissions', methods=['GET'])
@jwt_required()
def get_admissions():
    """
    Obtiene lista de admisiones/worklist del usuario
    
    Query Parameters:
    - status (optional): Filtrar por estado
    - date (optional): Filtrar por fecha (YYYY-MM-DD)
    - page (optional): Número de página
    - per_page (optional): Items por página
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "admission_number": "ADM001",
                "accession_number": "ACC001",
                "patient_surname": "Díaz",
                "patient_name": "Lucia",
                "study_type": "ANGIOGRAFÍA",
                "status": "A",
                "created_on": "datetime",
                "is_executed": false,
                "is_admitted": true
            },
            ...
        ],
        "total": 150,
        "page": 1,
        "per_page": 20
    }
    """
    try:
        user_id = get_jwt_identity()
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        # Parámetros de paginación
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        per_page = min(per_page, 100)  # Máximo 100
        offset = (page - 1) * per_page
        
        # Filtros
        status = request.args.get('status')
        date_filter = request.args.get('date')
        
        connection = psycopg2.connect(**db_config)
        user_locations = get_user_locations(user_id, connection)
        
        if not user_locations:
            connection.close()
            return jsonify({
                'success': True,
                'data': [],
                'total': 0,
                'page': page,
                'per_page': per_page
            }), 200
        
        cursor = connection.cursor()
        
        location_placeholders = ','.join(['%s'] * len(user_locations))
        
        # Query base
        base_query = f"""
            SELECT e.Guid, e.AdmisionNumber, e.LocalAcc,
                   dp.Surname, dp.Name,
                   st.Description,
                   e.Status, e.CreatedOn, e.IsExecuted, e.IsAdmitted
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            WHERE eq.location_id IN ({location_placeholders})
            AND e.IsAdmitted = 1
        """
        
        params = list(user_locations)
        
        # Aplicar filtros
        if status:
            base_query += " AND e.Status = %s"
            params.append(status)
        
        if date_filter:
            base_query += " AND DATE(e.CreatedOn) = %s"
            params.append(date_filter)
        
        # Contar total
        count_query = f"SELECT COUNT(*) FROM ({base_query}) AS count_table"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Query con paginación
        query = base_query + f"""
            ORDER BY e.CreatedOn DESC
            LIMIT %s OFFSET %s
        """
        
        params.extend([per_page, offset])
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'guid': str(row[0]),
                'admission_number': row[1] or '',
                'accession_number': row[2] or '',
                'patient_surname': row[3] or '',
                'patient_name': row[4] or '',
                'study_type': row[5] or '',
                'status': row[6] or '',
                'created_on': row[7].isoformat() if row[7] else None,
                'is_executed': bool(row[8]),
                'is_admitted': bool(row[9])
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': results,
            'total': total,
            'page': page,
            'per_page': per_page
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/admissions/<admission_guid>', methods=['GET'])
@jwt_required()
def get_admission_details(admission_guid):
    """
    Obtiene detalles completos de una admisión
    
    Path Parameters:
    - admission_guid: GUID de la admisión
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid",
            "admission_number": "ADM001",
            "accession_number": "ACC001",
            "patient_name": "nombre completo",
            "patient_id": "uuid",
            "study_type": "descripción",
            "status": "estado",
            "created_on": "datetime",
            "is_executed": boolean,
            "is_admitted": true,
            "is_reported": boolean,
            "equipment": "nombre equipo",
            "location": "nombre ubicación"
        }
    }
    """
    try:
        db_config = get_db_config()
        if not db_config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        query = """
            SELECT e.Guid, e.AdmisionNumber, e.LocalAcc,
                   dp.Surname, dp.Name, dp.Guid,
                   st.Description,
                   e.Status, e.CreatedOn, e.IsExecuted, e.IsAdmitted,
                   e.isreported,
                   eq.Description, loc.name
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            LEFT JOIN nextris.tblocation loc ON eq.location_id = loc.guid
            WHERE e.Guid = %s
        """
        
        cursor.execute(query, (admission_guid,))
        admission_data = cursor.fetchone()
        
        if not admission_data:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Admisión no encontrada'
            }), 404
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'guid': str(admission_data[0]),
                'admission_number': admission_data[1] or '',
                'accession_number': admission_data[2] or '',
                'patient_surname': admission_data[3] or '',
                'patient_name': admission_data[4] or '',
                'patient_id': str(admission_data[5]) if admission_data[5] else None,
                'study_type': admission_data[6] or '',
                'status': admission_data[7] or '',
                'created_on': admission_data[8].isoformat() if admission_data[8] else None,
                'is_executed': bool(admission_data[9]),
                'is_admitted': bool(admission_data[10]),
                'is_reported': bool(admission_data[11]),
                'equipment': admission_data[12] or '',
                'location': admission_data[13] or ''
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/admissions/appointment/<appointment_guid>/admit', methods=['POST'])
@jwt_required()
def create_admission_from_appointment(appointment_guid):
    """
    Admisiona una cita existente (tbagendaevents) creando un examen en tbexamination
    
    Path Parameters:
    - appointment_guid: GUID de la cita en tbagendaevents
    
    Body JSON (opcional):
    {
        "notes": "notas adicionales",
        "equipment_id": "uuid del equipo" (opcional, sobreescribe el equipo de la cita)
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "admission_number": "ADM001",
            "accession_number": "ACC001",
            "examination_guid": "uuid",
            "appointment_guid": "uuid"
        }
    }
    """
    try:
        data = request.get_json() or {}
        notes = data.get('notes', '')
        equipment_id_override = data.get('equipment_id')
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener datos de la cita en tbagendaevents
        cursor.execute("""
            SELECT idpatient, idequipment, idexam, idmed_sol, location_id, isadmitted
            FROM nextris.tbagendaevents 
            WHERE guid = %s
        """, (appointment_guid,))
        
        appointment_row = cursor.fetchone()
        
        if not appointment_row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Cita no encontrada'
            }), 404
        
        patient_id, equipment_id, study_type_id, physician_id, location_id, is_admitted = appointment_row
        
        # Verificar si ya está admitida
        if is_admitted:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'La cita ya ha sido admitida'
            }), 400
        
        # Si se proporciona equipment_id, usar ese, sino el de la cita
        final_equipment_id = equipment_id_override if equipment_id_override else equipment_id
        
        # Verificar que el equipo existe
        if final_equipment_id:
            cursor.execute(
                "SELECT guid FROM nextris.isequipment WHERE guid = %s",
                (final_equipment_id,)
            )
            if not cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({
                    'success': False,
                    'message': 'Equipo no encontrado'
                }), 404
        
        # Obtener último número de admisión
        cursor.execute(
            "SELECT MAX(CAST(SUBSTRING(AdmisionNumber, 4) AS INTEGER)) FROM nextris.tbexamination WHERE AdmisionNumber LIKE 'ADM%'"
        )
        last_adm_row = cursor.fetchone()
        last_adm = last_adm_row[0] if last_adm_row[0] else 0
        new_admission = f"ADM{(last_adm + 1):03d}"
        
        # Obtener último accession number
        cursor.execute(
            "SELECT MAX(CAST(SUBSTRING(LocalAcc, 4) AS INTEGER)) FROM nextris.tbexamination WHERE LocalAcc LIKE 'ACC%'"
        )
        last_acc_row = cursor.fetchone()
        last_acc = last_acc_row[0] if last_acc_row[0] else 0
        new_accession = f"ACC{(last_acc + 1):03d}"
        
        # Generar Study Instance UID (solo números y puntos, formato DICOM válido)
        import time
        import hashlib
        timestamp = str(int(time.time() * 1000))
        # Convertir patient_id UUID a número usando hash
        patient_hash = int(hashlib.md5(str(patient_id).encode()).hexdigest()[:12], 16)
        study_instance_uid = f"1.2.840.{timestamp}.{patient_hash}"
        
        # Crear nuevo examen en tbexamination
        cursor.execute("""
            INSERT INTO nextris.tbexamination (
                guid, studyinstanceuid, idpatient, studytype_id, idequipment,
                admisionnumber, localacc, createdon, status, isexecuted,
                idrequestingphysician, isadmitted, location_id
            ) VALUES (
                uuid_generate_v4(), %s, %s, %s, %s, %s, %s, NOW(), 'A', 0, %s, 1, %s
            ) RETURNING guid
        """, (
            study_instance_uid,
            patient_id,
            study_type_id,
            final_equipment_id,
            new_admission,
            new_accession,
            physician_id,
            location_id
        ))
        
        examination_guid = cursor.fetchone()[0]
        
        # Crear registro en tbReport
        cursor.execute("""
            INSERT INTO nextris.tbreport (
                guid, admnumber, idexamination, idpatient, date
            ) VALUES (
                uuid_generate_v4(), %s, %s, %s, NOW()
            )
        """, (new_admission, examination_guid, patient_id))
        
        # Marcar la cita como admitida
        cursor.execute("""
            UPDATE nextris.tbagendaevents
            SET isadmitted = true
            WHERE guid = %s
        """, (appointment_guid,))
        
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'admission_number': new_admission,
                'accession_number': new_accession,
                'examination_guid': str(examination_guid),
                'appointment_guid': str(appointment_guid)
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/admissions/<admission_guid>', methods=['DELETE'])
@jwt_required()
def cancel_admission(admission_guid):
    """
    Cancela una admisión (marca IsAdmitted = 0)
    
    Path Parameters:
    - admission_guid: GUID de la admisión
    
    Returns:
    {
        "success": true,
        "message": "Admisión cancelada exitosamente"
    }
    """
    try:
        db_config = get_db_config()
        if not db_config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Verificar que existe
        cursor.execute(
            "SELECT 1 FROM nextris.tbexamination WHERE Guid = %s AND IsAdmitted = 1",
            (admission_guid,)
        )
        
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Admisión no encontrada'
            }), 404
        
        # Cancelar admisión
        update_query = """
            UPDATE nextris.tbexamination
            SET IsAdmitted = 0
            WHERE Guid = %s
        """
        
        cursor.execute(update_query, (admission_guid,))

        # Desvincular imágenes DICOM asociadas al examen
        cursor.execute("""
            UPDATE nextris.tbmanual_uploads
            SET islinked = 0,
                linked_examination_guid = NULL,
                linked_date = NULL
            WHERE linked_examination_guid = %s
        """, (admission_guid,))

        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'nextris' AND table_name = 'tbpacs_study_link'
            )
        """)
        has_pacs_link_table = cursor.fetchone()[0]

        if has_pacs_link_table:
            cursor.execute("""
                UPDATE nextris.tbpacs_study_link
                SET link_status = 'unlinked',
                    unlinked_at = CURRENT_TIMESTAMP,
                    unlinked_reason = 'Admisión cancelada desde /api/admissions/<admission_guid>',
                    updated_at = CURRENT_TIMESTAMP
                WHERE order_guid = %s
                  AND link_status = 'linked'
            """, (admission_guid,))

        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Admisión cancelada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/admission/create-order', methods=['POST'])
@jwt_required()
def create_admission_order():
    """
    Crea una orden de admisión (worklist) con un examen
    
    POST /api/admission/create-order
    
    Body JSON:
    {
        "patient_id": "uuid-del-paciente",
        "location_id": "uuid-de-la-ubicacion",
        "exam": {
            "study_type_id": "uuid-del-tipo-de-estudio",
            "equipment_id": "uuid-del-equipo",
            "physician_id": "uuid-del-medico-solicitante" (opcional),
            "referring_physician_id": "uuid-del-radiologo-firmante" (opcional),
            "insurance_id": "uuid-de-la-obra-social" (opcional),
            "severity": "normal" | "urgent" (opcional, default: "normal")
        }
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "admission_number": "ADM001",
            "accession_number": "ACC001",
            "exam_id": "uuid-del-examen",
            "study_instance_uid": "1.2.840...",
            "timezone": "America/Argentina/Buenos_Aires"
        },
        "message": "Orden creada exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        patient_id = data.get('patient_id')
        location_id = data.get('location_id')
        exam_data = data.get('exam', {})
        
        # Validaciones
        if not patient_id:
            return jsonify({
                'success': False,
                'message': 'patient_id es obligatorio'
            }), 400
        
        if not location_id:
            return jsonify({
                'success': False,
                'message': 'location_id es obligatorio'
            }), 400
            
        if not exam_data.get('study_type_id'):
            return jsonify({
                'success': False,
                'message': 'exam.study_type_id es obligatorio'
            }), 400
            
        if not exam_data.get('equipment_id'):
            return jsonify({
                'success': False,
                'message': 'exam.equipment_id es obligatorio'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # 1. Obtener timezone de la location
        cursor.execute("""
            SELECT COALESCE(timezone, 'America/Argentina/Buenos_Aires')
            FROM nextris.tblocation
            WHERE guid = %s
        """, (location_id,))
        
        timezone_result = cursor.fetchone()
        timezone = timezone_result[0] if timezone_result else 'America/Argentina/Buenos_Aires'
        
        # 2. Obtener datos del paciente
        cursor.execute("""
            SELECT guid, name, surname, nationalcode, birthdate, sexcode
            FROM nextris.datapatient
            WHERE guid = %s
        """, (patient_id,))
        
        patient = cursor.fetchone()
        if not patient:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        # 3. Generar números de admisión y acceso
        cursor.execute("""
            SELECT MAX(CAST(SUBSTRING(admisionnumber, 4) AS INTEGER)) 
            FROM nextris.tbexamination 
            WHERE admisionnumber LIKE 'ADM%'
              AND SUBSTRING(admisionnumber, 4) ~ '^[0-9]+$'
        """)
        last_adm = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT MAX(CAST(SUBSTRING(localacc, 4) AS INTEGER)) 
            FROM nextris.tbexamination 
            WHERE localacc LIKE 'ACC%'
              AND SUBSTRING(localacc, 4) ~ '^[0-9]+$'
        """)
        last_acc = cursor.fetchone()[0] or 0
        
        admission_number = f"ADM{(last_adm + 1):03d}"
        accession_number = f"ACC{(last_acc + 1):03d}"
        
        # 4. Obtener datos del equipo y modalidad
        cursor.execute("""
            SELECT e.guid, e.aetitle, e.description, e.idmodality,
                   m.externalcode
            FROM nextris.isequipment e
            LEFT JOIN nextris.ismodality m ON e.idmodality = m.guid
            WHERE e.guid = %s
        """, (exam_data['equipment_id'],))
        
        equipment = cursor.fetchone()
        if not equipment:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Equipo no encontrado'
            }), 404
        
        # 5. Obtener descripción del estudio
        cursor.execute("""
            SELECT description
            FROM nextris.isstudytype
            WHERE guid = %s
        """, (exam_data['study_type_id'],))
        
        study_type = cursor.fetchone()
        if not study_type:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Tipo de estudio no encontrado'
            }), 404
        
        # 6. Generar Study Instance UID (solo números y puntos, formato DICOM válido)
        import time
        import hashlib
        timestamp = str(int(time.time() * 1000))
        # Convertir patient_id UUID a número usando hash
        patient_hash = int(hashlib.md5(str(patient[0]).encode()).hexdigest()[:12], 16)
        study_instance_uid = f"1.2.840.{timestamp}.{patient_hash}"
        
        # Nota: Envío HL7 al worklist DICOM comentado para compatibilidad con BD de prueba
        # En producción, descomentar y verificar HL7Service
        # study_instance_uid, hl7_success = HL7Service.send_exam_to_worklist(...)
        # if not hl7_success: return error
        
        # 7. Insertar examen en tbexamination
        severity_id = None
        if exam_data.get('severity') == 'urgent':
            # Obtener ID de severidad "Urgente"
            cursor.execute("SELECT guid FROM nextris.isseverity WHERE description ILIKE '%urgente%' LIMIT 1")
            severity_result = cursor.fetchone()
            severity_id = severity_result[0] if severity_result else None
        
        cursor.execute("""
            INSERT INTO nextris.tbexamination (
                guid, studyinstanceuid, idpatient, studytype_id, idequipment,
                admisionnumber, localacc, createdon, status, isexecuted,
                idseverity, idrequestingphysician, idreferringphysician, idpricelist, isadmitted, location_id
            ) VALUES (
                uuid_generate_v4(), %s, %s, %s, %s, %s, %s, NOW(), 'A', 0, %s, %s, %s, %s, 1, %s
            ) RETURNING guid
        """, (
            study_instance_uid,
            patient[0],
            exam_data['study_type_id'],
            exam_data['equipment_id'],
            admission_number,
            accession_number,
            severity_id,
            exam_data.get('physician_id'),
            exam_data.get('referring_physician_id'),
            exam_data.get('insurance_id'),
            location_id
        ))
        
        exam_guid = cursor.fetchone()[0]
        
        # 8. Crear registro en tbReport
        cursor.execute("""
            INSERT INTO nextris.tbreport (
                guid, admnumber, idexamination, idpatient, date
            ) VALUES (
                uuid_generate_v4(), %s, %s, %s, NOW()
            )
        """, (admission_number, exam_guid, patient[0]))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'admission_number': admission_number,
                'accession_number': accession_number,
                'exam_id': exam_guid,
                'study_instance_uid': study_instance_uid,
                'timezone': timezone
            },
            'message': 'Orden creada exitosamente'
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/appointments_to_admit', methods=['GET'])
@jwt_required()
def appointments_to_admit():
    """
    Obtiene todas las citas no admitidas de hoy (appointments_to_admit)
    
    Returns:
    [
        {
            "guid": "uuid",
            "fullname": "nombre apellido",
            "comienzo": "datetime",
            "medref": "médico referencia",
            "description": "descripción examen",
            "equipo": "equipo DICOM",
            "med_solicitante": "médico solicitante"
        },
        ...
    ]
    """
    try:
        db_config = get_db_config()
        if not db_config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        query = """
            SELECT tba.guid, 
                   COALESCE(pat.name || ' ' || pat.surname, 'Sin paciente') as fullname, 
                   tba.comienzo,
                   tba.idequipment as equipo,
                   tba.location_id as location,
                   COALESCE(us.name || ' ' || us.surname, 'Sin médico') as medref, 
                   COALESCE(st.description, 'Sin examen') as description,
                   COALESCE(equip.aetitle, 'Sin equipo') as equipo, 
                   COALESCE(rp.description, 'Sin médico solicitante') as med_solicitante,
                   equip.idmodality as modality_id
            FROM nextris.tbagendaevents tba
            LEFT JOIN nextris.datapatient pat on tba.idpatient=pat.guid
            LEFT JOIN nextris.isrequestingphysician rp on tba.idmed_sol=rp.guid
            LEFT JOIN nextris.tbuser us on tba.idmed=us.guid
            LEFT JOIN nextris.isstudytype st on tba.idexam=st.guid
            LEFT JOIN nextris.isequipment equip on equip.guid=tba.idequipment
            WHERE isadmitted=false
            AND DATE(tba.comienzo) = CURRENT_DATE
            ORDER BY tba.comienzo DESC
        """
        
        cursor.execute(query)
        results = []
        for row in cursor.fetchall():
            results.append({
                'guid': str(row[0]),
                'fullname': row[1],
                'comienzo': row[2].isoformat() if row[2] else None,
                'equipo': row[3],
                'location': row[4],
                'medref': row[5],
                'description': row[6],
                'equipment_name': row[7],
                'med_solicitante': row[8],
                'modality_id': str(row[9]) if row[9] else None
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': results
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
