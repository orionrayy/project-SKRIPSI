"""Workspace creation and read-only project status operations."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import append_audit_event
from .constants import THESIS_PHASES
from .validation import ValidationError, validate_project_id, validate_workspace

WORKSPACE_DIRS = (
    "intake",
    "requirements/institution",
    "requirements/programme",
    "sources/registry",
    "sources/snapshots",
    "sources/cache",
    "literature/matrix",
    "methodology/design",
    "methodology/instruments",
    "ethics/approvals",
    "data/raw",
    "data/processed",
    "data/registry",
    "analysis/design",
    "analysis/scripts",
    "analysis/outputs",
    "manuscript/drafts",
    "manuscript/revisions",
    "manuscript/builds",
    "manuscript/figures",
    "deliverables",
    "audit",
    "decisions",
    "references",
    "qa",
    "state/approvals",
)


def _restrict_private_permissions(path: Path, mode: int) -> None:
    """Best-effort POSIX privacy mode; Windows ACLs remain OS-managed."""
    if os.name != "nt":
        try:
            path.chmod(mode)
        except OSError:
            # Keep workspace creation portable; operators must verify storage ACLs.
            pass


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _restrict_private_permissions(path, 0o600)


def build_default_manifest(
    project_id: str,
    title: str,
    discipline: str,
    research_design: str,
    institution: str,
    programme: str = "",
    language: str = "id-ID",
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "workspace_type": "independent_thesis_project",
        "project_id": project_id,
        "title": title,
        "discipline": discipline,
        "research_design": research_design,
        "language": language,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "institution": {
            "name": institution,
            "programme": programme,
            "guideline_profile_id": None,
            "guideline_version": None,
            "source_required": True,
        },
        "privacy": {
            "classification": "CONFIDENTIAL",
            "storage_mode": "LOCAL_ONLY",
            "external_ai_transfer": False,
            "contains_personal_data": None,
            "ethics_review_required": None,
            "retention_policy_id": None,
        },
        "governance": {
            "human_author_responsible": True,
            "ai_use_disclosure_required_by_institution": None,
            "data_fabrication_prohibited": True,
            "authorship_misrepresentation_prohibited": True,
            "detector_evasion_prohibited": True,
        },
        "tooling": {
            "statistics_software": None,
            "reference_manager": None,
            "document_format": "docx",
        },
        "notes": "Fill only from verified project-owner information. Null means not yet assessed.",
    }


def build_default_ledger(project_id: str) -> dict[str, Any]:
    phases = []
    for index, (phase_id, name) in enumerate(THESIS_PHASES):
        phases.append({
            "phase_id": phase_id,
            "phase_name": name,
            "execution_status": "NOT_STARTED",
            "validation_status": "NOT_RUN",
            "human_acceptance_status": "PENDING",
            "approval_status": "PENDING",
            "authorization_status": "NOT_AUTHORIZED",
            "phase_conclusion": "NOT_STARTED",
            "dependencies": [THESIS_PHASES[index - 1][0]] if index else [],
            "scope": None,
            "evidence": [],
            "blockers": ["Intake and phase-specific approval/authorization have not been recorded."],
            "last_verified_at": None,
            "next_action": "Complete prior gates and record explicit phase authorization before execution.",
        })
    return {
        "schema_version": "1.0.0",
        "ledger_id": f"THESIS-LEDGER-{project_id.upper()}",
        "project_id": project_id,
        "workflow_id": "thesis-lifecycle-v1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "current_phase": "T0",
        "current_work_item": "INTAKE_PENDING",
        "phases": phases,
        "transition_policy": {
            "sequential_only": True,
            "predecessor_must_be_complete_and_approved": True,
            "phase_specific_authorization_required": True,
            "human_acceptance_required": True,
            "ai_self_approval_forbidden": True,
        },
    }


def init_project(
    workspace_root: Path,
    *,
    project_id: str,
    title: str,
    discipline: str,
    research_design: str,
    institution: str,
    programme: str = "",
    language: str = "id-ID",
) -> Path:
    validate_project_id(project_id)
    for label, value in (("title", title), ("discipline", discipline), ("research_design", research_design), ("institution", institution)):
        if not value.strip():
            raise ValidationError(f"{label} must not be blank")
    root = workspace_root.expanduser().resolve()
    project_dir = (root / project_id).resolve()
    if project_dir.parent != root:
        raise ValidationError("project path escaped workspace root")
    if project_dir.exists():
        raise FileExistsError(f"workspace already exists: {project_dir}")

    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    _restrict_private_permissions(root, 0o700)
    project_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    _restrict_private_permissions(project_dir, 0o700)
    try:
        for relative in WORKSPACE_DIRS:
            subdir = project_dir / relative
            subdir.mkdir(parents=True, exist_ok=True, mode=0o700)
            _restrict_private_permissions(subdir, 0o700)
        _write_json(project_dir / "project.json", build_default_manifest(
            project_id, title, discipline, research_design, institution, programme, language
        ))
        _write_json(project_dir / "state" / "phase_ledger.json", build_default_ledger(project_id))
        _write_json(project_dir / "state" / "approval_register.json", {
            "schema_version": "1.0.0", "project_id": project_id, "approvals": []
        })
        _write_json(project_dir / "sources" / "registry" / "source_register.json", {
            "schema_version": "1.0.0", "project_id": project_id,
            "sources": [], "claim_evidence_links": []
        })
        _write_json(project_dir / "methodology" / "design" / "methodology_profile.json", {
            "schema_version": "1.0.0", "project_id": project_id,
            "research_design": research_design, "research_question_ids": [],
            "population_or_case_definition": None, "sampling_strategy": None,
            "sample_size_rationale": None, "variables_or_constructs": [],
            "instrument_and_validity_plan": None, "data_sources": [],
            "data_collection_protocol": None, "qualitative_coding_approach": None,
            "integration_strategy": None, "analysis_plan": {},
            "assumptions_and_diagnostics": [], "ethics_and_permissions": None,
            "limitations": [], "software_candidates": []
        })
        _write_json(project_dir / "methodology" / "design" / "research_alignment.json", {
            "schema_version": "1.0.0", "project_id": project_id,
            "research_design": research_design, "research_questions": [], "objectives": [],
            "constructs": [], "hypotheses": [], "analysis_plan": [], "integration_points": []
        })
        _write_json(project_dir / "analysis" / "design" / "analysis_specification.json", {
            "schema_version": "1.0.0", "project_id": project_id,
            "analysis_id": "ANALYSIS-001", "analysis_plan_id": None,
            "research_question_ids": [], "dataset_artifact_id": None,
            "method": None, "justification": None,
            "human_method_approval": "NOT_GRANTED", "human_method_approval_reference": None, "variables": [],
            "missing_value_tokens": [""], "small_cell_suppression_threshold": 5,
            "assumption_review_notes": []
        })
        _write_json(project_dir / "manuscript" / "document_specification.json", {
            "schema_version": "1.0.0", "project_id": project_id, "document_id": "THESIS-DRAFT-001",
            "title": title, "language": language, "citation_style": "APA7",
            "institution_profile": {"path": None, "sha256": None, "approval_reference": None},
            "output": {
                "filename": "thesis-draft.docx", "include_cover": True, "include_toc": True,
                "include_bibliography": True, "page_size": "A4",
                "formatting": {
                    "font_family": "Times New Roman", "font_size_pt": 12, "line_spacing": 1.5,
                    "first_line_indent_cm": 1.25, "space_after_pt": 0,
                    "margins_cm": {"top": 3.0, "right": 2.5, "bottom": 2.5, "left": 3.0},
                    "heading_sizes_pt": {"1": 14, "2": 12, "3": 12}
                }
            },
            "sections": [{"section_id": "BAB-I", "heading": "BAB I PENDAHULUAN", "level": 1, "blocks": []}]
        })
        _write_json(project_dir / "decisions" / "decision_register.json", {
            "schema_version": "1.0.0", "project_id": project_id, "decisions": []
        })
        private_readme = project_dir / "README.private.md"
        private_readme.write_text(
            f"# Private thesis workspace: {project_id}\n\n"
            "This directory is local-only by default. Do not move it into a public repository.\n\n"
            "Start with `project-skripsi validate <workspace>` and complete T0 intake.\n",
            encoding="utf-8",
        )
        _restrict_private_permissions(private_readme, 0o600)
        intake = project_dir / "intake" / "INTAKE_CHECKLIST.md"
        intake.write_text(
            "# Thesis project intake checklist\n\n"
            "Complete only with information verified by the student or current official documents.\n\n"
            "## Project scope\n- Working title: \n- Discipline/programme: \n- Research problem in the student's own words: \n- Research questions/objectives: \n- Required deliverables and deadlines: \n\n"
            "## Institutional requirements\n- Institution and programme: \n- Official guideline title/version/date: \n- Required chapter structure: \n- Citation style and template: \n- AI-use disclosure rule (verified / unknown): \n\n"
            "## Research design (provisional until reviewed)\n- Design: \n- Population/case and unit of analysis: \n- Sampling/data sources: \n- Planned instruments/protocol: \n- Planned analysis and why it fits: \n\n"
            "## Evidence and permissions\n- Existing drafts/files received: \n- Source access constraints: \n- Ethics/permission/consent status: \n- Personal or sensitive data present (yes/no/unknown): \n- Approved storage and external-transfer constraints: \n\n"
            "## T0 gate\n- [ ] Requirements and deadline checked against current institutional source.\n"
            "- [ ] Student has reviewed and confirmed the scope.\n"
            "- [ ] Missing facts are marked unknown, not guessed.\n"
            "- [ ] T0 authorization is separately recorded by an authorized human.\n",
            encoding="utf-8",
        )
        _restrict_private_permissions(intake, 0o600)
        guideline_readme = project_dir / "requirements" / "institution" / "PROFILE_README.md"
        guideline_readme.write_text(
            "# Institutional guideline profile\n\n"
            "Store the current official guide in the private project workspace only when permitted. "
            "Record its exact version, effective date, source URL, retrieval timestamp and SHA-256. "
            "Do not assume an old cohort's guideline is current. Mark profiles UNREVIEWED until a human checks them.\n",
            encoding="utf-8",
        )
        _restrict_private_permissions(guideline_readme, 0o600)
        append_audit_event(
            project_dir / "audit" / "events.jsonl",
            event_type="project.created",
            object_type="thesis_project",
            object_id=project_id,
            summary="Created an empty, local-only thesis workspace from the reusable template.",
        )
        _restrict_private_permissions(project_dir / "audit" / "events.jsonl", 0o600)
    except Exception:
        # Remove only the directory created by this call; never clean a pre-existing path.
        import shutil
        shutil.rmtree(project_dir, ignore_errors=True)
        raise
    return project_dir


def create_methodology_alignment_scaffold(project_dir: Path) -> Path:
    """Add the v0.4.0 alignment scaffold to an existing project without overwriting."""
    requested = project_dir.expanduser()
    if not requested.is_absolute():
        requested = Path.cwd() / requested
    for component in reversed((requested, *requested.parents)):
        if component.is_symlink():
            raise ValidationError(f"workspace path contains a symlink component: {component}")
    project_dir = requested.resolve(strict=True)
    if not project_dir.is_dir():
        raise FileNotFoundError(f"workspace does not exist: {project_dir}")
    manifest_path = project_dir / "project.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot read project manifest: {exc}") from exc
    project_id = manifest.get("project_id") if isinstance(manifest, dict) else None
    research_design = manifest.get("research_design") if isinstance(manifest, dict) else None
    if not isinstance(project_id, str) or not isinstance(research_design, str):
        raise ValidationError("project manifest must contain project_id and research_design")
    if project_dir.name != project_id:
        raise ValidationError("workspace directory name does not match project_id")
    output = project_dir / "methodology" / "design" / "research_alignment.json"
    for component in (project_dir / "methodology", output.parent):
        if component.is_symlink():
            raise ValidationError(f"research alignment parent directory is a symlink: {component}")
    payload = json.dumps({
        "schema_version": "1.0.0", "project_id": project_id,
        "research_design": research_design, "research_questions": [], "objectives": [],
        "constructs": [], "hypotheses": [], "analysis_plan": [], "integration_points": []
    }, ensure_ascii=False, indent=2) + "\n"
    try:
        with output.open("x", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        _restrict_private_permissions(output, 0o600)
    except FileExistsError:
        raise FileExistsError(f"research alignment already exists: {output}")
    except Exception:
        try:
            output.unlink()
        except OSError:
            pass
        raise
    return output


def project_status(project_dir: Path) -> dict[str, Any]:
    errors, manifest, ledger = validate_workspace(project_dir)
    if errors or manifest is None or ledger is None:
        raise ValidationError("; ".join(errors) or "workspace is invalid")
    phases = ledger["phases"]
    current = next((p for p in phases if p["phase_conclusion"] != "COMPLETE_AND_APPROVED"), phases[-1])
    return {
        "project_id": manifest["project_id"],
        "title": manifest["title"],
        "current_phase": current["phase_id"],
        "phase_name": current["phase_name"],
        "execution_status": current["execution_status"],
        "validation_status": current["validation_status"],
        "human_acceptance_status": current["human_acceptance_status"],
        "authorization_status": current["authorization_status"],
        "workspace_path": str(project_dir.resolve()),
        "classification": manifest["privacy"]["classification"],
        "storage_mode": manifest["privacy"]["storage_mode"],
    }
