BEGIN;
ALTER TABLE nextris.datapatient ADD COLUMN IF NOT EXISTS patient_type varchar(20) NOT NULL DEFAULT 'M';
ALTER TABLE nextris.tbexamination
    ADD COLUMN IF NOT EXISTS hidden_in_portal integer DEFAULT 0,
    ADD COLUMN IF NOT EXISTS flags text[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS "w-order" integer NOT NULL DEFAULT 1;
-- Existing general-edition examinations are orders; new automatic PACS arrivals are not.
ALTER TABLE nextris.tbexamination ALTER COLUMN "w-order" SET DEFAULT 0;
ALTER TABLE nextris.tb_analytics_events ADD COLUMN IF NOT EXISTS facility_id varchar(100);
ALTER TABLE nextris.tbexamination
    ADD COLUMN IF NOT EXISTS isplanned integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS issuspended integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS isapproved integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS isdigitalsigned integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS isbilled integer NOT NULL DEFAULT 0;
COMMIT;
