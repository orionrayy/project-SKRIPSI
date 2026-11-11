# Changelog

## 0.8.0 — Turnitin report comparison and empirical evidence QA (2026-11-10)

- Added optional local Turnitin PDF report parser and comparison engine: submission metadata, similarity percentage, visible exclusions, source-category percentages, top-source inventory and visible source-badge references.
- Added `turnitin-report-audit` and `turnitin-report-compare` CLI commands. Comparison labels only visible-setting comparability and explicitly refuses to infer identical account/database configuration or a plagiarism verdict.
- Extended empirical consistency QA with paired-test output-table presence, paired-difference assumption diagnostics, explicit row-order pairing warnings, and per-instrument validation evidence/item-coverage checks.
- Added two JSON schemas, a synthetic per-instrument/paired-test template, tests and documentation.
- PDF parser stores report metadata and source labels only; it does not persist thesis body text, participant-level data, or perform network calls.
- Validation: **200/200 full regression tests PASS**; compileall PASS; phase-ledger validator PASS; **29/29 JSON Schemas** pass Draft 2020-12 meta-schema checks; editable install and new CLI smoke tests PASS.
- No private thesis or respondent data was added to the public source tree; no remote or research-phase mutation occurred.

## [0.7.0] — 2026-11-10

### Added
- Added local-only revision QA engine and four CLI commands: `revision-pairs-audit`, `marked-region-audit`, `empirical-consistency-audit`, and `artifact-manifest-audit`.
- Added exact normalized `SEBELUM` / `SESUDAH` correspondence checks against immutable original and candidate DOCX files. Repeated exact locations are classified as ambiguous rather than silently counted as unique; explicitly new content can be marked not-applicable on the before side.
- Added marked-region register audits for stable unique IDs, mapping confidence, issue classification, evidence-access state, disposition, validation state and written rationale. Registration coverage is separated from actual resolution.
- Added a structured empirical-study consistency audit for declared sample sizes, demographic counts/percentages, unique participant pairing keys, construct modality, Cronbach alpha grouping, ICC configuration, p-value display and design-to-claim strength.
- Added a relative-path artifact manifest verifier for DOCX/PDF/TXT and other deliverables, checking SHA-256 and byte length and rejecting path traversal.
- Added Draft 2020-12 schemas, an example empirical study model, CLI documentation and deterministic regression fixtures. All audits run offline with the Python standard library.

### Validation
- Validation: **187/187 full regression tests PASS**, including 12 revision-QA tests; Python compileall PASS; phase-ledger validator PASS; **27/27 JSON schemas** parse and pass Draft 2020-12 meta-schema validation.
- Real private-case audit was run without copying thesis paragraphs, personal identifiers or participant data into the public source tree. Its raw reports remain in the private audit workspace.
- This release is a local isolated source candidate; no commit, push, PR, merge, publication, deployment or governance/phase-state mutation occurred.

### Boundaries
- These checks validate traceability and declared structural consistency only. They do not assess plagiarism, estimate Turnitin/AI-detector scores, prove semantic equivalence, verify source truth, calculate inferential statistics, or certify academic/institutional acceptance.
- Existing document build and render gates remain required; full-page visual review is not replaced by artifact hashes or text matching.
- The reusable platform does not automatically correct missing data, respondent identities, demographic totals, statistical output, citations or causal claims.

## [0.6.0] — 2026-11-06

