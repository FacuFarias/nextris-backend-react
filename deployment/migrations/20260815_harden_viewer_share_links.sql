-- Hardening: the public token must never be persisted in plain text.
BEGIN;

ALTER TABLE nextris.tbviewer_share_link
    ALTER COLUMN location_id DROP NOT NULL;

ALTER TABLE nextris.tbviewer_share_link
    DROP COLUMN IF EXISTS raw_token;

CREATE UNIQUE INDEX IF NOT EXISTS ux_tbviewer_share_link_token_hash
    ON nextris.tbviewer_share_link (token_hash);

COMMIT;
