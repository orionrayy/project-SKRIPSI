from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import project_skripsi.documents as document_module
from project_skripsi.documents import (
    DocumentEngineError,
    audit_docx_structure,
    build_document,
    create_document_scaffold,
    verify_document_build,
    _validate_spec,
)
from project_skripsi.service import init_project


DOCX_AVAILABLE = document_module.Document is not None
PDF_RENDER_AVAILABLE = DOCX_AVAILABLE and document_module.fitz is not None and (shutil.which("libreoffice") or shutil.which("soffice"))


class DocumentEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.workspace = init_project(
            self.base / "workspaces",
            project_id="thesis-doc-001",
            title="Pengaruh Literasi Digital terhadap Pembelajaran",
            discipline="Pendidikan",
            research_design="QUANTITATIVE_DESCRIPTIVE",
            institution="Universitas Contoh",
            programme="Pendidikan",
        )
        self.spec_path = self.workspace / "manuscript" / "document_specification.json"
        self.spec = json.loads(self.spec_path.read_text(encoding="utf-8"))
        self.spec["title"] = "Pengaruh Literasi Digital terhadap Pembelajaran"
        self.spec["sections"] = [
            {
                "section_id": "BAB-I",
                "heading": "BAB I PENDAHULUAN",
                "level": 1,
                "blocks": [
                    {"type": "paragraph", "text": "Literasi digital menjadi konteks penting dalam pembelajaran. ", "claim_ids": ["CLAIM-001"]},
                    {"type": "bullet", "text": "Aspek akses informasi."},
                    {"type": "numbered", "text": "Aspek evaluasi informasi."},
                    {"type": "table", "caption": "Tabel 1. Konstruk penelitian", "headers": ["Konstruk", "Indikator"], "rows": [["Literasi digital", "Akses dan evaluasi"]]},
                ],
            },
            {
                "section_id": "BAB-II",
                "heading": "BAB II TINJAUAN PUSTAKA",
                "level": 1,
                "blocks": [
                    {"type": "paragraph", "text": "Pembahasan teori didukung oleh sumber yang telah diperiksa.", "claim_ids": ["CLAIM-001"]},
                ],
            },
        ]
        self.spec_path.write_text(json.dumps(self.spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        source_register_path = self.workspace / "sources" / "registry" / "source_register.json"
        register = json.loads(source_register_path.read_text(encoding="utf-8"))
        register["sources"] = [
            {
                "source_id": "SRC-001",
                "source_type": "JOURNAL_ARTICLE",
                "title": "Digital Literacy in Higher Education",
                "authors": ["Ada Lovelace", "Grace Hopper"],
                "year": 2024,
                "doi": "10.1234/example.2024.001",
                "url": "https://doi.org/10.1234/example.2024.001",
                "retrieval_date": "2026-11-06",
                "access_status": "FULL_TEXT_REVIEWED",
                "retrieval_method": "Researcher reviewed publisher full text",
                "exact_locator": "Section 2, paragraph 3",
                "rights_status": "UNKNOWN",
                "license": None,
                "file_sha256": None,
                "notes": "Test fixture only",
            }
        ]
        register["claim_evidence_links"] = [
            {
                "claim_id": "CLAIM-001",
                "source_id": "SRC-001",
                "relation": "SUPPORTS",
                "claim_scope": "FULL_TEXT_SECTION",
                "exact_locator": "Section 2, paragraph 3",
                "support_level": "DIRECT",
                "review_status": "VERIFIED",
                "reviewer_role": "researcher-reviewer",
                "limitations": "Test fixture only",
            }
        ]
        source_register_path.write_text(json.dumps(register, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_scaffold_is_created_and_refuses_overwrite(self):
        self.assertTrue(self.spec_path.is_file())
        with self.assertRaises(FileExistsError):
            create_document_scaffold(self.workspace)
        self.spec_path.unlink()  # simulate a legacy workspace created before v0.6.0
        p = create_document_scaffold(self.workspace)
        self.assertEqual(p.name, "document_specification.json")
        with self.assertRaises(FileExistsError):
            create_document_scaffold(self.workspace)

    @unittest.skipUnless(PDF_RENDER_AVAILABLE, "python-docx, PyMuPDF and LibreOffice are required for render integration tests")
    def test_build_has_page_mapped_toc_citations_and_bibliography(self):
        self.spec["output"]["filename"] = "thesis-build-001.docx"
        self.spec_path.write_text(json.dumps(self.spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = build_document(self.workspace)
        self.assertEqual(result["status"], "BUILT_NOT_REVIEWED")
        self.assertIn("BAB-I", result["toc_page_map"])
        self.assertIn("BAB-II", result["toc_page_map"])
        self.assertIn("__BIBLIOGRAPHY__", result["toc_page_map"])
        self.assertEqual(verify_document_build(self.workspace, "THESIS-DRAFT-001")["status"], "PASS")
        audit = audit_docx_structure(self.workspace / result["docx_path"])
        self.assertEqual(audit["status"], "PASS")
        self.assertGreaterEqual(audit["heading_count"], 3)
        self.assertGreaterEqual(audit["table_count"], 1)
        self.assertGreaterEqual(audit["hyperlink_count"], 3)
        self.assertGreaterEqual(audit["bookmark_count"], 3)
        self.assertTrue((self.workspace / result["pdf_path"]).is_file())
        try:
            from jsonschema import Draft202012Validator
            root = Path(__file__).resolve().parents[1]
            spec_schema = json.loads((root / "schemas/manuscript/document-specification.schema.json").read_text())
            build_schema = json.loads((root / "schemas/manuscript/document-build-record.schema.json").read_text())
            Draft202012Validator(spec_schema).validate(json.loads(self.spec_path.read_text()))
            record = json.loads((self.workspace / result["build_record"]).read_text())
            Draft202012Validator(build_schema).validate(record)
        except ImportError:
            pass

    @unittest.skipUnless(DOCX_AVAILABLE, "python-docx is required for document tests")
    def test_rejects_unverified_claim_evidence(self):
        path = self.workspace / "sources" / "registry" / "source_register.json"
        register = json.loads(path.read_text(encoding="utf-8"))
        register["claim_evidence_links"][0]["review_status"] = "UNREVIEWED"
        path.write_text(json.dumps(register, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(DocumentEngineError):
            build_document(self.workspace)

    @unittest.skipUnless(DOCX_AVAILABLE, "python-docx is required for document tests")
    def test_rejects_path_escape_for_figure(self):
        self.spec["sections"][0]["blocks"].append({
            "type": "figure", "path": "../../outside.png", "caption": "Gambar 1", "alt_text": "Contoh gambar"
        })
        self.spec["output"]["filename"] = "thesis-figure-001.docx"
        self.spec_path.write_text(json.dumps(self.spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(DocumentEngineError):
            build_document(self.workspace)

    @unittest.skipUnless(PDF_RENDER_AVAILABLE, "python-docx, PyMuPDF and LibreOffice are required for render integration tests")
    def test_build_never_overwrites_existing_output(self):
        self.spec["output"]["filename"] = "thesis-once-001.docx"
        self.spec_path.write_text(json.dumps(self.spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        build_document(self.workspace)
        with self.assertRaises(FileExistsError):
            build_document(self.workspace)

    def test_ieee_numbers_follow_first_appearance(self):
        path = self.workspace / "sources" / "registry" / "source_register.json"
        register = json.loads(path.read_text(encoding="utf-8"))
        second = dict(register["sources"][0])
        second.update({"source_id": "SRC-002", "title": "Another source", "doi": None, "url": "https://example.edu/source2"})
        register["sources"].append(second)
        link2 = dict(register["claim_evidence_links"][0])
        link2.update({"claim_id": "CLAIM-002", "source_id": "SRC-002"})
        register["claim_evidence_links"].append(link2)
        path.write_text(json.dumps(register, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.spec["citation_style"] = "IEEE"
        self.spec["sections"][0]["blocks"][0]["claim_ids"] = ["CLAIM-002", "CLAIM-001"]
        self.spec["output"]["filename"] = "thesis-ieee-001.docx"
        self.spec_path.write_text(json.dumps(self.spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = build_document(self.workspace)
        record = json.loads((self.workspace / result["build_record"]).read_text(encoding="utf-8"))
        self.assertEqual([x["source_id"] for x in record["citations"]], ["SRC-002", "SRC-001"])
        self.assertEqual([x["style_order"] for x in record["citations"]], [1, 2])

    @unittest.skipUnless(PDF_RENDER_AVAILABLE, "python-docx, PyMuPDF and LibreOffice are required for render integration tests")
    def test_verify_detects_source_register_drift(self):
        self.spec["output"]["filename"] = "thesis-drift-001.docx"
        self.spec_path.write_text(json.dumps(self.spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        build_document(self.workspace)
        path = self.workspace / "sources" / "registry" / "source_register.json"
        register = json.loads(path.read_text(encoding="utf-8"))
        register["sources"][0]["notes"] = "changed after build"
        path.write_text(json.dumps(register, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(verify_document_build(self.workspace, "THESIS-DRAFT-001")["status"], "FAIL")

    @unittest.skipUnless(PDF_RENDER_AVAILABLE, "python-docx, PyMuPDF and LibreOffice are required for render integration tests")
    def test_analysis_table_requires_verified_run(self):
        out = self.workspace / "analysis" / "outputs" / "RUN-DOC001"
        out.mkdir(parents=True)
        (out / "results.json").write_text(json.dumps({
            "variable_results": [{"variable_id": "VAR-001", "operation": "NUMERIC_SUMMARY", "summary_suppressed": False,
                                  "mean": 3.0, "sample_standard_deviation": 1.0, "minimum": 2.0, "maximum": 4.0,
                                  "n": 3, "missing_n": 0}]
        }), encoding="utf-8")
        (out / "run.json").write_text(json.dumps({"analysis_run_id": "RUN-DOC001"}), encoding="utf-8")
        self.spec["sections"][0]["blocks"].append({"type": "analysis_table", "run_id": "RUN-DOC001", "variable_ids": ["VAR-001"]})
        self.spec["output"]["filename"] = "thesis-analysis-001.docx"
        self.spec_path.write_text(json.dumps(self.spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with patch("project_skripsi.documents.verify_analysis_run", return_value={"status": "PASS"}):
            result = build_document(self.workspace)
        record = json.loads((self.workspace / result["build_record"]).read_text(encoding="utf-8"))
        self.assertEqual(record["analysis_run_pins"][0]["run_id"], "RUN-DOC001")

    def test_institution_profile_requires_human_review_and_matching_citation_style(self):
        profile = {
            "profile_id": "guideline-test-v1", "institution_name": "Universitas Contoh",
            "programme": "Pendidikan", "version": "1.0", "effective_date": "2026-01-01",
            "supersedes_version": None,
            "source": {"url": "https://example.org/guideline", "retrieved_at": "2026-11-06T00:00:00Z", "sha256": "0" * 64},
            "requirements": {
                "structure": {"chapters": ["I", "II", "III", "IV", "V"]},
                "formatting": {"font_family": "Times New Roman", "font_size_pt": 12, "line_spacing": 1.5},
                "citation_style": "APA7", "submission": {"file_formats": ["DOCX", "PDF"]},
                "disclosure": {"ai_assistance_policy": "REVIEW_REQUIRED"}
            },
            "review_status": "UNREVIEWED", "reviewer_role": None, "notes": "Test fixture"
        }
        profile_path = self.workspace / "requirements" / "institution" / "guideline-profile.json"
        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        import hashlib
        digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()
        self.spec["institution_profile"] = {"path": "requirements/institution/guideline-profile.json", "sha256": digest, "approval_reference": "APPROVAL-REF-001"}
        self.spec["citation_style"] = "APA7"
        errors, _warnings, _parsed_profile = _validate_spec(self.workspace, self.spec)
        self.assertTrue(any("HUMAN_REVIEWED" in error for error in errors))
        profile["review_status"] = "HUMAN_REVIEWED"
        profile["reviewer_role"] = "academic-supervisor"
        profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()
        self.spec["institution_profile"]["sha256"] = digest
        errors, warnings, parsed = _validate_spec(self.workspace, self.spec)
        self.assertEqual(errors, [])
        self.assertIsNotNone(parsed)
        self.spec["citation_style"] = "IEEE"
        errors, _warnings, _parsed = _validate_spec(self.workspace, self.spec)
        self.assertTrue(any("does not match" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
