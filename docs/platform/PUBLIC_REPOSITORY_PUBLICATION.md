# Public Repository Publication Policy

## Authorized publication scope

The project owner explicitly instructed on 2026-11-10 that the previously empty public repository be populated with Project-SKRIPSI platform and research status. This authorizes the allowlist below only. The repository was already public; no visibility or settings change was requested or performed.

### Allowlist

- Platform source v0.8.0, schemas, generic documentation, CI configuration and synthetic regression fixtures.
- Canonical governance ledger with P0/P1/P2 statuses and aggregate-only evidence summaries.
- Public, aggregate phase status and generalized privacy-safe QA lessons.
- Release manifest and checksum for the sanitized source bundle.

### Excluded material

- P1/P2 CSV/JSON datasets, source/evidence registers, record IDs, abstracts, source URLs and exact locators.
- Private extraction/coding/adjudication/source-recheck/coverage matrices and packages.
- Thesis DOCX/PDF, Turnitin reports, report/submission identifiers, similarity scores, source labels, original/revised passages, marked-region registers and case-specific QA reports.
- Participant identities, pseudonymous row-level keys, individual scores/measurements and consent/institutional records.
- Secrets, credentials, tokens, cookies, private keys, databases, source caches and local runtime artifacts.

## Governance invariants

P0/P1 statuses remain unchanged. P2 remains validation-passed with limitations and awaits explicit human acceptance. P3–P9 remain not started/not authorized. No public repository operation changes research acceptance or authorization.

## Integrity and licensing

The source bundle includes its own SHA-256 manifest; the external bundle checksum is stored next to the bundle. No software license is declared unless a separately approved license file is added. Public visibility does not grant redistribution rights to third-party source material.


## Expanded-source publication protocol

The public source release uses an explicit `MANIFEST.sha256` allowlist. `scripts/package_public_source.py` can create deterministic ZIP or TAR.XZ archives, rejects stale hashes, path traversal, symlinks and blocked research-document/database suffixes, and writes an adjacent SHA-256 sidecar. The one-shot `.github/workflows/expand-public-source.yml` workflow checks the release archive and internal manifest, extracts only regular safe members, reruns schema, manifest, phase-ledger, compile and regression checks, and fast-forwards the expanded source tree to `main`.

The workflow is a transport mechanism, not a governance bypass. Its successful engineering checks cannot fill a human acceptance record, advance P2, or unlock P3–P9. Only the sanitized allowlist and aggregate summaries are published.


## Publication verification checkpoint — 2026-11-11

**Status: EXPANDED SOURCE PUBLICATION VERIFIED.**

- Bootstrap commit: `ce24e8a4051658de4412aded3ca43602d8fbc750`.
- Expansion workflow run #2: [43002256443](https://github.com/orionrayy/project-SKRIPSI/actions/runs/43002256443) — `success`.
- Automated expansion commit: [`a667940306d57d83032ad973985c504fb7774a30`](https://github.com/orionrayy/project-SKRIPSI/commit/a667940306d57d83032ad973985c504fb7774a30).
- Expanded tree: `a8f3c08429582d2ff62e912a5f73fb191cd65503`; 133 file blobs, 49 directories, 130 manifest-listed source files, `MANIFEST.sha256`, archive and checksum sidecar.
- Distribution archive: 169,800 bytes; SHA-256 `bcade06f387de89a1c93dd468ff8ff4baf474c4f8976284e2091a1bce6ef805f`. Remote Git blob SHA `311cd93a46715a3c61a1e9cbb6c2e6a3164af644` matches the local archive bytes.
- Expansion workflow steps for reconstruction/checksum, allowlist-safe extraction, dependency/renderer installation, source validation, and cleanup/commit all concluded successfully. The recorded platform baseline is 200/200 unit/regression tests, 29/29 JSON Schema meta-validation, compileall, ledger validator, manifest, and CLI smoke test.

The separate cross-platform CI matrix has not yet been observed passing on the expanded tree. The bootstrap CI run was skipped by design, and the earlier pre-expansion CI run failed against the README-only repository. A later non-bootstrap push or manual CI run is required before claiming the Ubuntu/Windows Python matrix passed.

Publication does not change research status: P0/P1 remain accepted within their recorded scopes; P2 remains validation-passed with limitations and APR-P2-001 blank; P3–P9 remain not started/not authorized. The workflow cannot create a human research decision or authorize a later phase.
