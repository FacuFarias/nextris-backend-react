"""
Controller para funciones administrativas del sistema RIS
Migrado masivamente desde routes.py para reducir el archivo principal
"""

from flask import Blueprint, request, jsonify, render_template
import os
import psycopg2
from apps.home.services.database_service import DatabaseService
from apps.home.services.config_service import ConfigService

# Crear blueprint para administración
admin_bp = Blueprint('admin', __name__, url_prefix='/api')

# Obtener configuración de BD
config = ConfigService.get_db_config()

@admin_bp.route('/quitar_definitivo', methods=['POST'])
def quitar_definitivo():
    """Quita un reporte definitivo (cambia IsReported a 0)"""
    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        reporteid = request.get_json()
        exam_id = reporteid.get('id')
        
        if not exam_id:
            return jsonify({'error': 'Falta el ID del examen'}), 400
        
        query = "UPDATE nextris.tbexamination SET IsReported=0 WHERE Guid=%s"
        cursor.execute(query, (exam_id,))
        connection.commit()
        
        # Actualizar estado si existe la función
        try:
            updatestatus(exam_id)
        except:
            pass  # Si no existe la función, continuar
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Reporte removido exitosamente'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/actualizar_examen_status', methods=['POST'])
def actualizar_examen_status():
    """Actualiza el estado de un examen"""
    try:
        data = request.get_json()
        exam_id = data.get('exam_id')
        new_status = data.get('status')
        
        if not exam_id or new_status is None:
            return jsonify({'error': 'Faltan parámetros requeridos'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = "UPDATE nextris.tbexamination SET Status=%s WHERE Guid=%s"
        cursor.execute(query, (new_status, exam_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({'success': True, 'message': 'Estado actualizado exitosamente'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/get_exams_adm', methods=['GET'])
def get_exams_adm():
    """Obtiene lista de exámenes para administración"""
    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT 
                e.guid, e.localacc, e.createdon, e.status,
                p.name, p.surname, p.nationalcode,
                s.description as study_type
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient p ON p.patientid = e.idpatient
            LEFT JOIN nextris.isstudytype s ON s.guid = e.studytype_id
            ORDER BY e.createdon DESC
            LIMIT 100
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        examenes = []
        for row in results:
            examenes.append({
                'guid': row[0],
                'localacc': row[1],
                'createdon': row[2].strftime('%d/%m/%Y %H:%M') if row[2] else '',
                'status': row[3],
                'patient_name': f"{row[4]} {row[5]}" if row[4] and row[5] else '',
                'patient_dni': row[6] or '',
                'study_type': row[7] or ''
            })
        
        return jsonify(examenes)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/get_equip_for_exam', methods=['POST'])
def get_equip_for_exam():
    """Obtiene equipos disponibles para un tipo de examen"""
    try:
        data = request.get_json()
        study_type_id = data.get('study_type_id')
        
        if not study_type_id:
            return jsonify({'error': 'Falta study_type_id'}), 400
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            SELECT e.guid, e.description, e.aetitle
            FROM nextris.isequipment e
            INNER JOIN nextris.rel_equip_studytype res ON res.equip_id = e.guid
            WHERE res.studytype_id = %s
            AND e.isactive = true
        """
        cursor.execute(query, (study_type_id,))
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        equipos = []
        for row in results:
            equipos.append({
                'guid': row[0],
                'description': row[1],
                'aetitle': row[2]
            })
        
        return jsonify(equipos)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/get_mach', methods=['GET'])
def get_mach():
    """Obtiene lista de máquinas/equipos"""
    try:
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
        
        maquinas = []
        for row in results:
            maquinas.append({
                'guid': row[0],
                'description': row[1],
                'aetitle': row[2],
                'isactive': row[3]
            })
        
        return jsonify(maquinas)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/get_days', methods=['GET'])
def get_days():
    """Obtiene configuración de días laborables"""
    try:
        # Retornar días de la semana estándar
        days = [
            {'id': 1, 'name': 'Lunes'},
            {'id': 2, 'name': 'Martes'},
            {'id': 3, 'name': 'Miércoles'},
            {'id': 4, 'name': 'Jueves'},
            {'id': 5, 'name': 'Viernes'},
            {'id': 6, 'name': 'Sábado'},
            {'id': 7, 'name': 'Domingo'}
        ]
        
        return jsonify(days)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Función auxiliar para compatibilidad
def updatestatus(exam_id):
    """Función para actualizar estado de examen basado en flags"""
    try:
        print(f"[DEBUG] Actualizando estado para examen: {exam_id}")
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Obtener estado actual de los flags
        query = """
            SELECT isplanned, isadmitted, isexecuted, issuspended, isimage, isreported, isapproved, isdigitalsigned, ispublicated, isbilled 
            FROM nextris.tbexamination
            WHERE Guid = %s
        """
        cursor.execute(query, (exam_id,))
        datos = cursor.fetchone()
        
        if not datos:
            print(f"[ERROR] No se encontró examen con ID: {exam_id}")
            return 'error'
        
        print(f"[DEBUG] Flags del examen: {datos}")
        
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
            status += 'U '
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
        
        status = status.strip() if status else 'N'  # Si no hay estados, poner 'N' de Ninguno
        
        print(f"[DEBUG] Nuevo status calculado: {status}")
        
        # Actualizar el campo status
        update_query = "UPDATE nextris.tbexamination SET status = %s WHERE Guid = %s"
        cursor.execute(update_query, (status, exam_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        print(f"[SUCCESS] Estado actualizado exitosamente a: {status}")
        return 'success'
        
    except Exception as e:
        print(f"[ERROR] Error updating status: {e}")
        return 'error'


@admin_bp.route('/get_lista_de_equipos', methods=['GET'])
def get_lista_de_equipos():
    """Obtiene la lista de equipos disponibles"""
    try:
        print("[DEBUG] get_lista_de_equipos endpoint called")
        
        # Intentar primero con la tabla isequipment
        query = """
            SELECT guid, title, description 
            FROM nextris.isequipment 
            WHERE active = true
            ORDER BY title
        """
        
        try:
            result = DatabaseService.execute_query(query)
        except Exception as e:
            print(f"[DEBUG] Error with isequipment table: {e}")
            # Si falla, intentar con una estructura diferente
            query = """
                SELECT guid, name as title, description 
                FROM nextris.isequipment 
                ORDER BY name
            """
            try:
                result = DatabaseService.execute_query(query)
            except Exception as e2:
                print(f"[DEBUG] Error with alternative structure: {e2}")
                # Como fallback, devolver lista vacía
                return jsonify([])
        
        # Formatear los resultados
        equipos = []
        for row in result:
            equipos.append([
                row[0],  # guid
                row[1] or '',  # title
                row[2] or '' if len(row) > 2 else ''  # description
            ])
        
        print(f"[DEBUG] Returning {len(equipos)} equipos")
        return jsonify(equipos)
        
    except Exception as e:
        print(f"[ERROR] Error getting equipos list: {str(e)}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/get_block_prestacion_per_equipo')
def get_block_prestacion_per_equipo():
    """Retorna el template HTML para prestaciones por equipo"""
    return render_template('includes/blocks/block_prestacion_per_equipo.html')