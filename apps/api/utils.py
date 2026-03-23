# -*- encoding: utf-8 -*-
"""
Utilidades compartidas para la API
"""
import psycopg2

def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.services import ConfigService
        config = ConfigService.get_db_config()
        return config
    except:
        return None

def update_examination_status(exam_id):
    """
    Actualiza el estado de un examen basado en sus flags
    Mapea los flags booleanos a letras de estado
    """
    try:
        config = get_db_config()
        if not config:
            return False
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener estado actual de los flags
        query = """
            SELECT isplanned, isadmitted, isexecuted, issuspended, isimage, 
                   isreported, isapproved, isdigitalsigned, ispublicated, isbilled 
            FROM nextris.tbexamination
            WHERE guid = %s
        """
        cursor.execute(query, (exam_id,))
        datos = cursor.fetchone()
        
        if not datos:
            cursor.close()
            connection.close()
            return False
        
        # Mapear los estados a letras
        status = ''
        if datos[0]:  # isplanned
            status += 'P '
        if datos[1]:  # isadmitted
            status += 'A '
        if datos[2]:  # isexecuted
            status += 'E '
        if datos[3]:  # issuspended
            status += 'S '
        if datos[4]:  # isimage
            status += 'I '
        if datos[5]:  # isreported
            status += 'R '
        if datos[6]:  # isapproved
            status += 'AP '
        if datos[7]:  # isdigitalsigned
            status += 'DS '
        if datos[8]:  # ispublicated
            status += 'PU '
        if datos[9]:  # isbilled
            status += 'B '
        
        status = status.strip() if status else 'N'
        
        # Actualizar el campo status
        update_query = "UPDATE nextris.tbexamination SET status = %s WHERE guid = %s"
        cursor.execute(update_query, (status, exam_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] update_examination_status: {str(e)}")
        return False
