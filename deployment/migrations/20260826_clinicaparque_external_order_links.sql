BEGIN;

-- Relación entre identificadores de Clínica Parque y entidades internas.
-- Los GUID de examination/report permanecen exclusivamente dentro de NextRIS.
CREATE TABLE IF NOT EXISTS nextris.clinicaparque_order_links (
    guid                    VARCHAR(50) PRIMARY KEY,
    source                  VARCHAR(50) NOT NULL DEFAULT 'clinicaparque',
    external_order_id       VARCHAR(100) NOT NULL,
    external_patient_id     VARCHAR(50),
    examination_guid        VARCHAR(50) NOT NULL,
    report_guid             VARCHAR(50),
    accession_number        VARCHAR(50),
    created_at              TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_clinicaparque_order_links_order
    ON nextris.clinicaparque_order_links (source, external_order_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_clinicaparque_order_links_accession
    ON nextris.clinicaparque_order_links (source, accession_number)
    WHERE accession_number IS NOT NULL AND accession_number <> '';

CREATE INDEX IF NOT EXISTS idx_clinicaparque_order_links_exam
    ON nextris.clinicaparque_order_links (examination_guid);

COMMIT;
