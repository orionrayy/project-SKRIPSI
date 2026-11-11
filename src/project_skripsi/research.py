"""Project-scoped scholarly search orchestration and provenance persistence."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import append_audit_event, read_audit_events
from .integrations.openalex import OpenAlexClient, _private_write
from .locking import FileLock
from .quality import validate_source_register
from .validation import validate_workspace


def _safe_timestamp(value: str) -> str:
    return re.sub(r"[^0-9TZ-]", "-", value)


def _workspace_path(project_dir: Path, relative: str) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"workspace path escaped project boundary: {relative}")
    current = project_dir
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"refusing symlinked workspace path: {relative}")
    candidate = current.resolve()
    try:
        candidate.relative_to(project_dir)
    except ValueError as exc:
        raise ValueError(f"workspace path escaped project boundary: {relative}") from exc
    return candidate


def _safe_csv_cell(value: Any) -> str:
    rendered = str(value if value is not None else "")
    probe = rendered.lstrip(" \t\r\n")
    if probe.startswith(("=", "+", "-", "@")):
        return "'" + rendered
    return rendered


def _existing_doi_keys(records: list[dict[str, Any]]) -> set[str]:
    return {
        str(record.get("doi")).strip().casefold()
        for record in records
        if isinstance(record, dict) and isinstance(record.get("doi"), str) and record["doi"].strip()
    }


def _merge_source_records(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge by stable source ID and DOI without replacing human-edited records."""
    merged = list(existing)
    ids = {str(item.get("source_id")) for item in existing if isinstance(item, dict)}
    dois = _existing_doi_keys(existing)
    for source in incoming:
        source_id = str(source.get("source_id") or "")
        doi = source.get("doi")
        if source_id in ids or (isinstance(doi, str) and doi.casefold() in dois):
            continue
        merged.append(source)
        ids.add(source_id)
        if isinstance(doi, str) and doi:
            dois.add(doi.casefold())
    return merged


