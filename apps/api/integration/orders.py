# -*- encoding: utf-8 -*-
"""
API de Integración - Endpoints para recibir órdenes externas
Permite a sistemas externos enviar órdenes de exámenes al RIS
"""

from flask import jsonify, request
import psycopg2
import uuid
from datetime import datetime
from apps.api import api_blueprint


def get_db_config():
    """Obtiene la configuración de la base de datos"""
    from apps.home.services import ConfigService
    db_config = ConfigService.get_db_config()
    return db_config


def find_or_create_patient(cursor, patient_data, patientdomain_id):
    """
    Busca un paciente por DNI o lo crea si no existe.
    Retorna el guid UUID (no el patientid) porque tbexamination.idpatient referencia datapatient.guid.
    """
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
        (guid, name, surname, patientid, nationalcode, birthdate, sexcode, id_patientdomain)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        new_guid,
        first_name,
        surname,
        new_patient_id,
        dni,
        birthdate,
        sex,
        patientdomain_id
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
        SELECT guid, name, hl7_enable_orm 
        FROM nextris.tbfacility 
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


def get_patientdomain_from_location(cursor, location_id):
    """
    Obtiene el patientdomain_id de una ubicación.
    """
    cursor.execute("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'nextris'
          AND table_name = 'tbfacility'
          AND column_name = 'id_patientdomain'
        LIMIT 1
    """)
    has_facility_domain = cursor.fetchone() is not None
    
    if has_facility_domain:
        cursor.execute("""
            SELECT COALESCE(NULLIF(f.id_patientdomain, ''), NULLIF(l.id_patientdomain, ''))
            FROM nextris.tblocation l
            LEFT JOIN nextris.tbfacility f ON f.guid = l.facility_id
            WHERE l.guid = %s
        """, (location_id,))
    else:
        cursor.execute("""
            SELECT NULLIF(l.id_patientdomain, '')
            FROM nextris.tblocation l
            WHERE l.guid = %s
        """, (location_id,))
    
    result = cursor.fetchone()
    return result[0] if result and result[0] else None


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
            # Validar que la institución existe y tiene HL7 habilitado
            if institution_name:
                facility = find_facility_by_name(cursor, institution_name)
                if not facility:
                    return jsonify({
                        'success': False,
                        'message': f'Institución no encontrada: {institution_name}'
                    }), 404
                if not facility['hl7_enable_orm']:
                    return jsonify({
                        'success': False,
                        'message': f'HL7 no habilitado para la institución: {institution_name}'
                    }), 403
            
            # Buscar ubicación
            location_id = None
            patientdomain_id = None
            
            if location_name:
                location_id = find_location_by_name(cursor, location_name, institution_name)
                if location_id:
                    patientdomain_id = get_patientdomain_from_location(cursor, location_id)
            
            # Si no se encontró patientdomain, usar el primero disponible
            if not patientdomain_id:
                cursor.execute("SELECT guid FROM nextris.ispatientdomain LIMIT 1")
                result = cursor.fetchone()
                patientdomain_id = result[0] if result else None
            
            # Buscar o crear paciente
            patient_id = find_or_create_patient(cursor, patient_data, patientdomain_id)
            
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
                INSERT INTO nextris.tbexamination (
                    guid, studyinstanceuid, idpatient, studytype_id, idequipment,
                    AdmisionNumber, localacc, createdon, status, isexecuted,
                    isadmitted, idreferringphysician, location_id
                ) VALUES (
                    uuid_generate_v4(), %s, %s, %s, %s, %s, %s, NOW(), 'A', 0,
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
                    uuid_generate_v4(), %s, %s, %s, NOW()
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
