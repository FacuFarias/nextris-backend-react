-- Auditoría de sesiones asumidas y revocación de JWT.
CREATE TABLE IF NOT EXISTS nextris.tb_impersonation_session (
    id UUID PRIMARY KEY,
    actor_guid VARCHAR(100) NOT NULL,
    actor_username VARCHAR(255) NOT NULL,
    target_guid VARCHAR(100) NOT NULL,
    target_username VARCHAR(255) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    ip_address VARCHAR(100),
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_impersonation_actor
    ON nextris.tb_impersonation_session (actor_guid, started_at DESC);

CREATE TABLE IF NOT EXISTS nextris.tb_revoked_jwt (
    jti VARCHAR(100) PRIMARY KEY,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_revoked_jwt_expires
    ON nextris.tb_revoked_jwt (expires_at);

CREATE TABLE IF NOT EXISTS nextris.tb_impersonation_request_audit (
    id BIGSERIAL PRIMARY KEY,
    impersonation_id UUID NOT NULL REFERENCES nextris.tb_impersonation_session(id),
    actor_guid VARCHAR(100) NOT NULL,
    target_guid VARCHAR(100) NOT NULL,
    request_path TEXT NOT NULL,
    http_method VARCHAR(10) NOT NULL,
    http_status INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_impersonation_request_session
    ON nextris.tb_impersonation_request_audit (impersonation_id, created_at DESC);
