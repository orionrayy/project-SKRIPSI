# Remote and Data Boundaries

## Repository identity

- Remote: `https://github.com/orionrayy/project-SKRIPSI`
- Owner/repository: `orionrayy/project-SKRIPSI`
- Visibility observed: public
- Default branch metadata: `main`
- Latest read-only API audit: root contents 404 `This repository is empty`; branches `[]`; commits endpoint 409 `Git Repository is empty`; releases `[]`; workflow runs `0`.

## Local-only state

The bootstrap creates a local Git working tree and `origin` reference only. It does not activate or populate GitHub. At this checkpoint no remote branch, commit, PR, release, settings change or publication exists.

## Approval constraints

`APR-P0-001` approves the P0 governance baseline and separately authorizes P1 local work on public bibliographic metadata. It does not approve P1 output acceptance, P2 execution, publication of P0/P1 artifacts, processing restricted/private/participant data, external transfer, or institutional/legal/ethics certification.

UD-001 through UD-007 remain open according to their action-specific/per-project scope. Do not push, publish, upload private data or alter repository settings until the proper approval is recorded.

## Excluded from Git

P1 corpus JSON/CSV, source ledger, evidence register, source PDFs, local archives, private thesis drafts, respondent/participant data, credentials and local environment files remain outside this repository and are covered by `.gitignore` patterns where applicable.
