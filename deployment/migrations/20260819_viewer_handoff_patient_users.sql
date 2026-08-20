BEGIN;

-- tbuser and tbuser_patient are separate identity namespaces. The handoff
-- stores the namespace in user_type and is valid only for 60 seconds, so a
-- single FK to tbuser incorrectly rejects every patient session.
ALTER TABLE nextris.tb_viewer_handoff
    DROP CONSTRAINT IF EXISTS tb_viewer_handoff_user_id_fkey;

COMMENT ON COLUMN nextris.tb_viewer_handoff.user_id IS
    'Authenticated principal GUID; resolved in tbuser or tbuser_patient according to user_type';

COMMIT;
