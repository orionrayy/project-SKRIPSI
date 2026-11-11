# Project-SKRIPSI

**Universal Academic Research, Thesis Engineering & Reproducible QA Platform**  
Platform release: **0.8.0** · Python 3.10+ · local-first · human-governed

Repository: https://github.com/orionrayy/project-SKRIPSI

## Purpose

Project-SKRIPSI is a reusable framework for evidence-grounded academic research and thesis workflows. It separates platform engineering from the reference research programme and from each individual thesis workspace. It supports source provenance, methodology gates, descriptive analysis reproducibility, document engineering, revision traceability, Turnitin-report metadata QA and empirical-consistency checks.

It is not a thesis-substitution service. It must not fabricate sources, data, findings, approvals or human reviewers; conceal plagiarism; misrepresent authorship; bypass source access controls; or optimize prose to evade similarity/AI detectors. The student remains responsible for the intellectual work, evidence, interpretation and institutional disclosure.

## Current research-governance checkpoint

The canonical source is `config/pipeline/PHASE_LEDGER.json` (ledger 2.3.0). Platform test results do not advance research phases.

| Phase | Current status | Boundary |
|---|---|---|
| P0 — Research Charter & Integrity | `COMPLETE_AND_APPROVED` | APR-P0-001; scoped governance approval |
| P1 — Cross-Domain Thesis Corpus | `COMPLETE_AND_APPROVED` | APR-P1-001; 50-record bibliographic eligibility corpus only, with access limitations |
| P2 — Thesis Extraction & Coding | `VALIDATION_PASSED_APPROVAL_PENDING` | AUTH-P2-001; 214 abstract-level observations; human acceptance record APR-P2-001 remains blank |
| P3–P9 | `NOT_STARTED / NOT_AUTHORIZED` | Each phase requires predecessor acceptance and its own authorization |

P1 is not 50 full-text-reviewed theses. P2 is abstract-bounded, not thesis full-text coding. P2's second independent coder remains `NOT_RUN`; semantic review remains `SELF_REVIEW_ONLY`. Do not treat absence from an abstract as evidence that the full thesis lacks a method, instrument, result or approval. The next research action remains P2 human acceptance, not P3 execution.

A public aggregate-only research status is in `docs/research/P0_P1_P2_PUBLIC_STATUS.md`. The private P1/P2 packages, record-level observations, abstracts, source registers and coverage data are intentionally not included in this public repository.

## Platform capabilities (v0.8.0)

- Isolated project workspaces and T0–T9 phase ledgers.
- Claim-to-source provenance with exact locators and distinct access states.
- Methodology/research-question alignment and approval gates.
- Descriptive statistical summaries with privacy suppression, audit events, stable hashes, recovery and same-engine replay.
- Evidence-linked DOCX/PDF document engineering and document verification.
- Before/after revision-pair auditing and marked-region coverage checks.
- Empirical study consistency checks for sample counts, constructs, instrument validation, ICC configuration, paired-test evidence and interpretation boundaries.
- Local Turnitin report auditing/comparison for visible metadata, exclusions and source inventories. It does not make plagiarism verdicts or AI-detection predictions.

See `docs/operations/QUICKSTART.md`, `docs/platform/REUSABLE_PLATFORM_ARCHITECTURE.md`, and `docs/quality/ACADEMIC_QA_ACCEPTANCE_MATRIX.md`.

## Complete expanded source tree

The complete sanitized platform implementation is expanded directly in this repository: application source (`src/project_skripsi/`), JSON schemas (`schemas/`), regression tests (`tests/`), reusable templates (`templates/`), operations and governance documentation (`docs/`, `config/`, `prompts/`), automation (`scripts/`, `.github/workflows/`), and the public integrity manifest (`MANIFEST.sha256`). No private thesis or record-level research package is part of this tree.

The immutable transfer bundle is also published at [`dist/project-SKRIPSI-public-source-v0.8.0-expanded.tar.xz`](dist/project-SKRIPSI-public-source-v0.8.0-expanded.tar.xz), with a separate SHA-256 sidecar. The archive is a sanitized snapshot; its contents are expanded into the repository root by the one-shot publication workflow.

## Install and validate

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/validate_phase_ledger.py
python scripts/verify_manifest.py
```

Optional extras are declared in `pyproject.toml`. The local PDF report parser requires the `pdf-qa` extra. Do not point tools at private thesis paths from this public repository; create a private workspace and review its governance/authorization first.

## Public/private boundary

This repository contains platform source, generic governance, schemas, synthetic tests and aggregate phase status only. It excludes private thesis manuscripts, Turnitin PDFs, individual reports/identifiers, participant identities/scores, record-level P1/P2 data, abstracts, source registers, adjudication logs, private archives, databases, caches, credentials and `.env` files. The corresponding private research packages remain outside Git. Public visibility is not a license grant; no separate software license is declared in this repository.

The generic quality lessons from private case review are documented without source text or case identifiers in `docs/quality/THESIS_CASE_LEARNING_PUBLIC.md`.

## Engineering status

Platform v0.8.0 regression suite: **200/200 PASS**; JSON Schemas: **29/29 PASS** (Draft 2020-12); compileall, phase-ledger validator and CLI smoke tests: PASS in the recorded local release validation. GitHub Actions and native Windows runner remain separate checks; do not claim CI passed until an actual workflow run reports success.

See `CHANGELOG.md` and `ORCHESTRATION_MEMORY.md` for provenance and dated checkpoints. The canonical phase ledger is never to be changed to simulate human acceptance.
