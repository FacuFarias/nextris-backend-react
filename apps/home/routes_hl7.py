# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
import mysql.connector
from flask import jsonify
import requests
from apps.home import blueprint
from flask import render_template, request
from flask_login import login_required
from jinja2 import TemplateNotFound
import json
import sqlite3
from flask import session
from datetime import datetime



#server_url = "http://hapi.fhir.org/baseR4"
server_url = "http://localhost:8080/fhir"  # URL del servidor HAPI FHIR local

# Configuración de la conexión
config = {
    'user': 'hig948c5thl6s4onwucj',
    'password': 'pscale_pw_k50FNrDhyaYvGQAAjAdToZwTGULpaJ65GOgjJyjSssB',
    'host': 'aws.connect.psdb.cloud',
    'database': 'planetscale_db',
}

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


@blueprint.route('/index')
@login_required
def index():

    return render_template('home/index.html', segment='index')


@blueprint.route('/buscar_pacientes', methods=['POST'])
def buscar_pacientes():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    try:
        # Obtener datos del cuerpo de la solicitud en formato JSON
        data = request.get_json()
        
        # Acceder a los valores individuales
        name = data.get('name')

        surname = data.get('surname')
        documento = data.get('documento')
        Telefono = data.get('Telefono')
        buscar_mail = data.get('buscar_mail')
        sex = data.get('sex')
        fecha_nacimiento = data.get('fecha_nacimiento')
        tarjeta_sanitaria = data.get('tarjeta_sanitaria')
        idP = data.get('idP')

        # Realizar la lógica de búsqueda con los datos recibidos
        query=f"SELECT Guid, Name, Surname, NationalCode,SexCode,BirthDate  FROM planetscale_db.DataPatient WHERE Surname LIKE '%{name}%'"
        cursor.execute(query)

        response_data=cursor.fetchall()

        return jsonify(response_data)

    except Exception as e:
        # Manejar errores si es necesario
        response_data = {
            'success': False,
            'message': 'Error en la búsqueda',
            'error': str(e)
        }
        return jsonify(response_data), 500



@blueprint.route('/eliminar_paciente', methods=['GET'])
def eliminar_paciente():
    
    id_paciente = request.args.get('id')

    paciente_url = f'{server_url}/Patient/{id_paciente}?_cascade=delete'

    try:
        # Realiza la solicitud DELETE al servidor HAPI FHIR para eliminar el paciente
        response = requests.delete(paciente_url)

        if response.status_code == 200:
            # La eliminación fue exitosa (código de respuesta 204)
            print("nice")
            return jsonify({'success': True})
            
        else:
            # La eliminación no fue exitosa, puedes manejar el error según tus necesidades
            #print(response.status_code)
            return jsonify({'success': False, 'error': 'Error en la eliminación'})

    except Exception as e:
        # Ocurrió un error durante la solicitud, puedes manejarlo adecuadamente
        return jsonify({'success': False, 'error': str(e)})




@blueprint.route('/editar_paciente', methods=['POST'])
def editar_pacientes():
    id_paciente = request.form['id']

    # Realiza una solicitud GET para obtener los datos actuales del paciente
    response = requests.get(f"{server_url}/Patient/{id_paciente}")

    if response.status_code == 200:
        # El paciente existe y se obtuvieron los datos actuales
        paciente_existente = response.json()

        # Actualiza los datos del paciente con los valores del formulario
        paciente_existente['name'] = [{'text': request.form['nombrePaciente']}]
        paciente_existente['identifier'] = [
            {"type": {"text": "DNI"}, "value": request.form['dni']},
            {"type": {"text": "Número Vademecum"}, "value": request.form['nvademecum']},
            {"type": {"text": "Número Nosológico"}, "value": request.form['nosologico']},
            # Agrega más identificadores según sea necesario
        ]
        paciente_existente['gender'] = request.form['sex']
        paciente_existente['birthDate'] = request.form['fecha_nacimiento']
        paciente_existente['telecom'] = [
            {"system": "email", "value": request.form['mail']},
            {"system": "phone", "value": request.form['telefono']},
        ]
        # Agrega otros campos según sea necesario (teléfono, correo, etc.)

        # Realiza una solicitud PUT para actualizar el paciente
        response_actualizar = requests.put(f"{server_url}/Patient/{id_paciente}", json=paciente_existente)

        if response_actualizar.status_code == 200:
            print("Paciente actualizado con éxito en el servidor FHIR")
        else:
            print(response_actualizar.content)
    else:
        print("Paciente no encontrado en el servidor FHIR")

    return render_template('/home/buscar_paciente.html', actualizado=True)

