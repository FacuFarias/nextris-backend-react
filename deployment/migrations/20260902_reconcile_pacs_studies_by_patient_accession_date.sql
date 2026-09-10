BEGIN;

-- Reconciliación automática de estudios PACS con órdenes recibidas desde
-- Clínica Parque.
--
-- Una orden puede tener inicialmente un StudyInstanceUID generado por el
-- worklist HL7. Algunas modalidades no lo conservan y envían otro UID al
-- PACS. En ese caso, la identidad operativa de la orden se valida por:
--   1) mismo accession number;
--   2) mismo PatientName;
--   3) mismo día del estudio/orden.
--
-- Al reconciliar, el UID canónico pasa a ser siempre el UID real del PACS.

CREATE OR REPLACE FUNCTION public._normalize_pacs_patient_name(p_name text)
RETURNS text AS $$
BEGIN
    RETURN regexp_replace(
        upper(
            translate(
                replace(coalesce(p_name, ''), '^', ' '),
                'ÁÉÍÓÚÜÑáéíóúüñ',
                'AEIOUUNaeiouun'
            )
        ),
        '[^A-Z0-9]',
        '',
        'g'
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION public._safe_dicom_date(p_value text)
RETURNS date AS $$
BEGIN
    IF p_value IS NULL OR p_value !~ '^\d{8}$' THEN
        RETURN NULL;
    END IF;

    RETURN make_date(
        substring(p_value, 1, 4)::integer,
        substring(p_value, 5, 2)::integer,
        substring(p_value, 7, 2)::integer
    );
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION public.fn_create_nextris_examination_from_pacs()
RETURNS trigger AS $$
DECLARE
    v_dicom_patient_id varchar;
    v_patient_guid varchar;
    v_pacs_patient_name text;
    v_pacs_name_normalized text;
    v_study_date date;
    v_study_desc_cleaned varchar;
    v_studytype_id varchar;
    v_adm_number varchar;
    v_exam_guid varchar;
    v_report_guid varchar;
    v_matched_exam_guid varchar;
    v_old_study_uid varchar;
BEGIN
    -- 1. Identidad del paciente DICOM.
    SELECT public._parse_dicom_patient_id(da.attrs),
           pn.alphabetic_name
    INTO v_dicom_patient_id, v_pacs_patient_name
    FROM public.patient p
    JOIN public.dicomattrs da ON da.pk = p.dicomattrs_fk
    LEFT JOIN public.person_name pn ON pn.pk = p.pat_name_fk
    WHERE p.pk = NEW.patient_fk;

    IF v_dicom_patient_id IS NULL OR trim(v_dicom_patient_id) = '' THEN
        RETURN NEW;
    END IF;

    -- Si existe, conservamos el GUID del paciente identificado por DICOM.
    -- La reconciliación de una orden existente también puede resolverse por
    -- nombre + accession + fecha, aunque el PatientID DICOM no coincida.
    SELECT guid INTO v_patient_guid
    FROM nextris.datapatient
    WHERE patientid = v_dicom_patient_id
    LIMIT 1;

    v_pacs_name_normalized := public._normalize_pacs_patient_name(v_pacs_patient_name);
    v_study_date := public._safe_dicom_date(NEW.study_date);

    -- 2. Reconciliar una orden existente. Solo se consideran órdenes sin
    -- imagen para no reemplazar vínculos válidos. Se compara el nombre en
    -- ambos órdenes posibles porque NextRIS guarda name/surname separados.
    IF NEW.accession_no IS NOT NULL
       AND NEW.accession_no <> ''
       AND NEW.accession_no <> '*'
       AND v_pacs_name_normalized <> '' THEN
        SELECT e.guid, e.studyinstanceuid
        INTO v_matched_exam_guid, v_old_study_uid
        FROM nextris.tbexamination e
        JOIN nextris.datapatient dp ON dp.guid = e.idpatient
        WHERE e.localacc = NEW.accession_no
          AND COALESCE(e.isimage, 0) = 0
          AND (
                public._normalize_pacs_patient_name(dp.surname || ' ' || dp.name)
                    = v_pacs_name_normalized
                OR public._normalize_pacs_patient_name(dp.name || ' ' || dp.surname)
                    = v_pacs_name_normalized
              )
          AND (
                (v_study_date IS NOT NULL AND e.createdon::date = v_study_date)
                OR (
                    v_study_date IS NULL
                    AND NEW.created_time IS NOT NULL
                    AND e.createdon::date = NEW.created_time::date
                )
              )
        ORDER BY COALESCE(e."w-order", 0) DESC, e.createdon DESC NULLS LAST
        LIMIT 1;

        IF v_matched_exam_guid IS NOT NULL THEN
            UPDATE nextris.tbexamination
            SET studyinstanceuid = CASE
                    WHEN NEW.study_iuid IS NOT NULL
                         AND NEW.study_iuid <> ''
                         AND NEW.study_iuid <> '*'
                    THEN NEW.study_iuid
                    ELSE studyinstanceuid
                END,
                isimage = 1
            WHERE guid = v_matched_exam_guid;

            -- Mantener un vínculo auditable con el estudio PACS cuando la
            -- tabla de vínculos está instalada.
            IF to_regclass('nextris.tbpacs_study_link') IS NOT NULL
               AND NEW.study_iuid IS NOT NULL
               AND NEW.study_iuid <> ''
               AND NEW.study_iuid <> '*' THEN
                EXECUTE $sql$
                    UPDATE nextris.tbpacs_study_link
                    SET link_status = 'unlinked',
                        unlinked_at = CURRENT_TIMESTAMP,
                        unlinked_reason = 'Relink automático por accession, paciente y fecha',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE link_status = 'linked'
                      AND (order_guid = $1 OR pacs_study_pk = $2 OR pacs_study_iuid = $3)
                $sql$ USING v_matched_exam_guid, NEW.pk, NEW.study_iuid;

                EXECUTE $sql$
                    INSERT INTO nextris.tbpacs_study_link (
                        pacs_study_pk, pacs_study_iuid, order_guid,
                        order_study_uuid, link_status, source,
                        linked_at, linked_by_username, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, 'linked', 'auto',
                        CURRENT_TIMESTAMP, 'PACS Trigger', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                $sql$ USING NEW.pk, NEW.study_iuid, v_matched_exam_guid, v_old_study_uid;
            END IF;

            RAISE NOTICE 'NextRIS examination reconciled: % with PACS study % (accession: %)',
                v_matched_exam_guid, NEW.study_iuid, NEW.accession_no;
            RETURN NEW;
        END IF;
    END IF;

    -- 3. Si ya existe una orden por accession o UID pero no cumple la regla
    -- de seguridad anterior, no crear un duplicado automático.
    IF NEW.accession_no IS NOT NULL AND NEW.accession_no <> '' AND NEW.accession_no <> '*' THEN
        IF EXISTS (SELECT 1 FROM nextris.tbexamination WHERE localacc = NEW.accession_no) THEN
            RETURN NEW;
        END IF;
    END IF;

    IF NEW.study_iuid IS NOT NULL AND NEW.study_iuid <> '' AND NEW.study_iuid <> '*' THEN
        IF EXISTS (SELECT 1 FROM nextris.tbexamination WHERE studyinstanceuid = NEW.study_iuid) THEN
            RETURN NEW;
        END IF;
    END IF;

    -- Para crear un examen PACS sin orden previa sí necesitamos un paciente
    -- existente en NextRIS. La creación del paciente desde PACS sigue siendo
    -- una operación separada.
    IF v_patient_guid IS NULL THEN
        RAISE WARNING 'NextRIS patient not found for DICOM PatientID: %', v_dicom_patient_id;
        RETURN NEW;
    END IF;

    -- 4. Estudio PACS sin orden previa: conservar el comportamiento actual y
    -- crear un examen de imagen pendiente.
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
        CASE WHEN NEW.accession_no IS NOT NULL AND NEW.accession_no <> '*'
             THEN NEW.accession_no ELSE NULL END,
        CASE WHEN NEW.study_iuid IS NOT NULL AND NEW.study_iuid <> '*'
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

-- Regularizar órdenes ya recibidas antes de instalar esta regla. La fecha se
-- toma de DICOM StudyDate y el nombre se normaliza igual que en el trigger.
WITH candidates AS (
    SELECT
        e.guid AS exam_guid,
        e.studyinstanceuid AS old_study_uid,
        s.pk AS pacs_study_pk,
        s.study_iuid AS pacs_study_iuid,
        ROW_NUMBER() OVER (
            PARTITION BY e.guid
            ORDER BY s.created_time DESC NULLS LAST, s.pk DESC
        ) AS rn
    FROM nextris.tbexamination e
    JOIN nextris.datapatient dp ON dp.guid = e.idpatient
    JOIN public.study s ON s.accession_no = e.localacc
    JOIN public.patient pp ON pp.pk = s.patient_fk
    LEFT JOIN public.person_name pn ON pn.pk = pp.pat_name_fk
    WHERE COALESCE(e.isimage, 0) = 0
      AND public._normalize_pacs_patient_name(pn.alphabetic_name) <> ''
      AND (
            public._normalize_pacs_patient_name(dp.surname || ' ' || dp.name)
                = public._normalize_pacs_patient_name(pn.alphabetic_name)
            OR public._normalize_pacs_patient_name(dp.name || ' ' || dp.surname)
                = public._normalize_pacs_patient_name(pn.alphabetic_name)
          )
      AND public._safe_dicom_date(s.study_date) = e.createdon::date
)
UPDATE nextris.tbexamination e
SET studyinstanceuid = c.pacs_study_iuid,
    isimage = 1
FROM candidates c
WHERE c.rn = 1
  AND c.exam_guid = e.guid
  AND c.pacs_study_iuid IS NOT NULL
  AND c.pacs_study_iuid <> ''
  AND c.pacs_study_iuid <> '*';

-- Registrar los vínculos de las órdenes ya reparadas. No se insertan vínculos
-- para exámenes PACS sin orden API (w-order = 0).
DO $$
BEGIN
    IF to_regclass('nextris.tbpacs_study_link') IS NOT NULL THEN
        INSERT INTO nextris.tbpacs_study_link (
            pacs_study_pk, pacs_study_iuid, order_guid,
            order_study_uuid, link_status, source,
            linked_at, linked_by_username, created_at, updated_at
        )
        SELECT DISTINCT ON (e.guid)
            s.pk, s.study_iuid, e.guid, e.studyinstanceuid,
            'linked', 'auto', CURRENT_TIMESTAMP, 'PACS Reconciliation',
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM nextris.tbexamination e
        JOIN public.study s ON s.accession_no = e.localacc
                           AND s.study_iuid = e.studyinstanceuid
        JOIN nextris.datapatient dp ON dp.guid = e.idpatient
        JOIN public.patient pp ON pp.pk = s.patient_fk
        LEFT JOIN public.person_name pn ON pn.pk = pp.pat_name_fk
        WHERE e.createdon::date = public._safe_dicom_date(s.study_date)
          AND COALESCE(e.isimage, 0) = 1
          AND COALESCE(e."w-order", 0) = 1
          AND (
                public._normalize_pacs_patient_name(dp.surname || ' ' || dp.name)
                    = public._normalize_pacs_patient_name(pn.alphabetic_name)
                OR public._normalize_pacs_patient_name(dp.name || ' ' || dp.surname)
                    = public._normalize_pacs_patient_name(pn.alphabetic_name)
              )
        ORDER BY e.guid, s.created_time DESC NULLS LAST, s.pk DESC
        ON CONFLICT DO NOTHING;
    END IF;
END;
$$;

COMMIT;
