# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import mysql.connector
from apps import db
from flask import jsonify,send_file, send_from_directory
import requests
from apps.home import blueprint
from flask import render_template, request
from flask_login import login_required
from jinja2 import TemplateNotFound
import json
import sqlite3
from flask import session
from datetime import datetime
import hl7
from hl7apy.core import Message, Segment
import socket
import time
import pydicom.uid
from psycopg2 import sql, Error
import psycopg2
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from apps.authentication.forms import CreateAccountForm
from apps.authentication.models import Users
from werkzeug.security import generate_password_hash
import pytz
from datetime import datetime, timedelta
from collections import defaultdict

#server_url = "http://hapi.fhir.org/baseR4"
server_url = "http://localhost:8080/fhir"  # URL del servidor HAPI FHIR local

# Configuración de la conexión
config = {
    'user': 'pacs',
    'password': 'pacs',
    'host': '192.168.31.56',
    'port': '5432',
    'database': 'pacsdb',
}


def send_hl7_message(message, host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))

    # Agregar delimitadores para el protocolo MLLP
    message = f"\x0b{message}\x1c\x0d"

    s.sendall(message.encode())
    response = s.recv(4096)
    s.close()

    return response.decode()

class Cita():
    def __init__(self, paciente_id=None, fecha=None, time=None, paciente_dni=None, machine=None, codigo_examen=None,
                 coste=None, urgencia=None, medico=None, cons_investigacion=None, exp_sanitario=None,
                 exp_san_elec=None):
        self.fecha = fecha
        self.time = time
        self.paciente_dni = paciente_dni
        self.machine = machine
        self.codigo_examen = codigo_examen
        self.coste = coste
        self.urgencia = urgencia
        self.medico = medico
        self.cons_investigacion = cons_investigacion
        self.exp_sanitario = exp_sanitario
        self.exp_san_elec = exp_san_elec
        self.paciente_id = paciente_id

    def to_dict(self):
        # Convertir el objeto a un diccionario
        return {
            'fecha': self.fecha,
            'time': self.time,
            'paciente_dni': self.paciente_dni,
            'machine': self.machine,
            'codigo_examen': self.codigo_examen,
            'coste': self.coste,
            'urgencia': self.urgencia,
            'medico': self.medico,
            'cons_investigacion': self.cons_investigacion,
            'exp_sanitario': self.exp_sanitario,
            'exp_san_elec': self.exp_san_elec,
            'paciente_id':self.paciente_id
        }

    @classmethod
    def from_dict(cls, data):
        # Crear un objeto Cita a partir de un diccionario
        return cls(**data)
class Orden():
    def __init__(self, paciente_id=None, fecha=None, time=None, EquipmentId=None, ExamId=None,
                 coste=None, urgencia=None, medico_solicitante=None, cons_investigacion=None, exp_sanitario=None,
                 exp_san_elec=None):
        self.fecha = fecha
        self.time = time
        self.EquipmentId = EquipmentId
        self.ExamId = ExamId
        self.coste = coste
        self.urgencia = urgencia
        self.medico_solicitante = medico_solicitante
        self.cons_investigacion = cons_investigacion
        self.exp_sanitario = exp_sanitario
        self.exp_san_elec = exp_san_elec
        self.paciente_id = paciente_id

    def to_dict(self):
        # Convertir el objeto a un diccionario
        return {
            'fecha': self.fecha,
            'time': self.time,
            'paciente_dni': self.paciente_dni,
            'machine': self.machine,
            'codigo_examen': self.codigo_examen,
            'coste': self.coste,
            'urgencia': self.urgencia,
            'medico': self.medico,
            'cons_investigacion': self.cons_investigacion,
            'exp_sanitario': self.exp_sanitario,
            'exp_san_elec': self.exp_san_elec,
            'paciente_id':self.paciente_id
        }

    @classmethod
    def from_dict(cls, data):
        # Crear un objeto Cita a partir de un diccionario
        return cls(**data)


@blueprint.route('/index')
@login_required
def index():

    return render_template('home/analisis_facturacion.html', segment='index')


@blueprint.route('/buscar_pacientes', methods=['POST'])
def buscar_pacientes():
    try:
        # Obtener datos del cuerpo de la solicitud en formato JSON
        data = request.get_json()
        
        # Acceder a los valores individuales
        name = data.get('name')

        # Establecer conexión con PostgreSQL
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        # Construir la consulta SQL con parámetros seguros
        query = "SELECT Guid, Name, Surname, NationalCode, SexCode, BirthDate, Phone, Email, HealthCard FROM public.datapatient WHERE Surname LIKE %s"
        cursor.execute(query, (f'%{name}%',))

        # Obtener resultados de la consulta
        response_data = cursor.fetchall()

        # Cerrar cursor y conexión
        cursor.close()
        connection.close()

        # Devolver los datos en formato JSON
        return jsonify(response_data)

    except psycopg2.Error as e:
        # Manejar errores de psycopg2
        response_data = {
            'success': False,
            'message': 'Error en la búsqueda',
            'error': str(e)
        }
        return jsonify(response_data), 500

    except Exception as e:
        # Manejar otros errores
        response_data = {
            'success': False,
            'message': 'Error en la búsqueda',
            'error': str(e)
        }
        return jsonify(response_data), 500
    

@blueprint.route('/buscar_pacientes2', methods=['POST'])
def buscar_pacientes2():
    try:
        # Establecer la conexión a PostgreSQL
        conn = psycopg2.connect(**config)
        cursor = conn.cursor()

        # Obtener datos del cuerpo de la solicitud en formato JSON
        r = request.form.to_dict()

        # Construir y ejecutar la consulta SQL
        query = "SELECT Guid, Name, Surname, SexCode, BirthDate, NationalCode FROM public.DataPatient WHERE Surname LIKE %s"
        cursor.execute(query, (f"%{r['name']}%",))

        # Obtener resultados y convertirlos a formato JSON
        response_data = cursor.fetchall()

        # Cerrar cursor y conexión
        cursor.close()
        conn.close()

        return jsonify(response_data)

    except Exception as e:
        # Manejar errores si es necesario
        response_data = {
            'success': False,
            'message': 'Error en la búsqueda',
            'error': str(e)
        }
        return jsonify(response_data), 500

@blueprint.route('/editar_paciente', methods=['POST'])
def editar_pacientes():
    conn = psycopg2.connect(**config)
    cursor = conn.cursor()
    r = request.form.to_dict()

    IsAn = r.get('IsAn') == 'on'
    r['IsAn'] = 1 if IsAn else 0

    IsMerged = r.get('IsMerged') == 'on'
    r['IsMerged'] = 1 if IsMerged else 0

    query="""UPDATE public.DataPatient SET Surname=%s, Name=%s, NationalCode=%s, BirthDate=%s, PatientId=%s, SexCode=%s, IsAnonymous=%s, IsMerged=%s, Phone=%s,Email=%s,HealthCard=%s WHERE Guid=%s"""

    cursor.execute(query,(r['p_surname'],r['p_name'],r['p_dni'],r['fecha_nacimiento'],r['p_id'],r['sex'],r['IsAn'],r['IsMerged'],r['telefono'],r['mail'],r['p_healthcard'],r['id_np'])) 
    conn.commit()
    # response_data=cursor.fetchall()
    response=[r['p_name'],r['p_surname'],r['p_dni'],r['sex'],r['fecha_nacimiento'],r['telefono'],r['mail'],r['p_healthcard']]

    return jsonify(response)

@blueprint.route('/nueva_cita', methods=['GET'])
def nueva_cita():

    cita = Cita()
    # Guardar la cita en la sesión
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    cita.fecha = fecha_actual
    session['cita'] = cita.to_dict()

    query="""
        SELECT  m.Description AS MinisterialCode, e.Description,n.Description AS modality, m.Description
        FROM public.exam e
        JOIN public.IsMinisterialCode m ON e.IdMinisterialCode = m.Guid
        JOIN public.IsModality n ON e.IdModality = n.Guid
        WHERE e.IsActive=1
    """
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    cursor.execute(query)
    tipos=cursor.fetchall()
    
    query="SELECT codigo FROM Machine"
    conn = sqlite3.connect('basededatos.db')
    cursor = conn.cursor()
    cursor.execute(query)
    codigos_machine=cursor.fetchall()

    return render_template('/home/nueva_cita.html',tipoestudios=tipos,codigos=codigos_machine,segment='nueva_cita')


@blueprint.route('/configuraciones', methods=['GET'])
def configuraciones():


    return render_template('/home/configuraciones.html')


from flask import jsonify, request
import psycopg2

@blueprint.route('/agregar_pacientes', methods=['POST'])
def agregar_pacientes():
    
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    r = request.form.to_dict()

    # Convertir 'on' a bit '0' o '1'
    IsAn = r.get('IsAn') == 'on'
    r['IsAn'] = '1' if IsAn else '0'

    IsMerged = r.get('IsMerged') == 'on'
    r['IsMerged'] = '1' if IsMerged else '0'

    print(r)

    query = """
    INSERT INTO public.DataPatient(
        Guid, Surname, Name, NationalCode, BirthDate, PatientId, SexCode, 
        IsAnonymous, IsMerged, Phone, Email, HealthCard) 
    VALUES (
        uuid_generate_v4(), %s, %s, %s, %s, %s, %s, 
        %s::bit, %s::bit, %s, %s, %s) 
    """
    
    cursor.execute(query, (
        r['p_surname'], r['p_name'], r['p_dni'], r['fecha_nacimiento'],
        r['p_id'], r['sex'], r['IsAn'], r['IsMerged'], r['telefono'],
        r['mail'], r['p_healthcard']
    ))
    
    connection.commit()

    return jsonify(r)



@blueprint.route('/obtener_historial', methods=['GET'])
def obtener_historial():
    patient_id = request.args.get('id')
    server_url = "http://hapi.fhir.org/baseR4/DiagnosticReport?subject=Patient/" + patient_id
    server_response=""

    try:
        response = requests.get(server_url)
        if response.status_code == 200:
            historial = response.json()
            print(historial['total'])

            if "entry" in historial:
                reportes = []
                # Itera a través de las entradas (DiagnosticReport)
                for entry in historial["entry"]:
                    resource = entry.get("resource")
                    if resource and resource.get("resourceType") == "DiagnosticReport":
                # Obtiene los datos de interés
                        last_updated = resource["meta"]["lastUpdated"]
                        code = resource["code"]["coding"][0]["code"]
                        status = resource["status"]
                        source = resource["meta"]["source"]

                        # Agregar estos datos a una lista de reportes
                        reporte = {
                            "lastUpdated": last_updated,
                            "code": code,
                            "status": status,
                            "source": source
                        }
                        print(reporte)
                        reportes.append(reporte)
            
        return jsonify(reportes)
                        
    except:
        pass


@blueprint.route('/agregar_notas', methods=['POST'])
def agregar_notas_ex():
    
    data = request.get_json()
    print("hola",data)
    record_id = data['data_id']
    execution_notes = data['execution_notes']
    
    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query = f"""
            UPDATE public.tbExamination
            SET ExecutionNotes = %s
            WHERE Guid = %s
        """
        cursor.execute(query, (execution_notes, record_id))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@blueprint.route('/get_patients', methods=['GET']) 
def get_patients():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "SELECT Guid,name,surname,NationalCode,Sexcode,BirthDate,phone,email,healthcard FROM public.datapatient;"
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_patients_min', methods=['GET']) 
def get_patients_min():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "SELECT Guid,name,surname,Sexcode,BirthDate,NationalCode FROM public.datapatient;"
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_data_report', methods=['POST']) 
def get_data_report():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    data = request.get_json()
    guid = data['id']
    
    print("Received ID:", guid)
    
    # Obtener el reporte
    query = f"SELECT Guid,IdPatient,AdmNumber,IdReferringPhysician,ExecutionText,FindingText,conclusionText,ClinicalQuestion,IsSigned,IsReported FROM public.tbReport WHERE IdExamination='{guid}';"
    cursor.execute(query)
    report = cursor.fetchall()

    # Obtener el estado de IsReported
    query = f"SELECT IsReported FROM public.tbExamination WHERE Guid='{guid}'"
    cursor.execute(query)
    isreported = cursor.fetchall()

    # Crear una respuesta combinada
    response = {
        'report': report,
        'isreported': isreported
    }

    return jsonify(response)

import psycopg2
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch

def generate_pdf(report_id, logo_path, institution_name, output_dir='output_pdfs'):
    query = f"""SELECT p.surname,p.name,ex.description,date,rep.idreferringphysician,rep.executiontext,rep.findingtext,rep.conclusiontext,rep.clinicalquestion FROM public.tbreport rep
                left join public.tbexamination tbex on tbex.Guid=rep.idexamination
                left join public.exam ex on tbex.idexam=ex.Guid
                left join public.datapatient p on p.patientid=rep.idpatient
                where rep.idexamination='{report_id}'"""
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    cursor.execute(query)
    datos = cursor.fetchone()
    connection.close()
    print(datos)
    if datos:
        surname, name, examen, fecha, refmed, executiontext, findingtext, conclusiontext, clinicalquestion = datos

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        pdf_filename = os.path.join(output_dir, f"r_{report_id}.pdf")
        c = canvas.Canvas(pdf_filename, pagesize=letter)
        width, height = letter

        # Añadir el logo
        c.drawImage(logo_path, 50, height - 180, width=2*inch, preserveAspectRatio=True, mask='auto')

        # Añadir el nombre de la institución
        c.setFont("Helvetica-Bold", 16)
        c.drawString(200, height - 50, institution_name)

        # Añadir el título del informe
        c.setFont("Helvetica-Bold", 14)
        c.drawString(200, height - 70, f"Exámen: {examen}")

        # Añadir los datos del informe
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 150, f"Paciente: {name}, {surname}")
        c.drawString(50, height - 170, f"Fecha: {fecha}")
        c.drawString(50, height - 190, f"ID del Médico Referente: {refmed}")

        # Añadir los textos largos con envoltura de texto
        text_objects = [
            ("Pregunta Clínica:", clinicalquestion),
            ("Tecnicas de Examen:", executiontext),
            ("Hallazgos:", findingtext),
            ("Conclusión:", conclusiontext)
        ]

        y_position = height - 230
        for title, text in text_objects:
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y_position, title)
            y_position -= 20
            c.setFont("Helvetica", 12)
            text_lines = c.beginText(50, y_position)
            text_lines.setTextOrigin(50, y_position)
            text_lines.setFont("Helvetica", 12)
            for line in text.split('\n'):
                text_lines.textLine(line)
            c.drawText(text_lines)
            y_position = text_lines.getY() - 20

        c.save()
        print(f"PDF generado: {pdf_filename}")
        return pdf_filename
    else:
        print("No se encontraron datos para el informe.")
        return None



