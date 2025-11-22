"""
Servicio de base de datos para el sistema RIS
Maneja conexiones y operaciones comunes de base de datos
"""

import psycopg2
from contextlib import contextmanager
from .config_service import ConfigService


class DatabaseService:
    """Servicio para gestión de operaciones de base de datos"""

    @staticmethod
    def get_connection():
        """Obtiene una conexión a la base de datos"""
        config = ConfigService.get_db_config()
        return psycopg2.connect(**config)

    @staticmethod
    @contextmanager
    def get_db_cursor():
        """Context manager para obtener cursor de base de datos con manejo automático de conexión"""
        connection = None
        cursor = None
        try:
            connection = DatabaseService.get_connection()
            cursor = connection.cursor()
            yield cursor, connection
        except Exception as e:
            if connection:
                connection.rollback()
            raise e
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    @staticmethod
    def execute_query(query, params=None, fetch_one=False, fetch_all=True, commit=False):
        """
        Ejecuta una consulta SQL y retorna resultados
        
        Args:
            query: Consulta SQL a ejecutar
            params: Parámetros para la consulta
            fetch_one: Si True, retorna solo un resultado
            fetch_all: Si True, retorna todos los resultados
            commit: Si True, hace commit de la transacción
        """
        with DatabaseService.get_db_cursor() as (cursor, connection):
            cursor.execute(query, params)
            
            if commit:
                connection.commit()
            
            # Detectar si la consulta devuelve resultados
            query_upper = query.strip().upper()
            is_returning_query = 'RETURNING' in query_upper
            is_select_query = query_upper.startswith('SELECT')
            
            # Solo hacer fetch si es una consulta que devuelve resultados
            if is_select_query or is_returning_query:
                if fetch_one:
                    return cursor.fetchone()
                elif fetch_all:
                    return cursor.fetchall()
            
            # Para INSERT/UPDATE/DELETE sin RETURNING, retornar el número de filas afectadas
            return cursor.rowcount

    @staticmethod
    def execute_transaction(queries_and_params, fetch_results=False):
        """
        Ejecuta múltiples consultas en una transacción
        
        Args:
            queries_and_params: Lista de tuplas (query, params)
            fetch_results: Si True, retorna los resultados de cada consulta
        """
        results = []
        with DatabaseService.get_db_cursor() as (cursor, connection):
            try:
                for query, params in queries_and_params:
                    cursor.execute(query, params)
                    if fetch_results:
                        results.append(cursor.fetchall())
                
                connection.commit()
                return results if fetch_results else True
                
            except Exception as e:
                connection.rollback()
                raise e

    # Métodos específicos para operaciones comunes
    
    @staticmethod
    def get_patient_by_id(patient_id):
        """Obtiene información de un paciente por ID"""
        query = "SELECT PatientId, Surname, Name, NationalCode, SexCode FROM nextris.datapatient WHERE PatientId = %s"
        return DatabaseService.execute_query(query, (patient_id,), fetch_one=True)

    @staticmethod
    def get_patient_by_guid(guid):
        """Obtiene información de un paciente por GUID"""
        query = "SELECT PatientId, Surname, Name, NationalCode, SexCode FROM nextris.datapatient WHERE Guid = %s"
        return DatabaseService.execute_query(query, (guid,), fetch_one=True)

    @staticmethod
    def get_examination_by_guid(exam_guid):
        """Obtiene información de un examen por GUID"""
        query = """
            SELECT guid, studytype_id, idpatient, idreferringphysician, 
                   idrequestingphysician, status, createdon, isreported, isimage, 
                   studyinstanceuid, numberofviews, stat, othersdetails, 
                   laterality_id, history, clinicalquestion 
            FROM nextris.tbexamination 
            WHERE guid = %s
        """
        return DatabaseService.execute_query(query, (exam_guid,), fetch_one=True)

    @staticmethod
    def get_study_type_description(study_type_guid):
        """Obtiene la descripción de un tipo de estudio"""
        query = "SELECT description FROM nextris.isstudytype WHERE guid = %s"
        result = DatabaseService.execute_query(query, (study_type_guid,), fetch_one=True)
        return result[0] if result else None

    @staticmethod
    def get_equipment_by_guid(equipment_guid):
        """Obtiene información de un equipo por GUID"""
        query = "SELECT Guid, Description, Aetitle, IdModality FROM nextris.isequipment WHERE guid = %s"
        return DatabaseService.execute_query(query, (equipment_guid,), fetch_one=True)

    @staticmethod
    def get_user_by_guid(user_guid):
        """Obtiene información de un usuario por GUID"""
        query = "SELECT UserName FROM nextris.tbuser WHERE Guid = %s"
        result = DatabaseService.execute_query(query, (user_guid,), fetch_one=True)
        return result[0] if result else None

    @staticmethod
    def get_severity_description(severity_guid):
        """Obtiene la descripción de una severidad"""
        query = "SELECT Description FROM nextris.IsSeverity WHERE Guid = %s"
        result = DatabaseService.execute_query(query, (severity_guid,), fetch_one=True)
        return result[0] if result else None

    @staticmethod
    def set_timezone():
        """Establece la zona horaria para la sesión actual"""
        query = "SET TIME ZONE 'America/Argentina/Buenos_Aires'"
        return DatabaseService.execute_query(query, commit=True)