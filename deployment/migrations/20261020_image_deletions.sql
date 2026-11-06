BEGIN;

INSERT INTO nextris.ispermission (guid, code, module, action, description, is_active)
VALUES ('images.delete', 'images.delete', 'images', 'delete',
        'Gestión de imágenes: eliminar estudios, series e imágenes', TRUE)
ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description, is_active = TRUE;

-- Rejection notes are DICOM objects, but must never count as patient images.
CREATE OR REPLACE VIEW nextris.available_pacs_instance AS
SELECT i.* FROM public.instance i
LEFT JOIN public.code c ON c.pk = i.srcode_fk
WHERE NOT EXISTS (
    SELECT 1 FROM public.rejected_instance r
    JOIN public.study s ON s.study_iuid = r.study_iuid
    JOIN public.series sr ON sr.study_fk = s.pk AND sr.series_iuid = r.series_iuid
    WHERE sr.pk = i.series_fk AND r.sop_iuid = i.sop_iuid
)
AND NOT (COALESCE(c.code_designator, '') = 'DCM'
         AND COALESCE(c.code_value, '') IN ('113001', '113037', '113038', '113039'))
AND NOT (COALESCE(c.code_designator, '') = '99DCM4CHEE'
         AND COALESCE(c.code_value, '') = 'REVOKE_REJECTION');

CREATE OR REPLACE VIEW nextris.available_pacs_series AS
SELECT sr.* FROM public.series sr
WHERE EXISTS (SELECT 1 FROM nextris.available_pacs_instance i WHERE i.series_fk = sr.pk);

CREATE OR REPLACE VIEW nextris.available_pacs_study AS
SELECT s.* FROM public.study s
WHERE (SELECT TRUE FROM public.series sr
       JOIN nextris.available_pacs_instance i ON i.series_fk = sr.pk
       WHERE sr.study_fk = s.pk LIMIT 1);

CREATE OR REPLACE VIEW nextris.examination_pacs_study AS
SELECT e.guid AS examination_guid, e.studyinstanceuid AS study_iuid
FROM nextris.tbexamination e WHERE NULLIF(trim(e.studyinstanceuid), '') IS NOT NULL
UNION
SELECT l.order_guid, l.pacs_study_iuid FROM nextris.tbpacs_study_link l
WHERE l.link_status = 'linked'
UNION
SELECT m.linked_examination_guid::varchar, m.study_instance_uid
FROM nextris.tbmanual_uploads m WHERE m.islinked = 1 AND m.linked_examination_guid IS NOT NULL;

CREATE OR REPLACE FUNCTION nextris.available_study_for_exam(exam_guid varchar)
RETURNS varchar LANGUAGE sql STABLE AS $$
    SELECT s.study_iuid FROM nextris.examination_pacs_study ep
    JOIN nextris.available_pacs_study s ON s.study_iuid = ep.study_iuid
    JOIN nextris.tbexamination e ON e.guid = ep.examination_guid
    WHERE ep.examination_guid = exam_guid
    ORDER BY (s.study_iuid = e.studyinstanceuid) DESC, s.pk LIMIT 1
$$;

CREATE OR REPLACE FUNCTION nextris.available_image_count_for_exam(exam_guid varchar)
RETURNS bigint LANGUAGE sql STABLE AS $$
    SELECT count(DISTINCT i.pk) FROM nextris.examination_pacs_study ep
    JOIN public.study s ON s.study_iuid = ep.study_iuid
    JOIN public.series sr ON sr.study_fk = s.pk
    JOIN nextris.available_pacs_instance i ON i.series_fk = sr.pk
    WHERE ep.examination_guid = exam_guid
$$;

