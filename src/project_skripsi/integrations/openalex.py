"""OpenAlex Works search with private caching and conservative normalization.

The adapter requests bibliographic metadata only by default. Abstract retrieval is
an explicit opt-in; no PDF or full-text download is performed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.request import HTTPRedirectHandler, build_opener

from .crossref import normalize_doi

BASE_URL = "https://api.openalex.org/works"
MAX_PAGE_SIZE = 25
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60
BASE_FIELDS = (
    "id,doi,display_name,publication_year,publication_date,type,authorships,"
    "primary_location,open_access,language,cited_by_count"
)
ABSTRACT_FIELD = "abstract_inverted_index"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _private_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        try:
            path.parent.chmod(0o700)
        except OSError:
            pass
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            temporary.chmod(0o600)
        os.replace(temporary, path)
        if os.name != "nt":
            path.chmod(0o600)
            # Persist the directory entry as well as file contents where the
            # filesystem supports directory fsync (important for crash recovery).
            try:
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def reconstruct_abstract(inverted_index: Any) -> str | None:
    """Reconstruct an OpenAlex inverted-index abstract without inventing gaps."""
    if not isinstance(inverted_index, dict) or not inverted_index:
        return None
    positions: dict[int, str] = {}
    for token, indices in inverted_index.items():
        if not isinstance(token, str) or not token.strip() or not isinstance(indices, list):
            continue
        for index in indices:
            if isinstance(index, int) and index >= 0:
                # Preserve the first value if malformed data repeats a position.
                positions.setdefault(index, token)
    if not positions:
        return None
    max_position = max(positions)
    # Defensive bound against malformed provider payloads.
    if max_position > 100_000:
        return None
    if len(positions) < max_position + 1:
        # A gap means the provider index is incomplete; don't fabricate a sentence.
        return None
    return " ".join(positions[index] for index in range(max_position + 1)).strip() or None


def _clean_doi(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return normalize_doi(value).casefold()
    except ValueError:
        return None


def _source_id(work: dict[str, Any], doi: str | None) -> str:
    openalex_id = str(work.get("id") or "").strip()
    title = str(work.get("display_name") or work.get("title") or "").strip()
    year = work.get("publication_year")
    identity = f"doi:{doi}" if doi else (f"openalex:{openalex_id}" if openalex_id else f"title:{title.casefold()}|{year}")
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16].upper()
    return f"OA-{digest}"


def _authors(work: dict[str, Any]) -> list[str]:
    values: list[str] = []
    authorships = work.get("authorships")
    if not isinstance(authorships, list):
        return values
    for item in authorships:
        if not isinstance(item, dict):
            continue
        author = item.get("author")
        if isinstance(author, dict):
            name = author.get("display_name")
            if isinstance(name, str) and name.strip():
                values.append(name.strip())
    return values


def _source_type(value: Any) -> str:
    normalized = str(value or "").casefold().replace("_", "-")
    if normalized in {"article", "journal-article", "proceedings-article", "review"}:
        return "JOURNAL_ARTICLE"
    if normalized in {"book", "book-chapter", "monograph"}:
        return "BOOK"
    if normalized in {"dissertation", "thesis"}:
        return "DISSERTATION"
    if normalized == "dataset":
        return "DATASET"
    return "OTHER"


def normalize_work(work: dict[str, Any], *, retrieval_date: str, include_abstract: bool) -> dict[str, Any] | None:
    """Convert one provider work into a source-register record plus snapshot fields."""
    if not isinstance(work, dict):
        return None
    title = work.get("display_name") or work.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    openalex_id = str(work.get("id") or "").strip()
    if not re.fullmatch(r"https://openalex\.org/W[0-9A-Za-z]+", openalex_id):
        return None

    doi = _clean_doi(work.get("doi"))
    doi_url = f"https://doi.org/{urllib.parse.quote(doi, safe='/') }" if doi else None
    url = doi_url or openalex_id
    abstract = reconstruct_abstract(work.get(ABSTRACT_FIELD)) if include_abstract else None
    year = work.get("publication_year")
    if isinstance(year, bool) or not isinstance(year, int) or not 1500 <= year <= 2200:
        year = None
    primary_location = work.get("primary_location") if isinstance(work.get("primary_location"), dict) else {}
    license_value = primary_location.get("license") if isinstance(primary_location, dict) else None
    open_access = work.get("open_access") if isinstance(work.get("open_access"), dict) else {}
    oa_status = open_access.get("oa_status") if isinstance(open_access, dict) else None
    oa_url = open_access.get("oa_url") if isinstance(open_access, dict) else None
    cited_by_count = work.get("cited_by_count")
    if not isinstance(cited_by_count, int):
        cited_by_count = None

    source_record: dict[str, Any] = {
        "source_id": _source_id(work, doi),
        "source_type": _source_type(work.get("type")),
        "title": title.strip(),
        "authors": _authors(work),
        "year": year,
        "doi": doi,
        "url": url,
        "retrieval_date": retrieval_date,
        "access_status": "ABSTRACT_ONLY" if abstract else "METADATA_ONLY",
        "retrieval_method": "OpenAlex REST API /works search; bibliographic metadata only",
        "rights_status": "UNKNOWN",
        "license": str(license_value) if license_value else None,
        "notes": (
            f"Provider=OpenAlex; OpenAlex ID={openalex_id}; cited_by_count={cited_by_count}; "
            f"open_access_status={oa_status}; open_access_url={oa_url}; "
            "Provider metadata is not independent source-content verification. "
            "No PDF or full text was retrieved. Rights status remains UNKNOWN."
        ),
    }
    if abstract:
        source_record["exact_locator"] = "OpenAlex abstract_inverted_index (provider-reconstructed abstract)"
    snapshot_item = {
        "source": source_record,
        "provider_metadata": {
            "openalex_id": openalex_id,
            "type": work.get("type"),
            "publication_date": work.get("publication_date"),
            "language": work.get("language"),
            "cited_by_count": cited_by_count,
            "open_access_status": oa_status,
            "open_access_url": oa_url,
            "license_statement": license_value,
        },
    }
    if abstract:
        snapshot_item["abstract"] = abstract
    return snapshot_item


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value.strip()))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            delta = (parsed - datetime.now(timezone.utc)).total_seconds()
            return max(0.0, delta)
        except (TypeError, ValueError, OverflowError):
            return None


class OpenAlexClient:
    """Small standard-library-only OpenAlex search client."""

    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        api_key: str | None = None,
        mailto: str | None = None,
        timeout: int = 20,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        max_retries: int = 2,
        opener: Any | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if timeout < 1 or timeout > 60:
            raise ValueError("timeout must be between 1 and 60 seconds")
        if cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds must not be negative")
        if max_retries < 0 or max_retries > 4:
            raise ValueError("max_retries must be between 0 and 4")
        if mailto and ("\n" in mailto or "\r" in mailto):
            raise ValueError("mailto must be a single-line contact address")
        self.cache_dir = cache_dir
        self.api_key = api_key or os.environ.get("OPENALEX_API_KEY")
        if self.api_key and ("\n" in self.api_key or "\r" in self.api_key):
            raise ValueError("api_key must be a single-line secret")
        self.mailto = mailto
        self.timeout = timeout
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_retries = max_retries
        self.opener = opener or build_opener(_NoRedirect())
        self.sleeper = sleeper
        self.clock = clock

    def _cache_path(self, query: str, per_page: int, include_abstracts: bool) -> Path | None:
        if self.cache_dir is None:
            return None
        cache_key = json.dumps(
            {"query": query.casefold(), "per_page": per_page, "include_abstracts": include_abstracts},
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"openalex-{digest}.json"

    def _request(self, query: str, per_page: int, include_abstracts: bool) -> tuple[dict[str, Any], str]:
        params: dict[str, str] = {
            "search": query,
            "per_page": str(per_page),
            "page": "1",
            "select": BASE_FIELDS + ("," + ABSTRACT_FIELD if include_abstracts else ""),
        }
        if self.mailto:
            params["mailto"] = self.mailto
        url = BASE_URL + "?" + urllib.parse.urlencode(params)
        safe_url = url
        headers = {"Accept": "application/json", "User-Agent": "Project-SKRIPSI/0.3.1 (OpenAlex literature search)"}
        if self.api_key:
            # OpenAlex supports bearer auth; keep credentials out of URLs and cache records.
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(url, headers=headers, method="GET")
        for attempt in range(self.max_retries + 1):
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("OpenAlex response exceeded the 10 MiB safety limit")
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise RuntimeError(f"OpenAlex returned invalid JSON: {exc}") from exc
                if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                    raise RuntimeError("OpenAlex response did not contain a results array")
                return payload, safe_url
            except urllib.error.HTTPError as exc:
                retryable = exc.code == 429 or exc.code in {500, 502, 503, 504}
                if not retryable or attempt >= self.max_retries:
                    if exc.code == 429:
                        retry_after = _retry_after_seconds(exc.headers.get("Retry-After") if exc.headers else None)
                        suffix = f" Retry-After was {retry_after:.1f}s." if retry_after is not None else ""
                        raise RuntimeError(f"OpenAlex rate limit reached (HTTP 429).{suffix} Retry later or use a cached result.") from exc
                    if 300 <= exc.code < 400:
                        raise RuntimeError(f"OpenAlex redirect refused (HTTP {exc.code})") from exc
                    raise RuntimeError(f"OpenAlex request failed with HTTP {exc.code}") from exc
                delay = _retry_after_seconds(exc.headers.get("Retry-After") if exc.headers else None)
                if delay is not None and delay > 10:
                    raise RuntimeError(
                        f"OpenAlex requested a {delay:.1f}s Retry-After; automatic wait is capped at 10s. Retry manually later."
                    ) from exc
                self.sleeper(delay if delay is not None else min(2 ** attempt, 5))
            except urllib.error.URLError as exc:
                if attempt >= self.max_retries:
                    raise RuntimeError(f"OpenAlex API unavailable: {exc}") from exc
                self.sleeper(min(2 ** attempt, 5))
        raise RuntimeError("OpenAlex request failed after bounded retries")

    def search(self, query: str, *, per_page: int = 10, include_abstracts: bool = False, use_cache: bool = True) -> dict[str, Any]:
        normalized_query = " ".join(query.split()) if isinstance(query, str) else ""
        if not normalized_query:
            raise ValueError("search query must not be blank")
        if len(normalized_query) > 500:
            raise ValueError("search query must be 500 characters or fewer")
        if isinstance(per_page, bool) or not isinstance(per_page, int) or per_page < 1 or per_page > MAX_PAGE_SIZE:
            raise ValueError(f"per_page must be between 1 and {MAX_PAGE_SIZE}")
        cache_path = self._cache_path(normalized_query, per_page, include_abstracts)
        payload: dict[str, Any] | None = None
        cache_hit = False
        retrieved_at = _utc_now()
        request_url = BASE_URL
        if use_cache and cache_path and cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                age = self.clock() - float(cached.get("cached_epoch", 0))
                if (
                    0 <= age <= self.cache_ttl_seconds
                    and cached.get("query_key") == hashlib.sha256(
                        json.dumps({"query": normalized_query.casefold(), "per_page": per_page, "include_abstracts": include_abstracts}, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    ).hexdigest()
                    and isinstance(cached.get("payload"), dict)
                ):
                    payload = cached["payload"]
                    retrieved_at = str(cached.get("retrieved_at") or retrieved_at)
                    request_url = str(cached.get("request_url") or BASE_URL)
                    cache_hit = True
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                payload = None
        if payload is None:
            payload, request_url = self._request(normalized_query, per_page, include_abstracts)
            retrieved_at = _utc_now()
            if use_cache and cache_path:
                cache_key = hashlib.sha256(
                    json.dumps({"query": normalized_query.casefold(), "per_page": per_page, "include_abstracts": include_abstracts}, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                _private_write(cache_path, {
                    "schema_version": "1.0.0", "query_key": cache_key,
                    "query": normalized_query, "retrieved_at": retrieved_at,
                    "cached_epoch": self.clock(), "request_url": request_url,
                    "payload": payload,
                })
        items = [
            normalized for work in payload.get("results", [])
            if (normalized := normalize_work(work, retrieval_date=retrieved_at[:10], include_abstract=include_abstracts)) is not None
        ]
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        return {
            "schema_version": "1.0.0",
            "provider": "openalex",
            "query": normalized_query,
            "retrieved_at": retrieved_at,
            "request_url": request_url,
            "cache_hit": cache_hit,
            "total_count": meta.get("count"),
            "per_page": per_page,
            "result_count": len(items),
            "abstracts_requested": bool(include_abstracts),
            "items": items,
            "flags": [
                "OpenAlex records are provider metadata and are not independent verification of article contents.",
                "Citation counts and open-access labels are provider snapshots and can change over time.",
                "No PDF or full-text content was downloaded.",
                "Rights status for the underlying publication remains UNKNOWN unless separately verified.",
            ],
        }
