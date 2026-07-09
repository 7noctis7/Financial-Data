import tempfile
import unittest
from pathlib import Path

from mesh import aml
from mesh.audit import AuditLog
from mesh.feedback import FeedbackStore
from mesh.lineage import Lineage
from mesh.registry import Registry
from sim.generator import SimulatedClientSource, SimulatedTradingSource

DATE = "2026-07-09"
REGISTRY = Registry()


class TestAmlScreening(unittest.TestCase):
    def setUp(self):
        self.trades = SimulatedTradingSource(seed=42, n_trades=250).fetch(DATE)
        self.kyc = SimulatedClientSource(seed=42).fetch(DATE)
        self.lineage = Lineage(REGISTRY)

    def test_kyc_profiles_conform_to_contract(self):
        from mesh.quality import validate_record
        contract = REGISTRY.get("urn:fcc:client:kyc-profiles")
        for record in self.kyc["records"]:
            self.assertEqual(validate_record(contract, record), [])

    def test_pep_counterparty_raises_alerts(self):
        # force un profil PEP à haut risque sur une contrepartie active
        for p in self.kyc["records"]:
            if p["lei"] == self.trades["records"][0]["counterparty_lei"]:
                p.update(pep=True, risk_rating="high", residence_country="PA")
        prediction = aml.screen(self.trades, self.kyc, self.lineage)
        self.assertIn("lineage_proof", prediction)  # G6
        alerts = prediction["output"]["alerts"]
        self.assertTrue(alerts)
        top = alerts[0]
        self.assertEqual(top["features"]["pep"], 1.0)
        self.assertGreaterEqual(top["score"], 0.65)

    def test_cancelled_trades_not_screened(self):
        prediction = aml.screen(self.trades, self.kyc, self.lineage)
        cancelled = sum(1 for t in self.trades["records"] if t["status"] == "cancelled")
        self.assertEqual(prediction["output"]["screened_trades"],
                         len(self.trades["records"]) - cancelled)

    def test_decision_logged_and_learned_with_aml_features(self):
        log = AuditLog()
        with tempfile.TemporaryDirectory() as tmp:
            feedback = FeedbackStore(Path(tmp) / "fb.jsonl",
                                     feature_order=aml.AML_FEATURES)
            alert = {"trade_id": "T1", "client_id": "CLI-0001", "score": 0.7,
                     "features": {"pep": 1.0, "high_risk_country": 0.0,
                                  "risk_rating": 1.0, "large_amount": 0.4,
                                  "velocity": 0.1}}
            aml.decide(alert, escalated=True, actor="compliance@fcc",
                       audit_log=log, timestamp=f"{DATE}T15:00:00Z", feedback=feedback)
            self.assertEqual(log.entries()[-1]["action"], "aml.escalated")
            self.assertIsNone(log.verify_chain())
            # une escalade renforce le score d'un cas similaire
            self.assertGreater(feedback.adjust(0.7, alert["features"]), 0.7)


if __name__ == "__main__":
    unittest.main()
