#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Test Suite Interactivo - API NextRIS
Permite elegir qué módulo y endpoints probar
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from datetime import datetime

# Configuración
BASE_URL = "http://127.0.0.1:5001/api"
USERNAME = "sysadmin"
PASSWORD = "1234"

# Variables globales
access_token = None
test_data = {}


def clear_screen():
    """Limpia la pantalla"""
    os.system('clear' if os.name != 'nt' else 'cls')


def print_header(title):
    """Imprime encabezado"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def print_menu(title, options):
    """Imprime menú de opciones"""
    print_header(title)
    for key, value in options.items():
        print(f"  {key}. {value}")
    print("  0. Volver/Salir")
    print("-"*70)


def get_headers():
    """Retorna headers con token de autorización"""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }


def login():
    """Realiza login y obtiene token"""
    global access_token
    
    print("\n🔐 Iniciando sesión...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "username": USERNAME,
                "password": PASSWORD,
                "user_type": "staff"
            },
            headers={"Content-Type": "application/json"}
        )
        
        data = response.json()
        
        if response.status_code == 200 and data.get('success'):
            access_token = data['data']['access_token']
            print(f"✓ Login exitoso como {USERNAME}")
            return True
        else:
            print(f"✗ Login fallido: {data.get('message', 'Error desconocido')}")
            return False
            
    except Exception as e:
        print(f"✗ Error en login: {str(e)}")
        return False


def execute_test(endpoint, method, url, body=None, params=None):
    """Ejecuta un test de endpoint"""
    print(f"\n{'='*70}")
    print(f"Endpoint: {method} {endpoint}")
    print(f"{'='*70}")
    
    try:
        if method == "GET":
            response = requests.get(url, headers=get_headers(), params=params)
        elif method == "POST":
            response = requests.post(url, headers=get_headers(), json=body)
        elif method == "PUT":
            response = requests.put(url, headers=get_headers(), json=body)
        elif method == "PATCH":
            response = requests.patch(url, headers=get_headers(), json=body)
        elif method == "DELETE":
            response = requests.delete(url, headers=get_headers())
        
        print(f"\nEstado: {response.status_code}")
        
        try:
            data = response.json()
            print(f"Respuesta:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Guardar datos útiles para otros tests
            if response.status_code == 200 and data.get('success'):
                if 'data' in data:
                    if isinstance(data['data'], list) and len(data['data']) > 0:
                        if isinstance(data['data'][0], list):
                            test_data['last_id'] = data['data'][0][0]
                        elif isinstance(data['data'][0], dict):
                            test_data['last_id'] = data['data'][0].get('guid')
                    elif isinstance(data['data'], dict):
                        test_data['last_id'] = data['data'].get('guid')
            
            return response.status_code == 200
        except:
            print(f"Respuesta (texto): {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


# ==================== TESTS DE ADMINISTRACIÓN ====================

def test_admin_menu():
    """Menú de tests de administración"""
    
    endpoints = {
        '1': ('GET /admin/examinations', 'Lista de exámenes (admin)'),
        '2': ('POST /admin/examinations/<id>/unreport', 'Quitar estado reportado'),
        '3': ('PATCH /admin/examinations/<id>/status', 'Actualizar estado de examen'),
        '4': ('GET /admin/equipment', 'Lista de equipos'),
        '5': ('POST /admin/equipment/by-study-type', 'Equipos por tipo de estudio'),
        '6': ('GET /admin/workdays', 'Días laborables'),
    }
    
    while True:
        print_menu("API DE ADMINISTRACIÓN - Endpoints", endpoints)
        
        choice = input("\nSeleccione opción: ").strip()
        
        if choice == '0':
            break
        
        if choice == '1':
            limit = input("Límite de resultados (Enter para 10): ").strip() or "10"
            offset = input("Offset (Enter para 0): ").strip() or "0"
            execute_test('/admin/examinations', 'GET', f"{BASE_URL}/admin/examinations",
                        params={'limit': limit, 'offset': offset})
        
        elif choice == '2':
            exam_id = input(f"Ingrese GUID del examen (Enter para usar último: {test_data.get('last_id', 'N/A')}): ").strip()
            exam_id = exam_id or test_data.get('last_id')
            if exam_id:
                confirm = input("⚠️  ¿Está seguro de quitar el reporte? (s/n): ").strip().lower()
                if confirm == 's':
                    execute_test(f'/admin/examinations/{exam_id}/unreport', 'POST',
                                f"{BASE_URL}/admin/examinations/{exam_id}/unreport")
            else:
                print("✗ GUID requerido")
        
        elif choice == '3':
            exam_id = input("Ingrese GUID del examen: ").strip()
            new_status = input("Ingrese nuevo estado: ").strip()
            if exam_id and new_status:
                execute_test(f'/admin/examinations/{exam_id}/status', 'PATCH',
                            f"{BASE_URL}/admin/examinations/{exam_id}/status",
                            body={'status': new_status})
            else:
                print("✗ GUID y estado requeridos")
        
        elif choice == '4':
            execute_test('/admin/equipment', 'GET', f"{BASE_URL}/admin/equipment")
        
        elif choice == '5':
            study_type_id = input("Ingrese GUID del tipo de estudio: ").strip()
            if study_type_id:
                execute_test('/admin/equipment/by-study-type', 'POST',
                            f"{BASE_URL}/admin/equipment/by-study-type",
                            body={'study_type_id': study_type_id})
            else:
                print("✗ GUID del tipo de estudio requerido")
        
        elif choice == '6':
            execute_test('/admin/workdays', 'GET', f"{BASE_URL}/admin/workdays")
        
        else:
            print("⚠️  Opción inválida")
        
        input("\nPresione Enter para continuar...")


# ==================== TESTS DE CITAS/AGENDA ====================

def test_appointments_menu():
    """Menú de tests de citas/agenda"""
    
    endpoints = {
        '1': ('POST /appointments/calendar-events', 'Eventos del calendario'),
        '2': ('POST /appointments', 'Crear nueva cita'),
        '3': ('GET /appointments', 'Lista de citas'),
        '4': ('PATCH /appointments/<id>', 'Actualizar cita'),
        '5': ('PATCH /appointments/<id>/reschedule', 'Reprogramar cita'),
        '6': ('POST /appointments/<id>/admit', 'Admisionar cita'),
        '7': ('DELETE /appointments/<id>', 'Eliminar cita'),
    }
    
    while True:
        print_menu("API DE CITAS/AGENDA - Endpoints", endpoints)
        
        choice = input("\nSeleccione opción: ").strip()
        
        if choice == '0':
            break
        
        if choice == '1':
            equipment = input("Ingrese AETitle del equipo (Enter para RX1): ").strip() or "RX1"
            execute_test('/appointments/calendar-events', 'POST',
                        f"{BASE_URL}/appointments/calendar-events",
                        body={'equipment_aetitle': equipment})
        
        elif choice == '2':
            patient_id = input("GUID del paciente: ").strip()
            exam_id = input("GUID del tipo de examen: ").strip()
            start_dt = input("Fecha/hora inicio (YYYY-MM-DD HH:MM:SS): ").strip()
            end_dt = input("Fecha/hora fin (YYYY-MM-DD HH:MM:SS): ").strip()
            appt_type = input("Tipo (doctor/equipment): ").strip()
            
            if patient_id and exam_id and start_dt and end_dt and appt_type:
                body = {
                    'patient_id': patient_id,
                    'exam_id': exam_id,
                    'start_datetime': start_dt,
                    'end_datetime': end_dt,
                    'appointment_type': appt_type
                }
                
                if appt_type == 'doctor':
                    doctor_id = input("GUID del doctor: ").strip()
                    if doctor_id:
                        body['doctor_id'] = doctor_id
                else:
                    equip_id = input("GUID del equipo: ").strip()
                    if equip_id:
                        body['equipment_id'] = equip_id
                
                execute_test('/appointments', 'POST', f"{BASE_URL}/appointments", body=body)
            else:
                print("✗ Faltan campos requeridos")
        
        elif choice == '3':
            print("\nFiltros disponibles:")
            date_filter = input("Fecha (YYYY-MM-DD, opcional): ").strip()
            admitted_filter = input("Admisionados (true/false, opcional): ").strip()
            
            params = {}
            if date_filter:
                params['date'] = date_filter
            if admitted_filter:
                params['admitted'] = admitted_filter
            
            execute_test('/appointments', 'GET', f"{BASE_URL}/appointments", params=params)
        
        elif choice == '4':
            appt_id = input(f"GUID de la cita (Enter para usar último: {test_data.get('last_id', 'N/A')}): ").strip()
            appt_id = appt_id or test_data.get('last_id')
            
            if appt_id:
                doctor_id = input("Nuevo GUID del doctor (opcional): ").strip()
                equip_id = input("Nuevo GUID del equipo (opcional): ").strip()
                
                body = {}
                if doctor_id:
                    body['doctor_id'] = doctor_id
                if equip_id:
                    body['equipment_id'] = equip_id
                
                if body:
                    execute_test(f'/appointments/{appt_id}', 'PATCH',
                                f"{BASE_URL}/appointments/{appt_id}", body=body)
                else:
                    print("✗ Debe proporcionar al menos un campo para actualizar")
            else:
                print("✗ GUID de cita requerido")
        
        elif choice == '5':
            appt_id = input("GUID de la cita: ").strip()
            start_dt = input("Nueva fecha/hora inicio (ISO 8601): ").strip()
            end_dt = input("Nueva fecha/hora fin (ISO 8601): ").strip()
            
            if appt_id and start_dt and end_dt:
                execute_test(f'/appointments/{appt_id}/reschedule', 'PATCH',
                            f"{BASE_URL}/appointments/{appt_id}/reschedule",
                            body={'start': start_dt, 'end': end_dt})
            else:
                print("✗ Todos los campos son requeridos")
        
        elif choice == '6':
            appt_id = input("GUID de la cita: ").strip()
            if appt_id:
                confirm = input("⚠️  ¿Confirmar admisión de cita? (s/n): ").strip().lower()
                if confirm == 's':
                    execute_test(f'/appointments/{appt_id}/admit', 'POST',
                                f"{BASE_URL}/appointments/{appt_id}/admit")
            else:
                print("✗ GUID de cita requerido")
        
        elif choice == '7':
            appt_id = input("GUID de la cita: ").strip()
            if appt_id:
                confirm = input("⚠️  ¿Confirmar eliminación? (s/n): ").strip().lower()
                if confirm == 's':
                    execute_test(f'/appointments/{appt_id}', 'DELETE',
                                f"{BASE_URL}/appointments/{appt_id}")
            else:
                print("✗ GUID de cita requerido")
        
        else:
            print("⚠️  Opción inválida")
        
        input("\nPresione Enter para continuar...")


# ==================== TESTS DE INFORMACIÓN INSTITUCIONAL ====================

def test_institutional_menu():
    """Menú de tests de información institucional"""
    
    endpoints = {
        '1': ('GET /institutional/info', 'Obtener información institucional'),
        '2': ('POST /institutional/info', 'Actualizar información (sin logo)'),
        '3': ('POST /institutional/info', 'Actualizar información (con logo)'),
    }
    
    while True:
        print_menu("API DE INFORMACIÓN INSTITUCIONAL - Endpoints", endpoints)
        
        choice = input("\nSeleccione opción: ").strip()
        
        if choice == '0':
            break
        
        if choice == '1':
            execute_test('/institutional/info', 'GET', f"{BASE_URL}/institutional/info")
        
        elif choice == '2':
            name = input("Nombre de la institución: ").strip()
            mail = input("Email (opcional): ").strip()
            address = input("Dirección (opcional): ").strip()
            phone = input("Teléfono (opcional): ").strip()
            
            if name:
                data = {'name': name}
                if mail:
                    data['mail'] = mail
                if address:
                    data['address'] = address
                if phone:
                    data['phone'] = phone
                
                # Para multipart/form-data, necesitamos usar requests directamente
                import requests
                response = requests.post(
                    f"{BASE_URL}/institutional/info",
                    headers=get_headers(),
                    data=data
                )
                
                print(f"\nStatus Code: {response.status_code}")
                try:
                    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
                except:
                    print(f"Response: {response.text}")
            else:
                print("✗ El nombre es requerido")
        
        elif choice == '3':
            print("⚠️  Para actualizar con logo, use el test automatizado test_institutional_api.py")
            print("    Este menú interactivo no soporta upload de archivos.")
        
        else:
            print("⚠️  Opción inválida")
        
        input("\nPresione Enter para continuar...")


# ==================== TESTS DE MÉDICOS Y USUARIOS ====================

def test_medical_menu():
    """Menú de tests de médicos y usuarios"""
    
    endpoints = {
        '1': ('GET /doctors', 'Lista de médicos'),
        '2': ('GET /doctors?active_only=true', 'Médicos activos'),
        '3': ('GET /doctors/<id>/groups', 'Grupos del médico'),
        '4': ('POST /doctors/check-group-membership', 'Verificar pertenencia a grupo'),
        '5': ('POST /doctors/by-study-type', 'Médicos por tipo de estudio'),
        '6': ('GET /users', 'Lista de usuarios'),
        '7': ('POST /users', 'Crear usuario'),
        '8': ('PATCH /users/<id>', 'Actualizar usuario'),
    }
    
    while True:
        print_menu("API DE MÉDICOS Y USUARIOS - Endpoints", endpoints)
        
        choice = input("\nSeleccione opción: ").strip()
        
        if choice == '0':
            break
        
        if choice == '1':
            execute_test('/doctors', 'GET', f"{BASE_URL}/doctors")
        
        elif choice == '2':
            execute_test('/doctors?active_only=true', 'GET', f"{BASE_URL}/doctors?active_only=true")
        
        elif choice == '3':
            doctor_id = input(f"GUID del médico (Enter para último: {test_data.get('last_id', 'N/A')}): ").strip()
            doctor_id = doctor_id or test_data.get('last_id')
            if doctor_id:
                execute_test(f'/doctors/{doctor_id}/groups', 'GET',
                            f"{BASE_URL}/doctors/{doctor_id}/groups")
            else:
                print("✗ GUID del médico requerido")
        
        elif choice == '4':
            doctor_id = input("GUID del médico: ").strip()
            study_type_id = input("GUID del tipo de estudio: ").strip()
            if doctor_id and study_type_id:
                execute_test('/doctors/check-group-membership', 'POST',
                            f"{BASE_URL}/doctors/check-group-membership",
                            body={'doctor_id': doctor_id, 'study_type_id': study_type_id})
            else:
                print("✗ Ambos GUIDs son requeridos")
        
        elif choice == '5':
            study_type_id = input("GUID del tipo de estudio (Enter para todos): ").strip()
            body = {'study_type_id': study_type_id} if study_type_id else {}
            execute_test('/doctors/by-study-type', 'POST',
                        f"{BASE_URL}/doctors/by-study-type", body=body)
        
        elif choice == '6':
            execute_test('/users', 'GET', f"{BASE_URL}/users")
        
        elif choice == '7':
            username = input("Username: ").strip()
            password = input("Password: ").strip()
            name = input("Nombre: ").strip()
            surname = input("Apellido: ").strip()
            email = input("Email (opcional): ").strip()
            
            if username and password and name and surname:
                body = {
                    'username': username,
                    'password': password,
                    'name': name,
                    'surname': surname
                }
                if email:
                    body['email'] = email
                
                execute_test('/users', 'POST', f"{BASE_URL}/users", body=body)
            else:
                print("✗ Username, password, name y surname son requeridos")
        
        elif choice == '8':
            user_id = input(f"GUID del usuario (Enter para último: {test_data.get('last_id', 'N/A')}): ").strip()
            user_id = user_id or test_data.get('last_id')
            
            if user_id:
                print("\nCampos a actualizar (dejar vacío para omitir):")
                name = input("Nuevo nombre: ").strip()
                surname = input("Nuevo apellido: ").strip()
                email = input("Nuevo email: ").strip()
                
                body = {}
                if name:
                    body['name'] = name
                if surname:
                    body['surname'] = surname
                if email:
                    body['email'] = email
                
                if body:
                    execute_test(f'/users/{user_id}', 'PATCH',
                                f"{BASE_URL}/users/{user_id}", body=body)
                else:
                    print("✗ Debe proporcionar al menos un campo para actualizar")
            else:
                print("✗ GUID del usuario requerido")
        
        else:
            print("⚠️  Opción inválida")
        
        input("\nPresione Enter para continuar...")


# ==================== TESTS DE AUTENTICACIÓN ====================

def test_auth_menu():
    """Menú de tests de autenticación"""
    
    endpoints = {
        '1': ('POST /auth/login', 'Login staff'),
        '2': ('POST /auth/login', 'Login con credenciales inválidas'),
        '3': ('POST /auth/login', 'Login sin campos requeridos'),
        '4': ('GET /auth/me', 'Obtener usuario actual'),
        '5': ('POST /auth/refresh', 'Refrescar access token'),
        '6': ('POST /auth/logout', 'Cerrar sesión'),
    }
    
    while True:
        print_menu("API DE AUTENTICACIÓN - Endpoints", endpoints)
        
        choice = input("\nSeleccione opción: ").strip()
        
        if choice == '0':
            break
        
        if choice == '1':
            username = input(f"Usuario (Enter para '{USERNAME}'): ").strip() or USERNAME
            password = input(f"Contraseña (Enter para '{PASSWORD}'): ").strip() or PASSWORD
            user_type = input("Tipo de usuario (staff/patient, Enter para 'staff'): ").strip() or "staff"
            
            execute_test('/auth/login', 'POST', f"{BASE_URL}/auth/login",
                        body={'username': username, 'password': password, 'user_type': user_type})
        
        elif choice == '2':
            print("Probando con credenciales inválidas...")
            execute_test('/auth/login', 'POST', f"{BASE_URL}/auth/login",
                        body={'username': 'usuario_invalido', 'password': 'pass_invalido', 'user_type': 'staff'})
        
        elif choice == '3':
            print("Probando sin campo password...")
            execute_test('/auth/login', 'POST', f"{BASE_URL}/auth/login",
                        body={'username': 'test'})
        
        elif choice == '4':
            if not access_token:
                print("⚠️  Debe hacer login primero (opción 1)")
            else:
                execute_test('/auth/me', 'GET', f"{BASE_URL}/auth/me")
        
        elif choice == '5':
            print("⚠️  Este endpoint requiere un refresh_token")
            print("El refresh_token se obtiene al hacer login y debe enviarse en el header Authorization")
            print("Ejemplo: Authorization: Bearer <refresh_token>")
        
        elif choice == '6':
            if not access_token:
                print("⚠️  Debe hacer login primero (opción 1)")
            else:
                execute_test('/auth/logout', 'POST', f"{BASE_URL}/auth/logout")
        
        else:
            print("⚠️  Opción inválida")
        
        input("\nPresione Enter para continuar...")


# ==================== TESTS DE PACIENTES ====================

def test_patients_menu():
    """Menú de tests de pacientes"""
    
    endpoints = {
        '1': ('GET /patients', 'Listar pacientes (paginado)'),
        '2': ('GET /patients/minimal', 'Listar pacientes (mínimo)'),
        '3': ('POST /patients/search', 'Buscar pacientes'),
        '4': ('POST /patients/search/advanced', 'Búsqueda avanzada'),
        '5': ('POST /patients/by-location', 'Pacientes por ubicación'),
        '6': ('GET /patients/<guid>', 'Obtener paciente por ID'),
        '7': ('POST /patients', 'Crear paciente completo'),
        '8': ('POST /patients/quick', 'Crear paciente rápido'),
        '9': ('PUT /patients/<guid>', 'Actualizar paciente'),
        '10': ('PATCH /patients/<guid>/email', 'Actualizar email'),
        '11': ('DELETE /patients/<guid>', 'Eliminar paciente'),
        '12': ('POST /patients/merge', 'Fusionar pacientes'),
        '13': ('GET /patients/<guid>/history', 'Historial del paciente'),
        '14': ('GET /patients/<guid>/history/report', 'Historial detallado'),
        '15': ('GET /patients/<guid>/studies/count', 'Contar estudios'),
        '16': ('GET /studies/reassign/list', 'Lista de reasignación'),
        '17': ('POST /studies/reassign', 'Reasignar estudio'),
        '18': ('GET /studies/<exam_id>/image-link', 'Link de imagen'),
        '19': ('GET /patients/reassign/list', 'Lista pacientes reasignar'),
        '20': ('GET /user/locations', 'Ubicaciones del usuario'),
    }
    
    while True:
        print_menu("API DE PACIENTES - Endpoints", endpoints)
        
        choice = input("\nSeleccione opción: ").strip()
        
        if choice == '0':
            break
        
        if choice == '1':
            execute_test('/patients', 'GET', f"{BASE_URL}/patients", params={'page': 1, 'per_page': 10})
        
        elif choice == '2':
            execute_test('/patients/minimal', 'GET', f"{BASE_URL}/patients/minimal")
        
        elif choice == '3':
            query = input("Ingrese texto de búsqueda (Enter para 'test'): ").strip() or "test"
            execute_test('/patients/search', 'POST', f"{BASE_URL}/patients/search", 
                        body={'query': query, 'page': 1, 'per_page': 10})
        
        elif choice == '4':
            execute_test('/patients/search/advanced', 'POST', f"{BASE_URL}/patients/search/advanced",
                        body={'name': '', 'surname': '', 'dni': '', 'page': 1, 'per_page': 10})
        
        elif choice == '5':
            execute_test('/patients/by-location', 'POST', f"{BASE_URL}/patients/by-location",
                        body={'location_ids': [], 'page': 1, 'per_page': 10})
        
        elif choice == '6':
            patient_id = input(f"Ingrese GUID del paciente (Enter para usar último: {test_data.get('last_id', 'N/A')}): ").strip()
            patient_id = patient_id or test_data.get('last_id')
            if patient_id:
                execute_test(f'/patients/{patient_id}', 'GET', f"{BASE_URL}/patients/{patient_id}")
            else:
                print("✗ No hay GUID disponible")
        
        elif choice == '7':
            print("Creando paciente de prueba...")
            execute_test('/patients', 'POST', f"{BASE_URL}/patients",
                        body={
                            'name': 'Test',
                            'surname': 'API',
                            'nationalcode': f'DNI{datetime.now().strftime("%H%M%S")}',
                            'birthdate': '1990-01-01',
                            'sexcode': 'M',
                            'email': 'test@example.com'
                        })
        
        elif choice == '8':
            print("Creando paciente rápido...")
            execute_test('/patients/quick', 'POST', f"{BASE_URL}/patients/quick",
                        body={
                            'name': 'Quick',
                            'surname': 'Test',
                            'nationalcode': f'Q{datetime.now().strftime("%H%M%S")}'
                        })
        
        elif choice == '9':
            patient_id = input("Ingrese GUID del paciente: ").strip()
            if patient_id:
                execute_test(f'/patients/{patient_id}', 'PUT', f"{BASE_URL}/patients/{patient_id}",
                            body={'name': 'Updated', 'surname': 'Name', 'email': 'updated@test.com'})
            else:
                print("✗ GUID requerido")
        
        elif choice == '10':
            patient_id = input("Ingrese GUID del paciente: ").strip()
            new_email = input("Ingrese nuevo email: ").strip()
            if patient_id and new_email:
                execute_test(f'/patients/{patient_id}/email', 'PATCH', 
                            f"{BASE_URL}/patients/{patient_id}/email",
                            body={'email': new_email})
            else:
                print("✗ GUID y email requeridos")
        
        elif choice == '11':
            patient_id = input("Ingrese GUID del paciente a eliminar: ").strip()
            if patient_id:
                confirm = input("⚠️  ¿Está seguro? (s/n): ").strip().lower()
                if confirm == 's':
                    execute_test(f'/patients/{patient_id}', 'DELETE', f"{BASE_URL}/patients/{patient_id}")
            else:
                print("✗ GUID requerido")
        
        elif choice == '13':
            patient_id = input(f"Ingrese GUID del paciente: ").strip() or test_data.get('last_id')
            if patient_id:
                execute_test(f'/patients/{patient_id}/history', 'GET', 
                            f"{BASE_URL}/patients/{patient_id}/history")
            else:
                print("✗ GUID requerido")
        
        elif choice == '15':
            patient_id = input(f"Ingrese GUID del paciente: ").strip() or test_data.get('last_id')
            if patient_id:
                execute_test(f'/patients/{patient_id}/studies/count', 'GET',
                            f"{BASE_URL}/patients/{patient_id}/studies/count")
            else:
                print("✗ GUID requerido")
        
        elif choice == '20':
            execute_test('/user/locations', 'GET', f"{BASE_URL}/user/locations")
        
        else:
            print("⚠️  Opción en desarrollo o inválida")
        
        input("\nPresione Enter para continuar...")


# ==================== TESTS DE ESTUDIOS ====================

def test_studies_menu():
    """Menú de tests de estudios/exámenes"""
    
    endpoints = {
        '1': ('GET /examinations/<guid>', 'Detalles de examen'),
        '2': ('GET /examinations', 'Listar todos los exámenes'),
        '3': ('POST /examinations/filtered', 'Exámenes filtrados'),
        '4': ('POST /examinations/assigned/<medico_id>', 'Exámenes asignados a médico'),
        '5': ('POST /worklist', 'Crear worklist DICOM'),
        '6': ('DELETE /worklist/<exam_id>', 'Cancelar worklist'),
        '7': ('GET /examinations/orders', 'Órdenes pendientes'),
        '8': ('POST /examinations/verify-assignability', 'Verificar asignabilidad médico'),
        '9': ('GET /study-types', 'Catálogo tipos de estudios'),
        '10': ('GET /equipment', 'Lista de equipos'),
        '11': ('POST /equipment/by-modality', 'Equipos por modalidad'),
        '12': ('POST /appointments/equipment', 'Crear citas por equipo'),
        '13': ('POST /appointments/medico', 'Crear citas por médico'),
        '14': ('POST /examinations/<exam_id>/execute', 'Ejecutar orden'),
        '15': ('GET /examinations/unreported', 'Exámenes no reportados'),
        '16': ('GET /examinations/all', 'Todos los exámenes'),
        '17': ('GET /examinations/<exam_id>/report-data', 'Datos para reporte'),
        '18': ('GET /examinations/distribution', 'Órdenes para distribución'),
    }
    
    while True:
        print_menu("API DE ESTUDIOS/EXÁMENES - Endpoints", endpoints)
        
        choice = input("\nSeleccione opción: ").strip()
        
        if choice == '0':
            break
        
        if choice == '1':
            exam_id = input(f"Ingrese GUID del examen (Enter para usar último: {test_data.get('last_id', 'N/A')}): ").strip()
            exam_id = exam_id or test_data.get('last_id')
            if exam_id:
                execute_test(f'/examinations/{exam_id}', 'GET', f"{BASE_URL}/examinations/{exam_id}")
            else:
                print("✗ No hay GUID disponible")
        
        elif choice == '2':
            execute_test('/examinations', 'GET', f"{BASE_URL}/examinations")
        
        elif choice == '3':
            include_reported = input("¿Incluir reportados? (s/n): ").strip().lower() == 's'
            execute_test('/examinations/filtered', 'POST', f"{BASE_URL}/examinations/filtered",
                        body={'filters': {}, 'include_reported': include_reported})
        
        elif choice == '4':
            medico_id = input("Ingrese GUID del médico: ").strip()
            include_reported = input("¿Incluir reportados? (s/n): ").strip().lower() == 's'
            if medico_id:
                execute_test(f'/examinations/assigned/{medico_id}', 'POST',
                            f"{BASE_URL}/examinations/assigned/{medico_id}",
                            body={'include_reported': include_reported})
            else:
                print("✗ GUID del médico requerido")
        
        elif choice == '5':
            print("⚠️  Este endpoint requiere datos válidos de paciente, tipo de estudio y equipo")
            print("Ejemplo de uso documentado en test_studies_api.py")
        
        elif choice == '6':
            exam_id = input("Ingrese GUID del examen a cancelar: ").strip()
            if exam_id:
                confirm = input("⚠️  ¿Está seguro de cancelar este examen? (s/n): ").strip().lower()
                if confirm == 's':
                    execute_test(f'/worklist/{exam_id}', 'DELETE', f"{BASE_URL}/worklist/{exam_id}")
            else:
                print("✗ GUID requerido")
        
        elif choice == '7':
            execute_test('/examinations/orders', 'GET', f"{BASE_URL}/examinations/orders")
        
        elif choice == '8':
            medico_id = input("Ingrese GUID del médico: ").strip()
            study_type_id = input("Ingrese GUID del tipo de estudio: ").strip()
            if medico_id and study_type_id:
                execute_test('/examinations/verify-assignability', 'POST',
                            f"{BASE_URL}/examinations/verify-assignability",
                            body={'medico_id': medico_id, 'study_type_id': study_type_id})
            else:
                print("✗ Ambos GUIDs requeridos")
        
        elif choice == '9':
            execute_test('/study-types', 'GET', f"{BASE_URL}/study-types")
        
        elif choice == '10':
            location_id = input("Ingrese location_id (Enter para todos): ").strip()
            params = {'location_id': location_id} if location_id else None
            execute_test('/equipment', 'GET', f"{BASE_URL}/equipment", params=params)
        
        elif choice == '11':
            study_type_id = input("Ingrese GUID del tipo de estudio: ").strip()
            location_id = input("Ingrese location_id (opcional): ").strip()
            if study_type_id:
                body = {'study_type_id': study_type_id}
                if location_id:
                    body['location_id'] = location_id
                execute_test('/equipment/by-modality', 'POST', 
                            f"{BASE_URL}/equipment/by-modality", body=body)
            else:
                print("✗ GUID del tipo de estudio requerido")
        
        elif choice == '14':
            exam_id = input("Ingrese GUID del examen: ").strip()
            if exam_id:
                execute_test(f'/examinations/{exam_id}/execute', 'POST',
                            f"{BASE_URL}/examinations/{exam_id}/execute",
                            body={
                                'history': 'Historial de prueba',
                                'clinicalquestion': 'Pregunta clínica de prueba',
                                'stat': False
                            })
            else:
                print("✗ GUID requerido")
        
        elif choice == '15':
            execute_test('/examinations/unreported', 'GET', f"{BASE_URL}/examinations/unreported")
        
        elif choice == '16':
            execute_test('/examinations/all', 'GET', f"{BASE_URL}/examinations/all")
        
        elif choice == '17':
            exam_id = input(f"Ingrese GUID del examen: ").strip() or test_data.get('last_id')
            if exam_id:
                execute_test(f'/examinations/{exam_id}/report-data', 'GET',
                            f"{BASE_URL}/examinations/{exam_id}/report-data")
            else:
                print("✗ GUID requerido")
        
        elif choice == '18':
            all_reported = input("¿Incluir todos los reportados? (s/n): ").strip().lower() == 's'
            execute_test('/examinations/distribution', 'GET',
                        f"{BASE_URL}/examinations/distribution",
                        params={'all_reported': str(all_reported).lower()})
        
        else:
            print("⚠️  Opción inválida")
        
        input("\nPresione Enter para continuar...")


# ==================== MENÚ PRINCIPAL ====================

def main_menu():
    """Menú principal"""
    
    clear_screen()
    print_header("TEST SUITE INTERACTIVO - API NEXTRIS")
    print(f"\nURL Base: {BASE_URL}")
    print(f"Usuario: {USERNAME}")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Login automático
    if not login():
        print("\n❌ No se pudo iniciar sesión. Verifique las credenciales y el servidor.")
        sys.exit(1)
    
    while True:
        modules = {
            '1': 'API de Autenticación (6 endpoints)',
            '2': 'API de Pacientes (20 endpoints)',
            '3': 'API de Estudios/Exámenes (19 endpoints)',
            '4': 'API de Administración (6 endpoints)',
            '5': 'API de Citas/Agenda (7 endpoints)',
            '6': 'API de Información Institucional (2 endpoints)',
            '7': 'API de Médicos y Usuarios (7 endpoints)',
        }
        
        print_menu("MÓDULOS DISPONIBLES", modules)
        
        choice = input("\nSeleccione módulo: ").strip()
        
        if choice == '0':
            print("\n👋 Saliendo...")
            break
        
        elif choice == '1':
            test_auth_menu()
        
        elif choice == '2':
            test_patients_menu()
        
        elif choice == '3':
            test_studies_menu()
        
        elif choice == '4':
            test_admin_menu()
        
        elif choice == '5':
            test_appointments_menu()
        
        elif choice == '6':
            test_institutional_menu()
        
        elif choice == '7':
            test_medical_menu()
        
        else:
            print("⚠️  Opción inválida")
            input("\nPresione Enter para continuar...")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Saliendo...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)
