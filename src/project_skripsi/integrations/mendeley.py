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
    "profiles": "application/vnd.mendeley-profile.2+json",
    "profile_patch": "application/vnd.mendeley-profile-amendment.2+json",
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
        if token is None: raise MendeleyError("Not connected. Run project-skripsi-mendeley auth-url and complete OAuth first")
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

    def request(self, method: str, path: str, *, params: dict[str, Any] | None = None, body: Any = None, raw_body: bytes | None = None, headers: dict[str, str] | None = None, accept: str | None = None, content_type: str | None = None, retry_get: bool = True) -> tuple[Any, Any, int]:
        method = method.upper()
        if method not in {"GET", "POST", "PATCH", "DELETE", "PUT"}: raise MendeleyError("Unsupported HTTP method")
        url = self._safe_api_url(self.config.api_base_url, path, params)
        data = raw_body if raw_body is not None else (json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None)
        request_headers = {"Authorization": "Bearer " + self._valid_token(), "User-Agent": USER_AGENT}
        if accept: request_headers["Accept"] = accept
        if body is not None: request_headers["Content-Type"] = content_type or accept or "application/json"
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

    def pages(self, path: str, *, params: dict[str, Any] | None = None, accept: str) -> list[Any]:
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
        data, _, _ = self.request("GET", "/profiles/v2/me", accept=MEDIA["profiles"])
        if not isinstance(data, dict): raise MendeleyError("Profile response is not an object")
        return data
    def update_profile(self, changes: dict[str, Any]) -> Any:
        if not changes: raise MendeleyError("Profile changes must not be empty")
        return self.request("PATCH", "/profiles/v2/me", body=changes, accept=MEDIA["profile_patch"])[0]
    def get_profile_by_id(self, profile_id: str) -> dict[str, Any]:
        data, _, _ = self.request("GET", "/profiles/v2/" + _id(profile_id), accept=MEDIA["profiles"])
        if not isinstance(data, dict): raise MendeleyError("Profile response is not an object")
        return data

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
        if str(payload.get("access_level", "private")).casefold() in {"public", "open", "invite_only"}:
            raise MendeleyError("Mendeley has retired public/open/invite-only group operations; create private groups only")
        return self.request("POST", "/groups/v2", body=payload, accept="application/vnd.mendeley-group+json")[0]
    def update_group(self, group_id: str, changes: dict[str, Any]) -> Any:
        if not changes: raise MendeleyError("Group changes must not be empty")
        if str(changes.get("access_level", "")).casefold() in {"public", "open", "invite_only"}:
            raise MendeleyError("Mendeley has retired public/open/invite-only group operations; private groups only")
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
    def leave_group(self, group_id: str) -> Any:
        return self.request("DELETE", "/groups/v2/" + _id(group_id) + "/members")[0]
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
        return self.request(
            "POST", "/groups/v2/" + _id(group_id) + "/invitations", body=payload,
            content_type="application/vnd.mendeley-group-invitation+json",
            accept="application/vnd.mendeley-group-invitation-response-list+json",
        )[0]
    def group_invitation_action(self, group_id: str, invitation_id: str, action: str) -> Any:
        if action not in {"resend", "revoke"}: raise MendeleyError("Unsupported group invitation action")
        path = "/groups/v2/" + _id(group_id) + "/invitations/" + _id(invitation_id) + "/actions/" + action
        return self.request("POST", path)[0]
    def respond_to_group_invitation(self, group_id: str, accept: bool) -> Any:
        action = "accept_invitation" if accept else "decline_invitation"
        path = "/groups/v2/" + _id(group_id) + "/actions/" + action
        return self.request("POST", path)[0]
    def request_group_join(self, group_id: str, message: str) -> Any:
        if not message.strip(): raise MendeleyError("Group join request message must not be empty")
        path = "/groups/v2/" + _id(group_id) + "/actions/join_request"
        return self.request("POST", path, body={"message": message}, accept="application/vnd.mendeley-group-message+json")[0]
    def respond_to_group_join_request(self, group_id: str, profile_id: str, accept: bool, message: str) -> Any:
        if not message.strip(): raise MendeleyError("Group join-request response message must not be empty")
        action = "accept" if accept else "decline"
        path = "/groups/v2/" + _id(group_id) + "/members/" + _id(profile_id) + "/actions/" + action
        return self.request("POST", path, body={"message": message}, accept="application/vnd.mendeley-group-message+json")[0]
        path = "/groups/v2/" + _id(group_id) + "/actions/join_request"
        return self.request("POST", path, body={"message": message}, accept="application/vnd.mendeley-group-message+json")[0]


