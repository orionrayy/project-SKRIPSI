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

Recorded local engineering validation: 200/200 unit/regression tests, 29/29 JSON Schemas (Draft 2020-12), compileall, phase-ledger validator and CLI smoke tests passed. GitHub Actions CI must be verified from an actual workflow run before making a remote CI claim.

## 4. Public/private separation

Public repository allowlist: platform code, schemas, synthetic test fixtures, generic documentation, sanitized governance records and aggregate phase status.

Private-only material: P1/P2 datasets, evidence/source registers, abstract text, exact source routes/locators, per-record codes, adjudication and coverage tables, private packages, thesis DOCX/PDF, Turnitin reports, marked-region exports, participant names/scores, case-specific hashes, credentials and local caches.

The repo must remain free of raw participant-level or private source material. Public availability does not grant rights to third-party source content; no software license is declared unless a separate approved license is added.

## 5. Repository activation and publication checkpoint

The first repository content commit created the public README on `main`: `c51b223fcd4803006afbba9d68e891216b83ce0a`. On 2026-11-11, the sanitized source publication completed through the one-shot GitHub Actions expansion workflow:

- Bootstrap commit: `ce24e8a4051658de4412aded3ca43602d8fbc750`.
- Expansion workflow run #2: **SUCCESS**, run ID `43002256443`, completed at 2026-11-11 17:17:49 WIB.
- GitHub Actions expansion commit on `main`: `a667940306d57d83032ad973985c504fb7774a30`.
- Expanded tree: `a8f3c08429582d2ff62e912a5f73fb191cd65503`; recursive tree read was not truncated.
- Remote tree inventory: **133 file blobs and 49 directories**. It contains **130 manifest-allowlisted source files**, `MANIFEST.sha256`, the distribution TAR.XZ archive, and its SHA-256 sidecar.
- Archive: 169,800 bytes; SHA-256 `bcade06f387de89a1c93dd468ff8ff4baf474c4f8976284e2091a1bce6ef805f`. Its Git blob SHA `311cd93a46715a3c61a1e9cbb6c2e6a3164af644` matches the locally verified archive bytes.
- Repository metadata at verification: public, active, default branch `main`, one branch, reported size 612 KB.

The expansion job's reconstruction/checksum, safe extraction, dependency/renderer installation, complete source validation, and transport-fragment removal/commit steps all completed successfully. The source-validation step runs the manifest verifier, phase-ledger validator, Python compileall, 200-test unit/regression suite, editable package installation without dependency changes, and CLI help smoke test.

The independent cross-platform `Project Skripsi CI` matrix has **not yet been verified on the expanded tree**: the bootstrap-triggered CI run was intentionally skipped, while an earlier run against the pre-expansion repository failed because the source tree was not yet present. Do not describe the six-platform matrix as passed until a post-expansion run is observed. No release, deployment, force-push, or visibility change was performed. The authenticated GitHub account matches the repository owner; the local Git author remains unconfigured, so no local commit is claimed.

## 6. Public repository contents and private-data boundary

The expanded public tree contains the reusable platform source, Python package and CLI, 29 JSON Schemas, synthetic regression suite, generic documentation, project/workspace templates, canonical sanitized P0–P9 governance snapshot, aggregate-only P0/P1/P2 status, `MANIFEST.sha256`, and the deterministic TAR.XZ distribution archive with its checksum sidecar. The manifest contains 130 source-file entries; the archive contains those 130 files plus `MANIFEST.sha256`.

Private material remains excluded: P1/P2 record-level datasets, source/evidence registers, abstract text and exact locators, extraction/coding/adjudication matrices, private QA exports, individual thesis DOCX/PDF, actual Turnitin reports, report/submission identifiers, participant-level data, credentials, databases and caches. The Turnitin-named source module, schema, generic documentation, and tests are platform functionality using synthetic test fixtures; they are not actual Turnitin report exports or case-level QA files.

The repository remains a platform publication, not a publication of the user's thesis or research corpus. Public source availability does not grant redistribution rights to third-party material, and no software license is declared until a separate license is approved and added.

## 7. Recovery, verification, and continuation protocol

On every invocation:
1. Read this memory and `config/pipeline/PHASE_LEDGER.json`; verify the current `main` head and repository tree rather than relying on a previous checkpoint.
2. Verify the 130-entry public manifest, archive SHA-256, safe-path rules, and absence of private thesis/report/database/participant artifacts before any further publication.
3. Distinguish engineering checks from research-phase validation, human acceptance, and phase-specific authorization.
4. Continue the earliest incomplete authorized work item. Preserve P0 and P1 accepted scopes; P2 remains `VALIDATION_PASSED_APPROVAL_PENDING` with APR-P2-001 blank; P3–P9 remain `NOT_STARTED / NOT_AUTHORIZED`.
5. The project owner's standing instruction to continue implementation without repeated operational approvals does not allow the system to invent a P2 acceptance decision, waive research ethics or source restrictions, or self-authorize P3–P9. Keep execution authorization, human acceptance, and evidence validation separate.
6. Update the canonical ledger and this memory only from verified repository and artifact evidence. Do not claim a workflow, package installation, external review, or academic acceptance unless its actual result is observed.



