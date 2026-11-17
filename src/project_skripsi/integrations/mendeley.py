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
