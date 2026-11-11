# Engineering Roadmap

This roadmap is for the reusable platform, not the P0–P9 reference-research programme and not an individual thesis T0–T9 ledger.

| Engineering release | Scope | Acceptance evidence |
|---|---|---|
| E0 — Workspace foundation | Manifest, isolation, lifecycle ledger, audit log, CLI; release 0.1.0 baseline | Multi-project tests, path-safety, no-overwrite, phase-gate tests — implemented and tested |
| E1 — Evidence engine | Source registry, retrieval snapshots, claim links, Crossref DOI metadata verification and private cache | Source/claim checks and Crossref fixtures implemented; OpenAlex metadata search, private cache/snapshots, DOI deduplication and checksummed write-ahead recovery added in 0.3.0/0.3.1; live runtime verification and source-screening workflow still pending |
| E2 — Methodology and academic reasoning | Design-specific readiness checks, research question/objective/construct/hypothesis/analysis traceability, mixed-methods integration structure, evidence-aware bilingual writing patterns and claim-strength guardrails | Deterministic alignment audit and scaffold implemented in 0.4.0; expert review, rubric validation, instrument/method validity and semantic benchmark still pending |
| E3 — Analysis adapters | v0.5.0 adds CSV dataset registration, hash-verified analysis specifications, human method decisions, T0–T6 gates and a deterministic descriptive-only engine. v0.5.1 adds write-ahead recovery; v0.5.2 adds pinned-input recovery, read-only computational replay and diagnostic summaries. Inferential tests and SPSS/SmartPLS/R adapters remain future work. | Synthetic descriptive fixtures, hash determinism, privacy suppression, tamper verification, abrupt process-kill recovery at four persistence boundaries, source-drift refusal, replay hash match, diagnostics read-only checks; native Windows/GitHub CI still pending |
| E4 — Document engineering | v0.6.0 implements researcher-supplied DOCX assembly, PDF rendering, page-mapped static TOC, APA7/IEEE citation rendering, verified analysis tables, workspace-local figures, institution-profile approval gates and provenance-pinned build records. | 175 full regression tests / 9 document tests; 8-page synthetic DOCX/PDF visual inspection; document build/verify/audit CLI smoke. Real institutional profile review and native Windows/GitHub CI remain pending. |
| E5 — Research and citation adapters | Provider interfaces, Crossref and OpenAlex metadata adapters; future reference-manager integrations | Crossref fixtures and OpenAlex query/cache/429/retry/provenance tests; API integration is code-tested but live runtime behavior and broader connector parity remain pending |
| E6 — Operator and client workflow | Intake, scope/pricing, approvals, revision tracking and export | Role/permission matrix, client-isolation tests, human acceptance records |
| E7 — Red-team and release | Adversarial tests, security/privacy review, packaging and recovery | Red-team report, dependency audit, clean install, restore drill |

Platform v0.3.0 added an initial OpenAlex retrieval slice; v0.3.1 hardens its persistence and recovery; v0.4.0 adds a deterministic research-alignment audit on top of v0.2.0 evidence-safe writing/revision and Crossref metadata verification. It does not complete the full E1/E2 work packages or a systematic literature review. Platform v0.5.0 implements only the descriptive-only portion of E3; it is not an inferential statistical package and does not claim parity with SPSS, SmartPLS, R or specialist Python libraries. No release is complete because its prompt or documentation exists. Each release needs executable code, deterministic tests, artifacts and acceptance evidence. High-stakes academic judgments remain human-reviewed.


Platform v0.5.1 closes the first statistical-run persistence recovery gap; v0.5.2 adds source-pinned restore, same-engine replay and read-only diagnostic reporting. These releases still do not implement inferential procedures or external SPSS/SmartPLS/R adapters.


Platform v0.6.0 completes the first E4 document-engineering slice. It creates reviewable drafts rather than submission-ready theses; institution-specific compliance, citation completeness and academic correctness require human validation. The rendered fixture is synthetic and does not represent a real research manuscript.
