# Roles y permisos — edición para una institución

La política está centralizada en `apps/permission_policy.py`. El rol es una plantilla
para altas y cambios de rol. Los permisos persistidos son la autoridad efectiva.
La única excepción es Sysadmin, que conserva `*` y no tiene casillas editables.
Las ubicaciones, la propiedad de recursos y los requisitos clínicos de las acciones
siguen aplicándose. Los pacientes permanecen en un ámbito separado.

## Catálogo

Se normalizan los alias `tabs.patients.view` → `patients.view`,
`tabs.images.view` → `images.view` y `tabs.distribution.view` → `distribution.view`.
Los alias históricos de Ejecución/Redacción también siguen aceptándose al guardar.
Los códigos desconocidos, módulos ocultos y `*` no son asignaciones persistibles.
Una lista vacía revoca todos los permisos individuales y no activa la plantilla.

`NEXTRIS_DISABLED_MODULES` controla la visibilidad del despliegue; su valor
predeterminado es vacío. Cuando se configuran módulos deshabilitados se ocultan
pantallas, accesos directos, promociones, agendas y permisos; se conservan las
integraciones y los datos. El portal de pacientes sigue activo.
El frontend recibe `disabled_modules` desde `/api/config/me/modules` y utiliza
el mismo valor predeterminado mientras carga para evitar mostrar módulos ocultos.

Los permisos de Gestión administrativa, configuración, usuarios y permisos son
distintos. Plantillas y carga DICOM solo hacen visible su propia entrada en Gestión.
El permiso explícito habilita una función para cualquier rol del personal.
Médico incluye firmar y desfirmar informes, sin Gestión administrativa. Técnico
incluye cargar/vincular/desvincular DICOM. Borrar imágenes/notas e impersonar no
están incluidos en las plantillas comunes.

## Interfaces

- `GET /api/config/roles`: agrega `default_permissions: string[]` por rol.
- `GET /api/config/me/modules`: agrega `disabled_modules: string[]` y filtra
  `module_codes` según la configuración del despliegue.
- `POST /api/config/users` y `PUT/PATCH /api/config/users/{id}`: aceptan
  `permission_codes: string[]`. Usuario, rol y permisos se guardan en una transacción.
  Si se omite la propiedad, se usa la plantilla al crear/cambiar el rol; con el mismo
  rol se conserva la selección anterior. La lista vacía se respeta.
- Los endpoints dedicados `GET/PUT /api/config/users/{id}/permissions` se conservan;
  `effective_permissions` coincide con la sesión, incluido `*` para Sysadmin.
- Crear usuarios requiere `users.manage` y `users.permissions.manage`. Editar datos
  de perfil requiere `users.manage`; cambiar rol o enviar `permission_codes` exige
  además `users.permissions.manage`. El editor independiente de permisos permite
  operar con `users.permissions.manage` sin conceder gestión de perfiles.
- Las lecturas del catálogo y selección del usuario admiten también `users.manage`
  para editar perfiles sin modificar sus permisos. Los metadatos operativos de
  configuración siguen disponibles a los formularios del personal.

## Migración y relevamiento

Ejecutar desde el backend, con su entorno virtual y `.env`. No importa Flask ni
inicia workers. Antes de aplicar debe estar desplegado el archivo de política.
Los informes contienen autorizaciones del personal: guardarlos fuera de `/var/www`.

```bash
venv/bin/python deployment/migrations/20261021_permission_templates.py \
  --report /ruta/privada/permissions-preview.json
venv/bin/python deployment/migrations/20261021_permission_templates.py \
  --apply --report /ruta/privada/permissions-applied.json
```

La simulación no escribe en la base. La aplicación conserva los grants explícitos
activos y materializa la herencia anterior congelada en el script, normaliza alias,
retira permisos no disponibles y verifica el resultado antes del commit. No aplica
las nuevas plantillas a las cuentas existentes. Los informes incluyen antes/después
por usuario, conteos por rol y una copia completa de las tablas anteriores.