@blueprint.route('/nueva_cita', methods=['GET'])
def nueva_cita():

    cita = Cita()
    # Guardar la cita en la sesión
    fecha_actual = datetime.now().strftime('%Y-%m-%d')
    cita.fecha = fecha_actual
    session['cita'] = cita.to_dict()

    query="SELECT * FROM TipoEstudio"
    conn = sqlite3.connect('basededatos.db')
    cursor = conn.cursor()
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


@blueprint.route('/agregar_paciente', methods=['POST'])
def agregar_pacientes():
    
    print(request.form['nombrePaciente'])
    
    name=request.form['nombrePaciente']
    dni=request.form['dni']

    gender=request.form['sex']

    
    fecha_nacimiento=request.form['fecha_nacimiento']
    nvademecum=request.form['nvademecum']
    nosologico=request.form['nosologico']
    telefono=request.form['telefono']
    mail=request.form['mail']
    #tsan=request.form['tsan']

    paciente = {
        "resourceType": "Patient",
        "name": [{"text": name}],
        "identifier": [
            {"type": {"text": "DNI"}, "value": dni},
            {"type": {"text": "Número Vademecum"}, "value": nvademecum},
            {"type": {"text": "Número Nosológico"}, "value": nosologico},
            # Agrega más identificadores según sea necesario
        ],
        "gender": gender,
        "birthDate": fecha_nacimiento,

        "telecom": [{"system": "email", "value": mail}, {"system": "phone", "value": telefono}],
    }

    response = requests.post(f"{server_url}/Patient/", json=paciente)

    if response.status_code == 201:
        print("Paciente creado con éxito en el servidor FHIR")
    else:
        print(response.content)


    return render_template('/home/buscar_paciente.html',cargado=True)


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
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "SELECT * FROM planetscale_db.IsProvenanceGroup;"
    cursor.execute(query)

    return jsonify(cursor.fetchall())


@blueprint.route('/get_origins', methods=['GET']) 
def get_origins():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = """SELECT o.Guid, o.Description, g.Description AS groupo, o.IsActive, o.ExternalCode, o.PatientCD, o.IsEditingExaminationDisabled, o.PublicationWeb, o.IsPriceListMandatory, o.IsOrderToNotify
               FROM planetscale_db.IsProvenance o 
               JOIN planetscale_db.IsProvenanceGroup g ON o.IdProvenanceGroup = g.Guid"""
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_body_parts', methods=['GET']) 
def get_body_parts():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "SELECT * FROM planetscale_db.IsAnatomicalPart;"
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_ministerial_codes', methods=['GET']) 
def get_codes():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "SELECT * FROM planetscale_db.IsMinisterialCode"
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_modalities', methods=['GET']) 
def get_modalities():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "SELECT * FROM planetscale_db.IsModality"
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_exams', methods=['GET']) 
def get_exams():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    # Modificamos la consulta para incluir un JOIN con la tabla IsMinisterialCode
    query = """
        SELECT e.Guid, e.Description, m.Description AS MinisterialCode, n.Description AS modality, e.ExecutionTime, e.IsActive 
        FROM planetscale_db.IsExam e
        JOIN planetscale_db.IsMinisterialCode m ON e.IdMinisterialCode = m.Guid
        JOIN planetscale_db.IsModality n ON e.IdModality = n.Guid
    """
    
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_rooms', methods=['GET']) 
def get_rooms():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "SELECT Guid,Description,ExternalCode,IsActive FROM planetscale_db.IsRoom"
    cursor.execute(query)

    return jsonify(cursor.fetchall())

@blueprint.route('/get_mach', methods=['GET']) 
def get_mach():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = """SELECT e.Guid, e.Description, e.AETitle,e.ExternalCode, r.Description AS Room, d.Code AS MDICOM, e.IsActive, p.Description AS provenance, e.IP, e.BrandEquipment,e.ModelEquipment,e.SNEquipment
                 FROM planetscale_db.IsEquipment e
                 JOIN planetscale_db.IsRoom r ON e.IdRoom = r.Guid
                 JOIN planetscale_db.IsDICOMModality d ON e.IdDICOMModality = d.Guid
                 JOIN planetscale_db.IsProvenance p ON e.IdProvenance = p.Guid
                """
    
    cursor.execute(query)
    #print(cursor.fetchall())
    return jsonify(cursor.fetchall())

