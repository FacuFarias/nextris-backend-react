-- Canonical report body: study_reason, content and conclusion.
-- The historical columns remain untouched as a read-only compatibility source.

BEGIN;

ALTER TABLE nextris.tbreport
    ADD COLUMN IF NOT EXISTS study_reason TEXT,
    ADD COLUMN IF NOT EXISTS content TEXT,
    ADD COLUMN IF NOT EXISTS conclusion TEXT;

ALTER TABLE nextris.tbinfpredef
    ADD COLUMN IF NOT EXISTS study_reason TEXT,
    ADD COLUMN IF NOT EXISTS content TEXT;

-- Backfill reports without overwriting a partially migrated row.
UPDATE nextris.tbreport r
SET study_reason = COALESCE(
        NULLIF(BTRIM(e.clinicalquestion), ''),
        NULLIF(BTRIM(e.history), ''),
        ''
    )
FROM nextris.tbexamination e
WHERE e.guid = r.idexamination
  AND r.study_reason IS NULL;

UPDATE nextris.tbreport r
SET content = NULLIF(CONCAT_WS(
        '<p></p>',
        CASE WHEN NULLIF(BTRIM(r.techniques), '') IS NOT NULL
             THEN '<p><strong>Técnica de examen:</strong></p>' || r.techniques END,
        CASE WHEN NULLIF(BTRIM(r.findings), '') IS NOT NULL
             THEN '<p><strong>Hallazgos:</strong></p>' || r.findings END,
        CASE WHEN NULLIF(BTRIM(r.impressions), '') IS NOT NULL
             THEN '<p><strong>Impresiones:</strong></p>' || r.impressions END
    ), '')
WHERE r.content IS NULL;

UPDATE nextris.tbreport
SET conclusion = COALESCE(conclusions, '')
WHERE conclusion IS NULL;

-- Templates have no historical report-specific reason.  Their reason is an
-- intentional empty value; existing conclusion values are already canonical.
UPDATE nextris.tbinfpredef
SET study_reason = ''
WHERE study_reason IS NULL;

UPDATE nextris.tbinfpredef ip
SET content = NULLIF(CONCAT_WS(
        '<p></p>',
        CASE WHEN NULLIF(BTRIM(ip.technique), '') IS NOT NULL
             THEN '<p><strong>Técnica de examen:</strong></p>' || ip.technique END,
        CASE WHEN NULLIF(BTRIM(ip.findings), '') IS NOT NULL
             THEN '<p><strong>Hallazgos:</strong></p>' || ip.findings END,
        CASE WHEN NULLIF(BTRIM(ip.impression), '') IS NOT NULL
             THEN '<p><strong>Impresiones:</strong></p>' || ip.impression END
    ), '')
WHERE ip.content IS NULL;

COMMENT ON COLUMN nextris.tbreport.study_reason IS 'Canonical report field: reason for the study';
COMMENT ON COLUMN nextris.tbreport.content IS 'Canonical report field: consolidated report content';
COMMENT ON COLUMN nextris.tbreport.conclusion IS 'Canonical report field: conclusion';
COMMENT ON COLUMN nextris.tbreport.findings IS 'LEGACY: use content';
COMMENT ON COLUMN nextris.tbreport.techniques IS 'LEGACY: use content';
COMMENT ON COLUMN nextris.tbreport.impressions IS 'LEGACY: use content';
COMMENT ON COLUMN nextris.tbreport.conclusions IS 'LEGACY: use conclusion';
COMMENT ON COLUMN nextris.tbinfpredef.study_reason IS 'Canonical template field: reason for the study';
COMMENT ON COLUMN nextris.tbinfpredef.content IS 'Canonical template field: consolidated template content';
COMMENT ON COLUMN nextris.tbinfpredef.findings IS 'LEGACY: use content';
COMMENT ON COLUMN nextris.tbinfpredef.technique IS 'LEGACY: use content';
COMMENT ON COLUMN nextris.tbinfpredef.impression IS 'LEGACY: use content';

COMMIT;
