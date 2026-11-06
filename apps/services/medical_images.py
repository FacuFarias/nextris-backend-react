"""Validation shared by medical signature/stamp uploads and the batch importer."""

from io import BytesIO

from PIL import Image, UnidentifiedImageError


MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000
FORMATS = {'png': 'PNG', 'jpg': 'JPEG', 'jpeg': 'JPEG', 'gif': 'GIF'}


def validate_medical_image(stream, filename):
    """Return original bytes and extension after verifying the complete image."""
    extension = str(filename).rsplit('.', 1)[-1].lower()
    if extension not in FORMATS:
        raise ValueError('Se admite PNG, JPEG o GIF')
    content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError('La imagen supera los 5 MB')
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format != FORMATS[extension]:
                raise ValueError('El contenido no coincide con el formato del archivo')
            if image.width * image.height > MAX_PIXELS:
                raise ValueError('La imagen supera los 16 millones de píxeles')
            image.verify()
        # verify() does not decode pixel data for every format.
        with Image.open(BytesIO(content)) as image:
            image.load()
    except (OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError('El archivo no es una imagen válida') from exc
    return content, extension
