from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from project_skripsi.methodology import audit_research_alignment
from project_skripsi.cli import main as cli_main
from project_skripsi.service import init_project
from project_skripsi.validation import validate_workspace


def valid_alignment() -> dict:
    return {
        "schema_version": "1.0.0",
        "project_id": "alignment-test-001",
        "research_design": "QUANTITATIVE_SURVEY",
        "research_questions": [
            {"question_id": "RQ1", "text": "Is X associated with Y?", "intent": "RELATIONAL", "unit_of_analysis": "student"}
        ],
        "objectives": [
            {"objective_id": "OBJ1", "text": "Examine the association between X and Y.", "research_question_ids": ["RQ1"]}
        ],
        "constructs": [
            {"construct_id": "X", "name": "X", "role": "PREDICTOR", "conceptual_definition": "Concept X", "operationalization": "Mean of a validated item set", "measurement_level": "INTERVAL", "indicators": ["X1", "X2"]},
            {"construct_id": "Y", "name": "Y", "role": "OUTCOME", "conceptual_definition": "Concept Y", "operationalization": "Mean of a validated item set", "measurement_level": "INTERVAL", "indicators": ["Y1", "Y2"]}
        ],
        "hypotheses": [
            {"hypothesis_id": "H1", "text": "X is positively associated with Y.", "research_question_ids": ["RQ1"], "predictor_construct_ids": ["X"], "outcome_construct_ids": ["Y"], "direction": "POSITIVE", "theoretical_basis_source_ids": ["SRC-THEORY-001", "SRC-THEORY-002"]}
        ],
        "analysis_plan": [
            {"analysis_id": "A1", "research_question_ids": ["RQ1"], "hypothesis_ids": ["H1"], "construct_ids": ["X", "Y"], "strategy": "INFERENTIAL", "technique": "Correlation analysis (researcher-selected)", "selection_rationale": "Selected to address the relational question using the defined paired construct scores.", "assumption_diagnostics": ["linearity", "outliers", "distribution"]}
        ],
        "integration_points": []
    }


