-- Configuración y cola persistente para el envío diferido de reportes firmados.

ALTER TABLE nextris.app_config
    ADD COLUMN IF NOT EXISTS report_send_delay_minutes INTEGER
        NOT NULL DEFAULT 15;

CREATE TABLE IF NOT EXISTS nextris.clinicaparque_report_queue (
    id UUID PRIMARY KEY,
    exam_id VARCHAR(100) NOT NULL,
    scheduled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    locked_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_cp_report_queue_pending
    ON nextris.clinicaparque_report_queue (scheduled_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_cp_report_queue_exam_status
    ON nextris.clinicaparque_report_queue (exam_id, status);
