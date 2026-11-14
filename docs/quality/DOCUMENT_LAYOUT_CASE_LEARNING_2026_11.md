# Sanitized Document-Engineering Case Learning — 2026-11

**Case key:** `CASE-DOC-LAYOUT-2026-11`  
**Classification:** public, de-identified engineering lessons  
**Source materials reviewed:** task brief and iterative chat requirements, final DOCX/PDF pair, supplied emblem asset (inspection only), and page-render QA outputs  
**Research phase impact:** none; this is platform engineering evidence, not P0–P9 research evidence.

## 1. Privacy and use boundary

This case is a derived engineering record. It does not include the student's name, student number, institution/program identifiers, exact title, personal document filenames, original wording, references, source locators, file hashes, original DOCX/PDF bytes, or the emblem binary. The supplied emblem was used only to understand the document's image/alternative-text requirement. Do not reconstruct identities from the subject matter.

The original manuscript is not a public training corpus. Only generic layout contracts, observed defect classes, test scenarios, and process lessons may be reused. If the source artifacts are ever needed again, they must remain in the originating private workspace with its access controls and retention policy.

## 2. Task contract captured from the brief

The task was an individual Indonesian-language social-anthropology paper based on a personal experience of attending a wedding in Banten. The only case-specific observation supplied by the author was that Javanese cultural elements appeared more dominant than Sundanese elements at the wedding attended. The assignment required an autoethnographic/participant-observation method, four main chapters, a bibliography with a minimum source mix, and a final PDF.

The declared technical contract was:

| Requirement | Captured value |
|---|---|
| Paper size | A4 |
| Body font | Times New Roman, 12 pt |
| Line spacing | 1.5 |
| Margins | left 4 cm; top, right and bottom 3 cm |
| Main-body length | 8–12 pages, excluding cover and bibliography |
| Delivery | PDF, with editable DOCX as working source |
| Structure | Cover, front matter, BAB I–IV, bibliography |

The resulting final pair had 14 physical PDF pages. Ten pages contained the substantive BAB I–IV body; the other pages were the cover, front matter and bibliography. The minimum bibliography count was exceeded in the document, but this case audit did not independently validate the bibliographic metadata or the truth of each cited source. Source verification remains a separate gate.

## 3. Evidence-bounded content lessons

The supplied lived-experience data was sparse. It supported a bounded statement about one wedding the author attended and the author's perception of relative cultural prominence. It did not support an exact date, village/venue, wedding sequence, named relatives, the families' motivations, or a claim about all Banten weddings.

Reusable controls:

1. Preserve the author's direct observation and identify it as retrospective self-report when no contemporaneous field notes exist.
2. Keep observation, interpretation, literature-derived context, inference and unknown facts visibly distinct.
3. Do not invent ritual names, ceremony order, speech, family background, participant identities, dates or locations to make a case sound vivid.
4. A single case cannot establish regional prevalence. Present Banten as culturally diverse and state the limits of the selected experience.
5. If richer ethnographic detail is necessary, request a real follow-up interview, field note, photo caption or event document; otherwise narrow the claim.
6. Autoethnography requires reflexivity about the observer's position, memory limits and interpretation. Retrospective reflection should not be represented as systematic participant observation if it was not recorded as such.
7. For a Pendidikan Nonformal framing, describe plausible informal cultural learning through family interaction and community participation as an analytical interpretation, not as an observed teaching event unless the author actually reports one.

Writing-quality preference derived from the revision instructions: natural academic Indonesian, varied but controlled sentence rhythm, precise transitions, minimal repeated sentence templates, and avoidance of formulaic contrastive constructions. This is a clarity and authorial-consistency requirement, not an AI-detector or similarity-score optimization target.

## 4. Revision and visual-QA chronology

The production cycle exposed a sequence of defects and corrected them through render-inspect-revise cycles:

- The first rendered document exceeded the intended page budget. Content and repeated explanation were condensed while maintaining the required chapter structure.
- Subsequent layout passes improved the visual hierarchy of the cover, institutional emblem placement, title block, chapter headings, subheadings, table of contents, paragraph spacing and bibliography indentation.
- An initial pagination defect left a number on the cover. The user explicitly identified this. The DOCX was corrected and the final PDF was re-rendered; the cover became unnumbered and the following page displayed 1.
- The table-of-contents page references were reconciled against actual rendered PDF pages rather than estimated from the source paragraph sequence.
- The final visual review covered the complete 14-page rendered PDF, not only a cover sample or the final page.

The important process lesson is that a successful file save or DOCX package check is not a final-document acceptance. The final exported PDF must be the exact build inspected, and any layout edit invalidates the previous render review and artifact hashes.

## 5. Final-pair observations

The final PDF had 14 physical pages. Physical page 1 was the unnumbered cover. Physical pages 2–14 displayed page numbers 1–13. The substantive BAB I–IV body occupied ten physical pages. The table of contents was checked against the rendered pages, using displayed page numbers rather than physical page indexes.

The final DOCX/PDF pair met the observable A4, margin, Times New Roman 12 pt Normal style, and 1.5 Normal line-spacing requirements. The document contained one embedded institutional emblem. That inline image lacked OOXML alternative text.

A structural audit also found that cover suppression and body numbering were implemented with one DOCX section, `different_first_page_header_footer`, and a zero-based `w:pgNumType` start. The rendered PDF looked correct, but this is a fragile implementation. The recommended production architecture is a dedicated cover section with no page field, followed by a body section whose page-number field starts at 1 and whose header/footer linkage is explicit.

