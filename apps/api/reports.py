# -*- encoding: utf-8 -*-
"""
API REST para gestión de reportes médicos y plantillas predefinidas
Endpoints para CRUD de reportes, plantillas y generación de PDFs
"""

from flask import request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import psycopg2
from apps.api import api_blueprint
import uuid
import os


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


# ====================================================================
# ENDPOINTS PARA REDACCIÓN DE INFORMES
# ====================================================================

@api_blueprint.route('/examinations/for-reporting', methods=['GET'])
@jwt_required()
def get_examinations_for_reporting():
    """
    Obtiene lista de exámenes listos para reportar
    Filtra por ubicaciones del usuario
    
    Query Parameters:
    - status (optional): Filtrar por estado (default: todos)
    - show_reported (optional): true para incluir exámenes reportados (isreported=1)
    - show_ready (optional): true para incluir exámenes listos para reportar (isreported=0)
    - assigned_to_me (optional): true para mostrar solo exámenes asignados al usuario actual
    - page (optional): Número de página (default: 1)
    - per_page (optional): Items por página (default: 50, max: 100)
    
    Nota: Si show_reported y show_ready están activos simultáneamente, se muestran ambos tipos.
          Si ninguno está activo, se muestran todos por defecto.
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "patient_name": "nombre completo",
                "patient_dni": "dni",
                "study_type": "descripción",
                "admission_number": "ADM001",
                "accession_number": "ACC001",
                "created_on": "datetime",
                "status": "estado",
                "is_reported": false,
                "is_executed": true,
                "is_image": true,
                "study_instance_uid": "1.2.840...",
                "equipment": "equipo",
                "location": "ubicación",
                "assigned_to": "uuid del médico asignado"
            }
        ],
        "total": 150,
        "page": 1,
        "per_page": 50
    }
    """
    try:
        user_id = get_jwt_identity()
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        # Parámetros de paginación
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        per_page = min(per_page, 100)
        offset = (page - 1) * per_page
        
        # Filtros opcionales
        status_filter = request.args.get('status')
        show_reported = request.args.get('show_reported', 'false').lower() == 'true'
        show_ready = request.args.get('show_ready', 'false').lower() == 'true'
        assigned_to_me = request.args.get('assigned_to_me', 'false').lower() == 'true'
        
        connection = psycopg2.connect(**config)
        user_locations = get_user_locations(user_id, connection)
        
        if not user_locations:
            connection.close()
            return jsonify({
                'success': True,
                'data': {
                    'data': [],
                    'page': page,
                    'per_page': per_page,
                    'total': 0
                }
            }), 200
        
        cursor = connection.cursor()
        
        location_placeholders = ','.join(['%s'] * len(user_locations))
        
        # Query base - exámenes ejecutados
        # Lógica de filtrado por estado de reporte:
        # - Si ambos show_reported y show_ready están activos: mostrar ambos (sin filtro)
        # - Si solo show_reported: mostrar solo reportados (isreported=1)
        # - Si solo show_ready: mostrar solo listos/no reportados (isreported=0)
        # - Si ninguno está activo: mostrar todos por defecto
        if show_reported and show_ready:
            # Ambos activos: mostrar todo
            reported_filter = ""
        elif show_reported:
            # Solo reportados
            reported_filter = "AND e.IsReported = 1"
        elif show_ready:
            # Solo listos (no reportados)
            reported_filter = "AND (e.IsReported IS NULL OR e.IsReported = 0)"
        else:
            # Ninguno activo: mostrar todo por defecto
            reported_filter = ""
        
        base_query = f"""
            SELECT e.Guid, 
                   CONCAT(dp.Name, ' ', dp.Surname) as patient_name,
                   dp.nationalcode,
                   st.Description as study_type,
                   e.AdmisionNumber,
                   e.LocalAcc,
                   e.CreatedOn,
                   e.Status,
                   COALESCE(e.IsReported, 0) as is_reported,
                   COALESCE(e.IsExecuted, 0) as is_executed,
                   COALESCE(e.isimage, 0) as is_image,
                   e.studyinstanceuid,
                   eq.Description as equipment,
                   loc.name as location,
                   e.assignto
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.Guid
            LEFT JOIN nextris.isequipment eq ON e.IdEquipment = eq.Guid
            LEFT JOIN nextris.tblocation loc ON eq.location_id = loc.guid
            WHERE eq.location_id IN ({location_placeholders})
            AND e.IsExecuted = 1
            {reported_filter}
        """
        
        params = list(user_locations)
        
        # Aplicar filtro de estado si se proporciona
        if status_filter:
            base_query += " AND e.Status = %s"
            params.append(status_filter)
        
        # Aplicar filtro de asignación si se solicita
        if assigned_to_me:
            base_query += " AND e.assignto = %s"
            params.append(user_id)
        
        # Contar total
        count_query = f"SELECT COUNT(*) FROM ({base_query}) AS count_table"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        
        # Query con paginación
        query = base_query + """
            ORDER BY e.CreatedOn DESC
            LIMIT %s OFFSET %s
        """
        
        params.extend([per_page, offset])
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'guid': str(row[0]),
                'patient_name': row[1] or '',
                'patient_dni': row[2] or '',
                'study_type': row[3] or '',
                'admission_number': row[4] or '',
                'accession_number': row[5] or '',
                'created_on': row[6].isoformat() if row[6] else None,
                'status': row[7] or '',
                'is_reported': bool(row[8]),
                'is_executed': bool(row[9]),
                'is_image': bool(row[10]),
                'study_instance_uid': row[11] or '',
                'equipment': row[12] or '',
                'location': row[13] or '',
                'assigned_to': str(row[14]) if row[14] else None
            })
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'data': results,
                'page': page,
                'per_page': per_page,
                'total': total
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/report', methods=['GET'])
@jwt_required()
def get_examination_report(exam_id):
    """
    Obtiene los datos del reporte de un examen específico
    
    Path Parameters:
    - exam_id: GUID del examen
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid",
            "exam_id": "uuid",
            "patient_id": "uuid",
            "patient_name": "nombre completo",
            "admission_number": "ADM001",
            "findings": "texto hallazgos",
            "impressions": "texto impresiones",
            "techniques": "texto técnicas",
            "conclusions": "texto conclusiones",
            "was_saved": true,
            "pdf_path": "ruta/al/archivo.pdf",
            "updated_on": "datetime",
            "history": "historia clínica",
            "clinical_question": "pregunta clínica",
            "laterality_id": "uuid",
            "stat": "urgencia",
            "others_details": "otros detalles"
        }
    }
    
    Nota: Si was_saved es false, devuelve el informe predefinido del study type.
          Si no existe predefinido, devuelve los campos de informe en blanco.
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
        
        # Verificar que el examen existe y obtener datos adicionales
        cursor.execute("""
            SELECT e.Guid, e.IdPatient, e.AdmisionNumber,
                   CONCAT(dp.Name, ' ', dp.Surname) as patient_name,
                   e.studytype_id, e.history, e.clinicalquestion,
                   e.laterality_id, e.stat, e.othersdetails
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient dp ON e.IdPatient = dp.Guid
            WHERE e.Guid = %s
        """, (exam_id,))
        
        exam = cursor.fetchone()
        if not exam:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        exam_guid = exam[0]
        patient_id = exam[1]
        admission_number = exam[2]
        patient_name = exam[3]
        study_type_id = exam[4]
        history = exam[5]
        clinical_question = exam[6]
        laterality_id = exam[7]
        stat = exam[8]
        others_details = exam[9]
        
        # Obtener reporte
        cursor.execute("""
            SELECT r.Guid, r.idexamination, r.idpatient, r.admnumber,
                   r.findings, r.impressions, r.techniques, r.conclusions,
                   r.wassaved, r.pdfpath, r.date
            FROM nextris.tbreport r
            WHERE r.IdExamination = %s
        """, (exam_id,))
        
        report = cursor.fetchone()
        
        # Determinar si usar datos guardados o predefinidos
        findings = ''
        impressions = ''
        techniques = ''
        conclusions = ''
        was_saved = False
        report_guid = None
        pdf_path = None
        updated_on = None
        
        if report:
            was_saved = bool(report[8])
            report_guid = report[0]
            pdf_path = report[9]
            updated_on = report[10]
            
            if was_saved:
                # Si está guardado, usar datos de tbreport
                findings = report[4] or ''
                impressions = report[5] or ''
                techniques = report[6] or ''
                conclusions = report[7] or ''
            else:
                # Si no está guardado, buscar informe predefinido
                cursor.execute("""
                    SELECT default_predef_id 
                    FROM nextris.isstudytype 
                    WHERE guid = %s
                """, (study_type_id,))
                
                study_type_result = cursor.fetchone()
                default_predef_id = study_type_result[0] if study_type_result else None
                
                if default_predef_id:
                    # Obtener datos del predefinido
                    cursor.execute("""
                        SELECT findings, impression, technique, conclusion
                        FROM nextris.tbinfpredef
                        WHERE guid = %s
                    """, (default_predef_id,))
                    
                    predef = cursor.fetchone()
                    if predef:
                        findings = predef[0] or ''
                        impressions = predef[1] or ''
                        techniques = predef[2] or ''
                        conclusions = predef[3] or ''
        else:
            # Si no existe reporte, buscar predefinido
            if study_type_id:
                cursor.execute("""
                    SELECT default_predef_id 
                    FROM nextris.isstudytype 
                    WHERE guid = %s
                """, (study_type_id,))
                
                study_type_result = cursor.fetchone()
                default_predef_id = study_type_result[0] if study_type_result else None
                
                if default_predef_id:
                    cursor.execute("""
                        SELECT findings, impression, technique, conclusion
                        FROM nextris.tbinfpredef
                        WHERE guid = %s
                    """, (default_predef_id,))
                    
                    predef = cursor.fetchone()
                    if predef:
                        findings = predef[0] or ''
                        impressions = predef[1] or ''
                        techniques = predef[2] or ''
                        conclusions = predef[3] or ''
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'guid': str(report_guid) if report_guid else None,
                'exam_id': str(exam_guid),
                'patient_id': str(patient_id) if patient_id else None,
                'admission_number': admission_number or '',
                'patient_name': patient_name or '',
                'findings': findings,
                'impressions': impressions,
                'techniques': techniques,
                'conclusions': conclusions,
                'was_saved': was_saved,
                'pdf_path': pdf_path or None,
                'updated_on': updated_on.isoformat() if updated_on else None,
                'history': history or '',
                'clinical_question': clinical_question or '',
                'laterality_id': str(laterality_id) if laterality_id else None,
                'stat': stat or '',
                'others_details': others_details or ''
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/report', methods=['PUT', 'PATCH'])
@jwt_required()
def update_examination_report(exam_id):
    """
    Actualiza o crea el reporte de un examen
    
    Path Parameters:
    - exam_id: GUID del examen
    
    Body JSON:
    {
        "findings": "texto hallazgos" (optional),
        "impressions": "texto impresiones" (optional),
        "techniques": "texto técnicas" (optional),
        "conclusions": "texto conclusiones" (optional),
        "mark_as_reported": false (optional, default: false)
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte actualizado exitosamente",
        "data": {
            "report_id": "uuid"
        }
    }
    """
    try:
        data = request.get_json() or {}
        
        findings = data.get('findings')
        impressions = data.get('impressions')
        techniques = data.get('techniques')
        conclusions = data.get('conclusions')
        mark_as_reported = data.get('mark_as_reported', False)
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el examen existe
        cursor.execute("""
            SELECT IdPatient, AdmisionNumber
            FROM nextris.tbexamination
            WHERE Guid = %s
        """, (exam_id,))
        
        exam = cursor.fetchone()
        if not exam:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        patient_id = exam[0]
        admission_number = exam[1]
        
        # Verificar si ya existe un reporte
        cursor.execute("""
            SELECT Guid FROM nextris.tbreport
            WHERE IdExamination = %s
        """, (exam_id,))
        
        existing_report = cursor.fetchone()
        
        if existing_report:
            # Actualizar reporte existente
            report_id = existing_report[0]
            
            updates = []
            params = []
            
            if findings is not None:
                updates.append("Findings = %s")
                params.append(findings)
            if impressions is not None:
                updates.append("Impressions = %s")
                params.append(impressions)
            if techniques is not None:
                updates.append("Techniques = %s")
                params.append(techniques)
            if conclusions is not None:
                updates.append("Conclusions = %s")
                params.append(conclusions)
            
            updates.append("WasSaved = 1")
            updates.append("Date = NOW()")
            
            if updates:
                params.append(report_id)
                update_query = f"""
                    UPDATE nextris.tbreport
                    SET {', '.join(updates)}
                    WHERE Guid = %s
                """
                cursor.execute(update_query, params)
        else:
            # Crear nuevo reporte
            report_id = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO nextris.tbreport (
                    Guid, IdExamination, IdPatient, admnumber,
                    Findings, Impressions, Techniques, Conclusions,
                    WasSaved, CreatedOn, Date
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, 1, NOW(), NOW()
                )
            """, (
                report_id, exam_id, patient_id, admission_number,
                findings or '', impressions or '', techniques or '', conclusions or ''
            ))
        
        # Marcar examen como reportado si se solicita
        if mark_as_reported:
            cursor.execute("""
                UPDATE nextris.tbexamination
                SET IsReported = 1
                WHERE Guid = %s
            """, (exam_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Reporte actualizado exitosamente',
            'data': {
                'report_id': str(report_id)
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/notes', methods=['GET'])
@jwt_required()
def get_examination_notes(exam_id):
    """
    Obtiene las notas clínicas de un examen
    
    Path Parameters:
    - exam_id: GUID del examen
    
    Returns:
    {
        "success": true,
        "data": {
            "history": "historia clínica",
            "clinical_question": "pregunta clínica",
            "others_details": "otros detalles",
            "number_of_views": "número de vistas",
            "laterality": "lateralidad",
            "stat": "urgencia"
        }
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
        
        cursor.execute("""
            SELECT e.history, e.clinicalquestion, e.othersdetails,
                   e.numberofviews, e.stat, l.Description as laterality
            FROM nextris.tbexamination e
            LEFT JOIN nextris.islaterality l ON e.laterality_id = l.Guid
            WHERE e.Guid = %s
        """, (exam_id,))
        
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not result:
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'history': result[0] or '',
                'clinical_question': result[1] or '',
                'others_details': result[2] or '',
                'number_of_views': result[3] or '',
                'stat': result[4] or '',
                'laterality': result[5] or ''
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/examinations/<exam_id>/notes', methods=['PUT', 'PATCH'])
@jwt_required()
def update_examination_notes(exam_id):
    """
    Actualiza las notas clínicas de un examen
    
    Path Parameters:
    - exam_id: GUID del examen
    
    Body JSON:
    {
        "history": "historia clínica" (optional),
        "clinical_question": "pregunta clínica" (optional),
        "others_details": "otros detalles" (optional),
        "number_of_views": "número de vistas" (optional),
        "laterality_id": "uuid lateralidad" (optional),
        "stat": "urgencia" (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Notas actualizadas exitosamente"
    }
    """
    try:
        data = request.get_json() or {}
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Verificar que el examen existe
        cursor.execute("""
            SELECT Guid FROM nextris.tbexamination
            WHERE Guid = %s
        """, (exam_id,))
        
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Examen no encontrado'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'history' in data:
            updates.append("history = %s")
            params.append(data['history'])
        if 'clinical_question' in data:
            updates.append("clinicalquestion = %s")
            params.append(data['clinical_question'])
        if 'others_details' in data:
            updates.append("othersdetails = %s")
            params.append(data['others_details'])
        if 'number_of_views' in data:
            updates.append("numberofviews = %s")
            params.append(data['number_of_views'])
        if 'laterality_id' in data:
            updates.append("laterality_id = %s")
            params.append(data['laterality_id'])
        if 'stat' in data:
            updates.append("stat = %s")
            params.append(data['stat'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(exam_id)
        update_query = f"""
            UPDATE nextris.tbexamination
            SET {', '.join(updates)}
            WHERE Guid = %s
        """
        
        cursor.execute(update_query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Notas actualizadas exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


# ====================================================================
# ENDPOINTS EXISTENTES DE PLANTILLAS
# ====================================================================


@jwt_required()
def get_report_template(template_id):
    """
    Obtiene los textos de una plantilla de reporte
    
    Path:
    - template_id: GUID de la plantilla
    
    Returns:
    {
        "success": true,
        "data": {
            "report": "Contenido de la plantilla"
        }
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
        
        cursor.execute("SELECT report FROM nextris.isreporttemplate WHERE guid=%s", (template_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if result:
            return jsonify({
                'success': True,
                'data': {
                    'report': result[0] or ''
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Plantilla no encontrada'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/study-types/<study_type_id>/default-template', methods=['GET'])
@jwt_required()
def get_default_template_for_study_type(study_type_id):
    """
    Obtiene el ID de plantilla predefinida por defecto para un tipo de estudio
    
    Path:
    - study_type_id: GUID del tipo de estudio
    
    Returns:
    {
        "success": true,
        "data": {
            "default_template_id": "uuid"
        }
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
        
        cursor.execute("SELECT default_predef_id FROM nextris.isstudytype WHERE guid=%s", (study_type_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'data': {
                'default_template_id': result[0] if result and result[0] else None
            }
        }), 200
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/predefined-reports', methods=['GET'])
@jwt_required()
def get_predefined_reports():
    """
    Obtiene lista de todos los reportes predefinidos
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "guid": "uuid",
                "title": "Título",
                "study_type": "Descripción del tipo de estudio"
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
            SELECT ip.guid, ip.tittle, ist.description
            FROM nextris.tbinfpredef ip
            LEFT JOIN nextris.isstudytype ist ON ip.studytype_id = ist.guid
            ORDER BY ip.tittle ASC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        predefined = []
        for row in results:
            predefined.append({
                'guid': row[0],
                'title': row[1] or '',
                'study_type': row[2] or ''
            })
        
        return jsonify({
            'success': True,
            'data': predefined
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/predefined-reports/<predef_id>', methods=['GET'])
@jwt_required()
def get_predefined_report(predef_id):
    """
    Obtiene datos de un reporte predefinido específico
    
    Path:
    - predef_id: GUID del reporte predefinido
    
    Returns:
    {
        "success": true,
        "data": {
            "guid": "uuid",
            "title": "Título",
            "findings": "Hallazgos",
            "impression": "Impresión",
            "technique": "Técnica",
            "conclusion": "Conclusión",
            "study_type_id": "uuid"
        }
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
            SELECT guid, tittle, findings, impression, technique, conclusion, studytype_id
            FROM nextris.tbinfpredef 
            WHERE guid=%s
        """
        
        cursor.execute(query, (predef_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if result:
            return jsonify({
                'success': True,
                'data': {
                    'guid': result[0],
                    'title': result[1] or '',
                    'findings': result[2] or '',
                    'impression': result[3] or '',
                    'technique': result[4] or '',
                    'conclusion': result[5] or '',
                    'study_type_id': result[6]
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Reporte predefinido no encontrado'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/predefined-reports', methods=['POST'])
@jwt_required()
def create_predefined_report():
    """
    Crea un nuevo reporte predefinido
    
    Body JSON:
    {
        "title": "string" (required),
        "study_type_id": "uuid" (required),
        "findings": "string" (optional),
        "technique": "string" (optional),
        "impression": "string" (optional),
        "conclusion": "string" (optional),
        "is_default": boolean (optional)
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte predefinido creado exitosamente",
        "data": {
            "predef_id": "uuid"
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
        
        title = data.get('title')
        study_type_id = data.get('study_type_id')
        
        if not title or not study_type_id:
            return jsonify({
                'success': False,
                'message': 'title y study_type_id son campos requeridos'
            }), 400
        
        findings = data.get('findings', '')
        technique = data.get('technique', '')
        impression = data.get('impression', '')
        conclusion = data.get('conclusion', '')
        is_default = data.get('is_default', False)
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Generar nuevo GUID
        new_guid = str(uuid.uuid4())
        
        # Si este debe ser el predefinido por defecto, actualizar el tipo de estudio
        if is_default:
            update_query = "UPDATE nextris.isstudytype SET default_predef_id=%s WHERE guid=%s"
            cursor.execute(update_query, (new_guid, study_type_id))
        
        # Insertar el nuevo predefinido
        insert_query = """
            INSERT INTO nextris.tbinfpredef 
            (guid, tittle, findings, impression, technique, conclusion, studytype_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            new_guid, title, findings, impression, technique, conclusion, study_type_id
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Reporte predefinido creado exitosamente',
            'data': {
                'predef_id': new_guid
            }
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/predefined-reports/<predef_id>', methods=['PATCH', 'PUT'])
@jwt_required()
def update_predefined_report(predef_id):
    """
    Actualiza un reporte predefinido existente
    
    Path:
    - predef_id: GUID del reporte predefinido
    
    Body JSON (todos opcionales):
    {
        "title": "string",
        "findings": "string",
        "technique": "string",
        "impression": "string",
        "conclusion": "string"
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte predefinido actualizado exitosamente"
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
        
        # Verificar que existe
        cursor.execute("SELECT 1 FROM nextris.tbinfpredef WHERE guid=%s", (predef_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'Reporte predefinido no encontrado'
            }), 404
        
        # Construir query dinámicamente
        updates = []
        params = []
        
        if 'title' in data:
            updates.append("tittle = %s")
            params.append(data['title'])
        if 'findings' in data:
            updates.append("findings = %s")
            params.append(data['findings'])
        if 'technique' in data:
            updates.append("technique = %s")
            params.append(data['technique'])
        if 'impression' in data:
            updates.append("impression = %s")
            params.append(data['impression'])
        if 'conclusion' in data:
            updates.append("conclusion = %s")
            params.append(data['conclusion'])
        
        if not updates:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'message': 'No hay campos para actualizar'
            }), 400
        
        params.append(predef_id)
        query = f"UPDATE nextris.tbinfpredef SET {', '.join(updates)} WHERE guid = %s"
        
        cursor.execute(query, params)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Reporte predefinido actualizado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/<exam_id>', methods=['PATCH', 'PUT'])
@jwt_required()
def save_report(exam_id):
    """
    Guarda o actualiza los datos de un reporte médico
    
    Path:
    - exam_id: GUID del examen
    
    Body JSON:
    {
        "findings": "string" (required),
        "techniques": "string" (required),
        "impressions": "string" (required),
        "conclusions": "string" (required)
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte guardado exitosamente"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'Se requiere un cuerpo JSON'
            }), 400
        
        findings = data.get('findings')
        techniques = data.get('techniques')
        impressions = data.get('impressions')
        conclusions = data.get('conclusions')
        
        if findings is None or techniques is None or impressions is None or conclusions is None:
            return jsonify({
                'success': False,
                'message': 'findings, techniques, impressions y conclusions son campos requeridos'
            }), 400
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = """
            UPDATE nextris.tbreport 
            SET findings=%s, techniques=%s, impressions=%s, conclusions=%s, wassaved=true 
            WHERE idexamination=%s
        """
        
        cursor.execute(query, (findings, techniques, impressions, conclusions, exam_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Reporte guardado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/<exam_id>/sign', methods=['POST'])
@jwt_required()
def sign_report(exam_id):
    """
    Firma un reporte médico (marca como reportado)
    
    Path:
    - exam_id: GUID del examen
    
    Body JSON (opcional):
    {
        "reporter_physician_id": "uuid" (opcional, se usa JWT identity si no se provee)
    }
    
    Returns:
    {
        "success": true,
        "message": "Reporte firmado exitosamente"
    }
    """
    try:
        data = request.get_json() or {}
        
        # Obtener ID del médico que firma
        reporter_physician_id = data.get('reporter_physician_id')
        if not reporter_physician_id:
            # Usar el ID del usuario autenticado
            reporter_physician_id = get_jwt_identity()
        
        config = get_db_config()
        if not config:
            return jsonify({
                'success': False,
                'message': 'Error de configuración de base de datos'
            }), 500
        
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        # Marcar el examen como reportado
        query = "UPDATE nextris.tbexamination SET isreported=1 WHERE guid=%s"
        cursor.execute(query, (exam_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # Actualizar estado (si existe la función)
        try:
            from apps.home.routes import updatestatus
            updatestatus(exam_id)
        except:
            pass
        
        return jsonify({
            'success': True,
            'message': 'Reporte firmado exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/<exam_id>/unsign', methods=['POST'])
@jwt_required()
def unsign_report(exam_id):
    """
    Quita la firma de un reporte (desmarca como reportado)
    
    Path:
    - exam_id: GUID del examen
    
    Returns:
    {
        "success": true,
        "message": "Firma removida exitosamente"
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
        
        query = "UPDATE nextris.tbexamination SET isreported=0 WHERE guid=%s"
        cursor.execute(query, (exam_id,))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        # Actualizar estado (si existe la función)
        try:
            from apps.home.routes import updatestatus
            updatestatus(exam_id)
        except:
            pass
        
        return jsonify({
            'success': True,
            'message': 'Firma removida exitosamente'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@api_blueprint.route('/reports/<exam_id>/pdf', methods=['GET'])
@jwt_required()
def get_report_pdf(exam_id):
    """
    Obtiene el PDF de un reporte
    
    Path:
    - exam_id: GUID del examen
    
    Returns:
    - Archivo PDF del reporte
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
        
        query = "SELECT pdfpath FROM nextris.tbreport WHERE idexamination = %s"
        cursor.execute(query, (exam_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not result or not result[0]:
            return jsonify({
                'success': False,
                'message': 'PDF no disponible'
            }), 404
        
        pdf_path = os.path.normpath(result[0])
        absolute_path = os.path.abspath(pdf_path)
        
        if not os.path.exists(absolute_path):
            return jsonify({
                'success': False,
                'message': 'Archivo PDF no encontrado en el sistema'
            }), 404
        
        return send_file(absolute_path, as_attachment=False, mimetype='application/pdf')
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500
