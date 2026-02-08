#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test directo de la función generate_report_pdf_with_signature
Sin pasar por el API REST
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, '/var/www/nextris-dev-react')

def test_direct_pdf_generation():
    """Prueba directa de generación de PDF"""
    
    print("="*70)
    print("  TEST DIRECTO DE GENERACIÓN DE PDF")
    print("="*70)
    
    # Importar la función
    print("\n[1] Importando función...")
    try:
        from apps.home.controllers.report_controller import generate_report_pdf_with_signature
        print("  ✓ Función importada correctamente")
    except Exception as e:
        print(f"  ✗ Error al importar: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ID del examen de prueba
    exam_id = "646bed76-a9ab-41f4-b9b2-deb6660df876"
    pdf_filename = "TEST_MANUAL.pdf"
    
    print(f"\n[2] Generando PDF para examen: {exam_id}")
    print(f"    Nombre de archivo: {pdf_filename}")
    
    try:
        result = generate_report_pdf_with_signature(exam_id, pdf_filename=pdf_filename)
        
        print(f"\n[3] Resultado de la función:")
        print(f"    Valor retornado: {result}")
        print(f"    Tipo: {type(result)}")
        
        if result:
            print(f"\n[4] Verificando archivo...")
            if os.path.exists(result):
                size = os.path.getsize(result)
                print(f"  ✓ Archivo existe: {result}")
                print(f"  ✓ Tamaño: {size} bytes")
                return True
            else:
                print(f"  ✗ El archivo NO existe: {result}")
                return False
        else:
            print("\n  ✗ La función retornó None")
            return False
            
    except Exception as e:
        print(f"\n  ✗ Error durante la generación: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_direct_pdf_generation()
    
    print("\n" + "="*70)
    if success:
        print("  ✓ TEST EXITOSO")
    else:
        print("  ✗ TEST FALLIDO")
    print("="*70)
    
    sys.exit(0 if success else 1)
