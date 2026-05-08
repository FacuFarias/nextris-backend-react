-- Migration: create tables for temporary viewer share links
-- Date: 2026-03-24

BEGIN;

CREATE TABLE IF NOT EXISTS nextris.tbviewer_share_link (
    guid VARCHAR(100) PRIMARY KEY,
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    study_iuid VARCHAR(255) NOT NULL,
    location_id VARCHAR(100) NOT NULL,
    created_by_user_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at TIMESTAMP NULL,
    reason TEXT NULL,
    patient_email VARCHAR(255) NULL,
    open_count INTEGER NOT NULL DEFAULT 0,
    last_opened_at TIMESTAMP NULL,
    created_ip VARCHAR(64) NULL,
    last_opened_ip VARCHAR(64) NULL,
    CONSTRAINT fk_viewer_share_location
        FOREIGN KEY (location_id)
        REFERENCES nextris.tblocation (guid)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_tbviewer_share_link_study_iuid
    ON nextris.tbviewer_share_link (study_iuid);

CREATE INDEX IF NOT EXISTS idx_tbviewer_share_link_expires_at
    ON nextris.tbviewer_share_link (expires_at);

CREATE INDEX IF NOT EXISTS idx_tbviewer_share_link_created_by
    ON nextris.tbviewer_share_link (created_by_user_id);

CREATE TABLE IF NOT EXISTS nextris.tbviewer_share_link_access (
    id BIGSERIAL PRIMARY KEY,
    share_guid VARCHAR(100) NOT NULL,
    opened_at TIMESTAMP NOT NULL DEFAULT NOW(),
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(255) NULL,
    ip_address VARCHAR(64) NULL,
    user_agent TEXT NULL,
    reason TEXT NULL,
    CONSTRAINT fk_viewer_share_access_share
        FOREIGN KEY (share_guid)
        REFERENCES nextris.tbviewer_share_link (guid)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tbviewer_share_access_share_guid
    ON nextris.tbviewer_share_link_access (share_guid);

CREATE INDEX IF NOT EXISTS idx_tbviewer_share_access_opened_at
    ON nextris.tbviewer_share_link_access (opened_at);

COMMIT;
