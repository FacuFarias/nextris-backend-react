BEGIN;
ALTER TABLE nextris.app_config
    ADD COLUMN IF NOT EXISTS hl7_enable_orm boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS hl7_enable_report_sending boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS hl7_bearer_token_orm text,
    ADD COLUMN IF NOT EXISTS hl7_report_send_mode varchar(20) NOT NULL DEFAULT 'text';
DO $$
DECLARE legacy jsonb;
BEGIN
    IF to_regclass('nextris.tbfacility') IS NOT NULL THEN
        EXECUTE 'SELECT to_jsonb(f) FROM nextris.tbfacility f' INTO legacy;
        UPDATE nextris.app_config SET
            hl7_enable_orm=COALESCE((legacy->>'hl7_enable_orm')::boolean,false),
            hl7_enable_report_sending=COALESCE((legacy->>'hl7_enable_report_sending')::boolean,false),
            hl7_bearer_token_orm=COALESCE(hl7_bearer_token_orm,legacy->>'hl7_bearer_token_orm')
        WHERE id=1 AND legacy IS NOT NULL;
    END IF;
END $$;
COMMIT;
