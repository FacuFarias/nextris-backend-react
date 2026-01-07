import requests
import sys

BASE_URL = "http://localhost:5001/api"
TEST_USER_EMAIL = "sysadmin"
TEST_USER_PASSWORD = "1234"
TARGET_GUID = "9b130f5c-e689-4b47-9488-3629a24d9cac"

def login():
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}
    )
    if response.status_code == 200:
        return response.json()['data']['access_token']
    return None

def execute_order(token, guid):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Payload por defecto
    payload = {
        "history": "Ejecución manual solicitada por usuario",
        "clinical_question": "N/A",
        "laterality": "no clasifica",
        "stat": False,
        "number_of_views": 1,
        "other_details": "Ejecutado desde script de asistencia"
    }

    print(f"Ejecutando orden {guid}...")
    response = requests.post(
        f"{BASE_URL}/executions/examination/{guid}/execute",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        print(f"✅ Éxito: {response.json().get('message')}")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")

if __name__ == "__main__":
    token = login()
    if token:
        execute_order(token, TARGET_GUID)
    else:
        print("❌ Error de login")
