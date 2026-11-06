BEGIN;
CREATE TABLE IF NOT EXISTS nextris.cancellation_reasons (
                guid VARCHAR(50) PRIMARY KEY,
                code VARCHAR(80) NOT NULL UNIQUE,
                description VARCHAR(255) NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            );
ALTER TABLE nextris.tbexamination
                ADD COLUMN IF NOT EXISTS workflow_state VARCHAR(20)
                    NOT NULL DEFAULT 'pending',
                ADD COLUMN IF NOT EXISTS workflow_state_at
                    TIMESTAMP WITHOUT TIME ZONE,
                ADD COLUMN IF NOT EXISTS workflow_state_source
                    VARCHAR(32),
                ADD COLUMN IF NOT EXISTS workflow_state_user_id
                    VARCHAR(100),
                ADD COLUMN IF NOT EXISTS cancellation_reason_id
                    VARCHAR(50),
                ADD COLUMN IF NOT EXISTS cancellation_detail TEXT;
CREATE INDEX IF NOT EXISTS idx_tbexamination_workflow_state
            ON nextris.tbexamination (workflow_state);
CREATE INDEX IF NOT EXISTS idx_tbexamination_cancel_reason
            ON nextris.tbexamination (cancellation_reason_id);
INSERT INTO nextris.cancellation_reasons
                    (guid, code, description, sort_order, active)
                VALUES ('08c34cc7-28cc-414f-b308-80311a486ac8', 'PATIENT_ABSENT', 'Paciente ausente', 10, TRUE)
                ON CONFLICT (code) DO NOTHING;
INSERT INTO nextris.cancellation_reasons
                    (guid, code, description, sort_order, active)
                VALUES ('bc2cfd82-f79c-4d4d-9e4b-84498d563021', 'PATIENT_REFUSAL', 'Rechazo del paciente', 20, TRUE)
                ON CONFLICT (code) DO NOTHING;
INSERT INTO nextris.cancellation_reasons
                    (guid, code, description, sort_order, active)
                VALUES ('fa389c87-2780-4dd1-b124-2665781c9399', 'CLINICAL_CONTRAINDICATION', 'Contraindicación clínica', 30, TRUE)
                ON CONFLICT (code) DO NOTHING;
INSERT INTO nextris.cancellation_reasons
                    (guid, code, description, sort_order, active)
                VALUES ('cc9a7375-beea-42a6-a29a-f41282c9475f', 'INADEQUATE_PREPARATION', 'Preparación inadecuada', 40, TRUE)
                ON CONFLICT (code) DO NOTHING;
INSERT INTO nextris.cancellation_reasons
                    (guid, code, description, sort_order, active)
                VALUES ('f736af08-3b2b-47a3-a57e-2594cc90a733', 'TECHNICAL_FAILURE', 'Falla técnica o de equipo', 50, TRUE)
                ON CONFLICT (code) DO NOTHING;
INSERT INTO nextris.cancellation_reasons
                    (guid, code, description, sort_order, active)
                VALUES ('b03a6745-c279-4cdf-93ce-e330ed552d37', 'DUPLICATE_ORDER', 'Orden duplicada', 60, TRUE)
                ON CONFLICT (code) DO NOTHING;
INSERT INTO nextris.cancellation_reasons
                    (guid, code, description, sort_order, active)
                VALUES ('ea70e4ec-e536-4433-beb0-39c6f40358d8', 'INCORRECT_ORDER', 'Orden incorrecta', 70, TRUE)
                ON CONFLICT (code) DO NOTHING;
INSERT INTO nextris.cancellation_reasons
                    (guid, code, description, sort_order, active)
                VALUES ('12554760-3033-49fe-bb93-e3a988cf4185', 'OTHER', 'Otro', 80, TRUE)
                ON CONFLICT (code) DO NOTHING;
COMMIT;
