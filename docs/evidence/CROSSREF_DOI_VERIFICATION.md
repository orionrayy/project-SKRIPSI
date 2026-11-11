# Crossref DOI metadata verification

Project-SKRIPSI can retrieve a single Crossref work record by DOI using the public Crossref REST API. The API does not require registration for public use; Crossref documents `/works/{doi}` and recommends a polite-pool contact parameter or User-Agent identification. See the [official REST API documentation](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) and [REST API technical guide](https://github.com/CrossRef/rest-api-doc).

## Data boundary

The adapter transmits the DOI identifier and optional contact email only. It does not transmit a manuscript, abstract, thesis title, research question or candidate text. A user may optionally compare supplied expected bibliographic metadata locally with returned metadata. Cache filenames are SHA-256-derived from the DOI and cached JSON is stored with user-only file permissions when supported.

## What is checked

- DOI syntax and retrieval from Crossref.
- Title, year, author and journal-title comparisons when the caller supplies expected values.
- Retrieval time, cache hit state, source endpoint and mismatch flags.

## Limitations

Crossref metadata is deposited by publishers/members and may be incomplete or inaccurate. Successful lookup does not prove the article exists as described in the thesis, validate its content, verify peer review, establish journal indexing or quartile, confirm access/license rights, or prove that a citation supports a claim. Non-Crossref DOIs may not be found. A mismatch is a review trigger; the tool never overwrites the student's reference automatically.

## Command

```bash
project-skripsi verify-doi 10.1234/example-doi \
  --expected .private/expected-reference.json \
  --cache-dir .private/cache/crossref \
  --mailto contact@example.org \
  --output .private/doi-verification.json
```

This is a bibliographic retrieval aid, not a substitute for reading the source and recording exact claim locators.
