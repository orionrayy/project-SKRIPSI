"""Deterministic, local-only quality audits for thesis revision artifacts.

The module checks traceability and structural consistency. It does not assess
plagiarism, predict Turnitin/AI-detector results, infer semantic equivalence,
or approve academic content.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_SECTION_RE = re.compile(r"(?m)^BAGIAN\s+(\d+)\s*\|\s*(.*?)(?:\s*\|\s*PID\s+([^\r\n]+))?\s*$")
_ALLOWED_MAPPING = {"MAPPED", "LOW_CONFIDENCE", "UNMAPPED"}
_RESOLVED_VALIDATION = {"PASS", "VERIFIED", "RESOLVED", "REVIEWED_PASS"}


class RevisionQAError(ValueError):
    """Raised when an input artifact cannot be parsed safely."""


def _normalise_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = value.replace("\u00a0", " ").replace("\u00ad", "")
    value = value.replace("\u200b", "").replace("\ufeff", "")
    value = re.sub(r"\s+", " ", value).strip()
    # Word may split a subscripted symbol across runs (e.g., r + 11) and use
    # tab stops around an equation label. Normalize spacing around punctuation
    # without changing lexical tokens or comparing paraphrases.
    value = re.sub(r"\s*([=,:;])\s*", r"\1", value)
    value = re.sub(r"(?<=[A-Za-z])\s+(?=\d)", "", value)
    return value


def _parse_bubble_text(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise RevisionQAError(f"cannot read before-after text: {exc}") from exc

    starts = list(_SECTION_RE.finditer(text))
    if not starts:
        raise RevisionQAError("no BAGIAN headers found in before-after text")

    pairs: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[match.end():end]
        before_match = re.search(r"(?m)^SEBELUM:\s*\n", block)
        after_match = re.search(r"(?m)^SESUDAH:\s*\n", block)
        if before_match is None or after_match is None or after_match.start() <= before_match.end():
            errors.append(f"section {int(match.group(1)):03d}: missing or misordered SEBELUM/SESUDAH labels")
            continue

        before = block[before_match.end():after_match.start()]
        before = re.split(r"\n\s*-{5,}\s*(?:\n|$)", before, maxsplit=1)[0]
        after = block[after_match.end():]
        after = re.split(r"\n\s*-{5,}\s*(?:\n|$)", after, maxsplit=1)[0]
        after = re.split(r"\n\s*BAGIAN\s+\d+\s*\|", after, maxsplit=1)[0]
        before, after = before.strip(), after.strip()
        section_num = int(match.group(1))
        if not before or not after:
            errors.append(f"section {section_num:03d}: empty SEBELUM or SESUDAH block")
            continue
        pairs.append({
            "pair_id": f"PAIR-{section_num:03d}",
            "section_number": section_num,
            "section_title": match.group(2).strip(),
            "paragraph_id": match.group(3).strip() if match.group(3) else None,
            "before_text": before,
            "after_text": after,
        })

    numbers = [p["section_number"] for p in pairs]
    duplicate_numbers = sorted(n for n, count in Counter(numbers).items() if count > 1)
    if duplicate_numbers:
        errors.append(f"duplicate BAGIAN numbers: {duplicate_numbers}")
    return pairs, errors


def _docx_paragraph_texts(path: Path) -> list[str]:
    if not path.is_file():
        raise RevisionQAError(f"DOCX not found: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise RevisionQAError(f"DOCX ZIP CRC failed at {bad_member}")
            xml = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise RevisionQAError(f"cannot read DOCX package: {exc}") from exc

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise RevisionQAError(f"word/document.xml is malformed: {exc}") from exc

    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_W}p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{_W}t":
                parts.append(node.text or "")
            elif node.tag == f"{_W}tab":
                parts.append("\t")
            elif node.tag in {f"{_W}br", f"{_W}cr"}:
                parts.append("\n")
        paragraphs.append("".join(parts))
    if not paragraphs:
        raise RevisionQAError("DOCX main document contains no paragraphs")
    return paragraphs


def _build_exact_window_index(paragraphs: list[str], max_window: int = 5) -> dict[str, list[dict[str, int]]]:
    index: dict[str, list[dict[str, int]]] = {}
    for start in range(len(paragraphs)):
        joined = ""
        for end in range(start, min(len(paragraphs), start + max_window)):
            joined = f"{joined} {paragraphs[end]}" if joined else paragraphs[end]
            normalized = _normalise_text(joined)
            if normalized:
                index.setdefault(normalized, []).append({"start_paragraph": start + 1, "end_paragraph": end + 1})
    return index


def _find_exact_windows(value: str, index: dict[str, list[dict[str, int]]]) -> list[dict[str, int]]:
    return index.get(_normalise_text(value), [])


def audit_before_after_pairs(
    bubble_text: Path | str,
    candidate_docx: Path | str,
    original_docx: Path | str | None = None,
    *,
    max_window: int = 5,
) -> dict[str, Any]:
    """Check exact normalized before/after passage correspondence with DOCX files."""
    bubble_path = Path(bubble_text)
    candidate_path = Path(candidate_docx)
    pairs, parse_errors = _parse_bubble_text(bubble_path)
    candidate_paragraphs = _docx_paragraph_texts(candidate_path)
    original_paragraphs = _docx_paragraph_texts(Path(original_docx)) if original_docx else None
    candidate_index = _build_exact_window_index(candidate_paragraphs, max_window=max_window)
    original_index = _build_exact_window_index(original_paragraphs, max_window=max_window) if original_paragraphs is not None else None

    results: list[dict[str, Any]] = []
    after_counts: Counter[str] = Counter()
    before_counts: Counter[str] = Counter()
    for pair in pairs:
        after_norm = _normalise_text(pair["after_text"])
        after_counts[after_norm] += 1
        after_matches = _find_exact_windows(pair["after_text"], candidate_index)
        row: dict[str, Any] = {
            "pair_id": pair["pair_id"],
            "section_title": pair["section_title"],
            "paragraph_id": pair["paragraph_id"],
            "after_match_count": len(after_matches),
            "after_match_locations": after_matches[:5],
            "after_status": "NOT_FOUND" if not after_matches else "MATCHED_UNIQUE" if len(after_matches) == 1 else "MATCHED_MULTIPLE",
        }
        if original_paragraphs is not None:
            before_norm = _normalise_text(pair["before_text"])
            if before_norm.casefold() in {"tidak terdapat pada daftar pustaka original.", "not present in the original reference list."}:
                row.update({"before_match_count": 0, "before_match_locations": [], "before_status": "NOT_APPLICABLE_NEW_CONTENT"})
            else:
                before_counts[before_norm] += 1
                before_matches = _find_exact_windows(pair["before_text"], original_index or {})
                row.update({
                    "before_match_count": len(before_matches),
                    "before_match_locations": before_matches[:5],
                    "before_status": "NOT_FOUND" if not before_matches else "MATCHED_UNIQUE" if len(before_matches) == 1 else "MATCHED_MULTIPLE",
                })
        results.append(row)

    matched = sum(row["after_status"] == "MATCHED_UNIQUE" for row in results)
    multiple = sum(row["after_status"] == "MATCHED_MULTIPLE" for row in results)
    present = matched + multiple
    missing = sum(row["after_status"] == "NOT_FOUND" for row in results)
    before_summary = None
    if original_paragraphs is not None:
        before_summary = {
            "total": len(results),
            "applicable": sum(row.get("before_status") != "NOT_APPLICABLE_NEW_CONTENT" for row in results),
            "matched_unique": sum(row.get("before_status") == "MATCHED_UNIQUE" for row in results),
            "matched_multiple": sum(row.get("before_status") == "MATCHED_MULTIPLE" for row in results),
            "not_found": sum(row.get("before_status") == "NOT_FOUND" for row in results),
            "not_applicable_new_content": sum(row.get("before_status") == "NOT_APPLICABLE_NEW_CONTENT" for row in results),
        }
    duplicate_after_blocks = sum(count > 1 for count in after_counts.values())
    if parse_errors or missing:
        status = "FAIL"
    elif multiple or duplicate_after_blocks:
        status = "CONDITIONAL"
    else:
        status = "PASS"
    return {
        "schema_version": "1.0.0",
        "audit_type": "BEFORE_AFTER_DOCX_CORRESPONDENCE",
        "status": status,
        "bubble_text": str(bubble_path),
        "candidate_docx": str(candidate_path),
        "original_docx": str(original_docx) if original_docx else None,
        "bubble_text_sha256": _sha256(bubble_path),
        "candidate_docx_sha256": _sha256(candidate_path),
        "original_docx_sha256": _sha256(Path(original_docx)) if original_docx else None,
        "summary": {
            "pair_count": len(pairs),
            "parsed_pair_count": len(pairs),
            "after_matched_unique": matched,
            "after_matched_multiple": multiple,
            "after_present_at_least_once": present,
            "after_not_found": missing,
            "after_presence_ratio": round(present / len(pairs), 6) if pairs else 0.0,
            "after_unique_location_ratio": round(matched / len(pairs), 6) if pairs else 0.0,
            "duplicate_after_text_values": duplicate_after_blocks,
            "candidate_paragraph_count": len(candidate_paragraphs),
            "before": before_summary,
        },
        "parse_errors": parse_errors,
        "unmatched_or_ambiguous_pairs": [row for row in results if row["after_status"] != "MATCHED_UNIQUE"],
        "pair_results": results,
        "turnitin_similarity": "NOT_MEASURED",
        "semantic_equivalence": "NOT_AUTOMATICALLY_ASSESSED_HUMAN_REVIEW_REQUIRED",
        "notice": "This is exact normalized text-to-document traceability, not a plagiarism, similarity, authorship, or semantic-equivalence assessment.",
    }


def audit_marked_region_register(csv_path: Path | str) -> dict[str, Any]:
    """Audit completeness and unresolved states in a Turnitin marked-region CSV."""
    path = Path(csv_path)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise RevisionQAError(f"cannot read marked-region register: {exc}") from exc

    required = {"region_id", "mapping_status", "issue_class", "evidence_status", "disposition", "validation_status"}
    missing_headers = sorted(required - set(headers))
    if missing_headers:
        raise RevisionQAError(f"marked-region register missing required columns: {missing_headers}")

    ids = [(row.get("region_id") or "").strip() for row in rows]
    empty_ids = sum(not value for value in ids)
    duplicate_ids = sorted(key for key, count in Counter(v for v in ids if v).items() if count > 1)
    mapping_counts = Counter((row.get("mapping_status") or "").strip().upper() for row in rows)
    disposition_counts = Counter((row.get("disposition") or "").strip().upper() for row in rows)
    evidence_counts = Counter((row.get("evidence_status") or "").strip().lower() for row in rows)
    validation_counts = Counter((row.get("validation_status") or "").strip().upper() for row in rows)

    documented = 0
    resolved = 0
    rationale_candidates = {"rationale", "disposition_rationale", "validation_notes", "reviewer_notes"}
    rationale_column = next((h for h in headers if h.lower() in rationale_candidates), None)
    missing_rationale = 0
    unresolved: list[dict[str, Any]] = []
    for row in rows:
        rid = (row.get("region_id") or "").strip()
        mapping = (row.get("mapping_status") or "").strip().upper()
        issue = (row.get("issue_class") or "").strip()
        evidence = (row.get("evidence_status") or "").strip()
        disposition = (row.get("disposition") or "").strip()
        validation = (row.get("validation_status") or "").strip().upper()
        rationale = (row.get(rationale_column) or "").strip() if rationale_column else ""
        is_documented = bool(rid and issue and evidence and disposition and validation)
        is_resolved = bool(is_documented and mapping == "MAPPED" and validation in _RESOLVED_VALIDATION and rationale)
        documented += int(is_documented)
        resolved += int(is_resolved)
        missing_rationale += int(not rationale)
        if not is_resolved:
            unresolved.append({
                "region_id": rid or None,
                "mapping_status": mapping or "MISSING",
                "issue_class": issue or "MISSING",
                "evidence_status": evidence or "MISSING",
                "disposition": disposition or "MISSING",
                "validation_status": validation or "MISSING",
                "rationale_missing": not bool(rationale),
            })

    unknown_mapping = sorted(set(mapping_counts) - _ALLOWED_MAPPING - {""})
    all_region_ids_unique = empty_ids == 0 and not duplicate_ids
    accounted_ratio = documented / len(rows) if rows else 0.0
    resolved_ratio = resolved / len(rows) if rows else 0.0
    status = "PASS" if rows and all_region_ids_unique and documented == len(rows) and resolved == len(rows) and not unknown_mapping else "CONDITIONAL"
    return {
        "schema_version": "1.0.0",
        "audit_type": "MARKED_REGION_REGISTER",
        "status": status,
        "source_file": str(path),
        "source_sha256": _sha256(path),
        "summary": {
            "row_count": len(rows),
            "unique_region_ids": len(set(v for v in ids if v)),
            "empty_region_ids": empty_ids,
            "duplicate_region_ids": duplicate_ids,
            "mapping_status_counts": dict(mapping_counts),
            "disposition_counts": dict(disposition_counts),
            "evidence_status_counts": dict(evidence_counts),
            "validation_status_counts": dict(validation_counts),
            "documented_count": documented,
            "documented_ratio": round(accounted_ratio, 6),
            "resolved_count": resolved,
            "resolved_ratio": round(resolved_ratio, 6),
            "missing_rationale_count": missing_rationale,
            "rationale_column_present": rationale_column is not None,
            "unknown_mapping_statuses": unknown_mapping,
        },
        "unresolved_regions": unresolved,
        "notice": "A report source label is metadata, not full-text evidence. LOW_CONFIDENCE, UNMAPPED, pending, or rationale-free regions remain open; registration alone is not resolution.",
    }


def audit_empirical_study_consistency(document: dict[str, Any]) -> dict[str, Any]:
    """Check study design, sample, measurement modality and analysis declarations.

    This deterministic audit does not compute statistics or prove that raw data
    are valid. It highlights inconsistencies that require source-data review.
    """
    if not isinstance(document, dict):
        raise RevisionQAError("study consistency input must be a JSON object")
    findings: list[dict[str, str]] = []

    def add(level: str, code: str, detail: str) -> None:
        findings.append({"severity": level, "code": code, "detail": detail})

    sample = document.get("sample", {})
    declared_n = sample.get("declared_n") if isinstance(sample, dict) else None
    if not isinstance(declared_n, int) or declared_n < 1:
        add("ERROR", "DECLARED_SAMPLE_SIZE_INVALID", "sample.declared_n must be a positive integer")
        declared_n = None

    for distribution in document.get("demographic_distributions", []) or []:
        if not isinstance(distribution, dict):
            add("ERROR", "DEMOGRAPHIC_DISTRIBUTION_MALFORMED", "each demographic distribution must be an object")
            continue
        name = str(distribution.get("name", "unnamed"))
        counts = distribution.get("counts")
        percentages = distribution.get("percentages")
        local_n = distribution.get("declared_n", declared_n)
        if not isinstance(counts, list) or not counts or any(not isinstance(v, int) or v < 0 for v in counts):
            add("ERROR", "DEMOGRAPHIC_COUNTS_INVALID", f"{name}: counts must be non-empty non-negative integers")
            continue
        total = sum(counts)
        if isinstance(local_n, int) and total != local_n:
            add("ERROR", "DEMOGRAPHIC_COUNTS_DO_NOT_MATCH_N", f"{name}: counts sum to {total}, declared N is {local_n}; verify source data, do not auto-correct")
        if percentages is not None:
            if not isinstance(percentages, list) or len(percentages) != len(counts) or any(not isinstance(v, (int, float)) for v in percentages):
                add("ERROR", "DEMOGRAPHIC_PERCENTAGES_INVALID", f"{name}: percentages must match counts length")
            elif isinstance(local_n, int) and local_n > 0:
                expected = [round(count / local_n * 100, 2) for count in counts]
                for index, (observed, calculated) in enumerate(zip(percentages, expected), start=1):
                    if abs(float(observed) - calculated) > 0.51:
                        add("ERROR", "DEMOGRAPHIC_PERCENTAGE_MISMATCH", f"{name}, category {index}: reported {observed}%, count/N implies {calculated}%; verify source data")

    design = document.get("design", {})
    design_type = str(design.get("type", "")).upper() if isinstance(design, dict) else ""
    has_control = bool(design.get("has_control_group", False)) if isinstance(design, dict) else False
    participant_ids = bool(sample.get("participant_ids_available", False)) if isinstance(sample, dict) else False
    participant_ids_unique = bool(sample.get("participant_ids_unique", False)) if isinstance(sample, dict) else False

    constructs = document.get("constructs", []) or []
    modalities: dict[str, str] = {}
    for construct in constructs:
        if not isinstance(construct, dict):
            continue
        cid = str(construct.get("id", "")).strip()
        modality = str(construct.get("measurement_modality", "")).upper().strip()
        if cid and modality:
            modalities[cid] = modality

    for analysis in document.get("analyses", []) or []:
        if not isinstance(analysis, dict):
            add("ERROR", "ANALYSIS_DECLARATION_MALFORMED", "each analysis declaration must be an object")
            continue
        aid = str(analysis.get("id", "unnamed"))
        procedure = str(analysis.get("procedure", "")).upper()
        if procedure in {"PAIRED_T_TEST", "PAIRED_TTEST", "PAIRED_TEST", "WILCOXON_SIGNED_RANK"}:
            key = analysis.get("pairing_key")
            if not key or not participant_ids or not participant_ids_unique:
                add("ERROR", "PAIRED_ANALYSIS_WITHOUT_VERIFIED_PAIRING_KEY", f"{aid}: paired analysis requires a documented unique participant matching key")
            if analysis.get("test_output_table_present") is False:
                add("ERROR", "PAIRED_TEST_OUTPUT_TABLE_MISSING", f"{aid}: the reported inferential result has no corresponding paired-test output table in the declared appendix/evidence package")
            diagnostics = analysis.get("assumption_diagnostics")
            if not isinstance(diagnostics, dict) or diagnostics.get("difference_distribution_reviewed") is not True:
                add("WARNING", "PAIRED_DIFFERENCE_DIAGNOSTICS_NOT_DOCUMENTED", f"{aid}: document the paired-difference distribution review and the rationale for the selected paired procedure")
            if analysis.get("pairing_method") == "ROW_ORDER" and (not key or not participant_ids_unique):
                add("WARNING", "PAIRED_ROWS_MATCHED_BY_ORDER_ONLY", f"{aid}: row-order pairing is provisional until verified participant identities or a validated matching key are available")
        if procedure in {"CRONBACH_ALPHA", "CRONBACHS_ALPHA"}:
            grouped = analysis.get("construct_ids") or ([analysis.get("construct_id")] if analysis.get("construct_id") else [])
            if len(grouped) > 1 and not analysis.get("multidimensional_model_justification"):
                add("ERROR", "CRONBACH_ALPHA_POOLS_DISTINCT_CONSTRUCTS", f"{aid}: alpha combines multiple constructs without a documented measurement-model justification; estimate reliability per scale")
        if procedure == "ICC":
            missing = [field for field in ("rater_count", "model", "measurement_type", "definition") if analysis.get(field) in (None, "")]
            if missing:
                add("ERROR", "ICC_CONFIGURATION_INCOMPLETE", f"{aid}: ICC declaration is missing {', '.join(missing)}")
        p_value = analysis.get("p_value")
        if p_value is not None and str(p_value).strip().lower() in {"0", "0.0", "0.00", "0.000", ".000"}:
            add("WARNING", "P_VALUE_ROUNDED_TO_ZERO", f"{aid}: report p < .001 (or the unrounded value), not p = 0.000")
        dependent = analysis.get("dependent_construct_id")
        outcome_kind = str(analysis.get("outcome_kind", "")).upper()
        if dependent in modalities:
            expected = modalities[dependent]
            if outcome_kind and outcome_kind != expected:
                add("ERROR", "ANALYSIS_OUTCOME_MODALITY_MISMATCH", f"{aid}: outcome_kind {outcome_kind} conflicts with construct {dependent} modality {expected}")
        claimed_target = analysis.get("claimed_target_construct_id")
        if dependent and claimed_target and claimed_target != dependent:
            actual_modality = modalities.get(dependent, "UNDECLARED")
            claimed_modality = modalities.get(claimed_target, "UNDECLARED")
            add("ERROR", "ANALYSIS_CLAIMS_DIFFERENT_OUTCOME_CONSTRUCT", f"{aid}: analysis outcome is {dependent} ({actual_modality}) but interpretation claims {claimed_target} ({claimed_modality})")
        if analysis.get("claims_causality") and design_type in {"ONE_GROUP_PRETEST_POSTTEST", "ONE_GROUP_PRETEST_POSTTEST_NO_CONTROL"} and not has_control:
            add("ERROR", "CAUSAL_CLAIM_EXCEEDS_DESIGN", f"{aid}: a one-group pretest-posttest design without a control group does not by itself identify a causal effect")

    if design_type in {"ONE_GROUP_PRETEST_POSTTEST", "ONE_GROUP_PRETEST_POSTTEST_NO_CONTROL"} and not has_control:
        add("INFO", "CAUSAL_INTERPRETATION_LIMIT", "interpret pre/post differences as observed within-group change; discuss history, maturation, testing, instrumentation and other threats")

    for instrument in document.get("instruments", []) or []:
        if not isinstance(instrument, dict):
            add("ERROR", "INSTRUMENT_DECLARATION_MALFORMED", "each instrument declaration must be an object")
            continue
        iid = str(instrument.get("id", "unnamed"))
        item_count = instrument.get("item_count")
        if not isinstance(item_count, int) or item_count < 1:
            add("ERROR", "INSTRUMENT_ITEM_COUNT_INVALID", f"{iid}: item_count must be a positive integer")
            continue
        validity = instrument.get("validity_evidence")
        if not isinstance(validity, dict):
            add("WARNING", "INSTRUMENT_VALIDITY_EVIDENCE_NOT_DOCUMENTED", f"{iid}: no distinct validity-evidence record is attached to this instrument")
            continue
        state = str(validity.get("status", "")).upper()
        if state in {"NOT_VISIBLE", "NOT_PROVIDED", "PENDING", "UNKNOWN", ""}:
            add("WARNING", "INSTRUMENT_VALIDITY_EVIDENCE_NOT_VISIBLE", f"{iid}: validity evidence is not visible/complete in the declared package; do not infer that validation was completed")
        validated_count = validity.get("validated_item_count")
        if validated_count is not None and (not isinstance(validated_count, int) or validated_count < 0 or validated_count > item_count):
            add("ERROR", "INSTRUMENT_VALIDATED_ITEM_COUNT_INVALID", f"{iid}: validated_item_count must be between 0 and item_count")
        if str(validity.get("method", "")).upper() == "AIKEN_V" and validated_count is not None and validated_count != item_count:
            add("ERROR", "AIKEN_V_ITEM_COVERAGE_MISMATCH", f"{iid}: Aiken's V evidence covers {validated_count} of {item_count} declared items")

    severity_rank = {"ERROR": 3, "WARNING": 2, "INFO": 1}
    highest = max((severity_rank[f["severity"]] for f in findings), default=0)
    status = "FAIL" if highest == 3 else "CONDITIONAL" if highest == 2 else "PASS_WITH_NOTES"
    return {
        "schema_version": "1.0.0",
        "audit_type": "EMPIRICAL_STUDY_CONSISTENCY",
        "status": status,
        "study_id": document.get("study_id"),
        "declared_sample_size": declared_n,
        "findings": findings,
        "finding_counts": dict(Counter(item["severity"] for item in findings)),
        "statistics_computed": False,
        "raw_data_validated": False,
        "human_methodology_review_required": True,
        "notice": "Structural consistency checks only. No missing counts or participant identities were inferred, corrected, imputed, or fabricated.",
    }


def audit_artifact_manifest(manifest_path: Path | str) -> dict[str, Any]:
    """Verify declared artifact paths, byte counts and SHA-256 hashes."""
    path = Path(manifest_path)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RevisionQAError(f"cannot read artifact manifest: {exc}") from exc
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise RevisionQAError("manifest must contain a non-empty 'artifacts' array")
    results: list[dict[str, Any]] = []
    for item in artifacts:
        if not isinstance(item, dict):
            results.append({"status": "FAIL", "error": "artifact entry is not an object"})
            continue
        rel = item.get("path")
        expected_hash = item.get("sha256")
        expected_bytes = item.get("bytes")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            results.append({"artifact_id": item.get("id"), "status": "FAIL", "error": "artifact path must be relative and traversal-free"})
            continue
        target = (path.parent / rel).resolve()
        root = path.parent.resolve()
        if root not in target.parents:
            results.append({"artifact_id": item.get("id"), "path": rel, "status": "FAIL", "error": "artifact escapes manifest directory"})
            continue
        if not target.is_file():
            results.append({"artifact_id": item.get("id"), "path": rel, "status": "FAIL", "error": "artifact file is missing"})
            continue
        actual_hash = _sha256(target)
        actual_bytes = target.stat().st_size
        errors = []
        if expected_hash != actual_hash:
            errors.append("sha256_mismatch")
        if expected_bytes is not None and expected_bytes != actual_bytes:
            errors.append("byte_count_mismatch")
        results.append({
            "artifact_id": item.get("id"), "path": rel,
            "expected_sha256": expected_hash, "actual_sha256": actual_hash,
            "expected_bytes": expected_bytes, "actual_bytes": actual_bytes,
            "status": "FAIL" if errors else "PASS", "errors": errors,
        })
    failed = sum(row["status"] != "PASS" for row in results)
    return {
        "schema_version": "1.0.0",
        "audit_type": "ARTIFACT_MANIFEST_INTEGRITY",
        "status": "PASS" if not failed else "FAIL",
        "manifest_path": str(path),
        "manifest_sha256": _sha256(path),
        "artifact_count": len(results),
        "passed": len(results) - failed,
        "failed": failed,
        "artifacts": results,
        "notice": "The manifest must be regenerated after final render/export; a DOCX/PDF mismatch is a provenance failure, not a visual opinion.",
    }


def write_report(report: dict[str, Any], output_path: Path | str) -> Path:
    output = Path(output_path)
    if output.exists():
        raise RevisionQAError(f"refusing to overwrite existing report: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    try:
        output.chmod(0o600)
    except OSError:
        pass
    return output


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
