#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Tests para API Institucional - institutional.py
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from io import BytesIO
from PIL import Image

# Configuración
BASE_URL = "http://127.0.0.1:5001/api"
USERNAME = "sysadmin"
PASSWORD = "1234"

# Variables globales
access_token = None
institutional_guid = None


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
        "Authorization": f"Bearer {access_token}"
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


def create_test_image():
    """Crea una imagen PNG de prueba en memoria"""
    img = Image.new('RGB', (200, 200), color='blue')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes


# ==================== TESTS ====================

def test_01_get_institutional_info():
    """Test 1: Obtener información institucional"""
    global institutional_guid
    
    print_test_header(1, "GET /institutional/info - Obtener información")
    
    try:
        response = requests.get(
            f"{BASE_URL}/institutional/info",
            headers=get_headers()
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            if data.get('data'):
                institutional_guid = data['data'].get('guid')
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_02_update_institutional_info_basic():
    """Test 2: Actualizar información institucional (sin logo)"""
    print_test_header(2, "POST /institutional/info - Actualizar sin logo")
    
    try:
        data = {
            'name': 'Centro Médico NextRIS Test',
            'mail': 'test@nextris.com',
            'address': 'Calle Test 123',
            'phone': '+54 11 1234-5678'
        }
        
        response = requests.post(
            f"{BASE_URL}/institutional/info",
            headers=get_headers(),
            data=data
        )
        
        result = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and result.get('success'):
            return print_result(True)
        else:
            return print_result(False, result.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_03_update_institutional_info_with_logo():
    """Test 3: Actualizar información institucional con logo"""
    print_test_header(3, "POST /institutional/info - Actualizar con logo")
    
    try:
        # Crear imagen de prueba
        test_image = create_test_image()
        
        data = {
            'name': 'Centro Médico NextRIS',
            'mail': 'contacto@nextris.com',
            'address': 'Av. Principal 456',
            'phone': '+54 11 4567-8901'
        }
        
        files = {
            'logo': ('logo_test.png', test_image, 'image/png')
        }
        
        response = requests.post(
            f"{BASE_URL}/institutional/info",
            headers=get_headers(),
            data=data,
            files=files
        )
        
        result = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and result.get('success'):
            assert 'logo_path' in result.get('data', {}), "Falta logo_path en respuesta"
            return print_result(True)
        else:
            return print_result(False, result.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_04_update_institutional_info_missing_name():
    """Test 4: Actualizar sin campo requerido (name)"""
    print_test_header(4, "POST /institutional/info - Sin nombre")
    
    try:
        data = {
            'mail': 'test@nextris.com',
            'address': 'Calle Test 123'
        }
        
        response = requests.post(
            f"{BASE_URL}/institutional/info",
            headers=get_headers(),
            data=data
        )
        
        result = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        # Debe retornar 400
        if response.status_code == 400:
            return print_result(True)
        else:
            return print_result(False, f"Debería retornar 400, retornó {response.status_code}")
            
    except Exception as e:
        return print_result(False, str(e))


def test_05_verify_info_updated():
    """Test 5: Verificar que la información se actualizó correctamente"""
    print_test_header(5, "GET /institutional/info - Verificar actualización")
    
    try:
        response = requests.get(
            f"{BASE_URL}/institutional/info",
            headers=get_headers()
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            info = data.get('data')
            if info:
                assert info['name'] == 'Centro Médico NextRIS', "El nombre no coincide"
                assert info['mail'] == 'contacto@nextris.com', "El mail no coincide"
                assert 'logo_path' in info, "Falta logo_path"
                return print_result(True)
            else:
                return print_result(False, "No hay datos en la respuesta")
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_06_update_with_put_method():
    """Test 6: Actualizar usando método PUT"""
    print_test_header(6, "PUT /institutional/info - Actualizar con PUT")
    
    try:
        data = {
            'name': 'Centro Médico NextRIS Updated',
            'mail': 'info@nextris.com',
            'address': 'Nueva Dirección 789',
            'phone': '+54 11 9999-8888'
        }
        
        response = requests.put(
            f"{BASE_URL}/institutional/info",
            headers=get_headers(),
            data=data
        )
        
        result = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and result.get('success'):
            return print_result(True)
        else:
            return print_result(False, result.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_07_unauthorized_access_get():
    """Test 7: Acceso sin token (GET)"""
    print_test_header(7, "GET /institutional/info - Sin autorización")
    
    try:
        response = requests.get(f"{BASE_URL}/institutional/info")
        
        print(f"Status Code: {response.status_code}")
        
        # Debe retornar 401
        if response.status_code == 401:
            return print_result(True)
        else:
            return print_result(False, f"Debería retornar 401, retornó {response.status_code}")
            
    except Exception as e:
        return print_result(False, str(e))


def test_08_unauthorized_access_post():
    """Test 8: Acceso sin token (POST)"""
    print_test_header(8, "POST /institutional/info - Sin autorización")
    
    try:
        data = {
            'name': 'Test sin auth',
            'mail': 'test@test.com'
        }
        
        response = requests.post(
            f"{BASE_URL}/institutional/info",
            data=data
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
    print("  SUITE DE TESTS - API INSTITUCIONAL")
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
        test_01_get_institutional_info,
        test_02_update_institutional_info_basic,
        test_03_update_institutional_info_with_logo,
        test_04_update_institutional_info_missing_name,
        test_05_verify_info_updated,
        test_06_update_with_put_method,
        test_07_unauthorized_access_get,
        test_08_unauthorized_access_post,
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
