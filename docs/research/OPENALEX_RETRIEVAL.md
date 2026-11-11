# OpenAlex metadata retrieval adapter (platform 0.3.1)

## Purpose

`research-search` retrieves public scholarly-work metadata from the OpenAlex `/works` endpoint and records the retrieval in one independent thesis workspace. It is a search and provenance adapter, not a systematic-review workflow or source-quality validator.

## Data and transfer boundary

The operator-supplied search query is transmitted to `https://api.openalex.org/works`. The default request selects bibliographic fields only. `abstract_inverted_index` is omitted unless `--include-abstracts` is supplied. No title, abstract, manuscript paragraph, interview transcript, personal data, raw dataset, or unpublished research file is read from the workspace or transmitted by the adapter.

An optional `OPENALEX_API_KEY` environment variable is sent as an Authorization bearer header. It is not written to cache files, snapshots, logs, stdout or source records. OpenAlex currently publishes a $0.10/day anonymous API budget and a $1/day free-key budget (no payment method required); a direct `search=` API call is priced at $1 per 1,000 calls, or approximately $0.001 each. The adapter runs one request per invocation. See the current [pricing](https://help.openalex.org/access/pricing/), [example costs](https://help.openalex.org/access/example-costs/) and [search](https://help.openalex.org/api/searching/) documentation before high-volume use. OpenAlex's basic API is available without an API key. The optional `--mailto` parameter identifies a contact address for the polite pool; it is not required.

No PDF or full-text download is implemented. No access-control bypass, paywall bypass, or automated repository harvesting is performed.

## Command

```bash
project-skripsi research-search <workspace> \
  --query "digital literacy university students Indonesia" \
  --per-page 10
```

Optional abstract retrieval:

```bash
project-skripsi research-search <workspace> \
  --query "digital literacy university students Indonesia" \
  --per-page 10 \
  --include-abstracts
```

Flags:

- `--per-page`: 1–25 results; one page per call in this release.
- `--include-abstracts`: explicitly request OpenAlex's abstract inverted index and store the reconstructed abstract.
- `--mailto`: optional polite-pool contact.
- `--no-cache`: bypass cache read and write.

Each snapshot preserves both `created_at` (local persistence time) and `retrieved_at` (provider/cache retrieval time). The default cache lifetime is 24 hours and is stored under the project's private `sources/cache/openalex/` directory. Retrieval snapshots are stored under `sources/snapshots/`; normalized source records are appended to `sources/registry/source_register.json`; a hash-chained audit event records the snapshot reference. Search snapshots are append-only and are not overwritten. Repeated results are deduplicated in the source register by normalized DOI or stable OpenAlex-derived source ID.

## Literature matrix and coverage summary

After one or more retrievals, run:

```bash
project-skripsi literature-matrix <workspace>
```

This writes `literature/matrix/literature_matrix.csv` and `literature/matrix/literature_coverage.json`. The matrix combines registered bibliographic metadata with abstracts explicitly saved in OpenAlex snapshots. It provides blank fields for screening decisions, research-question mapping, theory, method, population/context, variables/themes, findings, limitations, relevance and research-gap notes. Those fields are intentionally not inferred from titles or metadata.

When the CSV is rebuilt, recognized human annotation columns are preserved by `source_id`; malformed or duplicate-key existing matrices are rejected instead of overwritten. Spreadsheet formula-like text from provider records is escaped before writing. Output paths must remain directly inside the project's `literature/matrix/` directory. Coverage counts describe the records' current access/review-state distribution only; they do not measure representativeness, completeness, methodological quality or saturation.

## Access-status and rights semantics

| Condition | Source register status | Meaning |
|---|---|---|
| Default metadata-only query | `METADATA_ONLY` | Bibliographic metadata retrieved; it cannot support content-derived claims. |
| Explicit request and valid reconstructed abstract | `ABSTRACT_ONLY` | Abstract text saved in the private retrieval snapshot; claim links may cite abstract-scope content only. |
| No valid DOI | DOI is `null` | OpenAlex ID is used for stable source identity; the record remains usable as a metadata candidate. |

`rights_status` remains `UNKNOWN`, even when OpenAlex labels a work open access. A provider's OA flag or deposited license label is not treated as independent confirmation of the publication's license or reuse rights. The `license` field records the provider's location-level statement when present; operators must verify the source's actual terms.

OpenAlex stores abstracts as `abstract_inverted_index`, which the adapter reconstructs by positional order. If positions are incomplete or malformed, the adapter omits the abstract rather than filling gaps or inventing text. The reconstructed abstract can still contain indexing artifacts and is not full text.

## Reliability and security

- Maximum results per call: 25.
- HTTP timeout: 20 seconds by default, configurable in the Python adapter up to 60 seconds.
- Retry count: at most two retries by default; bounded exponential backoff for transient HTTP/network failures.
- `Retry-After` values above the 10-second automatic wait threshold are surfaced to the operator instead of causing a long block.
- Redirects are refused; only the OpenAlex works API endpoint is requested.
- Response limit: 10 MiB.
- Cache and snapshot writes use temporary files and atomic replacement; POSIX files are restricted to mode `0600`, directories `0700` on a best-effort basis.
- Per-workspace storage and manifest validation prevent cross-project source-register writes.

## Persistence, crash recovery and integrity checks (0.3.1)

The retrieval sequence is protected by a kernel-managed project lock (`state/.research.lock`) and a write-ahead journal under `state/research-transactions/`. Each new journal records a SHA-256 checksum over its immutable transaction payload. This detects accidental or partial journal modification; it is not a keyed signature and does not protect against a malicious actor who can rewrite the journal and checksum.

Persistence proceeds in this order: durable journal, atomic snapshot write, atomic source-register update, idempotent audit append, journal retirement. If the process stops at any point, the journal remains for the next explicit recovery. Audit events use their snapshot-specific idempotency key, so a retry after the audit append but before journal deletion does not create a second event. Reusing an idempotency key with a different event payload is rejected.

Run a read-only check first:

```bash
project-skripsi research-integrity <workspace>
```

A clean workspace returns `PASS`. A valid pending transaction returns `RECOVERY_REQUIRED`; the check does not alter research artifacts or repair content, although kernel-lock sidecar files may be created when a lock has not existed before. To apply pending transactions, explicitly run:

```bash
project-skripsi recover-research <workspace>
```

Then run `research-integrity` again. A malformed/checksum-invalid journal, orphan snapshot, missing audit event, or invalid audit chain returns `FAIL` and requires operator investigation; the engine does not silently discard or overwrite such data. The lock is automatically released by the operating system after process termination. POSIX flock behavior is covered by multi-process and process-termination tests; Windows uses the `msvcrt` byte-range lock implementation and still requires native Windows validation.

## Non-goals and required human review

This adapter does not rank source quality, verify peer review, confirm journal indexing, validate source relevance, screen inclusion/exclusion criteria, verify an abstract's claims, prove a gap exists, or establish that a source supports a thesis claim. It does not automatically create claim-evidence links. Human screening, primary-source inspection where accessible, license review, and citation verification are required before academic use.

The provider's bibliographic metadata is a discovery aid. Record-level metadata, abstracts, citation counts, OA status, source types and DOI links can be incomplete or wrong and must be checked against the publisher/repository record.

## Verification status

Unit tests use controlled fixtures/mocks for HTTP, cache, retries, redirects, normalization, project isolation, audit provenance and deduplication. A passing test suite is not a live OpenAlex runtime test. Live provider access remains separately unverified until an operator executes the command in a network-enabled runtime and reviews its output.
