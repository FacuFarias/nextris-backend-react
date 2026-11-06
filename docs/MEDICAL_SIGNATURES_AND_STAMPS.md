# Firmas y sellos

Los profesionales administran sus imágenes de firma y sello desde su perfil médico.
Se aceptan PNG, JPEG y GIF verificados, hasta 5 MB y 16 millones de píxeles. Los
archivos se guardan en `media/firmas`, que no se publica en Git.

La firma del documento corresponde al `iduser` del informe firmado y respeta
`firma_habilitada`. Las imágenes se leen únicamente desde los directorios permitidos
y se convierten a PNG para el documento. No se consultan catálogos externos.

La edición de perfiles y la firma requieren sus respectivos permisos. No se incluyen
archivos de firmas de una institución ni importaciones de profesionales externos.

Validación: `python tests/test_medical_images.py` y la suite `test_general_edition.py`.
