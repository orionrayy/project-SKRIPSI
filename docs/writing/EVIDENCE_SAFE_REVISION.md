# Evidence-safe revision workflow

## Purpose

This workflow helps a student improve clarity, grammar, flow or academic register while retaining the meaning, evidence and attribution of their own work. It is not a plagiarism-removal service and does not target Turnitin, Copyleaks, Grammarly or AI-detector thresholds.

## Workflow

1. Confirm the student's authorship responsibility, institutional AI-use policy, document confidentiality and approved processing location.
2. Identify the claim IDs and source IDs attached to the passage. Missing evidence remains missing; the tool must not create citations.
3. Generate a revision brief locally with `revision-brief`. This command does not call a model.
4. Optionally use `local-revise` with a model endpoint operated on the same machine. The adapter only accepts loopback endpoints and blocks redirects. It does not support a cloud free-tier endpoint.
5. Run `revision-audit` on the original and candidate. The report contains content hashes and detected structural differences, not the full manuscript text.
6. A human compares the proposition, evidence, population, method, time scope, uncertainty, negation, causal status and citations. A structurally clear report does not mean the candidate is semantically equivalent.
7. The student accepts, rejects or revises the candidate, records the decision in the project workspace and follows institutional disclosure requirements.

## Protected information

The audit attempts to preserve exact citations, author-year markers, URLs, DOIs, quotations, numbers, units and selected statistical tokens. It also flags changes in selected negation, uncertainty and causal vocabulary. Because these are heuristic checks, false positives and false negatives are possible. A human must inspect the exact context.

## Local model setup

An OpenAI-compatible local endpoint is optional. Examples include Ollama's local OpenAI-compatible route and a locally hosted llama.cpp server. The operator must install and manage the model separately; Project-SKRIPSI does not download model weights, require PyTorch, or start a model server. No model is assumed to fit a particular device. Check memory, license, language performance and evaluation results before adoption.

## Acceptance boundary

- No plagiarism score or AI-detection score is computed.
- No rewrite-until-score-threshold loop exists.
- Citation preservation is not proof of citation correctness.
- Token preservation is not proof of semantic equivalence.
- No revised text is automatically marked approved or final.
- External provider transfer is not implemented in this release.
