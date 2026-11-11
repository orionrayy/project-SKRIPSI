from __future__ import annotations

import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_skripsi.audit import verify_audit_log
from project_skripsi.integrations.openalex import (
    OpenAlexClient,
    normalize_work,
    reconstruct_abstract,
)
from project_skripsi.quality import validate_source_register
from project_skripsi.research import build_literature_matrix, search_project_literature
from project_skripsi.service import init_project


def work_payload(*, with_abstract: bool = True) -> dict:
    record = {
        "id": "https://openalex.org/W123456789",
        "doi": "https://doi.org/10.5555/EXAMPLE.1",
        "display_name": "A Reproducible Example Study",
        "publication_year": 2024,
        "publication_date": "2024-05-10",
        "type": "article",
        "authorships": [
            {"author": {"display_name": "Ayu Sari"}},
            {"author": {"display_name": "Bima Putra"}},
        ],
        "primary_location": {"landing_page_url": "https://publisher.example/article", "license": None},
        "open_access": {"is_oa": True, "oa_status": "gold", "oa_url": "https://repository.example/paper"},
        "language": "en",
        "cited_by_count": 9,
    }
    if with_abstract:
        record["abstract_inverted_index"] = {
            "This": [0], "study": [1], "uses": [2], "public": [3], "data.": [4]
        }
    return record


def fake_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
    return response


class OpenAlexNormalizationTests(unittest.TestCase):
    def test_reconstructs_inverted_index_in_position_order(self):
        self.assertEqual(
            reconstruct_abstract({"second": [1], "first": [0], "third": [2]}),
            "first second third",
        )

    def test_rejects_incomplete_or_malformed_inverted_index(self):
        self.assertIsNone(reconstruct_abstract({"start": [0], "end": [2]}))
        self.assertIsNone(reconstruct_abstract({"broken": "not-a-list"}))
        self.assertIsNone(reconstruct_abstract(None))

    def test_metadata_default_does_not_promote_unretrieved_abstract(self):
        normalized = normalize_work(work_payload(), retrieval_date="2026-11-05", include_abstract=False)
        self.assertIsNotNone(normalized)
        source = normalized["source"]
        self.assertEqual(source["access_status"], "METADATA_ONLY")
        self.assertNotIn("abstract", normalized)
        self.assertEqual(source["rights_status"], "UNKNOWN")
        self.assertEqual(source["doi"], "10.5555/example.1")

    def test_explicit_abstract_retrieval_is_labelled_abstract_only(self):
        normalized = normalize_work(work_payload(), retrieval_date="2026-11-05", include_abstract=True)
        self.assertEqual(normalized["source"]["access_status"], "ABSTRACT_ONLY")
        self.assertEqual(normalized["source"]["exact_locator"], "OpenAlex abstract_inverted_index (provider-reconstructed abstract)")
        self.assertEqual(normalized["abstract"], "This study uses public data.")
        self.assertEqual(validate_source_register([normalized["source"]]), [])

    def test_rejects_work_without_openalex_id_or_title(self):
        self.assertIsNone(normalize_work({"id": "https://example.org/x", "display_name": "Title"}, retrieval_date="2026-11-05", include_abstract=False))
        self.assertIsNone(normalize_work({"id": "https://openalex.org/W1"}, retrieval_date="2026-11-05", include_abstract=False))


