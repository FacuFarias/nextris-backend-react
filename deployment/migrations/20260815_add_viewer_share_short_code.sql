-- Add a compact bearer code for QR/share URLs without persisting raw tokens.
BEGIN;

ALTER TABLE nextris.tbviewer_share_link
    ADD COLUMN IF NOT EXISTS short_code VARCHAR(16);

CREATE UNIQUE INDEX IF NOT EXISTS ux_tbviewer_share_link_short_code
    ON nextris.tbviewer_share_link (short_code)
    WHERE short_code IS NOT NULL;

COMMIT;
