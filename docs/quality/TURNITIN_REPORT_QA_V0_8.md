# Turnitin Report QA — v0.8.0

## Purpose and boundary

The optional `pdf-qa` component parses exported Turnitin Similarity Report PDFs locally. It extracts only report metadata, visible exclusions, the rendered top-source list, and visible numeric source badges on thesis pages. It does not store thesis paragraph text, download underlying matched sources, determine plagiarism, predict AI-detection results, or estimate a score before a future Turnitin submission.

Install the optional dependency with:

```bash
python -m pip install -e '.[pdf-qa]'
```

## Commands

Audit one report:

```bash
project-skripsi turnitin-report-audit path/to/turnitin-report.pdf \
  --output .private/reports/turnitin-audit.json
```

Compare two report exports:

```bash
project-skripsi turnitin-report-compare baseline-report.pdf current-report.pdf \
  --output .private/reports/turnitin-comparison.json
```

Outputs are no-overwrite JSON reports. Use a private output directory because top-source labels can contain authors, repository names, or unpublished-work metadata.

## What is extracted

- Submission ID, submission date, filename and PDF SHA-256.
- Report page count, thesis page count as printed, word/character counts as printed.
- Overall Similarity and the source-category percentages, kept separate (they may overlap and must not be summed).
- Visible exclusions such as Bibliography and Quoted Text.
- Numbered top-source entries rendered in the exported report, with source class and the reported share string.
- Visible source-badge occurrences on the thesis pages, unique IDs, page coverage, unreadable badge shapes, and badge IDs that do not resolve to a source entry.

Badge occurrence counts are drawing-level metadata. They are not matched-word counts, unique passages, or a measure of plagiarism severity.

## Comparison semantics

The comparison reports percentage-point deltas, relative change from the baseline, visible category deltas, word-count/page-count deltas, top-source entry deltas, and badge-count deltas. It labels the reports `COMPARABLE_VISIBLE_SETTINGS` only when the visible exclusions match. It still records that database and account-side configuration cannot be verified from PDFs alone.

A 39% to 29% difference is therefore a descriptive comparison of two exports, not a causal estimate of the effect of a particular edit and not a plagiarism verdict.

## Empirical evidence extensions

The v0.8 empirical consistency audit adds:

- Explicit presence/absence of the paired-test output table.
- Evidence that the paired-difference distribution was reviewed and an assumption diagnostic/method was recorded.
- A warning when row-order pairing is stated without a verified unique matching key.
- Per-instrument validity evidence, preventing a questionnaire's Aiken's V table from being implicitly treated as validation evidence for a different oral-performance rubric.
- Aiken's V item-coverage checks against the declared item count for the specific instrument.

A missing form in an exported report is reported as evidence not visible in that package; it is not proof that the study never performed the validation.

## Privacy and research governance

The parser is local-only and does not call a network service. The output should be stored under `.private/` or another access-controlled location. Never commit real Turnitin reports, thesis paragraphs, respondent identities, raw scores, or private source labels to the public source repository. The parser does not alter the P0–P9 research phase ledger, approve a research phase, or authorize publication.

## Known limitations

- Source-list parsing depends on the text layout of the exported Turnitin PDF and may need a version-specific adapter if the provider changes the export layout.
- Some source metadata may be omitted, truncated, or wrapped differently in the PDF export.
- The tool does not inspect the original underlying matched-source documents or verify whether each match is correctly cited.
- Identical visible exclusions do not prove identical databases, account options, institution settings, or report-generation configuration.
- Visual badge extraction is a PDF drawing heuristic and must be checked if the report layout changes.
- It does not calculate inferential statistics; it checks whether declared evidence for the selected analysis is present and traceable.
