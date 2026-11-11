# Generalized Thesis-QA Lessons — Privacy-Safe Engineering Transfer

This document records reusable quality patterns from private thesis-review work. It intentionally excludes the student's identity, institution, title, Turnitin score, report/submission identifiers, source labels, passages, DOCX/PDF bytes, respondent names, individual scores and case-specific hashes.

## Patterns that should be enforced by the platform

1. **A similarity percentage is not a plagiarism verdict.** Report metadata, visible exclusions and matched-source inventories must be stored as provenance. The platform must not infer misconduct or predict another run's score.
2. **A before/after list is not proof of document synchronization.** Each revised passage needs a stable identifier, an exact original-source match, a candidate-document match, a unique-location status, and an explicit disposition for missing or ambiguous passages.
3. **Marked-region counts must distinguish unique passages from repeated highlights.** Duplicate source matches should preserve the underlying evidence while preventing double-counting of the same document passage. Low-confidence and unmapped regions must remain visible.
4. **Instrument validity is instrument-specific.** Evidence for one questionnaire cannot be silently transferred to a distinct oral-performance rubric. Aiken's V item coverage must be reconciled with the actual instrument version and validator forms.
5. **Reliability is construct-specific.** A combined coefficient across distinct constructs must not be used as proof that each scale is reliable. The data layout, scoring model and item grouping require review.
6. **ICC needs a fully specified model.** Record model, single/average measurement, consistency/absolute agreement, number and identity class of raters, and the actual rating design before interpreting the coefficient.
7. **Paired tests require a verified pair key.** Matching rows by table order is not enough. The platform must require a stable pseudonymous participant key in private workspaces and should block inferential interpretation when pairing is unverified.
8. **An inferential result needs the relevant output table and assumptions.** A reported t statistic and p value without the paired-test output or required assumption evidence remains conditional.
9. **The instrument, variable and outcome must not be conflated.** Survey constructs and performance-test scores are distinct outcomes unless the measurement model explicitly connects them.
10. **Causal language must reflect design strength.** A one-group pre/post design can show observed change; it does not by itself isolate the intervention from other temporal or contextual factors.
11. **Document fidelity is independent from academic validity.** DOCX/PDF openability, page layout, table/footnote integrity, citations, statistical correctness and human institutional review are separate acceptance gates.
12. **A final package needs a single provenance chain.** DOCX, rendered PDF, TXT before/after export, register, run manifest and hashes must describe the same exact build. Stale hashes must block release.

## Platform implementation references

- `src/project_skripsi/revision_qa.py`
- `src/project_skripsi/turnitin_reports.py`
- `schemas/quality/turnitin-report-audit.schema.json`
- `schemas/quality/turnitin-report-comparison.schema.json`
- `schemas/quality/empirical-study-consistency.schema.json`
- `docs/quality/REVISION_QA_V0_7.md`
- `docs/quality/TURNITIN_REPORT_QA_V0_8.md`

Tests must use synthetic fixtures or otherwise authorized, non-identifying material. Do not copy private thesis passages into public fixtures or training datasets.
