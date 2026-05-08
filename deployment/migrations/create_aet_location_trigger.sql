-- Migration: Create AET-based location assignment trigger for PACS studies
-- Date: 2026-03-24
-- Description:
--   Phase 1: Create nextris.tbpacs_location_assignment
--   Phase 2: Create trigger on public.series using sending_aet -> nextris.tblocation.gateway_aet

BEGIN;

CREATE TABLE IF NOT EXISTS nextris.tbpacs_location_assignment (
    pacs_study_pk BIGINT PRIMARY KEY,
    pacs_study_iuid VARCHAR(255) NOT NULL,
    location_id VARCHAR(100) NOT NULL,
    sending_aet VARCHAR(64) NOT NULL,
    matched_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_pla_location
        FOREIGN KEY (location_id)
        REFERENCES nextris.tblocation (guid)
        ON DELETE CASCADE,
    CONSTRAINT fk_pla_study
        FOREIGN KEY (pacs_study_pk)
        REFERENCES public.study (pk)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pla_location_id
    ON nextris.tbpacs_location_assignment (location_id);

CREATE INDEX IF NOT EXISTS idx_pla_sending_aet
    ON nextris.tbpacs_location_assignment (sending_aet);

CREATE OR REPLACE FUNCTION nextris.fn_assign_location_from_aet()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_location_id VARCHAR(100);
    v_study_iuid VARCHAR(255);
BEGIN
    IF NEW.study_fk IS NULL OR NEW.sending_aet IS NULL OR NEW.sending_aet = '' THEN
        RETURN NEW;
    END IF;

    SELECT l.guid
      INTO v_location_id
      FROM nextris.tblocation l
     WHERE l.gateway_aet = NEW.sending_aet
     LIMIT 1;

    IF v_location_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT s.study_iuid
      INTO v_study_iuid
      FROM public.study s
     WHERE s.pk = NEW.study_fk;

    IF v_study_iuid IS NULL THEN
        RETURN NEW;
    END IF;

    -- Update public.study.location_id directly
    UPDATE public.study
    SET location_id = v_location_id
    WHERE pk = NEW.study_fk;

    -- Also record in audit table
    INSERT INTO nextris.tbpacs_location_assignment (
        pacs_study_pk,
        pacs_study_iuid,
        location_id,
        sending_aet,
        matched_at
    )
    VALUES (
        NEW.study_fk,
        v_study_iuid,
        v_location_id,
        NEW.sending_aet,
        NOW()
    )
    ON CONFLICT (pacs_study_pk)
    DO UPDATE SET
        pacs_study_iuid = EXCLUDED.pacs_study_iuid,
        location_id = EXCLUDED.location_id,
        sending_aet = EXCLUDED.sending_aet,
        matched_at = NOW();

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_assign_location_on_series ON public.series;

CREATE TRIGGER trg_assign_location_on_series
AFTER INSERT ON public.series
FOR EACH ROW
EXECUTE FUNCTION nextris.fn_assign_location_from_aet();

COMMIT;
