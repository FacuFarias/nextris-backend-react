-- Informe predefinido por defecto para todos los tipos de estudio. Idempotente: no pisa ediciones posteriores.
-- Una plantilla específica de un tipo de estudio tiene prioridad sobre esta.
BEGIN;
ALTER TABLE nextris.tbinfpredef ADD COLUMN IF NOT EXISTS applies_to_all BOOLEAN NOT NULL DEFAULT FALSE;
CREATE UNIQUE INDEX IF NOT EXISTS uq_tbinfpredef_applies_to_all ON nextris.tbinfpredef (applies_to_all) WHERE applies_to_all;
INSERT INTO nextris.tbinfpredef (guid, tittle, study_reason, content, conclusion, studytype_id, report_type, owner_id, isdefault, patient_kind, applies_to_all)
VALUES ('6d0c2f4e-3b1a-4c7e-9a52-0f7e1b8d4a10', 'Informe general', '',
        '<p><strong>Técnica</strong></p><p></p><p><strong>Estudio realizado</strong></p><p></p><p><strong>Descripción</strong></p><p></p>',
        '', NULL, 'simple', 'nextris', 1, 'animal', TRUE)
ON CONFLICT (guid) DO NOTHING;
COMMIT;
