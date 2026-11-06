# -*- encoding: utf-8 -*-
"""
Integración HL7 ORU - Envío de reportes firmados como mensajes ORU^R01
Se ejecuta como hook post-firma en los endpoints de firma de reportes.
"""

import os
import psycopg2
from apps.home.services import HL7Service


def get_db_config():
    from apps.home.services import ConfigService
    return ConfigService.get_db_config()


def send_report_hl7(exam_id):
    """
    Envía un reporte firmado como mensaje HL7 ORU^R01.

    1. Consulta la facility del examen y verifica hl7_enable_report_sending
    2. Si está habilitado, reúne datos del paciente/examen/reporte
    3. Envía el ORU via HL7Service.send_report_oru()
    4. Nunca lanza excepción al caller — solo loguea errores
    """
    try:
        db_config = get_db_config()
        if not db_config:
            print("[HL7_ORU] Error: no se pudo obtener config de DB")
            return

        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        try:
            cursor.execute("""
                SELECT
                    '1'::text AS facility_id,
                    f.name AS facility_name,
                    l.name AS location_name,
                    f.hl7_enable_report_sending
                FROM nextris.tbexamination e
                LEFT JOIN nextris.isequipment eq ON e.idequipment = eq.guid
                LEFT JOIN nextris.tblocation l ON COALESCE(e.location_id, eq.location_id) = l.guid
                LEFT JOIN nextris.app_config f ON f.id = 1
                WHERE e.guid = %s
            """, (exam_id,))

            row = cursor.fetchone()
            if not row:
                print(f"[HL7_ORU] Examen no encontrado: {exam_id}")
                return

            facility_id, facility_name, location_name, hl7_enabled = row

            if not hl7_enabled:
                print(f"[HL7_ORU] HL7 report sending deshabilitado para facility: {facility_name}")
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
                    COALESCE(NULLIF(rep.content, ''), rep.findings),
                    COALESCE(NULLIF(rep.study_reason, ''), rep.impressions),
                    rep.techniques,
                    COALESCE(NULLIF(rep.conclusion, ''), rep.conclusions),
                    NULL::text AS pdfpath
                FROM nextris.tbexamination e
                LEFT JOIN nextris.datapatient p ON e.idpatient = p.guid
                LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.guid
                LEFT JOIN nextris.tbuser u_ref ON e.idreferringphysician = u_ref.guid
                LEFT JOIN nextris.tbreport rep ON rep.idexamination = e.guid
                WHERE e.guid = %s
                ORDER BY
                    CASE
                        WHEN COALESCE(NULLIF(BTRIM(rep.findings), ''), '') <> ''
                          OR COALESCE(NULLIF(BTRIM(rep.techniques), ''), '') <> ''
                          OR COALESCE(NULLIF(BTRIM(rep.impressions), ''), '') <> ''
                          OR COALESCE(NULLIF(BTRIM(rep.conclusions), ''), '') <> ''
                        THEN 0 ELSE 1
                    END,
                    rep.date DESC NULLS LAST
                LIMIT 1
            """, (exam_id,))

            data = cursor.fetchone()
            if not data:
                print(f"[HL7_ORU] No se encontraron datos para examen: {exam_id}")
                return

            patient_data = {
                'patientid': data[0],
                'name': data[1],
                'surname': data[2],
                'birthdate': data[3],
                'sexcode': data[4],
            }

            exam_data = {
                'localacc': data[5],
                'studyinstanceuid': data[6],
                'study_description': data[7],
                'referring_physician': data[8],
            }

            report_data = {
                'findings': data[9],
                'impressions': data[10],
                'techniques': data[11],
                'conclusions': data[12],
                'pdfpath': data[13],
            }

            print(f"[HL7_ORU] Enviando ORU para examen {exam_id}, facility: {facility_name}, location: {location_name}")

            message, success = HL7Service.send_report_oru(
                patient_data=patient_data,
                exam_data=exam_data,
                report_data=report_data,
                facility_name=facility_name or 'Unknown',
                location_name=location_name or 'Unknown',
                host=os.getenv('HL7_HOST', '127.0.0.1'),
                port=int(os.getenv('HL7_REPORT_PORT', '9193')),
            )

            if success:
                print(f"[HL7_ORU] ORU enviado exitosamente para examen {exam_id}")
            else:
                print(f"[HL7_ORU] Falló el envío del ORU para examen {exam_id}")

        except Exception as inner_err:
            print(f"[HL7_ORU] Error interno: {inner_err}")
        finally:
            cursor.close()
            connection.close()

    except Exception as outer_err:
        print(f"[HL7_ORU] Error de conexión: {outer_err}")
