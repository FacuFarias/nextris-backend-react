-- Ownership is assigned by the authenticated NextRIS API, never from browser metadata.
CREATE TABLE IF NOT EXISTS nextris.tb_viewer_presentation_state (
    sop_iuid varchar(64) PRIMARY KEY,
    study_iuid varchar(64) NOT NULL,
    series_iuid varchar(64) NOT NULL,
    owner_id varchar(50) NOT NULL,
    author_name varchar(255) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    saved_at timestamptz,
    deleted_at timestamptz,
    deleted_by varchar(50)
);
CREATE INDEX IF NOT EXISTS ix_viewer_pr_study ON nextris.tb_viewer_presentation_state(study_iuid);
