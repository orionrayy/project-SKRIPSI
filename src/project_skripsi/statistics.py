"""Project-scoped, deterministic statistical analysis primitives.

Version 0.5 deliberately executes descriptive summaries only. It never selects
an inferential test, imputes data, creates observations, or writes row-level data
into analysis outputs. Human methodology approval is required before execution.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import re
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from . import __version__
from .audit import append_audit_event
from .locking import FileLock

ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
ANALYSIS_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
SUPPORTED_METHOD = "DESCRIPTIVE_SUMMARY"
SUPPORTED_OPERATIONS = {"NUMERIC_SUMMARY", "FREQUENCY_TABLE"}
NUMERIC_TYPES = {"INTEGER", "NUMBER"}
MAX_DATASET_BYTES = 512 * 1024 * 1024
MAX_ROWS = 2_000_000
MAX_COLUMNS = 5_000
MAX_DISTINCT_TRACK = 5_001
MAX_DISTINCT_TRACK_TOTAL = 50_000
MAX_FREQUENCY_CATEGORIES = 500


class StatisticalEngineError(ValueError):
    """Invalid dataset, specification, or statistical execution request."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file_stable(path: Path) -> str:
    """Hash a file only when its filesystem identity/metadata is stable across the read."""
    try:
        before = path.stat()
        digest = sha256_file(path)
        after = path.stat()
    except OSError as exc:
        raise StatisticalEngineError(f"cannot hash pinned input {path}: {exc}") from exc
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    if identity_before != identity_after:
        raise StatisticalEngineError(f"input changed while its SHA-256 was being calculated: {path}")
    return digest


def _private_mode(path: Path, mode: int) -> None:
    if os.name != "nt":
        try:
            path.chmod(mode)
        except OSError:
            pass


