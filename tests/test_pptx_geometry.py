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

from project_skripsi.pptx.geometry import (
    add_freeform_shape,
    set_picture_custom_path,
    set_picture_freeform_geometry,
    set_picture_geometry,
    tag_morph_object,
)


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



@unittest.skipIf(Presentation is None, "Install the optional slides extra to test native geometry")
class PictureFreeformGeometryTests(unittest.TestCase):
    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    P = "http://schemas.openxmlformats.org/presentationml/2006/main"
    PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/"
        "pL8AAAAASUVORK5CYII="
    )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.image_path = Path(self.temp.name) / "pixel.png"
        self.image_path.write_bytes(self.PNG)
        self.presentation = Presentation()
        self.slide = self.presentation.slides.add_slide(self.presentation.slide_layouts[6])
        self.picture = self.slide.shapes.add_picture(
            str(self.image_path), Inches(1), Inches(1), Inches(3), Inches(2)
        )

    def test_custom_geometry_keeps_picture_editable(self):
        points = [(0.5, 0.0), (1.0, 0.35), (0.82, 1.0), (0.18, 0.92), (0.0, 0.4)]
        set_picture_freeform_geometry(self.picture, points)
        tag_morph_object(self.picture, "river-cutout")
        self.assertEqual(self.picture.shape_type, MSO_SHAPE_TYPE.PICTURE)
        self.assertEqual(self.picture.name, "!!river-cutout")
        self.assertIsNone(self.picture._element.spPr.prstGeom)
        geom = self.picture._element.spPr.custGeom
        self.assertIsNotNone(geom)
        path = geom.pathLst.path_lst[0]
        self.assertEqual(path.get("w"), "21600")
        self.assertEqual(path.get("h"), "21600")
        self.assertEqual(len(path.findall(f"{{{self.A}}}moveTo")), 1)
        self.assertEqual(len(path.findall(f"{{{self.A}}}lnTo")), 4)
        self.assertIsNotNone(path.find(f"{{{self.A}}}close"))

    def test_saves_valid_pptx_with_pic_and_custgeom(self):
        set_picture_freeform_geometry(
            self.picture,
            [(0.5, 0), (1, 0.3), (0.8, 1), (0.2, 0.9), (0, 0.4)],
        )
        output = Path(self.temp.name) / "masked.pptx"
        self.presentation.save(output)
        import zipfile
        import xml.etree.ElementTree as ET

        with zipfile.ZipFile(output) as archive:
            self.assertIsNone(archive.testzip())
            root = ET.fromstring(archive.read("ppt/slides/slide1.xml"))
        picture = root.find(".//p:pic", {"p": self.P})
        self.assertIsNotNone(picture)
        self.assertIsNotNone(picture.find("p:spPr/a:custGeom", {"p": self.P, "a": self.A}))

    def test_rejects_non_picture_shape(self):
        shape = self.slide.shapes.add_shape(1, Inches(1), Inches(1), Inches(2), Inches(2))
        with self.assertRaises(TypeError):
            set_picture_freeform_geometry(shape, [(0, 0), (1, 0), (1, 1)])

    def test_rejects_invalid_coordinates(self):
        invalid = [
            [(0, 0), (1, 0), (1, 1.01)],
            [(0, 0), (-0.1, 0.5), (1, 1)],
            [(0, 0), (float("nan"), 0.5), (1, 1)],
            [(0, 0), (0, 0), (1, 1)],
            [(0, 0), (1, 1)],
        ]
        for points in invalid:
            with self.subTest(points=points), self.assertRaises(ValueError):
                set_picture_freeform_geometry(self.picture, points)

    def test_rejects_malformed_point_and_scale(self):
        with self.assertRaises(ValueError):
            set_picture_freeform_geometry(self.picture, [(0, 0, 1), (1, 0), (1, 1)])
        with self.assertRaises(ValueError):
            set_picture_freeform_geometry(self.picture, [(0, 0), (1, 0), (1, 1)], coordinate_scale=1)

    def test_deduplicates_repeated_vertices(self):
        set_picture_freeform_geometry(
            self.picture,
            [(0, 0), (0, 0), (1, 0), (1, 1), (0, 0)],
        )
        path = self.picture._element.spPr.custGeom.find(f"{{{self.A}}}pathLst").find(f"{{{self.A}}}path")
        self.assertEqual(len(path.findall(f"{{{self.A}}}lnTo")), 2)

    def test_supports_native_quadratic_and_cubic_bezier_segments(self):
        commands = [
            ("move", 0.5, 0.02),
            ("cubic", 0.76, 0.02, 0.98, 0.24, 0.98, 0.5),
            ("quad", 0.5, 0.98, 0.5, 0.98),
            ("cubic", 0.02, 0.76, 0.02, 0.24, 0.5, 0.02),
        ]
        set_picture_custom_path(self.picture, commands)
        path = self.picture._element.spPr.custGeom.find(f"{{{self.A}}}pathLst").find(f"{{{self.A}}}path")
        self.assertEqual(len(path.findall(f"{{{self.A}}}quadBezTo")), 1)
        self.assertEqual(len(path.findall(f"{{{self.A}}}cubicBezTo")), 2)
        self.assertEqual(len(path.findall(f"{{{self.A}}}moveTo")), 1)
        self.assertIsNotNone(path.find(f"{{{self.A}}}close"))

    def test_custom_path_preserves_picture_crop_and_reload(self):
        self.picture.crop_left = 0.1
        self.picture.crop_right = 0.15
        self.picture.crop_top = 0.05
        self.picture.crop_bottom = 0.2
        set_picture_custom_path(
            self.picture,
            [
                ("move", 0.5, 0.0),
                ("cubic", 0.85, 0.0, 1.0, 0.2, 1.0, 0.5),
                ("cubic", 1.0, 0.8, 0.8, 1.0, 0.5, 1.0),
                ("cubic", 0.2, 1.0, 0.0, 0.8, 0.0, 0.5),
                ("cubic", 0.0, 0.2, 0.15, 0.0, 0.5, 0.0),
            ],
        )
        output = Path(self.temp.name) / "bezier-crop.pptx"
        self.presentation.save(output)
        loaded = Presentation(output)
        picture = loaded.slides[0].shapes[0]
        self.assertEqual(picture.shape_type, MSO_SHAPE_TYPE.PICTURE)
        self.assertAlmostEqual(picture.crop_left, 0.1, places=4)
        self.assertAlmostEqual(picture.crop_right, 0.15, places=4)
        self.assertAlmostEqual(picture.crop_top, 0.05, places=4)
        self.assertAlmostEqual(picture.crop_bottom, 0.2, places=4)
        self.assertIsNotNone(picture._element.spPr.custGeom)
        self.assertEqual(picture._element.spPr.custGeom.find(f"{{{self.A}}}pathLst").find(f"{{{self.A}}}path").get("w"), "21600")

    def test_rejects_invalid_custom_path_commands(self):
        invalid_commands = [
            [("line", 0, 0), ("line", 1, 0), ("line", 1, 1)],
            [("move", 0, 0), ("move", 1, 0), ("line", 1, 1)],
            [("move", 0, 0), ("arc", 1, 0), ("line", 1, 1)],
            [("move", 0, 0), ("quad", 0.5, 0.5, 1, 0)],
            [("move", 0, 0), ("cubic", 0, 0, 1, 0)],
            [("move", 0, 0), ("line", 1.1, 0), ("line", 1, 1)],
            [("move", 0, 0), ("line", 1, 0), ("line", 0, 0)],
        ]
        for commands in invalid_commands:
            with self.subTest(commands=commands), self.assertRaises(ValueError):
                set_picture_custom_path(self.picture, commands)

    def test_custom_geometry_can_be_replaced_without_converting_picture(self):
        set_picture_freeform_geometry(
            self.picture, [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
        )
        set_picture_custom_path(
            self.picture,
            [("move", 0.5, 0.0), ("line", 1, 0.5), ("line", 0.5, 1), ("line", 0, 0.5)],
        )
        self.assertEqual(self.picture.shape_type, MSO_SHAPE_TYPE.PICTURE)
        path = self.picture._element.spPr.custGeom.find(f"{{{self.A}}}pathLst").find(f"{{{self.A}}}path")
        self.assertEqual(len(path.findall(f"{{{self.A}}}moveTo")), 1)
        self.assertEqual(len(path.findall(f"{{{self.A}}}lnTo")), 3)


if __name__ == "__main__":
    unittest.main()
