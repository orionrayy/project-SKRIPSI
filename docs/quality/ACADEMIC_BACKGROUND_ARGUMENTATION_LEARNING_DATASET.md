# Academic Background Argumentation — Video-Derived Learning Record

**Dataset record:** `PSK-LEARN-VID-001`  
**Record file:** `data/learning/academic-background-seven-stage-video-001.json`  
**Schema:** `schemas/learning/academic-background-sequence.schema.json`  
**Status:** curated draft; visual captions reviewed; audio not independently transcribed.

## Purpose and provenance

This record converts one user-supplied Indonesian short video into reusable learning signals for the research-background writing workflow. The clip depicts a student and a supervisor-character discussing the functions of successive sections in a research background. The video lasts approximately 140.443 seconds and is 480 × 852 pixels at 30 fps. The audio stream is AAC, 44.1 kHz, stereo.

The annotation is based on a full-duration visual pass using approximately one frame per second, including the visible stage labels and burned-in captions. Selected caption fragments are evidence anchors, not a verified transcript. The printed pages shown in the scene are not sufficiently legible to extract their manuscript content. The source file is not copied into this public repository: the upload contains a visible person and a platform watermark, and redistribution rights have not been established. A SHA-256 fingerprint is retained for source identification only.

The clip is treated as a roleplay-based teaching example. Its opening hook about progressing to a thesis defense after one supervision session, its joking reference to contract writing, and its ending about approval timing are not treated as factual academic procedures or evidence of anyone's conduct.

## Seven-stage argumentative model

The principal learning signal is a sequence of functions rather than a fixed page layout:

| Sequence | Stage focus | What the writer must establish |
|---:|---|---|
| 1 | Broad phenomenon | The topic, its context and a credible reason to focus on it |
| 2 | Contextual evidence | Traceable data, source, period, denominator and interpretation |
| 3 | Specific problem | The observable problem in the actual population or setting |
| 4 | Prior-study mapping | What earlier studies examined, how they differ and what they found |
| 5 | Unresolved dimension | What remains insufficiently addressed within the literature actually reviewed |
| 6 | Research significance | Proportionate theoretical, practical, institutional or methodological significance |
| 7 | Study objective | A feasible objective aligned with the gap, question, design and analysis |

Approximate time windows and caption evidence are stored at stage level in the JSON record. The argument moves from broad context to evidence, a bounded problem, an assessment of prior work, a defensible gap, significance and then objectives.

## Important flexibility rule

The video explicitly qualifies its seven-position example: the writing is not limited to one paragraph for each function and should follow the needs of the manuscript. Therefore, the platform must model these as **argumentative functions**, not mandatory paragraph counts. A stage may require more than one paragraph, two functions may be combined, or institutional conventions may place material elsewhere. The project must first verify the current institutional guide and the supervisor's approved requirements.

The recommended order of authority is:

1. Current institutional and programme guidance verified from an authoritative source.
2. Approved supervisor guidance for the specific thesis.
3. Disciplinary and research-design conventions.
4. This generic dataset as a planning aid only.

## Engineering transfer into Project-SKRIPSI

The record is suitable for a planning and QA layer that:

- creates a function-level outline before prose generation;
- links factual claims and statistics to verified sources before drafting;
- checks that every stage advances or narrows the argument;
- synthesizes prior studies instead of listing them;
- requires gap claims to be bounded to the search strategy and access depth;
- blocks generic urgency language that is not connected to a documented problem;
- checks objective-to-gap, question-to-method and objective-to-analysis alignment; and
- prompts an author teach-back in which the student explains the purpose and evidence of each section.

The teach-back signal is particularly important: the scene asks the student to explain the paragraph sequence before the supervisor-character walks through it. Project-SKRIPSI can use that as an academic-understanding checkpoint, not as proof of authorship or an automatic academic-integrity verdict.

## Failure patterns captured

The structured record includes 20 stage-linked failure patterns. They cover generic openings, failure to narrow the topic, statistics without provenance, data that do not support the claimed scope, unsupported local problems, causal overreach, citation-list literature reviews, inaccurate claims from abstract-only access, unqualified comparisons, gaps asserted from narrow searches, gaps disconnected from prior studies, location-only novelty, generic or exaggerated urgency, and objectives that are misaligned, infeasible or presume the result.

These are reusable QA heuristics. They do not imply that the video itself documents every failure; several are engineering safeguards derived from the argument functions and Project-SKRIPSI's evidence-governance rules.

## Evidence and interpretation boundaries

**Directly observed:** seven displayed headings; a sequence of captioned explanations; approximate timing; the later qualification that the seven positions are adaptable; a teach-back interaction.

**Interpretation added for platform use:** evidence requirements, stage-level quality gates, transitions, gap-taxonomy examples, failure patterns and validation rules. These are analytic recommendations, not verbatim statements from the video.

**Not established:** a universal thesis format; mandatory seven-paragraph rule; institutional approval; a particular discipline; research topic; citation style; source list; empirical data; methodology; or a verified transcript. The video must not be cited as an academic source for substantive research claims.

## Validation expectations

Before an implementation uses this record, validate that:

- all seven stage IDs and ordinals are unique and ordered;
- stage time windows are monotonic and within the media duration;
- all caption anchors are explicitly marked as burned-in fragments;
- the record contains the flexibility statement and no-phase-effect boundary;
- the 20 failure records use valid stage IDs; and
- no prose, statistic, citation or local research fact is fabricated to fill a stage.

A schema pass confirms structural conformity only. It does not certify that the teaching example is universally suitable, that the captions are verbatim, or that a thesis meets an institution's requirements.