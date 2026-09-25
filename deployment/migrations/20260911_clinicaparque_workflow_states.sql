BEGIN;

CREATE TABLE IF NOT EXISTS nextris.clinicaparque_cancellation_reasons (
    guid VARCHAR(50) PRIMARY KEY,
    code VARCHAR(80) NOT NULL UNIQUE,
    description VARCHAR(255) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE nextris.tbexamination
    ADD COLUMN IF NOT EXISTS clinicaparque_workflow_state VARCHAR(20)
        NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS clinicaparque_workflow_state_at
        TIMESTAMP WITHOUT TIME ZONE,
    ADD COLUMN IF NOT EXISTS clinicaparque_workflow_state_source VARCHAR(32),
    ADD COLUMN IF NOT EXISTS clinicaparque_workflow_state_user_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS clinicaparque_cancellation_reason_id VARCHAR(50),
    ADD COLUMN IF NOT EXISTS clinicaparque_cancellation_detail TEXT;

CREATE INDEX IF NOT EXISTS idx_tbexamination_cp_workflow_state
    ON nextris.tbexamination (clinicaparque_workflow_state);
CREATE INDEX IF NOT EXISTS idx_tbexamination_cp_cancel_reason
    ON nextris.tbexamination (clinicaparque_cancellation_reason_id);

INSERT INTO nextris.clinicaparque_cancellation_reasons
    (guid, code, description, sort_order, active)
VALUES
    (gen_random_uuid()::text, 'PATIENT_ABSENT', 'Paciente ausente', 10, TRUE),
    (gen_random_uuid()::text, 'PATIENT_REFUSAL', 'Rechazo del paciente', 20, TRUE),
    (gen_random_uuid()::text, 'CLINICAL_CONTRAINDICATION', 'Contraindicación clínica', 30, TRUE),
    (gen_random_uuid()::text, 'INADEQUATE_PREPARATION', 'Preparación inadecuada', 40, TRUE),
    (gen_random_uuid()::text, 'TECHNICAL_FAILURE', 'Falla técnica o de equipo', 50, TRUE),
    (gen_random_uuid()::text, 'DUPLICATE_ORDER', 'Orden duplicada', 60, TRUE),
    (gen_random_uuid()::text, 'INCORRECT_ORDER', 'Orden incorrecta', 70, TRUE),
    (gen_random_uuid()::text, 'OTHER', 'Otro', 80, TRUE)
ON CONFLICT (code) DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_tbexamination_cp_workflow_state'
    ) THEN
        ALTER TABLE nextris.tbexamination
            ADD CONSTRAINT ck_tbexamination_cp_workflow_state
            CHECK (clinicaparque_workflow_state IN ('pending', 'cancelled', 'already_read'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_tbexamination_cp_workflow_source'
    ) THEN
        ALTER TABLE nextris.tbexamination
            ADD CONSTRAINT ck_tbexamination_cp_workflow_source
            CHECK (clinicaparque_workflow_state_source IS NULL
                   OR clinicaparque_workflow_state_source IN ('nextris_ui', 'clinicaparque_api'));
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_tbexamination_cp_cancel_reason'
    ) THEN
        ALTER TABLE nextris.tbexamination
            ADD CONSTRAINT fk_tbexamination_cp_cancel_reason
            FOREIGN KEY (clinicaparque_cancellation_reason_id)
            REFERENCES nextris.clinicaparque_cancellation_reasons(guid);
    END IF;
END $$;

COMMIT;