CREATE TABLE IF NOT EXISTS nextris.tbimage_deletion (
    id uuid PRIMARY KEY,
    study_pk bigint NOT NULL,
    study_iuid varchar(255) NOT NULL,
    created_by varchar(100) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL DEFAULT now() + interval '10 minutes',
    updated_at timestamptz NOT NULL DEFAULT now(),
    status varchar(30) NOT NULL DEFAULT 'preview'
      CHECK (status IN ('preview','queued','running','completed','partial','failed')),
    selection jsonb NOT NULL,
    snapshot_hash varchar(64) NOT NULL,
    affected_examinations jsonb NOT NULL,
    rejection_code varchar(20),
    justification text,
    error text,
    finished_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_image_deletion_active_study
    ON nextris.tbimage_deletion(study_iuid) WHERE status IN ('queued','running');
CREATE TABLE IF NOT EXISTS nextris.tbimage_deletion_target (
    operation_id uuid NOT NULL REFERENCES nextris.tbimage_deletion(id),
    series_iuid varchar(255) NOT NULL,
    sop_iuid varchar(255) NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'pending'
      CHECK (status IN ('pending','completed','failed')),
    attempts integer NOT NULL DEFAULT 0,
    error text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (operation_id, series_iuid, sop_iuid)
);
CREATE INDEX IF NOT EXISTS ix_image_deletion_queue ON nextris.tbimage_deletion(created_at)
    WHERE status IN ('queued','running');

-- Only availability and access change. Clinical workflow flags and reports do not.
CREATE OR REPLACE FUNCTION nextris.reconcile_image_availability(p_uid varchar DEFAULT NULL)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE changed integer;
BEGIN
    IF p_uid IS NULL THEN
        -- Evaluate the million-instance availability predicate once per scan,
        -- rather than invoking the scalar resolver for every examination.
        WITH available AS MATERIALIZED (
            SELECT study_iuid FROM nextris.available_pacs_study
        ), desired AS (
            SELECT ep.examination_guid,
                   CASE WHEN bool_or(a.study_iuid IS NOT NULL) THEN 1 ELSE 0 END AS has_images
            FROM nextris.examination_pacs_study ep
            LEFT JOIN available a ON a.study_iuid = ep.study_iuid
            GROUP BY ep.examination_guid
        )
        UPDATE nextris.tbexamination e SET isimage = d.has_images
        FROM desired d WHERE e.guid = d.examination_guid AND e.isimage IS DISTINCT FROM d.has_images;
    ELSE
    WITH affected AS (
        SELECT DISTINCT examination_guid FROM nextris.examination_pacs_study
        WHERE p_uid IS NULL OR study_iuid = p_uid
    ), desired AS (
        SELECT e.guid, CASE WHEN nextris.available_study_for_exam(e.guid) IS NOT NULL
                           THEN 1 ELSE 0 END AS has_images
        FROM nextris.tbexamination e JOIN affected a ON a.examination_guid = e.guid
    )
    UPDATE nextris.tbexamination e SET isimage = d.has_images
    FROM desired d WHERE e.guid = d.guid AND e.isimage IS DISTINCT FROM d.has_images;
    END IF;
    GET DIAGNOSTICS changed = ROW_COUNT;

    UPDATE nextris.tbmanual_uploads m
    SET pacs_status = 'rejected', pacs_message = 'Imagen rechazada en PACS (IOCM)'
    WHERE (p_uid IS NULL OR m.study_instance_uid = p_uid)
      AND m.pacs_status IS DISTINCT FROM 'rejected'
      AND EXISTS (SELECT 1 FROM public.rejected_instance r
                  WHERE r.study_iuid = m.study_instance_uid
                    AND r.series_iuid = m.series_instance_uid AND r.sop_iuid = m.sop_instance_uid);
    UPDATE nextris.tbmanual_uploads m
    SET pacs_status = 'success', pacs_message = 'Imagen disponible nuevamente en PACS'
    WHERE m.pacs_status = 'rejected' AND (p_uid IS NULL OR m.study_instance_uid = p_uid)
      AND EXISTS (SELECT 1 FROM nextris.available_pacs_instance i
                  JOIN public.series sr ON sr.pk = i.series_fk
                  JOIN public.study s ON s.pk = sr.study_fk
                  WHERE s.study_iuid = m.study_instance_uid
                    AND sr.series_iuid = m.series_instance_uid AND i.sop_iuid = m.sop_instance_uid);

    UPDATE nextris.tbviewer_share_link sl SET revoked = TRUE, revoked_at = now()
    WHERE sl.share_type = 'image_share' AND NOT sl.revoked
      AND (p_uid IS NULL OR sl.study_iuid = p_uid)
      AND NOT EXISTS (SELECT 1 FROM nextris.available_pacs_study s WHERE s.study_iuid = sl.study_iuid);
    UPDATE nextris.tb_viewer_handoff h SET expires_at = LEAST(h.expires_at, now())
    WHERE h.consumed_at IS NULL AND h.expires_at > now()
      AND (p_uid IS NULL OR h.study_iuid = p_uid)
      AND NOT EXISTS (SELECT 1 FROM nextris.available_pacs_study s WHERE s.study_iuid = h.study_iuid);
    RETURN changed;
END;
$$;
COMMIT;
