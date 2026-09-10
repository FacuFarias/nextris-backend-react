#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""
Script de prueba para los endpoints de Clínica Parque
"""

import requests
import json
import os
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


def test_create_order_without_optional_fields():
    """Crear orden sin rad_id ni priority_id: deben aplicarse sus defaults."""
    print_header("ORDEN SIN RAD_ID NI PRIORITY_ID")
    print_test("POST /clinicaparque/orders_to_execute_and_read")

    timestamp = int(datetime.now().timestamp())
    payload = {
        "patient": {
            "id": f"TEST-OPTIONAL-{timestamp}",
            "dni": "12345678",
            "name": "JUAN PEREZ TEST",
            "birthdate": "1993-09-20",
            "sex": "M",
            "patient_type": "F",
            "healthcard_type": "Particular"
        },
        "order": {
            "orderId": f"ORD-OPTIONAL-{timestamp}",
            "accessionNumber": f"ACC-OPTIONAL-{timestamp}",
            "procedure_code": "RX-01",
            "procedure_name": "Radiografía de Tórax",
            "modality": "CR",
            "AET": "PACS_SERVER",
            "scheduledTime": "2026-05-14T10:30:00Z"
        }
    }

    resp = requests.post(f"{API_URL}/clinicaparque/orders_to_execute_and_read", headers=headers(), json=payload)
    data = resp.json()
    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if resp.status_code == 200 and data.get("success"):
        print_success("Orden creada con defaults de rad_id y priority_id")
        return data
    print_error(f"Error: {data.get('message')}")
    return None


def test_create_order_with_laterality():
    """Crear orden urgente con lateralidad; requiere UUID configurado para la instalación."""
    laterality_id = os.environ.get("CLINICAPARQUE_LATERALITY_ID")
    if not laterality_id:
        print(f"{Colors.YELLOW}↷ Se omite lateralidad: definir CLINICAPARQUE_LATERALITY_ID{Colors.ENDC}")
        return True

    print_header("ORDEN CON PRIORIDAD Y LATERALIDAD")
    print_test("POST /clinicaparque/orders_to_execute_and_read")

    timestamp = int(datetime.now().timestamp())
    payload = {
        "patient": {
            "id": f"TEST-LAT-{timestamp}",
            "dni": "12345678",
            "name": "JUAN PEREZ TEST",
            "birthdate": "1993-09-20",
            "sex": "M",
            "patient_type": "F",
            "healthcard_type": "Particular"
        },
        "order": {
            "orderId": f"ORD-LAT-{timestamp}",
            "accessionNumber": f"ACC-LAT-{timestamp}",
            "procedure_code": "RX-01",
            "procedure_name": "Radiografía de Tórax",
            "modality": "CR",
            "AET": "PACS_SERVER",
            "scheduledTime": "2026-05-14T10:30:00Z",
            "priority_id": 1,
            "laterality_id": laterality_id
        }
    }

    resp = requests.post(f"{API_URL}/clinicaparque/orders_to_execute_and_read", headers=headers(), json=payload)
    data = resp.json()
    print(f"Status: {resp.status_code}")
    print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if resp.status_code == 200 and data.get("success"):
        print_success("Orden creada con prioridad urgente y lateralidad")
        return data
    print_error(f"Error: {data.get('message')}")
    return None


def test_update_existing_order_fields():
    """Verificar que una orden existente actualiza prioridad y lateralidad."""
    laterality_id = os.environ.get("CLINICAPARQUE_LATERALITY_ID")
    if not laterality_id:
        print(f"{Colors.YELLOW}↷ Se omite actualización: definir CLINICAPARQUE_LATERALITY_ID{Colors.ENDC}")
        return True

    print_header("ACTUALIZAR PRIORIDAD Y LATERALIDAD DE ORDEN EXISTENTE")
    timestamp = int(datetime.now().timestamp())
    patient = {
        "id": f"TEST-UPDATE-{timestamp}",
        "dni": "12345678",
        "name": "JUAN PEREZ TEST",
        "birthdate": "1993-09-20",
        "sex": "M",
        "patient_type": "F",
        "healthcard_type": "Particular"
    }
    order = {
        "orderId": f"ORD-UPDATE-{timestamp}",
        "accessionNumber": f"ACC-UPDATE-{timestamp}",
        "procedure_code": "RX-01",
        "procedure_name": "Radiografía de Tórax",
        "modality": "CR",
        "AET": "PACS_SERVER",
        "scheduledTime": "2026-05-14T10:30:00Z",
        "priority_id": 0
    }

    first = requests.post(
        f"{API_URL}/clinicaparque/orders_to_execute_and_read",
        headers=headers(), json={"patient": patient, "order": order}
    )
    if first.status_code != 200 or not first.json().get("success"):
        print_error(f"No se pudo crear la orden base: {first.text}")
        return False

    order.update({"priority_id": 1, "laterality_id": laterality_id})
    second = requests.post(
        f"{API_URL}/clinicaparque/orders_to_execute_and_read",
        headers=headers(), json={"patient": patient, "order": order}
    )
    data = second.json()
    if second.status_code == 200 and data.get("success") and data.get("updated"):
        print_success("Orden existente actualizada")
        return True
    print_error(f"Error al actualizar: {second.status_code} {data}")
    return False


def test_create_order_invalid_priority():
    """Rechazar una prioridad distinta de 0 o 1."""
    print_header("VALIDACIÓN - PRIORITY_ID INVÁLIDO")
    print_test("POST /clinicaparque/orders_to_execute_and_read")

    payload = {
        "patient": {"id": "TEST-PRIORITY-001", "patient_type": "T"},
        "order": {
            "orderId": "ORD-PRIORITY-001",
            "accessionNumber": "ACC-PRIORITY-001",
            "procedure_code": "RX-01",
            "procedure_name": "Test",
            "modality": "CR",
            "AET": "PACS_SERVER",
            "scheduledTime": "2026-05-14T10:30:00Z",
            "priority_id": 2
        }
    }

    resp = requests.post(f"{API_URL}/clinicaparque/orders_to_execute_and_read", headers=headers(), json=payload)
    data = resp.json()
    if resp.status_code == 400 and "priority_id" in data.get("message", ""):
        print_success("priority_id inválido rechazado")
        return True
    print_error(f"Respuesta inesperada: {resp.status_code} {data}")
    return False


def test_create_order_invalid_laterality():
    """Rechazar una lateralidad que no sea un UUID válido."""
    print_header("VALIDACIÓN - LATERALITY_ID INVÁLIDO")
    print_test("POST /clinicaparque/orders_to_execute_and_read")

    payload = {
        "patient": {"id": "TEST-LATERALITY-001", "patient_type": "T"},
        "order": {
            "orderId": "ORD-LATERALITY-001",
            "accessionNumber": "ACC-LATERALITY-001",
            "procedure_code": "RX-01",
            "procedure_name": "Test",
            "modality": "CR",
            "AET": "PACS_SERVER",
            "scheduledTime": "2026-05-14T10:30:00Z",
            "laterality_id": "not-a-uuid"
        }
    }

    resp = requests.post(f"{API_URL}/clinicaparque/orders_to_execute_and_read", headers=headers(), json=payload)
    data = resp.json()
    if resp.status_code == 400 and "laterality_id" in data.get("message", ""):
        print_success("laterality_id inválido rechazado")
        return True
    print_error(f"Respuesta inesperada: {resp.status_code} {data}")
    return False


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

    print("\n4. Crear orden sin rad_id ni priority_id")
    test_create_order_without_optional_fields()

    print("\n5. Crear orden con prioridad y lateralidad")
    test_create_order_with_laterality()

    print("\n6. Actualizar prioridad y lateralidad de orden existente")
    test_update_existing_order_fields()

    print("\n7. Validación - campos faltantes")
    test_create_order_validation()

    print("\n8. Validación - patient_type inválido")
    test_create_order_invalid_patient_type()

    print("\n9. Validación - priority_id inválido")
    test_create_order_invalid_priority()

    print("\n10. Validación - laterality_id inválido")
    test_create_order_invalid_laterality()

    print_header("FIN DE PRUEBAS")
