-- Normaliza la técnica de todas las plantillas RMN al formato HTML usado por Muñeca:
-- un párrafo independiente para Motivo del estudio, Técnica y Comparación.

BEGIN;

DO $$
DECLARE
    template_record RECORD;
    lines TEXT[];
    line TEXT;
    next_line TEXT;
    matches TEXT[];
    normalized_html TEXT;
    section_label TEXT;
    section_content TEXT;
    line_index INTEGER;
BEGIN
    FOR template_record IN
        SELECT ip.guid, ip.technique
        FROM nextris.tbinfpredef ip
        JOIN nextris.isstudytype st ON st.guid = ip.studytype_id
        JOIN nextris.ismodality modality ON modality.guid = st.modality_id
        WHERE UPPER(COALESCE(modality.description, '')) LIKE '%RESONANCIA%'
          AND COALESCE(ip.technique, '') <> ''
    LOOP
        IF template_record.technique !~* '<[a-z][^>]*>' THEN
            lines := regexp_split_to_array(
                replace(template_record.technique, E'\r\n', E'\n'),
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

                matches := regexp_match(
                    line,
                    '^(DATOS CLÍNICOS|MOTIVO DEL ESTUDIO|TÉCNICA|COMPARACIÓN|CONTRASTE EV|ANTECEDENTE QUIRÚRGICO):?[[:space:]]*(.*)$',
                    'i'
                );

                IF matches IS NOT NULL THEN
                    section_label := CASE UPPER(matches[1])
                        WHEN 'DATOS CLÍNICOS' THEN 'Motivo del estudio'
                        WHEN 'MOTIVO DEL ESTUDIO' THEN 'Motivo del estudio'
                        WHEN 'TÉCNICA' THEN 'Técnica'
                        WHEN 'COMPARACIÓN' THEN 'Comparación'
                        WHEN 'CONTRASTE EV' THEN 'Contraste EV'
                        WHEN 'ANTECEDENTE QUIRÚRGICO' THEN 'Antecedente quirúrgico'
                    END;
                    section_content := btrim(matches[2]);

                    -- Algunas plantillas guardaban el título y su contenido en líneas separadas.
                    IF section_content = '' AND line_index < array_length(lines, 1) THEN
                        next_line := btrim(lines[line_index + 1]);
                        IF next_line <> '' AND regexp_match(
                            next_line,
                            '^(DATOS CLÍNICOS|MOTIVO DEL ESTUDIO|TÉCNICA|COMPARACIÓN|CONTRASTE EV|ANTECEDENTE QUIRÚRGICO):?',
                            'i'
                        ) IS NULL THEN
                            section_content := next_line;
                            line_index := line_index + 1;
                        END IF;
                    END IF;

                    normalized_html := normalized_html
                        || '<p><strong>' || section_label || ': </strong>'
                        || section_content || '</p>';
                ELSE
                    normalized_html := normalized_html || '<p>' || line || '</p>';
                END IF;

                line_index := line_index + 1;
            END LOOP;

            UPDATE nextris.tbinfpredef
            SET technique = normalized_html
            WHERE guid = template_record.guid;
        ELSE
            -- Unifica el nombre de la primera sección en plantillas que ya eran HTML.
            UPDATE nextris.tbinfpredef
            SET technique = regexp_replace(
                technique,
                '<strong>[[:space:]]*DATOS CLÍNICOS[[:space:]]*:[[:space:]]*</strong>',
                '<strong>Motivo del estudio: </strong>',
                'gi'
            )
            WHERE guid = template_record.guid;
        END IF;
    END LOOP;
END $$;

-- Esta plantilla tenía Comparación dentro del mismo párrafo de Técnica.
UPDATE nextris.tbinfpredef ip
SET technique = regexp_replace(
    technique,
    '[[:space:]]*<strong>COMPARACIÓN:',
    '</p><p><strong>COMPARACIÓN:',
    'i'
)
FROM nextris.isstudytype st
WHERE st.guid = ip.studytype_id
  AND st.code = '3134';

COMMIT;
