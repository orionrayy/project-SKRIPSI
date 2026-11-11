"""Evidence, methodology and analysis-record checks.

These checks establish traceability/readiness, not the truth of a study or the
correctness of a statistical conclusion. Human academic review remains separate.
"""

from __future__ import annotations

import re
from datetime import date, datetime
import math
from typing import Any
from urllib.parse import urlparse

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CLAIM_SCOPES = {"BIBLIOGRAPHIC_METADATA", "ABSTRACT", "FULL_TEXT_SECTION", "DATASET", "OTHER"}
ACCESS_STATUSES = {
    "METADATA_ONLY", "ABSTRACT_ONLY", "PARTIAL_TEXT_REVIEWED", "FULL_TEXT_REVIEWED",
    "NOT_ACCESSIBLE", "RESTRICTED_UNAVAILABLE",
}


def validate_source_register(records: list[dict[str, Any]]) -> list[str]:
    """Validate minimum provenance fields; does not verify source contents online."""
    errors: list[str] = []
    ids: set[str] = set()
    required_text = ("source_type", "title", "retrieval_method", "rights_status")
    for index, record in enumerate(records):
        label = f"sources[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{label} must be an object")
            continue
        for field in required_text:
            if not isinstance(record.get(field), str) or not record[field].strip():
                errors.append(f"{label}.{field} is required")
        sid = record.get("source_id")
        if not isinstance(sid, str) or not sid.strip():
            errors.append(f"{label}.source_id is required")
        elif sid in ids:
            errors.append(f"duplicate source_id: {sid}")
        else:
            ids.add(sid)
        url = record.get("url")
        parsed = urlparse(url if isinstance(url, str) else "")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"{label}.url must be an absolute HTTP(S) URL")
        status = record.get("access_status")
        if status not in ACCESS_STATUSES:
            errors.append(f"{label}.access_status is unsupported")
        if record.get("rights_status") not in {"OPEN_LICENSE", "PUBLIC_WEB_ACCESS", "LICENSED_ACCESS", "RESTRICTED", "UNKNOWN"}:
            errors.append(f"{label}.rights_status is unsupported")
        if record.get("source_type") not in {"JOURNAL_ARTICLE", "BOOK", "THESIS", "DISSERTATION", "OFFICIAL_GUIDELINE", "LAW_OR_REGULATION", "DATASET", "OFFICIAL_WEBPAGE", "OTHER"}:
            errors.append(f"{label}.source_type is unsupported")
        authors = record.get("authors", [])
        if not isinstance(authors, list) or any(not isinstance(author, str) or not author.strip() for author in authors):
            errors.append(f"{label}.authors must be an array of non-empty strings")
        for optional_author_field in ("citation_author", "reference_authors"):
            override = record.get(optional_author_field)
            if override is not None and (not isinstance(override, str) or not override.strip()):
                errors.append(f"{label}.{optional_author_field} must be null or a non-empty string")
        if status in {"ABSTRACT_ONLY", "PARTIAL_TEXT_REVIEWED", "FULL_TEXT_REVIEWED"}:
            if not isinstance(record.get("exact_locator"), str) or not record["exact_locator"].strip():
                errors.append(f"{label}.exact_locator is required for content-derived evidence")
        if status in {"NOT_ACCESSIBLE", "RESTRICTED_UNAVAILABLE", "METADATA_ONLY"} and record.get("exact_locator"):
            # Metadata locators can point to item pages; they must not be described as content locations.
            if record.get("locator_type") == "content":
                errors.append(f"{label} cannot claim a content locator for {status}")
        retrieval_date = record.get("retrieval_date")
        try:
            if not isinstance(retrieval_date, str) or not ISO_DATE_RE.fullmatch(retrieval_date):
                raise ValueError
            date.fromisoformat(retrieval_date)
        except (TypeError, ValueError):
            errors.append(f"{label}.retrieval_date must be ISO YYYY-MM-DD")
        digest = record.get("file_sha256")
        if digest is not None and (not isinstance(digest, str) or not SHA256_RE.fullmatch(digest)):
            errors.append(f"{label}.file_sha256 must be a lowercase SHA-256 when supplied")
        if record.get("rights_status") == "RESTRICTED" and status != "RESTRICTED_UNAVAILABLE":
            errors.append(f"{label} restricted source must not be treated as reviewed")
    return errors


