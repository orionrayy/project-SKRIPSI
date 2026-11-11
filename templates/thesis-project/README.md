# Thesis project template

Use `project-skripsi init` to instantiate this template with a unique `project_id`. The CLI writes the actual project manifest and phase ledger into the private workspace root. Do not copy a real student's project into `projects/_template/` or into this public repository.

Expected local structure:

```text
<project-id>/
  project.json
  README.private.md
  state/phase_ledger.json
  intake/
  requirements/{institution,programme}/
  sources/{registry,snapshots}/
  literature/matrix/
  methodology/{design,instruments}/
  ethics/approvals/
  data/{raw,processed}/
  analysis/{scripts,outputs}/
  manuscript/{drafts,revisions}/
  deliverables/
  audit/events.jsonl
  decisions/
  references/
```

All actual project workspaces are local-only by default and ignored by Git.
