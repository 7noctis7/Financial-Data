import tempfile
import unittest
from pathlib import Path

from mesh import audit
from mesh.derivations import combine_origin, derive_cash_positions, derive_exposures
from mesh.pipeline import run_business_day
from mesh.quality import validate_record
from mesh.registry import Registry
from mesh.regulatory import FilingError, OriginError, generate_filing
from mesh.sources import PRODUCTION, SIMULATED, make_batch
from sim.generator import SimulatedTradingSource, simulate_bank_statements

REGISTRY = Registry()
DATE = "2026-07-09"


def _day(seed=42, n_trades=250, drop_rate=0.005):
    trades = SimulatedTradingSource(seed=seed, n_trades=n_trades).fetch(DATE)
    statements = simulate_bank_statements(trades, seed=seed, drop_rate=drop_rate)
    return trades, statements


class TestSimulator(unittest.TestCase):
    def test_deterministic_replay(self):
        a = SimulatedTradingSource(seed=7).fetch(DATE)
        b = SimulatedTradingSource(seed=7).fetch(DATE)
        self.assertEqual(a, b)
        c = SimulatedTradingSource(seed=8).fetch(DATE)
        self.assertNotEqual(a, c)

    def test_trades_conform_to_contract(self):
        trades, _ = _day()
        contract = REGISTRY.get("urn:fcc:trading:executed-trades")
        for record in trades["records"]:
            self.assertEqual(validate_record(contract, record), [])

    def test_batches_are_marked_simulated(self):
        trades, statements = _day()
        self.assertEqual(trades["origin"], SIMULATED)
        self.assertEqual(statements["origin"], SIMULATED)

    def test_statements_mirror_settled_trades_with_drops(self):
        # drop_rate forcé haut pour garantir des trous quel que soit le seed
        trades, statements = _day(n_trades=2000, drop_rate=0.05)
        settled = sum(1 for t in trades["records"] if t["status"] == "settled")
        self.assertLess(len(statements["records"]), settled)
        self.assertGreater(len(statements["records"]), settled * 0.85)


class TestQuality(unittest.TestCase):
    def test_naked_amount_rejected(self):
        contract = REGISTRY.get("urn:fcc:trading:executed-trades")
        trade = dict(SimulatedTradingSource().fetch(DATE)["records"][0])
        trade["notional"] = 1_000_000
        self.assertTrue(any("couple" in e for e in validate_record(contract, trade)))

    def test_bad_timestamp_rejected(self):
        contract = REGISTRY.get("urn:fcc:trading:executed-trades")
        trade = dict(SimulatedTradingSource().fetch(DATE)["records"][0])
        trade["executed_at"] = "09/07/2026 14:00"
        self.assertTrue(validate_record(contract, trade))


class TestDerivations(unittest.TestCase):
    def test_origin_propagates_through_derivations(self):
        trades, statements = _day()
        cash = derive_cash_positions(trades, statements, DATE)
        self.assertEqual(cash["origin"], SIMULATED)
        self.assertEqual(
            combine_origin(make_batch("urn:fcc:trading:executed-trades",
                                      PRODUCTION, "t", [])),
            PRODUCTION,
        )

    def test_exposures_only_count_live_trades(self):
        trades, _ = _day()
        exposures = derive_exposures(trades, DATE)
        contract = REGISTRY.get("urn:fcc:risk:exposures")
        live_leis = {t["counterparty_lei"] for t in trades["records"]
                     if t["status"] == "executed"}
        self.assertEqual({r["counterparty_lei"] for r in exposures["records"]}, live_leis)
        for record in exposures["records"]:
            self.assertEqual(validate_record(contract, record), [])
            self.assertEqual(record["exposure"]["currency"], "EUR")

    def test_unmatched_flow_marks_account_unreconciled(self):
        trades, statements = _day(n_trades=2000, drop_rate=0.05)
        cash = derive_cash_positions(trades, statements, DATE)
        self.assertTrue(any(not r["reconciled"] for r in cash["records"]))

    def test_fully_matched_statements_reconcile(self):
        trades, statements = _day(drop_rate=0.0)
        cash = derive_cash_positions(trades, statements, DATE)
        self.assertTrue(all(r["reconciled"] for r in cash["records"]))


class TestRegulatoryG8(unittest.TestCase):
    def _assertion(self, origin, status=audit.CERTIFIED):
        log = audit.AuditLog()
        return audit.make_assertion(log, "auditor@fcc", "urn:fcc:risk:exposures",
                                    DATE, status, evidence={"records": 5},
                                    timestamp=f"{DATE}T19:00:00Z", origin=origin)

    def test_simulated_origin_refused(self):
        with self.assertRaises(OriginError):
            generate_filing("RULE-X", self._assertion(SIMULATED), f"{DATE}T20:00:00Z")

    def test_dry_run_is_marked_and_never_submittable(self):
        filing = generate_filing("RULE-X", self._assertion(SIMULATED),
                                 f"{DATE}T20:00:00Z", dry_run=True)
        self.assertTrue(filing["dry_run"])
        self.assertTrue(filing["filing_id"].startswith("DRYRUN-"))

    def test_production_certified_passes(self):
        filing = generate_filing("RULE-X", self._assertion(PRODUCTION),
                                 f"{DATE}T20:00:00Z")
        self.assertFalse(filing["dry_run"])
        self.assertTrue(filing["filing_id"].startswith("FIL-"))

    def test_qualified_assertion_refused_even_in_production(self):
        with self.assertRaises(FilingError):
            generate_filing("RULE-X", self._assertion(PRODUCTION, audit.QUALIFIED),
                            f"{DATE}T20:00:00Z")


class TestPipelineEndToEnd(unittest.TestCase):
    def test_full_business_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_business_day(
                DATE,
                trading_source=SimulatedTradingSource(seed=42, n_trades=250),
                statements_source=lambda t: simulate_bank_statements(t, seed=42),
                out_dir=tmp,
            )
            self.assertEqual(summary["origin"], SIMULATED)
            self.assertTrue(summary["audit_chain_intact"])
            self.assertEqual(len(summary["products"]), 4)
            trading = summary["products"]["urn:fcc:trading:executed-trades"]
            self.assertEqual(trading["records"], 250)
            self.assertEqual(trading["schema_violations"], 0)
            self.assertEqual(trading["breaker_state"], "closed")
            # G8 : aucune vraie soumission depuis du simulé, refus tracés
            self.assertTrue(all(f["dry_run"] for f in summary["filings"]))
            self.assertEqual(len(summary["g8_refusals"]), len(summary["filings"]))
            for name in ("trades", "cash-positions", "exposures", "ledger",
                         "audit-journal", "summary"):
                self.assertTrue((Path(tmp) / f"{name}.json").exists())


if __name__ == "__main__":
    unittest.main()
