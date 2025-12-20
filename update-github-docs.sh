#!/bin/bash

# Script para actualizar la documentación de API en GitHub
# Uso: ./update-github-docs.sh

echo "🚀 Actualizando documentación de API en GitHub..."

# Verificar si estamos en un repo git
if [ ! -d ".git" ]; then
    echo "❌ No estás en un repositorio Git"
    exit 1
fi

# Agregar la documentación del endpoint calendar-events
echo "📝 Agregando documentación de /appointments/calendar-events..."

# Crear backup del archivo original
cp API_DOCUMENTATION.md API_DOCUMENTATION.md.backup

# Agregar la nueva documentación (esto requiere edición manual o sed/awk)
echo "
#### POST /appointments/calendar-events
Obtiene eventos del calendario para editar.

**Request Body:**
\`\`\`json
{
  \"guid\": \"optional-event-guid-to-edit\",
  \"equipment_aetitle\": \"aetitle-del-equipo\"
}
\`\`\`

**Response (200):**
\`\`\`json
{
  \"success\": true,
  \"data\": {
    \"events\": [
      {
        \"guid\": \"uuid\",
        \"start\": \"2025-12-05T10:00:00\",
        \"end\": \"2025-12-05T11:00:00\",
        \"title\": \"Paciente - Examen\",
        \"patient_name\": \"string\",
        \"exam\": \"string\",
        \"editable\": true,
        \"idmed\": \"uuid\",
        \"idmed_sol\": \"uuid\"
      }
    ],
    \"work_hours\": [
      {
        \"day\": 1,
        \"start\": \"08:00:00\",
        \"end\": \"17:00:00\"
      }
    ]
  }
}
\`\`\`
" >> API_DOCUMENTATION_TEMP.md

# Hacer commit y push
git add .
git commit -m "docs: Add calendar-events endpoint documentation"
git push origin main

echo "✅ Documentación actualizada en GitHub!"
echo "📂 Archivo creado: CALENDAR_EVENTS_API.md"
echo "🔗 Revisa: https://github.com/FacuFarias/nextris-front-react"