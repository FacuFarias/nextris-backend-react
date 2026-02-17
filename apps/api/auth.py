# -*- encoding: utf-8 -*-
"""
API de Autenticación - Endpoints JWT para React
"""

from flask import jsonify, request
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token, 
    jwt_required, 
    get_jwt_identity
)
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg2
from apps.api import api_blueprint
from apps.authentication.models import Users, PatientUser
from apps import db


@api_blueprint.route('/auth/login', methods=['POST'])
def api_login():
    """
    Login endpoint que retorna JWT token
    
    Body JSON:
    {
        "username": "usuario",
        "password": "contraseña",
        "user_type": "staff" o "patient"
    }
    
    Respuesta exitosa:
    {
        "success": true,
        "data": {
            "access_token": "...",
            "refresh_token": "...",
            "user": {
                "id": "...",
                "username": "...",
                "user_type": "...",
                "requires_password_change": false
            }
        },
        "message": "Login exitoso"
    }
    """
    try:
        data = request.get_json(force=True, silent=True)
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON en la petición'
            }), 400
        
        username = data.get('username')
        password = data.get('password')
        user_type = data.get('user_type', 'staff')
        
        if not username or not password:
            return jsonify({
                'success': False,
                'message': 'Usuario y contraseña requeridos'
            }), 400
        
        user = None
        user_data = {}
        
        if user_type == 'patient':
            # Autenticación de paciente
            try:
                from apps.home.routes import config as db_config
                
                if not db_config:
                    return jsonify({
                        'success': False,
                        'message': 'Error de configuración de base de datos'
                    }), 500
                
                connection = psycopg2.connect(**db_config)
                cursor = connection.cursor()
                
                # Buscar paciente
                cursor.execute("""
                    SELECT up.guid, up.username, up.password, dp.name, dp.surname, 
                           dp.email, up.status, up.firstlogin
                    FROM nextris.tbuser_patient up
                    LEFT JOIN nextris.datapatient dp ON up.datapatient_id = dp.guid
                    WHERE up.username = %s
                """, (username,))
                
                patient_row = cursor.fetchone()
                cursor.close()
                connection.close()
                
                if not patient_row:
                    return jsonify({
                        'success': False,
                        'message': 'Credenciales inválidas'
                    }), 401
                
                patient_guid, db_username, db_password, name, surname, email, status, firstlogin = patient_row
                
                # Verificar contraseña
                if not check_password_hash(db_password, password):
                    return jsonify({
                        'success': False,
                        'message': 'Credenciales inválidas'
                    }), 401
                
                # Verificar que esté activo
                is_active = False
                if isinstance(status, (int, bool)):
                    is_active = bool(status)
                elif isinstance(status, str):
                    is_active = status.lower() in ['active', '1', 'true', 'activo']
                
                if not is_active:
                    return jsonify({
                        'success': False,
                        'message': 'Usuario inactivo'
                    }), 401
                
                user_data = {
                    'id': patient_guid,
                    'username': db_username,
                    'name': name or db_username,
                    'surname': surname or '',
                    'email': email or '',
                    'user_type': 'patient',
                    'requires_password_change': bool(firstlogin)
                }
                
            except Exception as e:
                print(f"[API LOGIN] Error en autenticación de paciente: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': f'Error en la autenticación: {str(e)}'
                }), 500
        
        else:
            # Autenticación de staff
            user = Users.query.filter_by(username=username, is_active=1).first()
            
            if not user or not check_password_hash(user.password, password):
                return jsonify({
                    'success': False,
                    'message': 'Credenciales inválidas'
                }), 401
            
            user_data = {
                'id': user.id,
                'username': user.username,
                'name': user.name or user.username,
                'surname': user.surname or '',
                'email': user.email or '',
                'user_type': user.user_type,
                'role_id': user.role_id,
                'requires_password_change': bool(user.first_login)
            }
        
        # Crear tokens JWT
        # Incluir información adicional en el token (user_type)
        additional_claims = {
            'user_type': user_data['user_type'],
            'username': user_data['username']
        }
        
        access_token = create_access_token(
            identity=user_data['id'],
            additional_claims=additional_claims
        )
        refresh_token = create_refresh_token(
            identity=user_data['id'],
            additional_claims=additional_claims
        )
        
        return jsonify({
            'success': True,
            'data': {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user': user_data
            },
            'message': 'Login exitoso'
        }), 200
        
    except Exception as e:
        print(f"[API LOGIN] Error general: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error en el servidor: {str(e)}'
        }), 500