### Added
- Added `src/project_skripsi/documents.py` and the `document-scaffold`, `document-build`, `document-verify`, and `document-audit` CLI commands. The engine assembles only operator-supplied blocks; it does not generate thesis findings, invent citations, or infer institutional requirements.
- Added an evidence-linked DOCX/PDF document pipeline with A4/Letter layouts, configurable typography/margins, cover, chapter headings, paragraphs, lists, tables, figures, bibliography, and a visible `DRAFT - NOT REVIEWED` footer.
- Replaced the initially blank TOC with a static page-mapped table of contents. The renderer extracts heading locations from PDF output, rebuilds until page mapping converges, and inserts internal hyperlinks/bookmarks into the DOCX.
- Added APA7 author-year and IEEE numeric citation rendering. IEEE ordering follows first citation appearance; APA author-year collisions receive deterministic suffixes. Citations require claim-evidence relations with `SUPPORTS`, `VERIFIED`, exact locator and reviewer role. Bibliographic completeness warnings remain explicit.
- Added verified analysis-table insertion using only aggregate results from runs that pass `analysis-verify`; respondent-level rows are never exported. Suppression state and analysis hashes are preserved in the document build record.
- Added workspace-local figure ingestion with path/symlink checks, PNG/JPEG type and size limits, caption and alt-text requirements.
- Added human-reviewed institutional-profile gating. A profile must be SHA-256 pinned and carry review status, reviewer role, version, profile ID and approval reference. Generic formatting remains explicitly institutionally unverified.
- Added immutable document build records pinning DOCX/PDF/specification/project manifest/source register/profile/citation claims/analysis runs, and a hash-chained audit event. Existing outputs and build records are never overwritten.
- Added manuscript specification/build-record schemas, example specification, document engineering guide, integration tests and Ubuntu/Windows Python CI matrix coverage. The Windows runner skips only render tests that require LibreOffice; native Windows CI has not yet been executed from this release runtime.
- New workspaces now receive `manuscript/document_specification.json` and `manuscript/builds/` plus `manuscript/figures/` directories.

### Validation
- Full regression suite: **175/175 PASS**; document-specific suite: **9/9 PASS**.
- **25/25** JSON schemas parse and pass Draft 2020-12 meta-schema validation; `compileall` and phase-ledger validator PASS.
- Editable package installed locally with `--no-build-isolation`; installed package and CLI report version `0.6.0`.
- Installed CLI smoke `init` → `validate` → `document-build` → `document-verify` → `document-audit` PASS on a disposable synthetic workspace. The result stays `BUILT_NOT_REVIEWED` / `NOT_REVIEWED`.
- Synthetic eight-page DOCX/PDF fixture visually reviewed page-by-page at 160 dpi: cover, non-empty static TOC, five chapter pages, and bibliography. TOC page map matched PDF pages 3–8; no clipping, overlap or truncated table was observed. Heading style uses black text.
- Build output integrity verified: DOCX/PDF SHA-256 pins, source register, source claims and audit event all pass. No real thesis or participant data was included in the fixture.

### Boundaries
- APA7/IEEE rendering is a scoped implementation, not certification of full style compliance for every source type. Journal volume/issue/page metadata may be incomplete and requires human completion/verification.
- Generic institutional formatting is not compliant-by-assumption. A human-reviewed profile is required; its metadata is a traceability assertion, not cryptographic proof of institutional approval.
- The PDF is generated by LibreOffice; rendering can vary across versions/platforms. Static TOC page mapping is validated against the generated PDF for that build.
- Every generated document remains a draft and requires human academic, methodological, citation and institution-specific review before submission.
- Native Windows CI and GitHub workflow execution were not performed in this runtime; no commit, push, PR, release publication or remote mutation occurred.
- The user's previously supplied ChatGPT share reference was not retrievable; no recommendations were inferred from its unseen content.
- Global research P0–P9 and per-project thesis T0–T9 states are unchanged. Platform release validation does not constitute research acceptance.

## [0.5.2] — 2026-11-06

### Added
- Added stable SHA-256 input hashing that checks filesystem identity and timestamps before/after reads; v0.5.2 run records also pin the project manifest and record Python implementation/platform plus an explicit reproducibility contract.
- Added pinned-input validation to recovery. The dataset, dataset registry record, analysis specification, methodology alignment, scoped decision register, T0–T9 phase ledger and project manifest are checked before and after restoration; drift preserves the journal and partial artifacts and blocks audit commit.
- Added `analysis-reproduce`, a read-only same-engine computational replay that reruns the descriptive calculation and compares the recomputed result SHA-256 to the stored result and run record.
- Added `analysis-diagnostics`, a read-only summary of persisted INFO/WARNING/ERROR findings with explicit limitations on untested inferential assumptions.
- Added process-termination tests using child processes and abrupt `os._exit` at four durable boundaries: transaction journal, result file, run record and audit append.
- Kept v0.5.1 run records and prepared transactions readable; the run-record schema conditionally requires v0.5.2 fields for version 0.5.2 while accepting legacy v0.5.1 records.

