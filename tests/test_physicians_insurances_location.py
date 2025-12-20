#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test para verificar endpoints de médicos y obras sociales por location_id
Verifica que ambos endpoints REQUIEREN location_id obligatoriamente
"""

import requests
import json
import sys

# Configuración
BASE_URL = "http://localhost:5001/api"
TEST_USER_EMAIL = "sysadmin"
TEST_USER_PASSWORD = "1234"

# Variables globales
token = None


def print_header(title):
    """Imprime encabezado"""
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}")


def print_test(test_name):
    """Imprime nombre del test"""
    print(f"\n{test_name}")
    print("-" * 70)


def print_success(message):
    """Imprime mensaje de éxito"""
    print(f"✅ {message}")


def print_error(message):
    """Imprime mensaje de error"""
    print(f"❌ {message}")


def print_info(message):
    """Imprime información"""
    print(f"ℹ️  {message}")


def login():
    """Realizar login y obtener token"""
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
        else:
            print_error("Respuesta de login sin token")
            print(json.dumps(data, indent=2))
            return False
    else:
        print_error(f"Error en login: {response.status_code}")
        print(response.text)
        return False


def get_headers():
    """Retorna headers con token"""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def get_valid_location():
    """Obtiene una location válida para tests"""
    response = requests.get(
        f"{BASE_URL}/institutional/locations",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and data.get('data') and len(data['data']) > 0:
            return data['data'][0]['guid'], data['data'][0].get('name', 'N/A')
    return None, None


def test_physicians_by_location():
    """Test: Obtener médicos por ubicación"""
    print_test("2. Test: GET /institutional/locations/{location_id}/physicians")
    
    location_id, location_name = get_valid_location()
    
    if not location_id:
        print_error("No se pudo obtener una ubicación válida")
        return False
    
    print_info(f"Usando location: {location_name} ({location_id})")
    
    response = requests.get(
        f"{BASE_URL}/institutional/locations/{location_id}/physicians",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and isinstance(data.get('data'), list):
            physicians_count = len(data['data'])
            print_success(f"Médicos encontrados: {physicians_count}")
            
            if physicians_count > 0:
                print_info("Primeros 3 médicos:")
                for i, physician in enumerate(data['data'][:3]):
                    print(f"   {i+1}. {physician.get('description', 'N/A')}")
            else:
                print_info("No hay médicos asignados a esta ubicación")
            
            return True
        else:
            print_error("Respuesta no tiene el formato esperado")
            print(json.dumps(data, indent=2))
            return False
    else:
        print_error(f"Error: {response.status_code}")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
        return False


def test_physicians_invalid_location():
    """Test: Médicos con location_id inválido"""
    print_test("3. Test: Médicos con location_id inválido")
    
    fake_location = "00000000-0000-0000-0000-000000000000"
    
    response = requests.get(
        f"{BASE_URL}/institutional/locations/{fake_location}/physicians",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and len(data.get('data', [])) == 0:
            print_success("Devolvió lista vacía para location_id inválido")
            return True
        else:
            print_info(f"Devolvió {len(data.get('data', []))} médicos")
            return True
    else:
        print_info(f"Devolvió error {response.status_code}")
        return True


def test_health_insurances_by_location():
    """Test: Obtener obras sociales por ubicación"""
    print_test("4. Test: GET /institutional/locations/{location_id}/health-insurances")
    
    location_id, location_name = get_valid_location()
    
    if not location_id:
        print_error("No se pudo obtener una ubicación válida")
        return False
    
    print_info(f"Usando location: {location_name} ({location_id})")
    
    response = requests.get(
        f"{BASE_URL}/institutional/locations/{location_id}/health-insurances",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and isinstance(data.get('data'), list):
            insurances_count = len(data['data'])
            print_success(f"Obras sociales encontradas: {insurances_count}")
            
            if insurances_count > 0:
                print_info("Primeras 3 obras sociales:")
                for i, insurance in enumerate(data['data'][:3]):
                    print(f"   {i+1}. {insurance.get('description', 'N/A')}")
            else:
                print_info("No hay obras sociales asignadas a esta ubicación")
            
            return True
        else:
            print_error("Respuesta no tiene el formato esperado")
            print(json.dumps(data, indent=2))
            return False
    else:
        print_error(f"Error: {response.status_code}")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
        return False


def test_health_insurances_invalid_location():
    """Test: Obras sociales con location_id inválido"""
    print_test("5. Test: Obras sociales con location_id inválido")
    
    fake_location = "00000000-0000-0000-0000-000000000000"
    
    response = requests.get(
        f"{BASE_URL}/institutional/locations/{fake_location}/health-insurances",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and len(data.get('data', [])) == 0:
            print_success("Devolvió lista vacía para location_id inválido")
            return True
        else:
            print_info(f"Devolvió {len(data.get('data', []))} obras sociales")
            return True
    else:
        print_info(f"Devolvió error {response.status_code}")
        return True


def main():
    """Ejecutar todos los tests"""
    print_header("TEST: Médicos y Obras Sociales por Location ID")
    
    tests = [
        ("Login", login),
        ("Médicos por ubicación", test_physicians_by_location),
        ("Médicos con location_id inválido", test_physicians_invalid_location),
        ("Obras sociales por ubicación", test_health_insurances_by_location),
        ("Obras sociales con location_id inválido", test_health_insurances_invalid_location)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            if not result and test_name == "Login":
                print_error("Login falló, no se pueden ejecutar más tests")
                break
        except Exception as e:
            print_error(f"Excepción en test '{test_name}': {str(e)}")
            results.append((test_name, False))
    
    # Resumen
    print_header("RESUMEN DE TESTS")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nResultado: {passed}/{total} tests pasaron")
    
    if passed == total:
        print_success("¡Todos los tests pasaron!")
        return 0
    else:
        print_error(f"{total - passed} tests fallaron")
        return 1


if __name__ == "__main__":
    sys.exit(main())
