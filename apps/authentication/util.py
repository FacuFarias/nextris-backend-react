# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, redirect, url_for, abort
from functools import wraps

def hash_pass(password):
    """Hash a password for storing using Werkzeug."""
    return generate_password_hash(password)

def verify_pass(provided_password, stored_password):
    """Verify a stored password against one provided by user using Werkzeug."""
    # Si no hay contraseña almacenada, retornar False
    if stored_password is None or stored_password == 'None' or stored_password == '':
        return False
    
    try:
        return check_password_hash(stored_password, provided_password)
    except (AttributeError, ValueError) as e:
        # Si hay cualquier error con el hash, retornar False
        print(f"[ERROR] Error al verificar contraseña: {e}")
        return False

def require_role(*allowed_roles):
    """
    Decorador para restringir acceso a rutas basado en roles de usuario.
    
    Args:
        *allowed_roles: Lista de roles permitidos para acceder a la ruta
    
    Usage:
        @require_role('Sysadmin', 'Administrativo')
        def admin_function():
            return "Solo admins y sysadmins pueden ver esto"
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Verificar si el usuario está logueado y tiene un tipo de usuario
            if 'user_type' not in session:
                return redirect(url_for('authentication_blueprint.login'))
            
            # Verificar si el usuario tiene uno de los roles permitidos
            user_role = session.get('user_type')
            if user_role not in allowed_roles:
                # Usuario no autorizado - devolver error 403
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_user_permissions(user_type):
    """
    Retorna una lista de módulos/secciones a los que el usuario tiene acceso
    según su rol.
    
    Args:
        user_type (str): Tipo de usuario
        
    Returns:
        list: Lista de permisos/módulos permitidos
    """
    permissions = {
        'Sysadmin': ['pacientes', 'citas', 'admision', 'ejecucion', 'redaccion', 'distribucion', 'configuraciones', 'preferencias'],
        'Administrativo': ['pacientes', 'citas', 'admision', 'distribucion'],
        'Tecnico': ['pacientes', 'ejecucion'],
        'Medico': ['pacientes', 'redaccion', 'distribucion']
    }
    
    return permissions.get(user_type, [])