class ResearchAlignmentAuditTests(unittest.TestCase):
    def test_coherent_quantitative_alignment_is_ready_only_for_human_review(self):
        result = audit_research_alignment(valid_alignment())
        self.assertEqual(result["status"], "READY_FOR_HUMAN_REVIEW")
        self.assertEqual(result["summary"]["errors"], 0)
        self.assertEqual(result["human_approval"], "NOT_GRANTED")
        self.assertEqual(result["findings"], [])

    def test_unknown_objective_question_reference_is_error(self):
        doc = valid_alignment()
        doc["objectives"][0]["research_question_ids"] = ["RQ-UNKNOWN"]
        result = audit_research_alignment(doc)
        self.assertEqual(result["status"], "NEEDS_REVISION")
        self.assertTrue(any(item["code"] == "REFERENCE_UNKNOWN" for item in result["findings"]))

    def test_unmapped_research_question_is_error(self):
        doc = valid_alignment()
        doc["research_questions"].append({"question_id": "RQ2", "text": "What is the distribution of Y?", "intent": "DESCRIPTIVE"})
        result = audit_research_alignment(doc)
        self.assertTrue(any(item["code"] == "QUESTION_WITHOUT_ANALYSIS" for item in result["findings"]))

    def test_hypothesis_constructs_must_be_present_in_its_analysis(self):
        doc = valid_alignment()
        doc["analysis_plan"][0]["construct_ids"] = ["X"]
        result = audit_research_alignment(doc)
        self.assertTrue(any(item["code"] == "HYPOTHESIS_CONSTRUCTS_NOT_IN_ANALYSIS" for item in result["findings"]))

    def test_analysis_hypothesis_must_cover_its_research_questions(self):
        doc = valid_alignment()
        doc["research_questions"].append({"question_id": "RQ2", "text": "Does Y differ by group?", "intent": "COMPARATIVE"})
        doc["objectives"].append({"objective_id": "OBJ2", "text": "Compare Y across groups.", "research_question_ids": ["RQ2"]})
        doc["hypotheses"][0]["research_question_ids"] = ["RQ1", "RQ2"]
        result = audit_research_alignment(doc)
        self.assertTrue(any(item["code"] == "HYPOTHESIS_QUESTION_ANALYSIS_MISMATCH" for item in result["findings"]))

    def test_causal_question_in_observational_design_is_review_warning(self):
        doc = valid_alignment()
        doc["research_questions"][0]["intent"] = "CAUSAL"
        result = audit_research_alignment(doc)
        self.assertEqual(result["status"], "READY_FOR_HUMAN_REVIEW")
        self.assertTrue(any(item["code"] == "CAUSAL_INFERENCE_REVIEW_REQUIRED" for item in result["findings"]))

    def test_inferential_plan_without_diagnostics_is_flagged(self):
        doc = valid_alignment()
        doc["analysis_plan"][0]["assumption_diagnostics"] = []
        result = audit_research_alignment(doc)
        self.assertTrue(any(item["code"] == "INFERENTIAL_DIAGNOSTICS_REVIEW" for item in result["findings"]))

    def test_mixed_methods_requires_explicit_integration(self):
        doc = valid_alignment()
        doc["research_design"] = "MIXED_METHODS"
        result = audit_research_alignment(doc)
        self.assertTrue(any(item["code"] == "MIXED_INTEGRATION_REQUIRED" for item in result["findings"]))

    def test_mixed_methods_integration_references_both_strands(self):
        doc = valid_alignment()
        doc["research_design"] = "MIXED_METHODS"
        doc["analysis_plan"].append({
            "analysis_id": "A2", "research_question_ids": ["RQ1"], "strategy": "THEMATIC_ANALYSIS",
            "technique": "Thematic analysis", "selection_rationale": "Explore participant accounts as a qualitative strand.",
            "assumption_diagnostics": []
        })
        doc["integration_points"] = [{
            "integration_id": "INT1", "stage": "INTERPRETATION", "quant_analysis_ids": ["A1"],
            "qual_analysis_ids": ["A2"], "integration_rationale": "Compare convergences and divergences across strands."
        }]
        result = audit_research_alignment(doc)
        self.assertFalse(any(item["code"] == "MIXED_INTEGRATION_REQUIRED" for item in result["findings"]))
        self.assertEqual(result["status"], "READY_FOR_HUMAN_REVIEW")

    def test_qualitative_hypothesis_is_warning_not_blanket_rejection(self):
        doc = valid_alignment()
        doc["research_design"] = "QUALITATIVE"
        result = audit_research_alignment(doc)
        self.assertTrue(any(item["code"] == "HYPOTHESIS_IN_QUALITATIVE_DESIGN_REVIEW" for item in result["findings"]))
        self.assertNotEqual(result["status"], "NEEDS_REVISION")

    def test_mixed_methods_rejects_quantitative_strategy_in_qualitative_strand(self):
        doc = valid_alignment()
        doc["research_design"] = "MIXED_METHODS"
        doc["analysis_plan"].append({
            "analysis_id": "A2", "research_question_ids": ["RQ1"], "strategy": "INFERENTIAL",
            "technique": "Second quantitative model", "selection_rationale": "A separately specified quantitative analysis.",
            "assumption_diagnostics": ["model diagnostics"]
        })
        doc["integration_points"] = [{
            "integration_id": "INT1", "stage": "INTERPRETATION", "quant_analysis_ids": ["A1"],
            "qual_analysis_ids": ["A2"], "integration_rationale": "Integrate the two strands."
        }]
        # A1 is inferential and is therefore valid only in the quantitative strand.
        result = audit_research_alignment(doc)
        self.assertTrue(any(item["code"] == "INTEGRATION_STRAND_STRATEGY_MISMATCH" for item in result["findings"]))

    def test_duplicate_mixed_methods_integration_ids_are_rejected(self):
        doc = valid_alignment()
        doc["research_design"] = "MIXED_METHODS"
        doc["analysis_plan"].append({
            "analysis_id": "A2", "research_question_ids": ["RQ1"], "strategy": "THEMATIC_ANALYSIS",
            "technique": "Thematic analysis", "selection_rationale": "Qualitative strand.", "assumption_diagnostics": []
        })
        point = {
            "integration_id": "INT1", "stage": "INTERPRETATION", "quant_analysis_ids": ["A1"],
            "qual_analysis_ids": ["A2"], "integration_rationale": "Integrate the two strands."
        }
        doc["integration_points"] = [copy.deepcopy(point), copy.deepcopy(point)]
        result = audit_research_alignment(doc)
        self.assertTrue(any(item["code"] == "DUPLICATE_INTEGRATION_ID" for item in result["findings"]))

    def test_unsupported_schema_version_is_error(self):
        doc = valid_alignment()
        doc["schema_version"] = "9.9.9"
        result = audit_research_alignment(doc)
        self.assertTrue(any(item["code"] == "SCHEMA_VERSION_UNSUPPORTED" for item in result["findings"]))

    def test_malformed_enum_types_return_findings_without_crashing(self):
        doc = valid_alignment()
        doc["research_design"] = []
        doc["research_questions"][0]["intent"] = {"bad": "type"}
        doc["constructs"][0]["role"] = []
        doc["analysis_plan"][0]["strategy"] = {"bad": "type"}
        result = audit_research_alignment(doc)
        codes = {item["code"] for item in result["findings"]}
        self.assertTrue({"DESIGN_UNSUPPORTED", "QUESTION_INTENT_UNSUPPORTED", "CONSTRUCT_ROLE_UNSUPPORTED", "ANALYSIS_STRATEGY_UNSUPPORTED"}.issubset(codes))

    def test_duplicate_ids_are_errors(self):
        doc = valid_alignment()
        doc["objectives"].append(copy.deepcopy(doc["objectives"][0]))
        result = audit_research_alignment(doc)
        self.assertTrue(any(item["code"] == "DUPLICATE_ID" for item in result["findings"]))

    def test_alignment_profile_project_and_design_must_match(self):
        profile = {"project_id": "other-project", "research_design": "QUALITATIVE", "research_question_ids": ["RQ9"]}
        result = audit_research_alignment(valid_alignment(), methodology_profile=profile)
        codes = {item["code"] for item in result["findings"]}
        self.assertTrue({"PROJECT_ID_MISMATCH", "DESIGN_MISMATCH", "QUESTION_REGISTER_MISMATCH"}.issubset(codes))

    def test_alignment_references_are_checked_against_project_source_register(self):
        register = {
            "project_id": "alignment-test-001",
            "sources": [
                {"source_id": "SRC-THEORY-001", "access_status": "METADATA_ONLY"},
                {"source_id": "SRC-THEORY-002", "access_status": "FULL_TEXT_REVIEWED"},
                {"source_id": "SRC-INSTRUMENT-001", "access_status": "FULL_TEXT_REVIEWED"}
            ]
        }
        result = audit_research_alignment(valid_alignment(), source_register=register)
        codes = {item["code"] for item in result["findings"]}
        self.assertNotIn("SOURCE_REFERENCE_UNKNOWN", codes)
        self.assertIn("SOURCE_SCOPE_LIMITED_REVIEW_REQUIRED", codes)

    def test_unknown_source_reference_is_error(self):
        register = {"project_id": "alignment-test-001", "sources": []}
        result = audit_research_alignment(valid_alignment(), source_register=register)
        self.assertTrue(any(item["code"] == "SOURCE_REFERENCE_UNKNOWN" for item in result["findings"]))

    def test_source_register_must_be_project_scoped(self):
        register = {"project_id": "different-project", "sources": []}
        result = audit_research_alignment(valid_alignment(), source_register=register)
        self.assertTrue(any(item["code"] == "SOURCE_REGISTER_PROJECT_MISMATCH" for item in result["findings"]))

    def test_non_object_input_returns_structured_error(self):
        result = audit_research_alignment([])  # type: ignore[arg-type]
        self.assertEqual(result["status"], "NEEDS_REVISION")
        self.assertEqual(result["findings"][0]["code"], "DOCUMENT_NOT_OBJECT")

    def test_alignment_schema_is_valid_and_accepts_coherent_example(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema optional dependency is not installed")
        schema = json.loads(Path("schemas/methodology/research-alignment.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        self.assertEqual(list(validator.iter_errors(valid_alignment())), [])

    def test_workspace_initializes_project_scoped_alignment_scaffold(self):
        with tempfile.TemporaryDirectory() as temp:
            project = init_project(
                project_id="methodology-001", title="Methodology Test", discipline="Education",
                research_design="QUALITATIVE", institution="Test University", workspace_root=Path(temp) / "ws"
            )
            alignment_path = project / "methodology/design/research_alignment.json"
            data = json.loads(alignment_path.read_text(encoding="utf-8"))
            self.assertEqual(data["project_id"], "methodology-001")
            self.assertEqual(data["research_design"], "QUALITATIVE")
            self.assertEqual(data["research_questions"], [])
            errors, _manifest, _ledger = validate_workspace(project)
            self.assertEqual(errors, [])

    def test_workspace_validation_rejects_alignment_design_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            project = init_project(
                project_id="methodology-002", title="Methodology Test", discipline="Education",
                research_design="QUALITATIVE", institution="Test University", workspace_root=Path(temp) / "ws"
            )
            path = project / "methodology/design/research_alignment.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["research_design"] = "QUANTITATIVE_SURVEY"
            path.write_text(json.dumps(data), encoding="utf-8")
            errors, _manifest, _ledger = validate_workspace(project)
            self.assertTrue(any("research alignment research_design" in item for item in errors))

    def test_workspace_validation_rejects_symlinked_alignment_path(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = init_project(
                project_id="methodology-symlink", title="Methodology Test", discipline="Education",
                research_design="QUALITATIVE", institution="Test University", workspace_root=root / "ws"
            )
            path = project / "methodology/design/research_alignment.json"
            target = root / "outside.json"
            target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            path.unlink()
            try:
                path.symlink_to(target)
            except OSError:
                self.skipTest("symlink creation is not permitted")
            errors, _manifest, _ledger = validate_workspace(project)
            self.assertTrue(any("symlinked components" in item for item in errors))

    def test_legacy_workspace_without_alignment_remains_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            project = init_project(
                project_id="methodology-legacy", title="Legacy Workspace", discipline="Education",
                research_design="QUALITATIVE", institution="Test University", workspace_root=Path(temp) / "ws"
            )
            (project / "methodology/design/research_alignment.json").unlink()
            errors, _manifest, _ledger = validate_workspace(project)
            self.assertEqual(errors, [])

    def test_cli_scaffold_migrates_legacy_workspace_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            project = init_project(
                project_id="methodology-migrate", title="Legacy Workspace", discipline="Education",
                research_design="QUALITATIVE", institution="Test University", workspace_root=Path(temp) / "ws"
            )
            path = project / "methodology/design/research_alignment.json"
            path.unlink()
            code = cli_main(["methodology-scaffold", str(project)])
            self.assertEqual(code, 0)
            scaffold = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(scaffold["project_id"], "methodology-migrate")
            self.assertEqual(scaffold["research_design"], "QUALITATIVE")
            second = cli_main(["methodology-scaffold", str(project)])
            self.assertEqual(second, 2)

    def test_cli_methodology_audit_writes_local_machine_readable_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            alignment = root / "alignment.json"
            profile = root / "profile.json"
            output = root / "report.json"
            alignment.write_text(json.dumps(valid_alignment()), encoding="utf-8")
            profile.write_text(json.dumps({
                "project_id": "alignment-test-001", "research_design": "QUANTITATIVE_SURVEY",
                "research_question_ids": ["RQ1"]
            }), encoding="utf-8")
            code = cli_main(["methodology-audit", str(alignment), "--profile", str(profile), "--output", str(output)])
            self.assertEqual(code, 0)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "READY_FOR_HUMAN_REVIEW")
            self.assertEqual(result["human_approval"], "NOT_GRANTED")

    def test_cli_methodology_audit_returns_nonzero_for_broken_alignment(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "alignment.json"
            document = valid_alignment()
            document["analysis_plan"] = []
            path.write_text(json.dumps(document), encoding="utf-8")
            code = cli_main(["methodology-audit", str(path)])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
