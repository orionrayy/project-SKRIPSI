# ORCHESTRATION_MEMORY — Public Canonical Project Memory

**Memory version:** 1.4.0  
**Project:** `orionrayy/project-SKRIPSI`  
**Updated:** 2026-11-10 (Asia/Jakarta)  
**Platform baseline:** 0.8.0  
**Repository visibility:** public (pre-existing setting; no setting change made).

## 1. Source precedence and provenance

This file is the public, sanitized orchestration memory. The canonical phase state is `config/pipeline/PHASE_LEDGER.json`. Private working directories, per-record research data, source URLs/locators, abstracts, participant information, thesis files, Turnitin reports and private QA reports are deliberately excluded. Historical chat share URLs and private archive hashes are not reproduced here.

The public state derives from the validated governance bootstrap (ledger 2.3.0), public aggregate phase reports and the platform v0.8.0 source snapshot. The platform archive and this repository's Git commit are separate provenance records.

## 2. Research-governance state

- **P0 — COMPLETE_AND_APPROVED:** scoped governance baseline under APR-P0-001. This is not a blanket institutional, ethics, legal or privacy certification.
- **P1 — COMPLETE_AND_APPROVED:** accepted 50-record bibliographic eligibility corpus, within APR-P1-001 scope. It is not a full-text-reviewed or systematically coded thesis corpus. Access profile: 25 partial-text-reviewed, 18 abstract-only, 7 metadata-only and 0 full-text-reviewed.
- **P2 — VALIDATION_PASSED_APPROVAL_PENDING:** AUTH-P2-001 authorizes P2 only. Aggregate result: 50 linked record shells, 214 abstract-level observations, 40 records with abstract observations, 3 without content observations due to access/retrieval limitations, 7 metadata-only and 0 unresolved abstract locators. Human acceptance APR-P2-001 remains blank. Independent second coder is NOT_RUN; semantic review is SELF_REVIEW_ONLY.
- **P3–P9 — NOT_STARTED / NOT_AUTHORIZED:** each phase requires predecessor completion/acceptance and its own explicit authorization.

Platform test results do not change research phase status. No AI-generated approval is permitted.

## 3. Platform architecture and releases

Platform development progressed through local engineering checkpoints v0.5.0–v0.8.0. The current public source baseline is v0.8.0 and includes:

- Evidence/source provenance, claim-evidence links and methodology alignment.
- A bounded descriptive statistical engine with transaction recovery, reproducibility and diagnostics.
- Evidence-linked DOCX/PDF document engineering and document audits.
- Revision-pair and marked-region QA.
- Empirical consistency gates for instrument constructs, paired tests, ICC and causal interpretation.
- Local-only Turnitin report metadata and report-comparison QA; no thesis body text storage or detector evasion.

Recorded local engineering validation: 197/197 regression tests, 29/29 JSON Schemas (Draft 2020-12), compileall, phase-ledger validator and CLI smoke tests passed. GitHub Actions CI must be verified from an actual workflow run before making a remote CI claim.

## 4. Public/private separation

Public repository allowlist: platform code, schemas, synthetic test fixtures, generic documentation, sanitized governance records and aggregate phase status.

Private-only material: P1/P2 datasets, evidence/source registers, abstract text, exact source routes/locators, per-record codes, adjudication and coverage tables, private packages, thesis DOCX/PDF, Turnitin reports, marked-region exports, participant names/scores, case-specific hashes, credentials and local caches.

The repo must remain free of raw participant-level or private source material. Public availability does not grant rights to third-party source content; no software license is declared unless a separate approved license is added.

## 5. Repository activation checkpoint

On 2026-11-10 the project owner instructed that the previously empty public repository be populated. The first repository content commit created the public README on `main`: `c51b223fcd4803006afbba9d68e891216b83ce0a` (verified from GitHub). The complete sanitized source bundle and aggregate public reports are prepared for expanded publication. The repository remains public; visibility and settings were not changed. No force push, branch rewrite, release or deployment was performed. The expanded source tree will be verified against its manifest after the publication workflow completes.

## 6. Repository publication contents

The intended expanded public tree comprises the complete reusable platform source, JSON Schemas, synthetic regression suite, CLI, documentation, project/workspace templates, generic P0–P9 governance snapshot, aggregate-only P0/P1/P2 reports, source manifest, and the deterministic sanitized distribution ZIP. The public content allowlist is recorded in `docs/platform/PUBLIC_REPOSITORY_PUBLICATION.md`. The archive is not a substitute for direct expanded files; both should be present on `main`.

The remote first commit currently verified is `c51b223fcd4803006afbba9d68e891216b83ce0a`. Do not claim the complete source is published until the expanded tree and file count are read back from GitHub and the CI workflow result is inspected.

## 7. Recovery and update protocol

On every invocation: read this memory and the current phase ledger; verify GitHub branch/head and repository tree; validate source manifests; preserve private data boundaries; select only the earliest incomplete authorized research phase; never self-authorize; update canonical status only from verifiable evidence. Keep human acceptance and execution authorization as distinct fields.