### Validation
- Full regression suite: **166/166 PASS**; Statistical Engine-focused suite: **43/43 PASS**.
- `compileall` and phase-ledger validator PASS; **23/23** JSON schemas parse and pass Draft 2020-12 meta-schema validation, including conditional acceptance of v0.5.1 legacy run records.
- Editable installation and package/runtime metadata both report `0.5.2`; installed CLI lifecycle `validate` → `analysis-spec-check` → `analysis-run` → `analysis-verify` → `analysis-reproduce` → `analysis-diagnostics` PASS on a disposable synthetic-data workspace.
- Abrupt subprocess termination at transaction, result, run-record and post-audit persistence boundaries recovers successfully; each recovered run verifies and reproduces with one audit event. Pinned dataset drift is refused and the journal is preserved.
- Final source manifest contains 99 entries; ZIP packaging is verified as 100 exact members including the manifest, CRC PASS, and no blocked/private files in the archive.

### Boundaries
- A successful replay is same-engine computational consistency, not independent review, second implementation validation, methodological correctness or thesis approval.
- Recovery refuses changed input hashes rather than adapting a pending run to modified files. It rechecks inputs immediately before and after restoring outputs and before retiring the journal; it never recalculates results or overwrites conflicts.
- Diagnostic output does not test normality, independence, homoscedasticity, missingness mechanism, measurement validity/reliability or inferential-model assumptions.
- Native Windows runner and GitHub CI remain unverified until they actually execute.

## [0.5.1] — 2026-11-06

### Added
- Added checksummed write-ahead transaction records for descriptive analysis runs. The journal is persisted before run output creation and contains only the already-approved aggregate result payload and reproducibility record, never participant-level source rows.
- Added `analysis-recover` to idempotently complete interrupted run persistence, reconstruct missing result/run artifacts from a verified journal, and append or reuse the audit event by stable idempotency key.
- Added transaction integrity checks, safe workspace path checks, conflict detection for partial/tampered outputs, and a Draft 2020-12 transaction schema.
- Added recovery regression tests for interruption before audit append, interruption after durable audit append, and tampered transaction refusal.

### Validation
- Full regression suite: **160/160 PASS**; Statistical Engine-focused recovery and analysis tests PASS.
- `compileall`, phase-ledger validator, and **23 JSON schema parse checks** PASS.
- Recovery restores incomplete artifacts without duplicate audit events; tampered journals are refused and preserved for investigation.
- No live API, external model, participant dataset, GitHub workflow, commit, push or PR was used.

### Boundaries
- Recovery only completes a transaction whose checksummed journal is present and internally consistent. It does not rerun calculations, change approvals, alter phase states, or resolve conflicts by overwriting operator data.
- Windows-native filesystem and lock behavior remain unverified until the configured Windows CI runner executes.

## [0.5.0] — 2026-11-05

### Added
- Project-scoped CSV dataset registration under `data/raw/` or `data/processed/`, with provenance, content hash, UTF-8/CSV structural checks, bounded streaming profile and privacy/permission classification.
- Registration profiles omit observed category labels/raw rows and suppress numeric aggregate metadata below N=5 by default.
- Descriptive-only Statistical Engine for numeric summaries (valid N, mean, sample SD, min/max) and frequency tables; no inferential test selection, p-values, confidence intervals, imputation, weighting or causal interpretation.
- Analysis specification scaffold and strict link validation to the approved research-alignment analysis plan, dataset artifact, source columns, constructs, research questions and human method decision record.
- T0–T5 human-acceptance and T6 scoped-authorization gates before execution.
- Small-cell suppression, complementary suppression when one low-frequency category would otherwise be reconstructable, pseudonymized frequency categories by default, confidential/restricted label-exposure refusal, and no combined hidden-category totals.
- Bounded CSV profiling at 5,000 columns and a global budget of 50,000 distinct values tracked across all columns, in addition to file-size/row/frequency-category limits.
- Reproducible run records with SHA-256 links to data, registry, analysis specification, research alignment, decision register and phase ledger; audit-pinned result/run hashes and `analysis-verify` command.
- Additional malformed-input hardening and regression coverage for invalid JSON types in analysis specs, dataset profiles, plans and approval records.

