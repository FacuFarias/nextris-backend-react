#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests para API REST de Reportes Médicos
Tests completos para endpoints de plantillas, predefinidos y reportes
"""

import requests
import json
import sys
import uuid
from datetime import datetime

# Configuración
BASE_URL = "http://localhost:5001/api"
TEST_USER_EMAIL = "sysadmin"
TEST_USER_PASSWORD = "1234"

# Variables globales para tests
token = None
created_predef_id = None
test_exam_id = None
test_study_type_id = None


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
            print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        except:
            print(f"Response: {response.text}")
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


def test_get_predefined_reports():
    """Test 2: Obtener lista de reportes predefinidos"""
    print_test_header("Obtener lista de reportes predefinidos")
    
    response = requests.get(
        f"{BASE_URL}/predefined-reports",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and isinstance(data.get('data'), list):
            return print_result(True, f"Lista obtenida: {len(data['data'])} reportes predefinidos", response)
    
    return print_result(False, "Error al obtener lista de predefinidos", response)


def test_create_predefined_report():
    """Test 3: Crear nuevo reporte predefinido"""
    global created_predef_id, test_study_type_id
    print_test_header("Crear nuevo reporte predefinido")
    
    # Primero obtenemos un tipo de estudio válido
    response = requests.get(
        f"{BASE_URL}/study-types",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        result = response.json()
        study_types = result.get('data', result) if isinstance(result, dict) else result
        if study_types and len(study_types) > 0:
            # Puede ser array de objetos o array de arrays
            first_item = study_types[0]
            test_study_type_id = first_item[0] if isinstance(first_item, list) else first_item['guid']
        else:
            return print_result(False, "No hay tipos de estudio disponibles")
    else:
        return print_result(False, "Error al obtener tipos de estudio")
    
    # Crear el predefinido
    response = requests.post(
        f"{BASE_URL}/predefined-reports",
        headers=get_headers(),
        json={
            "title": f"Test Predefinido {datetime.now().isoformat()}",
            "study_type_id": test_study_type_id,
            "findings": "Hallazgos de prueba",
            "technique": "Técnica de prueba",
            "impression": "Impresión de prueba",
            "conclusion": "Conclusión de prueba"
        }
    )
    
    if response.status_code == 201:
        data = response.json()
        if data.get('success') and 'predef_id' in data.get('data', {}):
            created_predef_id = data['data']['predef_id']
            return print_result(True, f"Reporte predefinido creado: {created_predef_id}", response)
    
    return print_result(False, "Error al crear reporte predefinido", response)


def test_get_predefined_report_by_id():
    """Test 4: Obtener reporte predefinido por ID"""
    print_test_header("Obtener reporte predefinido específico")
    
    if not created_predef_id:
        return print_result(False, "No hay ID de predefinido para probar")
    
    response = requests.get(
        f"{BASE_URL}/predefined-reports/{created_predef_id}",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and data.get('data'):
            predef = data['data']
            if predef.get('guid') == created_predef_id:
                return print_result(True, "Reporte predefinido obtenido correctamente", response)
    
    return print_result(False, "Error al obtener reporte predefinido", response)


def test_update_predefined_report():
    """Test 5: Actualizar reporte predefinido"""
    print_test_header("Actualizar reporte predefinido")
    
    if not created_predef_id:
        return print_result(False, "No hay ID de predefinido para probar")
    
    response = requests.patch(
        f"{BASE_URL}/predefined-reports/{created_predef_id}",
        headers=get_headers(),
        json={
            "findings": "Hallazgos actualizados",
            "impression": "Impresión actualizada"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            return print_result(True, "Reporte predefinido actualizado exitosamente", response)
    
    return print_result(False, "Error al actualizar reporte predefinido", response)


def test_get_default_template_for_study_type():
    """Test 6: Obtener plantilla predefinida por defecto para tipo de estudio"""
    print_test_header("Obtener plantilla por defecto para tipo de estudio")
    
    if not test_study_type_id:
        return print_result(False, "No hay ID de tipo de estudio para probar")
    
    response = requests.get(
        f"{BASE_URL}/study-types/{test_study_type_id}/default-template",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and 'default_template_id' in data.get('data', {}):
            return print_result(True, "Plantilla por defecto obtenida", response)
    
    return print_result(False, "Error al obtener plantilla por defecto", response)


def test_save_report():
    """Test 7: Guardar datos de un reporte"""
    global test_exam_id
    print_test_header("Guardar datos de reporte")
    
    # Primero obtenemos un examen existente
    response = requests.get(
        f"{BASE_URL}/examinations",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        result = response.json()
        exams = result.get('data', result) if isinstance(result, dict) else result
        if exams and len(exams) > 0:
            # Puede ser array de objetos o array de arrays
            first_item = exams[0]
            test_exam_id = first_item[0] if isinstance(first_item, list) else first_item['guid']
        else:
            return print_result(False, "No hay exámenes disponibles para probar")
    else:
        return print_result(False, "Error al obtener exámenes")
    
    # Guardar el reporte
    response = requests.patch(
        f"{BASE_URL}/reports/{test_exam_id}",
        headers=get_headers(),
        json={
            "findings": "Hallazgos del reporte de prueba",
            "techniques": "Técnicas aplicadas",
            "impressions": "Impresiones diagnósticas",
            "conclusions": "Conclusiones finales"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            return print_result(True, "Reporte guardado exitosamente", response)
    
    return print_result(False, "Error al guardar reporte", response)


def test_sign_report():
    """Test 8: Firmar un reporte"""
    print_test_header("Firmar reporte")
    
    if not test_exam_id:
        return print_result(False, "No hay ID de examen para probar")
    
    response = requests.post(
        f"{BASE_URL}/reports/{test_exam_id}/sign",
        headers=get_headers(),
        json={}
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            return print_result(True, "Reporte firmado exitosamente", response)
    
    return print_result(False, "Error al firmar reporte", response)


def test_unsign_report():
    """Test 9: Quitar firma de un reporte"""
    print_test_header("Quitar firma de reporte")
    
    if not test_exam_id:
        return print_result(False, "No hay ID de examen para probar")
    
    response = requests.post(
        f"{BASE_URL}/reports/{test_exam_id}/unsign",
        headers=get_headers(),
        json={}
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            return print_result(True, "Firma removida exitosamente", response)
    
    return print_result(False, "Error al remover firma", response)


def test_get_report_pdf():
    """Test 10: Obtener PDF de reporte"""
    print_test_header("Obtener PDF de reporte")
    
    if not test_exam_id:
        return print_result(False, "No hay ID de examen para probar")
    
    response = requests.get(
        f"{BASE_URL}/reports/{test_exam_id}/pdf",
        headers=get_headers()
    )
    
    # El PDF puede no existir, eso es OK
    if response.status_code == 200:
        if response.headers.get('Content-Type') == 'application/pdf':
            return print_result(True, "PDF obtenido exitosamente", response)
    elif response.status_code == 404:
        return print_result(True, "PDF no disponible (esperado si no se generó)", response)
    
    return print_result(False, "Error al obtener PDF", response)


def test_create_predefined_without_required_fields():
    """Test 11: Crear predefinido sin campos requeridos (debe fallar)"""
    print_test_header("Crear predefinido sin campos requeridos")
    
    response = requests.post(
        f"{BASE_URL}/predefined-reports",
        headers=get_headers(),
        json={
            "findings": "Solo hallazgos"
        }
    )
    
    if response.status_code == 400:
        data = response.json()
        if not data.get('success'):
            return print_result(True, "Validación correcta: rechaza campos faltantes", response)
    
    return print_result(False, "Debería rechazar por campos faltantes", response)


def test_update_nonexistent_predefined():
    """Test 12: Actualizar predefinido inexistente (debe fallar)"""
    print_test_header("Actualizar predefinido inexistente")
    
    fake_id = str(uuid.uuid4())
    response = requests.patch(
        f"{BASE_URL}/predefined-reports/{fake_id}",
        headers=get_headers(),
        json={
            "title": "No debería actualizarse"
        }
    )
    
    if response.status_code == 404:
        data = response.json()
        if not data.get('success'):
            return print_result(True, "Validación correcta: predefinido no encontrado", response)
    
    return print_result(False, "Debería retornar 404 para ID inexistente", response)


def test_save_report_without_required_fields():
    """Test 13: Guardar reporte sin campos requeridos (debe fallar)"""
    print_test_header("Guardar reporte sin campos requeridos")
    
    if not test_exam_id:
        return print_result(False, "No hay ID de examen para probar")
    
    response = requests.patch(
        f"{BASE_URL}/reports/{test_exam_id}",
        headers=get_headers(),
        json={
            "findings": "Solo hallazgos"
            # Faltan techniques, impressions, conclusions
        }
    )
    
    if response.status_code == 400:
        data = response.json()
        if not data.get('success'):
            return print_result(True, "Validación correcta: rechaza campos faltantes", response)
    
    return print_result(False, "Debería rechazar por campos faltantes", response)


def test_get_nonexistent_predefined():
    """Test 14: Obtener predefinido inexistente (debe fallar)"""
    print_test_header("Obtener predefinido inexistente")
    
    fake_id = str(uuid.uuid4())
    response = requests.get(
        f"{BASE_URL}/predefined-reports/{fake_id}",
        headers=get_headers()
    )
    
    if response.status_code == 404:
        data = response.json()
        if not data.get('success'):
            return print_result(True, "Validación correcta: predefinido no encontrado", response)
    
    return print_result(False, "Debería retornar 404 para ID inexistente", response)


def test_unauthorized_access():
    """Test 15: Acceso sin token (debe fallar)"""
    print_test_header("Acceso sin autenticación")
    
    response = requests.get(
        f"{BASE_URL}/predefined-reports",
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 401:
        return print_result(True, "Validación correcta: requiere autenticación", response)
    
    return print_result(False, "Debería rechazar acceso sin token", response)


def run_all_tests():
    """Ejecutar todos los tests"""
    print("\n" + "="*60)
    print("INICIANDO TESTS DE API REST - REPORTES MÉDICOS")
    print("="*60)
    
    tests = [
        ("Login", test_login),
        ("Listar predefinidos", test_get_predefined_reports),
        ("Crear predefinido", test_create_predefined_report),
        ("Obtener predefinido", test_get_predefined_report_by_id),
        ("Actualizar predefinido", test_update_predefined_report),
        ("Plantilla por defecto", test_get_default_template_for_study_type),
        ("Guardar reporte", test_save_report),
        ("Firmar reporte", test_sign_report),
        ("Quitar firma", test_unsign_report),
        ("Obtener PDF", test_get_report_pdf),
        ("Validación: crear sin campos", test_create_predefined_without_required_fields),
        ("Validación: actualizar inexistente", test_update_nonexistent_predefined),
        ("Validación: guardar sin campos", test_save_report_without_required_fields),
        ("Validación: obtener inexistente", test_get_nonexistent_predefined),
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
