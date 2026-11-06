# Verificación de la edición para una institución

Bases conservadas: backend `d03b6d8` (`main`) y frontend `4770752` (`ui2`). Los cambios
locales se trasladaron en copias aisladas mediante comparación de tres vías, sin
cambiar las ramas ni archivos de las instalaciones originales.

## Backend y migraciones

- Compilación de los módulos Python y comprobación de sintaxis de instaladores: OK.
- PostgreSQL 17.4 dcm4chee descartable, separado de la base clínica: instalación de
  esquema y secuencia de migraciones, repetición y rechazo de múltiples instituciones.
- Diez pruebas integradas: salud y ausencia de rutas/esquema de la integración
  retirada; informe/PDF local; pertenencia y visibilidad; APIs generales; firma;
  precondiciones de migración; login/configuración; ORM/ORU con transporte simulado;
  cancelación; preservación de permisos, alias y revocaciones posteriores.
- 99 pruebas complementarias aprobadas: campos de informes (8), imágenes de firma
  (1), verificación de email (15), sesiones asumidas (9), permisos (12), paginación
  de pacientes (7), Presentation States (12), operaciones de imágenes (27), sesión
  clínica del visor (3), identidad del handoff (1), hanging protocols (4).
- Las pruebas usaron datos sintéticos, emails simulados y transporte HL7 simulado.
  No se contactaron sistemas de informes externos ni se activó el worker de imágenes.

## Frontend

TypeScript y compilación Vite: aprobados. Navegador con APIs interceptadas:
lectura de informes y errores de disponibilidad en escritorio/móvil, lectura desde
el enlace clínico de informes, sanitización HTML, identidad institucional, permisos
por usuario y enlaces compartidos de imágenes/estudio desde lista y editor.

ESLint global **no pasa**: 465 errores y 22 advertencias. El código local de partida
ya presentaba 446 errores y 21 advertencias; además se conservaron los módulos de
ejecución de la rama general, que también traían hallazgos de lint. Esos archivos de
ejecución mantienen el contenido de `ui2` salvo normalización de saltos de línea.
Los cinco componentes de lectura/firma/configuración creados o adaptados para esta
edición no presentan errores de ESLint. Esta actualización no declara resuelta la
deuda global de lint.

Los avisos de tamaño de chunks de Vite permanecen. No impiden la compilación.

## Despliegue

Las comprobaciones no aplicaron migraciones en la base de la instalación ni
reiniciaron servicios existentes. La publicación actualiza los repositorios;
el despliegue y la migración de cada instalación siguen la [guía](GENERAL_EDITION.md).
