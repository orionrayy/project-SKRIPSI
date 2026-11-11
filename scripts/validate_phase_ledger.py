#!/usr/bin/env python3
"""Validate Project Skripsi phase ledger structure and sequential gates."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

EXPECTED_PHASES=[f"P{i}" for i in range(10)]
EXECUTION={"NOT_STARTED","IN_PROGRESS","EXECUTED","VALIDATION_PASSED_APPROVAL_PENDING","COMPLETE","BLOCKED","VALIDATION_FAILED"}
APPROVAL={"APPROVED","PENDING","NOT_AUTHORIZED","REJECTED","CONDITIONALLY_APPROVED"}
AUTHORIZATION={"APPROVED_SCOPED","AUTHORIZED_SCOPED","AUTHORIZED_TO_START","NOT_AUTHORIZED"}
VALIDATION={"NOT_RUN","PASS","PASS_WITH_LIMITATION","FAIL","NOT_APPLICABLE"}
ACCEPTANCE={"PENDING","ACCEPTED","ACCEPTED_WITH_CONDITIONS","REJECTED","DEFERRED"}
CONCLUSIONS={"NOT_STARTED","COMPLETE_AND_APPROVED","VALIDATION_PASSED_APPROVAL_PENDING","IN_PROGRESS","BLOCKED","VALIDATION_FAILED","REOPENED_FOR_MATERIAL_DEFECT"}

def load_json(path:Path)->Any:
    return json.loads(path.read_text(encoding="utf-8"))

def basic_schema_checks(ledger:dict,schema:dict)->list[str]:
    errors=[]
    for key in schema.get("required",[]):
        if key not in ledger: errors.append(f"missing root key: {key}")
    if ledger.get("project")!="project-skripsi": errors.append("project must be project-skripsi")
    phases=ledger.get("phases")
    if not isinstance(phases,list): return errors+["phases must be an array"]
    for i,p in enumerate(phases):
        required=schema.get("$defs",{}).get("phase",{}).get("required",[])
        for key in required:
            if key not in p: errors.append(f"phase[{i}] missing {key}")
        if p.get("execution_status") not in EXECUTION: errors.append(f"phase[{i}] invalid execution_status")
        if p.get("approval_status") not in APPROVAL: errors.append(f"phase[{i}] invalid approval_status")
        if p.get("authorization_status") not in AUTHORIZATION: errors.append(f"phase[{i}] invalid authorization_status")
        if p.get("validation_status") not in VALIDATION: errors.append(f"phase[{i}] invalid validation_status")
        if p.get("human_acceptance_status") not in ACCEPTANCE: errors.append(f"phase[{i}] invalid human_acceptance_status")
        if p.get("phase_conclusion") not in CONCLUSIONS: errors.append(f"phase[{i}] invalid phase_conclusion")
    return errors

def validate_ledger(ledger_path:Path,schema_path:Path)->list[str]:
    ledger=load_json(ledger_path); schema=load_json(schema_path); errors=[]
    try:
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(schema)
        errors.extend(f"schema: {list(e.path)}: {e.message}" for e in Draft202012Validator(schema).iter_errors(ledger))
    except ImportError:
        errors.extend(basic_schema_checks(ledger,schema))
    except Exception as exc:
        errors.append(f"schema validator error: {exc}")
    phases=ledger.get("phases",[]); ids=[p.get("phase_id") for p in phases]
    if ids!=EXPECTED_PHASES: errors.append(f"phase order must be {EXPECTED_PHASES}; got {ids}")
    if len(ids)!=len(set(ids)): errors.append("phase IDs must be unique")
    by={p.get("phase_id"):p for p in phases}
    p0=by.get("P0",{}); p1=by.get("P1",{}); p2=by.get("P2",{})
    if p0.get("execution_status")!="COMPLETE" or p0.get("approval_status")!="APPROVED" or p0.get("human_acceptance_status")!="ACCEPTED":
        errors.append("P0 must be COMPLETE/APPROVED/ACCEPTED before P1")
    if p1.get("execution_status")=="COMPLETE":
        if p1.get("approval_status")!="APPROVED" or p1.get("human_acceptance_status")!="ACCEPTED" or p1.get("phase_conclusion")!="COMPLETE_AND_APPROVED":
            errors.append("P1 COMPLETE requires APPROVED + ACCEPTED + COMPLETE_AND_APPROVED")
        if p1.get("validation_status") not in {"PASS","PASS_WITH_LIMITATION"}: errors.append("P1 COMPLETE requires passed validation")
        if not ledger.get("p1_acceptance_decision_record"): errors.append("P1 COMPLETE requires a human acceptance record path")
    elif p1.get("execution_status")=="VALIDATION_PASSED_APPROVAL_PENDING":
        if p1.get("validation_status") not in {"PASS","PASS_WITH_LIMITATION"} or p1.get("human_acceptance_status")!="PENDING" or p1.get("phase_conclusion")!="VALIDATION_PASSED_APPROVAL_PENDING":
            errors.append("P1 pending state must retain passed validation and pending acceptance")
        if p2.get("execution_status")!="NOT_STARTED" or p2.get("approval_status")!="NOT_AUTHORIZED" or p2.get("authorization_status")!="NOT_AUTHORIZED":
            errors.append("P2 must remain blocked while P1 acceptance is pending")
    elif p1.get("execution_status") not in {"COMPLETE","BLOCKED","VALIDATION_FAILED"}:
        errors.append("P1 state is inconsistent with its validation/acceptance gate")
    if p2.get("execution_status") in {"IN_PROGRESS","EXECUTED","VALIDATION_PASSED_APPROVAL_PENDING","COMPLETE"}:
        if p1.get("execution_status")!="COMPLETE" or p1.get("approval_status")!="APPROVED" or p1.get("human_acceptance_status")!="ACCEPTED":
            errors.append("P2 cannot start before P1 is COMPLETE/APPROVED/ACCEPTED")
        if p2.get("authorization_status") not in {"AUTHORIZED_SCOPED","AUTHORIZED_TO_START"}:
            errors.append("P2 execution requires its own scoped authorization")
    for i in range(1,10):
        cur=by.get(f"P{i}",{}); prev=by.get(f"P{i-1}",{})
        if cur.get("execution_status")=="COMPLETE" or cur.get("approval_status")=="APPROVED":
            if prev.get("execution_status")!="COMPLETE" or prev.get("approval_status")!="APPROVED":
                errors.append(f"{cur.get('phase_id')} cannot be complete/approved before {prev.get('phase_id')}")
    for i in range(3,10):
        cur=by.get(f"P{i}",{}); prev=by.get(f"P{i-1}",{})
        if cur.get("authorization_status") in {"AUTHORIZED_SCOPED","AUTHORIZED_TO_START"} and (prev.get("execution_status")!="COMPLETE" or prev.get("approval_status")!="APPROVED"):
            errors.append(f"{cur.get('phase_id')} cannot be authorized before {prev.get('phase_id')} is complete/approved")
    active=ledger.get("current_active_phase")
    expected_active=next((f"P{i}" for i in range(10) if by.get(f"P{i}",{}).get("phase_conclusion")!="COMPLETE_AND_APPROVED"),None)
    if active!=expected_active: errors.append(f"current_active_phase must be earliest incomplete phase {expected_active}; got {active}")
    allowed_remote_states={"NONE","PUBLIC_ALLOWLIST_POPULATED"}
    root_remote=ledger.get("remote_mutation_state")
    repo_remote=ledger.get("repository",{}).get("remote_mutation_state")
    if root_remote not in allowed_remote_states: errors.append("remote_mutation_state is not an approved state")
    if repo_remote not in allowed_remote_states: errors.append("repository.remote_mutation_state is not an approved state")
    if root_remote != repo_remote: errors.append("root and repository remote mutation states must match")
    if root_remote == "PUBLIC_ALLOWLIST_POPULATED":
        publication_policy=Path("docs/platform/PUBLIC_REPOSITORY_PUBLICATION.md")
        if not publication_policy.is_file(): errors.append("public allowlist publication state requires docs/platform/PUBLIC_REPOSITORY_PUBLICATION.md")
    return errors

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--ledger",default="config/pipeline/PHASE_LEDGER.json"); ap.add_argument("--schema",default="schemas/pipeline/PHASE_LEDGER.schema.json"); args=ap.parse_args()
    errors=validate_ledger(Path(args.ledger),Path(args.schema))
    if errors:
        print(f"FAIL: {len(errors)} error(s)"); [print("- "+e) for e in errors]; return 1
    print("PASS: phase ledger schema and sequential invariants")
    ledger = load_json(Path(args.ledger))
    by_phase = {phase["phase_id"]: phase for phase in ledger["phases"]}
    p0, p1, p2 = (by_phase[name] for name in ("P0", "P1", "P2"))
    print(
        "PASS: "
        f"P0 {p0['execution_status']}/{p0['approval_status']}/{p0['human_acceptance_status']}; "
        f"P1 {p1['execution_status']}/{p1['approval_status']}/{p1['human_acceptance_status']}; "
        f"P2 {p2['execution_status']} "
        f"(approval={p2['approval_status']}, acceptance={p2['human_acceptance_status']}, "
        f"authorization={p2['authorization_status']})"
    )
    print("PASS: P3-P9 remain gated; remote mutation state is explicitly allowlist-scoped")
    return 0
if __name__=="__main__": raise SystemExit(main())
