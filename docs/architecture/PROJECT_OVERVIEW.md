# Project Overview

## Mission

Provide a reusable, auditable, evidence-driven environment for academic research and thesis engineering across disciplines, research designs, languages and institution-specific requirements.

## Architectural posture

Start with a modular monolith and explicit contracts. Avoid premature distributed services. Keep each capability behind a clear boundary and make external systems optional adapters.

## Planned capability areas

- Project workspace and manifest management.
- Source discovery and bibliographic verification.
- Corpus ingestion and provenance tracking.
- Thesis extraction/coding and coverage reporting.
- Cross-domain evidence synthesis.
- Institution-specific requirement registry.
- Methodology/data-validity checks.
- Citation/evidence traceability.
- Semantic editing and authorial consistency support.
- Document engineering and visual QA.
- Workflow orchestration, audit, versioning and recovery.

These are architectural targets, not claims that production engines already exist. Phase P8 remains unstarted; this bootstrap only establishes minimal local governance, ledger validation and repository scaffolding.

## Data separation

Public general knowledge may be shared. Every real thesis project has a unique `project_id` and separate sources, requirements, research data, methods, drafts, revisions and audit records. Raw thesis files and all non-public/sensitive content stay outside the public repository by default.

## Phase dependencies

P0 governance -> P1 verified corpus -> P2 extraction/coding -> P3 cross-domain synthesis -> P4 institution compliance -> P5 methodology/data validity -> P6 evidence/citation/ethics -> P7 semantic writing -> P8 engineering -> P9 red-team/final compilation.
