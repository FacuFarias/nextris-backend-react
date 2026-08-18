-- =============================================================================
-- Migration: Auto-create NextRIS patient from dcm4chee PACS patient
-- Date: 2026-05-26
-- Description:
--   When a new patient is inserted into public.patient (dcm4chee PACS),
--   this trigger automatically creates the corresponding patient in
--   nextris.datapatient and notifies a Python listener to create the
--   portal user (nextris.tbuser_patient).
--
-- Prerequisites:
--   - Both schemas (public, nextris) must be in the same database (pacsdb)
--   - nextris.datapatient table must exist
--   - nextris.tbuser_patient table must exist
-- =============================================================================

-- 1. Sequence for NR patient IDs
-- Start from current max + 1
DO $$
DECLARE
    v_max integer := 0;
BEGIN
    SELECT COALESCE(MAX(CAST(SUBSTRING(patientid FROM 3) AS INTEGER)), 0)
    INTO v_max
    FROM nextris.datapatient
    WHERE patientid LIKE 'NR%';

    EXECUTE format(
        'CREATE SEQUENCE IF NOT EXISTS nextris.seq_patient_nr START WITH %s',
        v_max + 1
    );
END $$;

-- 2. Helper function: extract PatientID (0010,0020) from dicomattrs binary
-- dcm4chee stores DICOM attrs as binary: Tag(4) + VR(2) + Length(2) + Value
-- Tag (0010,0020) = bytes 10 00 20 00
CREATE OR REPLACE FUNCTION public._parse_dicom_patient_id(p_attrs bytea)
RETURNS varchar AS $$
DECLARE
    v_len integer;
    v_idx integer := 0;
    v_tag bytea;
    v_vr bytea;
    v_val_len integer;
    v_byte integer;
    v_result text := '';
BEGIN
    IF p_attrs IS NULL OR length(p_attrs) < 8 THEN
        RETURN NULL;
    END IF;

    v_len := length(p_attrs);

    WHILE v_idx <= v_len - 8 LOOP
        v_tag := substring(p_attrs FROM v_idx + 1 FOR 4);

        IF v_tag = E'\\x10002000' THEN
            v_vr := substring(p_attrs FROM v_idx + 5 FOR 2);

            -- LO=0x4C4F, SH=0x5348, PN=0x504E
            IF v_vr IN (E'\\x4C4F', E'\\x5348', E'\\x504E') THEN
                v_val_len := get_byte(p_attrs, v_idx + 6)
                            + get_byte(p_attrs, v_idx + 7) * 256;

                IF v_val_len > 0 AND v_idx + 8 + v_val_len <= v_len THEN
                    v_result := '';
                    FOR i IN 0..v_val_len - 1 LOOP
                        v_byte := get_byte(p_attrs, v_idx + 8 + i);
                        -- Only keep printable ASCII (0x20-0x7E)
                        IF v_byte >= 32 AND v_byte <= 126 THEN
                            v_result := v_result || chr(v_byte);
                        END IF;
                    END LOOP;
                    v_result := trim(v_result);
                    IF v_result != '' THEN
                        RETURN v_result;
                    END IF;
                END IF;
            END IF;
        END IF;

        v_idx := v_idx + 1;
    END LOOP;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;

-- 3. Trigger function: create patient in nextris + notify for portal user
CREATE OR REPLACE FUNCTION public.fn_create_nextris_patient_from_pacs()
RETURNS trigger AS $$
DECLARE
    v_dicomattrs bytea;
    v_dicom_patient_id varchar;
    v_pat_name varchar;
    v_surname varchar;
    v_firstname varchar;
    v_birthdate date;
    v_sexcode varchar(1);
    v_existing_guid varchar;
    v_new_guid varchar;
