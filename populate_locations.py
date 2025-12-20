#!/usr/bin/env python3
"""
Script de prueba para agregar ubicaciones con zonas horarias a la tabla tblocation
Uso: python3 populate_locations.py
"""

import psycopg2
import uuid
from datetime import datetime

# Configuración de conexión
DB_CONFIG = {
    'host': '148.230.72.8',
    'user': 'pacs',
    'password': 'pacs',
    'database': 'pacsdb'
}

# Datos de ejemplo de ubicaciones con sus zonas horarias
LOCATIONS_DATA = [
    {
        'name': 'Consultorio Buenos Aires Centro',
        'code': 'LOC-BA-001',
        'address': 'Av. Pueyrredón 1234, Buenos Aires',
        'phone': '011-4000-1000',
        'geographic_location': '-34.6037, -58.3816',
        'timezone': 'America/Argentina/Buenos_Aires',
        'status': 'Active'
    },
    {
        'name': 'Consultorio Mendoza',
        'code': 'LOC-MD-001',
        'address': 'Calle San Martín 567, Mendoza',
        'phone': '0261-4000-2000',
        'geographic_location': '-32.8896, -68.8458',
        'timezone': 'America/Argentina/Mendoza',
        'status': 'Active'
    },
    {
        'name': 'Consultorio Nueva York',
        'code': 'LOC-NY-001',
        'address': '350 5th Avenue, New York',
        'phone': '+1-212-555-0100',
        'geographic_location': '40.7128, -74.0060',
        'timezone': 'America/New_York',
        'status': 'Active'
    },
    {
        'name': 'Consultorio Madrid',
        'code': 'LOC-MD-ES-001',
        'address': 'Paseo de la Castellana 162, Madrid',
        'phone': '+34-91-5000-100',
        'geographic_location': '40.4168, -3.7038',
        'timezone': 'Europe/Madrid',
        'status': 'Active'
    },
    {
        'name': 'Consultorio Tokio',
        'code': 'LOC-TK-001',
        'address': '1 Chome, Nihonbashi, Tokyo',
        'phone': '+81-3-1234-5678',
        'geographic_location': '35.6762, 139.7674',
        'timezone': 'Asia/Tokyo',
        'status': 'Active'
    }
]


def get_facility_id(cursor):
    """Obtener el GUID de la primera facility (para usar como referencia)"""
    cursor.execute("SELECT guid FROM nextris.tbfacility LIMIT 1")
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        print("⚠️  No hay facilities en la base de datos. Crea una facility primero.")
        return None


def populate_locations():
    """Agregar ubicaciones de prueba a la tabla"""
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print("🔍 Obteniendo facility_id...")
        facility_id = get_facility_id(cursor)
        
        if not facility_id:
            cursor.close()
            connection.close()
            return
        
        print(f"✓ Facility encontrada: {facility_id}\n")
        print("📍 Agregando ubicaciones de prueba...\n")
        
        for idx, loc in enumerate(LOCATIONS_DATA, 1):
            location_guid = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO nextris.tblocation 
                (guid, facility_id, name, code, address, phone, geographic_location, timezone, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                location_guid,
                facility_id,
                loc['name'],
                loc['code'],
                loc['address'],
                loc['phone'],
                loc['geographic_location'],
                loc['timezone'],
                loc['status']
            ))
            
            print(f"{idx}. ✓ Agregada: {loc['name']}")
            print(f"   Código: {loc['code']}")
            print(f"   Zona horaria: {loc['timezone']}")
            print(f"   Ubicación: {loc['geographic_location']}\n")
        
        connection.commit()
        print("✅ Todas las ubicaciones fueron agregadas exitosamente!")
        
        cursor.close()
        connection.close()
        
    except psycopg2.Error as e:
        print(f"❌ Error de base de datos: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def list_locations():
    """Listar todas las ubicaciones con sus zonas horarias"""
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print("\n📋 Ubicaciones registradas:\n")
        
        cursor.execute("""
            SELECT guid, name, code, geographic_location, timezone, status, created_at
            FROM nextris.tblocation
            ORDER BY created_at DESC
        """)
        
        locations = cursor.fetchall()
        
        if not locations:
            print("⚠️  No hay ubicaciones registradas")
        else:
            for idx, loc in enumerate(locations, 1):
                print(f"{idx}. {loc[1]}")
                print(f"   Código: {loc[2]}")
                print(f"   Ubicación: {loc[3]}")
                print(f"   Zona horaria: {loc[4]}")
                print(f"   Estado: {loc[5]}")
                print(f"   Creada: {loc[6]}\n")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")


def test_timezone_conversion():
    """Probar conversión de zonas horarias"""
    try:
        import pytz
        from datetime import datetime
        
        print("\n🌍 Prueba de conversión de zonas horarias:\n")
        
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT name, timezone
            FROM nextris.tblocation
            WHERE timezone IS NOT NULL
            ORDER BY name
        """)
        
        locations = cursor.fetchall()
        
        # Hora UTC actual
        utc_time = datetime.now(pytz.UTC)
        
        for loc in locations:
            tz = pytz.timezone(loc[1])
            local_time = utc_time.astimezone(tz)
            
            print(f"{loc[0]}")
            print(f"  Zona horaria: {loc[1]}")
            print(f"  Hora UTC: {utc_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"  Hora local: {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"  Offset UTC: {local_time.strftime('%z')}\n")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == '__main__':
    print("=" * 60)
    print("🔧 Script de Prueba: Ubicaciones y Zonas Horarias")
    print("=" * 60 + "\n")
    
    # Agregar datos de prueba
    populate_locations()
    
    # Listar ubicaciones
    list_locations()
    
    # Probar conversión de zonas horarias
    try:
        test_timezone_conversion()
    except ImportError:
        print("⚠️  Nota: Para ver la prueba de zonas horarias instala pytz")
        print("   pip install pytz")
    
    print("=" * 60)
