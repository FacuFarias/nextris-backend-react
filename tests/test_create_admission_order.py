#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test para el endpoint de crear orden de admisión
"""

import requests
import json
import sys

# Configuración
BASE_URL = "http://localhost:5001/api"
TEST_USER_EMAIL = "sysadmin"
TEST_USER_PASSWORD = "1234"

token = None


def print_header(title):
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}")


def print_test(test_name):
    print(f"\n{test_name}")
    print("-" * 70)


def print_success(message):
    print(f"✅ {message}")


def print_error(message):
    print(f"❌ {message}")


def print_info(message):
    print(f"ℹ️  {message}")


def login():
    global token
    print_test("1. Login")
    
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and 'access_token' in data.get('data', {}):
            token = data['data']['access_token']
            print_success("Login exitoso")
            return True
    
    print_error("Login falló")
    return False


def get_headers():
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def get_test_data():
    """Obtiene datos necesarios para crear una orden de prueba"""
    print_test("2. Obteniendo datos de prueba")
    
    # Obtener ubicación
    response = requests.get(f"{BASE_URL}/institutional/locations", headers=get_headers())
    locations = response.json().get('data', [])
    if not locations:
        print_error("No hay ubicaciones disponibles")
        return None
    
    location_id = locations[0]['guid']
    print_info(f"Ubicación: {locations[0].get('name')}")
    
    # Obtener pacientes
    response = requests.post(
        f"{BASE_URL}/patients/by-location",
        headers=get_headers(),
        json={"location_id": location_id}
    )
    patients = response.json().get('data', [])
    if not patients:
        print_error("No hay pacientes disponibles")
        return None
    
    patient_id = patients[0]['guid']
    print_info(f"Paciente: {patients[0].get('name')} {patients[0].get('surname')}")
    
    # Obtener tipos de estudio
    response = requests.get(f"{BASE_URL}/study-types", headers=get_headers())
    study_types = response.json().get('data', [])
    if not study_types:
        print_error("No hay tipos de estudio disponibles")
        return None
    
    study_type_id = study_types[0][0]  # El primer elemento es el GUID
    print_info(f"Tipo de estudio: {study_types[0][2]}")  # El tercer elemento es la descripción
    
    # Obtener equipos
    response = requests.get(
        f"{BASE_URL}/config/equipment?location_id={location_id}",
        headers=get_headers()
    )
    equipment = response.json().get('data', [])
    if not equipment:
        print_error("No hay equipos disponibles")
        return None
    
    equipment_id = equipment[0]['guid']
    print_info(f"Equipo: {equipment[0].get('description')}")
    
    # Obtener médicos
    response = requests.get(
        f"{BASE_URL}/institutional/locations/{location_id}/physicians",
        headers=get_headers()
    )
    physicians = response.json().get('data', [])
    physician_id = physicians[0]['guid'] if physicians else None
    if physician_id:
        print_info(f"Médico: {physicians[0].get('description')}")
    
    # Obtener obras sociales
    response = requests.get(
        f"{BASE_URL}/institutional/locations/{location_id}/health-insurances",
        headers=get_headers()
    )
    insurances = response.json().get('data', [])
    insurance_id = insurances[0]['guid'] if insurances else None
    if insurance_id:
        print_info(f"Obra social: {insurances[0].get('description')}")
    
    return {
        'location_id': location_id,
        'patient_id': patient_id,
        'study_type_id': study_type_id,
        'equipment_id': equipment_id,
        'physician_id': physician_id,
        'insurance_id': insurance_id
    }


def test_create_order():
    """Test: Crear orden de admisión"""
    print_test("3. Test: POST /admission/create-order")
    
    test_data = get_test_data()
    if not test_data:
        return False
    
    order_data = {
        "patient_id": test_data['patient_id'],
        "location_id": test_data['location_id'],
        "exam": {
            "study_type_id": test_data['study_type_id'],
            "equipment_id": test_data['equipment_id'],
            "physician_id": test_data['physician_id'],
            "insurance_id": test_data['insurance_id'],
            "severity": "normal"
        }
    }
    
    print_info("Creando orden de admisión...")
    response = requests.post(
        f"{BASE_URL}/admission/create-order",
        headers=get_headers(),
        json=order_data
    )
    
    if response.status_code == 201:
        data = response.json()
        if data.get('success'):
            result = data.get('data', {})
            print_success("Orden creada exitosamente")
            print_info(f"Número de admisión: {result.get('admission_number')}")
            print_info(f"Número de acceso: {result.get('accession_number')}")
            print_info(f"ID del examen: {result.get('exam_id')}")
            print_info(f"Study Instance UID: {result.get('study_instance_uid')}")
            return True
        else:
            print_error(f"Error: {data.get('message')}")
            return False
    else:
        print_error(f"Error HTTP {response.status_code}")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
        return False


def test_create_order_without_required_fields():
    """Test: Validaciones de campos obligatorios"""
    print_test("4. Test: Validaciones de campos obligatorios")
    
    # Sin patient_id
    response = requests.post(
        f"{BASE_URL}/admission/create-order",
        headers=get_headers(),
        json={"location_id": "test"}
    )
    
    if response.status_code == 400:
        print_success("Validación patient_id: OK")
    else:
        print_error(f"Esperaba 400, recibió {response.status_code}")
        return False
    
    # Sin location_id
    response = requests.post(
        f"{BASE_URL}/admission/create-order",
        headers=get_headers(),
        json={"patient_id": "test"}
    )
    
    if response.status_code == 400:
        print_success("Validación location_id: OK")
    else:
        print_error(f"Esperaba 400, recibió {response.status_code}")
        return False
    
    # Sin study_type_id
    response = requests.post(
        f"{BASE_URL}/admission/create-order",
        headers=get_headers(),
        json={
            "patient_id": "test",
            "location_id": "test",
            "exam": {"equipment_id": "test"}
        }
    )
    
    if response.status_code == 400:
        print_success("Validación study_type_id: OK")
        return True
    else:
        print_error(f"Esperaba 400, recibió {response.status_code}")
        return False


def main():
    print_header("TEST: Crear Orden de Admisión")
    
    tests = [
        ("Login", login),
        ("Crear orden completa", test_create_order),
        ("Validaciones", test_create_order_without_required_fields)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            if not result and test_name == "Login":
                print_error("Login falló, no se pueden ejecutar más tests")
                break
        except Exception as e:
            print_error(f"Excepción en test '{test_name}': {str(e)}")
            results.append((test_name, False))
    
    # Resumen
    print_header("RESUMEN DE TESTS")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nResultado: {passed}/{total} tests pasaron")
    
    if passed == total:
        print_success("¡Todos los tests pasaron!")
        return 0
    else:
        print_error(f"{total - passed} tests fallaron")
        return 1


if __name__ == "__main__":
    sys.exit(main())
