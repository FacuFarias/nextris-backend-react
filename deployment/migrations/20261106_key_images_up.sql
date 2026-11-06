BEGIN;
-- Author and study come from the authenticated viewer session, never from browser metadata.
-- Rows outlive deleted_at: reports that already use an image must keep rendering it.
CREATE TABLE nextris.tb_key_image (
    id uuid PRIMARY KEY,
    study_iuid varchar(64) NOT NULL,
    series_iuid varchar(64),
    sop_iuid varchar(64),
    frame integer,
    owner_id varchar(50) NOT NULL,
    author_name varchar(255) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    deleted_by varchar(50)
);
CREATE INDEX ix_key_image_study ON nextris.tb_key_image(study_iuid) WHERE deleted_at IS NULL;
COMMIT;
