# P0–P2 Research Status — Public Aggregate Summary

**Canonical ledger:** `config/pipeline/PHASE_LEDGER.json` (v2.4.0).  
**Checkpoint:** 2026-11-14 (Asia/Jakarta).

| Phase | Status | Accepted/authorized scope |
|---|---|---|
| P0 — Research Charter & Integrity | `COMPLETE_AND_APPROVED` | Scoped governance baseline under APR-P0-001. |
| P1 — Cross-Domain Thesis Corpus | `COMPLETE_AND_APPROVED` | 50-record bibliographic eligibility corpus under APR-P1-001; no claim of 50 full-text reviews. |
| P2 — Thesis Extraction & Coding | `COMPLETE_AND_APPROVED` | Scoped public abstract/item-page extraction accepted under APR-P2-001; validation remains PASS_WITH_LIMITATION. |
| P3 — Cross-Domain Synthesis | `VALIDATION_PASSED_APPROVAL_PENDING` | Candidate generated under AUTH-P3-P9-001; validation passed with limitations; human acceptance pending. |
| P4–P9 | `NOT_STARTED / PRE-AUTHORIZED CONDITIONALLY` | AUTH-P3-P9-001 records standing authorization; each phase remains gated by acceptance of its immediate predecessor. |

## P1 aggregate profile

- 50 canonical bibliographic records, 10 primary domains with five records per domain.
- Access depth: 25 partial-text-reviewed, 18 abstract-only, 7 metadata-only, 0 full-text-reviewed.
- Human acceptance is scoped to bibliographic eligibility and disclosed limitations only.

## P2 aggregate profile

- 50 P1-linked record shells; 214 abstract-level observations.
- 40 records with abstract observations; 3 without content observations due to access/retrieval limitations; 7 metadata-only; zero unresolved abstract locators.
- 24/25 partial-text routes yielded complete publicly visible HTML abstracts; 16/18 abstract-only records were coded; metadata-only records remain uncoded.
- No thesis full-text/chapter/appendix extraction is claimed. Independent second coder remains `NOT_RUN`; semantic review remains `SELF_REVIEW_ONLY`.
- P2 technical validation passed with limitations. The project owner explicitly selected ACCEPT on 2026-11-14 for the disclosed abstract/item-page scope; independent second coder remains NOT_RUN and semantic review remains SELF_REVIEW_ONLY.

## P3 status

See `docs/research/P3_PUBLIC_STATUS.md` for the sanitized aggregate synthesis status. P3 has been executed and technically validated with limitations but has not been human-accepted.

## Governance limits

The P0–P2 record-level corpora, abstracts, bibliographic source registers, exact locators, adjudication logs, coding rows, source recheck tables and private archives remain outside this repository. This public page exposes aggregate status only. Platform engineering tests do not alter research-phase acceptance. Conditional pre-authorization for P4–P9 does not permit execution before each immediate predecessor is COMPLETE_AND_APPROVED.