@blueprint.route('/firmar_reporte', methods=['POST']) 
def firmar_reporte():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    reporteid = request.get_json()
    print("id:",reporteid['id'])
    query = f"UPDATE public.tbExamination SET IsReported=1 WHERE Guid='{reporteid['id']}'"
    
    print(query)
    cursor.execute(query)
    connection.commit()
    response=generate_pdf(reporteid['id'],'apps/static/assets/img/icono.jpg','NEXTRIS')
    query = f"UPDATE public.tbReport SET pdfpath='{response}' WHERE IdExamination='{reporteid['id']}'"
    cursor.execute(query)
    connection.commit()

    return jsonify('success;')

@blueprint.route('/verpdf/<report_id>', methods=['GET'])
def verpdf(report_id):
    query = f"SELECT pdfpath FROM public.tbReport WHERE IdExamination = '{report_id}'"
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    cursor.execute(query)
    result = cursor.fetchone()
    connection.close()
    
    if result:
        pdf_path = result[0]
        pdf_path = os.path.normpath(pdf_path)  # Normalizar la ruta
        print(f"Ruta normalizada del PDF: {pdf_path}")
        
        # Imprimir ruta absoluta del archivo
        absolute_path = os.path.abspath(pdf_path)
        print(f"Ruta absoluta del PDF: {absolute_path}")
        
        # Asegúrate de que la ruta esté correcta
        if os.path.exists(absolute_path):
            print("PDF encontrado, enviando archivo...")
            return send_file(absolute_path, as_attachment=False)
        else:
            print("PDF no encontrado en la ruta especificada.")
            return jsonify({"error": "PDF no encontrado"}), 404
    else:
        print("Reporte no encontrado en la base de datos.")
        return jsonify({"error": "Reporte no encontrado"}), 404
    
@blueprint.route('/send_mail/<report_id>', methods=['GET'])
def send_mail(report_id):
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    # Configura los detalles del correo electrónico
    SMTP_SERVER = 'smtp.gmail.com'  # Cambia esto por tu servidor SMTP
    SMTP_PORT = 587  # Cambia esto por el puerto adecuado
    SMTP_USER = 'facufarias93@gmail.com'  # Cambia esto por tu dirección de correo electrónico
    SMTP_PASSWORD = 'pjiwxoqulgvdctgc'  # Cambia esto por tu contraseña de correo electrónico
    FROM_EMAIL = 'facufarias93@gmail.com'  # Dirección de correo electrónico del remitente
    TO_EMAIL = request.args.get('mail')  # Obtén el correo del parámetro 'mail'
    query = f"SELECT pdfpath FROM public.tbReport WHERE IdExamination = '{report_id}'"
    cursor.execute(query)
    result = cursor.fetchone()

    query = f"SELECT StudyInstanceUID,IsImage,IdPatient,LocalAcc FROM public.tbexamination WHERE Guid='{report_id}'"
    cursor.execute(query)
    study_id = cursor.fetchone()

    print("study_id: ",study_id[0])



    connection.close()
    print("mail teorico:",TO_EMAIL)
    if result:
        pdf_path = result[0]
        pdf_path = os.path.normpath(pdf_path)  # Normalizar la ruta
        absolute_path = os.path.abspath(pdf_path)
        
        if os.path.exists(absolute_path):
            print("PDF encontrado, enviando archivo...")
            
            # Crear el mensaje
            msg = MIMEMultipart()
            msg['From'] = FROM_EMAIL
            msg['To'] = 'facufarias93@gmail.com'
            msg['Subject'] = 'Centro Médico - Informe de estudio e Imágenes'
            
            # Agregar el cuerpo del mensaje
            body = MIMEText(f'Adjunto encontrarás el reporte en PDF.\n Link de las imagenes: http://192.168.31.56/viewer.html?studyUID={study_id[0]}')
            msg.attach(body)
            
            # Adjuntar el archivo PDF
            with open(absolute_path, 'rb') as file:
                pdf_attachment = MIMEApplication(file.read(), _subtype='pdf')
                pdf_attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(absolute_path))
                msg.attach(pdf_attachment)
            
            # Enviar el correo electrónico
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            
            return jsonify({"message": "Correo enviado con éxito."})
        else:
            print("PDF no encontrado en la ruta especificada.")
            return jsonify({"error": "PDF no encontrado"}), 404
    else:
        print("Reporte no encontrado en la base de datos.")
        return jsonify({"error": "Reporte no encontrado"}), 404

@blueprint.route('/get_image_link', methods=['POST']) 
def get_image_link():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    reporteid = request.get_json()
    print("id:",reporteid['id'])
    query = f"SELECT StudyInstanceUID,IsImage,IdPatient,LocalAcc FROM public.tbexamination WHERE Guid='{reporteid['id']}'"
    print(query)
    cursor.execute(query)
    return jsonify(cursor.fetchone())

@blueprint.route('/quitar_definitivo', methods=['POST']) 
def quitar_definitivo():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    reporteid = request.get_json()
    print("id:",reporteid['id'])
    query = f"UPDATE public.tbExamination SET IsReported=0 WHERE Guid='{reporteid['id']}'"
    print(query)
    cursor.execute(query)
    connection.commit()
    return jsonify('success;')

@blueprint.route('/guardar_reporte', methods=['POST']) 
def guardar_reporte():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    data = request.get_json()
    print(data)
    query = f"UPDATE public.tbReport SET ExecutionText='{data['tecnicas_examen']}', FindingText='{data['informe']}',ConclusionText='{data['conclusion']}', ClinicalQuestion='{data['pregunta_clinica']}' WHERE IdExamination='{data['id']}' "
    print(query)
    cursor.execute(query)
    connection.commit()

    return jsonify('success;')

@blueprint.route('/get_examinations', methods=['GET']) 
def get_examinations():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "SELECT Guid, CreatedOn, IdPatient, LocalAcc, IdExam, Status, IdSeverity, IdReferringPhysician FROM public.tbexamination;"
    cursor.execute(query)
    datos = cursor.fetchall()

    to_send = []

    for dato in datos:
        print(dato)

        query = f"SELECT Description FROM public.exam WHERE Guid='{dato[4]}';" 
        cursor.execute(query)
        est = cursor.fetchone()
        est = est[0] if est else ''

        query = f"SELECT Description FROM public.IsSeverity WHERE Guid='{dato[6]}';" 
        cursor.execute(query)
        sev = cursor.fetchone()
        sev = sev[0] if sev else ''

        query = f"SELECT UserName FROM public.tbuser WHERE Guid='{dato[7]}';" 
        cursor.execute(query)
        mref = cursor.fetchone()
        mref = mref[0] if mref else ''

        query = f"SELECT Surname,Name,NationalCode,SexCode FROM public.datapatient WHERE PatientId='{dato[2]}';"  
        cursor.execute(query)
        patient_info = cursor.fetchone()
        print(patient_info)
        nombre = f"{patient_info[1]} {patient_info[0]}" if patient_info else ''
        dni=patient_info[2]
        sex=patient_info[3]

        fila = [dato[0], dato[1], nombre, dni, sex, est, dato[5], sev, mref]
        to_send.append(fila)

    cursor.close()
    connection.close()

    return jsonify(to_send)

@blueprint.route('/get_exams_modal', methods=['GET']) 
def get_exams_modal():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "SELECT Guid, code , description FROM public.exam;"
    cursor.execute(query)
    datos = cursor.fetchall()

    
    cursor.close()
    connection.close()

    return jsonify(datos)



@blueprint.route('/set_patient', methods=['GET'])
def set_patient():
    patient_id = request.args.get('id')
    dni = request.args.get('dni')
    
    cita_data = session.get('cita', {})
    cita = Cita.from_dict(cita_data)
    cita.paciente_id = patient_id
    cita.paciente_dni=dni
    print(cita.paciente_id)
    return jsonify(cita.to_dict())
    
@blueprint.route('/obtener_agenda', methods=['GET'])
def obtener_agenda():
    machine = request.args.get('machine')
    
    query=f"SELECT * FROM AG_{machine}"
    conn = sqlite3.connect('basededatos.db')
    cursor = conn.cursor()
    eventos=cursor.execute(query).fetchall()
    return jsonify(eventos)
    
@blueprint.route('/get_origins_group', methods=['GET']) 
def get_groups():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "SELECT guid,description,isexternal,iser,delaydays FROM public.IsProvenanceGroup;"
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_agenda_med', methods=['GET']) 
def get_agenda_med():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "SELECT guid,username,name,surname,nationalnumber FROM public.tbuser WHERE idrole='88e340f5-6fa5-4df1-aef6-c911625a4427';"
    cursor.execute(query)

    return jsonify(cursor.fetchall())


@blueprint.route('/get_days_agenda', methods=['POST']) 
def get_days_agenda():
    data = request.get_json()
    id_med = data.get('id')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    
    query = f"SELECT guid, day, timefrom, timeto, initday, finishday FROM public.isagendameditem WHERE idmed='{id_med}';"
    
    cursor.execute(query)
    datos = cursor.fetchall()
    
    # Convertir los datos a un formato serializable a JSON
    result = []
    for row in datos:
        result.append({
            'guid': row[0],
            'day': row[1],
            'timefrom': row[2].strftime('%H:%M:%S'),  # Convertir time a string
            'timeto': row[3].strftime('%H:%M:%S'),    # Convertir time a string
            'initday': row[4].strftime('%Y-%m-%d'),   # Convertir date a string
            'finishday': row[5].strftime('%Y-%m-%d')  # Convertir date a string
        })

    return jsonify(result)

@blueprint.route('/get_med_sol', methods=['GET']) 
def get_med_sol():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT guid,description,phone,mail,note FROM public.isrequestingphysician"""
    cursor.execute(query)

    return jsonify(cursor.fetchall())



@blueprint.route('/get_users', methods=['GET']) 
def get_users():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT u.guid,u.username,r.description,u.name,u.surname,u.nationalnumber,u.mail,u.isactive FROM public.tbuser u
                inner join public.isrole r on r.guid=u.idrole"""
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_orders_ex', methods=['GET']) 
def get_orders_ex():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT ex.Guid, ex.createdon,p.Surname,p.Name,exam.description,ex.Status,equip.Description,ex.AdmisionNumber,ex.LocalAcc
            FROM public.tbexamination ex 
            INNER JOIN public.datapatient p ON ex.IdPatient = p.PatientId 
            inner join public.exam exam on exam.Guid=ex.IdExam
            inner join public.isequipment equip on equip.Guid=ex.IdEquipment
            WHERE ex.IsExecuted=0
            """
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_orders_to_distribution', methods=['GET']) 
def get_orders_to_distribution():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT ex.Guid, ex.createdon,exam.description,p.Surname || ' ' || p.Name AS FullName,p.email,ex.Status, ex.idrequestingphysician,ex.idreferringphysician,ex.idseverity
                FROM public.tbexamination ex 
                INNER JOIN public.datapatient p ON ex.IdPatient = p.PatientId 
                inner join public.exam exam on exam.Guid=ex.IdExam
                inner join public.isequipment equip on equip.Guid=ex.IdEquipment
                WHERE ex.Isreported=1
            """
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_orders_to_bill', methods=['GET']) 
def get_orders_to_bill():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT ex.Guid, ex.createdon,ex.localacc,p.Surname || ' ' || p.Name AS FullName,exam.description,ex.priceid, ex.idrequestingphysician,ex.idreferringphysician,exam.precio,ex.Status
                FROM public.tbexamination ex 
                INNER JOIN public.datapatient p ON ex.IdPatient = p.PatientId 
                inner join public.exam exam on exam.Guid=ex.IdExam
                left join public.isrequestingphysician rq on rq.guid=ex.idrequestingphysician
                left join public.tbuser u on u.guid=ex.idreferringphysician
                WHERE ex.isbill=false
            """
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/ejecutar_orden', methods=['POST']) 
def ejecutar_orden():
    data = request.get_json()
    data_id = data.get('id')
    
    if not data_id:
        return jsonify({'success': False, 'error': 'No se proporcionó el ID'}), 400

    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        # Actualizar la columna IsExecuted en la tabla public.tbexaminations
        query = """
            UPDATE public.tbexamination
            SET IsExecuted = 1
            WHERE Guid = %s
        """
        cursor.execute(query, (data_id,))
        connection.commit()

        cursor.close()
        connection.close()

        return jsonify({'success': True})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500

@blueprint.route('/edit_mail', methods=['POST']) 
def edit_mail():
    data = request.get_json()
    data_id_examination = data.get('id_order')
    mail=data.get('mail')
    

    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        # Actualizar la columna IsExecuted en la tabla public.tbexaminations
        query = f"""
            UPDATE public.datapatient
            SET email = '{mail}'
            WHERE patientid = (SELECT idpatient FROM public.tbexamination WHERE guid='{data_id_examination}')
        """
        print(query)
        # cursor.execute(query)
        # connection.commit()

        cursor.close()
        connection.close()

        return jsonify({'success': True})
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'error': str(err)}), 500
    

@blueprint.route('/facturar_orden', methods=['POST']) 
def facturar_orden():
    data = request.get_json()
    print(data)
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = f"""SELECT guid,idexam,idpatient,idreferringphysician,idrequestingphysician,status FROM public.tbexamination WHERE guid='{data['id_examination']}'"""
    cursor.execute(query)
    examination=cursor.fetchone()
    print(examination)
    cursor.execute("SET TIME ZONE 'America/Argentina/Buenos_Aires';")

    query = f"""INSERT INTO public.tbregistrocuentas(guid,patientid,adminid,autorid,solicid,createdon,totalcost,os_cover,orderid,description,status,typeofentry) VALUES (uuid_generate_v4(),
                '{examination[2]}','Peter Lopez','{examination[3]}','{examination[4]}',NOW(),'{data['totalcost']}','{data['oscover']}','{data['id_examination']}',(SELECT description FROM public.exam WHERE guid='{examination[1]}'),'{examination[5]}',true)              """
    cursor.execute(query)
    connection.commit()

    print(query)

    # Actualizar la columna IsExecuted en la tabla public.tbexaminations
    query = f"""
        UPDATE public.tbexamination
        SET isbill = true
        WHERE Guid = '{data['id_examination']}'
    """
    cursor.execute(query)
    connection.commit()


    return jsonify({'success': True})

@blueprint.route('/retirar_dinero', methods=['POST']) 
def retirar_dinero():
    data = request.get_json()
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    print(data)
    tipo=data['tipo']

    if tipo=='p_med':
        cursor.execute("SET TIME ZONE 'America/Argentina/Buenos_Aires';")

        query = f"""INSERT INTO public.tbregistrocuentas(guid,adminid,autorid,createdon,totalcost,typeofentry,typeid,description) VALUES (uuid_generate_v4(),'Peter Lopez','{data['refmed']}',NOW(),'{data['mount']}',false,'{data['tipo']}','Pago de dividendos Medico')"""
        cursor.execute(query)
        connection.commit()

    return jsonify({'success': True})

@blueprint.route('/filter_by_med', methods=['POST']) 
def filter_by_med():
    data = request.get_json()
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    cursor.execute("SELECT fecha::date, monto FROM tbpruebascount ORDER BY fecha")
    results = cursor.fetchall()
    query = f"""SELECT fecha::date, monto FROM tbpruebascount WHERE profesional='{data['id']}' ORDER BY fecha ASC"""
    cursor.execute(query)
    datos=cursor.fetchall()
    montos_por_dia = defaultdict(int)
    fechas = []

    for fecha, monto in datos:
        montos_por_dia[fecha] += monto
        fechas.append(fecha)

    fechas_unicas = sorted(set(fechas))
    montos_ordenados = [montos_por_dia[fecha] for fecha in fechas_unicas]

    return jsonify({
        "labels": [fecha.strftime('%Y-%m-%d') for fecha in fechas_unicas],
        "data": montos_ordenados
    })

@blueprint.route('/filter_by_os', methods=['POST']) 
def filter_by_os():
    data = request.get_json()
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    cursor.execute("SELECT fecha::date, monto FROM tbpruebascount ORDER BY fecha")
    results = cursor.fetchall()
    query = f"""SELECT fecha::date, monto FROM tbpruebascount WHERE obra_social='{data['id']}' ORDER BY fecha ASC"""
    cursor.execute(query)
    datos=cursor.fetchall()
    montos_por_dia = defaultdict(int)
    fechas = []

    for fecha, monto in datos:
        montos_por_dia[fecha] += monto
        fechas.append(fecha)

    fechas_unicas = sorted(set(fechas))
    montos_ordenados = [montos_por_dia[fecha] for fecha in fechas_unicas]

    return jsonify({
        "labels": [fecha.strftime('%Y-%m-%d') for fecha in fechas_unicas],
        "data": montos_ordenados
    })

@blueprint.route('/get_historial_facturacion',  methods=['GET']) 
def get_historial_facturacion():
    connection = psycopg2.connect(**config)
    print("hola")
    cursor = connection.cursor()
    query = """SELECT rc.guid,rc.createdon,rc.typeofentry,rc.description,u.username,rc.adminid,rc.totalcost
                FROM public.tbregistrocuentas rc
                LEFT JOIn public.tbuser as u on u.guid=rc.autorid
                ORDER BY rc.createdon ASC
            """
    cursor.execute(query)

    return jsonify(cursor.fetchall())
   
@blueprint.route('/get_historial_prueba',  methods=['GET']) 
def get_historial_prueba():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT guid, to_char(fecha, 'YYYY-MM-DD') AS fecha, tipo, descripcion, profesional, obra_social, monto 
               FROM public.tbpruebascount 
               ORDER BY fecha ASC"""
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/ingresos_ultima_semana', methods=['GET'])
def ingresos_ultima_semana():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    
    # Consulta para obtener la suma de los montos en los últimos 7 días
    query = """
    SELECT SUM(monto) 
    FROM public.tbpruebascount 
    WHERE fecha >= CURRENT_DATE - INTERVAL '7 days'
    """
    cursor.execute(query)
    ingresos_ultima_semana = cursor.fetchone()[0]
    
    # Asegúrate de cerrar la conexión y el cursor
    cursor.close()
    connection.close()
    
    return jsonify({"ingresos_ultima_semana": ingresos_ultima_semana})