### Validation
- Full regression suite: **157/157 tests PASS**; Statistical Engine-focused suite: **34/34 PASS**.
- `compileall` and phase-ledger validator PASS. P0/P1/P2 recorded states remain unchanged; P3–P9 remain gated.
- All **22/22 Draft 2020-12 JSON schemas** pass schema self-validation.
- Editable installation reports `project-skripsi-engine 0.5.0` using `--no-build-isolation`; isolated build dependency download was unavailable because runtime DNS/network access failed.
- Installed CLI end-to-end smoke using a temporary synthetic workspace: `validate`, `analysis-spec-check`, `analysis-run` and `analysis-verify` PASS. No real participant dataset was read or analyzed.
- Deterministic output hashes, tamper detection, small-sample suppression, secondary suppression and malformed-input handling are regression-tested.

### Boundaries
- v0.5.0 is a descriptive-only execution slice, not a replacement for SPSS, SmartPLS, R or specialist statistical packages. Inferential tests, reliability/validity analysis, sample-size calculation and external statistical adapters are not implemented.
- No dataset was transmitted to an external service. The run smoke used synthetic test rows.
- Decision-register approval references are local traceability records, not cryptographic identity verification or proof of actual supervisor approval.
- Statistical run-directory crash recovery is not implemented; partial run folders are preserved for manual inspection and never silently overwritten. A later v0.5.x recovery protocol is required.
- Native Windows lock/filesystem behavior and GitHub CI execution remain unverified in this runtime.
- No individual research phase was advanced or accepted; no GitHub commit, push, PR, release publication or settings mutation was performed.

## [0.4.0] — 2026-11-05

### Added
- Project-scoped research-alignment scaffold linking research questions, objectives, constructs/variables, optional hypotheses, analysis plans and mixed-methods integration points.
- Strict JSON schema and illustrative template for the alignment record.
- Deterministic `methodology-audit` CLI and library engine for ID/reference integrity, question-to-objective/analysis coverage, hypothesis-to-construct/analysis coverage, optional source-register provenance checks, cross-register consistency, and human-review warnings.
- Methodology alignment guide documenting finding semantics, design boundaries and non-goals; additive `methodology-scaffold` command migrates older workspaces without overwriting.

### Validation
- Full regression suite: **123/123 tests PASS** after the v0.4.0 implementation and documentation refresh.
- `compileall`, phase-ledger validator, and all **19 JSON schemas** pass; the research-alignment example conforms to its Draft 2020-12 schema.
- Editable installation and installed distribution metadata both report `0.4.0`; root CLI, `methodology-audit` and `methodology-scaffold` help pass.
- Throwaway end-to-end CLI smoke passed: initialize workspace, validate, audit a coherent example, persist report, and refuse report overwrite. The report remains `READY_FOR_HUMAN_REVIEW` with `human_approval: NOT_GRANTED`.
- Legacy-workspace migration, no-overwrite behavior, path/symlink checks, source-register reference checks and cross-register consistency are covered by regression tests.

### Boundaries
- The audit does not select a research design, statistical test, estimator, software or sample size; it does not validate theory, instruments, sampling, assumptions or causal identification.
- Optional source-register checks resolve IDs and flag access classes; they do not verify that a cited source substantively supports a theory, construct or instrument.
- `READY_FOR_HUMAN_REVIEW` is a structural status only. `human_approval` remains `NOT_GRANTED`; qualified human review is required.
- No raw participant data or confidential interview text belongs in the alignment record.
- No live OpenAlex/Crossref requests or external LLM requests were made. The CI workflow and native Windows lock implementation have not yet been executed on GitHub/Windows.
- Research phase ledger P0–P9 and individual T0–T9 approval states were not advanced. No GitHub remote mutation was performed.


## [0.3.1] — 2026-11-05

