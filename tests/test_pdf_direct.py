#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test directo de la función generate_report_pdf_with_signature
Sin pasar por el API REST
"""

import sys

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
        from apps.services.report_pdf_service import render_report_pdf
        print("  ✓ Función importada correctamente")
    except Exception as e:
        print(f"  ✗ Error al importar: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    from run import app
    from apps.home.services.config_service import ConfigService
    import psycopg2
    with app.app_context():
        conn = psycopg2.connect(**ConfigService.get_db_config())
        cur = conn.cursor()
        cur.execute("SELECT guid FROM nextris.tbexamination WHERE COALESCE(isreported, 0) = 1 LIMIT 1")
        exam_id = str(cur.fetchone()[0])
        cur.close()
        conn.close()
    print(f"\n[2] Generando PDF para examen: {exam_id}")
    
    try:
        with app.app_context():
            result = render_report_pdf(exam_id)
        
        print(f"\n[3] Resultado de la función:")
        print(f"    Valor retornado: {type(result).__name__}")
        print(f"    Tipo de contenido: {type(result.content).__name__}")
        
        if result:
            print(f"\n[4] Verificando bytes...")
            if result.content.startswith(b'%PDF'):
                print(f"  ✓ PDF válido: {result.filename}")
                print(f"  ✓ Tamaño: {len(result.content)} bytes")
                return True
            else:
                print("  ✗ Los bytes no contienen un PDF válido")
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
