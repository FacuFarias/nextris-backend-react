BEGIN;

-- Historial de mensajes recibidos y enviados por la integración Clínica Parque.
-- La tabla ya puede existir en instalaciones anteriores; por eso la migración
-- es idempotente.
CREATE TABLE IF NOT EXISTS nextris.communication_logs (
    guid              VARCHAR(50) PRIMARY KEY,
    received_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    api_endpoint      VARCHAR(255) NOT NULL,
    http_method       VARCHAR(10) NOT NULL DEFAULT 'POST',
    patient_id        VARCHAR(100),
    patient_name      VARCHAR(255),
    accession_number  VARCHAR(100),
    order_id          VARCHAR(100),
    request_body      TEXT,
    response_status   INTEGER,
    response_body     TEXT,
    success           BOOLEAN DEFAULT TRUE,
    error_message     TEXT,
    source_ip         VARCHAR(64),
    duration_ms       INTEGER
);

CREATE INDEX IF NOT EXISTS idx_clinicaparque_logs_received_at
    ON nextris.communication_logs (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_clinicaparque_logs_endpoint
    ON nextris.communication_logs (api_endpoint);
CREATE INDEX IF NOT EXISTS idx_clinicaparque_logs_success
    ON nextris.communication_logs (success);
CREATE INDEX IF NOT EXISTS idx_clinicaparque_logs_patient_id
    ON nextris.communication_logs (patient_id);

COMMIT;
