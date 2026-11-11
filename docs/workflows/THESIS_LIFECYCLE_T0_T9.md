# Individual Thesis Lifecycle T0–T9

The T0–T9 workflow applies independently to each thesis workspace. Every phase records execution, validation, human acceptance, approval, authorization, conclusion, evidence, blockers and next action as separate fields. A tool passing its checks does not create human acceptance.

| Phase | Purpose | Minimum evidence before acceptance |
|---|---|---|
| T0 | Intake & project charter | User-approved topic/context, institution/programme, deadline, scope, privacy class, policy and responsibility record |
| T1 | Research question & proposal design | Problem statement, objectives, questions/hypotheses if applicable, delimitations and feasibility review |
| T2 | Literature review & conceptual framework | Search log, source register, inclusion rationale, synthesis matrix, theory/construct mapping and identified gap supported by evidence |
| T3 | Methodology & instrument design | Design rationale, population/case, sampling, measures/instruments, procedures, analysis plan, assumptions and limitations |
| T4 | Ethics, permissions & data readiness | Ethics/permission status, consent/data-protection plan, access rights, instrument approval and data-collection readiness |
| T5 | Data collection & provenance | Immutable raw-data inventory, provenance, dates, collection protocol, data-quality log and missingness account |
| T6 | Data preparation & analysis | Reproducible processing steps, checksums, analysis scripts/settings, diagnostics, software/version and reviewer status |
| T7 | Results, discussion & interpretation | Result-to-data traceability, answer to each question, comparison with literature, limitations and no unsupported causal claims |
| T8 | Manuscript, compliance & revision | University format/version check, citation/reference audit, table/figure checks, supervisor revisions and change log |
| T9 | Final review, defense & publication readiness | Final artifact manifest, defense readiness, human sign-off, repository/retention plan and separate journal decision if applicable |

## Transition rule

A phase may start only when its predecessor is `COMPLETE_AND_APPROVED` and that phase has its own scoped authorization. `PASS_WITH_LIMITATION` can be acceptable only when limitations are explicit and the human decision accepts the bounded scope. P9-style roadmap intent is not permission to skip a predecessor or to accept work on behalf of a student.

## Stop conditions

Stop when required evidence is unavailable, access is restricted, ethics or permission is unresolved, data integrity fails, the methodology does not match the research question, or human acceptance is pending. Keep unknowns as unknowns; do not invent evidence to make a phase green.
