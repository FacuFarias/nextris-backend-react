# -*- encoding: utf-8 -*-
"""
API de Citas/Agenda - Endpoints REST para gestión de citas y agenda
Migrado desde appointment_controller.py
"""

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import psycopg2
from psycopg2.extras import RealDictCursor
from apps.api import api_blueprint
from datetime import datetime, timedelta
import uuid
import pytz


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.routes import config
        return config
    except:
        return None


@api_blueprint.route('/appointments/calendar-events', methods=['POST'])
@jwt_required()
def get_calendar_events():
    """
    Obtiene eventos del calendario para editar
    
    Body JSON:
    {
        "guid": "optional-event-guid-to-edit",
        "equipment_aetitle": "aetitle-del-equipo"
    }
    
    Respuesta:
    {
        "success": true,
        "data": {
            "events": [
                {
                    "guid": "...",
                    "start": "2025-12-05T10:00:00",
                    "end": "2025-12-05T11:00:00",
                    "title": "Paciente - Examen",
                    "patient_name": "...",
                    "exam": "...",
                    "editable": true
                }
            ],
            "work_hours": [
                {
                    "day": 1,
                    "start": "08:00:00",
                    "end": "17:00:00"
                }
            ]
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        equipment_aetitle = data.get('equipment_aetitle')
        edit_guid = data.get('guid')  # Opcional - para marcar un evento como editable
        
        if not equipment_aetitle:
            return jsonify({
                'success': False,
                'message': 'El campo equipment_aetitle es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener eventos del equipo
        query_events = """
            SELECT tba.guid, tba.comienzo, tba.fin, tba.idmed, st.description as exam, 
                   tba.idmed_sol, CONCAT(pat.surname, ' ', pat.name) as patient_name
            FROM nextris.tbagendaevents tba
            INNER JOIN nextris.isequipment equip ON equip.guid = tba.idequipment
            INNER JOIN nextris.isstudytype st ON st.guid = tba.idexam
            INNER JOIN nextris.datapatient pat ON pat.guid = tba.idpatient
            WHERE equip.aetitle = %s
            ORDER BY tba.comienzo
        """
        
        cursor.execute(query_events, (equipment_aetitle,))
        eventos = cursor.fetchall()
        
        # Formatear eventos
        events_list = []
        for ev in eventos:
            # Ajustar zona horaria si es necesario
            start_time = ev[1]
            end_time = ev[2]
            
            if start_time and end_time:
                event = {
                    'guid': str(ev[0]),
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat(),
                    'idmed': ev[3],
                    'exam': ev[4] or 'Sin examen',
                    'idmed_sol': ev[5],
                    'patient_name': ev[6] or 'Sin nombre',
                    'title': f"{ev[6] or 'Sin nombre'} - {ev[4] or 'Sin examen'}",
                    'editable': str(ev[0]) == str(edit_guid) if edit_guid else False
                }
                events_list.append(event)
        
        # Obtener horarios de trabajo del equipo
        query_work_hours = """
            SELECT ae.day, ae.timefrom, ae.timeto
            FROM nextris.isagendaequip ae
            INNER JOIN nextris.isequipment equip ON equip.guid = ae.idequipment
            WHERE equip.aetitle = %s
        """
        cursor.execute(query_work_hours, (equipment_aetitle,))
        work_hours_data = cursor.fetchall()
        
        # Mapeo de días
        days_mapping = {
            'lunes': 1, 'martes': 2, 'miércoles': 3, 'miercoles': 3,
            'jueves': 4, 'viernes': 5, 'sábado': 6, 'sabado': 6, 'domingo': 0
        }
        
        work_hours = []
        for row in work_hours_data:
            work_hours.append({
                'day': days_mapping.get(row[0].lower(), 1),
                'start': row[1].strftime('%H:%M:%S') if row[1] else '08:00:00',
                'end': row[2].strftime('%H:%M:%S') if row[2] else '17:00:00'
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'events': events_list,
                'work_hours': work_hours
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/appointments/<appointment_id>/reschedule', methods=['PATCH'])
@jwt_required()
def reschedule_appointment(appointment_id):
    """
    Actualiza las fechas de una cita (reprogramar)
    
    Path:
    - appointment_id: GUID de la cita
    
    Body JSON:
    {
        "start": "2025-12-05T10:00:00Z",
        "end": "2025-12-05T11:00:00Z"
    }
    
    Respuesta:
    {
        "success": true,
        "message": "Cita reprogramada exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        start = data.get('start')
        end = data.get('end')
        
        if not start or not end:
            return jsonify({
                'success': False,
                'message': 'Los campos start y end son requeridos'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que la cita existe
        cursor.execute(
            "SELECT guid FROM nextris.tbagendaevents WHERE guid = %s",
            (appointment_id,)
        )
        
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Cita no encontrada'
            }), 404
        
        # Convertir fechas ISO a formato PostgreSQL
        # Manejar zona horaria
        local_tz = pytz.timezone("America/Argentina/Buenos_Aires")
        
        try:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            
            # Convertir a zona horaria local
            start_local = start_dt.astimezone(local_tz)
            end_local = end_dt.astimezone(local_tz)
            
            # Formato para PostgreSQL (sin zona horaria)
            start_str = start_local.strftime('%Y-%m-%d %H:%M:%S')
            end_str = end_local.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'Error en formato de fecha: {str(e)}'
            }), 400
        
        # Actualizar la cita
        query = """
            UPDATE nextris.tbagendaevents 
            SET comienzo = %s, fin = %s 
            WHERE guid = %s
        """
        
        cursor.execute(query, (start_str, end_str, appointment_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Cita reprogramada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/appointments', methods=['POST'])
@jwt_required()
def create_appointment():
    """
    Crea una nueva cita en la agenda
    
    Body JSON:
    {
        "patient_id": "guid-del-paciente",
        "exam_id": "guid-del-examen",
        "start_datetime": "2025-12-05 10:00",
        "end_datetime": "2025-12-05 11:00",
        "doctor_id": "optional-guid-del-medico",
        "equipment_id": "optional-guid-del-equipo",
        "appointment_type": "doctor" o "equipment"
    }
    
    Respuesta:
    {
        "success": true,
        "data": {
            "appointment_id": "nuevo-guid"
        },
        "message": "Cita creada exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        patient_id = data.get('patient_id')
        exam_id = data.get('exam_id')
        start_datetime = data.get('start_datetime')
        end_datetime = data.get('end_datetime')
        appointment_type = data.get('appointment_type', 'doctor')
        
        if not all([patient_id, exam_id, start_datetime, end_datetime]):
            return jsonify({
                'success': False,
                'message': 'Faltan campos requeridos: patient_id, exam_id, start_datetime, end_datetime'
            }), 400
        
        doctor_id = data.get('doctor_id')
        equipment_id = data.get('equipment_id')
        
        if appointment_type == 'equipment' and not equipment_id:
            return jsonify({
                'success': False,
                'message': 'equipment_id es requerido para citas de tipo equipment'
            }), 400
        
        if appointment_type == 'doctor' and not doctor_id:
            return jsonify({
                'success': False,
                'message': 'doctor_id es requerido para citas de tipo doctor'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Generar nuevo GUID
        new_guid = str(uuid.uuid4())
        
        # Insertar cita
        if appointment_type == 'equipment':
            query = """
                INSERT INTO nextris.tbagendaevents 
                (guid, comienzo, fin, idequipment, idpatient, idexam, idmed, createdon, isadmitted)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), false)
            """
            params = (new_guid, start_datetime, end_datetime, equipment_id, 
                     patient_id, exam_id, doctor_id)
        else:
            query = """
                INSERT INTO nextris.tbagendaevents 
                (guid, comienzo, fin, idmed, idpatient, idexam, createdon, isadmitted)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), false)
            """
            params = (new_guid, start_datetime, end_datetime, doctor_id, 
                     patient_id, exam_id)
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'appointment_id': new_guid
            },
            'message': 'Cita creada exitosamente'
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/appointments', methods=['GET'])
@jwt_required()
def get_appointments():
    """
    Obtiene lista de citas con filtros
    
    Query params:
    - date: fecha específica (YYYY-MM-DD)
    - doctor_id: filtrar por médico
    - equipment_id: filtrar por equipo
    - admitted: true/false (filtrar por estado de admisión)
    - today: true (obtener solo citas del día actual)
    
    Respuesta:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "patient_name": "...",
                "start": "2025-12-05T10:00:00",
                "end": "2025-12-05T11:00:00",
                "exam": "...",
                "doctor": "...",
                "equipment": "...",
                "status": "...",
                "is_admitted": false
            }
        ]
    }
    """
    try:
        # Obtener parámetros de query
        date_filter = request.args.get('date')
        doctor_id = request.args.get('doctor_id')
        equipment_id = request.args.get('equipment_id')
        admitted_filter = request.args.get('admitted')
        today_only = request.args.get('today', 'false').lower() == 'true'
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Construir query base
        query = """
            SELECT 
                tba.guid,
                CONCAT(pat.surname, ' ', pat.name) as patient_name,
                tba.comienzo,
                tba.fin,
                st.description as exam,
                CONCAT(med.surname, ' ', med.name) as doctor,
                equip.aetitle as equipment,
                tba.isadmitted
            FROM nextris.tbagendaevents tba
            LEFT JOIN nextris.datapatient pat ON pat.guid = tba.idpatient
            LEFT JOIN nextris.isstudytype st ON st.guid = tba.idexam
            LEFT JOIN nextris.tbuser med ON med.guid = tba.idmed
            LEFT JOIN nextris.isequipment equip ON equip.guid = tba.idequipment
            WHERE 1=1
        """
        
        params = []
        
        if today_only:
            query += " AND DATE(tba.comienzo) = CURRENT_DATE"
        elif date_filter:
            query += " AND DATE(tba.comienzo) = %s"
            params.append(date_filter)
        
        if doctor_id:
            query += " AND tba.idmed = %s"
            params.append(doctor_id)
        
        if equipment_id:
            query += " AND tba.idequipment = %s"
            params.append(equipment_id)
        
        if admitted_filter is not None:
            is_admitted = admitted_filter.lower() == 'true'
            query += " AND tba.isadmitted = %s"
            params.append(is_admitted)
        
        query += " ORDER BY tba.comienzo DESC"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        # Formatear resultados
        appointments = []
        for row in results:
            appointments.append({
                'guid': row[0],
                'patient_name': row[1] or 'Sin paciente',
                'start': row[2].isoformat() if row[2] else '',
                'end': row[3].isoformat() if row[3] else '',
                'exam': row[4] or 'Sin examen',
                'doctor': row[5] or 'Sin médico',
                'equipment': row[6] or 'Sin equipo',
                'is_admitted': bool(row[7]) if row[7] is not None else False
            })
        
        return jsonify({
            'success': True,
            'data': appointments
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/appointments/<appointment_id>', methods=['PATCH'])
@jwt_required()
def update_appointment(appointment_id):
    """
    Actualiza los datos de una cita existente
    
    Path:
    - appointment_id: GUID de la cita
    
    Body JSON:
    {
        "doctor_id": "optional-nuevo-guid-medico",
        "requesting_physician_id": "optional-guid-medico-solicitante",
        "exam_id": "optional-nuevo-guid-examen"
    }
    
    Respuesta:
    {
        "success": true,
        "message": "Cita actualizada exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que la cita existe
        cursor.execute(
            "SELECT guid FROM nextris.tbagendaevents WHERE guid = %s",
            (appointment_id,)
        )
        
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Cita no encontrada'
            }), 404
        
        # Construir query de actualización dinámicamente
        update_fields = []
        params = []
        
        if 'doctor_id' in data:
            update_fields.append("idmed = %s")
            params.append(data['doctor_id'])
        
        if 'requesting_physician_id' in data:
            update_fields.append("idmed_sol = %s")
            params.append(data['requesting_physician_id'])
        
        if 'exam_id' in data:
            update_fields.append("idexam = %s")
            params.append(data['exam_id'])
        
        if not update_fields:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(appointment_id)
        
        query = f"""
            UPDATE nextris.tbagendaevents 
            SET {', '.join(update_fields)}
            WHERE guid = %s
        """
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Cita actualizada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/appointments/<appointment_id>', methods=['DELETE'])
@jwt_required()
def delete_appointment(appointment_id):
    """
    Elimina una cita de la agenda
    
    Path:
    - appointment_id: GUID de la cita
    
    Respuesta:
    {
        "success": true,
        "message": "Cita eliminada exitosamente"
    }
    """
    try:
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que la cita existe
        cursor.execute(
            "SELECT guid FROM nextris.tbagendaevents WHERE guid = %s",
            (appointment_id,)
        )
        
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Cita no encontrada'
            }), 404
        
        # Eliminar la cita
        query = "DELETE FROM nextris.tbagendaevents WHERE guid = %s"
        cursor.execute(query, (appointment_id,))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Cita eliminada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/appointments/<appointment_id>/admit', methods=['POST'])
