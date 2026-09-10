# Campos canónicos de reportes

Los reportes y plantillas utilizan como contrato canónico únicamente:

- `study_reason`: Razón del estudio.
- `content`: Contenido consolidado.
- `conclusion`: Conclusión.

Las columnas y propiedades `findings`, `techniques`/`technique`,
`impressions`/`impression` y `conclusions` son legacy/deprecadas. Se conservan
para compatibilidad de lectura; las escrituras nuevas sólo actualizan los tres
campos canónicos. Las respuestas mantienen alias (`findings=content`,
`conclusions=conclusion`, técnicas e impresiones vacías) para clientes antiguos.

La migración `deployment/migrations/20260903_canonical_report_fields.sql` es
idempotente y realiza el backfill histórico con encabezados HTML explícitos.
Los reportes no migrados se resuelven mediante el fallback común en
`apps/services/report_fields.py`; un valor canónico explícitamente vacío no
reactiva el contenido legacy.
