# ORCHESTRATION_MEMORY — Public Canonical Project Memory

**Memory version:** 1.6.0  
**Project:** `orionrayy/project-SKRIPSI`  
**Updated:** 2026-11-14 (Asia/Jakarta)  
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
2. Verify the source manifest for the exact branch/ref, archive SHA-256, safe-path rules, and absence of private thesis/report/database/participant artifacts before any further publication.
3. Distinguish engineering checks from research-phase validation, human acceptance, and phase-specific authorization.
4. Continue the earliest incomplete authorized work item. Preserve P0 and P1 accepted scopes; P2 is accepted within its abstract/item-page scope; P3 is the active synthesis candidate; P4–P9 are conditionally pre-authorized but remain execution-gated.
5. The project owner's standing instruction to continue implementation without repeated operational approvals does not allow the system to invent human acceptance, waive research ethics or source restrictions, or expand a phase's evidence scope. A user may pre-authorize later phases, but sequential predecessor acceptance remains mandatory. Keep execution authorization, human acceptance, and evidence validation separate.
6. Update the canonical ledger and this memory only from verified repository and artifact evidence. Do not claim a workflow, package installation, external review, or academic acceptance unless its actual result is observed.


## 8. Document-layout case learning and QA candidate (2026-11-14)

- **Review scope:** task brief, iterative revision instructions, final DOCX/PDF pair, supplied emblem asset, and rendered-page QA outputs. The private source pair, emblem bytes, original manuscript text, personal identifiers, institution-specific identifiers, personal filenames and per-artifact hashes were not added to the public repository.
- **Sanitized case record:** `data/quality_learning/document-layout-case-2026-11.json` and `docs/quality/DOCUMENT_LAYOUT_CASE_LEARNING_2026_11.md`. The case is a derived requirements/defect/regression record, not a raw text training corpus and not a representative sample of all theses or institutional styles.
- **Rendered evidence:** 14 physical PDF pages; one unnumbered cover; two front-matter pages; ten substantive BAB I–IV pages; one bibliography page. Displayed numbering is 1–13 from the first post-cover page to the last page. Seven selected TOC entries were reconciled to displayed page numbers.
- **Evidence-bounded writing lesson:** one retrospective personal experience supports only the author's bounded observation and interpretation. No exact date, venue, relatives, event sequence, family motives or regional prevalence may be invented. Separate first-person observation, literature context, inference and unknown details. Natural academic language requirements are clarity/style constraints, not AI-detector evasion.
- **New layout QA candidate:** `src/project_skripsi/document_layout_qa.py`, `scripts/audit_document_layout.py`, policy/output/case schemas, synthetic tests and engineering documentation. The auditor inspects DOCX section geometry, margins, page fields, Normal style, font inventory and inline-image alt text, then checks rendered PDF page count, cover numbering, displayed-number sequence, optional sparse pages and TOC heading/page mapping. Its report excludes filenames, paths, manuscript text, personal identifiers and input hashes.
- **Case audit result:** `WARN`, zero errors and two warnings. The visible PDF pagination is correct (cover unnumbered; body labels 1–13); selected TOC positions match. Remaining structural warnings are the one-section `different_first_page_header_footer` + `w:pgNumType start=0` workaround and missing alternative text on one inline image. Production recommendation: dedicated cover section plus a body section restarted at 1, and meaningful alt text for non-decorative images.
- **Local verification:** the new isolated regression suite is 6/6 PASS; three new Draft 2020-12 schemas and the sanitized case record validate; Python compile check PASS. Full repository regression and GitHub Actions CI remain pending on draft PR #1. Do not claim the complete suite or cross-platform CI has passed until observed.
- **Remote checkpoint:** draft PR #1, branch `feature/document-layout-case-learning`, base `main`. No merge, release, deployment or phase-ledger mutation has occurred. P0/P1 accepted states are unchanged; P2 is accepted under APR-P2-001; P3 is executed and validation-passed-with-limitations with acceptance pending; P4–P9 are conditionally pre-authorized but not started.
- **Release boundary:** platform baseline remains v0.8.0. This is an unreleased feature candidate; the v0.8.0 distribution archive remains an immutable release snapshot and is not represented as containing the candidate files.
- **Limits:** page-number detection relies on extractable PDF text and may miss rasterized numbers; heading matching is heuristic. This module does not detect all clipping, overlap, widow/orphan cases, table splits or visual-aesthetic defects. Full page-by-page visual QA and human academic review remain required.


