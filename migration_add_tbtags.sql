-- Migración: Crear tabla nextris.tbtags y agregar tag_ids a tbexamination
-- Fecha: 2026-02-18
-- Descripción: Sistema de Tags personalizados por facility para clasificar estudios
-- Nota: tbfacility.guid es character varying, por lo que guid y facility_id usan el mismo tipo.

-- ====================================================================
-- TABLA DE TAGS POR FACILITY
-- ====================================================================
CREATE TABLE IF NOT EXISTS nextris.tbtags (
    guid        CHARACTER VARYING PRIMARY KEY,
    facility_id CHARACTER VARYING NOT NULL REFERENCES nextris.tbfacility(guid) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    color       VARCHAR(20) NOT NULL DEFAULT '#6366f1',
    description TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE nextris.tbtags IS 'Tags personalizados por facility para clasificar estudios';
COMMENT ON COLUMN nextris.tbtags.guid IS 'Identificador único del tag (UUID como varchar, igual que tbfacility)';
COMMENT ON COLUMN nextris.tbtags.facility_id IS 'Facility a la que pertenece el tag';
COMMENT ON COLUMN nextris.tbtags.name IS 'Nombre visible del tag';
COMMENT ON COLUMN nextris.tbtags.color IS 'Color del tag en formato hex, ej: #ef4444';
COMMENT ON COLUMN nextris.tbtags.description IS 'Descripción opcional del tag';
COMMENT ON COLUMN nextris.tbtags.is_active IS 'Indica si el tag está activo y disponible para asignar';
COMMENT ON COLUMN nextris.tbtags.created_at IS 'Fecha y hora de creación';
COMMENT ON COLUMN nextris.tbtags.updated_at IS 'Fecha y hora de última modificación';

-- Índice para búsqueda eficiente por facility
CREATE INDEX IF NOT EXISTS idx_tbtags_facility_id ON nextris.tbtags(facility_id);

-- ====================================================================
-- COLUMNA tag_ids EN tbexamination
-- (usa TEXT[] para almacenar los varchar GUIDs, consistente con flags TEXT[])
-- ====================================================================
ALTER TABLE nextris.tbexamination
    ADD COLUMN IF NOT EXISTS tag_ids TEXT[] DEFAULT '{}';

COMMENT ON COLUMN nextris.tbexamination.tag_ids
    IS 'GUIDs de tags de nextris.tbtags asignados al estudio';

-- Mensaje de confirmación
SELECT 'Tabla nextris.tbtags creada y columna tag_ids agregada a nextris.tbexamination exitosamente' AS resultado;
