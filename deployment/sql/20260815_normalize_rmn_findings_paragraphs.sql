-- Convierte los hallazgos RMN en párrafos HTML independientes.
-- Las líneas que funcionan como encabezado se agrupan con su descripción.

BEGIN;

DO $$
DECLARE
    template_record RECORD;
    lines TEXT[];
    line TEXT;
    next_line TEXT;
    matches TEXT[];
    normalized_html TEXT;
    finding_label TEXT;
    finding_content TEXT;
    line_index INTEGER;
BEGIN
    FOR template_record IN
        SELECT ip.guid, ip.findings
        FROM nextris.tbinfpredef ip
        JOIN nextris.isstudytype st ON st.guid = ip.studytype_id
        JOIN nextris.ismodality modality ON modality.guid = st.modality_id
        WHERE UPPER(COALESCE(modality.description, '')) LIKE '%RESONANCIA%'
          AND COALESCE(ip.findings, '') <> ''
          AND ip.findings !~* '<[a-z][^>]*>'
    LOOP
        lines := regexp_split_to_array(
            replace(template_record.findings, E'\r\n', E'\n'),
            E'\n'
        );
        normalized_html := '';
        line_index := 1;

        WHILE line_index <= COALESCE(array_length(lines, 1), 0) LOOP
            line := btrim(lines[line_index]);

            IF line = '' THEN
                line_index := line_index + 1;
                CONTINUE;
            END IF;

            matches := regexp_match(line, '^([^:]{1,120}:)[[:space:]]*(.*)$');

            IF matches IS NOT NULL THEN
                finding_label := btrim(matches[1]);
                finding_content := btrim(matches[2]);

                -- Si el encabezado estaba solo, reúne sus líneas descriptivas hasta
                -- encontrar el encabezado del siguiente hallazgo.
                IF finding_content = '' THEN
                    WHILE line_index < array_length(lines, 1) LOOP
                        next_line := btrim(lines[line_index + 1]);

                        IF next_line = '' THEN
                            line_index := line_index + 1;
                            CONTINUE;
                        END IF;

                        IF next_line ~ '^[^:]{1,120}:[[:space:]]*' THEN
                            EXIT;
                        END IF;

                        finding_content := concat_ws(' ', NULLIF(finding_content, ''), next_line);
                        line_index := line_index + 1;
                    END LOOP;
                END IF;

                normalized_html := normalized_html
                    || '<p>' || finding_label
                    || CASE WHEN finding_content <> '' THEN ' ' || finding_content ELSE '' END
                    || '</p>';
            ELSE
                normalized_html := normalized_html || '<p>' || line || '</p>';
            END IF;

            line_index := line_index + 1;
        END LOOP;

        UPDATE nextris.tbinfpredef
        SET findings = normalized_html
        WHERE guid = template_record.guid;
    END LOOP;
END $$;

COMMIT;
