-- =============================================================================
-- Analytics table for NextRIS usage monitoring
-- Run once against pacsdb: psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f this_file.sql
-- =============================================================================

CREATE TABLE IF NOT EXISTS nextris.tb_analytics_events (
    id            BIGSERIAL    PRIMARY KEY,
    event_id      UUID         DEFAULT gen_random_uuid() NOT NULL,
    user_id       VARCHAR(100),
    session_id    VARCHAR(100),
    facility_id   VARCHAR(100),
    event_type    VARCHAR(50)  NOT NULL DEFAULT 'api_request',
    route         VARCHAR(500),
    http_method   VARCHAR(10),
    http_status   SMALLINT,
    duration_ms   INTEGER,
    ip_address    VARCHAR(45),
    country       VARCHAR(100),
    city          VARCHAR(100),
    user_agent    TEXT,
    extra_data    JSONB,
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_analytics_created_at  ON nextris.tb_analytics_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_user_id     ON nextris.tb_analytics_events (user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analytics_session_id  ON nextris.tb_analytics_events (session_id) WHERE session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analytics_event_type  ON nextris.tb_analytics_events (event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_ip          ON nextris.tb_analytics_events (ip_address) WHERE ip_address IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analytics_facility    ON nextris.tb_analytics_events (facility_id) WHERE facility_id IS NOT NULL;
