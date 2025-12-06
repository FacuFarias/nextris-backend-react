#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Tests para API de Médicos y Usuarios - medical.py
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json

# Configuración
BASE_URL = "http://127.0.0.1:5001/api"
USERNAME = "sysadmin"
PASSWORD = "1234"

# Variables globales
access_token = None
test_user_id = None
test_doctor_id = None
test_study_type_id = None


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
    """Obtiene IDs para usar en tests"""
    global test_doctor_id, test_study_type_id
    
    try:
        # Obtener un doctor
        response = requests.get(
            f"{BASE_URL}/doctors?active_only=true",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and len(data['data']) > 0:
                test_doctor_id = data['data'][0]['guid']
        
        # Obtener un tipo de estudio
        response = requests.get(
            f"{BASE_URL}/study-types",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and len(data['data']) > 0:
                test_study_type_id = data['data'][0][0]
        
        return test_doctor_id and test_study_type_id
        
    except Exception as e:
        print(f"Error en setup: {str(e)}")
        return False


# ==================== TESTS ====================

def test_01_get_doctors():
    """Test 1: Obtener lista de médicos"""
    global test_doctor_id
    
    print_test_header(1, "GET /doctors - Lista de médicos")
    
    try:
        response = requests.get(
            f"{BASE_URL}/doctors",
            headers=get_headers()
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
        
        if response.status_code == 200 and data.get('success'):
            assert 'data' in data, "Falta campo data"
            assert isinstance(data['data'], list), "data debe ser una lista"
            if len(data['data']) > 0:
                test_doctor_id = data['data'][0]['guid']
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_02_get_doctors_active_only():
    """Test 2: Obtener solo médicos activos"""
    print_test_header(2, "GET /doctors?active_only=true - Médicos activos")
    
    try:
        response = requests.get(
            f"{BASE_URL}/doctors?active_only=true",
            headers=get_headers()
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
        
        if response.status_code == 200 and data.get('success'):
            # Verificar que todos sean activos
            for doctor in data['data']:
                if not doctor.get('isactive'):
                    return print_result(False, "Se encontraron médicos inactivos")
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_03_get_doctor_groups():
    """Test 3: Obtener grupos de un médico"""
    print_test_header(3, "GET /doctors/<id>/groups - Grupos del médico")
    
    if not test_doctor_id:
        return print_result(False, "No hay doctor_id disponible")
    
    try:
        response = requests.get(
            f"{BASE_URL}/doctors/{test_doctor_id}/groups",
            headers=get_headers()
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            assert 'data' in data, "Falta campo data"
            assert isinstance(data['data'], list), "data debe ser una lista"
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_04_check_doctor_group_membership():
    """Test 4: Verificar pertenencia a grupo"""
    print_test_header(4, "POST /doctors/check-group-membership - Verificar grupo")
    
    if not test_doctor_id or not test_study_type_id:
        return print_result(False, "No hay datos de prueba disponibles")
    
    try:
        response = requests.post(
            f"{BASE_URL}/doctors/check-group-membership",
            headers=get_headers(),
            json={
                'doctor_id': test_doctor_id,
                'study_type_id': test_study_type_id
            }
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            assert 'belongs_to_group' in data['data'], "Falta campo belongs_to_group"
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_05_check_group_membership_missing_fields():
    """Test 5: Verificar grupo sin campos requeridos"""
    print_test_header(5, "POST /doctors/check-group-membership - Sin campos")
    
    try:
        response = requests.post(
            f"{BASE_URL}/doctors/check-group-membership",
            headers=get_headers(),
            json={'doctor_id': test_doctor_id}
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


def test_06_get_doctors_by_study_type():
    """Test 6: Obtener médicos por tipo de estudio"""
    print_test_header(6, "POST /doctors/by-study-type - Con tipo de estudio")
    
    if not test_study_type_id:
        return print_result(False, "No hay study_type_id disponible")
    
    try:
        response = requests.post(
            f"{BASE_URL}/doctors/by-study-type",
            headers=get_headers(),
            json={'study_type_id': test_study_type_id}
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


def test_07_get_doctors_by_study_type_all():
    """Test 7: Obtener todos los médicos (sin filtro)"""
    print_test_header(7, "POST /doctors/by-study-type - Sin filtro")
    
    try:
        response = requests.post(
            f"{BASE_URL}/doctors/by-study-type",
            headers=get_headers(),
            json={}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
        
        if response.status_code == 200 and data.get('success'):
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_08_get_users():
    """Test 8: Obtener lista de usuarios"""
    print_test_header(8, "GET /users - Lista de usuarios")
    
    try:
        response = requests.get(
            f"{BASE_URL}/users",
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


def test_09_create_user():
    """Test 9: Crear nuevo usuario"""
    global test_user_id
    
    print_test_header(9, "POST /users - Crear usuario")
    
    try:
        import random
        username = f"test_user_{random.randint(1000, 9999)}"
        
        response = requests.post(
            f"{BASE_URL}/users",
            headers=get_headers(),
            json={
                'username': username,
                'password': 'test1234',
                'name': 'Usuario',
                'surname': 'Test',
                'email': f'{username}@test.com',
                'usertype': 'user'
            }
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 201 and data.get('success'):
            test_user_id = data['data']['user_id']
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_10_create_user_missing_fields():
    """Test 10: Crear usuario sin campos requeridos"""
    print_test_header(10, "POST /users - Sin campos requeridos")
    
    try:
        response = requests.post(
            f"{BASE_URL}/users",
            headers=get_headers(),
            json={
                'username': 'incomplete',
                'password': 'test'
            }
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


def test_11_update_user():
    """Test 11: Actualizar usuario"""
    print_test_header(11, "PATCH /users/<id> - Actualizar usuario")
    
    if not test_user_id:
        return print_result(False, "No hay user_id disponible")
    
    try:
        response = requests.patch(
            f"{BASE_URL}/users/{test_user_id}",
            headers=get_headers(),
            json={
                'name': 'Usuario Actualizado',
                'email': 'updated@test.com'
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


def test_12_update_user_not_found():
    """Test 12: Actualizar usuario inexistente"""
    print_test_header(12, "PATCH /users/<id> - Usuario inexistente")
    
    try:
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = requests.patch(
            f"{BASE_URL}/users/{fake_id}",
            headers=get_headers(),
            json={'name': 'Test'}
        )
        
        print(f"Status Code: {response.status_code}")
        
        # Debe retornar 404
        if response.status_code == 404:
            return print_result(True)
        else:
            return print_result(False, f"Debería retornar 404, retornó {response.status_code}")
            
    except Exception as e:
        return print_result(False, str(e))


def test_13_update_user_no_fields():
    """Test 13: Actualizar usuario sin campos"""
    print_test_header(13, "PATCH /users/<id> - Sin campos para actualizar")
    
    if not test_user_id:
        return print_result(False, "No hay user_id disponible")
    
    try:
        response = requests.patch(
            f"{BASE_URL}/users/{test_user_id}",
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


def test_14_unauthorized_access():
    """Test 14: Acceso sin token"""
    print_test_header(14, "GET /doctors - Sin autorización")
    
    try:
        response = requests.get(f"{BASE_URL}/doctors")
        
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
    print("  SUITE DE TESTS - API DE MÉDICOS Y USUARIOS")
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
        print(f"✓ Doctor ID: {test_doctor_id}")
        print(f"✓ Study Type ID: {test_study_type_id}")
    
    tests = [
        test_01_get_doctors,
        test_02_get_doctors_active_only,
        test_03_get_doctor_groups,
        test_04_check_doctor_group_membership,
        test_05_check_group_membership_missing_fields,
        test_06_get_doctors_by_study_type,
        test_07_get_doctors_by_study_type_all,
        test_08_get_users,
        test_09_create_user,
        test_10_create_user_missing_fields,
        test_11_update_user,
        test_12_update_user_not_found,
        test_13_update_user_no_fields,
        test_14_unauthorized_access,
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
