from __future__ import annotations

import copy
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from project_skripsi.service import init_project
from project_skripsi.statistics import (
    StatisticalEngineError,
    profile_csv,
    register_dataset,
    run_descriptive_analysis,
    recover_analysis_transactions,
    validate_analysis_specification,
    verify_analysis_run,
    reproduce_analysis_run,
)


def configure_analysis_workspace(root: Path) -> tuple[Path, Path]:
    workspace = init_project(
        root / "workspaces", project_id="stat-test-001", title="Statistical Engine Test",
        discipline="Education", research_design="QUANTITATIVE_SURVEY", institution="Test University",
    )
    # T0-T5 are accepted; T6 is explicitly scoped-authorized and in progress.
    ledger_path = workspace / "state/phase_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    for index, phase in enumerate(ledger["phases"]):
        if index <= 5:
            phase.update({
                "execution_status": "COMPLETE", "validation_status": "PASS",
                "human_acceptance_status": "ACCEPTED", "approval_status": "APPROVED",
                "authorization_status": "AUTHORIZED_SCOPED", "phase_conclusion": "COMPLETE_AND_APPROVED",
                "scope": f"Test scope {phase['phase_id']}", "evidence": [f"fixture-{phase['phase_id']}"],
                "blockers": [], "last_verified_at": datetime.now(timezone.utc).isoformat(),
            })
        elif phase["phase_id"] == "T6":
            phase.update({
                "execution_status": "IN_PROGRESS", "validation_status": "NOT_RUN",
                "human_acceptance_status": "PENDING", "approval_status": "PENDING",
                "authorization_status": "AUTHORIZED_SCOPED", "phase_conclusion": "NOT_STARTED",
                "scope": "Execute approved descriptive analysis", "evidence": [],
                "blockers": [], "last_verified_at": None,
            })
    ledger["current_phase"] = "T6"
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    alignment = {
        "schema_version": "1.0.0", "project_id": "stat-test-001", "research_design": "QUANTITATIVE_SURVEY",
        "research_questions": [{"question_id": "RQ1", "text": "What is the observed distribution?", "intent": "DESCRIPTIVE", "unit_of_analysis": "respondent"}],
        "objectives": [{"objective_id": "O1", "text": "Describe the observed variables.", "research_question_ids": ["RQ1"]}],
        "constructs": [
            {"construct_id": "C1", "name": "Score", "role": "OUTCOME", "measurement_level": "RATIO", "indicators": ["score"]},
            {"construct_id": "C2", "name": "Group", "role": "CONTROL", "measurement_level": "NOMINAL", "indicators": ["group"]},
        ],
        "hypotheses": [],
        "analysis_plan": [{
            "analysis_id": "A1", "research_question_ids": ["RQ1"], "hypothesis_ids": [],
            "construct_ids": ["C1", "C2"], "strategy": "DESCRIPTIVE", "technique": "Descriptive summary and frequencies",
            "selection_rationale": "The research question is descriptive and requires univariate summaries only.",
            "assumption_diagnostics": ["Review missingness and observed category frequencies."],
            "planned_outputs": ["Descriptive summary", "Frequency table"],
        }],
        "integration_points": [],
    }
    (workspace / "methodology/design/research_alignment.json").write_text(json.dumps(alignment, indent=2) + "\n", encoding="utf-8")

    csv_path = workspace / "data/raw/respondents.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["score", "group"])
        writer.writerows([
            [10, "A"], [20, "A"], [30, "A"], [40, "A"], [50, "A"],
            [60, "B"], [70, "B"], [80, "B"], [90, "B"], ["", "C"],
        ])

    register_dataset(
        workspace, csv_path, artifact_id="DATASET-001", origin="Synthetic unit-test fixture",
        privacy_classification="CONFIDENTIAL", permission_status="APPROVED",
    )

    decision_register_path = workspace / "decisions/decision_register.json"
    decision_register = json.loads(decision_register_path.read_text(encoding="utf-8"))
    decision_register["decisions"].append({
        "decision_id": "DEC-METHOD-001", "decision_type": "METHOD_SELECTION_APPROVAL", "status": "APPROVED",
        "reviewer_role": "SUPERVISOR", "decided_at": datetime.now(timezone.utc).isoformat(),
        "rationale": "The descriptive method fits the approved descriptive research question.",
        "scope": {"analysis_plan_id": "A1", "dataset_artifact_id": "DATASET-001", "method": "DESCRIPTIVE_SUMMARY"},
    })
    decision_register_path.write_text(json.dumps(decision_register, indent=2) + "\n", encoding="utf-8")

    specification = {
        "schema_version": "1.0.0", "project_id": "stat-test-001", "analysis_id": "ANALYSIS-001",
        "analysis_plan_id": "A1", "research_question_ids": ["RQ1"], "dataset_artifact_id": "DATASET-001",
        "method": "DESCRIPTIVE_SUMMARY",
        "justification": "The approved plan is descriptive and requires univariate summaries.",
        "human_method_approval": "APPROVED", "human_method_approval_reference": "DEC-METHOD-001",
        "variables": [
            {"variable_id": "V1", "column_name": "score", "construct_id": "C1", "operation": "NUMERIC_SUMMARY"},
            {"variable_id": "V2", "column_name": "group", "construct_id": "C2", "operation": "FREQUENCY_TABLE", "expose_category_labels": False},
        ],
        "missing_value_tokens": [""], "small_cell_suppression_threshold": 5,
        "assumption_review_notes": ["Review the approved codebook before interpretation."],
    }
    spec_path = workspace / "analysis/design/analysis_specification.json"
    spec_path.write_text(json.dumps(specification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return workspace, spec_path


class DatasetRegistrationTests(unittest.TestCase):
    def test_profile_csv_infers_types_and_missingness_without_raw_values(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "small.csv"
            path.write_text("number,label\n1,A\n2,B\n, C\n", encoding="utf-8")
            profile = profile_csv(path)
            self.assertEqual(profile["row_count"], 3)
            self.assertEqual(profile["columns"][0]["inferred_type"], "INTEGER")
            self.assertEqual(profile["columns"][0]["missing_count"], 1)
            self.assertEqual(profile["columns"][1]["inferred_type"], "TEXT")
            self.assertNotIn('"A"', json.dumps(profile))
            self.assertNotIn('"B"', json.dumps(profile))

    def test_profile_suppresses_numeric_aggregates_below_five_observations(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "tiny.csv"
            path.write_text("score\n10\n20\n30\n", encoding="utf-8")
            profile = profile_csv(path)
            column = profile["columns"][0]
            self.assertTrue(column["numeric_summary_suppressed"])
            self.assertIsNone(column["numeric_summary"])
            self.assertEqual(profile["numeric_summary_suppression_threshold"], 5)

    def test_zero_one_numeric_column_is_not_automatically_boolean(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "flags.csv"
            path.write_text("code\n0\n1\n0\n", encoding="utf-8")
            self.assertEqual(profile_csv(path)["columns"][0]["inferred_type"], "INTEGER")

    def test_rejects_duplicate_headers_and_wrong_row_width(self):
        with tempfile.TemporaryDirectory() as temp:
            duplicate = Path(temp) / "duplicate.csv"
            duplicate.write_text("x,x\n1,2\n", encoding="utf-8")
            with self.assertRaises(StatisticalEngineError):
                profile_csv(duplicate)
            malformed = Path(temp) / "malformed.csv"
            malformed.write_text("x,y\n1\n", encoding="utf-8")
            with self.assertRaises(StatisticalEngineError):
                profile_csv(malformed)

    def test_register_requires_workspace_data_directory_and_stable_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = init_project(root / "ws", project_id="stat-reg-001", title="Test", discipline="Education", research_design="QUANTITATIVE_SURVEY", institution="Uni")
            outside = root / "outside.csv"
            outside.write_text("x\n1\n", encoding="utf-8")
            with self.assertRaises(StatisticalEngineError):
                register_dataset(workspace, outside, artifact_id="DATASET-001", origin="test", permission_status="APPROVED")

    def test_registered_profile_contains_no_observed_category_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = init_project(root / "ws", project_id="stat-reg-002", title="Test", discipline="Education", research_design="QUANTITATIVE_SURVEY", institution="Uni")
            dataset = workspace / "data/raw/data.csv"
            dataset.parent.mkdir(parents=True, exist_ok=True)
            dataset.write_text("category\nSecret-A\nSecret-B\n", encoding="utf-8")
            result = register_dataset(workspace, dataset, artifact_id="DATASET-002", origin="local test", permission_status="APPROVED")
            record = json.loads((workspace / "data/registry/DATASET-002.json").read_text())
            self.assertNotIn("Secret-A", json.dumps(record))
            self.assertEqual(result["status"], "REGISTERED")
            try:
                from jsonschema import Draft202012Validator
            except ImportError:
                self.skipTest("jsonschema optional dependency not installed")
            schema = json.loads(Path("schemas/data/data-artifact.schema.json").read_text())
            Draft202012Validator.check_schema(schema)
            self.assertEqual(list(Draft202012Validator(schema).iter_errors(record)), [])

    def test_registration_refuses_symlinked_dataset(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks unavailable")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = init_project(root / "ws", project_id="stat-reg-003", title="Test", discipline="Education", research_design="QUANTITATIVE_SURVEY", institution="Uni")
            target = workspace / "data/raw/real.csv"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n1\n", encoding="utf-8")
            alias = workspace / "data/raw/alias.csv"
            try:
                alias.symlink_to(target)
            except OSError:
                self.skipTest("symlink creation not permitted")
            with self.assertRaises(StatisticalEngineError):
                register_dataset(workspace, alias, artifact_id="DATASET-003", origin="test", permission_status="APPROVED")


class DescriptiveAnalysisTests(unittest.TestCase):
    def test_end_to_end_descriptive_run_and_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            errors = validate_analysis_specification(workspace, json.loads(spec_path.read_text()))
            self.assertEqual(errors, [])
            result = run_descriptive_analysis(workspace, spec_path, run_id="RUN-STAT-001")
            self.assertEqual(result["status"], "CREATED")
            result_doc = json.loads((workspace / result["result_path"]).read_text())
            score = result_doc["variable_results"][0]
            self.assertEqual(score["n"], 9)
            self.assertEqual(score["missing_n"], 1)
            self.assertAlmostEqual(score["mean"], 50.0)
            freq = result_doc["variable_results"][1]
            self.assertEqual(freq["suppressed_category_count"], 2)
            self.assertIsNone(freq["suppressed_observation_count"])
            self.assertFalse(freq["category_labels_exposed"])
            self.assertNotIn('"A"', json.dumps(result_doc))
            verified = verify_analysis_run(workspace, "RUN-STAT-001")
            self.assertEqual(verified["status"], "PASS", verified["errors"])

    def test_interrupted_run_is_recovered_without_duplicate_audit_event(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            from project_skripsi import statistics
            with patch.object(statistics, "append_audit_event", side_effect=OSError("simulated crash before audit")):
                with self.assertRaises(OSError):
                    run_descriptive_analysis(workspace, spec_path, run_id="RUN-RECOVER-001")
            tx = workspace / "analysis/transactions/RUN-RECOVER-001.json"
            self.assertTrue(tx.exists())
            recovered = recover_analysis_transactions(workspace)
            self.assertEqual(recovered["status"], "PASS")
            self.assertEqual(recovered["recovered"], ["RUN-RECOVER-001"])
            self.assertFalse(tx.exists())
            verified = verify_analysis_run(workspace, "RUN-RECOVER-001")
            self.assertEqual(verified["status"], "PASS", verified["errors"])
            from project_skripsi.audit import read_audit_events
            ok, reason, events = read_audit_events(workspace / "audit/events.jsonl")
            self.assertTrue(ok, reason)
            matching = [e for e in events if e.get("object_id") == "RUN-RECOVER-001" and e.get("event_type") == "STATISTICAL_ANALYSIS_RUN_CREATED"]
            self.assertEqual(len(matching), 1)

    def test_interrupted_after_audit_append_recovers_without_duplicate_event(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            from project_skripsi import statistics
            original_append = statistics.append_audit_event
            def append_then_crash(*args, **kwargs):
                original_append(*args, **kwargs)
                raise OSError("simulated crash after durable audit append")
            with patch.object(statistics, "append_audit_event", side_effect=append_then_crash):
                with self.assertRaises(OSError):
                    run_descriptive_analysis(workspace, spec_path, run_id="RUN-RECOVER-002")
            recovered = recover_analysis_transactions(workspace)
            self.assertEqual(recovered["recovered"], ["RUN-RECOVER-002"])
            from project_skripsi.audit import read_audit_events
            ok, reason, events = read_audit_events(workspace / "audit/events.jsonl")
            self.assertTrue(ok, reason)
            matching = [e for e in events if e.get("object_id") == "RUN-RECOVER-002" and e.get("event_type") == "STATISTICAL_ANALYSIS_RUN_CREATED"]
            self.assertEqual(len(matching), 1)
            self.assertEqual(verify_analysis_run(workspace, "RUN-RECOVER-002")["status"], "PASS")

    def test_tampered_transaction_is_refused_and_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            from project_skripsi import statistics
            with patch.object(statistics, "append_audit_event", side_effect=OSError("crash")):
                with self.assertRaises(OSError):
                    run_descriptive_analysis(workspace, spec_path, run_id="RUN-RECOVER-003")
            tx = workspace / "analysis/transactions/RUN-RECOVER-003.json"
            payload = json.loads(tx.read_text())
            payload["result_payload"]["project_id"] = "tampered-project"
            tx.write_text(json.dumps(payload))
            with self.assertRaises(StatisticalEngineError):
                recover_analysis_transactions(workspace)
            self.assertTrue(tx.exists())

    def test_analysis_reproduction_matches_hash_without_writing_or_changing_review_status(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            run_descriptive_analysis(workspace, spec_path, run_id="RUN-REPRO-001")
            audit_before = (workspace / "audit/events.jsonl").read_bytes()
            run_path = workspace / "analysis/outputs/RUN-REPRO-001/run.json"
            run_before = json.loads(run_path.read_text(encoding="utf-8"))
            reproduction = reproduce_analysis_run(workspace, "RUN-REPRO-001")
            self.assertEqual(reproduction["status"], "REPRODUCED", reproduction)
            self.assertTrue(reproduction["hash_match"])
            self.assertFalse(reproduction["writes_performed"])
            self.assertFalse(reproduction["audit_events_written"])
            self.assertEqual(reproduction["independent_reviewer_confirmation"], "NOT_PERFORMED")
            self.assertEqual((workspace / "audit/events.jsonl").read_bytes(), audit_before)
            run_after = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertEqual(run_after["review_status"], "NOT_REVIEWED")
            self.assertEqual(run_after, run_before)

    def test_analysis_diagnostic_summary_is_read_only_and_limits_claims(self):
        from project_skripsi.statistics import summarize_analysis_diagnostics
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            run_descriptive_analysis(workspace, spec_path, run_id="RUN-DIAG-001")
            audit_before = (workspace / "audit/events.jsonl").read_bytes()
            report = summarize_analysis_diagnostics(workspace, "RUN-DIAG-001")
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(sum(report["severity_counts"].values()), report["diagnostic_count"])
            self.assertIn("Normality", report["scope_notice"])
            self.assertFalse(report["writes_performed"])
            self.assertFalse(report["audit_events_written"])
            self.assertEqual((workspace / "audit/events.jsonl").read_bytes(), audit_before)

    def test_recovery_refuses_when_pinned_dataset_changes_after_crash(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            from project_skripsi import statistics
            with patch.object(statistics, "append_audit_event", side_effect=OSError("simulated crash before audit")):
                with self.assertRaises(OSError):
                    run_descriptive_analysis(workspace, spec_path, run_id="RUN-DRIFT-001")
            tx = workspace / "analysis/transactions/RUN-DRIFT-001.json"
            self.assertTrue(tx.exists())
            with (workspace / "data/raw/respondents.csv").open("a", encoding="utf-8") as stream:
                stream.write("100,D\n")
            with self.assertRaisesRegex(StatisticalEngineError, "pinned source inputs changed"):
                recover_analysis_transactions(workspace)
            self.assertTrue(tx.exists(), "failed recovery must preserve the journal")
            self.assertTrue((workspace / "analysis/outputs/RUN-DRIFT-001/results.json").exists())

    def test_project_manifest_change_invalidates_run_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            run_descriptive_analysis(workspace, spec_path, run_id="RUN-MANIFEST-001")
            project_path = workspace / "project.json"
            project = json.loads(project_path.read_text(encoding="utf-8"))
            project["title"] = "Changed after run"
            project_path.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            verification = verify_analysis_run(workspace, "RUN-MANIFEST-001")
            self.assertEqual(verification["status"], "FAIL")
            self.assertTrue(any("project_manifest_path" in error for error in verification["errors"]))

    def test_process_termination_recovery_at_real_persistence_boundaries(self):
        stages = ("transaction", "results", "run_record", "after_audit")
        for index, stage in enumerate(stages, start=1):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temp:
                workspace, spec_path = configure_analysis_workspace(Path(temp))
                run_id = f"RUN-PROCKILL-{index:03d}"
                worker = r"""
import os, sys
from pathlib import Path
from project_skripsi import statistics
workspace, spec_path, run_id, stage = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
if stage == "after_audit":
    original = statistics.append_audit_event
    def abrupt_after_audit(*args, **kwargs):
        original(*args, **kwargs)
        os._exit(73)
    statistics.append_audit_event = abrupt_after_audit
else:
    original = statistics._atomic_json
    target = {"transaction": run_id + ".json", "results": "results.json", "run_record": "run.json"}[stage]
    def abrupt_after_write(path, value):
        original(path, value)
        if path.name == target:
            os._exit(73)
    statistics._atomic_json = abrupt_after_write
statistics.run_descriptive_analysis(workspace, spec_path, run_id=run_id)
raise SystemExit(0)
"""
                env = os.environ.copy()
                source_root = str(Path(__file__).resolve().parents[1] / "src")
                env["PYTHONPATH"] = source_root + os.pathsep + env.get("PYTHONPATH", "")
                process = subprocess.run(
                    [sys.executable, "-c", worker, str(workspace), str(spec_path), run_id, stage],
                    env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
                )
                self.assertEqual(process.returncode, 73, process.stdout + process.stderr)
                recovered = recover_analysis_transactions(workspace)
                self.assertEqual(recovered["status"], "PASS")
                self.assertEqual(recovered["recovered"], [run_id])
                verified = verify_analysis_run(workspace, run_id)
                self.assertEqual(verified["status"], "PASS", verified["errors"])
                reproduction = reproduce_analysis_run(workspace, run_id)
                self.assertEqual(reproduction["status"], "REPRODUCED", reproduction)

    def test_numeric_summary_is_suppressed_for_small_n(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            dataset = workspace / "data/raw/respondents.csv"
            dataset.write_text("score,group\n100,A\n200,B\n", encoding="utf-8")
            register_dataset(workspace, dataset, artifact_id="DATASET-SMALL", origin="small synthetic fixture", permission_status="APPROVED")
            spec = json.loads(spec_path.read_text())
            spec["dataset_artifact_id"] = "DATASET-SMALL"
            spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
            decision_path = workspace / "decisions/decision_register.json"
            decisions = json.loads(decision_path.read_text())
            decisions["decisions"][0]["scope"]["dataset_artifact_id"] = "DATASET-SMALL"
            decision_path.write_text(json.dumps(decisions, indent=2) + "\n", encoding="utf-8")
            result = run_descriptive_analysis(workspace, spec_path, run_id="RUN-STAT-SMALL")
            data = json.loads((workspace / result["result_path"]).read_text())
            numeric = data["variable_results"][0]
            self.assertTrue(numeric["summary_suppressed"])
            self.assertIsNone(numeric["mean"])
            self.assertIsNone(numeric["minimum"])
            self.assertTrue(any(item["code"] == "SMALL_SAMPLE_SUPPRESSION_APPLIED" for item in data["assumption_diagnostics"]))

    def test_same_inputs_produce_same_result_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            first = run_descriptive_analysis(workspace, spec_path, run_id="RUN-STAT-002")
            second = run_descriptive_analysis(workspace, spec_path, run_id="RUN-STAT-003")
            self.assertEqual(first["result_sha256"], second["result_sha256"])

    def test_requires_explicit_human_method_approval_and_decision_record(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            spec = json.loads(spec_path.read_text())
            spec["human_method_approval"] = "NOT_GRANTED"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            self.assertTrue(any("human methodology approval" in item for item in validate_analysis_specification(workspace, spec)))

    def test_approval_record_scope_must_match_data_and_analysis(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            path = workspace / "decisions/decision_register.json"
            register = json.loads(path.read_text())
            register["decisions"][0]["scope"]["dataset_artifact_id"] = "DATASET-OTHER"
            path.write_text(json.dumps(register), encoding="utf-8")
            errors = validate_analysis_specification(workspace, json.loads(spec_path.read_text()))
            self.assertTrue(any("decision scope" in item for item in errors))

    def test_phase_gate_blocks_analysis_before_t5_and_t6_authorization(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            ledger_path = workspace / "state/phase_ledger.json"
            ledger = json.loads(ledger_path.read_text())
            ledger["phases"][5]["phase_conclusion"] = "NOT_STARTED"
            ledger["phases"][5]["execution_status"] = "IN_PROGRESS"
            ledger["phases"][5]["authorization_status"] = "AUTHORIZED_SCOPED"
            ledger["current_phase"] = "T5"
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            errors = validate_analysis_specification(workspace, json.loads(spec_path.read_text()))
            self.assertTrue(any("T5" in item for item in errors), errors)

    def test_inferential_plan_cannot_be_run_by_descriptive_engine(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            alignment_path = workspace / "methodology/design/research_alignment.json"
            alignment = json.loads(alignment_path.read_text())
            alignment["analysis_plan"][0]["strategy"] = "INFERENTIAL"
            alignment_path.write_text(json.dumps(alignment), encoding="utf-8")
            errors = validate_analysis_specification(workspace, json.loads(spec_path.read_text()))
            self.assertTrue(any("DESCRIPTIVE" in item for item in errors))

    def test_dataset_changed_after_registration_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            dataset = workspace / "data/raw/respondents.csv"
            dataset.write_text(dataset.read_text() + "100,A\n", encoding="utf-8")
            errors = validate_analysis_specification(workspace, json.loads(spec_path.read_text()))
            self.assertTrue(any("SHA-256 has changed" in item for item in errors))

    def test_confidential_category_labels_cannot_be_exposed(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            spec = json.loads(spec_path.read_text())
            spec["variables"][1]["expose_category_labels"] = True
            errors = validate_analysis_specification(workspace, spec)
            self.assertTrue(any("cannot expose category labels" in item for item in errors))

    def test_output_directory_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            run_descriptive_analysis(workspace, spec_path, run_id="RUN-STAT-004")
            with self.assertRaises(FileExistsError):
                run_descriptive_analysis(workspace, spec_path, run_id="RUN-STAT-004")

    def test_result_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            run = run_descriptive_analysis(workspace, spec_path, run_id="RUN-STAT-005")
            output = workspace / run["result_path"]
            output.write_text(output.read_text() + " ", encoding="utf-8")
            verified = verify_analysis_run(workspace, "RUN-STAT-005")
            self.assertEqual(verified["status"], "FAIL")
            self.assertTrue(any("result SHA-256 mismatch" in item for item in verified["errors"]))

    def test_run_record_tampering_is_pinned_by_audit_event(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            run = run_descriptive_analysis(workspace, spec_path, run_id="RUN-STAT-REC")
            run_path = workspace / run["run_record_path"]
            record = json.loads(run_path.read_text())
            record["review_status"] = "SELF_REVIEWED"
            run_path.write_text(json.dumps(record), encoding="utf-8")
            verified = verify_analysis_run(workspace, "RUN-STAT-REC")
            self.assertEqual(verified["status"], "FAIL")
            self.assertTrue(any("run record SHA-256" in item for item in verified["errors"]))

    def test_dataset_change_after_run_is_detected_by_verify(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            run_descriptive_analysis(workspace, spec_path, run_id="RUN-STAT-006")
            dataset = workspace / "data/raw/respondents.csv"
            dataset.write_text(dataset.read_text() + "100,A\n", encoding="utf-8")
            verified = verify_analysis_run(workspace, "RUN-STAT-006")
            self.assertEqual(verified["status"], "FAIL")
            self.assertTrue(any("dataset_path content hash mismatch" in item for item in verified["errors"]))

    def test_new_workspace_analysis_scaffold_conforms_to_schema(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema optional dependency not installed")
        with tempfile.TemporaryDirectory() as temp:
            workspace = init_project(Path(temp) / "ws", project_id="stat-scaffold-001", title="Scaffold", discipline="Education", research_design="QUANTITATIVE_SURVEY", institution="Uni")
            spec = json.loads((workspace / "analysis/design/analysis_specification.json").read_text())
            schema = json.loads(Path("schemas/analysis/analysis-specification.schema.json").read_text())
            Draft202012Validator.check_schema(schema)
            self.assertEqual(list(Draft202012Validator(schema).iter_errors(spec)), [])

    def test_specification_schema_and_run_record_schema_accept_generated_records(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema optional dependency not installed")
        from project_skripsi.quality import validate_analysis_run
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            spec = json.loads(spec_path.read_text())
            schema_path = Path("schemas/analysis/analysis-specification.schema.json")
            schema = json.loads(schema_path.read_text())
            Draft202012Validator.check_schema(schema)
            self.assertEqual(list(Draft202012Validator(schema).iter_errors(spec)), [])
            result = run_descriptive_analysis(workspace, spec_path, run_id="RUN-STAT-007")
            run_record = json.loads((workspace / result["run_record_path"]).read_text())
            self.assertEqual(validate_analysis_run(run_record), [])
            run_schema = json.loads(Path("schemas/analysis/analysis-run.schema.json").read_text())
            Draft202012Validator.check_schema(run_schema)
            self.assertEqual(list(Draft202012Validator(run_schema).iter_errors(run_record)), [])
            self.assertIn("project_manifest_sha256", run_record)
            self.assertEqual(run_record["reproducibility_contract"]["hash_algorithm"], "SHA-256")
            legacy_record = copy.deepcopy(run_record)
            legacy_record["software"] = {"name": legacy_record["software"]["name"], "version": "0.5.1", "python_version": run_record["software"]["python_version"]}
            for field in ("project_manifest_path", "project_manifest_sha256", "reproducibility_contract"):
                legacy_record.pop(field, None)
            self.assertEqual(list(Draft202012Validator(run_schema).iter_errors(legacy_record)), [])
            result_doc = json.loads((workspace / result["result_path"]).read_text())
            result_schema = json.loads(Path("schemas/analysis/analysis-results.schema.json").read_text())
            Draft202012Validator.check_schema(result_schema)
            self.assertEqual(list(Draft202012Validator(result_schema).iter_errors(result_doc)), [])
            approval = json.loads((workspace / "decisions/decision_register.json").read_text())["decisions"][0]
            approval_schema = json.loads(Path("schemas/governance/methodology-approval.schema.json").read_text())
            Draft202012Validator.check_schema(approval_schema)
            self.assertEqual(list(Draft202012Validator(approval_schema).iter_errors(approval)), [])


class MalformedInputHardeningTests(unittest.TestCase):
    def test_malformed_question_ids_return_validation_error_without_type_error(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["research_question_ids"] = [{"not": "a string"}]
            errors = validate_analysis_specification(workspace, spec)
            self.assertTrue(any("research_question_ids" in item for item in errors))

    def test_malformed_file_profile_returns_validation_error(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            artifact_path = workspace / "data/registry/DATASET-001.json"
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            artifact["file_profile"] = ["not", "an", "object"]
            artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
            errors = validate_analysis_specification(workspace, json.loads(spec_path.read_text(encoding="utf-8")))
            self.assertTrue(any("file_profile" in item for item in errors))

    def test_malformed_decision_scope_returns_validation_error(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            decision_path = workspace / "decisions/decision_register.json"
            register = json.loads(decision_path.read_text(encoding="utf-8"))
            register["decisions"][0]["scope"] = "not-an-object"
            decision_path.write_text(json.dumps(register), encoding="utf-8")
            errors = validate_analysis_specification(workspace, json.loads(spec_path.read_text(encoding="utf-8")))
            self.assertTrue(any("scope must be an object" in item for item in errors))

    def test_malformed_plan_construct_ids_return_validation_error(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            alignment_path = workspace / "methodology/design/research_alignment.json"
            alignment = json.loads(alignment_path.read_text(encoding="utf-8"))
            alignment["analysis_plan"][0]["construct_ids"] = [{"bad": "id"}]
            alignment_path.write_text(json.dumps(alignment), encoding="utf-8")
            errors = validate_analysis_specification(workspace, json.loads(spec_path.read_text(encoding="utf-8")))
            self.assertTrue(any("construct_ids must be an array of strings" in item for item in errors))

    def test_malformed_variable_operation_returns_validation_error(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["variables"][0]["operation"] = {"unexpected": "object"}
            errors = validate_analysis_specification(workspace, spec)
            self.assertTrue(any("operation must be" in item for item in errors))

    def test_malformed_variable_column_and_construct_ids_return_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["variables"][0]["column_name"] = ["score"]
            spec["variables"][1]["construct_id"] = {"bad": "id"}
            errors = validate_analysis_specification(workspace, spec)
            self.assertTrue(any("column_name is required" in item for item in errors))
            self.assertTrue(any("construct_id" in item for item in errors))

    def test_malformed_decisions_collection_returns_validation_error(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            decision_path = workspace / "decisions/decision_register.json"
            register = json.loads(decision_path.read_text(encoding="utf-8"))
            register["decisions"] = {"not": "an array"}
            decision_path.write_text(json.dumps(register), encoding="utf-8")
            errors = validate_analysis_specification(workspace, json.loads(spec_path.read_text(encoding="utf-8")))
            self.assertTrue(any("decisions must be an array" in item for item in errors))

    def test_malformed_assumption_review_notes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["assumption_review_notes"] = {"note": "not a list"}
            errors = validate_analysis_specification(workspace, spec)
            self.assertTrue(any("assumption_review_notes must be an array" in item for item in errors))

class DisclosureControlTests(unittest.TestCase):
    def test_single_primary_small_cell_triggers_complementary_suppression(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            dataset = workspace / "data/raw/respondents.csv"
            with dataset.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["score", "group"])
                for score in range(1, 12):
                    writer.writerow([score, "A" if score <= 7 else "B"])
            register_dataset(workspace, dataset, artifact_id="DATASET-COMP", origin="synthetic disclosure fixture", permission_status="APPROVED")
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["dataset_artifact_id"] = "DATASET-COMP"
            spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
            decision_path = workspace / "decisions/decision_register.json"
            decision_register = json.loads(decision_path.read_text(encoding="utf-8"))
            decision_register["decisions"][0]["scope"]["dataset_artifact_id"] = "DATASET-COMP"
            decision_path.write_text(json.dumps(decision_register, indent=2) + "\n", encoding="utf-8")
            run = run_descriptive_analysis(workspace, spec_path, run_id="RUN-COMP-001")
            results = json.loads((workspace / run["result_path"]).read_text(encoding="utf-8"))
            frequency = results["variable_results"][1]
            self.assertTrue(frequency["complementary_suppression_applied"])
            self.assertEqual(frequency["suppressed_category_count"], 2)
            self.assertIsNone(frequency["suppressed_observation_count"])
            self.assertIsNone(frequency["valid_n"])
            self.assertEqual(frequency["categories"], [])

    def test_duplicate_column_mapping_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace, spec_path = configure_analysis_workspace(Path(temp))
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["variables"][1]["column_name"] = "score"
            errors = validate_analysis_specification(workspace, spec)
            self.assertTrue(any("column_name must be unique" in item for item in errors))

    def test_csv_column_limit_is_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "too-wide.csv"
            path.write_text(",".join(f"c{i}" for i in range(5001)) + "\n", encoding="utf-8")
            with self.assertRaises(StatisticalEngineError):
                profile_csv(path)


class StableHashTests(unittest.TestCase):
    def test_file_mutated_during_hash_is_rejected(self):
        from project_skripsi import statistics
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "input.csv"
            target.write_text("x\n1\n", encoding="utf-8")
            original = statistics.sha256_file
            def mutate_after_hash(path):
                digest = original(path)
                path.write_text("x\nchanged-content\n", encoding="utf-8")
                return digest
            with patch.object(statistics, "sha256_file", side_effect=mutate_after_hash):
                with self.assertRaisesRegex(StatisticalEngineError, "changed while its SHA-256"):
                    statistics.sha256_file_stable(target)


class ResourceBoundTests(unittest.TestCase):
    def test_global_distinct_value_tracking_budget_is_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "wide-categories.csv"
            path.write_text("left,right\nA,X\nB,Y\nA,Z\nC,X\n", encoding="utf-8")
            with patch("project_skripsi.statistics.MAX_DISTINCT_TRACK_TOTAL", 3):
                profile = profile_csv(path)
            right = profile["columns"][1]
            self.assertTrue(right["distinct_count_truncated"])
            self.assertGreaterEqual(right["distinct_count_lower_bound"], 2)


if __name__ == "__main__":
    unittest.main()
