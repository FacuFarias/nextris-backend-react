BEGIN;

-- Existing operations retain their original logical meaning. Only a new,
-- explicitly confirmed preview may request permanent deletion.
ALTER TABLE nextris.tbimage_deletion
    ADD COLUMN IF NOT EXISTS deletion_mode varchar(20) NOT NULL DEFAULT 'logical'
        CHECK (deletion_mode IN ('logical','permanent')),
    ADD COLUMN IF NOT EXISTS pacs_instance_pks bigint[] NOT NULL DEFAULT '{}';
ALTER TABLE nextris.tbimage_deletion_target
    ADD COLUMN IF NOT EXISTS instance_pk bigint,
    ADD COLUMN IF NOT EXISTS storage_location_pks bigint[] NOT NULL DEFAULT '{}';

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
AND NOT (COALESCE(c.code_designator, '') = '99NEXTRIS'
         AND COALESCE(c.code_value, '') = 'NEXTDEL')
AND NOT (COALESCE(c.code_designator, '') = '99DCM4CHEE'
         AND COALESCE(c.code_value, '') = 'REVOKE_REJECTION');

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
    -- A permanent deletion removes the PACS index as well as its rejection.
    -- Keep the existing upload status contract, with an explicit audit message.
    UPDATE nextris.tbmanual_uploads m
    SET pacs_status = 'rejected', pacs_message = 'Imagen eliminada permanentemente del PACS'
    WHERE (p_uid IS NULL OR m.study_instance_uid = p_uid)
      AND m.pacs_message IS DISTINCT FROM 'Imagen eliminada permanentemente del PACS'
      AND EXISTS (
          SELECT 1 FROM nextris.tbimage_deletion d
          JOIN nextris.tbimage_deletion_target t ON t.operation_id=d.id
          WHERE d.deletion_mode='permanent' AND d.status <> 'preview'
            AND d.study_iuid=m.study_instance_uid AND t.series_iuid=m.series_instance_uid
            AND t.sop_iuid=m.sop_instance_uid
            AND t.instance_pk IS NOT NULL
            AND NOT EXISTS (SELECT 1 FROM public.instance i WHERE i.pk=t.instance_pk))
      AND NOT EXISTS (
          SELECT 1 FROM nextris.available_pacs_instance i
          JOIN public.series sr ON sr.pk=i.series_fk JOIN public.study s ON s.pk=sr.study_fk
          WHERE s.study_iuid=m.study_instance_uid AND sr.series_iuid=m.series_instance_uid
            AND i.sop_iuid=m.sop_instance_uid);

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
