#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test para verificar GET /admissions/{admission_guid}
Crea una admisión primero y luego verifica los números
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
    print_test("2. Obtener datos de prueba")
    
    try:
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
        
        study_type_id = study_types[0][0]
        print_info(f"Tipo de estudio: {study_types[0][2]}")
        
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
        
        return {
            'location_id': location_id,
            'patient_id': patient_id,
            'study_type_id': study_type_id,
            'equipment_id': equipment_id
        }
    except Exception as e:
        print_error(f"Error obteniendo datos: {str(e)}")
        return None


def create_order():
    """Crea una orden de admisión"""
    print_test("3. Crear orden de admisión")
    
    test_data = get_test_data()
    if not test_data:
        return None
    
    order_data = {
        "patient_id": test_data['patient_id'],
        "location_id": test_data['location_id'],
        "exam": {
            "study_type_id": test_data['study_type_id'],
            "equipment_id": test_data['equipment_id'],
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
            exam_id = result.get('exam_id')
            print_success("Orden creada exitosamente")
            print_info(f"Número de admisión: {result.get('admission_number')}")
            print_info(f"Número de acceso: {result.get('accession_number')}")
            print_info(f"ID del examen: {exam_id}")
            return exam_id
        else:
            print_error(f"Error: {data.get('message')}")
            return None
    else:
        print_error(f"Error HTTP {response.status_code}")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
        return None


def test_admission_details(admission_guid):
    """Test: GET /admissions/{admission_guid}"""
    print_test(f"4. Test: GET /admissions/{admission_guid}")
    
    response = requests.get(
        f"{BASE_URL}/admissions/{admission_guid}",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            admission = data.get('data', {})
            
            print_success("Respuesta obtenida")
            print("\nDetalles completos de la admisión:")
            print(json.dumps(admission, indent=2, ensure_ascii=False))
            
            # Verificar campos clave
            print("\n" + "="*70)
            print("VERIFICACIÓN DE CAMPOS:")
            print("="*70)
            
            admission_number = admission.get('admission_number')
            accession_number = admission.get('accession_number')
            
            if admission_number and admission_number.strip():
                print_success(f"✓ Admission Number: '{admission_number}'")
            else:
                print_error(f"✗ Admission Number: VACÍO o NULL (valor: '{admission_number}')")
            
            if accession_number and accession_number.strip():
                print_success(f"✓ Accession Number: '{accession_number}'")
            else:
                print_error(f"✗ Accession Number: VACÍO o NULL (valor: '{accession_number}')")

            # Verificación de Location y Equipment
            location = admission.get('location')
            equipment = admission.get('equipment')

            if location and location.strip():
                print_success(f"✓ Location: '{location}'")
            else:
                print_error(f"✗ Location: VACÍO o NULL (valor: '{location}')")

            if equipment and equipment.strip():
                print_success(f"✓ Equipment: '{equipment}'")
            else:
                print_error(f"✗ Equipment: VACÍO o NULL (valor: '{equipment}')")
            
            # Otros campos importantes
            print(f"\nℹ️  Otros campos:")
            print(f"   - GUID: {admission.get('guid')}")
            print(f"   - Patient: {admission.get('patient_name')} {admission.get('patient_surname')}")
            print(f"   - Study Type: {admission.get('study_type')}")
            print(f"   - Status: {admission.get('status')}")
            print(f"   - Is Admitted: {admission.get('is_admitted')}")
            print(f"   - Is Executed: {admission.get('is_executed')}")
            print(f"   - Equipment: {admission.get('equipment')}")
            print(f"   - Location: {admission.get('location')}")
            
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


def main():
    print_header("TEST: Detalles de Admisión - Verificar Números")
    
    if not login():
        print_error("No se pudo autenticar")
        return 1
    
    exam_id = create_order()
    if not exam_id:
        print_error("No se pudo crear la orden")
        return 1
    
    test_admission_details(exam_id)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
