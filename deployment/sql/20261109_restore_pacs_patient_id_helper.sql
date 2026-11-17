-- Restore the read-only DICOM PatientID helper required by PACS study queries.
-- Extracted unchanged from 20260526_pacs_patient_trigger.sql.
-- Deliberately excludes automatic patient creation, triggers, sequences and backfills.
-- Safe to repeat; no clinical records or DICOM files are modified.
BEGIN;

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

COMMIT;
