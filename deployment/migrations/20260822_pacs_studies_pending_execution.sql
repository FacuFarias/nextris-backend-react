-- Los estudios creados automáticamente al llegar desde PACS quedan
-- pendientes de confirmación/ejecución.
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

    IF v_patient_guid IS NULL THEN
        RAISE WARNING 'NextRIS patient not found for DICOM PatientID: %', v_dicom_patient_id;
        RETURN NEW;
    END IF;

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

    v_adm_number := 'ADM' || lpad(
        nextval('nextris.seq_adm_number')::text,
        6, '0'
    );
    v_exam_guid := gen_random_uuid()::text;

    INSERT INTO nextris.tbexamination (
        guid, idpatient, studytype_id,
        admisionnumber, localacc, studyinstanceuid,
        status, isexecuted, isreported, isimage,
        createdon, executedon, "w-order"
    ) VALUES (
        v_exam_guid, v_patient_guid, v_studytype_id,
        v_adm_number,
        CASE WHEN NEW.accession_no IS NOT NULL AND NEW.accession_no != '*' THEN NEW.accession_no ELSE NULL END,
        CASE WHEN NEW.study_iuid IS NOT NULL AND NEW.study_iuid != '*' THEN NEW.study_iuid ELSE NULL END,
        'Scheduled', 0,
        0, 1,
        NOW(), NULL, 0
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
    RAISE WARNING 'Error creating NextRIS examination from PACS: %', SQLERRM;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- El trigger ya existe; CREATE OR REPLACE FUNCTION actualiza su comportamiento
-- sin duplicar el trigger ni cambiar su momento de ejecución.
