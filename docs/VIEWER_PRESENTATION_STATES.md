# PR: autoría y eliminación

Los PR nuevos se envían a `/api/viewer/presentation-states/<studyUID>` con el JWT
limitado del handoff de NextViewer. Se exige personal activo, `images.view` (o
Sysadmin) y coincidencia con el estudio de la sesión. El servidor valida GSPS y
las imágenes referenciadas, asigna el autor desde `tbuser`, escribe
`ContentCreatorName` en DICOM y verifica el acuse STOW del SOP exacto.

La tabla `nextris.tb_viewer_presentation_state` conserva el propietario, el nombre
al crear, fecha, confirmación PACS y autor/fecha de eliminación. Se reserva el
propietario antes de STOW para conservarlo si se pierde el acuse remoto.
No se admite apropiarse de un SOP que ya existe en PACS.

El creador puede eliminar sus propios PR. Sysadmin y el permiso asignable
`images.presentation_states.delete_any` permiten eliminar PR de otros usuarios y
los antiguos sin autor. Los permisos se consultan en cada solicitud. La operación
rechaza exclusivamente una instancia GSPS mediante IOCM `113001`, conserva una
marca de eliminación y nunca modifica tablas PACS directamente ni permite borrar
instancias de imagen a través de esta API.

Los PR anteriores muestran «Autor no registrado»; no se infiere ni se adjudica un
propietario. El listado del visor incorpora el autor y la capacidad de eliminación
que calcula el servidor. Cancelar o fallar una eliminación conserva el registro.
El proxy DICOM del visor admite únicamente GET/HEAD; las escrituras pasan por
NextRIS. Las sesiones sin handoff NextRIS pueden consultar PR, pero no gestionarlos.

## Despliegue

1. Aplicar `deployment/migrations/20261023_viewer_presentation_states.sql`.
2. Sincronizar el catálogo mediante `seed_permissions` (no concede el nuevo permiso
   automáticamente a usuarios comunes).
3. Recargar backend y publicar assets/index del visor y su `nginx.conf`.
4. Reabrir el visor desde NextRIS para cargar la nueva aplicación.

## Verificación

- `venv/bin/python tests/test_presentation_states.py`: autorización, autor no
  falsificable, referencias, acuse STOW y rechazo PACS simulado.
- `venv/bin/python tests/test_viewer_clinical_access.py`: contrato de handoff.
- En el visor, `npm test` y `npm run build`.
- Las pruebas aisladas no eliminan PR clínicos ni crean pacientes de prueba en PACS.