@blueprint.route('/delta_ingresos', methods=['GET'])
def delta_ingresos():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    # Consulta para los ingresos de la última semana
    query_ultima_semana = """
    SELECT SUM(monto) 
    FROM public.tbpruebascount 
    WHERE fecha >= CURRENT_DATE - INTERVAL '7 days'
    """
    cursor.execute(query_ultima_semana)
    ingresos_ultima_semana = cursor.fetchone()[0] or 0

    # Consulta para los ingresos de la semana anterior a la última semana
    query_semana_anterior = """
    SELECT SUM(monto) 
    FROM public.tbpruebascount 
    WHERE fecha >= CURRENT_DATE - INTERVAL '14 days' 
    AND fecha < CURRENT_DATE - INTERVAL '7 days'
    """
    cursor.execute(query_semana_anterior)
    ingresos_semana_anterior = cursor.fetchone()[0] or 0

    # Calcular el delta
    if ingresos_semana_anterior == 0:
        delta = 0
    else:
        delta = round(((ingresos_ultima_semana - ingresos_semana_anterior) / ingresos_semana_anterior) * 100, 2)

    # Asegúrate de cerrar la conexión y el cursor
    cursor.close()
    connection.close()

    return jsonify({"delta_ingresos": delta})

@blueprint.route('/estudios_ultima_semana', methods=['GET'])
def estudios_ultima_semana():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    
    # Consulta para obtener el número de estudios en los últimos 7 días
    query = """
    SELECT COUNT(*) 
    FROM public.tbpruebascount 
    WHERE fecha >= CURRENT_DATE - INTERVAL '7 days'
    """
    cursor.execute(query)
    estudios_ultima_semana = cursor.fetchone()[0]
    
    # Asegúrate de cerrar la conexión y el cursor
    cursor.close()
    connection.close()
    
    return jsonify({"estudios_ultima_semana": estudios_ultima_semana})

@blueprint.route('/delta_estudios', methods=['GET'])
def delta_estudios():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    # Consulta para los estudios de la última semana
    query_ultima_semana = """
    SELECT COUNT(*) 
    FROM public.tbpruebascount 
    WHERE fecha >= CURRENT_DATE - INTERVAL '7 days'
    """
    cursor.execute(query_ultima_semana)
    estudios_ultima_semana = cursor.fetchone()[0]

    # Consulta para los estudios de la semana anterior a la última semana
    query_semana_anterior = """
    SELECT COUNT(*) 
    FROM public.tbpruebascount 
    WHERE fecha >= CURRENT_DATE - INTERVAL '14 days' 
    AND fecha < CURRENT_DATE - INTERVAL '7 days'
    """
    cursor.execute(query_semana_anterior)
    estudios_semana_anterior = cursor.fetchone()[0]

    # Calcular el delta
    if estudios_semana_anterior == 0:
        delta = 0
    else:
        delta = round(((estudios_ultima_semana - estudios_semana_anterior) / estudios_semana_anterior) * 100, 2)

    # Asegúrate de cerrar la conexión y el cursor
    cursor.close()
    connection.close()

    return jsonify({"delta_estudios": delta})




@blueprint.route('/get_comp_med',  methods=['GET']) 
def get_comp_med():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT 
                    profesional,profesional,
                    COUNT(*) AS cantidad_estudios, 
                    SUM(monto) AS total_monto
                FROM 
                    public.tbpruebascount
                GROUP BY 
                    profesional
                ORDER BY 
                    total_monto DESC;"""
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_best_med', methods=['GET'])
def get_best_med():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    
    # Consulta para obtener al médico con mayor producción
    query = """
    SELECT 
        profesional,
        COUNT(*) AS cantidad_estudios, 
        SUM(monto) AS total_monto
    FROM 
        public.tbpruebascount
    GROUP BY 
        profesional
    ORDER BY 
        total_monto DESC
    LIMIT 1;  -- Solo traer el primero
    """
    cursor.execute(query)
    result = cursor.fetchone()
    
    # Asegúrate de cerrar la conexión y el cursor
    cursor.close()
    connection.close()

    return jsonify({
        "profesional": result[0],
        "cantidad_estudios": result[1],
        "total_monto": result[2]
    })

@blueprint.route('/get_best_os', methods=['GET'])
def get_best_os():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    
    # Consulta para obtener la obra social con mayor monto generado
    query = """
    SELECT 
        obra_social,
        COUNT(*) AS cantidad_estudios, 
        SUM(monto) AS total_monto
    FROM 
        public.tbpruebascount
    GROUP BY 
        obra_social
    ORDER BY 
        total_monto DESC
    LIMIT 1;  -- Solo traer la obra social con mayor monto
    """
    cursor.execute(query)
    result = cursor.fetchone()
    
    # Asegúrate de cerrar la conexión y el cursor
    cursor.close()
    connection.close()

    return jsonify({
        "obra_social": result[0],
        "cantidad_estudios": result[1],
        "total_monto": result[2]
    })


@blueprint.route('/get_comp_os',  methods=['GET']) 
def get_comp_os():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT 
                    obra_social, obra_social,
                    COUNT(*) AS cantidad_estudios, 
                    SUM(monto) AS total_monto
                FROM 
                    public.tbpruebascount
                GROUP BY 
                    obra_social
                ORDER BY 
                    total_monto DESC;
                """
    cursor.execute(query)

    return jsonify(cursor.fetchall())

def get_montos():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    cursor.execute("SELECT fecha::date, monto FROM tbpruebascount ORDER BY fecha")
    results = cursor.fetchall()
    connection.close()
    return results

@blueprint.route('/api/montos', methods=['GET'])
def montos():
    datos = get_montos()
    montos_por_dia = defaultdict(int)
    fechas = []

    for fecha, monto in datos:
        montos_por_dia[fecha] += monto
        fechas.append(fecha)

    fechas_unicas = sorted(set(fechas))
    montos_ordenados = [montos_por_dia[fecha] for fecha in fechas_unicas]

    return jsonify({
        "labels": [fecha.strftime('%Y-%m-%d') for fecha in fechas_unicas],
        "data": montos_ordenados
    })

@blueprint.route('/get_origins', methods=['GET']) 
def get_origins():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT o.Guid, o.Description, g.Description AS groupo, o.IsActive, o.ExternalCode, o.PatientCD, o.IsEditingExaminationDisabled, o.PublicationWeb, o.IsPriceListMandatory, o.IsOrderToNotify
               FROM public.IsProvenance o 
               JOIN public.IsProvenanceGroup g ON o.IdProvenanceGroup = g.Guid"""
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_body_parts', methods=['GET']) 
def get_body_parts():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "SELECT guid,description FROM public.IsAnatomicalPart;"
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_ministerial_codes', methods=['GET']) 
def get_codes():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "SELECT guid,code,description,grupo FROM public.IsMinisterialCode"
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_modalities', methods=['GET']) 
def get_modalities():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "SELECT * FROM public.IsModality"
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_exams', methods=['GET']) 
def get_exams():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    # Modificamos la consulta para incluir un JOIN con la tabla IsMinisterialCode
    query = """
        SELECT e.Guid, e.Description, m.Description AS MinisterialCode, n.Description AS modality, e.ExecutionTime, e.IsActive, e.precio 
        FROM public.exam e
        JOIN public.IsMinisterialCode m ON e.IdMinisterialCode = m.Guid
        JOIN public.IsModality n ON e.IdModality = n.Guid
    """
    
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_exams_adm', methods=['GET']) 
def get_exams_adm():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    # Modificamos la consulta para incluir un JOIN con la tabla IsMinisterialCode
    query = """
        SELECT e.Guid, m.Description AS MinisterialCode, e.Description, n.Description AS modality, bp.Description as AnatomicalPart
        FROM public.exam e
        JOIN public.IsMinisterialCode m ON e.IdMinisterialCode = m.Guid
        JOIN public.IsModality n ON e.IdModality = n.Guid
        left JOIN public.IsAnatomicalPart bp ON e.IdBodyPart= bp.Guid
    """
    
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_rooms', methods=['GET']) 
def get_rooms():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "SELECT Guid,Description,ExternalCode,IsActive FROM public.IsRoom"
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_equip_for_exam', methods=['GET']) 
def get_equip_for_exam():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    exam=request.args.get('exam')
    #print("exam:",exam)
    query = f"""SELECT eq.Guid,eq.Description FROM public.IsEquipment eq
                INNER JOIN public.exam ex ON ex.IdModality=eq.IdModality
                WHERE ex.Description='{exam}'"""
    print(query)
    cursor.execute(query)


    return jsonify(cursor.fetchall())


@blueprint.route('/get_mach', methods=['GET']) 
def get_mach():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT e.Guid, e.Description, e.AETitle,e.ExternalCode, r.Description AS Room, d.Description AS MDICOM, e.IsActive, p.Description AS provenance, e.IP, e.BrandEquipment,e.ModelEquipment,e.SNEquipment
                 FROM public.isequipment e
                 JOIN public.IsRoom r ON e.IdRoom = r.Guid
                 JOIN public.IsProvenance p ON e.IdProvenance = p.Guid
                 JOIN public.IsModality d ON e.IdModality = d.Guid
                """
    
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_days', methods=['GET']) 
def get_days():
    agenda_param = request.args.get('agenda')
    
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    
    # Obtener el IdAgenda
    query = "SELECT Guid FROM public.IsAgenda WHERE Description=%s"
    cursor.execute(query, (agenda_param,))
    IdAgenda = cursor.fetchall()[0][0]

    # Obtener los datos de la tabla IsAgendaDays
    query = "SELECT * FROM public.IsAgendaDays WHERE IdAgenda=%s"
    cursor.execute(query, (IdAgenda,))
    datos = cursor.fetchall()

    data=[]
    for dato in datos:
        fila=[str(dato[0]),dato[2],str(dato[3]),str(dato[4]),dato[5],dato[6]]
        data.append(fila)
    
    connection.close()

    return jsonify(data)

