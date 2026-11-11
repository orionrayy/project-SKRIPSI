# Reusable Platform Architecture

**Platform baseline:** 0.1.0 · **Posture:** local-first modular monolith

## 1. Purpose

Project-SKRIPSI is a reusable academic research and thesis-engineering framework. It is not a service that writes a thesis in place of a student. It provides controlled project setup, source provenance, research-design checks, reproducible-analysis records, document QA, auditability and phase-gated workspaces. Each student remains the author and remains responsible for the research, data, interpretation and institutional disclosure.

## 2. Keep three workstreams separate

1. **Platform engineering** evolves the reusable software, schemas, tests, workflows and documentation in this public source repository.
2. **Reference-research programme P0–P9** is the current cross-domain research/benchmark programme recorded by `config/pipeline/PHASE_LEDGER.json`. At this checkpoint P0/P1 are accepted within their bounded scope; P2 is validation-passed with limitations but awaits human acceptance; P3–P9 remain gated.
3. **Individual thesis lifecycle T0–T9** is instantiated once per thesis under a unique `project_id`. These ledgers and artifacts are independent from the reference-research programme and from other students.

A P-phase completion does not complete a T-phase. A T-phase in one thesis never authorizes a phase in another thesis.

## 3. Logical components

- **Control plane (public):** CLI, schemas, templates, methodology profiles, validation rules, general guidance, test fixtures and CI.
- **Project workspace (private/local by default):** project manifest, university/programme requirements, literature matrix, methodology, ethics/permissions, data, analysis, manuscript, revisions, deliverables, approvals and audit events.
- **Evidence plane:** source registry, retrieval/access metadata, exact locators, claim-to-source links, source hashes where lawful, and missingness records.
- **Quality plane:** deterministic contract checks, design-specific readiness reports, document conformance checks, statistical diagnostics and human review records.
- **Adapters (optional):** reference managers, institutional repositories, Crossref/OpenAlex, SPSS/SmartPLS/R/Python, DOCX/PDF tooling and approved storage. An adapter must not bypass project privacy or phase gates.

## 4. Project isolation

The default CLI workspace root is `.private/workspaces/`, which is ignored by Git. Each project uses a non-reused `project_id`; all source IDs, evidence links, approval records, analysis runs and audit events are scoped to that ID. Do not copy raw data, participants, interviews, consent forms, student identities, unpublished theses or private drafts into this public repository.

Shared platform knowledge may include generic methodology guidance and public institutional requirements with provenance. It must not silently inherit a previous student's research content or decisions.

## 5. Runtime posture

The first implementation is standard-library-only Python. Runtime dependencies are intentionally absent. Optional extras are declared for DOCX handling, JSON Schema validation and network research adapters, but must be installed only when a task needs them. The default path does not upload data or call paid services.

## 6. Current implementation boundary

Implemented in baseline 0.1.0: workspace initialization, unique project-ID validation, per-project manifest and T0–T9 ledger creation, sequential phase-gate checks, local append-only hash-chained audit events, source-register structural checks, claim-source referential checks, methodology readiness checklist and analysis-run metadata validation.

Not implemented or not accepted as production capability yet: automated source truth verification, full systematic literature review, discipline-complete methodology approval, SPSS/SmartPLS/R statistical execution, statistical-result correctness certification, full-text document understanding, DOCX/PDF visual QA, plagiarism/similarity interpretation, human reviewer workflow, multi-user access control and secure hosted tenancy. These require separate modules, tests and evidence.
