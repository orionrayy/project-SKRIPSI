# Quickstart

## Requirements

Python 3.10 or newer. Runtime has no required third-party dependencies.

## Install locally

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\\Scripts\\activate
python -m pip install -e .
```

## Create an isolated thesis workspace

```bash
project-skripsi init \
  --project-id thesis-2026-001 \
  --title "Research title" \
  --discipline "Information Systems" \
  --research-design "QUANTITATIVE_SURVEY" \
  --institution "University name" \
  --programme "Programme name"
```

The default location is `.private/workspaces/thesis-2026-001/`. It is local-only and ignored by Git.

## Validate and inspect

```bash
project-skripsi validate .private/workspaces/thesis-2026-001
project-skripsi status .private/workspaces/thesis-2026-001
python -m unittest discover -s tests -v
```

## Methodology alignment (v0.4.0)

New workspaces include `methodology/design/research_alignment.json`. For a pre-v0.4 workspace, add the blank file without overwriting existing work:

```bash
project-skripsi methodology-scaffold .private/workspaces/thesis-2026-001
```

Edit the alignment JSON using the structure in `templates/thesis-project/research-alignment.example.json`, then run:

```bash
project-skripsi methodology-audit \
  .private/workspaces/thesis-2026-001/methodology/design/research_alignment.json \
  --profile .private/workspaces/thesis-2026-001/methodology/design/methodology_profile.json \
  --source-register .private/workspaces/thesis-2026-001/sources/registry/source_register.json \
  --output .private/workspaces/thesis-2026-001/qa/methodology_alignment_audit.json
```

A structurally clean report is only `READY_FOR_HUMAN_REVIEW`, never approved. The engine checks traceability; it does not pick a method/test, compute sample size or certify academic validity.

## Next steps inside the workspace

Complete the T0 intake information and institutional guideline profile. Do not start a later phase until the predecessor has passed its quality gate, a human has accepted it, and the later phase has its own scoped authorization. Keep thesis PDFs, datasets, interview files and drafts out of the public repository.
