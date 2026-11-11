# Research Alignment Engine — v0.4.0

## Purpose and boundary

`methodology-audit` checks whether the research questions, objectives, constructs/variables, hypotheses, analysis plan and (when applicable) mixed-methods integration points refer to one another consistently. It is a deterministic traceability audit, not an automated supervisor, method selector or statistical consultant.

A result of `READY_FOR_HUMAN_REVIEW` means only that no blocking structural errors were detected in the supplied alignment record. It does **not** mean that the theory, construct definitions, instrument, sampling, sample size, statistical technique, model assumptions or causal interpretation is valid. `human_approval` therefore remains `NOT_GRANTED` in every report.

## Workspace artifact

New workspaces receive:

```text
methodology/design/research_alignment.json
```

The initial file is an empty, project-scoped scaffold. Complete it from the researcher's approved proposal, institutional guideline and reviewed sources. The separate `methodology_profile.json` retains design-specific readiness information such as population/case, sampling, sample-size rationale, data collection, validity, ethics, limitations and broad analysis fields. `methodology-audit --profile` checks the shared project ID, research design and research-question IDs between both records.

Existing workspaces created before v0.4.0 remain valid even if this additive file is absent. Create it without overwriting any existing work with:

```bash
project-skripsi methodology-scaffold .private/workspaces/thesis-2026-001
```

## Alignment model

1. `research_questions`: stable `question_id`, the actual question text, intent and optional unit of analysis.
2. `objectives`: stable `objective_id`, objective text and one or more `research_question_ids` it addresses.
3. `constructs`: stable `construct_id`, name, conceptual/operational definitions, role, measurement level, indicators and source/instrument references. A measurement level is recorded by the researcher; software must not infer it from a construct label.
4. `hypotheses`: optional, with linked questions, predictor and outcome construct IDs, direction and theoretical source references. Hypotheses are not mandatory for every design, especially qualitative work.
5. `analysis_plan`: one or more records linked to research questions; each records a researcher-selected strategy, technique, rationale and relevant assumption/diagnostic plan. The engine never chooses a test or estimator.
6. `integration_points`: for `MIXED_METHODS`, each point identifies a stage, both quantitative and qualitative analysis references, and the reason/how the strands are integrated. Merely collecting two data types does not document integration.

The schema is `schemas/methodology/research-alignment.schema.json`; an illustrative record is available at `templates/thesis-project/research-alignment.example.json`.

## Run the audit

```bash
project-skripsi methodology-audit \
  .private/workspaces/thesis-2026-001/methodology/design/research_alignment.json \
  --profile .private/workspaces/thesis-2026-001/methodology/design/methodology_profile.json \
  --source-register .private/workspaces/thesis-2026-001/sources/registry/source_register.json \
  --output .private/workspaces/thesis-2026-001/qa/methodology_alignment_audit.json
```

Exit code `0` means no blocking structural alignment errors were found and human review is still required. Exit code `1` means `NEEDS_REVISION` because at least one structural error was found. Warnings do not automatically block the report; they identify issues such as unreviewed causal inference in observational designs, missing diagnostics for inferential plans, or design/strategy combinations that require clarification. Exit code `2` indicates an input or I/O failure.

Finding codes are stable machine-readable identifiers; `path` points to the relevant JSON location. Fix the source record, rerun the audit, and retain the report as a QA artifact if required by the institution.

## What the engine checks

- required and duplicate IDs for questions, objectives, constructs, hypotheses, analyses;
- objective → question, hypothesis → question/construct, analysis → question/hypothesis/construct references;
- whether every research question has an analysis plan;
- whether every hypothesis mapped to an analysis has all of its questions and predictor/outcome constructs represented;
- construct roles, measurement-level declarations and operationalization/indicator omissions;
- explicit integration points in mixed-methods designs;
- cross-register project/design/question ID consistency;
- optional project source-register lookups for theory, construct and instrument references, including warnings where content access is metadata-only or abstract-only;
- review warnings for causal questions in observational designs, qualitative hypotheses and potentially mismatched analysis strategies.

## Interpretation and non-goals

The engine cannot establish construct validity, content validity, reliability, representativeness, power, correct estimator choice, statistical assumptions, measurement invariance, thematic saturation, trustworthiness or the correctness of a causal design. It does not compute sample size, power, instrument scores or test statistics. It does not recommend SPSS, SmartPLS, R, Python or a particular test. Those decisions require the full protocol, data structure, relevant methods literature, institutional requirements and qualified human review.

Do not add participant identities, raw responses or confidential interview text to this alignment file. Use stable anonymous IDs and keep raw research data in the appropriate private data workspace with an approved data-protection plan.
