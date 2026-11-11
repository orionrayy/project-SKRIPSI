"""Deterministic contract and phase-gate checks for thesis workspaces."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .constants import (
    ACCEPTANCE_STATUSES,
    APPROVAL_STATUSES,
    AUTHORIZATION_STATUSES,
    COMPLETE_CONCLUSION,
    EXECUTION_STATUSES,
    THESIS_PHASES,
    VALIDATION_STATUSES,
)

PROJECT_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,62}[a-z0-9])$")


class ValidationError(ValueError):
    """Raised for invalid project or ledger content."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"expected JSON object: {path}")
    return value


def validate_project_id(project_id: str) -> None:
    if not PROJECT_ID_RE.fullmatch(project_id):
        raise ValidationError(
            "project_id must be 3–64 lowercase letters/digits/hyphens, "
            "start/end with a letter or digit, and contain no path separators"
        )


def _check_enum(value: Any, allowed: set[str], label: str, errors: list[str]) -> None:
    if value not in allowed:
        errors.append(f"{label}: unsupported value {value!r}")


def validate_manifest(manifest: dict[str, Any], directory_name: str | None = None) -> list[str]:
    errors: list[str] = []
    required = ("schema_version", "project_id", "title", "discipline", "research_design", "institution", "privacy")
    for key in required:
        if key not in manifest:
            errors.append(f"manifest missing required field: {key}")
    project_id = manifest.get("project_id")
    if isinstance(project_id, str):
        try:
            validate_project_id(project_id)
        except ValidationError as exc:
            errors.append(str(exc))
        if directory_name and project_id != directory_name:
            errors.append("project_id does not match workspace directory name")
    if manifest.get("schema_version") != "1.0.0":
        errors.append("schema_version must be 1.0.0")
    for key in ("title", "discipline", "research_design"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            errors.append(f"{key} must be a non-empty string")
    if not isinstance(manifest.get("institution"), dict):
        errors.append("institution must be an object")
    privacy = manifest.get("privacy")
    if not isinstance(privacy, dict):
        errors.append("privacy must be an object")
    else:
        if privacy.get("classification") not in {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"}:
            errors.append("privacy.classification has an unsupported value")
        if privacy.get("storage_mode") not in {"LOCAL_ONLY", "APPROVED_PRIVATE_STORAGE", "PUBLIC_RELEASE_APPROVED"}:
            errors.append("privacy.storage_mode has an unsupported value")
        if privacy.get("external_ai_transfer") is not False:
            errors.append("external_ai_transfer must default to false")
    if manifest.get("workspace_type") != "independent_thesis_project":
        errors.append("workspace_type must be independent_thesis_project")
    return errors


def validate_phase_ledger(ledger: dict[str, Any], project_id: str | None = None) -> list[str]:
    errors: list[str] = []
    if ledger.get("schema_version") != "1.0.0":
        errors.append("phase ledger schema_version must be 1.0.0")
    if project_id and ledger.get("project_id") != project_id:
        errors.append("phase ledger project_id does not match manifest")
    phases = ledger.get("phases")
    if not isinstance(phases, list):
        return errors + ["phases must be an array"]
    expected_ids = [phase_id for phase_id, _ in THESIS_PHASES]
    actual_ids = [item.get("phase_id") if isinstance(item, dict) else None for item in phases]
    if actual_ids != expected_ids:
        errors.append(f"phases must contain exact ordered IDs {expected_ids}")
        return errors

    derived_current = next((phase["phase_id"] for phase in phases if phase.get("phase_conclusion") != COMPLETE_CONCLUSION), phases[-1]["phase_id"])
    if ledger.get("current_phase") != derived_current:
        errors.append(f"current_phase must point to earliest non-accepted phase {derived_current}")

    for index, phase in enumerate(phases):
        pid = phase["phase_id"]
        expected_name = THESIS_PHASES[index][1]
        if phase.get("phase_name") != expected_name:
            errors.append(f"{pid}.phase_name must match the canonical lifecycle name")
        expected_dependencies = [expected_ids[index - 1]] if index else []
        if phase.get("dependencies") != expected_dependencies:
            errors.append(f"{pid}.dependencies must equal {expected_dependencies}")
        _check_enum(phase.get("execution_status"), EXECUTION_STATUSES, f"{pid}.execution_status", errors)
        _check_enum(phase.get("validation_status"), VALIDATION_STATUSES, f"{pid}.validation_status", errors)
        _check_enum(phase.get("human_acceptance_status"), ACCEPTANCE_STATUSES, f"{pid}.human_acceptance_status", errors)
        _check_enum(phase.get("approval_status"), APPROVAL_STATUSES, f"{pid}.approval_status", errors)
        _check_enum(phase.get("authorization_status"), AUTHORIZATION_STATUSES, f"{pid}.authorization_status", errors)

        is_complete = phase.get("phase_conclusion") == COMPLETE_CONCLUSION
        if is_complete:
            if phase.get("execution_status") != "COMPLETE":
                errors.append(f"{pid} cannot conclude complete unless execution_status is COMPLETE")
            if phase.get("validation_status") not in {"PASS", "PASS_WITH_LIMITATION"}:
                errors.append(f"{pid} cannot conclude complete without passing validation")
            if phase.get("human_acceptance_status") != "ACCEPTED":
                errors.append(f"{pid} cannot conclude complete without human ACCEPTED status")
            if phase.get("approval_status") != "APPROVED":
                errors.append(f"{pid} cannot conclude complete without APPROVED status")
            if phase.get("authorization_status") not in {"AUTHORIZED_SCOPED", "APPROVED_SCOPED"}:
                errors.append(f"{pid} cannot conclude complete without scoped authorization")

        has_started = phase.get("execution_status") in {"IN_PROGRESS", "COMPLETE"}
        authorized = phase.get("authorization_status") in {"AUTHORIZED_SCOPED", "APPROVED_SCOPED"}
        if has_started and not authorized:
            errors.append(f"{pid} cannot start without phase-specific scoped authorization")
        if index == 0:
            continue
        predecessor = phases[index - 1]
        predecessor_complete = predecessor.get("phase_conclusion") == COMPLETE_CONCLUSION
        if authorized and not predecessor_complete:
            errors.append(f"{pid} cannot be authorized before {predecessor['phase_id']} is COMPLETE_AND_APPROVED")
        if has_started and not predecessor_complete:
            errors.append(f"{pid} cannot start before {predecessor['phase_id']} is COMPLETE_AND_APPROVED")

    return errors


def validate_workspace(project_dir: Path) -> tuple[list[str], dict[str, Any] | None, dict[str, Any] | None]:
    errors: list[str] = []
    manifest_path = project_dir / "project.json"
    ledger_path = project_dir / "state" / "phase_ledger.json"
    try:
        manifest = load_json(manifest_path)
        errors.extend(validate_manifest(manifest, project_dir.name))
    except ValidationError as exc:
        return [str(exc)], None, None
    try:
        ledger = load_json(ledger_path)
        errors.extend(validate_phase_ledger(ledger, manifest.get("project_id")))
    except ValidationError as exc:
        errors.append(str(exc))
        ledger = None

    project_id = manifest.get("project_id")
    starter_files = {
        "approval register": project_dir / "state" / "approval_register.json",
        "source register": project_dir / "sources" / "registry" / "source_register.json",
        "methodology profile": project_dir / "methodology" / "design" / "methodology_profile.json",
        "decision register": project_dir / "decisions" / "decision_register.json",
    }
    starter_values: dict[str, dict[str, Any]] = {}
    for label, path in starter_files.items():
        try:
            starter_values[label] = load_json(path)
        except ValidationError as exc:
            errors.append(f"{label}: {exc}")
    for label, value in starter_values.items():
        if value.get("project_id") != project_id:
            errors.append(f"{label} project_id does not match project manifest")

    approvals = starter_values.get("approval register")
    if approvals is not None and not isinstance(approvals.get("approvals"), list):
        errors.append("approval register approvals must be an array")
    decisions = starter_values.get("decision register")
    if decisions is not None and not isinstance(decisions.get("decisions"), list):
        errors.append("decision register decisions must be an array")

    source_register = starter_values.get("source register")
    if source_register is not None:
        from .quality import validate_claim_evidence_links, validate_source_register
        sources = source_register.get("sources")
        links = source_register.get("claim_evidence_links")
        if not isinstance(sources, list):
            errors.append("source register sources must be an array")
        else:
            errors.extend(validate_source_register(sources))
        if not isinstance(links, list):
            errors.append("source register claim_evidence_links must be an array")
        elif isinstance(sources, list):
            errors.extend(validate_claim_evidence_links(links, sources))

    profile = starter_values.get("methodology profile")
    if profile is not None:
        if profile.get("research_design") != manifest.get("research_design"):
            errors.append("methodology profile research_design does not match project manifest")

    # v0.4.0 alignment is additive: older v0.1-v0.3 workspaces remain valid
    # until the operator explicitly creates the new project-scoped scaffold.
    alignment_path = project_dir / "methodology" / "design" / "research_alignment.json"
    alignment_components = (project_dir / "methodology", alignment_path.parent, alignment_path)
    if any(component.is_symlink() for component in alignment_components):
        errors.append("research alignment path must not contain symlinked components")
    elif alignment_path.exists():
        try:
            alignment = load_json(alignment_path)
            if alignment.get("project_id") != project_id:
                errors.append("research alignment project_id does not match project manifest")
            if alignment.get("research_design") != manifest.get("research_design"):
                errors.append("research alignment research_design does not match project manifest")
        except ValidationError as exc:
            errors.append(f"research alignment: {exc}")

    analysis_spec_path = project_dir / "analysis" / "design" / "analysis_specification.json"
    analysis_components = (project_dir / "analysis", analysis_spec_path.parent, analysis_spec_path)
    if any(component.is_symlink() for component in analysis_components):
        errors.append("analysis specification path must not contain symlinked components")
    elif analysis_spec_path.exists():
        try:
            analysis_spec = load_json(analysis_spec_path)
            if analysis_spec.get("project_id") != project_id:
                errors.append("analysis specification project_id does not match project manifest")
        except ValidationError as exc:
            errors.append(f"analysis specification: {exc}")

    return errors, manifest, ledger
