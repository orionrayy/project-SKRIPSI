from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    import fitz
except ImportError:  # pragma: no cover - optional dependency
    fitz = None

from project_skripsi.turnitin_reports import audit_turnitin_report, compare_turnitin_reports


def make_report(path: Path, score: int, internet: int, publication: int, student: int, *, doc_id: str = "A") -> None:
    doc = fitz.open()
    cover = doc.new_page(width=612, height=792)
    cover.insert_text((50, 60), "no name\ndocx\nDocument Details\nSubmission ID\nSYNTHETIC-REPORT-0001\nSubmission Date\nJan 02, 2025, 09:00 AM GMT+7\nFile Name\nsample-thesis.docx\n120.0 KB\n24 Pages\n3,200 Words\n20,000 Characters")
    cover.insert_text((30, 775), "Page 1 of 4 - Cover Page")

    overview = doc.new_page(width=612, height=792)
    overview.insert_text((30, 60), f"{score}% Overall Similarity\nFiltered from the Report\nBibliography\nQuoted Text\nTop Sources\n{internet}% Internet sources\n{publication}% Publications\n{student}% Submitted works (Student Papers)")
    overview.insert_text((30, 775), "Page 2 of 4 - Integrity Overview")

    sources = doc.new_page(width=612, height=792)
    sources.insert_text((30, 40), "Top Sources\nThe sources with the highest number of matches within the submission. Overlapping sources will not be displayed.\n1\nInternet\nrepository.example.org\n1%\n2\nPublication\nExample Author. \"An Example Article\"\n<1%")
    sources.insert_text((30, 775), "Page 3 of 4 - Integrity Overview")

    body = doc.new_page(width=595, height=842)
    body.insert_text((30, 40), "Synthetic thesis body page. No source passage is embedded.")
    rect = fitz.Rect(7.48, 200, 25.20, 215.51)
    body.draw_rect(rect, color=None, fill=(0.0, 0.45, 0.27), overlay=True)
    body.insert_text((12, 211), "1", fontsize=8, color=(1, 1, 1))
    body.insert_text((30, 825), "Page 4 of 4 - Integrity Submission")
    doc.save(path)
    doc.close()


@unittest.skipIf(fitz is None, "PyMuPDF optional dependency not installed")
class TurnitinReportTests(unittest.TestCase):
    def test_extracts_report_metadata_sources_and_badges_without_body_text(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.pdf"
            make_report(path, 33, 30, 25, 20)
            report = audit_turnitin_report(path)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["report"]["overall_similarity_percent"], 33)
            self.assertEqual(report["report"]["visible_exclusions"], ["Bibliography", "Quoted Text"])
            self.assertEqual(report["source_inventory"]["source_entries_parsed"], 2)
            self.assertEqual(report["body_source_badges"]["source_badge_occurrences"], 1)
            self.assertEqual(report["body_source_badges"]["out_of_range_source_ids"], [])
            self.assertEqual(report["text_storage"], "REPORT_METADATA_ONLY_NO_THESIS_BODY_TEXT_STORED")
            self.assertNotIn("thesis_body_text", report)

    def test_compares_visible_exclusions_and_percentage_point_delta(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = root / "old.pdf"
            new = root / "new.pdf"
            make_report(old, 41, 35, 28, 22)
            make_report(new, 33, 30, 25, 20)
            result = compare_turnitin_reports(old, new)
            self.assertEqual(result["status"], "COMPARABLE_VISIBLE_SETTINGS")
            self.assertEqual(result["change"]["overall_similarity_percentage_point_delta"], -8)
            self.assertEqual(result["change"]["source_category_percentage_point_deltas"], {
                "internet_sources": -5, "publications": -3, "student_papers": -2
            })
            self.assertTrue(result["comparability"]["visible_exclusion_settings_match"])
            self.assertFalse(result["comparability"]["database_and_account_side_settings_verified"])

    def test_different_visible_exclusions_are_conditional(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = root / "old.pdf"
            new = root / "new.pdf"
            make_report(old, 41, 35, 28, 22)
            make_report(new, 33, 30, 25, 20)
            doc = fitz.open(new)
            page = doc[1]
            page.add_redact_annot(fitz.Rect(25, 90, 220, 145), fill=(1, 1, 1))
            page.apply_redactions()
            page.insert_text((30, 100), "33% Overall Similarity\nFiltered from the Report\nQuoted Text\nTop Sources\n30% Internet sources\n25% Publications\n20% Submitted works (Student Papers)")
            doc.saveIncr()
            doc.close()
            result = compare_turnitin_reports(old, new)
            self.assertEqual(result["status"], "CONDITIONAL_SETTINGS_DIFFER")


if __name__ == "__main__":
    unittest.main()
