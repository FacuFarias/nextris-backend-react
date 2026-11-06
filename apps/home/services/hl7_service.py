import os
"""
Servicio de HL7 para el sistema RIS
Maneja comunicación HL7 y generación de mensajes
"""

import socket
import time
import pydicom.uid
from .config_service import ConfigService


class HL7Service:
    """Servicio para gestión de mensajes HL7"""

    @staticmethod
    def send_hl7_message(message, host=None, port=None):
        """
        Envía un mensaje HL7 al servidor especificado
        
        Args:
            message: Mensaje HL7 a enviar
            host: Host del servidor HL7 (si no se especifica, usa configuración)
            port: Puerto del servidor HL7 (por defecto 2575 para DCM4CHEE)
        """
        if port is None:
            port = int(os.getenv('HL7_ORM_PORT', '2575'))
        if host is None:
            host = os.getenv('HL7_HOST', ConfigService.get_ipserver())
            
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((host, port))

            # Agregar delimitadores para el protocolo MLLP
            message_with_delimiters = f"\x0b{message}\x1c\r"
            s.sendall(message_with_delimiters.encode())
            
            response = s.recv(4096)
            s.close()

            return response.decode() if response else None
        except Exception as e:
            print(f"[HL7] Error: {e}")
            return None

    @staticmethod
    def create_orm_message(patient_data, exam_data, equipment_data, modality_data, 
                          admission_number, accession_number, study_instance_uid, 
                          message_control_id="123456"):
        """
        Crea un mensaje HL7 ORM (Order Message)
        """
        import datetime
        current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        
        print(f"[HL7] 📝 Creando mensaje ORM con StudyInstanceUID: {study_instance_uid}")
        
        message = (
            f"MSH|^~\\&|HIS|RIS|PACS|Radiology|{current_time}|QUE|ORM^O01|{message_control_id}|P|2.3\r"
            f"PID|{admission_number}||{patient_data[3] if len(patient_data) > 3 else patient_data[0]}||{patient_data[1]}^{patient_data[2]}|{patient_data[3] if len(patient_data) > 3 else patient_data[0]}|19700101|{patient_data[4] if len(patient_data) > 4 else 'M'}||||||||M\r"
            f"PV1|{admission_number}|I|^^^Department|||||||^Referring^Doctor|||||||||{accession_number}\r"
            f"ORC|NW||||SC||1^once^^^^S||T||||||||Didrasoft|\r"
            f"OBR|1|\r"
            f"IPC|{accession_number}||{study_instance_uid}||{modality_data}|{exam_data}|||GATEWAY|||\r"
        )
        
        print(f"[HL7] ✅ Mensaje creado con StudyInstanceUID en IPC: {study_instance_uid}")
        
        return message

    @staticmethod
    def create_cancel_message(patient_id, study_instance_uid, message_control_id="123457"):
        """
        Crea un mensaje HL7 de cancelación
        
        Args:
            patient_id: ID del paciente
            study_instance_uid: UID de instancia del estudio
            message_control_id: ID de control del mensaje
        """
        message = (
            f"MSH|^~\\&|HIS|RIS|PACS|Radiology|202306241200|QUE|ORM^O01|{message_control_id}|P|2.3\r"
            f"PID|2002||{patient_id}^^^public|\r"
            "PV1||E|\r"
            "ORC|CA||||CA|\r"
            "OBR|1|\r"
            f"IPC|||{study_instance_uid}"
        )
        
        return message

    @staticmethod
    def generate_study_instance_uid():
        """Genera un nuevo Study Instance UID"""
        return pydicom.uid.generate_uid()

    @staticmethod
    def send_exam_to_worklist(patient_data, exam_data, equipment_data, modality_data, 
                             admission_number, accession_number, retries=3, delay=1):
        """
        Envía un examen completo al worklist con reintentos
        """
        study_instance_uid = HL7Service.generate_study_instance_uid()
        
        message = HL7Service.create_orm_message(
            patient_data, exam_data, equipment_data, modality_data,
            admission_number, accession_number, study_instance_uid
        )
        
        for attempt in range(retries):
            try:
                response = HL7Service.send_hl7_message(message)
                
                if response:
                    return study_instance_uid, True
                    
            except Exception as e:
                pass
                
            if attempt < retries - 1:
                time.sleep(delay)
        
        return study_instance_uid, False

    @staticmethod
    def cancel_worklist_item(patient_id, study_instance_uid):
        """
        Cancela un item del worklist
        
        Args:
            patient_id: ID del paciente
            study_instance_uid: UID de instancia del estudio
        """
        message = HL7Service.create_cancel_message(patient_id, study_instance_uid)
        
        try:
            response = HL7Service.send_hl7_message(message)
            if response:
                print(f"Mensaje de cancelación HL7 enviado correctamente para {study_instance_uid}")
                return True
            else:
                print(f"Fallo al enviar el mensaje de cancelación HL7 para {study_instance_uid}")
                return False
                
        except Exception as e:
            print(f"Error al enviar mensaje de cancelación HL7 para {study_instance_uid}: {e}")
            return False

    @staticmethod
    def _escape_hl7(text):
        """Escapa caracteres especiales HL7 en un texto."""
        if not text:
            return ''
        text = str(text)
        text = text.replace('\\', '\\\\')
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        text = text.replace('\n', '\\.br\\')
        text = text.replace('|', '\\E\\')
        text = text.replace('^', '\\S\\')
        text = text.replace('&', '\\T\\')
        text = text.replace('~', '\\R\\')
        return text

    @staticmethod
    def create_oru_message(patient_data, exam_data, report_data, facility_name,
                           location_name, message_control_id=None):
        """
        Crea un mensaje HL7 ORU^R01 (Observation Result) para envío de reportes firmados.

        Args:
            patient_data: dict con patientid, name, surname, birthdate, sexcode
            exam_data: dict con localacc, studyinstanceuid, study_description, referring_physician
            report_data: dict con findings, impressions, techniques, conclusions, pdfpath
            facility_name: nombre de la facility (MSH-4 Sending Facility)
            location_name: nombre de la ubicación (PV1-3)
            message_control_id: ID de control del mensaje (auto-generado si no se provee)
        """
        import datetime
        import uuid

        current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        if message_control_id is None:
            message_control_id = str(uuid.uuid4())[:8]

        escape = HL7Service._escape_hl7

        def _format_hl7_date(dt):
            if dt is None:
                return ''
            if isinstance(dt, str):
                try:
                    dt = datetime.datetime.strptime(dt[:10], '%Y-%m-%d')
                except (ValueError, IndexError):
                    return ''
            return dt.strftime('%Y%m%d')

        patient_id = patient_data.get('patientid', '') or ''
        surname = escape(patient_data.get('surname', '') or '')
        name = escape(patient_data.get('name', '') or '')
        birthdate = _format_hl7_date(patient_data.get('birthdate'))
        sex = patient_data.get('sexcode', '') or ''

        accession = exam_data.get('localacc', '') or ''
        study_desc = escape(exam_data.get('study_description', '') or '')
        referring = escape(exam_data.get('referring_physician', '') or '')

        findings = escape(report_data.get('findings', '') or '')
        impressions = escape(report_data.get('impressions', '') or '')
        techniques = escape(report_data.get('techniques', '') or '')
        conclusions = escape(report_data.get('conclusions', '') or '')
        pdfpath = escape(report_data.get('pdfpath', '') or '')

        message = (
            f"MSH|^~\\&|RIS|{facility_name}|PACS|Radiology|{current_time}||ORU^R01|{message_control_id}|P|2.3\r"
            f"PID|||{patient_id}||{surname}^{name}||{birthdate}|{sex}\r"
            f"PV1|||{location_name}\r"
            f"OBR|1||{accession}||{study_desc}||||||{referring}\r"
            f"OBX|1|TX|FINDINGS||{findings}||||||F\r"
            f"OBX|2|TX|IMPRESSIONS||{impressions}||||||F\r"
            f"OBX|3|TX|TECHNIQUES||{techniques}||||||F\r"
            f"OBX|4|TX|CONCLUSIONS||{conclusions}||||||F\r"
            f"OBX|5|TX|ACCESSION_NUMBER||{accession}||||||F\r"
            f"OBX|6|TX|PDF_PATH||{pdfpath}||||||F\r"
        )

        return message

    @staticmethod
    def send_report_oru(patient_data, exam_data, report_data, facility_name,
                        location_name, host=None, port=9193, retries=3, delay=1):
        """
        Envía un reporte firmado como mensaje ORU^R01 con reintentos.

        Args:
            patient_data: dict con datos del paciente
            exam_data: dict con datos del examen
            report_data: dict con datos del reporte
            facility_name: nombre de la facility
            location_name: nombre de la ubicación
            host: destino HL7 (default: ConfigService.get_ipserver())
            port: puerto HL7 (default: 2575)
            retries: cantidad de reintentos (default: 3)
            delay: segundos entre reintentos (default: 1)

        Returns:
            tuple: (message_str, success_bool)
        """
        message = HL7Service.create_oru_message(
            patient_data, exam_data, report_data, facility_name, location_name
        )

        for attempt in range(retries):
            try:
                response = HL7Service.send_hl7_message(message, host, port)

                if response:
                    print(f"[HL7_ORU] ORU enviado exitosamente (intento {attempt + 1})")
                    return message, True

            except Exception as e:
                print(f"[HL7_ORU] Intento {attempt + 1} falló: {e}")

            if attempt < retries - 1:
                time.sleep(delay)

        print(f"[HL7_ORU] Todos los reintentos agotados")
        return message, False