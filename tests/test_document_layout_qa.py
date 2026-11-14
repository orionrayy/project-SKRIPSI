from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import fitz
from docx import Document
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from project_skripsi.document_layout_qa import audit_document_layout


def add_page_field(paragraph):
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    cached = OxmlElement("w:t")
    cached.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for node in (begin, instruction, separate, cached, end):
        run._r.append(node)


def make_docx(path: Path, *, dedicated_cover_section=True, zero_start=False, margins=(3, 3, 3, 4)):
    doc = Document()
    for section in doc.sections:
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(margins[0])
        section.right_margin = Cm(margins[1])
        section.bottom_margin = Cm(margins[2])
        section.left_margin = Cm(margins[3])
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5
    doc.add_paragraph("Synthetic cover page")
    if dedicated_cover_section:
        body = doc.add_section(WD_SECTION.NEW_PAGE)
        body.page_width = Cm(21)
        body.page_height = Cm(29.7)
        body.top_margin = Cm(margins[0])
        body.right_margin = Cm(margins[1])
        body.bottom_margin = Cm(margins[2])
        body.left_margin = Cm(margins[3])
        body.footer.is_linked_to_previous = False
        add_page_field(body.footer.paragraphs[0])
        page_num_type = body._sectPr.find(qn("w:pgNumType"))
        if page_num_type is None:
            page_num_type = OxmlElement("w:pgNumType")
            body._sectPr.append(page_num_type)
        page_num_type.set(qn("w:start"), "1")
        doc.add_paragraph("Body section starts here")
    else:
        section = doc.sections[0]
        section.different_first_page_header_footer = True
        add_page_field(section.footer.paragraphs[0])
        section.first_page_footer.paragraphs[0].text = ""
        page_num_type = OxmlElement("w:pgNumType")
        page_num_type.set(qn("w:start"), "0" if zero_start else "1")
        section._sectPr.append(page_num_type)
        doc.add_paragraph("Body starts after cover")
    doc.save(path)


def make_pdf(path: Path, numbers: list[int | None], page_texts: list[str] | None = None):
    pdf = fitz.open()
    for index, number in enumerate(numbers):
        page = pdf.new_page(width=595.276, height=841.89)
        text = page_texts[index] if page_texts and index < len(page_texts) else f"Synthetic body content page {index + 1}"
        page.insert_text((72, 100), text, fontsize=12)
        if number is not None:
            rect = fitz.Rect(250, 795, 345, 825)
            page.insert_textbox(rect, str(number), fontsize=10, align=1)
    pdf.save(path)
    pdf.close()


class DocumentLayoutQATests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.docx = self.root / "synthetic.docx"
        self.pdf = self.root / "synthetic.pdf"
        self.policy = {
            "page_size": "A4",
            "margins_cm": {"top": 3, "right": 3, "bottom": 3, "left": 4},
            "font_family": "Times New Roman",
            "font_size_pt": 12,
            "line_spacing": 1.5,
            "cover_pages": 1,
            "body_start_number": 1,
            "page_number_position": "BOTTOM_CENTER",
            "require_dedicated_cover_section": True,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_accepts_dedicated_cover_and_restart_at_one(self):
        make_docx(self.docx, dedicated_cover_section=True)
        make_pdf(self.pdf, [None, 1, 2, 3])
        report = audit_document_layout(self.docx, self.pdf, self.policy)
        self.assertEqual(report["status"], "PASS", report["findings"])
        self.assertEqual(report["pagination"]["detected_body_page_numbers"], [1, 2, 3])
        self.assertEqual(report["docx"]["section_count"], 2)

    def test_detects_number_visible_on_cover_and_bad_body_sequence(self):
        make_docx(self.docx, dedicated_cover_section=True)
        make_pdf(self.pdf, [1, 2, 3])
        report = audit_document_layout(self.docx, self.pdf, self.policy)
        codes = {item["code"] for item in report["findings"]}
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("COVER_PAGE_NUMBER_VISIBLE", codes)
        self.assertIn("BODY_PAGE_NUMBER_SEQUENCE_MISMATCH", codes)

    def test_warns_on_zero_based_single_section_workaround(self):
        make_docx(self.docx, dedicated_cover_section=False, zero_start=True)
        make_pdf(self.pdf, [None, 1, 2])
        policy = dict(self.policy)
        policy["require_dedicated_cover_section"] = False
        report = audit_document_layout(self.docx, self.pdf, policy)
        self.assertEqual(report["status"], "WARN")
        self.assertIn("NONSTANDARD_ZERO_BASED_COVER_NUMBERING", {x["code"] for x in report["findings"]})
        self.assertTrue(report["pagination"]["body_numbering_sequence_valid"])

    def test_detects_margin_mismatch(self):
        make_docx(self.docx, dedicated_cover_section=True, margins=(3, 2.5, 2.5, 3))
        make_pdf(self.pdf, [None, 1, 2])
        report = audit_document_layout(self.docx, self.pdf, self.policy)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("MARGIN_MISMATCH", {x["code"] for x in report["findings"]})

    def test_validates_toc_page_map_using_displayed_body_page_numbers(self):
        make_docx(self.docx, dedicated_cover_section=True)
        make_pdf(
            self.pdf,
            [None, 1, 2, 3],
            [
                "COVER PAGE",
                "KATA PENGANTAR",
                "BAB I PENDAHULUAN\nSynthetic body text",
                "BAB II TINJAUAN PUSTAKA\nSynthetic body text",
            ],
        )
        policy = dict(self.policy)
        policy["expected_page_map"] = {
            "KATA PENGANTAR": 1,
            "BAB I PENDAHULUAN": 2,
            "BAB II TINJAUAN PUSTAKA": 3,
        }
        report = audit_document_layout(self.docx, self.pdf, policy)
        self.assertEqual(report["status"], "PASS", report["findings"])

        policy["expected_page_map"]["BAB I PENDAHULUAN"] = 3
        report = audit_document_layout(self.docx, self.pdf, policy)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("TOC_PAGE_MAP_MISMATCH", {x["code"] for x in report["findings"]})

    def test_report_redacts_input_filenames_and_file_hashes(self):
        private_docx = self.root / "private_student_123.docx"
        private_pdf = self.root / "private_student_123.pdf"
        make_docx(private_docx, dedicated_cover_section=True)
        make_pdf(private_pdf, [None, 1, 2])
        report = audit_document_layout(private_docx, private_pdf, self.policy)
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn(private_docx.name, serialized)
        self.assertNotIn(private_pdf.name, serialized)
        self.assertNotIn("sha256", serialized.casefold())
        self.assertNotIn("/tmp/", serialized)


if __name__ == "__main__":
    unittest.main()