@blueprint.route('/get_days', methods=['GET']) 
def get_days():
    agenda_param = request.args.get('agenda')
    
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    
    # Obtener el IdAgenda
    query = "SELECT Guid FROM planetscale_db.IsAgenda WHERE Description=%s"
    cursor.execute(query, (agenda_param,))
    IdAgenda = cursor.fetchall()[0][0]

    # Obtener los datos de la tabla IsAgendaDays
    query = "SELECT * FROM planetscale_db.IsAgendaDays WHERE IdAgenda=%s"
    cursor.execute(query, (IdAgenda,))
    datos = cursor.fetchall()

    data=[]
    for dato in datos:
        fila=[str(dato[0]),dato[2],str(dato[3]),str(dato[4]),dato[5],dato[6]]
        data.append(fila)
    print(data)
    # Convertir timedelta a cadenas antes de jsonif

    connection.close()

    return jsonify(data)

@blueprint.route('/get_agendas', methods=['GET']) 
def get_agendas():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = """SELECT a.Guid, a.Description, e.Description AS Equipment, a.ExternalCode, a.IsActive,
                      DATE_FORMAT(a.StartDate, '%d-%m-%Y') AS FormattedStartDate,
                      DATE_FORMAT(a.EndDate, '%d-%m-%Y') AS FormattedEndDate
               FROM planetscale_db.IsAgenda a
               JOIN planetscale_db.IsEquipment e ON a.IdEquipment = e.Guid
            """
    
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_business_units', methods=['GET']) 
def get_business_units():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = """SELECT * FROM planetscale_db.IsBusinessUnit"""
    
    cursor.execute(query)
    return jsonify(cursor.fetchall())

@blueprint.route('/get_domain_procede', methods=['GET']) 
def get_domain_procede():
    
    BU_name=request.args.get('BU')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = """SELECT Guid FROM planetscale_db.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(BU_name,))
    bu_id=cursor.fetchall()[0][0]
    query = """SELECT Guid,IdProvenance FROM planetscale_db.RelBusinessUnitProvenance WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(bu_id,))
    provenance_group=cursor.fetchall()
    

    response=[]
    for provenance in provenance_group:
        query="""SELECT Description from planetscale_db.IsProvenance WHERE Guid=%s"""
        cursor.execute(query,(provenance[1],))
        ProvenanceName=cursor.fetchall()[0][0]
        fila=[provenance[0],ProvenanceName]
        response.append(fila)

    return jsonify(response)
    
@blueprint.route('/get_domain_equipment', methods=['GET']) 
def get_domain_equipment():
    
    BU_name=request.args.get('BU')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = """SELECT Guid FROM planetscale_db.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(BU_name,))
    bu_id=cursor.fetchall()[0][0]
    
    query = """SELECT Guid,IdEquipment FROM planetscale_db.RelBusinessUnitEquipment WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(bu_id,))
    equipment_group=cursor.fetchall()
    
    #print(equipment_group)
    response=[]
    for equip in equipment_group:
        query="""SELECT Description from planetscale_db.IsEquipment WHERE Guid=%s"""
        cursor.execute(query,(equip[1],))
        EquipName=cursor.fetchall()[0][0]
        fila=[equip[0],EquipName]
        response.append(fila)
    
    return jsonify(response)


@blueprint.route('/get_domain_modalities', methods=['GET']) 
def get_domain_modalities():
    
    BU_name=request.args.get('BU')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = """SELECT Guid FROM planetscale_db.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(BU_name,))
    bu_id=cursor.fetchall()[0][0]
    query = """SELECT Guid,IdModality FROM planetscale_db.RelBusinessUnitModality WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(bu_id,))
    modalities_group=cursor.fetchall()

    response=[]
    for modality in modalities_group:
        query="""SELECT Description from planetscale_db.IsModality WHERE Guid=%s"""
        cursor.execute(query,(modality[1],))
        ProvenanceName=cursor.fetchall()[0][0]
        fila=[modality[0],ProvenanceName]
        response.append(fila)

    return jsonify(response)

@blueprint.route('/get_check_procede', methods=['GET']) 
def get_check_procede():
    
    BU_name=request.args.get('BU')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = """SELECT Guid FROM planetscale_db.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(BU_name,))
    bu_id=cursor.fetchall()[0][0]
    query = """SELECT IdProvenance FROM planetscale_db.RelBusinessUnitProvenance WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(bu_id,))
    provenance_group=cursor.fetchall()
    
    idProvenances_group=[]

    for provenance in provenance_group:
        idProvenances_group.append(provenance[0])
    
    query = """SELECT Guid,Description FROM planetscale_db.IsProvenance"""
    cursor.execute(query)
    all_procedences=cursor.fetchall()

    response=[]
    for procedence in all_procedences:
        if procedence[0] in idProvenances_group:
            fila=[1,procedence[0],procedence[1]]
        else:
            fila=[0,procedence[0],procedence[1]]
        response.append(fila)

    print(response)
    return jsonify(response)