### Added
- Added POSIX `flock` and Windows `msvcrt` advisory locking for project-level research mutations; kernel lock ownership is released automatically after process termination.
- Added checksummed OpenAlex write-ahead journals (`1.1.0`) and recovery-safe persistence for snapshot, source register and audit event writes.
- Added `research-integrity` read-only consistency checks and retained explicit `recover-research` as the only repair action.
- Added idempotent audit append conflict detection: retries with identical event payloads reuse the original event, while key reuse with changed payloads is rejected.
- Added symlink/path-boundary checks across workspace path components and audit/lock files.
- Added recovery transaction JSON Schema and corrected the source-record schema identifier/reference path.
- Added crash-injection, recovery, process-contention, process-termination and audit-idempotency tests.
- Added cross-platform Python manifest verifier and expanded CI configuration to Ubuntu/Windows × Python 3.10–3.12.

### Validation
- 95/95 unit tests passed on the current POSIX runtime.
- Phase ledger validator, compileall, 18 JSON-schema parse checks, editable package installation (`0.3.1`) and installed CLI smoke tests passed.
- `research-integrity` clean-workspace smoke returned `PASS`; a throwaway workspace and generated matrix were removed after testing.
- Recovery tests injected interruptions after journal preparation, snapshot persistence, source-register persistence, and audit append; retry recovery preserved one snapshot and one audit event.
- OpenAlex live API retrieval and native Windows `msvcrt` behavior remain unverified in this runtime. The current runtime validates POSIX locking; the new Windows CI matrix is configured but has not yet run on GitHub.
- No P0–P9 or T0–T9 research approval state was advanced. No remote mutation was performed.

## 0.2.0 — 2026-11-05

- Added an evidence-safe revision brief generator for Bahasa Indonesia and English.
- Added structural revision audit for citations, quotations, DOIs, URLs, numeric/statistical values, negation, uncertainty and causal language.
- Added loopback-only OpenAI-compatible local model adapter; external endpoints are rejected and redirects are disabled.
- Added original academic rhetoric patterns with evidence levels and claim-strength ceilings.
- Added claim overreach warnings; causal claims always remain human-review-required.
- Added a third-party tool assessment. Free-tier/cloud tools are not enabled by default; no detector-evasion or score-targeting rewrite loop is provided.
- Added tests for citation/number loss, epistemic marker changes, endpoint restrictions and causal overclaim risk.
- Added a Crossref DOI metadata lookup with URL-encoded DOI paths, polite-pool support, private SHA-keyed cache, expected-metadata comparisons and explicit metadata-only limitations.

## 2026-11-05T04:55:33+07:00 — Local bootstrap genesis

- Created a new local Git working tree at `[private local path omitted]` for `orionrayy/project-SKRIPSI`.
- Added canonical memory genesis record, reconciled P0–P9 ledger/schema, prompt execution log, project rules, repository boundary documentation and lightweight ledger validator/tests.
- Reconciled stale P0 ledger state against newer P1 corpus/acceptance/validation artifacts.
- Kept P1 human acceptance pending; P2–P9 remain not authorized.
- No P1 corpus, thesis full text, private data or secrets copied into the repository.
- No remote mutation, push, branch creation, release or settings change.

## 2026-11-05 — Bootstrap checkpoint reconciliation

- Revalidated P0 reconciled archive and P1 package: schema/hash/CRC/member checks pass.
- Restaged only sanitized local bootstrap files after staged-diff and privacy review.
- Re-ran phase-ledger validation and five unit tests; all pass.
- No local commit (Git identity absent); no remote mutation.
- P1 remains awaiting explicit human acceptance; P2–P9 remain unauthorized.
- Checkpoint: `2026-11-05T05:00:56+07:00` (Asia/Jakarta).


## 2026-11-05T05:20:24+07:00 — Master continuation v2.1.0

