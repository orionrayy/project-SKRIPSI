from __future__ import annotations

import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from project_skripsi.revision_qa import (
    RevisionQAError,
    audit_artifact_manifest,
    audit_before_after_pairs,
    audit_empirical_study_consistency,
    audit_marked_region_register,
    write_report,
)


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def make_docx(path: Path, paragraphs: list[str]) -> None:
    import xml.etree.ElementTree as ET

    ET.register_namespace("w", W_NS)
    doc = ET.Element(f"{{{W_NS}}}document")
    body = ET.SubElement(doc, f"{{{W_NS}}}body")
    for value in paragraphs:
        paragraph = ET.SubElement(body, f"{{{W_NS}}}p")
        run = ET.SubElement(paragraph, f"{{{W_NS}}}r")
        text = ET.SubElement(run, f"{{{W_NS}}}t")
        text.text = value
    ET.SubElement(body, f"{{{W_NS}}}sectPr")
    xml = ET.tostring(doc, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>')
        archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
        archive.writestr("word/document.xml", xml)


class RevisionPairAuditTests(unittest.TestCase):
    def test_pair_audit_finds_applied_and_unapplied_after_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            txt = root / "pairs.txt"
            candidate = root / "candidate.docx"
            original = root / "original.docx"
            txt.write_text(
                "BAGIAN 001 | BAB I | PID 1\nSEBELUM:\nOld sentence one.\n\nSESUDAH:\nNew sentence one.\n\n-----\n"
                "BAGIAN 002 | BAB I | PID 2\nSEBELUM:\nOld sentence two.\n\nSESUDAH:\nNew sentence two.\n\n-----\n",
                encoding="utf-8",
            )
            make_docx(candidate, ["New sentence one."])
            make_docx(original, ["Old sentence one.", "Old sentence two."])
            report = audit_before_after_pairs(txt, candidate, original)
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(report["summary"]["pair_count"], 2)
            self.assertEqual(report["summary"]["after_matched_unique"], 1)
            self.assertEqual(report["summary"]["after_not_found"], 1)
            self.assertEqual(report["summary"]["before"]["matched_unique"], 2)

    def test_pair_audit_matches_multi_paragraph_after_block_with_whitespace_normalization(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            txt = root / "pairs.txt"
            docx = root / "candidate.docx"
            txt.write_text(
                "BAGIAN 001 | BAB I | PID 1\nSEBELUM:\nOriginal paragraph.\n\nSESUDAH:\nFirst revised line.\nSecond revised line.\n\n-----\n",
                encoding="utf-8",
            )
            make_docx(docx, ["First revised line.", "Second revised line."])
            report = audit_before_after_pairs(txt, docx)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["summary"]["after_matched_unique"], 1)

    def test_pair_audit_parses_new_bibliography_sections_without_pid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            txt = root / "pairs.txt"
            candidate = root / "candidate.docx"
            original = root / "original.docx"
            txt.write_text(
                """BAGIAN 153 | DAFTAR PUSTAKA
SEBELUM:
Tidak terdapat pada daftar pustaka original.

SESUDAH:
Reference Alpha (2020). Journal of Synthetic Tests.

-----
BAGIAN 154 | DAFTAR PUSTAKA
SEBELUM:
Tidak terdapat pada daftar pustaka original.

SESUDAH:
Reference Beta (2021). Journal of Synthetic Tests.

-----
BAGIAN 155 | DAFTAR PUSTAKA
SEBELUM:
Tidak terdapat pada daftar pustaka original.

SESUDAH:
Reference Gamma (2022). Journal of Synthetic Tests.

-----
""",
                encoding="utf-8",
            )
            make_docx(candidate, ["Reference Alpha (2020). Journal of Synthetic Tests.", "Reference Beta (2021). Journal of Synthetic Tests."])
            make_docx(original, ["Original bibliography only."])
            report = audit_before_after_pairs(txt, candidate, original)
            self.assertEqual(report["summary"]["pair_count"], 3)
            self.assertEqual(report["summary"]["after_matched_unique"], 2)
            self.assertEqual(report["summary"]["after_not_found"], 1)
            self.assertEqual(report["pair_results"][0]["before_status"], "NOT_APPLICABLE_NEW_CONTENT")

    def test_pair_audit_rejects_unreadable_docx_and_malformed_pair_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bad_txt = root / "bad.txt"
            bad_docx = root / "bad.docx"
            bad_txt.write_text("no pair structure", encoding="utf-8")
            bad_docx.write_bytes(b"not a zip")
            with self.assertRaises(RevisionQAError):
                audit_before_after_pairs(bad_txt, bad_docx)


class MarkedRegionAuditTests(unittest.TestCase):
    def _write(self, path: Path, extra: bool = True, duplicate: bool = False) -> None:
        fields = ["region_id", "mapping_status", "issue_class", "evidence_status", "disposition", "validation_status"]
        if extra:
            fields.append("rationale")
        rows = [
            ["MR-001", "MAPPED", "substantive", "full_text_inspected", "REVISE", "PASS"] + (["source claim verified"] if extra else []),
            ["MR-002", "LOW_CONFIDENCE", "religious", "metadata_only", "SOURCE_AUDIT_REQUIRED", "PENDING"] + ([""] if extra else []),
        ]
        if duplicate:
            rows.append(rows[0].copy())
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(fields)
            writer.writerows(rows)

    def test_register_preserves_unresolved_states_and_reports_rationale(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "regions.csv"
            self._write(path)
            report = audit_marked_region_register(path)
            self.assertEqual(report["status"], "CONDITIONAL")
            self.assertEqual(report["summary"]["row_count"], 2)
            self.assertEqual(report["summary"]["resolved_count"], 1)
            self.assertEqual(report["summary"]["mapping_status_counts"]["LOW_CONFIDENCE"], 1)

    def test_register_duplicate_ids_are_exposed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "regions.csv"
            self._write(path, duplicate=True)
            report = audit_marked_region_register(path)
            self.assertEqual(report["status"], "CONDITIONAL")
            self.assertEqual(report["summary"]["duplicate_region_ids"], ["MR-001"])

    def test_register_missing_required_column_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "regions.csv"
            path.write_text("region_id,mapping_status\nMR-001,MAPPED\n", encoding="utf-8")
            with self.assertRaises(RevisionQAError):
                audit_marked_region_register(path)


class EmpiricalConsistencyAuditTests(unittest.TestCase):
    def test_detects_demographic_and_methodology_contradictions(self):
        model = {
            "study_id": "SYNTHETIC-01",
            "sample": {"declared_n": 25, "participant_ids_available": False, "participant_ids_unique": False},
            "design": {"type": "ONE_GROUP_PRETEST_POSTTEST", "has_control_group": False},
            "demographic_distributions": [
                {"name": "juz", "counts": [7, 3, 10], "percentages": [28, 12, 60]},
                {"name": "age", "counts": [6, 18], "percentages": [24, 76]},
            ],
            "constructs": [
                {"id": "performance", "measurement_modality": "ORAL_PERFORMANCE_TEST"},
                {"id": "perception", "measurement_modality": "SELF_REPORT"},
            ],
            "analyses": [
                {"id": "paired", "procedure": "PAIRED_T_TEST", "pairing_key": None},
                {"id": "alpha", "procedure": "CRONBACH_ALPHA", "construct_ids": ["X", "Y"]},
                {"id": "icc", "procedure": "ICC", "rater_count": 5},
                {"id": "regression", "procedure": "LINEAR_REGRESSION", "dependent_construct_id": "perception", "claimed_target_construct_id": "performance", "outcome_kind": "ORAL_PERFORMANCE_TEST", "claims_causality": True, "p_value": ".000"},
            ],
        }
        report = audit_empirical_study_consistency(model)
        codes = {item["code"] for item in report["findings"]}
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("DEMOGRAPHIC_COUNTS_DO_NOT_MATCH_N", codes)
        self.assertIn("DEMOGRAPHIC_PERCENTAGE_MISMATCH", codes)
        self.assertIn("PAIRED_ANALYSIS_WITHOUT_VERIFIED_PAIRING_KEY", codes)
        self.assertIn("CRONBACH_ALPHA_POOLS_DISTINCT_CONSTRUCTS", codes)
        self.assertIn("ICC_CONFIGURATION_INCOMPLETE", codes)
        self.assertIn("ANALYSIS_OUTCOME_MODALITY_MISMATCH", codes)
        self.assertIn("ANALYSIS_CLAIMS_DIFFERENT_OUTCOME_CONSTRUCT", codes)
        self.assertIn("CAUSAL_CLAIM_EXCEEDS_DESIGN", codes)
        self.assertIn("P_VALUE_ROUNDED_TO_ZERO", codes)

    def test_paired_test_requires_appendix_output_and_difference_diagnostics(self):
        model = {
            "study_id": "SYNTHETIC-PAIRED-EVIDENCE",
            "sample": {"declared_n": 12, "participant_ids_available": False, "participant_ids_unique": False},
            "design": {"type": "ONE_GROUP_PRETEST_POSTTEST", "has_control_group": False},
            "constructs": [{"id": "oral", "measurement_modality": "ORAL_PERFORMANCE_TEST"}],
            "analyses": [{
                "id": "paired-test", "procedure": "PAIRED_T_TEST", "pairing_key": None,
                "dependent_construct_id": "oral", "outcome_kind": "ORAL_PERFORMANCE_TEST",
                "test_output_table_present": False,
                "pairing_method": "ROW_ORDER",
                "assumption_diagnostics": {"difference_distribution_reviewed": False}
            }]
        }
        report = audit_empirical_study_consistency(model)
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("PAIRED_TEST_OUTPUT_TABLE_MISSING", codes)
        self.assertIn("PAIRED_DIFFERENCE_DIAGNOSTICS_NOT_DOCUMENTED", codes)
        self.assertIn("PAIRED_ROWS_MATCHED_BY_ORDER_ONLY", codes)

    def test_instrument_validation_coverage_is_scoped_per_instrument(self):
        model = {
            "study_id": "SYNTHETIC-INSTRUMENTS",
            "sample": {"declared_n": 10},
            "design": {"type": "QUANTITATIVE_SURVEY", "has_control_group": False},
            "instruments": [
                {"id": "questionnaire", "item_count": 8,
                 "validity_evidence": {"method": "AIKEN_V", "status": "REPORTED", "validated_item_count": 8}},
                {"id": "oral-rubric", "item_count": 12,
                 "validity_evidence": {"method": "EXPERT_REVIEW", "status": "NOT_VISIBLE", "validated_item_count": None}}
            ]
        }
        report = audit_empirical_study_consistency(model)
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("INSTRUMENT_VALIDITY_EVIDENCE_NOT_VISIBLE", codes)
        self.assertNotIn("AIKEN_V_ITEM_COVERAGE_MISMATCH", codes)

    def test_aiken_coverage_must_match_declared_instrument_items(self):
        model = {
            "study_id": "SYNTHETIC-AIKEN",
            "sample": {"declared_n": 10},
            "design": {"type": "QUANTITATIVE_SURVEY", "has_control_group": False},
            "instruments": [{"id": "questionnaire", "item_count": 12,
                "validity_evidence": {"method": "AIKEN_V", "status": "REPORTED", "validated_item_count": 8}}]
        }
        report = audit_empirical_study_consistency(model)
        self.assertIn("AIKEN_V_ITEM_COVERAGE_MISMATCH", {item["code"] for item in report["findings"]})

    def test_valid_bounded_design_has_no_error(self):
        model = {
            "study_id": "SYNTHETIC-02",
            "sample": {"declared_n": 10, "participant_ids_available": True, "participant_ids_unique": True},
            "design": {"type": "ONE_GROUP_PRETEST_POSTTEST", "has_control_group": False},
            "demographic_distributions": [{"name": "group", "counts": [4, 6], "percentages": [40, 60]}],
            "constructs": [{"id": "outcome", "measurement_modality": "ORAL_PERFORMANCE_TEST"}],
            "analyses": [{"id": "paired", "procedure": "PAIRED_T_TEST", "pairing_key": "participant_id", "dependent_construct_id": "outcome", "outcome_kind": "ORAL_PERFORMANCE_TEST", "test_output_table_present": True, "assumption_diagnostics": {"difference_distribution_reviewed": True}}],
        }
        report = audit_empirical_study_consistency(model)
        self.assertEqual(report["status"], "PASS_WITH_NOTES")
        self.assertEqual(report["finding_counts"], {"INFO": 1})


class ArtifactManifestAuditTests(unittest.TestCase):
    def test_manifest_passes_then_detects_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifact = root / "draft.txt"
            artifact.write_text("immutable output\n", encoding="utf-8")
            import hashlib
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"artifacts": [{"id": "D1", "path": "draft.txt", "bytes": artifact.stat().st_size, "sha256": digest}]}), encoding="utf-8")
            self.assertEqual(audit_artifact_manifest(manifest)["status"], "PASS")
            artifact.write_text("changed output\n", encoding="utf-8")
            self.assertEqual(audit_artifact_manifest(manifest)["status"], "FAIL")

    def test_manifest_blocks_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"artifacts": [{"id": "bad", "path": "../secret.txt", "bytes": 1, "sha256": "0"}]}), encoding="utf-8")
            self.assertEqual(audit_artifact_manifest(manifest)["status"], "FAIL")

    def test_write_report_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.json"
            write_report({"status": "PASS"}, path)
            with self.assertRaises(RevisionQAError):
                write_report({"status": "FAIL"}, path)


if __name__ == "__main__":
    unittest.main()
