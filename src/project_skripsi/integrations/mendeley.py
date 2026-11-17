"""Mendeley REST API integration (OAuth 2.0 + library resources).

The module uses only Python's standard library. API writes are never retried after
ambiguous network failures; token refresh is serialized and secrets are kept out
of output, exceptions, caches and audit records.
"""
from __future__ import annotations

import argparse
import base64
import email.utils
import json
import mimetypes
import os
import re
import secrets
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable

from ..locking import FileLock

API_BASE = "https://api.mendeley.com"
AUTH_URL = "https://api.mendeley.com/oauth/authorize"
TOKEN_URL = "https://api.mendeley.com/oauth/token"
USER_AGENT = "Project-SKRIPSI-Mendeley-Connector/0.1 (local user-authorized integration)"
MEDIA = {
    "documents": "application/vnd.mendeley-document.1+json",
    "folders": "application/vnd.mendeley-folder.1+json",
    "annotations": "application/vnd.mendeley-annotation.1+json",
    "files": "application/vnd.mendeley-file.1+json",
    "profiles": "application/vnd.mendeley-profiles.1+json",
    "profile_patch": "application/vnd.mendeley-profile-amendment.1+json",
    "catalog": "application/vnd.mendeley-document.1+json",
}
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024


class MendeleyError(RuntimeError):
    """Sanitized API or OAuth failure; never contains request headers or tokens."""
    def __init__(self, message: str, *, status: int | None = None, code: str | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status, self.code, self.retry_after = status, code, retry_after


@dataclass(frozen=True)
class MendeleyConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    token_path: Path
    api_base_url: str = API_BASE
    timeout: int = 25

    @classmethod
    def from_env(cls, *, token_path: Path | None = None) -> "MendeleyConfig":
        missing = [key for key in ("MENDELEY_CLIENT_ID", "MENDELEY_CLIENT_SECRET", "MENDELEY_REDIRECT_URI") if not os.environ.get(key)]
        if missing:
            raise MendeleyError("Missing environment configuration: " + ", ".join(missing))
        path = token_path or Path(os.environ.get("MENDELEY_TOKEN_FILE", Path.home() / ".project-skripsi" / "mendeley" / "tokens.json"))
        return cls(os.environ["MENDELEY_CLIENT_ID"], os.environ["MENDELEY_CLIENT_SECRET"], os.environ["MENDELEY_REDIRECT_URI"], Path(path).expanduser())

    def validate(self) -> None:
        if not self.client_id.strip() or not self.client_secret.strip():
            raise MendeleyError("Mendeley client ID and secret must be configured")
        parsed = urllib.parse.urlsplit(self.redirect_uri)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise MendeleyError("MENDELEY_REDIRECT_URI must be an absolute HTTP(S) URL")
        base = urllib.parse.urlsplit(self.api_base_url)
        if base.scheme != "https" or not base.netloc:
            raise MendeleyError("Mendeley API base URL must use HTTPS")
        if not 1 <= self.timeout <= 60:
            raise MendeleyError("timeout must be between 1 and 60 seconds")


class TokenStore:
    """Atomic, permission-restricted token storage with serialized refresh."""
    def __init__(self, path: Path):
        self.path = Path(path).expanduser()
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.state_path = self.path.with_name(self.path.name + ".oauth-state.json")

    @staticmethod
    def _reject_symlink(path: Path) -> None:
        if path.is_symlink():
            raise MendeleyError(f"Refusing symlinked credential path: {path}")

    @classmethod
    def _validate_location(cls, path: Path) -> None:
        cls._reject_symlink(path)
        for parent in (path.parent, *path.parent.parents):
            if parent.is_symlink():
                raise MendeleyError(f"Refusing symlinked credential directory: {parent}")

    def _atomic_write_unlocked(self, path: Path, payload: dict[str, Any]) -> None:
        self._validate_location(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt": path.parent.chmod(0o700)
        fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
                stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
            if os.name != "nt": temp.chmod(0o600)
            os.replace(temp, path)
            if os.name != "nt": path.chmod(0o600)
        finally:
            try: temp.unlink(missing_ok=True)
            except OSError: pass

    def save(self, token: dict[str, Any]) -> None:
        required = ("access_token", "refresh_token", "expires_at")
        if any(not token.get(key) for key in required):
            raise MendeleyError("OAuth token response is incomplete")
        self._validate_location(self.path)
        with FileLock(self.lock_path):
            self._atomic_write_unlocked(self.path, token)

    def load(self) -> dict[str, Any] | None:
        self._validate_location(self.path)
        if not self.path.exists(): return None
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise MendeleyError("Credential store cannot be read; reauthorize after inspecting the local file") from exc
        if not isinstance(value, dict) or not isinstance(value.get("access_token"), str):
            raise MendeleyError("Credential store has an invalid structure")
        return value

    def clear(self) -> bool:
        self._validate_location(self.path)
        self._validate_location(self.state_path)
        with FileLock(self.lock_path):
            self._validate_location(self.path)
            existed = self.path.exists()
            if existed: self.path.unlink()
            self._reject_symlink(self.state_path)
            self.state_path.unlink(missing_ok=True)
            return existed

    def save_state(self, state: str, *, created_at: float | None = None) -> None:
        self._validate_location(self.state_path)
        with FileLock(self.lock_path):
            self._atomic_write_unlocked(self.state_path, {"state": state, "created_at": created_at or time.time()})

    def consume_state(self, supplied: str, *, max_age: int = 600) -> bool:
        self._validate_location(self.state_path)
        with FileLock(self.lock_path):
            self._reject_symlink(self.state_path)
            if not self.state_path.exists(): return False
            try: data = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError): data = {}
            self.state_path.unlink(missing_ok=True)
            expected, created = data.get("state"), data.get("created_at")
            return bool(isinstance(expected, str) and isinstance(created, (int, float)) and time.time() - created <= max_age and time.time() >= created and secrets.compare_digest(expected, supplied))


class MendeleyClient:
    def __init__(self, config: MendeleyConfig, *, opener: Callable[..., Any] | None = None):
        config.validate()
        self.config = config
        self.store = TokenStore(config.token_path)
        self._open = opener or _open_no_redirect

    def authorization_url(self) -> tuple[str, str]:
        """Create a one-use CSRF state and return (URL, state)."""
        state = secrets.token_urlsafe(32)
        self.store.save_state(state)
        query = urllib.parse.urlencode({"client_id": self.config.client_id, "redirect_uri": self.config.redirect_uri, "response_type": "code", "scope": "all", "state": state})
        return AUTH_URL + "?" + query, state

    def exchange_code(self, code: str, state: str) -> dict[str, Any]:
        if not code.strip() or not self.store.consume_state(state):
            raise MendeleyError("OAuth state is missing, expired, already used, or does not match")
        token = self._token_request({"grant_type": "authorization_code", "code": code, "redirect_uri": self.config.redirect_uri})
        self.store.save(token)
        return {"status": "AUTHORIZED", "expires_at": token["expires_at"], "token_type": token.get("token_type", "bearer")}

    def _token_request(self, form: dict[str, str]) -> dict[str, Any]:
        basic = base64.b64encode(f"{self.config.client_id}:{self.config.client_secret}".encode()).decode("ascii")
        request = urllib.request.Request(TOKEN_URL, data=urllib.parse.urlencode(form).encode(), headers={"Authorization": "Basic " + basic, "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json", "User-Agent": USER_AGENT}, method="POST")
        payload, _headers, status = self._read_response(request)
        if status not in {200, 201} or not isinstance(payload, dict): raise MendeleyError("Mendeley token endpoint returned an invalid response", status=status)
        access, refresh = payload.get("access_token"), payload.get("refresh_token")
        expires_in = payload.get("expires_in")
        if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh or not isinstance(expires_in, (int, float)) or expires_in <= 0:
            raise MendeleyError("Mendeley token response lacks required token fields")
        return {"access_token": access, "refresh_token": refresh, "token_type": str(payload.get("token_type") or "bearer"), "expires_at": time.time() + float(expires_in), "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    def _read_response(self, request: urllib.request.Request, *, max_bytes: int = MAX_DOWNLOAD_BYTES) -> tuple[Any, Any, int]:
        try:
            response = self._open(request, timeout=self.config.timeout)
            with response:
                status = getattr(response, "status", 200)
                raw = response.read(max_bytes + 1)
                headers = response.headers
        except urllib.error.HTTPError as exc:
            status, headers = exc.code, exc.headers
            raw = exc.read(4096)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise MendeleyError(f"Mendeley network request failed: {type(exc).__name__}") from exc
        if len(raw) > max_bytes: raise MendeleyError("Mendeley response exceeded the configured safety size limit", status=status)
        if status >= 400:
            code = None; message = f"HTTP {status}"
            retry_after = _retry_after_seconds(headers.get("Retry-After") if headers else None)
            try:
                error = json.loads(raw.decode("utf-8"))
                if isinstance(error, dict):
                    code = str(error.get("error") or error.get("code") or "") or None
                    message = str(error.get("error_description") or error.get("message") or message)[:180]
            except (UnicodeError, json.JSONDecodeError): pass
            raise MendeleyError(f"Mendeley API error: {message}", status=status, code=code, retry_after=retry_after)
        if not raw: return None, headers, status
        content_type = str(headers.get("Content-Type", ""))
        if "json" in content_type or raw[:1] in (b"{", b"["):
            try: return json.loads(raw.decode("utf-8")), headers, status
            except (UnicodeError, json.JSONDecodeError) as exc: raise MendeleyError("Mendeley returned invalid JSON", status=status) from exc
        return raw, headers, status

    def _valid_token(self) -> str:
        token = self.store.load()
        if token is None: raise MendeleyError("Not connected. Run \`project-skripsi-mendeley auth-url\` and complete OAuth first")
        if float(token.get("expires_at", 0)) > time.time() + 90: return token["access_token"]
        # Serialize refresh and reload after obtaining lock so a concurrent process can rotate tokens.
        with FileLock(self.store.lock_path):
            token = self.store.load()
            if token is None: raise MendeleyError("No saved Mendeley authorization")
            if float(token.get("expires_at", 0)) > time.time() + 90: return token["access_token"]
            refresh = token.get("refresh_token")
            if not isinstance(refresh, str) or not refresh: raise MendeleyError("Refresh token missing; run OAuth authorization again")
            replacement = self._token_request({"grant_type": "refresh_token", "refresh_token": refresh, "redirect_uri": self.config.redirect_uri})
            self.store._atomic_write_unlocked(self.store.path, replacement)
            return replacement["access_token"]

    @staticmethod
    def _safe_api_url(base: str, path: str, params: dict[str, Any] | None = None) -> str:
        root = urllib.parse.urlsplit(base)
        if root.scheme != "https" or not root.netloc:
            raise MendeleyError("Mendeley API base URL must use HTTPS")
        if path.startswith("https://"):
            target = urllib.parse.urlsplit(path); root = urllib.parse.urlsplit(base)
            if target.scheme != "https" or target.netloc.casefold() != root.netloc.casefold() or not target.path.startswith("/"):
                raise MendeleyError("Refusing pagination URL outside the configured Mendeley API host")
            url = path
        else:
            if not path.startswith("/") or path.startswith("//") or ".." in path.split("/"):
                raise MendeleyError("Invalid Mendeley API path")
            url = base.rstrip("/") + path
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
            if query: url += ("&" if "?" in url else "?") + query
        return url

    def request(self, method: str, path: str, *, params: dict[str, Any] | None = None, body: Any = None, raw_body: bytes | None = None, headers: dict[str, str] | None = None, accept: str | None = None, retry_get: bool = True) -> tuple[Any, Any, int]:
        method = method.upper()
        if method not in {"GET", "POST", "PATCH", "DELETE", "PUT"}: raise MendeleyError("Unsupported HTTP method")
        url = self._safe_api_url(self.config.api_base_url, path, params)
        data = raw_body if raw_body is not None else (json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None)
        request_headers = {"Authorization": "Bearer " + self._valid_token(), "User-Agent": USER_AGENT}
        if accept: request_headers["Accept"] = accept
        if body is not None: request_headers["Content-Type"] = accept or "application/json"
        if headers:
            protected = {"authorization", "host", "cookie", "proxy-authorization"}
            if any(str(key).casefold() in protected for key in headers):
                raise MendeleyError("Request headers may not override protected authentication or routing fields")
            request_headers.update(headers)
        max_attempts = 3 if (method == "GET" and retry_get) else 1
        refreshed = False
        for attempt in range(max_attempts + 1):
            req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
            try: return self._read_response(req)
            except MendeleyError as exc:
                if exc.status == 401 and not refreshed:
                    refreshed = True
                    rejected_access_token = request_headers["Authorization"].removeprefix("Bearer ")
                    with FileLock(self.store.lock_path):
                        token = self.store.load()
                        if not token:
                            raise MendeleyError("Mendeley authorization disappeared; reconnect the account")
                        # Another process may already have rotated the token after our request began.
                        if token.get("access_token") == rejected_access_token:
                            refresh = token.get("refresh_token")
                            if not refresh: raise MendeleyError("Refresh token missing; reconnect the account")
                            token = self._token_request({"grant_type": "refresh_token", "refresh_token": refresh, "redirect_uri": self.config.redirect_uri})
                            self.store._atomic_write_unlocked(self.store.path, token)
                        request_headers["Authorization"] = "Bearer " + str(token["access_token"])
                    continue
                if method == "GET" and attempt < max_attempts and exc.status in {429, 500, 502, 503, 504}:
                    delay = exc.retry_after if exc.retry_after is not None else float(min(2 ** attempt, 4))
                    if exc.retry_after is not None and delay > 30:
                        raise MendeleyError(
                            "Mendeley requested a retry delay longer than the 30-second automatic cap; retry manually later",
                            status=exc.status, code=exc.code, retry_after=delay,
                        ) from exc
                    time.sleep(max(0.0, delay))
                    continue
                raise
        raise MendeleyError("Mendeley request retry budget exhausted")
        url, first = path, True
        out: list[Any] = []
        while url:
            data, headers, _status = self.request("GET", url, params=params if first else None, accept=accept)
            first = False
            if data is None: break
            if isinstance(data, dict): out.append(data)
            elif isinstance(data, list): out.extend(data)
            else: raise MendeleyError("Expected a JSON collection from Mendeley")
            link = headers.get("Link", "") if headers else ""
            url = _next_link(link, self.config.api_base_url)
        return out

    # Profile
    def get_profile(self) -> dict[str, Any]:
        data, _, _ = self.request("GET", "/profiles/me", accept=MEDIA["profiles"])
        if not isinstance(data, dict): raise MendeleyError("Profile response is not an object")
        return data
    def update_profile(self, changes: dict[str, Any]) -> Any:
        if not changes: raise MendeleyError("Profile changes must not be empty")
        return self.request("PATCH", "/profiles/me", body=changes, accept=MEDIA["profile_patch"])[0]

    # Documents
    def list_documents(self, **params: Any) -> list[dict[str, Any]]:
        params.setdefault("view", "all")
        return self.pages("/documents", params=params, accept=MEDIA["documents"])
    def get_document(self, document_id: str) -> Any:
        return self.request("GET", "/documents/" + _id(document_id), accept=MEDIA["documents"])[0]
    def create_document(self, metadata: dict[str, Any]) -> Any:
        if not isinstance(metadata, dict) or not metadata.get("title") or not metadata.get("type"):
            raise MendeleyError("Document metadata requires non-empty title and type")
        return self.request("POST", "/documents", body=metadata, accept=MEDIA["documents"])[0]
    def update_document(self, document_id: str, changes: dict[str, Any], *, if_unmodified_since: str | None = None) -> Any:
        if not changes: raise MendeleyError("Document changes must not be empty")
        headers = {}
        if if_unmodified_since:
            value = if_unmodified_since.strip()
            if not value or "\r" in value or "\n" in value:
                raise MendeleyError("If-Unmodified-Since must be a single valid HTTP date value")
            headers["If-Unmodified-Since"] = value
        return self.request("PATCH", "/documents/" + _id(document_id), body=changes, headers=headers, accept=MEDIA["documents"])[0]
    def trash_document(self, document_id: str) -> Any:
        return self.request("POST", "/documents/" + _id(document_id) + "/trash")[0]
    def delete_document_permanently(self, document_id: str) -> Any:
        return self.request("DELETE", "/documents/" + _id(document_id))[0]
    def deleted_document_ids(self, **params: Any) -> list[Any]:
        return self.pages("/deleted_documents", params=params, accept="application/vnd.mendeley-deleted-document.1+json")
    def restore_document(self, document_id: str) -> Any:
        return self.request("POST", "/trash/" + _id(document_id) + "/restore")[0]
    def search_library_documents(self, query: str, **params: Any) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise MendeleyError("Library search query must not be empty")
        params["query"] = query.strip()
        return self.pages("/search/documents", params=params, accept=MEDIA["documents"])
    def list_document_types(self) -> list[dict[str, Any]]:
        return self.pages("/document_types", accept="application/vnd.mendeley-document-type.1+json")
    def create_document_from_file(self, file_path: Path) -> Any:
        supplied = Path(file_path).expanduser()
        if supplied.is_symlink(): raise MendeleyError("Document import path must not be a symlink")
        path = supplied.resolve(strict=True)
        if not path.is_file(): raise MendeleyError("Document import path must be a regular file")
        payload = path.read_bytes()
        if len(payload) > MAX_UPLOAD_BYTES: raise MendeleyError("File exceeds 100 MiB upload limit")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        safe_name = path.name.replace('"', "_").replace("\\", "_").replace("\r", "_").replace("\n", "_")
        headers = {"Content-Type": content_type, "Content-Disposition": f'attachment; filename="{safe_name}"'}
        return self.request("POST", "/documents", raw_body=payload, headers=headers, accept=MEDIA["documents"])[0]

    # Folders
    def list_folders(self, **params: Any) -> list[dict[str, Any]]:
        return self.pages("/folders", params=params, accept=MEDIA["folders"])
    def get_folder(self, folder_id: str) -> Any:
        return self.request("GET", "/folders/" + _id(folder_id), accept=MEDIA["folders"])[0]
    def create_folder(self, name: str, *, parent_id: str | None = None) -> Any:
        if not name.strip(): raise MendeleyError("Folder name must not be empty")
        body = {"name": name}
        if parent_id: body["parent_id"] = _id(parent_id)
        return self.request("POST", "/folders", body=body, accept=MEDIA["folders"])[0]
    def update_folder(self, folder_id: str, changes: dict[str, Any]) -> Any:
        if not changes: raise MendeleyError("Folder changes must not be empty")
        return self.request("PATCH", "/folders/" + _id(folder_id), body=changes, accept=MEDIA["folders"])[0]
    def delete_folder(self, folder_id: str) -> Any:
        return self.request("DELETE", "/folders/" + _id(folder_id))[0]
    def list_folder_documents(self, folder_id: str, **params: Any) -> list[Any]:
        return self.pages("/folders/" + _id(folder_id) + "/documents", params=params, accept=MEDIA["documents"])
    def add_document_to_folder(self, folder_id: str, document_id: str) -> Any:
        return self.request("POST", "/folders/" + _id(folder_id) + "/documents", body={"id": _id(document_id)}, accept=MEDIA["documents"])[0]
    def remove_document_from_folder(self, folder_id: str, document_id: str) -> Any:
        return self.request("DELETE", "/folders/" + _id(folder_id) + "/documents/" + _id(document_id))[0]

    # Annotations
    def list_annotations(self, **params: Any) -> list[dict[str, Any]]:
        return self.pages("/annotations", params=params, accept=MEDIA["annotations"])
    def get_annotation(self, annotation_id: str) -> Any:
        return self.request("GET", "/annotations/" + _id(annotation_id), accept=MEDIA["annotations"])[0]
    def create_annotation(self, annotation: dict[str, Any]) -> Any:
        if not isinstance(annotation, dict) or not annotation.get("document_id"):
            raise MendeleyError("Annotation requires document_id")
        return self.request("POST", "/annotations", body=annotation, accept=MEDIA["annotations"])[0]
    def update_annotation(self, annotation_id: str, changes: dict[str, Any]) -> Any:
        if not changes: raise MendeleyError("Annotation changes must not be empty")
        return self.request("PATCH", "/annotations/" + _id(annotation_id), body=changes, accept=MEDIA["annotations"])[0]
    def delete_annotation(self, annotation_id: str) -> Any:
        return self.request("DELETE", "/annotations/" + _id(annotation_id))[0]

    # Files
    def list_files(self, **params: Any) -> list[dict[str, Any]]:
        return self.pages("/files", params=params, accept=MEDIA["files"])
    def list_document_files(self, document_id: str, **params: Any) -> list[dict[str, Any]]:
        return self.pages("/documents/v1/" + _id(document_id) + "/files", params=params, accept=MEDIA["files"])
    def delete_file(self, file_id: str) -> Any:
        return self.request("DELETE", "/files/" + _id(file_id))[0]
    def delete_document_file(self, document_id: str, file_id: str) -> Any:
        return self.request("DELETE", "/documents/v1/" + _id(document_id) + "/files/" + _id(file_id))[0]
    def upload_document_file(self, document_id: str, file_path: Path) -> Any:
        supplied = Path(file_path).expanduser()
        if supplied.is_symlink(): raise MendeleyError("Upload path must not be a symlink")
        path = supplied.resolve(strict=True)
        if not path.is_file(): raise MendeleyError("Upload path must be a regular file")
        payload = path.read_bytes()
        if len(payload) > MAX_UPLOAD_BYTES: raise MendeleyError("File exceeds 100 MiB upload limit")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        name = path.name.replace('"', "_").replace("\\", "_").replace("\r", "_").replace("\n", "_")
        headers = {"Content-Type": mime, "Content-Disposition": f'attachment; filename="{name}"'}
        return self.request("POST", "/documents/v1/" + _id(document_id) + "/files", raw_body=payload, headers=headers, accept=MEDIA["files"])[0]
    def upload_file(self, document_id: str, file_path: Path) -> Any:
        supplied = Path(file_path).expanduser()
        if supplied.is_symlink(): raise MendeleyError("Upload path must not be a symlink")
        path = supplied.resolve(strict=True)
        if not path.is_file(): raise MendeleyError("Upload path must be a regular file")
        payload = path.read_bytes()
        if len(payload) > MAX_UPLOAD_BYTES: raise MendeleyError("File exceeds 100 MiB upload limit")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        name = path.name.replace('"', "_").replace("\\", "_").replace("\r", "_").replace("\n", "_")
        headers = {"Content-Type": mime, "Content-Disposition": f'attachment; filename="{name}"', "Link": f'<{self.config.api_base_url.rstrip("/")}/documents/{_id(document_id)}>; rel="document"'}
        return self.request("POST", "/files", raw_body=payload, headers=headers, accept=MEDIA["files"])[0]
    def download_file(self, file_id: str, destination: Path) -> dict[str, Any]:
        """Follow the API's 303 signed URL without forwarding the Bearer token."""
        path = "/files/" + _id(file_id)
        req = urllib.request.Request(self.config.api_base_url.rstrip("/") + path, headers={"Authorization": "Bearer " + self._valid_token(), "User-Agent": USER_AGENT}, method="GET")
        try:
            response = self._open(req, timeout=self.config.timeout)
            with response:
                if getattr(response, "status", 200) != 200: raise MendeleyError("Expected a 303 signed download redirect", status=getattr(response, "status", None))
                data = response.read(MAX_DOWNLOAD_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code != 303: raise MendeleyError(f"Mendeley file endpoint returned HTTP {exc.code}", status=exc.code) from exc
            location = exc.headers.get("Location")
            if not location: raise MendeleyError("Mendeley file response omitted signed download URL")
            parsed = urllib.parse.urlsplit(location)
            if parsed.scheme != "https" or not parsed.hostname: raise MendeleyError("Refusing a non-HTTPS signed file URL")
            # Never attach the Mendeley bearer token to the pre-signed storage URL.
            try:
                with urllib.request.urlopen(urllib.request.Request(location, headers={"User-Agent": USER_AGENT}), timeout=self.config.timeout) as file_response:
                    data = file_response.read(MAX_DOWNLOAD_BYTES + 1)
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                raise MendeleyError("Signed file download failed") from error
        if len(data) > MAX_DOWNLOAD_BYTES: raise MendeleyError("Downloaded file exceeded 100 MiB safety limit")
        target = Path(destination).expanduser()
        if target.exists() or target.is_symlink(): raise MendeleyError("Refusing to overwrite an existing download target")
        for parent in (target.parent, *target.parent.parents):
            if parent.is_symlink(): raise MendeleyError("Refusing a symlinked download destination directory")
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".part", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.replace(tmp_name, target)
            if os.name != "nt": target.chmod(0o600)
        finally:
            try: Path(tmp_name).unlink(missing_ok=True)
            except OSError: pass
        import hashlib
        return {"path": str(target), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    # Catalog and search (catalog lookup is distinct from the user's private library)
    def search_catalog(self, **params: Any) -> list[dict[str, Any]]:
        return self.pages("/catalog", params=params, accept=MEDIA["catalog"])
    def search_catalog_query(self, query: str, **params: Any) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise MendeleyError("Catalog search query must not be empty")
        params["query"] = query.strip()
        return self.pages("/search/catalog", params=params, accept=MEDIA["catalog"])
    def search_profiles(self, query: str, **params: Any) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not query.strip():
            raise MendeleyError("Profile search query must not be empty")
        params["query"] = query.strip()
        return self.pages("/search/profiles", params=params, accept="application/vnd.mendeley-profile.1+json")

    # Groups v2 (legacy /groups endpoints are deliberately not used)
    def list_groups(self, **params: Any) -> list[dict[str, Any]]:
        return self.pages("/groups/v2", params=params, accept="application/vnd.mendeley-group-list+json")
    def get_group(self, group_id: str) -> Any:
        return self.request("GET", "/groups/v2/" + _id(group_id), accept="application/vnd.mendeley-group+json")[0]
    def create_group(self, payload: dict[str, Any]) -> Any:
        if not isinstance(payload, dict) or not str(payload.get("name", "")).strip():
            raise MendeleyError("Group creation requires a non-empty name")
        return self.request("POST", "/groups/v2", body=payload, accept="application/vnd.mendeley-group+json")[0]
    def update_group(self, group_id: str, changes: dict[str, Any]) -> Any:
        if not changes: raise MendeleyError("Group changes must not be empty")
        return self.request("PATCH", "/groups/v2/" + _id(group_id), body=changes, accept="application/vnd.mendeley-group+json")[0]
    def delete_group(self, group_id: str) -> Any:
        return self.request("DELETE", "/groups/v2/" + _id(group_id))[0]
    def list_group_members(self, group_id: str, **params: Any) -> list[dict[str, Any]]:
        return self.pages("/groups/v2/" + _id(group_id) + "/members", params=params, accept="application/vnd.mendeley-group-member-list+json")
    def update_group_member(self, group_id: str, profile_id: str, role: str) -> Any:
        if role not in {"admin", "normal"}: raise MendeleyError("Group member role must be admin or normal")
        return self.request("PATCH", "/groups/v2/" + _id(group_id) + "/members/" + _id(profile_id), body={"membership": role}, accept="application/vnd.mendeley-group-membership+json")[0]
    def remove_group_member(self, group_id: str, profile_id: str) -> Any:
        return self.request("DELETE", "/groups/v2/" + _id(group_id) + "/members/" + _id(profile_id))[0]
    def join_group(self, group_id: str) -> Any:
        return self.request("POST", "/groups/v2/" + _id(group_id) + "/members")[0]
    def leave_group(self, group_id: str) -> Any:
        return self.request("DELETE", "/groups/v2/" + _id(group_id) + "/members")[0]
    def follow_group(self, group_id: str) -> Any:
        return self.request("POST", "/groups/v2/" + _id(group_id) + "/followers")[0]
    def unfollow_group(self, group_id: str) -> Any:
        return self.request("DELETE", "/groups/v2/" + _id(group_id) + "/followers")[0]
    def group_limits(self, group_id: str | None = None) -> Any:
        path = "/groups/v2/limits" if group_id is None else "/groups/v2/" + _id(group_id) + "/limits"
        return self.request("GET", path)[0]
    def list_group_invitations(self, group_id: str | None = None, **params: Any) -> list[dict[str, Any]]:
        path = "/groups/v2/invitations" if group_id is None else "/groups/v2/" + _id(group_id) + "/invitations"
        return self.pages(path, params=params, accept="application/vnd.mendeley-group-invitation-list+json")
    def invite_group_members(self, group_id: str, payload: dict[str, Any]) -> Any:
        recipients = payload.get("recipients") if isinstance(payload, dict) else None
        if not isinstance(recipients, list) or not recipients:
            raise MendeleyError("Group invitation requires a non-empty recipients array")
        return self.request("POST", "/groups/v2/" + _id(group_id) + "/invitations", body=payload, accept="application/vnd.mendeley-group-invitation-response-list+json")[0]
    def group_invitation_action(self, group_id: str, invitation_id: str, action: str) -> Any:
        if action not in {"resend", "revoke"}: raise MendeleyError("Unsupported group invitation action")
        path = "/groups/v2/" + _id(group_id) + "/invitations/" + _id(invitation_id) + "/actions/" + action
        return self.request("POST", path)[0]
    def respond_to_group_invitation(self, group_id: str, invitation_id: str, accept: bool) -> Any:
        action = "accept" if accept else "decline"
        path = "/groups/v2/" + _id(group_id) + "/invitations/" + _id(invitation_id) + "/actions/" + action
        return self.request("POST", path)[0]
    def request_group_join(self, group_id: str, message: str) -> Any:
        if not message.strip(): raise MendeleyError("Group join request message must not be empty")
        path = "/groups/v2/" + _id(group_id) + "/actions/join_request"
        return self.request("POST", path, body={"message": message}, accept="application/vnd.mendeley-group-message+json")[0]
