#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Tests para API de Citas/Agenda - appointments.py
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from datetime import datetime, timedelta

# Configuración
BASE_URL = "http://127.0.0.1:5001/api"
USERNAME = "sysadmin"
PASSWORD = "1234"

# Variables globales
access_token = None
test_appointment_id = None
test_patient_id = None
test_exam_id = None


def print_test_header(test_num, test_name):
    """Imprime encabezado de test"""
    print(f"\n{'='*70}")
    print(f"Test {test_num}: {test_name}")
    print('='*70)


def print_result(success, message=""):
    """Imprime resultado del test"""
    if success:
        print(f"✓ Test exitoso")
    else:
        print(f"✗ Test fallido: {message}")
    return success


def get_headers():
    """Retorna headers con token de autorización"""
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }


def login():
    """Realiza login y obtiene token"""
    global access_token
    
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
            return True
        else:
            return False
            
    except Exception as e:
        print(f"Error en login: {str(e)}")
        return False


def setup_test_data():
    """Obtiene IDs de paciente y examen para usar en tests"""
    global test_patient_id, test_exam_id
    
    try:
        # Obtener un paciente
        response = requests.get(
            f"{BASE_URL}/patients/minimal",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and len(data['data']) > 0:
                # data es lista de objetos dict
                test_patient_id = data['data'][0]['guid']
        
        # Obtener un tipo de estudio
        response = requests.get(
            f"{BASE_URL}/study-types",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and len(data['data']) > 0:
                # data es una lista de listas [guid, descripcion, ...]
                test_exam_id = data['data'][0][0]
        
        if test_patient_id and test_exam_id:
            return True
        else:
            print(f"❌ No se pudieron obtener datos: patient_id={test_patient_id}, exam_id={test_exam_id}")
            return False
        
    except Exception as e:
        print(f"Error en setup: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


# ==================== TESTS ====================

def test_01_create_appointment():
    """Test 1: Crear una nueva cita"""
    global test_appointment_id
    
    print_test_header(1, "POST /appointments - Crear cita")
    
    if not test_patient_id or not test_exam_id:
        return print_result(False, "No hay datos de prueba disponibles")
    
    try:
        # Crear cita para mañana
        tomorrow = datetime.now() + timedelta(days=1)
        start_time = tomorrow.replace(hour=10, minute=0, second=0)
        end_time = tomorrow.replace(hour=11, minute=0, second=0)
        
        response = requests.post(
            f"{BASE_URL}/appointments",
            headers=get_headers(),
            json={
                'patient_id': test_patient_id,
                'exam_id': test_exam_id,
                'start_datetime': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'end_datetime': end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'appointment_type': 'doctor',
                'doctor_id': '9388650a-fa37-4cb1-b346-e68ef2407d1b'  # sysadmin
            }
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 201 and data.get('success'):
            test_appointment_id = data['data']['appointment_id']
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_02_create_appointment_missing_fields():
    """Test 2: Crear cita sin campos requeridos"""
    print_test_header(2, "POST /appointments - Sin campos requeridos")
    
    try:
        response = requests.post(
            f"{BASE_URL}/appointments",
            headers=get_headers(),
            json={'patient_id': test_patient_id}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Debe retornar 400
        if response.status_code == 400:
            return print_result(True)
        else:
            return print_result(False, f"Debería retornar 400, retornó {response.status_code}")
            
    except Exception as e:
        return print_result(False, str(e))


def test_03_get_appointments():
    """Test 3: Obtener lista de citas"""
    print_test_header(3, "GET /appointments - Lista de citas")
    
    try:
        response = requests.get(
            f"{BASE_URL}/appointments",
            headers=get_headers()
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
        
        if response.status_code == 200 and data.get('success'):
            assert 'data' in data, "Falta campo data"
            assert isinstance(data['data'], list), "data debe ser una lista"
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_04_get_appointments_with_filters():
    """Test 4: Obtener citas con filtros"""
    print_test_header(4, "GET /appointments?admitted=false - Con filtros")
    
    try:
        response = requests.get(
            f"{BASE_URL}/appointments",
            headers=get_headers(),
            params={'admitted': 'false'}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
        
        if response.status_code == 200 and data.get('success'):
            # Verificar que las citas no están admisionadas
            for appointment in data['data']:
                if appointment.get('is_admitted'):
                    return print_result(False, "Se encontraron citas admisionadas en el filtro")
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_05_update_appointment():
    """Test 5: Actualizar datos de una cita"""
    print_test_header(5, "PATCH /appointments/<id> - Actualizar cita")
    
    if not test_appointment_id:
        return print_result(False, "No hay appointment_id disponible")
    
    try:
        response = requests.patch(
            f"{BASE_URL}/appointments/{test_appointment_id}",
            headers=get_headers(),
            json={'doctor_id': '9388650a-fa37-4cb1-b346-e68ef2407d1b'}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_06_reschedule_appointment():
    """Test 6: Reprogramar una cita"""
    print_test_header(6, "PATCH /appointments/<id>/reschedule - Reprogramar")
    
    if not test_appointment_id:
        return print_result(False, "No hay appointment_id disponible")
    
    try:
        # Nueva fecha
        new_date = datetime.now() + timedelta(days=2)
        start_time = new_date.replace(hour=14, minute=0, second=0)
        end_time = new_date.replace(hour=15, minute=0, second=0)
        
        response = requests.patch(
            f"{BASE_URL}/appointments/{test_appointment_id}/reschedule",
            headers=get_headers(),
            json={
                'start': start_time.isoformat() + 'Z',
                'end': end_time.isoformat() + 'Z'
            }
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_07_get_calendar_events():
    """Test 7: Obtener eventos del calendario"""
    print_test_header(7, "POST /appointments/calendar-events - Eventos del calendario")
    
    try:
        response = requests.post(
            f"{BASE_URL}/appointments/calendar-events",
            headers=get_headers(),
            json={'equipment_aetitle': 'RX1'}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
        
        if response.status_code == 200 and data.get('success'):
            assert 'data' in data, "Falta campo data"
            assert 'events' in data['data'], "Falta campo events"
            assert 'work_hours' in data['data'], "Falta campo work_hours"
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_08_calendar_events_missing_field():
    """Test 8: Eventos del calendario sin campo requerido"""
    print_test_header(8, "POST /appointments/calendar-events - Sin equipment_aetitle")
    
    try:
        response = requests.post(
            f"{BASE_URL}/appointments/calendar-events",
            headers=get_headers(),
            json={}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Debe retornar 400
        if response.status_code == 400:
            return print_result(True)
        else:
            return print_result(False, f"Debería retornar 400, retornó {response.status_code}")
            
    except Exception as e:
        return print_result(False, str(e))


def test_09_delete_appointment():
    """Test 9: Eliminar una cita"""
    print_test_header(9, "DELETE /appointments/<id> - Eliminar cita")
    
    if not test_appointment_id:
        return print_result(False, "No hay appointment_id disponible")
    
    try:
        response = requests.delete(
            f"{BASE_URL}/appointments/{test_appointment_id}",
            headers=get_headers()
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_10_delete_nonexistent_appointment():
    """Test 10: Eliminar cita inexistente"""
    print_test_header(10, "DELETE /appointments/<id> - Cita inexistente")
    
    try:
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = requests.delete(
            f"{BASE_URL}/appointments/{fake_id}",
            headers=get_headers()
        )
        
        print(f"Status Code: {response.status_code}")
        
        # Debe retornar 404
        if response.status_code == 404:
            return print_result(True)
        else:
            return print_result(False, f"Debería retornar 404, retornó {response.status_code}")
            
    except Exception as e:
        return print_result(False, str(e))


def test_11_unauthorized_access():
    """Test 11: Acceso sin token"""
    print_test_header(11, "GET /appointments - Sin autorización")
    
    try:
        response = requests.get(f"{BASE_URL}/appointments")
        
        print(f"Status Code: {response.status_code}")
        
        # Debe retornar 401
        if response.status_code == 401:
            return print_result(True)
        else:
            return print_result(False, f"Debería retornar 401, retornó {response.status_code}")
            
    except Exception as e:
        return print_result(False, str(e))


# ==================== EJECUTOR DE TESTS ====================

def run_all_tests():
    """Ejecuta todos los tests en orden"""
    
    print("\n" + "="*70)
    print("  SUITE DE TESTS - API DE CITAS/AGENDA")
    print("="*70)
    print(f"URL Base: {BASE_URL}")
    print(f"Usuario: {USERNAME}")
    
    # Login
    print("\n🔐 Iniciando sesión...")
    if not login():
        print("❌ No se pudo iniciar sesión")
        return False
    print("✓ Login exitoso")
    
    # Setup de datos de prueba
    print("\n📊 Configurando datos de prueba...")
    if not setup_test_data():
        print("⚠️  Advertencia: No se pudieron obtener todos los datos de prueba")
    else:
        print(f"✓ Paciente ID: {test_patient_id}")
        print(f"✓ Examen ID: {test_exam_id}")
    
    tests = [
        test_01_create_appointment,
        test_02_create_appointment_missing_fields,
        test_03_get_appointments,
        test_04_get_appointments_with_filters,
        test_05_update_appointment,
        test_06_reschedule_appointment,
        test_07_get_calendar_events,
        test_08_calendar_events_missing_field,
        test_09_delete_appointment,
        test_10_delete_nonexistent_appointment,
        test_11_unauthorized_access,
    ]
    
    results = []
    
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Error ejecutando test: {str(e)}")
            results.append(False)
    
    # Resumen
    print("\n" + "="*70)
    print("  RESUMEN DE TESTS")
    print("="*70)
    
    passed = sum(results)
    total = len(results)
    failed = total - passed
    success_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"Tests ejecutados: {total}")
    print(f"Tests exitosos: {passed}")
    print(f"Tests fallidos: {failed}")
    print(f"Tasa de éxito: {success_rate:.1f}%")
    print("="*70)
    
    return success_rate == 100.0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
