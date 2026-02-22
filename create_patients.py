#!/usr/bin/env python3
"""
Script para crear 10 pacientes de prueba con cuentas de usuario
para el patientdomain de23d6c8-1a71-4f06-9120-a99b5b518ba3
"""

import uuid
import sys
import os

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

import psycopg2
from werkzeug.security import generate_password_hash

# Configuración de la base de datos
db_config = {
    'user': os.getenv('DB_USER', 'pacs'),
    'password': os.getenv('DB_PASS', 'pacs'),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'pacsdb'),
}

PATIENTDOMAIN_ID = 'de23d6c8-1a71-4f06-9120-a99b5b518ba3'

# 10 pacientes con datos realistas
PATIENTS = [
    {"name": "María",     "surname": "González López",    "nationalcode": "12345678A", "birthdate": "1985-03-15", "gender": "F", "email": "maria.gonzalez@email.com",    "phone": "612345678"},
    {"name": "Carlos",    "surname": "Martínez Ruiz",     "nationalcode": "23456789B", "birthdate": "1990-07-22", "gender": "M", "email": "carlos.martinez@email.com",   "phone": "623456789"},
    {"name": "Ana",       "surname": "Fernández García",  "nationalcode": "34567890C", "birthdate": "1978-11-08", "gender": "F", "email": "ana.fernandez@email.com",     "phone": "634567890"},
    {"name": "Javier",    "surname": "Rodríguez Sánchez", "nationalcode": "45678901D", "birthdate": "1995-01-30", "gender": "M", "email": "javier.rodriguez@email.com",  "phone": "645678901"},
    {"name": "Laura",     "surname": "Díaz Moreno",       "nationalcode": "56789012E", "birthdate": "1982-06-12", "gender": "F", "email": "laura.diaz@email.com",        "phone": "656789012"},
    {"name": "Pedro",     "surname": "Hernández Torres",  "nationalcode": "67890123F", "birthdate": "1970-09-25", "gender": "M", "email": "pedro.hernandez@email.com",   "phone": "667890123"},
    {"name": "Elena",     "surname": "Jiménez Navarro",   "nationalcode": "78901234G", "birthdate": "1988-12-03", "gender": "F", "email": "elena.jimenez@email.com",     "phone": "678901234"},
    {"name": "Roberto",   "surname": "Ruiz Domínguez",    "nationalcode": "89012345H", "birthdate": "1975-04-18", "gender": "M", "email": "roberto.ruiz@email.com",      "phone": "689012345"},
    {"name": "Sofía",     "surname": "Morales Castillo",  "nationalcode": "90123456J", "birthdate": "1992-08-07", "gender": "F", "email": "sofia.morales@email.com",     "phone": "690123456"},
    {"name": "Diego",     "surname": "Ortega Vega",       "nationalcode": "01234567K", "birthdate": "1998-02-14", "gender": "M", "email": "diego.ortega@email.com",      "phone": "601234567"},
]


def main():
    connection = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        # Obtener el último PatientID para continuar la secuencia
        cursor.execute("""
            SELECT patientid
            FROM nextris.datapatient
            WHERE patientid LIKE 'NR%%'
            ORDER BY patientid DESC
            LIMIT 1
        """)
        result = cursor.fetchone()

        if result and result[0]:
            try:
                last_number = int(result[0][2:])
            except (ValueError, IndexError):
                last_number = 0
        else:
            last_number = 0

        # Password hasheado para todos los usuarios
        hashed_password = generate_password_hash('next')

        created = []

        for i, patient_data in enumerate(PATIENTS):
            new_number = last_number + i + 1
            patient_id = f"NR{new_number:08d}"
            patient_guid = str(uuid.uuid4())

            # Insertar paciente
            cursor.execute("""
                INSERT INTO nextris.datapatient
                (guid, name, surname, patientid, nationalcode, email, phone,
                 birthdate, sexcode, healthcard, trial190, isanonymous, ismerged, id_patientdomain)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::bit, %s::bit, %s)
                RETURNING guid
            """, (
                patient_guid,
                patient_data['name'],
                patient_data['surname'],
                patient_id,
                patient_data['nationalcode'],
                patient_data['email'],
                patient_data['phone'],
                patient_data['birthdate'],
                patient_data['gender'],
                None,  # healthcard
                None,  # trial190
                0,     # isanonymous
                0,     # ismerged
                PATIENTDOMAIN_ID,
            ))
            new_guid = cursor.fetchone()[0]

            # Generar username: primera letra del nombre + apellido (sin espacios, minúsculas)
            nombre = patient_data['name'].strip()
            apellido = patient_data['surname'].strip()
            base_username = (nombre[0] + apellido.split()[0]).lower().replace(' ', '')
            # Remover acentos para el username
            import unicodedata
            base_username = ''.join(
                c for c in unicodedata.normalize('NFD', base_username)
                if unicodedata.category(c) != 'Mn'
            )

            # Verificar si el username ya existe
            cursor.execute("""
                SELECT username FROM nextris.tbuser_patient
                WHERE username LIKE %s
                ORDER BY username
            """, (f"{base_username}%",))
            existing_users = cursor.fetchall()

            username = base_username
            if existing_users and any(user[0] == base_username for user in existing_users):
                counter = 1
                while True:
                    test_username = f"{base_username}{counter:02d}"
                    if not any(user[0] == test_username for user in existing_users):
                        username = test_username
                        break
                    counter += 1

            # Crear usuario del portal
            cursor.execute("""
                INSERT INTO nextris.tbuser_patient (
                    guid, username, password, datapatient_id, status, firstlogin
                ) VALUES (
                    uuid_generate_v4(), %s, %s, %s, 'Active', 1
                )
            """, (username, hashed_password, new_guid))

            created.append({
                'guid': new_guid,
                'patient_id': patient_id,
                'name': f"{patient_data['name']} {patient_data['surname']}",
                'username': username,
                'dni': patient_data['nationalcode'],
            })

            print(f"  [{i+1}/10] Creado: {patient_id} | {patient_data['name']} {patient_data['surname']} | Usuario: {username}")

        connection.commit()
        cursor.close()

        print("\n=== RESUMEN ===")
        print(f"Pacientes creados: {len(created)}")
        print(f"PatientDomain: {PATIENTDOMAIN_ID}")
        print(f"Password por defecto: next")
        print("\n{:<14} {:<30} {:<16} {:<12}".format("PatientID", "Nombre", "Usuario", "DNI"))
        print("-" * 72)
        for p in created:
            print("{:<14} {:<30} {:<16} {:<12}".format(p['patient_id'], p['name'], p['username'], p['dni']))

    except Exception as e:
        if connection:
            connection.rollback()
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)
    finally:
        if connection:
            connection.close()


if __name__ == '__main__':
    main()