@blueprint.route('/get_agendas', methods=['GET']) 
def get_agendas():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT a.Guid, a.Description, e.Description AS Equipment, a.ExternalCode, a.IsActive,
                    TO_CHAR(a.StartDate, 'DD-MM-YYYY') AS FormattedStartDate,
                    TO_CHAR(a.EndDate, 'DD-MM-YYYY') AS FormattedEndDate
                FROM public.IsAgenda a
                JOIN public.IsEquipment e ON a.IdEquipment = e.Guid;

            """
    print("query: ",query)
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_business_units', methods=['GET']) 
def get_business_units():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT * FROM public.IsBusinessUnit"""
    
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_equipo_modal', methods=['GET']) 
def get_equipo_modal():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT guid,aetitle,externalcode FROM public.isequipment"""
    
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_domain_procede', methods=['GET']) 
def get_domain_procede():
    
    BU_name=request.args.get('BU')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = """SELECT Guid FROM public.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(BU_name,))
    bu_id=cursor.fetchall()[0][0]
    query = """SELECT Guid,IdProvenance FROM public.RelBusinessUnitProvenance WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(bu_id,))
    provenance_group=cursor.fetchall()
    

    response=[]
    for provenance in provenance_group:
        query="""SELECT Description from public.IsProvenance WHERE Guid=%s"""
        cursor.execute(query,(provenance[1],))
        ProvenanceName=cursor.fetchall()[0][0]
        fila=[provenance[0],ProvenanceName]
        response.append(fila)

    return jsonify(response)
    
@blueprint.route('/get_domain_equipment', methods=['GET']) 
def get_domain_equipment():
    
    BU_name=request.args.get('BU')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = """SELECT Guid FROM public.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(BU_name,))
    bu_id=cursor.fetchall()[0][0]
    
    query = """SELECT Guid,IdEquipment FROM public.RelBusinessUnitEquipment WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(bu_id,))
    equipment_group=cursor.fetchall()
    
    #print(equipment_group)
    response=[]
    for equip in equipment_group:
        query="""SELECT Description from public.IsEquipment WHERE Guid=%s"""
        cursor.execute(query,(equip[1],))
        EquipName=cursor.fetchall()[0][0]
        fila=[equip[0],EquipName]
        response.append(fila)
    
    return jsonify(response)


@blueprint.route('/get_domain_modalities', methods=['GET']) 
def get_domain_modalities():
    
    BU_name=request.args.get('BU')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = """SELECT Guid FROM public.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(BU_name,))
    bu_id=cursor.fetchall()[0][0]
    query = """SELECT Guid,IdModality FROM public.RelBusinessUnitModality WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(bu_id,))
    modalities_group=cursor.fetchall()

    response=[]
    for modality in modalities_group:
        query="""SELECT Description from public.IsModality WHERE Guid=%s"""
        cursor.execute(query,(modality[1],))
        ProvenanceName=cursor.fetchall()[0][0]
        fila=[modality[0],ProvenanceName]
        response.append(fila)

    return jsonify(response)

@blueprint.route('/get_check_procede', methods=['GET']) 
def get_check_procede():
    
    BU_name=request.args.get('BU')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = """SELECT Guid FROM public.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(BU_name,))
    bu_id=cursor.fetchall()[0][0]
    query = """SELECT IdProvenance FROM public.RelBusinessUnitProvenance WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(bu_id,))
    provenance_group=cursor.fetchall()
    
    idProvenances_group=[]

    for provenance in provenance_group:
        idProvenances_group.append(provenance[0])
    
    query = """SELECT Guid,Description FROM public.IsProvenance"""
    cursor.execute(query)
    all_procedences=cursor.fetchall()

    response=[]
    for procedence in all_procedences:
        if procedence[0] in idProvenances_group:
            fila=[1,procedence[0],procedence[1]]
        else:
            fila=[0,procedence[0],procedence[1]]
        response.append(fila)
    return jsonify(response)


@blueprint.route('/get_check_equip', methods=['GET']) 
def get_check_equip():
    
    BU_name=request.args.get('BU')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    #Obtengo el nombre del bu, y con eso obtengo el id
    query = """SELECT Guid FROM public.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(BU_name,))
    bu_id=cursor.fetchone()[0]
    #print("bu_id> "+bu_id)

    #En la lista de relaciones, obtengo todos los id de los equipment que tengan relacion con el id del bu que acabo de obtener
    query = """SELECT IdEquipment FROM public.RelBusinessUnitEquipment WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(bu_id,))
    equipment_group=cursor.fetchall()
    
    idEquipment_group=[]

    for equip in equipment_group:
        idEquipment_group.append(equip[0])

    # en idEquipment_group tengo todos los id de los equipos que tienen relacion
    
    #Aca saco toda la lista de los equipos
    query = """SELECT Guid,Description FROM public.IsEquipment"""
    cursor.execute(query)
    all_equipment=cursor.fetchall()

    response=[]
    #Repaso toda la lista, y chequeo si el que tengo, tiene union, y ahi lo agrego a la respuesta.
    for equip in all_equipment:
        if equip[0] in idEquipment_group:
            fila=[1,equip[0],equip[1]]
        else:
            fila=[0,equip[0],equip[1]]
        response.append(fila)

    
    return jsonify(response)


@blueprint.route('/get_patient_history', methods=['POST'])
def get_patient_history():
    # Obtener el ID del paciente desde la solicitud POST
    data = request.get_json()
    patient_id = data.get('id')

    if not patient_id:
        return jsonify({"error": "ID de paciente no proporcionado"}), 400

    # Conectar a la base de datos
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    # Consulta SQL para obtener el historial del paciente desde la tabla tbexamination
    query = f"""
        SELECT ex.guid,localacc, CONCAT(us.name, ' ', us.surname) AS refPhy, rp.description as ReqPhy, reportdate, equip.description, isimage
        FROM public.tbexamination ex
        LEFT JOIN public.isrequestingphysician rp on rp.guid=ex.idrequestingphysician
        LEFT JOIN public.tbuser us on us.guid=ex.idreferringphysician
        LEFT JOIN public.isequipment equip on equip.guid=ex.idequipment
        WHERE idpatient = (SELECT patientid FROM public.datapatient WHERE guid='{patient_id}') and isreported=1
    """
    print(query)
    # Ejecutar la consulta con el ID del paciente
    cursor.execute(query)
    
    # Obtener todos los resultados
    results = cursor.fetchall()

    # Cerrar la conexión
    cursor.close()
    connection.close()

    # Devolver los resultados en formato JSON
    return jsonify(results)


@blueprint.route('/get_check_mod', methods=['GET']) 
def get_check_mod():
    
    BU_name=request.args.get('BU')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    #Obtengo el nombre del bu, y con eso obtengo el id
    query = """SELECT Guid FROM public.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(BU_name,))
    bu_id=cursor.fetchone()[0]
    

    #En la lista de relaciones, obtengo todos los id de los equipment que tengan relacion con el id del bu que acabo de obtener
    query = """SELECT IdModality FROM public.RelBusinessUnitModality WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(bu_id,))
    modalities_group=cursor.fetchall()
    
    idModality_group=[]

    for modality in modalities_group:
        idModality_group.append(modality[0])

    # en idModality_group tengo todos los id de los modalidades que tienen relacion
    
    #Aca saco toda la lista de los equipos
    query = """SELECT Guid,Description FROM public.IsModality"""
    cursor.execute(query)
    all_equipment=cursor.fetchall()

    response=[]
    #Repaso toda la lista, y chequeo si el que tengo, tiene union, y ahi lo agrego a la respuesta.
    for mod in all_equipment:
        if mod[0] in idModality_group:
            fila=[1,mod[0],mod[1]]
        else:
            fila=[0,mod[0],mod[1]]
        response.append(fila)


    return jsonify(response)


@blueprint.route('/update_procede', methods=['POST']) 
def update_procede():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    name_bu = request.form['name_bu']
    query="""SELECT Guid FROM public.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(name_bu,))
    id_bu=cursor.fetchone()[0]

    seleccion_multiple_valores = request.form.getlist('seleccion_multiple[]')
    
    # Hacer algo con los valores, por ejemplo, imprimirlos
    print(seleccion_multiple_valores)

    query="""SELECT IdProvenance FROM public.RelBusinessUnitProvenance WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(id_bu,))
    lista_procedencias = [procedencia[0] for procedencia in cursor.fetchall()] #Aca tengo la lista de procedencias para ese bu

    # Aca recorro los seleccionados. Si el seleccionado no está en la lista de relaciones, agrego la relación
    for id in seleccion_multiple_valores:
        
        if id not in lista_procedencias:
            print("el id= "+id+" no está en la lista de proc")
            query="""INSERT INTO public.RelBusinessUnitProvenance(Guid,IdBusinessUnit,IdProvenance) VALUES (uuid_generate_v4(),%s,%s)"""
            cursor.execute(query,(id_bu,id))
            connection.commit()

    #Ahora tengo que recorrer la lista de las relaciones creadas. Si está creada una relación, pero no está en las actuales, debo eliminar esa relación.
    for procedencia in lista_procedencias:
        if procedencia not in seleccion_multiple_valores:
            print("saque a: "+procedencia)
            query="""DELETE FROM public.RelBusinessUnitProvenance WHERE IdProvenance = %s and IdBusinessUnit=%s;"""
            cursor.execute(query,(procedencia,id_bu,))
            connection.commit()

    response=[]
    for provenance in seleccion_multiple_valores:
        query="""SELECT Description FROM public.IsProvenance WHERE Guid=%s"""
        cursor.execute(query,(provenance,))
        response.append(cursor.fetchone()[0])
    
    return jsonify(response)

@blueprint.route('/update_equip', methods=['POST']) 
def update_equip():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    name_bu = request.form['name_bu_equip']
    query="""SELECT Guid FROM public.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(name_bu,))
    id_bu=cursor.fetchone()[0]

    seleccion_multiple_valores = request.form.getlist('seleccion_multiple[]')

    query="""SELECT IdEquipment FROM public.RelBusinessUnitEquipment WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(id_bu,))
    lista_equipment = [equipment[0] for equipment in cursor.fetchall()] #Aca tengo la lista de procedencias para ese bu

    # Aca recorro los seleccionados. Si el seleccionado no está en la lista de relaciones, agrego la relación
    for id in seleccion_multiple_valores:
        
        if id not in lista_equipment:
            query="""INSERT INTO public.RelBusinessUnitEquipment(Guid,IdBusinessUnit,IdEquipment) VALUES (uuid_generate_v4(),%s,%s)"""
            cursor.execute(query,(id_bu,id))
            connection.commit()

    #Ahora tengo que recorrer la lista de las relaciones creadas. Si está creada una relación, pero no está en las actuales, debo eliminar esa relación.
    for procedencia in lista_equipment:
        if procedencia not in seleccion_multiple_valores:
            #print("saque a: "+procedencia)
            query="""DELETE FROM public.RelBusinessUnitEquipment WHERE IdEquipment = %s and IdBusinessUnit=%s;"""
            cursor.execute(query,(procedencia,id_bu,))
            connection.commit()

    response=[]
    for provenance in seleccion_multiple_valores:
        query="""SELECT Description FROM public.IsEquipment WHERE Guid=%s"""
        cursor.execute(query,(provenance,))
        response.append(cursor.fetchone()[0])
    return jsonify(response)

@blueprint.route('/update_mod', methods=['POST']) 
def update_mod():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    name_bu = request.form['name_bu_mod']
    query="""SELECT Guid FROM public.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(name_bu,))
    id_bu=cursor.fetchone()[0]

    seleccion_multiple_valores = request.form.getlist('seleccion_multiple[]')
    
    query="""SELECT IdModality FROM public.RelBusinessUnitModality WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(id_bu,))
    lista_modality = [equipment[0] for equipment in cursor.fetchall()] #Aca tengo la lista de modality para ese bu

    # Aca recorro los seleccionados. Si el seleccionado no está en la lista de relaciones, agrego la relación
    for id in seleccion_multiple_valores:
        
        if id not in lista_modality:
            #print("el id= "+id+" no está en la lista de proc")
            query="""INSERT INTO public.RelBusinessUnitModality(Guid,IdBusinessUnit,IdModality) VALUES (uuid_generate_v4(),%s,%s)"""
            cursor.execute(query,(id_bu,id))
            connection.commit()

    #Ahora tengo que recorrer la lista de las relaciones creadas. Si está creada una relación, pero no está en las actuales, debo eliminar esa relación.
    for modality in lista_modality:
        if modality not in seleccion_multiple_valores:
            #print("saque a: "+modality)
            query="""DELETE FROM public.RelBusinessUnitModality WHERE IdModality = %s and IdBusinessUnit=%s;"""
            cursor.execute(query,(modality,id_bu,))
            connection.commit()

    response=[]
    for provenance in seleccion_multiple_valores:
        query="""SELECT Description FROM public.IsModality WHERE Guid=%s"""
        cursor.execute(query,(provenance,))
        response.append(cursor.fetchone()[0])
    # print(response)
    return jsonify(response)


@blueprint.route('/eliminar_grupo', methods=['POST']) 
def eliminar_grupo():
    data = request.json
    id = data.get('id')
    
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.IsProvenanceGroup WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()

    return jsonify("Fila eliminada")


@blueprint.route('/eliminar_item_agenda', methods=['POST']) 
def eliminar_item_agenda():
    data = request.json
    id = data.get('id')
    
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.isagendameditem WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()

    return jsonify("Fila eliminada")


@blueprint.route('/eliminar_med_sol', methods=['POST']) 
def eliminar_med_sol():
    data = request.json
    id = data.get('id')
    print(data)
    
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.isrequestingphysician WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()

    return jsonify("Fila eliminada")


@blueprint.route('/eliminar_procedencia', methods=['POST']) 
def eliminar_procedencia():
    data = request.json
    id = data.get('id')
    
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.IsProvenance WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()

    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_codigo', methods=['POST']) 
def eliminar_codigo():
    data = request.json
    id = data.get('id')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.IsMinisterialCode WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_mod', methods=['POST']) 
def eliminiar_mod():
    data = request.json
    id = data.get('id')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.IsModality WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_ap', methods=['POST']) 
def eliminar_ap():
    data = request.json
    id = data.get('id')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.IsAnatomicalPart WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_cita', methods=['POST']) 
def eliminar_cita():
    data = request.json
    id = data.get('id')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.tbagendaevents WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_examen', methods=['POST']) 
def eliminar_examen():
    data = request.json
    id = data.get('id')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.exam WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_room', methods=['POST']) 
def eliminar_room():
    data = request.json
    id = data.get('id')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.IsRoom WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_mach', methods=['POST']) 
def eliminar_mach():
    data = request.json
    id = data.get('id')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.IsEquipment WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_agenda', methods=['POST']) 
def eliminar_agenda():
    data = request.json
    id = data.get('id')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.IsAgenda WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_dia', methods=['POST']) 
def eliminar_dia():
    data = request.json
    id = data.get('id')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.IsAgendaDays WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_bu', methods=['POST']) 
def eliminar_bu():
    data = request.json
    id = data.get('id')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM public.IsBusinessUnit WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/agregar_go', methods=['POST']) 
def agregar_go():
    respuesta = request.form.to_dict()
    is_ex = respuesta.get('IsEx') == 'on'
    respuesta['IsEx'] = 1 if is_ex else 0

    is_ps = respuesta.get('ps') == 'on'
    respuesta['ps'] = 1 if is_ps else 0
    print(respuesta)
    response=[respuesta['Description'],respuesta['IsEx'],respuesta['ps'],respuesta['delaydays']]

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO public.IsProvenanceGroup(Guid, Description, IsExternal, IsER, DelayDays) VALUES (uuid_generate_v4(), %s, %s, %s, %s)"
    
    cursor.execute(query, (respuesta['Description'], respuesta['IsEx'], respuesta['ps'], respuesta['delaydays']))
    connection.commit()
    connection.close()

    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}
    return jsonify(response_data)


@blueprint.route('/agregar_med_sol', methods=['POST']) 
def agregar_med_sol():
    respuesta = request.form.to_dict()
    print(respuesta)
    response=[respuesta['description'],respuesta['phone'],respuesta['mail'],respuesta['notes']]

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = f"INSERT INTO public.isrequestingphysician(guid,description,phone,mail,note) VALUES (uuid_generate_v4(),'{respuesta['description']}','{respuesta['phone']}','{respuesta['mail']}','{respuesta['notes']}')"
    
    cursor.execute(query)
    connection.commit()
    connection.close()

    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}
    return jsonify(response_data)

@blueprint.route('/agregar_item', methods=['POST']) 
def agregar_item():
    respuesta = request.form.to_dict()
    print(respuesta)
    response=[respuesta['day'],respuesta['timefrom'],respuesta['timeto'],respuesta['initday'],respuesta['finishday']]

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = f"INSERT INTO public.isagendameditem(guid,day,idmed,timefrom,timeto,initday,finishday) VALUES (uuid_generate_v4(),'{respuesta['day']}','{respuesta['id_agenda_med']}','{respuesta['timefrom']}','{respuesta['timeto']}','{respuesta['initday']}','{respuesta['finishday']}')"
    
    cursor.execute(query)
    connection.commit()
    connection.close()

    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}
    return jsonify(response_data)

@blueprint.route('/create_user', methods=['POST'])
def create_user():
    respuesta = request.form.to_dict()
    print(respuesta)
    dni = respuesta.get('nationalnumber')
    mail = respuesta.get('text_mail')
    name = respuesta.get('name')
    surname = respuesta.get('surname')
    username = respuesta.get('username')
    rol = respuesta.get('s_type_of_user')
    
    
    # Conexión a la base de datos secundaria y creación del usuario en tbuser
    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        insert_query = """
            INSERT INTO public.tbuser(guid, name, surname, username, nationalnumber, mail, idrole, isactive)
            VALUES (uuid_generate_v4(), %s, %s, %s, %s, %s, %s, 0)
        """
        cursor.execute(insert_query, (name, surname, username, dni, mail, rol))
        
        select_query = "SELECT description FROM public.isrole WHERE guid=%s"
        cursor.execute(select_query, (rol,))
        rol_desc = cursor.fetchone()[0]
        
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error en la base de datos secundaria: {e}")
        return jsonify({'status': 'error', 'message': 'Error al crear el usuario en tbuser', 'details': str(e)}), 500

    # Creación del usuario en la base de datos principal
    try:
        # Verificar si el usuario ya existe en la base de datos principal
        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({'status': 'error', 'message': 'El nombre de usuario ya existe en la base de datos principal'}), 400

        # # Hashear la contraseña
        hashed_password = generate_password_hash('1234')

        print("estoy aca")

        user = Users(
            username=username,
            email=mail,
            password=hashed_password,  # Almacenar la contraseña hasheada
            user_type=rol_desc
        )
        db.session.add(user)
        db.session.commit()

    except Exception as e:
        print(f"Error en la base de datos principal: {e}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Error al crear el usuario en la base de datos principal', 'details': str(e)}), 500

    # Preparar los datos para la respuesta
    response=[username,rol_desc,name,surname,dni,mail,'0']
    response_data = {
        'status': 'OK',
        'message': 'Inserción exitosa',
        'data': response}
    return jsonify(response_data)


@blueprint.route('/delete_user', methods=['POST'])
def delete_user():
    respuesta = request.get_json()  # Cambiar a get_json para recibir datos en formato JSON
    print(respuesta)
    user_id = respuesta.get('id')
    
    users_main_db  = []
    users_main_db   = Users.query.all()
    print("Usuarios en tbuser:")
    for user in users_main_db:
        print(user)

    # Conexión a la base de datos secundaria y eliminación del usuario en tbuser
    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()

        query=f"SELECT username FROM public.tbuser WHERE guid='{user_id}'"
        cursor.execute(query)
        username=cursor.fetchone()[0]
        print("username: ",username)
        
        delete_query = "DELETE FROM public.tbuser WHERE guid=%s"
        cursor.execute(delete_query, (user_id,))
        connection.commit()
        cursor.close()
        connection.close()
    except Exception as e:
        print(f"Error en la base de datos secundaria: {e}")
        return jsonify({'status': 'error', 'message': 'Error al eliminar el usuario en tbuser'}), 500

    # Eliminación del usuario en la base de datos principal
    try:
        user = Users.query.filter_by(username=username).first()
        if user:
            db.session.delete(user)
            db.session.commit()
        else:
            return jsonify({'status': 'error', 'message': 'El usuario no existe en la base de datos principal'}), 404
    except Exception as e:
        print(f"Error en la base de datos principal: {e}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Error al eliminar el usuario en la base de datos principal'}), 500
    
    return jsonify({"success": True})

@blueprint.route('/edit_user', methods=['POST'])
def edit_user():
    respuesta = request.form.to_dict()  # Cambiar a get_json para recibir datos en formato JSON
    print(respuesta)
    user_id = respuesta.get('id_user')
    username = respuesta.get('username')
    name = respuesta.get('name')
    surname = respuesta.get('surname')
    dni = respuesta.get('nationalnumber')
    type_of_user = respuesta.get('s_type_of_user')
    mail = respuesta.get('text_mail')

    # Imprimir usuarios en pantalla (consola del servidor)
    users_main_db = []
    users_main_db = Users.query.all()
    print("Usuarios en la base de datos principal:")
    for user in users_main_db:
        print(user)

    # Conexión a la base de datos secundaria y actualización del usuario en tbuser
    try:
        connection = psycopg2.connect(**config)
        cursor = connection.cursor()
        
        query=f"SELECT username FROM public.tbuser WHERE guid='{user_id}'"
        cursor.execute(query)
        old_username=cursor.fetchone()[0]
        print("old:",old_username)

        update_query = """
            UPDATE public.tbuser 
            SET username = %s, name = %s, surname = %s, nationalnumber = %s, idrole = %s, mail=%s
            WHERE guid = %s
        """
        cursor.execute(update_query, (username, name, surname, dni, type_of_user,mail, user_id))
        connection.commit()

    except Exception as e:
        print(f"Error en la base de datos secundaria: {e}")
        return jsonify({'status': 'error', 'message': 'Error al actualizar el usuario en tbuser'}), 500

    
    query = f"""SELECT description FROM public.isrole WHERE guid='{type_of_user}'"""
    cursor.execute(query)
    type_of_user=cursor.fetchone()[0]
    cursor.close()
    connection.close()
    print("tipo de usuario:",type_of_user)
    # Actualización del usuario en la base de datos principal
    try:
        user = Users.query.filter_by(username=old_username).first()  # Utilizando id para la consulta
        if user:
            user.username = username
            user.user_type = type_of_user
            user.email=mail
            db.session.commit()
        else:
            return jsonify({'status': 'error', 'message': 'El usuario no existe en la base de datos principal'}), 404
    except Exception as e:
        print(f"Error en la base de datos principal: {e}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Error al actualizar el usuario en la base de datos principal'}), 500

    

    return jsonify({"success": True})


@blueprint.route('/agregar_codigo', methods=['POST']) 
def agregar_codigo():
    respuesta = request.form.to_dict()
    print(respuesta)
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO public.IsMinisterialCode(Guid, Code, Description, `Group`) VALUES (uuid_generate_v4(), %s, %s, %s)"
    
    cursor.execute(query, (respuesta['ministerial_code'], respuesta['Description_code'], respuesta['group_code']))
    connection.commit()
    connection.close()
    response=[respuesta['ministerial_code'],respuesta['Description_code'],respuesta['group_code'],respuesta['id_code']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    return jsonify(response_data)

@blueprint.route('/agregar_mod', methods=['POST']) 
def agregar_mod():
    respuesta = request.form.to_dict()

    val = respuesta.get('IsMandatoryEquipmentChange') == 'on'
    respuesta['IsMandatoryEquipmentChange'] = 1 if val else 0
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO public.IsModality(Guid, Description, ExternalCode, IsMandatoryEquipmentChange) VALUES (uuid_generate_v4(), %s, %s, %s)"
    
    cursor.execute(query, (respuesta['Description_mod'], respuesta['ext_code_mod'], respuesta['IsMandatoryEquipmentChange']))
    connection.commit()
    connection.close()
    response=[respuesta['Description_mod'],respuesta['ext_code_mod'], respuesta['IsMandatoryEquipmentChange'],respuesta['id_mod']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    return jsonify(response_data)

@blueprint.route('/agregar_examen', methods=['POST']) 
def agregar_examen():
    respuesta = request.form.to_dict()

    val = respuesta.get('IsAc_ex') == 'on'
    respuesta['IsAc_ex'] = 1 if val else 0
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO public.exam(Guid, Description, IdMinisterialCode, IdModality,ExecutionTime,IsActive,precio) VALUES (uuid_generate_v4(), %s, %s, %s, %s,%s, %s)"
    
    cursor.execute(query, (respuesta['Description_ex'], respuesta['s_cod_min'], respuesta['s_modality'], respuesta['time_execution'], respuesta['IsAc_ex'], respuesta['precio']))
    connection.commit()
    
    query= "SELECT Description from public.IsMinisterialCode WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_cod_min'],))
    cod_min=cursor.fetchone()[0]

    query= "SELECT Description from public.IsModality WHERE Guid=%s"
  

    cursor.execute(query,(respuesta['s_modality'],))
    modality=cursor.fetchone()[0]

    response=[respuesta['Description_ex'],cod_min, modality,respuesta['time_execution'],respuesta['IsAc_ex'],respuesta['precio']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    connection.close()
    return jsonify(response_data)

@blueprint.route('/agregar_ap', methods=['POST']) 
def agregar_ap():
    respuesta = request.form.to_dict()
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO public.IsAnatomicalPart(Guid, Description) VALUES (uuid_generate_v4(), %s)"
    print(respuesta)
    cursor.execute(query, (respuesta['Description_ap'],))
    connection.commit()
    connection.close()
    
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': (respuesta['Description_ap'],)}
    return jsonify(response_data)


@blueprint.route('/agregar_origen', methods=['POST']) 
def agregar_origen():
    respuesta = request.form.to_dict()
    print("estoy aca")
    
    val = respuesta.get('IsAc') == 'on'
    respuesta['IsAc'] = 1 if val else 0

    val = respuesta.get('PatientCD') == 'on'
    respuesta['PatientCD'] = 1 if val else 0

    val = respuesta.get('IsEditingExaminationDisabled') == 'on'
    respuesta['IsEditingExaminationDisabled'] = 1 if val else 0

    val = respuesta.get('PublicationWeb') == 'on'
    respuesta['PublicationWeb'] = 1 if val else 0

    val = respuesta.get('IsAutomaticPrinting') == 'on'
    respuesta['IsAutomaticPrinting'] = 1 if val else 0

    val = respuesta.get('IsChargeMandatory') == 'on'
    respuesta['IsChargeMandatory'] = 1 if val else 0

    val = respuesta.get('IsPriceListMandatory') == 'on'
    respuesta['IsPriceListMandatory'] = 1 if val else 0

    val = respuesta.get('IsOrderToNotify') == 'on'
    respuesta['IsOrderToNotify'] = 1 if val else 0
    print(respuesta)
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query="SELECT Description From public.IsProvenanceGroup WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_go'],))

    Description=cursor.fetchone()[0]
    query = "INSERT INTO public.IsProvenance(Guid, Description, IdProvenanceGroup, IsActive, ExternalCode,PatientCD,PublicationWeb,IsPriceListMandatory,IsChargeMandatory,IsOrderToNotify) VALUES (uuid_generate_v4(), %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    
    cursor.execute(query,(respuesta['Description_o'],respuesta['s_go'],respuesta['IsAc'],respuesta['AltCode_or'],respuesta['PatientCD'],respuesta['PublicationWeb'],respuesta['IsPriceListMandatory'],respuesta['IsChargeMandatory'],respuesta['IsOrderToNotify']))
    connection.commit()
    response=[respuesta['Description_o'],Description,respuesta['IsAc'],respuesta['AltCode_or'],respuesta['PatientCD'],respuesta['PublicationWeb'],respuesta['IsPriceListMandatory'],respuesta['IsChargeMandatory'],respuesta['IsOrderToNotify']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}
    return jsonify(response_data)


@blueprint.route('/agregar_mach', methods=['POST']) 
def agregar_mach():
    respuesta = request.form.to_dict()
    
    val = respuesta.get('IsAc_mach') == 'on'
    respuesta['IsAc_mach'] = 1 if val else 0
    print("query mod: ",respuesta)
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "INSERT INTO public.IsEquipment(Guid, Description, AETitle,ExternalCode, IdRoom,IdProvenance,IdModality,BrandEquipment,ModelEquipment,SNEquipment,IsActive,IP) VALUES (uuid_generate_v4(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    
    cursor.execute(query,(respuesta['Description_mach'],respuesta['AETitle'],respuesta['Ext_code_equip'],respuesta['s_sala'],respuesta['s_proc'],respuesta['s_moda'],respuesta['equip_brand'],respuesta['equip_model'],respuesta['equip_sn'],respuesta['IsAc_mach'],respuesta['equip_ip']))
    connection.commit()
    
    query= "SELECT Description from public.IsProvenance WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_proc'],))
    provenance=cursor.fetchall()[0][0]

    query= "SELECT Description from public.IsModality WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_moda'],))
    modality=cursor.fetchall()[0][0]

    query= "SELECT Description from public.IsRoom WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_sala'],))
    sala=cursor.fetchall()[0][0]

    response=[respuesta['Description_mach'],respuesta['AETitle'],respuesta['Ext_code_equip'],sala, modality,respuesta['IsAc_mach'],provenance,respuesta['equip_ip'],respuesta['equip_brand'],respuesta['equip_model'],respuesta['equip_sn']]

    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}
    return jsonify(response_data)


@blueprint.route('/agregar_dia', methods=['POST']) 
def agregar_dia():
    respuesta = request.form.to_dict()
    
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query= "SELECT Guid FROM public.IsAgenda WHERE Description=%s"
    cursor.execute(query,(respuesta["id_agenda_"],))
    IdAgenda=cursor.fetchall()[0][0]
    
    query = "INSERT INTO public.IsAgendaDays(Guid, IdAgenda, Day,StartTime, EndTime,SlotNumber,PlacePerSlot) VALUES (uuid_generate_v4(), %s, %s, %s, %s, %s, %s)"
    
    cursor.execute(query,(IdAgenda,respuesta['dia_ag'],respuesta['hora_inicio_dia'],respuesta['hora_final_dia'],respuesta['n_slots'],respuesta['lugares_x_slots'],))
    connection.commit()
    

    response=[respuesta['dia_ag'],respuesta['hora_inicio_dia'],respuesta['hora_final_dia'],respuesta['n_slots'],respuesta['lugares_x_slots']]

    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}
    return jsonify(response_data)

@blueprint.route('/agregar_business_units', methods=['POST']) 
def agregar_business_units():
    respuesta = request.form.to_dict()

    val = respuesta.get('IsAc_bu') == 'on'
    respuesta['IsAc_bu'] = 1 if val else 0

    val = respuesta.get('tecnico_obl') == 'on'
    respuesta['tecnico_obl'] = 1 if val else 0

    val = respuesta.get('questions_manda') == 'on'
    respuesta['questions_manda'] = 1 if val else 0

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO public.IsBusinessUnit(Guid, Description, Code, ExternalCode,HttpPacs,IsActive,IsQuestionListMandatory,IsTechnicianMandatory) VALUES (uuid_generate_v4(), %s, %s, %s, %s, %s, %s, %s)"
    
    cursor.execute(query, (respuesta['Description_bu'], respuesta['code_bu'], respuesta['ex_code_bu'], respuesta['http_pacs'], respuesta['IsAc_bu'],respuesta['questions_manda'],respuesta['tecnico_obl'],))
    connection.commit()
    

    response=[respuesta['Description_bu'],respuesta['code_bu'],respuesta['ex_code_bu'],respuesta['IsAc_bu'],respuesta['http_pacs'],respuesta['questions_manda'],respuesta['tecnico_obl']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    connection.close()
    return jsonify(response_data)


@blueprint.route('/actualizar_go', methods=['POST']) 
def actualizar_go():
    # Hacer una copia mutable de request.form
    respuesta = request.form.to_dict()

    is_ex = respuesta.get('IsEx') == 'on'
    respuesta['IsEx'] = 1 if is_ex else 0

    is_ps = respuesta.get('ps') == 'on'
    respuesta['ps'] = 1 if is_ps else 0

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    # Modificar la consulta SQL para no incluir la columna Guid
    query = "UPDATE public.IsProvenanceGroup SET Description = %s, IsExternal = %s, IsER = %s, DelayDays = %s WHERE Guid = %s;"
    
    cursor.execute(query,(respuesta['Description'],respuesta['IsEx'],respuesta['ps'],respuesta['delaydays'],respuesta['id_go']))
    connection.commit()
    response=[respuesta['Description'],respuesta['IsEx'],respuesta['ps'],respuesta['delaydays']]
    # Crear un objeto de respuesta JSON
    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}

    # Enviar el objeto JSON como respuesta
    return jsonify(response_data)

@blueprint.route('/actualizar_room', methods=['POST']) 
def actualizar_room():
    # Hacer una copia mutable de request.form
    respuesta = request.form.to_dict()

    is_ex = respuesta.get('IsAc_room') == 'on'
    respuesta['IsAc_room'] = 1 if is_ex else 0
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    # Modificar la consulta SQL para no incluir la columna Guid
    query = "UPDATE public.IsRoom SET Description = %s, ExternalCode = %s, IsActive = %s WHERE Guid = %s;"
    
    cursor.execute(query,(respuesta['Description_room'],respuesta['ExtCode_room'],respuesta['IsAc_room'],respuesta['id_room']))
    connection.commit()
    
    response=[respuesta['Description_room'],respuesta['ExtCode_room'],respuesta['IsAc_room']]
    # Crear un objeto de respuesta JSON
    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}

    # Enviar el objeto JSON como respuesta
    return jsonify(response_data)

@blueprint.route('/agregar_room', methods=['POST']) 
def agregar_room():
    respuesta = request.form.to_dict()

    val = respuesta.get('IsAc_room') == 'on'
    respuesta['IsAc_room'] = 1 if val else 0
    
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO public.IsRoom(Guid, Description, ExternalCode, IsActive) VALUES (uuid_generate_v4(), %s, %s, %s)"
    
    cursor.execute(query, (respuesta['Description_room'], respuesta['ExtCode_room'], respuesta['IsAc_room'],))
    connection.commit()
    

    response=[respuesta['Description_room'],respuesta['ExtCode_room'],respuesta['IsAc_room']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    connection.close()
    return jsonify(response_data)

@blueprint.route('/agregar_agendas', methods=['POST']) 
def agregar_agenda():
    respuesta = request.form.to_dict()

    val = respuesta.get('IsAc_ag') == 'on'
    respuesta['IsAc_ag'] = 1 if val else 0
    
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    fin=respuesta.get('fecha_fin_agenda_input') 
    if fin=='':
        respuesta['fecha_fin_agenda_input']=None

    print(respuesta)
    query = "INSERT INTO public.IsAgenda(Guid, Description, IdEquipment, StartDate,EndDate,ExternalCode,IsActive) VALUES (uuid_generate_v4(), %s, %s, %s,%s,%s,%s)"
    
    cursor.execute(query, (respuesta['Description_agenda'], respuesta['s_equip'], respuesta['fecha_inicio_agenda_input'],respuesta['fecha_fin_agenda_input'],respuesta['Ex_agenda'],respuesta['IsAc_ag']))
    connection.commit()

    query="SELECT Description FROM public.IsEquipment WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_equip'],))
    equipo=cursor.fetchall()[0][0]

    response=[respuesta['Description_agenda'],equipo,respuesta['Ex_agenda'],respuesta['IsAc_ag'],respuesta['fecha_inicio_agenda_input'],respuesta['fecha_fin_agenda_input']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    connection.close()
    return jsonify(response_data)

@blueprint.route('/actualizar_codigo', methods=['POST']) 
def actualizar_codigo():
    # Hacer una copia mutable de request.form
    respuesta = request.form.to_dict()

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    
    # Modificar la consulta SQL para no incluir la columna Guid
    query = "UPDATE public.IsMinisterialCode SET Code = %s, Description = %s, `Group` = %s WHERE Guid = %s;"
    
    cursor.execute(query,(respuesta['ministerial_code'],respuesta['Description_code'],respuesta['group_code'],respuesta['id_code']))
    connection.commit()
    
    # Crear un objeto de respuesta JSON
    response=[respuesta['ministerial_code'],respuesta['Description_code'],respuesta['group_code']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}

    # Enviar el objeto JSON como respuesta
    return jsonify(response_data)

@blueprint.route('/actualizar_med_sol', methods=['POST']) 
def actualizar_med_sol():
    # Hacer una copia mutable de request.form
    respuesta = request.form.to_dict()
    print(respuesta)
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    
    # Modificar la consulta SQL para no incluir la columna Guid
    query = f"UPDATE public.isrequestingphysician SET description = '{respuesta['description']}', phone = '{respuesta['phone']}', mail = '{respuesta['mail']}',note = '{respuesta['notes']}' WHERE Guid = '{respuesta['id_ms']}';"
    
    cursor.execute(query)
    connection.commit()
    
    # Crear un objeto de respuesta JSON
    response=[respuesta['description'],respuesta['phone'],respuesta['mail'],respuesta['notes']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}

    # Enviar el objeto JSON como respuesta
    return jsonify(response_data)

@blueprint.route('/actualizar_cita', methods=['POST']) 
def actualizar_cita():
    # Hacer una copia mutable de request.form
    respuesta = request.form.to_dict()
    print(respuesta)
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    if not respuesta['id_est']:
        query = f"UPDATE public.tbagendaevents SET idmed = '{respuesta['s_mref']}', idmed_sol = '{respuesta['s_msol']}' WHERE Guid = '{respuesta['id_ec']}';"
    else:
        query = f"UPDATE public.tbagendaevents SET idmed = '{respuesta['s_mref']}', idmed_sol = '{respuesta['s_msol']}', idexam = '{respuesta['id_est']}' WHERE Guid = '{respuesta['id_ec']}';"
      
    cursor.execute(query)
    connection.commit()

    query=f"SELECT username FROM public.tbuser WHERE guid='{respuesta['s_mref']}'"
    cursor.execute(query)
    mref=cursor.fetchone()[0]

    # Crear un objeto de respuesta JSON
    response=[respuesta['nombre_modal'],respuesta['fecha'],mref,respuesta['ex_old'],respuesta['s_msol']]
    response_data = {"success": True, 'message': 'Inserción exitosa', 'data': response}

    # Enviar el objeto JSON como respuesta
    return jsonify(response_data)

def get_admision_accesion_number():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT LocalAcc, AdmisionNumber FROM tbExamination ORDER BY CreatedOn DESC LIMIT 1 """
    cursor.execute(query)
    dato = cursor.fetchone()
    
    if dato:
        lastAcc = dato[0]
        lastAdm = dato[1]

        # Extraer parte numérica del LocalAcc
        parte_numerica_acc = ''.join(filter(str.isdigit, lastAcc))

        # Extraer parte numérica del AdmisionNumber
        parte_numerica_adm = ''.join(filter(str.isdigit, lastAdm))
        # Convertir la parte numérica a entero y aumentar en 1
        NewAdm = f"ADM{int(parte_numerica_adm) + 1:03d}"
    else:
        parte_numerica_acc = "000"
        NewAdm = "ADM001"
    newAcc = f"ACC{int(parte_numerica_acc) + 1 }"

    connection.close()
    return(newAcc,NewAdm)


