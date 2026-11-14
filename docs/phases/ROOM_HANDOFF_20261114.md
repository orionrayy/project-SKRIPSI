# Project-SKRIPSI Room Handoff — 2026-11-14

## Canonical state

- Repository: `orionrayy/project-SKRIPSI`
- Canonical memory: `ORCHESTRATION_MEMORY.md` v1.6.0
- Canonical phase ledger: `config/pipeline/PHASE_LEDGER.json` v2.4.0
- Candidate branch: `feature/document-layout-case-learning`
- PR #1: open, draft, unmerged; target `main`
- Main branch remains unchanged by this candidate work; platform release baseline remains v0.8.0.

## Research governance

- P0: COMPLETE_AND_APPROVED (APR-P0-001), unchanged.
- P1: COMPLETE_AND_APPROVED (APR-P1-001), 50-record bibliographic eligibility corpus only; no full-text review implied.
- P2: COMPLETE_AND_APPROVED under APR-P2-001. The project owner explicitly selected ACCEPT on 2026-11-14 for the documented abstract/item-page scope. Technical validation remains PASS_WITH_LIMITATION.
- P3: executed and validation-passed-with-limitations; human acceptance pending.
- P4–P9: explicitly authorized conditionally under AUTH-P3-P9-001; all remain NOT_STARTED until the immediate predecessor is COMPLETE_AND_APPROVED.

## P2 acceptance scope

50 P1-linked record shells; 214 abstract-level observations; 40 records with observations; 3 inaccessible; 7 metadata-only; zero unresolved abstract locators. There is no full-text/chapter/appendix/PDF coding claim. Independent second coder is NOT_RUN and semantic review remains SELF_REVIEW_ONLY.

## P3 candidate

Private package: `project_skripsi_P3_private_v1.0.0.zip` (13 members, ZIP CRC PASS, SHA-256 verified; private P1/P2 evidence references remain inside the private package only).

- 10 findings: 8 content findings and 2 corpus coverage/composition findings.
- 120 domain-by-code matrix rows.
- 173 private evidence references.
- Draft 2020-12 schema, linkage, observation provenance and 13-file package manifest: PASS.
- Confidence capped at MODERATE; no HIGH confidence.
- One MTH-04 codebook-fit exception is disclosed and excluded from the conservative sampling-strategy count.
- No official policy corpus was reviewed; no normative university requirement is claimed.
- P3 acceptance report remains PENDING; P4 is not active.

Sanitized status is published at `docs/research/P3_PUBLIC_STATUS.md`. Do not copy P1/P2 record IDs, source URLs, abstracts, institution names, source locators or private extraction rows into public artifacts.

## Platform engineering

The layout-QA feature and sanitized case-learning candidate are part of draft PR #1. The first full CI run had 3/3 Ubuntu jobs and Windows Python 3.11 pass; Windows Python 3.10/3.12 failed only the stable-hash mutation regression because the fixture rewrote a file with the same size. The fixture now writes a different-size payload; production hash code is unchanged. Recheck the full six-job matrix against the new head before ready-for-review. Do not mark CI green until all jobs pass.

## Next action

Obtain the owner's P3 acceptance decision after presenting the P3 findings and limitations. Continue no further than P3 in this execution unit. P4–P9 retain conditional authorization but require sequential predecessor acceptance. Do not merge, release, or deploy from this checkpoint.
