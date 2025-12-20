#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test específico para verificar el filtrado de equipos por location_id
Verifica que el endpoint GET /config/equipment REQUIERE location_id
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


def print_warning(message):
    """Imprime advertencia"""
    print(f"⚠️  {message}")


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


def test_equipment_without_location():
    """Test: Verificar que rechaza peticiones sin location_id"""
    print_test("2. Test: GET /config/equipment SIN location_id (debe fallar)")
    
    response = requests.get(
        f"{BASE_URL}/config/equipment",
        headers=get_headers()
    )
    
    if response.status_code == 400:
        data = response.json()
        if not data.get('success') and 'location_id' in data.get('message', '').lower():
            print_success("CORRECTO: Rechazó la petición sin location_id")
            print_info(f"Mensaje: {data.get('message')}")
            return True
        else:
            print_error("Devolvió 400 pero con mensaje incorrecto")
            print(json.dumps(data, indent=2))
            return False
    else:
        print_error(f"INCORRECTO: No rechazó la petición (HTTP {response.status_code})")
        print_error("El endpoint DEBE requerir location_id obligatoriamente")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
        return False


def test_equipment_with_location():
    """Test: Verificar que funciona con location_id válido"""
    print_test("3. Test: GET /config/equipment CON location_id válido")
    
    # Primero obtener una location válida
    print_info("Obteniendo ubicaciones disponibles...")
    response = requests.get(
        f"{BASE_URL}/institutional/locations",
        headers=get_headers()
    )
    
    if response.status_code != 200:
        print_error("No se pudieron obtener ubicaciones")
        return False
    
    locations_data = response.json()
    if not locations_data.get('success') or not locations_data.get('data'):
        print_error("No hay ubicaciones disponibles en el sistema")
        return False
    
    location_id = locations_data['data'][0]['guid']
    location_name = locations_data['data'][0].get('name', 'N/A')
    print_info(f"Usando location: {location_name} ({location_id})")
    
    # Ahora probar con location_id
    response = requests.get(
        f"{BASE_URL}/config/equipment?location_id={location_id}",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and isinstance(data.get('data'), list):
            equipment_count = len(data['data'])
            print_success(f"Equipos encontrados: {equipment_count}")
            
            if equipment_count > 0:
                print_info("Primeros 3 equipos:")
                for i, equip in enumerate(data['data'][:3]):
                    print(f"   {i+1}. {equip.get('description', 'N/A')} (AE: {equip.get('aeTitle', 'N/A')})")
            else:
                print_info("No hay equipos asignados a esta ubicación (esto puede ser normal)")
            
            return True
        else:
            print_error("Respuesta no tiene el formato esperado")
            print(json.dumps(data, indent=2))
            return False
    else:
        print_error(f"Error al obtener equipos: {response.status_code}")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
        return False


def test_equipment_with_invalid_location():
    """Test: Verificar comportamiento con location_id inválido"""
    print_test("4. Test: GET /config/equipment con location_id inválido")
    
    fake_location_id = "00000000-0000-0000-0000-000000000000"
    
    response = requests.get(
        f"{BASE_URL}/config/equipment?location_id={fake_location_id}",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and isinstance(data.get('data'), list):
            equipment_count = len(data['data'])
            if equipment_count == 0:
                print_success("Devolvió lista vacía para location_id inválido (correcto)")
            else:
                print_warning(f"Devolvió {equipment_count} equipos para location_id inexistente")
            return True
        else:
            print_error("Respuesta no tiene el formato esperado")
            return False
    else:
        print_info(f"Devolvió error {response.status_code} para location_id inválido")
        return True


def main():
    """Ejecutar todos los tests"""
    print_header("TEST: Filtrado de Equipos por Location ID")
    
    tests = [
        ("Login", login),
        ("Sin location_id", test_equipment_without_location),
        ("Con location_id válido", test_equipment_with_location),
        ("Con location_id inválido", test_equipment_with_invalid_location)
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
