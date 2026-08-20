-- Corrige la asociación automática de estudios de resonancia provenientes de PACS.
-- dcm4chee envía normalmente la descripción con prefijo "RES: " y la modalidad
-- DICOM como MR; el catálogo interno de NextRIS representa esa modalidad como RMN.

CREATE OR REPLACE FUNCTION public._clean_study_desc(p_desc varchar)
RETURNS varchar AS $$
DECLARE
    v_cleaned varchar;
BEGIN
    IF p_desc IS NULL OR p_desc = '' OR p_desc = '*' THEN
        RETURN NULL;
    END IF;

    v_cleaned := p_desc;

    IF v_cleaned ~* '^ECO\s+\d+\s*:\s*'
       OR v_cleaned ~* '^ECO\s*:\s*'
       OR v_cleaned ~* '^MAMO\s*:\s*'
       OR v_cleaned ~* '^END\s*:\s*'
       OR v_cleaned ~* '^RES\s*:\s*' THEN
        v_cleaned := trim(substring(v_cleaned from ':\s*(.+)$'));
    END IF;

    IF v_cleaned = '' OR v_cleaned = '*' THEN
        RETURN NULL;
    END IF;

    RETURN v_cleaned;
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;
