BEGIN;

INSERT INTO nextris.ispermission (guid, code, module, action, description, is_active)
VALUES
    ('tabs.worklist.view', 'tabs.worklist.view', 'worklist', 'view', 'Ver Lista de trabajo', TRUE),
    ('worklist.confirm_execute', 'worklist.confirm_execute', 'worklist', 'confirm_execute', 'Confirmar o ejecutar estudios', TRUE),
    ('reports.write', 'reports.write', 'reports', 'write', 'Redactar informes', TRUE),
    ('templates.manage', 'templates.manage', 'templates', 'manage', 'Gestionar informes predefinidos', TRUE),
    ('dicom.studies.manage', 'dicom.studies.manage', 'dicom', 'manage_studies', 'Cargar, vincular y desvincular estudios DICOM', TRUE)
ON CONFLICT (code)
DO UPDATE SET
    module = EXCLUDED.module,
    action = EXCLUDED.action,
    description = EXCLUDED.description,
    is_active = TRUE;

-- Toda persona que veía Redacción o Ejecución conserva acceso a la lista.
INSERT INTO nextris.rel_user_permission (
    guid, user_id, permission_id, is_granted, created_on, updated_on
)
SELECT DISTINCT
    md5(up.user_id || ':tabs.worklist.view'),
    up.user_id,
    target.guid,
    TRUE,
    NOW(),
    NOW()
FROM nextris.rel_user_permission up
JOIN nextris.ispermission source ON source.guid = up.permission_id
CROSS JOIN nextris.ispermission target
WHERE source.code IN (
        'tabs.reports.view', 'reports.view_writing', 'reports.view_reports',
        'tabs.execution.view', 'execution.view_pending', 'execution.execute'
    )
  AND target.code = 'tabs.worklist.view'
  AND up.is_granted = TRUE
ON CONFLICT (user_id, permission_id)
DO UPDATE SET is_granted = TRUE, updated_on = NOW();

-- La capacidad operativa se conserva solo para quienes tenían Ejecución.
INSERT INTO nextris.rel_user_permission (
    guid, user_id, permission_id, is_granted, created_on, updated_on
)
SELECT DISTINCT
    md5(up.user_id || ':worklist.confirm_execute'),
    up.user_id,
    target.guid,
    TRUE,
    NOW(),
    NOW()
FROM nextris.rel_user_permission up
JOIN nextris.ispermission source ON source.guid = up.permission_id
CROSS JOIN nextris.ispermission target
WHERE source.code IN ('tabs.execution.view', 'execution.view_pending', 'execution.execute')
  AND target.code = 'worklist.confirm_execute'
  AND up.is_granted = TRUE
ON CONFLICT (user_id, permission_id)
DO UPDATE SET is_granted = TRUE, updated_on = NOW();

-- Los permisos de páginas clínicas se migran respetando las restricciones de rol anteriores.
WITH eligible AS (
    SELECT DISTINCT up.user_id
    FROM nextris.rel_user_permission up
    JOIN nextris.ispermission source ON source.guid = up.permission_id
    JOIN nextris.tbuser u ON u.guid = up.user_id
    JOIN nextris.isrole r ON r.guid = u.idrole
    WHERE source.code = 'reports.view_writing'
      AND up.is_granted = TRUE
      AND lower(r.description) IN ('sysadmin', 'medico', 'médico', 'administrador')
), grants AS (
    SELECT user_id, 'reports.write' AS code FROM eligible
    UNION ALL
    SELECT user_id, 'dicom.studies.manage' AS code FROM eligible
)
INSERT INTO nextris.rel_user_permission (
    guid, user_id, permission_id, is_granted, created_on, updated_on
)
SELECT
    md5(grants.user_id || ':' || grants.code),
    grants.user_id,
    target.guid,
    TRUE,
    NOW(),
    NOW()
FROM grants
JOIN nextris.ispermission target ON target.code = grants.code
ON CONFLICT (user_id, permission_id)
DO UPDATE SET is_granted = TRUE, updated_on = NOW();

INSERT INTO nextris.rel_user_permission (
    guid, user_id, permission_id, is_granted, created_on, updated_on
)
SELECT
    md5(up.user_id || ':templates.manage'),
    up.user_id,
    target.guid,
    TRUE,
    NOW(),
    NOW()
FROM nextris.rel_user_permission up
JOIN nextris.ispermission source ON source.guid = up.permission_id
JOIN nextris.tbuser u ON u.guid = up.user_id
JOIN nextris.isrole r ON r.guid = u.idrole
CROSS JOIN nextris.ispermission target
WHERE source.code = 'reports.view_reports'
  AND target.code = 'templates.manage'
  AND up.is_granted = TRUE
  AND lower(r.description) IN ('sysadmin', 'medico', 'médico', 'administrador')
ON CONFLICT (user_id, permission_id)
DO UPDATE SET is_granted = TRUE, updated_on = NOW();

-- Gestión debe quedar visible para toda persona con plantillas o carga DICOM.
INSERT INTO nextris.rel_user_permission (
    guid, user_id, permission_id, is_granted, created_on, updated_on
)
SELECT DISTINCT
    md5(up.user_id || ':tabs.gestion.view'),
    up.user_id,
    gestion.guid,
    TRUE,
    NOW(),
    NOW()
FROM nextris.rel_user_permission up
JOIN nextris.ispermission child ON child.guid = up.permission_id
CROSS JOIN nextris.ispermission gestion
WHERE child.code IN ('templates.manage', 'dicom.studies.manage')
  AND gestion.code = 'tabs.gestion.view'
  AND up.is_granted = TRUE
ON CONFLICT (user_id, permission_id)
DO UPDATE SET is_granted = TRUE, updated_on = NOW();

UPDATE nextris.ispermission
SET is_active = FALSE
WHERE code IN (
    'tabs.execution.view',
    'execution.view_pending',
    'execution.execute',
    'tabs.reports.view',
    'reports.view_writing',
    'reports.view_reports'
);

COMMIT;
