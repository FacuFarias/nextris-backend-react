#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Tests para API de Autenticación - auth.py
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json

# Configuración
BASE_URL = "http://127.0.0.1:5001/api"
USERNAME_STAFF = "sysadmin"
PASSWORD_STAFF = "1234"

# Variables globales para tokens
access_token = None
refresh_token = None


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


# ==================== TESTS ====================

def test_01_login_staff():
    """Test 1: Login con credenciales de staff"""
    global access_token, refresh_token
    
    print_test_header(1, "POST /auth/login - Login staff")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "username": USERNAME_STAFF,
                "password": PASSWORD_STAFF,
                "user_type": "staff"
            },
            headers={"Content-Type": "application/json"}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            access_token = data['data']['access_token']
            refresh_token = data['data']['refresh_token']
            
            # Verificar estructura de respuesta
            assert 'access_token' in data['data'], "Falta access_token"
            assert 'refresh_token' in data['data'], "Falta refresh_token"
            assert 'user' in data['data'], "Falta información de usuario"
            # Permitir diferentes tipos de usuario staff
            user_type = data['data']['user']['user_type']
            assert user_type in ['staff', 'Sysadmin', 'Medico', 'Technician', 'Admin'], f"Tipo de usuario inesperado: {user_type}"
            
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_02_login_invalid_credentials():
    """Test 2: Login con credenciales inválidas"""
    print_test_header(2, "POST /auth/login - Credenciales inválidas")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "username": "usuario_invalido",
                "password": "password_invalido",
                "user_type": "staff"
            },
            headers={"Content-Type": "application/json"}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Debe fallar con 401
        if response.status_code == 401 and not data.get('success'):
            return print_result(True)
        else:
            return print_result(False, "Debería retornar 401 Unauthorized")
            
    except Exception as e:
        return print_result(False, str(e))


def test_03_login_missing_fields():
    """Test 3: Login sin campos requeridos"""
    print_test_header(3, "POST /auth/login - Campos faltantes")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "username": "test"
                # Falta password
            },
            headers={"Content-Type": "application/json"}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Debe fallar con 400
        if response.status_code == 400 and not data.get('success'):
            return print_result(True)
        else:
            return print_result(False, "Debería retornar 400 Bad Request")
            
    except Exception as e:
        return print_result(False, str(e))


def test_04_login_no_json_body():
    """Test 4: Login sin cuerpo JSON"""
    print_test_header(4, "POST /auth/login - Sin cuerpo JSON")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        # Puede fallar con 400 o 500 dependiendo de cómo Flask maneje el error
        if response.status_code in [400, 500]:
            try:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
                if not data.get('success'):
                    return print_result(True)
            except:
                # Si no puede parsear JSON, también está bien
                return print_result(True)
        
        return print_result(False, "Debería retornar 400 o 500 Bad Request")
            
    except Exception as e:
        return print_result(False, str(e))


