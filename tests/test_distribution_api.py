#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Script de prueba para los endpoints de la API de Distribución de Informes
Prueba paginación y funcionalidad de envío de reportes
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

def print_json(data, indent=2):
    print(json.dumps(data, indent=indent, ensure_ascii=False))


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
                return True
            else:
                print_error(f"Login falló: {data.get('message')}")
                return False
        else:
            print_error(f"Error HTTP {response.status_code}")
            print_info(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Exception durante login: {str(e)}")
        return False


def get_headers():
    """Obtener headers con token de autenticación"""
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }


def test_get_examinations_distribution_default():
    """Test GET /examinations/distribution sin parámetros (default)"""
    print_header("TEST 1: GET /examinations/distribution (default)")
    print_test("Obtener exámenes para distribución con parámetros por defecto")
    
    try:
        response = requests.get(
            f"{API_URL}/examinations/distribution",
            headers=get_headers()
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success("Respuesta recibida correctamente")
            
            # Verificar estructura de respuesta
            if data.get('success'):
                print_success("success: true ✓")
                
                # Verificar estructura de paginación
                if 'data' in data and isinstance(data['data'], dict):
                    pagination_data = data['data']
                    
                    # Verificar campos de paginación
                    required_fields = ['data', 'page', 'per_page', 'total']
                    for field in required_fields:
                        if field in pagination_data:
                            print_success(f"Campo '{field}' presente ✓")
                        else:
                            print_error(f"Campo '{field}' faltante ✗")
                    
                    # Verificar valores por defecto
                    if pagination_data.get('page') == 1:
                        print_success("page = 1 (default) ✓")
                    else:
                        print_error(f"page = {pagination_data.get('page')} (esperado: 1)")
                    
                    if pagination_data.get('per_page') == 50:
                        print_success("per_page = 50 (default) ✓")
                    else:
                        print_error(f"per_page = {pagination_data.get('per_page')} (esperado: 50)")
                    
                    print_info(f"Total de registros: {pagination_data.get('total')}")
                    print_info(f"Registros en esta página: {len(pagination_data.get('data', []))}")
                    
                    # Mostrar primer registro si existe
                    if pagination_data.get('data'):
                        print_info("\nPrimer registro:")
                        first_record = pagination_data['data'][0]
                        print_json(first_record)
                        
                        # Verificar campos requeridos en cada registro
                        required_exam_fields = ['guid', 'fecha', 'examen', 'paciente', 'mail', 'estado']
                        print_info("\nVerificando campos del registro:")
                        for field in required_exam_fields:
                            if field in first_record:
                                print_success(f"  ✓ {field}: {first_record[field]}")
                            else:
                                print_error(f"  ✗ {field}: FALTANTE")
                        
                        return first_record.get('guid')  # Retornar GUID para tests posteriores
                    else:
                        print_info("No hay exámenes para distribuir")
                        return None
                else:
                    print_error("Estructura de 'data' incorrecta - debe ser un objeto con paginación")
                    print_json(data)
            else:
                print_error(f"success: false - {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
            print_info(f"Response: {response.text}")
            
    except Exception as e:
        print_error(f"Exception: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return None


def test_get_examinations_distribution_with_pagination():
    """Test GET /examinations/distribution con paginación personalizada"""
    print_header("TEST 2: GET /examinations/distribution (con paginación)")
    print_test("Obtener exámenes con page=1, per_page=10")
    
    try:
        response = requests.get(
            f"{API_URL}/examinations/distribution",
            headers=get_headers(),
            params={
                'page': 1,
                'per_page': 10
            }
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success("Respuesta recibida correctamente")
            
            if data.get('success'):
                pagination_data = data['data']
                
                if pagination_data.get('page') == 1:
                    print_success("page = 1 ✓")
                else:
                    print_error(f"page = {pagination_data.get('page')} (esperado: 1)")
                
                if pagination_data.get('per_page') == 10:
                    print_success("per_page = 10 ✓")
                else:
                    print_error(f"per_page = {pagination_data.get('per_page')} (esperado: 10)")
                
                actual_count = len(pagination_data.get('data', []))
                print_info(f"Registros obtenidos: {actual_count}")
                
                if actual_count <= 10:
                    print_success(f"Cantidad de registros correcta (≤ 10) ✓")
                else:
                    print_error(f"Se obtuvieron más registros de los solicitados")
                
                print_info(f"Total en BD: {pagination_data.get('total')}")
            else:
                print_error(f"success: false - {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
            
    except Exception as e:
        print_error(f"Exception: {str(e)}")


def test_get_examinations_distribution_page_2():
    """Test GET /examinations/distribution - página 2"""
    print_header("TEST 3: GET /examinations/distribution (página 2)")
    print_test("Obtener segunda página de resultados")
    
    try:
        response = requests.get(
            f"{API_URL}/examinations/distribution",
            headers=get_headers(),
            params={
                'page': 2,
                'per_page': 10
            }
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success("Respuesta recibida correctamente")
            
            if data.get('success'):
                pagination_data = data['data']
                
                if pagination_data.get('page') == 2:
                    print_success("page = 2 ✓")
                else:
                    print_error(f"page = {pagination_data.get('page')} (esperado: 2)")
                
                print_info(f"Registros en página 2: {len(pagination_data.get('data', []))}")
                print_info(f"Total: {pagination_data.get('total')}")
            else:
                print_error(f"success: false - {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
            
    except Exception as e:
        print_error(f"Exception: {str(e)}")


def test_get_examinations_distribution_all_reported():
    """Test GET /examinations/distribution con all_reported=true"""
    print_header("TEST 4: GET /examinations/distribution (all_reported=true)")
    print_test("Obtener todos los exámenes reportados (incluye enviados)")
    
    try:
        response = requests.get(
            f"{API_URL}/examinations/distribution",
            headers=get_headers(),
            params={
                'all_reported': 'true',
                'per_page': 20
            }
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success("Respuesta recibida correctamente")
            
            if data.get('success'):
                pagination_data = data['data']
                print_info(f"Total de reportados (incluye enviados): {pagination_data.get('total')}")
                print_info(f"Registros en esta página: {len(pagination_data.get('data', []))}")
                
                # Contar estados
                examinations = pagination_data.get('data', [])
                if examinations:
                    estados = {}
                    for exam in examinations:
                        estado = exam.get('estado', 'DESCONOCIDO')
                        estados[estado] = estados.get(estado, 0) + 1
                    
                    print_info("\nDistribución de estados:")
                    for estado, count in estados.items():
                        estado_text = "Reportado (pendiente envío)" if estado == 'R' else "Enviado"
                        print_info(f"  {estado} ({estado_text}): {count}")
            else:
                print_error(f"success: false - {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
            
    except Exception as e:
        print_error(f"Exception: {str(e)}")


def test_get_examinations_distribution_only_pending():
    """Test GET /examinations/distribution con all_reported=false"""
    print_header("TEST 5: GET /examinations/distribution (all_reported=false)")
    print_test("Obtener solo exámenes pendientes de envío")
    
    try:
        response = requests.get(
            f"{API_URL}/examinations/distribution",
            headers=get_headers(),
            params={
                'all_reported': 'false',
                'per_page': 20
            }
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success("Respuesta recibida correctamente")
            
            if data.get('success'):
                pagination_data = data['data']
                print_info(f"Total de pendientes: {pagination_data.get('total')}")
                print_info(f"Registros en esta página: {len(pagination_data.get('data', []))}")
                
                # Verificar que todos sean estado 'R' (reportado, no enviado)
                examinations = pagination_data.get('data', [])
                if examinations:
                    all_pending = all(exam.get('estado') == 'R' for exam in examinations)
                    if all_pending:
                        print_success("Todos los registros están en estado 'R' (pendientes) ✓")
                    else:
                        print_error("Hay registros con estado diferente a 'R'")
                        for exam in examinations:
                            if exam.get('estado') != 'R':
                                print_info(f"  Exam {exam.get('guid')}: estado={exam.get('estado')}")
            else:
                print_error(f"success: false - {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
            
    except Exception as e:
        print_error(f"Exception: {str(e)}")


def test_update_examination_email(exam_id):
    """Test PATCH /examinations/<exam_id>/update-email"""
    print_header("TEST 6: PATCH /examinations/<exam_id>/update-email")
    
    if not exam_id:
        print_error("No hay exam_id disponible para probar")
        return
    
    print_test(f"Actualizar email del examen: {exam_id}")
    
    try:
        test_email = "test_updated@example.com"
        
        response = requests.patch(
            f"{API_URL}/examinations/{exam_id}/update-email",
            headers=get_headers(),
            json={
                "email": test_email
            }
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success("Respuesta recibida correctamente")
            
            if data.get('success'):
                print_success(f"Email actualizado: {data.get('message')}")
                print_info(f"Nuevo email: {test_email}")
            else:
                print_error(f"success: false - {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
            print_info(f"Response: {response.text}")
            
    except Exception as e:
        print_error(f"Exception: {str(e)}")


def test_send_report_email(exam_id):
    """Test POST /examinations/<exam_id>/send-report"""
    print_header("TEST 7: POST /examinations/<exam_id>/send-report")
    
    if not exam_id:
        print_error("No hay exam_id disponible para probar")
        return
    
    print_test(f"Enviar informe por email: {exam_id}")
    print_info("NOTA: Este test puede fallar si no hay configuración SMTP válida")
    print_info("o si el examen no tiene PDF generado")
    
    try:
        test_email = "test@example.com"
        
        response = requests.post(
            f"{API_URL}/examinations/{exam_id}/send-report",
            headers=get_headers(),
            json={
                "email": test_email
            }
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success("Respuesta recibida correctamente")
            
            if data.get('success'):
                print_success(f"Informe enviado: {data.get('message')}")
            else:
                print_error(f"success: false - {data.get('message')}")
        elif response.status_code == 404:
            data = response.json()
            print_info(f"Examen o PDF no encontrado: {data.get('message')}")
        elif response.status_code == 500:
            data = response.json()
            print_info(f"Error de servidor (posiblemente configuración SMTP): {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
            print_info(f"Response: {response.text}")
            
    except Exception as e:
        print_error(f"Exception: {str(e)}")


def test_max_per_page_limit():
    """Test límite máximo de per_page (100)"""
    print_header("TEST 8: Límite máximo de per_page")
    print_test("Solicitar per_page=200 (debe limitarse a 100)")
    
    try:
        response = requests.get(
            f"{API_URL}/examinations/distribution",
            headers=get_headers(),
            params={
                'per_page': 200
            }
        )
        
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('success'):
                pagination_data = data['data']
                
                if pagination_data.get('per_page') == 100:
                    print_success("per_page limitado a 100 correctamente ✓")
                else:
                    print_error(f"per_page = {pagination_data.get('per_page')} (esperado: 100)")
                
                actual_count = len(pagination_data.get('data', []))
                print_info(f"Registros obtenidos: {actual_count}")
            else:
                print_error(f"success: false - {data.get('message')}")
        else:
            print_error(f"Error HTTP {response.status_code}")
            
    except Exception as e:
        print_error(f"Exception: {str(e)}")


def run_all_tests():
    """Ejecutar todos los tests"""
    print_header("TESTS DE API DE DISTRIBUCIÓN DE INFORMES")
    print_info(f"Base URL: {BASE_URL}")
    print_info(f"API URL: {API_URL}")
    print_info(f"Usuario: {USERNAME}")
    
    # Login
    if not login():
        print_error("No se pudo autenticar. Abortando tests.")
        sys.exit(1)
    
    # Ejecutar tests
    exam_id = test_get_examinations_distribution_default()
    test_get_examinations_distribution_with_pagination()
    test_get_examinations_distribution_page_2()
    test_get_examinations_distribution_all_reported()
    test_get_examinations_distribution_only_pending()
    test_max_per_page_limit()
    
    # Tests que requieren exam_id
    if exam_id:
        test_update_examination_email(exam_id)
        test_send_report_email(exam_id)
    else:
        print_info("\nNo se encontraron exámenes para probar actualización y envío de email")
    
    # Resumen
    print_header("TESTS COMPLETADOS")
    print_success("Todos los tests de estructura de respuesta han sido ejecutados")
    print_info("Revisa los resultados arriba para verificar el comportamiento")


if __name__ == "__main__":
    run_all_tests()