@blueprint.route('/get_check_equip', methods=['GET']) 
def get_check_equip():
    
    BU_name=request.args.get('BU')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    #Obtengo el nombre del bu, y con eso obtengo el id
    query = """SELECT Guid FROM planetscale_db.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(BU_name,))
    bu_id=cursor.fetchone()[0]

    #En la lista de relaciones, obtengo todos los id de los equipment que tengan relacion con el id del bu que acabo de obtener
    query = """SELECT IdEquipment FROM planetscale_db.RelBusinessUnitEquipment WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(bu_id,))
    equipment_group=cursor.fetchall()
    
    idEquipment_group=[]

    for equip in equipment_group:
        idEquipment_group.append(equip[0])

    # en idEquipment_group tengo todos los id de los equipos que tienen relacion
    
    #Aca saco toda la lista de los equipos
    query = """SELECT Guid,Description FROM planetscale_db.IsEquipment"""
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

    print(response)
    return jsonify(response)

@blueprint.route('/get_check_mod', methods=['GET']) 
def get_check_mod():
    
    BU_name=request.args.get('BU')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    #Obtengo el nombre del bu, y con eso obtengo el id
    query = """SELECT Guid FROM planetscale_db.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(BU_name,))
    bu_id=cursor.fetchone()[0]

    #En la lista de relaciones, obtengo todos los id de los equipment que tengan relacion con el id del bu que acabo de obtener
    query = """SELECT IdModality FROM planetscale_db.RelBusinessUnitModality WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(bu_id,))
    modalities_group=cursor.fetchall()
    
    idModality_group=[]

    for modality in modalities_group:
        idModality_group.append(modality[0])

    # en idModality_group tengo todos los id de los modalidades que tienen relacion
    
    #Aca saco toda la lista de los equipos
    query = """SELECT Guid,Description FROM planetscale_db.IsModality"""
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

    print(response)
    return jsonify(response)



@blueprint.route('/update_procede', methods=['POST']) 
def update_procede():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    name_bu = request.form['name_bu']
    query="""SELECT Guid FROM planetscale_db.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(name_bu,))
    id_bu=cursor.fetchone()[0]

    seleccion_multiple_valores = request.form.getlist('seleccion_multiple[]')
    
    # Hacer algo con los valores, por ejemplo, imprimirlos
    print(seleccion_multiple_valores)

    query="""SELECT IdProvenance FROM planetscale_db.RelBusinessUnitProvenance WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(id_bu,))
    lista_procedencias = [procedencia[0] for procedencia in cursor.fetchall()] #Aca tengo la lista de procedencias para ese bu

    # Aca recorro los seleccionados. Si el seleccionado no está en la lista de relaciones, agrego la relación
    for id in seleccion_multiple_valores:
        
        if id not in lista_procedencias:
            print("el id= "+id+" no está en la lista de proc")
            query="""INSERT INTO planetscale_db.RelBusinessUnitProvenance(Guid,IdBusinessUnit,IdProvenance) VALUES (UUID(),%s,%s)"""
            cursor.execute(query,(id_bu,id))
            connection.commit()

    #Ahora tengo que recorrer la lista de las relaciones creadas. Si está creada una relación, pero no está en las actuales, debo eliminar esa relación.
    for procedencia in lista_procedencias:
        if procedencia not in seleccion_multiple_valores:
            print("saque a: "+procedencia)
            query="""DELETE FROM planetscale_db.RelBusinessUnitProvenance WHERE IdProvenance = %s and IdBusinessUnit=%s;"""
            cursor.execute(query,(procedencia,id_bu,))
            connection.commit()

    response=[]
    for provenance in seleccion_multiple_valores:
        query="""SELECT Description FROM planetscale_db.IsProvenance WHERE Guid=%s"""
        cursor.execute(query,(provenance,))
        response.append(cursor.fetchone()[0])
    # print(response)
    return jsonify(response)

