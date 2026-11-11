# Document Engineering v0.6.0

## Scope

The v0.6 document engine assembles only manuscript blocks supplied by the researcher/operator. It does not write research findings from abstracts, invent citations, infer institutional formatting, or approve academic content. Every build is marked `DRAFT_NOT_REVIEWED`.

## Workspace files

- `manuscript/document_specification.json`: project-scoped document plan.
- `manuscript/builds/<document_id>.json`: immutable build/provenance record.
- `deliverables/<filename>.docx`: generated Word document.
- `deliverables/<filename>.pdf`: rendered pagination proof/final preview.
- `sources/registry/source_register.json`: bibliographic source records and claim-evidence links.
- `analysis/outputs/<run_id>/`: descriptive analysis result and run record.

## Commands

```bash
project-skripsi document-scaffold <workspace>
project-skripsi document-build <workspace>
project-skripsi document-verify <workspace> THESIS-DRAFT-001
project-skripsi document-audit <workspace>/deliverables/thesis-draft.docx
```

`document-scaffold` refuses to overwrite an existing specification. `document-build` renders DOCX to PDF with LibreOffice and uses PyMuPDF to locate heading pages. The static TOC is rebuilt until its page map converges; internal hyperlinks point to section bookmarks. The final PDF is retained alongside DOCX so the pagination and visual output can be inspected.

## Supported content blocks

- `paragraph`, `bullet`, `numbered`: researcher-provided text.
- `table`: researcher-provided tabular content.
- `analysis_table`: selected variable results from an `analysis_run_id` that passes `analysis-verify`; summary suppression is preserved.
- `figure`: a workspace-local PNG/JPEG with required caption and alternative text.

All `claim_ids` must resolve to at least one claim-evidence link with relation `SUPPORTS`, `review_status=VERIFIED`, an exact locator, and a valid reviewer role. Citations are generated from this reviewed register only. Source status and locator scope are not upgraded by document generation. Metadata-only and abstract-only records produce scope warnings. A source entry without enough metadata for APA7 author-year citations is rejected.

## Citation styles

APA7 author-year and IEEE numeric in-text citation order are supported. IEEE numbers follow first appearance. APA author-year collisions receive stable `a/b/...` suffixes. Because the source register currently has limited bibliographic fields, journal/container, volume, issue and page-range completeness can remain insufficient; the engine warns for journal articles and requires a human to complete/verify bibliography details before submission. This implementation is not a certification of full APA/IEEE conformity for every publication type.

## Institutional profiles

When no institution profile is supplied, a generic A4/Times New Roman template is used and the build is tagged `GENERIC_TEMPLATE`; institutional compliance is unverified. To apply a profile, the document specification must pin its path and SHA-256 and provide an approval reference. The profile must have `review_status=HUMAN_REVIEWED`, a non-empty `reviewer_role`, `profile_id`, and version. Formatting keys are applied only from the supported allowlist (page size, margins, font, line spacing, indent, spacing and heading sizes). Human review metadata is a provenance record, not cryptographic proof that an institution or supervisor approved it.

## Statistical tables

The document generator calls the Statistical Engine verifier for every `analysis_table` block. It reads only aggregate `results.json`; it never exports respondent rows. Small-cell and complementary suppression labels/nulls are preserved, and a build record pins both the result and run record SHA-256. A descriptive table is not an inferential result and is not evidence of causal effect.

## Provenance, safety and verification

Before building, the workspace, specification, source register, citations and selected analysis runs are validated. At publication time the specification, project manifest and source register hashes are rechecked. DOCX/PDF outputs are never overwritten. A build record pins the DOCX/PDF, specification, manifest, source register, profile, citations, claims and analysis run hashes. A hash-chained audit event records the build.

`document-verify` checks current input/artifact pins and exactly one matching build audit event. Changing the specification, source register, project manifest, institution profile, or linked analysis run after the build makes verification fail; this preserves the fact that the document was generated from an earlier state.

The engine does not automatically complete a table of contents using Word fields. It creates a static, page-mapped TOC with internal links so page numbers are visible in the headless PDF render. A two-pass convergence loop checks the final page map. `document-audit` verifies the OOXML ZIP, required package parts, headings, tables and image relationships; visual QA must still inspect the rendered PDF pages.

## Dependencies

- `python-docx` for DOCX authoring (`pip install -e '.[docx]'`).
- LibreOffice (`soffice`/`libreoffice`) to render DOCX to PDF.
- PyMuPDF for page mapping (`pip install -e '.[document-qa]'`).

No network service is called by the document engine. Keep the project workspace private; it may contain unpublished research, respondent data, and personal information.


## v0.6.0 release validation checkpoint

- Full regression suite: 175/175 PASS; document-specific integration suite: 9/9 PASS.
- All 25 JSON schemas pass Draft 2020-12 meta-schema validation; compileall and phase-ledger validator PASS.
- Installed CLI smoke passed on a disposable synthetic workspace: `init`, `validate`, `document-build`, `document-verify`, and `document-audit`.
- A synthetic eight-page DOCX/PDF was rendered and inspected page-by-page at 160 dpi. Its static TOC maps BAB I–V and bibliography to PDF pages 3–8; no clipping, overlap or table truncation was observed.
- The fixture has no real research findings or respondent data. The generated build remains `BUILT_NOT_REVIEWED`.
- Known limitations: institutional compliance is unverified for the generic template; bibliographic field completeness and full APA7/IEEE conformity require human review; LibreOffice/PyMuPDF must be installed for build/render; native Windows CI and the GitHub workflow have not been executed.
