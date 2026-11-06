BEGIN;

INSERT INTO nextris.ispermission (guid, code, module, action, description, is_active)
VALUES (
    'reports.notes.delete',
    'reports.notes.delete',
    'reports',
    'delete_notes',
    'Eliminar notas de estudios',
    TRUE
)
ON CONFLICT (code)
DO UPDATE SET
    module = EXCLUDED.module,
    action = EXCLUDED.action,
    description = EXCLUDED.description,
    is_active = TRUE;

COMMIT;
