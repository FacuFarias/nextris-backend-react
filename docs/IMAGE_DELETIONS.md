# Gestión de eliminación de imágenes

En `/imagenes`, el permiso asignable `images.delete` habilita «Eliminar imágenes».
Sysadmin accede mediante `*`. Los permisos de visualización o carga no conceden
eliminación. Los endpoints de gestión verifican el permiso y la propiedad de la
operación; sysadmin puede consultar operaciones de otros usuarios.

Las nuevas operaciones eliminan permanentemente los objetos seleccionados del
PACS, incluyendo todos los cuadros de objetos multiframe. Conservan el paciente,
los exámenes, informes, asociaciones y archivos originales de cargas manuales.
La interfaz advierte que la eliminación no se puede deshacer y solicita una
confirmación explícita. Al finalizar no quedan registros de rechazo que impidan
volver a recibir las mismas imágenes.

Los estudios completos se eliminan con `DELETE /aets/{aet}/rs/studies/{uid}`.
Para series e imágenes, la selección exacta se marca con el código privado
`NEXTDEL^99NEXTRIS` y se purga mediante la API oficial del PACS. Este código se
reserva exclusivamente a eliminaciones permanentes confirmadas de NextRIS;
nunca se ejecuta una purga global de los motivos clínicos estándar. Las notas
técnicas de esta operación también se eliminan.

La purga física de almacenamiento es asíncrona (intervalo actual de PACS: cinco
minutos). La operación permanece `running` hasta que desaparecen las ubicaciones
originales del almacenamiento. Un rechazo lógico por sí solo nunca cuenta como
eliminación permanente completada. Los PK originales impiden que un reintento
elimine una carga posterior que reutilice los mismos UID.

## API

Todos los endpoints de gestión requieren JWT y `images.delete`:

- `GET /api/dicom/studies/<pk>/series?page=1&per_page=25`
- `GET /api/dicom/studies/<pk>/series/<uid>/instances?page=1&per_page=25`
- `GET /api/dicom/studies/<pk>/series/<uid>/instances/<sop>/thumbnail`
- `GET /api/dicom/rejection-reasons`
- `POST /api/dicom/image-deletions/preview`
- `POST /api/dicom/image-deletions/<id>/execute`
- `GET /api/dicom/image-deletions/<id>?page=1` (50 resultados por página)

Ejemplo de previsualización:

```json
{"study_pk":123,"level":"instances","instances":[{"series_uid":"1.2.3","sop_uid":"1.2.3.4"}]}
```

También admite `level: "study"`, o `level: "series"` y `series_uids: ["1.2.3"]`.
La respuesta incluye operación, imágenes y exámenes afectados. La confirmación:

```json
{"rejection_code":"113001","justification":"Duplicado verificado","permanent":true}
```

La respuesta incluye `deletion_mode: "permanent"`. La confirmación sin
`permanent: true` se rechaza con `409`. El motivo se conserva para auditoría en
NextRIS y no cambia las políticas de retención del PACS.

Motivos permitidos: calidad (`113001`), seguridad (`113037`) y worklist incorrecta
(`113038`), siempre que estén configurados en PACS. Las previsualizaciones vencen
a los diez minutos y se invalidan si cambia la selección o los exámenes afectados.
La ejecución devuelve `202`. Estados: `preview`, `queued`, `running`, `completed`,
`partial`, `failed`. Confirmar nuevamente una operación en curso es idempotente.
Reintentar una operación permanente parcial/fallida conserva sus UIDs, motivo y justificación;
únicamente reencola objetivos fallidos.

## Operación y despliegue

1. Aplicar `deployment/migrations/20261020_image_deletions.sql` antes de cargar el
   backend nuevo. Es idempotente e instala las vistas compartidas de disponibilidad.
2. Instalar `deployment/config/nextris-image-deletions.service` en systemd y ejecutar
   `systemctl enable --now nextris-image-deletions.service`.
3. Ejecutar `venv/bin/python deployment/configure_image_rejection_view.py --apply`.
   Actualiza exclusivamente las notas ocultas de `hideRejected`, conserva las
   políticas de purga y guarda la lista anterior en `/tmp/nextris-rejection-view-*.json`.
   Sin `--apply`, únicamente informa diferencias.
4. Aplicar `deployment/migrations/20261027_permanent_image_deletions.sql` y ejecutar
   `venv/bin/python deployment/configure_permanent_image_deletions.py --apply`.
   El script configura únicamente el código privado, oculta sus notas técnicas y
   guarda un respaldo sin credenciales. Sin `--apply` informa las diferencias.
   Conserva las políticas y plazos de los rechazos clínicos estándar.
5. Reiniciar `nextris-image-deletions.service`, recargar `nextris-backend.service`
   y ejecutar `npm run build` en el frontend. Vite sirve también el código actualizado.

La migración conserva como `logical` las operaciones anteriores. No convierte
rechazos históricos en eliminaciones permanentes. Las previsualizaciones y los reintentos de bajas lógicas anteriores requieren
volver a revisar la selección antes de ejecutar una operación permanente nueva.

El trabajador utiliza el `.env` del backend y las credenciales técnicas existentes
`PACS_KEYCLOAK_*`, `PACS_STOW_URL` y `DB_*`. `PACS_VERIFY_TLS` conserva el valor por
defecto actual de la integración (`false`); puede establecerse en `true` cuando el
endpoint interno tiene un certificado verificable.

```bash
venv/bin/flask --app apps.image_worker image-deletion-worker --once
systemctl status nextris-image-deletions.service
journalctl -u nextris-image-deletions.service -f
```

Las operaciones y objetivos quedan en `nextris.tbimage_deletion` y
`nextris.tbimage_deletion_target`. Un bloqueo de sesión por StudyInstanceUID impide
dos trabajadores simultáneos sobre el mismo estudio. Ante reinicios se retoman los
pendientes y se comprueba el estado del índice y del almacenamiento antes de
repetir una petición ambigua. La cola rota entre estudios para que una purga física
pendiente no bloquee las operaciones de otros estudios. Si llegan nuevos objetos
antes de ejecutar un borrado completo, se requiere una nueva selección.

La disponibilidad se reconcilia tras cada objetivo y en un hilo independiente cada
30 segundos. Se excluyen instancias rechazadas y notas IOCM. Al quedar cero imágenes
se actualiza `isimage`, se revocan enlaces exclusivos de imágenes y caducan handoffs
pendientes; los Case Links mantienen el informe. Los accesos al visor comprueban
disponibilidad de nuevo. El gateway público admite únicamente lectura y OPTIONS.

## Validación

```bash
venv/bin/python tests/test_image_deletions.py
venv/bin/python tests/test_permanent_image_deletions_integration.py --synthetic
```

La primera suite trabaja sin red ni base de datos y verifica permisos, confirmación
explícita, selección, reintentos, respuestas ambiguas y protección de nuevas cargas.
La segunda requiere PACS y trabajador activos y usa exclusivamente objetos
sintéticos `NRDEL*`, JWT aislado y el blueprint de gestión real. Verifica los tres
niveles de eliminación, espera la purga física, conserva informes guardados y tres
formas de asociación, y vuelve a cargar exactamente los mismos SOP Instance UID.
Al terminar elimina los estudios sintéticos del PACS y conserva la auditoría de
NextRIS; los archivos de limpieza se retiran por el planificador de almacenamiento.
La suite anterior `test_image_deletions_integration.py` documenta el comportamiento
histórico de baja lógica y ya no corresponde al flujo de confirmación permanente.
