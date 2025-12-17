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
from apps.home.services import HL7Service


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
    Actualiza las fechas y/o equipo de una cita (reprogramar)
    
    Path:
    - appointment_id: GUID de la cita
    
    Body JSON:
    {
        "start": "2025-12-05T10:00:00Z",
        "end": "2025-12-05T11:00:00Z",
        "equipment_id": "uuid-del-equipo (opcional)"
    }
    
    Respuesta:
    {
        "success": true,
        "message": "Cita reprogramada exitosamente",
        "rows_affected": 1
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
        equipment_id = data.get('equipment_id')  # Opcional
        
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
            
            print(f"[DEBUG RESCHEDULE] appointment_id: {appointment_id}, start: {start_str}, end: {end_str}, equipment_id: {equipment_id}")
        except Exception as e:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'Error en formato de fecha: {str(e)}'
            }), 400
        
        # Construir el UPDATE dinámicamente dependiendo de qué campos se actualicen
        set_clauses = ["comienzo = %s", "fin = %s"]
        params = [start_str, end_str]
        
        if equipment_id:
            set_clauses.append("idequipment = %s")
            params.append(equipment_id)
        
        params.append(appointment_id)
        
        # Actualizar la cita
        query = f"""
            UPDATE nextris.tbagendaevents 
            SET {', '.join(set_clauses)}
            WHERE guid = %s
        """
        
        cursor.execute(query, params)
        rows_affected = cursor.rowcount
        
        # Verificar que la actualización fue exitosa
        if rows_affected == 0:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No se pudo actualizar la cita (guid no encontrado)'
            }), 400
        
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': f'Cita reprogramada exitosamente ({rows_affected} registro(s) actualizado(s))',
            'rows_affected': rows_affected
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
    Crea una o múltiples citas en la agenda
    
    Body JSON:
    {
        "patient_id": "guid-del-paciente",
        "appointment_type": "doctor" o "equipment",
        "calendar_events": [
            {
                "exam_id": "guid-del-examen",
                "start_datetime": "2025-12-05 10:00",
                "end_datetime": "2025-12-05 11:00",
                "physician_id": "guid-del-medico",
                "obra_social_id": "guid-de-la-obra-social",
                "equipment_id": "optional-guid-del-equipo"
            },
            {
                "exam_id": "guid-del-examen-2",
                "start_datetime": "2025-12-05 14:00",
                "end_datetime": "2025-12-05 15:00",
                "physician_id": "guid-del-medico-2",
                "obra_social_id": "guid-de-la-obra-social-2",
                "equipment_id": "optional-guid-del-equipo-2"
            }
        ]
    }
    
    Respuesta:
    {
        "success": true,
        "data": {
            "appointment_ids": ["guid-1", "guid-2"],
            "created_count": 2
        },
        "message": "Citas creadas exitosamente"
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
        calendar_events = data.get('calendar_events', [])
        appointment_type = data.get('appointment_type', 'doctor')
        
        if not patient_id:
            return jsonify({
                'success': False,
                'message': 'patient_id es requerido'
            }), 400
        
        if not calendar_events or not isinstance(calendar_events, list):
            return jsonify({
                'success': False,
                'message': 'Se requiere al menos un evento en calendar_events'
            }), 400
        
        # Validar cada evento de calendario
        for i, event in enumerate(calendar_events):
            exam_id = event.get('exam_id')
            start_datetime = event.get('start_datetime')
            end_datetime = event.get('end_datetime')
            physician_id = event.get('physician_id')
            obra_social_id = event.get('obra_social_id')
            equipment_id = event.get('equipment_id')
            
            if not all([exam_id, start_datetime, end_datetime, physician_id, obra_social_id]):
                return jsonify({
                    'success': False,
                    'message': f'Evento {i+1}: Faltan campos requeridos exam_id, start_datetime, end_datetime, physician_id, obra_social_id'
                }), 400
            
            if appointment_type == 'equipment' and not equipment_id:
                return jsonify({
                    'success': False,
                    'message': f'Evento {i+1}: equipment_id es requerido para citas de tipo equipment'
                }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        created_appointment_ids = []
        
        try:
            # Crear cada evento de calendario como una cita separada
            for event in calendar_events:
                # Generar nuevo GUID para cada cita
                new_guid = str(uuid.uuid4())
                
                exam_id = event.get('exam_id')
                start_datetime = event.get('start_datetime')
                end_datetime = event.get('end_datetime')
                physician_id = event.get('physician_id')
                obra_social_id = event.get('obra_social_id')
                equipment_id = event.get('equipment_id')
                
                # Insertar cada cita
                if appointment_type == 'equipment':
                    query = """
                        INSERT INTO nextris.tbagendaevents 
                        (guid, comienzo, fin, idequipment, idpatient, idexam, idmed, obrasocial, createdon, isadmitted)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), false)
                    """
                    params = (new_guid, start_datetime, end_datetime, equipment_id, 
                             patient_id, exam_id, physician_id, obra_social_id)
                else:
                    query = """
                        INSERT INTO nextris.tbagendaevents 
                        (guid, comienzo, fin, idmed, idpatient, idexam, obrasocial, createdon, isadmitted)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), false)
                    """
                    params = (new_guid, start_datetime, end_datetime, physician_id, 
                             patient_id, exam_id, obra_social_id)
                
                cursor.execute(query, params)
                created_appointment_ids.append(new_guid)
            
            # Confirmar todas las transacciones
            connection.commit()
            
            return jsonify({
                'success': True,
                'data': {
                    'appointment_ids': created_appointment_ids,
                    'created_count': len(created_appointment_ids)
                },
                'message': f'{len(created_appointment_ids)} cita(s) creada(s) exitosamente'
            }), 201
            
        except Exception as e:
            # Si hay error, hacer rollback
            connection.rollback()
            raise e
        
        finally:
            cursor.close()
            connection.close()
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/appointments', methods=['GET'])
@jwt_required()
def get_appointments():
    """
    Obtiene lista de citas con filtros y paginación
    
    Query params:
    - date: fecha específica (YYYY-MM-DD)
    - doctor_id: filtrar por médico
    - equipment_id: filtrar por equipo
    - admitted: true/false (filtrar por estado de admisión)
    - today: true (obtener solo citas del día actual)
    - page: número de página (default: 1)
    - per_page: items por página (default: 20, max: 100)
    
    Respuesta:
    {
        "success": true,
        "data": {
            "data": [...],
            "page": 1,
            "per_page": 20,
            "total": 150
        }
    }
    """
    try:
        # Obtener parámetros de query
        date_filter = request.args.get('date')
        doctor_id = request.args.get('doctor_id')
        equipment_id = request.args.get('equipment_id')
        admitted_filter = request.args.get('admitted')
        today_only = request.args.get('today', 'false').lower() == 'true'
        
        # Parámetros de paginación
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)  # Máximo 100 items
        
        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 20
            
        # Calcular offset
        offset = (page - 1) * per_page
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Query base para contar total de registros
        count_query = """
            SELECT COUNT(*)
            FROM nextris.tbagendaevents tba
            LEFT JOIN nextris.datapatient pat ON pat.guid = tba.idpatient
            LEFT JOIN nextris.isstudytype st ON st.guid = tba.idexam
            LEFT JOIN nextris.tbuser med ON med.guid = tba.idmed
            LEFT JOIN nextris.isequipment equip ON equip.guid = tba.idequipment
            WHERE 1=1
        """
        
        # Query base para obtener datos
        data_query = """
            SELECT 
                tba.guid,
                CONCAT(pat.surname, ' ', pat.name) as patient_name,
                tba.comienzo,
                tba.fin,
                st.description as exam,
                CONCAT(med.surname, ' ', med.name) as doctor,
                equip.aetitle as equipment,
                tba.isadmitted,
                tba.location_id,
                tba.idequipment as equipment_id,
                mod.description as modality
            FROM nextris.tbagendaevents tba
            LEFT JOIN nextris.datapatient pat ON pat.guid = tba.idpatient
            LEFT JOIN nextris.isstudytype st ON st.guid = tba.idexam
            LEFT JOIN nextris.tbuser med ON med.guid = tba.idmed
            LEFT JOIN nextris.isequipment equip ON equip.guid = tba.idequipment
            LEFT JOIN nextris.ismodality mod ON mod.guid = st.modality_id
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros a ambas queries
        filter_conditions = ""
        
        if today_only:
            filter_conditions += " AND DATE(tba.comienzo) = CURRENT_DATE"
        elif date_filter:
            filter_conditions += " AND DATE(tba.comienzo) = %s"
            params.append(date_filter)
        
        if doctor_id:
            filter_conditions += " AND tba.idmed = %s"
            params.append(doctor_id)
        
        if equipment_id:
            filter_conditions += " AND tba.idequipment = %s"
            params.append(equipment_id)
        
        if admitted_filter is not None:
            is_admitted = admitted_filter.lower() == 'true'
            filter_conditions += " AND tba.isadmitted = %s"
            params.append(is_admitted)
        
        # Ejecutar query de conteo
        cursor.execute(count_query + filter_conditions, params)
        total_items = cursor.fetchone()[0]
        
        # Calcular información de paginación
        total_pages = (total_items + per_page - 1) // per_page  # Redondear hacia arriba
        has_next = page < total_pages
        has_prev = page > 1
        next_page = page + 1 if has_next else None
        prev_page = page - 1 if has_prev else None
        
        # Ejecutar query de datos con LIMIT y OFFSET
        data_query += filter_conditions + " ORDER BY tba.comienzo DESC LIMIT %s OFFSET %s"
        data_params = params + [per_page, offset]
        
        cursor.execute(data_query, data_params)
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
                'is_admitted': bool(row[7]) if row[7] is not None else False,
                'location_id': row[8] if row[8] else None,
                'equipment_id': row[9] if row[9] else None,
                'modality': row[10] if row[10] else None
            })
        
        return jsonify({
            'success': True,
            'data': {
                'data': appointments,
                'page': page,
                'per_page': per_page,
                'total': total_items
            }
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


@api_blueprint.route('/institutional/locations/<location_id>/physicians', methods=['GET'])
@jwt_required()
def get_physicians_by_location(location_id):
    """
    Obtiene médicos solicitantes filtrados por ubicación
    
    GET /api/institutional/locations/{location_id}/physicians
    
    Path Parameters:
    - location_id (OBLIGATORIO): UUID de la ubicación
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "Dr. Juan Pérez"
            }
        ]
    }
    """
    try:
        if not location_id:
            return jsonify({
                'success': False,
                'message': 'El parámetro location_id es obligatorio'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT guid, description
            FROM nextris.isrequestingphysician
            WHERE location_id = %s
            ORDER BY description
        """
        
        cursor.execute(query, (location_id,))
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        physicians_list = []
        for row in results:
            physicians_list.append({
                'guid': row[0],
                'description': row[1]
            })
        
        return jsonify({
            'success': True,
            'data': physicians_list
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/institutional/locations/<location_id>/health-insurances', methods=['GET'])
@jwt_required()
def get_health_insurances_by_location(location_id):
    """
    Obtiene obras sociales (price lists) filtradas por ubicación
    
    GET /api/institutional/locations/{location_id}/health-insurances
    
    Path Parameters:
    - location_id (OBLIGATORIO): UUID de la ubicación
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "OSDE"
            }
        ]
    }
    """
    try:
        if not location_id:
            return jsonify({
                'success': False,
                'message': 'El parámetro location_id es obligatorio'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT guid, description
            FROM nextris.ispricelist
            WHERE location_id = %s AND isactive = 1
            ORDER BY description
        """
        
        cursor.execute(query, (location_id,))
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        insurances_list = []
        for row in results:
            insurances_list.append({
                'guid': row[0],
                'description': row[1]
            })
        
        return jsonify({
            'success': True,
            'data': insurances_list
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
            "study_instance_uid": "1.2.840..."
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
        
        # 1. Obtener datos del paciente
        cursor.execute("""
            SELECT patientid, name, surname, nationalcode, birthdate, sexcode
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
        
        # 2. Generar números de admisión y acceso
        cursor.execute("""
            SELECT MAX(CAST(SUBSTRING(admisionnumber, 4) AS INTEGER)) 
            FROM nextris.tbexamination 
            WHERE admisionnumber LIKE 'ADM%'
        """)
        last_adm = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT MAX(CAST(SUBSTRING(localacc, 4) AS INTEGER)) 
            FROM nextris.tbexamination 
            WHERE localacc LIKE 'ACC%'
        """)
        last_acc = cursor.fetchone()[0] or 0
        
        admission_number = f"ADM{(last_adm + 1):03d}"
        accession_number = f"ACC{(last_acc + 1):03d}"
        
        # 3. Obtener datos del equipo y modalidad
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
        
        # 4. Obtener descripción del estudio
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
        
        # 5. Generar Study Instance UID y enviar mensaje HL7 al dcm4chee
        import time
        timestamp = str(int(time.time() * 1000))
        study_instance_uid = f"1.2.840.{timestamp}.{patient[0]}"
        
        # Enviar mensaje HL7 al worklist (dcm4chee creará el mwl_item)
        study_instance_uid, hl7_success = HL7Service.send_exam_to_worklist(
            patient_data=patient,
            exam_data=study_type[0],
            equipment_data=equipment,
            modality_data=equipment[4],  # externalcode de la modalidad
            admission_number=admission_number,
            accession_number=accession_number
        )
        
        if not hl7_success:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Error al enviar orden al worklist DICOM'
            }), 500
        
        # 6. Insertar examen en tbexamination
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
                idseverity, idrequestingphysician, idpricelist
            ) VALUES (
                uuid_generate_v4(), %s, %s, %s, %s, %s, %s, NOW(), 'A', 0, %s, %s, %s
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
            exam_data.get('insurance_id')
        ))
        
        exam_guid = cursor.fetchone()[0]
        
        # 7. Crear registro en tbReport
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
                'study_instance_uid': study_instance_uid
            },
            'message': 'Orden creada exitosamente'
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
