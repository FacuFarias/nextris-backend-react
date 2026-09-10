-- Reorganiza las plantillas de Resonancia en los campos canónicos del editor.
--
-- Razón del estudio: técnica de examen + motivo + técnica + comparación.
-- Contenido: hallazgos.
-- Conclusión: impresiones.
--
-- Las columnas históricas (technique, findings e impression) se conservan
-- para compatibilidad y se utilizan como fuente de esta reorganización.

BEGIN;

DO $$
DECLARE
    template_record RECORD;
    reason_content TEXT;
    findings_content TEXT;
    impressions_content TEXT;
BEGIN
    FOR template_record IN
        SELECT
            ip.guid,
            ip.study_reason,
            ip.technique,
            ip.findings,
            ip.content,
            ip.conclusion,
            ip.impression
        FROM nextris.tbinfpredef ip
        JOIN nextris.isstudytype st ON st.guid = ip.studytype_id
        JOIN nextris.ismodality modality ON modality.guid = st.modality_id
        WHERE UPPER(COALESCE(modality.description, '')) LIKE '%RESONANCIA%'
    LOOP
        -- La columna histórica technique contiene las secciones de contexto
        -- incluso cuando study_reason ya tiene solo el motivo.
        reason_content := NULLIF(BTRIM(template_record.technique), '');
        IF reason_content IS NULL THEN
            reason_content := NULLIF(BTRIM(template_record.study_reason), '');
        END IF;
        reason_content := COALESCE(reason_content, '<p></p>');

        -- Evita acumular párrafos vacíos al volver a ejecutar la migración.
        reason_content := regexp_replace(reason_content, '(<p>[[:space:]]*</p>[[:space:]]*)+$', '', 'gi');
        IF reason_content !~* '<strong[^>]*>[[:space:]]*Técnica de examen[[:space:]]*:' THEN
            reason_content := '<p><strong>Técnica de examen:</strong></p>' || reason_content;
        END IF;

        -- Si una plantilla no tenía secciones reconocibles, conserva su texto
        -- como técnica y completa la estructura con placeholders editables.
        IF reason_content !~* 'Motivo del estudio|Datos clínicos' THEN
            reason_content := regexp_replace(
                reason_content,
                '^<p><strong>[[:space:]]*Técnica de examen[[:space:]]*:</strong></p>',
                '<p><strong>Técnica de examen:</strong></p><p><strong>Motivo del estudio: </strong>[[ ]]</p><p><strong>Técnica: </strong></p>',
                1,
                0,
                'i'
            ) || '<p><strong>Comparación: </strong>[[ ]]</p>';
        ELSE
            IF reason_content !~* '<strong[^>]*>[[:space:]]*Técnica[[:space:]]*:' THEN
                reason_content := reason_content || '<p><strong>Técnica: </strong>[[ ]]</p>';
            END IF;
            IF reason_content !~* '<strong[^>]*>[[:space:]]*Comparación[[:space:]]*:' THEN
                reason_content := reason_content || '<p><strong>Comparación: </strong>[[ ]]</p>';
            END IF;
        END IF;

        findings_content := NULLIF(BTRIM(template_record.findings), '');
        IF findings_content IS NULL THEN
            -- Fallback para una fila creada ya con el formato canónico.
            findings_content := NULLIF(BTRIM(template_record.content), '');
            findings_content := regexp_replace(
                findings_content,
                '^([[:space:]]*<p>[[:space:]]*<strong[^>]*>[[:space:]]*(Técnica de examen|Impresiones|Hallazgos)[[:space:]]*:[^<]*</strong>[[:space:]]*</p>[[:space:]]*)+',
                '',
                'gi'
            );
        END IF;
        findings_content := COALESCE(findings_content, '<p>[[ ]]</p>');
        findings_content := regexp_replace(findings_content, '(<p>[[:space:]]*</p>[[:space:]]*)+$', '', 'gi');
        IF findings_content !~* '^([[:space:]]*<p[^>]*>[[:space:]]*)?(<strong[^>]*>)?[[:space:]]*Hallazgos[[:space:]]*:' THEN
            findings_content := '<p><strong>Hallazgos:</strong></p>' || findings_content;
        END IF;

        -- En el modelo actual conclusion contiene el texto de impresiones;
        -- impression se conserva como fallback para filas antiguas.
        impressions_content := NULLIF(BTRIM(template_record.conclusion), '');
        IF impressions_content IS NULL THEN
            impressions_content := NULLIF(BTRIM(template_record.impression), '');
        END IF;
        impressions_content := COALESCE(impressions_content, '<p>[[ ]]</p>');
        impressions_content := regexp_replace(impressions_content, '(<p>[[:space:]]*</p>[[:space:]]*)+$', '', 'gi');
        IF impressions_content !~* '^([[:space:]]*<p[^>]*>[[:space:]]*)?(<strong[^>]*>)?[[:space:]]*Impresiones[[:space:]]*:' THEN
            impressions_content := '<p><strong>Impresiones:</strong></p>' || impressions_content;
        END IF;

        UPDATE nextris.tbinfpredef
        SET study_reason = reason_content,
            content = findings_content,
            conclusion = impressions_content
        WHERE guid = template_record.guid;
    END LOOP;
END $$;

COMMIT;
