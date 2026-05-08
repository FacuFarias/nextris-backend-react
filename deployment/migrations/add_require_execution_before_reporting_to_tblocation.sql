-- Migration: Add workflow execution requirement flag to nextris.tblocation
-- Date: 2026-03-27
-- Description: Permite configurar por ubicacion si se requiere ejecucion previa antes de reportar

BEGIN;

ALTER TABLE nextris.tblocation
    ADD COLUMN IF NOT EXISTS require_execution_before_reporting BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN nextris.tblocation.require_execution_before_reporting
IS 'Si TRUE, exige IsExecuted=1 antes de redactar/firmar reportes en esta ubicacion';

COMMIT;
