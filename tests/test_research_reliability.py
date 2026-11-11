from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from project_skripsi.audit import verify_audit_log
from project_skripsi.integrations.openalex import normalize_work
from project_skripsi.research import (
    recover_research_transactions,
    research_integrity_check,
    search_project_literature,
)
from project_skripsi.service import init_project
from project_skripsi.validation import load_json


def _work_payload() -> dict:
    return {
        "id": "https://openalex.org/W1234567890",
        "doi": "https://doi.org/10.5555/reliability.2026.1",
        "display_name": "A Reliability Test Study",
        "publication_year": 2026,
        "publication_date": "2026-01-15",
        "type": "article",
        "authorships": [{"author": {"display_name": "Example Author"}}],
        "primary_location": {"license": None},
        "open_access": {"oa_status": "closed", "oa_url": None},
        "language": "en",
        "cited_by_count": 0,
    }


class _FakeClient:
    def search(self, query: str, **kwargs):
        item = normalize_work(
            _work_payload(), retrieval_date="2026-11-05", include_abstract=kwargs.get("include_abstracts", False)
        )
        return {
            "provider": "openalex",
            "query": query,
            "retrieved_at": "2026-11-05T10:00:00+00:00",
            "request_url": "https://api.openalex.org/works?search=reliability",
            "cache_hit": False,
            "total_count": 1,
            "per_page": kwargs.get("per_page", 10),
            "result_count": 1,
            "abstracts_requested": bool(kwargs.get("include_abstracts", False)),
            "items": [item],
            "flags": ["Human screening required."],
        }


def _recover_worker(workspace: str, result_queue) -> None:
    try:
        result_queue.put(recover_research_transactions(Path(workspace)))
    except Exception as exc:  # pragma: no cover - only emitted on multiprocessing failure
        result_queue.put({"error": f"{type(exc).__name__}: {exc}"})


class ResearchRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = init_project(
            Path(self.temp.name) / "workspaces",
            project_id="reliability-test-001",
            title="Reliability Test",
            discipline="Information Systems",
            research_design="QUALITATIVE_CASE_STUDY",
            institution="Example University",
        )

    def tearDown(self):
        self.temp.cleanup()

    def _search(self):
        return search_project_literature(self.workspace, "reliability recovery test", client=_FakeClient())

    def _pending_files(self):
        journals = list((self.workspace / "state/research-transactions").glob("OPENALEX-*.json"))
        snapshots = list((self.workspace / "sources/snapshots").glob("OPENALEX-*.json"))
        return journals, snapshots

    def _audit_events(self):
        path = self.workspace / "audit/events.jsonl"
        if not path.exists():
            return []
        return [
            event for event in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
            if str(event.get("idempotency_key") or "").startswith("research-search:")
        ]

    def test_failure_after_snapshot_is_recovered_without_duplicate_snapshot_or_event(self):
        from project_skripsi import research as research_module
        real_validate = research_module.validate_source_register
        calls = 0

        def interrupt_on_apply(records):
            nonlocal calls
            calls += 1
            if calls == 3:
                return ["simulated interruption after snapshot persistence"]
            return real_validate(records)

        with patch("project_skripsi.research.validate_source_register", side_effect=interrupt_on_apply):
            with self.assertRaisesRegex(ValueError, "simulated interruption"):
                self._search()

        journals, snapshots = self._pending_files()
        self.assertEqual(len(journals), 1)
        self.assertEqual(len(snapshots), 1)
        register = load_json(self.workspace / "sources/registry/source_register.json")
        self.assertEqual(register["sources"], [])

        result = recover_research_transactions(self.workspace)
        self.assertEqual(result["status"], "RECOVERED")
        self.assertEqual(len(self._pending_files()[0]), 0)
        self.assertEqual(len(self._pending_files()[1]), 1)
        self.assertEqual(len(load_json(self.workspace / "sources/registry/source_register.json")["sources"]), 1)
        self.assertEqual(len(self._audit_events()), 1)
        self.assertTrue(verify_audit_log(self.workspace / "audit/events.jsonl")[0])
        self.assertEqual(research_integrity_check(self.workspace)["status"], "PASS")

    def test_failure_after_registry_before_audit_is_recovered(self):
        with patch("project_skripsi.research.append_audit_event", side_effect=OSError("simulated audit interruption")):
            with self.assertRaisesRegex(OSError, "simulated audit interruption"):
                self._search()
        journals, snapshots = self._pending_files()
        self.assertEqual((len(journals), len(snapshots)), (1, 1))
        register = load_json(self.workspace / "sources/registry/source_register.json")
        self.assertEqual(len(register["sources"]), 1)
        self.assertEqual(self._audit_events(), [])

        recover_research_transactions(self.workspace)
        self.assertEqual(len(self._audit_events()), 1)
        self.assertEqual(research_integrity_check(self.workspace)["status"], "PASS")

    def test_failure_after_audit_before_journal_retirement_is_idempotent(self):
        real_unlink = Path.unlink

        def fail_journal_retirement(path: Path, *args, **kwargs):
            if path.parent.name == "research-transactions" and path.suffix == ".json":
                raise OSError("simulated crash before journal retirement")
            return real_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", fail_journal_retirement):
            with self.assertRaisesRegex(OSError, "journal retirement"):
                self._search()
        self.assertEqual(len(self._audit_events()), 1)
        self.assertEqual(len(self._pending_files()[0]), 1)

        result = recover_research_transactions(self.workspace)
        self.assertEqual(result["status"], "RECOVERED")
        self.assertEqual(len(self._audit_events()), 1)
        self.assertTrue(verify_audit_log(self.workspace / "audit/events.jsonl")[0])

    def test_journal_checksum_detects_accidental_modification_before_recovery(self):
        from project_skripsi import research as research_module
        real_validate = research_module.validate_source_register
        calls = 0

        def interrupt_on_apply(records):
            nonlocal calls
            calls += 1
            if calls == 3:
                return ["hold journal for checksum test"]
            return real_validate(records)

        with patch("project_skripsi.research.validate_source_register", side_effect=interrupt_on_apply):
            with self.assertRaisesRegex(ValueError, "hold journal"):
                self._search()
        journals, _ = self._pending_files()
        payload = json.loads(journals[0].read_text(encoding="utf-8"))
        payload["snapshot"]["query"] = "modified after journal preparation"
        journals[0].write_text(json.dumps(payload), encoding="utf-8")

        report = research_integrity_check(self.workspace)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any("checksum mismatch" in issue for issue in report["issues"]))
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            recover_research_transactions(self.workspace)
        self.assertEqual(load_json(self.workspace / "sources/registry/source_register.json")["sources"], [])
        self.assertEqual(len(self._audit_events()), 0)

    def test_new_journal_matches_recovery_transaction_schema(self):
        from project_skripsi import research as research_module
        real_validate = research_module.validate_source_register
        calls = 0

        def interrupt_on_apply(records):
            nonlocal calls
            calls += 1
            if calls == 3:
                return ["leave prepared journal for schema test"]
            return real_validate(records)

        with patch("project_skripsi.research.validate_source_register", side_effect=interrupt_on_apply):
            with self.assertRaisesRegex(ValueError, "schema test"):
                self._search()
        journals, _ = self._pending_files()
        payload = json.loads(journals[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "1.1.0")
        try:
            import jsonschema
            from referencing import Registry, Resource
            schemas = [
                "schemas/research/openalex-recovery-transaction.schema.json",
                "schemas/research/openalex-search-snapshot.schema.json",
                "schemas/evidence/source-record.schema.json",
            ]
            registry = Registry()
            loaded = []
            for relative in schemas:
                schema = json.loads((Path(__file__).resolve().parents[1] / relative).read_text(encoding="utf-8"))
                loaded.append(schema)
                registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
            jsonschema.Draft202012Validator(loaded[0], registry=registry).validate(payload)
        except ImportError:
            self.skipTest("jsonschema/referencing is an optional validation extra")

    @unittest.skipUnless(os.name != "nt", "symlink behavior varies on Windows")
    def test_intermediate_workspace_symlink_is_refused_before_provider_call(self):
        cache_dir = self.workspace / "sources/cache/openalex"
        outside = Path(self.temp.name) / "outside-cache"
        outside.mkdir()
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        else:
            cache_dir.parent.mkdir(parents=True, exist_ok=True)
        cache_dir.symlink_to(outside, target_is_directory=True)

        class NeverCall:
            def search(self, *_args, **_kwargs):
                raise AssertionError("provider must not be called after workspace symlink detection")

        with self.assertRaisesRegex(ValueError, "symlinked workspace path"):
            search_project_literature(self.workspace, "must not call", client=NeverCall())
        self.assertEqual(list(outside.iterdir()), [])

    def test_integrity_check_reports_pending_recovery_without_mutating(self):
        from project_skripsi import research as research_module
        real_validate = research_module.validate_source_register
        calls = 0

        def interrupt_on_apply(records):
            nonlocal calls
            calls += 1
            if calls == 3:
                return ["pending transaction"]
            return real_validate(records)

        with patch("project_skripsi.research.validate_source_register", side_effect=interrupt_on_apply):
            with self.assertRaisesRegex(ValueError, "pending transaction"):
                self._search()
        before_journals, before_snapshots = self._pending_files()
        report = research_integrity_check(self.workspace)
        after_journals, after_snapshots = self._pending_files()
        self.assertEqual(report["status"], "RECOVERY_REQUIRED")
        self.assertEqual((len(before_journals), len(before_snapshots)), (1, 1))
        self.assertEqual((len(after_journals), len(after_snapshots)), (1, 1))

    @unittest.skipUnless(os.name != "nt", "POSIX process locking test")
    def test_two_processes_recover_one_journal_exactly_once(self):
        from project_skripsi import research as research_module
        real_validate = research_module.validate_source_register
        calls = 0

        def interrupt_on_apply(records):
            nonlocal calls
            calls += 1
            if calls == 3:
                return ["leave journal for multiprocessing test"]
            return real_validate(records)

        with patch("project_skripsi.research.validate_source_register", side_effect=interrupt_on_apply):
            with self.assertRaisesRegex(ValueError, "multiprocessing test"):
                self._search()

        context = multiprocessing.get_context("spawn")
        result_queue = context.Queue()
        processes = [
            context.Process(target=_recover_worker, args=(str(self.workspace), result_queue))
            for _ in range(2)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
            self.assertEqual(process.exitcode, 0)
        results = [result_queue.get(timeout=2) for _ in processes]
        self.assertTrue(all("error" not in result for result in results), results)
        self.assertEqual(len(self._audit_events()), 1)
        self.assertEqual(len(self._pending_files()[0]), 0)
        self.assertEqual(research_integrity_check(self.workspace)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
