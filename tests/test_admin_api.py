#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Tests para API de Administración - admin.py
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


# ==================== TESTS ====================

def test_01_get_examinations_admin():
    """Test 1: Obtener lista de exámenes para administración"""
    global test_exam_id
    
    print_test_header(1, "GET /admin/examinations - Lista de exámenes")
    
    try:
        response = requests.get(
            f"{BASE_URL}/admin/examinations",
            headers=get_headers(),
            params={'limit': 10}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            assert 'data' in data, "Falta campo data"
            assert isinstance(data['data'], list), "data debe ser una lista"
            assert 'total' in data, "Falta campo total"
            
            # Guardar primer exam_id para pruebas posteriores
            if len(data['data']) > 0:
                test_exam_id = data['data'][0].get('guid')
            
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_02_get_examinations_with_filters():
    """Test 2: Obtener exámenes con filtros"""
    print_test_header(2, "GET /admin/examinations - Con filtros de paginación")
    
    try:
        response = requests.get(
            f"{BASE_URL}/admin/examinations",
            headers=get_headers(),
            params={'limit': 5, 'offset': 0}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            assert len(data['data']) <= 5, "Debe respetar el límite"
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_03_unreport_examination():
    """Test 3: Quitar estado de reportado a un examen"""
    print_test_header(3, "POST /admin/examinations/<id>/unreport - Quitar reporte")
    
    if not test_exam_id:
        return print_result(False, "No hay exam_id disponible para probar")
    
    try:
        response = requests.post(
            f"{BASE_URL}/admin/examinations/{test_exam_id}/unreport",
            headers=get_headers()
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Puede ser 200 (éxito) o 404 (no encontrado)
        if response.status_code in [200, 404]:
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_04_update_examination_status():
    """Test 4: Actualizar estado de un examen"""
    print_test_header(4, "PATCH /admin/examinations/<id>/status - Actualizar estado")
    
    if not test_exam_id:
        return print_result(False, "No hay exam_id disponible para probar")
    
    try:
        response = requests.patch(
            f"{BASE_URL}/admin/examinations/{test_exam_id}/status",
            headers=get_headers(),
            json={'status': 'TEST'}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Puede ser 200 (éxito) o 404 (no encontrado)
        if response.status_code in [200, 404]:
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_05_update_status_missing_field():
    """Test 5: Actualizar estado sin campo requerido"""
    print_test_header(5, "PATCH /admin/examinations/<id>/status - Sin campo status")
    
    if not test_exam_id:
        return print_result(False, "No hay exam_id disponible para probar")
    
    try:
        response = requests.patch(
            f"{BASE_URL}/admin/examinations/{test_exam_id}/status",
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


def test_06_get_equipment():
    """Test 6: Obtener lista de equipos"""
    print_test_header(6, "GET /admin/equipment - Lista de equipos")
    
    try:
        response = requests.get(
            f"{BASE_URL}/admin/equipment",
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


def test_07_get_equipment_by_study_type():
    """Test 7: Obtener equipos por tipo de estudio"""
    print_test_header(7, "POST /admin/equipment/by-study-type - Equipos por tipo")
    
    # Primero obtenemos un tipo de estudio válido
    try:
        # Obtener un tipo de estudio
        response_st = requests.get(
            f"{BASE_URL}/study-types",
            headers=get_headers()
        )
        
        if response_st.status_code == 200:
            study_types_data = response_st.json()
            if study_types_data.get('success') and len(study_types_data['data']) > 0:
                study_type_id = study_types_data['data'][0][0]
                
                # Ahora buscar equipos para ese tipo
                response = requests.post(
                    f"{BASE_URL}/admin/equipment/by-study-type",
                    headers=get_headers(),
                    json={'study_type_id': study_type_id}
                )
                
                data = response.json()
                print(f"Status Code: {response.status_code}")
                print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
                
                if response.status_code == 200 and data.get('success'):
                    return print_result(True)
                else:
                    return print_result(False, data.get('message', 'Error desconocido'))
            else:
                return print_result(False, "No hay tipos de estudio disponibles")
        else:
            return print_result(False, "No se pudo obtener tipos de estudio")
            
    except Exception as e:
        return print_result(False, str(e))


def test_08_get_equipment_by_study_type_missing_field():
    """Test 8: Equipos por tipo de estudio sin campo requerido"""
    print_test_header(8, "POST /admin/equipment/by-study-type - Sin study_type_id")
    
    try:
        response = requests.post(
            f"{BASE_URL}/admin/equipment/by-study-type",
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


def test_09_get_workdays():
    """Test 9: Obtener días laborables"""
    print_test_header(9, "GET /admin/workdays - Días de la semana")
    
    try:
        response = requests.get(
            f"{BASE_URL}/admin/workdays",
            headers=get_headers()
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            assert 'data' in data, "Falta campo data"
            assert len(data['data']) == 7, "Deben ser 7 días"
            assert data['data'][0]['name'] == 'Lunes', "Primer día debe ser Lunes"
            
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_10_unauthorized_access():
    """Test 10: Intentar acceder sin token"""
    print_test_header(10, "GET /admin/examinations - Sin autorización")
    
    try:
        response = requests.get(
            f"{BASE_URL}/admin/examinations"
        )
        
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
    print("  SUITE DE TESTS - API DE ADMINISTRACIÓN")
    print("="*70)
    print(f"URL Base: {BASE_URL}")
    print(f"Usuario: {USERNAME}")
    
    # Login
    print("\n🔐 Iniciando sesión...")
    if not login():
        print("❌ No se pudo iniciar sesión")
        return False
    print("✓ Login exitoso")
    
    tests = [
        test_01_get_examinations_admin,
        test_02_get_examinations_with_filters,
        test_03_unreport_examination,
        test_04_update_examination_status,
        test_05_update_status_missing_field,
        test_06_get_equipment,
        test_07_get_equipment_by_study_type,
        test_08_get_equipment_by_study_type_missing_field,
        test_09_get_workdays,
        test_10_unauthorized_access,
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
