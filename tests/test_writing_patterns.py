from __future__ import annotations

import json
import unittest
from pathlib import Path

from project_skripsi.writing.patterns import assess_claim_strength, list_patterns


class WritingPatternTests(unittest.TestCase):
    def test_catalog_contains_multiple_academic_stages(self):
        patterns = list_patterns()
        self.assertGreaterEqual(len(patterns), 8)
        stages = {item["stage"] for item in patterns}
        self.assertTrue({"introduction", "literature_review", "results", "discussion", "conclusion"}.issubset(stages))
        self.assertTrue(all(item.get("template_id_text") and item.get("template_en_text") for item in patterns))
        catalog_path = Path(__file__).resolve().parents[1] / "data" / "writing" / "evidence-safe-patterns.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertEqual([item["pattern_id"] for item in catalog["patterns"]], [item["pattern_id"] for item in patterns])

    def test_pattern_catalog_entries_match_json_schema_when_available(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("optional jsonschema extra is not installed")
        root = Path(__file__).resolve().parents[1]
        schema = json.loads((root / "schemas/writing/evidence-safe-pattern.schema.json").read_text(encoding="utf-8"))
        catalog = json.loads((root / "data/writing/evidence-safe-patterns.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        errors = [error.message for item in catalog["patterns"] for error in validator.iter_errors(item)]
        self.assertEqual(errors, [])

    def test_observational_data_cannot_justify_causal_claim(self):
        result = assess_claim_strength(
            evidence_level="observational",
            requested_strength="causal",
            research_design="QUANTITATIVE_SURVEY",
        )
        self.assertEqual(result["status"], "HIGH_RISK_REVIEW_REQUIRED")
        self.assertFalse(result["automatically_approved"])

    def test_causal_claim_still_needs_human_reviewer_and_is_not_auto_approved(self):
        result = assess_claim_strength(
            evidence_level="direct",
            requested_strength="causal",
            research_design="QUANTITATIVE_EXPERIMENT",
            causal_identification_reviewed=True,
            human_reviewer_role="methodology_reviewer",
        )
        self.assertEqual(result["status"], "HIGH_RISK_REVIEW_REQUIRED")
        self.assertFalse(result["automatically_approved"])

    def test_bounded_association_claim_still_requires_human_review(self):
        result = assess_claim_strength(
            evidence_level="observational",
            requested_strength="bounded",
            research_design="QUANTITATIVE_SURVEY",
        )
        self.assertEqual(result["status"], "NEEDS_HUMAN_REVIEW")
        self.assertFalse(result["automatically_approved"])

    def test_strong_claim_with_no_evidence_is_flagged(self):
        result = assess_claim_strength(
            evidence_level="none",
            requested_strength="assertive",
            research_design="QUALITATIVE",
        )
        self.assertEqual(result["status"], "OVERCLAIM_RISK")


if __name__ == "__main__":
    unittest.main()