## Mendeley REST API integration candidate — checkpoint 2026-11-17

- Implementation branch: `feature/mendeley-api-integration`; PR #2 targets `main`. Current verified pre-documentation-cleanup head: `45f21eac21c409a59bf8fb5924a32a1a891387e3`. PR remains open and draft; no merge and no changes to `main`.
- Implementation: `src/project_skripsi/integrations/mendeley.py`; CLI entry point `project-skripsi-mendeley`; tests `tests/test_mendeley.py`; operator guide `docs/integrations/MENDELEY_API_INTEGRATION.md`.
- Supported surface: OAuth Authorization Code and local token refresh/storage; authorized-user profile v2 operations (read/update/by ID/listing visible profiles); private library document list/search/get/create/update/trash/restore/delete; folders; annotations; document-scoped file transfer; public Catalog search/lookup; supported private Groups v2 routes; opt-in metadata-only source-register import.
- Explicitly excluded retired/unsupported API features: Profile Search, follower/followee/social endpoints, public/invite-only group capabilities, public-group joins, and popular-public-group search. Do not reintroduce these based on older Mendeley reference pages. Catalog search remains supported and is not profile search.
- Validation: GitHub Actions run `44019624146` (run #75) passed the baseline integration changes, run `44020957966` (run #79) passed the canonical-memory/manifest correction, run `44023290647` (run #90) passed the initial journaled-sync implementation, and run `44023903965` (run #94) passed the expanded journaled-sync implementation plus all four fault-injection scenarios with **6/6 matrix jobs successful**: Ubuntu Python 3.10, 3.11, 3.12; Windows Python 3.10, 3.11, 3.12. Each matrix job passed manifest verification, package compilation, research-ledger validation, the unit/regression suite, editable install, and CLI smoke test. Ubuntu jobs installed LibreOffice for document-render integration coverage; its installation step was skipped on Windows. A dedicated Python 3.14 Mendeley connector job has now been added to cover the runtime version used by recent Termux environments; it awaits its first CI run and does not constitute a native Android test.
- Connector-specific tests exercise OAuth state/refresh and a local loopback callback with a mocked token exchange, API contract/media types, pagination/host restrictions, retries, private-resource operations, confirmation gates, and metadata-only sync. All four journal recovery fault-injection tests passed on run #94: interruption before register replacement, post-replacement audit failure, audit append committed before interruption/journal cleanup (idempotency), and fail-closed external-edit conflict. These are test-double/isolated tests; CI success is not a live Mendeley account authorization or provider-side operation.
- **Live account status:** no real Mendeley account has been authorized and no live profile/library API request has succeeded in this environment. The account owner must register a Developer Portal app and configure `MENDELEY_CLIENT_ID`, `MENDELEY_CLIENT_SECRET`, and the exact redirect URI locally. Never request or store the client secret in chat or Git.
- Cost boundary: no paid SDK or third-party Python runtime dependency is required. Free app registration does not imply unlimited API quotas, universal endpoint permission, or guaranteed account eligibility. Personal/local use remains the only assumed deployment until the current Developer Terms have been checked against intended use; commercial/multi-client embedding is not cleared.
- Sync safety: preview is the default. Apply appends only stable-ID-deduplicated `METADATA_ONLY` records with `rights_status=UNKNOWN`, no exact content locator, and no claim-evidence links. The implementation now stages a new register and backup, persists a journal with before/after SHA-256 values before replacement, atomically replaces the register, and completes a hash-chained audit event with a deterministic idempotency key. A later explicit `--apply` rolls forward a pending transaction; preview fails closed; external edits that match neither recorded hash are not overwritten. Backup is retained. Fault-injection tests now cover pre-replace interruption, post-replace/audit failure, and modified-register conflict; this new behavior remains pending latest-head CI verification.
- Repository status must remain distinct from research governance: engineering CI does not accept P2, authorize P3–P9, or alter `config/pipeline/PHASE_LEDGER.json`. P2 acceptance remains pending; no phase ledger change was made by this connector work.
- Next gates: (1) pass latest-head CI including the new dedicated Python 3.14 connector job; (2) review any remaining security/recovery findings; (3) complete a live read-only OAuth/profile/library smoke test on the account owner's machine; (4) only then test individual write operations against disposable resources with explicit authorization. Apply-mode sync remains a guarded candidate pending Python 3.14 CI and live read-only account validation.