BEGIN
    -- 1. Extract PatientID from dicomattrs binary
    IF NEW.dicomattrs_fk IS NOT NULL THEN
        SELECT da.attrs INTO v_dicomattrs
        FROM public.dicomattrs da
        WHERE da.pk = NEW.dicomattrs_fk;

        IF v_dicomattrs IS NOT NULL THEN
            v_dicom_patient_id := public._parse_dicom_patient_id(v_dicomattrs);
        END IF;
    END IF;

    -- Skip if no PatientID available
    IF v_dicom_patient_id IS NULL OR trim(v_dicom_patient_id) = '' THEN
        RETURN NEW;
    END IF;

    -- Skip known placeholder/anonymous values
    IF lower(v_dicom_patient_id) IN ('', 'unknown', 'n/a', 'none', 'null', 'anonymous') THEN
        RETURN NEW;
    END IF;

    -- 2. Check if patient already exists in nextris by DICOM PatientID
    SELECT guid INTO v_existing_guid
    FROM nextris.datapatient
    WHERE patientid = v_dicom_patient_id
       OR (nationalcode IS NOT NULL AND nationalcode = v_dicom_patient_id)
    LIMIT 1;

    IF v_existing_guid IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- 3. Parse patient name from person_name
    IF NEW.pat_name_fk IS NOT NULL THEN
        SELECT pn.alphabetic_name INTO v_pat_name
        FROM public.person_name pn
        WHERE pn.pk = NEW.pat_name_fk;
    END IF;

    -- Split DICOM name: LASTNAME^FIRSTNAME^MIDDLENAME^PREFIX^SUFFIX
    IF v_pat_name IS NOT NULL AND v_pat_name != '' THEN
        v_surname := split_part(v_pat_name, '^', 1);
        v_firstname := split_part(v_pat_name, '^', 2);
        v_surname := trim(trailing ' ' FROM v_surname);
        v_firstname := trim(trailing ' ' FROM v_firstname);
    ELSE
        v_surname := '';
        v_firstname := '';
    END IF;

    -- Ensure we have at least some name
    IF (v_surname IS NULL OR v_surname = '')
       AND (v_firstname IS NULL OR v_firstname = '') THEN
        v_surname := 'SIN NOMBRE';
    END IF;

    -- 4. Parse birthdate: YYYYMMDD -> date
    IF NEW.pat_birthdate IS NOT NULL
       AND NEW.pat_birthdate != '*'
       AND NEW.pat_birthdate ~ '^\d{8}$' THEN
        BEGIN
            v_birthdate := to_date(NEW.pat_birthdate, 'YYYYMMDD');
        EXCEPTION WHEN OTHERS THEN
            v_birthdate := NULL;
        END;
    ELSE
        v_birthdate := NULL;
    END IF;

    -- 5. Map sex code
    v_sexcode := CASE NEW.pat_sex
        WHEN 'M' THEN 'M'
        WHEN 'F' THEN 'F'
        ELSE 'I'
    END;

    -- 6. Generate new patient GUID
    v_new_guid := gen_random_uuid()::text;

    -- 7. Insert patient into nextris.datapatient
    -- patientid = DICOM PatientID (tag 0010,0020)
    INSERT INTO nextris.datapatient (
        guid, patientid, nationalcode, name, surname,
        birthdate, sexcode,
        patient_type, healthcard_type
    ) VALUES (
        v_new_guid, v_dicom_patient_id, v_dicom_patient_id,
        v_firstname, v_surname,
        v_birthdate, v_sexcode,
        'F', 'Particular'
    );

    -- 8. Portal user creation via NOTIFY (DISABLED)
    --    Uncomment to re-enable automatic portal user creation.
    --    username = patientid = DICOM PatientID
    --    password = last 3 digits of patientid
    --
    -- v_notify_payload := json_build_object(
    --     'guid', v_new_guid,
    --     'nationalcode', v_dicom_patient_id,
    --     'patientid', v_dicom_patient_id,
    --     'name', coalesce(v_firstname || ' ' || v_surname, v_surname)
    -- )::text;
    --
    -- PERFORM pg_notify('pacs_new_patient', v_notify_payload);

    RAISE NOTICE 'NextRIS patient created: % (DICOM PatientID: %)',
        v_dicom_patient_id, v_dicom_patient_id;

    RETURN NEW;

EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Error creating NextRIS patient from PACS: %', SQLERRM;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4. Create deferred trigger on public.patient
--    DISABLED 2026-06-19: Patient creation now happens via API (from-dicom),
--    not automatically when the image arrives. The trigger is dropped.
--    The function fn_create_nextris_patient_from_pacs() is kept for reference.
DROP TRIGGER IF EXISTS trg_new_pacs_patient ON public.patient;

-- CREATE CONSTRAINT TRIGGER trg_new_pacs_patient
--     AFTER INSERT ON public.patient
--     DEFERRABLE INITIALLY DEFERRED
--     FOR EACH ROW
--     EXECUTE FUNCTION public.fn_create_nextris_patient_from_pacs();


-- =============================================================================
-- 5. Sequence for ADM numbers
-- =============================================================================
DO $$
DECLARE
    v_max integer := 0;
BEGIN
    SELECT COALESCE(MAX(CAST(SUBSTRING(admisionnumber FROM 4) AS INTEGER)), 0)
    INTO v_max
    FROM nextris.tbexamination
    WHERE admisionnumber LIKE 'ADM%';

    EXECUTE format(
        'CREATE SEQUENCE IF NOT EXISTS nextris.seq_adm_number START WITH %s',
        v_max + 1
    );
END $$;

-- 6. Helper: clean PACS study description for matching
--    Strips prefixes like "ECO 1:  ", "MAMO:  ", "END: ", "ECO: "
CREATE OR REPLACE FUNCTION public._clean_study_desc(p_desc varchar)
RETURNS varchar AS $$
DECLARE
    v_cleaned varchar;
