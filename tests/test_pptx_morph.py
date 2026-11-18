from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from project_skripsi.pptx.morph import apply_morph, inspect_deck

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
ET.register_namespace("p", P)
ET.register_namespace("a", A)


def slide_xml(shape_names: list[str]) -> bytes:
    root = ET.Element(f"{{{P}}}sld")
    c_sld = ET.SubElement(root, f"{{{P}}}cSld")
    tree = ET.SubElement(c_sld, f"{{{P}}}spTree")
    group = ET.SubElement(tree, f"{{{P}}}nvGrpSpPr")
    ET.SubElement(group, f"{{{P}}}cNvPr", {"id": "1", "name": ""})
    ET.SubElement(group, f"{{{P}}}cNvGrpSpPr")
    ET.SubElement(group, f"{{{P}}}nvPr")
    ET.SubElement(tree, f"{{{P}}}grpSpPr")
    for i, name in enumerate(shape_names, start=2):
        shape = ET.SubElement(tree, f"{{{P}}}sp")
        nv = ET.SubElement(shape, f"{{{P}}}nvSpPr")
        ET.SubElement(nv, f"{{{P}}}cNvPr", {"id": str(i), "name": name})
        ET.SubElement(nv, f"{{{P}}}cNvSpPr")
        ET.SubElement(nv, f"{{{P}}}nvPr")
        sppr = ET.SubElement(shape, f"{{{P}}}spPr")
        geom = ET.SubElement(sppr, f"{{{A}}}prstGeom", {"prst": "rect"})
        ET.SubElement(geom, f"{{{A}}}avLst")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def presentation_xml(count: int) -> bytes:
    root = ET.Element(f"{{{P}}}presentation", {"xmlns:r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"})
    slide_list = ET.SubElement(root, f"{{{P}}}sldIdLst")
    for index in range(1, count + 1):
        ET.SubElement(slide_list, f"{{{P}}}sldId", {"id": str(255 + index), "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id": f"rId{index}"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def relationships_xml(order: list[int]) -> bytes:
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    office_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    root = ET.Element(f"{{{rel_ns}}}Relationships")
    for display_id, physical_id in enumerate(order, start=1):
        ET.SubElement(root, f"{{{rel_ns}}}Relationship", {
            "Id": f"rId{display_id}", "Type": f"{office_rel}/slide",
            "Target": f"slides/slide{physical_id}.xml",
        })
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def make_deck(path: Path, source_names=None, target_names=None, target_timing=False):
    source_names = source_names if source_names is not None else ["!!hero"]
    target_names = target_names if target_names is not None else ["!!hero"]
    target_xml = ET.fromstring(slide_xml(target_names))
    if target_timing:
        ET.SubElement(target_xml, f"{{{P}}}timing")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", f'<Types xmlns="{CT}"/>')
        z.writestr("ppt/presentation.xml", presentation_xml(2))
        z.writestr("ppt/_rels/presentation.xml.rels", relationships_xml([1, 2]))
        z.writestr("ppt/slides/slide1.xml", slide_xml(source_names))
        z.writestr("ppt/slides/slide2.xml", ET.tostring(target_xml, encoding="utf-8"))


def make_reordered_deck(path: Path):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", f'<Types xmlns="{CT}"/>')
        z.writestr("ppt/presentation.xml", presentation_xml(3))
        z.writestr("ppt/_rels/presentation.xml.rels", relationships_xml([1, 3, 2]))
        z.writestr("ppt/slides/slide1.xml", slide_xml(["!!route"]))
        z.writestr("ppt/slides/slide2.xml", slide_xml(["!!other"]))
        z.writestr("ppt/slides/slide3.xml", slide_xml(["!!route"]))


class MorphPatcherTests(unittest.TestCase):
    def test_apply_adds_morph_and_fade_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "source.pptx"
            out = Path(temp) / "morphed.pptx"
            make_deck(deck)
            result = apply_morph(deck, [2], output=out, duration_ms=1200, option="byObject")
            report = inspect_deck(result)
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual(report["slide_count"], 2)
            self.assertEqual(report["morph_slides"], [2])
            self.assertTrue(report["slides"][1]["fade_fallback"])
            self.assertEqual(report["slides"][1]["duration_ms"], 1200)
            self.assertTrue(deck.exists())

    def test_patch_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "deck.pptx"
            make_deck(deck)
            apply_morph(deck, [2])
            apply_morph(deck, [2])
            report = inspect_deck(deck)
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual(report["morph_slides"], [2])

    def test_rejects_missing_pair(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "deck.pptx"
            make_deck(deck, ["!!hero"], ["!!other"])
            apply_morph(deck, [2])
            report = inspect_deck(deck)
            self.assertFalse(report["ok"])
            self.assertTrue(any("unpaired Morph objects" in e for e in report["errors"]))

    def test_rejects_duplicate_forced_names(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "deck.pptx"
            make_deck(deck, ["!!hero", "!!hero"], ["!!hero"])
            apply_morph(deck, [2])
            report = inspect_deck(deck)
            self.assertFalse(report["ok"])
            self.assertTrue(any("duplicate forced object names" in e for e in report["errors"]))

    def test_rejects_invalid_destination_and_option(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "deck.pptx"
            make_deck(deck)
            with self.assertRaises(ValueError):
                apply_morph(deck, [1])
            with self.assertRaises(ValueError):
                apply_morph(deck, [2], option="unsupported")

    def test_uses_presentation_order_not_slide_part_number(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "reordered.pptx"
            make_reordered_deck(deck)
            apply_morph(deck, [2])
            report = inspect_deck(deck)
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual(report["morph_slides"], [2])
            self.assertEqual(report["slides"][1]["part"], "ppt/slides/slide3.xml")

    def test_inserts_transition_before_timing(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "timing.pptx"
            make_deck(deck, target_timing=True)
            apply_morph(deck, [2])
            with zipfile.ZipFile(deck) as z:
                root = ET.fromstring(z.read("ppt/slides/slide2.xml"))
                tags = [child.tag.rsplit("}", 1)[-1] for child in list(root)]
                self.assertLess(tags.index("AlternateContent"), tags.index("timing"))

    def test_rejects_corrupt_package(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "bad.pptx"
            deck.write_bytes(b"not a zip file")
            report = inspect_deck(deck)
            self.assertFalse(report["ok"])


if __name__ == "__main__":
    unittest.main()


class StrictSlideOrderTests(unittest.TestCase):
    def _replace_member(self, deck: Path, member: str, payload: bytes):
        rewritten = deck.with_name(deck.stem + ".rewritten.pptx")
        with zipfile.ZipFile(deck, "r") as source:
            entries = [(info, source.read(info.filename)) for info in source.infolist()]
        with zipfile.ZipFile(rewritten, "w", zipfile.ZIP_DEFLATED) as target:
            for info, data in entries:
                target.writestr(info, payload if info.filename == member else data)
        rewritten.replace(deck)

    def test_rejects_malformed_presentation_xml_instead_of_numeric_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "malformed-presentation.pptx"
            make_deck(deck)
            self._replace_member(deck, "ppt/presentation.xml", b"<p:presentation")
            report = inspect_deck(deck)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("Malformed XML in ppt/presentation.xml" in error for error in report["errors"]),
                report["errors"],
            )

    def test_rejects_malformed_relationships_xml_instead_of_numeric_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "malformed-relationships.pptx"
            make_deck(deck)
            self._replace_member(deck, "ppt/_rels/presentation.xml.rels", b"<Relationships")
            report = inspect_deck(deck)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("Malformed XML in ppt/_rels/presentation.xml.rels" in error for error in report["errors"]),
                report["errors"],
            )

    def test_rejects_unresolved_slide_relationship_instead_of_omitting_slide(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "missing-slide-relationship.pptx"
            make_deck(deck)
            self._replace_member(
                deck,
                "ppt/_rels/presentation.xml.rels",
                relationships_xml([1]),
            )
            report = inspect_deck(deck)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("unresolved slide relationship" in error.lower() for error in report["errors"]),
                report["errors"],
            )




class MorphMarkupCompatibilityTests(unittest.TestCase):
    def _replace_slide_xml_bytes(self, deck: Path, payload: bytes):
        rewritten = deck.with_name(deck.stem + ".rewritten.pptx")
        with zipfile.ZipFile(deck, "r") as source:
            entries = [(info, source.read(info.filename)) for info in source.infolist()]
        with zipfile.ZipFile(rewritten, "w", zipfile.ZIP_DEFLATED) as target:
            for info, data in entries:
                target.writestr(info, payload if info.filename == "ppt/slides/slide2.xml" else data)
        rewritten.replace(deck)

    def test_generated_morph_uses_p159_choice_and_scoped_namespace_declarations(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "morph-choice.pptx"
            make_deck(deck)
            apply_morph(deck, [2], duration_ms=950, option="byObject")
            with zipfile.ZipFile(deck, "r") as archive:
                xml = archive.read("ppt/slides/slide2.xml")
            root_open = re.search(rb"<p:sld\\b[^>]*>", xml)
            choice_open = re.search(rb"<mc:Choice\\b[^>]*>", xml)
            transition_open = re.search(
                rb"<mc:Choice\\b[^>]*>.*?(<p:transition\\b[^>]*>)",
                xml,
                re.DOTALL,
            )
            self.assertIsNotNone(root_open)
            self.assertIsNotNone(choice_open)
            self.assertIsNotNone(transition_open)
            self.assertIn(b'Requires="p159"', choice_open.group(0))
            self.assertIn(b'xmlns:p159="http://schemas.microsoft.com/office/powerpoint/2015/09/main"', choice_open.group(0))
            self.assertIn(b'xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main"', transition_open.group(1))
            self.assertIn(b'p14:dur="950"', transition_open.group(1))
            self.assertNotIn(b"xmlns:p159=", root_open.group(0))
            self.assertNotIn(b"xmlns:p14=", root_open.group(0))

    def test_inspector_accepts_p14_duration_with_p159_only_in_requires(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "p159-only-requires.pptx"
            make_deck(deck)
            apply_morph(deck, [2], duration_ms=950, option="byObject")
            report = inspect_deck(deck)
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual(report["slides"][1]["morph_requires"], ["p159"])

    def test_inspector_rejects_morph_without_p159_requirement(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "missing-p159-requirement.pptx"
            make_deck(deck)
            apply_morph(deck, [2], duration_ms=950, option="byObject")
            with zipfile.ZipFile(deck, "r") as archive:
                xml = archive.read("ppt/slides/slide2.xml")
            self.assertIn(b'Requires="p159"', xml)
            self._replace_slide_xml_bytes(deck, xml.replace(b'Requires="p159"', b'Requires="p14"', 1))
            report = inspect_deck(deck)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("Morph Choice Requires is missing p159" in error for error in report["errors"]),
                report["errors"],
            )

    def test_patch_preserves_other_slide_xml_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            deck = Path(temp) / "preserve-slide-parts.pptx"
            make_deck(deck)
            with zipfile.ZipFile(deck, "r") as archive:
                original_slide_1 = archive.read("ppt/slides/slide1.xml")
            apply_morph(deck, [2], duration_ms=950, option="byObject")
            with zipfile.ZipFile(deck, "r") as archive:
                patched_slide_1 = archive.read("ppt/slides/slide1.xml")
            self.assertEqual(patched_slide_1, original_slide_1)
