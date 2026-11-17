from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

try:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    from pptx.util import Inches
except ImportError:
    Presentation = None
    Inches = None
    MSO_SHAPE_TYPE = None

from project_skripsi.pptx.geometry import add_freeform_shape, set_picture_geometry, tag_morph_object


@unittest.skipIf(Presentation is None, "Install the optional slides extra to test native geometry")
class NativeGeometryTests(unittest.TestCase):
    def setUp(self):
        self.presentation = Presentation()
        self.slide = self.presentation.slides.add_slide(self.presentation.slide_layouts[6])

    def test_adds_editable_freeform_and_tags_name(self):
        shape = add_freeform_shape(
            self.slide,
            [(1, 1), (3, 1), (2.5, 3), (1, 1.5)],
            name="district border",
            fill="245E59",
            line="4C9E8E",
        )
        self.assertEqual(shape.name, "!!district-border")
        self.assertIsNotNone(shape._element.spPr.custGeom)

    def test_picture_geometry_stays_a_picture(self):
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/"
            "pL8AAAAASUVORK5CYII="
        )
        with tempfile.TemporaryDirectory() as temp:
            asset = Path(temp) / "pixel.png"
            asset.write_bytes(png)
            picture = self.slide.shapes.add_picture(str(asset), Inches(1), Inches(1), Inches(3), Inches(3))
        set_picture_geometry(picture, "ellipse")
        tag_morph_object(picture, "mountain reveal")
        self.assertEqual(picture.shape_type, MSO_SHAPE_TYPE.PICTURE)
        self.assertEqual(picture._element.spPr.prstGeom.get("prst"), "ellipse")
        self.assertEqual(picture.name, "!!mountain-reveal")

    def test_rejects_unknown_picture_geometry(self):
        picture = self.slide.shapes.add_shape(1, Inches(1), Inches(1), Inches(1), Inches(1))
        with self.assertRaises(ValueError):
            set_picture_geometry(picture, "pentagon-ish")

    def test_tags_non_empty_name(self):
        shape = self.slide.shapes.add_shape(1, Inches(1), Inches(1), Inches(1), Inches(1))
        with self.assertRaises(ValueError):
            tag_morph_object(shape, "   ")


if __name__ == "__main__":
    unittest.main()
