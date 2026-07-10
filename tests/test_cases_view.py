import unittest

from app import cases_view
from mesh import cases
from mesh.audit import AuditLog
from mesh.four_eyes import FourEyesError, FourEyesRegister
from mesh.registry import Registry

DATE = "2026-07-09"
REGISTRY = Registry()


def _open_kyc_case_id(log):
    data = cases_view.payload(REGISTRY, log, DATE, filters={
        "case_type": "kyc_review", "status": "open"})
    return data["cases"][0]["case_id"]


class TestCasesView(unittest.TestCase):
    def setUp(self):
        self.log = AuditLog()           # journal en mémoire, chaîné
        self.fe = FourEyesRegister()

    def _body(self, **kw):
        return dict(date=DATE, **kw)

    def test_payload_exposes_queue_counts_and_assignees(self):
        data = cases_view.payload(REGISTRY, self.log, DATE)
        self.assertGreater(data["total"], 0)
        self.assertIn("kyc_review", data["counts"])
        self.assertEqual(data["assignees"], [])  # rien d'assigné au départ

    def test_full_lifecycle_with_four_eyes(self):
        cid = _open_kyc_case_id(self.log)
        cases_view.decide(REGISTRY, self.log, self.fe,
                          self._body(case_id=cid, action="assign",
                                     assignee="alice", actor="alice"))
        cases_view.decide(REGISTRY, self.log, self.fe,
                          self._body(case_id=cid, action="review_started", actor="alice"))
        pending = cases_view.decide(REGISTRY, self.log, self.fe,
                                    self._body(case_id=cid, action="cleared", actor="alice"))
        self.assertTrue(pending["pending"])
        with self.assertRaises(FourEyesError):  # même acteur refusé
            cases_view.decide(REGISTRY, self.log, self.fe,
                              self._body(case_id=cid, action="cleared", actor="alice"))
        done = cases_view.decide(REGISTRY, self.log, self.fe,
                                 self._body(case_id=cid, action="cleared", actor="bob"))
        self.assertEqual(done["status"], "cleared")
        self.assertEqual(done["validated_by"], ["alice", "bob"])
        self.assertTrue(done["audit_chain_intact"])
        # l'état persiste dans le repli du journal
        after = {c["case_id"]: c for c in
                 cases_view.payload(REGISTRY, self.log, DATE)["cases"]}
        self.assertEqual(after[cid]["status"], cases.CLEARED)
        self.assertEqual(after[cid]["assignee"], "alice")

    def test_illegal_transition_refused_at_view(self):
        cid = _open_kyc_case_id(self.log)
        with self.assertRaises(cases.CaseTransitionError):
            cases_view.decide(REGISTRY, self.log, self.fe,  # clore un cas 'open'
                              self._body(case_id=cid, action="cleared", actor="bob"))

    def test_sar_document_is_fully_sourced(self):
        data = cases_view.payload(REGISTRY, self.log, DATE,
                                  filters={"case_type": "aml_alert"})
        cid = data["cases"][0]["case_id"]
        doc = cases_view.sar_document(REGISTRY, self.log,
                                      self._body(case_id=cid))
        self.assertEqual(doc["unsourced"], [])


if __name__ == "__main__":
    unittest.main()
