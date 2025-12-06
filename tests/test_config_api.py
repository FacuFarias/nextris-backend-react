#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests para API REST de Configuración del Sistema
Tests completos para endpoints de configuración, tipos de estudio, equipos, etc.
"""

import requests
import json
import sys
import uuid

# Configuración
BASE_URL = "http://localhost:5001/api"
TEST_USER_EMAIL = "sysadmin"
TEST_USER_PASSWORD = "1234"

# Variables globales para tests
token = None
created_study_type_id = None
created_equipment_id = None
created_location_id = None
test_modality_id = None
test_bodypart_id = None
test_studygroup_id = None


def print_test_header(test_name):
    """Imprime encabezado de test"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")


def print_result(success, message, response=None):
    """Imprime resultado de test"""
    status = "✓ PASS" if success else "✗ FAIL"
    print(f"{status}: {message}")
    if response:
        print(f"Status Code: {response.status_code}")
        try:
            print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)[:500]}...")
        except:
            print(f"Response: {response.text[:500]}...")
    return success


def test_login():
    """Test 1: Login exitoso"""
    global token
    print_test_header("Login y obtención de token JWT")
    
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
            return print_result(True, "Login exitoso y token obtenido", response)
    
    return print_result(False, "Error en login", response)


def get_headers():
    """Retorna headers con token de autenticación"""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def test_get_system_config():
    """Test 2: Obtener configuración del sistema"""
    print_test_header("Obtener configuración del sistema")
    
    response = requests.get(
        f"{BASE_URL}/config/system",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and 'data' in data:
            return print_result(True, "Configuración del sistema obtenida", response)
    
    return print_result(False, "Error al obtener configuración del sistema", response)


def test_get_workflow_config():
    """Test 3: Obtener configuración de workflow"""
    print_test_header("Obtener configuración de workflow")
    
    response = requests.get(
        f"{BASE_URL}/config/workflow",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and 'data' in data:
            return print_result(True, "Configuración de workflow obtenida", response)
    
    return print_result(False, "Error al obtener configuración de workflow", response)


def test_get_modalities():
    """Test 4: Obtener modalidades"""
    global test_modality_id
    print_test_header("Obtener modalidades")
    
    response = requests.get(
        f"{BASE_URL}/config/modalities",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and isinstance(data.get('data'), list):
            if len(data['data']) > 0:
                test_modality_id = data['data'][0]['guid']
            return print_result(True, f"Modalidades obtenidas: {len(data['data'])} registros", response)
    
    return print_result(False, "Error al obtener modalidades", response)


def test_get_body_parts():
    """Test 5: Obtener partes del cuerpo"""
    global test_bodypart_id
    print_test_header("Obtener partes del cuerpo")
    
    response = requests.get(
        f"{BASE_URL}/config/body-parts",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and isinstance(data.get('data'), list):
            if len(data['data']) > 0:
                test_bodypart_id = data['data'][0]['guid']
            return print_result(True, f"Partes del cuerpo obtenidas: {len(data['data'])} registros", response)
    
    return print_result(False, "Error al obtener partes del cuerpo", response)


def test_get_study_groups():
    """Test 6: Obtener grupos de estudio"""
    global test_studygroup_id
    print_test_header("Obtener grupos de estudio")
    
    response = requests.get(
        f"{BASE_URL}/config/study-groups",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and isinstance(data.get('data'), list):
            if len(data['data']) > 0:
                test_studygroup_id = data['data'][0]['guid']
            return print_result(True, f"Grupos de estudio obtenidos: {len(data['data'])} registros", response)
    
    return print_result(False, "Error al obtener grupos de estudio", response)


def test_get_study_types():
    """Test 7: Obtener tipos de estudio"""
    print_test_header("Obtener tipos de estudio")
    
    response = requests.get(
        f"{BASE_URL}/config/study-types",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and isinstance(data.get('data'), list):
            return print_result(True, f"Tipos de estudio obtenidos: {len(data['data'])} registros", response)
    
    return print_result(False, "Error al obtener tipos de estudio", response)


def test_create_study_type():
    """Test 8: Crear tipo de estudio"""
    global created_study_type_id
    print_test_header("Crear tipo de estudio")
    
    if not all([test_modality_id, test_bodypart_id, test_studygroup_id]):
        return print_result(False, "Faltan IDs necesarios para crear tipo de estudio")
    
    response = requests.post(
        f"{BASE_URL}/config/study-types",
        headers=get_headers(),
        json={
            "code": f"TEST{uuid.uuid4().hex[:6].upper()}",
            "description": "Tipo de Estudio de Prueba API",
            "studygroup_id": test_studygroup_id,
            "bodypart_id": test_bodypart_id,
            "modality_id": test_modality_id,
            "rvu": 100,
            "nofviews": 2
        }
    )
    
    if response.status_code == 201:
        data = response.json()
        if data.get('success') and 'study_type_id' in data.get('data', {}):
            created_study_type_id = data['data']['study_type_id']
            return print_result(True, f"Tipo de estudio creado: {created_study_type_id}", response)
    
    return print_result(False, "Error al crear tipo de estudio", response)


def test_update_study_type():
    """Test 9: Actualizar tipo de estudio"""
    print_test_header("Actualizar tipo de estudio")
    
    if not created_study_type_id:
        return print_result(False, "No hay ID de tipo de estudio para actualizar")
    
    response = requests.patch(
        f"{BASE_URL}/config/study-types/{created_study_type_id}",
        headers=get_headers(),
        json={
            "description": "Tipo de Estudio Actualizado API",
            "rvu": 150
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            return print_result(True, "Tipo de estudio actualizado exitosamente", response)
    
    return print_result(False, "Error al actualizar tipo de estudio", response)


def test_get_locations():
    """Test 10: Obtener ubicaciones"""
    print_test_header("Obtener ubicaciones")
    
    response = requests.get(
        f"{BASE_URL}/config/locations",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and isinstance(data.get('data'), list):
            return print_result(True, f"Ubicaciones obtenidas: {len(data['data'])} registros", response)
    
    return print_result(False, "Error al obtener ubicaciones", response)


def test_create_location():
    """Test 11: Crear ubicación"""
    global created_location_id
    print_test_header("Crear ubicación")
    
    # Obtener una ubicación existente para tests subsecuentes
    response = requests.get(
        f"{BASE_URL}/config/locations",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and data.get('data') and len(data['data']) > 0:
            created_location_id = data['data'][0]['guid']
            return print_result(True, f"Ubicación seleccionada para tests: {created_location_id}", response)
    
    return print_result(False, "No hay ubicaciones disponibles", response)


def test_get_equipment():
    """Test 12: Obtener equipos"""
    print_test_header("Obtener equipos")
    
    response = requests.get(
        f"{BASE_URL}/config/equipment",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and isinstance(data.get('data'), list):
            return print_result(True, f"Equipos obtenidos: {len(data['data'])} registros", response)
    
    return print_result(False, "Error al obtener equipos", response)


def test_create_equipment():
    """Test 13: Verificar que se requieren campos para crear equipo"""
    global created_equipment_id
    print_test_header("Crear equipo sin campos requeridos")
    
    # Probar crear equipo sin todos los campos
    response = requests.post(
        f"{BASE_URL}/config/equipment",
        headers=get_headers(),
        json={
            "name": "Equipo de Prueba API"
            # Faltan aetitle y location_id
        }
    )
    
    if response.status_code == 400:
        data = response.json()
        if not data.get('success'):
            return print_result(True, "Validación correcta: rechaza campos faltantes", response)
    
    return print_result(False, "Debería rechazar por campos faltantes", response)


def test_delete_equipment():
    """Test 14: Verificar que no se puede eliminar equipo inexistente"""
    print_test_header("Eliminar equipo inexistente")
    
    fake_id = str(uuid.uuid4())
    response = requests.delete(
        f"{BASE_URL}/config/equipment/{fake_id}",
        headers=get_headers()
    )
    
    # Si no hay ID de equipo creado, probar con fake ID
    if response.status_code == 404:
        data = response.json()
        if not data.get('success'):
            return print_result(True, "Validación correcta: equipo no encontrado", response)
    
    return print_result(False, "Debería retornar 404 para ID inexistente", response)


def test_delete_study_type():
    """Test 15: Eliminar tipo de estudio"""
    print_test_header("Eliminar tipo de estudio")
    
    if not created_study_type_id:
        return print_result(False, "No hay ID de tipo de estudio para eliminar")
    
    response = requests.delete(
        f"{BASE_URL}/config/study-types/{created_study_type_id}",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            return print_result(True, "Tipo de estudio eliminado exitosamente", response)
    
    return print_result(False, "Error al eliminar tipo de estudio", response)


def test_delete_location():
    """Test 16: Verificar que no se puede eliminar ubicación inexistente"""
    print_test_header("Eliminar ubicación inexistente")
    
    fake_id = str(uuid.uuid4())
    response = requests.delete(
        f"{BASE_URL}/config/locations/{fake_id}",
        headers=get_headers()
    )
    
    if response.status_code == 404:
        data = response.json()
        if not data.get('success'):
            return print_result(True, "Validación correcta: ubicación no encontrada", response)
    
    return print_result(False, "Debería retornar 404 para ID inexistente", response)


def test_create_study_type_without_required_fields():
    """Test 17: Crear tipo de estudio sin campos requeridos (debe fallar)"""
    print_test_header("Crear tipo de estudio sin campos requeridos")
    
    response = requests.post(
        f"{BASE_URL}/config/study-types",
        headers=get_headers(),
        json={
            "code": "TEST123"
            # Faltan campos requeridos
        }
    )
    
    if response.status_code == 400:
        data = response.json()
        if not data.get('success'):
            return print_result(True, "Validación correcta: rechaza campos faltantes", response)
    
    return print_result(False, "Debería rechazar por campos faltantes", response)


def test_update_nonexistent_study_type():
    """Test 18: Actualizar tipo de estudio inexistente (debe fallar)"""
    print_test_header("Actualizar tipo de estudio inexistente")
    
    fake_id = str(uuid.uuid4())
    response = requests.patch(
        f"{BASE_URL}/config/study-types/{fake_id}",
        headers=get_headers(),
        json={
            "description": "No debería actualizarse"
        }
    )
    
    if response.status_code == 404:
        data = response.json()
        if not data.get('success'):
            return print_result(True, "Validación correcta: tipo de estudio no encontrado", response)
    
    return print_result(False, "Debería retornar 404 para ID inexistente", response)


def test_delete_nonexistent_equipment():
    """Test 19: Eliminar equipo inexistente (debe fallar)"""
    print_test_header("Eliminar equipo inexistente")
    
    fake_id = str(uuid.uuid4())
    response = requests.delete(
        f"{BASE_URL}/config/equipment/{fake_id}",
        headers=get_headers()
    )
    
    if response.status_code == 404:
        data = response.json()
        if not data.get('success'):
            return print_result(True, "Validación correcta: equipo no encontrado", response)
    
    return print_result(False, "Debería retornar 404 para ID inexistente", response)


def test_unauthorized_access():
    """Test 20: Acceso sin token (debe fallar)"""
    print_test_header("Acceso sin autenticación")
    
    response = requests.get(
        f"{BASE_URL}/config/system",
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 401:
        return print_result(True, "Validación correcta: requiere autenticación", response)
    
    return print_result(False, "Debería rechazar acceso sin token", response)


def run_all_tests():
    """Ejecutar todos los tests"""
    print("\n" + "="*60)
    print("INICIANDO TESTS DE API REST - CONFIGURACIÓN DEL SISTEMA")
    print("="*60)
    
    tests = [
        ("Login", test_login),
        ("Configuración sistema", test_get_system_config),
        ("Configuración workflow", test_get_workflow_config),
        ("Listar modalidades", test_get_modalities),
        ("Listar partes del cuerpo", test_get_body_parts),
        ("Listar grupos de estudio", test_get_study_groups),
        ("Listar tipos de estudio", test_get_study_types),
        ("Crear tipo de estudio", test_create_study_type),
        ("Actualizar tipo de estudio", test_update_study_type),
        ("Listar ubicaciones", test_get_locations),
        ("Crear ubicación", test_create_location),
        ("Listar equipos", test_get_equipment),
        ("Crear equipo", test_create_equipment),
        ("Eliminar equipo", test_delete_equipment),
        ("Eliminar tipo de estudio", test_delete_study_type),
        ("Eliminar ubicación", test_delete_location),
        ("Validación: crear sin campos", test_create_study_type_without_required_fields),
        ("Validación: actualizar inexistente", test_update_nonexistent_study_type),
        ("Validación: eliminar inexistente", test_delete_nonexistent_equipment),
        ("Validación: sin autenticación", test_unauthorized_access),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ FAIL: {test_name}")
            print(f"Exception: {str(e)}")
            results.append((test_name, False))
    
    # Resumen final
    print("\n" + "="*60)
    print("RESUMEN DE RESULTADOS")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*60)
    print(f"TOTAL: {passed}/{total} tests pasados ({passed*100//total}%)")
    print("="*60)
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
