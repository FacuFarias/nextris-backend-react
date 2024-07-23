# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import mysql.connector
from flask import jsonify,send_file
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

    return render_template('home/index.html', segment='index')


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

    return render_template('/home/nueva_cita.html',tipoestudios=tipos,codigos=codigos_machine)


@blueprint.route('/configuraciones', methods=['GET'])
def configuraciones():


    return render_template('/home/configuraciones.html')


@blueprint.route('/agregar_pacientes', methods=['POST'])
def agregar_pacientes():
    
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    r = request.form.to_dict()

    IsAn = r.get('IsAn') == 'on'
    r['IsAn'] = 1 if IsAn else 0

    IsMerged = r.get('IsMerged') == 'on'
    r['IsMerged'] = 1 if IsMerged else 0

    query="""INSERT INTO public.DataPatient(Guid,Surname,Name,NationalCode,BirthDate,PatientId,SexCode,IsAnonymous,IsMerged,Phone,Email,HealthCard) VALUES (UUID(),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) """
    cursor.execute(query,(r['p_surname'],r['p_name'],r['p_dni'],r['fecha_nacimiento'],r['p_id'],r['sex'],r['IsAn'],r['IsMerged'],r['telefono'],r['mail'],r['p_healthcard'])) 
    connection.commit()
    # response_data=cursor.fetchall()

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
    query = "SELECT * FROM public.IsProvenanceGroup;"
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_users', methods=['GET']) 
def get_users():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = """SELECT u.guid,u.username,r.description,u.name,u.surname,u.nationalnumber,u.isactive FROM public.tbuser u
                inner join public.isrole r on r.guid=u.idrole
                where u.isactive=1"""
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
    query = "SELECT * FROM public.IsAnatomicalPart;"
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_ministerial_codes', methods=['GET']) 
def get_codes():
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()
    query = "SELECT * FROM public.IsMinisterialCode"
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
        SELECT e.Guid, e.Description, m.Description AS MinisterialCode, n.Description AS modality, e.ExecutionTime, e.IsActive 
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
            query="""INSERT INTO public.RelBusinessUnitProvenance(Guid,IdBusinessUnit,IdProvenance) VALUES (UUID(),%s,%s)"""
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
            query="""INSERT INTO public.RelBusinessUnitEquipment(Guid,IdBusinessUnit,IdEquipment) VALUES (UUID(),%s,%s)"""
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
            query="""INSERT INTO public.RelBusinessUnitModality(Guid,IdBusinessUnit,IdModality) VALUES (UUID(),%s,%s)"""
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

    query = "INSERT INTO public.IsProvenanceGroup(Guid, Description, IsExternal, IsER, DelayDays) VALUES (UUID(), %s, %s, %s, %s)"
    
    cursor.execute(query, (respuesta['Description'], respuesta['IsEx'], respuesta['ps'], respuesta['delaydays']))
    connection.commit()
    connection.close()

    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}
    return jsonify(response_data)

@blueprint.route('/create_user', methods=['POST']) 
def create_user():
    respuesta = request.form.to_dict()
    dni = respuesta.get('dni')
    name = respuesta.get('name')
    surname = respuesta.get('surname')
    username = respuesta.get('username')
    rol = respuesta.get('rol')


    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = f"INSERT INTO public.tbuser(guid, name, surname, username, nationalnumber,idrole,isactive) VALUES (uuid_generate_v4(), '{name}', '{surname}', '{username}', '{dni}',{rol},0)'"
    print("query de user:",query)
    cursor.execute(query)
    connection.commit()
    connection.close()

    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': respuesta}
    return jsonify(response_data)


