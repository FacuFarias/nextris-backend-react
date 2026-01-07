# -*- encoding: utf-8 -*-
"""
API de Administración - Endpoints REST para funciones administrativas
Migrado desde admin_controller.py
"""

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import psycopg2
from psycopg2.extras import RealDictCursor
from apps.api import api_blueprint
from datetime import datetime


from apps.api.utils import get_db_config, update_examination_status





@api_blueprint.route('/admin/examinations/<exam_id>/unreport', methods=['POST'])
@jwt_required()
def unreport_examination(exam_id):
    """
    Quita el estado de reportado a un examen
    
    Path:
    - exam_id: GUID del examen
    
    Respuesta:
    {
        "success": true,
        "message": "Reporte removido exitosamente"
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
        
        # Verificar que el examen existe
        cursor.execute(
            "SELECT guid FROM nextris.tbexamination WHERE guid = %s",
            (exam_id,)
        )
        
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        # Quitar el estado de reportado (usar 0 para smallint)
        query = "UPDATE nextris.tbexamination SET isreported = 0 WHERE guid = %s"
        cursor.execute(query, (exam_id,))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        # Actualizar el campo status basado en flags
        update_examination_status(exam_id)
        
        return jsonify({
            'success': True,
            'message': 'Reporte removido exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/admin/examinations/<exam_id>/status', methods=['PATCH'])
@jwt_required()
def update_examination_status_endpoint(exam_id):
    """
    Actualiza el estado de un examen
    
    Path:
    - exam_id: GUID del examen
    
    Body JSON:
    {
        "status": "nuevo estado"
    }
    
    Respuesta:
    {
        "success": true,
        "message": "Estado actualizado exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        new_status = data.get('status')
        
        if new_status is None:
            return jsonify({
                'success': False,
                'message': 'El campo status es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el examen existe
        cursor.execute(
            "SELECT guid FROM nextris.tbexamination WHERE guid = %s",
            (exam_id,)
        )
        
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        # Actualizar el estado
        query = "UPDATE nextris.tbexamination SET status = %s WHERE guid = %s"
        cursor.execute(query, (new_status, exam_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Estado actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/admin/examinations', methods=['GET'])
@jwt_required()
def get_examinations_admin():
    """
    Obtiene lista de exámenes para administración
    
    Query params:
    - limit: número máximo de resultados (default: 100)
    - offset: número de resultados a saltar (default: 0)
    - status: filtrar por estado
    - from_date: filtrar desde fecha (YYYY-MM-DD)
    - to_date: filtrar hasta fecha (YYYY-MM-DD)
    
    Respuesta:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "localacc": "...",
                "createdon": "DD/MM/YYYY HH:MM",
                "status": "...",
                "patient_name": "...",
                "patient_dni": "...",
                "study_type": "..."
            }
        ],
        "total": 150
    }
    """
    try:
        # Obtener parámetros de query
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        status_filter = request.args.get('status')
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Construir query con filtros
        where_clauses = []
        params = []
        
        if status_filter:
            where_clauses.append("e.status = %s")
            params.append(status_filter)
        
        if from_date:
            where_clauses.append("e.createdon >= %s")
            params.append(from_date)
        
        if to_date:
            where_clauses.append("e.createdon <= %s")
            params.append(to_date)
        
        where_sql = " AND " + " AND ".join(where_clauses) if where_clauses else ""
        
        # Query para obtener el total
        count_query = f"""
            SELECT COUNT(*)
            FROM nextris.tbexamination e
            WHERE 1=1 {where_sql}
        """
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Query principal
        query = f"""
            SELECT 
                e.guid, e.localacc, e.createdon, e.status,
                p.name, p.surname, p.nationalcode,
                s.description as study_type
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient p ON p.patientid = e.idpatient
            LEFT JOIN nextris.isstudytype s ON s.guid = e.studytype_id
            WHERE 1=1 {where_sql}
            ORDER BY e.createdon DESC
            LIMIT %s OFFSET %s
        """
        
        params.extend([limit, offset])
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        # Formatear resultados
        examinations = []
        for row in results:
            examinations.append({
                'guid': row[0],
                'localacc': row[1],
                'createdon': row[2].strftime('%d/%m/%Y %H:%M') if row[2] else '',
                'status': row[3],
                'patient_name': f"{row[4]} {row[5]}" if row[4] and row[5] else '',
                'patient_dni': row[6] or '',
                'study_type': row[7] or ''
            })
        
        return jsonify({
            'success': True,
            'data': examinations,
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/admin/equipment', methods=['GET'])
@jwt_required()
def get_equipment_admin():
    """
    Obtiene lista completa de equipos/máquinas
    
    Respuesta:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "...",
                "aetitle": "...",
                "isactive": true
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
            SELECT guid, description, aetitle, isactive
            FROM nextris.isequipment
            ORDER BY description
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        # Formatear resultados
        equipment = []
        for row in results:
            equipment.append({
                'guid': row[0],
                'description': row[1],
                'aetitle': row[2],
                'isactive': bool(row[3]) if row[3] is not None else False
            })
        
        return jsonify({
            'success': True,
            'data': equipment
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/admin/equipment/by-study-type', methods=['POST'])
@jwt_required()
def get_equipment_by_study_type():
    """
    Obtiene equipos disponibles para un tipo de estudio específico
    
    Body JSON:
    {
        "study_type_id": "guid-del-tipo-de-estudio"
    }
    
    Respuesta:
    {
        "success": true,
        "data": [
            {
                "guid": "...",
                "description": "...",
                "aetitle": "..."
            }
        ]
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        study_type_id = data.get('study_type_id')
        
        if not study_type_id:
            return jsonify({
                'success': False,
                'message': 'El campo study_type_id es requerido'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Intentar con diferentes nombres de tabla de relación
        queries = [
            # Opción 1: rel_equip_studytype
            """
                SELECT e.guid, e.description, e.aetitle
                FROM nextris.isequipment e
                INNER JOIN nextris.rel_equip_studytype res ON res.equip_id = e.guid
                WHERE res.studytype_id = %s
                AND e.isactive = true
                ORDER BY e.description
            """,
            # Opción 2: rel_equipment_studytype
            """
                SELECT e.guid, e.description, e.aetitle
                FROM nextris.isequipment e
                INNER JOIN nextris.rel_equipment_studytype res ON res.equipment_id = e.guid
                WHERE res.studytype_id = %s
                AND e.isactive = true
                ORDER BY e.description
            """,
            # Opción 3: isrel_studytype_equipment
            """
                SELECT e.guid, e.description, e.aetitle
                FROM nextris.isequipment e
                INNER JOIN nextris.isrel_studytype_equipment res ON res.equipment_id = e.guid
                WHERE res.studytype_id = %s
                AND e.isactive = true
                ORDER BY e.description
            """
        ]
        
        results = []
        for query in queries:
            try:
                cursor.execute(query, (study_type_id,))
                results = cursor.fetchall()
                break  # Si funciona, salir del loop
            except Exception:
                continue  # Probar siguiente query
        
        # Si ninguna query funcionó, retornar lista vacía
        if not results:
            cursor.close()
            connection.close()
            return jsonify({
                'success': True,
                'data': [],
                'message': 'No se encontraron equipos o tabla de relación no existe'
            }), 200
        
        cursor.close()
        connection.close()
        
        # Formatear resultados
        equipment = []
        for row in results:
            equipment.append({
                'guid': row[0],
                'description': row[1],
                'aetitle': row[2]
            })
        
        return jsonify({
            'success': True,
            'data': equipment
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/admin/workdays', methods=['GET'])
@jwt_required()
def get_workdays():
    """
    Obtiene la lista de días de la semana
    
    Respuesta:
    {
        "success": true,
        "data": [
            {"id": 1, "name": "Lunes"},
            {"id": 2, "name": "Martes"},
            ...
        ]
    }
    """
    try:
        days = [
            {'id': 1, 'name': 'Lunes'},
            {'id': 2, 'name': 'Martes'},
            {'id': 3, 'name': 'Miércoles'},
            {'id': 4, 'name': 'Jueves'},
            {'id': 5, 'name': 'Viernes'},
            {'id': 6, 'name': 'Sábado'},
            {'id': 7, 'name': 'Domingo'}
        ]
        
        return jsonify({
            'success': True,
            'data': days
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