BEGIN
    IF p_desc IS NULL OR p_desc = '' OR p_desc = '*' THEN
        RETURN NULL;
    END IF;

    v_cleaned := p_desc;

    -- Strip "ECO N:  " prefix
    IF v_cleaned ~* '^ECO\s+\d+\s*:\s*' THEN
        v_cleaned := trim(substring(v_cleaned from ':\s*(.+)$'));
    -- Strip "ECO: " prefix
    ELSIF v_cleaned ~* '^ECO\s*:\s*' THEN
        v_cleaned := trim(substring(v_cleaned from ':\s*(.+)$'));
    -- Strip "MAMO:  " prefix
    ELSIF v_cleaned ~* '^MAMO\s*:\s*' THEN
        v_cleaned := trim(substring(v_cleaned from ':\s*(.+)$'));
    -- Strip "END: " prefix
    ELSIF v_cleaned ~* '^END\s*:\s*' THEN
        v_cleaned := trim(substring(v_cleaned from ':\s*(.+)$'));
    END IF;

    IF v_cleaned = '' OR v_cleaned = '*' THEN
        RETURN NULL;
    END IF;

    RETURN v_cleaned;
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;

-- 7. Trigger function: create examination when study arrives in PACS
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
BEGIN
    -- 1. Get the DICOM PatientID from the patient's dicomattrs
    SELECT public._parse_dicom_patient_id(da.attrs)
    INTO v_dicom_patient_id
    FROM public.patient p
    JOIN public.dicomattrs da ON da.pk = p.dicomattrs_fk
    WHERE p.pk = NEW.patient_fk;

    IF v_dicom_patient_id IS NULL OR trim(v_dicom_patient_id) = '' THEN
        RETURN NEW;
    END IF;

    -- 2. Find the patient in nextris (must already exist, created by patient trigger)
    SELECT guid INTO v_patient_guid
    FROM nextris.datapatient
    WHERE patientid = v_dicom_patient_id
    LIMIT 1;

    IF v_patient_guid IS NULL THEN
        RAISE WARNING 'NextRIS patient not found for DICOM PatientID: %', v_dicom_patient_id;
        RETURN NEW;
    END IF;

    -- 3. Skip if examination already exists for this accession or study_iuid
    IF NEW.accession_no IS NOT NULL AND NEW.accession_no != '' AND NEW.accession_no != '*' THEN
        IF EXISTS (SELECT 1 FROM nextris.tbexamination WHERE localacc = NEW.accession_no) THEN
            RETURN NEW;
        END IF;
    END IF;

    IF NEW.study_iuid IS NOT NULL AND NEW.study_iuid != '' AND NEW.study_iuid != '*' THEN
        IF EXISTS (SELECT 1 FROM nextris.tbexamination WHERE studyinstanceuid = NEW.study_iuid) THEN
            RETURN NEW;
        END IF;
    END IF;

    -- 4. Clean study description and match to study type
    v_study_desc_cleaned := public._clean_study_desc(NEW.study_desc);

    IF v_study_desc_cleaned IS NOT NULL THEN
        -- Exact match (case insensitive)
        SELECT guid INTO v_studytype_id
        FROM nextris.isstudytype
        WHERE UPPER(description) = UPPER(v_study_desc_cleaned)
        LIMIT 1;

        -- If no exact match, try: PACS desc contains studytype description
        IF v_studytype_id IS NULL THEN
            SELECT guid INTO v_studytype_id
            FROM nextris.isstudytype
            WHERE UPPER(v_study_desc_cleaned) LIKE '%' || UPPER(description) || '%'
            ORDER BY LENGTH(description) DESC
            LIMIT 1;
        END IF;
    END IF;

    -- 5. Generate ADM number
    v_adm_number := 'ADM' || lpad(
        nextval('nextris.seq_adm_number')::text,
        6, '0'
    );

    -- 6. Create examination
    v_exam_guid := gen_random_uuid()::text;

    INSERT INTO nextris.tbexamination (
        guid, idpatient, studytype_id,
        admisionnumber, localacc, studyinstanceuid,
        status, isexecuted, isreported, isimage,
        createdon, executedon
    ) VALUES (
        v_exam_guid, v_patient_guid, v_studytype_id,
        v_adm_number,
        CASE WHEN NEW.accession_no IS NOT NULL AND NEW.accession_no != '*' THEN NEW.accession_no ELSE NULL END,
        CASE WHEN NEW.study_iuid IS NOT NULL AND NEW.study_iuid != '*' THEN NEW.study_iuid ELSE NULL END,
        'Executed', 1, 0, 1,
        NOW(), NOW()
    );

    -- 7. Create empty report
    v_report_guid := gen_random_uuid()::text;

    INSERT INTO nextris.tbreport (
        guid, idexamination, idpatient, admnumber, createdon, wassaved
    ) VALUES (
        v_report_guid, v_exam_guid, v_patient_guid, v_adm_number, NOW(), FALSE
    );

    RAISE NOTICE 'NextRIS examination created: % for study % (patient: %)',
        v_adm_number, NEW.study_iuid, v_dicom_patient_id;

    RETURN NEW;

EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Error creating NextRIS examination from PACS: %', SQLERRM;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 8. Create trigger on public.study
DROP TRIGGER IF EXISTS trg_new_pacs_study ON public.study;

CREATE CONSTRAINT TRIGGER trg_new_pacs_study
    AFTER INSERT ON public.study
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    EXECUTE FUNCTION public.fn_create_nextris_examination_from_pacs();
