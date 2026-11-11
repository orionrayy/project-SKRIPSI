# Statistical Reproducibility & Diagnostics — v0.5.2

## Scope

This release strengthens the descriptive-only Statistical Engine. It does not add inferential statistics, choose a statistical test, impute or transform observations, infer causal effects, or grant human academic acceptance.

## Pinned input contract

Each v0.5.2 run record pins the SHA-256 of:

- the registered CSV dataset;
- the dataset artifact registry record;
- the analysis specification;
- the methodology research-alignment document;
- the decision register containing the scoped method approval;
- the T0–T9 phase ledger; and
- the project manifest (`project.json`).

The record also stores the package version, Python version/implementation, platform string, and a reproducibility-contract description covering hashing, CSV parsing, numeric representation, and result serialization. Input hashing compares filesystem identity/metadata before and after reading the file and rejects a file that changes during hashing.

`analysis-verify` checks the saved results, run record, pinned source inputs, current authorization/approval, and audit-chain pin. Changing any pinned input after a run invalidates verification; the old output is not silently updated.

## Recovery contract

`analysis-recover` only restores a prepared transaction; it never reruns the calculation. Before writing missing artifacts it validates the journal checksum, run/result identity, and every pinned source input. It validates the pinned inputs again after restoring `results.json` and `run.json`, immediately before appending/reusing the idempotent audit event.

When a pinned source input differs, recovery stops and preserves the journal and any partial output. Do not edit the journal to make the hashes match. Restore the exact source version from a trusted backup, or retain the transaction for manual investigation and create a new registered dataset/run after the research operator decides how to proceed. A changed source must not be treated as the original approved input.

Compatibility: v0.5.1 transactions without `project_manifest_path`/`project_manifest_sha256` remain readable. New v0.5.2 transactions pin `project.json` as well.

## Read-only computational replay

```bash
project-skripsi analysis-reproduce <workspace> RUN-<id>
```

The command first verifies the original run and its current pinned inputs. It then executes the same descriptive computation again, serializes the result under the recorded contract, and compares the recomputed SHA-256 with both `results.json` and `run.json`.

Possible statuses:

- `REPRODUCED`: hashes match;
- `DIVERGENCE`: verified inputs exist, but recomputation differs;
- `BLOCKED_INPUT_OR_ARTIFACT_INTEGRITY`: the original run or a pinned input does not verify;
- `BLOCKED_CURRENT_APPROVAL_OR_SPECIFICATION`: the current specification/authorization is no longer executable; or
- `BLOCKED_INPUT_CHANGED_DURING_REPRODUCTION`: a source changed while replay was in progress.

This is computational replay, not an independent reproduction by a second analyst or software implementation. The command is read-only: it writes no report, adds no audit event, does not alter `review_status`, and never changes phase acceptance. A cross-version replay is labelled `CROSS_VERSION_COMPATIBILITY_CHECK`; it must not be represented as same-version execution.

## Diagnostic summary

```bash
project-skripsi analysis-diagnostics <workspace> RUN-<id>
```

This command verifies the run and summarizes the diagnostics already attached to the result. It does not inspect or export participant-level rows. Current diagnostics cover descriptive data-quality and execution limitations such as missingness, constant variables, small-sample suppression, insufficient N for sample variance, zero variance, and category suppression.

These diagnostics do not test normality, independence, homoscedasticity, the missingness mechanism, measurement validity/reliability, sampling assumptions, or inferential-model adequacy. `INFO`, `WARNING`, and `ERROR` describe engine findings; they are not a substitute for a qualified statistician's assessment.

## Crash validation

The regression suite uses child Python processes terminated with `os._exit` after durable writes at four boundaries: prepared transaction, results file, run record, and audit append. The parent process then runs recovery, verifies the resulting artifact/audit chain, and performs read-only computational replay. These tests validate process termination and OS lock release in the current runtime; they do not establish native Windows filesystem/locking behavior until Windows CI is actually run.

## Human review and privacy

`review_status` remains `NOT_REVIEWED` after replay. A hash match proves byte-level computational consistency for the tested inputs and execution contract; it does not prove correct method selection, valid measurement, representative sampling, correct interpretation, ethical approval, or thesis acceptance. Real participant data remains private to its project workspace. No network service or external model is contacted by these commands.
