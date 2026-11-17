from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

from project_skripsi.integrations.mendeley import (
    MendeleyClient, MendeleyConfig, MendeleyError, TokenStore,
    _next_link, _mendeley_source_record, sync_library_to_workspace, build_parser, main,
)


def make_client(tmp: str) -> MendeleyClient:
    return MendeleyClient(MendeleyConfig(
        client_id="demo-client", client_secret="demo-secret",
        redirect_uri="http://localhost:8765/mendeley/callback",
        token_path=Path(tmp) / "private" / "tokens.json",
    ))


class Response:
    def __init__(self, payload=b"{}", status=200, headers=None):
        self.payload, self.status = payload, status
        self.headers = headers or {"Content-Type": "application/json"}
    def read(self, _limit=-1): return self.payload
    def __enter__(self): return self
    def __exit__(self, *_args): return None


class MendeleyOAuthTests(unittest.TestCase):
    def test_auth_url_persists_one_time_state_and_exchange_stores_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = make_client(tmp)
            url, state = client.authorization_url()
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            self.assertEqual(query["client_id"], ["demo-client"])
            self.assertEqual(query["scope"], ["all"])
            self.assertEqual(query["state"], [state])
            payload = {"access_token": "access-secret", "refresh_token": "refresh-secret", "expires_in": 3600, "token_type": "bearer"}
            with patch.object(client, "_read_response", return_value=(payload, {}, 200)):
                result = client.exchange_code("one-use-code", state)
            self.assertEqual(result["status"], "AUTHORIZED")
            stored = client.store.load()
            self.assertEqual(stored["access_token"], "access-secret")
            self.assertNotIn("access-secret", json.dumps(result))
            self.assertFalse(client.store.state_path.exists())
            if os.name != "nt": self.assertEqual(client.store.path.stat().st_mode & 0o777, 0o600)

    def test_state_is_one_time_and_rejects_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TokenStore(Path(tmp) / "tokens.json")
            store.save_state("expected")
            self.assertFalse(store.consume_state("wrong"))
            self.assertFalse(store.consume_state("expected"))

    def test_expired_token_refresh_is_serialized_and_rotates_refresh_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = make_client(tmp)
            client.store.save({"access_token": "old", "refresh_token": "refresh-1", "expires_at": time.time() - 2})
            with patch.object(client, "_token_request", return_value={"access_token": "new", "refresh_token": "refresh-2", "expires_at": time.time() + 3600}) as refresh:
                self.assertEqual(client._valid_token(), "new")
            refresh.assert_called_once_with({"grant_type": "refresh_token", "refresh_token": "refresh-1", "redirect_uri": client.config.redirect_uri})
            self.assertEqual(client.store.load()["refresh_token"], "refresh-2")

    def test_missing_configuration_is_actionable(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(MendeleyError): MendeleyConfig.from_env()


class MendeleyApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = make_client(self.tmp.name)
        self.client.store.save({"access_token": "access", "refresh_token": "refresh", "expires_at": time.time() + 3600})

    def test_documents_requests_use_resource_version_headers_and_pagination(self):
        first = Response(b'[{"id":"1"}]', headers={"Content-Type": "application/vnd.mendeley-document.1+json", "Link": '<https://api.mendeley.com/documents?marker=next&limit=2>; rel="next"'})
        second = Response(b'[{"id":"2"}]', headers={"Content-Type": "application/vnd.mendeley-document.1+json"})
        calls = []
        def opener(req, timeout=25):
            calls.append(req)
            return first if len(calls) == 1 else second
        self.client._open = opener
        docs = self.client.list_documents(limit=2)
        self.assertEqual([item["id"] for item in docs], ["1", "2"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].get_header("Accept"), "application/vnd.mendeley-document.1+json")
        self.assertEqual(calls[0].get_method(), "GET")
        self.assertTrue(calls[1].full_url.endswith("marker=next&limit=2"))

    def test_documents_create_patch_and_folder_add_are_explicit_methods(self):
        calls = []
        def fake(method, path, **kwargs):
            calls.append((method, path, kwargs)); return ({"id": "doc-1"}, {}, 201)
        self.client.request = fake
        self.client.create_document({"title": "T", "type": "journal"})
        self.client.update_document("doc-1", {"title": "Changed"})
        self.client.add_document_to_folder("folder-1", "doc-1")
        self.assertEqual(calls[0][0:2], ("POST", "/documents"))
        self.assertEqual(calls[1][0:2], ("PATCH", "/documents/doc-1"))
        self.assertEqual(calls[2][0:2], ("POST", "/folders/folder-1/documents"))

    def test_ambiguous_write_failure_is_not_retried(self):
        calls = []
        def opener(req, timeout=25):
            calls.append(req)
            raise urllib.error.HTTPError(req.full_url, 503, "unavailable", {}, None)
        self.client._open = opener
        with self.assertRaises(MendeleyError):
            self.client.request("POST", "/documents", body={"title": "T"}, accept="application/vnd.mendeley-document.1+json")
        self.assertEqual(len(calls), 1)

    def test_401_refreshes_once_and_retries_with_new_token(self):
        calls = []
        def opener(req, timeout=25):
            calls.append(req.get_header("Authorization"))
            if len(calls) == 1:
                raise urllib.error.HTTPError(req.full_url, 401, "expired", {}, None)
            return Response(b'{"id":"ok"}')
        self.client._open = opener
        with patch.object(self.client, "_token_request", return_value={"access_token": "new-access", "refresh_token": "new-refresh", "expires_at": time.time() + 3600}):
            result, _, _ = self.client.request("GET", "/profiles/me")
        self.assertEqual(result["id"], "ok")
        self.assertEqual(calls, ["Bearer access", "Bearer new-access"])

    def test_pagination_rejects_foreign_host(self):
        with self.assertRaises(MendeleyError):
            _next_link('<https://attacker.example/steal>; rel="next"', "https://api.mendeley.com")

    def test_path_id_rejects_slash_and_query_injection(self):
        with self.assertRaises(MendeleyError): self.client.get_document("../other")
        with self.assertRaises(MendeleyError): self.client.get_document("x?token=y")

    def test_permanent_delete_cli_requires_exact_confirmation(self):
        parser = build_parser()
        args = parser.parse_args(["document-delete", "doc-1", "--confirm", "wrong"])
        self.assertEqual(args.id, "doc-1")
        # Dispatch check is isolated via a stub client; mismatched confirmation must not call API.
        with patch("project_skripsi.integrations.mendeley._client") as factory:
            fake = MagicMock(); factory.return_value = fake
            with patch("sys.stderr"):
                code = main(["document-delete", "doc-1", "--confirm", "wrong"])
            self.assertEqual(code, 2)
            fake.delete_document_permanently.assert_not_called()

    def test_annotation_create_requires_document_id(self):
        with self.assertRaises(MendeleyError): self.client.create_annotation({"text": "note"})

    def test_api_url_rejects_http_origin(self):
        with self.assertRaises(MendeleyError):
            self.client._safe_api_url("http://api.mendeley.com", "/documents")

    def test_mendeley_source_mapping_is_stable_and_metadata_only(self):
        first = _mendeley_source_record({
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "title": "An actual article", "type": "journal", "year": 2024,
            "authors": [{"first_name": "Ayu", "last_name": "Sari"}],
            "identifiers": {"doi": "10.1234/example"},
        }, retrieval_date="2026-11-17")
        second = _mendeley_source_record({
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "title": "An actual article", "type": "journal", "year": 2024,
            "authors": [{"first_name": "Ayu", "last_name": "Sari"}],
            "identifiers": {"doi": "10.1234/example"},
        }, retrieval_date="2026-11-17")
        self.assertEqual(first["source_id"], second["source_id"])
        self.assertEqual(first["access_status"], "METADATA_ONLY")
        self.assertEqual(first["rights_status"], "UNKNOWN")
        self.assertIsNone(first["exact_locator"])
        self.assertEqual(first["authors"], ["Ayu Sari"])
        self.assertIn("123e4567", first["notes"])

    def test_workspace_sync_defaults_to_preview_then_appends_only_new_records(self):
        from types import ModuleType
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo-workspace"
            (workspace / "state").mkdir(parents=True)
            (workspace / "sources" / "registry").mkdir(parents=True)
            (workspace / "audit").mkdir()
            (workspace / "project.json").write_text("{}", encoding="utf-8")
            register_path = workspace / "sources" / "registry" / "source_register.json"
            register_path.write_text(json.dumps({"schema_version": "1.0.0", "project_id": "demo-project", "sources": [], "claim_evidence_links": []}), encoding="utf-8")
            calls = []
            validation = ModuleType("project_skripsi.validation")
            validation.validate_workspace = lambda _p: ([], {"project_id": "demo-project"}, {})
            quality = ModuleType("project_skripsi.quality")
            quality.validate_source_register = lambda records: []
            audit = ModuleType("project_skripsi.audit")
            audit.append_audit_event = lambda *a, **kw: calls.append((a, kw))
            fake_client = MagicMock()
            fake_client.list_documents.return_value = [{
                "id": "123e4567-e89b-12d3-a456-426614174000", "title": "A reference",
                "type": "journal", "year": 2024, "authors": [{"first_name": "Ayu", "last_name": "Sari"}],
                "identifiers": {"doi": "10.1234/example"},
            }]
            with patch.dict("sys.modules", {
                "project_skripsi.validation": validation,
                "project_skripsi.quality": quality,
                "project_skripsi.audit": audit,
            }):
                preview = sync_library_to_workspace(fake_client, workspace, apply=False)
                self.assertEqual(preview["status"], "PREVIEW_ONLY")
                self.assertEqual(preview["new_records"], 1)
                self.assertEqual(json.loads(register_path.read_text())["sources"], [])
                applied = sync_library_to_workspace(fake_client, workspace, apply=True)
                self.assertEqual(applied["status"], "APPLIED")
                saved = json.loads(register_path.read_text())
                self.assertEqual(len(saved["sources"]), 1)
                self.assertEqual(saved["sources"][0]["access_status"], "METADATA_ONLY")
                self.assertEqual(saved["claim_evidence_links"], [])
                self.assertTrue(Path(applied["backup"]).is_file())
                self.assertEqual(len(calls), 1)
                repeated = sync_library_to_workspace(fake_client, workspace, apply=True)
                self.assertEqual(repeated["status"], "NO_CHANGES")
                self.assertEqual(len(calls), 1)
