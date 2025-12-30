# -*- encoding: utf-8 -*-
"""
API REST para gestión de ejecución de órdenes de examen
Endpoints para ejecutar, cancelar y obtener detalles de órdenes de examen
"""

from flask import request, jsonify
from flask_jwt_extended import jwt_required
import psycopg2
from apps.api import api_blueprint
from datetime import datetime


def get_db_config():
    """Obtener configuración de base de datos"""
    try:
        from apps.home.routes import config
        return config
    except:
        return None


def get_user_locations(user_id, connection):
    """Obtener ubicaciones del usuario"""
    cursor = connection.cursor()
    cursor.execute(
        "SELECT location_id FROM nextris.rel_user_location WHERE user_id = %s",
        (user_id,)
    )
    locations = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return locations


@api_blueprint.route('/executions/orders', methods=['GET'])
@jwt_required()
def get_execution_orders():
    """
    Obtiene órdenes de exámenes pendientes de ejecución
    Filtradas por ubicaciones del usuario y estado (no ejecutadas)
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "created_on": "datetime",
                "patient_surname": "apellido",
                "patient_name": "nombre",
                "study_type": "descripción",
                "status": "estado",
                "equipment": "nombre equipo",
                "admission_number": "ADM001",
                "accession_number": "ACC001"
            },
            ...
        ]
    }
    """
    try:
        from flask_jwt_extended import get_jwt_identity
        
        user_id = get_jwt_identity()
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**db_config)
        user_locations = get_user_locations(user_id, connection)
        
        if not user_locations:
            connection.close()
            return jsonify({
                'success': True,
                'data': []
            }), 200
        
        cursor = connection.cursor()
        
        location_placeholders = ','.join(['%s'] * len(user_locations))
        
        query = f"""
            SELECT 
                e.Guid, e.CreatedOn,
                dp.Surname, dp.Name,
                st.Description as study_type,
                e.Status,
                eq.Description as equipment,
                e.admisionnumber, e.LocalAcc
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            WHERE e.IsExecuted = 0
            AND eq.location_id IN ({location_placeholders})
            ORDER BY e.CreatedOn DESC
        """
        
        cursor.execute(query, user_locations)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'guid': str(row[0]),
                'created_on': row[1].isoformat() if row[1] else None,
                'patient_surname': row[2] or '',
                'patient_name': row[3] or '',
                'study_type': row[4] or '',
                'status': row[5] or '',
                'equipment': row[6] or '',
                'admission_number': row[7] or '',
                'accession_number': row[8] or ''
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': results
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/executions/examination/<exam_guid>/details', methods=['GET'])
@jwt_required()
def get_execution_examination_details(exam_guid):
    """
    Obtiene detalles completos de un examen para ejecución
    
    Path Parameters:
    - exam_guid: GUID del examen
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid",
            "study_type": "descripción",
            "patient_name": "nombre completo",
            "status": "estado",
            "created_on": "datetime",
            "is_reported": boolean,
            "study_instance_uid": "uid",
            "history": "historia clínica",
            "clinical_question": "pregunta clínica",
            "laterality": "lateralidad",
            "stat": boolean,
            "number_of_views": número,
            "other_details": "otros detalles"
        }
    }
    """
    try:
        db_config = get_db_config()
        if not db_config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        query = """
            SELECT 
                e.Guid, e.studytype_id, e.IdPatient, e.Status, e.CreatedOn,
                e.isreported, e.StudyInstanceUid, e.history, e.clinicalquestion,
                e.laterality_id, e.stat, e.numberofviews, e.othersdetails
            FROM nextris.tbexamination e
            WHERE e.Guid = %s
        """
        
        cursor.execute(query, (exam_guid,))
        exam_data = cursor.fetchone()
        
        if not exam_data:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        # Obtener descripción del tipo de estudio
        cursor.execute(
            "SELECT Description FROM nextris.isstudytype WHERE Guid = %s",
            (exam_data[1],)
        )
        study_type_row = cursor.fetchone()
        study_type = study_type_row[0] if study_type_row else ''
        
        # Obtener datos del paciente
        cursor.execute(
            "SELECT Surname, Name FROM nextris.datapatient WHERE Guid = %s",
            (exam_data[2],)
        )
        patient_row = cursor.fetchone()
        patient_name = f"{patient_row[0]} {patient_row[1]}" if patient_row else ''
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'guid': str(exam_data[0]),
                'study_type': study_type,
                'patient_name': patient_name,
                'status': exam_data[3] or '',
                'created_on': exam_data[4].isoformat() if exam_data[4] else None,
                'is_reported': bool(exam_data[5]),
                'study_instance_uid': exam_data[6] or '',
                'history': exam_data[7] or '',
                'clinical_question': exam_data[8] or '',
                'laterality': exam_data[9] or '',
                'stat': bool(exam_data[10]),
                'number_of_views': exam_data[11],
                'other_details': exam_data[12] or ''
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/executions/examination/<exam_guid>/execute', methods=['POST'])
@jwt_required()
def execute_examination_order(exam_guid):
    """
    Ejecuta un examen actualizando su estado y detalles clínicos
    
    Path Parameters:
    - exam_guid: GUID del examen
    
    Body JSON:
    {
        "history": "historia clínica (opcional)",
        "clinical_question": "pregunta clínica (opcional)",
        "laterality": "lateralidad (opcional)",
        "stat": boolean (opcional),
        "number_of_views": número (opcional),
        "other_details": "otros detalles (opcional)"
    }
    
    Returns:
    {
        "success": true,
        "message": "Examen ejecutado exitosamente"
    }
    """
    try:
        data = request.get_json() or {}
        
        db_config = get_db_config()
        if not db_config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        # Función para convertir 'no clasifica' a None
        def null_if_no_clasifica(val):
            return None if val == 'no clasifica' else val
        
        history = null_if_no_clasifica(data.get('history', 'no clasifica'))
        clinical_question = null_if_no_clasifica(data.get('clinical_question', 'no clasifica'))
        laterality = null_if_no_clasifica(data.get('laterality', 'no clasifica'))
        stat = data.get('stat', False)
        number_of_views = null_if_no_clasifica(data.get('number_of_views', 'no clasifica'))
        other_details = null_if_no_clasifica(data.get('other_details', 'no clasifica'))
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        query = """
            UPDATE nextris.tbexamination
            SET IsExecuted = 1,
                history = %s,
                clinicalquestion = %s,
                laterality_id = %s,
                stat = %s::boolean,
                numberofviews = %s,
                othersdetails = %s
            WHERE Guid = %s
        """
        
        cursor.execute(
            query,
            (history, clinical_question, laterality, stat, number_of_views, 
             other_details, exam_guid)
        )
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Examen ejecutado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/executions/examination/<exam_guid>/cancel', methods=['POST'])
@jwt_required()
def cancel_examination_execution_order(exam_guid):
    """
    Cancela la ejecución de un examen (marca como no ejecutado)
    
    Path Parameters:
    - exam_guid: GUID del examen
    
    Returns:
    {
        "success": true,
        "message": "Examen cancelado exitosamente"
    }
    """
    try:
        db_config = get_db_config()
        if not db_config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        
        query = """
            UPDATE nextris.tbexamination
            SET IsExecuted = 0
            WHERE Guid = %s
        """
        
        cursor.execute(query, (exam_guid,))
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Examen cancelado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
