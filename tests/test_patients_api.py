#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Script de prueba para los endpoints de la API de Pacientes
Prueba todos los 21 endpoints migrados
"""

import requests
import json
from datetime import datetime
import sys

# Configuración
BASE_URL = "http://148.230.72.8:5001"
API_URL = f"{BASE_URL}/api"

# Credenciales de prueba
USERNAME = "sysadmin"
PASSWORD = "1234"

# Token de autenticación (se obtiene en login)
TOKEN = None
PATIENTDOMAIN_ID = None  # Se obtiene dinámicamente

# Colores para la consola
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}\n")

def print_test(test_name):
    print(f"{Colors.YELLOW}[TEST]{Colors.ENDC} {test_name}")

def print_success(message):
    print(f"{Colors.GREEN}✓ {message}{Colors.ENDC}")

def print_error(message):
    print(f"{Colors.RED}✗ {message}{Colors.ENDC}")

def print_info(message):
    print(f"{Colors.BLUE}ℹ {message}{Colors.ENDC}")


def login():
    """Obtener token JWT"""
    global TOKEN
    print_header("AUTENTICACIÓN")
    print_test("Login con usuario admin")
    
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            json={
                "username": USERNAME,
                "password": PASSWORD,
                "user_type": "staff"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                TOKEN = data['data']['access_token']
                print_success(f"Login exitoso. Token obtenido.")
                print_info(f"User ID: {data['data'].get('user_id')}")
                return True
            else:
                print_error(f"Login falló: {data.get('message')}")
                return False
        else:
            print_error(f"Error HTTP {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
        return False


def get_headers():
    """Obtener headers con token JWT"""
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }


def get_patientdomain_id():
    """Obtener un patientdomain_id válido del usuario actual"""
    try:
        # Obtener el user_id actual
        response = requests.get(
            f"{API_URL}/auth/me",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                user_id = data['data']['id']
                
                # Obtener patientdomains del usuario
                response = requests.get(
                    f"{API_URL}/auth/user/{user_id}/patientdomains",
                    headers=get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and len(data['data']) > 0:
                        patientdomain_id = data['data'][0]['patientdomain_id']
                        print_info(f"Usando PatientDomain: {data['data'][0]['patientdomain_name']} ({patientdomain_id})")
                        return patientdomain_id
        
        print_error("No se pudo obtener patientdomain_id")
        return None
        
    except Exception as e:
        print_error(f"Error obteniendo patientdomain_id: {str(e)}")
        return None


# ===========================
# TESTS DE BÚSQUEDA Y LISTADO
# ===========================

def test_get_patients():
    """Test: GET /api/patients - Listar pacientes con paginación"""
    print_test("GET /api/patients - Listar pacientes")
    
    try:
        response = requests.get(
            f"{API_URL}/patients",
            headers=get_headers(),
            params={
                "page": 1,
                "per_page": 10,
                "search": ""
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                patients = data['data']['patients']
                total = data['data']['total']
                print_success(f"Obtenidos {len(patients)} pacientes de {total} totales")
                if patients:
                    print_info(f"Primer paciente: {patients[0].get('name')} {patients[0].get('surname')}")
                return patients[0]['guid'] if patients else None
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return None


def test_get_patients_minimal():
    """Test: GET /api/patients/minimal - Lista mínima para autocompletes"""
    print_test("GET /api/patients/minimal - Lista mínima")
    
    try:
        response = requests.get(
            f"{API_URL}/patients/minimal",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                patients = data['data']
                print_success(f"Obtenidos {len(patients)} pacientes (versión mínima)")
                return True
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return False


def test_search_patients():
    """Test: POST /api/patients/search - Búsqueda simple"""
    print_test("POST /api/patients/search - Búsqueda simple")
    
    try:
        response = requests.post(
            f"{API_URL}/patients/search",
            headers=get_headers(),
            json={
                "search_term": "a"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                patients = data['data']
                print_success(f"Búsqueda exitosa: {len(patients)} resultados")
                return True
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return False


def test_search_patients_advanced():
    """Test: POST /api/patients/search/advanced - Búsqueda avanzada"""
    print_test("POST /api/patients/search/advanced - Búsqueda avanzada")
    
    try:
        response = requests.post(
            f"{API_URL}/patients/search/advanced",
            headers=get_headers(),
            json={
                "criteria": {
                    "name": "juan"
                }
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                patients = data['data']
                print_success(f"Búsqueda avanzada exitosa: {len(patients)} resultados")
                return True
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return False


def test_get_patient_detail(patient_guid):
    """Test: GET /api/patients/<guid> - Detalle de paciente"""
    if not patient_guid:
        print_test("GET /api/patients/<guid> - SALTADO (no hay GUID)")
        return False
    
    print_test(f"GET /api/patients/{patient_guid[:8]}... - Detalle de paciente")
    
    try:
        response = requests.get(
            f"{API_URL}/patients/{patient_guid}",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                patient = data['data']
                print_success(f"Detalle obtenido: {patient.get('name')} {patient.get('surname')}")
                print_info(f"Email: {patient.get('email')}, Teléfono: {patient.get('phone')}")
                return True
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return False


# ===========================
# TESTS DE CREACIÓN
# ===========================

def test_create_patient_quick():
    """Test: POST /api/patients/quick - Crear paciente rápido"""
    print_test("POST /api/patients/quick - Crear paciente rápido")
    
    timestamp = datetime.now().strftime("%H%M%S")
    
    try:
        response = requests.post(
            f"{API_URL}/patients/quick",
            headers=get_headers(),
            json={
                "nombre": f"TestNombre{timestamp}",
                "apellido": f"TestApellido{timestamp}",
                "dni": f"99{timestamp}",
                "fecha_nac": "1990-01-01",
                "sexo": "M"
            }
        )
        
        if response.status_code == 201:
            data = response.json()
            if data.get('success'):
                guid = data.get('guid')
                print_success(f"Paciente rápido creado: {guid}")
                return guid
            else:
                print_error(f"Respuesta no exitosa: {data.get('message', data.get('error'))}")
        else:
            print_error(f"Error HTTP {response.status_code}: {response.text}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return None


def test_create_patient_full():
    """Test: POST /api/patients - Crear paciente completo"""
    print_test("POST /api/patients - Crear paciente completo (con PatientID autoincremental)")
    
    global PATIENTDOMAIN_ID
    timestamp = datetime.now().strftime("%H%M%S")
    
    # Obtener patientdomain_id si no lo tenemos
    if not PATIENTDOMAIN_ID:
        PATIENTDOMAIN_ID = get_patientdomain_id()
        if not PATIENTDOMAIN_ID:
            print_error("No se pudo obtener patientdomain_id")
            return None
    
    try:
        response = requests.post(
            f"{API_URL}/patients",
            headers=get_headers(),
            json={
                "name": f"TestNombreFull{timestamp}",
                "surname": f"TestApellidoFull{timestamp}",
                "patientdomain_id": PATIENTDOMAIN_ID,
                "nationalcode": f"88{timestamp}",
                "email": f"test{timestamp}@test.com",
                "phone": f"555-{timestamp}",
                "birthdate": "1985-05-15",
                "gender": "F",
                "healthcard": f"HC{timestamp}",
                "create_user": True
            }
        )
        
        if response.status_code == 201:
            data = response.json()
            if data.get('success'):
                guid = data['data']['guid']
                # Obtener el PatientID generado
                patient_resp = requests.get(
                    f"{API_URL}/patients/{guid}",
                    headers=get_headers()
                )
                if patient_resp.status_code == 200:
                    patient_data = patient_resp.json()
                    if patient_data.get('success'):
                        patient_id = patient_data['data']['patientid']
                        print_success(f"Paciente creado: {guid}")
                        print_info(f"PatientID autoincremental: {patient_id}")
                return guid
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}: {response.text}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return None


# ===========================
# TESTS DE ACTUALIZACIÓN
# ===========================

def test_update_patient(patient_guid):
    """Test: PUT /api/patients/<guid> - Actualizar paciente"""
    if not patient_guid:
        print_test("PUT /api/patients/<guid> - SALTADO (no hay GUID)")
        return False
    
    print_test(f"PUT /api/patients/{patient_guid[:8]}... - Actualizar paciente")
    
    try:
        response = requests.put(
            f"{API_URL}/patients/{patient_guid}",
            headers=get_headers(),
            json={
                "email": "updated_email@test.com",
                "phone": "555-UPDATED"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print_success("Paciente actualizado exitosamente")
                return True
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return False


def test_update_patient_email(patient_guid):
    """Test: PATCH /api/patients/<guid>/email - Actualizar solo email"""
    if not patient_guid:
        print_test("PATCH /api/patients/<guid>/email - SALTADO (no hay GUID)")
        return False
    
    print_test(f"PATCH /api/patients/{patient_guid[:8]}... - Actualizar email")
    
    try:
        response = requests.patch(
            f"{API_URL}/patients/{patient_guid}/email",
            headers=get_headers(),
            json={
                "email": "newemail@test.com"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print_success("Email actualizado exitosamente")
                return True
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return False


# ===========================
# TESTS DE HISTORIAL
# ===========================

def test_get_patient_history(patient_guid):
    """Test: GET /api/patients/<guid>/history - Historial completo"""
    if not patient_guid:
        print_test("GET /api/patients/<guid>/history - SALTADO (no hay GUID)")
        return False
    
    print_test(f"GET /api/patients/{patient_guid[:8]}.../history - Historial")
    
    try:
        response = requests.get(
            f"{API_URL}/patients/{patient_guid}/history",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                history = data['data']
                print_success(f"Historial obtenido: {len(history)} estudios")
                return True
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return False


def test_get_patient_history_report(patient_guid):
    """Test: GET /api/patients/<guid>/history/report - Historial para reportes"""
    if not patient_guid:
        print_test("GET /api/patients/<guid>/history/report - SALTADO (no hay GUID)")
        return False
    
    print_test(f"GET /api/patients/{patient_guid[:8]}.../history/report")
    
    try:
        response = requests.get(
            f"{API_URL}/patients/{patient_guid}/history/report",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                history = data['data']
                print_success(f"Historial para reporte: {len(history)} estudios")
                return True
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return False


def test_get_patient_studies_count(patient_guid):
    """Test: GET /api/patients/<guid>/studies/count - Cantidad de estudios"""
    if not patient_guid:
        print_test("GET /api/patients/<guid>/studies/count - SALTADO (no hay GUID)")
        return False
    
    print_test(f"GET /api/patients/{patient_guid[:8]}.../studies/count")
    
    try:
        response = requests.get(
            f"{API_URL}/patients/{patient_guid}/studies/count",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                count = data['data']['cantidad']
                print_success(f"Cantidad de estudios: {count}")
                return True
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return False


# ===========================
# TESTS DE REASIGNACIÓN
# ===========================

def test_get_studies_to_reassign():
    """Test: GET /api/studies/reassign/list - Lista de estudios para reasignar"""
    print_test("GET /api/studies/reassign/list")
    
    try:
        response = requests.get(
            f"{API_URL}/studies/reassign/list",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                studies = data['data']
                print_success(f"Estudios para reasignar: {len(studies)}")
                return studies[0]['guid'] if studies else None
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return None


def test_get_patients_to_reassign():
    """Test: GET /api/patients/reassign/list - Lista de pacientes para reasignación"""
    print_test("GET /api/patients/reassign/list")
    
    try:
        response = requests.get(
            f"{API_URL}/patients/reassign/list",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                patients = data['data']
                print_success(f"Pacientes para reasignar: {len(patients)}")
                return True
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return False


# ===========================
# TESTS DE UBICACIONES
# ===========================

def test_get_user_locations():
    """Test: GET /api/user/locations - Ubicaciones del usuario"""
    print_test("GET /api/user/locations")
    
    try:
        response = requests.get(
            f"{API_URL}/user/locations",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                locations = data['data']
                print_success(f"Ubicaciones del usuario: {len(locations)}")
                if locations:
                    print_info(f"Primera ubicación: {locations[0].get('name')}")
                return locations[0]['guid'] if locations else None
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return None


def test_get_patients_by_location(location_guid):
    """Test: POST /api/patients/by-location - Pacientes por ubicación"""
    if not location_guid:
        print_test("POST /api/patients/by-location - SALTADO (no hay location)")
        return False
    
    print_test(f"POST /api/patients/by-location")
    
    try:
        response = requests.post(
            f"{API_URL}/patients/by-location",
            headers=get_headers(),
            json={
                "location_id": location_guid
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                patients = data['data']
                print_success(f"Pacientes en ubicación: {len(patients)}")
                return True
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return False


# ===========================
# TESTS DE ELIMINACIÓN (AL FINAL)
# ===========================

def test_delete_patient(patient_guid):
    """Test: DELETE /api/patients/<guid> - Eliminar paciente"""
    if not patient_guid:
        print_test("DELETE /api/patients/<guid> - SALTADO (no hay GUID)")
        return False
    
    print_test(f"DELETE /api/patients/{patient_guid[:8]}... - Eliminar paciente")
    
    try:
        response = requests.delete(
            f"{API_URL}/patients/{patient_guid}",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print_success("Paciente eliminado exitosamente")
                return True
            else:
                print_error(f"Respuesta no exitosa: {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
    
    return False


# ===========================
# EJECUTAR TODOS LOS TESTS
# ===========================

def run_all_tests():
    """Ejecutar todos los tests"""
    print(f"\n{Colors.BOLD}INICIANDO TESTS DE API DE PACIENTES{Colors.ENDC}")
    print(f"Base URL: {BASE_URL}")
    print(f"Usuario: {USERNAME}")
    
    results = {
        'total': 0,
        'passed': 0,
        'failed': 0
    }
    
    # 1. Login
    if not login():
        print_error("No se pudo autenticar. Abortando tests.")
        return
    
    # 2. Tests de búsqueda y listado
    print_header("BÚSQUEDA Y LISTADO")
    
    results['total'] += 1
    patient_guid = test_get_patients()
    if patient_guid:
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    results['total'] += 1
    if test_get_patients_minimal():
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    results['total'] += 1
    if test_search_patients():
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    results['total'] += 1
    if test_search_patients_advanced():
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    results['total'] += 1
    if test_get_patient_detail(patient_guid):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # 3. Tests de creación
    print_header("CREACIÓN DE PACIENTES")
    
    results['total'] += 1
    new_patient_quick = test_create_patient_quick()
    if new_patient_quick:
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    results['total'] += 1
    new_patient_full = test_create_patient_full()
    if new_patient_full:
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # 4. Tests de actualización
    print_header("ACTUALIZACIÓN DE PACIENTES")
    
    update_guid = new_patient_full or patient_guid
    
    results['total'] += 1
    if test_update_patient(update_guid):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    results['total'] += 1
    if test_update_patient_email(update_guid):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # 5. Tests de historial
    print_header("HISTORIAL Y ESTUDIOS")
    
    results['total'] += 1
    if test_get_patient_history(patient_guid):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    results['total'] += 1
    if test_get_patient_history_report(patient_guid):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    results['total'] += 1
    if test_get_patient_studies_count(patient_guid):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # 6. Tests de reasignación
    print_header("REASIGNACIÓN DE ESTUDIOS")
    
    results['total'] += 1
    study_guid = test_get_studies_to_reassign()
    if study_guid is not None:
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    results['total'] += 1
    if test_get_patients_to_reassign():
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # 7. Tests de ubicaciones
    print_header("UBICACIONES")
    
    results['total'] += 1
    location_guid = test_get_user_locations()
    if location_guid:
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    results['total'] += 1
    if test_get_patients_by_location(location_guid):
        results['passed'] += 1
    else:
        results['failed'] += 1
    
    # 8. Tests de eliminación (al final)
    print_header("ELIMINACIÓN DE PACIENTES")
    
    # Eliminar los pacientes de prueba creados
    if new_patient_quick:
        results['total'] += 1
        if test_delete_patient(new_patient_quick):
            results['passed'] += 1
        else:
            results['failed'] += 1
    
    if new_patient_full:
        results['total'] += 1
        if test_delete_patient(new_patient_full):
            results['passed'] += 1
        else:
            results['failed'] += 1
    
    # Resumen final
    print_header("RESUMEN DE TESTS")
    print(f"Total de tests: {results['total']}")
    print(f"{Colors.GREEN}Tests exitosos: {results['passed']}{Colors.ENDC}")
    print(f"{Colors.RED}Tests fallidos: {results['failed']}{Colors.ENDC}")
    
    percentage = (results['passed'] / results['total'] * 100) if results['total'] > 0 else 0
    print(f"\n{Colors.BOLD}Porcentaje de éxito: {percentage:.2f}%{Colors.ENDC}\n")
    
    if results['failed'] == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}¡TODOS LOS TESTS PASARON!{Colors.ENDC}\n")
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}Algunos tests fallaron. Revisar los errores arriba.{Colors.ENDC}\n")


if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrumpidos por el usuario.{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Error fatal: {str(e)}{Colors.ENDC}")
        sys.exit(1)
