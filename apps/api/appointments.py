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
import uuid
from apps.home.services import HL7Service
from apps.services.timezone_utils import (
    DEFAULT_TIMEZONE,
    format_local_datetime,
    get_timezone,
    to_utc_naive,
)


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.services import ConfigService
        config = ConfigService.get_db_config()
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
            "timezone": "America/Argentina/Buenos_Aires",
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
        
        # Obtener timezone de la ubicación del equipo
        query_timezone = """
            SELECT tbl.timezone
            FROM nextris.isequipment equip
            LEFT JOIN nextris.tblocation tbl ON equip.location_id = tbl.guid
            WHERE equip.aetitle = %s
            LIMIT 1
        """
        cursor.execute(query_timezone, (equipment_aetitle,))
        timezone_result = cursor.fetchone()
        default_tz = DEFAULT_TIMEZONE
        timezone = timezone_result[0] if timezone_result and timezone_result[0] else default_tz

        # Crear objeto timezone con fallback
        tz = get_timezone(timezone)
        timezone = getattr(tz, 'zone', default_tz)

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

        # Formatear eventos - convertir UTC a hora local
        events_list = []
        for ev in eventos:
            start_time = ev[1]
            end_time = ev[2]

            if start_time and end_time:
                try:
                    start_str = format_local_datetime(start_time, timezone)
                except Exception:
                    start_str = start_time.strftime('%Y-%m-%dT%H:%M:%S')

                try:
                    end_str = format_local_datetime(end_time, timezone)
                except Exception:
                    end_str = end_time.strftime('%Y-%m-%dT%H:%M:%S')

                event = {
                    'guid': str(ev[0]),
                    'start': start_str,
                    'end': end_str,
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
        
        # Mapeo de días (texto en español → número FullCalendar)
        days_mapping = {
            'lunes': 1, 'martes': 2, 'miércoles': 3, 'miercoles': 3,
            'jueves': 4, 'viernes': 5, 'sábado': 6, 'sabado': 6, 'domingo': 0
        }

        def parse_day(raw_day):
            """Convierte el día a número. Soporta valores numéricos (int o str) y texto en español."""
            if isinstance(raw_day, int):
                return raw_day
            day_str = str(raw_day).strip().lower()
            # Si es un valor numérico almacenado como string
            if day_str.isdigit():
                return int(day_str)
            return days_mapping.get(day_str, 1)

        work_hours = []
        for row in work_hours_data:
            work_hours.append({
                'day': parse_day(row[0]),
                'start': row[1].strftime('%H:%M:%S') if row[1] else '08:00:00',
                'end': row[2].strftime('%H:%M:%S') if row[2] else '17:00:00'
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'timezone': timezone,
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
        "start_datetime": "2025-12-05 10:00:00",  // ← Hora LOCAL
        "end_datetime": "2025-12-05 11:00:00",    // ← Hora LOCAL
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
        
        start_datetime = data.get('start_datetime')
        end_datetime = data.get('end_datetime')
        equipment_id = data.get('equipment_id')  # Opcional
        
        if not start_datetime or not end_datetime:
            return jsonify({
                'success': False,
                'message': 'Los campos start_datetime y end_datetime son requeridos'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que la cita existe y obtener su equipo
        cursor.execute(
            "SELECT guid, idequipment FROM nextris.tbagendaevents WHERE guid = %s",
            (appointment_id,)
        )
        
        result = cursor.fetchone()
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Cita no encontrada'
            }), 404
        
        _, current_equipment_id = result
        
        # Si no se proporciona equipment_id, usar el actual
        if not equipment_id:
            equipment_id = current_equipment_id
        
        # Obtener timezone de la location del equipo
        timezone_str = DEFAULT_TIMEZONE
        if equipment_id:
            query_tz = """
                SELECT COALESCE(tbl.timezone, 'America/Argentina/Buenos_Aires')
                FROM nextris.isequipment tbe
                LEFT JOIN nextris.tblocation tbl ON tbl.guid = tbe.location_id
                WHERE tbe.guid = %s
            """
            cursor.execute(query_tz, (equipment_id,))
            tz_result = cursor.fetchone()
            if tz_result:
                timezone_str = tz_result[0]
        
        # Convertir datetimes de local a UTC
        try:
            start_to_save = to_utc_naive(start_datetime, timezone_str)
            end_to_save = to_utc_naive(end_datetime, timezone_str)
            
            print(f"[DEBUG RESCHEDULE] appointment_id: {appointment_id}, start: {start_to_save}, end: {end_to_save}, equipment_id: {equipment_id}")
        except Exception as e:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': f'Error en formato de fecha: {str(e)}'
            }), 400
        
        # Construir el UPDATE dinámicamente dependiendo de qué campos se actualicen
        set_clauses = ["comienzo = %s", "fin = %s"]
        params = [start_to_save, end_to_save]
        
        if equipment_id and equipment_id != current_equipment_id:
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
        "location_id": "guid-de-la-ubicacion (opcional)",
        "calendar_events": [
            {
                "exam_id": "guid-del-examen",
                "start_datetime": "2025-12-05 10:00",
                "end_datetime": "2025-12-05 11:00",
                "physician_id": "guid-del-medico",
                "obra_social_id": "guid-de-la-obra-social",
                "equipment_id": "optional-guid-del-equipo"
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
        location_id = data.get('location_id')  # Parámetro opcional
        
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
            
            if not all([exam_id, start_datetime, end_datetime]):
                return jsonify({
                    'success': False,
                    'message': f'Evento {i+1}: Faltan campos requeridos exam_id, start_datetime, end_datetime'
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
                
                # Obtener timezone de la location del equipo
                timezone_str = DEFAULT_TIMEZONE
                if equipment_id:
                    query_tz = """
                        SELECT COALESCE(tbl.timezone, 'America/Argentina/Buenos_Aires')
                        FROM nextris.isequipment tbe
                        LEFT JOIN nextris.tblocation tbl ON tbl.guid = tbe.location_id
                        WHERE tbe.guid = %s
                    """
                    cursor.execute(query_tz, (equipment_id,))
                    tz_result = cursor.fetchone()
                    if tz_result:
                        timezone_str = tz_result[0]
                elif location_id:
                    cursor.execute(
                        "SELECT COALESCE(timezone, %s) FROM nextris.tblocation WHERE guid = %s",
                        (DEFAULT_TIMEZONE, location_id),
                    )
                    tz_result = cursor.fetchone()
                    if tz_result:
                        timezone_str = tz_result[0]
                
                # Convertir datetimes de local a UTC
                try:
                    start_datetime_to_save = to_utc_naive(start_datetime, timezone_str)
                    end_datetime_to_save = to_utc_naive(end_datetime, timezone_str)
                except Exception as tz_error:
                    raise ValueError(f'Formato de fecha inválido: {tz_error}') from tz_error
                
                # Construir INSERT dinámicamente según campos disponibles
                columns = ['guid', 'comienzo', 'fin', 'idpatient', 'idexam']
                values = [new_guid, start_datetime_to_save, end_datetime_to_save, patient_id, exam_id]

                if appointment_type == 'equipment' and equipment_id:
                    columns.append('idequipment')
                    values.append(equipment_id)

                if physician_id:
                    columns.append('idmed')
                    values.append(physician_id)

                if obra_social_id:
                    columns.append('obrasocial')
                    values.append(obra_social_id)

                if location_id:
                    columns.append('location_id')
                    values.append(location_id)

                # createdon e isadmitted van al final con valores SQL literales
                columns.extend(['createdon', 'isadmitted'])
                placeholders = ', '.join(['%s'] * len(values) + ['NOW()', 'false'])
                query = f"""
                    INSERT INTO nextris.tbagendaevents
                    ({', '.join(columns)})
                    VALUES ({placeholders})
                """
                
                cursor.execute(query, tuple(values))
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
            "data": [
                {
                    "guid": "...",
                    "patient_name": "...",
                    "start": "2025-12-05T10:00:00",
                    "end": "2025-12-05T11:00:00",
                    "exam": "...",
                    "doctor": "...",
                    "equipment": "...",
                    "is_admitted": false,
                    "location_id": "...",
                    "equipment_id": "...",
                    "modality": "...",
                    "timezone": "America/Argentina/Buenos_Aires"
                }
            ],
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
        search = request.args.get('search', '').strip()
        
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
            LEFT JOIN nextris.tblocation tbl_event ON tbl_event.guid = tba.location_id
            LEFT JOIN nextris.tblocation tbl_equip ON tbl_equip.guid = equip.location_id
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
                mod.description as modality,
                COALESCE(tbl_equip.timezone, tbl_event.timezone, 'America/Argentina/Buenos_Aires') as timezone,
                tba.idexam as exam_id
            FROM nextris.tbagendaevents tba
            LEFT JOIN nextris.datapatient pat ON pat.guid = tba.idpatient
            LEFT JOIN nextris.isstudytype st ON st.guid = tba.idexam
            LEFT JOIN nextris.tbuser med ON med.guid = tba.idmed
            LEFT JOIN nextris.isequipment equip ON equip.guid = tba.idequipment
            LEFT JOIN nextris.ismodality mod ON mod.guid = st.modality_id
            LEFT JOIN nextris.tblocation tbl_event ON tbl_event.guid = tba.location_id
            LEFT JOIN nextris.tblocation tbl_equip ON tbl_equip.guid = equip.location_id
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros a ambas queries
        filter_conditions = ""
        
        local_timezone_sql = "COALESCE(tbl_equip.timezone, tbl_event.timezone, 'America/Argentina/Buenos_Aires')"
        local_start_sql = f"((tba.comienzo AT TIME ZONE 'UTC') AT TIME ZONE {local_timezone_sql})"

        if today_only:
            filter_conditions += f" AND DATE({local_start_sql}) = (CURRENT_TIMESTAMP AT TIME ZONE {local_timezone_sql})::date"
        elif date_filter:
            filter_conditions += f" AND DATE({local_start_sql}) = %s"
            params.append(date_filter)
        
        if doctor_id:
            filter_conditions += " AND tba.idmed = %s"
            params.append(doctor_id)
        
        if equipment_id:
            filter_conditions += " AND tba.idequipment = %s"
            params.append(equipment_id)
        
        if search:
            filter_conditions += " AND (CONCAT(pat.surname, ' ', pat.name) ILIKE %s OR pat.name ILIKE %s OR pat.surname ILIKE %s OR equip.aetitle ILIKE %s OR st.description ILIKE %s)"
            search_param = f'%{search}%'
            params.extend([search_param, search_param, search_param, search_param, search_param])

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
        
        # Timezone por defecto (fallback)
        default_tz = DEFAULT_TIMEZONE
        response_timezone = default_tz
        
        # Formatear resultados
        appointments = []
        for row in results:
            # Convertir de UTC (naive) a la zona horaria local por cada fila
            start_time = row[2]
            end_time = row[3]
            row_timezone = row[11] if row[11] else default_tz

            tz = get_timezone(row_timezone)
            row_timezone = getattr(tz, 'zone', default_tz)

            if response_timezone == default_tz and row_timezone:
                response_timezone = row_timezone
            
            if start_time:
                try:
                    start_str = format_local_datetime(start_time, row_timezone, separator=' ')
                except Exception:
                    start_str = str(start_time)
            else:
                start_str = ''

            if end_time:
                try:
                    end_str = format_local_datetime(end_time, row_timezone, separator=' ')
                except Exception:
                    end_str = str(end_time)
            else:
                end_str = ''
            
            appointments.append({
                'guid': row[0],
                'patient_name': row[1] or 'Sin paciente',
                'start': start_str,
                'end': end_str,
                'exam': row[4] or 'Sin examen',
                'exam_id': row[12] if row[12] else None,
                'doctor': row[5] or 'Sin médico',
                'equipment': row[6] or 'Sin equipo',
                'is_admitted': bool(row[7]) if row[7] is not None else False,
                'location_id': row[8] if row[8] else None,
                'equipment_id': row[9] if row[9] else None,
                'modality': row[10] if row[10] else None,
                'timezone': row_timezone
            })
        
        return jsonify({
            'success': True,
            'data': {
                'timezone': response_timezone,
                'data': appointments,
                'page': page,
                'per_page': per_page,
                'total': total_items
            }
        }), 200
        
    except Exception as e:
        import traceback
        print(f"Error en GET /appointments: {str(e)}")
        traceback.print_exc()
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


@api_blueprint.route('/institutional/locations/<location_id>/physicians', methods=['GET'])
@api_blueprint.route('/institutional/physicians', methods=['GET'])
@jwt_required()
def get_physicians_by_location(location_id=None):
    """
    Obtiene médicos solicitantes filtrados opcionalmente por ubicación
    
    GET /api/institutional/locations/{location_id}/physicians
    GET /api/institutional/physicians
    
    Path Parameters:
    - location_id (OPCIONAL): UUID de la ubicación
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "Dr. Juan Pérez",
                "location_id": "...",
                "location_name": "..."
            }
        ]
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
        
        # Consulta con JOIN para incluir información de la ubicación
        query = """
            SELECT p.guid, p.description, p.location_id, l.name as location_name
            FROM nextris.isrequestingphysician p
            LEFT JOIN nextris.tblocation l ON p.location_id = l.guid
            WHERE 1=1
        """
        
        params = []
        
        # Agregar filtro de ubicación si se proporciona
        if location_id:
            query += " AND p.location_id = %s"
            params.append(location_id)
        
        query += " ORDER BY p.description"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        physicians_list = []
        for row in results:
            physicians_list.append({
                'guid': row[0],
                'description': row[1],
                'location_id': row[2],
                'location_name': row[3]
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


@api_blueprint.route('/institutional/locations/<location_id>/rads_per_location', methods=['GET'])
@jwt_required()
def get_rads_per_location(location_id):
    """
    Obtiene radiólogos (médicos firmantes) con acceso a una ubicación.

    GET /api/institutional/locations/{location_id}/rads_per_location
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

        query = """
            SELECT DISTINCT
                u.guid,
                CONCAT(COALESCE(u.name, ''), ' ', COALESCE(u.surname, '')) as description,
                r.description as role
            FROM nextris.tbuser u
            INNER JOIN nextris.isrole r ON r.guid = u.idrole
            INNER JOIN nextris.rel_user_location rul ON rul.user_id = u.guid
            WHERE u.isactive = 1
              AND rul.location_id = %s
              AND (
                  r.description ILIKE '%%med%%' OR
                  r.description ILIKE '%%rad%%'
              )
            ORDER BY description
        """

        cursor.execute(query, (location_id,))
        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        rads_list = []
        for row in rows:
            rads_list.append({
                'guid': row[0],
                'description': (row[1] or '').strip(),
                'role': row[2]
            })

        return jsonify({
            'success': True,
            'data': rads_list
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/institutional/locations/<location_id>/health-insurances', methods=['GET'])
@api_blueprint.route('/institutional/health-insurances', methods=['GET'])
@jwt_required()
def get_health_insurances_by_location(location_id=None):
    """
    Obtiene obras sociales filtradas opcionalmente por ubicación

    GET /api/institutional/locations/{location_id}/health-insurances
    GET /api/institutional/health-insurances

    Path Parameters:
    - location_id (OPCIONAL): UUID de la ubicación

    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "OSDE",
                "location_id": "...",
                "location_name": "..."
            }
        ]
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

        if location_id:
            query = """
                SELECT hi.guid, hi.description,hi.externalcode,hi.headerdescription
                FROM nextris.ishealthinsurances hi
                INNER JOIN nextris.rel_insurance_location ril ON hi.guid = ril.insurance_id
                WHERE hi.isactive = 1
                AND ril.location_id = %s
                ORDER BY hi.description
            """
            cursor.execute(query, [location_id])
        else:
            query = """
                SELECT hi.guid, hi.description
                FROM nextris.ishealthinsurances hi
                WHERE hi.isactive = 1
                ORDER BY hi.description
            """
            cursor.execute(query)

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
