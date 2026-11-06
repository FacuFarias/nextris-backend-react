BEGIN;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM nextris.tb_key_image) THEN
  RAISE EXCEPTION 'Key images exist. Downgrade refused because reports may reference them.';
 END IF;
END $$;
DROP TABLE nextris.tb_key_image;
COMMIT;
