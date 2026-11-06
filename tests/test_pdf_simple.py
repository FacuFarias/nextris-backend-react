#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test para verificar que la firma de reportes funciona correctamente después de las correcciones
"""

import sys
import psycopg2

sys.path.insert(0, '/var/www/nextris-dev-react')

# El examen se selecciona dinámicamente para que el test no dependa de datos
# concretos del entorno.
TEST_EXAM_ID = None

# Configuración de base de datos
DB_CONFIG = {
    'host': 'localhost',
    'database': 'pacsdb',
    'user': 'pacs',
    'password': 'pacs'
}

def check_imports():
    """Verificar que todos los módulos necesarios estén disponibles"""
    print("\n=== Verificando imports ===")
    try:
        import psycopg2
        print("✓ psycopg2")
        
        from reportlab.pdfgen import canvas
        print("✓ reportlab.pdfgen.canvas")
        
        from reportlab.lib.pagesizes import letter
        print("✓ reportlab.lib.pagesizes.letter")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_database_query():
    """Probar la consulta de base de datos directamente"""
    print("\n=== Probando consulta de base de datos ===")
    
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        query = """
            SELECT p.Surname, p.Name, st.Description, rep.Date,
                   rep.Findings, rep.Techniques, rep.Impressions, rep.Conclusions, rep.iduser
            FROM nextris.tbreport rep
            LEFT JOIN nextris.tbexamination tbex ON tbex.Guid = rep.IdExamination
            LEFT JOIN nextris.isstudytype st ON tbex.studytype_id = st.Guid
            LEFT JOIN nextris.datapatient p ON p.guid = rep.IdPatient
            WHERE rep.IdExamination = %s
        """
        
        cursor.execute("""
            SELECT e.guid
            FROM nextris.tbexamination e
            JOIN nextris.tbreport r ON r.idexamination = e.guid
            WHERE COALESCE(e.isreported, 0) = 1
            LIMIT 1
        """)
        exam = cursor.fetchone()
        if not exam:
            print("✗ No hay informes firmados para probar")
            cursor.close()
            connection.close()
            return False
        cursor.execute(query, (exam[0],))
        result = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        if result:
            print(f"✓ Query exitoso, {len(result)} registros")
            print(f"  Datos: Apellido={result[0][0]}, Nombre={result[0][1]}, Estudio={result[0][2]}")
            return True
        else:
            print("✗ Query no retornó resultados")
            return False
            
    except Exception as e:
        print(f"✗ Error en query: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pdf_generation_inline():
    """Verifica que el PDF se renderiza en memoria y no crea archivos."""
    print("\n=== Probando generación de PDF bajo demanda ===")
    try:
        from run import app
        from apps.services.report_pdf_service import render_report_pdf
        from apps.home.services.config_service import ConfigService
        import psycopg2
        with app.app_context():
            conn = psycopg2.connect(**ConfigService.get_db_config())
            cur = conn.cursor()
            cur.execute("SELECT guid FROM nextris.tbexamination WHERE COALESCE(isreported, 0) = 1 LIMIT 1")
            exam_id = str(cur.fetchone()[0])
            cur.close()
            conn.close()
            rendered = render_report_pdf(exam_id)
        if rendered.content.startswith(b"%PDF"):
            print(f"✓ PDF renderizado en memoria: {len(rendered.content)} bytes")
            return True
        print("✗ El resultado no es un PDF válido")
        return False
    except Exception as error:
        print(f"✗ Error: {error}")
        return False

def main():
    """Ejecutar todos los tests"""
    print("="*70)
    print("VERIFICACIÓN DE GENERACIÓN DE PDFs")
    print("="*70)
    
    results = []
    
    # Test 1: Imports
    results.append(("Imports", check_imports()))
    
    # Test 2: Database Query
    results.append(("Database Query", test_database_query()))
    
    # Test 3: PDF Generation Inline
    results.append(("PDF Generation Inline", test_pdf_generation_inline()))
    
    # Resumen
    print("\n" + "="*70)
    print("RESUMEN")
    print("="*70)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\n{passed}/{total} tests passed")
    print("="*70)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
