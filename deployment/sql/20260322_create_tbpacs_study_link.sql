-- RIS-PACS link table
-- Keeps PACS study linkage independent from dcm4chee core schema.

CREATE TABLE IF NOT EXISTS nextris.tbpacs_study_link (
    id BIGSERIAL PRIMARY KEY,
    pacs_study_pk BIGINT NOT NULL,
    pacs_study_iuid VARCHAR(255) NOT NULL,
    order_guid VARCHAR(100) NOT NULL,
    order_study_uuid VARCHAR(255),
    manual_upload_guid VARCHAR(100),
    link_status VARCHAR(20) NOT NULL DEFAULT 'linked',
    source VARCHAR(30) NOT NULL DEFAULT 'manual',
    linked_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    unlinked_at TIMESTAMP WITHOUT TIME ZONE,
    linked_by_user_guid VARCHAR(100),
    linked_by_username VARCHAR(255),
    unlinked_reason TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_tbpacs_study_link_status
        CHECK (link_status IN ('linked', 'unlinked')),
    CONSTRAINT chk_tbpacs_study_link_source
        CHECK (source IN ('manual', 'reconcile', 'auto')),
    CONSTRAINT fk_tbpacs_study_link_order
        FOREIGN KEY (order_guid) REFERENCES nextris.tbexamination(guid) ON DELETE RESTRICT,
    CONSTRAINT fk_tbpacs_study_link_manual_upload
        FOREIGN KEY (manual_upload_guid) REFERENCES nextris.tbmanual_uploads(guid) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tbpacs_study_link_order_guid
    ON nextris.tbpacs_study_link (order_guid);

CREATE INDEX IF NOT EXISTS idx_tbpacs_study_link_order_study_uuid
    ON nextris.tbpacs_study_link (order_study_uuid);

CREATE INDEX IF NOT EXISTS idx_tbpacs_study_link_pacs_study_pk
    ON nextris.tbpacs_study_link (pacs_study_pk);

CREATE INDEX IF NOT EXISTS idx_tbpacs_study_link_pacs_study_iuid
    ON nextris.tbpacs_study_link (pacs_study_iuid);

CREATE UNIQUE INDEX IF NOT EXISTS ux_tbpacs_study_link_order_active
    ON nextris.tbpacs_study_link (order_guid)
    WHERE link_status = 'linked';

CREATE UNIQUE INDEX IF NOT EXISTS ux_tbpacs_study_link_study_pk_active
    ON nextris.tbpacs_study_link (pacs_study_pk)
    WHERE link_status = 'linked';

CREATE UNIQUE INDEX IF NOT EXISTS ux_tbpacs_study_link_study_iuid_active
    ON nextris.tbpacs_study_link (pacs_study_iuid)
    WHERE link_status = 'linked';
