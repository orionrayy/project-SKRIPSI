# Third-party writing-tool assessment

**Audit date:** 2026-11-05
**Decision owner:** Project-SKRIPSI maintainers
**Default policy:** free-first, local-first, evidence-preserving; no provider is enabled by appearing in this report.

## Decisions

| Reference | Observed capability / constraint | Decision |
|---|---|---|
| [RhetoriLex](https://github.com/rezaprama/RhetoriLex) | Evidence-first phrasebank; claim-strength and causal-design guards; bilingual writing workbench. Upstream describes Apache-2.0 software and CC BY 4.0 original data/docs. | Adopt design concepts only. The repository now has independently authored patterns and checks; no upstream phrase inventory or code was copied. |
| [ai-workers-mcp](https://github.com/basttran/ai-workers-mcp) | Multi-provider MCP for rewrite, proofread, translate and other NLP tasks; free-tier routing still sends text to configured external providers and depends on changing quotas/availability. | Not enabled. A local loopback model adapter is available instead. A future external connector needs project-specific privacy approval, current license/security review and explicit transfer consent. |
| [grammarly-mcp](https://github.com/BjornMelin/grammarly-mcp) | README describes Grammarly Pro for detector/plagiarism features, Browserbase or Browser Use Cloud, and LLM rewriting to reduce AI-detection scores. | Rejected as a default. No detector-evasion or score-targeting loop is implemented. |
| [RePro 4B](https://huggingface.co/cx-cmu/repro-rephraser-4B) | Model card reports Apache-2.0, English-focused training, and a model repository of approximately 8.06 GB. | Optional research model only; not bundled and not a default mobile dependency. |
| [unslop](https://github.com/MohamedAbdallah-14/unslop) | MIT-licensed deterministic text-cleanup CLI and writing style tools, while also exposing an anti-detector mode. | Not imported. Existing Document Craft rules already cover clarity and repetitive prose. Future deterministic lint must not optimize detector outcomes. |
| [aryadytm/paraphrase Space](https://huggingface.co/spaces/aryadytm/paraphrase) | Page returned a runtime error during this audit. | Unavailable/unverified; not used. |
| [rakeeb paraphrase Space](https://huggingface.co/spaces/rizam/rakeeb_paraphrase) | Runtime, license and actual bilingual behavior not verified. | Not used. |
| [paraphrasing-tool1](https://github.com/aigeon-ai/paraphrasing-tool1) | Current code, license, maintenance and privacy behavior not verified. | Not used. |
| [plagiarism-removal-app](https://github.com/adityaraul004/plagiarism-removal-app) | Current code, model, license and Indonesian performance not verified. Its plagiarism-removal positioning is not an accepted product goal. | Not used. |
| [Promptify](https://github.com/AlexGovi/Promptify) | Gemini-backed API implies external credentials and document transfer; free-tier terms/quotas require runtime verification. | Not enabled. |

## Implemented from the useful ideas

- Original bilingual evidence-aware phrasing patterns, each with a purpose, evidence level, claim-strength ceiling and caution.
- Claim-strength guardrails that flag causal claims and overclaim risk; the tool never approves claims.
- A revision prompt generator that preserves citations, quoted spans, numbers, units, negation, uncertainty and causal status.
- A revision audit that detects changed protected tokens and epistemic markers, but explicitly does **not** claim semantic equivalence.
- A loopback-only OpenAI-compatible adapter for a locally operated model (for example, Ollama or llama.cpp). No text leaves the machine through this adapter.
- No plagiarism percentage or AI-detector percentage, and no rewrite-until-threshold loop.

## Operating constraints

1. Cite the original source whenever the idea or claim is derived from it. A paraphrase is not a substitute for attribution.
2. Students remain responsible for the argument, data, interpretation, authorship and institution-specific AI-use disclosure.
3. Never fabricate citations, evidence, research observations, participant statements, data or analysis.
4. A structural revision audit is a screening aid, not proof of preserved meaning. Human semantic and methodological review is mandatory.
5. Local model endpoints must use `localhost`, `127.0.0.1` or `::1`. External endpoints are rejected by the built-in adapter.
6. Optional providers and model licenses/terms must be rechecked before enabling them in a future release.
