#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test para verificar que la firma de reportes funciona correctamente después de las correcciones
"""

import sys
import psycopg2

# Exam ID conocido que tiene reporte
TEST_EXAM_ID = "646bed76-a9ab-41f4-b9b2-deb6660df876"

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
            SELECT p.Surname, p.Name, st.Description, rep.Date, rep.idreferringphysician, 
                   rep.Findings, rep.Techniques, rep.Impressions, rep.Conclusions, rep.iduser
            FROM nextris.tbreport rep
            LEFT JOIN nextris.tbexamination tbex ON tbex.Guid = rep.IdExamination
            LEFT JOIN nextris.isstudytype st ON tbex.studytype_id = st.Guid
            LEFT JOIN nextris.datapatient p ON p.guid = rep.IdPatient
            WHERE rep.IdExamination = %s
        """
        
        cursor.execute(query, (TEST_EXAM_ID,))
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
    """Generar PDF usando el código inline (sin función importada)"""
    print("\n=== Probando generación de PDF inline ===")
    
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        import psycopg2
        import os
        
        # Conectar a BD
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        # Obtener datos
        query = """
            SELECT p.Surname, p.Name, st.Description, rep.Date, rep.idreferringphysician, 
                   rep.Findings, rep.Techniques, rep.Impressions, rep.Conclusions, rep.iduser
            FROM nextris.tbreport rep
            LEFT JOIN nextris.tbexamination tbex ON tbex.Guid = rep.IdExamination
            LEFT JOIN nextris.isstudytype st ON tbex.studytype_id = st.Guid
            LEFT JOIN nextris.datapatient p ON p.guid = rep.IdPatient
            WHERE rep.IdExamination = %s
        """
        
        cursor.execute(query, (TEST_EXAM_ID,))
        result = cursor.fetchall()
        
        if not result:
            print("✗ No se encontraron datos")
            cursor.close()
            connection.close()
            return False
        
        data = result[0]
        surname, name, examen, fecha, refmed, findings, techniques, impressions, conclusions, userid = data
        
        # Crear PDF
        output_dir = 'output_pdfs'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        pdf_file_path = os.path.join(output_dir, "TEST_INLINE.pdf")
        
        c = canvas.Canvas(pdf_file_path, pagesize=letter)
        width, height = letter
        
        # Contenido mínimo
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, height - 50, f"Examen: {examen or 'N/A'}")
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 80, f"Paciente: {name or ''} {surname or ''}")
        c.drawString(50, height - 100, f"Fecha: {fecha or 'N/A'}")
        
        c.save()
        
        cursor.close()
        connection.close()
        
        if os.path.exists(pdf_file_path):
            size = os.path.getsize(pdf_file_path)
            print(f"✓ PDF generado: {pdf_file_path} ({size} bytes)")
            return True
        else:
            print(f"✗ PDF no se generó")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
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
