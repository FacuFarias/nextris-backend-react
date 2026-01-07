import psycopg2
import sys

# Config
DB_CONFIG = {
    'user': 'pacs',
    'password': 'pacs',
    'host': '148.230.72.8',
    'port': '5432',
    'dbname': 'pacsdb'
}

TARGET_GUID = "9b130f5c-e689-4b47-9488-3629a24d9cac"

def update_status_logic(cursor, exam_id):
    # Logic copied from update_examination_status
    query = """
        SELECT isplanned, isadmitted, isexecuted, issuspended, isimage, 
               isreported, isapproved, isdigitalsigned, ispublicated, isbilled 
        FROM nextris.tbexamination
        WHERE guid = %s
    """
    cursor.execute(query, (exam_id,))
    datos = cursor.fetchone()
    
    if not datos:
        return False
    
    status = ''
    if datos[0]: status += 'P '
    if datos[1]: status += 'A '
    if datos[2]: status += 'E '
    if datos[3]: status += 'S '
    if datos[4]: status += 'U '
    if datos[5]: status += 'R '
    if datos[6]: status += 'AP '
    if datos[7]: status += 'DS '
    if datos[8]: status += 'PU '
    if datos[9]: status += 'B '
    
    status = status.strip() if status else 'N'
    
    update_query = "UPDATE nextris.tbexamination SET status = %s WHERE guid = %s"
    cursor.execute(update_query, (status, exam_id))
    print(f"Status calculated: '{status}'")
    return True

def fix_order():
    print(f"Fixing order {TARGET_GUID}...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 1. Set IsAdmitted = 1
        print("Setting IsAdmitted = 1...")
        cursor.execute("UPDATE nextris.tbexamination SET IsAdmitted = 1 WHERE Guid = %s", (TARGET_GUID,))
        
        if cursor.rowcount == 0:
            print("❌ Orden no encontrada")
            conn.close()
            return

        print(f"Updated {cursor.rowcount} rows.")
        
        # 2. Update status string
        print("Updating status string...")
        if update_status_logic(cursor, TARGET_GUID):
            print("✅ Status actualizado correctamente")
        else:
            print("❌ Falló update_status_logic")

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_order()
