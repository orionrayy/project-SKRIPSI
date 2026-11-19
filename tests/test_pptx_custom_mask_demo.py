from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

try:
    from pptx import Presentation
except ImportError:
    Presentation = None

from examples.pptx.custom_picture_mask_morph_demo import build_demo

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P159 = "http://schemas.microsoft.com/office/powerpoint/2015/09/main"


@unittest.skipIf(Presentation is None, "Install the optional slides extra to test the demo generator")
class CustomMaskDemoTests(unittest.TestCase):
    def test_demo_has_five_distinct_native_shape_picture_fill_keyframes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "custom-mask-morph.pptx"
            report = build_demo(output, duration_ms=1100)
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual(report["slide_count"], 5)
            self.assertEqual(report["morph_slides"], [2, 3, 4, 5])
            geometries = []
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                for number in range(1, 6):
                    root = ET.fromstring(archive.read(f"ppt/slides/slide{number}.xml"))
                    shape = None
                    for candidate in root.findall(".//p:sp", {"p": P}):
                        nonvisual = candidate.find("p:nvSpPr/p:cNvPr", {"p": P})
                        if nonvisual is not None and nonvisual.get("name") == "!!hero-photo-mask":
                            shape = candidate
                            break
                    self.assertIsNotNone(shape)
                    sp_pr = shape.find("p:spPr", {"p": P})
                    self.assertIsNotNone(sp_pr)
                    geometry = sp_pr.find("a:custGeom", {"a": A})
                    self.assertIsNotNone(geometry)
                    self.assertIsNotNone(sp_pr.find("a:blipFill/a:blip", {"a": A}))
                    path = geometry.find("a:pathLst/a:path", {"a": A})
                    self.assertIsNotNone(path)
                    self.assertEqual(len(path.findall("a:moveTo", {"a": A})), 1)
                    self.assertEqual(len(path.findall("a:cubicBezTo", {"a": A})), 10)
                    self.assertIsNotNone(path.find("a:close", {"a": A}))
                    geometries.append(ET.tostring(geometry))
                    self.assertEqual(root.find(f".//{{{P159}}}morph") is not None, number > 1)
            self.assertEqual(len(set(geometries)), 5, "Each slide must contain a different mask keyframe")


if __name__ == "__main__":
    unittest.main()
