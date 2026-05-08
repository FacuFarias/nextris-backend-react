-- Migración: agregar owner_id a nextris.tbinfpredef
-- Fecha: 2026-04-26
-- Propósito: Implementar ownership de plantillas predefinidas.
--   * Plantillas existentes quedan con owner_id = 'nextris' (sistema, no editables por usuarios)
--   * Nuevas plantillas toman el GUID del usuario creador
--   * Usuarios ven sólo sus plantillas + plantillas del sistema
--   * sysadmin puede ver/editar/eliminar todo
--
-- Rollback:
--   DROP INDEX IF EXISTS nextris.idx_tbinfpredef_owner_id;
--   ALTER TABLE nextris.tbinfpredef DROP COLUMN IF EXISTS owner_id;

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'nextris'
          AND table_name   = 'tbinfpredef'
          AND column_name  = 'owner_id'
    ) THEN
        ALTER TABLE nextris.tbinfpredef
            ADD COLUMN owner_id VARCHAR(45) NOT NULL DEFAULT 'nextris';

        -- Backfill explícito: todos los registros históricos son del sistema
        UPDATE nextris.tbinfpredef
           SET owner_id = 'nextris'
         WHERE owner_id IS NULL OR TRIM(owner_id) = '';

        -- Índice para acelerar los filtros por owner en los listados
        CREATE INDEX IF NOT EXISTS idx_tbinfpredef_owner_id
            ON nextris.tbinfpredef (owner_id);

        RAISE NOTICE 'owner_id agregado a nextris.tbinfpredef y backfill aplicado.';
    ELSE
        RAISE NOTICE 'La columna owner_id ya existe en nextris.tbinfpredef. Sin cambios.';
    END IF;
END;
$$;

COMMIT;