- Rechecked the current shared conversation and confirmed it is an older snapshot; later local P1 and bootstrap artifacts supersede its phase state.
- Revalidated actual P1 and reconciled P0 archive bytes, schemas, CSV parity, evidence/decision/source-ledger counts, manifests and ZIP integrity.
- Evolved the phase ledger/schema to separate execution, validation, human acceptance and phase conclusion states; P1 remains acceptance-pending and P2–P9 remain unauthorized.
- Updated prompt execution log, P1 reconciliation/recheck notes, local bootstrap report, and memory checkpoint.
- Authenticated GitHub login matches repository owner account ID, but full commit author attribution is not sufficiently verified; no Git identity configured and no local commit made.
- No remote mutation, push, release, or P1 corpus inclusion in the bootstrap tree.


## 2026-11-05T05:22:19+07:00 — Final v2.1.0 validation checkpoint

- Updated ledger to `2.1.0` and added explicit validation, human-acceptance and phase-conclusion fields with schema enforcement.
- Expanded validator gates and unit tests from five to seven; current validator and all seven tests pass.
- Refreshed prompt execution log and canonical memory; no P1 corpus changes.
- Git author remains unresolved (profile display name/verified noreply address not provided); no commit/push/remote changes.


## 2026-11-05T05:24:52+07:00 — Final test checkpoint

- Ledger validator and seven unit tests passed; exact outputs saved in `tests/TEST_RESULTS.md`.
- P1 acceptance remains pending; no P2 execution authorization or remote mutation.


## 2.2.0 — 2026-11-05

- Recovered the local source tree from the verified Library bootstrap v2.1.0 ZIP; explicitly documented that `.git` and historical staging were not restored.
- Recorded P1 owner acceptance within the bibliographic eligibility corpus scope and its disclosed access limitations.
- Authorized and began P2; created the private abstract-only extraction batch and governance/QA artifacts outside the public repository.
- Updated phase ledger, validator, tests, room handoff, recovery report, P1 recheck log, memory and prompt execution inventory.
- No local commit or remote GitHub mutation.


## 2026-11-05T10:28:48+07:00 — v2.2.0 final validation refresh

- Re-ran the phase-ledger validator, all nine unit tests, and the P2 package validator; all passed within the documented limitations.
- Recomputed the repository manifest and confirmed 26/26 hashes; P2 package manifest confirmed 11/11 hashes.
- Confirmed 27 sanitized paths remain staged locally; Git author identity remains unresolved, no commit created.
- GitHub empty-repository HTTP 409 rechecked; no remote mutation.


## 2026-11-05T10:32:05+07:00 — `.gitignore` privacy regression fix

- Added missing deny patterns for generic project data files, private CSV/JSON artifacts, credential JSON, source cache and explicit P1/P2 manifests/exports.
- Repository-relative ignore smoke test now passes 15/15. Temporary fixtures were removed; no private research data entered the source tree.


## [v2.3.0] — 2026-11-05T12:38:28+07:00

- Resumed P2 from the unchanged batch-01 private package and created private P2 v1.1.0 continuation artifacts.
- Reopened all 25 P1 partial-text routes; 22 individual item pages accessible, three still inaccessible; added 28 abstract-located observations (cumulative 200).
- Resolved a source record, a source record and a source record locator/item-page issues without modifying P1 canonical records or access classes.
- Added per-observation retrieval dates, schema requirements, provenance checks and a ninth negative regression case; P2 package validator passes.
- Updated phase ledger, P2 aggregate execution report, acceptance gate record, room handoff and local bootstrap report.
- No P3 work, no Git commit, no remote GitHub mutation, and no restricted thesis downloads.

- Reconstructed local Git metadata on `main`, added the exact `origin`, staged only the sanitized source allowlist; no commit due unresolved author identity.
- Verified local privacy/ignore gates, ledger validator, 9 unit tests and staged diff check; remote GitHub was left untouched.

## v2.3.0 final P2 checkpoint — 2026-11-05T13:09:28+07:00

- Updated sanitized aggregate reports, canonical memory, prompt log and phase ledger to the final private P2 continuation counts: 50 linked records, 214 observations, 40 extracted, 3 not accessible, 7 metadata-only, zero unresolved locators.
- Recorded 24/25 P1 partial-text routes with complete public HTML abstracts; a source record remains uncoded after incomplete capture.
- Recorded official HTML abstract retrieval for a source record/a source record; no thesis binaries or restricted files accessed.
- P2 remains validation-passed/approval-pending; independent second coder not run; P3–P9 remain gated.

