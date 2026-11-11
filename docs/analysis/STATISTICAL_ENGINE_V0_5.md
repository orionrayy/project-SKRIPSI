# Statistical Engine v0.5.0 — operating contract

## Scope

v0.5.0 implements a deterministic, standard-library-only descriptive slice. It registers CSV datasets, profiles their structure without persisting raw rows/category labels, validates the analysis specification against methodology alignment, and executes:

- `NUMERIC_SUMMARY`: valid N, mean, sample standard deviation, minimum and maximum.
- `FREQUENCY_TABLE`: counts and percentages for categorical/selected coded columns, with default pseudonymization and small-cell suppression.

Inferential procedures, p-values, confidence intervals, effect sizes, regression, group-comparison tests, reliability/validity coefficients, sample-size calculations and qualitative coding are not implemented.

## Dataset registration and provenance

Datasets must be CSV, UTF-8/UTF-8-BOM, at most 512 MiB, 2,000,000 data rows and 5,000 columns, stored within the project workspace under `data/raw/` or `data/processed/`. Symlinked paths and paths outside the project workspace are refused. Headers must be non-empty and unique; malformed row widths are rejected.

`dataset-register` writes `data/registry/<artifact_id>.json`, containing the SHA-256, immutable relative path, provenance origin, privacy/permission fields, row/column counts, inferred types, missingness counts/rates, bounded cardinality indicators and aggregate numeric metadata. No raw row or observed category value is written into the profile. Numeric aggregate values are suppressed in the registration profile when valid N is below the default threshold of 5. Registration refuses an input that changes while being profiled. Replacing a source file requires a new artifact ID; the old registry record is not silently rewritten.

The profile's inferred type is a convenience, not a codebook. Verify units, labels, coding, reverse-scoring, measurement level and all transformations against approved project documentation. Locale-specific decimal formats and date parsing are not inferred. Numeric parsing uses dot-decimal notation.

## Specification and approval gates

`analysis/design/analysis_specification.json` explicitly identifies:

- project, analysis-plan and research-question IDs;
- a registered dataset artifact;
- one supported descriptive method;
- variable/column/construct mappings and requested operations;
- missing-value tokens and small-cell suppression threshold;
- a written method justification and a human approval reference.

The referenced entry in `decisions/decision_register.json` must be `METHOD_SELECTION_APPROVAL` with `APPROVED` status, an allowed human reviewer role, rationale, timezone-aware timestamp and scope matching the exact analysis-plan ID, dataset artifact ID and method. The approval reference is a local traceability mechanism, not cryptographic identity verification; the institution/supervisor's actual approval must be confirmed independently. The engine does not create or grant approval.

The linked analysis plan in `methodology/design/research_alignment.json` must be structurally sound, explicitly `DESCRIPTIVE`, and cover the selected research questions and constructs. An inferential plan or hypothesis-linked analysis is not run by this descriptive engine.

The thesis phase ledger is also enforced: T0–T5 must be `COMPLETE_AND_APPROVED`; T6 must be `IN_PROGRESS` or `COMPLETE` with scoped authorization. T4 ethics/permissions and data permissions must be confirmed through their respective human/project records. The statistical engine does not authorize any phase.

## Privacy controls

- Raw data stays inside the private project workspace; no data is sent to OpenAlex, Crossref, a cloud LLM or another network endpoint.
- Dataset registration persists no observed category labels or raw rows.
- Frequency categories are pseudonymized by default. Exposing category labels is prohibited for `CONFIDENTIAL` or `RESTRICTED` datasets.
- Registration profiles suppress numerical aggregates below N=5 by default; analysis output applies the explicit threshold in the approved analysis specification.
- Category levels below the configured threshold (2–50; default 5) are suppressed. If only one category would be hidden, a complementary visible category is also suppressed so that the hidden count cannot be reconstructed from the overall total. If a single-category table is entirely suppressed, its `valid_n` is hidden too. The combined count across suppressed levels is never emitted. Numeric descriptive values are also suppressed when valid N is below that threshold.
- Output artifacts are created with restrictive local permissions where supported. Windows ACLs remain OS-managed and must be reviewed by the operator.
- No participant-level rows are exported.

Small-cell suppression reduces one disclosure risk; it is not a complete anonymization or disclosure-control guarantee. It does not defend against all differencing or repeated-query attacks. Review combinations of variables, quasi-identifiers and the contextual risk of re-identification before sharing outputs.

## Reproducibility and verification

A run writes `analysis/outputs/<run_id>/results.json` and `run.json`. It records hashes for the dataset, dataset registry record, analysis specification, methodology alignment, decision register and phase ledger. The audit event pins full hashes of the results and run record. `analysis-verify` checks current linked files, current approvals/phase validity, the result hash, run-record hash pin and audit-chain inclusion.

The result JSON is deterministic for identical dataset bytes, specification, and engine version. Run metadata includes timestamp and environment and is not expected to be byte-identical across runs. A matching result hash is an artifact reproducibility signal, not proof that the method is academically appropriate or that the underlying data is valid.

## Diagnostics and limitations

The engine flags missingness, relatively high observed missingness, constant variables, low N, zero variance and applied small-cell suppression. It does not identify MCAR/MAR/MNAR, test normality/independence/homoscedasticity, diagnose measurement validity or decide whether a variable is suitable for a model. No imputation, weighting, recoding, deletion or transformation is performed.

Do not interpret descriptive summaries as evidence of statistical significance, causal effect, representativeness, generalizability or hypothesis support. Those require design-specific procedures, assumptions, diagnostics and qualified review.

## Suggested extension sequence

1. v0.5.x: strengthen crash recovery for partially written analysis-run directories; add native Windows CI results and restore drills.
2. v0.6: reviewed inferential method contracts and adapter interfaces, beginning with transparent Python/R exports rather than silent automatic test selection.
3. v0.7: SPSS/SmartPLS adapters only after supported formats, version capture, assumption diagnostics and independent reproduction are specified.
4. v0.8: result interpretation guardrails, visual/table export and document traceability.

No data fabrication, automatic test selection, detector evasion or external manuscript transfer is in scope.

## v0.5.1 recovery extension

Before creating a run output directory, the engine now writes a checksummed `analysis/transactions/<run_id>.json` write-ahead journal. It contains the approved aggregate result payload and run record, not source rows. If the process stops during persistence, `analysis-recover <workspace>` validates the journal, recreates only missing artifacts, reuses the audit event through its stable idempotency key, and retires the journal only after completion. Conflicting or tampered files are refused and preserved. Recovery does not recalculate statistics or modify approvals/phase states.


## v0.5.2 reproducibility and diagnostics

See [`STATISTICAL_REPRODUCIBILITY_V0_5_2.md`](STATISTICAL_REPRODUCIBILITY_V0_5_2.md) for the pinned-input contract, process-kill recovery validation, same-engine read-only replay and diagnostic summary commands. This does not change the descriptive-only analysis scope.