def _mendeley_source_record(document: dict[str, Any], *, retrieval_date: str) -> dict[str, Any] | None:
    """Map a user-library item to a metadata-only, review-required source record."""
    document_id = document.get("id")
    title = document.get("title")
    if not isinstance(document_id, str) or not document_id.strip() or not isinstance(title, str) or not title.strip():
        return None
    raw_type = str(document.get("type") or "").casefold()
    if raw_type in {"journal", "journal_article", "article"}: source_type = "JOURNAL_ARTICLE"
    elif raw_type in {"book", "book_section"}: source_type = "BOOK"
    elif raw_type in {"thesis", "dissertation"}: source_type = "THESIS" if raw_type == "thesis" else "DISSERTATION"
    else: source_type = "OTHER"
    authors = []
    for person in document.get("authors", []) if isinstance(document.get("authors", []), list) else []:
        if not isinstance(person, dict): continue
        name = " ".join(str(person.get(part) or "").strip() for part in ("first_name", "last_name")).strip()
        if name: authors.append(name)
    identifiers = document.get("identifiers") if isinstance(document.get("identifiers"), dict) else {}
    doi = identifiers.get("doi")
    year = document.get("year")
    if not isinstance(year, int) or not 1500 <= year <= 2200: year = None
    item_url = document.get("link")
    if not isinstance(item_url, str) or not item_url.startswith("https://"):
        item_url = API_BASE + "/documents/" + urllib.parse.quote(document_id, safe="-")
    import hashlib
    stable_id = hashlib.sha256(document_id.encode("utf-8")).hexdigest()[:32].upper()
    return {
        "source_id": "MENDELEY-" + stable_id,
        "source_type": source_type,
        "title": title.strip(),
        "authors": authors,
        "year": year,
        "doi": str(doi).strip() if isinstance(doi, str) and doi.strip() else None,
        "url": item_url,
        "retrieval_date": retrieval_date,
        "access_status": "METADATA_ONLY",
        "retrieval_method": "MENDELEY_API_USER_LIBRARY",
        "exact_locator": None,
        "rights_status": "UNKNOWN",
        "license": None,
        "file_sha256": None,
        "notes": f"Imported from the authorized user's Mendeley library (item ID: {document_id}). Metadata only; inspect the item and its file/access rights before using it as evidence.",
        "citation_author": None,
        "reference_authors": None,
    }


