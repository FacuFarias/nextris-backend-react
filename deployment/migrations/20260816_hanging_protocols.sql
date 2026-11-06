BEGIN;

CREATE TABLE IF NOT EXISTS nextris.tb_hanging_protocol (
    guid UUID PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL REFERENCES nextris.tbuser(guid) ON DELETE CASCADE,
    name VARCHAR(80) NOT NULL,
    modality VARCHAR(4) NOT NULL,
    layout VARCHAR(4) NOT NULL,
    viewport_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_on TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_on TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_hanging_protocol_modality CHECK (
        modality IN ('CT','MR','CR','DX','MG','US','XA','RF','NM','PT','SC','OT')
    ),
    CONSTRAINT ck_hanging_protocol_layout CHECK (layout IN ('1x1','1x2','2x1','2x2','mpr'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_hanging_protocol_active_modality
    ON nextris.tb_hanging_protocol(user_id, modality)
    WHERE is_active;
CREATE UNIQUE INDEX IF NOT EXISTS uq_hanging_protocol_user_name
    ON nextris.tb_hanging_protocol(user_id, LOWER(name));

CREATE TABLE IF NOT EXISTS nextris.tb_viewer_handoff (
    code_hash CHAR(64) PRIMARY KEY,
    -- Polymorphic identity: staff lives in tbuser, patients in tbuser_patient.
    user_id VARCHAR(50) NOT NULL,
    study_iuid VARCHAR(64) NOT NULL,
    user_type VARCHAR(40) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    created_on TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_viewer_handoff_expiry
    ON nextris.tb_viewer_handoff(expires_at);

COMMIT;
