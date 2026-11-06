"""Medical signature/stamp image validation without external catalogs."""
import io
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.services import medical_images as images
from PIL import Image

def picture(format='GIF', size=(20, 10)):
    stream = io.BytesIO()
    Image.new('RGB', size, 'white').save(stream, format=format)
    return stream.getvalue()


class ValidationTests(unittest.TestCase):
    def test_formats_and_limits(self):
        for extension, format in [('png', 'PNG'), ('jpg', 'JPEG'), ('jpeg', 'JPEG'), ('gif', 'GIF')]:
            content = picture(format)
            self.assertEqual(images.validate_medical_image(io.BytesIO(content), 'test.' + extension),
                             (content, extension))
        for content, name in [(b'bad', 'test.gif'), (picture(), 'test.png'), (picture(), 'test.svg'),
                              (b'x' * (images.MAX_BYTES + 1), 'test.gif'),
                              (picture(size=(4001, 4000)), 'large.gif')]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                images.validate_medical_image(io.BytesIO(content), name)


if __name__ == "__main__":
    unittest.main()