## [0.1.0] - 2026-11-05

### Added
- Reusable local-first thesis workspace engine with isolated per-project manifests and T0–T9 ledgers.
- Starter source register, methodology profile, decision/approval register and hash-chained audit log for every new workspace.
- Structural checks for source provenance, exact locators, claim-to-source links, design-specific methodology readiness and analysis-run reproducibility metadata.
- Versioned institutional guideline, literature synthesis, research data provenance and human approval schemas.
- Multi-project isolation, path traversal, no-overwrite, sequential authorization/acceptance and audit-tampering tests.
- CI matrix for Python 3.10–3.12 and a platform implementation roadmap.

### Boundaries
- This release does not perform systematic literature review, verify source truth automatically, execute SPSS/SmartPLS/R analyses, certify statistical correctness, or generate/visually QA final DOCX/PDF documents.
- The existing reference-research P0–P9 ledger and each independent thesis T0–T9 ledger remain separate.


## 2026-11-05T15:58:00+07:00 — Reusable workspace platform v0.1.0 checkpoint

- Reconciled the newest Library bootstrap v2.3.0 and master continuation v2.4.0; retained the existing reference-research P0–P9 state and kept P2 human acceptance pending.
- Added a reusable local-first thesis workspace engine with per-project isolation, T0–T9 phase ledgers, project-specific source/claim registries, methodology readiness checks, analysis reproducibility metadata and hash-chained audit logs.
- Added institutional, literature, methodology, data, approval and analysis JSON schemas; added CLI commands for project creation, workspace validation/status, source checks, methodology readiness and analysis metadata.
- Added reproducible public-source manifest builder; refreshed manifest to 57 entries and verified 57/57 hashes.
- Runtime validation: 32/32 unit tests, phase-ledger validator, compileall, and end-to-end CLI workspace smoke test passed.
- Reconstructed local Git metadata only: `main` unborn, exact origin configured, 58 sanitized files staged, staged diff check passed. No author identity, commit or remote mutation.
- P1/P2 research packages remain outside the public source tree; P2 remains validation-passed/approval-pending.


## 2026-11-05T16:48:00+07:00 — v0.2.0 revalidation and reference integration checkpoint

- Corrected the earlier v0.2.0 test-count note: the current test suite contains 51 tests, and all 51 pass in the revalidation run.
- Re-ran the phase-ledger validator and Python compilation; both pass.
- Reconciled README and canonical-memory changes with the source manifest; the prior manifest had two stale hashes and has been regenerated.
- Confirmed the CLI surface includes workspace lifecycle, source/methodology/analysis checks, evidence-safe revision, a loopback-only local model adapter, claim-strength guard, writing-pattern catalogue and metadata-only DOI verification.
- Crossref and local-model live execution remain unverified in this environment; fixture/mock tests pass. No manuscript was sent to an external provider.
- Reference-research P0/P1 remain accepted within their recorded scope; P2 remains validation-passed/approval-pending; P3–P9 remain gated.
- Git staging remains source-only; eight P1/P2 governance records remain untracked/outside the public source allowlist. No commit, push, PR, release or repository-setting change was made.

## [0.3.0] — 2026-11-05

### Added
- Standard-library-only OpenAlex Works metadata search with a 1–25 result bound, selected-field requests, 24-hour per-workspace cache, bounded retry handling, redirect refusal and response-size limits.
- Explicit opt-in retrieval of OpenAlex `abstract_inverted_index`, with conservative reconstruction that rejects malformed/incomplete positional indexes.
- Project-scoped retrieval snapshots, DOI/OpenAlex identity deduplication, source-register integration and hash-chained retrieval audit events.
- Private CSV literature matrix and coverage summary; regenerated matrices preserve human-entered annotations and deliberately leave methods, samples, findings, limitations, relevance and research-gap analysis uncoded.
- Research snapshot and coverage JSON schemas; privacy, cost, provenance and operating-boundary documentation.

