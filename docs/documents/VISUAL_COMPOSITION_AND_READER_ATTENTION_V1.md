# Visual Composition & Reader-Attention Engineering

**Status:** additive candidate for review; not a released or institutionally certified capability.

## 1. Separate quality gates

Review paginated documents through four distinct gates:

1. Content integrity: required information is present, accurate and not invented.
2. Layout integrity: page geometry, fonts, styles, pagination, fields, tables and figures behave as required.
3. Visual composition: hierarchy, motif, spacing, alignment, rhythm, contrast and shape language form a coherent publication.
4. Reader usability: intended readers can locate and understand information needed for their tasks.

A pass in one gate does not prove another. A structurally valid PDF can still be visually monotonous; an attractive page can still omit a critical field; static composition analysis cannot certify comprehension.

## 2. Attention is task-dependent, not a fixed timer

Do not encode a universal human attention span in seconds. Eye-tracking research describes multiple scanning behaviors, including F-shaped, spotted, layer-cake and commitment patterns. The pattern depends on the reader's task, motivation, prior experience, content and layout. Finding a date differs from studying a methodology or reading a policy in full.

Design for actual reader tasks: identify the document, locate the date/venue/speaker/duration, understand a sequence, and find a contact or requirement. Use informative headings, front-loaded labels, recognizable numbers, meaningful grouping and restrained emphasis. Do not assume one gaze pattern applies to every printed or digital document.

### Task-based reader check

Write 3–7 realistic find-and-understand tasks for each document family. Record task wording, expected answer, observed completion time, accuracy, navigation difficulty, ambiguity and confidence. Completion time is a sample observation, not a universal pass threshold. Set any threshold before testing and justify it for the document's stakes and audience.

An informal task test is a usability observation, not an eye-tracking study. Keep reader-task status NOT_RUN until evidence exists. Claim eye-tracking only when calibrated instrumentation and an appropriate protocol were used.

## 3. Composition principles

### Whitespace

Evaluate whitespace by function, not by a universal page-fill percentage. Space can separate unrelated groups, connect related information, protect a title, create a pause or improve emphasis. Unexplained gaps, isolated labels, broken reading paths and accidentally unfinished pages remain defects.

Inspect every page at full size and as a reduced overview. Check top, middle and bottom regions, page-to-page density and orphaned items. Never add filler prose or globally shrink type/margins just to fill a page.

### Motif system

Choose a motif family with a reason to exist. Use it for identity, transition, sequence or topic reinforcement. A motif can vary in scale and placement while retaining a recognizable visual grammar. Botanical linework, celestial paths, architectural curves, editorial rules and topographic contours are examples, not defaults. Motifs must remain secondary to information and comply with institutional/cultural requirements.

### Reduce box dependence

Do not convert every paragraph, list, heading or metadata field into a card. Use boxes only when they communicate a real boundary, state, category or comparison. Prefer open typography, editorial numbering, aligned columns, timelines, indentation and subtle rules for narrative content. Use tables when row/column relationships materially aid comparison. A borderless Word table can be an implementation detail, but its rendered result should not read as repeated cards.

### Organic geometry and rhythm

Combine straight alignment with controlled curves, arcs, open paths and asymmetry where content supports them. Do not use identical rectangles as the only visual language. Variation must preserve legibility and reading order. Define typographic roles before assigning sizes; create hierarchy through size, weight, family, spacing and position, not color alone.

## 4. Document-family design profiles

| Family | Primary task | Candidate composition |
|---|---|---|
| Event TOR | identify event, people, date, sequence and responsibilities | expressive title, open metadata, editorial lists, timeline |
| Thesis/report | follow argument and verify methods/results/sources | restrained typography, stable chapter system, figure/table semantics |
| Training module | learn a concept and follow actions | chunked instruction, diagrams, progressive examples |
| Policy/SOP | find rules and execute a procedure | stable numbering, explicit conditions, decision trees |
| Scientific poster | grasp question, method and findings | strong information architecture, figure-led hierarchy |

These are starting points, not mandates. Institutional rules, accessibility, language direction and discipline take precedence.

## 5. Render and review

1. Freeze source content, scope, identity variables and institutional constraints.
2. Build a semantic outline of headings, metadata, lists, schedules, figures and tables.
3. Select a document-family composition profile and motif grammar.
4. Build using reusable styles and layout primitives.
5. Render DOCX to PDF with renderer and font provenance.
6. Run structural and mechanical composition diagnostics.
7. Inspect every page at full resolution; use contact sheets only for navigation.
8. Run task-based reader checks when required.
9. Re-render after every meaningful correction and invalidate previous QA.
10. Record unresolved issues and exact acceptance scope.

## 6. Mechanical audit limits

The visual composition auditor reports text-area ratio, text bounds, margin-band ratios, text block/line/span counts, font sizes/families, approximate heading/body size contrast, vector rectangle counts and image counts.

These are proxies. The auditor cannot identify semantic headings reliably, know whether a rectangle is a card or necessary diagram, understand motif quality, estimate gaze or certify aesthetic value. Text-area ratio measures text geometry only; it does not include all images, backgrounds or vector artwork.

A profile-specific mechanical PASS means only that configured thresholds were not crossed. It is not visual QA acceptance, reader usability, eye-tracking, institutional compliance or user approval.

## 7. Sanitized learning history

| Iteration | Outcome | Lesson |
|---|---|---|
| T0 | generic hierarchy and upper-page clustering | correct content does not create visual identity |
| T1 | palette improved, layout still templated | color alone does not solve composition |
| T2 | repeated boxed groups remained | repeated rectangles create a rigid visual grammar |
| T3 | open lists improved, explicit page break created a blank page | full render is mandatory after layout changes |
| T4 | pagination recovered, visual composition still flat | technical correction is not visual acceptance |
| T5 | open three-page editorial structure, recurring motif, open material spread and curved schedule path | motif continuity and purposeful space can add character without invented content |

T5 remains pending user review and is not a universal template.

## 8. Research references

- Pernice, K. Text Scanning Patterns: Eyetracking Evidence. Nielsen Norman Group. https://www.nngroup.com/articles/text-scanning-patterns-eyetracking/
- Pernice, K. F-Shaped Pattern of Reading: Misunderstood, But Still Relevant. Nielsen Norman Group. https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content/
- Chiu, T.-Y., & Drieghe, D. (2023). The role of visual crowding in eye movements during reading: Effects of text spacing. Attention, Perception, & Psychophysics, 85, 2834–2858. https://doi.org/10.3758/s13414-023-02787-1

The eye-tracking sources primarily concern web scanning and controlled reading experiments. Chiu and Drieghe report spacing-related changes in fixation behavior, but some line-spacing effects were subtle and not uniformly beneficial. These findings inform hypotheses; they do not justify maximizing whitespace or transferring one layout to every document.
