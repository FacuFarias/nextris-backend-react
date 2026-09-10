-- Clasifica los enlaces externos para su administración en Gestión.
BEGIN;

ALTER TABLE nextris.tbviewer_share_link
    ADD COLUMN IF NOT EXISTS share_type VARCHAR(30) NOT NULL DEFAULT 'image_share';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_tbviewer_share_link_share_type'
    ) THEN
        ALTER TABLE nextris.tbviewer_share_link
            ADD CONSTRAINT ck_tbviewer_share_link_share_type
            CHECK (share_type IN ('case_link', 'image_share'));
    END IF;
END $$;

-- Los enlaces creados por usuarios del portal corresponden a Case Links.
UPDATE nextris.tbviewer_share_link sl
SET share_type = 'case_link'
WHERE EXISTS (
    SELECT 1
    FROM nextris.tbuser_patient up
    WHERE up.guid = sl.created_by_user_id
);

CREATE INDEX IF NOT EXISTS idx_tbviewer_share_link_share_type
    ON nextris.tbviewer_share_link (share_type);

CREATE INDEX IF NOT EXISTS idx_tbviewer_share_link_type_created_at
    ON nextris.tbviewer_share_link (share_type, created_at DESC);

COMMIT;
