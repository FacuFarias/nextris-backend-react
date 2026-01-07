#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test request para verificar el flujo completo de ejecucion de examen:
1. Login
2. Crear orden
3. Listar pendientes
4. Ver detalles
5. Ejecutar
6. Verificar que este ejecutado
7. Cancelar ejecucion
8. Verificar que no este ejecutado
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

# --- Helper functions (reused logic) ---

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
    try:
        # Obtener ubicación
        response = requests.get(f"{BASE_URL}/institutional/locations", headers=get_headers())
        locations = response.json().get('data', [])
        if not locations:
            return None
        location_id = locations[0]['guid']
        
        # Obtener pacientes
        response = requests.post(f"{BASE_URL}/patients/by-location", headers=get_headers(), json={"location_id": location_id})
        patients = response.json().get('data', [])
        if not patients:
            return None
        patient_id = patients[0]['guid']
        
        # Obtener tipos de estudio
        response = requests.get(f"{BASE_URL}/study-types", headers=get_headers())
        study_types = response.json().get('data', [])
        if not study_types:
            return None
        study_type_id = study_types[0][0]
        
        # Obtener equipos
        response = requests.get(f"{BASE_URL}/config/equipment?location_id={location_id}", headers=get_headers())
        equipment = response.json().get('data', [])
        if not equipment:
            return None
        equipment_id = equipment[0]['guid']
        
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
    """Crea una orden de admisión para usar en el test"""
    print_test("2. Crear orden de prueba")
    
    test_data = get_test_data()
    if not test_data:
        print_error("No se pudieron obtener datos de prueba")
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
    
    response = requests.post(f"{BASE_URL}/admission/create-order", headers=get_headers(), json=order_data)
    
    if response.status_code == 201:
        data = response.json()
        if data.get('success'):
            result = data.get('data', {})
            exam_id = result.get('exam_id')
            print_success(f"Orden creada correctamente. Exam ID: {exam_id}")
            return exam_id
    
    print_error("Falló la creación de la orden")
    return None

# --- Main Test Logic ---

def test_get_execution_orders(exam_id):
    """Test: GET /executions/orders"""
    print_test("3. Test: GET /executions/orders")
    
    response = requests.get(f"{BASE_URL}/executions/orders", headers=get_headers())
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            orders = data.get('data', [])
            # Buscar nuestro examen en la lista
            found = False
            for order in orders:
                if order.get('guid') == exam_id:
                    found = True
                    break
            
            if found:
                print_success(f"Examen {exam_id} encontrado en la lista de pendientes")
                return True
            else:
                print_error(f"Examen {exam_id} NO encontrado en la lista de pendientes")
                return False
        else:
            print_error(f"Error en respuesta: {data.get('message')}")
            return False
    else:
        print_error(f"Error HTTP {response.status_code}")
        return False

def test_get_details_initial(exam_id):
    """Test: GET /executions/examination/<guid>/details (Antes de ejecutar)"""
    print_test("4. Test: GET Details (Inicial)")
    
    response = requests.get(f"{BASE_URL}/executions/examination/{exam_id}/details", headers=get_headers())
    
    if response.status_code == 200:
        data = response.json()
        details = data.get('data', {})
        
        # Verificar estado inicial
        if details.get('status') == 'A' and details.get('is_reported') == False:
             print_success("Detalles iniciales correctos (Status A, IsReported False)")
             return True
        else:
            print_error(f"Estado incorrecto: {details}")
            return False
            
    print_error(f"Error HTTP {response.status_code}")
    return False

def test_execute_exam(exam_id):
    """Test: POST /executions/examination/<guid>/execute"""
    print_test("5. Test: POST Execute Exam")
    
    payload = {
        "history": "Paciente refiere dolor abdominal agudo",
        "clinical_question": "Descartar apendicitis",
        "laterality": "no clasifica",
        "stat": True,
        "number_of_views": 3,
        "other_details": "Paciente claustrofobico leve"
    }
    
    response = requests.post(
        f"{BASE_URL}/executions/examination/{exam_id}/execute",
        headers=get_headers(),
        json=payload
    )
    
    if response.status_code == 200 and response.json().get('success'):
        print_success("Ejecución reportada exitosamente")
        return True
    
    print_error(f"Falló la ejecución: {response.text}")
    return False

def test_verify_execution(exam_id):
    """Verificar que el examen ahora figura como ejecutado y con los datos"""
    print_test("6. Verificación Post-Ejecución")
    
    response = requests.get(f"{BASE_URL}/executions/examination/{exam_id}/details", headers=get_headers())
    
    if response.status_code == 200:
        data = response.json().get('data', {})
        
        # Verificar campos
        checks = [
            (data.get('history') == "Paciente refiere dolor abdominal agudo", "History matches"),
            (data.get('clinical_question') == "Descartar apendicitis", "Clinical Question matches"),
            (data.get('stat') == True, "Stat is True"),
            (data.get('number_of_views') == 3, "Number of views is 3"),
            ("E" in data.get('status', '') and "A" in data.get('status', ''), f"Status contains 'A' and 'E' (Got: {data.get('status')})")
        ]
        
        all_passed = True
        for result, msg in checks:
            if result:
                print_success(msg)
            else:
                print_error(msg)
                all_passed = False
                
        # Verificar que YA NO aparece en la lista de pendientes (opcional, pero buena práctica)
        # Nota: La API execution/orders filtra por IsExecuted=0, así que NO debería aparecer.
        
        return all_passed
        
    print_error("No se pudieron obtener detalles")
    return False

def test_cancel_execution(exam_id):
    """Test: POST /executions/examination/<guid>/cancel"""
    print_test("7. Test: Cancel Execution")
    
    response = requests.post(
        f"{BASE_URL}/executions/examination/{exam_id}/cancel",
        headers=get_headers()
    )
    
    if response.status_code == 200 and response.json().get('success'):
        print_success("Cancelación reportada exitosamente")
        return True
        
    print_error(f"Falló la cancelación: {response.text}")
    return False

def test_verify_cancellation(exam_id):
    """Verificar que IsExecuted es 0 (o false en lógica de negocio, aunque la API devuelve detalles agnósticos de eso)"""
    print_test("8. Verificación Post-Cancelación")

    # Podemos verificar llamando a listar ordenes, debería aparecer de nuevo
    response = requests.get(f"{BASE_URL}/executions/orders", headers=get_headers())
    
    if response.status_code == 200:
        orders = response.json().get('data', [])
        found = False
        for order in orders:
            if order.get('guid') == exam_id:
                found = True
                break
        
        if found:
            print_success("El examen apareció nuevamente en la lista de pendientes")
            return True
        else:
            print_error("El examen NO apareció en lista de pendientes (¿Sigue ejecutado?)")
            return False

    return False

def main():
    print_header("TEST: Flujo Completo de Ejecución")
    
    if not login(): return 1
    
    exam_id = create_order()
    if not exam_id: return 1
    
    if not test_get_execution_orders(exam_id): return 1
    if not test_get_details_initial(exam_id): return 1
    if not test_execute_exam(exam_id): return 1
    if not test_verify_execution(exam_id): return 1
    if not test_cancel_execution(exam_id): return 1
    if not test_verify_cancellation(exam_id): return 1
    
    print_header("RESUMEN: TODOS LOS TESTS PASARON EXITOSAMENTE")
    return 0

if __name__ == "__main__":
    sys.exit(main())
