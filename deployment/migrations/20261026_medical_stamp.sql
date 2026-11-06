BEGIN;

ALTER TABLE nextris.tbuser_medical_data
    ADD COLUMN IF NOT EXISTS sello_digital VARCHAR(500);

COMMENT ON COLUMN nextris.tbuser_medical_data.sello_digital
    IS 'Nombre del archivo de sello del médico, relativo a media/firmas.';

COMMIT;
