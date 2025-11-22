"""
Controlador de configuración para el sistema RIS
Maneja rutas relacionadas con configuración del sistema
"""

import os
from flask import Blueprint, jsonify, request, current_app
from apps.home.services import ConfigService, DatabaseService
from apps.authentication.util import require_role, hash_pass
from apps.authentication.models import Users
from apps import db
import uuid
from PIL import Image

# Crear blueprint específico para configuración
config_bp = Blueprint('config', __name__, url_prefix='')

@config_bp.route('/test_endpoint', methods=['GET'])
def test_endpoint():
    """Endpoint de prueba para verificar que el controlador funciona"""
    return jsonify({'status': 'OK', 'message': 'Config controller is working!'})


@config_bp.route('/get_backend_config', methods=['GET'])
@require_role('Sysadmin')
def get_backend_config():
    """Endpoint para obtener la configuración actual - Solo Sysadmin"""
    return jsonify(ConfigService.get_all_config())


@config_bp.route('/update_backend_config', methods=['POST'])
@require_role('Sysadmin')
def update_config():
    """Endpoint para actualizar la configuración y persistir en .env - Solo Sysadmin"""
    data = request.get_json()
    
    try:
        updated_config = ConfigService.update_config(data)
        return jsonify(updated_config), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_config_workflow', methods=['GET'])
