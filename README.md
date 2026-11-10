# Project-SKRIPSI

**Universal Academic Research, Thesis Engineering & Reproducible QA Platform**  
Platform baseline: **0.8.0** · Python 3.10+ · local-first · human-governed

Repository: https://github.com/orionrayy/project-SKRIPSI

## Purpose

Project-SKRIPSI is a reusable framework for evidence-grounded academic research and thesis workflows. It separates platform engineering from the reference research programme and from each individual thesis workspace. Capabilities include source provenance, methodology gates, descriptive-analysis reproducibility, evidence-linked document engineering, revision traceability, empirical consistency checks, and local Turnitin-report metadata QA.

It is not a thesis-substitution service. It must not fabricate sources, data, findings, approvals or human reviewers; conceal plagiarism; misrepresent authorship; bypass source access controls; or optimize prose to evade similarity/AI detectors. The student remains responsible for the intellectual work, evidence, interpretation and institutional disclosure.

## Repository contents

The complete sanitized source tree, schemas, synthetic tests, CI workflow, governance snapshot and public aggregate phase summaries are packaged in:

- `dist/project-SKRIPSI-public-source-v0.8.0.tar.gz`
- `dist/project-SKRIPSI-public-source-v0.8.0.tar.gz.sha256`

The bundle contains the normal Python project layout. Extract it to obtain `pyproject.toml`, `src/project_skripsi/`, `schemas/`, `tests/`, `docs/` and project governance files.

## Current research-governance checkpoint

The canonical source is `config/pipeline/PHASE_LEDGER.json` (ledger 2.3.0). Platform test results do not advance research phases.

| Phase | Current status | Boundary |
|---|---|---|
| P0 — Research Charter & Integrity | `COMPLETE_AND_APPROVED` | APR-P0-001; scoped governance approval |
| P1 — Cross-Domain Thesis Corpus | `COMPLETE_AND_APPROVED` | APR-P1-001; 50-record bibliographic eligibility corpus only |
| P2 — Thesis Extraction & Coding | `VALIDATION_PASSED_APPROVAL_PENDING` | AUTH-P2-001; 214 abstract-level observations; APR-P2-001 remains blank |
| P3–P9 | `NOT_STARTED / NOT_AUTHORIZED` | Each phase requires predecessor acceptance and its own authorization |

P1 is not 50 full-text-reviewed theses. P2 is abstract-bounded, not thesis full-text coding. P2's second independent coder remains `NOT_RUN`; semantic review remains `SELF_REVIEW_ONLY`. P2 has not been accepted by the project owner. P3 remains locked.

A public aggregate-only research summary is included in `docs/research/P0_P1_P2_PUBLIC_STATUS.md`. P1/P2 record-level data remain private and are not part of this repository.

## Platform validation

Recorded local v0.8.0 release checks: **193/193 regression tests**, **29/29 JSON Schemas** (Draft 2020-12), compileall, phase-ledger validator and CLI smoke tests passed. These are platform engineering checks, not institutional certification or research-phase acceptance. GitHub CI must be checked from an actual workflow run before claiming remote CI success.

## Install and validate

After extracting the source bundle:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/validate_phase_ledger.py
python scripts/verify_manifest.py
```

Optional extras are declared in `pyproject.toml`. The local PDF report parser requires the `pdf-qa` extra.

## Public/private boundary

This public repository contains platform source, generic governance, synthetic tests and aggregate phase status only. It excludes private thesis manuscripts, Turnitin PDFs and case identifiers, individual reports/source labels, participant identities/scores, P1/P2 abstracts, source registers, row-level observations, private archives, databases, caches and credentials. The corresponding private research packages remain outside Git. Public visibility is not a license grant; no separate software license is declared.

See `docs/platform/PUBLIC_REPOSITORY_PUBLICATION.md`, `CHANGELOG.md` and `ORCHESTRATION_MEMORY.md` for the allowlist and provenance.