def sync_library_to_workspace(client: MendeleyClient, workspace: Path, *, apply: bool = False) -> dict[str, Any]:
    """Preview or explicitly import Mendeley references into a private source register.

    The default is read-only. Applying only appends newly identified Mendeley items;
    it never changes existing source records or creates claim-evidence links.
    """
    from ..audit import append_audit_event
    from ..quality import validate_source_register
    from ..validation import validate_workspace
    import hashlib
    supplied_workspace = Path(workspace).expanduser()
    if supplied_workspace.is_symlink():
        raise MendeleyError("Workspace path must not be a symlink")
    project_dir = supplied_workspace.resolve(strict=True)
    if not project_dir.is_dir():
        raise MendeleyError("Workspace must be an existing real directory")
    errors, manifest, _ledger = validate_workspace(project_dir)
    if errors or not manifest:
        raise MendeleyError("Workspace validation failed: " + "; ".join(errors[:8]))
    register_path = project_dir / "sources" / "registry" / "source_register.json"
    if register_path.is_symlink() or not register_path.is_file():
        raise MendeleyError("Workspace source register is missing or symlinked")
    documents = client.list_documents(view="all")
    date_value = datetime.now(timezone.utc).date().isoformat()
    candidates = [record for item in documents if isinstance(item, dict) and (record := _mendeley_source_record(item, retrieval_date=date_value)) is not None]
    skipped = len(documents) - len(candidates)
    with FileLock(project_dir / "state" / ".mendeley-sync.lock"):
        if register_path.is_symlink(): raise MendeleyError("Refusing symlinked source register")
        try: register = json.loads(register_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc: raise MendeleyError("Workspace source register could not be read") from exc
        if register.get("project_id") != manifest.get("project_id") or not isinstance(register.get("sources"), list) or not isinstance(register.get("claim_evidence_links"), list):
            raise MendeleyError("Workspace source register has an invalid project identity or structure")
        validation_errors = validate_source_register(register["sources"])
        if validation_errors: raise MendeleyError("Existing source register is invalid: " + "; ".join(validation_errors[:8]))
        existing_ids = {str(item.get("source_id")) for item in register["sources"] if isinstance(item, dict)}
        additions = [item for item in candidates if item["source_id"] not in existing_ids]
        duplicate_ids = len(candidates) - len(additions)
        result = {
            "status": "PREVIEW_ONLY" if not apply else ("NO_CHANGES" if not additions else "APPLIED"),
            "project_id": manifest["project_id"],
            "mendeley_documents_seen": len(documents),
            "eligible_metadata_records": len(candidates),
            "new_records": len(additions),
            "already_imported": duplicate_ids,
            "skipped_missing_id_or_title": skipped,
            "claim_evidence_links_created": 0,
            "source_register": str(register_path),
            "note": "Imported entries are METADATA_ONLY; they are not content-reviewed evidence and require human source review.",
        }
        if not apply or not additions: return result
        combined = list(register["sources"]) + additions
        validation_errors = validate_source_register(combined)
        if validation_errors: raise MendeleyError("Imported source records failed validation: " + "; ".join(validation_errors[:8]))
        new_register = dict(register)
        new_register["sources"] = combined
        old_bytes = register_path.read_bytes()
        new_bytes = (json.dumps(new_register, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        old_sha = hashlib.sha256(old_bytes).hexdigest()
        new_sha = hashlib.sha256(new_bytes).hexdigest()
        backup = register_path.with_name("source_register.mendeley-backup-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
        fd, temp_name = tempfile.mkstemp(prefix="source_register.", suffix=".tmp", dir=register_path.parent)
        try:
            with os.fdopen(fd, "wb") as stream: stream.write(new_bytes); stream.flush(); os.fsync(stream.fileno())
            if os.name != "nt": os.chmod(temp_name, 0o600)
            # A separate immutable snapshot permits manual restoration if the workspace is later edited.
            with backup.open("xb") as backup_stream:
                backup_stream.write(old_bytes); backup_stream.flush(); os.fsync(backup_stream.fileno())
            if os.name != "nt": backup.chmod(0o600)
            os.replace(temp_name, register_path)
            if os.name != "nt": register_path.chmod(0o600)
            append_audit_event(
                project_dir / "audit" / "events.jsonl",
                event_type="MENDELEY_LIBRARY_SYNC", object_type="SOURCE_REGISTER",
                object_id=str(manifest["project_id"]),
                summary=f"Imported {len(additions)} metadata-only Mendeley reference(s); prior source-register SHA-256 {old_sha}; new SHA-256 {new_sha}.",
                actor_type="human_authorized_integration",
                evidence_refs=["MENDELEY_API:/documents", "source_register.json"],
                idempotency_key="mendeley-sync-" + hashlib.sha256((str(manifest["project_id"]) + new_sha).encode()).hexdigest()[:24],
            )
        except BaseException:
            # Restore the original bytes on a caught error; never leave a half-written JSON register.
            if backup.exists():
                restore_fd, restore_name = tempfile.mkstemp(prefix="source_register.restore.", suffix=".tmp", dir=register_path.parent)
                with os.fdopen(restore_fd, "wb") as stream: stream.write(old_bytes); stream.flush(); os.fsync(stream.fileno())
                os.replace(restore_name, register_path)
            raise
        finally:
            try: Path(temp_name).unlink(missing_ok=True)
            except OSError: pass
        result["backup"] = str(backup)
        result["source_register_sha256"] = new_sha
        return result


def _open_no_redirect(request: urllib.request.Request, *, timeout: int = 25):
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl): return None
    return urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout)


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        try:
            target = email.utils.parsedate_to_datetime(value)
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def _next_link(value: str, base: str) -> str | None:
    if not value: return None
    for part in re.split(r",(?=\s*<)", value):
        match = re.match(r"\s*<([^>]+)>\s*;(.*)$", part)
        if match and re.search(r'rel\s*=\s*"?next"?(?:\s|$)', match.group(2), re.I):
            target = urllib.parse.urljoin(base, match.group(1))
            root, parsed = urllib.parse.urlsplit(base), urllib.parse.urlsplit(target)
            if parsed.scheme != "https" or parsed.netloc.casefold() != root.netloc.casefold():
                raise MendeleyError("Refusing pagination link outside the Mendeley API host")
            return target
    return None


def _id(value: str) -> str:
    value = str(value).strip()
    if not value or len(value) > 200 or any(c in value for c in "/?#\\"):
        raise MendeleyError("Invalid Mendeley resource ID")
    return urllib.parse.quote(value, safe="-")


def _load_json_file(path: Path) -> dict[str, Any]:
    try: data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc: raise MendeleyError(f"Cannot read JSON payload file: {path}") from exc
    if not isinstance(data, dict): raise MendeleyError("JSON payload file must contain an object")
    return data


def _dump(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _client(args: argparse.Namespace) -> MendeleyClient:
    token_path = getattr(args, "token_file", None)
    return MendeleyClient(MendeleyConfig.from_env(token_path=Path(token_path) if token_path else None))



def run_local_oauth_login(client: MendeleyClient, *, timeout_seconds: int = 240) -> dict[str, Any]:
    """Run a temporary loopback callback server for an exact registered localhost URI."""
    parsed = urllib.parse.urlsplit(client.config.redirect_uri)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise MendeleyError("Automatic login requires a registered http://localhost or http://127.0.0.1 callback URI; otherwise use auth-url/auth-exchange")
    if parsed.query or parsed.fragment:
        raise MendeleyError("Registered redirect URI must not contain a query or fragment")
    try:
        port = parsed.port or 80
    except ValueError as exc:
        raise MendeleyError("Registered localhost redirect URI has an invalid port") from exc
    expected_path = parsed.path or "/"
    if timeout_seconds < 1 or timeout_seconds > 600:
        raise MendeleyError("OAuth callback timeout must be between 1 and 600 seconds")
    url, state = client.authorization_url()
    captured: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            request_path, _, query = self.path.partition("?")
            if request_path != expected_path:
                self.send_error(404)
                return
            values = urllib.parse.parse_qs(query, keep_blank_values=True)
            callback_state = (values.get("state") or [""])[0]
            if not secrets.compare_digest(callback_state, state):
                self.send_error(400, "OAuth state mismatch")
                return
            captured["state"] = callback_state
            if values.get("error"):
                captured["error"] = (values.get("error_description") or values["error"])[0]
            else:
                captured["code"] = (values.get("code") or [""])[0]
            body = b"Mendeley authorization response received. You may close this browser tab and return to Project-SKRIPSI."
            self.send_response(200 if "code" in captured else 400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    try:
        server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    except OSError as exc:
        client.store.consume_state(state)
        raise MendeleyError("Could not bind the registered localhost callback port; use auth-url/auth-exchange") from exc
    server.timeout = 1
    try:
        print("Opening Mendeley authorization in the default browser. If it does not open, copy this URL:")
        print(url)
        webbrowser.open(url)
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline and not captured:
            server.handle_request()
    finally:
        server.server_close()
    if "error" in captured:
        client.store.consume_state(state)
        raise MendeleyError("Mendeley authorization was denied or failed: " + captured["error"][:160])
    if not captured.get("code"):
        client.store.consume_state(state)
        raise MendeleyError("Mendeley OAuth callback timed out; restart login or use auth-url/auth-exchange")
    return client.exchange_code(captured["code"], captured["state"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="project-skripsi-mendeley", description="Free-first local Mendeley API connector")
    parser.add_argument("--token-file", help="local private token store; default ~/.project-skripsi/mendeley/tokens.json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("auth-url", help="create OAuth authorization URL and one-time CSRF state")
    sub.add_parser("login", help="open OAuth in browser and receive callback on registered localhost redirect URI")
    ex = sub.add_parser("auth-exchange", help="exchange callback code after validating the one-time state")
    ex.add_argument("--code", required=True); ex.add_argument("--state", required=True)
    sub.add_parser("status", help="show connection/token expiry without displaying tokens")
    sub.add_parser("logout", help="remove local Mendeley tokens; this does not revoke the provider-side grant")
    sub.add_parser("profile", help="read logged-in Mendeley profile")
    profiles = sub.add_parser("profiles", help="list profiles visible to the authorized Mendeley account")
    profiles.add_argument("--limit", type=int, default=100)
    profile_get = sub.add_parser("profile-get", help="read a public profile by ID")
    profile_get.add_argument("id")
    followers.add_argument("id")
    followees.add_argument("id")
    profile_follow.add_argument("id")
    follow_accept.add_argument("relationship_id")
    profile_unfollow.add_argument("relationship_id")
    profile_unfollow.add_argument("--confirm", required=True)
    updprof = sub.add_parser("profile-update", help="patch the authenticated user profile")
    updprof.add_argument("payload", type=Path)
    docs = sub.add_parser("documents", help="list all user-library documents (view=all)")
    docs.add_argument("--limit", type=int, default=100); docs.add_argument("--modified-since")
    searchlib = sub.add_parser("library-search", help="search documents in the authenticated user's private library")
    searchlib.add_argument("query"); searchlib.add_argument("--limit", type=int, default=100)
    sub.add_parser("document-types", help="list document types accepted by Mendeley")
    getdoc = sub.add_parser("document-get"); getdoc.add_argument("id")
    createdoc = sub.add_parser("document-create"); createdoc.add_argument("payload", type=Path)
    updatedoc = sub.add_parser("document-update", help="patch metadata; optional optimistic-concurrency precondition")
    updatedoc.add_argument("id"); updatedoc.add_argument("payload", type=Path); updatedoc.add_argument("--if-unmodified-since")
    trashdoc = sub.add_parser("document-trash"); trashdoc.add_argument("id")
    deldoc = sub.add_parser("document-delete"); deldoc.add_argument("id"); deldoc.add_argument("--confirm", required=True, help="must exactly match ID; permanently deletes")
    restore = sub.add_parser("document-restore"); restore.add_argument("id")
    fromfile = sub.add_parser("document-from-file"); fromfile.add_argument("file", type=Path)
    folders = sub.add_parser("folders"); folders.add_argument("--limit", type=int, default=100)
    getfolder = sub.add_parser("folder-get"); getfolder.add_argument("id")
    newfolder = sub.add_parser("folder-create"); newfolder.add_argument("name"); newfolder.add_argument("--parent-id")
    upfolder = sub.add_parser("folder-update"); upfolder.add_argument("id"); upfolder.add_argument("payload", type=Path)
    delfolder = sub.add_parser("folder-delete"); delfolder.add_argument("id"); delfolder.add_argument("--confirm", required=True)
    folderdocs = sub.add_parser("folder-documents"); folderdocs.add_argument("id")
    folderadd = sub.add_parser("folder-add-document"); folderadd.add_argument("folder_id"); folderadd.add_argument("document_id")
    folderremove = sub.add_parser("folder-remove-document"); folderremove.add_argument("folder_id"); folderremove.add_argument("document_id")
    anns = sub.add_parser("annotations"); anns.add_argument("--document-id")
    getann = sub.add_parser("annotation-get"); getann.add_argument("id")
    newann = sub.add_parser("annotation-create"); newann.add_argument("payload", type=Path)
    upann = sub.add_parser("annotation-update"); upann.add_argument("id"); upann.add_argument("payload", type=Path)
    delann = sub.add_parser("annotation-delete"); delann.add_argument("id"); delann.add_argument("--confirm", required=True)
    files = sub.add_parser("files"); files.add_argument("--document-id")
    upload = sub.add_parser("file-upload", help="upload using the generic /files endpoint")
    upload.add_argument("document_id"); upload.add_argument("file", type=Path)
    doc_upload = sub.add_parser("document-file-upload", help="upload through the document-scoped files endpoint")
    doc_upload.add_argument("document_id"); doc_upload.add_argument("file", type=Path)
    download = sub.add_parser("file-download"); download.add_argument("id"); download.add_argument("destination", type=Path)
    delfile = sub.add_parser("file-delete"); delfile.add_argument("id"); delfile.add_argument("--confirm", required=True)
    docfiles = sub.add_parser("document-files"); docfiles.add_argument("document_id")
    doc_file_delete = sub.add_parser("document-file-delete")
    doc_file_delete.add_argument("document_id"); doc_file_delete.add_argument("file_id"); doc_file_delete.add_argument("--confirm", required=True)
    sync = sub.add_parser("sync-workspace", help="preview or append Mendeley library metadata into a private workspace source register")
    sync.add_argument("workspace", type=Path)
    sync.add_argument("--apply", action="store_true", help="perform local source-register update; default is preview-only")
    catalog = sub.add_parser("catalog-search", help="search public catalog with metadata filters")
    catalog.add_argument("--doi"); catalog.add_argument("--title"); catalog.add_argument("--authors"); catalog.add_argument("--year", type=int)
    catalog_query = sub.add_parser("catalog-query", help="search public Mendeley catalog by terms")
    catalog_query.add_argument("query"); catalog_query.add_argument("--limit", type=int, default=100)
    profile_search.add_argument("query"); profile_search.add_argument("--limit", type=int, default=100)
    groups = sub.add_parser("groups", help="list your groups using the current Groups v2 API")
    groups.add_argument("--limit", type=int, default=100)
    popular_groups.add_argument("--limit", type=int, default=100)
    group_get = sub.add_parser("group-get"); group_get.add_argument("id")
    group_create = sub.add_parser("group-create"); group_create.add_argument("payload", type=Path)
    group_update = sub.add_parser("group-update"); group_update.add_argument("id"); group_update.add_argument("payload", type=Path)
    group_delete = sub.add_parser("group-delete"); group_delete.add_argument("id"); group_delete.add_argument("--confirm", required=True)
    group_members = sub.add_parser("group-members"); group_members.add_argument("id"); group_members.add_argument("--query")
    group_role = sub.add_parser("group-member-role"); group_role.add_argument("id"); group_role.add_argument("profile_id"); group_role.add_argument("role", choices=["admin", "normal"])
    group_remove = sub.add_parser("group-member-remove"); group_remove.add_argument("id"); group_remove.add_argument("profile_id"); group_remove.add_argument("--confirm", required=True)
    group_leave = sub.add_parser("group-leave"); group_leave.add_argument("id"); group_leave.add_argument("--confirm", required=True)
    group_limits = sub.add_parser("group-limits"); group_limits.add_argument("--id")
    invitations = sub.add_parser("group-invitations"); invitations.add_argument("--id")
    invite = sub.add_parser("group-invite"); invite.add_argument("id"); invite.add_argument("payload", type=Path)
    invite_action = sub.add_parser("group-invitation-action"); invite_action.add_argument("id"); invite_action.add_argument("invitation_id"); invite_action.add_argument("action", choices=["revoke", "resend"])
    invite_response = sub.add_parser("group-invitation-decision"); invite_response.add_argument("id"); invite_response.add_argument("decision", choices=["accept", "decline"])
    group_request = sub.add_parser("group-join-request"); group_request.add_argument("id"); group_request.add_argument("message")
    group_request_action = sub.add_parser("group-join-request-action"); group_request_action.add_argument("id"); group_request_action.add_argument("profile_id"); group_request_action.add_argument("decision", choices=["accept", "decline"]); group_request_action.add_argument("message")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "auth-url":
            client = _client(args); url, state = client.authorization_url()
            print("Open this URL and authorize the application in Mendeley:")
            print(url); print("\nOne-time state (keep private until exchange): " + state)
            print("After redirect, run auth-exchange with the callback code and this state.")
            return 0
        client = _client(args)
        if args.command == "login":
            result = run_local_oauth_login(client)
            _dump(result); return 0
        if args.command == "auth-exchange": result = client.exchange_code(args.code, args.state)
        elif args.command == "status":
            token = client.store.load()
            result = {"status": "CONNECTED" if token and float(token.get("expires_at", 0)) > time.time() else ("TOKEN_REFRESH_REQUIRED" if token else "DISCONNECTED"), "expires_at": token.get("expires_at") if token else None, "token_path": str(client.store.path)}
        elif args.command == "logout": result = {"local_tokens_removed": client.store.clear(), "provider_grant_revoked": False}
        elif args.command == "profile": result = client.get_profile()
        elif args.command == "profiles": result = client.list_profiles(limit=max(1, min(args.limit, 100)))
        elif args.command == "profile-get": result = client.get_profile_by_id(args.id)
        elif args.command == "profile-update": result = client.update_profile(_load_json_file(args.payload))
        elif args.command == "documents": result = client.list_documents(limit=max(1, min(args.limit, 500)), modified_since=args.modified_since)
        elif args.command == "library-search": result = client.search_library_documents(args.query, limit=max(1, min(args.limit, 500)))
        elif args.command == "document-types": result = client.list_document_types()
        elif args.command == "document-get": result = client.get_document(args.id)
        elif args.command == "document-create": result = client.create_document(_load_json_file(args.payload))
        elif args.command == "document-update": result = client.update_document(args.id, _load_json_file(args.payload), if_unmodified_since=args.if_unmodified_since)
        elif args.command == "document-trash": result = client.trash_document(args.id)
        elif args.command == "document-delete":
            if args.confirm != args.id: raise MendeleyError("Confirmation ID does not match; permanent deletion refused")
            result = client.delete_document_permanently(args.id)
        elif args.command == "document-restore": result = client.restore_document(args.id)
        elif args.command == "document-from-file": result = client.create_document_from_file(args.file)
        elif args.command == "folders": result = client.list_folders(limit=max(1, min(args.limit, 500)))
        elif args.command == "folder-get": result = client.get_folder(args.id)
        elif args.command == "folder-create": result = client.create_folder(args.name, parent_id=args.parent_id)
        elif args.command == "folder-update": result = client.update_folder(args.id, _load_json_file(args.payload))
        elif args.command == "folder-delete":
            if args.confirm != args.id: raise MendeleyError("Confirmation ID does not match; folder deletion refused")
            result = client.delete_folder(args.id)
        elif args.command == "folder-documents": result = client.list_folder_documents(args.id)
        elif args.command == "folder-add-document": result = client.add_document_to_folder(args.folder_id, args.document_id)
        elif args.command == "folder-remove-document": result = client.remove_document_from_folder(args.folder_id, args.document_id)
        elif args.command == "annotations": result = client.list_annotations(document_id=args.document_id)
        elif args.command == "annotation-get": result = client.get_annotation(args.id)
        elif args.command == "annotation-create": result = client.create_annotation(_load_json_file(args.payload))
        elif args.command == "annotation-update": result = client.update_annotation(args.id, _load_json_file(args.payload))
        elif args.command == "annotation-delete":
            if args.confirm != args.id: raise MendeleyError("Confirmation ID does not match; annotation deletion refused")
            result = client.delete_annotation(args.id)
        elif args.command == "files": result = client.list_files(document_id=args.document_id)
        elif args.command == "file-upload": result = client.upload_file(args.document_id, args.file)
        elif args.command == "document-file-upload": result = client.upload_document_file(args.document_id, args.file)
        elif args.command == "file-download": result = client.download_file(args.id, args.destination)
        elif args.command == "file-delete":
            if args.confirm != args.id: raise MendeleyError("Confirmation ID does not match; file deletion refused")
            result = client.delete_file(args.id)
        elif args.command == "document-files": result = client.list_document_files(args.document_id)
        elif args.command == "document-file-delete":
            if args.confirm != args.file_id: raise MendeleyError("Confirmation file ID does not match; document file deletion refused")
            result = client.delete_document_file(args.document_id, args.file_id)
        elif args.command == "sync-workspace": result = sync_library_to_workspace(client, args.workspace, apply=args.apply)
        elif args.command == "catalog-search":
            params = {"doi": args.doi, "title": args.title, "authors": args.authors, "year": args.year}
            result = client.search_catalog(**{k: v for k, v in params.items() if v is not None})
        elif args.command == "catalog-query": result = client.search_catalog_query(args.query, limit=max(1, min(args.limit, 500)))
        elif args.command == "groups": result = client.list_groups(limit=max(1, min(args.limit, 500)))
        elif args.command == "group-get": result = client.get_group(args.id)
        elif args.command == "group-create": result = client.create_group(_load_json_file(args.payload))
        elif args.command == "group-update": result = client.update_group(args.id, _load_json_file(args.payload))
        elif args.command == "group-delete":
            if args.confirm != args.id: raise MendeleyError("Confirmation ID does not match; group deletion refused")
            result = client.delete_group(args.id)
        elif args.command == "group-members": result = client.list_group_members(args.id, query=args.query)
        elif args.command == "group-member-role": result = client.update_group_member(args.id, args.profile_id, args.role)
        elif args.command == "group-member-remove":
            if args.confirm != args.profile_id: raise MendeleyError("Confirmation profile ID does not match; member removal refused")
            result = client.remove_group_member(args.id, args.profile_id)
        elif args.command == "group-leave":
            if args.confirm != args.id: raise MendeleyError("Confirmation group ID does not match; leave action refused")
            result = client.leave_group(args.id)
        elif args.command == "group-limits": result = client.group_limits(args.id)
        elif args.command == "group-invitations": result = client.list_group_invitations(args.id)
        elif args.command == "group-invite": result = client.invite_group_members(args.id, _load_json_file(args.payload))
        elif args.command == "group-invitation-action": result = client.group_invitation_action(args.id, args.invitation_id, args.action)
        elif args.command == "group-join-request": result = client.request_group_join(args.id, args.message)
        elif args.command == "group-join-request-action": result = client.respond_to_group_join_request(args.id, args.profile_id, args.decision == "accept", args.message)
        else: raise MendeleyError("Unsupported command")
        _dump(result); return 0
    except (MendeleyError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
