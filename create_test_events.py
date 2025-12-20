#!/usr/bin/env python3
import psycopg2
from datetime import datetime, timedelta
import uuid

# Configuración de base de datos
config = {
    'host': 'localhost',
    'database': 'pacsdb',
    'user': 'pacs',
    'password': 'pacs'
}

def get_equipment():
    conn = psycopg2.connect(**config)
    cursor = conn.cursor()
    
    # Obtener equipos disponibles
    cursor.execute('SELECT guid, aetitle, description FROM nextris.isequipment LIMIT 10')
    equipos = cursor.fetchall()
    
    print('Equipos disponibles:')
    for equipo in equipos:
        print(f'  {equipo[0]} | {equipo[1]} | {equipo[2]}')
    
    cursor.close()
    conn.close()
    return equipos

def get_patients():
    conn = psycopg2.connect(**config)
    cursor = conn.cursor()
    
    # Obtener algunos pacientes
    cursor.execute('SELECT guid, name, surname FROM nextris.datapatient LIMIT 5')
    pacientes = cursor.fetchall()
    
    print('\nPacientes disponibles:')
    for paciente in pacientes:
        print(f'  {paciente[0]} | {paciente[1]} {paciente[2]}')
    
    cursor.close()
    conn.close()
    return pacientes

def get_study_types():
    conn = psycopg2.connect(**config)
    cursor = conn.cursor()
    
    # Obtener tipos de estudios
    cursor.execute('SELECT guid, description FROM nextris.isstudytype LIMIT 5')
    estudios = cursor.fetchall()
    
    print('\nTipos de estudios disponibles:')
    for estudio in estudios:
        print(f'  {estudio[0]} | {estudio[1]}')
    
    cursor.close()
    conn.close()
    return estudios

def create_test_events():
    equipos = get_equipment()
    pacientes = get_patients()
    estudios = get_study_types()
    
    if not equipos or not pacientes or not estudios:
        print("Error: No hay datos suficientes para crear eventos")
        return
    
    conn = psycopg2.connect(**config)
    cursor = conn.cursor()
    
    # Fecha de hoy
    hoy = datetime.now().date()
    
    eventos_creados = []
    
    # Crear eventos para los primeros 3 equipos
    for i, equipo in enumerate(equipos[:3]):
        equipment_guid = equipo[0]
        equipment_name = equipo[2]
        
        # Crear 2 eventos por equipo
        for j in range(2):
            # Horarios diferentes para cada evento
            hora_inicio = 9 + (j * 2) + (i * 1)  # 9:00, 11:00, 12:00, 14:00, etc.
            
            start_time = datetime.combine(hoy, datetime.min.time().replace(hour=hora_inicio))
            end_time = start_time + timedelta(hours=1)
            
            # Seleccionar paciente y estudio
            paciente = pacientes[j % len(pacientes)]
            estudio = estudios[j % len(estudios)]
            
            event_guid = str(uuid.uuid4())
            
            try:
                # Insertar evento en tbagendaevents
                query = """
                    INSERT INTO nextris.tbagendaevents 
                    (guid, comienzo, fin, idequipment, idpatient, idexam, createdon, isadmitted)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), false)
                """
                
                cursor.execute(query, (
                    event_guid,
                    start_time,
                    end_time, 
                    equipment_guid,
                    paciente[0],
                    estudio[0]
                ))
                
                eventos_creados.append({
                    'guid': event_guid,
                    'equipo': equipment_name,
                    'paciente': f"{paciente[1]} {paciente[2]}",
                    'estudio': estudio[1],
                    'inicio': start_time,
                    'fin': end_time
                })
                
                print(f"✅ Evento creado: {equipment_name} | {paciente[1]} {paciente[2]} | {estudio[1]} | {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}")
                
            except Exception as e:
                print(f"❌ Error creando evento: {e}")
    
    # Commit cambios
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n🎉 Se crearon {len(eventos_creados)} eventos para hoy ({hoy})")
    return eventos_creados

if __name__ == "__main__":
    create_test_events()