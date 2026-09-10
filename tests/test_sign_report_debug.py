#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de diagnóstico para firma de reportes
Prueba paso a paso el proceso de firma de un reporte médico
"""

import requests
import json
import sys
import psycopg2
from datetime import datetime

# Configuración
BASE_URL = "http://localhost:5001/api"
TEST_USER_EMAIL = "sysadmin"
TEST_USER_PASSWORD = "1234"

# Configuración de base de datos
DB_CONFIG = {
    'host': 'localhost',
    'database': 'pacsdb',
    'user': 'pacs',
    'password': 'pacs'
}

token = None


def print_header(title):
    """Imprime encabezado"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_step(step, message):
    """Imprime paso del test"""
    print(f"\n[PASO {step}] {message}")


def print_success(message):
    """Imprime mensaje de éxito"""
    print(f"  ✓ {message}")


def print_error(message):
    """Imprime mensaje de error"""
    print(f"  ✗ {message}")


def print_info(message):
    """Imprime información"""
    print(f"  ℹ {message}")


def login():
    """Login y obtención de token"""
    global token
    print_step(1, "Autenticación")
    
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
            print_success(f"Login exitoso, token obtenido")
            return True
    
    print_error(f"Error en login: {response.status_code}")
    print(f"Response: {response.text}")
    return False


