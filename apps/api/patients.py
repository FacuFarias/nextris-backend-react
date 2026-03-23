# -*- encoding: utf-8 -*-
"""
API de Pacientes - Endpoints REST para gestión de pacientes
Migrado desde patient_controller.py con autenticación JWT
"""

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
import uuid
from datetime import datetime
from apps.api import api_blueprint
from apps.api.permissions import require_permission
from apps.authentication.util import hash_pass


def get_db_config():
    """Obtiene la configuración de la base de datos"""
    from apps.home.services import ConfigService
    db_config = ConfigService.get_db_config()
    return db_config


def normalize_user_id(identity):
    """Support legacy string identities and object-based JWT identities."""
    if isinstance(identity, dict):
        return identity.get('id') or identity.get('guid') or identity.get('user_id')
    return identity


def get_user_patientdomain_ids(cursor, user_id):
    """Resolve domains from user locations/facilities, then legacy relation, then all domains."""
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'nextris'
          AND table_name = 'tbfacility'
          AND column_name = 'id_patientdomain'
        LIMIT 1
        """
    )
    has_facility_domain_column = cursor.fetchone() is not None

    if has_facility_domain_column:
        cursor.execute(
            """
            SELECT DISTINCT COALESCE(NULLIF(f.id_patientdomain, ''), NULLIF(l.id_patientdomain, ''))
            FROM nextris.rel_user_location rul
            INNER JOIN nextris.tblocation l ON l.guid = rul.location_id
            LEFT JOIN nextris.tbfacility f ON f.guid = l.facility_id
            WHERE rul.user_id = %s
              AND COALESCE(NULLIF(f.id_patientdomain, ''), NULLIF(l.id_patientdomain, '')) IS NOT NULL
            """,
            (user_id,),
        )
    else:
        cursor.execute(
            """
            SELECT DISTINCT NULLIF(l.id_patientdomain, '')
            FROM nextris.rel_user_location rul
            INNER JOIN nextris.tblocation l ON l.guid = rul.location_id
            WHERE rul.user_id = %s
              AND NULLIF(l.id_patientdomain, '') IS NOT NULL
            """,
            (user_id,),
        )

    location_domains = [row[0] for row in cursor.fetchall()]
    if location_domains:
        return location_domains

    # Legacy fallback while rel_user_patientdomain still exists.
    cursor.execute(
        """
        SELECT patientdomain_id
        FROM nextris.rel_user_patientdomain
        WHERE user_id = %s
        """,
        (user_id,)
    )

    legacy_domains = [row[0] for row in cursor.fetchall()]
    if legacy_domains:
        return legacy_domains

    cursor.execute("SELECT guid FROM nextris.ispatientdomain")
    return [row[0] for row in cursor.fetchall()]


# ===========================
# ENDPOINTS DE BÚSQUEDA Y LISTADO
# ===========================

@api_blueprint.route('/patients', methods=['GET'])
@jwt_required()
def get_patients():
    """
    Listar pacientes con paginación, búsqueda y conteo de estudios
    Filtra pacientes según los dominios a los que el usuario tiene acceso
    
    Query params:
    - page: número de página (default: 1)
    - per_page: resultados por página (default: 1000)
    - search: término de búsqueda (opcional)
    """
    try:
        user_id = normalize_user_id(get_jwt_identity())
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 1000, type=int)
        search = request.args.get('search', '')
        hide_without_studies = request.args.get('hide_without_studies', 'false').lower() == 'true'

        if page < 1:
            page = 1
        if per_page < 1 or per_page > 1000:
            per_page = 1000
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener los dominios del usuario (fallback: todos si no tiene asignados)
        user_domains = get_user_patientdomain_ids(cursor, user_id)
        
        if not user_domains:
            cursor.close()
            connection.close()
            return jsonify({
                'success': True,
                'data': {
                    'data': [],
                    'page': page,
                    'per_page': per_page,
                    'total': 0
                }
            }), 200
        
        search_pattern = f'%{search}%'
        offset = (page - 1) * per_page
        
        # Cláusula HAVING para filtrar pacientes sin estudios terminados
        having_clause = "HAVING COUNT(CASE WHEN tbex.isreported = 1 AND rep.pdfpath IS NOT NULL THEN tbex.guid END) > 0" if hide_without_studies else ""

        # Contar total de resultados
        count_query = f"""
            SELECT COUNT(*) FROM (
                SELECT dp.guid
                FROM nextris.datapatient dp
                LEFT JOIN nextris.tbexamination tbex ON tbex.idpatient = dp.guid
                LEFT JOIN nextris.tbreport rep ON rep.idexamination = tbex.guid
                WHERE dp.id_patientdomain = ANY(%s)
                AND (dp.name ILIKE %s OR dp.surname ILIKE %s OR dp.nationalcode ILIKE %s OR dp.patientid ILIKE %s)
                GROUP BY dp.guid
                {having_clause}
            ) sub
        """
        cursor.execute(count_query, (user_domains, search_pattern, search_pattern, search_pattern, search_pattern))
        total = cursor.fetchone()[0]

        # Obtener pacientes con conteo de estudios terminados
        query = f"""
            SELECT
                dp.guid,
                dp.name,
                dp.surname,
                dp.nationalcode,
                dp.sexcode,
                dp.birthdate,
                dp.phone,
                dp.email,
                dp.patientid,
                COUNT(CASE WHEN tbex.isreported = 1 AND rep.pdfpath IS NOT NULL THEN tbex.guid END) as study_count,
                tup.username,
                tup.status as user_status
            FROM nextris.datapatient dp
            LEFT JOIN nextris.tbexamination tbex ON tbex.idpatient = dp.guid
            LEFT JOIN nextris.tbreport rep ON rep.idexamination = tbex.guid
            LEFT JOIN nextris.tbuser_patient tup ON tup.datapatient_id = dp.guid
            WHERE dp.id_patientdomain = ANY(%s)
            AND (dp.name ILIKE %s OR dp.surname ILIKE %s OR dp.nationalcode ILIKE %s OR dp.patientid ILIKE %s)
            GROUP BY dp.guid, dp.name, dp.surname, dp.nationalcode, dp.sexcode,
                     dp.birthdate, dp.phone, dp.email, dp.patientid, tup.username, tup.status
            {having_clause}
            ORDER BY dp.surname, dp.name
            LIMIT %s OFFSET %s
        """

        cursor.execute(query, (user_domains, search_pattern, search_pattern, search_pattern, search_pattern, per_page, offset))

        patients = []
        for row in cursor.fetchall():
            patients.append({
                'guid': row[0],
                'name': row[1],
                'surname': row[2],
                'nationalcode': row[3],
                'gender': row[4],
                'birthdate': row[5].isoformat() if row[5] else None,
                'phone': row[6],
                'email': row[7],
                'patientid': row[8],
                'study_count': row[9],
                'username': row[10],
                'user_status': row[11]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'data': patients,
                'page': page,
                'per_page': per_page,
                'total': total
            }
        }), 200
        
    except Exception as e:
        print(f"[API PATIENTS] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/patients/minimal', methods=['GET'])
@jwt_required()
def get_patients_minimal():
    """
    Obtener información mínima de pacientes (para autocompletes)
    """
    try:
        user_id = normalize_user_id(get_jwt_identity())
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        query = """
            SELECT dp.guid, dp.name, dp.surname, dp.sexcode, 
                   TO_CHAR(dp.birthdate, 'DD/MM/YYYY') as birthdate, 
                   dp.nationalcode
            FROM nextris.datapatient dp
            INNER JOIN nextris.rel_user_patientdomain rup 
                ON dp.id_patientdomain = rup.patientdomain_id
            WHERE rup.user_id = %s
            ORDER BY dp.surname, dp.name
            LIMIT 500
        """
        
        cursor.execute(query, (user_id,))
        
        patients = []
        for row in cursor.fetchall():
            patients.append({
                'guid': row[0],
                'name': row[1],
                'surname': row[2],
                'gender': row[3],
                'birthdate': row[4],
                'nationalcode': row[5]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': patients
        }), 200
        
    except Exception as e:
        print(f"[API PATIENTS MINIMAL] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/patients/search', methods=['POST'])
@jwt_required()
def search_patients():
    """
    Buscar pacientes con término de búsqueda
    
    Body JSON:
    {
        "search_term": "..."
    }
    """
    try:
        user_id = normalize_user_id(get_jwt_identity())
        data = request.get_json()
        search_term = data.get('search_term', '')
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        query = """
            SELECT dp.guid, dp.patientid, dp.surname, dp.name, dp.nationalcode, dp.sexcode, dp.birthdate
            FROM nextris.datapatient dp
            INNER JOIN nextris.rel_user_patientdomain rup 
                ON dp.id_patientdomain = rup.patientdomain_id
            WHERE rup.user_id = %s
              AND (LOWER(dp.name) LIKE LOWER(%s) 
               OR LOWER(dp.surname) LIKE LOWER(%s) 
               OR dp.nationalcode LIKE %s
               OR dp.patientid LIKE %s)
            ORDER BY dp.surname, dp.name
            LIMIT 100
        """
        
        search_pattern = f"%{search_term}%"
        cursor.execute(query, (user_id, search_pattern, search_pattern, search_pattern, search_pattern))
        
        patients = []
        for row in cursor.fetchall():
            patients.append({
                'guid': row[0],
                'patientid': row[1],
                'surname': row[2],
                'name': row[3],
                'nationalcode': row[4],
                'gender': row[5],
                'birthdate': row[6].isoformat() if row[6] else None
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': patients
        }), 200
        
    except Exception as e:
        print(f"[API SEARCH PATIENTS] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/patients/search/advanced', methods=['POST'])
@jwt_required()
def search_patients_advanced():
    """
    Búsqueda avanzada de pacientes con múltiples criterios
    
    Body JSON:
    {
        "criteria": {
            "name": "...",
            "surname": "...",
            "national_code": "...",
            "patient_id": "..."
        }
    }
    """
    try:
        user_id = normalize_user_id(get_jwt_identity())
        data = request.get_json()
        criteria = data.get('criteria', {})
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        conditions = ["rup.user_id = %s"]
        params = [user_id]
        
        if criteria.get('name'):
            conditions.append("LOWER(dp.name) LIKE LOWER(%s)")
            params.append(f"%{criteria['name']}%")
            
        if criteria.get('surname'):
            conditions.append("LOWER(dp.surname) LIKE LOWER(%s)")
            params.append(f"%{criteria['surname']}%")
            
        if criteria.get('national_code'):
            conditions.append("dp.nationalcode = %s")
            params.append(criteria['national_code'])
            
        if criteria.get('patient_id'):
            conditions.append("dp.patientid = %s")
            params.append(criteria['patient_id'])
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT dp.guid, dp.patientid, dp.surname, dp.name, dp.nationalcode, dp.sexcode, dp.birthdate
            FROM nextris.datapatient dp
            INNER JOIN nextris.rel_user_patientdomain rup 
                ON dp.id_patientdomain = rup.patientdomain_id
            WHERE {where_clause}
            ORDER BY dp.surname, dp.name
            LIMIT 50
        """
        
        cursor.execute(query, params)
        
        patients = []
        for row in cursor.fetchall():
            patients.append({
                'guid': row[0],
                'patientid': row[1],
                'surname': row[2],
                'name': row[3],
                'nationalcode': row[4],
                'gender': row[5],
                'birthdate': row[6].isoformat() if row[6] else None
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': patients
        }), 200
        
    except Exception as e:
        print(f"[API SEARCH ADVANCED] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/patients/by-location', methods=['POST'])
@jwt_required()
def get_patients_by_location():
    """
    Obtener pacientes filtrados por ubicación
    
    Body JSON:
    {
        "location_id": "..."
    }
    """
    try:
        data = request.get_json()
        location_id = data.get('location_id')
        
        if not location_id:
            return jsonify({
                'success': False,
                'message': 'location_id requerido'
            }), 400
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener dominio heredado desde facility cuando la columna existe.
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'nextris'
              AND table_name = 'tbfacility'
              AND column_name = 'id_patientdomain'
            LIMIT 1
            """
        )
        has_facility_domain_column = cursor.fetchone() is not None

        if has_facility_domain_column:
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
        
        if not result or not result[0]:
            cursor.close()
            connection.close()
            return jsonify({
                'success': True,
                'data': []
            }), 200
        
        patientdomain_id = result[0]
        
        # Traer pacientes de ese dominio
        cursor.execute("""
            SELECT dp.guid, dp.name, dp.surname, dp.sexcode, 
                   TO_CHAR(dp.birthdate, 'DD/MM/YYYY') as birthdate, 
                   dp.nationalcode
            FROM nextris.datapatient dp
            WHERE dp.id_patientdomain = %s
            ORDER BY dp.surname, dp.name
            LIMIT 500
        """, (patientdomain_id,))
        
        patients = []
        for row in cursor.fetchall():
            patients.append({
                'guid': row[0],
                'name': row[1],
                'surname': row[2],
                'gender': row[3],
                'birthdate': row[4],
                'nationalcode': row[5]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': patients
        }), 200
        
    except Exception as e:
        print(f"[API PATIENTS BY LOCATION] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ===========================
# ENDPOINTS DE DETALLE DE PACIENTE
# ===========================

@api_blueprint.route('/patients/<guid>', methods=['GET'])
@jwt_required()
def get_patient(guid):
    """
    Obtener detalles completos de un paciente
    Verifica que el usuario tenga acceso al dominio del paciente
    """
    try:
        user_id = normalize_user_id(get_jwt_identity())
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener los dominios del usuario (fallback: todos si no tiene asignados)
        user_domains = get_user_patientdomain_ids(cursor, user_id)
        
        if not user_domains:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario sin acceso a dominios de pacientes'
            }), 403
        
        cursor.execute("""
            SELECT guid, name, surname, email, phone, nationalcode, birthdate, 
                   sexcode, patientid, healthcard, trial190, id_patientdomain, ismerged, isanonymous
            FROM nextris.datapatient
            WHERE guid = %s AND id_patientdomain = ANY(%s)
        """, (guid, user_domains))
        
        row = cursor.fetchone()
        
        if not row:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado o sin acceso'
            }), 404
        
        patient = {
            'guid': row[0],
            'name': row[1],
            'surname': row[2],
            'email': row[3],
            'phone': row[4],
            'nationalcode': row[5],
            'birthdate': row[6].isoformat() if row[6] else None,
            'gender': row[7],
            'patientid': row[8],
            'healthcard': row[9],
            'trial190': row[10],
            'id_patientdomain': row[11],
            'ismerged': row[12],
            'isanonymous': row[13]
        }
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': patient
        }), 200
        
    except Exception as e:
        print(f"[API PATIENT] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ===========================
# ENDPOINTS DE CREACIÓN DE PACIENTES
# ===========================

@api_blueprint.route('/patients', methods=['POST'])
@jwt_required()
@require_permission('patients.manage', include_role_permissions=True)
def create_patient():
    """
    Crear un nuevo paciente con todos los datos completos
    El PatientID se genera automáticamente con formato NR00000001, NR00000002, etc.
    
    Body JSON:
    {
        "name": "...",
        "surname": "...",
        "patientdomain_id": "uuid",
        "nationalcode": "...",
        "email": "...",
        "phone": "...",
        "birthdate": "YYYY-MM-DD",
        "gender": "M/F/O",
        "healthcard": "...",
        "create_user": true
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
        required_fields = ['name', 'surname', 'patientdomain_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'message': f'El campo {field} es requerido'
                }), 400
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Generar nuevo GUID
        patient_guid = str(uuid.uuid4())
        
        # Generar PatientID autoincremental con formato NR00000001
        cursor.execute("""
            SELECT patientid 
            FROM nextris.datapatient 
            WHERE patientid LIKE 'NR%' 
            ORDER BY patientid DESC 
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        
        if result and result[0]:
            # Extraer el número del último PatientID (NR00000005 -> 5)
            last_id = result[0]
            try:
                last_number = int(last_id[2:])  # Quitar "NR" y convertir a int
                new_number = last_number + 1
            except (ValueError, IndexError):
                new_number = 1
        else:
            new_number = 1
        
        # Formatear con 8 dígitos: NR00000001
        patient_id = f"NR{new_number:08d}"
        
        # Insertar paciente
        cursor.execute("""
            INSERT INTO nextris.datapatient 
            (guid, name, surname, patientid, nationalcode, email, phone, birthdate, sexcode, 
             healthcard, trial190, isanonymous, ismerged, id_patientdomain)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::bit, %s::bit, %s)
            RETURNING guid
        """, (
            patient_guid,
            data.get('name'),
            data.get('surname'),
            patient_id,
            data.get('nationalcode'),
            data.get('email'),
            data.get('phone'),
            data.get('birthdate'),
            data.get('gender', 'O'), 
            data.get('healthcard'),
            data.get('trial190'),
            1 if data.get('isanonymous', False) else 0,
            1 if data.get('ismerged', False) else 0,
            data.get('patientdomain_id')
        ))
        
        new_guid = cursor.fetchone()[0]
        
        # Crear usuario para el paciente si se solicita
        if data.get('create_user') and data.get('name') and data.get('surname'):
            try:
                nombre = data.get('name').strip()
                apellido = data.get('surname').strip()
                
                # Generar username
                base_username = (nombre[0] + apellido).lower().replace(' ', '')
                
                # Verificar si existe
                cursor.execute("""
                    SELECT username FROM nextris.tbuser_patient 
                    WHERE username LIKE %s 
                    ORDER BY username
                """, (f"{base_username}%",))
                
                existing_users = cursor.fetchall()
                username = base_username
                
                if existing_users:
                    counter = 1
                    while True:
                        test_username = f"{base_username}{counter:02d}"
                        if not any(user[0] == test_username for user in existing_users):
                            username = test_username
                            break
                        counter += 1
                
                # Crear usuario
                hashed_password = hash_pass('next')
                cursor.execute("""
                    INSERT INTO nextris.tbuser_patient (
                        guid, username, password, datapatient_id, status, firstlogin
                    ) VALUES (
                        uuid_generate_v4(), %s, %s, %s, 'Active', 1
                    )
                """, (username, hashed_password, new_guid))
                
                print(f"[DEBUG] Usuario '{username}' creado para paciente {new_guid}")
                
            except Exception as user_error:
                print(f"[ERROR] Error al crear usuario: {str(user_error)}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'guid': new_guid
            },
            'message': 'Paciente creado exitosamente'
        }), 201
        
    except Exception as e:
        print(f"[API CREATE PATIENT] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/patients/quick', methods=['POST'])
@jwt_required()
@require_permission('patients.manage', include_role_permissions=True)
def create_patient_quick():
    """
    Crear un paciente rápidamente con datos mínimos
    
    Body JSON:
    {
        "nombre": "...",
        "apellido": "...",
        "dni": "...",
        "fecha_nac": "YYYY-MM-DD",
        "sexo": "M/F/I"
    }
    """
    try:
        data = request.get_json()
        
        nombre = data.get('nombre', '')
        apellido = data.get('apellido', '')
        dni = data.get('dni', '')
        fecha_nac = data.get('fecha_nac', None)
        sexo = data.get('sexo', 'I')
        
        # Generar PatientId
        patient_id = dni if dni else str(uuid.uuid4())[:8]
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO nextris.datapatient (guid, patientid, surname, name, nationalcode, sexcode, birthdate)
            VALUES (uuid_generate_v4(), %s, %s, %s, %s, %s, %s)
            RETURNING guid
        """, (patient_id, apellido, nombre, dni, sexo, fecha_nac))
        
        guid = cursor.fetchone()[0]
        
        # Crear usuario automáticamente
        if guid and nombre and apellido:
            try:
                base_username = (nombre[0] + apellido).lower().strip()
                
                cursor.execute("""
                    SELECT username FROM nextris.tbuser_patient 
                    WHERE username LIKE %s 
                    ORDER BY username
                """, (f"{base_username}%",))
                
                existing_users = cursor.fetchall()
                username = base_username
                
                if existing_users:
                    counter = 1
                    while True:
                        test_username = f"{base_username}{counter:02d}"
                        if not any(user[0] == test_username for user in existing_users):
                            username = test_username
                            break
                        counter += 1
                
                hashed_password = hash_pass('next')
                
                cursor.execute("""
                    INSERT INTO nextris.tbuser_patient (
                        guid, username, password, datapatient_id, status, firstlogin
                    ) VALUES (
                        uuid_generate_v4(), %s, %s, %s, 'Active', 1
                    )
                """, (username, hashed_password, str(guid)))
                
                print(f"[DEBUG] Usuario '{username}' creado para paciente rápido {guid}")
                
            except Exception as user_error:
                print(f"[ERROR] Error al crear usuario: {str(user_error)}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Paciente agregado correctamente',
            'guid': str(guid)
        }), 201
        
    except Exception as e:
        print(f"[API CREATE PATIENT QUICK] Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ===========================
# CREAR USUARIO PARA PACIENTE EXISTENTE
# ===========================

@api_blueprint.route('/patients/<guid>/create-user', methods=['POST'])
@jwt_required()
@require_permission('patients.manage', include_role_permissions=True)
def create_user_for_patient(guid):
    """
    Crea un usuario en tbuser_patient para un paciente existente que no tiene usuario.
    """
    try:
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        # Verificar que el paciente existe
        cursor.execute("""
            SELECT guid, name, surname FROM nextris.datapatient WHERE guid = %s
        """, (guid,))
        patient = cursor.fetchone()
        if not patient:
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'Paciente no encontrado'}), 404

        # Verificar que no tiene usuario ya
        cursor.execute("""
            SELECT guid FROM nextris.tbuser_patient WHERE datapatient_id = %s
        """, (guid,))
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({'success': False, 'message': 'El paciente ya tiene un usuario asignado'}), 409

        nombre = patient[1].strip()
        apellido = patient[2].strip()
        base_username = (nombre[0] + apellido).lower().replace(' ', '')

        # Verificar colisión de username
        cursor.execute("""
            SELECT username FROM nextris.tbuser_patient WHERE username LIKE %s ORDER BY username
        """, (f"{base_username}%",))
        existing_users = cursor.fetchall()
        username = base_username
        if existing_users:
            counter = 1
            while True:
                test_username = f"{base_username}{counter:02d}"
                if not any(u[0] == test_username for u in existing_users):
                    username = test_username
                    break
                counter += 1

        hashed_password = hash_pass('next')
        cursor.execute("""
            INSERT INTO nextris.tbuser_patient (guid, username, password, datapatient_id, status, firstlogin)
            VALUES (uuid_generate_v4(), %s, %s, %s, 'Active', 1)
        """, (username, hashed_password, guid))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': f"Usuario '{username}' creado correctamente",
            'username': username
        }), 201

    except Exception as e:
        print(f"[API CREATE USER FOR PATIENT] Error: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# ===========================
# ENDPOINTS DE ACTUALIZACIÓN
# ===========================

@api_blueprint.route('/patients/<guid>', methods=['PUT'])
@jwt_required()
@require_permission('patients.manage', include_role_permissions=True)
def update_patient(guid):
    """
    Actualizar un paciente existente
    
    Body JSON: campos a actualizar
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Construir query dinámico
        update_fields = []
        values = []
        
        allowed_fields = {
            'name': 'name',
            'surname': 'surname',
            'patientid': 'patientid',
            'nationalcode': 'nationalcode',
            'email': 'email',
            'phone': 'phone',
            'birthdate': 'birthdate',
            'gender': 'sexcode',
            'healthcard': 'healthcard',
            'trial190': 'trial190',
            'isanonymous': 'isanonymous',
            'ismerged': 'ismerged'
        }
        
        for json_field, db_field in allowed_fields.items():
            if json_field in data:
                # Convertir booleanos a bit para isanonymous e ismerged
                if json_field in ['isanonymous', 'ismerged']:
                    update_fields.append(f"{db_field} = %s::bit")
                    values.append(1 if data[json_field] else 0)
                else:
                    update_fields.append(f"{db_field} = %s")
                    values.append(data[json_field])
        
        if not update_fields:
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        values.append(guid)
        query = f"UPDATE nextris.datapatient SET {', '.join(update_fields)} WHERE guid = %s"
        
        cursor.execute(query, values)
        connection.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Paciente actualizado exitosamente'
        }), 200
        
    except Exception as e:
        print(f"[API UPDATE PATIENT] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/patients/<guid>/email', methods=['PATCH'])
@jwt_required()
@require_permission('patients.manage', include_role_permissions=True)
def update_patient_email(guid):
    """
    Actualizar solo el email de un paciente
    
    Body JSON:
    {
        "email": "..."
    }
    """
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({
                'success': False,
                'message': 'Email requerido'
            }), 400
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        cursor.execute("""
            UPDATE nextris.datapatient
            SET email = %s
            WHERE guid = %s
        """, (email, guid))
        
        connection.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Email actualizado exitosamente'
        }), 200
        
    except Exception as e:
        print(f"[API UPDATE EMAIL] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ===========================
# ENDPOINTS DE ELIMINACIÓN Y UNIFICACIÓN
# ===========================

@api_blueprint.route('/patients/<guid>', methods=['DELETE'])
@jwt_required()
@require_permission('patients.manage', include_role_permissions=True)
def delete_patient(guid):
    """
    Eliminar un paciente
    Solo se permite si no tiene estudios asociados
    """
    try:
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener patientid
        cursor.execute("SELECT patientid FROM nextris.datapatient WHERE guid = %s", (guid,))
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        patient_id = result[0]
        
        # Verificar que no tenga estudios
        cursor.execute("SELECT COUNT(*) FROM nextris.tbexamination WHERE idpatient = %s", (patient_id,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No se puede eliminar el paciente porque tiene estudios asociados'
            }), 400
        
        # Eliminar paciente
        cursor.execute("DELETE FROM nextris.datapatient WHERE guid = %s", (guid,))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Paciente eliminado correctamente'
        }), 200
        
    except Exception as e:
        print(f"[API DELETE PATIENT] Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_blueprint.route('/patients/merge', methods=['POST'])
@jwt_required()
@require_permission('patients.manage', include_role_permissions=True)
def merge_patients():
    """
    Unificar/fusionar pacientes duplicados
    
    Body JSON:
    {
        "master_guid": "...",
        "duplicate_guid": "..."
    }
    """
    try:
        data = request.get_json()
        
        master_guid = data.get('master_guid') or data.get('id_correcto')
        duplicate_guid = data.get('duplicate_guid') or data.get('id_eliminar')
        
        if not master_guid or not duplicate_guid:
            return jsonify({
                'success': False,
                'message': 'Se requieren los GUIDs de ambos pacientes'
            }), 400
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener PatientIds
        cursor.execute("SELECT patientid FROM nextris.datapatient WHERE guid = %s", (master_guid,))
        master_result = cursor.fetchone()
        
        if not master_result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No se encontró el paciente maestro'
            }), 400
        
        master_id = master_result[0]
        
        cursor.execute("SELECT patientid FROM nextris.datapatient WHERE guid = %s", (duplicate_guid,))
        duplicate_result = cursor.fetchone()
        
        if not duplicate_result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No se encontró el paciente duplicado'
            }), 400
        
        duplicate_id = duplicate_result[0]
        
        # Actualizar referencias
        cursor.execute("UPDATE nextris.tbexamination SET idpatient = %s WHERE idpatient = %s", 
                      (master_id, duplicate_id))
        
        cursor.execute("UPDATE nextris.tbreport SET idpatient = %s WHERE idpatient = %s", 
                      (master_id, duplicate_id))
        
        # Eliminar paciente duplicado
        cursor.execute("DELETE FROM nextris.datapatient WHERE guid = %s", (duplicate_guid,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Pacientes unificados correctamente'
        }), 200
        
    except Exception as e:
        print(f"[API MERGE PATIENTS] Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ===========================
# ENDPOINTS DE HISTORIAL Y ESTUDIOS
# ===========================

@api_blueprint.route('/patients/<guid>/history', methods=['GET'])
@jwt_required()
def get_patient_history(guid):
    """
    Obtener el historial de estudios de un paciente
    """
    try:
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        query = """
            SELECT
                ex.guid,
                st.description AS estudio,
                ex.createdon,
                ex.localacc,
                ex.isreported,
                CONCAT(us_reporter.name,' ',us_reporter.surname) as medico_autor,
                ex.isimage,
                mod.externalcode as modality,
                CONCAT(us_referring.name,' ',us_referring.surname) as medico_referente,
                rep.pdfpath,
                loc.name as ubicacion
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.isstudytype st ON ex.studytype_id = st.guid
            LEFT JOIN nextris.datapatient data on data.guid=ex.idpatient
            LEFT JOIN nextris.tbreport rep on rep.idexamination=ex.guid
            LEFT JOIN nextris.tbuser us_reporter on us_reporter.guid=rep.idreporterphysician
            LEFT JOIN nextris.tbuser us_referring on us_referring.guid=rep.idreferringphysician
            LEFT JOIN nextris.ismodality mod on mod.guid=st.modality_id
            LEFT JOIN nextris.isequipment eq ON ex.IdEquipment = eq.Guid
            LEFT JOIN nextris.tblocation loc ON eq.location_id = loc.guid
            WHERE data.guid = %s
              AND ex.isreported = 1
              AND rep.pdfpath IS NOT NULL
            ORDER BY ex.createdon DESC
        """
        
        cursor.execute(query, (guid,))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'guid': row[0],
                'estudio': row[1] or 'Sin descripción',
                'medico_autor': row[5] or 'No asignado',
                'medico_referente': row[8] or 'No asignado',
                'fecha': row[2].strftime('%d/%m/%Y %H:%M') if row[2] else 'Sin fecha',
                'modalidad': row[7] or 'N/A',
                'con_imagen': 'Sí' if row[6] == 1 else 'No',
                'isreported': row[4],
                'pdf_path': row[9] or None,
                'ubicacion': row[10] or 'Sin ubicación'
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': history
        }), 200
        
    except Exception as e:
        print(f"[API PATIENT HISTORY] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_blueprint.route('/patients/<guid>/history/report', methods=['GET'])
@jwt_required()
def get_patient_history_for_report(guid):
    """
    Obtener historial resumido de un paciente para reportes
    Últimos 10 estudios reportados
    """
    try:
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT ex.guid, st.description AS estudio, ex.reportdate
            FROM nextris.tbexamination ex
            INNER JOIN nextris.isstudytype st ON ex.studytype_id = st.guid
            WHERE ex.idpatient = %s AND ex.isreported = 1
            ORDER BY ex.reportdate DESC
            LIMIT 10
        """, (guid,))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'guid': row[0],
                'estudio': row[1],
                'fecha': row[2].strftime('%d/%m/%Y') if row[2] else None
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': history
        }), 200
        
    except Exception as e:
        print(f"[API HISTORY FOR REPORT] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@api_blueprint.route('/patients/<guid>/studies/count', methods=['GET'])
@jwt_required()
def get_patient_studies_count(guid):
    """
    Obtener la cantidad de estudios de un paciente
    """
    try:
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener patientid
        cursor.execute("SELECT patientid FROM nextris.datapatient WHERE guid = %s", (guid,))
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 404
        
        patient_id = result[0]
        
        cursor.execute("""
            SELECT COUNT(*) as cantidad
            FROM nextris.tbexamination 
            WHERE idpatient = %s
        """, (patient_id,))
        
        cantidad = cursor.fetchone()[0]
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'cantidad': cantidad
            }
        }), 200
        
    except Exception as e:
        print(f"[API STUDIES COUNT] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ===========================
# ENDPOINTS DE ESTUDIOS Y REASIGNACIÓN
# ===========================

@api_blueprint.route('/studies/reassign/list', methods=['GET'])
@jwt_required()
def get_studies_to_reassign():
    """
    Obtener lista de estudios para reasignar
    """
    try:
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT ex.guid, ex.createdon, ex.localacc, pat.patientid, 
                   CONCAT(pat.surname, ' ', pat.name) as nombre, pat.birthdate, 
                   st.description as estudio, ex.status
            FROM nextris.tbexamination ex
            LEFT JOIN nextris.datapatient as pat on pat.patientid = ex.idpatient
            LEFT JOIN nextris.isstudytype as st on st.guid = ex.studytype_id
            ORDER BY ex.createdon ASC 
            LIMIT 100
        """)
        
        studies = []
        for row in cursor.fetchall():
            studies.append({
                'guid': row[0],
                'createdon': row[1].isoformat() if row[1] else None,
                'localacc': row[2],
                'patientid': row[3],
                'patient_name': row[4],
                'birthdate': row[5].isoformat() if row[5] else None,
                'study_description': row[6],
                'status': row[7]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': studies
        }), 200
        
    except Exception as e:
        print(f"[API STUDIES TO REASSIGN] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_blueprint.route('/studies/reassign', methods=['POST'])
@jwt_required()
def reassign_study():
    """
    Reasignar un estudio a otro paciente
    
    Body JSON:
    {
        "estudio_id": "...",
        "paciente_id": "..."
    }
    """
    try:
        data = request.get_json()
        estudio_id = data.get('estudio_id')
        paciente_guid = data.get('paciente_id')
        
        if not estudio_id or not paciente_guid:
            return jsonify({
                'success': False,
                'message': 'estudio_id y paciente_id son requeridos'
            }), 400
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener PatientId del GUID
        cursor.execute("SELECT patientid FROM nextris.datapatient WHERE guid = %s", (paciente_guid,))
        patient_result = cursor.fetchone()
        
        if not patient_result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Paciente no encontrado'
            }), 400
        
        patient_id = patient_result[0]
        
        # Verificar que el estudio existe
        cursor.execute("SELECT guid FROM nextris.tbexamination WHERE guid = %s", (estudio_id,))
        exam_result = cursor.fetchone()
        
        if not exam_result:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Estudio no encontrado'
            }), 400
        
        # Actualizar estudio
        cursor.execute("UPDATE nextris.tbexamination SET idpatient = %s WHERE guid = %s", 
                      (patient_id, estudio_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': f'Estudio reasignado correctamente al paciente {patient_id}'
        }), 200
        
    except Exception as e:
        print(f"[API REASSIGN STUDY] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_blueprint.route('/studies/<exam_id>/image-link', methods=['GET'])
@jwt_required()
def get_study_image_link(exam_id):
    """
    Obtener el enlace de imágenes de un estudio
    """
    try:
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT studyinstanceuid
            FROM nextris.tbexamination 
            WHERE guid = %s
        """, (exam_id,))
        
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if result and result[0]:
            return jsonify({
                'success': True,
                'data': {
                    'study_uid': result[0],
                    'has_images': 1
                }
            }), 200
        
        return jsonify({
            'success': True,
            'data': {
                'study_uid': '',
                'has_images': 0
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': True,
            'data': {
                'study_uid': '',
                'has_images': 0
            }
        }), 200


# ===========================
# ENDPOINTS DE UBICACIONES
# ===========================

@api_blueprint.route('/user/locations', methods=['GET'])
@jwt_required()
def get_user_locations():
    """
    Obtener las ubicaciones del usuario autenticado
    """
    try:
        user_id = normalize_user_id(get_jwt_identity())
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT 
                loc.guid,
                loc.name,
                loc.code,
                loc.facility_id,
                rul.is_default
            FROM nextris.tblocation loc
            INNER JOIN nextris.rel_user_location rul 
                ON loc.guid = rul.location_id
            WHERE rul.user_id = %s
            AND loc.status = 'Active'
            ORDER BY rul.is_default DESC, loc.name
        """, (user_id,))
        
        locations = []
        for row in cursor.fetchall():
            locations.append({
                'guid': row[0],
                'name': row[1],
                'code': row[2],
                'facility_id': row[3],
                'is_default': row[4]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': locations
        }), 200
        
    except Exception as e:
        print(f"[API USER LOCATIONS] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@api_blueprint.route('/patients/reassign/list', methods=['GET'])
@jwt_required()
def get_patients_to_reassign():
    """
    Obtener lista de pacientes disponibles para reasignación
    """
    try:
        user_id = normalize_user_id(get_jwt_identity())
        
        db_config = get_db_config()
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT dp.guid, dp.name, dp.surname, dp.nationalcode, dp.sexcode, 
                   dp.birthdate, dp.phone, dp.email, dp.healthcard 
            FROM nextris.datapatient dp
            INNER JOIN nextris.rel_user_patientdomain rup 
                ON dp.id_patientdomain = rup.patientdomain_id
            WHERE rup.user_id = %s
            ORDER BY dp.surname, dp.name
        """, (user_id,))
        
        patients = []
        for row in cursor.fetchall():
            patients.append({
                'guid': row[0],
                'name': row[1],
                'surname': row[2],
                'nationalcode': row[3],
                'gender': row[4],
                'birthdate': row[5].isoformat() if row[5] else None,
                'phone': row[6],
                'email': row[7],
                'healthcard': row[8]
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': patients
        }), 200
        
    except Exception as e:
        print(f"[API PATIENTS TO REASSIGN] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
