-- Reconcile PACS studies with existing NextRIS orders by accession number.
--
-- The previous trigger also required the PACS study date to equal
-- tbexamination.createdon::date.  PACS stores the DICOM study date while
-- NextRIS stores the order timestamp in UTC, so that condition could prevent
-- a valid accession match.  Accession number is the authoritative order key.

CREATE OR REPLACE FUNCTION public.fn_create_nextris_examination_from_pacs()
RETURNS trigger AS $$
DECLARE
    v_dicom_patient_id varchar;
    v_patient_guid varchar;
    v_study_desc_cleaned varchar;
    v_studytype_id varchar;
    v_adm_number varchar;
    v_exam_guid varchar;
    v_report_guid varchar;
    v_matched_exam_guid varchar;
    v_old_study_uid varchar;
BEGIN
    -- Reconcile an existing pending order using accession only.
    IF NEW.accession_no IS NOT NULL
       AND trim(NEW.accession_no) <> ''
       AND trim(NEW.accession_no) <> '*' THEN
        SELECT e.guid, e.studyinstanceuid
        INTO v_matched_exam_guid, v_old_study_uid
        FROM nextris.tbexamination e
        WHERE trim(e.localacc) = trim(NEW.accession_no)
          AND COALESCE(e.isimage, 0) = 0
        ORDER BY COALESCE(e."w-order", 0) DESC, e.createdon DESC NULLS LAST
        LIMIT 1;

        IF v_matched_exam_guid IS NOT NULL THEN
            UPDATE nextris.tbexamination
            SET studyinstanceuid = CASE
                    WHEN NEW.study_iuid IS NOT NULL
                         AND trim(NEW.study_iuid) <> ''
                         AND trim(NEW.study_iuid) <> '*'
                    THEN NEW.study_iuid
                    ELSE studyinstanceuid
                END,
                isimage = 1
            WHERE guid = v_matched_exam_guid;

            IF to_regclass('nextris.tbpacs_study_link') IS NOT NULL
               AND NEW.study_iuid IS NOT NULL
               AND trim(NEW.study_iuid) <> ''
               AND trim(NEW.study_iuid) <> '*' THEN
                UPDATE nextris.tbpacs_study_link
                SET link_status = 'unlinked',
                    unlinked_at = CURRENT_TIMESTAMP,
                    unlinked_reason = 'Reemplazo por reconciliación automática por accession',
                    updated_at = CURRENT_TIMESTAMP
                WHERE link_status = 'linked'
                  AND (order_guid = v_matched_exam_guid
                       OR pacs_study_pk = NEW.pk
                       OR pacs_study_iuid = NEW.study_iuid);

                INSERT INTO nextris.tbpacs_study_link (
                    pacs_study_pk, pacs_study_iuid, order_guid,
                    order_study_uuid, link_status, source,
                    linked_at, linked_by_username, created_at, updated_at
                ) VALUES (
                    NEW.pk, NEW.study_iuid, v_matched_exam_guid,
                    v_old_study_uid, 'linked', 'auto',
                    CURRENT_TIMESTAMP, 'PACS Trigger', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
            END IF;

            RAISE NOTICE 'NextRIS examination reconciled by accession: % with PACS study % (accession: %)',
                v_matched_exam_guid, NEW.study_iuid, NEW.accession_no;
            RETURN NEW;
        END IF;
    END IF;

    -- PACS-only studies still need the DICOM PatientID to find their
    -- NextRIS patient. This is intentionally after accession reconciliation:
    -- an accession is sufficient to link an existing order.
    SELECT public._parse_dicom_patient_id(da.attrs)
    INTO v_dicom_patient_id
    FROM public.patient p
    JOIN public.dicomattrs da ON da.pk = p.dicomattrs_fk
    WHERE p.pk = NEW.patient_fk;

    IF v_dicom_patient_id IS NULL OR trim(v_dicom_patient_id) = '' THEN
        RETURN NEW;
    END IF;

    SELECT guid INTO v_patient_guid
    FROM nextris.datapatient
    WHERE patientid = v_dicom_patient_id
    LIMIT 1;

    -- Do not create a duplicate if this accession or UID is already present.
    IF NEW.accession_no IS NOT NULL
       AND trim(NEW.accession_no) <> ''
       AND trim(NEW.accession_no) <> '*'
       AND EXISTS (
           SELECT 1 FROM nextris.tbexamination
           WHERE trim(localacc) = trim(NEW.accession_no)
       ) THEN
        RETURN NEW;
    END IF;

    IF NEW.study_iuid IS NOT NULL
       AND trim(NEW.study_iuid) <> ''
       AND trim(NEW.study_iuid) <> '*'
       AND EXISTS (
           SELECT 1 FROM nextris.tbexamination
           WHERE studyinstanceuid = NEW.study_iuid
       ) THEN
        RETURN NEW;
    END IF;

    -- A PACS-only study still requires a previously known NextRIS patient.
    IF v_patient_guid IS NULL THEN
        RAISE WARNING 'NextRIS patient not found for DICOM PatientID: %', v_dicom_patient_id;
        RETURN NEW;
    END IF;

    -- Preserve the existing behavior for PACS studies without an order.
    v_study_desc_cleaned := public._clean_study_desc(NEW.study_desc);

    IF v_study_desc_cleaned IS NOT NULL THEN
        SELECT guid INTO v_studytype_id
        FROM nextris.isstudytype
        WHERE UPPER(description) = UPPER(v_study_desc_cleaned)
        LIMIT 1;

        IF v_studytype_id IS NULL THEN
            SELECT guid INTO v_studytype_id
            FROM nextris.isstudytype
            WHERE UPPER(v_study_desc_cleaned) LIKE '%' || UPPER(description) || '%'
            ORDER BY LENGTH(description) DESC
            LIMIT 1;
        END IF;
    END IF;

    v_adm_number := 'ADM' || lpad(nextval('nextris.seq_adm_number')::text, 6, '0');
    v_exam_guid := gen_random_uuid()::text;

    INSERT INTO nextris.tbexamination (
        guid, idpatient, studytype_id, admisionnumber, localacc,
        studyinstanceuid, status, isexecuted, isreported, isimage,
        createdon, executedon, "w-order"
    ) VALUES (
        v_exam_guid, v_patient_guid, v_studytype_id, v_adm_number,
        CASE WHEN NEW.accession_no IS NOT NULL AND trim(NEW.accession_no) <> '*'
             THEN NEW.accession_no ELSE NULL END,
        CASE WHEN NEW.study_iuid IS NOT NULL AND trim(NEW.study_iuid) <> '*'
             THEN NEW.study_iuid ELSE NULL END,
        'Scheduled', 0, 0, 1, NOW(), NULL, 0
    );

    v_report_guid := gen_random_uuid()::text;

    INSERT INTO nextris.tbreport (
        guid, idexamination, idpatient, admnumber, createdon, wassaved
    ) VALUES (
        v_report_guid, v_exam_guid, v_patient_guid, v_adm_number, NOW(), FALSE
    );

    RAISE NOTICE 'NextRIS examination created from PACS: % for study % (patient: %)',
        v_adm_number, NEW.study_iuid, v_dicom_patient_id;

    RETURN NEW;

EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Error creating/reconciling NextRIS examination from PACS: %', SQLERRM;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
