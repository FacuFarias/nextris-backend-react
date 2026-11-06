BEGIN;
ALTER TABLE nextris.tbuser_patient
    ADD COLUMN IF NOT EXISTS verified_email VARCHAR(150),
    ADD COLUMN IF NOT EXISTS email_code_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS email_code_address VARCHAR(150),
    ADD COLUMN IF NOT EXISTS email_code_expires TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS email_code_sent_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS email_code_attempts INTEGER NOT NULL DEFAULT 0;

-- Any writer (portal, administration or integration) invalidates verification.
CREATE OR REPLACE FUNCTION nextris.invalidate_patient_email_verification()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF lower(btrim(COALESCE(NEW.email, ''))) IS DISTINCT FROM lower(btrim(COALESCE(OLD.email, ''))) THEN
        UPDATE nextris.tbuser_patient SET verified_email = NULL,
            email_code_hash = NULL, email_code_address = NULL,
            email_code_expires = NULL, email_code_attempts = 0
        WHERE datapatient_id = NEW.guid;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_invalidate_patient_email ON nextris.datapatient;
CREATE TRIGGER trg_invalidate_patient_email AFTER UPDATE OF email ON nextris.datapatient
FOR EACH ROW EXECUTE FUNCTION nextris.invalidate_patient_email_verification();
COMMIT;