@blueprint.route('/admisionar_cita', methods=['POST']) 
def admisionar_cita():
    # Obtener los datos del formulario
    dataId = request.form.get('dataId')

    # Obtener los datos del formulario
    
    idevent = request.form.get('idevent')
    idequip = request.form.get('idequip')
    
    # Imprimir para depuración
    print('idevent:', idevent)
    print('idequip:', idequip)

    newAcc,NewAdm=get_admision_accesion_number()

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query=f"SELECT idmed,idpatient,idexam,idmed_sol FROM public.tbagendaevents WHERE guid='{idevent}'"
    cursor.execute(query)
    event=cursor.fetchone()

    idmed=event[0]
    idpatient=event[1]
    idexam=event[2]
    idmed_sol=event[3]

    query = f"""SELECT PatientId, Surname, Name, NationalCode, SexCode FROM public.datapatient WHERE Guid='{idpatient}'"""
    cursor.execute(query)
    patient = cursor.fetchone()

    study_instance_uid = pydicom.uid.generate_uid()

    query = f"""
            INSERT INTO public.tbExamination(
                Guid, LocalAcc, IdExam, IdPatient, IdEquipment, AdmisionNumber, IsAdmitted, IsExecuted,IsSentWorkList, CreatedOn,StudyInstanceUID
            ) VALUES (
                uuid_generate_v4(), '{newAcc}', '{idexam}', '{patient[0]}', '{idequip}', '{NewAdm}', 1, 0,1, NOW(),'{study_instance_uid}'
            )
        """
    print(query)
    cursor.execute(query)
    connection.commit()

    #Vamos con el HL7

    query = f"""SELECT ie.guid, ie.Description, ie.Aetitle, im.description FROM public.isequipment ie
                INNER JOIN public.ismodality im on ie.IdModality=im.guid
                WHERE ie.guid='{idequip}'"""
    cursor.execute(query)
    equipo_data = cursor.fetchone()

    query = f"""SELECT description FROM public.exam WHERE guid='{idexam}'"""
    cursor.execute(query)
    examen_descr = cursor.fetchone()[0]

    message = (
            "MSH|^~\&|HIS|RIS|PACS|Radiology|202306241200|QUE|ORM^O01|123456|P|2.3\r"
            f"PID|2002||{patient[0]}^^^public||{patient[1]} {patient[2]}|{patient[3]}|19700101|{patient[4]}||||||||M\r"
            f"PV1|1001|I|^^^Department|||||||^Referring^Doctor|||||||||{NewAdm}\r"
            f"ORC|NW||||SC||1^once^^^^S||T||||||||ClinicaGaleno|\r"
            f"OBR|1|\r"
            f"IPC|{newAcc}||{study_instance_uid}||{equipo_data[3]}|{examen_descr}|||{equipo_data[2]}|||"
        )

    try:
        print("mensaje hl7: ", message)

        # Enviar el mensaje HL7 al servidor de worklist
        response = send_hl7_message(message, '192.168.31.56', 2575)

        if response:  # Assuming send_hl7_message returns True if successful
            print(f"Mensaje HL7 enviado correctamente para {newAcc}")
        else:
            print(f"Fallo al enviar el mensaje HL7 para {newAcc}")

        # Pausa de 10 milisegundos para evitar conflictos
        time.sleep(1)
    except Exception as e:
        print(f"Error al enviar mensaje HL7 para {newAcc}: {e}")
        return jsonify({"error": str(e)}), 500

    # Tengo que crear tambien el reporte, por lo que busco el id del examination recien creado, y hago una entrada en tbreport.

    query = f"""SELECT Guid FROM public.tbExamination WHERE AdmisionNumber='{NewAdm}'"""
    cursor.execute(query)
    guid=cursor.fetchone()[0]
    query = f"""
        INSERT INTO public.tbReport(
            Guid, AdmNumber, IdExamination, IdPatient, Date
        ) VALUES (
            uuid_generate_v4(), '{NewAdm}', '{guid}', '{patient[0]}',NOW()
        )
    """
    cursor.execute(query)
    connection.commit()

    # Por ultimo me queda eliminar el evento de la tabla tbagendaevents
    query = f"""DELETE FROM public.tbagendaevents WHERE guid='{idevent}'"""
    cursor.execute(query)
    connection.commit()
    return jsonify({"success": True})