def _journal_payload(transaction: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical payload covered by a journal checksum."""
    return {
        "schema_version": transaction.get("schema_version"),
        "project_id": transaction.get("project_id"),
        "created_at": transaction.get("created_at"),
        "snapshot": transaction.get("snapshot"),
        "new_sources": transaction.get("new_sources"),
    }


def _journal_checksum(transaction: dict[str, Any]) -> str:
    canonical = json.dumps(
        _journal_payload(transaction), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _read_research_transaction(project_dir: Path, transaction_path: Path) -> dict[str, Any]:
    """Read and validate a prepared transaction without mutating its targets."""
    if transaction_path.is_symlink() or not transaction_path.is_file():
        raise ValueError(f"refusing non-regular recovery journal: {transaction_path.name}")
    try:
        transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read research recovery journal {transaction_path.name}: {exc}") from exc
    if not isinstance(transaction, dict) or transaction.get("schema_version") not in {"1.0.0", "1.1.0"}:
        raise ValueError(f"unsupported research recovery journal: {transaction_path.name}")

    manifest_path = _workspace_path(project_dir, "project.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read workspace manifest during recovery: {exc}") from exc
    project_id = manifest.get("project_id") if isinstance(manifest, dict) else None
    if not isinstance(project_id, str) or transaction.get("project_id") != project_id:
        raise ValueError("research recovery journal belongs to another project")

    snapshot = transaction.get("snapshot")
    incoming = transaction.get("new_sources")
    if not isinstance(snapshot, dict) or snapshot.get("project_id") != project_id or not isinstance(incoming, list):
        raise ValueError("research recovery journal has malformed snapshot or source records")
    snapshot_id = snapshot.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not re.fullmatch(r"OPENALEX-[A-Fa-f0-9]{12}-[0-9TZ-]+", snapshot_id):
        raise ValueError("research recovery journal has an invalid snapshot ID")
    if transaction_path.name != f"{snapshot_id}.json":
        raise ValueError("research recovery journal filename does not match its snapshot ID")
    items = snapshot.get("items")
    if not isinstance(items, list) or any(not isinstance(item, dict) or not isinstance(item.get("source"), dict) for item in items):
        raise ValueError("research recovery journal snapshot items are malformed")
    if any(not isinstance(source, dict) for source in incoming):
        raise ValueError("research recovery journal contains a non-object source record")

    if transaction.get("schema_version") == "1.1.0":
        supplied = transaction.get("payload_sha256")
        if not isinstance(supplied, str) or not re.fullmatch(r"[a-f0-9]{64}", supplied):
            raise ValueError("research recovery journal checksum is missing or malformed")
        if supplied != _journal_checksum(transaction):
            raise ValueError("research recovery journal checksum mismatch; refusing recovery")
        snapshot_sources = [item["source"] for item in items]
        if snapshot_sources != incoming:
            raise ValueError("research recovery journal source records do not match snapshot items")

    incoming_errors = validate_source_register(incoming)
    if incoming_errors:
        raise ValueError("research recovery journal source records failed validation: " + "; ".join(incoming_errors))
    return transaction


def _apply_research_transaction(project_dir: Path, transaction_path: Path) -> dict[str, Any]:
    """Idempotently apply snapshot -> registry -> audit, then retire the journal."""
    transaction = _read_research_transaction(project_dir, transaction_path)
    manifest = json.loads(_workspace_path(project_dir, "project.json").read_text(encoding="utf-8"))
    project_id = manifest["project_id"]
    snapshot = transaction["snapshot"]
    incoming = transaction["new_sources"]
    snapshot_id = snapshot["snapshot_id"]

    # Refuse symlink escapes before any destination file is touched.
    raw_snapshot_dir = project_dir / "sources" / "snapshots"
    if raw_snapshot_dir.is_symlink():
        raise ValueError("refusing symlinked snapshot directory during transaction recovery")
    snapshot_dir = _workspace_path(project_dir, "sources/snapshots")
    snapshot_path = snapshot_dir / f"{snapshot_id}.json"
    if snapshot_path.is_symlink():
        raise ValueError("refusing symlinked snapshot destination during transaction recovery")
    if snapshot_path.exists():
        try:
            existing_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"existing snapshot is unreadable; refusing overwrite: {exc}") from exc
        if existing_snapshot != snapshot:
            raise FileExistsError(f"existing retrieval snapshot differs from recovery journal: {snapshot_path}")
    else:
        _private_write(snapshot_path, snapshot)

    register_path = _workspace_path(project_dir, "sources/registry/source_register.json")
    try:
        register = json.loads(register_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read project source register during recovery: {exc}") from exc
    if register.get("project_id") != project_id or not isinstance(register.get("sources"), list):
        raise ValueError("source register is malformed or belongs to another project")
    if not isinstance(register.get("claim_evidence_links"), list):
        raise ValueError("source register claim_evidence_links array is malformed")
    next_sources = _merge_source_records(register["sources"], incoming)
    register_errors = validate_source_register(next_sources)
    if register_errors:
        raise ValueError("recovered source records failed validation: " + "; ".join(register_errors))
    if next_sources != register["sources"]:
        register["sources"] = next_sources
        _private_write(register_path, register)

    audit_path = _workspace_path(project_dir, "audit/events.jsonl")
    result_count = len(snapshot.get("items", []))
    append_audit_event(
        audit_path,
        event_type="research.source_search.persisted",
        object_type="retrieval_snapshot",
        object_id=snapshot_id,
        summary=(
            f"OpenAlex search snapshot persisted; {result_count} result(s), "
            f"{len(incoming)} new source candidate(s)."
        ),
        evidence_refs=[str(snapshot_path.relative_to(project_dir)), "sources/registry/source_register.json"],
        idempotency_key=f"research-search:{snapshot_id}",
    )

    transaction_path.unlink()
    if os.name != "nt":
        try:
            directory_fd = os.open(transaction_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    return {"snapshot_id": snapshot_id, "snapshot": str(snapshot_path), "source_count": len(next_sources)}

def _recover_research_transactions_locked(project_dir: Path) -> dict[str, Any]:
    raw_transaction_dir = project_dir / "state" / "research-transactions"
    if raw_transaction_dir.is_symlink():
        raise ValueError("refusing symlinked research transaction directory")
    transaction_dir = _workspace_path(project_dir, "state/research-transactions")
    transaction_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        try:
            transaction_dir.chmod(0o700)
        except OSError:
            pass
    recovered: list[dict[str, Any]] = []
    for transaction_path in sorted(transaction_dir.glob("OPENALEX-*.json")):
        recovered.append(_apply_research_transaction(project_dir, transaction_path))
    return {"status": "CLEAN" if not recovered else "RECOVERED", "recovered_count": len(recovered), "transactions": recovered}


def recover_research_transactions(workspace: Path) -> dict[str, Any]:
    """Recover prepared OpenAlex persistence transactions within one workspace."""
    project_dir = workspace.expanduser().resolve()
    errors, manifest, _ledger = validate_workspace(project_dir)
    if errors or not manifest:
        raise ValueError("workspace validation failed: " + "; ".join(errors))
    lock_path = _workspace_path(project_dir, "state/.research.lock")
    with FileLock(lock_path):
        return _recover_research_transactions_locked(project_dir)


def research_integrity_check(workspace: Path) -> dict[str, Any]:
    """Read-only consistency check for snapshots, source register, journals and audit.

    This command never repairs files. It reports pending valid journals as
    RECOVERY_REQUIRED so an operator can explicitly invoke recover-research.
    """
    project_dir = workspace.expanduser().resolve()
    errors, manifest, _ledger = validate_workspace(project_dir)
    if errors or not manifest:
        raise ValueError("workspace validation failed: " + "; ".join(errors))

    lock_path = _workspace_path(project_dir, "state/.research.lock")
    with FileLock(lock_path):
        issues: list[str] = []
        raw_journal_dir = project_dir / "state" / "research-transactions"
        if raw_journal_dir.is_symlink():
            raise ValueError("refusing symlinked research transaction directory")
        journal_dir = _workspace_path(project_dir, "state/research-transactions")
        if journal_dir.exists() and not journal_dir.is_dir():
            raise ValueError("research transaction path exists but is not a directory")
        pending_ids: set[str] = set()
        if journal_dir.is_dir():
            for journal_path in sorted(journal_dir.glob("OPENALEX-*.json")):
                try:
                    transaction = _read_research_transaction(project_dir, journal_path)
                    pending_ids.add(transaction["snapshot"]["snapshot_id"])
                except (OSError, ValueError) as exc:
                    issues.append(f"journal {journal_path.name}: {exc}")

        register_path = _workspace_path(project_dir, "sources/registry/source_register.json")
        try:
            register = json.loads(register_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read project source register: {exc}") from exc
        if register.get("project_id") != manifest["project_id"] or not isinstance(register.get("sources"), list):
            raise ValueError("source register is malformed or belongs to another project")
        register_errors = validate_source_register(register["sources"])
        if register_errors:
            issues.extend(f"source register: {error}" for error in register_errors)
        source_ids = {
            str(source.get("source_id"))
            for source in register["sources"]
            if isinstance(source, dict) and source.get("source_id")
        }

        raw_snapshot_dir = project_dir / "sources" / "snapshots"
        if raw_snapshot_dir.is_symlink():
            raise ValueError("refusing symlinked snapshot directory")
        snapshot_dir = _workspace_path(project_dir, "sources/snapshots")
        snapshot_ids: set[str] = set()
        for snapshot_path in sorted(snapshot_dir.glob("OPENALEX-*.json")):
            if snapshot_path.is_symlink() or not snapshot_path.is_file():
                issues.append(f"snapshot {snapshot_path.name}: non-regular file")
                continue
            try:
                snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                issues.append(f"snapshot {snapshot_path.name}: unreadable ({exc})")
                continue
            if not isinstance(snapshot, dict):
                issues.append(f"snapshot {snapshot_path.name}: root is not an object")
                continue
            snapshot_id = snapshot.get("snapshot_id")
            if (
                snapshot.get("project_id") != manifest["project_id"]
                or snapshot_id != snapshot_path.stem
                or not isinstance(snapshot_id, str)
                or not re.fullmatch(r"OPENALEX-[A-Fa-f0-9]{12}-[0-9TZ-]+", snapshot_id)
            ):
                issues.append(f"snapshot {snapshot_path.name}: project or snapshot identity mismatch")
                continue
            if not isinstance(snapshot.get("items"), list):
                issues.append(f"snapshot {snapshot_path.name}: items is not an array")
                continue
            snapshot_ids.add(snapshot_id)
            for index, item in enumerate(snapshot["items"]):
                if not isinstance(item, dict) or not isinstance(item.get("source"), dict):
                    issues.append(f"snapshot {snapshot_path.name}: malformed item {index}")
                    continue
                source_id = item["source"].get("source_id")
                if snapshot_id not in pending_ids and (not isinstance(source_id, str) or source_id not in source_ids):
                    issues.append(f"snapshot {snapshot_path.name}: source {source_id!r} missing from source register")

        audit_path = _workspace_path(project_dir, "audit/events.jsonl")
        audit_ok, audit_reason, audit_events = read_audit_events(audit_path)
        audit_keys: set[str] = set()
        audit_snapshot_ids: set[str] = set()
        if not audit_ok:
            issues.append(f"audit log: {audit_reason}")
        else:
            for event in audit_events:
                key = event.get("idempotency_key")
                if isinstance(key, str) and key.startswith("research-search:"):
                    if key in audit_keys:
                        issues.append(f"audit log: duplicate idempotency key: {key}")
                    audit_keys.add(key)
                    audit_snapshot_ids.add(key.removeprefix("research-search:"))

        for snapshot_id in snapshot_ids - pending_ids:
            key = f"research-search:{snapshot_id}"
            if key not in audit_keys:
                issues.append(f"snapshot {snapshot_id}: committed snapshot has no matching audit event")
        orphan_audit_snapshots = audit_snapshot_ids - snapshot_ids - pending_ids
        for snapshot_id in sorted(orphan_audit_snapshots):
            issues.append(f"audit event references missing snapshot {snapshot_id}")
        missing_snapshots = pending_ids - snapshot_ids
        # A journal may precede the first snapshot write; recovery is expected to create it.
        status = "FAIL" if issues else ("RECOVERY_REQUIRED" if pending_ids else "PASS")
        return {
            "status": status,
            "project_id": manifest["project_id"],
            "snapshot_count": len(snapshot_ids),
            "source_count": len(register["sources"]),
            "pending_transaction_count": len(pending_ids),
            "pending_snapshot_not_yet_written_count": len(missing_snapshots),
            "audit_chain": audit_reason,
            "issues": issues,
            "notice": "Read-only for research content; kernel lock sidecars may be created. No repair or bibliographic/content truth certification is performed.",
        }


def search_project_literature(
    workspace: Path,
    query: str,
    *,
    per_page: int = 10,
    include_abstracts: bool = False,
    mailto: str | None = None,
    api_key: str | None = None,
    use_cache: bool = True,
    client: OpenAlexClient | None = None,
) -> dict[str, Any]:
    """Search OpenAlex and persist through a recoverable, project-scoped journal.

    Network retrieval happens outside the project mutation lock. The critical
    section reloads current state and uses a write-ahead journal, so crashes
    between snapshot, source-register and audit writes can be resumed safely.
    """
    project_dir = workspace.expanduser().resolve()
    errors, manifest, _ledger = validate_workspace(project_dir)
    if errors:
        raise ValueError("workspace validation failed: " + "; ".join(errors))
    if not manifest or not isinstance(manifest.get("project_id"), str):
        raise ValueError("workspace manifest is unavailable")

    raw_snapshot_dir = project_dir / "sources" / "snapshots"
    if raw_snapshot_dir.is_symlink():
        raise ValueError(f"workspace path escaped project boundary: {raw_snapshot_dir}")
    register_path = _workspace_path(project_dir, "sources/registry/source_register.json")
    cache_dir = _workspace_path(project_dir, "sources/cache/openalex")
    snapshot_dir = _workspace_path(project_dir, "sources/snapshots")
    if not snapshot_dir.is_dir():
        raise ValueError("project snapshot directory is unavailable")
    active_client = client or OpenAlexClient(cache_dir=cache_dir, api_key=api_key, mailto=mailto)

    # Recover before spending another provider request, then fetch without
    # holding the workspace lock so concurrent reads do not block on network I/O.
    lock_path = _workspace_path(project_dir, "state/.research.lock")
    with FileLock(lock_path):
        _recover_research_transactions_locked(project_dir)
    result = active_client.search(query, per_page=per_page, include_abstracts=include_abstracts, use_cache=use_cache)

    created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    query_digest = hashlib.sha256(" ".join(query.split()).casefold().encode("utf-8")).hexdigest()[:12]
    snapshot_id = f"OPENALEX-{query_digest}-{_safe_timestamp(created_at)}"
    snapshot = {
        "schema_version": "1.0.0",
        "snapshot_id": snapshot_id,
        "project_id": manifest["project_id"],
        "created_at": created_at,
        "retrieved_at": result["retrieved_at"],
        "provider": result["provider"],
        "query": result["query"],
        "request_url": result["request_url"],
        "cache_hit": result["cache_hit"],
        "total_count": result["total_count"],
        "per_page": result["per_page"],
        "result_count": result["result_count"],
        "abstracts_requested": result["abstracts_requested"],
        "items": result["items"],
        "flags": result["flags"],
    }

    with FileLock(lock_path):
        _recover_research_transactions_locked(project_dir)
        try:
            register = json.loads(register_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read project source register: {exc}") from exc
        if register.get("project_id") != manifest["project_id"]:
            raise ValueError("source register project_id does not match workspace manifest")
        records = register.get("sources")
        if not isinstance(records, list) or not isinstance(register.get("claim_evidence_links"), list):
            raise ValueError("source register arrays are malformed")
        next_records = _merge_source_records(records, [item["source"] for item in result["items"]])
        register_errors = validate_source_register(next_records)
        if register_errors:
            raise ValueError("normalized source records failed validation: " + "; ".join(register_errors))
        existing_ids = {str(item.get("source_id")) for item in records if isinstance(item, dict)}
        new_count = sum(1 for item in next_records if str(item.get("source_id")) not in existing_ids)
        candidate_count = len(result["items"])
        raw_journal_dir = project_dir / "state" / "research-transactions"
        if raw_journal_dir.is_symlink():
            raise ValueError("refusing symlinked research transaction directory")
        journal_dir = _workspace_path(project_dir, "state/research-transactions")
        journal_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            journal_dir.chmod(0o700)
        transaction_path = journal_dir / f"{snapshot_id}.json"
        if transaction_path.exists() or transaction_path.is_symlink():
            raise FileExistsError(f"refusing to overwrite existing research transaction: {transaction_path}")
        transaction = {
            "schema_version": "1.1.0",
            "project_id": manifest["project_id"],
            "created_at": created_at,
            "snapshot": snapshot,
            "new_sources": [item["source"] for item in result["items"]],
        }
        transaction["payload_sha256"] = _journal_checksum(transaction)
        _private_write(transaction_path, transaction)
        _apply_research_transaction(project_dir, transaction_path)

    duplicate_count = candidate_count - new_count
    return {
        "status": "PERSISTED",
        "project_id": manifest["project_id"],
        "provider": "openalex",
        "query": result["query"],
        "result_count": result["result_count"],
        "total_count": result["total_count"],
        "new_sources": new_count,
        "duplicates_skipped": duplicate_count,
        "abstracts_requested": include_abstracts,
        "snapshot": str(snapshot_dir / f"{snapshot_id}.json"),
        "register": str(register_path),
        "cache_hit": result["cache_hit"],
        "notice": "Search metadata is not quality appraisal or evidence verification; human screening is required.",
    }


LITERATURE_MATRIX_COLUMNS = (
    "source_id", "source_type", "title", "authors", "year", "doi", "url",
    "retrieval_date", "access_status", "rights_status", "exact_locator", "abstract",
    "screening_decision", "screening_reason", "research_question_ids",
    "theoretical_framework", "method_summary", "population_or_context",
    "variables_or_themes", "findings_summary", "limitations", "relevance",
    "research_gap_notes", "review_status", "reviewer_role",
)
MANUAL_MATRIX_COLUMNS = (
    "screening_decision", "screening_reason", "research_question_ids",
    "theoretical_framework", "method_summary", "population_or_context",
    "variables_or_themes", "findings_summary", "limitations", "relevance",
    "research_gap_notes", "review_status", "reviewer_role",
)


def build_literature_matrix(workspace: Path, *, output_path: Path | None = None) -> dict[str, Any]:
    project_dir = workspace.expanduser().resolve()
    errors, manifest, _ledger = validate_workspace(project_dir)
    if errors or not manifest:
        raise ValueError("workspace validation failed: " + "; ".join(errors))
    lock_path = _workspace_path(project_dir, "state/.research.lock")
    with FileLock(lock_path):
        _recover_research_transactions_locked(project_dir)
        return _build_literature_matrix_locked(project_dir, output_path=output_path)


def _build_literature_matrix_locked(workspace: Path, *, output_path: Path | None = None) -> dict[str, Any]:
    """Create/update a project matrix while preserving all recognized human annotations."""
    import csv
    import io

    project_dir = workspace.expanduser().resolve()
    errors, manifest, _ledger = validate_workspace(project_dir)
    if errors:
        raise ValueError("workspace validation failed: " + "; ".join(errors))
    project_id = manifest["project_id"]
    register_path = _workspace_path(project_dir, "sources/registry/source_register.json")
    try:
        register = json.loads(register_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read project source register: {exc}") from exc
    if register.get("project_id") != project_id or not isinstance(register.get("sources"), list):
        raise ValueError("source register is malformed or belongs to another project")
    source_records = register["sources"]
    register_errors = validate_source_register(source_records)
    if register_errors:
        raise ValueError("source register validation failed: " + "; ".join(register_errors))

    matrix_dir = _workspace_path(project_dir, "literature/matrix")
    default_output = matrix_dir / "literature_matrix.csv"
    output = output_path.expanduser().resolve() if output_path else default_output
    if output.parent != matrix_dir or output.suffix.casefold() != ".csv":
        raise ValueError("literature matrix output must be a .csv file directly inside this project's literature/matrix directory")

    existing_annotations: dict[str, dict[str, str]] = {}
    if output.exists():
        try:
            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames or "source_id" not in reader.fieldnames:
                    raise ValueError("existing literature matrix has no source_id column; refusing to overwrite")
                for row in reader:
                    source_id = (row.get("source_id") or "").strip()
                    if not source_id:
                        raise ValueError("existing literature matrix contains a row without source_id")
                    if source_id in existing_annotations:
                        raise ValueError(f"existing literature matrix contains duplicate source_id: {source_id}")
                    existing_annotations[source_id] = {
                        column: str(row.get(column) or "") for column in MANUAL_MATRIX_COLUMNS
                    }
        except (OSError, UnicodeError, csv.Error) as exc:
            raise ValueError(f"cannot read existing literature matrix safely: {exc}") from exc

    latest_abstracts: dict[str, tuple[str, str]] = {}
    snapshot_dir = _workspace_path(project_dir, "sources/snapshots")
    for snapshot_path in sorted(snapshot_dir.glob("OPENALEX-*.json")):
        try:
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if snapshot.get("project_id") != project_id or not isinstance(snapshot.get("items"), list):
            continue
        retrieved_at = str(snapshot.get("retrieved_at") or snapshot.get("created_at") or "")
        for item in snapshot["items"]:
            if not isinstance(item, dict) or not isinstance(item.get("source"), dict):
                continue
            source_id = item["source"].get("source_id")
            abstract = item.get("abstract")
            if isinstance(source_id, str) and isinstance(abstract, str) and abstract.strip():
                previous = latest_abstracts.get(source_id)
                if previous is None or retrieved_at > previous[0]:
                    latest_abstracts[source_id] = (retrieved_at, abstract)

    rows: list[dict[str, str]] = []
    known_ids: set[str] = set()
    for source in source_records:
        source_id = source["source_id"]
        known_ids.add(source_id)
        annotations = existing_annotations.get(source_id, {})
        abstract = latest_abstracts.get(source_id, ("", ""))[1]
        row = {
            "source_id": source_id,
            "source_type": str(source.get("source_type") or ""),
            "title": str(source.get("title") or ""),
            "authors": "; ".join(source.get("authors") or []),
            "year": "" if source.get("year") is None else str(source.get("year")),
            "doi": str(source.get("doi") or ""),
            "url": str(source.get("url") or ""),
            "retrieval_date": str(source.get("retrieval_date") or ""),
            "access_status": str(source.get("access_status") or ""),
            "rights_status": str(source.get("rights_status") or "UNKNOWN"),
            "exact_locator": str(source.get("exact_locator") or ""),
            "abstract": abstract,
        }
        for column in MANUAL_MATRIX_COLUMNS:
            row[column] = annotations.get(column, "")
        if not row["review_status"]:
            row["review_status"] = "UNREVIEWED"
        rows.append(row)

    # Preserve rows that may have been manually added before their source was registered.
    for source_id, annotations in existing_annotations.items():
        if source_id not in known_ids:
            row = {column: "" for column in LITERATURE_MATRIX_COLUMNS}
            row["source_id"] = source_id
            row.update(annotations)
            rows.append(row)

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=LITERATURE_MATRIX_COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    safe_rows = [
        {key: _safe_csv_cell(value) for key, value in row.items()}
        for row in rows
    ]
    writer.writerows(safe_rows)
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _write_private_text(output, buffer.getvalue())

    counts: dict[str, int] = {}
    for source in source_records:
        status = str(source.get("access_status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    review_statuses: dict[str, int] = {}
    for row in rows:
        status = row.get("review_status") or "UNREVIEWED"
        review_statuses[status] = review_statuses.get(status, 0) + 1
    coverage = {
        "schema_version": "1.0.0",
        "project_id": project_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_count": len(source_records),
        "matrix_row_count": len(rows),
        "abstract_snapshot_count": len(latest_abstracts),
        "doi_count": sum(1 for source in source_records if source.get("doi")),
        "access_status_counts": counts,
        "review_status_counts": review_statuses,
        "claim": "Coverage metrics only; not source-quality, relevance, or systematic-review completeness assessment.",
    }
    coverage_path = output.with_name("literature_coverage.json")
    _private_write(coverage_path, coverage)
    return {
        "status": "GENERATED",
        "project_id": project_id,
        "source_count": len(source_records),
        "matrix_row_count": len(rows),
        "abstract_snapshot_count": len(latest_abstracts),
        "matrix": str(output),
        "coverage": str(coverage_path),
        "human_annotations_preserved": len(existing_annotations),
        "notice": "Methods, samples, findings, limitations, relevance and research gaps remain human-entered; no synthesis was fabricated.",
    }


def _write_private_text(path: Path, content: str) -> None:
    """Atomic private text write for CSV artifacts."""
    import os
    import uuid

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        try:
            path.parent.chmod(0o700)
        except OSError:
            pass
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            temporary.chmod(0o600)
        os.replace(temporary, path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
