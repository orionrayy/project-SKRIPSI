# Revision QA and Empirical Consistency — v0.7.0

## Purpose

The v0.7 quality layer adds deterministic, offline checks for four failure classes observed in thesis revision workflows:

1. complete `SEBELUM` / `SESUDAH` pair accounting against the actual DOCX files;
2. stable marked-region IDs, evidence state, mapping confidence and unresolved dispositions;
3. study-model consistency across sample size, demographic frequencies, measurement modality, pairing, reliability configuration and interpretation strength; and
4. SHA-256/byte-level synchronization of final artifacts and their manifest.

These checks improve traceability. They do not judge plagiarism, predict Turnitin or AI-detector scores, prove semantic equivalence, authenticate the author, validate source truth, calculate inferential statistics, or provide human academic approval.

## CLI

```bash
# Verify every after-text passage against the candidate DOCX. Optionally verify
# every before-text passage against the immutable original DOCX.
project-skripsi revision-pairs-audit \
  .private/revision/before-after.txt \
  .private/revision/candidate.docx \
  --original-docx .private/source/original.docx \
  --output .private/revision/pair-audit.json

# Inspect every region ID and keep low-confidence/unmapped rows visible.
project-skripsi marked-region-audit \
  .private/revision/marked-region-register.csv \
  --output .private/revision/region-audit.json

# Check the structured cross-chapter study model; missing/contradictory values
# are reported, never imputed.
project-skripsi empirical-consistency-audit \
  .private/revision/study-model.json \
  --output .private/revision/empirical-consistency.json

# Verify final DOCX/PDF/TXT bytes against a relative-path manifest.
project-skripsi artifact-manifest-audit \
  .private/revision/run-manifest.json \
  --output .private/revision/manifest-audit.json
```

All output paths use create-only semantics: an existing report is not overwritten. The artifact manifest only accepts paths relative to its own directory and blocks path traversal.

## Pair correspondence semantics

The pair auditor parses each `BAGIAN n` block and requires exactly one non-empty `SEBELUM` and `SESUDAH` block. It performs Unicode/whitespace normalization and exact text matching against the DOCX main document XML. It does not fuzzy-match a revised paragraph into the document. It distinguishes:

- `MATCHED_UNIQUE`: exact text appears at one location;
- `MATCHED_MULTIPLE`: exact text appears more than once, so positional correspondence needs review;
- `NOT_FOUND`: exact text does not appear in the candidate;
- `NOT_APPLICABLE_NEW_CONTENT`: the before block explicitly states that the item is new and was absent from the original bibliography.

A presence ratio is not a semantic-fidelity score. Repeated identical paragraphs may legitimately occur in a table of contents and chapter body; they remain ambiguous until the operator links the stable pair ID to an intended document anchor.

## Marked-region semantics

Every report unit must have a stable unique `region_id`, mapping status, classification, evidence status, disposition, validation state and a written rationale. A source label or repository URL is only discovery metadata; it is not proof that the source content was inspected. `LOW_CONFIDENCE`, `UNMAPPED`, `PENDING`, `METADATA_ONLY`, or rationale-free regions remain unresolved. Registration coverage and resolution coverage are reported separately.

## Empirical consistency contract

A project study model should declare:

- sample size and whether unique participant identifiers exist;
- design type and control-group availability;
- demographic count arrays and percentages, with missing categories explicit;
- measurement constructs and modalities (e.g. self-report vs oral performance test);
- pairing key for paired procedures;
- construct-specific item groupings for Cronbach's alpha;
- ICC rater count, model, measurement type and definition (consistency or absolute agreement); and
- the outcome actually modeled versus the outcome claimed in interpretation.

A one-group pretest-posttest design without a control group triggers an interpretation-limit note. It cannot by itself establish a causal effect. P-values displayed as `0.000` trigger a reporting warning; report the unrounded value or `p < .001` when warranted by the actual output.

## Case-derived patterns generalized for reusable QA

The private reference case exposed: three after-text reference additions listed in TXT but absent from the current DOCX; repeated text hits at multiple positions; all 384 marking units being recorded without their source texts having been fully inspected; 74 low-confidence mappings and nine unmapped rows; missing rationale fields; demographic counts that did not reconcile with stated N; a paired analysis whose unique participant matching key was not supplied; pooled reliability reporting across distinct constructs; incomplete ICC configuration; and a stale PDF hash in a run report. This document intentionally excludes the thesis text, respondent identities, individual scores and private source labels.

## Non-goals and human gates

- No automatic rewrite, synonym substitution, paraphrase scoring or detector evasion.
- No automatic correction of counts, missing values, identities, p-values or statistical model settings.
- No source is upgraded from metadata-only to full-text-reviewed by this audit.
- No project phase, human acceptance or approval status is changed.
- A `PASS` means the specific structural contract passed, not that the thesis is academically correct or submission-ready.
- Page-by-page visual review, source verification, substantive semantic review, institutional style validation and author/supervisor acceptance remain separate release gates.
