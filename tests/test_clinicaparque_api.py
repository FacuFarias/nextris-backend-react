#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Script de prueba para los endpoints de Clínica Parque
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://148.230.72.8:5001"
API_URL = f"{BASE_URL}/api"

CLINICAPARQUE_TOKEN = "Xr9rB5e7GqL2nq8hFJv0W8E9y7Hq3zTjYzP2n8oKp1s="

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

def print_test(name):
    print(f"{Colors.YELLOW}[TEST]{Colors.ENDC} {name}")

def print_success(msg):
    print(f"{Colors.GREEN}✓ {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.RED}✗ {msg}{Colors.ENDC}")

def headers():
    return {"Authorization": f"Bearer {CLINICAPARQUE_TOKEN}", "Content-Type": "application/json"}


def test_create_patient_final():
    """Crear paciente Final (F)"""
    print_header("CREAR PACIENTE FINAL")
    print_test("POST /clinicaparque/patients")

    payload = {
        "patient": {
            "id": f"TEST-F-{int(datetime.now().timestamp())}",
            "dni": "12345678",
            "name": "JUAN PEREZ TEST",
            "birthdate": "1993-09-20",
            "sex": "M",
            "patient_type": "F",
            "healthcard_type": "Particular"
        }
    }

    resp = requests.post(f"{API_URL}/clinicaparque/patients", headers=headers(), json=payload)
    data = resp.json()

    if resp.status_code == 200 and data.get("success"):
        print_success(f"Paciente creado: {data.get('patientid')}")
        return data.get("patientid")
    else:
        print_error(f"Error: {data.get('message')} (HTTP {resp.status_code})")
        return None


def test_create_order_to_execute_and_read(patient_id=None):
    """Crear orden para ejecutar y leer"""
    print_header("CREAR ORDEN PARA EJECUTAR Y LEER")
    print_test("POST /clinicaparque/orders_to_execute_and_read")

    if not patient_id:
        patient_id = f"TEST-F-{int(datetime.now().timestamp())}"

    payload = {
        "patient": {
            "id": patient_id,
            "dni": "12345678",
            "name": "JUAN PEREZ TEST",
            "birthdate": "1993-09-20",
            "sex": "M",
            "patient_type": "F",
            "healthcard_type": "Particular"
        },
        "order": {
            "orderId": f"ORD-TEST-{int(datetime.now().timestamp())}",
            "accessionNumber": f"ACC-TEST-{int(datetime.now().timestamp())}",
            "procedure_code": "RX-01",
            "procedure_name": "Radiografía de Tórax",
            "modality": "CR",
            "AET": "PACS_SERVER",
            "scheduledTime": "2026-05-14T10:30:00Z",
            "rad_id": "sysadmin",
            "priority_id": 1,
            "study_reason": "Dolor torácico",
            "req_doctor": "Dr. Juan García"
        }
    }

    resp = requests.post(f"{API_URL}/clinicaparque/orders_to_execute_and_read", headers=headers(), json=payload)
    data = resp.json()

    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if resp.status_code == 200 and data.get("success"):
        print_success(f"Orden creada: {data.get('accession_number')}")
        return data
    else:
        print_error(f"Error: {data.get('message')}")
        return None


def test_create_order_patient_temporal():
    """Crear orden con paciente Temporal (T)"""
    print_header("CREAR ORDEN CON PACIENTE TEMPORAL")
    print_test("POST /clinicaparque/orders_to_execute_and_read (T)")

    patient_id = f"TEST-T-{int(datetime.now().timestamp())}"

    payload = {
        "patient": {
            "id": patient_id,
            "patient_type": "T"
        },
        "order": {
            "orderId": f"ORD-TEST-T-{int(datetime.now().timestamp())}",
            "accessionNumber": f"ACC-TEST-T-{int(datetime.now().timestamp())}",
            "procedure_code": "RX-01",
            "procedure_name": "Radiografía de Tórax",
            "modality": "CR",
            "AET": "PACS_SERVER",
            "scheduledTime": "2026-05-14T10:30:00Z",
            "rad_id": "sysadmin",
            "priority_id": 1
        }
    }

    resp = requests.post(f"{API_URL}/clinicaparque/orders_to_execute_and_read", headers=headers(), json=payload)
    data = resp.json()

    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if resp.status_code == 200 and data.get("success"):
        print_success(f"Orden creada con paciente Temporal: {data.get('accession_number')}")
        return data
    else:
        print_error(f"Error: {data.get('message')}")
        return None


def test_create_order_validation():
    """Probar validación de campos requeridos"""
    print_header("VALIDACIÓN - CAMPOS FALTANTES")
    print_test("POST /clinicaparque/orders_to_execute_and_read")

    payload = {
        "patient": {
            "id": "TEST-VAL-001"
        },
        "order": {
            "orderId": "ORD-VAL-001",
            "accessionNumber": "ACC-VAL-001"
        }
    }

    resp = requests.post(f"{API_URL}/clinicaparque/orders_to_execute_and_read", headers=headers(), json=payload)
    data = resp.json()

    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if resp.status_code == 400 and not data.get("success"):
        print_success(f"Validación funciona: {data.get('message')}")
        return True
    else:
        print_error("La validación debería haber fallado")
        return False


def test_create_order_invalid_patient_type():
    """Probar patient_type inválido"""
    print_header("VALIDACIÓN - PATIENT_TYPE INVÁLIDO")
    print_test("POST /clinicaparque/orders_to_execute_and_read")

    payload = {
        "patient": {
            "id": "TEST-INVAL-001",
            "patient_type": "X"
        },
        "order": {
            "orderId": "ORD-INVAL-001",
            "accessionNumber": "ACC-INVAL-001",
            "procedure_code": "RX-01",
            "procedure_name": "Test",
            "modality": "CR",
            "AET": "PACS_SERVER",
            "scheduledTime": "2026-05-14T10:30:00Z",
            "rad_id": "sysadmin",
            "priority_id": 0
        }
    }

    resp = requests.post(f"{API_URL}/clinicaparque/orders_to_execute_and_read", headers=headers(), json=payload)
    data = resp.json()

    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if resp.status_code == 400 and not data.get("success"):
        print_success(f"Validación funciona: patient_type inválido rechazado")
        return True
    else:
        print_error("patient_type inválido debería ser rechazado")
        return False


if __name__ == "__main__":
    print_header("PRUEBAS API CLINICAPARQUE")
    print(f"Base URL: {BASE_URL}")
    print(f"Token: {CLINICAPARQUE_TOKEN[:10]}...")

    print("\n1. Crear paciente Final")
    pid = test_create_patient_final()

    print("\n2. Crear orden para ejecutar y leer (con paciente Final)")
    test_create_order_to_execute_and_read(pid)

    print("\n3. Crear orden para ejecutar y leer (con paciente Temporal)")
    test_create_order_patient_temporal()

    print("\n4. Validación - campos faltantes")
    test_create_order_validation()

    print("\n5. Validación - patient_type inválido")
    test_create_order_invalid_patient_type()

    print_header("FIN DE PRUEBAS")
