import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from connectors.fix_trading import FixExecutionConnector
from mesh import audit, iam
from mesh.audit import AuditLog
from mesh.feedback import FeedbackStore
from mesh.lineage import Lineage
from mesh.reconciliation import decide, suggest, unmatched
from mesh.registry import Registry
from reporting.generator import ReportError, ReportGenerator, demo_assertions
from sim.generator import SimulatedTradingSource, simulate_bank_statements

DATE = "2026-07-09"
REGISTRY = Registry()


class TestIAM(unittest.TestCase):
    def test_clearance_ladder(self):
        iam.check_access("auditor", iam.RESTRICTED)
        iam.check_access("risk-analyst", iam.INTERNAL)
        with self.assertRaises(iam.AccessError):
            iam.check_access("viewer", iam.INTERNAL)
        with self.assertRaises(iam.AccessError):
            iam.check_access("treasury-ops", iam.RESTRICTED)

    def test_unknown_role_denied_even_for_public(self):
        with self.assertRaises(iam.AccessError):
            iam.check_access("stagiaire", iam.PUBLIC)

    def test_explicit_role_list_narrows(self):
        with self.assertRaises(iam.AccessError):
            iam.check_access("trader", iam.INTERNAL, allowed_roles=["auditor"])

    def test_denial_is_audited(self):
        log = AuditLog()
        with self.assertRaises(iam.AccessError):
            iam.check_access("viewer", iam.RESTRICTED, audit_log=log,
                             actor="v@fcc", timestamp="2026-07-09T10:00:00Z")
        self.assertEqual(log.entries()[-1]["action"], "iam.denied")
        self.assertIsNone(log.verify_chain())


class TestReconciliation(unittest.TestCase):
    def setUp(self):
        self.trades = SimulatedTradingSource(seed=42, n_trades=2000).fetch(DATE)
        self.statements = simulate_bank_statements(self.trades, seed=42, drop_rate=0.05)
        self.lineage = Lineage(REGISTRY)

    def test_unmatched_found(self):
        missing, unknown = unmatched(self.trades, self.statements)
        self.assertGreater(len(missing), 0)  # drop_rate garantit des trous
        self.assertEqual(len(unknown), 0)    # le simulateur ne crée pas d'inconnus

    def test_suggestions_are_lineage_wrapped_and_explainable(self):
        # un relevé orphelin proche d'un trade manquant → suggestion
        missing, _ = unmatched(self.trades, self.statements)
        trade = missing[0]
        self.statements["records"].append({
            "reference": f"STL-{trade['trade_id']}-DUP",
            "amount": {"amount": trade["notional"]["amount"],
                       "currency": trade["notional"]["currency"]},
            "value_date": f"{DATE}T00:00:00Z",
        })
        prediction = suggest(self.trades, self.statements, self.lineage)
        self.assertIn("lineage_proof", prediction)  # G6
        top = prediction["output"]["suggestions"][0]
        self.assertEqual(top["trade_id"], trade["trade_id"])
        self.assertIn("amount_proximity", top["features"])  # score décomposé

    def test_human_decision_logged_and_learned(self):
        log = AuditLog()
        with tempfile.TemporaryDirectory() as tmp:
            feedback = FeedbackStore(Path(tmp) / "fb.jsonl")
            suggestion = {"trade_id": "T1", "statement_reference": "S1", "score": 0.9,
                          "features": {"currency_match": 1.0, "amount_proximity": 0.99,
                                       "reference_similarity": 0.9, "same_day": 1.0}}
            decide(suggestion, accepted=False, actor="ops@fcc", audit_log=log,
                   timestamp="2026-07-09T15:00:00Z", feedback=feedback)
            self.assertEqual(log.entries()[-1]["action"], "reconciliation.rejected")
            # le feedback négatif tire un score similaire vers le bas
            adjusted = feedback.adjust(0.9, suggestion["features"])
            self.assertLess(adjusted, 0.9)
            # persistance : un nouveau store relit le même apprentissage
            self.assertEqual(len(FeedbackStore(Path(tmp) / "fb.jsonl")), 1)


class TestConnector(unittest.TestCase):
    def test_fix_messages_translated_and_validated(self):
        connector = FixExecutionConnector(REGISTRY)
        ok = {"35": "8", "17": "EXEC-1", "48": "FR0000120271",
              "452": "R0MUWSFPU8MPRO8K5P83", "31": "62.5", "32": "10000",
              "15": "EUR", "39": "2", "60": f"{DATE}T10:00:00Z"}
        bad_type = dict(ok, **{"35": "D"})
        missing_tag = {k: v for k, v in ok.items() if k != "31"}
        batch, rejects = connector.ingest([ok, bad_type, missing_tag],
                                          f"{DATE}T18:00:00Z")
        self.assertEqual(len(batch["records"]), 1)
        self.assertEqual(batch["records"][0]["notional"],
                         {"amount": 625000.0, "currency": "EUR"})
        self.assertEqual(len(rejects), 2)
        self.assertIn("ExecutionReport", rejects[0]["reason"])


