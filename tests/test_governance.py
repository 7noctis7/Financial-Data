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


class TestPersistentAuditLog(unittest.TestCase):
    def test_reload_preserves_chain_and_continues_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            log = AuditLog(path=path)
            h1 = log.append("ops@fcc", "test.first", "urn:fcc:audit:journal",
                            {"k": 1}, "2026-07-09T10:00:00Z")
            reloaded = AuditLog(path=path)
            self.assertEqual(len(reloaded.entries()), 1)
            self.assertIsNone(reloaded.verify_chain())
            h2 = reloaded.append("ops@fcc", "test.second", "urn:fcc:audit:journal",
                                 {"k": 2}, "2026-07-09T10:01:00Z")
            self.assertEqual(reloaded.entries()[1]["prev_hash"], h1)
            self.assertNotEqual(h1, h2)
            # le fichier contient bien les deux entrées, une par ligne
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)

    def test_two_writers_share_one_chain(self):
        # Serveur et export écrivent le même journal : chaque append doit
        # se chaîner sur la tête du FICHIER, pas sur la mémoire locale.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            a, b = AuditLog(path=path), AuditLog(path=path)
            for i in range(5):
                a.append("server@fcc", "test.a", "urn:fcc:audit:journal",
                         {"i": i}, "2026-07-09T10:00:00Z")
                b.append("export@fcc", "test.b", "urn:fcc:audit:journal",
                         {"i": i}, "2026-07-09T10:00:01Z")
            check = AuditLog(path=path)
            self.assertEqual(len(check.entries()), 10)
            self.assertIsNone(check.verify_chain())

    def test_reload_skips_unchanged_file(self):
        # Constat D1 : reload() ne doit relire que si le fichier a changé.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            log = AuditLog(path=path)
            log.append("ops@fcc", "test", "urn:fcc:audit:journal", {}, "2026-07-09T10:00:00Z")
            reader = AuditLog(path=path)
            self.assertEqual(len(reader.entries()), 1)
            calls = {"n": 0}
            original = reader._load_lines
            def counting(fh):
                calls["n"] += 1
                return original(fh)
            reader._load_lines = counting
            for _ in range(5):
                reader.entries()      # fichier inchangé -> aucune relecture
                reader.verify_chain()
            self.assertEqual(calls["n"], 0)

    def test_reload_detects_external_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            writer = AuditLog(path=path)
            reader = AuditLog(path=path)
            writer.append("ops@fcc", "test", "urn:fcc:audit:journal", {}, "2026-07-09T10:00:00Z")
            self.assertEqual(len(reader.entries()), 1)  # mtime a changé -> relu
            self.assertIsNone(reader.verify_chain())

    def test_verify_still_catches_tamper_after_memo(self):
        # La mémoïsation ne doit jamais masquer une falsification.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            log = AuditLog(path=path)
            log.append("ops@fcc", "a", "urn:fcc:audit:journal", {"k": 1}, "2026-07-09T10:00:00Z")
            log.append("ops@fcc", "b", "urn:fcc:audit:journal", {"k": 2}, "2026-07-09T10:01:00Z")
            self.assertIsNone(log.verify_chain())  # mémoïse l'état sain
            entries = [json.loads(ln) for ln in
                       path.read_text(encoding="utf-8").strip().splitlines()]
            entries[0]["details"]["k"] = 999
            path.write_text("\n".join(json.dumps(e, ensure_ascii=False)
                                      for e in entries) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):  # reload (mtime) -> re-vérif fraîche
                AuditLog(path=path)

    def test_tampered_file_refuses_to_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            log = AuditLog(path=path)
            log.append("ops@fcc", "test.first", "urn:fcc:audit:journal",
                       {"k": 1}, "2026-07-09T10:00:00Z")
            log.append("ops@fcc", "test.second", "urn:fcc:audit:journal",
                       {"k": 2}, "2026-07-09T10:01:00Z")
            entries = [json.loads(ln) for ln in
                       path.read_text(encoding="utf-8").strip().splitlines()]
            entries[0]["details"]["k"] = 999  # falsification a posteriori
            path.write_text("\n".join(json.dumps(e, ensure_ascii=False)
                                      for e in entries) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                AuditLog(path=path)


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


class TestProductionConnectivity(unittest.TestCase):
    CAMT = """<?xml version="1.0"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
 <BkToCstmrStmt><Stmt><CreDtTm>2026-07-09T18:00:00Z</CreDtTm>
  <Ntry><NtryRef>STL-TRD-20260709-00001</NtryRef><Amt Ccy="EUR">1000000.00</Amt>
   <CdtDbtInd>CRDT</CdtDbtInd><ValDt><Dt>2026-07-09</Dt></ValDt></Ntry>
  <Ntry><NtryRef>STL-TRD-20260709-00002</NtryRef><Amt Ccy="USD">250000.50</Amt>
   <CdtDbtInd>DBIT</CdtDbtInd><ValDt><Dt>2026-07-09</Dt></ValDt></Ntry>
 </Stmt></BkToCstmrStmt></Document>"""

    def test_camt053_parses_to_production_batch(self):
        from connectors.camt053 import parse_camt053
        batch = parse_camt053(self.CAMT)
        self.assertEqual(batch["origin"], "production")
        self.assertEqual(len(batch["records"]), 2)
        self.assertEqual(batch["records"][0]["amount"],
                         {"amount": 1000000.0, "currency": "EUR"})
        self.assertEqual(batch["records"][1]["amount"]["amount"], -250000.5)

    def test_camt053_rejects_garbage(self):
        from connectors.camt053 import Camt053Error, parse_camt053
        with self.assertRaises(Camt053Error):
            parse_camt053("<pas-du-camt/>")

    def test_camt053_rejects_xxe_doctype(self):
        # Le relevé vient d'une banque tierce : un DOCTYPE/ENTITY (vecteur
        # XXE / billion laughs) doit être refusé AVANT parsing.
        from connectors.camt053 import Camt053Error, parse_camt053
        xxe = ('<?xml version="1.0"?>\n'
               '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>\n'
               '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">'
               '<BkToCstmrStmt><Stmt>&xxe;</Stmt></BkToCstmrStmt></Document>')
        with self.assertRaises(Camt053Error):
            parse_camt053(xxe)

    def test_xbrl_format_produces_valid_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            generator = ReportGenerator(audit_log=AuditLog(),
                                        reports_dir=Path(tmp) / "r")
            meta = generator.demo("finrep_f0101_fr", "xbrl", requester="r@fcc",
                                  role="regulatory-officer", business_date=DATE)
            content = Path(meta["path"]).read_text(encoding="utf-8")
            self.assertTrue(content.startswith('<?xml'))
            self.assertIn("pre-mappage DPM", content)
            self.assertIn('<fcc:r380', content)
            self.assertIn("ANNEXE DE PREUVE", content)