@blueprint.route('/update_equip', methods=['POST']) 
def update_equip():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    name_bu = request.form['name_bu_equip']
    query="""SELECT Guid FROM planetscale_db.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(name_bu,))
    id_bu=cursor.fetchone()[0]

    seleccion_multiple_valores = request.form.getlist('seleccion_multiple[]')

    query="""SELECT IdEquipment FROM planetscale_db.RelBusinessUnitEquipment WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(id_bu,))
    lista_equipment = [equipment[0] for equipment in cursor.fetchall()] #Aca tengo la lista de procedencias para ese bu

    # Aca recorro los seleccionados. Si el seleccionado no está en la lista de relaciones, agrego la relación
    for id in seleccion_multiple_valores:
        
        if id not in lista_equipment:
            query="""INSERT INTO planetscale_db.RelBusinessUnitEquipment(Guid,IdBusinessUnit,IdEquipment) VALUES (UUID(),%s,%s)"""
            cursor.execute(query,(id_bu,id))
            connection.commit()

    #Ahora tengo que recorrer la lista de las relaciones creadas. Si está creada una relación, pero no está en las actuales, debo eliminar esa relación.
    for procedencia in lista_equipment:
        if procedencia not in seleccion_multiple_valores:
            #print("saque a: "+procedencia)
            query="""DELETE FROM planetscale_db.RelBusinessUnitEquipment WHERE IdEquipment = %s and IdBusinessUnit=%s;"""
            cursor.execute(query,(procedencia,id_bu,))
            connection.commit()

    response=[]
    for provenance in seleccion_multiple_valores:
        query="""SELECT Description FROM planetscale_db.IsEquipment WHERE Guid=%s"""
        cursor.execute(query,(provenance,))
        response.append(cursor.fetchone()[0])
    return jsonify(response)

@blueprint.route('/update_mod', methods=['POST']) 
def update_mod():
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    name_bu = request.form['name_bu_mod']
    query="""SELECT Guid FROM planetscale_db.IsBusinessUnit WHERE Description=%s"""
    cursor.execute(query,(name_bu,))
    id_bu=cursor.fetchone()[0]

    seleccion_multiple_valores = request.form.getlist('seleccion_multiple[]')
    
    query="""SELECT IdModality FROM planetscale_db.RelBusinessUnitModality WHERE IdBusinessUnit=%s"""
    cursor.execute(query,(id_bu,))
    lista_modality = [equipment[0] for equipment in cursor.fetchall()] #Aca tengo la lista de modality para ese bu

    # Aca recorro los seleccionados. Si el seleccionado no está en la lista de relaciones, agrego la relación
    for id in seleccion_multiple_valores:
        
        if id not in lista_modality:
            #print("el id= "+id+" no está en la lista de proc")
            query="""INSERT INTO planetscale_db.RelBusinessUnitModality(Guid,IdBusinessUnit,IdModality) VALUES (UUID(),%s,%s)"""
            cursor.execute(query,(id_bu,id))
            connection.commit()

    #Ahora tengo que recorrer la lista de las relaciones creadas. Si está creada una relación, pero no está en las actuales, debo eliminar esa relación.
    for modality in lista_modality:
        if modality not in seleccion_multiple_valores:
            #print("saque a: "+modality)
            query="""DELETE FROM planetscale_db.RelBusinessUnitModality WHERE IdModality = %s and IdBusinessUnit=%s;"""
            cursor.execute(query,(modality,id_bu,))
            connection.commit()

    response=[]
    for provenance in seleccion_multiple_valores:
        query="""SELECT Description FROM planetscale_db.IsModality WHERE Guid=%s"""
        cursor.execute(query,(provenance,))
        response.append(cursor.fetchone()[0])
    # print(response)
    return jsonify(response)


@blueprint.route('/eliminar_grupo', methods=['POST']) 
def eliminar_grupo():
    data = request.json
    id = data.get('id')
    
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM planetscale_db.IsProvenanceGroup WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()

    return jsonify("Fila eliminada")


@blueprint.route('/eliminar_procedencia', methods=['POST']) 
def eliminar_procedencia():
    data = request.json
    id = data.get('id')
    
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM planetscale_db.IsProvenance WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()

    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_codigo', methods=['POST']) 
def eliminar_codigo():
    data = request.json
    id = data.get('id')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM planetscale_db.IsMinisterialCode WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_mod', methods=['POST']) 
def eliminiar_mod():
    data = request.json
    id = data.get('id')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM planetscale_db.IsModality WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_ap', methods=['POST']) 
def eliminar_ap():
    data = request.json
    id = data.get('id')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM planetscale_db.IsAnatomicalPart WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_examen', methods=['POST']) 