class TestReporting(unittest.TestCase):
    def _generator(self, tmp):
        return ReportGenerator(audit_log=AuditLog(),
                               reports_dir=Path(tmp) / "reports")

    def test_all_formats_with_proof_annex(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = self._generator(tmp)
            for fmt in ("csv", "xlsx", "pdf"):
                meta = generator.demo("regulatory", fmt, requester="u@fcc",
                                      role="regulatory-officer", business_date=DATE)
                path = Path(meta["path"])
                content = path.read_bytes()
                self.assertEqual(len(meta["file_hash"]), 64)
                sidecar = json.loads((path.parent / (path.name + ".proof.json"))
                                     .read_text(encoding="utf-8"))
                self.assertEqual(sidecar["audit_proof_hash"], meta["audit_proof_hash"])
                if fmt == "csv":
                    self.assertIn("ANNEXE DE PREUVE", content.decode("utf-8"))
                    self.assertIn(meta["content_hash"], content.decode("utf-8"))
                elif fmt == "xlsx":
                    with zipfile.ZipFile(path) as z:  # zip valide + annexe
                        self.assertIn("xl/worksheets/sheet2.xml", z.namelist())
                        self.assertIn(meta["content_hash"],
                                      z.read("xl/worksheets/sheet2.xml").decode())
                else:
                    self.assertTrue(content.startswith(b"%PDF-1.4"))
                    self.assertTrue(content.rstrip().endswith(b"%%EOF"))

    def test_export_blocked_by_iam(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = self._generator(tmp)
            with self.assertRaises(iam.AccessError):
                generator.demo("regulatory", "csv", requester="t@fcc",
                               role="treasury-ops", business_date=DATE)
            self.assertEqual(generator.audit_log.entries()[-1]["action"], "iam.denied")
            self.assertEqual(list(Path(tmp, "reports").glob("*")), [])  # rien de rendu

    def test_missing_assertion_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = self._generator(tmp)
            assertions = demo_assertions(generator.audit_log,
                                         "urn:fcc:risk:exposures", DATE, "simulated")
            del assertions["completeness"]
            with self.assertRaises(ReportError):
                generator.generate("regulatory", [], assertions, "u@fcc",
                                   "regulatory-officer")

    def test_qualified_assertion_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = self._generator(tmp)
            assertions = demo_assertions(generator.audit_log,
                                         "urn:fcc:risk:exposures", DATE, "simulated")
            assertions["accuracy"] = audit.make_assertion(
                generator.audit_log, "a@fcc", "urn:fcc:risk:exposures",
                f"{DATE}:accuracy", audit.QUALIFIED, evidence={},
                timestamp=f"{DATE}T19:00:00Z", origin="simulated")
            with self.assertRaises(ReportError):
                generator.generate("regulatory", [], assertions, "u@fcc",
                                   "regulatory-officer")

    def test_emir_template_filters_derivatives_and_cites_norm(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = self._generator(tmp)
            meta = generator.demo("emir", "csv", requester="r@fcc",
                                  role="regulatory-officer", business_date=DATE)
            self.assertIn("648/2012", meta["norm_ref"])
            content = Path(meta["path"]).read_text(encoding="utf-8")
            self.assertIn("Norme source", content)
            self.assertIn("IRS", content)              # dérivés présents
            self.assertNotIn("FR0000120271", content)  # actions exclues

    def test_mifid2_template_reports_all_executions(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = self._generator(tmp)
            meta = generator.demo("mifid2", "xlsx", requester="r@fcc",
                                  role="regulatory-officer", business_date=DATE)
            self.assertIn("RTS 22", meta["norm_ref"])
            self.assertGreater(meta["rows"], 200)  # ~250 trades moins annulés

    def test_finrep_restitution_controls_pass_and_are_sealed(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = self._generator(tmp)
            meta = generator.demo("finrep_f0101_fr", "csv", requester="r@fcc",
                                  role="regulatory-officer", business_date=DATE)
            self.assertEqual(len(meta["controls"]), 3)
            self.assertTrue(all(c["ok"] for c in meta["controls"]))
            content = Path(meta["path"]).read_text(encoding="utf-8")
            self.assertIn("Controles de restitution : 3/3 OK", content)

    def test_broken_total_blocks_delivery(self):
        from reporting.generator import demo_assertions
        with tempfile.TemporaryDirectory() as tmp:
            generator = self._generator(tmp)
            assertions = demo_assertions(generator.audit_log,
                                         "urn:fcc:accounting:general-ledger",
                                         DATE, "simulated")
            rows = [{"row_ref": r, "item": "x", "reference": "", "amount_eur": v}
                    for r, v in [("010", 100.0), ("040", 100.0), ("050", 50.0),
                                 ("060", 30.0), ("080", 20.0), ("360", 0.0),
                                 ("380", 999.0)]]  # total falsifié
            with self.assertRaises(ReportError):
                generator.generate("finrep_f0101_fr", rows, assertions, "r@fcc",
                                   "regulatory-officer",
                                   control_context={"ledger_equity_eur": 150.0})
            self.assertEqual(generator.audit_log.entries()[-1]["action"],
                             "report.control_failed")

    def test_generation_is_chained_in_audit_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = self._generator(tmp)
            meta = generator.demo("treasury", "csv", requester="t@fcc",
                                  role="treasury-ops", business_date=DATE)
            entry = generator.audit_log.entries()[-1]
            self.assertEqual(entry["action"], "report.generated")
            self.assertEqual(entry["details"]["file_hash"], meta["file_hash"])
            self.assertIsNone(generator.audit_log.verify_chain())


if __name__ == "__main__":
    unittest.main()