def get_headers():
    """Retorna headers con token"""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def find_examination_with_report():
    """Busca un examen que tenga reporte para firmar"""
    print_step(2, "Buscando examen con reporte para firmar")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Buscar un examen que tenga reporte y no esté firmado
        query = """
            SELECT e.guid, e.localacc, p.name, p.surname, e.isreported
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient p ON e.idpatient = p.guid
            LEFT JOIN nextris.tbreport r ON r.idexamination = e.guid
            WHERE r.guid IS NOT NULL
            ORDER BY e.createdon DESC
            LIMIT 5
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        if not results:
            print_error("No se encontraron exámenes con reportes en la base de datos")
            return None
        
        print_info(f"Se encontraron {len(results)} exámenes con reportes:")
        for i, (guid, acc, name, surname, is_reported) in enumerate(results, 1):
            status = "FIRMADO" if is_reported else "SIN FIRMAR"
            print(f"    {i}. ACC: {acc}, Paciente: {surname or ''} {name or ''}, Estado: {status}")
            print(f"       GUID: {guid}")
        
        # Tomar el primero
        exam_id = results[0][0]
        print_success(f"Usando examen: {exam_id}")
        return exam_id
        
    except Exception as e:
        print_error(f"Error al buscar examen: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def check_report_exists(exam_id):
    """Verifica que el reporte exista en la base de datos"""
    print_step(3, "Verificando existencia del reporte en la base de datos")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        query = """
            SELECT r.guid, r.findings, r.techniques, r.impressions, r.conclusions,
                   r.idpatient, r.idexamination, r.iduser
            FROM nextris.tbreport r
            WHERE r.idexamination = %s
        """
        
        cursor.execute(query, (exam_id,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not result:
            print_error("El reporte NO existe en la base de datos")
            return False
        
        print_success("El reporte existe en la base de datos")
        print_info(f"Report GUID: {result[0]}")
        print_info(f"Findings: {result[1][:50] if result[1] else 'NULL'}...")
        print_info(f"Techniques: {result[2][:50] if result[2] else 'NULL'}...")
        print_info(f"Impressions: {result[3][:50] if result[3] else 'NULL'}...")
        print_info(f"Conclusions: {result[4][:50] if result[4] else 'NULL'}...")
        print_info(f"Patient ID: {result[5]}")
        print_info(f"User ID: {result[7]}")
        print_info("PDF: se genera bajo demanda")
        
        return True
        
    except Exception as e:
        print_error(f"Error al verificar reporte: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def check_examination_data(exam_id):
    """Verifica los datos del examen"""
    print_step(4, "Verificando datos del examen")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        query = """
            SELECT e.guid, e.localacc, e.idpatient, e.studytype_id, e.isreported,
                   p.patientid, p.name, p.surname, p.guid as patient_guid,
                   st.description
            FROM nextris.tbexamination e
            LEFT JOIN nextris.datapatient p ON e.idpatient = p.guid
            LEFT JOIN nextris.isstudytype st ON e.studytype_id = st.guid
            WHERE e.guid = %s
        """
        
        cursor.execute(query, (exam_id,))
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not result:
            print_error("El examen NO existe")
            return False
        
        print_success("Datos del examen encontrados")
        print_info(f"Exam GUID: {result[0]}")
        print_info(f"Accession Number: {result[1]}")
        print_info(f"Patient ID (FK): {result[2]}")
        print_info(f"Patient ID (Table): {result[5]}")
        print_info(f"Patient Name: {result[7]} {result[6]}")
        print_info(f"Patient GUID: {result[8]}")
        print_info(f"Study Type: {result[9]}")
        print_info(f"Is Reported: {result[4]}")
        
        # Verificar que el JOIN es correcto
        if result[2] == result[8]:
            print_success("✓ El JOIN entre examen y paciente es correcto (e.idpatient = p.guid)")
        else:
            print_error(f"✗ JOIN INCORRECTO: e.idpatient ({result[2]}) != p.guid ({result[8]})")
        
        return True
        
    except Exception as e:
        print_error(f"Error al verificar examen: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_sign_report_api(exam_id):
    """Prueba el endpoint de firma de reporte"""
    print_step(5, "Llamando al endpoint de firma de reporte")
    
    url = f"{BASE_URL}/reports/{exam_id}/sign"
    print_info(f"URL: {url}")
    
    try:
        response = requests.post(
            url,
            headers=get_headers(),
            json={}
        )
        
        print_info(f"Status Code: {response.status_code}")
        print_info(f"Response Headers: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print_info(f"Response JSON:")
            print(json.dumps(response_data, indent=2, ensure_ascii=False))
        except:
            print_info(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            print_success("Reporte firmado exitosamente")
            return True
        else:
            print_error(f"Error al firmar reporte: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Excepción al llamar API: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_pdf_generated(exam_id):
    """Verifica que el PDF se haya generado"""
    print_step(6, "Verificando generación del PDF")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.close()
        conn.close()
        from run import app
        from apps.services.report_pdf_service import render_report_pdf
        with app.app_context():
            rendered = render_report_pdf(exam_id)
        if rendered.content.startswith(b'%PDF'):
            print_success("PDF renderizado correctamente en memoria")
            print_info(f"Tamaño: {len(rendered.content)} bytes")
            return True
        else:
            print_error("✗ El renderizador no devolvió un PDF válido")
            return False
        
    except Exception as e:
        print_error(f"Error al verificar PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def check_server_logs():
    """Intenta capturar logs del servidor"""
    print_step(7, "Revisando logs del servidor")
    
    import subprocess
    
    try:
        # Buscar proceso de gunicorn
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )
        
        gunicorn_processes = [line for line in result.stdout.split('\n') if 'gunicorn' in line and '5001' in line]
        
        if gunicorn_processes:
            print_info(f"Procesos Gunicorn encontrados: {len(gunicorn_processes)}")
            for proc in gunicorn_processes[:2]:
                print(f"    {proc}")
        else:
            print_error("No se encontraron procesos de Gunicorn en puerto 5001")
        
    except Exception as e:
        print_error(f"Error al revisar procesos: {str(e)}")


def run_diagnostic():
    """Ejecuta diagnóstico completo"""
    print_header("DIAGNÓSTICO DE FIRMA DE REPORTES")
    
    # Paso 1: Login
    if not login():
        print_error("ABORTADO: No se pudo autenticar")
        return False
    
    # Paso 2: Encontrar examen
    exam_id = find_examination_with_report()
    if not exam_id:
        print_error("ABORTADO: No se encontró examen para probar")
        return False
    
    # Paso 3: Verificar reporte
    if not check_report_exists(exam_id):
        print_error("ABORTADO: El reporte no existe")
        return False
    
    # Paso 4: Verificar examen
    if not check_examination_data(exam_id):
        print_error("ABORTADO: El examen no existe o tiene datos incorrectos")
        return False
    
    # Paso 5: Firmar reporte
    sign_success = test_sign_report_api(exam_id)
    
    # Paso 6: Verificar PDF
    if sign_success:
        verify_pdf_generated(exam_id)
    
    # Paso 7: Revisar logs
    check_server_logs()
    
    print_header("FIN DEL DIAGNÓSTICO")
    
    if sign_success:
        print_success("✓ El test de firma fue exitoso")
        return True
    else:
        print_error("✗ El test de firma falló")
        return False


if __name__ == "__main__":
    success = run_diagnostic()
    sys.exit(0 if success else 1)