def validate_claim_evidence_links(links: list[dict[str, Any]], source_records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    source_map = {item.get("source_id"): item for item in source_records}
    for index, link in enumerate(links):
        label = f"claim_links[{index}]"
        if not isinstance(link, dict):
            errors.append(f"{label} must be an object")
            continue
        source_id = link.get("source_id")
        source = source_map.get(source_id)
        if source is None:
            errors.append(f"{label} references unknown source_id {source_id!r}")
            continue
        if not isinstance(link.get("claim_id"), str) or not link["claim_id"].strip():
            errors.append(f"{label}.claim_id is required")
        if link.get("relation") not in {"SUPPORTS", "CONTRADICTS", "CONTEXTUALIZES"}:
            errors.append(f"{label}.relation is unsupported")
        locator = link.get("exact_locator")
        claim_scope = link.get("claim_scope")
        if claim_scope not in CLAIM_SCOPES:
            errors.append(f"{label}.claim_scope is unsupported")
        if not isinstance(locator, str) or not locator.strip():
            errors.append(f"{label}.exact_locator is required")
        access_status = source.get("access_status")
        if access_status in {"NOT_ACCESSIBLE", "RESTRICTED_UNAVAILABLE"}:
            errors.append(f"{label} cannot derive a claim from {access_status}")
        elif access_status == "METADATA_ONLY" and claim_scope != "BIBLIOGRAPHIC_METADATA":
            errors.append(f"{label} metadata-only source can support bibliographic metadata only")
        elif access_status == "ABSTRACT_ONLY" and claim_scope != "ABSTRACT":
            errors.append(f"{label} abstract-only source can support abstract-scope claims only")
        elif access_status in {"PARTIAL_TEXT_REVIEWED", "FULL_TEXT_REVIEWED"} and claim_scope == "BIBLIOGRAPHIC_METADATA":
            # A bibliographic fact may still be recorded, but its locator must explicitly be metadata.
            if "metadata" not in locator.casefold() and "title" not in locator.casefold():
                errors.append(f"{label} bibliographic metadata claims need a metadata/title locator")
        if link.get("support_level") not in {"DIRECT", "PARTIAL", "INDIRECT", "BACKGROUND"}:
            errors.append(f"{label}.support_level is unsupported")
        if link.get("review_status") not in {"UNREVIEWED", "VERIFIED", "NEEDS_REVIEW", "REJECTED"}:
            errors.append(f"{label}.review_status is unsupported")
        if link.get("review_status") == "VERIFIED" and not link.get("reviewer_role"):
            errors.append(f"{label} cannot be VERIFIED without a reviewer role")
    return errors


def _is_substantive(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().casefold()
        return bool(normalized) and normalized not in {"tbd", "todo", "n/a?", "to_be_decided", "belum ditentukan", "belum ada", "?"}
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value) and any(_is_substantive(item) for item in (value.values() if isinstance(value, dict) else value))
    return True


def methodology_readiness(profile: dict[str, Any]) -> dict[str, Any]:
    """Return design-specific missing fields; never auto-select a methodology/software."""
    design = profile.get("research_design")
    requirements: dict[str, tuple[str, ...]] = {
        "QUANTITATIVE_SURVEY": (
            "population_or_case_definition", "sampling_strategy", "sample_size_rationale",
            "variables_or_constructs", "instrument_and_validity_plan", "data_collection_protocol",
            "analysis_plan", "assumptions_and_diagnostics", "ethics_and_permissions",
        ),
        "QUANTITATIVE_EXPERIMENT": (
            "population_or_case_definition", "sampling_strategy", "sample_size_rationale",
            "variables_or_constructs", "instrument_and_validity_plan", "data_collection_protocol",
            "analysis_plan", "assumptions_and_diagnostics", "ethics_and_permissions",
        ),
        "QUALITATIVE": (
            "population_or_case_definition", "sampling_strategy", "data_collection_protocol",
            "qualitative_coding_approach", "analysis_plan", "ethics_and_permissions",
        ),
        "MIXED_METHODS": (
            "population_or_case_definition", "data_collection_protocol", "integration_strategy",
            "analysis_plan", "ethics_and_permissions",
        ),
        "SECONDARY_DATA": ("data_sources", "analysis_plan", "limitations"),
        "CASE_STUDY": ("population_or_case_definition", "data_sources", "analysis_plan", "limitations"),
        "SYSTEMATIC_REVIEW": ("data_sources", "analysis_plan", "limitations"),
    }
    required = requirements.get(design, ("data_sources", "analysis_plan", "limitations"))
    missing: list[str] = []
    for field in required:
        value = profile.get(field)
        if not _is_substantive(value):
            missing.append(field)
    if not _is_substantive(profile.get("research_question_ids")):
        missing.append("research_question_ids")
    if not _is_substantive(profile.get("limitations")):
        missing.append("limitations")
    return {
        "research_design": design,
        "ready_for_methodology_review": len(missing) == 0,
        "missing_fields": sorted(set(missing)),
        "notice": "Readiness is not methodological approval; a qualified reviewer must assess coherence and fit.",
    }


def _contains_non_finite(value: Any) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_contains_non_finite(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_non_finite(item) for item in value)
    return False


def validate_analysis_run(record: dict[str, Any]) -> list[str]:
    """Validate run metadata only; it does not execute or statistically verify outputs."""
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["analysis record must be an object"]
    for field in ("analysis_run_id", "project_id", "analysis_method", "script_or_command"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            errors.append(f"{field} is required")
    run_at = record.get("run_at")
    try:
        if not isinstance(run_at, str) or datetime.fromisoformat(run_at.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError
    except ValueError:
        errors.append("run_at must be an ISO-8601 timestamp with timezone")
    software = record.get("software")
    if not isinstance(software, dict) or not isinstance(software.get("name"), str) or not software["name"].strip() or not isinstance(software.get("version"), str) or not software["version"].strip():
        errors.append("software.name and software.version are required")
    elif software.get("version") == "0.5.2":
        for field in ("python_version", "implementation", "platform"):
            if not isinstance(software.get(field), str) or not software[field].strip():
                errors.append(f"software.{field} is required for v0.5.2 run records")
    manifest_path = record.get("project_manifest_path")
    manifest_hash = record.get("project_manifest_sha256")
    if manifest_path is not None or manifest_hash is not None:
        if not isinstance(manifest_path, str) or not manifest_path.strip() or not isinstance(manifest_hash, str) or not SHA256_RE.fullmatch(manifest_hash):
            errors.append("project manifest path and SHA-256 must be provided together")
    contract = record.get("reproducibility_contract")
    if software.get("version") == "0.5.2":
        required_contract = ("contract_version", "hash_algorithm", "input_hashing", "result_serialization", "csv_reader", "numeric_model", "reexecution_claim")
        if not isinstance(contract, dict) or any(not isinstance(contract.get(field), str) or not contract[field].strip() for field in required_contract):
            errors.append("v0.5.2 reproducibility_contract is incomplete")
        elif contract.get("contract_version") != "1.0.0" or contract.get("hash_algorithm") != "SHA-256":
            errors.append("unsupported reproducibility contract version or hash algorithm")
    hashes = record.get("input_artifact_hashes")
    if not isinstance(hashes, list) or not hashes:
        errors.append("input_artifact_hashes must contain at least one SHA-256")
    elif any(not isinstance(value, str) or not SHA256_RE.fullmatch(value) for value in hashes):
        errors.append("all input_artifact_hashes must be lowercase SHA-256 values")
    outputs = record.get("outputs")
    if not isinstance(outputs, list) or not outputs or any(not isinstance(item, str) or not item.strip() for item in outputs):
        errors.append("outputs must contain at least one non-empty artifact reference")
    if _contains_non_finite(record.get("parameters", {})):
        errors.append("parameters must not contain NaN or infinite numeric values")
    if record.get("review_status") not in {"NOT_REVIEWED", "SELF_REVIEWED", "INDEPENDENTLY_REPRODUCED", "REJECTED"}:
        errors.append("review_status is unsupported")
    return errors
