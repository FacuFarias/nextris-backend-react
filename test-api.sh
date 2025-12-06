#!/bin/bash
# Script para probar los endpoints de la API

echo "========================================="
echo "Probando API NextRIS - React Backend"
echo "========================================="
echo ""

API_URL="http://localhost:5001/api"

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Health Check
echo -e "${YELLOW}1. Health Check${NC}"
echo "GET $API_URL/health"
RESPONSE=$(curl -s $API_URL/health)
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

# 2. Login (reemplaza con credenciales reales)
echo -e "${YELLOW}2. Login Test${NC}"
echo "POST $API_URL/auth/login"
echo "Nota: Este test fallará si no existen las credenciales, es normal"
LOGIN_RESPONSE=$(curl -s -X POST $API_URL/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin",
    "user_type": "staff"
  }')
echo "$LOGIN_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LOGIN_RESPONSE"

# Extraer token si existe
ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('data', {}).get('access_token', ''))" 2>/dev/null)

if [ -n "$ACCESS_TOKEN" ]; then
    echo -e "${GREEN}✓ Login exitoso${NC}"
    echo ""
    
    # 3. Obtener usuario actual
    echo -e "${YELLOW}3. Get Current User${NC}"
    echo "GET $API_URL/auth/me"
    curl -s $API_URL/auth/me \
      -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
    echo ""
    
    # 4. Listar pacientes
    echo -e "${YELLOW}4. List Patients${NC}"
    echo "GET $API_URL/patients?page=1&per_page=5"
    curl -s "$API_URL/patients?page=1&per_page=5" \
      -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
    echo ""
    
    # 5. Listar estudios
    echo -e "${YELLOW}5. List Studies${NC}"
    echo "GET $API_URL/studies?page=1&per_page=5"
    curl -s "$API_URL/studies?page=1&per_page=5" \
      -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
    echo ""
    
else
    echo -e "${RED}✗ Login falló - No se pueden probar endpoints autenticados${NC}"
    echo "Crear un usuario válido para probar completamente la API"
fi

echo ""
echo "========================================="
echo "Pruebas completadas"
echo "========================================="
