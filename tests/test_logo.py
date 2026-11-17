"""Tests the picture with the logo in a corner. Needs Pillow; neither ffmpeg nor a video."""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import logo  # noqa: E402
from common import DavarError  # noqa: E402

try:
    from PIL import Image
except ImportError:
    Image = None


@unittest.skipIf(Image is None, "Pillow is not installed")
class Corners(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.mark = Path(self.folder.name) / "mark.png"
        Image.new("RGB", (650, 150), (238, 39, 46)).save(self.mark)

    def tearDown(self):
        self.folder.cleanup()

    def test_the_logo_goes_where_it_was_asked(self):
        out = Path(self.folder.name) / "corner.png"
        found = {corner: logo.picture(self.mark, corner, 12, 1920, 1080, out) for corner in logo.CORNERS}
        self.assertEqual(found["top right"], (1920 - 48 - 230, 48, 1920 - 48, 48 + 53))
        self.assertEqual(found["top left"][:2], (48, 48))
        self.assertEqual(found["bottom left"][3], 1080 - 48)
        self.assertEqual(found["bottom right"][2], 1920 - 48)

    def test_the_picture_is_transparent_except_for_the_logo(self):
        out = Path(self.folder.name) / "corner.png"
        box = logo.picture(self.mark, "top left", 10, 960, 540, out)
        image = Image.open(out)
        self.assertEqual(image.size, (960, 540))
        self.assertEqual(image.getchannel("A").getbbox(), box)

    def test_bad_choices_are_refused(self):
        out = Path(self.folder.name) / "corner.png"
        with self.assertRaises(DavarError):
            logo.picture(self.mark, "middle", 12, 1920, 1080, out)
        with self.assertRaises(DavarError):
            logo.picture(self.mark, "top right", 80, 1920, 1080, out)
        with self.assertRaises(DavarError):
            logo.picture(Path(self.folder.name) / "none.png", "top right", 12, 1920, 1080, out)


if __name__ == "__main__":
    unittest.main()