@blueprint.route('/agregar_codigo', methods=['POST']) 
def agregar_codigo():
    respuesta = request.form.to_dict()
    print(respuesta)
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO public.IsMinisterialCode(Guid, Code, Description, `Group`) VALUES (UUID(), %s, %s, %s)"
    
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

    query = "INSERT INTO public.IsModality(Guid, Description, ExternalCode, IsMandatoryEquipmentChange) VALUES (UUID(), %s, %s, %s)"
    
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

    query = "INSERT INTO public.exam(Guid, Description, IdMinisterialCode, IdModality,ExecutionTime,IsActive) VALUES (UUID(), %s, %s, %s, %s, %s)"
    
    cursor.execute(query, (respuesta['Description_ex'], respuesta['s_cod_min'], respuesta['s_modality'], respuesta['IsAc_ex'], respuesta['time_execution']))
    connection.commit()
    
    query= "SELECT Description from public.IsMinisterialCode WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_cod_min'],))
    cod_min=cursor.fetchone()[0]

    query= "SELECT Description from public.IsModality WHERE Guid=%s"
  

    cursor.execute(query,(respuesta['s_modality'],))
    modality=cursor.fetchone()[0]

    response=[respuesta['Description_ex'],cod_min, modality,respuesta['time_execution'],respuesta['IsAc_ex']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    connection.close()
    return jsonify(response_data)

@blueprint.route('/agregar_ap', methods=['POST']) 
def agregar_ap():
    respuesta = request.form.to_dict()
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO public.IsAnatomicalPart(Guid, Description) VALUES (UUID(), %s)"
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
    query = "INSERT INTO public.IsProvenance(Guid, Description, IdProvenanceGroup, IsActive, ExternalCode,PatientCD,PublicationWeb,IsPriceListMandatory,IsChargeMandatory,IsOrderToNotify) VALUES (UUID(), %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    
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
    query = "INSERT INTO public.IsEquipment(Guid, Description, AETitle,ExternalCode, IdRoom,IdProvenance,IdModality,BrandEquipment,ModelEquipment,SNEquipment,IsActive,IP) VALUES (UUID(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    
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
    
    query = "INSERT INTO public.IsAgendaDays(Guid, IdAgenda, Day,StartTime, EndTime,SlotNumber,PlacePerSlot) VALUES (UUID(), %s, %s, %s, %s, %s, %s)"
    
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

    query = "INSERT INTO public.IsBusinessUnit(Guid, Description, Code, ExternalCode,HttpPacs,IsActive,IsQuestionListMandatory,IsTechnicianMandatory) VALUES (UUID(), %s, %s, %s, %s, %s, %s, %s)"
    
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

    query = "INSERT INTO public.IsRoom(Guid, Description, ExternalCode, IsActive) VALUES (UUID(), %s, %s, %s)"
    
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
    query = "INSERT INTO public.IsAgenda(Guid, Description, IdEquipment, StartDate,EndDate,ExternalCode,IsActive) VALUES (UUID(), %s, %s, %s,%s,%s,%s)"
    
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

    query= """UPDATE public.Exam SET Description=%s, IdMinisterialCode=%s, IdModality=%s, ExecutionTime=%s, IsActive=%s WHERE Guid=%s"""
    
    cursor.execute(query, (respuesta['Description_ex'], respuesta['s_cod_min'], respuesta['s_modality'], respuesta['time_execution'],respuesta['IsAc_ex'],respuesta['id_examen']))
    connection.commit()

    response=[respuesta['Description_ex'],cod_min, modality,respuesta['time_execution'],respuesta['IsAc_ex']]
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
    query = f"SELECT Guid,{dNeeded} FROM {TableId} WHERE {colCond}@> ARRAY['{IdCond}']::uuid[];"
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



@blueprint.route('/crear_worklist', methods=['POST']) 
def crear_worklist():
    data = request.get_json()
    connection = psycopg2.connect(**config)
    cursor = connection.cursor()

    print("data:", data)

    query = """
        SELECT LocalAcc, AdmisionNumber FROM tbExamination
        ORDER BY CreatedOn DESC
        LIMIT 1
    """
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

        examen_descr = exam['examenId']
        equipo = exam['equipo']

        query = f"""SELECT Guid, Description, Aetitle, IdModality FROM public.isequipment WHERE description='{equipo}'"""
        cursor.execute(query)
        equipo_data = cursor.fetchone()
        cursor.fetchall()  # Consumir todos los resultados

        query = f"""SELECT Guid, ExternalCode FROM public.ismodality WHERE Guid='{equipo_data[3]}'"""
        cursor.execute(query)
        modalidad = cursor.fetchone()
        cursor.fetchall()  # Consumir todos los resultados

        query = f"""SELECT Guid FROM public.exam WHERE Description='{examen_descr}'"""
        cursor.execute(query)
        ex_id = cursor.fetchone()
        cursor.fetchall()  # Consumir todos los resultados

        # Construir el mensaje HL7
        study_instance_uid = pydicom.uid.generate_uid()
        message = (
            "MSH|^~\&|HIS|RIS|PACS|Radiology|202306241200|QUE|ORM^O01|123456|P|2.3\r"
            f"PID|2002||{patient[0]}^^^public||{patient[1]} {patient[2]}|{patient[3]}|19700101|{patient[4]}||||||||M\r"
            f"PV1|1001|I|^^^Department|||||||^Referring^Doctor|||||||||{NewAdm}\r"
            f"ORC|NW||||SC||1^once^^^^S||T||||||||ClinicaGaleno|\r"
            f"OBR|1|\r"
            f"IPC|{newAcc}||{study_instance_uid}||{modalidad[1]}|{examen_descr}|||{equipo_data[2]}|||"
        )

        query = f"""
            INSERT INTO public.tbExamination(
                Guid, LocalAcc, IdExam, IdPatient, IdEquipment, AdmisionNumber, IsAdmitted, IsExecuted,IsSentWorkList, CreatedOn,StudyInstanceUID
            ) VALUES (
                uuid_generate_v4(), '{newAcc}', '{ex_id[0]}', '{patient[0]}', '{equipo_data[0]}', '{NewAdm}', 1, 0,1, NOW(),'{study_instance_uid}'
            )
        """
        print(query)
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
