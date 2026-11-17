# Migración de CDIVET

Las ramas `cdivet` de frontend y backend conservan la versión activa y descienden de `version/veterinaria`. El paquete privado asociado contiene los datos y la configuración real de la instalación; GitHub contiene solamente código, recursos de marca y ejemplos sin secretos.

## Configuración pública

`deployment/cdivet/backend.env.example` conserva los nombres de las variables de producción con secretos vacíos. El perfil de pacientes, flujo veterinario, orígenes, marca y rutas públicas conservan sus valores. El frontend usa `deployment/cdivet.env.example` de su repositorio.

`deployment/cdivet/` también incluye los servicios systemd activos, Nginx y la política de caché: cinco días para recepción inicial y 24 horas para recuperación desde B2. Los catálogos de TC y la plantilla de informe general están incluidos como SQL repetible.

## Recuperación de datos

Para una copia exacta, restaurar el dump completo del paquete privado en PostgreSQL 17 compatible, junto con roles y archivos privados. El dump incluye los esquemas RIS, el archivo histórico y el catálogo PACS. Seguir el inventario y las instrucciones del paquete privado para servicios, almacenamiento, visor y credenciales.

No inicializar una base vacía con migraciones sobre una restauración completa: el dump ya contiene el esquema y los datos actuales. Las migraciones versionadas se conservan para futuras actualizaciones.

Las imágenes del catálogo PACS están en Backblaze B2; la recuperación del dump no recupera por sí sola los objetos DICOM. El paquete privado incluye la copia de los objetos disponibles y su inventario para conservar su correspondencia con el catálogo.

Verificar los SHA-256 del paquete y los conteos restaurados antes de cambiar DNS. Aislar la red del entorno de comprobación y mantener detenidos los workers de ingestión, borrado y caché hasta terminar la validación; sus configuraciones pueden apuntar al PACS original.

El respaldo es una instantánea. Si CDIVET recibe cambios después, tomar una copia final con las escrituras suspendidas antes del cambio definitivo de servidor.
