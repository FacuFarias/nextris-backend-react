-- Elimina encabezados de categoría pegados por error después de la conclusión vacía.
-- Ejemplos: ENCÉFALO, COLUMNA, PLEXOS Y NERVIOS PERIFÉRICOS.

BEGIN;

UPDATE nextris.tbinfpredef ip
SET conclusion = '[]'
FROM nextris.isstudytype st
JOIN nextris.ismodality modality ON modality.guid = st.modality_id
WHERE st.guid = ip.studytype_id
  AND UPPER(COALESCE(modality.description, '')) LIKE '%RESONANCIA%'
  AND ip.conclusion ~ '^\[\][[:space:]]*[[:upper:]ÁÉÍÓÚÜÑ, ]+$'
  AND btrim(ip.conclusion) <> '[]';

COMMIT;
