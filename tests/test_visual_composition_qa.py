from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import fitz

from project_skripsi.visual_composition_qa import audit_visual_composition


def make_pdf(path: Path, *, font_sizes=(24, 16, 11), boxes=0, text_lines=5):
    pdf = fitz.open()
    page = pdf.new_page(width=595.276, height=841.89)
    for idx, size in enumerate(font_sizes):
        page.insert_text((72, 90 + idx * 45), f"Synthetic label {idx + 1}", fontsize=size)
    for idx in range(text_lines):
        page.insert_text((72, 280 + idx * 24), f"Synthetic body paragraph line {idx + 1}", fontsize=11)
    for idx in range(boxes):
        x = 70 + (idx % 4) * 115
        y = 450 + (idx // 4) * 85
        page.draw_rect(fitz.Rect(x, y, x + 92, y + 62), color=(0.2, 0.3, 0.2), width=1)
    pdf.save(path)
    pdf.close()


class VisualCompositionQATests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pdf = self.root / "synthetic.pdf"

    def tearDown(self):
        self.tmp.cleanup()

    def test_reports_page_proxies_without_text_or_filename(self):
        make_pdf(self.pdf, font_sizes=(24, 16, 11), boxes=2, text_lines=5)
        report = audit_visual_composition(self.pdf, {
            "heading_min_size_pt": 14,
            "min_distinct_font_sizes": 3,
            "min_heading_body_size_ratio": 1.25,
        })
        self.assertEqual(report["summary"]["page_count"], 1)
        self.assertGreaterEqual(report["pages"][0]["distinct_font_size_count"], 3)
        self.assertGreaterEqual(report["pages"][0]["rectangle_shape_count"], 2)
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("Synthetic label", serialized)
        self.assertNotIn(self.pdf.name, serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertEqual(report["reader_attention"]["eye_tracking_status"], "NOT_MEASURED")

    def test_detects_rectangle_overuse(self):
        make_pdf(self.pdf, boxes=12)
        report = audit_visual_composition(self.pdf, {"max_rectangle_shapes_per_page": 4})
        self.assertIn("RECTANGULAR_SHAPE_OVERUSE", {x["code"] for x in report["findings"]})
        self.assertEqual(report["status"], "WARN")

    def test_detects_flat_typographic_hierarchy(self):
        make_pdf(self.pdf, font_sizes=(11, 11, 11), text_lines=4)
        report = audit_visual_composition(self.pdf, {
            "heading_min_size_pt": 14,
            "min_distinct_font_sizes": 3,
            "min_heading_body_size_ratio": 1.25,
        })
        codes = {x["code"] for x in report["findings"]}
        self.assertIn("TYPOGRAPHIC_HIERARCHY_TOO_FLAT", codes)
        self.assertIn("HEADING_BODY_CONTRAST_LOW", codes)

    def test_density_policy_is_profile_specific(self):
        make_pdf(self.pdf, text_lines=35)
        report = audit_visual_composition(self.pdf, {"max_text_area_ratio": 0.03})
        self.assertIn("PAGE_TEXT_DENSITY_ABOVE_PROFILE", {x["code"] for x in report["findings"]})

    def test_unconfigured_audit_is_not_a_pass_or_eye_tracking_claim(self):
        make_pdf(self.pdf)
        report = audit_visual_composition(self.pdf)
        self.assertEqual(report["status"], "WARN")
        self.assertEqual(report["reader_attention"]["eye_tracking_status"], "NOT_MEASURED")

    def test_profile_id_alone_does_not_pass(self):
        make_pdf(self.pdf)
        report = audit_visual_composition(self.pdf, {"profile_id": "TOR_PROFILE_V1"})
        self.assertEqual(report["profile_id"], "TOR_PROFILE_V1")
        self.assertEqual(report["status"], "WARN")
        self.assertEqual(report["summary"]["policy_threshold_count"], 0)

    def test_rejects_inconsistent_density_thresholds(self):
        make_pdf(self.pdf)
        with self.assertRaises(ValueError):
            audit_visual_composition(self.pdf, {"min_text_area_ratio": 0.4, "max_text_area_ratio": 0.2})


if __name__ == "__main__":
    unittest.main()
