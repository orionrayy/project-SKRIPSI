# Method Selection & Analysis Gates

## Software is not methodology

SPSS and SmartPLS are software products, not research designs or statistical methods by themselves. Select the analysis from the research question, design, measurement level, sampling/data structure, model specification, assumptions and university/supervisor requirements. Do not select software first and retrofit the method afterward.

## Quantitative research

Before selecting a test or estimator, capture: target population, sampling frame/strategy, sample-size rationale, unit of analysis, variables/constructs, measurement scales, instrument provenance/validity, missing-data strategy, planned estimand/model, assumptions and diagnostics, multiplicity/missingness considerations where relevant, effect-size/uncertainty reporting and limitations.

For regression or other parametric models, record the model form and check the assumptions relevant to that model and dataset. Do not apply a generic checklist mechanically or report a test merely because software exposes it.

For PLS-SEM, justify why a variance-based structural equation approach fits the research objective and model. Specify measurement-model type, reflective/formative rationale, construct/indicator specification, sample/power rationale, missing-data handling, collinearity assessment, measurement-model evaluation, structural-model evaluation, resampling/bootstrapping plan, predictive assessment if appropriate, and reporting limitations. Thresholds are context- and method-dependent; do not treat one universal numeric cutoff as proof of validity.

## Qualitative research

Capture the qualitative tradition/design, researcher's role/reflexivity, case/participant selection, recruitment, data-collection protocol, consent/privacy controls, corpus boundaries, coding/analytic approach, audit trail, saturation or information-power rationale where appropriate, negative/deviant cases, trustworthiness criteria and limits. Do not replace genuine interviews/observations with fabricated text.

## Mixed methods

Specify why integration is necessary, design sequence/priority, sampling for each strand, separate analysis plans, point(s) of integration, joint displays or integration procedure and how meta-inferences will be supported. Two methods placed side-by-side without an integration rationale do not establish a mixed-methods design.

## Secondary-data and review designs

Record dataset/document provenance, license/access status, inclusion/exclusion rules, extraction/harmonization, missingness, version/checksum and analytic limitations. For systematic/scoping reviews, separately specify protocol, databases, reproducible search strings, dates, screening rules, deduplication, flow accounting, quality/risk-of-bias appraisal and synthesis method.

## Research-alignment audit (0.4.0)

The platform now stores a separate `research_alignment.json` record to link each research question to its objectives and selected analysis plan, map optional hypotheses to predictor/outcome constructs, and document mixed-methods integration. Run `project-skripsi methodology-audit <alignment.json> --profile <methodology_profile.json>` to find broken IDs and missing links. The command produces structural findings only; it does not select a test, infer measurement levels, or certify theoretical and methodological validity. `READY_FOR_HUMAN_REVIEW` is not approval. See `docs/methodology/RESEARCH_ALIGNMENT_ENGINE.md` for the schema and finding codes.

## Readiness versus approval

The current engine reports missing design-specific fields. It does not choose a design, compute sample size, execute SPSS/SmartPLS, verify model assumptions, certify an instrument or approve a thesis methodology. Those capabilities require dedicated validated adapters and qualified human review.