Case-specific page map (numbers below are printed/displayed page numbers, not physical PDF indexes):

| Heading | Displayed page |
|---|---:|
| BAB I PENDAHULUAN | 3 |
| 1.1 Latar Belakang | 3 |
| BAB II TINJAUAN PUSTAKA | 6 |
| 2.1 Konsep Kebudayaan | 6 |
| BAB III PEMBAHASAN | 8 |
| BAB IV PENUTUP | 12 |
| DAFTAR PUSTAKA | 13 |

The case fixture stores this page map as a regression policy. It does not store page text or document hashes.

## 6. Defect taxonomy and platform requirements

| Defect class | Observed/latent issue | Required reusable control |
|---|---|---|
| Pagination | Cover number previously visible | Rendered-PDF check for no number on each cover page |
| Pagination | One-section zero-based restart workaround | Inspect OOXML section structure; warn or fail when dedicated cover section is required |
| Pagination | Correct visible sequence is separate from DOCX page-field presence | Read visible PDF footer tokens and validate exact sequence |
| TOC | Page labels can become stale after layout changes | Map each declared heading to the rendered physical page and its displayed page number |
| Length | Total physical pages differ from substantive body pages | Report physical count, cover count, and body count separately; never conflate them |
| Layout | Cover, heading hierarchy and front matter need distinct composition | Use explicit, versioned styles; avoid ad hoc run-level formatting as the only source of design rules |
| Typography | Normal style can be correct while individual runs vary | Report both Normal style and observed run-level font family/size inventory; apply policy intentionally |
| Margins/page size | Visual appearance cannot prove the exact measurements | Read section geometry from DOCX and compare against the institution/task policy |
| Image accessibility | Embedded emblem lacked alt text | Require meaningful alternative text for non-decorative images; distinguish decorative images explicitly in a future schema |
| Bibliography | Presence/count alone does not prove metadata accuracy | Separate reference completeness, DOI/URL resolution and claim-to-source validation from layout QA |
| Final package | Repeated exports can leave stale or mismatched PDF/DOCX | Pin exact input and output artifacts in a private manifest; re-render and re-audit after any mutation |
| Review process | User found a visible cover-number defect after an earlier “final” claim | Final acceptance must be evidence-based and must report unresolved warnings; avoid overclaiming “perfect” |

## 7. New regression/audit capability

A new privacy-minimizing DOCX/PDF layout auditor is proposed in `src/project_skripsi/document_layout_qa.py`, with a CLI wrapper at `scripts/audit_document_layout.py`.

It reports structural metrics without persisting manuscript text, names, student IDs, full filenames or file hashes. It checks:

- DOCX package readability and ZIP CRC;
- section count, page geometry, margins and first-page footer/header configuration;
- DOCX page-field locations and page-number restart configuration;
- Normal style font family, size, line spacing and indent;
- observed font-family/font-size inventory, heading/table/image counts and inline-image alt-text count;
- PDF physical page count and per-page extracted-text character counts;
- visible footer number candidates and cover suppression;
- sequential displayed page numbering after the cover;
- optional TOC heading-to-displayed-page mapping;
- optional sparse-page warnings and expected physical page count.

The audit result has `PASS`, `WARN` and `FAIL` states. `PASS` means only that configured structural checks passed. It does not prove that the writing is sound, references are true, the university accepts the template, the image is legally usable, or every page is visually attractive.

## 8. Production document-layout release contract

Before a generated academic document is labeled ready for user review:

1. Load a versioned, human-confirmed requirement profile. Never infer official brand colors, logo usage, or institution rules from a logo image alone.
2. Build the cover as a dedicated first section when the profile requires a clean unnumbered cover.
3. Start displayed numbering at 1 in the next section. Explicitly configure footer/header linkage and first-page behavior.
4. Render DOCX to PDF using a declared renderer/version and capture the conversion result.
5. Check the exported PDF, not just the Word object model: page count, cover footer, full body sequence, TOC page labels and footer location.
6. Distinguish physical PDF page indexes from displayed page labels in every report and TOC calculation.
7. Check A4/Letter dimensions, exact margins, Normal style, observed run-level styles, headings, list indentation, image alternative text and table/image counts.
8. Run a full-page visual review for clipping, overlap, blank/near-empty pages, bad page breaks, table splits, figure sizing, awkward whitespace and font substitution. Text extraction alone cannot detect all of these.
9. Re-run the build and all audits after any change to content, styles, section breaks, images, page fields or renderer configuration.
10. Verify the final DOCX, PDF, specification, policy and private artifact manifest all belong to the same exact build. Do not re-use stale hashes or previous visual QA.
11. Report warnings honestly. A technically valid file remains `DRAFT_NOT_REVIEWED` until the relevant human author/editor and institutional review gates are complete.

## 9. Limits and next research

The current auditor is deliberately narrow. PDF footer detection uses extracted text positions and may miss rasterized page numbers. Heading-to-page matching is heuristic and can fail on wrapped headings, unusual typography or complex layouts. The current implementation does not detect all clipping/overlap, widow/orphan lines, section-specific table geometry, tracked changes, floating/anchored image alt text, or visual consistency of colors and logo placement. Those remain human visual-review checks or later independently tested modules.

Do not train a prose model on this case. Its value is as a sanitized requirements/defect/regression case for document engineering and evidence-bounded writing. The case is one task in one style context and should not be generalized into a universal thesis template.