class OpenAlexClientTests(unittest.TestCase):
    def test_basic_request_omits_api_key_and_abstract_field_by_default(self):
        payload = {"meta": {"count": 1}, "results": [work_payload()]}
        opener = MagicMock()
        opener.open.return_value = fake_response(payload)
        with tempfile.TemporaryDirectory() as tmp:
            client = OpenAlexClient(cache_dir=Path(tmp), opener=opener, sleeper=lambda _seconds: None)
            result = client.search("research methods", per_page=5)
            request = opener.open.call_args.args[0]
            params = parse_qs(urlparse(request.full_url).query)
            self.assertNotIn("api_key", params)
            self.assertNotIn("abstract_inverted_index", params["select"][0])
            self.assertEqual(result["result_count"], 1)
            self.assertEqual(result["items"][0]["source"]["access_status"], "METADATA_ONLY")
            cache_file = next(Path(tmp).glob("*.json"))
            self.assertEqual(cache_file.stat().st_mode & 0o777, 0o600)

    def test_api_key_is_sent_as_bearer_header_not_url_or_cache_metadata(self):
        payload = {"meta": {"count": 0}, "results": []}
        opener = MagicMock()
        opener.open.return_value = fake_response(payload)
        with tempfile.TemporaryDirectory() as tmp:
            client = OpenAlexClient(cache_dir=Path(tmp), api_key="test-secret-key", opener=opener)
            result = client.search("auth test")
            request = opener.open.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer test-secret-key")
            self.assertNotIn("test-secret-key", request.full_url)
            self.assertNotIn("test-secret-key", result["request_url"])
            cache_text = next(Path(tmp).glob("*.json")).read_text(encoding="utf-8")
            self.assertNotIn("test-secret-key", cache_text)

    def test_no_cache_bypasses_cache_reads_and_writes(self):
        payload = {"meta": {"count": 0}, "results": []}
        opener = MagicMock()
        opener.open.return_value = fake_response(payload)
        with tempfile.TemporaryDirectory() as tmp:
            client = OpenAlexClient(cache_dir=Path(tmp), opener=opener)
            client.search("no cache", use_cache=False)
            self.assertEqual(list(Path(tmp).glob("*.json")), [])

    def test_abstract_field_is_requested_only_after_explicit_opt_in(self):
        payload = {"meta": {"count": 1}, "results": [work_payload()]}
        opener = MagicMock()
        opener.open.return_value = fake_response(payload)
        client = OpenAlexClient(opener=opener, sleeper=lambda _seconds: None)
        result = client.search("research methods", include_abstracts=True)
        request = opener.open.call_args.args[0]
        params = parse_qs(urlparse(request.full_url).query)
        self.assertIn("abstract_inverted_index", params["select"][0])
        self.assertEqual(result["items"][0]["abstract"], "This study uses public data.")

    def test_cache_is_reused_without_network(self):
        payload = {"meta": {"count": 1}, "results": [work_payload(with_abstract=False)]}
        opener = MagicMock()
        opener.open.return_value = fake_response(payload)
        with tempfile.TemporaryDirectory() as tmp:
            first = OpenAlexClient(cache_dir=Path(tmp), opener=opener, sleeper=lambda _seconds: None)
            self.assertFalse(first.search("cache test")["cache_hit"])
            second_opener = MagicMock()
            second = OpenAlexClient(cache_dir=Path(tmp), opener=second_opener)
            result = second.search("cache test")
            self.assertTrue(result["cache_hit"])
            second_opener.open.assert_not_called()

    def test_retry_after_is_respected_for_rate_limit(self):
        payload = {"meta": {"count": 0}, "results": []}
        opener = MagicMock()
        rate_error = urllib.error.HTTPError(
            "https://api.openalex.org/works", 429, "limited", {"Retry-After": "2"}, None
        )
        opener.open.side_effect = [rate_error, fake_response(payload)]
        sleeps: list[float] = []
        client = OpenAlexClient(opener=opener, sleeper=sleeps.append, max_retries=1)
        result = client.search("rate test")
        self.assertEqual(sleeps, [2.0])
        self.assertEqual(result["result_count"], 0)

    def test_exhausted_429_is_actionable_and_bounded(self):
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError(
            "https://api.openalex.org/works", 429, "limited", {"Retry-After": "30"}, None
        )
        client = OpenAlexClient(opener=opener, sleeper=lambda _seconds: None, max_retries=0)
        with self.assertRaisesRegex(RuntimeError, "rate limit reached"):
            client.search("rate test")
        self.assertEqual(opener.open.call_count, 1)

    def test_redirects_are_refused(self):
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError(
            "https://api.openalex.org/works", 302, "redirect", {}, None
        )
        client = OpenAlexClient(opener=opener, max_retries=0)
        with self.assertRaisesRegex(RuntimeError, "redirect refused"):
            client.search("redirect test")

    def test_query_and_page_size_are_bounded(self):
        client = OpenAlexClient(opener=MagicMock())
        with self.assertRaises(ValueError):
            client.search("   ")
        with self.assertRaises(ValueError):
            client.search("q", per_page=26)
        with self.assertRaises(ValueError):
            client.search("x" * 501)


class ProjectSearchPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name) / "workspaces"
        self.first = init_project(
            root, project_id="thesis-2026-101", title="Research title",
            discipline="Information Systems", research_design="QUALITATIVE_CASE_STUDY",
            institution="Example University",
        )
        self.second = init_project(
            root, project_id="thesis-2026-102", title="Another research title",
            discipline="Information Systems", research_design="QUALITATIVE_CASE_STUDY",
            institution="Example University",
        )

    def tearDown(self):
        self.temp.cleanup()

    def fake_client(self, *, include_abstracts=False):
        from project_skripsi.integrations.openalex import normalize_work
        normalized = normalize_work(work_payload(), retrieval_date="2026-11-05", include_abstract=include_abstracts)

        class FakeClient:
            def search(self, query, **kwargs):
                return {
                    "provider": "openalex", "query": query, "retrieved_at": "2026-11-05T00:00:00+00:00",
                    "request_url": "https://api.openalex.org/works?search=test", "cache_hit": False,
                    "total_count": 1, "per_page": kwargs.get("per_page", 10),
                    "result_count": 1, "abstracts_requested": include_abstracts,
                    "items": [normalized], "flags": ["Human screening required."],
                }
        return FakeClient()

    def test_search_persists_private_snapshot_register_and_audit(self):
        result = search_project_literature(self.first, "test query", client=self.fake_client())
        self.assertEqual(result["status"], "PERSISTED")
        self.assertEqual(result["new_sources"], 1)
        snapshot = Path(result["snapshot"])
        self.assertTrue(snapshot.is_file())
        register = json.loads(Path(result["register"]).read_text(encoding="utf-8"))
        self.assertEqual(len(register["sources"]), 1)
        self.assertEqual(register["sources"][0]["access_status"], "METADATA_ONLY")
        self.assertEqual(validate_source_register(register["sources"]), [])
        self.assertTrue(verify_audit_log(self.first / "audit" / "events.jsonl")[0])
        self.assertEqual(snapshot.stat().st_mode & 0o777, 0o600)
        snapshot_payload = json.loads(snapshot.read_text(encoding="utf-8"))
        self.assertIn("retrieved_at", snapshot_payload)
        try:
            import jsonschema
            from referencing import Registry, Resource
            schema = json.loads((ROOT / "schemas/research/openalex-search-snapshot.schema.json").read_text(encoding="utf-8"))
            source_schema = json.loads((ROOT / "schemas/evidence/source-record.schema.json").read_text(encoding="utf-8"))
            registry = Registry().with_resource(source_schema["$id"], Resource.from_contents(source_schema))
            jsonschema.Draft202012Validator(schema, registry=registry).validate(snapshot_payload)
        except ImportError:
            pass

    def test_repeat_search_deduplicates_registry_and_preserves_snapshots(self):
        first = search_project_literature(self.first, "test query", client=self.fake_client())
        second = search_project_literature(self.first, "test query", client=self.fake_client())
        self.assertEqual(first["new_sources"], 1)
        self.assertEqual(second["new_sources"], 0)
        self.assertEqual(second["duplicates_skipped"], 1)
        register = json.loads((self.first / "sources/registry/source_register.json").read_text())
        self.assertEqual(len(register["sources"]), 1)
        snapshots = list((self.first / "sources/snapshots").glob("OPENALEX-*.json"))
        self.assertEqual(len(snapshots), 2)

    def test_abstract_opt_in_persists_content_with_abstract_only_status(self):
        result = search_project_literature(
            self.first, "test query", include_abstracts=True,
            client=self.fake_client(include_abstracts=True),
        )
        snapshot = json.loads(Path(result["snapshot"]).read_text())
        self.assertIn("abstract", snapshot["items"][0])
        register = json.loads((self.first / "sources/registry/source_register.json").read_text())
        self.assertEqual(register["sources"][0]["access_status"], "ABSTRACT_ONLY")

    def test_project_search_does_not_write_to_another_workspace(self):
        search_project_literature(self.first, "test query", client=self.fake_client())
        other = json.loads((self.second / "sources/registry/source_register.json").read_text())
        self.assertEqual(other["sources"], [])
        self.assertEqual(list((self.second / "sources/snapshots").glob("*.json")), [])


    def test_literature_matrix_uses_saved_metadata_and_abstract_without_fabrication(self):
        search_project_literature(
            self.first, "test query", include_abstracts=True,
            client=self.fake_client(include_abstracts=True),
        )
        result = build_literature_matrix(self.first)
        import csv
        with Path(result["matrix"]).open("r", encoding="utf-8", newline="") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["title"], "A Reproducible Example Study")
        self.assertEqual(row["abstract"], "This study uses public data.")
        self.assertEqual(row["review_status"], "UNREVIEWED")
        self.assertEqual(row["method_summary"], "")
        self.assertEqual(row["findings_summary"], "")
        self.assertEqual(row["research_gap_notes"], "")
        coverage = json.loads(Path(result["coverage"]).read_text(encoding="utf-8"))
        self.assertEqual(coverage["source_count"], 1)
        self.assertEqual(coverage["abstract_snapshot_count"], 1)
        import jsonschema
        coverage_schema = json.loads((ROOT / "schemas/research/literature-coverage.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(coverage_schema).validate(coverage)
        self.assertEqual(Path(result["matrix"]).stat().st_mode & 0o777, 0o600)

    def test_literature_matrix_regeneration_preserves_manual_annotations(self):
        search_project_literature(self.first, "test query", client=self.fake_client())
        first = build_literature_matrix(self.first)
        import csv
        matrix_path = Path(first["matrix"])
        with matrix_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = reader.fieldnames
        rows[0]["method_summary"] = "Manual coding: cross-sectional survey"
        rows[0]["findings_summary"] = "Pending verification against the paper"
        rows[0]["review_status"] = "SELF_REVIEWED"
        with matrix_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        second = build_literature_matrix(self.first)
        with Path(second["matrix"]).open("r", encoding="utf-8", newline="") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["method_summary"], "Manual coding: cross-sectional survey")
        self.assertEqual(row["findings_summary"], "Pending verification against the paper")
        self.assertEqual(row["review_status"], "SELF_REVIEWED")
        self.assertGreaterEqual(second["human_annotations_preserved"], 1)

    def test_literature_matrix_refuses_output_outside_workspace_or_wrong_directory(self):
        with self.assertRaisesRegex(ValueError, "directly inside"):
            build_literature_matrix(self.first, output_path=Path(self.temp.name) / "leak.csv")
        with self.assertRaisesRegex(ValueError, "directly inside"):
            build_literature_matrix(self.first, output_path=self.first / "sources" / "registry" / "evil.csv")

    def test_literature_matrix_refuses_malformed_existing_file_without_overwrite(self):
        matrix_path = self.first / "literature" / "matrix" / "literature_matrix.csv"
        original = b"not_a_source_id,title\nA,Example\n"
        matrix_path.write_bytes(original)
        with self.assertRaisesRegex(ValueError, "no source_id column"):
            build_literature_matrix(self.first)
        self.assertEqual(matrix_path.read_bytes(), original)


    def test_search_refuses_symlinked_snapshot_directory_before_provider_call(self):
        if sys.platform == "win32":
            self.skipTest("symlink creation permissions vary on Windows")
        external = Path(self.temp.name) / "external-snapshots"
        external.mkdir()
        snapshot_dir = self.first / "sources" / "snapshots"
        snapshot_dir.rmdir()
        snapshot_dir.symlink_to(external, target_is_directory=True)

        class NeverCall:
            def search(self, *_args, **_kwargs):
                raise AssertionError("provider must not be called for escaped workspace path")

        with self.assertRaisesRegex(ValueError, "escaped project boundary"):
            search_project_literature(self.first, "test query", client=NeverCall())
        self.assertEqual(list(external.iterdir()), [])

    def test_matrix_csv_escapes_formula_like_provider_text(self):
        search_project_literature(self.first, "test query", client=self.fake_client())
        register_path = self.first / "sources/registry/source_register.json"
        register = json.loads(register_path.read_text(encoding="utf-8"))
        register["sources"][0]["title"] = "=HYPERLINK(\"https://evil.example\",\"click\")"
        register_path.write_text(json.dumps(register), encoding="utf-8")
        result = build_literature_matrix(self.first)
        import csv
        with Path(result["matrix"]).open("r", encoding="utf-8", newline="") as handle:
            row = next(csv.DictReader(handle))
        self.assertTrue(row["title"].startswith("'=HYPERLINK"))


    def test_invalid_workspace_is_rejected_before_provider_search(self):
        register_path = self.first / "sources/registry/source_register.json"
        register = json.loads(register_path.read_text())
        register["project_id"] = "other-project-001"
        register_path.write_text(json.dumps(register))

        class NeverCall:
            def search(self, *_args, **_kwargs):
                raise AssertionError("provider must not be called for invalid workspace")

        with self.assertRaisesRegex(ValueError, "workspace validation failed"):
            search_project_literature(self.first, "test query", client=NeverCall())


if __name__ == "__main__":
    unittest.main()
