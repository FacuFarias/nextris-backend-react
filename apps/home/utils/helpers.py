"""
Utilidades generales para el sistema RIS
"""

import os
from datetime import datetime
import pytz
from flask import session
from apps.authentication.util import get_user_permissions


def get_segment(request):
    """Helper - Extract current page name from request"""
    try:
        segment = request.endpoint.split('.')[-1]
        return segment if segment != 'index' else None
    except:
        return None


def user_has_permission(required_permission):
    """
    Verifica si el usuario actual tiene un permiso específico
    
    Args:
        required_permission (str): Permiso requerido
        
    Returns:
        bool: True si el usuario tiene el permiso
    """
    user_type = session.get('user_type')
    if not user_type:
        return False
    
    user_permissions = get_user_permissions(user_type)
    return required_permission in user_permissions


def get_current_user_permissions():
    """
    Obtiene la lista de permisos del usuario actual
    
    Returns:
        list: Lista de permisos del usuario
    """
    user_type = session.get('user_type')
    if not user_type:
        return []
    
    return get_user_permissions(user_type)


def format_datetime_for_timezone(dt, timezone_str="America/Argentina/Buenos_Aires"):
    """
    Formatea una fecha/hora para una zona horaria específica
    """
    if dt is None:
        return None
        
    if isinstance(dt, str):
        return dt
        
    try:
        local_tz = pytz.timezone(timezone_str)
        if dt.tzinfo is None:
            # Si no tiene timezone, asumir que es UTC
            dt = pytz.utc.localize(dt)
        
        local_dt = dt.astimezone(local_tz)
        return local_dt.strftime('%d/%m/%Y %H:%M')
    except:
        return dt.strftime('%d/%m/%Y %H:%M') if hasattr(dt, 'strftime') else str(dt)


def ensure_directory_exists(directory_path):
    """
    Asegura que un directorio existe, creándolo si es necesario
    """
    if not os.path.exists(directory_path):
        os.makedirs(directory_path, exist_ok=True)
    return directory_path


def safe_get_env(key, default=None, cast_type=str):
    """
    Obtiene una variable de entorno de forma segura con casting de tipo
    """
    value = os.getenv(key, default)
    if value is None:
        return default
        
    try:
        if cast_type == bool:
            return value.lower() in ('true', '1', 'yes', 'on')
        elif cast_type == int:
            return int(value)
        elif cast_type == float:
            return float(value)
        else:
            return cast_type(value)
    except (ValueError, TypeError):
        return default


def generate_accession_number(prefix="ACC", last_number=0):
    """
    Genera un nuevo número de acceso
    """
    return f"{prefix}{last_number + 1:03d}"


def generate_admission_number(prefix="ADM", last_number=0):
    """
    Genera un nuevo número de admisión
    """
    return f"{prefix}{last_number + 1:03d}"


def validate_guid(guid_string):
    """
    Valida si una cadena es un GUID válido
    """
    import re
    guid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(guid_pattern.match(guid_string))


def sanitize_filename(filename):
    """
    Sanitiza un nombre de archivo removiendo caracteres problemáticos
    """
    import re
    # Remover caracteres no válidos para nombres de archivo
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remover espacios al inicio y final
    filename = filename.strip()
    # Limitar longitud
    return filename[:255] if len(filename) > 255 else filename


def parse_hl7_datetime(hl7_datetime_str):
    """
    Parsea una fecha/hora en formato HL7 (YYYYMMDDHHMMSS)
    """
    try:
        if len(hl7_datetime_str) >= 8:
            # Formato básico YYYYMMDD
            dt = datetime.strptime(hl7_datetime_str[:8], '%Y%m%d')
            
            if len(hl7_datetime_str) >= 14:
                # Formato completo YYYYMMDDHHMMSS
                dt = datetime.strptime(hl7_datetime_str[:14], '%Y%m%d%H%M%S')
            elif len(hl7_datetime_str) >= 12:
                # Formato YYYYMMDDHHMM
                dt = datetime.strptime(hl7_datetime_str[:12], '%Y%m%d%H%M')
            elif len(hl7_datetime_str) >= 10:
                # Formato YYYYMMDDHH
                dt = datetime.strptime(hl7_datetime_str[:10], '%Y%m%d%H')
                
            return dt
    except ValueError:
        pass
    
    return None


def build_patient_full_name(first_name, last_name):
    """
    Construye el nombre completo de un paciente
    """
    names = [name.strip() for name in [first_name, last_name] if name and name.strip()]
    return ' '.join(names) if names else ''


def mask_sensitive_data(data, fields_to_mask=None):
    """
    Enmascara datos sensibles para logging
    """
    if fields_to_mask is None:
        fields_to_mask = ['password', 'token', 'secret', 'key']
    
    if isinstance(data, dict):
        masked_data = {}
        for key, value in data.items():
            if any(sensitive_field in key.lower() for sensitive_field in fields_to_mask):
                masked_data[key] = '*' * 8
            else:
                masked_data[key] = mask_sensitive_data(value, fields_to_mask)
        return masked_data
    elif isinstance(data, list):
        return [mask_sensitive_data(item, fields_to_mask) for item in data]
    else:
        return data