def test_05_get_current_user():
    """Test 5: Obtener información del usuario actual"""
    print_test_header(5, "GET /auth/me - Usuario actual")
    
    if not access_token:
        return print_result(False, "No hay access_token disponible")
    
    try:
        response = requests.get(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            # Verificar estructura
            assert 'data' in data, "Falta campo data"
            assert 'username' in data['data'], "Falta username"
            assert 'user_type' in data['data'], "Falta user_type"
            
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_06_get_current_user_no_token():
    """Test 6: Obtener usuario actual sin token"""
    print_test_header(6, "GET /auth/me - Sin token de autorización")
    
    try:
        response = requests.get(
            f"{BASE_URL}/auth/me"
        )
        
        print(f"Status Code: {response.status_code}")
        
        # Debe fallar con 401
        if response.status_code == 401:
            return print_result(True)
        else:
            return print_result(False, "Debería retornar 401 Unauthorized")
            
    except Exception as e:
        return print_result(False, str(e))


def test_07_get_current_user_invalid_token():
    """Test 7: Obtener usuario actual con token inválido"""
    print_test_header(7, "GET /auth/me - Token inválido")
    
    try:
        response = requests.get(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": "Bearer token_invalido_12345"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        # Debe fallar con 401 o 422
        if response.status_code in [401, 422]:
            return print_result(True)
        else:
            return print_result(False, f"Debería retornar 401/422, retornó {response.status_code}")
            
    except Exception as e:
        return print_result(False, str(e))


def test_08_refresh_token():
    """Test 8: Refrescar access token"""
    global access_token
    
    print_test_header(8, "POST /auth/refresh - Refrescar token")
    
    if not refresh_token:
        return print_result(False, "No hay refresh_token disponible")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            # Actualizar access token
            new_access_token = data['data']['access_token']
            
            # Verificar que el nuevo token es diferente
            if new_access_token != access_token:
                access_token = new_access_token
                return print_result(True)
            else:
                return print_result(False, "El nuevo token es igual al anterior")
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def test_09_refresh_with_access_token():
    """Test 9: Intentar refrescar con access token (debe fallar)"""
    print_test_header(9, "POST /auth/refresh - Con access token (debe fallar)")
    
    if not access_token:
        return print_result(False, "No hay access_token disponible")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/refresh",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        # Debe fallar con 401 o 422 (token type mismatch)
        if response.status_code in [401, 422]:
            return print_result(True)
        else:
            return print_result(False, f"Debería fallar, retornó {response.status_code}")
            
    except Exception as e:
        return print_result(False, str(e))


def test_10_logout():
    """Test 10: Logout"""
    print_test_header(10, "POST /auth/logout - Cerrar sesión")
    
    if not access_token:
        return print_result(False, "No hay access_token disponible")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
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


def test_11_logout_no_token():
    """Test 11: Logout sin token"""
    print_test_header(11, "POST /auth/logout - Sin token")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/logout"
        )
        
        print(f"Status Code: {response.status_code}")
        
        # Debe fallar con 401
        if response.status_code == 401:
            return print_result(True)
        else:
            return print_result(False, f"Debería retornar 401, retornó {response.status_code}")
            
    except Exception as e:
        return print_result(False, str(e))


def test_12_use_token_after_logout():
    """Test 12: Verificar que el token aún funciona después de logout (JWT stateless)"""
    print_test_header(12, "GET /auth/me - Token después de logout")
    
    if not access_token:
        return print_result(False, "No hay access_token disponible")
    
    try:
        response = requests.get(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # En JWT stateless, el token sigue siendo válido
        # El frontend debe manejarlo eliminándolo del localStorage
        if response.status_code == 200 and data.get('success'):
            print("ℹ️  Nota: JWT stateless - el token sigue válido, frontend debe eliminarlo")
            return print_result(True)
        else:
            return print_result(False, "El token debería seguir siendo válido (JWT stateless)")
            
    except Exception as e:
        return print_result(False, str(e))


# ==================== EJECUTOR DE TESTS ====================

def test_13_get_user_patientdomains():
    """Test 13: Obtener patientdomains de un usuario"""
    global access_token
    
    print_test_header(13, "GET /auth/user/:user_id/patientdomains")
    
    try:
        # Primero obtener el user_id del usuario actual
        response = requests.get(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        if response.status_code != 200:
            return print_result(False, "No se pudo obtener información del usuario actual")
        
        user_data = response.json()
        user_id = user_data['data']['id']
        
        # Obtener patientdomains del usuario
        response = requests.get(
            f"{BASE_URL}/auth/user/{user_id}/patientdomains",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        data = response.json()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if response.status_code == 200 and data.get('success'):
            # Verificar estructura
            assert 'data' in data, "Falta campo 'data'"
            assert isinstance(data['data'], list), "data debe ser una lista"
            
            if len(data['data']) > 0:
                pd = data['data'][0]
                assert 'patientdomain_id' in pd, "Falta patientdomain_id"
                assert 'patientdomain_name' in pd, "Falta patientdomain_name"
                print(f"✓ Usuario tiene {len(data['data'])} patientdomain(s)")
            else:
                print(f"✓ Usuario sin patientdomains asignados")
            
            return print_result(True)
        else:
            return print_result(False, data.get('message', 'Error desconocido'))
            
    except Exception as e:
        return print_result(False, str(e))


def run_all_tests():
    """Ejecuta todos los tests en orden"""
    
    print("\n" + "="*70)
    print("  SUITE DE TESTS - API DE AUTENTICACIÓN")
    print("="*70)
    print(f"URL Base: {BASE_URL}")
    print(f"Usuario: {USERNAME_STAFF}")
    
    tests = [
        test_01_login_staff,
        test_02_login_invalid_credentials,
        test_03_login_missing_fields,
        test_04_login_no_json_body,
        test_05_get_current_user,
        test_06_get_current_user_no_token,
        test_07_get_current_user_invalid_token,
        test_08_refresh_token,
        test_09_refresh_with_access_token,
        test_10_logout,
        test_11_logout_no_token,
        test_12_use_token_after_logout,
        test_13_get_user_patientdomains,
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
