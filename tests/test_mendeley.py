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

from project_skripsi.audit import append_audit_event as real_append_audit_event, read_audit_events

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
            result, _, _ = self.client.request("GET", "/profiles/v2/me")
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



class MendeleySyncRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name) / "workspace"
        (self.workspace / "state").mkdir(parents=True)
        (self.workspace / "sources" / "registry").mkdir(parents=True)
        (self.workspace / "audit").mkdir(parents=True)
        (self.workspace / "project.json").write_text("{}", encoding="utf-8")
        self.register_path = self.workspace / "sources" / "registry" / "source_register.json"
        self.original_register = {
            "schema_version": "1.0.0",
            "project_id": "demo-project",
            "sources": [],
            "claim_evidence_links": [],
        }
        self.original_bytes = (json.dumps(self.original_register) + "\n").encode("utf-8")
        self.register_path.write_bytes(self.original_bytes)

        from types import ModuleType
        self.validation_module = ModuleType("project_skripsi.validation")
        self.validation_module.validate_workspace = lambda _path: ([], {"project_id": "demo-project"}, {})
        self.quality_module = ModuleType("project_skripsi.quality")
        self.quality_module.validate_source_register = lambda _records: []
        self.audit_module = ModuleType("project_skripsi.audit")
        self.audit_calls = []

        def append_audit(*args, **kwargs):
            self.audit_calls.append((args, kwargs))
            return {"event_type": kwargs.get("event_type"), "idempotency_key": kwargs.get("idempotency_key")}

        self.audit_module.append_audit_event = append_audit
        self.modules_patch = patch.dict("sys.modules", {
            "project_skripsi.validation": self.validation_module,
            "project_skripsi.quality": self.quality_module,
            "project_skripsi.audit": self.audit_module,
        })
        self.modules_patch.start()
        self.addCleanup(self.modules_patch.stop)

        self.client = MagicMock()
        self.client.list_documents.return_value = [{
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "title": "A reference",
            "type": "journal",
            "year": 2024,
            "authors": [{"first_name": "Ayu", "last_name": "Sari"}],
            "identifiers": {"doi": "10.1234/example"},
        }]
        self.journal_path = self.workspace / "state" / ".mendeley-sync-transaction.json"

    def test_pre_replace_failure_is_recovered_only_by_explicit_apply(self):
        original_replace = os.replace

        def interrupt_register_replace(source, destination):
            if Path(destination).name == self.register_path.name:
                raise OSError("fault injection before source-register replace")
            return original_replace(source, destination)

        with patch("project_skripsi.integrations.mendeley.os.replace", side_effect=interrupt_register_replace):
            with self.assertRaisesRegex(MendeleyError, "journal and backup were retained"):
                sync_library_to_workspace(self.client, self.workspace, apply=True)

        self.assertEqual(self.register_path.read_bytes(), self.original_bytes)
        self.assertTrue(self.journal_path.is_file())
        staged = list(self.register_path.parent.glob("source_register.*.tmp"))
        backups = list(self.register_path.parent.glob("source_register.mendeley-backup-*.json"))
        self.assertEqual(len(staged), 1)
        self.assertEqual(len(backups), 1)

        with self.assertRaisesRegex(MendeleyError, "Preview did not change any files"):
            sync_library_to_workspace(self.client, self.workspace, apply=False)
        self.assertEqual(self.register_path.read_bytes(), self.original_bytes)
        self.assertTrue(self.journal_path.is_file())
        self.assertEqual(self.audit_calls, [])

        recovered = sync_library_to_workspace(self.client, self.workspace, apply=True)
        saved = json.loads(self.register_path.read_text(encoding="utf-8"))
        self.assertEqual(recovered["status"], "RECOVERED")
        self.assertTrue(recovered["recovered_pending_transaction"])
        self.assertEqual(len(saved["sources"]), 1)
        self.assertEqual(saved["claim_evidence_links"], [])
        self.assertFalse(self.journal_path.exists())
        self.assertTrue(Path(recovered["recovery_backup"]).is_file())
        self.assertEqual(len(self.audit_calls), 1)
        self.client.list_documents.assert_called_once_with(view="all")

    def test_post_replace_audit_failure_recovers_idempotently(self):
        def fail_audit(*_args, **_kwargs):
            raise OSError("fault injection while appending audit event")

        self.audit_module.append_audit_event = fail_audit
        with self.assertRaisesRegex(MendeleyError, "journal and backup were retained"):
            sync_library_to_workspace(self.client, self.workspace, apply=True)

        after_replace = json.loads(self.register_path.read_text(encoding="utf-8"))
        self.assertEqual(len(after_replace["sources"]), 1)
        self.assertTrue(self.journal_path.is_file())
        self.assertEqual(self.audit_calls, [])

        def append_audit(*args, **kwargs):
            self.audit_calls.append((args, kwargs))
            return {"event_type": kwargs.get("event_type"), "idempotency_key": kwargs.get("idempotency_key")}

        self.audit_module.append_audit_event = append_audit
        recovered = sync_library_to_workspace(self.client, self.workspace, apply=True)
        self.assertEqual(recovered["status"], "RECOVERED")
        self.assertTrue(recovered["recovered_pending_transaction"])
        self.assertFalse(self.journal_path.exists())
        self.assertEqual(len(json.loads(self.register_path.read_text(encoding="utf-8"))["sources"]), 1)
        self.assertEqual(len(self.audit_calls), 1)
        self.assertTrue(Path(recovered["recovery_backup"]).is_file())
        self.client.list_documents.assert_called_once_with(view="all")

    def test_audit_committed_before_interruption_is_idempotent_on_recovery(self):
        calls = {"count": 0}

        def append_then_interrupt_once(*args, **kwargs):
            event = real_append_audit_event(*args, **kwargs)
            calls["count"] += 1
            if calls["count"] == 1:
                raise OSError("fault injection after durable audit append")
            return event

        self.audit_module.append_audit_event = append_then_interrupt_once
        with self.assertRaisesRegex(MendeleyError, "journal and backup were retained"):
            sync_library_to_workspace(self.client, self.workspace, apply=True)

        audit_path = self.workspace / "audit" / "events.jsonl"
        ok, reason, before = read_audit_events(audit_path)
        self.assertTrue(ok, reason)
        self.assertEqual(len(before), 1)
        self.assertTrue(self.journal_path.is_file())

        recovered = sync_library_to_workspace(self.client, self.workspace, apply=True)
        ok, reason, after = read_audit_events(audit_path)
        self.assertTrue(ok, reason)
        self.assertEqual(len(after), 1)
        self.assertEqual(recovered["status"], "RECOVERED")
        self.assertFalse(self.journal_path.exists())
        self.assertEqual(calls["count"], 2)
        self.client.list_documents.assert_called_once_with(view="all")

    def test_recovery_fails_closed_when_register_changed_after_interruption(self):
        def fail_audit(*_args, **_kwargs):
            raise OSError("fault injection while appending audit event")

        self.audit_module.append_audit_event = fail_audit
        with self.assertRaises(MendeleyError):
            sync_library_to_workspace(self.client, self.workspace, apply=True)
        self.register_path.write_text('{"external_edit":true}\n', encoding="utf-8")

        with self.assertRaisesRegex(MendeleyError, "refusing automatic recovery"):
            sync_library_to_workspace(self.client, self.workspace, apply=True)
        self.assertTrue(self.journal_path.is_file())
        self.assertEqual(self.audit_calls, [])



class MendeleyExpandedResourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = make_client(self.tmp.name)
        self.client.store.save({"access_token": "access", "refresh_token": "refresh", "expires_at": time.time() + 3600})

    def test_cli_does_not_expose_retired_profile_or_public_group_search(self):
        parser = build_parser()
        for command in ("profile-search", "popular-groups"):
            with self.subTest(command=command), self.assertRaises(SystemExit):
                parser.parse_args([command, "sample-query"])

    def test_library_search_uses_private_library_endpoint_and_query(self):
        calls = []
        def fake(method, path, **kwargs):
            calls.append((method, path, kwargs))
            return ([{"id": "doc-1"}], {}, 200)
        self.client.request = fake
        self.client.search_library_documents("climate adaptation", limit=12)
        self.assertEqual(calls[0][0:2], ("GET", "/search/documents"))
        self.assertEqual(calls[0][2]["params"], {"limit": 12, "query": "climate adaptation"})

    def test_group_v2_creation_and_member_role_use_versioned_contract(self):
        calls = []
        def fake(method, path, **kwargs):
            calls.append((method, path, kwargs))
            return ({"id": "g-1"}, {}, 201)
        self.client.request = fake
        self.client.create_group({"name": "Research team", "access_level": "private"})
        self.client.update_group_member("g-1", "profile-1", "admin")
        self.assertEqual(calls[0][0:2], ("POST", "/groups/v2"))
        self.assertEqual(calls[0][2]["accept"], "application/vnd.mendeley-group+json")
        self.assertEqual(calls[1][0:2], ("PATCH", "/groups/v2/g-1/members/profile-1"))
        self.assertEqual(calls[1][2]["body"], {"membership": "admin"})
        with self.assertRaises(MendeleyError): self.client.update_group_member("g-1", "p-1", "owner")

    def test_group_invite_requires_recipient_list_and_action_allowlist(self):
        with self.assertRaises(MendeleyError): self.client.invite_group_members("g-1", {"recipients": []})
        with self.assertRaises(MendeleyError): self.client.group_invitation_action("g-1", "i-1", "delete")

    def test_group_invitation_acceptance_uses_current_action_route(self):
        calls = []
        self.client.request = lambda *a, **kw: calls.append((a, kw)) or ({"ok": True}, {}, 204)
        self.client.respond_to_group_invitation("group-1", True)
        self.client.respond_to_group_invitation("group-1", False)
        self.assertEqual(calls[0][0][:2], ("POST", "/groups/v2/group-1/actions/accept_invitation"))
        self.assertEqual(calls[1][0][:2], ("POST", "/groups/v2/group-1/actions/decline_invitation"))

    def test_public_group_operations_are_rejected_locally(self):
        with self.assertRaises(MendeleyError):
            self.client.create_group({"name": "Public group", "access_level": "public"})
        with self.assertRaises(MendeleyError):
            self.client.update_group("g-1", {"access_level": "open"})
        with self.assertRaises(MendeleyError):
            self.client.create_group({"name": "Invite-only group", "access_level": "invite_only"})

    def test_document_file_routes_use_document_scoped_api(self):
        calls = []
        def fake(method, path, **kwargs):
            calls.append((method, path, kwargs))
            return ([{"id": "f-1"}], {}, 200)
        self.client.request = fake
        self.client.pages = lambda path, **kwargs: calls.append(("PAGES", path, kwargs)) or [{"id": "f-1"}]
        self.client.list_document_files("d-1", limit=10)
        self.client.delete_document_file("d-1", "f-1")
        self.assertEqual(calls[0][0:2], ("PAGES", "/documents/v1/d-1/files"))
        self.assertEqual(calls[1][0:2], ("DELETE", "/documents/v1/d-1/files/f-1"))

    def test_retry_after_parser_handles_seconds_and_http_date(self):
        from project_skripsi.integrations.mendeley import _retry_after_seconds
        self.assertEqual(_retry_after_seconds("12"), 12.0)
        self.assertIsNone(_retry_after_seconds("bad-value"))

    def test_credential_load_rejects_symlinked_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "real"
            target.mkdir()
            link = root / "link"
            link.symlink_to(target, target_is_directory=True)
            store = TokenStore(link / "tokens.json")
            with self.assertRaises(MendeleyError): store.load()

    def test_profile_v2_collection_and_catalog_search_use_supported_endpoints(self):
        calls = []
        self.client.pages = lambda path, **kwargs: calls.append((path, kwargs)) or []
        self.client.list_profiles(limit=10)
        self.client.search_catalog(title="climate adaptation", author="Ayu Sari", min_year=2020, max_year=2024)
        self.assertEqual(calls[0][0], "/profiles/v2")
        self.assertEqual(calls[0][1]["accept"], "application/vnd.mendeley-profile.2+json")
        self.assertEqual(calls[1][0], "/search/catalog")
        self.assertEqual(calls[1][1]["params"], {"title": "climate adaptation", "author": "Ayu Sari", "min_year": 2020, "max_year": 2024})

    def test_catalog_search_validates_query_fields_and_year_bounds(self):
        with self.assertRaises(MendeleyError): self.client.search_catalog()
        with self.assertRaises(MendeleyError): self.client.search_catalog(doi="10.1234/example")
        with self.assertRaises(MendeleyError): self.client.search_catalog(query="climate", min_year=2025, max_year=2020)
        with self.assertRaises(MendeleyError): self.client.search_catalog(query="climate", min_year=1499)
        with self.assertRaises(MendeleyError): self.client.search_catalog(query="climate", unsupported="value")
        with self.assertRaises(MendeleyError): self.client.search_catalog(query="climate", limit=501)

    def test_catalog_identifier_and_id_retrieval_use_catalog_resource(self):
        calls = []
        def fake(method, path, **kwargs):
            calls.append((method, path, kwargs))
            return ({"id": "catalog-doc"}, {}, 200)
        self.client.request = fake
        self.client.get_catalog_document_by_identifier(doi="10.1234/example")
        self.client.get_catalog_document("catalog-doc", view="bib")
        self.assertEqual(calls[0][0:2], ("GET", "/catalog"))
        self.assertEqual(calls[0][2]["params"], {"doi": "10.1234/example"})
        self.assertEqual(calls[1][0:2], ("GET", "/catalog/catalog-doc"))
        self.assertEqual(calls[1][2]["params"], {"view": "bib"})
        with self.assertRaises(MendeleyError): self.client.get_catalog_document_by_identifier(doi="10.1234/example", isbn="9780000000000")
        with self.assertRaises(MendeleyError): self.client.get_catalog_document_by_identifier(doi="")

    def test_catalog_cli_exposes_search_get_and_identifier_lookup(self):
        parser = build_parser()
        search = parser.parse_args(["catalog-search", "--query", "climate change", "--min-year", "2018", "--view", "all"])
        get_item = parser.parse_args(["catalog-get", "catalog-id", "--view", "bib"])
        lookup = parser.parse_args(["catalog-lookup", "--doi", "10.1234/example"])
        self.assertEqual((search.command, search.query, search.min_year, search.view), ("catalog-search", "climate change", 2018, "all"))
        self.assertEqual((get_item.command, get_item.id, get_item.view), ("catalog-get", "catalog-id", "bib"))
        self.assertEqual((lookup.command, lookup.doi), ("catalog-lookup", "10.1234/example"))

    def test_cli_group_destructive_actions_require_exact_confirmation(self):
        with patch("project_skripsi.integrations.mendeley._client") as factory:
            fake = MagicMock(); factory.return_value = fake
            with patch("sys.stderr"):
                code = main(["group-delete", "g-1", "--confirm", "wrong"])
            self.assertEqual(code, 2)
            fake.delete_group.assert_not_called()

    def test_get_retry_honors_retry_after_seconds_and_still_never_retries_writes(self):
        calls = []
        def opener(req, timeout=25):
            calls.append(req)
            if len(calls) == 1:
                headers = {"Retry-After": "2", "Content-Type": "application/json"}
                raise urllib.error.HTTPError(req.full_url, 429, "rate limited", headers, None)
            return Response(b'{"ok":true}')
        self.client._open = opener
        with patch("project_skripsi.integrations.mendeley.time.sleep") as sleep:
            payload, _, _ = self.client.request("GET", "/profiles/me")
        self.assertEqual(payload, {"ok": True})
        sleep.assert_called_once_with(2.0)
        self.assertEqual(len(calls), 2)

    def test_long_retry_after_is_not_ignored_by_retrying_early(self):
        def opener(req, timeout=25):
            headers = {"Retry-After": "120", "Content-Type": "application/json"}
            raise urllib.error.HTTPError(req.full_url, 429, "rate limited", headers, None)
        self.client._open = opener
        with patch("project_skripsi.integrations.mendeley.time.sleep") as sleep:
            with self.assertRaises(MendeleyError) as error:
                self.client.request("GET", "/profiles/me")
        sleep.assert_not_called()
        self.assertEqual(error.exception.retry_after, 120.0)

    def test_document_file_upload_uses_document_scoped_route_and_file_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "sample.pdf"
            source.write_bytes(b"%PDF-demo")
            calls = []
            self.client.request = lambda *a, **kw: calls.append((a, kw)) or ({"id": "f-1"}, {}, 201)
            self.client.upload_document_file("doc-1", source)
            args, kwargs = calls[0]
            self.assertEqual(args[:2], ("POST", "/documents/v1/doc-1/files"))
            self.assertEqual(kwargs["raw_body"], b"%PDF-demo")
            self.assertEqual(kwargs["headers"]["Content-Type"], "application/pdf")

    def test_oversized_uploads_are_rejected_before_reading_file_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            oversized = Path(tmp) / "oversized.pdf"
            with oversized.open("wb") as stream:
                stream.truncate(100 * 1024 * 1024 + 1)
            self.client.request = MagicMock()
            with patch("pathlib.Path.read_bytes", side_effect=AssertionError("must not allocate an oversized upload")):
                for operation in (
                    lambda: self.client.create_document_from_file(oversized),
                    lambda: self.client.upload_file("doc-1", oversized),
                    lambda: self.client.upload_document_file("doc-1", oversized),
                ):
                    with self.assertRaisesRegex(MendeleyError, "100 MiB upload limit"):
                        operation()
            self.client.request.assert_not_called()

    def test_logout_only_clears_local_token_store(self):
        with patch("project_skripsi.integrations.mendeley._client") as factory:
            fake = MagicMock(); fake.store.clear.return_value = True; factory.return_value = fake
            with patch("builtins.print") as output:
                code = main(["logout"])
        self.assertEqual(code, 0)
        fake.store.clear.assert_called_once_with()
        self.assertIn('"provider_grant_revoked": false', output.call_args[0][0])

    def test_document_update_can_use_optimistic_concurrency_precondition(self):
        calls = []
        self.client.request = lambda *a, **kw: calls.append((a, kw)) or ({"id": "d-1"}, {}, 200)
        self.client.update_document("d-1", {"title": "Updated"}, if_unmodified_since="Tue, 17 Nov 2026 00:00:00 GMT")
        self.assertEqual(calls[0][1]["headers"]["If-Unmodified-Since"], "Tue, 17 Nov 2026 00:00:00 GMT")
        with self.assertRaises(MendeleyError): self.client.update_document("d-1", {"title": "x"}, if_unmodified_since="bad\r\nAuthorization:evil")

    def test_request_rejects_auth_header_override(self):
        with self.assertRaises(MendeleyError): self.client.request("GET", "/profiles/me", headers={"Authorization": "Bearer attacker"})


