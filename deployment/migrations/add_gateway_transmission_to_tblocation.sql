-- Migration: Add gateway and transmission columns to nextris.tblocation
-- Date: 2026-03-23
-- Description: Agrega columnas de configuración de gateway DICOM y política de retención

BEGIN;

ALTER TABLE nextris.tblocation
    ADD COLUMN IF NOT EXISTS gateway_aet       VARCHAR(64)  DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS gateway_ip        VARCHAR(45)  DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS transmission_type VARCHAR(16)  DEFAULT 'Manual'
        CONSTRAINT tblocation_transmission_type_check CHECK (transmission_type IN ('Manual', 'Automatic')),
    ADD COLUMN IF NOT EXISTS retention_days    INTEGER      DEFAULT NULL;

COMMENT ON COLUMN nextris.tblocation.gateway_aet       IS 'Application Entity Title del gateway DICOM de la ubicación';
COMMENT ON COLUMN nextris.tblocation.gateway_ip        IS 'Dirección IP del gateway DICOM de la ubicación';
COMMENT ON COLUMN nextris.tblocation.transmission_type IS 'Tipo de transmisión DICOM: Manual o Automatic';
COMMENT ON COLUMN nextris.tblocation.retention_days    IS 'Días de retención de estudios para esta ubicación';

COMMIT;
