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
            self.assertEqual({l["side"] for l in lines}, {"debit", "credit"})
            self.assertEqual(lines[0]["amount"], lines[1]["amount"])


if __name__ == "__main__":
    unittest.main()
