#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Script de prueba para los endpoints de la API de Templates (Plantillas)
Prueba los 6 endpoints de gestión de plantillas de informes predefinidos
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
STUDY_TYPE_ID = None  # Se obtiene dinámicamente
TEMPLATE_ID = None  # ID de plantilla creada durante los tests

# Colores para la consola
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[96m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.ENDC}\n")

def print_test(test_name):
    print(f"\n{Colors.YELLOW}[TEST]{Colors.ENDC} {Colors.BOLD}{test_name}{Colors.ENDC}")

def print_success(message):
    print(f"{Colors.GREEN}✓ {message}{Colors.ENDC}")

def print_error(message):
    print(f"{Colors.RED}✗ {message}{Colors.ENDC}")

def print_info(message):
    print(f"{Colors.CYAN}ℹ {message}{Colors.ENDC}")

def print_data(label, value):
    print(f"  {Colors.BOLD}{label}:{Colors.ENDC} {value}")


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
            print_error(f"Response: {response.text}")
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


def get_study_type_id():
    """Obtener un study_type_id válido de la base de datos"""
    global STUDY_TYPE_ID
    try:
        response = requests.get(
            f"{API_URL}/study-types",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            # El endpoint retorna arrays, no objetos
            # [guid, code, description, modality_code, bodypart, studygroup, modality_id]
            if data.get('success') and len(data['data']) > 0:
                first_study_type = data['data'][0]
                STUDY_TYPE_ID = first_study_type[0]  # guid está en índice 0
                description = first_study_type[2] if len(first_study_type) > 2 else 'N/A'
                print_info(f"Usando Study Type: {description} ({STUDY_TYPE_ID[:8]}...)")
                return True
        
        print_error("No se pudo obtener study_type_id")
        return False
        
    except Exception as e:
        print_error(f"Error obteniendo study_type_id: {str(e)}")
        return False


# ===========================
# TESTS DE TEMPLATES API
# ===========================

def test_get_templates():
    """Test: GET /api/templates - Listar todas las plantillas"""
    print_test("GET /api/templates - Listar todas las plantillas")
    
    try:
        response = requests.get(
            f"{API_URL}/templates",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                templates = data.get('data', [])
                print_success(f"Se obtuvieron {len(templates)} plantillas")
                
                if templates:
                    print_info("Primeras 3 plantillas:")
                    for i, template in enumerate(templates[:3]):
                        print(f"  {i+1}. {template.get('title')} - {template.get('study_type_description')}")
                
                return True
            else:
                print_error(f"API retornó success=false: {data}")
                return False
        else:
            print_error(f"Error HTTP {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
        return False


def test_get_templates_filtered():
    """Test: GET /api/templates?study_type_id=X - Filtrar por tipo de estudio"""
    print_test(f"GET /api/templates?study_type_id - Filtrar plantillas")
    
    if not STUDY_TYPE_ID:
        print_error("No hay STUDY_TYPE_ID para filtrar")
        return False
    
    try:
        response = requests.get(
            f"{API_URL}/templates",
            headers=get_headers(),
            params={"study_type_id": STUDY_TYPE_ID}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                templates = data.get('data', [])
                print_success(f"Se obtuvieron {len(templates)} plantillas filtradas")
                
                if templates:
                    print_info(f"Plantillas del tipo de estudio {STUDY_TYPE_ID[:8]}...:")
                    for i, template in enumerate(templates[:5]):
                        print(f"  {i+1}. {template.get('title')}")
                
                return True
            else:
                print_error(f"API retornó success=false: {data}")
                return False
        else:
            print_error(f"Error HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
        return False


def test_create_template():
    """Test: POST /api/templates - Crear nueva plantilla"""
    global TEMPLATE_ID
    print_test("POST /api/templates - Crear nueva plantilla")
    
    if not STUDY_TYPE_ID:
        print_error("No hay STUDY_TYPE_ID para crear plantilla")
        return False
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_template = {
            "title": f"Plantilla de Prueba {timestamp}",
            "study_type_id": STUDY_TYPE_ID,
            "findings": "Hallazgos de prueba:\n- Ejemplo 1\n- Ejemplo 2",
            "technique": "Técnica de prueba utilizada para el examen",
            "impression": "Impresión diagnóstica de prueba",
            "conclusion": "Conclusión de prueba",
            "is_default": False
        }
        
        print_info(f"Creando plantilla: {new_template['title']}")
        
        response = requests.post(
            f"{API_URL}/templates",
            headers=get_headers(),
            json=new_template
        )
        
        if response.status_code == 201:
            data = response.json()
            if data.get('success'):
                TEMPLATE_ID = data['data']['guid']
                print_success(f"Plantilla creada exitosamente")
                print_data("GUID", TEMPLATE_ID)
                print_data("Mensaje", data['data']['message'])
                return True
            else:
                print_error(f"API retornó success=false: {data}")
                return False
        else:
            print_error(f"Error HTTP {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
        return False


def test_get_template():
    """Test: GET /api/templates/<template_id> - Obtener plantilla específica"""
    print_test("GET /api/templates/<template_id> - Obtener plantilla específica")
    
    if not TEMPLATE_ID:
        print_error("No hay TEMPLATE_ID para obtener")
        return False
    
    try:
        response = requests.get(
            f"{API_URL}/templates/{TEMPLATE_ID}",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                template = data['data']
                print_success(f"Plantilla obtenida exitosamente")
                print_data("Título", template.get('title'))
                print_data("Study Type ID", template.get('study_type_id'))
                print_data("Findings (primeros 50 chars)", template.get('findings', '')[:50] + "...")
                print_data("Technique (primeros 50 chars)", template.get('technique', '')[:50] + "...")
                return True
            else:
                print_error(f"API retornó success=false: {data}")
                return False
        else:
            print_error(f"Error HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
        return False


def test_select_template():
    """Test: POST /api/templates/select/<template_id> - Seleccionar plantilla"""
    print_test("POST /api/templates/select/<template_id> - Seleccionar plantilla")
    
    if not TEMPLATE_ID:
        print_error("No hay TEMPLATE_ID para seleccionar")
        return False
    
    try:
        response = requests.post(
            f"{API_URL}/templates/select/{TEMPLATE_ID}",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                template = data['data']
                print_success(f"Plantilla seleccionada exitosamente")
                print_info("Datos listos para aplicar al formulario:")
                print_data("  Título", template.get('title'))
                print_data("  Findings", f"{len(template.get('findings', ''))} caracteres")
                print_data("  Technique", f"{len(template.get('technique', ''))} caracteres")
                print_data("  Impression", f"{len(template.get('impression', ''))} caracteres")
                print_data("  Conclusion", f"{len(template.get('conclusion', ''))} caracteres")
                return True
            else:
                print_error(f"API retornó success=false: {data}")
                return False
        else:
            print_error(f"Error HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
        return False


def test_edit_template():
    """Test: PUT /api/templates/<template_id> - Editar plantilla"""
    print_test("PUT /api/templates/<template_id> - Editar plantilla")
    
    if not TEMPLATE_ID:
        print_error("No hay TEMPLATE_ID para editar")
        return False
    
    try:
        updated_template = {
            "title": f"Plantilla EDITADA {datetime.now().strftime('%H:%M:%S')}",
            "study_type_id": STUDY_TYPE_ID,
            "findings": "Hallazgos ACTUALIZADOS:\n- Cambio 1\n- Cambio 2\n- Cambio 3",
            "technique": "Técnica ACTUALIZADA para el examen",
            "impression": "Impresión diagnóstica ACTUALIZADA",
            "conclusion": "Conclusión ACTUALIZADA"
        }
        
        print_info(f"Editando plantilla a: {updated_template['title']}")
        
        response = requests.put(
            f"{API_URL}/templates/{TEMPLATE_ID}",
            headers=get_headers(),
            json=updated_template
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print_success(f"Plantilla editada exitosamente")
                print_data("GUID", data['data']['guid'])
                print_data("Mensaje", data['data']['message'])
                return True
            else:
                print_error(f"API retornó success=false: {data}")
                return False
        else:
            print_error(f"Error HTTP {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
        return False


def test_delete_template():
    """Test: DELETE /api/templates/<template_id> - Eliminar plantilla"""
    print_test("DELETE /api/templates/<template_id> - Eliminar plantilla")
    
    if not TEMPLATE_ID:
        print_error("No hay TEMPLATE_ID para eliminar")
        return False
    
    try:
        print_info(f"Eliminando plantilla {TEMPLATE_ID[:8]}...")
        
        response = requests.delete(
            f"{API_URL}/templates/{TEMPLATE_ID}",
            headers=get_headers()
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print_success(f"Plantilla eliminada exitosamente")
                print_data("Mensaje", data['data']['message'])
                return True
            else:
                print_error(f"API retornó success=false: {data}")
                return False
        else:
            print_error(f"Error HTTP {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
        return False


def test_get_nonexistent_template():
    """Test: GET /api/templates/<invalid_id> - Intentar obtener plantilla inexistente"""
    print_test("GET /api/templates/<invalid_id> - Plantilla inexistente")
    
    try:
        fake_id = "00000000-0000-0000-0000-000000000000"
        
        response = requests.get(
            f"{API_URL}/templates/{fake_id}",
            headers=get_headers()
        )
        
        if response.status_code == 404:
            data = response.json()
            if not data.get('success'):
                print_success(f"Error 404 manejado correctamente")
                print_data("Error", data.get('error'))
                return True
            else:
                print_error(f"Debería retornar success=false")
                return False
        else:
            print_error(f"Se esperaba HTTP 404, obtuvo {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
        return False


def test_create_template_without_title():
    """Test: POST /api/templates sin título - Validación de campos requeridos"""
    print_test("POST /api/templates sin título - Validación")
    
    try:
        invalid_template = {
            "study_type_id": STUDY_TYPE_ID,
            "findings": "Hallazgos sin título"
        }
        
        response = requests.post(
            f"{API_URL}/templates",
            headers=get_headers(),
            json=invalid_template
        )
        
        if response.status_code == 400:
            data = response.json()
            if not data.get('success'):
                print_success(f"Validación de título funcionó correctamente")
                print_data("Error", data.get('error'))
                return True
            else:
                print_error(f"Debería retornar success=false")
                return False
        else:
            print_error(f"Se esperaba HTTP 400, obtuvo {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Excepción: {str(e)}")
        return False


# ===========================
# FUNCIÓN PRINCIPAL
# ===========================

def run_all_tests():
    """Ejecutar todos los tests en secuencia"""
    print_header("TEST API DE TEMPLATES (PLANTILLAS)")
    print(f"Base URL: {BASE_URL}")
    print(f"API URL: {API_URL}")
    print(f"Usuario: {USERNAME}")
    
    # Autenticación
    if not login():
        print_error("No se pudo autenticar. Tests abortados.")
        sys.exit(1)
    
    # Obtener study type
    if not get_study_type_id():
        print_error("No se pudo obtener study_type_id. Tests abortados.")
        sys.exit(1)
    
    # Contador de tests
    total_tests = 0
    passed_tests = 0
    
    # Lista de tests a ejecutar
    tests = [
        ("Listar Plantillas", test_get_templates),
        ("Filtrar Plantillas por Tipo", test_get_templates_filtered),
        ("Crear Plantilla", test_create_template),
        ("Obtener Plantilla Específica", test_get_template),
        ("Seleccionar Plantilla", test_select_template),
        ("Editar Plantilla", test_edit_template),
        ("Eliminar Plantilla", test_delete_template),
        ("Plantilla Inexistente (404)", test_get_nonexistent_template),
        ("Validación sin Título (400)", test_create_template_without_title),
    ]
    
    # Ejecutar tests
    print_header("EJECUTANDO TESTS")
    
    for test_name, test_func in tests:
        total_tests += 1
        try:
            if test_func():
                passed_tests += 1
        except Exception as e:
            print_error(f"Test falló con excepción: {str(e)}")
    
    # Resumen
    print_header("RESUMEN DE TESTS")
    print(f"Total de tests: {total_tests}")
    print(f"{Colors.GREEN}Tests exitosos: {passed_tests}{Colors.ENDC}")
    print(f"{Colors.RED}Tests fallidos: {total_tests - passed_tests}{Colors.ENDC}")
    
    if passed_tests == total_tests:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ TODOS LOS TESTS PASARON{Colors.ENDC}\n")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}✗ ALGUNOS TESTS FALLARON{Colors.ENDC}\n")
    
    return passed_tests == total_tests


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Tests interrumpidos por el usuario{Colors.ENDC}\n")
        sys.exit(1)
