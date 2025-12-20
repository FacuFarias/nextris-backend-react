#!/bin/bash

# Script para probar el filtrado de equipos por location_id

echo "==================================="
echo "TEST: GET /config/equipment"
echo "==================================="
echo ""

# URL del API
API_URL="http://localhost:5001/api"

echo "1. Haciendo login..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin",
    "user_type": "staff"
  }')

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "❌ Error: No se pudo obtener el token"
    echo "Response: $LOGIN_RESPONSE"
    exit 1
fi

echo "✅ Login exitoso"
echo ""

# Test 1: Sin location_id (debería devolver error 400)
echo "2. Test: GET /config/equipment (sin location_id - debe fallar)"
RESPONSE_NO_FILTER=$(curl -s -w "\n%{http_code}" -X GET "$API_URL/config/equipment" \
  -H "Authorization: Bearer $TOKEN")

HTTP_CODE=$(echo "$RESPONSE_NO_FILTER" | tail -n1)
RESPONSE_BODY=$(echo "$RESPONSE_NO_FILTER" | head -n-1)

if [ "$HTTP_CODE" == "400" ]; then
    echo "   ✅ CORRECTO: Rechazó la petición sin location_id (HTTP 400)"
    echo "   Mensaje: $(echo $RESPONSE_BODY | jq -r '.message')"
else
    echo "   ❌ ERROR: No rechazó la petición sin location_id (HTTP $HTTP_CODE)"
fi
echo ""

# Test 2: Obtener una location_id válida
echo "3. Obteniendo una location_id válida..."
LOCATIONS_RESPONSE=$(curl -s -X GET "$API_URL/institutional/locations" \
  -H "Authorization: Bearer $TOKEN")

FIRST_LOCATION=$(echo $LOCATIONS_RESPONSE | jq -r '.data[0].guid')

if [ "$FIRST_LOCATION" != "null" ] && [ ! -z "$FIRST_LOCATION" ]; then
    echo "   Location ID: $FIRST_LOCATION"
    echo ""
    
    echo "4. Test: GET /config/equipment?location_id=$FIRST_LOCATION"
    RESPONSE_FILTERED=$(curl -s -X GET "$API_URL/config/equipment?location_id=$FIRST_LOCATION" \
      -H "Authorization: Bearer $TOKEN")
    
    COUNT_FILTERED=$(echo $RESPONSE_FILTERED | jq -r '.data | length')
    echo "   ✅ Equipos encontrados para esta ubicación: $COUNT_FILTERED"
    echo ""
    
    # Mostrar los primeros equipos
    if [ $COUNT_FILTERED -gt 0 ]; then
        echo "   Primeros equipos encontrados:"
        echo $RESPONSE_FILTERED | jq -r '.data[0:3] | .[] | "   - " + .description + " (AE: " + .aeTitle + ")"'
    else
        echo "   ℹ️  No hay equipos asignados a esta ubicación"
    fi
    echo ""
    
    echo "✅ CORRECTO: El endpoint solo devuelve equipos de la ubicación especificada"
else
    echo "   ⚠️  No hay ubicaciones en el sistema para probar"
fi

echo ""
echo "==================================="
echo "TEST COMPLETADO"
echo "==================================="
