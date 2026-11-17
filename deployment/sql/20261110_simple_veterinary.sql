BEGIN;
CREATE TABLE IF NOT EXISTS nextris.pacs_animal_identity (
    identity_key TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    issuer TEXT NOT NULL DEFAULT '',
    normalized_name TEXT NOT NULL,
    animal_guid VARCHAR(100) NOT NULL REFERENCES nextris.datapatient(guid) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS nextris.pacs_auto_order (
    study_iuid TEXT PRIMARY KEY,
    pacs_study_pk BIGINT NOT NULL,
    animal_guid VARCHAR(100) REFERENCES nextris.datapatient(guid) ON DELETE RESTRICT,
    examination_guid VARCHAR(100) REFERENCES nextris.tbexamination(guid) ON DELETE RESTRICT,
    identity_key TEXT,
    provisional BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL CHECK (status IN ('ready','error')),
    metadata JSONB NOT NULL DEFAULT '{}',
    instance_count INTEGER NOT NULL DEFAULT 0,
    source_updated_at TIMESTAMP,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    retry_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_pacs_auto_order_identity ON nextris.pacs_auto_order(identity_key);
CREATE INDEX IF NOT EXISTS ix_pacs_auto_order_retry ON nextris.pacs_auto_order(retry_at) WHERE status='error';
CREATE INDEX IF NOT EXISTS ix_pacs_auto_order_exam ON nextris.pacs_auto_order(examination_guid);
COMMIT;
