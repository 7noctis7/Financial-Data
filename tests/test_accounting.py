import unittest

from mesh.accounting import derive_ledger, trial_balance
from mesh.quality import validate_record
from mesh.registry import Registry
from sim.generator import SimulatedTradingSource, simulate_bank_statements

DATE = "2026-07-09"
REGISTRY = Registry()


def _ledger(drop_rate=0.0, mutate_rate=0.0, n_trades=2000):
    trades = SimulatedTradingSource(seed=42, n_trades=n_trades).fetch(DATE)
    statements = simulate_bank_statements(trades, seed=42, drop_rate=drop_rate,
                                          mutate_rate=mutate_rate)
    return derive_ledger(trades, statements, DATE)


class TestGeneralLedger(unittest.TestCase):
    def test_entries_conform_to_contract(self):
        contract = REGISTRY.get("urn:fcc:accounting:general-ledger")
        ledger = _ledger(n_trades=200)
        self.assertTrue(ledger["records"])
        for entry in ledger["records"]:
            self.assertEqual(validate_record(contract, entry), [])

    def test_double_entry_always_balances(self):
        # même avec des flux manquants et des références mutilées
        balance = trial_balance(_ledger(drop_rate=0.02, mutate_rate=0.03))
        self.assertTrue(balance["balanced"])
        for ok in balance["balanced_by_currency"].values():
            self.assertTrue(ok)

    def test_clean_day_has_no_suspense(self):
        balance = trial_balance(_ledger())
        self.assertEqual(balance["suspense"], {})

    def test_unexplained_flows_land_in_suspense(self):
        balance = trial_balance(_ledger(drop_rate=0.02, mutate_rate=0.03))
        self.assertTrue(balance["suspense"])  # écarts exhibés, pas absorbés
        codes = {a["account_code"] for a in balance["accounts"]}
        self.assertIn("9990", codes)

    def test_each_event_books_debit_and_credit_same_amount(self):
        ledger = _ledger(n_trades=100)
        by_entry = {}
        for line in ledger["records"]:
            by_entry.setdefault(line["entry_id"], []).append(line)
        for lines in by_entry.values():
            self.assertEqual({ln["side"] for ln in lines}, {"debit", "credit"})
            self.assertEqual(lines[0]["amount"], lines[1]["amount"])


if __name__ == "__main__":
    unittest.main()


class TestPnlAndOffBalance(unittest.TestCase):
    def setUp(self):
        from mesh.fees import derive_fees
        trades = SimulatedTradingSource(seed=42, n_trades=250).fetch(DATE)
        statements = simulate_bank_statements(trades, seed=42)
        self.trades = trades
        from mesh.accounting import derive_ledger
        self.ledger = derive_ledger(trades, statements, DATE,
                                    fees_batch=derive_fees(trades, DATE))

    def test_pnl_revenue_equals_fee_income_account(self):
        from mesh.accounting import pnl_summary, trial_balance
        from mesh.derivations import FX_TO_EUR
        balance = trial_balance(self.ledger)
        pnl = pnl_summary(balance)
        expected = round(sum(-a["balance"] * FX_TO_EUR[a["currency"]]
                             for a in balance["accounts"] if a["account_code"] == "7000"), 2)
        self.assertEqual(pnl["chiffre_affaires"], expected)
        self.assertEqual(pnl["excedent_brut"], pnl["chiffre_affaires"])  # charges hors périmètre
        self.assertGreater(pnl["resultat_net"], 0)

    def test_off_balance_sheet_only_live_derivatives(self):
        from mesh.accounting import off_balance_sheet
        obs = off_balance_sheet(self.trades)
        labels = {l["engagement"] for l in obs["lines"]}
        self.assertTrue(labels.issubset({"Swaps de taux (IRS)", "Change à terme (FX forward)"}))
        self.assertAlmostEqual(obs["total_notionnel_eur"],
                               round(sum(l["notionnel_eur"] for l in obs["lines"]), 2), places=2)
        # aucun titre au comptant ni trade annulé dans le hors-bilan
        self.assertGreater(obs["total_notionnel_eur"], 0)


class TestSuspenseWorklist(unittest.TestCase):
    def _ledger(self, drop_rate, mutate_rate):
        trades = SimulatedTradingSource(seed=42, n_trades=2000).fetch(DATE)
        statements = simulate_bank_statements(trades, seed=42,
                                              drop_rate=drop_rate, mutate_rate=mutate_rate)
        from mesh.accounting import derive_ledger
        return derive_ledger(trades, statements, DATE)

    def test_worklist_lists_each_9990_flow_with_origin_reference(self):
        from mesh.accounting import suspense_worklist
        wl = suspense_worklist(self._ledger(0.03, 0.03), as_of=DATE)
        self.assertTrue(wl)  # des flux inexpliqués existent avec ces taux
        for r in wl:
            self.assertTrue(r["reference"])          # référence du flux d'origine
            self.assertIn(r["side"], ("debit", "credit"))
            self.assertNotEqual(r["contra_account"], "9990")  # la contrepartie, pas 9990
            self.assertEqual(r["age_days"], 0)       # écriture du jour d'arrêté

    def test_clean_day_has_empty_worklist(self):
        from mesh.accounting import suspense_worklist
        self.assertEqual(suspense_worklist(self._ledger(0.0, 0.0), as_of=DATE), [])
