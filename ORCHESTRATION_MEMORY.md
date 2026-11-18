# ORCHESTRATION_MEMORY — Public Canonical Project Memory

**Memory version:** 1.5.0  
**Project:** `orionrayy/project-SKRIPSI`  
**Updated:** 2026-11-18 (Asia/Jakarta)  
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


## 8. Visual composition and reader-task engineering candidate

A new additive feature candidate is being reviewed on branch `feature/visual-composition-reader-attention-v0.1.0`, based on the verified `main` head `2ddab892c9c4c927930e8424280a32f49ea0600e`. It is not merged or released.

The candidate adds a privacy-minimizing rendered-PDF composition auditor, a CLI wrapper, synthetic regression tests, profile and audit schemas, an event-TOR composition profile, a sanitized iteration-learning case, and generic design/reader-task guidance. Its purpose is to complement document layout preservation with visual composition and reader-usability checks.

The guidance separates four acceptance dimensions: content integrity, layout integrity, visual composition and reader usability. It discourages box/card overuse, promotes document-family-specific motif systems, intentional whitespace, typographic hierarchy, page-to-page rhythm and task-oriented scanability. It does not assert a universal attention-span duration.

The auditor measures static geometry proxies only: text-area ratio, text bounds, margin bands, font size/family distribution, approximate heading/body size contrast, vector rectangle counts and image counts. It deliberately reports eye-tracking as `NOT_MEASURED`; the reader task test remains `NOT_RUN` unless a human test is performed. A configured mechanical PASS is not a visual acceptance or user approval.

Candidate validation recorded in this branch: 7/7 dedicated unit tests pass; both new Draft 2020-12 schemas pass meta-schema validation; the synthetic event-TOR policy and a generated audit report validate against their schemas. The local TOR redesign is a separate private deliverable and is not included in this public repository. No private document, identity value, original asset, user file hash or raw case content was published.

This addition changes no P0-P9 research phase, approval, acceptance, ledger record, or authorization. P2 remains `VALIDATION_PASSED_APPROVAL_PENDING` and P3-P9 remain `NOT_STARTED / NOT_AUTHORIZED`. The candidate must be reviewed and merged separately before it becomes the canonical main-branch implementation.


## 9. Cross-platform manifest checkout remediation candidate

The first pull-request CI run for visual-composition candidate head `8863c1de20e489e70a6d2d76b00fba44d324f003` passed all three Ubuntu jobs but failed the three Windows jobs at manifest verification before compile/tests. Its logs reported SHA-256 mismatches across many tracked text files. The earlier main-branch push run had passed Windows manifest verification; the precise cause has not been conclusively isolated.

A fail-closed helper, `scripts/restore_manifest_blobs.py`, now restores only manifest-listed paths directly from Git blob bytes with `git cat-file`, validates manifest paths and rejects symlink targets, then lets the existing exact-byte verifier run. The CI workflow uses this helper before manifest verification. Three dedicated helper unit tests pass locally. The corrected manifest contains 140 entries.

The follow-up CI run is pending. Do not call cross-platform CI complete until all six jobs pass. This is an engineering/checkout remediation only; no private files, research records, phase status, approval, or authorization were changed.


## 10. Windows matrix interpreter-priority remediation

The follow-up CI after exact Git-blob restoration showed all six jobs passed the manifest restoration and exact-byte verification steps. One Windows/Python 3.12 job then failed unit tests because the LibreOffice installation step added its embedded Python directory to PATH ahead of the matrix interpreter; the log showed missing `fitz` and `jsonschema` and imports from LibreOffice's embedded Python. This is an environment-ordering defect, not a visual-composition audit failure.

The CI workflow has been reordered so LibreOffice is installed first and `actions/setup-python` runs afterwards, preserving `soffice` discovery while restoring the requested matrix interpreter to PATH priority. The next six-job run is pending. Do not claim Windows matrix acceptance until all jobs complete successfully.


## 11. Deterministic Windows regression fixture

The latest full matrix after interpreter-order correction passed Windows/Python 3.10 and 3.12. Windows/Python 3.11 failed one pre-existing stable-file-hash test because its fixture rewrote the same-length content and depended on filesystem timestamp resolution. The method-scaffold test's stderr was the expected second-call no-overwrite message and the test itself passed.

The test fixture now changes both content and file size during the injected mutation, so the existing stable-hash metadata guard receives a deterministic size delta across filesystems. No production hashing behavior was relaxed. The next CI run is pending.


## 9. Follow-up: genre fidelity and visual restraint (2026-11-18)

The event-TOR composition case was extended from T5 to T7 after user feedback that the motif-led version looked excessively fancy and recognizable as a generic AI-style template. T6 records the over-designed result; T7 records a conventional understated candidate based on the supplied TOR reference: Times New Roman, centered formal title, ordinary bold section labels, numbered lists, label-value metadata, one restrained rule, one functional schedule table and no invented logo/motif system.

The latest private TOR candidate is two A4 pages and is intentionally not included in this public repository. Its user acceptance remains pending. The public learning case contains no original document content, identity values, source PDF, final DOCX/PDF, original assets, private filenames or document hashes.

The reusable rule is genre fidelity before decorative novelty. Document-family conventions, the actual organization identity and reader tasks determine the level of visual treatment. Visual restraint must not become cramped or unfinished; whitespace and pagination still require full-page review. Reader-task testing remains NOT_RUN and eye-tracking remains NOT_MEASURED. No P0-P9 phase, acceptance or authorization state changed.
