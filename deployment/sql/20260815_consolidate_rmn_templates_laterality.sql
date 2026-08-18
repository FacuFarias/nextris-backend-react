-- Consolida plantillas RMN duplicadas únicamente por lateralidad.
-- Cada study type afectado queda asociado a una sola plantilla neutral.

BEGIN;

CREATE TEMP TABLE rmn_laterality_merge (
    removed_guid VARCHAR PRIMARY KEY,
    keeper_guid VARCHAR NOT NULL
) ON COMMIT DROP;

INSERT INTO rmn_laterality_merge (removed_guid, keeper_guid) VALUES
    ('bc3f9f1d-55b1-43e3-9256-e3578dc3e5eb', 'e01821d8-2ea7-4dda-bc39-63b7877ebf3c'), -- hombro
    ('72137f34-4725-42ab-a8b7-7c60307710b4', 'bf8100d2-083d-4be6-ae58-1124a33ef21f'), -- codo
    ('b463c971-b0ec-416b-9178-0d0f9ccc5460', '2e574510-023f-4cf5-9153-2587362fa0e9'), -- muñeca
    ('e54725be-3975-4ee8-98a9-c476d394b8f6', '268aa0ca-58f7-449a-8058-8a07fc05c959'), -- mano
    ('097377fc-a587-4385-9415-2e41cbbe1995', 'ae49b9e7-a44c-42fc-9bd6-2b4fe8cc006a'), -- cadera izquierda
    ('add2e793-175d-43d1-8005-e4b3e2a301b4', 'ae49b9e7-a44c-42fc-9bd6-2b4fe8cc006a'), -- caderas
    ('99ce85e1-1188-42b3-ad9d-3a62d3a7826f', 'f374ff00-4a65-4468-beb4-440d0f75ca8e'), -- muslo
    ('2ad8a82f-d5b5-4187-83cc-989d813654a5', '09b9499a-76a8-4209-a91a-da3a732a1f0a'), -- rodilla
    ('aa6842a9-f46a-4b51-8279-4a8abf5ce59c', 'faf475f1-d279-4763-9f66-dced1c5bb767'), -- pierna
    ('9fa68cb7-1b5b-4543-9cc0-126808f6a09a', '47f7984f-ef99-4aab-a8e4-1dd9e17a0825'), -- tobillo
    ('90465e3d-b1cf-4a68-8cef-708175a35a1e', 'c022b2d1-55be-4e94-9e04-680bceb8ac93'), -- pie
    ('9e9ae80e-20d0-43c5-a3f7-5dfbdfbbe798', 'd77c6e40-0a82-434d-9074-a764dfcf3bd8'); -- plexo braquial

-- Si existieran referencias al momento de desplegar, conservarlas en la plantilla elegida.
UPDATE nextris.isstudytype st
SET default_predef_id = merge.keeper_guid
FROM rmn_laterality_merge merge
WHERE st.default_predef_id = merge.removed_guid;

DELETE FROM nextris.tbinfpredef_user_default old_default
USING rmn_laterality_merge merge
WHERE old_default.template_id = merge.removed_guid
  AND EXISTS (
      SELECT 1
      FROM nextris.tbinfpredef_user_default keeper_default
      WHERE keeper_default.user_id = old_default.user_id
        AND keeper_default.study_type_id = old_default.study_type_id
        AND keeper_default.template_id = merge.keeper_guid
  );

UPDATE nextris.tbinfpredef_user_default user_default
SET template_id = merge.keeper_guid
FROM rmn_laterality_merge merge
WHERE user_default.template_id = merge.removed_guid;

DELETE FROM nextris.rel_infpredef_location old_location
USING rmn_laterality_merge merge
WHERE old_location.template_id = merge.removed_guid
  AND EXISTS (
      SELECT 1
      FROM nextris.rel_infpredef_location keeper_location
      WHERE keeper_location.template_id = merge.keeper_guid
        AND keeper_location.location_id = old_location.location_id
  );

UPDATE nextris.rel_infpredef_location location_relation
SET template_id = merge.keeper_guid
FROM rmn_laterality_merge merge
WHERE location_relation.template_id = merge.removed_guid;

DELETE FROM nextris.tbinfpredef template
USING rmn_laterality_merge merge
WHERE template.guid = merge.removed_guid;

UPDATE nextris.tbinfpredef
SET tittle = CASE guid
        WHEN 'e01821d8-2ea7-4dda-bc39-63b7877ebf3c' THEN 'RESONANCIA MAGNÉTICA DE HOMBRO'
        WHEN 'bf8100d2-083d-4be6-ae58-1124a33ef21f' THEN 'RESONANCIA MAGNÉTICA DE CODO'
        WHEN '2e574510-023f-4cf5-9153-2587362fa0e9' THEN 'RESONANCIA MAGNÉTICA DE MUÑECA'
        WHEN '268aa0ca-58f7-449a-8058-8a07fc05c959' THEN 'RESONANCIA MAGNÉTICA DE MANO'
        WHEN 'ae49b9e7-a44c-42fc-9bd6-2b4fe8cc006a' THEN 'RESONANCIA MAGNÉTICA DE CADERA'
        WHEN 'f374ff00-4a65-4468-beb4-440d0f75ca8e' THEN 'RESONANCIA MAGNÉTICA DE MUSLO'
        WHEN '09b9499a-76a8-4209-a91a-da3a732a1f0a' THEN 'RESONANCIA MAGNÉTICA DE RODILLA'
        WHEN 'faf475f1-d279-4763-9f66-dced1c5bb767' THEN 'RESONANCIA MAGNÉTICA DE PIERNA'
        WHEN '47f7984f-ef99-4aab-a8e4-1dd9e17a0825' THEN 'RESONANCIA MAGNÉTICA DE TOBILLO'
        WHEN 'c022b2d1-55be-4e94-9e04-680bceb8ac93' THEN 'RESONANCIA MAGNÉTICA DE PIE'
        WHEN 'd77c6e40-0a82-434d-9074-a764dfcf3bd8' THEN 'RM DE PLEXO BRAQUIAL CON Y SIN CONTRASTE EV'
    END,
    technique = regexp_replace(COALESCE(technique, ''), '\m(derecho|derecha|izquierdo|izquierda)\M', '', 'gi'),
    findings = regexp_replace(COALESCE(findings, ''), '\m(derecho|derecha|izquierdo|izquierda)\M', '', 'gi'),
    impression = regexp_replace(COALESCE(impression, ''), '\m(derecho|derecha|izquierdo|izquierda)\M', '', 'gi'),
    conclusion = regexp_replace(COALESCE(conclusion, ''), '\m(derecho|derecha|izquierdo|izquierda)\M', '', 'gi')
WHERE guid IN (SELECT DISTINCT keeper_guid FROM rmn_laterality_merge);

COMMIT;
