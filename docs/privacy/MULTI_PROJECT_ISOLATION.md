# Multi-project Isolation & Data Boundaries

## Default rules

- One thesis = one unique `project_id`, one workspace root, one manifest, one lifecycle ledger and one audit log.
- The public Git repository contains generic code, schemas, templates and de-identified fixtures only.
- Actual workspaces are created under `.private/workspaces/` and are excluded by `.gitignore`.
- Store raw data separately from processed data. Preserve raw originals read-only where practicable; record hashes and every transformation.
- Do not reuse participants, private datasets, drafts, decisions, institution records or supervisor feedback across projects.
- Shared guidance must be generic, sourced and versioned. Each university/programme profile must reference the exact official document and version.
- External AI/storage/research adapters are disabled by default for private workspaces. Require a separate lawful basis, data-minimization review and explicit authorization before transfer.

## Minimum data classification

`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`. The CLI defaults every project to `CONFIDENTIAL` and `LOCAL_ONLY`. Unknown personal-data/ethics flags remain `null` until assessed; do not interpret null as no risk.

## Secret and privacy response

Never commit `.env`, API keys, cookies, credentials, student identifiers, phone numbers, signatures, respondent contact details, consent forms, unredacted interviews or unpublished thesis content. If a sensitive file is accidentally staged, unstage it and inspect Git history; deleting the working file alone does not remove it from history.
