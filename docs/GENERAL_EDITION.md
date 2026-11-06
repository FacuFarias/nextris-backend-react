# NextRIS para una institución

Backend `main`, junto con frontend `ui2`. Esta edición incorpora pacientes y portal,
permisos por usuario, sesiones asumidas con auditoría, redacción y plantillas,
firmas/sellos, informes locales, PDF bajo demanda, enlaces compartidos, visor y
administración de imágenes. La configuración institucional es una única fila de
`nextris.app_config`; las ubicaciones representan sedes o equipos de esa institución.

## Instalación nueva

Requisitos: Python 3.12, PostgreSQL con el esquema `public` de dcm4chee 5.34 y Node
compatible con Vite 7. El PACS se instala por separado. Los reportes estructurados
requieren además el esquema `dicom_sr` del procesador de reportes estructurados.

1. Crear un entorno virtual e instalar `requirements.txt`.
2. Copiar `.env.example` a `.env` y definir la base, secretos JWT, orígenes públicos,
   PACS y visor. Los ejemplos no contienen credenciales de una instalación.
3. Ejecutar primero `python deployment/migrate_general.py --initialize` para revisar
   la precondición; después `python deployment/migrate_general.py --initialize --apply`.
4. Ejecutar `python deployment/create_admin.py --username admin` y escribir la
   contraseña cuando se solicite. El esquema no incluye cuentas ni contraseñas iniciales.
5. Configurar nombre, correo y HL7 desde Configuración → Institucional.
6. Instalar y compilar el frontend `ui2`; configurar el proxy `/api` al backend.

## Actualización desde la edición general

Hacer un respaldo de la base y probar la secuencia en una copia antes del despliegue.
Detener escrituras durante la conversión y desplegar backend/frontend como pareja.

```bash
python deployment/migrate_general.py
python deployment/migrate_general.py --apply
```

El primer comando solo verifica precondiciones y muestra la secuencia. El segundo
registra las migraciones aplicadas en `general_schema_migration`; repetirlo omite las
ya aplicadas. Las migraciones incluyen revocación JWT, informes canónicos, visibilidad
del portal, enlaces, firmas, verificación de email, estados locales e imágenes.

La conversión rechaza **más de una institución o dominio de pacientes antes de
escribir**. Se requiere una migración explícita de los datos elegidos para ese caso.
Las tablas antiguas quedan archivadas: no se borran pacientes, instituciones ni
permisos personalizados. Los permisos personalizados se conservan y la herencia histórica de los roles de la
edición general se persiste una sola vez, con auditoría. La marca impide restaurar
permisos revocados en ejecuciones posteriores. Los scripts históricos de concesión
masiva no se ejecutan automáticamente.

Las migraciones no contactan el PACS ni activan el servicio de eliminación. Los
triggers de importación automática desde PACS son una instalación opcional separada;
no se aplican correcciones históricas de datos ni plantillas institucionales.

## Contratos y configuración

- `GET /api/reports/<examen>/view`: informe firmado local, `data.source = nextris`,
  secciones canónicas y documento con membrete/firma del autor almacenado.
- `GET /api/reports/<examen>/pdf`: PDF generado en memoria; requiere JWT y permiso
  de lectura clínica o pertenencia del paciente. No escribe archivos de informes.
- `/api/pdfs/by-exam/<examen>` también requiere JWT. Los enlaces públicos usan los
  tokens limitados a estudio de `/api/s/<codigo>/report`, con expiración/revocación.
- Los enlaces clínicos de Nexi usan `/informes/<examen>` en el frontend y mantienen la sesión autenticada.
- El portal recibe JSON del informe. Pertenencia, visibilidad, estado finalizado y
  cancelación se verifican antes de devolver contenido. Un borrador, informe vacío,
  oculto o cancelado no está disponible para el paciente.
- `/api/patients/<id>/history/combined` se conserva por compatibilidad y devuelve
  exclusivamente entradas locales, con `source = nextris`.
- `GET /api/app-config` publica identidad institucional; `/app-config/settings` y
  `PUT /app-config` requieren permiso de configuración. No se devuelven contraseñas
  SMTP ni tokens HL7 guardados. Cambiar una contraseña/token requiere enviar su valor.
- `/api/integration/orders` conserva el cuerpo de órdenes; requiere recepción ORM
  habilitada y `Authorization: Bearer <token institucional>`, incluso sin nombre
  institucional en el cuerpo. Las rutas `/api/external/` requieren `EXTERNAL_API_TOKEN`.
- Los envíos ORU conservan los contratos generales, utilizan los campos canónicos
  del informe y los destinos `HL7_HOST`, `HL7_EXECUTION_PORT`, `HL7_REPORT_PORT`.
- La apertura del visor usa `DICOM_VIEWER_URL`; STOW-RS y credenciales PACS se
  configuran por separado. Nunca se requiere un servicio externo de informes.

La configuración de módulos puede restringirse con `NEXTRIS_DISABLED_MODULES`.
El servicio opcional de imágenes se distribuye como ejemplo para `/opt/nextris/backend`
y usuario `nextris`; debe configurarse y activarse de forma explícita por separado.

## Comprobación

```bash
python -m compileall -q apps
# Solo sobre un PostgreSQL dcm4chee descartable, nunca una base clínica:
NEXTRIS_GENERAL_TESTS=1 DB_NAME=nextris_test python -m unittest discover -s tests -p test_general_edition.py
```

Definir también DB_HOST, DB_PORT, DB_USER y DB_PASS de la base de prueba. Las pruebas
usan pacientes sintéticos y bloquean solicitudes HTTP salientes. En frontend ejecutar
`npm ci`, `npm run typecheck`, `npm run build`, `npm run lint` y las pruebas de navegador
con APIs interceptadas en un servidor de prueba. No usar los scripts HTTP históricos
contra una instalación en funcionamiento para validar esta actualización.
