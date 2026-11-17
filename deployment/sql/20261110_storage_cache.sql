-- Separate cache-management grant; existing read-only staff keep read-only access.
INSERT INTO nextris.ispermission(guid,code,module,action,description,is_active)
VALUES (gen_random_uuid()::text,'storage.manage','storage','manage',
        'Eliminar copias locales de caché con respaldo en Backblaze B2',true)
ON CONFLICT(code) DO UPDATE SET description=excluded.description,is_active=true;
INSERT INTO nextris.rel_user_permission(guid,user_id,permission_id,is_granted)
SELECT gen_random_uuid()::text,u.guid,p.guid,true
FROM nextris.tbuser u JOIN nextris.isrole r ON r.guid=u.idrole
CROSS JOIN nextris.ispermission p
WHERE p.code='storage.manage' AND lower(r.description) IN ('admin','administrador')
AND EXISTS(SELECT 1 FROM nextris.rel_user_permission up JOIN nextris.ispermission vp ON vp.guid=up.permission_id
           WHERE up.user_id=u.guid AND up.is_granted AND vp.code='storage.view' AND vp.is_active)
ON CONFLICT(user_id,permission_id) DO NOTHING;