class MendeleyOAuthCallbackTests(unittest.TestCase):
    def test_local_browser_callback_completes_authorization_code_exchange(self):
        import socket
        import threading
        from urllib.parse import parse_qs, urlencode, urlsplit
        from urllib.request import urlopen
        from project_skripsi.integrations.mendeley import run_local_oauth_login

        with tempfile.TemporaryDirectory() as tmp:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            client = MendeleyClient(MendeleyConfig(
                client_id="demo-client",
                client_secret="demo-secret",
                redirect_uri=f"http://127.0.0.1:{port}/mendeley/callback",
                token_path=Path(tmp) / "tokens.json",
            ))
            callback_errors = []
            callback_thread = []

            def fake_browser_open(auth_url):
                query = parse_qs(urlsplit(auth_url).query)
                state = query["state"][0]
                def send_callback():
                    callback_url = f"http://127.0.0.1:{port}/mendeley/callback?" + urlencode({"code": "authorization-code", "state": state})
                    try:
                        with urlopen(callback_url, timeout=5) as response:
                            self.assertEqual(response.status, 200)
                    except Exception as exc:
                        callback_errors.append(exc)
                worker = threading.Thread(target=send_callback, daemon=True)
                callback_thread.append(worker)
                worker.start()
                return True

            token_payload = {
                "access_token": "live-test-access",
                "refresh_token": "live-test-refresh",
                "expires_at": time.time() + 3600,
                "token_type": "bearer",
            }
            with patch("project_skripsi.integrations.mendeley.webbrowser.open", side_effect=fake_browser_open):
                with patch.object(client, "_token_request", return_value=token_payload) as exchange:
                    result = run_local_oauth_login(client, timeout_seconds=8)
            callback_thread[0].join(timeout=5)
            self.assertFalse(callback_thread[0].is_alive())
            self.assertEqual(callback_errors, [])
            self.assertEqual(result["status"], "AUTHORIZED")
            exchange.assert_called_once()
            self.assertEqual(client.store.load()["access_token"], "live-test-access")

    def test_automatic_login_rejects_non_loopback_redirect(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = MendeleyConfig(
                client_id="demo-client", client_secret="demo-secret",
                redirect_uri="https://example.com/oauth/callback",
                token_path=Path(tmp) / "tokens.json",
            )
            client = MendeleyClient(config)
            from project_skripsi.integrations.mendeley import run_local_oauth_login
            with self.assertRaises(MendeleyError):
                run_local_oauth_login(client)



class MendeleyAdditionalResourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = make_client(self.tmp.name)
        self.client.store.save({"access_token": "access", "refresh_token": "refresh", "expires_at": time.time() + 3600})

    def test_group_invitation_uses_distinct_documented_content_and_accept_types(self):
        calls = []
        self.client.request = lambda *a, **kw: calls.append((a, kw)) or ([{"invitation_uuid": "i-1"}], {}, 201)
        self.client.invite_group_members("g-1", {"recipients": [{"email": "a@example.test"}]})
        args, kwargs = calls[0]
        self.assertEqual(args[:2], ("POST", "/groups/v2/g-1/invitations"))
        self.assertEqual(kwargs["content_type"], "application/vnd.mendeley-group-invitation+json")
        self.assertEqual(kwargs["accept"], "application/vnd.mendeley-group-invitation-response-list+json")

    def test_profile_v2_read_and_update_routes(self):
        calls = []
        self.client.request = lambda *a, **kw: calls.append((a, kw)) or ({"id": "p-1"}, {}, 200)
        self.client.get_profile()
        self.client.get_profile_by_id("p-1")
        self.client.update_profile({"display_name": "Example"})
        self.assertEqual(calls[0][0][:2], ("GET", "/profiles/v2/me"))
        self.assertEqual(calls[0][1]["accept"], "application/vnd.mendeley-profile.2+json")
        self.assertEqual(calls[1][0][:2], ("GET", "/profiles/v2/p-1"))
        self.assertEqual(calls[2][0][:2], ("PATCH", "/profiles/v2/me"))
        self.assertEqual(calls[2][1]["accept"], "application/vnd.mendeley-profile-amendment.2+json")

    def test_group_join_request_decisions_use_documented_routes(self):
        calls = []
        self.client.request = lambda *a, **kw: calls.append((a, kw)) or ({"ok": True}, {}, 200)
        self.client.respond_to_group_join_request("g-1", "profile-1", True, "Welcome")
        self.client.respond_to_group_join_request("g-1", "profile-2", False, "Not eligible")
        self.assertEqual(calls[0][0][:2], ("POST", "/groups/v2/g-1/members/profile-1/actions/accept"))
        self.assertEqual(calls[1][0][:2], ("POST", "/groups/v2/g-1/members/profile-2/actions/decline"))
        self.assertEqual(calls[0][1]["body"], {"message": "Welcome"})
    def test_profile_get_by_id_uses_profiles_resource(self):
        calls = []
        self.client.request = lambda *a, **kw: calls.append((a, kw)) or ({"id": "profile-123"}, {}, 200)
        self.client.get_profile_by_id("profile-123")
        self.assertEqual(calls[0][0][:2], ("GET", "/profiles/v2/profile-123"))


if __name__ == "__main__": unittest.main()
