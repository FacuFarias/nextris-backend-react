#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Test para la API General - Endpoint de Viewer URL
"""

import requests
import json

# Configuración
API_BASE_URL = "http://localhost:5001/api"

# Datos de test
TEST_USER_ID = "9388650a-fa37-4cb1-b346-e68ef2407d1b"
TEST_EXAMINATION_ID = "5cbf5499-febd-47e9-a465-5117eb7c432d"

def test_viewer_url():
    """
    Test del endpoint de viewer URL
    """
    print("=" * 70)
    print("TEST: GET VIEWER URL")
    print("=" * 70)
    
    # 1. Login para obtener token
    print("\n1. Login...")
    login_data = {
        'username': 'sysadmin',
        'password': '1234'
    }
    
    resp = requests.post(f'{API_BASE_URL}/auth/login', json=login_data)
    
    if resp.status_code != 200:
        print(f"❌ Error en login: {resp.status_code}")
        print(resp.json())
        return
    
    token = resp.json()['data']['access_token']
    print(f"✓ Login exitoso. Token obtenido.")
    
    # 2. Obtener URL del visor
    print(f"\n2. Obteniendo URL del visor...")
    print(f"   User ID: {TEST_USER_ID}")
    print(f"   Examination ID: {TEST_EXAMINATION_ID}")
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'user_id': TEST_USER_ID,
        'examination_id': TEST_EXAMINATION_ID
    }
    
    resp = requests.post(f'{API_BASE_URL}/general/viewer-url', 
                        headers=headers, 
                        json=data)
    
    print(f"\n3. Respuesta del servidor:")
    print(f"   Status Code: {resp.status_code}")
    
    result = resp.json()
    print(f"   Response:")
    print(json.dumps(result, indent=2))
    
    if resp.status_code == 200 and result.get('success'):
        print(f"\n✓ TEST EXITOSO")
        print(f"\n📺 URL DIRECTA DEL VISOR:")
        print(f"   {result['data']['direct_url']}")
        print(f"\n🔬 Study UID:")
        print(f"   {result['data']['study_uid']}")
        viewer_url = result['data']['viewer_url']
        assert 'handoff_code=' in viewer_url
        assert 'access_token=' not in viewer_url
        assert 'access_token' not in result['data']
        print(f"\n🔑 Handoff opaco de un solo uso generado correctamente")
        print(f"\n⏱️  Expira en: {result['data']['expires_in']} segundos")
        print(f"\n💡 El frontend debe abrir viewer_url directamente; no recibe credenciales técnicas")
            
    elif resp.status_code == 403:
        print(f"\n⚠️  Sin permisos para ver esta ubicación")
    elif resp.status_code == 404:
        print(f"\n⚠️  Examen no encontrado")
    else:
        print(f"\n❌ TEST FALLIDO")
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    test_viewer_url()
