# -*- encoding: utf-8 -*-
"""
API de Integración - Endpoints para recibir órdenes externas
Permite a sistemas externos enviar órdenes de exámenes al RIS
"""

from flask import jsonify, request
import psycopg2
import uuid
import secrets
from datetime import datetime
from apps.api import api_blueprint


def get_db_config():
    """Obtiene la configuración de la base de datos"""
    from apps.home.services import ConfigService
    db_config = ConfigService.get_db_config()
    return db_config


def find_or_create_patient(cursor, patient_data):
    """
    Busca un paciente por DNI o lo crea si no existe.
    Retorna el guid UUID (no el patientid) porque tbexamination.idpatient referencia datapatient.guid.
    """
    from apps.services.veterinary import mode as patient_mode, VeterinaryError
    if patient_mode() == 'veterinary':
        external_id = str(patient_data.get('id') or '')
        cursor.execute("SELECT guid FROM nextris.datapatient WHERE patient_kind='animal' AND (patientid=%s OR guid=%s)",(external_id,external_id))
        row=cursor.fetchone()
        if not row:
            raise VeterinaryError('Registre primero el animal y utilice su PatientID, no el documento del responsable',409)
        return row[0]
    dni = patient_data.get('dni')
    name = patient_data.get('name', '')
    
    # Separar apellido y nombre (formato: "Apellido, Nombre")
    if ',' in name:
        parts = name.split(',', 1)
        surname = parts[0].strip()
        first_name = parts[1].strip()
    else:
        parts = name.split(' ', 1)
        surname = parts[0] if len(parts) > 0 else ''
        first_name = parts[1] if len(parts) > 1 else ''
    
    birthdate = patient_data.get('birthdate')
    sex = patient_data.get('sex', 'I')
    patient_id_external = patient_data.get('id')
    
    # Buscar paciente por DNI
    if dni:
        cursor.execute("""
            SELECT guid FROM nextris.datapatient 
            WHERE nationalcode = %s
            LIMIT 1
        """, (dni,))
        result = cursor.fetchone()
        if result:
            return result[0]
    
    # Buscar por patientid externo si se proporciona
    if patient_id_external:
        cursor.execute("""
            SELECT guid FROM nextris.datapatient 
            WHERE patientid = %s
            LIMIT 1
        """, (patient_id_external,))
        result = cursor.fetchone()
        if result:
            return result[0]
    
    # Crear nuevo paciente
    new_guid = str(uuid.uuid4())
    
    # Generar PatientID autoincremental
    cursor.execute("""
        SELECT patientid 
        FROM nextris.datapatient 
        WHERE patientid LIKE 'NR%' 
        ORDER BY patientid DESC 
        LIMIT 1
    """)
    result = cursor.fetchone()
    
    if result and result[0]:
        try:
            last_number = int(result[0][2:])
            new_number = last_number + 1
        except (ValueError, IndexError):
            new_number = 1
    else:
        new_number = 1
    
    new_patient_id = f"NR{new_number:08d}"
    
    cursor.execute("""
        INSERT INTO nextris.datapatient 
        (guid, name, surname, patientid, nationalcode, birthdate, sexcode)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        new_guid,
        first_name,
        surname,
        new_patient_id,
        dni,
        birthdate,
        sex
    ))
    
    return new_guid


def find_study_type_by_code(cursor, procedure_code):
    """
    Busca un tipo de estudio por código.
    Retorna el guid del studytype o None.
    """
    cursor.execute("""
        SELECT guid FROM nextris.isstudytype 
        WHERE code = %s
        LIMIT 1
    """, (procedure_code,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return None


def find_equipment_by_aet(cursor, aet):
    """
    Busca un equipo por AE Title.
    Retorna el guid del equipo o None.
    """
    cursor.execute("""
        SELECT guid FROM nextris.isequipment 
        WHERE aetitle = %s AND isactive = true
        LIMIT 1
    """, (aet,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return None


def find_location_by_name(cursor, location_name, institution_name):
    """
    Busca una ubicación por nombre.
    Retorna el guid de la ubicación o None.
    """
    cursor.execute("""
        SELECT guid FROM nextris.tblocation 
        WHERE LOWER(name) = LOWER(%s)
        LIMIT 1
    """, (location_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return None


def find_facility_by_name(cursor, institution_name):
    """
    Busca una facility por nombre (case-insensitive).
    Retorna un dict con guid, name, hl7_enable_orm o None si no existe.
    """
    cursor.execute("""
        SELECT id::text, name, hl7_enable_orm 
        FROM nextris.app_config 
        WHERE LOWER(name) = LOWER(%s)
        LIMIT 1
    """, (institution_name,))
    result = cursor.fetchone()
    if result:
        return {
            'guid': result[0],
            'name': result[1],
            'hl7_enable_orm': result[2]
        }
    return None




@api_blueprint.route('/integration/orders', methods=['POST'])
def receive_external_order():
    """
    Recibe una orden externa y crea el paciente y examen correspondiente.
    
    Body JSON:
    {
        "institution_name": "SUS",
        "location_name": "CLINICA 1",
        "patient": {
            "id": "23",
            "dni": "29074030",
            "name": "Dominicci, Pablo",
            "birthdate": "1981-09-25",
            "sex": "M"
        },
        "order": {
            "orderId": "18",
            "accessionNumber": "18-18-32",
            "procedure_code": "340302",
            "procedure_name": "RADIOGRAFIA O TELERRADIOGRAFIA DE TORAX PERFIL",
            "modality": "CR",
            "AET": "PACS_SERVER",
            "scheduledTime": "2026-06-10T16:30:00-03:00",
            "rad_id": "5",
            "priority_id": 0
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
        
        # Validar campos requeridos
        if not data.get('patient'):
            return jsonify({
                'success': False,
                'message': 'El campo patient es requerido'
            }), 400
        
        if not data.get('order'):
            return jsonify({
                'success': False,
                'message': 'El campo order es requerido'
            }), 400
        
        patient_data = data.get('patient')
        order_data = data.get('order')
        location_name = data.get('location_name')
        institution_name = data.get('institution_name')
        
        # Validar datos del paciente
        if not patient_data.get('dni') and not patient_data.get('id'):
            return jsonify({
                'success': False,
                'message': 'Se requiere al menos dni o id del paciente'
            }), 400
        
        # Validar datos de la orden
        if not order_data.get('procedure_code'):
            return jsonify({
                'success': False,
                'message': 'El campo procedure_code es requerido'
            }), 400
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        try:
            cursor.execute('SELECT name, hl7_enable_orm, hl7_bearer_token_orm FROM nextris.app_config WHERE id=1')
            settings = cursor.fetchone()
            if not settings or not settings[1]:
                return jsonify(success=False, message='La recepción de órdenes HL7 está deshabilitada'), 403
            if institution_name and str(institution_name).casefold() != str(settings[0]).casefold():
                return jsonify(success=False, message='Institución no encontrada'), 404
            if not settings[2]:
                return jsonify(success=False, message='Configure el token de recepción HL7'), 503
            authorization = request.headers.get('Authorization', '')
            if not secrets.compare_digest(authorization, 'Bearer ' + settings[2]):
                return jsonify(success=False, message='Token de integración inválido'), 401

            location_id = find_location_by_name(cursor, location_name, institution_name) if location_name else None
            patient_id = find_or_create_patient(cursor, patient_data)

            # Buscar tipo de estudio por código
            study_type_id = find_study_type_by_code(cursor, order_data.get('procedure_code'))
            
            if not study_type_id:
                # Si no encuentra por código, intentar buscar por descripción
                cursor.execute("""
                    SELECT guid FROM nextris.isstudytype 
                    WHERE LOWER(description) LIKE LOWER(%s)
                    LIMIT 1
                """, (f"%{order_data.get('procedure_name', '')}%",))
                result = cursor.fetchone()
                study_type_id = result[0] if result else None
            
            # Buscar equipo por AET
            equipment_id = None
            if order_data.get('AET'):
                equipment_id = find_equipment_by_aet(cursor, order_data.get('AET'))
            
            # Generar AdmisionNumber
            cursor.execute("""
                SELECT COALESCE(MAX(CAST(SUBSTRING(AdmisionNumber FROM 4) AS INTEGER)), 0) + 1
                FROM nextris.tbexamination
                WHERE AdmisionNumber LIKE 'ADM%'
            """)
            next_adm = cursor.fetchone()[0]
            adm_number = f"ADM{next_adm:03d}"
            
            # Usar accessionNumber del request o generar LocalAcc
            accession_number = order_data.get('accessionNumber')
            if not accession_number:
                cursor.execute("""
                    SELECT COALESCE(MAX(CAST(SUBSTRING(LocalAcc FROM 4) AS INTEGER)), 0) + 1
                    FROM nextris.tbexamination
                    WHERE LocalAcc LIKE 'ACC%'
                """)
                next_acc = cursor.fetchone()[0]
                accession_number = f"ACC{next_acc:03d}"
            
            # Generar Study Instance UID
            import time
            import hashlib
            timestamp = str(int(time.time() * 1000))
            patient_hash = int(hashlib.md5(str(patient_id).encode()).hexdigest()[:12], 16)
            study_instance_uid = f"1.2.840.{timestamp}.{patient_hash}"
            
            # Obtener rad_id como physician si se proporciona
            referring_physician_id = None
            if order_data.get('rad_id'):
                cursor.execute("""
                    SELECT guid FROM nextris.tbuser 
                    WHERE guid = %s
                """, (order_data.get('rad_id'),))
                result = cursor.fetchone()
                referring_physician_id = result[0] if result else None
            
            # Insertar examen en tbexamination
            cursor.execute("""
                INSERT INTO nextris.tbexamination ("w-order", 
                    guid, studyinstanceuid, idpatient, studytype_id, idequipment,
                    AdmisionNumber, localacc, createdon, status, isexecuted,
                    isadmitted, idreferringphysician, location_id
                ) VALUES (1, 
                    gen_random_uuid(), %s, %s, %s, %s, %s, %s, NOW(), 'A', 0,
                    1, %s, %s
                ) RETURNING guid
            """, (
                study_instance_uid,
                patient_id,
                study_type_id,
                equipment_id,
                adm_number,
                accession_number,
                referring_physician_id,
                location_id
            ))
            
            examination_guid = cursor.fetchone()[0]
            
            # Crear registro en tbReport
            cursor.execute("""
                INSERT INTO nextris.tbreport (
                    guid, admnumber, idexamination, idpatient, date
                ) VALUES (
                    gen_random_uuid(), %s, %s, %s, NOW()
                )
            """, (adm_number, examination_guid, patient_id))
            
            connection.commit()
            
            return jsonify({
                'success': True,
                'message': 'Orden recibida y procesada exitosamente',
                'data': {
                    'examination_guid': str(examination_guid),
                    'patient_id': patient_id,
                    'admission_number': adm_number,
                    'accession_number': accession_number,
                    'study_instance_uid': study_instance_uid
                }
            }), 201
            
        except Exception as e:
            connection.rollback()
            raise e
        finally:
            cursor.close()
            connection.close()
        
    except Exception as e:
        print(f"[API INTEGRATION] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error procesando orden: {str(e)}'
        }), 500