@blueprint.route('/actualizar_item_agenda', methods=['POST']) 
def actualizar_item_agenda():
    # Hacer una copia mutable de request.form
    respuesta = request.form.to_dict()
    print(respuesta)
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    
    # Modificar la consulta SQL para no incluir la columna Guid
    query = f"UPDATE public.isagendameditem SET day = '{respuesta['day']}', timefrom = '{respuesta['timefrom']}', timeto = '{respuesta['timeto']}',initday = '{respuesta['initday']}',finishday = '{respuesta['finishday']}' WHERE Guid = '{respuesta['id_item_agenda']}';"
    
    cursor.execute(query)
    connection.commit()
    
    # Crear un objeto de respuesta JSON
    response=[respuesta['day'],respuesta['timefrom'],respuesta['timeto'],respuesta['initday'],respuesta['finishday']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}

    # Enviar el objeto JSON como respuesta
    return jsonify(response_data)

@blueprint.route('/actualizar_mod', methods=['POST']) 
def actualizar_mod():
    # Hacer una copia mutable de request.form
    respuesta = request.form.to_dict()

    val = respuesta.get('IsMandatoryEquipmentChange') == 'on'
    respuesta['IsMandatoryEquipmentChange'] = 1 if val else 0

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    
    # Modificar la consulta SQL para no incluir la columna Guid
    query = "UPDATE public.IsModality SET Description = %s, ExternalCode = %s, IsMandatoryEquipmentChange = %s WHERE Guid = %s;"
    
    cursor.execute(query,(respuesta['Description_mod'], respuesta['ext_code_mod'], respuesta['IsMandatoryEquipmentChange'],respuesta['id_mod']))
    connection.commit()
    
    # Crear un objeto de respuesta JSON
    response=[respuesta['Description_mod'],respuesta['ext_code_mod'],respuesta['IsMandatoryEquipmentChange']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}

    # Enviar el objeto JSON como respuesta
    return jsonify(response_data)