def eliminar_examen():
    data = request.json
    id = data.get('id')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM planetscale_db.IsExam WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_room', methods=['POST']) 
def eliminar_room():
    data = request.json
    id = data.get('id')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM planetscale_db.IsRoom WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_mach', methods=['POST']) 
def eliminar_mach():
    data = request.json
    id = data.get('id')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM planetscale_db.IsEquipment WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_agenda', methods=['POST']) 
def eliminar_agenda():
    data = request.json
    id = data.get('id')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM planetscale_db.IsAgenda WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_dia', methods=['POST']) 
def eliminar_dia():
    data = request.json
    id = data.get('id')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM planetscale_db.IsAgendaDays WHERE Guid=(%s);"
    cursor.execute(query,(id,))
    connection.commit()
    return jsonify("Fila eliminada")

@blueprint.route('/eliminar_bu', methods=['POST']) 
def eliminar_bu():
    data = request.json
    id = data.get('id')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "DELETE FROM planetscale_db.IsBusinessUnit WHERE Guid=(%s);"
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

    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO planetscale_db.IsProvenanceGroup(Guid, Description, IsExternal, IsER, DelayDays) VALUES (UUID(), %s, %s, %s, %s)"
    
    cursor.execute(query, (respuesta['Description'], respuesta['IsEx'], respuesta['ps'], respuesta['delaydays']))
    connection.commit()
    connection.close()

    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}
    return jsonify(response_data)


