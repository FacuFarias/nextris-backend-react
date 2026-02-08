#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para crear informe predefinido de Ecografía de Cuello
"""

import psycopg2
import uuid

# Configuración de base de datos
DB_CONFIG = {
    'host': 'localhost',
    'database': 'pacsdb',
    'user': 'pacs',
    'password': 'pacs'
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    print("="*70)
    print("CREACIÓN DE INFORME PREDEFINIDO - ECOGRAFÍA DE CUELLO")
    print("="*70)
    
    # 1. Buscar el tipo de estudio
    print("\n[1] Buscando tipo de estudio de cuello/cervical...")
    cursor.execute("""
        SELECT guid, description 
        FROM nextris.isstudytype 
        WHERE LOWER(description) LIKE '%cuello%' OR LOWER(description) LIKE '%cervical%'
    """)
    
    study_types = cursor.fetchall()
    
    if not study_types:
        print("  ✗ No se encontró tipo de estudio de cuello")
        cursor.close()
        conn.close()
        return False
    
    print(f"  ✓ Encontrados {len(study_types)} tipos de estudio:")
    for guid, desc in study_types:
        print(f"    - {desc} ({guid})")
    
    # Usar el primero encontrado
    study_type_guid = study_types[0][0]
    study_type_name = study_types[0][1]
    
    print(f"\n  → Usando: {study_type_name}")
    
    # 2. Verificar si ya existe un predefinido para este tipo de estudio
    print("\n[2] Verificando informes predefinidos existentes...")
    cursor.execute("""
        SELECT guid, tittle 
        FROM nextris.tbinfpredef 
        WHERE studytype_id = %s
    """, (study_type_guid,))
    
    existing = cursor.fetchall()
    
    if existing:
        print(f"  ℹ Ya existen {len(existing)} informes predefinidos:")
        for guid, title in existing:
            print(f"    - {title}")
    else:
        print("  ℹ No hay informes predefinidos para este tipo de estudio")
    
    # 3. Crear nuevo informe predefinido
    print("\n[3] Creando nuevo informe predefinido...")
    
    new_guid = str(uuid.uuid4())
    
    # Contenido del informe predefinido de Ecografía de Cuello
    title = "Ecografía de Cuello - Normal"
    
    technique = """Estudio ecográfico del cuello realizado con transductor lineal de alta frecuencia (7-12 MHz), 
en planos longitudinales y transversales, evaluando estructuras cervicales anteriores y laterales."""
    
    findings = """GLÁNDULA TIROIDES:
- Lóbulo derecho: Tamaño normal, ecoestructura homogénea, sin nódulos.
- Lóbulo izquierdo: Tamaño normal, ecoestructura homogénea, sin nódulos.
- Istmo: De espesor normal.
- Vascularización: Patrón vascular conservado al Doppler color.

GANGLIOS LINFÁTICOS:
- Cadenas cervicales: Ganglios de morfología y tamaño conservados.
- No se observan adenomegalias significativas.

GLÁNDULAS SALIVALES:
- Glándulas submandibulares: Sin alteraciones.

ESTRUCTURAS VASCULARES:
- Arterias carótidas comunes: Permeables, de calibre normal.
- Venas yugulares internas: Permeables.

PARTES BLANDAS:
- Sin masas ni colecciones."""
    
    impressions = """1. Glándula tiroides de características ecográficas normales.
2. No se observan adenomegalias cervicales significativas.
3. Estructuras vasculares cervicales sin alteraciones."""
    
    conclusion = """Ecografía de cuello sin hallazgos patológicos significativos."""
    
    # Insertar el registro
    cursor.execute("""
        INSERT INTO nextris.tbinfpredef 
        (guid, tittle, findings, impression, technique, conclusion, studytype_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (new_guid, title, findings, impressions, technique, conclusion, study_type_guid))
    
    conn.commit()
    
    print(f"  ✓ Informe predefinido creado con GUID: {new_guid}")
    print(f"  ✓ Título: {title}")
    
    # 4. Opcionalmente, establecerlo como predefinido por defecto
    print("\n[4] ¿Establecer como predefinido por defecto? (opcional)")
    cursor.execute("""
        SELECT default_predef_id 
        FROM nextris.isstudytype 
        WHERE guid = %s
    """, (study_type_guid,))
    
    current_default = cursor.fetchone()
    
    if current_default and current_default[0]:
        print(f"  ℹ Ya existe un predefinido por defecto: {current_default[0]}")
        print("  ℹ No se cambiará el predefinido por defecto")
    else:
        print("  → Estableciendo como predefinido por defecto...")
        cursor.execute("""
            UPDATE nextris.isstudytype 
            SET default_predef_id = %s 
            WHERE guid = %s
        """, (new_guid, study_type_guid))
        conn.commit()
        print("  ✓ Establecido como predefinido por defecto")
    
    # 5. Mostrar resumen
    print("\n" + "="*70)
    print("RESUMEN DEL INFORME CREADO")
    print("="*70)
    print(f"\nTítulo: {title}")
    print(f"Tipo de estudio: {study_type_name}")
    print(f"GUID: {new_guid}")
    print(f"\nTÉCNICA:\n{technique}")
    print(f"\nHALLAZGOS:\n{findings}")
    print(f"\nIMPRESIONES:\n{impressions}")
    print(f"\nCONCLUSIÓN:\n{conclusion}")
    print("\n" + "="*70)
    
    cursor.close()
    conn.close()
    
    print("\n✓ Informe predefinido creado exitosamente")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
