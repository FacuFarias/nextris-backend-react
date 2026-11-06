BEGIN;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM nextris.veterinary_upload_session) THEN
  RAISE EXCEPTION 'Upload sessions exist. Downgrade refused to preserve upload files, audit and recovery state.';
 END IF;
END $$;
DROP TABLE nextris.veterinary_upload_file;
DROP TABLE nextris.veterinary_upload_session;
COMMIT;
