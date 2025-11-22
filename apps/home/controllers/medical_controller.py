"""
Controller para gestión de médicos, grupos médicos y usuarios
Migrado masivamente desde routes.py para reducir el archivo principal
"""

from flask import Blueprint, request, jsonify
import psycopg2
from apps.home.services.database_service import DatabaseService
from apps.home.services.config_service import ConfigService

# Crear blueprint para médicos
medical_bp = Blueprint('medical', __name__, url_prefix='/api')

# Obtener configuración de BD
config = ConfigService.get_db_config()

@medical_bp.route('/check_medico_grupo', methods=['POST'])
def check_medico_grupo():
    """Verifica si un médico pertenece a un grupo específico"""
    try:
        data = request.get_json()
        med_id = data.get('med_id')
        studytype_id = data.get('studytype_id')
        
        if not med_id or not studytype_id:
            return jsonify({'success': False, 'error': 'Faltan datos'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Buscar el grupo asociado al studytype
        query_grupo = "SELECT studygroup_id FROM nextris.isstudytype WHERE guid = %s"
        cursor.execute(query_grupo, (studytype_id,))
        grupo_row = cursor.fetchone()
        
        if not grupo_row or not grupo_row[0]:
            return jsonify({'success': False, 'error': 'No se encontró el grupo para el estudio'}), 404
        
        grupo_id = grupo_row[0]
        
        # Validar relación médico-grupo
        query = "SELECT 1 FROM nextris.rel_medico_studygroup WHERE med_id = %s AND studygroup_id = %s"
        cursor.execute(query, (med_id, grupo_id))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if result:
            return jsonify({'success': True, 'relacion': True})
        else:
            return jsonify({'success': True, 'relacion': False})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@medical_bp.route('/get_grupos_medico', methods=['POST'])
def get_grupos_medico():
    """Obtiene los grupos a los que pertenece un médico"""
    try:
        data = request.get_json()
        med_id = data.get('med_id')
        
        if not med_id:
            return jsonify({'error': 'Falta med_id'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT sg.guid, sg.description
            FROM nextris.isstudygroup sg
            INNER JOIN nextris.rel_medico_studygroup rms ON rms.studygroup_id = sg.guid
            WHERE rms.med_id = %s
        """
        cursor.execute(query, (med_id,))
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        grupos = []
        for row in results:
            grupos.append({
                'guid': row[0],
                'description': row[1]
            })
        
        return jsonify(grupos)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@medical_bp.route('/get_lista_de_med', methods=['GET'])
def get_lista_de_med():
    """Obtiene lista completa de médicos"""
    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT guid, name, surname, username, email, isactive
            FROM nextris.datauser
            WHERE usertype = 'medico' OR usertype = 'doctor'
            ORDER BY surname, name
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        medicos = []
        for row in results:
            medicos.append({
                'guid': row[0],
                'name': row[1] or '',
                'surname': row[2] or '',
                'username': row[3] or '',
                'email': row[4] or '',
                'isactive': row[5],
                'full_name': f"{row[2]} {row[1]}" if row[1] and row[2] else row[3]
            })
        
        return jsonify(medicos)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@medical_bp.route('/get_med_sol', methods=['POST'])
def get_med_sol():
    """Obtiene médicos solicitantes para un estudio"""
    try:
        data = request.get_json()
        study_type_id = data.get('study_type_id')
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        if study_type_id:
            # Obtener médicos específicos para el tipo de estudio
            query = """
                SELECT DISTINCT du.guid, du.name, du.surname, du.username
                FROM nextris.datauser du
                INNER JOIN nextris.rel_medico_studygroup rms ON rms.med_id = du.guid
                INNER JOIN nextris.isstudytype st ON st.studygroup_id = rms.studygroup_id
                WHERE st.guid = %s AND du.isactive = true
                ORDER BY du.surname, du.name
            """
            cursor.execute(query, (study_type_id,))
        else:
            # Obtener todos los médicos activos
            query = """
                SELECT guid, name, surname, username
                FROM nextris.datauser
                WHERE (usertype = 'medico' OR usertype = 'doctor') AND isactive = true
                ORDER BY surname, name
            """
            cursor.execute(query)
        
        results = cursor.fetchall()
        cursor.close()
        connection.close()
        
        medicos = []
        for row in results:
            medicos.append({
                'guid': row[0],
                'name': row[1] or '',
                'surname': row[2] or '',
                'username': row[3] or '',
                'full_name': f"{row[2]} {row[1]}" if row[1] and row[2] else row[3]
            })
        
        return jsonify(medicos)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@medical_bp.route('/get_users', methods=['GET'])
def get_users():
    """Obtiene lista completa de usuarios del sistema"""
    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT guid, username, name, surname, email, usertype, isactive, createdon
            FROM nextris.datauser
            ORDER BY surname, name
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        usuarios = []
        for row in results:
            usuarios.append({
                'guid': row[0],
                'username': row[1] or '',
                'name': row[2] or '',
                'surname': row[3] or '',
                'email': row[4] or '',
                'usertype': row[5] or '',
                'isactive': row[6],
                'createdon': row[7].strftime('%d/%m/%Y %H:%M') if row[7] else '',
                'full_name': f"{row[3]} {row[2]}" if row[2] and row[3] else row[1]
            })
        
        return jsonify(usuarios)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@medical_bp.route('/crear_usuario', methods=['POST'])
def crear_usuario():
    """Crea un nuevo usuario en el sistema"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        name = data.get('name')
        surname = data.get('surname')
        email = data.get('email')
        usertype = data.get('usertype', 'user')
        
        if not all([username, password, name, surname]):
            return jsonify({'error': 'Faltan campos requeridos'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar si el username ya existe
        check_query = "SELECT 1 FROM nextris.datauser WHERE username = %s"
        cursor.execute(check_query, (username,))
        if cursor.fetchone():
            return jsonify({'error': 'El nombre de usuario ya existe'}), 400
        
        # Crear nuevo usuario
        import uuid
        import hashlib
        from datetime import datetime
        
        new_guid = str(uuid.uuid4())
        hashed_password = hashlib.md5(password.encode()).hexdigest()
        
        query = """
            INSERT INTO nextris.datauser 
            (guid, username, password, name, surname, email, usertype, isactive, createdon)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            new_guid, username, hashed_password, name, surname, 
            email, usertype, True, datetime.now()
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'user_id': new_guid})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@medical_bp.route('/actualizar_usuario', methods=['POST'])
def actualizar_usuario():
    """Actualiza datos de un usuario existente"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'Falta user_id'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'name' in data:
            updates.append("name = %s")
            params.append(data['name'])
        if 'surname' in data:
            updates.append("surname = %s")
            params.append(data['surname'])
        if 'email' in data:
            updates.append("email = %s")
            params.append(data['email'])
        if 'usertype' in data:
            updates.append("usertype = %s")
            params.append(data['usertype'])
        if 'isactive' in data:
            updates.append("isactive = %s")
            params.append(data['isactive'])
        if 'password' in data:
            import hashlib
            hashed_password = hashlib.md5(data['password'].encode()).hexdigest()
            updates.append("password = %s")
            params.append(hashed_password)
        
        if not updates:
            return jsonify({'error': 'No hay campos para actualizar'}), 400
        
        params.append(user_id)
        query = f"UPDATE nextris.datauser SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Usuario actualizado exitosamente'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@medical_bp.route('/get_exams_modal', methods=['GET']) 
def get_exams_modal():
    """Obtiene todos los tipos de estudios/exámenes para modal"""
    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = "SELECT Guid, code, description FROM nextris.isstudytype"
        cursor.execute(query)
        datos = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return jsonify(datos)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500