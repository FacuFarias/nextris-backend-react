BEGIN;

CREATE TABLE IF NOT EXISTS nextris.tbexaminationnote (
    guid VARCHAR(36) PRIMARY KEY,
    examination_id VARCHAR NOT NULL,
    author_id VARCHAR NOT NULL,
    author_username VARCHAR(64) NOT NULL,
    author_display_name VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    created_on TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tbexaminationnote_examination_created
    ON nextris.tbexaminationnote (examination_id, created_on DESC);

-- Existing general notes are not migrated into the append-only history.
UPDATE nextris.tbexamination
SET othersdetails = NULL
WHERE othersdetails IS NOT NULL;

COMMIT;
