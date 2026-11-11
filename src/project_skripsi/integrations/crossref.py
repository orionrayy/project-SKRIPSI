"""Crossref DOI metadata lookup with cache and explicit limits.

Only a DOI identifier is sent to Crossref; manuscript text is never transmitted.
The returned deposit metadata is bibliographic evidence, not full-text verification.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def normalize_doi(value: str) -> str:
    doi = value.strip()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE).strip()
    doi = doi.rstrip(".,;)")
    if not DOI_RE.fullmatch(doi):
        raise ValueError("value is not a syntactically valid DOI")
    return doi


def _normalize_title(value: str) -> str:
    return " ".join(re.findall(r"[\w]+", value.casefold(), flags=re.UNICODE))


def _metadata_matches(expected: dict[str, Any], actual: dict[str, Any]) -> list[dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    expected_title = expected.get("title")
    actual_titles = actual.get("title") or []
    if expected_title:
        actual_title = actual_titles[0] if actual_titles else ""
        matched = _normalize_title(str(expected_title)) == _normalize_title(str(actual_title))
        comparisons.append({"field": "title", "expected": expected_title, "actual": actual_title, "match": matched})
    expected_year = expected.get("year")
    if expected_year is not None:
        year = None
        for date_field in ("published", "published-print", "published-online", "created", "issued"):
            parts = (actual.get(date_field) or {}).get("date-parts") or []
            if parts and parts[0]:
                year = parts[0][0]
                break
        comparisons.append({"field": "year", "expected": expected_year, "actual": year, "match": str(expected_year) == str(year)})
    expected_journal = expected.get("container-title") or expected.get("journal")
    actual_journals = actual.get("container-title") or []
    if expected_journal:
        actual_journal = actual_journals[0] if actual_journals else ""
        matched = _normalize_title(str(expected_journal)) == _normalize_title(str(actual_journal))
        comparisons.append({"field": "container-title", "expected": expected_journal, "actual": actual_journal, "match": matched})
    expected_authors = expected.get("authors")
    if expected_authors:
        actual_authors = actual.get("author") or []
        actual_names = [" ".join(filter(None, [item.get("given"), item.get("family")])).strip() for item in actual_authors]
        actual_norm = {_normalize_title(name) for name in actual_names}
        checks = []
        for name in expected_authors:
            norm = _normalize_title(str(name))
            checks.append({"expected": name, "match": norm in actual_norm or any(norm in item or item in norm for item in actual_norm)})
        comparisons.append({"field": "authors", "expected": expected_authors, "actual": actual_names, "match": bool(checks) and all(item["match"] for item in checks), "author_checks": checks})
    return comparisons


def _cache_file(cache_dir: Path, doi: str) -> Path:
    digest = hashlib.sha256(doi.casefold().encode("utf-8")).hexdigest()
    return cache_dir / f"crossref-{digest}.json"


def verify_doi(
    doi_value: str,
    *,
    expected: dict[str, Any] | None = None,
    cache_dir: Path | None = None,
    cache_ttl_seconds: int = 30 * 24 * 3600,
    timeout: int = 20,
    mailto: str | None = None,
) -> dict[str, Any]:
    """Fetch/cached-read a DOI's Crossref registration metadata and compare expectations."""
    doi = normalize_doi(doi_value)
    if timeout < 1 or timeout > 60:
        raise ValueError("timeout must be between 1 and 60 seconds")
    if cache_ttl_seconds < 0:
        raise ValueError("cache_ttl_seconds must not be negative")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cache_path: Path | None = _cache_file(cache_dir, doi) if cache_dir else None
    message: dict[str, Any] | None = None
    cache_hit = False
    retrieved_at = now
    if cache_path and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            age = time.time() - float(cached.get("cached_epoch", 0))
            if 0 <= age <= cache_ttl_seconds and cached.get("doi", "").casefold() == doi.casefold():
                message = cached["message"]
                retrieved_at = str(cached.get("cached_at") or now)
                cache_hit = True
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            message = None
    if message is None:
        encoded = urllib.parse.quote(doi, safe="")
        url = f"https://api.crossref.org/works/{encoded}"
        query = "?mailto=" + urllib.parse.quote(mailto, safe="") if mailto else ""
        request = urllib.request.Request(
            url + query,
            headers={"Accept": "application/json", "User-Agent": "Project-SKRIPSI/0.2.0 (bibliographic metadata verification)"},
            method="GET",
        )

        class _NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
                return None

        try:
            with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {
                    "schema_version": "1.0.0", "status": "DOI_NOT_FOUND_IN_CROSSREF",
                    "doi": doi, "source_url": url, "retrieved_at": now,
                    "cache_hit": False, "metadata_only": True,
                    "flags": ["No Crossref work record was found. Check DOI spelling or registration agency."],
                }
            raise RuntimeError(f"Crossref request failed with HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Crossref API unavailable: {exc}") from exc
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Crossref returned invalid JSON: {exc}") from exc
        if payload.get("status") != "ok" or not isinstance(payload.get("message"), dict):
            raise RuntimeError("Crossref response did not contain an OK message object")
        raw_message = payload["message"]
        # Persist only selected bibliographic fields; do not cache abstract/full-text-like content.
        allowed_fields = {
            "DOI", "title", "author", "container-title", "publisher", "type",
            "issued", "published", "published-print", "published-online", "URL",
            "license", "is-referenced-by-count",
        }
        message = {key: value for key, value in raw_message.items() if key in allowed_fields}
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            cache_path.write_text(json.dumps({"doi": doi, "cached_at": now, "cached_epoch": time.time(), "message": message}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            try:
                cache_path.chmod(0o600)
            except OSError:
                pass
    comparisons = _metadata_matches(expected or {}, message)
    mismatch = any(item.get("match") is False for item in comparisons)
    return {
        "schema_version": "1.0.0",
        "status": "METADATA_MISMATCH_REVIEW_REQUIRED" if mismatch else "METADATA_RETRIEVED_REVIEW_REQUIRED",
        "doi": doi,
        "source_url": f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}",
        "retrieved_at": retrieved_at,
        "checked_at": now,
        "cache_hit": cache_hit,
        "metadata_only": True,
        "metadata": {
            "title": (message.get("title") or [None])[0],
            "authors": [" ".join(filter(None, [item.get("given"), item.get("family")])).strip() for item in message.get("author", [])],
            "container_title": (message.get("container-title") or [None])[0],
            "publisher": message.get("publisher"),
            "type": message.get("type"),
            "issued": message.get("issued"),
            "published": message.get("published"),
            "published_print": message.get("published-print"),
            "published_online": message.get("published-online"),
            "URL": message.get("URL"),
            "license": message.get("license"),
            "is_referenced_by_count": message.get("is-referenced-by-count"),
        },
        "comparisons": comparisons,
        "flags": [
            "Crossref metadata is deposited by members and may be incomplete or incorrect.",
            "This lookup verifies bibliographic metadata only; it does not read the article or verify claim support, peer review quality, journal indexing, or legal access rights.",
        ] + (["One or more supplied expected metadata fields differ from the Crossref record."] if mismatch else []),
    }