### Boundaries
- The adapter transmits only operator-entered search terms and bibliographic API requests. It does not inspect or transmit manuscripts, interview transcripts or unpublished project files.
- No PDF/full-text download, access-control bypass, automated quality appraisal, systematic review, source-truth verification or research-gap inference is implemented.
- OpenAlex OA labels do not establish reuse rights; `rights_status` remains `UNKNOWN`. A reconstructed abstract is recorded as `ABSTRACT_ONLY`, never as full-text review.
- Provider runtime was not live-verified in this environment; automated tests use deterministic fixtures/mocks. Cross-process locking and a multi-file transaction remain future hardening work.


## Repository activation — 2026-11-10

- Reconciled platform v0.8.0 with the v2.3.0 canonical governance ledger; ledger hash and schema match the sanitized bootstrap.
- Added aggregate-only public P0–P2 research status, sanitized P2 execution/recheck summaries, and a public content allowlist.
- Added privacy-safe, generalized thesis QA lessons; no source thesis content, Turnitin report identifiers/scores, respondent data, P1/P2 record-level data, abstracts or private archives are included.
- Platform and research-phase state remain separate. P2 acceptance remains pending and P3–P9 remain gated.


## [v0.8.0-public] — 2026-11-10

- Consolidated the validated v0.8.0 platform source with the sanitized P0/P1/P2 governance ledger and aggregate research reports.
- Replaced historical P1/P2 record-level notes in public phase documents with privacy-safe aggregate summaries; kept datasets, abstracts, source locators, private package hashes and thesis/Turnitin case files outside Git.
- Changed the phase-ledger schema/validator to distinguish `NONE` from the narrow `PUBLIC_ALLOWLIST_POPULATED` repository state. Unscoped remote mutations remain rejected; sequential P0–P9 research gates remain enforced.
- Replaced report-parser test metadata with fully synthetic values unrelated to the reference thesis/report.
- Revalidated: 200/200 platform regression tests; 29/29 JSON Schemas (Draft 2020-12); compileall; phase-ledger validator; 130/130 source manifest entries.
- Hardened the deterministic public-source packager for ZIP and TAR.XZ output, with manifest checksum enforcement, path-traversal/symlink rejection, fixed metadata and SHA-256 sidecars. The expanded TAR.XZ and checksum are excluded from the source manifest to avoid recursive hashing.
- Added regression coverage for deterministic packaging, checksum verification, stale manifests and unsafe archive paths.
- Added a one-shot GitHub Actions expansion workflow that verifies the archive, expands the full source tree to the repository root, reruns schema/manifest/ledger checks and the full unit suite before committing the expanded tree.
- GitHub repository activation is authorized only for the public allowlist. No private research data or thesis files are included.


## 2026-11-10 — public repository expansion checkpoint

- Verified the first GitHub `main` commit (`c51b223fcd4803006afbba9d68e891216b83ce0a`); it contains the initial README only.
- Prepared the complete sanitized public source package for expansion into the repository root, including platform modules, schemas, synthetic tests, CLI, documentation, CI, templates and aggregate-only governance status.
- Public source archive SHA-256 is recorded by its adjacent sidecar; source-tree manifest is independently verified.
- No P1/P2 record-level dataset, abstract/source text, thesis manuscript, respondent-level information or Turnitin report was added to the public allowlist.
- P2 acceptance remains pending; P3–P9 remain not authorized.


## 2026-11-10 — expanded public repository release preparation

- Expanded the public allowlist to include the complete reusable source implementation, 29 JSON Schemas, 200-test synthetic regression suite, CLI, templates, operations/quality/methodology documentation, phase governance, manifest and GitHub automation.
- Added deterministic TAR.XZ release packaging and one-shot root expansion. The transfer archive is verified against both its SHA-256 sidecar and the internal source manifest before any repository write.
- Local revalidation: **200/200 tests PASS**, **29/29 JSON Schemas PASS**, manifest integrity PASS, phase-ledger validation PASS and CLI smoke test PASS.
- Public scope remains aggregate-only for reference research. P2 human acceptance is pending, and P3–P9 remain gated.
