-- Migration: Add flags column to tbexamination
-- Purpose: Allow users to assign color flags (red, green, blue, yellow)
--          to studies in the Redacción module.
-- Flags are stored as a TEXT array (e.g., '{"red","green"}').

ALTER TABLE nextris.tbexamination
    ADD COLUMN IF NOT EXISTS flags TEXT[] DEFAULT '{}';

COMMENT ON COLUMN nextris.tbexamination.flags
    IS 'Color flags assigned by radiologists. Allowed values: red, green, blue, yellow.';