@api_blueprint.route('/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Obtener información del usuario actual autenticado
    
    Headers:
    Authorization: Bearer <access_token>
    
    Respuesta:
    {
        "success": true,
        "data": {
            "id": "...",
            "username": "...",
            "name": "...",
            "email": "...",
            "user_type": "..."
        }
    }
    """
    try:
        user_id = get_jwt_identity()
        
        # Obtener claims adicionales del token
        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        user_type = claims.get('user_type', 'staff')
        
        if user_type == 'patient':
            # Buscar paciente
            try:
                from apps.home.routes import config as db_config
                connection = psycopg2.connect(**db_config)
                cursor = connection.cursor()
                
                cursor.execute("""
                    SELECT up.guid, up.username, dp.name, dp.surname, dp.email
                    FROM nextris.tbuser_patient up
                    LEFT JOIN nextris.datapatient dp ON up.datapatient_id = dp.guid
                    WHERE up.guid = %s
                """, (user_id,))
                
                patient_row = cursor.fetchone()
                cursor.close()
                connection.close()
                
                if not patient_row:
                    return jsonify({
                        'success': False,
                        'message': 'Usuario no encontrado'
                    }), 404
                
                patient_guid, username, name, surname, email = patient_row
                
                return jsonify({
                    'success': True,
                    'data': {
                        'id': patient_guid,
                        'username': username,
                        'name': name or username,
                        'surname': surname or '',
                        'email': email or '',
                        'user_type': 'patient'
                    }
                }), 200
                
            except Exception as e:
                print(f"[API ME] Error obteniendo paciente: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': f'Error: {str(e)}'
                }), 500
        
        else:
            # Buscar staff
            user = Users.query.get(user_id)
            
            if not user:
                return jsonify({
                    'success': False,
                    'message': 'Usuario no encontrado'
                }), 404
            
            return jsonify({
                'success': True,
                'data': {
                    'id': user.id,
                    'username': user.username,
                    'name': user.name or user.username,
                    'surname': user.surname or '',
                    'email': user.email or '',
                    'user_type': user.user_type,
                    'role_id': user.role_id
                }
            }), 200
    
    except Exception as e:
        print(f"[API ME] Error general: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refrescar access token usando refresh token
    
    Headers:
    Authorization: Bearer <refresh_token>
    
    Respuesta:
    {
        "success": true,
        "data": {
            "access_token": "..."
        }
    }
    """
    try:
        user_id = get_jwt_identity()
        
        # Obtener claims del refresh token
        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        
        # Crear nuevo access token con los mismos claims
        additional_claims = {
            'user_type': claims.get('user_type', 'staff'),
            'username': claims.get('username', '')
        }
        
        access_token = create_access_token(
            identity=user_id,
            additional_claims=additional_claims
        )
        
        return jsonify({
            'success': True,
            'data': {
                'access_token': access_token
            }
        }), 200
    
    except Exception as e:
        print(f"[API REFRESH] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Logout (en el frontend se debe eliminar el token)
    
    Respuesta:
    {
        "success": true,
        "message": "Logout exitoso"
    }
    """
    # En JWT stateless no necesitamos hacer nada en el servidor
    # El frontend debe eliminar el token del localStorage
    return jsonify({
        'success': True,
        'message': 'Logout exitoso'
    }), 200


@api_blueprint.route('/auth/change-password', methods=['POST'])
@jwt_required()
def change_password_first_login():
    """
    Cambia contraseña del usuario autenticado y desactiva bandera de primer login.

    Body JSON:
    {
        "new_password": "string" (required, min 6)
    }
    """
    try:
        data = request.get_json(force=True, silent=True)
        new_password = (data or {}).get('new_password')

        if not new_password:
            return jsonify({
                'success': False,
                'message': 'new_password es requerido'
            }), 400

        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'message': 'La contraseña debe tener al menos 6 caracteres'
            }), 400

        user_id = get_jwt_identity()

        from flask_jwt_extended import get_jwt
        claims = get_jwt()
        user_type = claims.get('user_type', 'staff')

        hashed_password = generate_password_hash(new_password)

        from apps.home.routes import config as db_config
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        if user_type == 'patient':
            cursor.execute(
                """
                UPDATE nextris.tbuser_patient
                SET password = %s,
                    firstlogin = 0,
                    updated_at = NOW()
                WHERE guid = %s
                """,
                (hashed_password, user_id)
            )
        else:
            cursor.execute(
                """
                UPDATE nextris.tbuser
                SET password = %s,
                    first_login = 0
                WHERE guid = %s
                """,
                (hashed_password, user_id)
            )

        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 404

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({
            'success': True,
            'message': 'Contraseña actualizada exitosamente'
        }), 200

    except Exception as e:
        try:
            connection.rollback()
            cursor.close()
            connection.close()
        except Exception:
            pass
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/auth/user/<user_id>/patientdomains', methods=['GET'])
@jwt_required()
def get_user_patientdomains(user_id):
    """
    Obtener los patientdomains asociados a un usuario
    
    Respuesta:
    {
        "success": true,
        "data": [
            {
                "patientdomain_id": "uuid",
                "patientdomain_name": "GENERAL",
                "created_at": "2024-01-01 10:00:00"
            }
        ]
    }
    """
    try:
        from apps.home.routes import config as db_config
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        # Obtener las relaciones con información del patientdomain
        query = """
            SELECT 
                rup.patientdomain_id,
                pd.description as patientdomain_name,
                rup.created_at
            FROM nextris.rel_user_patientdomain rup
            LEFT JOIN nextris.ispatientdomain pd ON pd.guid = rup.patientdomain_id
            WHERE rup.user_id = %s
            ORDER BY pd.description
        """
        
        cursor.execute(query, (user_id,))
        results = cursor.fetchall()
        
        patientdomains = []
        for row in results:
            patientdomains.append({
                'patientdomain_id': row[0],
                'patientdomain_name': row[1] or 'Sin nombre',
                'created_at': row[2].isoformat() if row[2] else None
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': patientdomains
        }), 200
        
    except Exception as e:
        print(f"[API USER PATIENTDOMAINS] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
