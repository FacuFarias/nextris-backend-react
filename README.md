# CDIVET — NextRIS Backend

Snapshot de la instalación de `https://cdivet.cloud`, rama `cdivet`, derivada de `version/veterinaria`.
Usar con [frontend `cdivet`](https://github.com/FacuFarias/nextris-front-react/tree/cdivet).

Incluye los cambios activos de órdenes veterinarias automáticas, referencias DICOM, reasignación de animales, informes y almacenamiento/caché.

- [Instalación general](docs/GENERAL_EDITION.md)
- [Edición veterinaria](docs/VETERINARY_EDITION.md)
- [Configuración y migración CDIVET](docs/CDIVET_MIGRATION.md)

La configuración pública está en `deployment/cdivet/`. Las credenciales, la base de datos y los archivos privados se transfieren con el paquete privado de migración. No se generan cuentas ni se cargan datos reales al clonar GitHub.