La marca `nextris.permission_policy_migration` guarda la versión y el relevamiento
original dentro de la misma transacción. Ejecutar otra vez devuelve
`already_applied` y el estado actual: nunca restaura permisos revocados después.
El lock transaccional evita aplicaciones simultáneas.

Orden de despliegue: migración → reinicio del backend → frontend. En este servidor
el servicio real es `nextris-backend.service`; el frontend activo es Vite mediante
`nextris-front.service`. Las sesiones recargan permisos al restaurarse, al recuperar
foco y cada 60 segundos mientras la pestaña está visible; las APIs validan los
grants guardados en cada solicitud.

Para revertir, coordinar la restauración del código previo con una copia previa de
`ispermission` y `rel_user_permission`. El JSON de auditoría guarda también esas
filas. No volver a aplicar la migración como mecanismo de restauración: su marca
impide sobreescribir cambios posteriores de permisos.

## Validación

```bash
NEXTRIS_PERMISSION_DB_TESTS=1 venv/bin/python tests/test_permission_templates.py
cd /var/www/nextris-front-react
npm run typecheck
npm run build
npm run lint
npm run test:permissions
```

Las pruebas PostgreSQL usan un schema temporal aleatorio y lo eliminan al finalizar;
no escriben en tablas clínicas. Sin la variable se ejecutan solo las pruebas sin DB.
La prueba de navegador usa Playwright (`npx playwright install --with-deps chromium` si falta
el navegador) y un frontend en :5173, configurable mediante `PERMISSION_TEST_BASE`.
Intercepta todas las APIs con datos sintéticos, bloquea conexiones externas y nunca
crea usuarios reales. Comprueba las cinco plantillas, cambios de rol, selección vacía,
excepciones existentes, fallos/reintentos y pantallas ocultas.

Para comprobar exactamente el artefacto compilado, iniciar `npm run preview --
--host 127.0.0.1 --port 5187` y ejecutar la prueba con
`PERMISSION_TEST_BASE=http://127.0.0.1:5187 npm run test:permissions`. Esto evita
recargas automáticas de Vite mientras se prueban cambios de sesión.

## Ajuste clínico posterior

`deployment/migrations/20261021_clinical_role_adjustments.py --apply --report
/ruta/privada/clinical-roles.json` aplica la corrección a las cuentas existentes:
revoca Gestión administrativa y concede Desfirmar a médicos; concede carga DICOM
a técnicos. Conserva los demás permisos y guarda su propia marca idempotente.

## Compartir desde Lista de trabajo

`worklist.share` («Compartir imágenes y estudio») habilita el menú de clic derecho
**Compartir → Imágenes / Estudio**. Estudio genera el Case Link existente. Se incluye
por defecto para todos los roles del personal, incluidos roles personalizados;
las selecciones explícitas de permisos se respetan y el permiso puede revocarse.
El portal de pacientes conserva sus permisos y endpoints separados.

Los endpoints `POST /api/general/viewer-share-links` y
`POST /api/reports/{exam_id}/case-link` aceptan `worklist.share` o el permiso
existente `images.share_link`. Este último conserva los accesos desde otras
pantallas y no hace visible el nuevo submenú por sí solo.

Conceder el permiso a las cuentas existentes sin reemplazar sus otros permisos:

```bash
venv/bin/python deployment/migrations/20261102_worklist_share.py --report /ruta/privada/share-preview.json
venv/bin/python deployment/migrations/20261102_worklist_share.py --apply --report /ruta/privada/share-applied.json
```

La migración registra el permiso y verifica las asignaciones en una transacción.
Su marca `20261102_worklist_share_v1` impide restaurar revocaciones posteriores al
ejecutarla de nuevo. Después se reinicia el backend para cargar la política nueva.
Las sesiones abiertas actualizan sus permisos con el refresco habitual.

Validación del menú con APIs interceptadas y datos sintéticos:
`npm run test:worklist-share` desde el frontend; `SHARE_TEST_BASE` permite cambiar
la URL del frontend (por defecto `http://127.0.0.1:5173`).
