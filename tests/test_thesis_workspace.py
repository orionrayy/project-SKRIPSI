from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_skripsi.audit import append_audit_event, verify_audit_log
from project_skripsi.quality import methodology_readiness, validate_analysis_run, validate_claim_evidence_links, validate_source_register
from project_skripsi.service import init_project, project_status
from project_skripsi.validation import ValidationError, validate_phase_ledger, validate_workspace


class ThesisWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "workspaces"

    def tearDown(self):
        self.temp.cleanup()

    def create(self, project_id="thesis-2026-001"):
        return init_project(
            self.root,
            project_id=project_id,
            title="A thesis title",
            discipline="Information Systems",
            research_design="QUANTITATIVE_SURVEY",
            institution="Example University",
        )

    def test_init_creates_private_isolated_workspace_and_valid_contracts(self):
        project = self.create()
        errors, manifest, ledger = validate_workspace(project)
        self.assertEqual(errors, [])
        self.assertEqual(manifest["project_id"], "thesis-2026-001")
        self.assertEqual(ledger["current_phase"], "T0")
        self.assertTrue((project / "data" / "raw").is_dir())
        self.assertTrue((project / "audit" / "events.jsonl").is_file())
        self.assertEqual(project_status(project)["current_phase"], "T0")

    def test_two_projects_never_share_manifest_or_audit_path(self):
        first = self.create("thesis-2026-001")
        second = self.create("thesis-2026-002")
        self.assertNotEqual(first, second)
        self.assertNotEqual(first / "audit" / "events.jsonl", second / "audit" / "events.jsonl")
        self.assertEqual(json.loads((first / "project.json").read_text())["project_id"], "thesis-2026-001")
        self.assertEqual(json.loads((second / "project.json").read_text())["project_id"], "thesis-2026-002")

    def test_path_traversal_project_id_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.create("../../outside")

    def test_existing_workspace_is_not_overwritten(self):
        project = self.create()
        original = (project / "project.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.create()
        self.assertEqual((project / "project.json").read_bytes(), original)

    def test_t1_cannot_start_before_t0_is_accepted(self):
        project = self.create()
        ledger_path = project / "state" / "phase_ledger.json"
        ledger = json.loads(ledger_path.read_text())
        ledger["phases"][1]["execution_status"] = "IN_PROGRESS"
        ledger["phases"][1]["authorization_status"] = "AUTHORIZED_SCOPED"
        errors = validate_phase_ledger(ledger, "thesis-2026-001")
        self.assertTrue(any("before T0 is COMPLETE_AND_APPROVED" in error for error in errors))

    def test_t0_cannot_start_without_scoped_authorization(self):
        project = self.create()
        ledger = json.loads((project / "state" / "phase_ledger.json").read_text())
        ledger["phases"][0]["execution_status"] = "IN_PROGRESS"
        errors = validate_phase_ledger(ledger, "thesis-2026-001")
        self.assertTrue(any("T0 cannot start without phase-specific scoped authorization" in error for error in errors))

    def test_phase_cannot_be_complete_without_human_acceptance(self):
        project = self.create()
        ledger = json.loads((project / "state" / "phase_ledger.json").read_text())
        phase = ledger["phases"][0]
        phase.update({
            "execution_status": "COMPLETE",
            "validation_status": "PASS",
            "human_acceptance_status": "PENDING",
            "approval_status": "APPROVED",
            "authorization_status": "APPROVED_SCOPED",
            "phase_conclusion": "COMPLETE_AND_APPROVED",
        })
        errors = validate_phase_ledger(ledger, "thesis-2026-001")
        self.assertTrue(any("without human ACCEPTED status" in error for error in errors))

    def test_audit_log_detects_tampering(self):
        project = self.create()
        path = project / "audit" / "events.jsonl"
        ok, message = verify_audit_log(path)
        self.assertTrue(ok, message)
        append_audit_event(path, event_type="note.added", object_type="decision", object_id="D1", summary="A minimal test event")
        ok, message = verify_audit_log(path)
        self.assertTrue(ok, message)
        rows = path.read_text().splitlines()
        event = json.loads(rows[0])
        event["summary"] = "tampered"
        rows[0] = json.dumps(event)
        path.write_text("\n".join(rows) + "\n")
        ok, message = verify_audit_log(path)
        self.assertFalse(ok)
        self.assertIn("hash mismatch", message)

    def test_source_registry_requires_exact_locator_for_abstract_evidence(self):
        records = [{
            "source_id": "SRC-001", "url": "https://example.org/paper", "access_status": "ABSTRACT_ONLY",
            "retrieval_date": "2026-11-05", "rights_status": "PUBLIC_WEB_ACCESS"
        }]
        errors = validate_source_register(records)
        self.assertTrue(any("exact_locator is required" in error for error in errors))

    def test_claim_link_cannot_use_metadata_only_source_for_content_claim(self):
        source = [{"source_id": "SRC-001", "access_status": "METADATA_ONLY"}]
        link = [{"claim_id": "CLM-1", "source_id": "SRC-001", "relation": "SUPPORTS", "exact_locator": "abstract"}]
        errors = validate_claim_evidence_links(link, source)
        self.assertTrue(any("metadata-only source can support bibliographic metadata only" in error for error in errors))


    def test_workspace_creates_project_scoped_starter_registers(self):
        project = self.create()
        source_register = json.loads((project / "sources/registry/source_register.json").read_text())
        method_profile = json.loads((project / "methodology/design/methodology_profile.json").read_text())
        approvals = json.loads((project / "state/approval_register.json").read_text())
        self.assertEqual(source_register["project_id"], "thesis-2026-001")
        self.assertEqual(source_register["sources"], [])
        self.assertEqual(method_profile["research_design"], "QUANTITATIVE_SURVEY")
        self.assertEqual(approvals["approvals"], [])
        self.assertTrue((project / "intake/INTAKE_CHECKLIST.md").is_file())
        self.assertTrue((project / "requirements/institution/PROFILE_README.md").is_file())
        if sys.platform != "win32":
            self.assertEqual(project.stat().st_mode & 0o777, 0o700)
            self.assertEqual((project / "project.json").stat().st_mode & 0o777, 0o600)


    def test_workspace_validation_rejects_cross_project_source_register(self):
        project = self.create()
        path = project / "sources/registry/source_register.json"
        source_register = json.loads(path.read_text())
        source_register["project_id"] = "another-thesis-001"
        path.write_text(json.dumps(source_register))
        errors, _manifest, _ledger = validate_workspace(project)
        self.assertTrue(any("source register project_id does not match" in error for error in errors))

    def test_workspace_validation_rejects_malformed_source_claim_links(self):
        project = self.create()
        path = project / "sources/registry/source_register.json"
        source_register = json.loads(path.read_text())
        source_register["claim_evidence_links"] = "not-an-array"
        path.write_text(json.dumps(source_register))
        errors, _manifest, _ledger = validate_workspace(project)
        self.assertTrue(any("claim_evidence_links must be an array" in error for error in errors))

    def test_current_phase_must_point_to_earliest_unaccepted_phase(self):
        project = self.create()
        ledger = json.loads((project / "state/phase_ledger.json").read_text())
        ledger["current_phase"] = "T3"
        errors = validate_phase_ledger(ledger, "thesis-2026-001")
        self.assertTrue(any("current_phase must point" in error for error in errors))

    def test_future_phase_cannot_be_authorized_before_predecessor_acceptance(self):
        project = self.create()
        ledger = json.loads((project / "state/phase_ledger.json").read_text())
        ledger["phases"][1]["authorization_status"] = "AUTHORIZED_SCOPED"
        errors = validate_phase_ledger(ledger, "thesis-2026-001")
        self.assertTrue(any("T1 cannot be authorized before T0" in error for error in errors))


    def test_generated_starter_artifacts_conform_to_json_schemas_when_available(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("optional jsonschema extra is not installed")
        project = self.create()
        pairs = [
            ("project.json", "schemas/projects/project-manifest.schema.json"),
            ("state/phase_ledger.json", "schemas/projects/thesis-phase-ledger.schema.json"),
            ("sources/registry/source_register.json", "schemas/evidence/source-register.schema.json"),
            ("methodology/design/methodology_profile.json", "schemas/methodology/methodology-profile.schema.json"),
            ("methodology/design/research_alignment.json", "schemas/methodology/research-alignment.schema.json"),
            ("state/approval_register.json", "schemas/governance/approval-register.schema.json"),
        ]
        for document_path, schema_path in pairs:
            with self.subTest(document=document_path):
                document = json.loads((project / document_path).read_text())
                schema = json.loads((ROOT / schema_path).read_text())
                validator = Draft202012Validator(schema)
                errors = list(validator.iter_errors(document))
                self.assertEqual(errors, [], "; ".join(error.message for error in errors))

    def test_schema_files_are_valid_json(self):
        schema_root = ROOT / "schemas"
        files = list(schema_root.rglob("*.schema.json"))
        self.assertGreaterEqual(len(files), 10)
        for schema_file in files:
            with self.subTest(schema=str(schema_file.relative_to(ROOT))):
                schema = json.loads(schema_file.read_text(encoding="utf-8"))
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_source_register_rejects_missing_provenance_fields(self):
        records = [{
            "source_id": "SRC-001", "url": "https://example.org/paper",
            "access_status": "METADATA_ONLY", "retrieval_date": "2026-11-05",
            "rights_status": "PUBLIC_WEB_ACCESS"
        }]
        errors = validate_source_register(records)
        self.assertTrue(any("source_type is required" in error for error in errors))
        self.assertTrue(any("title is required" in error for error in errors))


    def test_abstract_only_source_cannot_support_full_text_claim(self):
        source = [{"source_id": "SRC-001", "access_status": "ABSTRACT_ONLY"}]
        link = [{
            "claim_id": "CLM-1", "source_id": "SRC-001", "relation": "SUPPORTS",
            "claim_scope": "FULL_TEXT_SECTION", "exact_locator": "Chapter 4, p. 42",
            "support_level": "DIRECT", "review_status": "UNREVIEWED"
        }]
        errors = validate_claim_evidence_links(link, source)
        self.assertTrue(any("abstract-only source can support abstract-scope claims only" in error for error in errors))

    def test_metadata_only_source_can_only_support_bibliographic_metadata(self):
        source = [{"source_id": "SRC-001", "access_status": "METADATA_ONLY"}]
        link = [{
            "claim_id": "CLM-1", "source_id": "SRC-001", "relation": "SUPPORTS",
            "claim_scope": "BIBLIOGRAPHIC_METADATA", "exact_locator": "metadata/title",
            "support_level": "DIRECT", "review_status": "UNREVIEWED"
        }]
        errors = validate_claim_evidence_links(link, source)
        self.assertEqual(errors, [])

    def test_methodology_placeholder_does_not_count_as_complete(self):
        result = methodology_readiness({
            "research_design": "SECONDARY_DATA", "research_question_ids": ["RQ1"],
            "data_sources": ["SRC-001"], "analysis_plan": {"method": "to_be_decided"},
            "limitations": ["Coverage limits"]
        })
        self.assertFalse(result["ready_for_methodology_review"])
        self.assertIn("analysis_plan", result["missing_fields"])

    def test_analysis_record_requires_timezone_outputs_and_finite_parameters(self):
        errors = validate_analysis_run({
            "analysis_run_id": "RUN-1", "project_id": "thesis-2026-001",
            "run_at": "2026-11-05T12:00:00", "analysis_method": "regression",
            "software": {"name": "R", "version": "4.4"},
            "input_artifact_hashes": ["a" * 64], "script_or_command": "Rscript model.R",
            "parameters": {"alpha": float("nan")}, "outputs": [], "review_status": "NOT_REVIEWED"
        })
        self.assertTrue(any("timezone" in error for error in errors))
        self.assertTrue(any("outputs must contain" in error for error in errors))
        self.assertTrue(any("NaN" in error for error in errors))

    def test_methodology_readiness_is_design_specific_and_does_not_select_software(self):
        result = methodology_readiness({
            "research_design": "QUANTITATIVE_SURVEY",
            "research_question_ids": ["RQ1"],
            "data_sources": ["survey"],
            "analysis_plan": {"method": "to_be_decided"},
            "limitations": ["sample limitation"],
        })
        self.assertFalse(result["ready_for_methodology_review"])
        self.assertIn("assumptions_and_diagnostics", result["missing_fields"])
        self.assertNotIn("software", result)


if __name__ == "__main__":
    unittest.main()
