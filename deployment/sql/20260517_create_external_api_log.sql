BEGIN;

CREATE TABLE IF NOT EXISTS nextris.tbexternal_api_log (
    id                    BIGSERIAL PRIMARY KEY,
    request_id            VARCHAR(50) NOT NULL DEFAULT gen_random_uuid()::text,
    endpoint              VARCHAR(200) NOT NULL,
    method                VARCHAR(10) NOT NULL,
    payload               JSONB,
    patient_guid          VARCHAR(50),
    patient_nationalcode  VARCHAR(50),
    examination_guid      VARCHAR(50),
    report_guid           VARCHAR(50),
    study_uid             VARCHAR(255),
    pacs_linked           BOOLEAN DEFAULT FALSE,
    pacs_link_error       TEXT,
    status                VARCHAR(20) NOT NULL DEFAULT 'success',
    error_message         TEXT,
    ip_address            VARCHAR(64),
    user_agent            TEXT,
    created_at            TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_external_log_created ON nextris.tbexternal_api_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_external_log_nationalcode ON nextris.tbexternal_api_log (patient_nationalcode);
CREATE INDEX IF NOT EXISTS idx_external_log_request_id ON nextris.tbexternal_api_log (request_id);
CREATE INDEX IF NOT EXISTS idx_external_log_status ON nextris.tbexternal_api_log (status);

COMMIT;
