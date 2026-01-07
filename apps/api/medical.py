# -*- encoding: utf-8 -*-
"""
API REST para gestión de médicos, grupos médicos y usuarios
Endpoints para operaciones CRUD de usuarios del sistema y relaciones médico-grupo
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required
import psycopg2
from apps.api import api_blueprint
import uuid
import hashlib
from datetime import datetime


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.routes import config
        return config
    except:
        return None


@api_blueprint.route('/users_physician', methods=['GET'])
@jwt_required()
def get_doctors():
    """
    Obtiene lista de médicos filtrando por rol 'Medico'
    
    Query params:
    - active_only: boolean (opcional) - Solo médicos activos (default: false)
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "name": "Apellido Nombre"
            },
            ...
        ]
    }
    """
    try:
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener médicos filtrando por rol = 'Medico'
        query = """
            SELECT u.guid, u.surname || ' ' || u.name as full_name
            FROM nextris.tbuser u
            LEFT JOIN nextris.isrole ir ON ir.guid = u.idrole
            WHERE ir.description = 'Medico'
        """
        
        if active_only:
            query += " AND u.isactive = true"
        
        query += " ORDER BY u.surname, u.name"
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        doctors = []
        for row in results:
            doctors.append({
                'guid': row[0],
                'name': row[1] or ''
            })
        
        return jsonify({
            'success': True,
            'data': doctors
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/doctors/<doctor_id>/groups', methods=['GET'])
@jwt_required()
def get_doctor_groups(doctor_id):
    """
    Obtiene los grupos de estudio a los que pertenece un médico
    
    Path:
    - doctor_id: GUID del médico
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "description": "Nombre del grupo"
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
        
        query = """
            SELECT sg.guid, sg.description
            FROM nextris.isstudytypegroup sg
            INNER JOIN nextris.rel_medico_studygroup rms ON rms.studygroup_id = sg.guid
            WHERE rms.med_id = %s
            ORDER BY sg.description
        """
        
        cursor.execute(query, (doctor_id,))
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        groups = []
        for row in results:
            groups.append({
                'guid': row[0],
                'description': row[1]
            })
        
        return jsonify({
            'success': True,
            'data': groups
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/doctors/check-group-membership', methods=['POST'])
@jwt_required()
def check_doctor_group_membership():
    """
    Verifica si un médico pertenece al grupo requerido para un tipo de estudio
    
    Body JSON:
    {
        "doctor_id": "uuid-del-medico",
        "study_type_id": "uuid-del-tipo-de-estudio"
    }
    
    Returns:
    {
        "success": true,
        "data": {
            "belongs_to_group": true/false,
            "group_id": "uuid" (si pertenece)
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
        
        doctor_id = data.get('doctor_id')
        study_type_id = data.get('study_type_id')
        
        if not doctor_id or not study_type_id:
            return jsonify({
                'success': False,
                'message': 'doctor_id y study_type_id son requeridos'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Buscar el grupo asociado al studytype
        query_group = "SELECT studygroup_id FROM nextris.isstudytype WHERE guid = %s"
        cursor.execute(query_group, (study_type_id,))
        group_row = cursor.fetchone()
        
        if not group_row or not group_row[0]:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No se encontró el grupo para el tipo de estudio'
            }), 404
        
        group_id = group_row[0]
        
        # Verificar relación médico-grupo
        query = """
            SELECT 1 FROM nextris.rel_medico_studygroup 
            WHERE med_id = %s AND studygroup_id = %s
        """
        cursor.execute(query, (doctor_id, group_id))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'belongs_to_group': bool(result),
                'group_id': group_id if result else None
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/doctors/by-study-type', methods=['POST'])
@jwt_required()
def get_doctors_by_study_type():
    """
    Obtiene médicos solicitantes para un tipo de estudio específico
    Si no se proporciona study_type_id, retorna todos los médicos activos
    
    Body JSON:
    {
        "study_type_id": "uuid-opcional"
    }
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "name": "Nombre",
                "surname": "Apellido",
                "username": "usuario",
                "full_name": "Apellido Nombre"
            }
        ]
    }
    """
    try:
        data = request.get_json() or {}
        study_type_id = data.get('study_type_id')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        if study_type_id:
            # Obtener médicos específicos para el tipo de estudio
            query = """
                SELECT DISTINCT u.guid, u.name, u.surname, u.username
                FROM nextris.tbuser u
                INNER JOIN nextris.tbuser_medical_data md ON md.user_id = u.guid
                INNER JOIN nextris.rel_medico_studygroup rms ON rms.med_id = u.guid
                INNER JOIN nextris.isstudytype st ON st.studygroup_id = rms.studygroup_id
                WHERE st.guid = %s AND u.isactive = 1
                ORDER BY u.surname, u.name
            """
            cursor.execute(query, (study_type_id,))
        else:
            # Obtener todos los médicos activos
            query = """
                SELECT u.guid, u.name, u.surname, u.username
                FROM nextris.tbuser u
                INNER JOIN nextris.tbuser_medical_data md ON md.user_id = u.guid
                WHERE u.isactive = 1
                ORDER BY u.surname, u.name
            """
            cursor.execute(query)
        
        results = cursor.fetchall()
        cursor.close()
        connection.close()
        
        doctors = []
        for row in results:
            doctors.append({
                'guid': row[0],
                'name': row[1] or '',
                'surname': row[2] or '',
                'username': row[3] or '',
                'full_name': f"{row[2]} {row[1]}" if row[1] and row[2] else row[3]
            })
        
        return jsonify({
            'success': True,
            'data': doctors
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    """
    Obtiene lista completa de usuarios del sistema
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "username": "usuario",
                "name": "Nombre",
                "surname": "Apellido",
                "email": "email@ejemplo.com",
                "usertype": "tipo",
                "isactive": true,
                "createdon": "DD/MM/YYYY HH:MM",
                "full_name": "Apellido Nombre"
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
        
        query = """
            SELECT u.guid, u.username, u.name, u.surname, u.mail, 
                   CASE WHEN md.user_id IS NOT NULL THEN 'medico' ELSE 'user' END as usertype,
                   u.isactive
            FROM nextris.tbuser u
            LEFT JOIN nextris.tbuser_medical_data md ON md.user_id = u.guid
            ORDER BY u.surname, u.name
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        users = []
        for row in results:
            users.append({
                'guid': row[0],
                'username': row[1] or '',
                'name': row[2] or '',
                'surname': row[3] or '',
                'email': row[4] or '',
                'usertype': row[5] or '',
                'isactive': bool(row[6]),
                'full_name': f"{row[3]} {row[2]}" if row[2] and row[3] else row[1]
            })
        
        return jsonify({
            'success': True,
            'data': users
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/users', methods=['POST'])
@jwt_required()
def create_user():
    """
    Crea un nuevo usuario en el sistema
    
    Body JSON:
    {
        "username": "usuario" (required),
        "password": "contraseña" (required),
        "name": "Nombre" (required),
        "surname": "Apellido" (required),
        "email": "email@ejemplo.com" (optional),
        "usertype": "tipo" (optional, default: "user")
    }
    
    Returns:
    {
        "success": true,
        "message": "Usuario creado exitosamente",
        "data": {
            "user_id": "uuid"
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
        
        username = data.get('username')
        password = data.get('password')
        name = data.get('name')
        surname = data.get('surname')
        email = data.get('email')
        usertype = data.get('usertype', 'user')
        
        if not all([username, password, name, surname]):
            return jsonify({
                'success': False,
                'message': 'username, password, name y surname son campos requeridos'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar si el username ya existe
        check_query = "SELECT 1 FROM nextris.tbuser WHERE username = %s"
        cursor.execute(check_query, (username,))
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'El nombre de usuario ya existe'
            }), 400
        
        # Crear nuevo usuario
        new_guid = str(uuid.uuid4())
        hashed_password = hashlib.md5(password.encode()).hexdigest()
        
        # Obtener un role por defecto (buscar el primero disponible)
        cursor.execute("SELECT guid FROM nextris.isrole LIMIT 1")
        role_row = cursor.fetchone()
        default_role = role_row[0] if role_row else str(uuid.uuid4())
        
        query = """
            INSERT INTO nextris.tbuser 
            (guid, username, password, name, surname, mail, idrole, isactive)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (
            new_guid, username, hashed_password, name, surname, 
            email, default_role, 1
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuario creado exitosamente',
            'data': {
                'user_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/users/<user_id>', methods=['PATCH', 'PUT'])
@jwt_required()
def update_user(user_id):
    """
    Actualiza datos de un usuario existente
    
    Path:
    - user_id: GUID del usuario
    
    Body JSON (todos opcionales):
    {
        "name": "Nuevo nombre",
        "surname": "Nuevo apellido",
        "email": "nuevo@email.com",
        "usertype": "nuevo_tipo",
        "isactive": true/false,
        "password": "nueva_contraseña"
    }
    
    Returns:
    {
        "success": true,
        "message": "Usuario actualizado exitosamente"
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
        
        # Verificar que el usuario existe
        check_query = "SELECT 1 FROM nextris.tbuser WHERE guid = %s"
        cursor.execute(check_query, (user_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404
        
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
            updates.append("mail = %s")
            params.append(data['email'])
        if 'isactive' in data:
            updates.append("isactive = %s")
            params.append(1 if data['isactive'] else 0)
        if 'password' in data:
            hashed_password = hashlib.md5(data['password'].encode()).hexdigest()
            updates.append("password = %s")
            params.append(hashed_password)
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(user_id)
        query = f"UPDATE nextris.tbuser SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuario actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
