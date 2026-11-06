BEGIN;

ALTER TABLE nextris.tbuser_medical_data
    ADD COLUMN IF NOT EXISTS integration_id_1 VARCHAR(100);

COMMENT ON COLUMN nextris.tbuser_medical_data.integration_id_1
    IS 'Identificador institucional del médico en sistemas externos, para interoperabilidad configurable.';

COMMIT;
