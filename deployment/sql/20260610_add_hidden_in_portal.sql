-- Add hidden_in_portal flag to examinations
-- 0 = visible in patient portal (default)
-- 1 = hidden from patient portal
ALTER TABLE nextris.tbexamination ADD COLUMN IF NOT EXISTS hidden_in_portal INTEGER DEFAULT 0;
COMMENT ON COLUMN nextris.tbexamination.hidden_in_portal IS '0=visible in patient portal, 1=hidden from patient portal';
