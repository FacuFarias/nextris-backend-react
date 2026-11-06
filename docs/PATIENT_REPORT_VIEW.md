# Lectura de informes locales

El portal, la consulta clínica y los enlaces de estudio usan el mismo informe firmado
almacenado en NextRIS. `report_view_service` normaliza las secciones históricas a
motivo, contenido y conclusión; `patient_report_document` aplica pertenencia y
visibilidad antes de consultar el contenido. La firma se obtiene del usuario autor
exacto del informe; no se identifica al profesional mediante coincidencias de nombre.

El paciente recibe un documento con membrete configurable, datos del estudio, firma
y sello. Puede imprimirlo o guardarlo como PDF desde el navegador. El personal puede
obtener PDF directamente mediante la API autenticada. Los PDFs se generan en memoria.

Un informe ausente, vacío, sin finalizar o cancelado devuelve indisponibilidad.
Los enlaces públicos solo autorizan el estudio de su token; no exponen el historial
completo ni permiten elegir otro informe. Ver [instalación y contratos](GENERAL_EDITION.md).