@blueprint.route('/agregar_codigo', methods=['POST']) 
def agregar_codigo():
    respuesta = request.form.to_dict()
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO planetscale_db.IsMinisterialCode(Guid, Code, Description, `Group`) VALUES (UUID(), %s, %s, %s)"
    
    cursor.execute(query, (respuesta['ministerial_code'], respuesta['Description'], respuesta['group_code']))
    connection.commit()
    connection.close()
    response=[respuesta['ministerial_code'],respuesta['Description'],respuesta['group_code'],respuesta['id']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    return jsonify(response_data)

@blueprint.route('/agregar_mod', methods=['POST']) 
def agregar_mod():
    respuesta = request.form.to_dict()

    val = respuesta.get('IsMandatoryEquipmentChange') == 'on'
    respuesta['IsMandatoryEquipmentChange'] = 1 if val else 0
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO planetscale_db.IsModality(Guid, Description, ExternalCode, IsMandatoryEquipmentChange) VALUES (UUID(), %s, %s, %s)"
    
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
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO planetscale_db.IsExam(Guid, Description, IdMinisterialCode, IdModality,ExecutionTime,IsActive) VALUES (UUID(), %s, %s, %s, %s, %s)"
    
    cursor.execute(query, (respuesta['Description_ex'], respuesta['s_cod_min'], respuesta['s_modality'], respuesta['IsAc_ex'], respuesta['time_execution']))
    connection.commit()
    
    query= "SELECT Description from planetscale_db.IsMinisterialCode WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_cod_min'],))
    cod_min=cursor.fetchone()[0]

    query= "SELECT Description from planetscale_db.IsModality WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_modality'],))
    modality=cursor.fetchone()[0]

    response=[respuesta['Description_ex'],cod_min, modality,respuesta['time_execution'],respuesta['IsAc_ex']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    connection.close()
    return jsonify(response_data)

@blueprint.route('/agregar_ap', methods=['POST']) 
def agregar_ap():
    respuesta = request.form.to_dict()
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO planetscale_db.IsAnatomicalPart(Guid, Description) VALUES (UUID(), %s)"
    
    cursor.execute(query, (respuesta['Description_ap'],))
    connection.commit()
    connection.close()
    
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': (respuesta['Description_ap'],)}
    return jsonify(response_data)


@blueprint.route('/agregar_origen', methods=['POST']) 
def agregar_origen():
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

    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query="SELECT Description From planetscale_db.IsProvenanceGroup WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_go'],))

    Description=cursor.fetchone()[0]
    query = "INSERT INTO planetscale_db.IsProvenance(Guid, Description, IdProvenanceGroup, IsActive, ExternalCode,PatientCD,PublicationWeb,IsPriceListMandatory,IsChargeMandatory,IsOrderToNotify) VALUES (UUID(), %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    
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

    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "INSERT INTO planetscale_db.IsEquipment(Guid, Description, AETitle,ExternalCode, IdRoom,IdProvenance,IdDICOMModality,BrandEquipment,ModelEquipment,SNEquipment,IsActive,IP) VALUES (UUID(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    
    cursor.execute(query,(respuesta['Description_mach'],respuesta['AETitle'],respuesta['Ext_code_equip'],respuesta['s_sala'],respuesta['s_proc'],respuesta['s_moda'],respuesta['equip_brand'],respuesta['equip_model'],respuesta['equip_sn'],respuesta['IsAc_mach'],respuesta['equip_ip']))
    connection.commit()
    
    query= "SELECT Description from planetscale_db.IsProvenance WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_proc'],))
    provenance=cursor.fetchall()[0][0]

    query= "SELECT Code from planetscale_db.IsDICOMModality WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_moda'],))
    modality=cursor.fetchall()[0][0]

    query= "SELECT Description from planetscale_db.IsRoom WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_sala'],))
    sala=cursor.fetchall()[0][0]

    response=[respuesta['Description_mach'],respuesta['AETitle'],respuesta['Ext_code_equip'],sala, modality,respuesta['IsAc_mach'],provenance,respuesta['equip_ip'],respuesta['equip_brand'],respuesta['equip_model'],respuesta['equip_sn']]

    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}
    return jsonify(response_data)


@blueprint.route('/agregar_dia', methods=['POST']) 
def agregar_dia():
    respuesta = request.form.to_dict()
    
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query= "SELECT Guid FROM planetscale_db.IsAgenda WHERE Description=%s"
    cursor.execute(query,(respuesta["id_agenda_"],))
    IdAgenda=cursor.fetchall()[0][0]

    query = "INSERT INTO planetscale_db.IsAgendaDays(Guid, IdAgenda, Day,StartTime, EndTime,SlotNumber,PlaceForSlots) VALUES (UUID(), %s, %s, %s, %s, %s, %s)"
    
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

    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO planetscale_db.IsBusinessUnit(Guid, Description, Code, ExternalCode,HttpPacs,IsActive,IsQuestionListMandatory,IsTechnicianMandatory) VALUES (UUID(), %s, %s, %s, %s, %s, %s, %s)"
    
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

    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    # Modificar la consulta SQL para no incluir la columna Guid
    query = "UPDATE planetscale_db.IsProvenanceGroup SET Description = %s, IsExternal = %s, IsER = %s, DelayDays = %s WHERE Guid = %s;"
    
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
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    # Modificar la consulta SQL para no incluir la columna Guid
    query = "UPDATE planetscale_db.IsRoom SET Description = %s, ExternalCode = %s, IsActive = %s WHERE Guid = %s;"
    
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
    
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = "INSERT INTO planetscale_db.IsRoom(Guid, Description, ExternalCode, IsActive) VALUES (UUID(), %s, %s, %s)"
    
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
    
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    fin=respuesta.get('fecha_fin_agenda_input') 
    if fin=='':
        respuesta['fecha_fin_agenda_input']=None

    print(respuesta)
    query = "INSERT INTO planetscale_db.IsAgenda(Guid, Description, IdEquipment, StartDate,EndDate,ExternalCode,IsActive) VALUES (UUID(), %s, %s, %s,%s,%s,%s)"
    
    cursor.execute(query, (respuesta['Description_agenda'], respuesta['s_equip'], respuesta['fecha_inicio_agenda_input'],respuesta['fecha_fin_agenda_input'],respuesta['Ex_agenda'],respuesta['IsAc_ag']))
    connection.commit()

    query="SELECT Description FROM planetscale_db.IsEquipment WHERE Guid=%s"
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

    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    
    # Modificar la consulta SQL para no incluir la columna Guid
    query = "UPDATE planetscale_db.IsMinisterialCode SET Code = %s, Description = %s, `Group` = %s WHERE Guid = %s;"
    
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

    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    
    # Modificar la consulta SQL para no incluir la columna Guid
    query = "UPDATE planetscale_db.IsModality SET Description = %s, ExternalCode = %s, IsMandatoryEquipmentChange = %s WHERE Guid = %s;"
    
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
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    print(respuesta)
    
    query= "SELECT Description from planetscale_db.IsMinisterialCode WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_cod_min'],))
    cod_min=cursor.fetchone()[0]

    query= "SELECT Description from planetscale_db.IsModality WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_modality'],))
    modality=cursor.fetchone()[0]

    query= """UPDATE planetscale_db.IsExam SET Description=%s, IdMinisterialCode=%s, IdModality=%s, ExecutionTime=%s, IsActive=%s WHERE Guid=%s"""
    
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

    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    
    query = "UPDATE planetscale_db.IsEquipment SET Description = %s, ExternalCode = %s, AETitle = %s, IdRoom = %s, IdProvenance=%s, IdDICOMModality=%s ,BrandEquipment=%s, ModelEquipment= %s, SNEquipment = %s, IsActive=%s, IP=%s WHERE Guid = %s;"
    
    cursor.execute(query,(respuesta['Description_mach'], respuesta['Ext_code_equip'], respuesta['AETitle'],respuesta['s_sala'],respuesta['s_proc'],respuesta['s_moda'],respuesta['equip_brand'],respuesta['equip_model'],respuesta['equip_sn'],respuesta['IsAc_mach'],respuesta['equip_ip'],respuesta['id_mach']))
    connection.commit()

    query= "SELECT Description from planetscale_db.IsProvenance WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_proc'],))
    provenance=cursor.fetchall()[0][0]
   
    query= "SELECT Code from planetscale_db.IsDICOMModality WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_moda'],))
    modality=cursor.fetchall()[0][0]

    query= "SELECT Description from planetscale_db.IsRoom WHERE Guid=%s"
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

    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    
    # Modificar la consulta SQL para no incluir la columna Guid
    query = "UPDATE planetscale_db.IsAnatomicalPart SET Description = %s WHERE Guid = %s;"
    
    cursor.execute(query,(respuesta['Description_ap'],respuesta['id_ap']))
    connection.commit()
    
    # Crear un objeto de respuesta JSON
    response=[respuesta['Description_ap'],]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa', 'data': response}

    # Enviar el objeto JSON como respuesta
    return jsonify(response_data)

@blueprint.route('/actualizar_origen', methods=['POST']) 
def actualizar_origen ():
    connection = mysql.connector.connect(**config)
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
    query = "UPDATE planetscale_db.IsProvenance SET Description = %s, IdProvenanceGroup = %s, IsActive=%s, ExternalCode=%s,PatientCD=%s, IsEditingExaminationDisabled=%s,IsChargeMandatory=%s, IsPriceListMandatory=%s, IsOrderToNotify=%s,PublicationWeb=%s WHERE Guid = %s;"
    cursor.execute(query,(respuesta['Description_o'],respuesta['s_go'],respuesta['IsAc'],respuesta['AltCode_or'],respuesta['PatientCD'],respuesta['IsEditingExaminationDisabled'],respuesta['IsChargeMandatory'],respuesta['IsPriceListMandatory'],respuesta['IsOrderToNotify'],respuesta['PublicationWeb'],respuesta['id_origin'],))
    connection.commit()

    query="""SELECT Description FROM planetscale_db.IsProvenanceGroup WHERE Guid=%s"""
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
    
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = "UPDATE planetscale_db.IsAgenda SET Description=%s,IdEquipment=%s, StartDate=%s,EndDate=%s,ExternalCode=%s,IsActive=%s WHERE Guid=%s;"
    
    cursor.execute(query, (respuesta['Description_agenda'], respuesta['s_equip'], respuesta['fecha_inicio_agenda_input'],respuesta['fecha_fin_agenda_input'],respuesta['Ex_agenda'],respuesta['IsAc_ag'],respuesta['id_agenda'],))
    connection.commit()

    query="SELECT Description FROM planetscale_db.IsEquipment WHERE Guid=%s"
    cursor.execute(query,(respuesta['s_equip'],))
    equipo=cursor.fetchall()[0][0]

    response=[respuesta['Description_agenda'],equipo,respuesta['Ex_agenda'],respuesta['IsAc_ag'],respuesta['fecha_inicio_agenda_input'],respuesta['fecha_fin_agenda_input']]
    response_data = {'status': 'OK', 'message': 'Inserción exitosa','data': response}
    connection.close()
    return jsonify(response_data)

@blueprint.route('/actualizar_dia', methods=['POST']) 
def actualizar_dia():
    respuesta = request.form.to_dict()
    
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()

    query = "UPDATE planetscale_db.IsAgendaDays SET Day=%s,StartTime=%s, EndTime=%s,SlotNumber=%s,PlaceForSlots=%s WHERE Guid=%s;"
    
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

    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = "UPDATE planetscale_db.IsBusinessUnit SET Description=%s,Code=%s, ExternalCode=%s,HttpPacs=%s,IsActive=%s,IsQuestionListMandatory=%s,IsTechnicianMandatory=%s WHERE Guid=%s;"
    
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
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor()
    query = f'SELECT Guid,{dNeeded} FROM {TableId}'
    cursor.execute(query)

    return jsonify({'status': 'OK', 'data': cursor.fetchall()})


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
