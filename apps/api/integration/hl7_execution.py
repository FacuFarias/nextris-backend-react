# -*- encoding: utf-8 -*-
"""
Integración HL7 para ejecución de imágenes.
Envía un ORU^R01 al puerto 9195 cuando se ejecuta una imagen,
si la facility tiene hl7_enable_report_sending activado.
"""

import psycopg2
from apps.home.services import HL7Service


def get_db_config():
    from apps.home.services import ConfigService
    return ConfigService.get_db_config()


def send_execution_hl7(exam_id):
    """
    Envía un mensaje HL7 ORU^R01 al ejecutar una imagen.

    1. Consulta la facility del examen y verifica hl7_enable_report_sending
    2. Si está habilitado, reúne datos del paciente/examen/ejecución
    3. Envía el ORU via HL7Service.send_hl7_message() al puerto 9195
    4. Nunca lanza excepción al caller — solo loguea errores
    """
    try:
        db_config = get_db_config()
        if not db_config:
            print("[HL7_EXEC] Error: no se pudo obtener config de DB")
            return

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        try:
            cursor.execute("""
                SELECT
                    l.facility_id,
                    f.name AS facility_name,
                    l.name AS location_name,
                    f.hl7_enable_report_sending
                FROM nextris.tbexamination e
                LEFT JOIN nextris.isequipment eq ON e.idequipment = eq.guid
                LEFT JOIN nextris.tblocation l ON COALESCE(e.location_id, eq.location_id) = l.guid
                LEFT JOIN nextris.tbfacility f ON l.facility_id = f.guid
                WHERE e.guid = %s
            """, (exam_id,))

            row = cursor.fetchone()
            if not row:
                print(f"[HL7_EXEC] Examen no encontrado: {exam_id}")
                return

            facility_id, facility_name, location_name, hl7_enabled = row

            if not hl7_enabled:
                print(f"[HL7_EXEC] HL7 deshabilitado para facility: {facility_name}")
                return

            cursor.execute("""
                SELECT
                    p.patientid,
                    p.name,
                    p.surname,
                    p.birthdate,
                    p.sexcode,
                    e.localacc,
                    e.studyinstanceuid,
                    st.description AS study_description,
                    COALESCE(u_ref.username, '') AS referring_physician,
                    e.history,
                    e.clinicalquestion,
                    e.laterality_id,
                    e.stat,
                    e.numberofviews,
                    e.othersdetails,
                    e.executiondate
                FROM nextris.tbexamination e
                LEFT JOIN nextris.datapatient p ON e.idpatient = p.guid
                LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.guid
                LEFT JOIN nextris.tbuser u_ref ON e.idreferringphysician = u_ref.guid
                WHERE e.guid = %s
            """, (exam_id,))

            data = cursor.fetchone()
            if not data:
                print(f"[HL7_EXEC] No se encontraron datos para examen: {exam_id}")
                return

            patient_data = {
                'patientid': data[0],
                'name': data[1],
                'surname': data[2],
                'birthdate': data[3],
                'sexcode': data[4],
            }

            exam_info = {
                'localacc': data[5],
                'studyinstanceuid': data[6],
                'study_description': data[7],
                'referring_physician': data[8],
            }

            execution_data = {
                'history': data[9],
                'clinical_question': data[10],
                'laterality_id': data[11],
                'stat': data[12],
                'number_of_views': data[13],
                'other_details': data[14],
                'executedon': data[15],
            }

            message = _build_execution_oru(
                patient_data, exam_info, execution_data,
                facility_name or 'Unknown', location_name or 'Unknown'
            )

            print(f"[HL7_EXEC] Enviando ORU de ejecución para examen {exam_id}, facility: {facility_name}, location: {location_name}")

            success = HL7Service.send_hl7_message(message, port=9195)

            if success:
                print(f"[HL7_EXEC] ORU de ejecución enviado exitosamente para examen {exam_id}")
            else:
                print(f"[HL7_EXEC] Falló el envío del ORU de ejecución para examen {exam_id}")

        except Exception as inner_err:
            print(f"[HL7_EXEC] Error interno: {inner_err}")
        finally:
            cursor.close()
            connection.close()

    except Exception as outer_err:
        print(f"[HL7_EXEC] Error de conexión: {outer_err}")


def _build_execution_oru(patient_data, exam_data, execution_data, facility_name, location_name):
    """
    Construye un mensaje HL7 ORU^R01 con datos de ejecución de imagen.

    Segmentos:
    - MSH: encabezado
    - PID: datos del paciente
    - PV1: ubicación
    - OBR: orden/estudio
    - OBX: campos de ejecución (historia, pregunta clínica, etc.)
    """
    import datetime
    import uuid

    escape = HL7Service._escape_hl7

    current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    message_control_id = str(uuid.uuid4())[:8]

    def _format_hl7_date(dt):
        if dt is None:
            return ''
        if isinstance(dt, str):
            try:
                dt = datetime.datetime.strptime(dt[:10], '%Y-%m-%d')
            except (ValueError, IndexError):
                return ''
        return dt.strftime('%Y%m%d')

    def _format_hl7_datetime(dt):
        if dt is None:
            return ''
        if isinstance(dt, str):
            try:
                dt = datetime.datetime.fromisoformat(dt)
            except (ValueError, IndexError):
                return ''
        return dt.strftime('%Y%m%d%H%M%S')

    patient_id = patient_data.get('patientid', '') or ''
    surname = escape(patient_data.get('surname', '') or '')
    name = escape(patient_data.get('name', '') or '')
    birthdate = _format_hl7_date(patient_data.get('birthdate'))
    sex = patient_data.get('sexcode', '') or ''

    accession = exam_data.get('localacc', '') or ''
    study_desc = escape(exam_data.get('study_description', '') or '')
    referring = escape(exam_data.get('referring_physician', '') or '')

    history = escape(execution_data.get('history', '') or '')
    clinical_question = escape(execution_data.get('clinical_question', '') or '')
    laterality = escape(str(execution_data.get('laterality_id', '') or ''))
    stat_val = 'Y' if execution_data.get('stat') else 'N'
    number_of_views = escape(str(execution_data.get('number_of_views', '') or ''))
    other_details = escape(execution_data.get('other_details', '') or '')
    executed_on = _format_hl7_datetime(execution_data.get('executedon'))

    message = (
        f"MSH|^~\\&|RIS|{facility_name}|PACS|Radiology|{current_time}||ORU^R01|{message_control_id}|P|2.3\r"
        f"PID|||{patient_id}||{surname}^{name}||{birthdate}|{sex}\r"
        f"PV1|||{location_name}\r"
        f"OBR|1||{accession}||{study_desc}||||||{referring}||{executed_on}\r"
        f"OBX|1|TX|HISTORY||{history}||||||F\r"
        f"OBX|2|TX|CLINICAL_QUESTION||{clinical_question}||||||F\r"
        f"OBX|3|TX|LATERALITY||{laterality}||||||F\r"
        f"OBX|4|TX|STAT||{stat_val}||||||F\r"
        f"OBX|5|TX|NUMBER_OF_VIEWS||{number_of_views}||||||F\r"
        f"OBX|6|TX|OTHER_DETAILS||{other_details}||||||F\r"
    )

    return message