@blueprint.route('/actualizar_examen', methods=['POST']) 
def actualizar_examen():
    respuesta = request.form.to_dict()

    val = respuesta.get('IsAc_ex') == 'on'
    respuesta['IsAc_ex'] = 1 if val else 0
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    print(respuesta)
    
    query= "SELECT Description from public.IsMinisterialCode WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_cod_min'],))
    cod_min=cursor.fetchone()[0]

    query= "SELECT Description from public.IsModality WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_modality'],))
    modality=cursor.fetchone()[0]

    query= """UPDATE public.Exam SET Description=%s, IdMinisterialCode=%s, IdModality=%s, ExecutionTime=%s, IsActive=%s, precio=%s WHERE Guid=%s"""
    
    cursor.execute(query, (respuesta['Description_ex'], respuesta['s_cod_min'], respuesta['s_modality'], respuesta['time_execution'],respuesta['IsAc_ex'],respuesta['precio'],respuesta['id_examen']))
    connection.commit()

    response=[respuesta['Description_ex'],cod_min, modality,respuesta['time_execution'],respuesta['IsAc_ex'],respuesta['precio']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    connection.close()
    return jsonify(response_data)


@blueprint.route('/actualizar_mach', methods=['POST']) 
def actualizar_mach():
    # Hacer una copia mutable de request.form
    respuesta = request.form.to_dict()

    val = respuesta.get('IsAc_mach') == 'on'
    respuesta['IsAc_mach'] = 1 if val else 0

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "UPDATE public.IsEquipment SET Description = %s, ExternalCode = %s, AETitle = %s, IdRoom = %s, IdProvenance=%s, IdModality=%s ,BrandEquipment=%s, ModelEquipment= %s, SNEquipment = %s, IsActive=%s, IP=%s WHERE Guid = %s;"
    
    cursor.execute(query,(respuesta['Description_mach'], respuesta['Ext_code_equip'], respuesta['AETitle'],respuesta['s_sala'],respuesta['s_proc'],respuesta['s_moda'],respuesta['equip_brand'],respuesta['equip_model'],respuesta['equip_sn'],respuesta['IsAc_mach'],respuesta['equip_ip'],respuesta['id_mach']))
    connection.commit()

    query= "SELECT Description from public.IsProvenance WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_proc'],))
    provenance=cursor.fetchall()[0][0]
   
    query= "SELECT Description from public.IsModality WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_moda'],))
    modality=cursor.fetchall()[0][0]

    query= "SELECT Description from public.IsRoom WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_sala'],))
    sala=cursor.fetchall()[0][0]

    response=[respuesta['Description_mach'],respuesta['AETitle'],respuesta['Ext_code_equip'],sala, modality,respuesta['IsAc_mach'],provenance,respuesta['equip_ip'],respuesta['equip_brand'],respuesta['equip_model'],respuesta['equip_sn']]

    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}
    connection.close()
    # Enviar el objeto JSON como respuesta
    return jsonify(response_data)


@blueprint.route('/actualizar_ap', methods=['POST']) 
def actualizar_ap():
    # Hacer una copia mutable de request.form
    respuesta = request.form.to_dict()

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    
    # Modificar la consulta SQL para no incluir la columna Guid
    query = "UPDATE public.IsAnatomicalPart SET Description = %s WHERE Guid = %s;"
    
    cursor.execute(query,(respuesta['Description_ap'],respuesta['id_ap']))
    connection.commit()
    
    # Crear un objeto de respuesta JSON
    response=[respuesta['Description_ap'],]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}

    # Enviar el objeto JSON como respuesta
    return jsonify(response_data)

@blueprint.route('/actualizar_origen', methods=['POST']) 
def actualizar_origen ():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    # Hacer una copia mutable de request.form
    respuesta = request.form.to_dict()
    val = respuesta.get('IsAc') == 'on'
    respuesta['IsAc'] = 1 if val else 0

    val = respuesta.get('PatientCD') == 'on'
    respuesta['PatientCD'] = 1 if val else 0

    val = respuesta.get('IsEditingExaminationDisabled') == 'on'
    respuesta['IsEditingExaminationDisabled'] = 1 if val else 0

    val = respuesta.get('PublicationWeb') == 'on'
    respuesta['PublicationWeb'] = 1 if val else 0

    val = respuesta.get('IsAutomaticPrinting') == 'on'
    respuesta['IsAutomaticPrinting'] = 1 if val else 0

    val = respuesta.get('IsChargeMandatory') == 'on'
    respuesta['IsChargeMandatory'] = 1 if val else 0

    val = respuesta.get('IsPriceListMandatory') == 'on'
    respuesta['IsPriceListMandatory'] = 1 if val else 0

    val = respuesta.get('IsOrderToNotify') == 'on'
    respuesta['IsOrderToNotify'] = 1 if val else 0

    print(respuesta)
    query = "UPDATE public.IsProvenance SET Description = %s, IdProvenanceGroup = %s, IsActive=%s, ExternalCode=%s,PatientCD=%s, IsEditingExaminationDisabled=%s,IsChargeMandatory=%s, IsPriceListMandatory=%s, IsOrderToNotify=%s,PublicationWeb=%s WHERE Guid = %s;"
    cursor.execute(query,(respuesta['Description_o'],respuesta['s_go'],respuesta['IsAc'],respuesta['AltCode_or'],respuesta['PatientCD'],respuesta['IsEditingExaminationDisabled'],respuesta['IsChargeMandatory'],respuesta['IsPriceListMandatory'],respuesta['IsOrderToNotify'],respuesta['PublicationWeb'],respuesta['id_origin'],))
    connection.commit()

    query="""SELECT Description FROM public.IsProvenanceGroup WHERE Guid=%s"""
    cursor.execute(query,(respuesta['s_go'],))
    DescriptionGroup=cursor.fetchone()[0]
    response=[respuesta['Description_o'],DescriptionGroup,respuesta['IsAc'],respuesta['AltCode_or'],respuesta['PatientCD'],respuesta['IsEditingExaminationDisabled'],respuesta['PublicationWeb'],respuesta['IsPriceListMandatory'],respuesta['IsOrderToNotify']]

    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    return jsonify(response_data)

@blueprint.route('/actualizar_agenda', methods=['POST']) 
def actualizar_agenda():
    respuesta = request.form.to_dict()

    # Obtener las cadenas de fecha del formulario
    fecha_inicio_agenda_input = respuesta['fecha_inicio_agenda_input']
    fecha_fin_agenda_input = respuesta['fecha_fin_agenda_input']

    # Convertir las cadenas de fecha a objetos de fecha de Python
    fecha_inicio_agenda = datetime.strptime(fecha_inicio_agenda_input, '%d-%m-%Y').strftime('%Y-%m-%d')
    if (fecha_fin_agenda_input)!='':
        fecha_fin_agenda = datetime.strptime(fecha_fin_agenda_input, '%d-%m-%Y').strftime('%Y-%m-%d')
        respuesta['fecha_fin_agenda_input'] = fecha_fin_agenda
    else:
        respuesta['fecha_fin_agenda_input']=None
    # Actualizar las cadenas de fecha en la respuesta
    respuesta['fecha_inicio_agenda_input'] = fecha_inicio_agenda
    


    val = respuesta.get('IsAc_ag') == 'on'
    respuesta['IsAc_ag'] = 1 if val else 0
    
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = "UPDATE public.IsAgenda SET Description=%s,IdEquipment=%s, StartDate=%s,EndDate=%s,ExternalCode=%s,IsActive=%s WHERE Guid=%s;"
    
    cursor.execute(query, (respuesta['Description_agenda'], respuesta['s_equip'], respuesta['fecha_inicio_agenda_input'],respuesta['fecha_fin_agenda_input'],respuesta['Ex_agenda'],respuesta['IsAc_ag'],respuesta['id_agenda'],))
    connection.commit()

    query="SELECT Description FROM public.IsEquipment WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_equip'],))
    equipo=cursor.fetchall()[0][0]

    response=[respuesta['Description_agenda'],equipo,respuesta['Ex_agenda'],respuesta['IsAc_ag'],respuesta['fecha_inicio_agenda_input'],respuesta['fecha_fin_agenda_input']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    connection.close()
    return jsonify(response_data)

@blueprint.route('/actualizar_dia', methods=['POST']) 
def actualizar_dia():
    respuesta = request.form.to_dict()
    
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = "UPDATE public.IsAgendaDays SET Day=%s,StartTime=%s, EndTime=%s,SlotNumber=%s,PlacePerSlot=%s WHERE Guid=%s;"
    
    cursor.execute(query,(respuesta['dia_ag'],respuesta['hora_inicio_dia'],respuesta['hora_final_dia'],respuesta['n_slots'],respuesta['lugares_x_slots'],respuesta['id_dia'],))
    connection.commit()
    

    response=[respuesta['dia_ag'],respuesta['hora_inicio_dia'],respuesta['hora_final_dia'],respuesta['n_slots'],respuesta['lugares_x_slots']]

    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}
    return jsonify(response_data)

