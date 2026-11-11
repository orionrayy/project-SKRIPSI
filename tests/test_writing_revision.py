from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from project_skripsi.writing.revision import (
    LocalOpenAICompatibleClient,
    audit_revision,
    build_revision_prompt,
)


class RevisionSafetyTests(unittest.TestCase):
    def test_prompt_forbids_detector_evasion_and_preserves_evidence(self):
        prompt = build_revision_prompt(
            "Hasil menunjukkan hubungan (Sari, 2024) sebesar 12%.",
            language="id-ID",
            source_ids=["SRC-01"],
        )
        self.assertIn("Do not write to lower a plagiarism/similarity score", prompt)
        self.assertIn("Preserve negation, uncertainty, limitations", prompt)
        self.assertIn("SRC-01", prompt)
        self.assertIn("PASSAGE BEGIN", prompt)

    def test_audit_detects_lost_citation_number_and_negation(self):
        original = "Tidak terdapat hubungan signifikan (Sari et al., 2024) dengan p = 0,03 pada 120 responden."
        candidate = "Terdapat hubungan yang kuat pada sejumlah responden."
        report = audit_revision(original, candidate)
        self.assertEqual(report["status"], "REVIEW_REQUIRED")
        self.assertIn("PROTECTED_SPANS_MISSING_OR_CHANGED", report["flags"])
        self.assertIn("EPISTEMIC_MARKER_COUNTS_CHANGED", report["flags"])
        self.assertTrue(report["human_semantic_review_required"])
        self.assertEqual(report["similarity_or_ai_detector_scoring"], "NOT_PERFORMED")

    def test_audit_never_claims_semantic_equivalence_even_when_structural_checks_clear(self):
        original = "Temuan mungkin berkaitan dengan paparan 5 mg (Sari, 2024)."
        candidate = "Temuan mungkin berkaitan dengan paparan 5 mg (Sari, 2024)."
        report = audit_revision(original, candidate)
        self.assertEqual(report["status"], "STRUCTURAL_CHECKS_CLEAR_HUMAN_REVIEW_REQUIRED")
        self.assertTrue(report["human_semantic_review_required"])
        self.assertTrue(report["limitations"])

    def test_audit_flags_new_numeric_or_citation_tokens(self):
        report = audit_revision("Studi ini membahas satu kelompok.", "Studi ini membahas 75 peserta.")
        self.assertIn("NEW_PROTECTED_SPANS_REQUIRE_SOURCE_CHECK", report["flags"])

    def test_revision_report_matches_schema_when_available(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("optional jsonschema extra is not installed")
        from pathlib import Path
        schema_path = Path(__file__).resolve().parents[1] / "schemas/writing/revision-audit-report.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        report = audit_revision("Hasil mungkin terkait (Sari, 2024).", "Hasil mungkin terkait (Sari, 2024).")
        errors = list(Draft202012Validator(schema).iter_errors(report))
        self.assertEqual(errors, [], "; ".join(error.message for error in errors))

    def test_prompt_rejects_blank_text_and_unknown_purpose(self):
        with self.assertRaises(ValueError):
            build_revision_prompt(" ")
        with self.assertRaises(ValueError):
            build_revision_prompt("valid text", purpose="anti-detector")

    def test_local_adapter_calls_only_the_configured_loopback_compatible_api(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({"choices": [{"message": {"content": "Revised text (Sari, 2024)."}}]}).encode()
        with patch("project_skripsi.writing.revision.build_opener") as opener:
            opener.return_value.open.return_value = response
            client = LocalOpenAICompatibleClient("http://127.0.0.1:1234/v1")
            result = client.revise("Original text (Sari, 2024).", model="test-model")
        self.assertEqual(result, "Revised text (Sari, 2024).")
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:1234/v1/chat/completions")

    def test_local_adapter_rejects_non_loopback_endpoint(self):
        with self.assertRaises(ValueError):
            LocalOpenAICompatibleClient("https://api.example.com/v1")
        with self.assertRaises(ValueError):
            LocalOpenAICompatibleClient("http://127.0.0.1:11434/v1?redirect=https://evil.example")


if __name__ == "__main__":
    unittest.main()