def get_config_workflow():
    """Endpoint para obtener la configuración de workflow"""
    try:
        print("[DEBUG] get_config_workflow called")
        
        query = """
            SELECT agenda_tipo, agenda_estudios
            FROM nextris.config_workflow
            ORDER BY fecha_actualizacion DESC
            LIMIT 1
        """
        
        result = DatabaseService.execute_query(query)
        
        if result:
            response = {
                'agenda_tipo': result[0][0], 
                'agenda_estudios': result[0][1]
            }
            print(f"[DEBUG] Config workflow found: {response}")
            return jsonify(response)
        else:
            response = {
                'agenda_tipo': None, 
                'agenda_estudios': None
            }
            print("[DEBUG] No config workflow found, returning defaults")
            return jsonify(response)
            
    except Exception as e:
        print(f"[ERROR] Error getting config_workflow: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Funciones básicas de configuración solamente


# ====================================================================
# ENDPOINTS PARA CONFIGURACIONES DEL SISTEMA
# ====================================================================

@config_bp.route('/get_origins_group', methods=['GET'])
def get_origins_group():
    """Obtiene grupos de origen para configuraciones"""
    try:
        query = "SELECT guid, description, isexternal, iser, delaydays FROM nextris.IsProvenanceGroup"
        result = DatabaseService.execute_query(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_origins', methods=['GET'])
def get_origins():
    """Obtiene orígenes para configuraciones"""
    try:
        query = """SELECT o.Guid, o.Description, g.Description AS groupo, o.IsActive, o.ExternalCode
               FROM nextris.IsProvenance o 
               JOIN nextris.IsProvenanceGroup g ON o.IdProvenanceGroup = g.Guid"""
        result = DatabaseService.execute_query(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_study_types', methods=['GET'])
def get_study_types():
    """Obtiene tipos de estudio para configuraciones"""
    try:
        query = """SELECT st.guid,st.code,st.description, stg.description as studygroup, ap.description as bodypart, md.externalcode as modality, st.rvu, st.nofviews
                FROM nextris.isstudytype as st
                INNER JOIN nextris.isstudytypegroup stg on stg.guid=st.studygroup_id
                INNER JOIN nextris.isanatomicalpart ap on ap.guid=st.bodypart_id
                INNER JOIN nextris.ismodality md on md.guid=st.modality_id
                ORDER BY guid ASC"""
        result = DatabaseService.execute_query(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@config_bp.route('/get_user_patients', methods=['GET'])
def get_user_patients():
    """Obtiene pacientes para configuraciones"""
    try:
        query = """SELECT p.guid, CONCAT(dp.surname, ' ', dp.name) as name,dp.nationalcode, dp.birthdate,p.username, p.status, p.lastlogin
                FROM nextris.tbuser_patient as p
				LEFT JOIN nextris.datapatient dp on dp.guid=p.datapatient_id
                ORDER BY guid ASC"""
        result = DatabaseService.execute_query(query)
        
        # Formatear las fechas de nacimiento
        formatted_result = []
        for row in result:
            formatted_row = list(row)
            # Formatear la fecha de nacimiento (índice 3) si existe
            if formatted_row[3]:
                formatted_row[3] = formatted_row[3].strftime('%d/%m/%Y')
            formatted_result.append(formatted_row)
        
        return jsonify(formatted_result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/agregar_studytype', methods=['POST'])
def agregar_studytype():
    """Agregar un nuevo tipo de estudio"""
    try:
        respuesta = request.form.to_dict()
        print(f"[DEBUG] Datos recibidos: {respuesta}")
        
        # Validar que se reciban todos los campos requeridos
        required_fields = ['ministerial_code', 'Description_code', 'group_code', 'bodypart_code', 'modality_code']
        for field in required_fields:
            if field not in respuesta or not respuesta[field]:
                return jsonify({'error': f'Campo requerido faltante: {field}'}), 400
        
        # Obtener valores opcionales
        rvu = respuesta.get('rvu_code', None)
        nofviews = respuesta.get('nofviews_code', None)
        
        # Convertir a None si están vacíos
        if rvu == '':
            rvu = None
        if nofviews == '':
            nofviews = None
        
        # Insertar el nuevo tipo de estudio
        query = """
            INSERT INTO nextris.isstudytype(guid, code, description, studygroup_id, bodypart_id, modality_id, rvu, nofviews) 
            VALUES (uuid_generate_v4(), %s, %s, %s, %s, %s, %s, %s)
            RETURNING guid, code, description
        """
        
        result = DatabaseService.execute_query(
            query, 
            (
                respuesta['ministerial_code'], 
                respuesta['Description_code'], 
                respuesta['group_code'],
                respuesta['bodypart_code'],
                respuesta['modality_code'],
                rvu,
                nofviews
            ),
            commit=True,
            fetch_all=True
        )
        
        if result and len(result) > 0:
            # Obtener los nombres descriptivos de los datos relacionados
            query_details = """
                SELECT st.code, st.description, stg.description as studygroup, 
                       ap.description as bodypart, md.externalcode as modality,
                       st.rvu, st.nofviews
                FROM nextris.isstudytype st
                INNER JOIN nextris.isstudytypegroup stg on stg.guid=st.studygroup_id
                INNER JOIN nextris.isanatomicalpart ap on ap.guid=st.bodypart_id
                INNER JOIN nextris.ismodality md on md.guid=st.modality_id
                WHERE st.guid = %s
            """
            details = DatabaseService.execute_query(query_details, (result[0][0],), fetch_one=True)
            
            response_data = {
                'status': 'OK', 
                'message': 'Tipo de estudio creado exitosamente',
                'data': list(details) if details else list(result[0])
            }
            return jsonify(response_data)
        else:
            return jsonify({'error': 'No se pudo crear el tipo de estudio'}), 500
            
    except Exception as e:
        print(f"[ERROR] Error al agregar tipo de estudio: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/actualizar_studytype', methods=['POST'])
def actualizar_studytype():
    """Actualizar un tipo de estudio existente"""
    try:
        respuesta = request.form.to_dict()
        print(f"[DEBUG] Datos recibidos para actualizar: {respuesta}")
        
        # Validar que se reciba el ID
        if 'id_code' not in respuesta:
            return jsonify({'error': 'ID del tipo de estudio requerido'}), 400
        
        # Obtener valores opcionales
        rvu = respuesta.get('rvu_code', None)
        nofviews = respuesta.get('nofviews_code', None)
        
        # Convertir a None si están vacíos
        if rvu == '':
            rvu = None
        if nofviews == '':
            nofviews = None
            
        # Actualizar el tipo de estudio
        query = """
            UPDATE nextris.isstudytype 
            SET code = %s, 
                description = %s, 
                studygroup_id = %s,
                bodypart_id = %s,
                modality_id = %s,
                rvu = %s,
                nofviews = %s
            WHERE guid = %s
        """
        
        DatabaseService.execute_query(
            query, 
            (
                respuesta['ministerial_code'], 
                respuesta['Description_code'], 
                respuesta['group_code'],
                respuesta['bodypart_code'],
                respuesta['modality_code'],
                rvu,
                nofviews,
                respuesta['id_code']
            ),
            commit=True
        )
        
        # Obtener los datos actualizados con las descripciones
        query_details = """
            SELECT st.code, st.description, stg.description as studygroup, 
                   ap.description as bodypart, md.externalcode as modality,
                   st.rvu, st.nofviews
            FROM nextris.isstudytype st
            INNER JOIN nextris.isstudytypegroup stg on stg.guid=st.studygroup_id
            INNER JOIN nextris.isanatomicalpart ap on ap.guid=st.bodypart_id
            INNER JOIN nextris.ismodality md on md.guid=st.modality_id
            WHERE st.guid = %s
        """
        details = DatabaseService.execute_query(query_details, (respuesta['id_code'],), fetch_one=True)
        
        response_data = {
            'status': 'OK', 
            'message': 'Tipo de estudio actualizado exitosamente',
            'data': list(details) if details else []
        }
        return jsonify(response_data)
            
    except Exception as e:
        print(f"[ERROR] Error al actualizar tipo de estudio: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/eliminar_studytype', methods=['POST'])
def eliminar_studytype():
    """Eliminar un tipo de estudio"""
    try:
        data = request.json
        study_id = data.get('id')
        
        if not study_id:
            return jsonify({'error': 'ID del tipo de estudio requerido'}), 400
        
        # Eliminar el tipo de estudio
        query = "DELETE FROM nextris.isstudytype WHERE guid = %s"
        DatabaseService.execute_query(query, (study_id,), commit=True)
        
        return jsonify({'status': 'OK', 'message': 'Tipo de estudio eliminado exitosamente'})
            
    except Exception as e:
        print(f"[ERROR] Error al eliminar tipo de estudio: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_users_config', methods=['GET']) 
@require_role('Sysadmin')
def get_users_config():
    """Obtener usuarios para configuración - Solo Sysadmin"""
    # Parámetro opcional para incluir usuarios desactivados
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    
    if include_inactive:
        # Mostrar todos los usuarios (activos e inactivos)
        query = """SELECT u.guid,u.username,r.description,u.name,u.surname,u.nationalnumber,u.mail,u.isactive 
                   FROM nextris.tbuser u
                   INNER JOIN nextris.isrole r ON r.guid=u.idrole
                   ORDER BY u.isactive DESC, u.username"""
    else:
        # Mostrar solo usuarios activos (por defecto)
        query = """SELECT u.guid,u.username,r.description,u.name,u.surname,u.nationalnumber,u.mail,u.isactive 
                   FROM nextris.tbuser u
                   INNER JOIN nextris.isrole r ON r.guid=u.idrole
                   WHERE u.isactive = 1
                   ORDER BY u.username"""
    
    result = DatabaseService.execute_query(query)
    return jsonify(result)


@config_bp.route('/get_modalities', methods=['GET'])
def get_modalities():
    """Obtiene modalidades para configuraciones"""
    try:
        query = "SELECT * FROM nextris.IsModality;"
        result = DatabaseService.execute_query(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_body_parts', methods=['GET'])
def get_body_parts():
    """Obtiene partes del cuerpo para configuraciones"""
    try:
        query = "SELECT guid,description FROM nextris.IsAnatomicalPart;"
        result = DatabaseService.execute_query(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_exams', methods=['GET'])
def get_exams():
    """Obtiene exámenes para configuraciones"""
    try:
        query = """
            SELECT guid, description, duration, price, isactive 
            FROM nextris.isstudytype 
            ORDER BY description
        """
        result = DatabaseService.execute_query(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_mach', methods=['GET'])
def get_mach():
    """Obtiene equipos (máquinas) para configuraciones"""
    try:
        query = """
            SELECT equip.guid, equip.description, equip.aetitle, equip.externalcode, m.description as modality, 
                   equip.ip, equip.brandequipment, equip.modelequipment, equip.snequipment, equip.isactive
            FROM nextris.isequipment equip
            INNER JOIN nextris.ismodality m ON m.guid = equip.idmodality
            ORDER BY equip.description
        """
        result = DatabaseService.execute_query(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_facilities', methods=['GET'])
def get_facilities():
    """Obtiene facilities para configuraciones"""
    try:
        query = """
            SELECT guid, name, code, email, contact_person, status
            FROM nextris.tbfacility
            ORDER BY name
        """
        result = DatabaseService.execute_query(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/agregar_facility', methods=['POST'])
def agregar_facility():
    """Agrega una nueva facility"""
    try:
        # Obtener datos del formulario
        name = request.form.get('name_facility')
        code = request.form.get('code_facility')
        email = request.form.get('email_facility')
        contact_person = request.form.get('contact_person_facility')
        description = request.form.get('description_facility')
        address = request.form.get('address_facility')
        city = request.form.get('city_facility')
        country = request.form.get('country_facility')
        phone = request.form.get('phone_facility')
        status = request.form.get('status_facility', 'Active')
        
        # Generar GUID
        guid = str(uuid.uuid4())
        
        # Insertar en la base de datos
        query = """
            INSERT INTO nextris.tbfacility 
            (guid, name, code, email, contact_person, description, address, city, country, phone, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (guid, name, code, email, contact_person, description, address, city, country, phone, status)
        DatabaseService.execute_query(query, params, commit=True)
        
        # Retornar los datos para agregar a la tabla
        return jsonify({
            'status': 'OK',
            'message': 'Facility agregada correctamente',
            'data': {
                'name': name,
                'code': code,
                'email': email,
                'contact_person': contact_person,
                'status': status
            }
        })
    except Exception as e:
        print(f"[ERROR] agregar_facility: {str(e)}")
        return jsonify({'status': 'ERROR', 'error': str(e)}), 500


@config_bp.route('/actualizar_facility', methods=['POST'])
def actualizar_facility():
    """Actualiza una facility existente"""
    try:
        # Obtener datos del formulario
        guid = request.form.get('id_facility')
        name = request.form.get('name_facility')
        code = request.form.get('code_facility')
        email = request.form.get('email_facility')
        contact_person = request.form.get('contact_person_facility')
        description = request.form.get('description_facility')
        address = request.form.get('address_facility')
        city = request.form.get('city_facility')
        country = request.form.get('country_facility')
        phone = request.form.get('phone_facility')
        status = request.form.get('status_facility', 'Active')
        
        # Actualizar en la base de datos
        query = """
            UPDATE nextris.tbfacility 
            SET name=%s, code=%s, email=%s, contact_person=%s, description=%s, 
                address=%s, city=%s, country=%s, phone=%s, status=%s
            WHERE guid=%s
        """
        params = (name, code, email, contact_person, description, address, city, country, phone, status, guid)
        DatabaseService.execute_query(query, params, commit=True)
        
        return jsonify({
            'status': 'OK',
            'message': 'Facility actualizada correctamente',
            'data': {
                'name': name,
                'code': code,
                'email': email,
                'contact_person': contact_person,
                'status': status
            }
        })
    except Exception as e:
        print(f"[ERROR] actualizar_facility: {str(e)}")
        return jsonify({'status': 'ERROR', 'error': str(e)}), 500


@config_bp.route('/eliminar_facility', methods=['POST'])
def eliminar_facility():
    """Elimina una facility"""
    try:
        data = request.get_json()
        guid = data.get('id')
        
        query = "DELETE FROM nextris.tbfacility WHERE guid=%s"
        DatabaseService.execute_query(query, (guid,), commit=True)
        
        return jsonify({
            'status': 'OK',
            'message': 'Facility eliminada correctamente'
        })
    except Exception as e:
        print(f"[ERROR] eliminar_facility: {str(e)}")
        return jsonify({'status': 'ERROR', 'error': str(e)}), 500


@config_bp.route('/get_locations', methods=['GET'])
def get_locations():
    """Obtiene locations con información de facility y patientdomain"""
    try:
        query = """
            SELECT l.guid, l.name, l.code, f.name as facility_name, pd.description as patientdomain_desc, 
                   l.mail, l.address, l.phone, 
                   CASE WHEN l.logo_path IS NOT NULL AND l.logo_path != '' THEN '✔' ELSE '' END as has_logo
            FROM nextris.tblocation l
            LEFT JOIN nextris.tbfacility f ON f.guid = l.facility_id
            LEFT JOIN nextris.ispatientdomain pd ON pd.guid = l.id_patientdomain
            ORDER BY l.name
        """
        result = DatabaseService.execute_query(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_location_data', methods=['GET'])
def get_location_data():
    """Obtiene datos completos de una location específica incluyendo facility_id"""
    try:
        location_id = request.args.get('location_id')
        query = """
            SELECT l.guid, l.name, l.code, l.facility_id, f.name as facility_name, 
                   l.id_patientdomain, l.mail, l.address, l.phone, l.status, l.logo_path
            FROM nextris.tblocation l
            LEFT JOIN nextris.tbfacility f ON f.guid = l.facility_id
            WHERE l.guid = %s
        """
        result = DatabaseService.execute_query(query, (location_id,))
        
        if result and len(result) > 0:
            row = result[0]
            return jsonify({
                'guid': row[0],
                'name': row[1],
                'code': row[2],
                'facility_id': row[3],
                'facility_name': row[4],
                'patientdomain': row[5],
                'mail': row[6],
                'address': row[7],
                'phone': row[8],
                'status': row[9],
                'logo_path': row[10]
            })
        else:
            return jsonify({'error': 'Location no encontrada'}), 404
            
    except Exception as e:
        print(f"[ERROR] get_location_data: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/agregar_location', methods=['POST'])
def agregar_location():
    """Agrega una nueva location"""
    try:
        # Obtener datos del formulario
        name = request.form.get('name_location')
        code = request.form.get('code_location')
        facility_id = request.form.get('facility_location')
        patientdomain = request.form.get('patientdomain_location')
        description = request.form.get('description_location')
        address = request.form.get('address_location')
        phone = request.form.get('phone_location')
        status = request.form.get('status_location', 'Active')
        
        # Generar GUID
        guid = str(uuid.uuid4())
        
        email = request.form.get('email_location')
        
        # Insertar en la base de datos
        query = """
            INSERT INTO nextris.tblocation 
            (guid, name, code, facility_id, id_patientdomain, mail, address, phone, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (guid, name, code, facility_id, patientdomain, email, address, phone, status)
        DatabaseService.execute_query(query, params, commit=True)
        
        # Obtener el nombre de la facility para retornar
        facility_query = "SELECT name FROM nextris.tbfacility WHERE guid=%s"
        facility_result = DatabaseService.execute_query(facility_query, (facility_id,))
        facility_name = facility_result[0][0] if facility_result else ''
        
        # Retornar los datos para agregar a la tabla
        return jsonify({
            'status': 'OK',
            'message': 'Location agregada correctamente',
            'data': {
                'name': name,
                'code': code,
                'facility_name': facility_name,
                'patientdomain': patientdomain,
                'mail': email,
                'address': address,
                'phone': phone
            }
        })
    except Exception as e:
        print(f"[ERROR] agregar_location: {str(e)}")
        return jsonify({'status': 'ERROR', 'error': str(e)}), 500


@config_bp.route('/actualizar_location', methods=['POST'])
def actualizar_location():
    """Actualiza una location existente"""
    try:
        # Obtener datos del formulario
        guid = request.form.get('id_location')
        name = request.form.get('name_location')
        code = request.form.get('code_location')
        facility_id = request.form.get('facility_location')
        patientdomain = request.form.get('patientdomain_location')
        description = request.form.get('description_location')
        address = request.form.get('address_location')
        phone = request.form.get('phone_location')
        status = request.form.get('status_location', 'Active')
        
        email = request.form.get('email_location')
        
        # Actualizar en la base de datos
        query = """
            UPDATE nextris.tblocation 
            SET name=%s, code=%s, facility_id=%s, id_patientdomain=%s, 
                mail=%s, address=%s, phone=%s, status=%s
            WHERE guid=%s
        """
        params = (name, code, facility_id, patientdomain, email, address, phone, status, guid)
        DatabaseService.execute_query(query, params, commit=True)
        
        # Obtener el nombre de la facility para retornar
        facility_query = "SELECT name FROM nextris.tbfacility WHERE guid=%s"
        facility_result = DatabaseService.execute_query(facility_query, (facility_id,))
        facility_name = facility_result[0][0] if facility_result else ''
        
        return jsonify({
            'status': 'OK',
            'message': 'Location actualizada correctamente',
            'data': {
                'name': name,
                'code': code,
                'facility_name': facility_name,
                'patientdomain': patientdomain,
                'mail': email,
                'address': address,
                'phone': phone
            }
        })
    except Exception as e:
        print(f"[ERROR] actualizar_location: {str(e)}")
        return jsonify({'status': 'ERROR', 'error': str(e)}), 500


@config_bp.route('/eliminar_location', methods=['POST'])
def eliminar_location():
    """Elimina una location"""
    try:
        data = request.get_json()
        guid = data.get('id')
        
        query = "DELETE FROM nextris.tblocation WHERE guid=%s"
        DatabaseService.execute_query(query, (guid,), commit=True)
        
        return jsonify({
            'status': 'OK',
            'message': 'Location eliminada correctamente'
        })
    except Exception as e:
        print(f"[ERROR] eliminar_location: {str(e)}")
        return jsonify({'status': 'ERROR', 'error': str(e)}), 500


@config_bp.route('/actualizar_logo_location', methods=['POST'])
def actualizar_logo_location():
    """Actualiza o elimina el logo de una location"""
    try:
        location_id = request.form.get('location_id')
        remove_logo = request.form.get('remove_logo') == 'on'
        logo_file = request.files.get('logo_file')
        
        # Obtener la location actual para saber si tiene logo
        query = "SELECT logo_path FROM nextris.tblocation WHERE guid=%s"
        result = DatabaseService.execute_query(query, (location_id,))
        
        if not result or len(result) == 0:
            return jsonify({'status': 'ERROR', 'error': 'Location no encontrada'}), 404
        
        old_logo_path = result[0][0]
        new_logo_path = None
        
        # Si se marca eliminar logo
        if remove_logo:
            # Eliminar archivo físico si existe
            if old_logo_path:
                try:
                    full_path = os.path.join(current_app.root_path, '..', old_logo_path.lstrip('/'))
                    if os.path.exists(full_path):
                        os.remove(full_path)
                except Exception as e:
                    print(f"[WARN] No se pudo eliminar logo anterior: {e}")
            
            new_logo_path = None
        
        # Si se sube un nuevo logo
        elif logo_file and logo_file.filename:
            # Procesar logo usando la misma lógica que institucional
            new_logo_path = _process_location_logo(logo_file, location_id)
            
            if not new_logo_path:
                return jsonify({'status': 'ERROR', 'error': 'Error al procesar el logo'}), 500
            
            # Eliminar logo anterior si existe
            if old_logo_path and old_logo_path != new_logo_path:
                try:
                    old_full_path = os.path.join(current_app.root_path, '..', old_logo_path.lstrip('/'))
                    if os.path.exists(old_full_path):
                        os.remove(old_full_path)
                except Exception as e:
                    print(f"[WARN] No se pudo eliminar logo anterior: {e}")
        
        else:
            # No hay cambios en el logo
            new_logo_path = old_logo_path
        
        # Actualizar en la base de datos
        update_query = "UPDATE nextris.tblocation SET logo_path=%s WHERE guid=%s"
        DatabaseService.execute_query(update_query, (new_logo_path, location_id), commit=True)
        
        return jsonify({
            'status': 'OK',
            'message': 'Logo actualizado correctamente',
            'logo_path': new_logo_path
        })
        
    except Exception as e:
        print(f"[ERROR] actualizar_logo_location: {str(e)}")
        return jsonify({'status': 'ERROR', 'error': str(e)}), 500


def _process_location_logo(logo_file, location_id):
    """
    Procesa y guarda el logo de location
    Redimensiona a 100x100px y maneja diferentes formatos
    
    Args:
        logo_file: Archivo de imagen desde request.files
        location_id: GUID de la location
        
    Returns:
        str: Ruta del archivo guardado o None si hay error
    """
    try:
        # 📁 Configurar directorios
        ext = os.path.splitext(logo_file.filename)[1]
        logo_filename = f"logo_location_{location_id[:8]}{ext}"
        logo_dir = os.path.join('apps', 'static', 'assets', 'img', 'locations')
        os.makedirs(logo_dir, exist_ok=True)
        logo_full_path = os.path.join(logo_dir, logo_filename)
        
        # 🖼️ Procesar imagen
        img = Image.open(logo_file)
        
        # Convertir a RGBA para manipulación
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
            
        # Redimensionar manteniendo aspecto a 100x100px
        size = (100, 100)
        new_img = Image.new('RGBA', size, (255, 255, 255, 0))
        ratio = min(size[0] / img.width, size[1] / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        # Usar LANCZOS compatible con versiones antiguas y nuevas de Pillow
        try:
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        except AttributeError:
            img = img.resize(new_size, Image.LANCZOS)
        
        # Centrar imagen
        paste_pos = ((size[0] - new_size[0]) // 2, (size[1] - new_size[1]) // 2)
        new_img.paste(img, paste_pos)
        
        # 💾 Guardar según formato
        if ext.lower() in ['.jpg', '.jpeg']:
            # Para JPG, convertir a RGB con fondo blanco
            rgb_img = Image.new('RGB', size, (255, 255, 255))
            rgb_img.paste(new_img, mask=new_img.split()[3])
            rgb_img.save(logo_full_path, quality=95)
        else:
            # Para PNG mantener transparencia
            new_img.save(logo_full_path)
        
        # 🔄 Normalizar ruta para BD
        logo_path = logo_full_path.replace('\\', '/').replace('d:/', '/').replace('D:/', '/')
        return logo_path
        
    except Exception as e:
        print(f"Error procesando logo de location: {e}")
        return None


@config_bp.route('/get_equip_agenda', methods=['GET'])
def get_equip_agenda():
    """Obtiene equipos para agenda"""
    try:
        query = """
            SELECT equip.guid, equip.aetitle, m.description as modality, 
                   equip.ip
            FROM nextris.isequipment equip
            INNER JOIN nextris.ismodality m ON m.guid = equip.idmodality
            ORDER BY equip.guid ASC
        """
        result = DatabaseService.execute_query(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_med_sol', methods=['GET'])
def get_med_sol():
    """Obtiene médicos solicitantes"""
    try:
        query = """
            SELECT guid, description, phone, mail, note 
            FROM nextris.isrequestingphysician
            ORDER BY description
        """
        result = DatabaseService.execute_query(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_agenda_med', methods=['GET'])
def get_agenda_med():
    """Obtiene médicos para agenda"""
    try:
        query = """
            SELECT guid, username, name,surname, nationalnumber 
            FROM nextris.tbuser
            WHERE idrole = (SELECT guid FROM nextris.isrole WHERE description = 'Medico')
        """
        result = DatabaseService.execute_query(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_days_agenda_equip', methods=['POST'])
def get_days_agenda_equip():
    """Obtiene agenda de días para un equipo específico"""
    try:
        data = request.get_json()
        id_equip = data.get('id')
        
        if not id_equip:
            return jsonify({'error': 'ID de equipo requerido'}), 400
            
        query = """
            SELECT guid, day, timefrom, timeto
            FROM nextris.isagendaequip 
            WHERE idequipment = %s
        """
        result = DatabaseService.execute_query(query, (id_equip,))
        
        # Formatear las fechas y horas para JSON
        formatted_result = []
        for row in result:
            formatted_row = {
                'guid': row[0],
                'day': row[1],
                'timefrom': row[2].strftime('%H:%M') if row[2] else '',
                'timeto': row[3].strftime('%H:%M') if row[3] else ''
            }
            formatted_result.append(formatted_row)
        
        return jsonify(formatted_result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_equipment_studygroup', methods=['POST'])
def get_equipment_studygroup():
    """Obtiene grupos de estudios asociados a un equipo específico"""
    try:
        data = request.get_json()
        id_equip = data.get('id')
        
        if not id_equip:
            return jsonify({'error': 'ID de equipo requerido'}), 400
            
        query = """
            SELECT g.guid, g.description
            FROM nextris.isstudytypegroup g
            WHERE g.guid IN (
                SELECT studygroup_id FROM nextris.rel_equipment_studygroup WHERE equip_id = %s
            )
            ORDER BY g.description ASC
        """
        result = DatabaseService.execute_query(query, (id_equip,))
        
        # Formatear resultado como espera el frontend
        formatted_result = [{'id': row[0], 'description': row[1]} for row in result]
        
        return jsonify(formatted_result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_days_agenda', methods=['POST'])
def get_days_agenda():
    """Obtiene agenda de días para un médico específico"""
    try:
        data = request.get_json()
        id_med = data.get('id')
        
        if not id_med:
            return jsonify({'error': 'ID de médico requerido'}), 400
            
        query = """
            SELECT guid, day, timefrom, timeto, initday, finishday 
            FROM nextris.isagendameditem 
            WHERE idmed = %s
        """
        result = DatabaseService.execute_query(query, (id_med,))
        
        # Formatear las fechas y horas para JSON
        formatted_result = []
        for row in result:
            formatted_row = {
                'guid': row[0],
                'day': row[1],
                'timefrom': row[2].strftime('%H:%M:%S') if row[2] else '',
                'timeto': row[3].strftime('%H:%M:%S') if row[3] else '',
                'initday': row[4].strftime('%Y-%m-%d') if row[4] else '',
                'finishday': row[5].strftime('%Y-%m-%d') if row[5] else ''
            }
            formatted_result.append(formatted_row)
        
        return jsonify(formatted_result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_grupos_medico', methods=['POST'])
def get_grupos_medico():
    """Obtiene grupos de estudios asociados a un médico específico"""
    try:
        data = request.get_json()
        med_id = data.get('id')
        
        if not med_id:
            return jsonify({'error': 'ID de médico requerido'}), 400
            
        query = """
            SELECT r.guid, g.description
            FROM nextris.rel_medico_studygroup r
            LEFT JOIN nextris.isstudytypegroup g ON r.studygroup_id = g.guid
            WHERE r.med_id = %s
        """
        result = DatabaseService.execute_query(query, (med_id,))
        
        # Formatear resultado como espera el frontend
        formatted_result = [{'id': row[0], 'description': row[1]} for row in result]
        
        return jsonify(formatted_result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/agregar_mach', methods=['POST'])
def agregar_mach():
    """Agregar un nuevo equipo/máquina"""
    try:
        respuesta = request.form.to_dict()
        print(f"[DEBUG] Datos recibidos para agregar máquina: {respuesta}")
        
        # Obtener valores del formulario
        description = respuesta.get('Description_mach')
        aetitle = respuesta.get('AETitle')
        modalidad_id = respuesta.get('s_moda')
        brand = respuesta.get('equip_brand')
        model = respuesta.get('equip_model')
        serial_number = respuesta.get('equip_sn')
        ip_address = respuesta.get('equip_ip')
        external_code = respuesta.get('Ext_code_equip')
        is_active = True if 'IsAc_mach' in respuesta else False
        
        # Validar campos requeridos
        if not description or not modalidad_id:
            return jsonify({'error': 'Descripción y modalidad son requeridos'}), 400
        
        # Insertar el nuevo equipo
        query = """
            INSERT INTO nextris.isequipment 
            (description, aetitle, idmodality, brandequipment, modelequipment, 
             snequipment, ip, externalcode, isactive) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING guid, description, aetitle, externalcode
        """

        print("[DEBUG] query to insert equipment with explicit values:", query)
        
        result = DatabaseService.execute_query(
            query, 
            (description, aetitle, modalidad_id, brand, model, serial_number, ip_address, external_code, is_active),
            commit=True,
            fetch_all=True
        )
        
        if result and len(result) > 0:
            # Obtener los datos completos con la descripción de modalidad EN EL MISMO ORDEN que get_mach()
            query_details = """
                SELECT e.description, e.aetitle, e.externalcode, m.description as modality, 
                       e.ip, e.brandequipment, e.modelequipment, e.snequipment, e.isactive
                FROM nextris.isequipment e
                INNER JOIN nextris.ismodality m ON m.guid = e.idmodality
                WHERE e.guid = %s
            """
            details = DatabaseService.execute_query(query_details, (result[0][0],), fetch_one=True)
            
            response_data = {
                'status': 'OK', 
                'message': 'Equipo creado exitosamente',
                'data': list(details) if details else list(result[0])
            }
            return jsonify(response_data)
        else:
            return jsonify({'error': 'No se pudo crear el equipo'}), 500
            
    except Exception as e:
        print(f"[ERROR] Error al agregar equipo: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/actualizar_mach', methods=['POST'])
def actualizar_mach():
    """Actualizar un equipo/máquina existente"""
    try:
        respuesta = request.form.to_dict()
        print(f"[DEBUG] Datos recibidos para actualizar máquina: {respuesta}")
        
        # Validar que se reciba el ID
        if 'id_mach' not in respuesta:
            return jsonify({'error': 'ID del equipo requerido'}), 400
        
        # Obtener valores del formulario
        equipo_id = respuesta.get('id_mach')
        description = respuesta.get('Description_mach')
        aetitle = respuesta.get('AETitle')
        modalidad_id = respuesta.get('s_moda')
        brand = respuesta.get('equip_brand')
        model = respuesta.get('equip_model')
        serial_number = respuesta.get('equip_sn')
        ip_address = respuesta.get('equip_ip')
        external_code = respuesta.get('Ext_code_equip')
        is_active = True if 'IsAc_mach' in respuesta else False
        
        # Actualizar el equipo
        query = """
            UPDATE nextris.isequipment 
            SET description = %s, aetitle = %s, idmodality = %s, 
                brandequipment = %s, modelequipment = %s, snequipment = %s,
                ip = %s, externalcode = %s, isactive = %s
            WHERE guid = %s
        """
        
        DatabaseService.execute_query(
            query, 
            (description, aetitle, modalidad_id, brand, model, serial_number, 
             ip_address, external_code, is_active, equipo_id),
            commit=True
        )
        
        # Obtener los datos actualizados con la descripción de modalidad
        query_details = """
            SELECT e.guid, e.description, e.aetitle, e.externalcode, m.description as modality, 
                   e.ip, e.brandequipment, e.modelequipment, e.snequipment, e.isactive
            FROM nextris.isequipment e
            INNER JOIN nextris.ismodality m ON m.guid = e.idmodality
            WHERE e.guid = %s
        """
        details = DatabaseService.execute_query(query_details, (equipo_id,), fetch_one=True)
        
        response_data = {
            'status': 'OK', 
            'message': 'Equipo actualizado exitosamente',
            'data': list(details) if details else []
        }
        return jsonify(response_data)
            
    except Exception as e:
        print(f"[ERROR] Error al actualizar equipo: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/eliminar_mach', methods=['POST'])
def eliminar_mach():
    """Eliminar un equipo/máquina"""
    try:
        data = request.json
        equipo_id = data.get('id')
        
        if not equipo_id:
            return jsonify({'error': 'ID del equipo requerido'}), 400
        
        # Eliminar el equipo
        query = "DELETE FROM nextris.isequipment WHERE guid = %s"
        DatabaseService.execute_query(query, (equipo_id,), commit=True)
        
        return jsonify({'status': 'OK', 'message': 'Equipo eliminado exitosamente'})
            
    except Exception as e:
        print(f"[ERROR] Error al eliminar equipo: {str(e)}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/agregar_dia_agenda_equip', methods=['POST'])
def agregar_dia_agenda_equip():
    """Agregar un día de agenda para equipo"""
    try:
        data = request.form
        id_agenda_equip = data.get('id_agenda_equip')
        day = data.get('day')
        timefrom = data.get('timefrom')
        timeto = data.get('timeto')

        query = """
            INSERT INTO nextris.isagendaequip (guid, idequipment, day, timefrom, timeto)
            VALUES (uuid_generate_v4(), %s, %s, %s, %s)
            RETURNING guid, day, timefrom, timeto;
        """
        print("[DEBUG] Executing query to insert agenda equip day")
        print("[DEBUG] Full query:", query % (id_agenda_equip, day, timefrom, timeto))
        result = DatabaseService.execute_query(query, (id_agenda_equip, day, timefrom, timeto), commit=True)

        if result:
            new_row = result[0]
            formatted_result = [
                new_row[1],  # day
                new_row[2].strftime('%H:%M') if new_row[2] else '',  # timefrom
                new_row[3].strftime('%H:%M') if new_row[3] else '',  # timeto
            ]
            return jsonify({
                'status': 'OK',
                'message': 'Día de agenda agregado exitosamente',
                'data': formatted_result
            })
        else:
            return jsonify({'error': 'No se pudo insertar el registro'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/eliminar_dia_agenda_equip', methods=['POST'])
def eliminar_dia_agenda_equip():
    """Eliminar un día de agenda para equipo"""
    try:
        data = request.get_json()
        guid = data.get('id')
        
        if not guid:
            return jsonify({'error': 'No se recibió el id'}), 400
            
        query = "DELETE FROM nextris.isagendaequip WHERE guid = %s;"
        DatabaseService.execute_query(query, (guid,), commit=True)
        
        return jsonify({'status': 'OK', 'message': 'Día de agenda eliminado exitosamente'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/actualizar_dia_agenda_equip', methods=['POST'])
def actualizar_dia_agenda_equip():
    """Actualizar un día de agenda para equipo"""
    try:
        data = request.form
        guid = data.get('id_item_agenda')
        day = data.get('day')
        timefrom = data.get('timefrom')
        timeto = data.get('timeto')

        if not guid:
            return jsonify({'error': 'No se recibió el id del día de agenda'}), 400

        query = """
            UPDATE nextris.isagendaequip 
            SET day = %s, timefrom = %s, timeto = %s
            WHERE guid = %s
            RETURNING guid, day, timefrom, timeto;
        """
        print("[DEBUG] Executing query to update agenda equip day")
        result = DatabaseService.execute_query(query, (day, timefrom, timeto, guid), commit=True)

        if result:
            updated_row = result[0]
            formatted_result = [
                updated_row[1],  # day
                updated_row[2].strftime('%H:%M') if updated_row[2] else '',  # timefrom
                updated_row[3].strftime('%H:%M') if updated_row[3] else '',  # timeto
            ]
            return jsonify({
                'status': 'OK',
                'message': 'Día de agenda actualizado exitosamente',
                'data': formatted_result
            })
        else:
            return jsonify({'error': 'No se pudo actualizar el registro'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/get_equipo_modal', methods=['GET']) 
def get_equipo_modal():
    """Obtener lista de equipos para modal con preselección si se proporciona idevent"""
    try:
        idevent = request.args.get('idevent')
        print(f"[DEBUG] get_equipo_modal called with idevent: {idevent}")
        if idevent:
            # Obtener el equipo asignado y la modalidad del examen de la cita
            query = """
                SELECT ae.idequipment, st.modality_id
                FROM nextris.tbagendaevents ae
                LEFT JOIN nextris.isstudytype st ON ae.idexam = st.guid
				WHERE ae.guid =  %s
            """
            result = DatabaseService.execute_query(query, (idevent,))
            
            if result and len(result) > 0 and result[0][1]:  # Si hay modalidad
                equipo_asignado = result[0][0]  # Puede ser None
                modalidad = result[0][1]
                
                # Obtener equipos compatibles (mismo tipo de modalidad)
                query_equipos = """
                    SELECT e.guid, e.aetitle, e.externalcode, e.idmodality,
                           CASE WHEN e.guid = %s THEN 1 ELSE 0 END as es_asignado
                    FROM nextris.isequipment e
                    WHERE e.idmodality = %s
                    ORDER BY es_asignado DESC, e.aetitle ASC
                """
                equipos = DatabaseService.execute_query(query_equipos, (equipo_asignado, modalidad))
                
                # Devolver equipos con indicador de cuál está asignado
                return jsonify({
                    'equipos': [[e[0], e[1], e[2], e[3], e[4]] for e in equipos],
                    'equipo_asignado': equipo_asignado
                })
        
        # Si no hay idevent o no se encontró info, devolver todos los equipos
        query = """SELECT guid, aetitle, externalcode, idmodality FROM nextris.isequipment"""
        result = DatabaseService.execute_query(query)
        
        return jsonify({
            'equipos': [[e[0], e[1], e[2], e[3], 0] for e in result],
            'equipo_asignado': None
        })
        
    except Exception as e:
        print(f"Error en get_equipo_modal: {e}")
        # En caso de error, devolver todos los equipos sin preselección
        query = """SELECT guid, aetitle, externalcode, idmodality FROM nextris.isequipment"""
        result = DatabaseService.execute_query(query)
        return jsonify({
            'equipos': [[e[0], e[1], e[2], e[3], 0] for e in result],
            'equipo_asignado': None
        })


@config_bp.route('/get_equip_for_exam', methods=['GET']) 
def get_equip_for_exam():
    """Obtener equipos disponibles para un examen específico, opcionalmente filtrados por ubicación"""
    try:
        exam = request.args.get('exam')
        location_id = request.args.get('location_id')
        
        if not exam:
            return jsonify({'error': 'Parámetro exam requerido'}), 400
        
        # Si hay location_id, filtrar por ubicación
        if location_id:
            query = """SELECT eq.Guid, eq.Description FROM nextris.IsEquipment eq
                       LEFT JOIN nextris.isstudytype st ON st.modality_id = eq.IdModality
                       WHERE st.Description = %s AND eq.location_id = %s AND eq.isactive = true"""
            result = DatabaseService.execute_query(query, (exam, location_id))
            print(f"[DEBUG get_equip_for_exam] Filtrando por exam: {exam}, location_id: {location_id} - Encontrados: {len(result) if result else 0} equipos")
        else:
            # Sin filtro de ubicación (comportamiento original)
            query = """SELECT eq.Guid, eq.Description FROM nextris.IsEquipment eq
                       LEFT JOIN nextris.isstudytype st ON st.modality_id = eq.IdModality
                       WHERE st.Description = %s AND eq.isactive = true"""
            result = DatabaseService.execute_query(query, (exam,))
            print(f"[DEBUG get_equip_for_exam] Sin filtro de ubicación - Encontrados: {len(result) if result else 0} equipos")
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@config_bp.route('/create_user', methods=['POST'])
@require_role('Sysadmin')
def create_user():
    """Crear un nuevo usuario - Solo Sysadmin"""
    try:
        respuesta = request.form.to_dict()
        print(respuesta)
        dni = respuesta.get('nationalnumber')
        mail = respuesta.get('text_mail')
        name = respuesta.get('name')
        surname = respuesta.get('surname')
        username = respuesta.get('username')
        role_guid = respuesta.get('s_type_of_user')  # Este es el GUID del rol
        
        # Verificar si el usuario ya existe
        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({'status': 'error', 'message': 'El nombre de usuario ya existe'}), 400
        
        # Obtener el nombre del rol para la respuesta
        select_query = "SELECT description FROM nextris.isrole WHERE guid = %s"
        rol_desc_result = DatabaseService.execute_query(select_query, (role_guid,), fetch_one=True)
        rol_desc = rol_desc_result[0] if rol_desc_result else "Usuario"
        
        print(f"[DEBUG] Creando usuario con rol GUID: {role_guid} -> {rol_desc}")
        
        # Crear usuario usando el modelo actualizado
        new_user = Users(
            username=username,
            email=mail,
            password="1234",  # Contraseña automática que será hasheada por el modelo
            name=name,
            surname=surname,
            national_number=dni,
            role_id=role_guid,  # Usar el GUID del rol directamente
            is_active=True
        )
        
        # Generar un nuevo GUID para el usuario
        import uuid
        new_user.id = str(uuid.uuid4())
        
        db.session.add(new_user)
        db.session.commit()
        
        # Preparar los datos para la respuesta
        response = [username, rol_desc, name, surname, dni, mail, '1']
        response_data = {
            'status': 'OK',
            'message': 'Usuario creado exitosamente con contraseña: 1234',
            'data': response
        }
        return jsonify(response_data)
        
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Error creando usuario: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@config_bp.route('/edit_user', methods=['POST'])
@require_role('Sysadmin')
def edit_user():
    """Editar un usuario existente - Solo Sysadmin"""
    try:
        respuesta = request.form.to_dict()
        print(respuesta)
        user_id = respuesta.get('id_user')
        username = respuesta.get('username')
        name = respuesta.get('name')
        surname = respuesta.get('surname')
        dni = respuesta.get('nationalnumber')
        type_of_user = respuesta.get('s_type_of_user')
        mail = respuesta.get('text_mail')

        # Actualizar usuario en tbuser
        update_query = """
            UPDATE nextris.tbuser 
            SET username = %s, name = %s, surname = %s, nationalnumber = %s, idrole = %s, mail = %s
            WHERE guid = %s
        """
        DatabaseService.execute_query(
            update_query, 
            (username, name, surname, dni, type_of_user, mail, user_id), 
            commit=True
        )
        
        return jsonify({"success": True})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@config_bp.route('/deactivate_user', methods=['POST'])
@require_role('Sysadmin')
def deactivate_user():
    """Desactivar un usuario (en lugar de eliminarlo) - Solo Sysadmin"""
    try:
        respuesta = request.get_json()
        print(respuesta)
        user_id = respuesta.get('id')
        
        if not user_id:
            return jsonify({'status': 'error', 'message': 'ID de usuario requerido'}), 400
        
        # Desactivar usuario en lugar de eliminarlo
        update_query = "UPDATE nextris.tbuser SET isactive = 0 WHERE guid = %s"
        DatabaseService.execute_query(update_query, (user_id,), commit=True)
        
        return jsonify({"success": True, "message": "Usuario desactivado correctamente"})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@config_bp.route('/activate_user', methods=['POST'])
@require_role('Sysadmin')
def activate_user():
    """Reactivar un usuario desactivado - Solo Sysadmin"""
    try:
        respuesta = request.get_json()
        print(respuesta)
        user_id = respuesta.get('id')
        
        if not user_id:
            return jsonify({'status': 'error', 'message': 'ID de usuario requerido'}), 400
        
        # Reactivar usuario
        update_query = "UPDATE nextris.tbuser SET isactive = 1 WHERE guid = %s"
        DatabaseService.execute_query(update_query, (user_id,), commit=True)
        
        return jsonify({"success": True, "message": "Usuario reactivado correctamente"})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@config_bp.route('/reset_user_password', methods=['POST'])
@require_role('Sysadmin')
def reset_user_password():
    """Resetear contraseña de usuario con contraseña temporal - Solo Sysadmin"""
    try:
        from werkzeug.security import generate_password_hash
        import secrets
        import string
        
        data = request.get_json()
        user_id = data.get('user_id')
        temp_password = data.get('temp_password')
        
        if not user_id or not temp_password:
            return jsonify({'status': 'error', 'message': 'ID de usuario y contraseña temporal requeridos'}), 400
        
        # Verificar que el usuario existe
        check_query = "SELECT username FROM nextris.tbuser WHERE guid = %s"
        result = DatabaseService.execute_query(check_query, (user_id,))
        
        if not result:
            return jsonify({'status': 'error', 'message': 'Usuario no encontrado'}), 404
        
        # Generar hash de la contraseña temporal
        password_hash = generate_password_hash(temp_password)
        
        # Actualizar contraseña y marcar como primer inicio
        update_query = """
            UPDATE nextris.tbuser 
            SET password = %s, first_login = 1 
            WHERE guid = %s
        """
        DatabaseService.execute_query(update_query, (password_hash, user_id), commit=True)
        
        return jsonify({
            "success": True, 
            "message": "Contraseña reseteada correctamente. El usuario deberá cambiarla en su primer inicio de sesión."
        })
        
    except Exception as e:
        print(f"Error al resetear contraseña: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error interno: {str(e)}'}), 500


@config_bp.route('/generate_temp_password', methods=['GET'])
@require_role('Sysadmin')
def generate_temp_password():
    """Generar una contraseña temporal segura - Solo Sysadmin"""
    try:
        import secrets
        import string
        
        # Generar contraseña temporal de 8 caracteres
        alphabet = string.ascii_letters + string.digits
        temp_password = ''.join(secrets.choice(alphabet) for i in range(8))
        
        return jsonify({
            "success": True,
            "temp_password": temp_password
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@config_bp.route('/reset_patient_password', methods=['POST'])
@require_role('Sysadmin')
def reset_patient_password():
    """Resetear contraseña de paciente con contraseña temporal - Solo Sysadmin"""
    try:
        from werkzeug.security import generate_password_hash
        
        data = request.get_json()
        user_id = data.get('user_id')
        temp_password = data.get('temp_password')
        
        if not user_id or not temp_password:
            return jsonify({'status': 'error', 'message': 'ID de paciente y contraseña temporal requeridos'}), 400
        
        # Verificar que el paciente existe
        check_query = "SELECT username FROM nextris.tbuser_patient WHERE guid = %s"
        result = DatabaseService.execute_query(check_query, (user_id,))
        
        if not result:
            return jsonify({'status': 'error', 'message': 'Paciente no encontrado'}), 404
        
        # Generar hash de la contraseña temporal
        password_hash = generate_password_hash(temp_password)
        
        # Actualizar contraseña y marcar como primer inicio
        update_query = """
            UPDATE nextris.tbuser_patient 
            SET password = %s, firstlogin = 1 
            WHERE guid = %s
        """
        DatabaseService.execute_query(update_query, (password_hash, user_id), commit=True)
        
        return jsonify({
            "success": True, 
            "message": "Contraseña reseteada correctamente. El paciente deberá cambiarla en su primer inicio de sesión."
        })
        
    except Exception as e:
        print(f"Error al resetear contraseña del paciente: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error interno: {str(e)}'}), 500
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@config_bp.route('/get_patient_data', methods=['GET'])
@require_role('Sysadmin')
def get_patient_data():
    """Obtener datos completos de un paciente para edición - Solo Sysadmin"""
    try:
        patient_id = request.args.get('patient_id')
        
        if not patient_id:
            return jsonify({'status': 'error', 'message': 'ID de paciente requerido'}), 400
        
        # Paso 1: Obtener username, datapatient_id y status de tbuser_patient
        user_query = """
            SELECT username, datapatient_id, status
            FROM nextris.tbuser_patient
            WHERE guid = %s
        """
        user_result = DatabaseService.execute_query(user_query, (patient_id,))
        
        if not user_result or len(user_result) == 0:
            return jsonify({'status': 'error', 'message': 'Paciente no encontrado'}), 404
        
        username = user_result[0][0]
        datapatient_id = user_result[0][1]
        status = user_result[0][2]
        
        # Paso 2: Obtener datos del paciente de datapatient
        patient_query = """
            SELECT name, surname, nationalcode, birthdate, patientid, sexcode, phone, email
            FROM nextris.datapatient
            WHERE guid = %s
        """
        patient_result = DatabaseService.execute_query(patient_query, (datapatient_id,))
        
        if not patient_result or len(patient_result) == 0:
            return jsonify({'status': 'error', 'message': 'Datos del paciente no encontrados'}), 404
        
        # Construir respuesta con todos los datos
        patient_data = {
            'patient_id': patient_id,
            'username': username,
            'status': status,
            'name': patient_result[0][0],
            'surname': patient_result[0][1],
            'nationalcode': patient_result[0][2],  # DNI
            'birthdate': patient_result[0][3].strftime('%Y-%m-%d') if patient_result[0][3] else '',
            'patientid': patient_result[0][4],  # CUIL
            'sexcode': patient_result[0][5],
            'phone': patient_result[0][6],
            'email': patient_result[0][7]
        }
        
        return jsonify({
            'status': 'OK',
            'data': patient_data
        })
        
    except Exception as e:
        print(f"Error al obtener datos del paciente: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error interno: {str(e)}'}), 500


@config_bp.route('/edit_patient', methods=['POST'])
@require_role('Sysadmin')
def edit_patient():
    """Editar un paciente existente - Solo Sysadmin"""
    try:
        respuesta = request.form.to_dict()
        print(f"[DEBUG] Datos recibidos para editar paciente: {respuesta}")
        
        # Obtener datos del formulario
        patient_id = respuesta.get('id_patient')
        username = respuesta.get('patient_username')
        name = respuesta.get('patient_name')
        surname = respuesta.get('patient_surname')
        dni = respuesta.get('patient_dni')
        birthdate = respuesta.get('patient_birthdate')
        gender = respuesta.get('patient_gender')
        phone = respuesta.get('patient_phone')
        email = respuesta.get('patient_email')
        cuil = respuesta.get('patient_cuil')
        # insurance_number = respuesta.get('patient_insurance_number')  # Para futuro uso
        
        if not patient_id:
            return jsonify({'status': 'error', 'message': 'ID de paciente requerido'}), 400
        
        # Paso 1: Obtener el datapatient_id del usuario paciente
        get_datapatient_query = """
            SELECT datapatient_id FROM nextris.tbuser_patient WHERE guid = %s
        """
        result = DatabaseService.execute_query(get_datapatient_query, (patient_id,))
        
        if not result or len(result) == 0:
            return jsonify({'status': 'error', 'message': 'Paciente no encontrado'}), 404
        
        datapatient_id = result[0][0]
        
        # Paso 2: Actualizar datos en tbuser_patient (username)
        update_user_query = """
            UPDATE nextris.tbuser_patient 
            SET username = %s
            WHERE guid = %s
        """
        DatabaseService.execute_query(update_user_query, (username, patient_id), commit=True)
        print(f"[DEBUG] tbuser_patient actualizado - username: {username}")
        
        # Paso 3: Actualizar datos en datapatient
        update_patient_query = """
            UPDATE nextris.datapatient 
            SET name = %s, 
                surname = %s, 
                nationalcode = %s, 
                birthdate = %s, 
                patientid = %s, 
                sexcode = %s, 
                phone = %s, 
                email = %s
            WHERE guid = %s
        """
        DatabaseService.execute_query(
            update_patient_query, 
            (name, surname, dni, birthdate, cuil, gender, phone, email, datapatient_id), 
            commit=True
        )
        print(f"[DEBUG] datapatient actualizado - datapatient_id: {datapatient_id}")
        
        return jsonify({
            "status": "OK",
            "success": True,
            "message": "Paciente actualizado correctamente"
        })
        
    except Exception as e:
        print(f"[ERROR] Error al editar paciente: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error interno: {str(e)}'}), 500


@config_bp.route('/get_medical_data', methods=['GET'])
@require_role('Sysadmin')
def get_medical_data():
    """Obtener datos médicos de un usuario - Solo Sysadmin"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({'status': 'error', 'message': 'ID de usuario requerido'}), 400
        
        # Verificar si la tabla existe, si no crearla
        create_table_if_not_exists()
        
        # Obtener datos médicos del usuario
        query = """
            SELECT aclaracion_firma, matricula_nacional, firma_digital, firma_habilitada
            FROM nextris.tbuser_medical_data
            WHERE user_id = %s
        """
        result = DatabaseService.execute_query(query, (user_id,))
        
        if result:
            data = result[0]
            print(f"[DEBUG] Datos médicos encontrados: {data}")
            return jsonify({
                "success": True,
                "data": {
                    "aclaracion_firma": data[0],
                    "matricula_nacional": data[1],
                    "firma_digital": data[2],
                    "firma_habilitada": bool(data[3])
                }
            })
        else:
            return jsonify({
                "success": True,
                "data": {
                    "aclaracion_firma": "",
                    "matricula_nacional": "",
                    "firma_digital": None,
                    "firma_habilitada": False
                }
            })
        
    except Exception as e:
        print(f"Error al obtener datos médicos: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error interno: {str(e)}'}), 500


@config_bp.route('/save_medical_data', methods=['POST'])
@require_role('Sysadmin')
def save_medical_data():
    """Guardar datos médicos de un usuario - Solo Sysadmin"""
    try:
        import os
        import uuid
        from werkzeug.utils import secure_filename
        
        user_id = request.form.get('user_id_medical')
        aclaracion_firma = request.form.get('aclaracion_firma')
        matricula_nacional = request.form.get('matricula_nacional')
        firma_habilitada = 'firma_habilitada' in request.form
        
        if not user_id or not aclaracion_firma or not matricula_nacional:
            return jsonify({'status': 'error', 'message': 'Campos obligatorios faltantes'}), 400
        
        # Verificar si la tabla existe, si no crearla
        create_table_if_not_exists()
        
        # Manejar archivo de firma
        firma_filename = None
        if 'firma_digital' in request.files:
            file = request.files['firma_digital']
            if file and file.filename:
                # Validar tipo de archivo
                allowed_extensions = {'png', 'jpg', 'jpeg'}
                file_extension = file.filename.rsplit('.', 1)[1].lower()
                
                if file_extension not in allowed_extensions:
                    return jsonify({'status': 'error', 'message': 'Tipo de archivo no permitido'}), 400
                
                # Crear directorio de firmas si no existe
                upload_dir = os.path.join(os.getcwd(), 'media', 'firmas')
                os.makedirs(upload_dir, exist_ok=True)
                
                print(f"[DEBUG] Directorio de firmas: {upload_dir}")
                
                # Generar nombre único para el archivo
                unique_filename = f"{user_id}_{uuid.uuid4().hex}.{file_extension}"
                firma_path = os.path.join(upload_dir, unique_filename)
                
                print(f"[DEBUG] Guardando archivo en: {firma_path}")
                
                # Guardar archivo
                file.save(firma_path)
                
                # Solo guardar el nombre del archivo en la BD, no la ruta completa
                firma_filename = unique_filename
        
        # Verificar si ya existen datos para este usuario
        check_query = "SELECT user_id FROM nextris.tbuser_medical_data WHERE user_id = %s"
        existing = DatabaseService.execute_query(check_query, (user_id,))
        
        if existing:
            # Actualizar datos existentes
            if firma_filename:
                update_query = """
                    UPDATE nextris.tbuser_medical_data 
                    SET aclaracion_firma = %s, matricula_nacional = %s, 
                        firma_digital = %s, firma_habilitada = %s, fecha_actualizacion = NOW()
                    WHERE user_id = %s
                """
                DatabaseService.execute_query(update_query, 
                    (aclaracion_firma, matricula_nacional, firma_filename, firma_habilitada, user_id), 
                    commit=True)
            else:
                update_query = """
                    UPDATE nextris.tbuser_medical_data 
                    SET aclaracion_firma = %s, matricula_nacional = %s, 
                        firma_habilitada = %s, fecha_actualizacion = NOW()
                    WHERE user_id = %s
                """
                DatabaseService.execute_query(update_query, 
                    (aclaracion_firma, matricula_nacional, firma_habilitada, user_id), 
                    commit=True)
        else:
            # Insertar nuevos datos
            insert_query = """
                INSERT INTO nextris.tbuser_medical_data 
                (user_id, aclaracion_firma, matricula_nacional, firma_digital, firma_habilitada, fecha_creacion, fecha_actualizacion)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            """
            DatabaseService.execute_query(insert_query, 
                (user_id, aclaracion_firma, matricula_nacional, firma_filename, firma_habilitada), 
                commit=True)
        
        return jsonify({
            "success": True,
            "message": "Datos médicos guardados correctamente"
        })
        
    except Exception as e:
        print(f"Error al guardar datos médicos: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Error interno: {str(e)}'}), 500


def create_table_if_not_exists():
    """Crear tabla de datos médicos si no existe"""
    try:
        create_table_query = """
            CREATE TABLE IF NOT EXISTS nextris.tbuser_medical_data (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL UNIQUE,
                aclaracion_firma VARCHAR(255) NOT NULL,
                matricula_nacional VARCHAR(100) NOT NULL,
                firma_digital VARCHAR(500),
                firma_habilitada BOOLEAN DEFAULT FALSE,
                fecha_creacion TIMESTAMP DEFAULT NOW(),
                fecha_actualizacion TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES nextris.tbuser(guid) ON DELETE CASCADE
            );
        """
        DatabaseService.execute_query(create_table_query, commit=True)
        
    except Exception as e:
        print(f"Error al crear tabla de datos médicos: {str(e)}")
        raise e


@config_bp.route('/media/firmas/<filename>')
def serve_signature(filename):
    """Servir archivos de firmas digitales"""
    try:
        import os
        from flask import send_from_directory
        
        # Directorio base donde están las firmas
        upload_dir = os.path.join(os.getcwd(), 'media', 'firmas')
        file_path = os.path.join(upload_dir, filename)
        
        print(f"[DEBUG] Buscando archivo: {file_path}")
        
        if os.path.exists(file_path) and os.path.isfile(file_path):
            print(f"[DEBUG] Archivo encontrado, sirviendo: {filename}")
            return send_from_directory(upload_dir, filename)
        else:
            print(f"[DEBUG] Archivo no encontrado: {file_path}")
            return jsonify({'error': 'Archivo no encontrado'}), 404
            
    except Exception as e:
        print(f"Error al servir firma: {str(e)}")
        return jsonify({'error': 'Error interno'}), 500


@config_bp.route('/fix_medical_paths', methods=['GET'])
@require_role('Sysadmin')
def fix_medical_paths():
    """Endpoint temporal para corregir rutas duplicadas en la BD"""
    try:
        # Obtener todos los registros con rutas duplicadas
        query = "SELECT user_id, firma_digital FROM nextris.tbuser_medical_data WHERE firma_digital LIKE 'media/firmas/%'"
        result = DatabaseService.execute_query(query)
        
        fixed_count = 0
        for record in result:
            user_id, old_path = record
            # Extraer solo el nombre del archivo
            filename = old_path.split('/')[-1]
            
            # Actualizar con solo el nombre del archivo
            update_query = "UPDATE nextris.tbuser_medical_data SET firma_digital = %s WHERE user_id = %s"
            DatabaseService.execute_query(update_query, (filename, user_id), commit=True)
            fixed_count += 1
            
        return jsonify({
            "success": True,
            "message": f"Se corrigieron {fixed_count} registros",
            "fixed_records": fixed_count
        })
        
    except Exception as e:
        print(f"Error al corregir rutas: {str(e)}")
        return jsonify({'error': 'Error interno'}), 500


@config_bp.route('/remove_signature', methods=['POST'])
@require_role('Sysadmin')
def remove_signature():
    """Eliminar firma digital de un usuario"""
    try:
        user_id = request.form.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'message': 'ID de usuario requerido'}), 400
        
        # Obtener datos actuales del usuario para saber qué archivo eliminar
        query = "SELECT firma_digital FROM nextris.tbuser_medical_data WHERE user_id = %s"
        result = DatabaseService.execute_query(query, (user_id,))
        
        if result and result[0][0]:
            # Eliminar archivo físico del servidor
            firma_filename = result[0][0]
            if firma_filename:  # Solo eliminar si hay un archivo
                firma_path = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'media'), 'firmas', firma_filename)
                if os.path.exists(firma_path):
                    os.remove(firma_path)
        
        # Actualizar base de datos para eliminar referencia a la firma
        update_query = "UPDATE nextris.tbuser_medical_data SET firma_digital = NULL WHERE user_id = %s"
        DatabaseService.execute_query(update_query, (user_id,), commit=True)
        
        return jsonify({
            'success': True,
            'message': 'Firma eliminada correctamente'
        })
        
    except Exception as e:
        print(f"Error al eliminar firma: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error al eliminar firma: {str(e)}'
        }), 500


# =====================================================
# FUNCIONES AUXILIARES PARA MANEJO DE FIRMAS
# =====================================================

def get_user_signature_data(user_id):
    """
    Función auxiliar para obtener los datos de firma de un usuario
    Puede ser utilizada desde cualquier parte del sistema
    """
    try:
        query = """
            SELECT aclaracion_firma, matricula_nacional, firma_digital, firma_habilitada
            FROM nextris.tbuser_medical_data 
            WHERE user_id = %s AND firma_habilitada = true
        """
        result = DatabaseService.execute_query(query, (user_id,))
        
        if result and len(result) > 0:
            data = result[0]
            return {
                'aclaracion_firma': data[0],
                'matricula_nacional': data[1],
                'firma_digital': data[2],
                'firma_habilitada': bool(data[3]),
                'firma_path': os.path.join(os.getcwd(), 'media', 'firmas', data[2]) if data[2] else None
            }
    except Exception as e:
        print(f"Error al obtener datos de firma del usuario {user_id}: {e}")
    
    return None


def get_signature_image_path(user_id):
    """
    Función auxiliar para obtener solo la ruta de la imagen de firma
    """
    signature_data = get_user_signature_data(user_id)
    if signature_data and signature_data['firma_digital']:
        return signature_data['firma_path']
    return None


@config_bp.route('/create_patient', methods=['POST'])
def create_patient_from_config():
    """Endpoint para crear un paciente desde la página de configuración"""
    try:
        # Obtener datos del formulario
        r = request.form.to_dict()
        
        print(f"[DEBUG] Datos recibidos en create_patient_from_config: {r}")
        
        # Query para insertar en datapatient - RETURNING para obtener el GUID generado
        query = """
        INSERT INTO nextris.DataPatient(
            Guid, Surname, Name, NationalCode, BirthDate, PatientId, SexCode, 
            Phone, Email, HealthCard) 
        VALUES (
            uuid_generate_v4(), %s, %s, %s, %s, %s, %s, 
            %s, %s, %s) 
        RETURNING Guid
        """
        
        params = (
            r.get('patient_surname', ''),
            r.get('patient_name', ''),
            r.get('patient_dni', ''),
            r.get('patient_birthdate', None),
            r.get('patient_cuil', ''),  # patient_cuil va como PatientId
            r.get('patient_gender', ''),
            r.get('patient_phone', ''),
            r.get('patient_email', ''),
            r.get('patient_insurance_number', '')
        )
        
        # Ejecutar inserción en datapatient
        result = DatabaseService.execute_query(query, params, commit=True)
        
        # Obtener el GUID del paciente creado
        patient_guid = result[0][0] if result and len(result) > 0 else None
        
        print(f"[DEBUG] Paciente creado con GUID: {patient_guid}")
        
        # Crear usuario para el paciente en tbuser_patient
        if patient_guid:
            # Verificar si se proporcionó username personalizado
            custom_username = r.get('patient_username', '').strip()
            
            if custom_username:
                # Usar username personalizado
                base_username = custom_username.lower().replace(' ', '')
            else:
                # Generar username automáticamente: primera letra del nombre + apellido
                nombre = r.get('patient_name', '').strip()
                apellido = r.get('patient_surname', '').strip()
                
                if nombre and apellido:
                    base_username = (nombre[0] + apellido).lower().replace(' ', '')
                else:
                    # Fallback si no hay nombre o apellido
                    base_username = f"patient{patient_guid[:8]}"
            
            # Verificar si el username ya existe y agregar número si es necesario
            check_username_query = """
                SELECT COUNT(*) FROM nextris.tbuser_patient 
                WHERE username LIKE %s
            """
            
            # Buscar cuántos usuarios existen con ese patrón
            existing_count = DatabaseService.execute_query(
                check_username_query, 
                (f"{base_username}%",)
            )
            
            count = existing_count[0][0] if existing_count else 0
            
            # Si ya existe, agregar número secuencial
            if count > 0:
                # Buscar el siguiente número disponible
                for i in range(1, 100):
                    test_username = f"{base_username}{i:02d}"
                    check_exact = DatabaseService.execute_query(
                        "SELECT COUNT(*) FROM nextris.tbuser_patient WHERE username = %s",
                        (test_username,)
                    )
                    if check_exact[0][0] == 0:
                        username = test_username
                        break
                else:
                    username = base_username + str(count + 1).zfill(2)
            else:
                username = base_username
            
            print(f"[DEBUG] Username generado: {username}")
            
            # Hashear la contraseña temporal
            hashed_password = hash_pass('next')
            
            # Insertar el usuario del paciente
            insert_user_query = """
                INSERT INTO nextris.tbuser_patient (
                    guid, username, password, status, datapatient_id
                ) VALUES (
                    uuid_generate_v4(), %s, %s, %s, %s
                )
            """
            
            user_params = (
                username,
                hashed_password,  # password hasheada
                'Active',
                patient_guid
            )
            
            DatabaseService.execute_query(insert_user_query, user_params, commit=True)
            print(f"[DEBUG] Usuario paciente creado: {username}")
        
        # Retornar respuesta de éxito con formato esperado por ConfigModalForm
        return jsonify({
            'status': 'OK',
            'message': 'Paciente creado correctamente',
            'data': {
                'nombre': r.get('patient_name', ''),
                'dni': r.get('patient_dni', ''),
                'fecha_nacimiento': r.get('patient_birthdate', ''),
                'usuario': username if patient_guid else '',
                'estado': 'Active'
            }
        })
        
    except Exception as e:
        print(f"[ERROR] Error creando paciente desde configuración: {e}")
        return jsonify({
            'status': 'ERROR',
            'error': str(e)
        }), 500