@jwt_required()
def admit_appointment(appointment_id):
    """
    Admisiona una cita y crea el examen en worklist
    
    Path:
    - appointment_id: GUID de la cita
    
    Body JSON (opcional):
    {
        "equipment_id": "guid-del-equipo"  // Si no viene en la cita
    }
    
    Respuesta:
    {
        "success": true,
        "data": {
            "admission_number": "ADM123",
            "accession_number": "ACC123",
            "exam_id": "guid-del-examen-creado"
        },
        "message": "Cita admisionada exitosamente"
    }
    """
    try:
        data = request.get_json() or {}
        equipment_id_override = data.get('equipment_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener datos de la cita
        query_appointment = """
            SELECT idpatient, idexam, idequipment, isadmitted
            FROM nextris.tbagendaevents 
            WHERE guid = %s
        """
        cursor.execute(query_appointment, (appointment_id,))
        appointment_data = cursor.fetchone()
        
        if not appointment_data:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Cita no encontrada'
            }), 404
        
        patient_id, exam_id, cita_equipment_id, is_admitted = appointment_data
        
        # Verificar si ya está admisionada
        if is_admitted:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'La cita ya está admisionada'
            }), 400
        
        # Determinar equipo a usar
        final_equipment_id = equipment_id_override or cita_equipment_id
        
        if not final_equipment_id:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No se especificó equipo para la admisión'
            }), 400
        
        # Generar números de admisión y acceso
        query_last_adm = """
            SELECT MAX(CAST(SUBSTRING(admisionnumber, 4) AS INTEGER)) 
            FROM nextris.tbexamination 
            WHERE admisionnumber LIKE 'ADM%'
        """
        cursor.execute(query_last_adm)
        last_adm = cursor.fetchone()
        
        query_last_acc = """
            SELECT MAX(CAST(SUBSTRING(localacc, 4) AS INTEGER)) 
            FROM nextris.tbexamination 
            WHERE localacc LIKE 'ACC%'
        """
        cursor.execute(query_last_acc)
        last_acc = cursor.fetchone()
        
        adm_num = (last_adm[0] or 0) + 1
        acc_num = (last_acc[0] or 0) + 1
        
        new_admission = f"ADM{adm_num:03d}"
        new_accession = f"ACC{acc_num:03d}"
        
        # Generar StudyInstanceUID
        study_instance_uid = f"1.2.840.113619.{uuid.uuid4().int}"
        
        # Crear examen
        exam_guid = str(uuid.uuid4())
        
        query_insert_exam = """
            INSERT INTO nextris.tbexamination (
                guid, studyinstanceuid, idpatient, studytype_id, idequipment,
                admisionnumber, localacc, createdon, status, isexecuted, isadmitted
            ) VALUES (
                %s, %s, 
                (SELECT patientid FROM nextris.datapatient WHERE guid = %s), 
                %s, %s, %s, %s, NOW(), 'A', 0, 1
            )
        """
        
        cursor.execute(query_insert_exam, (
            exam_guid, study_instance_uid, patient_id, exam_id, 
            final_equipment_id, new_admission, new_accession
        ))
        
        # Crear registro en tbReport
        query_insert_report = """
            INSERT INTO nextris.tbreport (
                guid, admnumber, idexamination, idpatient, date
            ) VALUES (
                uuid_generate_v4(), %s, %s, %s, NOW()
            )
        """
        
        cursor.execute(query_insert_report, (new_admission, exam_guid, patient_id))
        
        # Marcar cita como admisionada
        query_update_appointment = """
            UPDATE nextris.tbagendaevents 
            SET isadmitted = true
            WHERE guid = %s
        """
        cursor.execute(query_update_appointment, (appointment_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'admission_number': new_admission,
                'accession_number': new_accession,
                'exam_id': exam_guid,
                'study_instance_uid': study_instance_uid
            },
            'message': 'Cita admisionada exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
