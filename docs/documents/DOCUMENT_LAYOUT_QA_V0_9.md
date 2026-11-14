# Rendered Document Layout QA — v0.9 engineering proposal

**Status:** feature-branch candidate; not a released platform capability  
**Baseline:** Project-SKRIPSI 0.8.0  
**Primary command:** `audit_document_layout.py`

## 1. Why this module is separate

`documents.py` already builds evidence-linked DOCX/PDF drafts, converges a static TOC against rendered PDF page positions, pins build inputs/outputs, and performs a DOCX package/structure audit. Those checks are valuable but do not prove the final visible page-number sequence, cover suppression, footer location, or conformance of the exact rendered pair to a task-specific page-layout profile.

This module adds a separate, read-only QA pass over the DOCX and its corresponding exported PDF. It complements `document-build`, `document-verify` and `document-audit`; it does not replace them.

## 2. CLI

From a source checkout:

```bash
python scripts/audit_document_layout.py \
  .private/workspaces/PROJECT-ID/deliverables/final.docx \
  .private/workspaces/PROJECT-ID/deliverables/final.pdf \
  --policy .private/workspaces/PROJECT-ID/requirements/document-layout-policy.json \
  --output .private/workspaces/PROJECT-ID/audit/document-layout-audit.json
```

The report writer refuses to overwrite an existing path. Choose a unique report path for every audit run. The command returns exit code 1 only for `FAIL`; `WARN` remains a nonzero-failure-free result and must still be reviewed by the operator.

Install the relevant optional extras:

```bash
python -m pip install -e ".[docx,pdf-qa]"
```

The CLI inserts `src/` into `sys.path`, so it works from a source checkout without an editable install when dependencies are available.

## 3. Policy contract

The policy is a JSON object validated by `schemas/quality/document-layout-policy.schema.json`. Supported fields:

| Field | Meaning |
|---|---|
| `page_size` | Expected section size: A4 or LETTER |
| `margins_cm` | Expected top/right/bottom/left margins |
| `font_family`, `font_size_pt`, `line_spacing` | Expected Normal style typography |
| `cover_pages` | Number of physical PDF cover pages excluded from numbering |
| `body_start_number` | Printed number shown on the first page after the cover |
| `page_number_position` | Footer detection zone: center, left or right |
| `footer_band_start` | Vertical threshold as a fraction of page height |
| `expected_page_count` | Optional total physical PDF page count |
| `require_dedicated_cover_section` | Whether one or more cover sections are mandatory |
| `min_page_text_chars` | Optional threshold for sparse-page warnings |
| `expected_page_map` | Heading text to expected displayed page number map |

The example at `tests/fixtures/document_layout/case_expected_policy.json` is a de-identified regression profile. Its exact page count and TOC map are case observations, not universal academic rules. A production institutional profile must be separately reviewed and version-pinned by a human.

## 4. Output and status semantics

The result is validated against `schemas/quality/document-layout-audit.schema.json` and reports structural metrics only. It intentionally omits filenames, absolute paths, manuscript text, personal identifiers and input hashes. Artifact identity and hash provenance remain the responsibility of the private document build record / artifact-manifest system.

- `PASS`: no configured mechanical finding was raised.
- `WARN`: one or more review findings remain, but no configured error was raised.
- `FAIL`: at least one configured error was raised.

Key finding codes include:

- `COVER_PAGE_NUMBER_VISIBLE`
- `BODY_PAGE_NUMBER_SEQUENCE_MISMATCH`
- `NONSTANDARD_ZERO_BASED_COVER_NUMBERING`
- `MISSING_DEDICATED_COVER_SECTION`
- `TOC_HEADING_NOT_FOUND`
- `TOC_PAGE_MAP_MISMATCH`
- `PAGE_SIZE_MISMATCH`
- `MARGIN_MISMATCH`
- `FONT_FAMILY_MISMATCH`
- `FONT_SIZE_MISMATCH`
- `LINE_SPACING_MISMATCH`
- `IMAGE_ALT_TEXT_MISSING`
- `SPARSE_BODY_PAGE`

The auditor distinguishes the physical PDF page index from the displayed page number. For example, physical page 2 can correctly display page number 1 when physical page 1 is an unnumbered cover.

## 5. Pagination implementation guidance

Preferred structure when a cover must be unnumbered:

1. Cover section with no page-number field in its first/default footer.
2. Explicit section break before front matter/body according to the campus requirement.
3. Next section with page-number field enabled, explicit restart at 1, and deliberate `header.is_linked_to_previous` / `footer.is_linked_to_previous` values.
4. Re-render and verify the physical-to-displayed page mapping in PDF.

A one-section workaround using `different_first_page_header_footer` plus `w:pgNumType start="0"` can produce the expected visual sequence in one renderer. The auditor reports this as a warning by default and an error when `require_dedicated_cover_section` is true. It should not be treated as a portable default.

## 6. Security and privacy

The auditor is offline and read-only. It does not send document text or files to external services. It emits counts, layout metadata and findings, not page text, author names, student numbers, source citations or filenames. The report belongs in the private project workspace. Do not commit real DOCX/PDF files, original logos, student or respondent identifiers, source registers, Turnitin exports, or per-case hashes to the public repository.

Tests use generated synthetic DOCX/PDF fixtures only.

## 7. Known limits

- PDF footer-number detection relies on selectable/extractable text coordinates; rasterized page numbers may not be detected.
- Heading-to-page mapping uses extracted text and a top-of-page heuristic. Long wrapped headings and unusual layouts require manual inspection.
- The auditor does not certify visual balance, clipping, overlap, typography aesthetics, widow/orphan control, table continuation, image cropping, official logo/color use, or accessibility beyond inline-image alternative-text presence.
- It does not validate citations, source accuracy, research content, plagiarism, AI-generated text, authorship, or institutional acceptance.
- A `PASS` does not replace page-by-page visual QA or human approval.

## 8. Regression baseline

Synthetic test cases cover a dedicated cover section with numbering restart, visible numbering on the cover, an invalid body sequence, a single-section zero-based workaround, margin mismatch and displayed-page TOC mapping. Tests are deterministic and do not depend on a live renderer; a separate integration fixture should exercise LibreOffice on CI where available.
