from __future__ import annotations
import json, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from validate_phase_ledger import validate_ledger
LEDGER=ROOT/"config/pipeline/PHASE_LEDGER.json"
SCHEMA=ROOT/"schemas/pipeline/PHASE_LEDGER.schema.json"
class PhaseLedgerTests(unittest.TestCase):
    def load(self): return json.loads(LEDGER.read_text(encoding="utf-8"))
    def check_temp(self,data):
        tmp=ROOT/"tests"/"_tmp_phase_ledger.json"
        try:
            tmp.write_text(json.dumps(data),encoding="utf-8")
            return validate_ledger(tmp,SCHEMA)
        finally: tmp.unlink(missing_ok=True)
    def test_current_ledger_is_valid(self): self.assertEqual(validate_ledger(LEDGER,SCHEMA),[])
    def test_duplicate_phase_id_rejected(self):
        d=self.load(); d["phases"][2]["phase_id"]="P1"; self.assertTrue(self.check_temp(d))
    def test_p2_cannot_complete_while_p1_pending(self):
        d=self.load(); p={x["phase_id"]:x for x in d["phases"]}; p["P1"].update(execution_status="VALIDATION_PASSED_APPROVAL_PENDING",approval_status="PENDING",human_acceptance_status="PENDING",phase_conclusion="VALIDATION_PASSED_APPROVAL_PENDING"); p["P2"].update(execution_status="COMPLETE",approval_status="APPROVED",human_acceptance_status="ACCEPTED",phase_conclusion="COMPLETE_AND_APPROVED"); d["current_active_phase"]="P1"; self.assertTrue(self.check_temp(d))
    def test_p1_complete_requires_human_acceptance(self):
        d=self.load(); p=d["phases"][1]; p["human_acceptance_status"]="PENDING"; self.assertTrue(self.check_temp(d))
    def test_p2_requires_own_authorization(self):
        d=self.load(); d["phases"][2]["authorization_status"]="NOT_AUTHORIZED"; self.assertTrue(self.check_temp(d))
    def test_future_phase_may_be_pre_authorized_but_not_executed(self):
        d=self.load()
        p={x["phase_id"]:x for x in d["phases"]}
        p["P4"]["authorization_status"]="AUTHORIZED_SCOPED"
        p["P4"]["execution_status"]="NOT_STARTED"
        p["P4"]["approval_status"]="PENDING"
        p["P4"]["human_acceptance_status"]="PENDING"
        p["P4"]["validation_status"]="NOT_RUN"
        p["P4"]["phase_conclusion"]="NOT_STARTED"
        self.assertEqual(self.check_temp(d),[])

    def test_future_phase_cannot_execute_before_predecessor_acceptance(self):
        d=self.load()
        p={x["phase_id"]:x for x in d["phases"]}
        p["P4"]["authorization_status"]="AUTHORIZED_SCOPED"
        p["P4"]["execution_status"]="IN_PROGRESS"
        d["current_active_phase"]="P3"
        self.assertTrue(self.check_temp(d))
    def test_earliest_incomplete_phase_is_active(self):
        d=self.load(); d["current_active_phase"]="P3"; self.assertTrue(self.check_temp(d))
    def test_unscoped_remote_mutation_rejected(self):
        d=self.load(); d["remote_mutation_state"]="PUSHED"; d["repository"]["remote_mutation_state"]="PUSHED"; self.assertTrue(self.check_temp(d))
    def test_allowlist_scoped_publication_is_valid(self):
        d=self.load(); d["remote_mutation_state"]="PUBLIC_ALLOWLIST_POPULATED"; d["repository"]["remote_mutation_state"]="PUBLIC_ALLOWLIST_POPULATED"; self.assertEqual(self.check_temp(d),[])
    def test_remote_mutation_states_must_match(self):
        d=self.load(); d["remote_mutation_state"]="PUBLIC_ALLOWLIST_POPULATED"; d["repository"]["remote_mutation_state"]="NONE"; self.assertTrue(self.check_temp(d))
    def test_phase_order_is_sequential(self):
        d=self.load(); d["phases"][0],d["phases"][1]=d["phases"][1],d["phases"][0]; self.assertTrue(self.check_temp(d))
if __name__=="__main__": unittest.main()
