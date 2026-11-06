BEGIN;
ALTER TABLE nextris.tbmanual_uploads
    ADD COLUMN IF NOT EXISTS linked_examination_guid varchar(100),
    ADD COLUMN IF NOT EXISTS linked_by_user_guid varchar(100),
    ADD COLUMN IF NOT EXISTS linked_by_username varchar(255),
    ADD COLUMN IF NOT EXISTS linked_at timestamp,
    ADD COLUMN IF NOT EXISTS unlinked_at timestamp;
COMMIT;
