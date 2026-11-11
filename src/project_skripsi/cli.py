"""Command-line interface for private thesis workspaces."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audit import verify_audit_log
from .quality import methodology_readiness, validate_analysis_run, validate_claim_evidence_links, validate_source_register
from .methodology import audit_research_alignment
from .service import create_methodology_alignment_scaffold, init_project, project_status
from .research import build_literature_matrix, recover_research_transactions, research_integrity_check, search_project_literature
from .integrations.crossref import verify_doi
from .statistics import (
    StatisticalEngineError, build_analysis_scaffold, register_dataset,
    run_descriptive_analysis, validate_analysis_specification, verify_analysis_run, reproduce_analysis_run,
    summarize_analysis_diagnostics,
)
from .writing.patterns import assess_claim_strength, list_patterns
from .writing.revision import LocalOpenAICompatibleClient, audit_revision, build_revision_prompt, write_revision_report
from .validation import ValidationError, load_json, validate_workspace
from .documents import (DocumentEngineError, create_document_scaffold, build_document, verify_document_build, audit_docx_structure)
from .revision_qa import (
    RevisionQAError, audit_before_after_pairs, audit_marked_region_register,
    audit_empirical_study_consistency, audit_artifact_manifest, write_report,
)
from .turnitin_reports import TurnitinReportError, audit_turnitin_report, compare_turnitin_reports


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="project-skripsi", description="Local-first thesis workspace engine")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create an isolated private workspace")
    init.add_argument("--project-id", required=True)
    init.add_argument("--title", required=True)
    init.add_argument("--discipline", required=True)
    init.add_argument("--research-design", required=True)
    init.add_argument("--institution", required=True)
    init.add_argument("--programme", default="")
    init.add_argument("--language", default="id-ID")
    init.add_argument("--workspace-root", type=Path, default=Path(".private/workspaces"))

    validate = commands.add_parser("validate", help="validate manifest, phase gates and audit chain")
    validate.add_argument("workspace", type=Path)

    status = commands.add_parser("status", help="show the earliest unaccepted thesis phase")
    status.add_argument("workspace", type=Path)

    sources = commands.add_parser("validate-sources", help="check a JSON source register without network access")
    sources.add_argument("source_register", type=Path)

    method_scaffold = commands.add_parser("methodology-scaffold", help="add the v0.4.0 research-alignment file to an older workspace without overwriting")
    method_scaffold.add_argument("workspace", type=Path)

    methods = commands.add_parser("methodology-check", help="report design-specific methodology fields that remain missing")
    methods.add_argument("methodology_profile", type=Path)

    method_audit = commands.add_parser("methodology-audit", help="audit research-question/objective/construct/hypothesis/analysis alignment")
    method_audit.add_argument("alignment_document", type=Path)
    method_audit.add_argument("--profile", type=Path, help="optional methodology_profile.json for cross-register checks")
    method_audit.add_argument("--source-register", type=Path, help="optional project source_register.json for theory/instrument reference checks")
    method_audit.add_argument("--output", type=Path, help="optional local JSON report path; refuses to overwrite")

    analysis = commands.add_parser("validate-analysis", help="validate reproducibility metadata for an analysis run")
    analysis.add_argument("analysis_record", type=Path)

    dataset_register = commands.add_parser("dataset-register", help="register and profile a workspace-contained CSV with privacy/provenance metadata")
    dataset_register.add_argument("workspace", type=Path)
    dataset_register.add_argument("dataset_path", type=Path, help="CSV path relative to workspace or absolute inside the workspace")
    dataset_register.add_argument("--artifact-id", required=True)
    dataset_register.add_argument("--origin", required=True, help="verified dataset origin or provenance description")
    dataset_register.add_argument("--artifact-type", choices=["RAW_DATA", "PROCESSED_DATA", "SECONDARY_DATASET"], default="RAW_DATA")
    dataset_register.add_argument("--privacy-classification", choices=["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"], default="CONFIDENTIAL")
    dataset_register.add_argument("--permission-status", choices=["NOT_REQUIRED", "PENDING", "APPROVED", "DENIED", "UNKNOWN"], default="UNKNOWN")
    dataset_register.add_argument("--missing-token", action="append", default=None, help="explicit value treated as missing; may be repeated")

    analysis_scaffold = commands.add_parser("analysis-scaffold", help="add a blank v0.5 analysis specification without overwriting")
    analysis_scaffold.add_argument("workspace", type=Path)

    analysis_check = commands.add_parser("analysis-spec-check", help="validate a human-approved descriptive analysis specification")
    analysis_check.add_argument("workspace", type=Path)
    analysis_check.add_argument("specification", type=Path)

    analysis_run = commands.add_parser("analysis-run", help="execute approved descriptive summaries and persist reproducibility metadata")
    analysis_run.add_argument("workspace", type=Path)
    analysis_run.add_argument("specification", type=Path)
    analysis_run.add_argument("--run-id", help="optional unique run identifier; existing run directories are never overwritten")

    analysis_verify = commands.add_parser("analysis-verify", help="verify hashes, linked inputs and audit evidence for a statistical run")
    analysis_verify.add_argument("workspace", type=Path)
    analysis_verify.add_argument("run_id")

    analysis_recover = commands.add_parser("analysis-recover", help="recover prepared descriptive-analysis transactions after interruption")
    analysis_recover.add_argument("workspace", type=Path)

    analysis_reproduce = commands.add_parser(
        "analysis-reproduce", help="recompute a completed descriptive run read-only and compare result SHA-256"
    )
    analysis_reproduce.add_argument("workspace", type=Path)
    analysis_reproduce.add_argument("run_id")

    analysis_diagnostics = commands.add_parser(
        "analysis-diagnostics", help="summarize saved descriptive data-quality diagnostics read-only"
    )
    analysis_diagnostics.add_argument("workspace", type=Path)
    analysis_diagnostics.add_argument("run_id")

    brief = commands.add_parser("revision-brief", help="build an evidence-safe revision prompt without sending text anywhere")
    brief.add_argument("input", type=Path)
    brief.add_argument("--language", default="id-ID")
    brief.add_argument("--purpose", choices=["clarity", "grammar", "flow", "conciseness", "academic_register"], default="clarity")
    brief.add_argument("--claim-id")
    brief.add_argument("--source-id", action="append", default=[])
    brief.add_argument("--output", type=Path)

    local_revise = commands.add_parser("local-revise", help="request a language revision from a loopback-only local model endpoint")
    local_revise.add_argument("input", type=Path)
    local_revise.add_argument("--model", required=True)
    local_revise.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    local_revise.add_argument("--language", default="id-ID")
    local_revise.add_argument("--purpose", choices=["clarity", "grammar", "flow", "conciseness", "academic_register"], default="clarity")
    local_revise.add_argument("--output", type=Path, required=True)

    revision_audit = commands.add_parser("revision-audit", help="compare source and candidate without plagiarism/AI-detector scoring")
    revision_audit.add_argument("original", type=Path)
    revision_audit.add_argument("candidate", type=Path)
    revision_audit.add_argument("--language", default="id-ID")
    revision_audit.add_argument("--output", type=Path, required=True)

    patterns = commands.add_parser("writing-patterns", help="list original evidence-safe academic writing patterns")
    patterns.add_argument("--stage", choices=["introduction", "literature_review", "results", "discussion", "limitations", "conclusion", "recommendation"])

    claim_check = commands.add_parser("claim-strength-check", help="flag overclaim risk; never self-approves academic claims")
    claim_check.add_argument("--evidence-level", choices=["none", "contextual", "observational", "direct", "convergent"], required=True)
    claim_check.add_argument("--requested-strength", choices=["tentative", "bounded", "assertive", "causal"], required=True)
    claim_check.add_argument("--research-design", required=True)
    claim_check.add_argument("--causal-identification-reviewed", action="store_true")
    claim_check.add_argument("--human-reviewer-role")

    doi_check = commands.add_parser("verify-doi", help="retrieve DOI bibliographic metadata from Crossref (metadata-only; no manuscript text sent)")
    doi_check.add_argument("doi")
    doi_check.add_argument("--expected", type=Path, help="optional JSON object with title, authors, year and/or container-title")
    doi_check.add_argument("--cache-dir", type=Path, default=Path(".private/cache/crossref"))
    doi_check.add_argument("--mailto", help="optional contact email for Crossref polite pool")
    doi_check.add_argument("--output", type=Path)

    research_search = commands.add_parser(
        "research-search",
        help="search OpenAlex and persist project-scoped source provenance (metadata-only by default)",
    )
    research_search.add_argument("workspace", type=Path)
    research_search.add_argument("--query", required=True, help="public scholarly search query; do not pass confidential manuscript text")
    research_search.add_argument("--per-page", type=int, default=10, help="number of results to request (1-25)")
    research_search.add_argument("--include-abstracts", action="store_true", help="explicitly retrieve and save OpenAlex-reconstructed abstracts")
    research_search.add_argument("--mailto", help="optional contact email for OpenAlex polite pool")
    research_search.add_argument("--no-cache", action="store_true", help="bypass the private 24-hour cache")

    matrix = commands.add_parser(
        "literature-matrix",
        help="generate a private CSV literature matrix and coverage summary without inventing analysis",
    )
    matrix.add_argument("workspace", type=Path)
    matrix.add_argument("--output", type=Path, help="optional .csv path inside the workspace literature/matrix directory")

    integrity = commands.add_parser(
        "research-integrity",
        help="read-only check of OpenAlex snapshots, source register, recovery journals and audit chain",
    )
    integrity.add_argument("workspace", type=Path)

    recover = commands.add_parser(
        "recover-research",
        help="resume interrupted OpenAlex snapshot/source-register/audit persistence transactions",
    )
    recover.add_argument("workspace", type=Path)

    doc_scaffold = commands.add_parser("document-scaffold", help="create a blank evidence-linked thesis document specification without overwriting")
    doc_scaffold.add_argument("workspace", type=Path)

    doc_build = commands.add_parser("document-build", help="build an evidence-linked, unreviewed DOCX/PDF draft with a page-mapped TOC")
    doc_build.add_argument("workspace", type=Path)
    doc_build.add_argument("specification", nargs="?", type=Path, default=Path("manuscript/document_specification.json"))

    doc_verify = commands.add_parser("document-verify", help="verify document build hashes, source pins, analysis runs and audit event")
    doc_verify.add_argument("workspace", type=Path)
    doc_verify.add_argument("document_id")

    doc_audit = commands.add_parser("document-audit", help="inspect DOCX package integrity, headings, tables and image relationships")
    doc_audit.add_argument("docx", type=Path)

    pairs_audit = commands.add_parser("revision-pairs-audit", help="verify every SEBELUM/SESUDAH pair against original and candidate DOCX files")
    pairs_audit.add_argument("bubble_text", type=Path)
    pairs_audit.add_argument("candidate_docx", type=Path)
    pairs_audit.add_argument("--original-docx", type=Path)
    pairs_audit.add_argument("--max-window", type=int, default=5)
    pairs_audit.add_argument("--output", type=Path)

    region_audit = commands.add_parser("marked-region-audit", help="audit stable IDs, mapping confidence, evidence state and dispositions in a marking register")
    region_audit.add_argument("register_csv", type=Path)
    region_audit.add_argument("--output", type=Path)

    consistency_audit = commands.add_parser("empirical-consistency-audit", help="check sample counts, measures, paired IDs, reliability and design-to-claim consistency from a declared JSON study model")
    consistency_audit.add_argument("study_model", type=Path)
    consistency_audit.add_argument("--output", type=Path)

    manifest_audit = commands.add_parser("artifact-manifest-audit", help="verify artifact SHA-256 and byte counts in a relative-path bundle manifest")
    manifest_audit.add_argument("manifest", type=Path)
    manifest_audit.add_argument("--output", type=Path)

    turnitin_audit = commands.add_parser("turnitin-report-audit", help="extract Turnitin report metadata, top sources and visible source badges without storing thesis text")
    turnitin_audit.add_argument("pdf", type=Path)
    turnitin_audit.add_argument("--output", type=Path, required=True)

    turnitin_compare = commands.add_parser("turnitin-report-compare", help="compare two Turnitin report exports on visible settings and score metadata")
    turnitin_compare.add_argument("baseline_pdf", type=Path)
    turnitin_compare.add_argument("current_pdf", type=Path)
    turnitin_compare.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            path = init_project(
                args.workspace_root,
                project_id=args.project_id,
                title=args.title,
                discipline=args.discipline,
                research_design=args.research_design,
                institution=args.institution,
                programme=args.programme,
                language=args.language,
            )
            print(f"CREATED {path}")
            print("NEXT: complete T0 intake; no phase is automatically authorized.")
            return 0
        if args.command == "document-scaffold":
            output = create_document_scaffold(args.workspace)
            print(f"CREATED {output}")
            print("NOTICE: scaffold is blank; no thesis content, citations or institutional requirements were inferred.")
            return 0
        if args.command == "document-build":
            result = build_document(args.workspace, args.specification)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("NOTICE: generated output is DRAFT_NOT_REVIEWED; institutional compliance and academic correctness require human review.")
            return 0
        if args.command == "document-verify":
            result = verify_document_build(args.workspace, args.document_id)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command == "document-audit":
            result = audit_docx_structure(args.docx)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command == "revision-pairs-audit":
            result = audit_before_after_pairs(
                args.bubble_text, args.candidate_docx, args.original_docx,
                max_window=args.max_window,
            )
            if args.output:
                output = write_report(result, args.output)
                print(f"CREATED {output}")
            print(json.dumps({"status": result["status"], "summary": result["summary"], "parse_errors": result["parse_errors"]}, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command == "marked-region-audit":
            result = audit_marked_region_register(args.register_csv)
            if args.output:
                output = write_report(result, args.output)
                print(f"CREATED {output}")
            print(json.dumps({"status": result["status"], "summary": result["summary"]}, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command == "empirical-consistency-audit":
            study_model = load_json(args.study_model.expanduser().resolve())
            result = audit_empirical_study_consistency(study_model)
            if args.output:
                output = write_report(result, args.output)
                print(f"CREATED {output}")
            print(json.dumps({"status": result["status"], "finding_counts": result["finding_counts"], "findings": result["findings"]}, ensure_ascii=False, indent=2))
            return 0 if result["status"] in {"PASS", "PASS_WITH_NOTES"} else 1
        if args.command == "turnitin-report-audit":
            result = audit_turnitin_report(args.pdf)
            output = write_report(result, args.output)
            print(json.dumps({"status": result["status"], "report": result["report"], "source_entries_parsed": result["source_inventory"]["source_entries_parsed"], "source_badges": {k: v for k, v in result["body_source_badges"].items() if k != "occurrences"}, "output": str(output)}, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command == "turnitin-report-compare":
            result = compare_turnitin_reports(args.baseline_pdf, args.current_pdf)
            output = write_report(result, args.output)
            print(json.dumps({"status": result["status"], "change": result["change"], "comparability": result["comparability"], "output": str(output)}, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "COMPARABLE_VISIBLE_SETTINGS" else 1
        if args.command == "artifact-manifest-audit":
            result = audit_artifact_manifest(args.manifest)
            if args.output:
                output = write_report(result, args.output)
                print(f"CREATED {output}")
            print(json.dumps({"status": result["status"], "artifact_count": result["artifact_count"], "passed": result["passed"], "failed": result["failed"]}, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command == "validate":
            path = args.workspace.expanduser().resolve()
            errors, manifest, _ledger = validate_workspace(path)
            audit_ok, audit_reason = verify_audit_log(path / "audit" / "events.jsonl")
            if not audit_ok:
                errors.append(f"audit log: {audit_reason}")
            if errors:
                for error in errors:
                    print(f"FAIL: {error}", file=sys.stderr)
                return 1
            print(f"PASS: {manifest['project_id']} manifest and sequential phase gates")
            print(f"PASS: audit chain — {audit_reason}")
            return 0
        if args.command == "status":
            result = project_status(args.workspace.expanduser().resolve())
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "validate-sources":
            value = load_json(args.source_register.expanduser().resolve())
            records = value.get("sources")
            if not isinstance(records, list):
                raise ValidationError("source register must contain a top-level 'sources' array")
            errors = validate_source_register(records)
            claim_links = value.get("claim_evidence_links", [])
            if not isinstance(claim_links, list):
                raise ValidationError("claim_evidence_links must be an array")
            errors.extend(validate_claim_evidence_links(claim_links, records))
            if errors:
                for error in errors:
                    print(f"FAIL: {error}", file=sys.stderr)
                return 1
            print(f"PASS: {len(records)} source record(s), {len(claim_links)} claim link(s)")
            print("NOTICE: URL syntax and provenance completeness are checked; source truth is not automatically verified.")
            return 0
        if args.command == "methodology-scaffold":
            output = create_methodology_alignment_scaffold(args.workspace)
            print(f"CREATED {output}")
            print("NOTICE: scaffold is blank; no questions, variables, hypotheses or methods were inferred.")
            return 0
        if args.command == "methodology-check":
            profile = load_json(args.methodology_profile.expanduser().resolve())
            result = methodology_readiness(profile)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ready_for_methodology_review"] else 1
        if args.command == "methodology-audit":
            alignment = load_json(args.alignment_document.expanduser().resolve())
            profile = load_json(args.profile.expanduser().resolve()) if args.profile else None
            source_register = load_json(args.source_register.expanduser().resolve()) if args.source_register else None
            result = audit_research_alignment(alignment, methodology_profile=profile, source_register=source_register)
            payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                output = args.output.expanduser().resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("x", encoding="utf-8") as stream:
                    stream.write(payload)
                    stream.flush()
                try:
                    output.chmod(0o600)
                except OSError:
                    pass
                print(f"CREATED {output}")
                print(json.dumps({"status": result["status"], "summary": result["summary"], "human_approval": result["human_approval"]}, ensure_ascii=False, indent=2))
            else:
                print(payload, end="")
            return 1 if result["status"] == "NEEDS_REVISION" else 0
        if args.command == "revision-brief":
            original = args.input.expanduser().resolve().read_text(encoding="utf-8")
            prompt = build_revision_prompt(original, language=args.language, purpose=args.purpose, claim_id=args.claim_id, source_ids=args.source_id)
            if args.output:
                output = args.output.expanduser().resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(prompt, encoding="utf-8")
                try:
                    output.chmod(0o600)
                except OSError:
                    pass
                print(f"CREATED {output}")
                print("NOTICE: prompt generation is local; no model or external service was called.")
            else:
                print(prompt)
            return 0
        if args.command == "local-revise":
            original = args.input.expanduser().resolve().read_text(encoding="utf-8")
            client = LocalOpenAICompatibleClient(args.base_url)
            candidate = client.revise(original, model=args.model, language=args.language, purpose=args.purpose)
            output = args.output.expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(candidate + "\n", encoding="utf-8")
            try:
                output.chmod(0o600)
            except OSError:
                pass
            print(f"CREATED {output}")
            print("NOTICE: candidate is unapproved; run revision-audit and perform human semantic review.")
            return 0
        if args.command == "revision-audit":
            original = args.original.expanduser().resolve().read_text(encoding="utf-8")
            candidate = args.candidate.expanduser().resolve().read_text(encoding="utf-8")
            report = audit_revision(original, candidate, language=args.language)
            output = args.output.expanduser().resolve()
            write_revision_report(report, output)
            print(json.dumps({"status": report["status"], "flags": report["flags"], "report": str(output)}, ensure_ascii=False, indent=2))
            return 1 if report["flags"] else 0
        if args.command == "writing-patterns":
            print(json.dumps(list_patterns(args.stage), ensure_ascii=False, indent=2))
            return 0
        if args.command == "claim-strength-check":
            result = assess_claim_strength(
                evidence_level=args.evidence_level,
                requested_strength=args.requested_strength,
                research_design=args.research_design,
                causal_identification_reviewed=args.causal_identification_reviewed,
                human_reviewer_role=args.human_reviewer_role,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if result["status"] in {"OVERCLAIM_RISK", "HIGH_RISK_REVIEW_REQUIRED"} else 0
        if args.command == "literature-matrix":
            result = build_literature_matrix(args.workspace, output_path=args.output)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "research-integrity":
            result = research_integrity_check(args.workspace)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command == "analysis-recover":
            from .statistics import recover_analysis_transactions
            result = recover_analysis_transactions(args.workspace)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command == "analysis-reproduce":
            result = reproduce_analysis_run(args.workspace, args.run_id)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "REPRODUCED" else 1
        if args.command == "analysis-diagnostics":
            result = summarize_analysis_diagnostics(args.workspace, args.run_id)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command == "recover-research":
            result = recover_research_transactions(args.workspace)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "research-search":
            result = search_project_literature(
                args.workspace,
                args.query,
                per_page=args.per_page,
                include_abstracts=args.include_abstracts,
                mailto=args.mailto,
                use_cache=not args.no_cache,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "verify-doi":
            expected = load_json(args.expected.expanduser().resolve()) if args.expected else None
            report = verify_doi(
                args.doi,
                expected=expected,
                cache_dir=args.cache_dir.expanduser().resolve(),
                mailto=args.mailto,
            )
            rendered = json.dumps(report, ensure_ascii=False, indent=2)
            if args.output:
                output = args.output.expanduser().resolve()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered + "\n", encoding="utf-8")
                try:
                    output.chmod(0o600)
                except OSError:
                    pass
                print(f"CREATED {output}")
                print(f"STATUS: {report['status']}")
            else:
                print(rendered)
            return 1 if report["status"] in {"DOI_NOT_FOUND_IN_CROSSREF", "METADATA_MISMATCH_REVIEW_REQUIRED"} else 0
        if args.command == "validate-analysis":
            record = load_json(args.analysis_record.expanduser().resolve())
            errors = validate_analysis_run(record)
            if errors:
                for error in errors:
                    print(f"FAIL: {error}", file=sys.stderr)
                return 1
            print("PASS: analysis-run reproducibility metadata is structurally complete")
            print("NOTICE: this does not prove statistical correctness or independent reproduction.")
            return 0
        if args.command == "dataset-register":
            result = register_dataset(
                args.workspace, args.dataset_path, artifact_id=args.artifact_id, origin=args.origin,
                artifact_type=args.artifact_type, privacy_classification=args.privacy_classification,
                permission_status=args.permission_status, missing_tokens=args.missing_token,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "analysis-scaffold":
            output = build_analysis_scaffold(args.workspace)
            print(f"CREATED {output}")
            print("NOTICE: no dataset, method, research question, variable mapping or approval was inferred.")
            return 0
        if args.command == "analysis-spec-check":
            workspace = args.workspace.expanduser().resolve()
            specification_path = args.specification.expanduser()
            if not specification_path.is_absolute():
                specification_path = workspace / specification_path
            from .statistics import _safe_path, _read_json
            specification = _read_json(_safe_path(workspace, specification_path, must_exist=True))
            errors = validate_analysis_specification(workspace, specification)
            if errors:
                for error in errors:
                    print(f"FAIL: {error}", file=sys.stderr)
                return 1
            print("PASS: explicit project, data, method and construct links; human methodology approval recorded")
            print("NOTICE: this is a structural/execution-scope gate, not independent academic approval of the analysis choice.")
            return 0
        if args.command == "analysis-run":
            result = run_descriptive_analysis(args.workspace, args.specification, run_id=args.run_id)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("NOTICE: descriptive summaries only; no inferential test, imputation or causal interpretation was performed.")
            return 0
        if args.command == "analysis-verify":
            result = verify_analysis_run(args.workspace, args.run_id)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
    except (ValidationError, StatisticalEngineError, DocumentEngineError, RevisionQAError, TurnitinReportError, FileExistsError, OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