## 9. Windows CI failure analysis and correction (2026-11-14)

- The first full matrix run for draft PR #1 exposed an existing workflow portability defect in the Windows job. Its LibreOffice setup step wrote the LibreOffice `program` directory to `GITHUB_PATH`, placing LibreOffice's bundled Python ahead of the interpreter selected by `actions/setup-python`.
- Observed evidence from Windows runner logs: `sys.executable`/traceback paths pointed into `C:\\Program Files\\LibreOffice\\program\\python-core-3.12.16`; the suite then could not import `python-docx`, `PyMuPDF` and `jsonschema` even though the preceding install step succeeded. Process tests also attempted to spawn the wrong Python executable and returned `WinError 5`. The manifest, package compile, phase-ledger validator and dependency installation had passed before the unit-test step.
- Correction on the candidate branch: Windows CI now exports the absolute `soffice.exe` path through `PROJECT_SKRIPSI_SOFFICE` in `GITHUB_ENV`, without prepending the LibreOffice folder to `PATH`. `documents._render_pdf` resolves this explicit override first and falls back to `shutil.which()` elsewhere. Documentation now describes this override.
- The earlier Windows failures also included a stable-hash race assertion while executing under the wrong LibreOffice-bundled Python. Do not change stable-hash production code based on that run until the test is repeated with the correct setup-python interpreter.
- The first CI run had all three Ubuntu matrix jobs SUCCESS; Windows 3.10/3.12 failed on unit tests under the contaminated PATH; Windows 3.11 was still running at checkpoint. A new run is required against the corrective commit. The first run is not an accepted validation result.
- Candidate CI remains a release gate. Verify the next run end-to-end across six Python/OS matrix combinations before considering PR #1 for ready-for-review. Main, release tags and distribution archive remain unchanged.


## 10. P2 acceptance, P3 synthesis and P3–P9 authorization (2026-11-14)

- **P2 human decision:** the project owner explicitly selected `ACCEPT` for the P2 v1.1.0 deliverable on 2026-11-14. APR-P2-001 records the decision, timestamp and accepted scope. The acceptance is limited to public abstract/item-page observations: 50 linked record shells, 214 observations, 40 content-coded records, 3 inaccessible and 7 metadata-only. It does not imply full-text review, independent second coding, external academic review, or a change to the `PASS_WITH_LIMITATION` technical state.
- **P3–P9 authorization:** AUTH-P3-P9-001 records the owner's explicit standing authorization for all phases P3 through P9. P3 is eligible now because P2 is accepted. P4–P9 are conditionally pre-authorized but cannot execute before each immediate predecessor is `COMPLETE_AND_APPROVED`.
- **P3 private candidate:** ten findings (eight content findings and two corpus coverage/composition findings), 120 domain-by-code matrix rows, 173 private evidence references, Draft 2020-12 validation and private SHA-256 manifest PASS. P3 remains pending human acceptance. No record-level P1/P2 data, abstracts, source locators or institution names were placed in the public repository.
- **P3 methodological boundaries:** 214 observations are nested within 40 abstract-coded records; three inaccessible and seven metadata-only records are not negative evidence. No finding is HIGH confidence. The archived P1/P2 source checkpoint is 2026-11-05; the P3 synthesis is not a fresh source retrieval.
- **Sequential-gate engineering update:** the phase-ledger validator now permits a standing conditional authorization to be recorded before predecessor acceptance, while still rejecting execution, approval or completion until the immediate predecessor is COMPLETE/APPROVED/ACCEPTED. Regression tests cover both valid pre-authorization and rejected early execution.
- **Platform candidate remains unreleased:** draft PR #1 is still unmerged. A Windows test-fixture correction changes the simulated file mutation from a same-size rewrite to a different-size rewrite; stable-hash production code is unchanged. Full CI must be observed against the resulting branch head before the candidate is marked ready.
