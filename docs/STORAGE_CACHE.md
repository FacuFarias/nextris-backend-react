# Gestión de caché local

`GET /api/storage/overview` incluye `local_cache.studies` y `b2.studies`, contando estudios distintos con ubicaciones DICOM válidas. Un estudio en ambos almacenes locales cuenta una vez en la tarjeta.

`GET /api/storage/cache/studies?page=1&per_page=25&search=...` requiere `storage.view`. Agrupa las copias por estudio, incluye tamaños, ingreso, vencimiento, cobertura B2, protección de recepción y estado de la cola. La búsqueda acepta nombre DICOM, descripción, número de acceso o UID. El frontend renueva la vista cada diez segundos.

Los plazos provienen del archivo **vigente** `/opt/dcm4chee/backblaze/cache-policy.json`, también utilizado por el timer del PACS. Puede cambiarse la ruta con `NEXTRIS_CACHE_POLICY_PATH`. El backend interpreta las fechas internas como UTC y devuelve ISO con zona; el frontend presenta la zona configurada en la política. El vencimiento se calcula desde la primera copia local: 5 días corridos (120 h) para toda recepción inicial, sin depender de la fecha DICOM, y 24 h desde cada recuperación de B2. El acceso no renueva ese plazo. La cola, la protección de escrituras o la falta de respaldo pueden demorar el retiro; la presión de disco puede adelantarlo.

`DELETE /api/storage/cache/studies/<study_pk>` requiere `storage.view`, `storage.manage` y un cuerpo JSON `{"storage":"fs1","confirm":true}` (también admite `fs1-retrieve`). Los tokens de visor/compartidos y pacientes no tienen acceso. Se exige respaldo B2 válido del mismo tipo y tamaño para todos los objetos seleccionados; se bloquea durante recepción o borrado clínico. Se comprueban nuevamente identidades y respaldo antes de programar la operación. Los exportadores existentes `TTLRemoveInitial` y `TTLRemoveRetrieved` usan `storage:b2` y retiran únicamente el almacenamiento local correspondiente. No se borran archivos ni se escriben ubicaciones mediante SQL. El resultado `status=queued` es una solicitud asíncrona, no una confirmación de espacio liberado. Los fallos terminales pueden reintentarse desde el listado. El registro de servicio incluye actor, hash de estudio y almacenamiento.

## Instalación

Aplicar `deployment/sql/20261110_storage_cache.sql` a la base del RIS. Registra el permiso y lo asigna a administradores existentes que ya tenían `storage.view`; otros usuarios conservan su acceso de lectura. La plantilla de administrador incluye el nuevo permiso.

Permitir al usuario del servicio leer **solo** la política, sin acceso a las credenciales ni listado del directorio:

```bash
setfacl -m u:nextris:--x /opt/dcm4chee/backblaze
setfacl -m u:nextris:r-- /opt/dcm4chee/backblaze/cache-policy.json
```

Conservar la ACL si se reemplaza ese archivo al cambiar la política. No dar permisos de lectura sobre el resto del directorio. No se modifica la política, el timer, las claves B2 ni las imágenes.

## Verificación

`tests/test_storage_cache_integration.py` usa HTTP real y una base descartable `cdivet_storage_cache_*_test`. Requiere `DB_*`, `SECRET_KEY`/`JWT_SECRET_KEY`, `CACHE_TEST_API_URL=http://127.0.0.1:5005/api` y servidor aislado con las URL PACS/token dirigidas a `http://127.0.0.1:1`. Inserta copias sintéticas solo en la base de prueba. Comprueba conteos distintos, plazos, búsqueda/paginación, estados de cola, permisos y rechazos de eliminación. Nunca solicitar retiros de estudios reales durante estas pruebas. `tests/test_storage_monitor.py` conserva sus pruebas de proyección y semáforo.
