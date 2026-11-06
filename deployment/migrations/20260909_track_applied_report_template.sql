-- Registra la plantilla que se utilizó al redactar cada informe.
-- Si no existe una asociación histórica, la lista de trabajo mostrará la
-- plantilla que corresponde actualmente por defecto.

BEGIN;

ALTER TABLE nextris.tbreport
    ADD COLUMN IF NOT EXISTS applied_template_id VARCHAR(45);

CREATE INDEX IF NOT EXISTS idx_tbreport_applied_template_id
    ON nextris.tbreport (applied_template_id);

COMMIT;