def _safe_path(workspace: Path, supplied: str | Path, *, must_exist: bool = True) -> Path:
    """Resolve a workspace-relative path while refusing symlink components."""
    root = workspace.expanduser().resolve(strict=True)
    raw = Path(supplied).expanduser()
    candidate = raw if raw.is_absolute() else root / raw
    try:
        lexical = Path(os.path.abspath(candidate))
        relative = lexical.relative_to(root)
    except ValueError as exc:
        raise StatisticalEngineError("path must remain inside the private project workspace") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise StatisticalEngineError(f"symlinked workspace path is not permitted: {relative.as_posix()}")
    if must_exist:
        try:
            resolved = lexical.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise StatisticalEngineError(f"workspace file is missing or escaped: {relative.as_posix()}") from exc
        if not resolved.is_file():
            raise StatisticalEngineError(f"workspace path is not a regular file: {relative.as_posix()}")
        return resolved
    return lexical


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise StatisticalEngineError(f"refusing symlink output path: {path}")
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        _private_mode(Path(temp_name), 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
        os.link(temp_name, path)
        os.unlink(temp_name)
        _private_mode(path, 0o600)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StatisticalEngineError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StatisticalEngineError(f"JSON root must be an object: {path}")
    return value


def _is_number(value: str) -> float | None:
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def _is_integer_number(value: float) -> bool:
    return value.is_integer()


def profile_csv(path: Path, *, missing_tokens: list[str] | None = None, small_cell_suppression_threshold: int = 5) -> dict[str, Any]:
    """Read a CSV in streaming row batches and emit metadata/aggregate profile only."""
    if path.stat().st_size > MAX_DATASET_BYTES:
        raise StatisticalEngineError(f"CSV exceeds {MAX_DATASET_BYTES} byte safety limit")
    if isinstance(small_cell_suppression_threshold, bool) or not isinstance(small_cell_suppression_threshold, int) or not 2 <= small_cell_suppression_threshold <= 50:
        raise StatisticalEngineError("small_cell_suppression_threshold must be between 2 and 50")
    if missing_tokens is not None and (not isinstance(missing_tokens, list) or any(not isinstance(token, str) for token in missing_tokens)):
        raise StatisticalEngineError("missing_tokens must be an array of strings")
    missing = {token.strip().casefold() for token in (missing_tokens or [""])}
    if not missing:
        missing = {""}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            try:
                headers = next(reader)
            except StopIteration as exc:
                raise StatisticalEngineError("CSV is empty; a header row is required") from exc
            if not headers or any(not isinstance(header, str) or not header.strip() for header in headers):
                raise StatisticalEngineError("CSV headers must be non-empty strings")
            if len(set(headers)) != len(headers):
                raise StatisticalEngineError("CSV contains duplicate column names")
            if len(headers) > MAX_COLUMNS:
                raise StatisticalEngineError(f"CSV exceeds {MAX_COLUMNS} column safety limit")
            row_count = 0
            missing_counts = [0 for _ in headers]
            distinct_sets: list[set[str]] = [set() for _ in headers]
            distinct_counts = [0 for _ in headers]
            distinct_truncated = [False for _ in headers]
            distinct_tracked_total = 0
            type_flags: list[dict[str, bool]] = [
                {"boolean": True, "numeric": True, "integer": True, "seen": False}
                for _ in headers
            ]
            non_empty_counts = [0 for _ in headers]
            numeric_state = [{"n": 0, "mean": 0.0, "m2": 0.0, "min": None, "max": None} for _ in headers]
            for row_number, row in enumerate(reader, start=2):
                if len(row) != len(headers):
                    raise StatisticalEngineError(f"CSV row {row_number} has {len(row)} cells; expected {len(headers)}")
                row_count += 1
                if row_count > MAX_ROWS:
                    raise StatisticalEngineError(f"CSV exceeds {MAX_ROWS} data-row safety limit")
                for index, raw in enumerate(row):
                    value = raw.strip()
                    if value.casefold() in missing:
                        missing_counts[index] += 1
                        continue
                    non_empty_counts[index] += 1
                    if not distinct_truncated[index]:
                        bucket = distinct_sets[index]
                        if value not in bucket:
                            if len(bucket) >= MAX_DISTINCT_TRACK or distinct_tracked_total >= MAX_DISTINCT_TRACK_TOTAL:
                                distinct_truncated[index] = True
                                distinct_counts[index] += 1
                                distinct_tracked_total -= len(bucket)
                                bucket.clear()
                            else:
                                bucket.add(value)
                                distinct_counts[index] += 1
                                distinct_tracked_total += 1
                    flags = type_flags[index]
                    flags["seen"] = True
                    lowered = value.casefold()
                    if lowered not in {"true", "false", "yes", "no"}:
                        flags["boolean"] = False
                    number = _is_number(value)
                    if number is None:
                        flags["numeric"] = False
                        flags["integer"] = False
                    else:
                        if not _is_integer_number(number):
                            flags["integer"] = False
                        state = numeric_state[index]
                        state["n"] += 1
                        delta = number - state["mean"]
                        state["mean"] += delta / state["n"]
                        state["m2"] += delta * (number - state["mean"])
                        state["min"] = number if state["min"] is None else min(state["min"], number)
                        state["max"] = number if state["max"] is None else max(state["max"], number)
            columns: list[dict[str, Any]] = []
            for index, header in enumerate(headers):
                flags = type_flags[index]
                if not flags["seen"]:
                    inferred = "EMPTY"
                elif flags["boolean"]:
                    inferred = "BOOLEAN"
                elif flags["numeric"]:
                    inferred = "INTEGER" if flags["integer"] else "NUMBER"
                else:
                    inferred = "TEXT"
                distinct_count = distinct_counts[index]
                state = numeric_state[index]
                numeric_summary = None
                numeric_summary_suppressed = bool(inferred in NUMERIC_TYPES and 0 < state["n"] < small_cell_suppression_threshold)
                if inferred in NUMERIC_TYPES and state["n"] >= small_cell_suppression_threshold:
                    if not all(math.isfinite(float(state[key])) for key in ("mean", "m2", "min", "max")):
                        raise StatisticalEngineError(f"numeric overflow while profiling column {header!r}")
                    variance = state["m2"] / (state["n"] - 1) if state["n"] > 1 else None
                    numeric_summary = {
                        "n": state["n"],
                        "mean": state["mean"],
                        "sample_standard_deviation": math.sqrt(variance) if variance is not None else None,
                        "minimum": state["min"],
                        "maximum": state["max"],
                    }
                columns.append({
                    "variable_id": f"VAR_{index + 1:03d}",
                    "column_name": header,
                    "inferred_type": inferred,
                    "row_count": row_count,
                    "non_empty_count": non_empty_counts[index],
                    "missing_count": missing_counts[index],
                    "missing_rate": (missing_counts[index] / row_count) if row_count else 0.0,
                    "distinct_count_lower_bound": distinct_count,
                    "distinct_count_truncated": distinct_truncated[index],
                    "is_constant": (not distinct_truncated[index] and distinct_count <= 1 and non_empty_counts[index] > 0),
                    "numeric_summary": numeric_summary,
                    "numeric_summary_suppressed": numeric_summary_suppressed,
                })
            return {
                "format": "CSV",
                "encoding": "utf-8-sig",
                "delimiter": "comma",
                "row_count": row_count,
                "column_count": len(headers),
                "size_bytes": path.stat().st_size,
                "missing_value_tokens": sorted(missing),
                "numeric_summary_suppression_threshold": small_cell_suppression_threshold,
                "columns": columns,
                "profile_notice": "Profile contains schema and aggregate metadata only; raw rows and category labels are not persisted.",
            }
    except UnicodeDecodeError as exc:
        raise StatisticalEngineError("CSV must be UTF-8 or UTF-8 with BOM") from exc
    except csv.Error as exc:
        raise StatisticalEngineError(f"invalid CSV: {exc}") from exc


def register_dataset(
    workspace: Path,
    dataset_path: str | Path,
    *,
    artifact_id: str,
    origin: str,
    artifact_type: str = "RAW_DATA",
    privacy_classification: str = "CONFIDENTIAL",
    permission_status: str = "UNKNOWN",
    missing_tokens: list[str] | None = None,
) -> dict[str, Any]:
    """Register a workspace-contained CSV with provenance and content hash."""
    if not isinstance(artifact_id, str) or not ARTIFACT_ID_RE.fullmatch(artifact_id):
        raise StatisticalEngineError("artifact_id must be 3-64 safe ASCII letters, digits, dot, underscore or hyphen")
    if not isinstance(origin, str) or not origin.strip():
        raise StatisticalEngineError("origin is required and must identify the data's provenance")
    if not isinstance(artifact_type, str) or artifact_type not in {"RAW_DATA", "PROCESSED_DATA", "SECONDARY_DATASET"}:
        raise StatisticalEngineError("artifact_type must be RAW_DATA, PROCESSED_DATA or SECONDARY_DATASET")
    if not isinstance(privacy_classification, str) or privacy_classification not in {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"}:
        raise StatisticalEngineError("unsupported privacy_classification")
    if not isinstance(permission_status, str) or permission_status not in {"NOT_REQUIRED", "PENDING", "APPROVED", "DENIED", "UNKNOWN"}:
        raise StatisticalEngineError("unsupported permission_status")
    if missing_tokens is not None and (not isinstance(missing_tokens, list) or any(not isinstance(token, str) for token in missing_tokens)):
        raise StatisticalEngineError("missing_tokens must be an array of strings")

    root = workspace.expanduser().resolve(strict=True)
    source = _safe_path(root, dataset_path, must_exist=True)
    if source.suffix.casefold() != ".csv":
        raise StatisticalEngineError("v0.5 currently supports CSV datasets only")
    relative_path = source.relative_to(root).as_posix()
    if relative_path.split("/")[:2] not in (["data", "raw"], ["data", "processed"]):
        raise StatisticalEngineError("CSV datasets must be stored under data/raw/ or data/processed/ inside the workspace")
    digest_before = sha256_file_stable(source)
    profile = profile_csv(source, missing_tokens=missing_tokens)
    digest = sha256_file_stable(source)
    if digest != digest_before:
        raise StatisticalEngineError("dataset changed during registration; retry with a stable file")
    register_path = _safe_path(root, Path("data/registry") / f"{artifact_id}.json", must_exist=False)
    register_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    record = {
        "artifact_id": artifact_id,
        "project_id": _read_json(_safe_path(root, "project.json", must_exist=True)).get("project_id"),
        "artifact_type": artifact_type,
        "origin": origin.strip(),
        "collected_or_retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": digest,
        "privacy_classification": privacy_classification,
        "permission_status": permission_status,
        "consent_reference": None,
        "deidentification_status": "NOT_ASSESSED",
        "transformations": [],
        "limitations": [
            "CSV metadata profile is descriptive and does not establish measurement validity or representativeness.",
            "Column types are inferred from observed values; verify against the approved codebook.",
        ],
        "storage_path": relative_path,
        "file_profile": profile,
    }
    lock = root / "state" / "statistical-engine.lock"
    with FileLock(lock):
        if register_path.exists() or register_path.is_symlink():
            raise FileExistsError(f"dataset artifact already exists; use a new artifact_id: {artifact_id}")
        if sha256_file_stable(source) != digest:
            raise StatisticalEngineError("dataset changed before registry commit; retry with a stable file")
        _atomic_json(register_path, record)
        append_audit_event(
            root / "audit" / "events.jsonl", event_type="DATASET_REGISTERED", object_type="data_artifact",
            object_id=artifact_id, summary=f"Registered {artifact_type} CSV dataset; SHA-256 {digest[:12]}.",
            evidence_refs=[relative_path, register_path.relative_to(root).as_posix()],
            idempotency_key=f"dataset-register:{artifact_id}:{digest}",
        )
    return {"status": "REGISTERED", "artifact_id": artifact_id, "sha256": digest, "record_path": register_path.relative_to(root).as_posix(), "file_profile": profile}


def build_analysis_scaffold(workspace: Path) -> Path:
    root = workspace.expanduser().resolve(strict=True)
    manifest = _read_json(_safe_path(root, "project.json", must_exist=True))
    output = _safe_path(root, "analysis/design/analysis_specification.json", must_exist=False)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"analysis specification already exists: {output}")
    scaffold = {
        "schema_version": "1.0.0",
        "project_id": manifest.get("project_id"),
        "analysis_id": "ANALYSIS-001",
        "analysis_plan_id": None,
        "research_question_ids": [],
        "dataset_artifact_id": None,
        "method": None,
        "justification": None,
        "human_method_approval": "NOT_GRANTED",
        "variables": [],
        "missing_value_tokens": [""],
        "small_cell_suppression_threshold": 5,
        "assumption_review_notes": [],
    }
    _atomic_json(output, scaffold)
    return output


def validate_analysis_specification(workspace: Path, specification: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(specification, dict):
        return ["analysis specification must be a JSON object"]
    root = workspace.expanduser().resolve(strict=True)
    manifest = _read_json(_safe_path(root, "project.json", must_exist=True))
    project_id = manifest.get("project_id")
    if specification.get("schema_version") != "1.0.0":
        errors.append("schema_version must be 1.0.0")
    if specification.get("project_id") != project_id:
        errors.append("project_id does not match workspace manifest")
    analysis_id = specification.get("analysis_id")
    if not isinstance(analysis_id, str) or not ANALYSIS_ID_RE.fullmatch(analysis_id):
        errors.append("analysis_id must be a safe 3-64 character identifier")
    if specification.get("method") != SUPPORTED_METHOD:
        errors.append(f"method must be explicitly set to {SUPPORTED_METHOD}; inferential methods are not executable in v0.5")
    if not isinstance(specification.get("justification"), str) or len(specification["justification"].strip()) < 12:
        errors.append("justification must explain why this descriptive method fits the approved research plan")
    review_notes = specification.get("assumption_review_notes", [])
    if not isinstance(review_notes, list) or any(not isinstance(item, str) for item in review_notes):
        errors.append("assumption_review_notes must be an array of strings")
    method_approval = specification.get("human_method_approval")
    if not isinstance(method_approval, str) or method_approval not in {"NOT_GRANTED", "APPROVED", "REJECTED"}:
        errors.append("human_method_approval must be NOT_GRANTED, APPROVED or REJECTED")
    if specification.get("human_method_approval") != "APPROVED":
        errors.append("human methodology approval is required before analysis execution")
    approval_reference = specification.get("human_method_approval_reference")
    if not isinstance(approval_reference, str) or not approval_reference.strip():
        errors.append("human_method_approval_reference must identify an approved human decision record")
    question_ids = specification.get("research_question_ids")
    valid_question_ids = [item for item in question_ids if isinstance(item, str) and item] if isinstance(question_ids, list) else []
    if (
        not isinstance(question_ids, list)
        or not valid_question_ids
        or len(valid_question_ids) != len(question_ids)
        or len(set(valid_question_ids)) != len(valid_question_ids)
    ):
        errors.append("research_question_ids must be a non-empty unique array of non-empty strings")
    safe_question_ids = set(valid_question_ids)
    variables = specification.get("variables")
    if not isinstance(variables, list) or not variables:
        errors.append("variables must contain at least one explicit column-to-construct mapping")
        variables = []
    variable_ids: set[str] = set()
    mapped_columns: set[str] = set()
    for index, variable in enumerate(variables):
        label = f"variables[{index}]"
        if not isinstance(variable, dict):
            errors.append(f"{label} must be an object")
            continue
        variable_id = variable.get("variable_id")
        if not isinstance(variable_id, str) or not variable_id.strip() or variable_id in variable_ids:
            errors.append(f"{label}.variable_id must be non-empty and unique")
        else:
            variable_ids.add(variable_id)
        column_name = variable.get("column_name")
        if not isinstance(column_name, str) or not column_name.strip():
            errors.append(f"{label}.column_name is required")
        elif column_name in mapped_columns:
            errors.append(f"{label}.column_name must be unique within the analysis specification")
        else:
            mapped_columns.add(column_name)
        operation = variable.get("operation")
        if not isinstance(operation, str) or operation not in SUPPORTED_OPERATIONS:
            errors.append(f"{label}.operation must be NUMERIC_SUMMARY or FREQUENCY_TABLE")
        if "expose_category_labels" in variable and not isinstance(variable.get("expose_category_labels"), bool):
            errors.append(f"{label}.expose_category_labels must be boolean")
        if variable.get("construct_id") is not None and (not isinstance(variable.get("construct_id"), str) or not variable["construct_id"].strip()):
            errors.append(f"{label}.construct_id must be a non-empty string or null")
    token_values = specification.get("missing_value_tokens", [""])
    if not isinstance(token_values, list) or any(not isinstance(value, str) for value in token_values):
        errors.append("missing_value_tokens must be an array of strings")
    threshold = specification.get("small_cell_suppression_threshold", 5)
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 2 or threshold > 50:
        errors.append("small_cell_suppression_threshold must be an integer between 2 and 50")

    artifact_id = specification.get("dataset_artifact_id")
    if not isinstance(artifact_id, str) or not ARTIFACT_ID_RE.fullmatch(artifact_id):
        errors.append("dataset_artifact_id must reference a registered data artifact")
        return errors
    artifact_path = _safe_path(root, Path("data/registry") / f"{artifact_id}.json", must_exist=False)
    if not artifact_path.is_file() or artifact_path.is_symlink():
        errors.append(f"dataset artifact is not registered: {artifact_id}")
        return errors
    try:
        artifact = _read_json(artifact_path)
    except StatisticalEngineError as exc:
        errors.append(str(exc))
        return errors
    if artifact.get("project_id") != project_id:
        errors.append("dataset artifact project_id does not match workspace")
    if artifact.get("artifact_id") != artifact_id:
        errors.append("dataset artifact ID does not match registry filename")
    artifact_permission = artifact.get("permission_status")
    if not isinstance(artifact_permission, str) or artifact_permission not in {"APPROVED", "NOT_REQUIRED"}:
        errors.append("dataset permission_status must be APPROVED or NOT_REQUIRED before analysis")
    file_profile = artifact.get("file_profile")
    if not isinstance(file_profile, dict):
        errors.append("dataset file_profile must be an object")
        file_profile = {}
    if not isinstance(file_profile.get("row_count"), int) or isinstance(file_profile.get("row_count"), bool) or file_profile.get("row_count", 0) < 1:
        errors.append("dataset must contain at least one data row")
    if artifact.get("permission_status") == "DENIED":
        errors.append("dataset permission was denied")
    storage_path = artifact.get("storage_path")
    if not isinstance(storage_path, str):
        errors.append("dataset storage_path is missing")
        return errors
    try:
        dataset_path = _safe_path(root, storage_path, must_exist=True)
        if sha256_file(dataset_path) != artifact.get("sha256"):
            errors.append("dataset SHA-256 has changed since registration; register a new immutable artifact")
        current_profile = profile_csv(dataset_path, missing_tokens=token_values if isinstance(token_values, list) else [""])
        registered_columns = file_profile.get("columns", [])
        if not isinstance(registered_columns, list):
            errors.append("registered dataset file_profile.columns must be an array")
            registered_columns = []
        if [item.get("column_name") for item in current_profile["columns"]] != [item.get("column_name") for item in registered_columns if isinstance(item, dict)]:
            errors.append("dataset column profile differs from registered artifact")
        registered_missing = file_profile.get("missing_value_tokens", [""])
        if not isinstance(registered_missing, list) or any(not isinstance(token, str) for token in registered_missing):
            errors.append("registered dataset missing_value_tokens must be an array of strings")
        elif sorted(str(token).strip().casefold() for token in token_values if isinstance(token, str)) != sorted(token.strip().casefold() for token in registered_missing):
            errors.append("missing_value_tokens must exactly match the dataset registration profile")
        profile_map = {item.get("column_name"): item for item in current_profile["columns"]}
        for index, variable in enumerate(variables):
            if not isinstance(variable, dict):
                continue
            column_name = variable.get("column_name")
            if not isinstance(column_name, str) or not column_name:
                continue
            column = profile_map.get(column_name)
            if column is None:
                errors.append(f"variables[{index}] references unknown dataset column")
                continue
            operation = variable.get("operation")
            inferred = column.get("inferred_type")
            if operation == "NUMERIC_SUMMARY" and inferred not in NUMERIC_TYPES:
                errors.append(f"variables[{index}] NUMERIC_SUMMARY requires an INTEGER or NUMBER column")
            if operation == "FREQUENCY_TABLE" and inferred == "EMPTY":
                errors.append(f"variables[{index}] FREQUENCY_TABLE cannot run on an EMPTY column")
            privacy_classification = artifact.get("privacy_classification")
            if variable.get("expose_category_labels") is True and isinstance(privacy_classification, str) and privacy_classification in {"CONFIDENTIAL", "RESTRICTED"}:
                errors.append(f"variables[{index}] cannot expose category labels for CONFIDENTIAL/RESTRICTED data")
    except (OSError, StatisticalEngineError) as exc:
        errors.append(str(exc))

    alignment_path = root / "methodology" / "design" / "research_alignment.json"
    if not alignment_path.exists():
        errors.append("research_alignment.json is required to trace analysis to approved research questions")
        return errors
    try:
        alignment = _read_json(_safe_path(root, "methodology/design/research_alignment.json", must_exist=True))
    except StatisticalEngineError as exc:
        errors.append(str(exc))
        return errors
    if alignment.get("project_id") != project_id:
        errors.append("research alignment project_id does not match workspace")
    from .methodology import audit_research_alignment
    alignment_audit = audit_research_alignment(alignment)
    if alignment_audit.get("status") == "NEEDS_REVISION":
        errors.append("research alignment has blocking structural errors; run methodology-audit and resolve them before statistical execution")
    alignment_questions = alignment.get("research_questions", [])
    if not isinstance(alignment_questions, list):
        errors.append("research alignment research_questions must be an array")
        alignment_questions = []
    question_registry = {item.get("question_id") for item in alignment_questions if isinstance(item, dict) and isinstance(item.get("question_id"), str)}
    for question_id in valid_question_ids:
        if question_id not in question_registry:
            errors.append(f"research question ID not found in alignment: {question_id}")
    plan_id = specification.get("analysis_plan_id")
    raw_plans = alignment.get("analysis_plan", [])
    if not isinstance(raw_plans, list):
        errors.append("research alignment analysis_plan must be an array")
        raw_plans = []
    plans = [item for item in raw_plans if isinstance(item, dict) and item.get("analysis_id") == plan_id]
    if not isinstance(plan_id, str) or len(plans) != 1:
        errors.append("analysis_plan_id must uniquely reference an analysis plan in research_alignment.json")
    else:
        plan = plans[0]
        if plan.get("strategy") != "DESCRIPTIVE":
            errors.append("v0.5 execution is restricted to a methodology plan explicitly classified DESCRIPTIVE")
        plan_question_ids = plan.get("research_question_ids", [])
        if not isinstance(plan_question_ids, list) or any(not isinstance(item, str) for item in plan_question_ids):
            errors.append("linked analysis plan research_question_ids must be an array of strings")
            plan_question_ids = []
        if safe_question_ids - set(plan_question_ids):
            errors.append("analysis specification research questions exceed the linked methodology analysis plan")
        hypothesis_ids = plan.get("hypothesis_ids", [])
        if not isinstance(hypothesis_ids, list):
            errors.append("linked analysis plan hypothesis_ids must be an array")
            hypothesis_ids = []
        if hypothesis_ids:
            errors.append("descriptive summaries cannot be used as execution evidence for a hypothesis-linked inferential plan")
        raw_allowed_constructs = plan.get("construct_ids", [])
        if not isinstance(raw_allowed_constructs, list) or any(not isinstance(item, str) for item in raw_allowed_constructs):
            errors.append("linked analysis plan construct_ids must be an array of strings")
            raw_allowed_constructs = []
        allowed_constructs = set(raw_allowed_constructs)
        alignment_constructs = alignment.get("constructs", [])
        if not isinstance(alignment_constructs, list):
            errors.append("research alignment constructs must be an array")
            alignment_constructs = []
        construct_ids = {item.get("construct_id") for item in alignment_constructs if isinstance(item, dict) and isinstance(item.get("construct_id"), str)}
        for index, variable in enumerate(variables):
            if not isinstance(variable, dict) or not variable.get("construct_id"):
                errors.append(f"variables[{index}] must reference a methodology construct")
                continue
            construct_id = variable["construct_id"]
            if not isinstance(construct_id, str) or not construct_id.strip():
                errors.append(f"variables[{index}] construct_id must be a non-empty string")
                continue
            if construct_id not in construct_ids:
                errors.append(f"variables[{index}] construct_id is not in research alignment")
            if allowed_constructs and construct_id not in allowed_constructs:
                errors.append(f"variables[{index}] construct_id is outside linked analysis plan")
        if not isinstance(plan.get("selection_rationale"), str) or len(plan["selection_rationale"].strip()) < 12:
            errors.append("linked methodology analysis plan must contain a substantive selection_rationale")

    # Human approval is tied to a project decision, not a checkbox alone.
    decision_path = root / "decisions" / "decision_register.json"
    try:
        decision_register = _read_json(_safe_path(root, "decisions/decision_register.json", must_exist=True))
        decisions = decision_register.get("decisions", [])
        if not isinstance(decisions, list):
            errors.append("decision register decisions must be an array")
            decisions = []
        matching = [item for item in decisions if isinstance(item, dict) and item.get("decision_id") == approval_reference]
        if decision_register.get("project_id") != project_id:
            errors.append("decision register project_id does not match workspace")
        if len(matching) != 1:
            errors.append("human_method_approval_reference must uniquely match a decision register entry")
        else:
            decision = matching[0]
            scope = decision.get("scope", {})
            if not isinstance(scope, dict):
                errors.append("method decision scope must be an object")
                scope = {}
            if decision.get("decision_type") != "METHOD_SELECTION_APPROVAL" or decision.get("status") != "APPROVED":
                errors.append("referenced decision must be an APPROVED METHOD_SELECTION_APPROVAL")
            reviewer_role = decision.get("reviewer_role")
            if not isinstance(reviewer_role, str) or reviewer_role not in {"SUPERVISOR", "PRINCIPAL_INVESTIGATOR", "METHODOLOGY_REVIEWER", "AUTHORIZED_HUMAN_REVIEWER"}:
                errors.append("method decision must identify an authorized human reviewer role")
            if not isinstance(decision.get("rationale"), str) or len(decision["rationale"].strip()) < 12:
                errors.append("method decision rationale must be substantive")
            try:
                decision_at = decision.get("decided_at")
                if not isinstance(decision_at, str) or datetime.fromisoformat(decision_at.replace("Z", "+00:00")).tzinfo is None:
                    raise ValueError
                if datetime.fromisoformat(decision_at.replace("Z", "+00:00")) > datetime.now(timezone.utc):
                    errors.append("method decision decided_at cannot be in the future")
            except ValueError:
                errors.append("method decision decided_at must be an ISO-8601 timestamp with timezone")
            if scope.get("analysis_plan_id") != specification.get("analysis_plan_id") or scope.get("dataset_artifact_id") != artifact_id or scope.get("method") != SUPPORTED_METHOD:
                errors.append("human method decision scope must match analysis plan, dataset artifact and method")
    except StatisticalEngineError as exc:
        errors.append(str(exc))

    # T6 analysis execution is blocked until T0-T5 are accepted and T6 is scoped-authorized.
    try:
        from .validation import validate_phase_ledger
        ledger = _read_json(_safe_path(root, "state/phase_ledger.json", must_exist=True))
        ledger_errors = validate_phase_ledger(ledger, project_id)
        if ledger_errors:
            errors.append("phase ledger invalid: " + "; ".join(ledger_errors))
        else:
            phases = {item.get("phase_id"): item for item in ledger.get("phases", []) if isinstance(item, dict)}
            for phase_id in ("T0", "T1", "T2", "T3", "T4", "T5"):
                if phases.get(phase_id, {}).get("phase_conclusion") != "COMPLETE_AND_APPROVED":
                    errors.append(f"analysis execution requires {phase_id} COMPLETE_AND_APPROVED")
            phase6 = phases.get("T6", {})
            if phase6.get("authorization_status") not in {"AUTHORIZED_SCOPED", "APPROVED_SCOPED"} or phase6.get("execution_status") not in {"IN_PROGRESS", "COMPLETE"}:
                errors.append("analysis execution requires T6 IN_PROGRESS/COMPLETE with scoped authorization")
    except StatisticalEngineError as exc:
        errors.append(str(exc))

    return errors


def _compute_variable_results(
    workspace: Path,
    dataset: Path,
    specification: dict[str, Any],
    registered_profile: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    variable_specs = specification["variables"]
    required_columns = {item["column_name"] for item in variable_specs}
    index_map: dict[str, int] = {}
    outputs: dict[str, dict[str, Any]] = {}
    diagnostics: list[dict[str, str]] = []
    missing_tokens = {token.strip().casefold() for token in specification.get("missing_value_tokens", [""])}
    suppression = specification.get("small_cell_suppression_threshold", 5)

    with dataset.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        headers = next(reader)
        for item in variable_specs:
            index_map[item["column_name"]] = headers.index(item["column_name"])
            outputs[item["column_name"]] = {"spec": item, "valid_n": 0, "missing_n": 0, "counts": Counter(), "n": 0, "mean": 0.0, "m2": 0.0, "minimum": None, "maximum": None}
        for row_number, row in enumerate(reader, start=2):
            if len(row) != len(headers):
                raise StatisticalEngineError(f"dataset changed or malformed at CSV row {row_number}")
            for column_name in required_columns:
                value = row[index_map[column_name]].strip()
                state = outputs[column_name]
                if value.casefold() in missing_tokens:
                    state["missing_n"] += 1
                    continue
                state["valid_n"] += 1
                operation = state["spec"]["operation"]
                if operation == "NUMERIC_SUMMARY":
                    number = _is_number(value)
                    if number is None:
                        raise StatisticalEngineError(f"non-numeric value encountered in {column_name} after validation")
                    state["n"] += 1
                    delta = number - state["mean"]
                    state["mean"] += delta / state["n"]
                    state["m2"] += delta * (number - state["mean"])
                    state["minimum"] = number if state["minimum"] is None else min(state["minimum"], number)
                    state["maximum"] = number if state["maximum"] is None else max(state["maximum"], number)
                else:
                    state["counts"][value] += 1
                    if len(state["counts"]) > MAX_FREQUENCY_CATEGORIES:
                        raise StatisticalEngineError(f"{column_name} has more than {MAX_FREQUENCY_CATEGORIES} categories; frequency output refused")

    results: list[dict[str, Any]] = []
    for item in variable_specs:
        name = item["column_name"]
        state = outputs[name]
        profile_col = next(col for col in registered_profile["columns"] if col["column_name"] == name)
        missing_rate = (state["missing_n"] / (state["missing_n"] + state["valid_n"])) if (state["missing_n"] + state["valid_n"]) else 0.0
        if state["missing_n"]:
            code = "HIGH_MISSINGNESS_REVIEW" if missing_rate >= 0.05 else "MISSING_VALUES_PRESENT"
            severity = "WARNING"
            diagnostics.append({"code": code, "severity": severity, "variable_id": item["variable_id"], "message": f"{state['missing_n']} missing value(s), {missing_rate:.4f} of observed rows; no imputation was performed."})
        if profile_col.get("is_constant"):
            diagnostics.append({"code": "CONSTANT_VARIABLE", "severity": "WARNING", "variable_id": item["variable_id"], "message": "The observed column is constant; interpretation requires review."})
        if item["operation"] == "NUMERIC_SUMMARY":
            n = state["n"]
            if n and not all(math.isfinite(float(state[key])) for key in ("mean", "m2", "minimum", "maximum")):
                raise StatisticalEngineError(f"numeric overflow while analyzing column {name!r}")
            variance = state["m2"] / (n - 1) if n > 1 else None
            summary_suppressed = n < suppression
            results.append({
                "variable_id": item["variable_id"],
                "construct_id": item["construct_id"],
                "column_name": name,
                "operation": "NUMERIC_SUMMARY",
                "n": n,
                "missing_n": state["missing_n"],
                "mean": state["mean"] if n and not summary_suppressed else None,
                "sample_standard_deviation": math.sqrt(variance) if variance is not None and not summary_suppressed else None,
                "minimum": state["minimum"] if n and not summary_suppressed else None,
                "maximum": state["maximum"] if n and not summary_suppressed else None,
                "summary_suppressed": summary_suppressed,
                "small_cell_suppression_threshold": suppression,
            })
            if summary_suppressed and n:
                diagnostics.append({"code": "SMALL_SAMPLE_SUPPRESSION_APPLIED", "severity": "INFO", "variable_id": item["variable_id"], "message": f"Numeric summary values were suppressed because valid n is below {suppression}."})
            if n < 2:
                diagnostics.append({"code": "INSUFFICIENT_N_FOR_VARIANCE", "severity": "WARNING", "variable_id": item["variable_id"], "message": "Fewer than two valid observations; sample standard deviation is unavailable."})
            elif variance == 0:
                diagnostics.append({"code": "ZERO_VARIANCE", "severity": "WARNING", "variable_id": item["variable_id"], "message": "Observed sample variance is zero."})
        else:
            counts: Counter[str] = state["counts"]
            ordered_counts = sorted(counts.items(), key=lambda pair: pair[0])
            primary_suppressed = [(value, count) for value, count in ordered_counts if count < suppression]
            visible = [(value, count, order) for order, (value, count) in enumerate(ordered_counts, start=1) if count >= suppression]
            complementary_suppressed: list[tuple[str, int]] = []
            # Complementary suppression prevents a single hidden cell from being
            # exactly reconstructed by subtracting all visible cells from valid N.
            if len(primary_suppressed) == 1 and visible:
                secondary = min(visible, key=lambda entry: (entry[1], entry[0]))
                visible.remove(secondary)
                complementary_suppressed.append((secondary[0], secondary[1]))
            all_suppressed = primary_suppressed + complementary_suppressed
            rows = [{
                "category": value if item.get("expose_category_labels", False) else f"CATEGORY_{order:03d}",
                "count": count,
                "percent_of_valid": count / state["valid_n"] if state["valid_n"] else 0.0,
            } for value, count, order in visible]
            rows.sort(key=lambda entry: (-entry["count"], entry["category"]))
            valid_n_output = None if len(primary_suppressed) == 1 and not visible else state["valid_n"]
            results.append({
                "variable_id": item["variable_id"],
                "construct_id": item["construct_id"],
                "column_name": name,
                "operation": "FREQUENCY_TABLE",
                "valid_n": valid_n_output,
                "missing_n": state["missing_n"],
                "categories": rows,
                "suppressed_category_count": len(all_suppressed),
                "suppressed_observation_count": None if all_suppressed else 0,
                "complementary_suppression_applied": bool(complementary_suppressed),
                "small_cell_suppression_threshold": suppression,
                "category_labels_exposed": bool(item.get("expose_category_labels", False)),
            })
            if all_suppressed:
                diagnostics.append({"code": "SMALL_CELL_SUPPRESSION_APPLIED", "severity": "INFO", "variable_id": item["variable_id"], "message": f"{len(primary_suppressed)} primary and {len(complementary_suppressed)} complementary category level(s) were suppressed below the effective threshold {suppression}."})

    return results, diagnostics


def _build_result_payload(
    specification: dict[str, Any],
    *,
    artifact_id: str,
    dataset_hash: str,
    spec_hash: str,
    alignment_hash: str,
    variable_results: list[dict[str, Any]],
    diagnostics: list[dict[str, str]],
) -> dict[str, Any]:
    """Build the version-1 result document identically for initial and replay runs."""
    return {
        "schema_version": "1.0.0",
        "project_id": specification["project_id"],
        "analysis_id": specification["analysis_id"],
        "analysis_method": SUPPORTED_METHOD,
        "dataset_artifact_id": artifact_id,
        "dataset_sha256": dataset_hash,
        "human_method_approval_reference": specification["human_method_approval_reference"],
        "analysis_specification_sha256": spec_hash,
        "methodology_alignment_sha256": alignment_hash,
        "deterministic": True,
        "variable_results": variable_results,
        "assumption_diagnostics": diagnostics,
        "operator_assumption_review_notes": specification.get("assumption_review_notes", []),
        "interpretation_limits": [
            "This release executes descriptive summaries only; no null-hypothesis tests, confidence intervals or effect-size inference are produced.",
            "Descriptive summaries do not establish causality, representativeness, measurement validity or generalizability.",
            "Normality, independence, homoscedasticity, missingness mechanism and inferential assumptions are not tested by this release.",
            "No imputation, weighting, recoding, outlier deletion or row-level export was performed.",
            "CSV numeric parsing uses dot decimal notation; locale-specific numeric strings require a documented transformation before registration.",
            "Frequency outputs suppress categories below the configured threshold; category labels are pseudonymized unless explicitly allowed by the specification.",
        ],
    }


def _validate_pinned_run_inputs(root: Path, run_record: dict[str, Any]) -> list[str]:
    """Check all current input files against a run record before verify/recovery/replay.

    project_manifest_path/hash are optional for v0.5.1 compatibility. All other
    source hashes are required by the analysis-run schema.
    """
    fields = [
        ("dataset_artifact_path", "dataset_artifact_record_sha256"),
        ("dataset_path", "dataset_sha256"),
        ("analysis_specification_path", "analysis_specification_sha256"),
        ("methodology_alignment_path", "methodology_alignment_sha256"),
        ("decision_register_path", "decision_register_sha256"),
        ("phase_ledger_path", "phase_ledger_sha256"),
    ]
    if run_record.get("project_manifest_path") or run_record.get("project_manifest_sha256"):
        fields.append(("project_manifest_path", "project_manifest_sha256"))
    errors: list[str] = []
    for path_field, hash_field in fields:
        relative = run_record.get(path_field)
        expected = run_record.get(hash_field)
        if not isinstance(relative, str) or not isinstance(expected, str):
            errors.append(f"{path_field}/{hash_field} is missing")
            continue
        try:
            source = _safe_path(root, relative, must_exist=True)
            actual = sha256_file_stable(source)
            if actual != expected:
                errors.append(f"{path_field} SHA-256 differs from the pinned run input")
        except (OSError, StatisticalEngineError) as exc:
            errors.append(f"{path_field}: {exc}")
    if not errors:
        try:
            project = _read_json(_safe_path(root, "project.json", must_exist=True))
            if project.get("project_id") != run_record.get("project_id"):
                errors.append("current project identity does not match the run record")
            artifact_path = _safe_path(root, run_record["dataset_artifact_path"], must_exist=True)
            artifact = _read_json(artifact_path)
            if artifact.get("storage_path") != run_record.get("dataset_path"):
                errors.append("dataset registry storage_path differs from the pinned run record")
            if artifact.get("sha256") != run_record.get("dataset_sha256"):
                errors.append("dataset registry content hash differs from the pinned run record")
        except (KeyError, OSError, StatisticalEngineError) as exc:
            errors.append(f"pinned project/dataset metadata: {exc}")
    return errors


def _run_reproducibility_contract() -> dict[str, Any]:
    return {
        "contract_version": "1.0.0",
        "hash_algorithm": "SHA-256",
        "input_hashing": "stable-stat-before-and-after-read",
        "result_serialization": "UTF-8 JSON; sort_keys=true; ensure_ascii=false; indent=2; LF final newline; allow_nan=false",
        "csv_reader": "Python csv.reader; utf-8-sig; comma delimiter; strict row width",
        "numeric_model": "IEEE-754 binary64; finite values only; Welford one-pass sample variance",
        "reexecution_claim": "same-engine deterministic replay; not independent reviewer approval",
    }


def run_descriptive_analysis(workspace: Path, specification_path: str | Path, *, run_id: str | None = None) -> dict[str, Any]:
    """Execute explicitly approved, descriptive-only analysis and persist provenance."""
    root = workspace.expanduser().resolve(strict=True)
    spec_path = _safe_path(root, specification_path, must_exist=True)
    specification = _read_json(spec_path)
    errors = validate_analysis_specification(root, specification)
    if errors:
        raise StatisticalEngineError("analysis specification is not executable: " + "; ".join(errors))

    artifact_id = specification["dataset_artifact_id"]
    artifact_path = _safe_path(root, Path("data/registry") / f"{artifact_id}.json", must_exist=True)
    artifact = _read_json(artifact_path)
    dataset = _safe_path(root, artifact["storage_path"], must_exist=True)
    project_manifest_path = _safe_path(root, "project.json", must_exist=True)
    project_manifest_hash = sha256_file_stable(project_manifest_path)
    spec_hash = sha256_file_stable(spec_path)
    alignment_path = _safe_path(root, "methodology/design/research_alignment.json", must_exist=True)
    alignment_hash = sha256_file_stable(alignment_path)
    decision_path = _safe_path(root, "decisions/decision_register.json", must_exist=True)
    phase_ledger_path = _safe_path(root, "state/phase_ledger.json", must_exist=True)
    decision_hash = sha256_file_stable(decision_path)
    phase_ledger_hash = sha256_file_stable(phase_ledger_path)
    artifact_registry_hash = sha256_file_stable(artifact_path)
    dataset_hash_before = sha256_file_stable(dataset)
    if dataset_hash_before != artifact.get("sha256"):
        raise StatisticalEngineError("dataset changed after registration; refusing analysis")
    refreshed_errors = validate_analysis_specification(root, specification)
    if refreshed_errors:
        raise StatisticalEngineError("analysis gates changed before execution: " + "; ".join(refreshed_errors))
    if any((sha256_file_stable(project_manifest_path) != project_manifest_hash,
            sha256_file_stable(spec_path) != spec_hash, sha256_file_stable(alignment_path) != alignment_hash,
            sha256_file_stable(artifact_path) != artifact_registry_hash, sha256_file_stable(decision_path) != decision_hash,
            sha256_file_stable(phase_ledger_path) != phase_ledger_hash, sha256_file_stable(dataset) != dataset_hash_before)):
        raise StatisticalEngineError("an input changed while the execution gate was being verified")

    variable_results, diagnostics = _compute_variable_results(root, dataset, specification, artifact["file_profile"])
    dataset_hash_after = sha256_file_stable(dataset)
    if dataset_hash_after != dataset_hash_before:
        raise StatisticalEngineError("dataset changed during analysis; refusing to persist results")
    if sha256_file_stable(spec_path) != spec_hash:
        raise StatisticalEngineError("analysis specification changed during analysis; refusing to persist results")
    if sha256_file_stable(alignment_path) != alignment_hash:
        raise StatisticalEngineError("methodology alignment changed during analysis; refusing to persist results")
    if sha256_file_stable(artifact_path) != artifact_registry_hash:
        raise StatisticalEngineError("dataset artifact registry changed during analysis; refusing to persist results")
    if (sha256_file_stable(decision_path) != decision_hash or sha256_file_stable(phase_ledger_path) != phase_ledger_hash
            or sha256_file_stable(project_manifest_path) != project_manifest_hash):
        raise StatisticalEngineError("human approval or lifecycle authorization changed during analysis; refusing to persist results")
    result_payload = _build_result_payload(
        specification, artifact_id=artifact_id, dataset_hash=dataset_hash_before,
        spec_hash=spec_hash, alignment_hash=alignment_hash,
        variable_results=variable_results, diagnostics=diagnostics,
    )
    result_bytes = json.dumps(result_payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n"
    result_hash = sha256_bytes(result_bytes)

    if run_id is None:
        run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    if not ANALYSIS_ID_RE.fullmatch(run_id):
        raise StatisticalEngineError("run_id must be a safe 3-64 character identifier")
    output_dir_rel = PurePosixPath("analysis/outputs") / run_id
    output_dir = _safe_path(root, Path(*output_dir_rel.parts), must_exist=False)
    run_record = {
        "analysis_run_id": run_id,
        "project_id": specification["project_id"],
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "analysis_method": SUPPORTED_METHOD,
        "software": {
            "name": "Project-SKRIPSI Statistical Engine", "version": __version__,
            "python_version": platform.python_version(), "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "input_artifact_hashes": [dataset_hash_before, spec_hash, alignment_hash, artifact_registry_hash, decision_hash, phase_ledger_hash, project_manifest_hash],
        "dataset_artifact_record_sha256": artifact_registry_hash,
        "decision_register_path": decision_path.relative_to(root).as_posix(),
        "decision_register_sha256": decision_hash,
        "phase_ledger_path": phase_ledger_path.relative_to(root).as_posix(),
        "phase_ledger_sha256": phase_ledger_hash,
        "script_or_command": f"project-skripsi analysis-run <workspace> {spec_path.relative_to(root).as_posix()}",
        "parameters": {"analysis_id": specification["analysis_id"], "dataset_artifact_id": artifact_id, "variable_count": len(variable_results), "method": SUPPORTED_METHOD},
        "outputs": [(output_dir_rel / "results.json").as_posix()],
        "assumption_diagnostics": [item["code"] for item in diagnostics],
        "review_status": "NOT_REVIEWED",
        "limitations": result_payload["interpretation_limits"],
        "analysis_specification_path": spec_path.relative_to(root).as_posix(),
        "analysis_specification_sha256": spec_hash,
        "dataset_artifact_path": artifact_path.relative_to(root).as_posix(),
        "dataset_path": dataset.relative_to(root).as_posix(),
        "dataset_sha256": dataset_hash_before,
        "project_manifest_path": project_manifest_path.relative_to(root).as_posix(),
        "project_manifest_sha256": project_manifest_hash,
        "reproducibility_contract": _run_reproducibility_contract(),
        "methodology_alignment_path": alignment_path.relative_to(root).as_posix(),
        "methodology_alignment_sha256": alignment_hash,
        "result_sha256": result_hash,
        "human_method_approval": specification["human_method_approval"],
        "human_method_approval_reference": specification["human_method_approval_reference"],
    }
    lock = root / "state" / "statistical-engine.lock"
    transaction_dir = _safe_path(root, "analysis/transactions", must_exist=False)
    transaction_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    _private_mode(transaction_dir, 0o700)
    transaction_path = _safe_path(root, transaction_dir / f"{run_id}.json", must_exist=False)
    transaction = {
        "schema_version": "1.0.0", "transaction_id": run_id,
        "transaction_state": "PREPARED", "analysis_run_id": run_id,
        "result_sha256": result_hash, "result_payload": result_payload,
        "run_record": run_record,
    }
    transaction["transaction_sha256"] = sha256_bytes(canonical_json_bytes(transaction))
    with FileLock(lock):
        if output_dir.exists() or output_dir.is_symlink() or transaction_path.exists() or transaction_path.is_symlink():
            raise FileExistsError(f"analysis run output or transaction already exists: {run_id}")
        input_errors = _validate_pinned_run_inputs(root, run_record)
        if input_errors:
            raise StatisticalEngineError("inputs changed before transaction commit: " + "; ".join(input_errors))
        _atomic_json(transaction_path, transaction)
        output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
        _private_mode(output_dir, 0o700)
        try:
            _atomic_json(output_dir / "results.json", result_payload)
            if sha256_file_stable(output_dir / "results.json") != result_hash:
                # Atomic JSON writer uses the same indent/Unicode/newline policy. Guard serializer drift.
                actual_hash = sha256_file_stable(output_dir / "results.json")
                raise StatisticalEngineError(f"result serialization checksum mismatch: {actual_hash}")
            _atomic_json(output_dir / "run.json", run_record)
            run_record_hash = sha256_file_stable(output_dir / "run.json")
            input_errors = _validate_pinned_run_inputs(root, run_record)
            if input_errors:
                raise StatisticalEngineError("pinned inputs changed before audit commit: " + "; ".join(input_errors))
            append_audit_event(
                root / "audit" / "events.jsonl", event_type="STATISTICAL_ANALYSIS_RUN_CREATED",
                object_type="analysis_run", object_id=run_id,
                summary=f"Created descriptive analysis run; result SHA-256 {result_hash}; run record SHA-256 {run_record_hash}.",
                evidence_refs=[(output_dir_rel / "results.json").as_posix(), (output_dir_rel / "run.json").as_posix()],
                idempotency_key=f"analysis-run:{run_id}:{result_hash}",
            )
            transaction_path.unlink()
        except BaseException:
            # Preserve any partial run directory as evidence; do not silently delete operator-visible files.
            raise
    return {"status": "CREATED", "analysis_run_id": run_id, "result_sha256": result_hash, "result_path": (output_dir_rel / "results.json").as_posix(), "run_record_path": (output_dir_rel / "run.json").as_posix(), "diagnostic_count": len(diagnostics)}



def recover_analysis_transactions(workspace: Path) -> dict[str, Any]:
    """Idempotently complete prepared descriptive-run transactions after interruption."""
    root = workspace.expanduser().resolve(strict=True)
    tx_dir = _safe_path(root, "analysis/transactions", must_exist=False)
    if not tx_dir.exists():
        return {"status": "PASS", "recovered": [], "pending": 0}
    if tx_dir.is_symlink() or not tx_dir.is_dir():
        raise StatisticalEngineError("analysis transaction path is not a safe directory")
    recovered: list[str] = []
    pending = 0
    for tx_path in sorted(tx_dir.glob("*.json")):
        if tx_path.is_symlink() or not tx_path.is_file():
            raise StatisticalEngineError(f"unsafe transaction entry: {tx_path.name}")
        with FileLock(root / "state" / "statistical-engine.lock"):
            tx = _read_json(tx_path)
            supplied_hash = tx.pop("transaction_sha256", None)
            expected_hash = sha256_bytes(canonical_json_bytes(tx))
            if supplied_hash != expected_hash:
                raise StatisticalEngineError(f"transaction checksum mismatch: {tx_path.name}")
            run_id = tx.get("analysis_run_id")
            if (not isinstance(run_id, str) or not ANALYSIS_ID_RE.fullmatch(run_id)
                    or tx_path.stem != run_id or tx.get("transaction_id") != run_id
                    or tx.get("transaction_state") != "PREPARED"):
                raise StatisticalEngineError(f"transaction identity/state mismatch: {tx_path.name}")
            result_payload = tx.get("result_payload")
            run_record = tx.get("run_record")
            if not isinstance(result_payload, dict) or not isinstance(run_record, dict):
                raise StatisticalEngineError(f"transaction payload malformed: {tx_path.name}")
            if run_record.get("analysis_run_id") != run_id or run_record.get("project_id") != result_payload.get("project_id"):
                raise StatisticalEngineError(f"transaction run-record identity mismatch: {tx_path.name}")
            from .quality import validate_analysis_run
            run_record_errors = validate_analysis_run(run_record)
            if run_record_errors:
                raise StatisticalEngineError(f"transaction run record is invalid: {'; '.join(run_record_errors)}")
            result_bytes = json.dumps(result_payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n"
            result_hash = sha256_bytes(result_bytes)
            if result_hash != tx.get("result_sha256") or run_record.get("result_sha256") != result_hash:
                raise StatisticalEngineError(f"transaction result hash mismatch: {tx_path.name}")
            if result_payload.get("dataset_sha256") != run_record.get("dataset_sha256"):
                raise StatisticalEngineError(f"transaction dataset identity mismatch: {tx_path.name}")
            input_errors = _validate_pinned_run_inputs(root, run_record)
            if input_errors:
                raise StatisticalEngineError(
                    f"recovery refused because pinned source inputs changed or are unavailable ({run_id}): "
                    + "; ".join(input_errors)
                )
            out_rel = Path("analysis/outputs") / run_id
            out_dir = _safe_path(root, out_rel, must_exist=False)
            if out_dir.is_symlink() or (out_dir.exists() and not out_dir.is_dir()):
                raise StatisticalEngineError(f"unsafe or conflicting analysis output directory: {run_id}")
            out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            _private_mode(out_dir, 0o700)
            result_path = _safe_path(root, out_rel / "results.json", must_exist=False)
            run_path = _safe_path(root, out_rel / "run.json", must_exist=False)
            if result_path.exists():
                if sha256_file_stable(result_path) != result_hash:
                    raise StatisticalEngineError(f"existing partial result conflicts with transaction: {run_id}")
            else:
                _atomic_json(result_path, result_payload)
            if run_path.exists():
                if sha256_file_stable(run_path) != sha256_bytes(json.dumps(run_record, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n"):
                    raise StatisticalEngineError(f"existing run record conflicts with transaction: {run_id}")
            else:
                _atomic_json(run_path, run_record)
            run_hash = sha256_file_stable(run_path)
            input_errors_after_write = _validate_pinned_run_inputs(root, run_record)
            if input_errors_after_write:
                raise StatisticalEngineError(
                    f"recovery paused because pinned source inputs changed during restoration ({run_id}): "
                    + "; ".join(input_errors_after_write)
                )
            append_audit_event(
                root / "audit" / "events.jsonl", event_type="STATISTICAL_ANALYSIS_RUN_CREATED",
                object_type="analysis_run", object_id=run_id,
                summary=f"Created descriptive analysis run; result SHA-256 {result_hash}; run record SHA-256 {run_hash}.",
                evidence_refs=[(out_rel / "results.json").as_posix(), (out_rel / "run.json").as_posix()],
                idempotency_key=f"analysis-run:{run_id}:{result_hash}",
            )
            final_input_errors = _validate_pinned_run_inputs(root, run_record)
            if final_input_errors:
                raise StatisticalEngineError(
                    f"recovery retained the journal because pinned inputs changed before transaction retirement ({run_id}): "
                    + "; ".join(final_input_errors)
                )
            tx_path.unlink()
            recovered.append(run_id)
    return {"status": "PASS", "recovered": recovered, "pending": pending}

def verify_analysis_run(workspace: Path, run_id: str) -> dict[str, Any]:
    root = workspace.expanduser().resolve(strict=True)
    if not ANALYSIS_ID_RE.fullmatch(run_id):
        raise StatisticalEngineError("run_id must be a safe identifier")
    run_path = _safe_path(root, Path("analysis/outputs") / run_id / "run.json", must_exist=True)
    result_path = _safe_path(root, Path("analysis/outputs") / run_id / "results.json", must_exist=True)
    record = _read_json(run_path)
    from .quality import validate_analysis_run
    errors: list[str] = validate_analysis_run(record)
    if record.get("analysis_run_id") != run_id:
        errors.append("analysis_run_id does not match run directory")
    try:
        if sha256_file_stable(result_path) != record.get("result_sha256"):
            errors.append("result SHA-256 mismatch")
    except StatisticalEngineError as exc:
        errors.append(str(exc))
    errors.extend(_validate_pinned_run_inputs(root, record))
    expected_result_rel = (PurePosixPath("analysis/outputs") / run_id / "results.json").as_posix()
    if record.get("outputs") != [expected_result_rel]:
        errors.append("run record output path does not match the run directory")
    path_fields = (
        ("analysis_specification_path", "analysis_specification_sha256"),
        ("dataset_artifact_path", None),
        ("dataset_path", "dataset_sha256"),
        ("methodology_alignment_path", "methodology_alignment_sha256"),
        ("decision_register_path", "decision_register_sha256"),
        ("phase_ledger_path", "phase_ledger_sha256"),
    )
    for path_field, hash_field in path_fields:
        value = record.get(path_field)
        if not isinstance(value, str):
            errors.append(f"{path_field} is missing")
            continue
        try:
            path = _safe_path(root, value, must_exist=True)
            if hash_field and sha256_file_stable(path) != record.get(hash_field):
                errors.append(f"{path_field} content hash mismatch")
        except (OSError, StatisticalEngineError) as exc:
            errors.append(f"{path_field}: {exc}")
    artifact_path = record.get("dataset_artifact_path")
    dataset_path = record.get("dataset_path")
    if isinstance(artifact_path, str):
        try:
            artifact_record_file = _safe_path(root, artifact_path, must_exist=True)
            if sha256_file_stable(artifact_record_file) != record.get("dataset_artifact_record_sha256"):
                errors.append("dataset artifact registry record SHA-256 mismatch")
        except (OSError, StatisticalEngineError) as exc:
            errors.append(f"dataset artifact registry record: {exc}")
    if isinstance(artifact_path, str) and isinstance(dataset_path, str):
        try:
            artifact = _read_json(_safe_path(root, artifact_path, must_exist=True))
            if artifact.get("storage_path") != dataset_path:
                errors.append("dataset artifact storage_path no longer matches run record")
            if artifact.get("sha256") != record.get("dataset_sha256"):
                errors.append("dataset artifact SHA-256 no longer matches run record")
        except (OSError, StatisticalEngineError) as exc:
            errors.append(f"dataset artifact validation: {exc}")
    from .audit import read_audit_events
    ok, reason, events = read_audit_events(root / "audit" / "events.jsonl")
    matching_events = [event for event in events if event.get("event_type") == "STATISTICAL_ANALYSIS_RUN_CREATED" and event.get("object_id") == run_id]
    if not ok:
        errors.append(f"audit log invalid: {reason}")
    elif len(matching_events) != 1:
        errors.append("exactly one matching statistical analysis run event is required in the audit chain")
    else:
        event_summary = matching_events[0].get("summary", "")
        if not isinstance(event_summary, str):
            event_summary = ""
        run_hash = sha256_file_stable(run_path)
        if f"run record SHA-256 {run_hash}" not in event_summary:
            errors.append("run record SHA-256 is not pinned by its audit event")
        if f"result SHA-256 {record.get('result_sha256')}" not in event_summary:
            errors.append("result SHA-256 is not pinned by its audit event")
    spec_rel = record.get("analysis_specification_path")
    if isinstance(spec_rel, str):
        try:
            spec_doc = _read_json(_safe_path(root, spec_rel, must_exist=True))
            spec_errors = validate_analysis_specification(root, spec_doc)
            if spec_errors:
                errors.append("current analysis specification/approval is no longer valid: " + "; ".join(spec_errors))
            if spec_doc.get("human_method_approval_reference") != record.get("human_method_approval_reference"):
                errors.append("run record approval reference does not match current analysis specification")
            expected_inputs = [
                record.get("dataset_sha256"), record.get("analysis_specification_sha256"),
                record.get("methodology_alignment_sha256"), record.get("dataset_artifact_record_sha256"),
                record.get("decision_register_sha256"), record.get("phase_ledger_sha256"),
            ]
            if record.get("project_manifest_sha256"):
                expected_inputs.append(record.get("project_manifest_sha256"))
            if record.get("input_artifact_hashes") != expected_inputs:
                errors.append("input_artifact_hashes do not match the explicit run-record hash fields")
        except (OSError, StatisticalEngineError) as exc:
            errors.append(f"current analysis specification: {exc}")
    return {"status": "PASS" if not errors else "FAIL", "analysis_run_id": run_id, "errors": errors, "result_sha256": record.get("result_sha256"), "audit_chain": reason}


def reproduce_analysis_run(workspace: Path, run_id: str) -> dict[str, Any]:
    """Recompute a prior descriptive run without writing outputs or audit events.

    This is same-engine computational replay. It is deliberately not labelled
    independent review or human acceptance.
    """
    root = workspace.expanduser().resolve(strict=True)
    verification = verify_analysis_run(root, run_id)
    if verification["status"] != "PASS":
        return {
            "status": "BLOCKED_INPUT_OR_ARTIFACT_INTEGRITY",
            "analysis_run_id": run_id,
            "errors": verification["errors"],
            "writes_performed": False,
            "human_review_status_changed": False,
        }
    run_path = _safe_path(root, Path("analysis/outputs") / run_id / "run.json", must_exist=True)
    result_path = _safe_path(root, Path("analysis/outputs") / run_id / "results.json", must_exist=True)
    run_record_hash_before = sha256_file_stable(run_path)
    run_record = _read_json(run_path)
    specification_path = _safe_path(root, run_record["analysis_specification_path"], must_exist=True)
    dataset_path = _safe_path(root, run_record["dataset_path"], must_exist=True)
    artifact_path = _safe_path(root, run_record["dataset_artifact_path"], must_exist=True)
    alignment_path = _safe_path(root, run_record["methodology_alignment_path"], must_exist=True)
    specification = _read_json(specification_path)
    artifact = _read_json(artifact_path)

    pinned_before = {
        field: sha256_file_stable(_safe_path(root, run_record[path_field], must_exist=True))
        for field, path_field in (
            ("dataset_sha256", "dataset_path"),
            ("analysis_specification_sha256", "analysis_specification_path"),
            ("methodology_alignment_sha256", "methodology_alignment_path"),
            ("dataset_artifact_record_sha256", "dataset_artifact_path"),
            ("decision_register_sha256", "decision_register_path"),
            ("phase_ledger_sha256", "phase_ledger_path"),
        )
    }
    if run_record.get("project_manifest_path"):
        pinned_before["project_manifest_sha256"] = sha256_file_stable(
            _safe_path(root, run_record["project_manifest_path"], must_exist=True)
        )
    errors = validate_analysis_specification(root, specification)
    if errors:
        return {"status": "BLOCKED_CURRENT_APPROVAL_OR_SPECIFICATION", "analysis_run_id": run_id,
                "errors": errors, "writes_performed": False, "human_review_status_changed": False}
    variable_results, diagnostics = _compute_variable_results(root, dataset_path, specification, artifact["file_profile"])
    pinned_after = {
        field: sha256_file_stable(_safe_path(root, run_record[path_field], must_exist=True))
        for field, path_field in (
            ("dataset_sha256", "dataset_path"),
            ("analysis_specification_sha256", "analysis_specification_path"),
            ("methodology_alignment_sha256", "methodology_alignment_path"),
            ("dataset_artifact_record_sha256", "dataset_artifact_path"),
            ("decision_register_sha256", "decision_register_path"),
            ("phase_ledger_sha256", "phase_ledger_path"),
        )
    }
    if run_record.get("project_manifest_path"):
        pinned_after["project_manifest_sha256"] = sha256_file_stable(
            _safe_path(root, run_record["project_manifest_path"], must_exist=True)
        )
    if pinned_before != pinned_after:
        return {"status": "BLOCKED_INPUT_CHANGED_DURING_REPRODUCTION", "analysis_run_id": run_id,
                "errors": ["one or more pinned inputs changed while reproducing the run"],
                "writes_performed": False, "human_review_status_changed": False}
    recomputed = _build_result_payload(
        specification,
        artifact_id=specification["dataset_artifact_id"],
        dataset_hash=pinned_after["dataset_sha256"],
        spec_hash=pinned_after["analysis_specification_sha256"],
        alignment_hash=pinned_after["methodology_alignment_sha256"],
        variable_results=variable_results,
        diagnostics=diagnostics,
    )
    recomputed_bytes = json.dumps(recomputed, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode("utf-8") + b"\n"
    recomputed_hash = sha256_bytes(recomputed_bytes)
    stored_hash = sha256_file_stable(result_path)
    if sha256_file_stable(run_path) != run_record_hash_before:
        return {"status": "BLOCKED_RUN_RECORD_CHANGED_DURING_REPRODUCTION", "analysis_run_id": run_id,
                "errors": ["run record changed while computational replay was in progress"],
                "writes_performed": False, "human_review_status_changed": False}
    final_verification = verify_analysis_run(root, run_id)
    if final_verification["status"] != "PASS":
        return {"status": "BLOCKED_INTEGRITY_CHANGED_DURING_REPRODUCTION", "analysis_run_id": run_id,
                "errors": final_verification["errors"], "writes_performed": False,
                "human_review_status_changed": False}
    same = recomputed_hash == stored_hash == run_record.get("result_sha256")
    recorded_version = run_record.get("software", {}).get("version") if isinstance(run_record.get("software"), dict) else None
    return {
        "status": "REPRODUCED" if same else "DIVERGENCE",
        "analysis_run_id": run_id,
        "stored_result_sha256": stored_hash,
        "reproduced_result_sha256": recomputed_hash,
        "hash_match": same,
        "recorded_engine_version": recorded_version,
        "current_engine_version": __version__,
        "engine_version_match": recorded_version == __version__,
        "reproduction_scope": "SAME_VERSION_REEXECUTION" if recorded_version == __version__ else "CROSS_VERSION_COMPATIBILITY_CHECK",
        "independent_reviewer_confirmation": "NOT_PERFORMED",
        "human_review_status_changed": False,
        "writes_performed": False,
        "audit_events_written": False,
    }


def summarize_analysis_diagnostics(workspace: Path, run_id: str) -> dict[str, Any]:
    """Return a read-only severity/code summary of diagnostics attached to a verified run."""
    root = workspace.expanduser().resolve(strict=True)
    verification = verify_analysis_run(root, run_id)
    if verification["status"] != "PASS":
        return {"status": "BLOCKED_INTEGRITY_FAILURE", "analysis_run_id": run_id,
                "errors": verification["errors"], "writes_performed": False}
    results_path = _safe_path(root, Path("analysis/outputs") / run_id / "results.json", must_exist=True)
    results = _read_json(results_path)
    diagnostics = results.get("assumption_diagnostics")
    if not isinstance(diagnostics, list):
        raise StatisticalEngineError("analysis results assumption_diagnostics must be an array")
    counts = {"INFO": 0, "WARNING": 0, "ERROR": 0}
    codes: list[str] = []
    for item in diagnostics:
        if not isinstance(item, dict) or item.get("severity") not in counts or not isinstance(item.get("code"), str):
            raise StatisticalEngineError("analysis result contains a malformed diagnostic record")
        counts[item["severity"]] += 1
        codes.append(item["code"])
    return {
        "status": "PASS",
        "analysis_run_id": run_id,
        "diagnostic_count": len(diagnostics),
        "severity_counts": counts,
        "diagnostic_codes": codes,
        "diagnostics": diagnostics,
        "scope_notice": "These are descriptive data-quality and execution-scope diagnostics. Normality, independence, homoscedasticity, missingness mechanism, measurement validity and inferential assumptions are not tested by this release.",
        "writes_performed": False,
        "audit_events_written": False,
    }
