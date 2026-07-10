import unittest

from mesh import cases, sar
from mesh.aml import screen
from mesh.audit import AuditLog
from mesh.four_eyes import FourEyesError, FourEyesRegister
from mesh.lineage import Lineage
from mesh.quality import validate_record
from mesh.registry import Registry
from sim.generator import SimulatedClientSource, SimulatedTradingSource

DATE = "2026-07-09"
REGISTRY = Registry()


def _kyc():
    return SimulatedClientSource(seed=42).fetch(DATE)


def _alerts():
    trades = SimulatedTradingSource(seed=42, n_trades=250).fetch(DATE)
    kyc = _kyc()
    for p in kyc["records"]:  # garantir au moins une alerte forte
        if p["lei"] == trades["records"][0]["counterparty_lei"]:
            p.update(pep=True, risk_rating="high", residence_country="PA")
    prediction = screen(trades, kyc, Lineage(REGISTRY))
    return kyc, prediction["output"]["alerts"]


class TestCaseDerivation(unittest.TestCase):
    def test_overdue_review_creates_a_case(self):
        # ACCEPTATION 1 : une revue échue crée un cas.
        candidates = cases.derive_kyc_review_candidates(_kyc(), DATE)
        self.assertTrue(candidates, "des revues > cycle existent dans le portefeuille")
        for case in candidates:
            self.assertEqual(case["case_type"], "kyc_review")
            self.assertEqual(case["status"], cases.OPEN)
            self.assertTrue(case["case_id"].startswith("CASE-KYC-"))

    def test_review_within_cycle_creates_no_case(self):
        kyc = _kyc()
        for p in kyc["records"]:  # revue d'aujourd'hui → dans le cycle
            p["last_review"] = f"{DATE}T00:00:00Z"
        self.assertEqual(cases.derive_kyc_review_candidates(kyc, DATE), [])

    def test_case_id_is_idempotent_on_replay(self):
        a = {c["case_id"] for c in cases.derive_kyc_review_candidates(_kyc(), DATE)}
        b = {c["case_id"] for c in cases.derive_kyc_review_candidates(_kyc(), DATE)}
        self.assertEqual(a, b)

    def test_records_conform_to_contract(self):
        contract = REGISTRY.get("urn:fcc:client:cases")
        for case in cases.derive_kyc_review_candidates(_kyc(), DATE):
            self.assertEqual(validate_record(contract, case), [])

    def test_aml_priority_is_derived_not_random(self):
        _, alerts = _alerts()
        derived = cases.derive_aml_candidates(alerts, DATE)
        self.assertTrue(derived)
        for case, alert in zip(derived, alerts):
            self.assertIn(case["priority"], ("high", "medium", "low"))
            if any(t["id"] in cases.HIGH_SEVERITY_TYPOLOGIES
                   for t in alert.get("typologies", [])):
                self.assertEqual(case["priority"], "high")


class TestStateMachine(unittest.TestCase):
    def test_legal_and_illegal_transitions(self):
        self.assertEqual(cases.next_status(cases.OPEN, cases.IN_REVIEW), cases.IN_REVIEW)
        self.assertEqual(cases.next_status(cases.IN_REVIEW, cases.CLEARED), cases.CLEARED)
        with self.assertRaises(cases.CaseTransitionError):
            cases.next_status(cases.OPEN, cases.CLEARED)  # doit passer par in_review
        with self.assertRaises(cases.CaseTransitionError):
            cases.next_status(cases.CLEARED, cases.IN_REVIEW)  # terminal

    def test_fold_applies_journaled_transitions(self):
        candidates = cases.derive_kyc_review_candidates(_kyc(), DATE)
        cid = candidates[0]["case_id"]
        log = AuditLog()
        for action, details in (
            ("case.assigned", {"case_id": cid, "assignee": "alice"}),
            ("case.review_started", {"case_id": cid}),
            ("case.cleared", {"case_id": cid}),
        ):
            log.append(actor="x", action=action, subject_urn=cases.CASE_URN,
                       details=details, timestamp=f"{DATE}T10:00:00Z")
        folded = {c["case_id"]: c for c in cases.fold_events(candidates, log.entries())}
        self.assertEqual(folded[cid]["assignee"], "alice")
        self.assertEqual(folded[cid]["status"], cases.CLEARED)


class TestFourEyes(unittest.TestCase):
    def test_no_closure_without_distinct_second_validator(self):
        # ACCEPTATION 2 : pas de clôture sans second validateur distinct.
        reg = FourEyesRegister()
        first = reg.submit("CASE-AML-T1", cases.CLEARED, "alice")
        self.assertEqual(first["status"], "pending")
        with self.assertRaises(FourEyesError):
            reg.submit("CASE-AML-T1", cases.CLEARED, "alice")  # même acteur refusé
        second = reg.submit("CASE-AML-T1", cases.CLEARED, "bob")
        self.assertEqual(second["status"], "committed")
        self.assertEqual(second["validators"], ["alice", "bob"])

    def test_distinct_actions_are_independent(self):
        reg = FourEyesRegister()
        reg.submit("CASE-AML-T1", cases.ESCALATED, "alice")
        # une proposition d'escalade ne valide pas un classement
        self.assertEqual(reg.submit("CASE-AML-T1", cases.CLEARED, "bob")["status"],
                         "pending")


class TestQueueSla(unittest.TestCase):
    def test_overdue_counter_flags_lapsed_cases(self):
        candidates = cases.derive_kyc_review_candidates(_kyc(), DATE)
        queue = cases.build_queue(candidates, DATE)
        self.assertEqual(queue["total"], len(candidates))
        # les revues échues de longue date dépassent leur SLA → au moins un retard
        self.assertGreater(queue["overdue"], 0)
        self.assertTrue(all(r["overdue"] for r in queue["cases"][:queue["overdue"]]))

    def test_filter_by_priority(self):
        candidates = cases.derive_kyc_review_candidates(_kyc(), DATE)
        high = cases.build_queue(candidates, DATE, priority="high")
        self.assertTrue(all(r["priority"] == "high" for r in high["cases"]))


class TestSar(unittest.TestCase):
    def test_no_sar_field_is_unsourced(self):
        # ACCEPTATION 3 : aucune SAR à champ non sourcé.
        kyc, alerts = _alerts()
        profiles = {p["client_id"]: p for p in kyc["records"]}
        aml_cases = cases.derive_aml_candidates(alerts, DATE)
        for case in aml_cases:
            alert = next(a for a in alerts if a["trade_id"] == case["source_ref"])
            document = sar.build_sar(case, profiles[case["subject_client_id"]],
                                     alert, DATE)
            self.assertEqual(sar.unsourced_fields(document), [])

    def test_kyc_only_sar_marks_transaction_nd_but_sourced(self):
        candidates = cases.derive_kyc_review_candidates(_kyc(), DATE)
        profiles = {p["client_id"]: p for p in _kyc()["records"]}
        case = candidates[0]
        document = sar.build_sar(case, profiles[case["subject_client_id"]], None, DATE)
        self.assertEqual(sar.unsourced_fields(document), [])  # n/d mais sourcé
        self.assertEqual(document["fields"]["transaction_ref"]["value"], "n/d")
        self.assertTrue(document["fields"]["transaction_ref"]["source"])


if __name__ == "__main__":
    unittest.main()