@blueprint.route('/actualizar_business_units', methods=['POST']) 
def actualizar_business_units():
    respuesta = request.form.to_dict()

    val = respuesta.get('IsAc_bu') == 'on'
    respuesta['IsAc_bu'] = 1 if val else 0

    val = respuesta.get('tecnico_obl') == 'on'
    respuesta['tecnico_obl'] = 1 if val else 0

    val = respuesta.get('questions_manda') == 'on'
    respuesta['questions_manda'] = 1 if val else 0

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "UPDATE public.IsBusinessUnit SET Description=%s,Code=%s, ExternalCode=%s,HttpPacs=%s,IsActive=%s,IsQuestionListMandatory=%s,IsTechnicianMandatory=%s WHERE Guid=%s;"
    
    cursor.execute(query, (respuesta['Description_bu'], respuesta['code_bu'], respuesta['ex_code_bu'], respuesta['http_pacs'], respuesta['IsAc_bu'],respuesta['questions_manda'],respuesta['tecnico_obl'],respuesta['id_bu'],))
    connection.commit()
    

    response=[respuesta['Description_bu'],respuesta['code_bu'],respuesta['ex_code_bu'],respuesta['IsAc_bu'],respuesta['http_pacs'],respuesta['questions_manda'],respuesta['tecnico_obl']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    connection.close()
    return jsonify(response_data)


@blueprint.route('/rellenar_select', methods=['POST']) 
def rellenar_select():
    data = request.get_json()

    # Acceder a los valores de dNeeded y TableId
    dNeeded = data.get('dNeeded')
    TableId = data.get('TableId')
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = f'SELECT Guid,{dNeeded} FROM {TableId}'
    print(query)
    cursor.execute(query)

    return jsonify({'status': 'OK', 'data': cursor.fetchall()})

@blueprint.route('/rellenar_select_cond_id', methods=['POST']) 
def rellenar_select_cond_id():
    data = request.get_json()

    # Acceder a los valores de dNeeded y TableId
    dNeeded = data.get('dNeeded')
    TableId = data.get('TableId')
    IdCond=data.get('idCond')
    colCond=data.get('colCond') 

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = f"SELECT Guid,{dNeeded} FROM {TableId} WHERE {colCond}='{IdCond}';"
    print(query)
    cursor.execute(query)

    return jsonify({'status': 'OK', 'data': cursor.fetchall()})

@blueprint.route('/get_inf_predef', methods=['POST']) 
def get_inf_predef():
    data = request.get_json()
    idpredef = data.get('idpredef')

    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "SELECT executiontext, findingtext, conclusiontext FROM public.tbreportdefault WHERE guid=%s"
    cursor.execute(query, (idpredef,))
    result = cursor.fetchone()  # Solo se espera una fila

    cursor.close()
    connection.close()

    if result:
        executiontext, findingtext, conclusiontext = result
        return jsonify({'status': 'OK', 'data': {
            'executiontext': executiontext,
            'findingtext': findingtext,
            'conclusiontext': conclusiontext
        }})
    else:
        return jsonify({'status': 'Error', 'message': 'No data found'})
    
@blueprint.route('/get_citas', methods=['GET']) 
def get_citas():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT tba.guid,pat.name || ' ' || pat.surname as fullname,tba.comienzo ,us.username,ex.description, tba.idmed_sol
                FROM public.tbagendaevents tba
                INNER JOIN public.datapatient pat on tba.idpatient=pat.guid
                LEFT JOIN public.isrequestingphysician rp on tba.idmed_sol=rp.guid
                INNER JOIN public.tbuser us on tba.idmed=us.guid
                INNER JOIN public.exam ex on tba.idexam=ex.guid"""
    
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_citas_for_today', methods=['GET']) 
def get_citas_for_today():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT tba.guid,pat.name || ' ' || pat.surname as fullname,tba.comienzo ,us.username,ex.description, tba.idmed_sol
                FROM public.tbagendaevents tba
                INNER JOIN public.datapatient pat on tba.idpatient=pat.guid
                LEFT JOIN public.isrequestingphysician rp on tba.idmed_sol=rp.guid
                INNER JOIN public.tbuser us on tba.idmed=us.guid
                INNER JOIN public.exam ex on tba.idexam=ex.guid
                WHERE DATE(tba.comienzo) = current_date"""
    
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_events', methods=['POST'])
def get_events():
    data = request.get_json()
    prof_ag = data.get('prof_ag')
    print(f"Received prof_ag: {prof_ag}")

    # Conectar a la base de datos
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    if data.get('prof_ag_text'):
        query_events = f"""SELECT ae.guid, CONCAT(dp.name, ' ', dp.surname) AS pat, ae.idmodality, ae.idexam, ae.comienzo, fin 
                        FROM public.tbagendaevents ae
                        INNER JOIN public.datapatient dp on dp.guid=ae.idpatient
                        WHERE idmed=(SELECT guid FROM public.tbuser WHERE username='{data.get('prof_ag_text')}')"""
    else:
    # Consulta a la base de datos para obtener los eventos existentes
        query_events = f"""SELECT ae.guid, CONCAT(dp.name, ' ', dp.surname) AS pat, ae.idmodality, ae.idexam, ae.comienzo, fin 
                        FROM public.tbagendaevents ae
                        INNER JOIN public.datapatient dp on dp.guid=ae.idpatient
                        WHERE idmed='{prof_ag}'"""
    cursor.execute(query_events)
    result_events = cursor.fetchall()

    # Consulta a la base de datos para obtener los horarios de trabajo del médico
    if data.get('prof_ag_text'):
        query_schedule = f"SELECT day, timefrom, timeto FROM public.isagendameditem WHERE idmed=(SELECT guid FROM public.tbuser WHERE username='{data.get('prof_ag_text')}')"
        
    else:
        query_schedule = f"SELECT day, timefrom, timeto FROM public.isagendameditem WHERE idmed='{prof_ag}'"
    # Consulta a la base de datos para obtener los eventos existentes
        
    print(query_schedule)
    
    cursor.execute(query_schedule)
    result_schedule = cursor.fetchall()

    # Procesar los resultados y construir los eventos existentes
    events = []
    for row in result_events:
        event = {
            'title': f'Paciente: {row[1]}, Modality: {row[2]}',  # Puedes personalizar el título como desees
            'start': row[4].strftime('%Y-%m-%dT%H:%M:%S'),  # Fecha y hora de inicio en formato ISO 8601
            'end': row[5].strftime('%Y-%m-%dT%H:%M:%S'),    # Fecha y hora de fin en formato ISO 8601
            'editable': False,  # Marcar los eventos del backend como no editables
            'color': 'gray',  # Color gris para los eventos del backend
            'guid':row[0]
        }
        events.append(event)

    # Construir los horarios de trabajo
    work_hours = []
    days_mapping = {
        'lunes': 1,
        'martes': 2,
        'miércoles': 3,
        'jueves': 4,
        'viernes': 5,
        'sábado': 6,
        'domingo': 0
    }
    for row in result_schedule:
        work_hours.append({
            'day': days_mapping[row[0].lower()],
            'start': row[1].strftime('%H:%M:%S'),
            'end': row[2].strftime('%H:%M:%S')
        })

    # Cerrar la conexión a la base de datos
    cursor.close()
    connection.close()

    print(f"Returning events: {events} and work hours: {work_hours}")
    return jsonify({'events': events, 'work_hours': work_hours})

@blueprint.route('/get_block_prestacion')
def get_block_prestacion():
    return render_template('includes/blocks/block_prestacion.html')

# @blueprint.route('/insertar_citas', methods=['POST'])
# def insertar_citas():
#     data = request.get_json()
#     # Conectar a la base de datos
#     connection = psycopg2.connect(**config)
#     cursor = connection.cursor()

#     # Zona horaria local, ajusta esto según tu zona horaria
#     local_tz = pytz.timezone("America/Argentina/Buenos_Aires")

#     for exam in data['exams']:
#         codigoexam = exam['examenId'][:3]
#         descrip = exam['examenId'][6:]
#         print("descrip:", descrip)
#         patient = data['patientId']
#         # Consulta a la base de datos para obtener los eventos existentes
#         query = f"""SELECT guid FROM public.exam WHERE description='{descrip}' """
#         cursor.execute(query)
#         idexam = cursor.fetchone()[0]

#         # Convertir las horas a la zona horaria local y luego restar 3 horas
#         init_local = local_tz.localize(datetime.strptime(exam['init'], '%Y-%m-%dT%H:%M:%S'))
#         finish_local = local_tz.localize(datetime.strptime(exam['finish'], '%Y-%m-%dT%H:%M:%S'))

#         init_adjusted = init_local - timedelta(hours=3)
#         finish_adjusted = finish_local - timedelta(hours=3)

#         # Convertir a formato ISO 8601
#         init_str = init_adjusted.strftime('%Y-%m-%dT%H:%M:%S')
#         finish_str = finish_adjusted.strftime('%Y-%m-%dT%H:%M:%S')

#         query_events = f"""INSERT INTO public.tbagendaevents(guid,idmed,idpatient,idexam,comienzo,fin)
#                             VALUES (uuid_generate_v4(),'{exam['profesional']}','{patient}','{idexam}','{init_str}','{finish_str}') """
#         print(query_events)
#         cursor.execute(query_events)
#         connection.commit()
        
#     print(data)
#     return jsonify({"success": True})

@blueprint.route('/static/templates/includes/toast/<path:filename>')
def custom_static(filename):
    return send_from_directory('templates/includes/toast', filename)

@blueprint.route('/insertar_citas', methods=['POST'])
def insertar_citas():
    data = request.get_json()
    print(data)
    # Conectar a la base de datos
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    # Zona horaria local, ajusta esto según tu zona horaria
    local_tz = pytz.timezone("America/Argentina/Buenos_Aires")

    for exam in data['exams']:
        # codigoexam = exam['examenId'][:3]
        descrip = exam['title'][6:]
        print("descrip:", descrip)
        patient = data['patientId']
        # Consulta a la base de datos para obtener los eventos existentes
        print(exam['examId'])
        idexam = exam['examId']
        

        # Quitar el sufijo .000Z antes de convertir
        init_str = exam['init'].replace('.000Z', '')
        finish_str = exam['finish'].replace('.000Z', '')

        # Convertir las horas a la zona horaria local y luego restar 3 horas
        init_local = local_tz.localize(datetime.strptime(init_str, '%Y-%m-%dT%H:%M:%S'))
        finish_local = local_tz.localize(datetime.strptime(finish_str, '%Y-%m-%dT%H:%M:%S'))

        init_adjusted = init_local - timedelta(hours=3)
        finish_adjusted = finish_local - timedelta(hours=3)

        # Convertir a formato ISO 8601
        init_str_adjusted = init_adjusted.strftime('%Y-%m-%dT%H:%M:%S')
        finish_str_adjusted = finish_adjusted.strftime('%Y-%m-%dT%H:%M:%S')

        query_events = f"""INSERT INTO public.tbagendaevents(guid,idmed,idpatient,idexam,comienzo,fin)
                            VALUES (uuid_generate_v4(),'{exam['profesional']}','{patient}','{idexam}','{init_str_adjusted}','{finish_str_adjusted}') """
        print(query_events)
        cursor.execute(query_events)
        connection.commit()
        
    print(data)
    return jsonify({"success": True})


@blueprint.route('/actualizar_evento_cita', methods=['POST'])
def actualizar_evento_cita():
    data = request.get_json()
    # Conectar a la base de datos
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    print(data)

    # Zona horaria local, ajusta esto según tu zona horaria
    local_tz = pytz.timezone("America/Argentina/Buenos_Aires")

    # Convertir las horas a UTC
    init_utc = datetime.fromisoformat(data['start'].replace('Z', '+00:00')).astimezone(pytz.utc)
    finish_utc = datetime.fromisoformat(data['end'].replace('Z', '+00:00')).astimezone(pytz.utc)

    # Convertir de UTC a la zona horaria local
    init_local = init_utc.astimezone(local_tz)
    finish_local = finish_utc.astimezone(local_tz)

    # Convertir a formato ISO 8601 sin la 'Z'
    init_str_adjusted = init_local.strftime('%Y-%m-%dT%H:%M:%S')
    finish_str_adjusted = finish_local.strftime('%Y-%m-%dT%H:%M:%S')

    query_events = f"""UPDATE public.tbagendaevents SET comienzo='{init_str_adjusted}', fin='{finish_str_adjusted}' WHERE guid='{data['guid']}'"""
    print(query_events)
    cursor.execute(query_events)
    connection.commit()
        
    return jsonify({"success": True})

    data = request.get_json()
    # Conectar a la base de datos
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    print(data)

    # Zona horaria local, ajusta esto según tu zona horaria
    local_tz = pytz.timezone("America/Argentina/Buenos_Aires")

    # Quitar el sufijo .000Z antes de convertir
    init_str = data['start'].replace('.000Z', '')
    finish_str = data['end'].replace('.000Z', '')

    # Convertir las horas a la zona horaria local y luego restar 3 horas
    init_local = local_tz.localize(datetime.strptime(init_str, '%Y-%m-%dT%H:%M:%S'))
    finish_local = local_tz.localize(datetime.strptime(finish_str, '%Y-%m-%dT%H:%M:%S'))

    init_adjusted = init_local - timedelta(hours=0)
    finish_adjusted = finish_local - timedelta(hours=0)

    # Convertir a formato ISO 8601
    init_str_adjusted = init_adjusted.strftime('%Y-%m-%dT%H:%M:%S')
    finish_str_adjusted = finish_adjusted.strftime('%Y-%m-%dT%H:%M:%S')

    query_events = f"""UPDATE public.tbagendaevents SET comienzo='{init_str_adjusted}', fin='{finish_str_adjusted}' WHERE guid='{data['guid']}'"""
    print(query_events)
    cursor.execute(query_events)
    connection.commit()
        
    
    return jsonify({"success": True})

@blueprint.route('/crear_worklist', methods=['POST']) 
def crear_worklist():
    data = request.get_json()
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    print("data:", data)

    query = """SELECT LocalAcc, AdmisionNumber FROM tbExamination ORDER BY CreatedOn DESC LIMIT 1 """
    cursor.execute(query)
    dato = cursor.fetchone()
    
    if dato:
        lastAcc = dato[0]
        lastAdm = dato[1]

        # Extraer parte numérica del LocalAcc
        parte_numerica_acc = ''.join(filter(str.isdigit, lastAcc))

        # Extraer parte numérica del AdmisionNumber
        parte_numerica_adm = ''.join(filter(str.isdigit, lastAdm))
        # Convertir la parte numérica a entero y aumentar en 1
        NewAdm = f"ADM{int(parte_numerica_adm) + 1:03d}"
    else:
        parte_numerica_acc = "000"
        NewAdm = "ADM001"

    query = f"""SELECT PatientId, Surname, Name, NationalCode, SexCode FROM public.datapatient WHERE Guid='{data['patientId']}'"""
    cursor.execute(query)
    patient = cursor.fetchone()

    contador = 0

    for exam in data['exams']:
        # Convertir la parte numérica a entero y aumentar en 1
        newAcc = f"ACC{int(parte_numerica_acc) + 1 + contador:03d}"
        contador += 1
        print("acc: ", newAcc)

        examId = exam['examId']
        equipo = exam['equip']

        query = f"""SELECT Guid, Description, Aetitle, IdModality FROM public.isequipment WHERE guid='{equipo}'"""

        cursor.execute(query)
        equipo_data = cursor.fetchone()

        cursor.fetchall()  # Consumir todos los resultados

        query = f"""SELECT Guid, ExternalCode FROM public.ismodality WHERE Guid='{equipo_data[3]}'"""

        cursor.execute(query)
        modalidad = cursor.fetchone()
        cursor.fetchall()  # Consumir todos los resultados

        query = f"""SELECT description FROM public.exam WHERE guid='{examId}'"""
        cursor.execute(query)
        ex_descrip = cursor.fetchone()[0]
        cursor.fetchall()  # Consumir todos los resultados

        # Construir el mensaje HL7
        study_instance_uid = pydicom.uid.generate_uid()
        message = (
            "MSH|^~\&|HIS|RIS|PACS|Radiology|202306241200|QUE|ORM^O01|123456|P|2.3\r"
            f"PID|2002||{patient[0]}^^^public||{patient[1]} {patient[2]}|{patient[3]}|19700101|{patient[4]}||||||||M\r"
            f"PV1|1001|I|^^^Department|||||||^Referring^Doctor|||||||||{NewAdm}\r"
            f"ORC|NW||||SC||1^once^^^^S||T||||||||ClinicaGaleno|\r"
            f"OBR|1|\r"
            f"IPC|{newAcc}||{study_instance_uid}||{modalidad[1]}|{ex_descrip}|||{equipo_data[2]}|||"
        )
        print("datos para la query: ",newAcc,ex_descrip,patient,equipo_data,study_instance_uid)
        query = f"""
            INSERT INTO public.tbExamination(
                Guid, LocalAcc, IdExam, IdPatient, IdEquipment, AdmisionNumber, IsAdmitted, IsExecuted,IsSentWorkList, CreatedOn,StudyInstanceUID
            ) VALUES (
                uuid_generate_v4(), '{newAcc}', '{examId}', '{patient[0]}', '{equipo_data[0]}', '{NewAdm}', 1, 0,1, NOW(),'{study_instance_uid}'
            )
        """
        
        cursor.execute(query)
        connection.commit()

        # Tengo que crear tambien el reporte, por lo que busco el id del examination recien creado, y hago una entrada en tbreport.

        query = f"""SELECT Guid FROM public.tbExamination WHERE AdmisionNumber='{NewAdm}'"""
        cursor.execute(query)
        guid=cursor.fetchone()[0]
        query = f"""
            INSERT INTO public.tbReport(
                Guid, AdmNumber, IdExamination, IdPatient, Date
            ) VALUES (
                uuid_generate_v4(), '{NewAdm}', '{guid}', '{patient[0]}',NOW()
            )
        """
        print(query)
        cursor.execute(query)
        connection.commit()


        try:
            print("mensaje hl7: ", message)

            # Enviar el mensaje HL7 al servidor de worklist
            response = send_hl7_message(message, '192.168.31.56', 2575)

            if response:  # Assuming send_hl7_message returns True if successful
                print(f"Mensaje HL7 enviado correctamente para {newAcc}")
            else:
                print(f"Fallo al enviar el mensaje HL7 para {newAcc}")

            # Pausa de 10 milisegundos para evitar conflictos
            time.sleep(1)
        except Exception as e:
            print(f"Error al enviar mensaje HL7 para {newAcc}: {e}")
            return jsonify({"error": str(e)}), 500

    connection.close()
    return jsonify({"success": True})

@blueprint.route('/cancelar_worklist', methods=['POST']) 
def cancelar_worklist():
    data = request.get_json()
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    print("data:", data)

    query= f"SELECT IdPatient,StudyInstanceUID FROM public.tbexamination WHERE Guid='{data['id']}'"
    cursor.execute(query)
    order=cursor.fetchone()  # Consumir todos los resultados

    message = (
            "MSH|^~\&|HIS|RIS|PACS|Radiology|202306241200|QUE|ORM^O01|123457|P|2.3\r"
                f"PID|2002||{order[0]}^^^public|\r"
                "PV1||E|\r"
                "ORC|CA||||CA|\r"
                "OBR|1|\r"
                f"IPC|||{order[1]}"
        )
    
    query=f"UPDATE public.tbexamination SET IsExecuted=1 WHERE StudyInstanceUID={order[1]}"
    cursor.execute(query)
    connection.commit()
    
    response = send_hl7_message(message, '192.168.31.56', 2575)

    if response:  # Assuming send_hl7_message returns True if successful
        print(f"Mensaje HL7 enviado correctamente para {order}")
    else:
        print(f"Fallo al enviar el mensaje HL7 para {order}")

    return jsonify({"success": True})
    
@blueprint.route('/<template>')
@login_required
def route_template(template):
    try:

        if not template.endswith('.html'):
            template += '.html'

        # Detect the current page
        segment = get_segment(request)
        print("el segmento es:",segment)

        # Serve the file (if exists) from app/templates/home/FILE.html
        return render_template("home/" + template, segment=segment)

    except TemplateNotFound:
        return render_template('home/page-404.html'), 404

    except:
        return render_template('home/page-500.html'), 500


# Helper - Extract current page name from request
def get_segment(request):

    try:

        segment = request.path.split('/')[-1]

        if segment == '':
            segment = 'index'

        return segment

    except:
        return None
