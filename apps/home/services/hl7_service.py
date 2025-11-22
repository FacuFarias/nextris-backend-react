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
    def send_hl7_message(message, host=None, port=2575):
        """
        Envía un mensaje HL7 al servidor especificado
        
        Args:
            message: Mensaje HL7 a enviar
            host: Host del servidor HL7 (si no se especifica, usa configuración)
            port: Puerto del servidor HL7 (por defecto 2575 para DCM4CHEE)
        """
        if host is None:
            host = ConfigService.get_ipserver()
            
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