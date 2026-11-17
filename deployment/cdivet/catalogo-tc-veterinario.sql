-- Catálogo inicial de TC veterinaria (CDIVET). Aditivo y repetible: no modifica entradas existentes.
BEGIN;
WITH grupos(guid,description) AS (VALUES
 ('c0000000-0000-4000-8000-000000000001','TC Canino'),
 ('c0000000-0000-4000-8000-000000000002','TC Felino'))
INSERT INTO nextris.isstudytypegroup(guid,description)
SELECT g.guid,g.description FROM grupos g
WHERE NOT EXISTS(SELECT 1 FROM nextris.isstudytypegroup x WHERE x.guid=g.guid);

WITH especies(sufijo,code,grupo) AS (VALUES
 ('Canino','CAN','c0000000-0000-4000-8000-000000000001'),
 ('Felino','FEL','c0000000-0000-4000-8000-000000000002')),
regiones(code,nombre,parte) AS (VALUES
 ('CRANEO','Cráneo y encéfalo','Cráneo'),
 ('NASAL','Cavidad nasal y senos','Cráneo / Senos'),
 ('OIDOS','Oídos y bullas timpánicas','Cabeza'),
 ('MAXIL','Maxilofacial y dental','Maxilofacial'),
 ('CUELLO','Cuello','Cuello'),
 ('TORAX','Tórax','Tórax'),
 ('ABDOM','Abdomen','Abdomen'),
 ('TORABD','Tórax y abdomen','Abdomen'),
 ('PELVIS','Pelvis','Pelvis'),
 ('COLCER','Columna cervical','Columna vertebral'),
 ('COLTOR','Columna torácica','Columna vertebral'),
 ('COLLUM','Columna lumbosacra','Columna vertebral'),
 ('MIEANT','Miembro anterior','Extremidad superior'),
 ('MIEPOS','Miembro posterior','Extremidad inferior'),
 ('ANGIO','Angio-TC','Sistema vascular'))
INSERT INTO nextris.isstudytype(guid,code,description,studygroup_id,bodypart_id,modality_id)
SELECT gen_random_uuid()::text,'TC-'||e.code||'-'||r.code,CASE WHEN r.code='ANGIO' THEN r.nombre ELSE 'TC '||r.nombre END||' - '||e.sufijo,e.grupo,
       (SELECT p.guid FROM nextris.isanatomicalpart p WHERE p.description=r.parte),
       'e0250b6c-3419-11ef-bdff-00ffb9d5e4de'
FROM especies e CROSS JOIN regiones r
WHERE NOT EXISTS(SELECT 1 FROM nextris.isstudytype x WHERE x.code='TC-'||e.code||'-'||r.code);
COMMIT;
