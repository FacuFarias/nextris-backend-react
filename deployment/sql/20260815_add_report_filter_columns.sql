-- Campos utilizados por los filtros de Redacción.
ALTER TABLE nextris.tbexamination
    ADD COLUMN IF NOT EXISTS flags TEXT[] NOT NULL DEFAULT '{}';
