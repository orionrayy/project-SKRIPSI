# Contributing

1. Read `ORCHESTRATION_MEMORY.md`, `PROJECT_RULES.md`, and the current phase ledger before making changes.
2. Identify the earliest incomplete phase and verify its approval/dependencies.
3. Work on one active phase at a time. Do not begin later-phase implementation while a prior acceptance gate is pending.
4. Keep source records, private research datasets, raw PDFs, secrets and participant data out of Git.
5. Add tests for validators and deterministic transformations. Record exact commands and outputs.
6. Run `python scripts/validate_phase_ledger.py` and `python -m unittest discover -s tests -v` before staging.
7. Review `git diff --cached` for secrets, personal data, research content and unintended files.
8. Do not push or publish without explicit repository-owner approval naming the exact action and intended public file set.
