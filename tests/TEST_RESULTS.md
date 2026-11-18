# Deterministic Windows stable-hash regression fixture — 2026-11-18

| Check | Result |
|---|---:|
| Dedicated visual-composition tests | **7/7 PASS (local)** |
| Git-blob restoration tests | **3/3 PASS (local)** |
| Combined focused tests | **10/10 PASS (local)** |
| Latest matrix before fixture correction | 5/6 jobs PASS; Windows/Python 3.11 failed the same-length mutation timing test |
| Windows manifest restore + verification | PASS on all three Windows jobs |
| Windows matrix interpreter selection | Corrected and verified in Python 3.10, 3.11 and 3.12 job setup |
| Stable-hash test fixture | Changed to deterministic file-size mutation |
| Next six-job CI run | PENDING |

The method-scaffold "already exists" message is the expected second invocation's stderr; the corresponding test status was ok. No production hashing logic has been weakened.

# Windows matrix interpreter-order candidate — 2026-11-18

| Check | Result |
|---|---:|
| Visual composition unit tests | **7/7 PASS (local)** |
| Git-blob restoration helper tests | **3/3 PASS (local)** |
| Combined focused tests | **10/10 PASS (local)** |
| Manifest restoration and verification | **6/6 jobs passed this step in follow-up run** |
| Compile + phase-ledger validation | Passed on all observed completed jobs |
| Windows/Python 3.12 full suite | Failed: LibreOffice embedded Python shadowed matrix Python |
| CI step ordering fix | Committed; follow-up run pending |
| Full six-platform suite | NOT_YET_VERIFIED |

The interpreter-order correction moves LibreOffice installation before actions/setup-python. Wait for the next six-job run before changing the cross-platform validation status.

---

# Cross-platform manifest restoration candidate — 2026-11-18

| Check | Result |
|---|---:|
| Git-blob restoration helper tests | **3/3 PASS (local)** |
| Exact-byte write assertion | PASS |
| Missing Git blob fail-closed test | PASS |
| Path traversal rejection | PASS |
| First feature PR Ubuntu matrix | **3/3 PASS** |
| First feature PR Windows matrix | **3/3 FAIL at manifest verification** |
| Follow-up six-job CI | PENDING |
| Full repository suite on follow-up head | PENDING |

The Windows failures occurred before compile and unit-test steps. Earlier main-branch push CI had passed the Windows manifest check. The follow-up candidate now restores manifest-listed files directly from Git blobs before invoking the existing exact-byte verifier. This is a remediation candidate, not yet a validated cross-platform resolution.

---

# Visual composition candidate validation — 2026-11-18

| Check | Result |
|---|---:|
| Dedicated visual composition unit tests | **7/7 PASS** |
| New Draft 2020-12 schemas (meta-validation) | **2/2 PASS** |
| Event-TOR policy schema instance | PASS |
| Generated audit report schema instance | PASS |
| Reader-task test | NOT_RUN |
| Eye-tracking evidence | NOT_MEASURED |
| Full repository suite on this candidate branch | NOT_RUN |

The audit operates on synthetic PDF test fixtures. The separate local TOR output was inspected and audited outside the public repository; its source files, identity fields, assets and per-document report are not included here. A profile-specific geometry PASS does not certify aesthetic quality, reader comprehension, institutional compliance or human acceptance.

---

# Project-SKRIPSI v0.8.0 — Public Platform Test Results

**Release checkpoint:** 2026-11-10 (Asia/Jakarta)

## Platform engineering validation

| Check | Result |
|---|---:|
| Full unit/regression suite | **200/200 PASS** |
| JSON Schema Draft 2020-12 meta-validation | **29/29 PASS** |
| Python compileall | PASS |
| Phase-ledger validator | PASS |
| CLI smoke tests | PASS |
| Public source manifest | PASS (all entries match) |

Tests include revision pair reconciliation, marked-region accounting, instrument and paired-test evidence gates, local Turnitin report metadata parsing/comparison, artifact integrity, statistical reproducibility, document assembly, phase authorization invariants, and deterministic public-source packaging with checksum/path-traversal safeguards. Turnitin parser tests use fully synthetic report metadata and do not embed real thesis/report material.

## Research phase boundary

The canonical ledger remains P0/P1 `COMPLETE_AND_APPROVED` in their bounded scopes; P2 `VALIDATION_PASSED_APPROVAL_PENDING`; P3–P9 `NOT_STARTED / NOT_AUTHORIZED`. Platform test success does not accept P2 or authorize P3.

P2's published aggregate summary is in `docs/phases/P2_EXECUTION_REPORT.md`. Record-level research files and private validation artifacts are not part of this public repository.

## Limitations

These are local platform tests. They are not evidence of a GitHub Actions run, external independent academic review, institutional compliance, or acceptance of any thesis/research phase.
