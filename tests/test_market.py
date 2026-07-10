import unittest

from mesh.derivations import FX_TO_EUR, derive_valuations
from mesh.pipeline import run_business_day
from mesh.sources import SIMULATED
from sim.generator import (INSTRUMENTS, SimulatedMarketDataSource,
                           SimulatedTradingSource, simulate_bank_statements)

DATE = "2026-07-09"


class TestMarketDataSource(unittest.TestCase):
    def test_deterministic_and_complete(self):
        a = SimulatedMarketDataSource(seed=42).fetch(DATE)
        b = SimulatedMarketDataSource(seed=42).fetch(DATE)
        self.assertEqual(a, b)
        self.assertEqual(len(a["records"]), len(INSTRUMENTS))
        self.assertEqual(a["origin"], SIMULATED)

    def test_prev_close_consistent_across_days(self):
        # Le prev_close du jour J doit être exactement le close du jour J-1
        # ouvré : les deux champs sortent de la même formule.
        source = SimulatedMarketDataSource(seed=42)
        today = {r["instrument_id"]: r for r in source.fetch("2026-07-09")["records"]}
        prev = {r["instrument_id"]: r for r in source.fetch("2026-07-08")["records"]}
        for instrument_id, record in today.items():
            self.assertEqual(record["prev_close"]["amount"],
                             prev[instrument_id]["close"]["amount"])

    def test_monday_prev_close_is_friday(self):
        monday = SimulatedMarketDataSource(seed=42).fetch("2026-07-06")
        friday = SimulatedMarketDataSource(seed=42).fetch("2026-07-03")
        px_monday = monday["records"][0]["prev_close"]["amount"]
        px_friday = friday["records"][0]["close"]["amount"]
        self.assertEqual(px_monday, px_friday)


class TestValuations(unittest.TestCase):
    def setUp(self):
        self.trades = SimulatedTradingSource(seed=42, n_trades=250).fetch(DATE)
        self.prices = SimulatedMarketDataSource(seed=42).fetch(DATE)
        self.valuations = derive_valuations(self.trades, self.prices, DATE)

    def test_mtm_is_return_times_live_notional(self):
        prices = {p["instrument_id"]: p for p in self.prices["records"]}
        for record in self.valuations["records"]:
            price = prices[record["instrument_id"]]
            expected_return = price["close"]["amount"] / price["prev_close"]["amount"] - 1
            self.assertAlmostEqual(record["daily_return"], expected_return, places=6)
            self.assertAlmostEqual(
                record["mtm_pnl"]["amount"],
                round(record["position_notional"]["amount"] * record["daily_return"], 2),
                delta=max(1.0, abs(record["position_notional"]["amount"]) * 1e-6))
            self.assertEqual(record["mtm_pnl"]["currency"], "EUR")

    def test_only_live_trades_are_valued(self):
        live_eur = {}
        for trade in self.trades["records"]:
            if trade["status"] != "executed":
                continue
            eur = trade["notional"]["amount"] * FX_TO_EUR[trade["notional"]["currency"]]
            live_eur[trade["instrument_id"]] = live_eur.get(trade["instrument_id"], 0) + eur
        for record in self.valuations["records"]:
            self.assertAlmostEqual(record["position_notional"]["amount"],
                                   round(live_eur[record["instrument_id"]], 2), places=2)

    def test_origin_propagates(self):
        self.assertEqual(self.valuations["origin"], SIMULATED)

    def test_missing_price_means_no_valuation(self):
        empty_prices = dict(self.prices, records=[])
        valuations = derive_valuations(self.trades, empty_prices, DATE)
        self.assertEqual(valuations["records"], [])  # jamais d'invention


class TestYahooConnector(unittest.TestCase):
    """Tests HORS LIGNE : la fonction de parsing est pure, la fixture
    reproduit le format réel de l'API chart Yahoo."""

    FIXTURE = {
        "chart": {"result": [{
            "meta": {"currency": "EUR"},
            # 2026-07-07, 08, 09, 10 à 00:00 UTC
            "timestamp": [1783382400, 1783468800, 1783555200, 1783641600],
            "indicators": {"quote": [{
                "close": [61.10, None, 62.00, 62.50],
            }]},
        }]},
    }

    def test_parse_takes_last_two_quotes_up_to_date(self):
        from connectors.yahoo_finance import _parse_chart
        close, prev_close, currency, close_date = _parse_chart(self.FIXTURE, "2026-07-10")
        self.assertEqual((close, prev_close, currency), (62.50, 62.00, "EUR"))
        self.assertLessEqual(close_date, "2026-07-10")

    def test_parse_skips_null_quotes(self):
        # Le None (jour férié / trou de cotation) ne doit jamais devenir un prix.
        from connectors.yahoo_finance import _parse_chart
        close, prev_close, _c, _d = _parse_chart(self.FIXTURE, "2026-07-09")
        self.assertEqual((close, prev_close), (62.00, 61.10))

    def test_parse_refuses_insufficient_history(self):
        from connectors.yahoo_finance import YahooError, _parse_chart
        with self.assertRaises(YahooError):
            _parse_chart(self.FIXTURE, "2026-07-07")  # une seule cotation <= date
        with self.assertRaises(YahooError):
            _parse_chart({"chart": {"result": []}}, "2026-07-10")

    def test_source_is_production_and_covers_known_instruments_only(self):
        from connectors.yahoo_finance import TICKERS, YahooFinanceSource
        from mesh.sources import PRODUCTION
        self.assertEqual(YahooFinanceSource.origin, PRODUCTION)
        known = {i for i, _c, _ccy, _m in INSTRUMENTS}
        self.assertTrue(set(TICKERS) <= known)
        # jamais de cours inventé pour les non-cotés (obligations, IRS)
        self.assertNotIn("FR0014007L00", TICKERS)
        self.assertNotIn("INT:IRS-EUR-5Y", TICKERS)

    def test_valuations_carry_price_source(self):
        prices = SimulatedMarketDataSource(seed=42).fetch(DATE)
        trades = SimulatedTradingSource(seed=42, n_trades=50).fetch(DATE)
        for record in derive_valuations(trades, prices, DATE)["records"]:
            self.assertEqual(record["price_source"], "SIMULATED-EOD")


class TestPipelineWithMarket(unittest.TestCase):
    def test_valuations_certified_in_daily_run(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_business_day(
                DATE,
                trading_source=SimulatedTradingSource(seed=42, n_trades=100),
                statements_source=lambda t: simulate_bank_statements(t, seed=42),
                market_source=SimulatedMarketDataSource(seed=42),
                out_dir=tmp)
            self.assertIn("urn:fcc:market:eod-prices", summary["products"])
            self.assertIn("urn:fcc:risk:valuations", summary["products"])
            self.assertEqual(len(summary["products"]), 7)
            self.assertEqual(
                summary["products"]["urn:fcc:risk:valuations"]["assertion"], "certified")


if __name__ == "__main__":
    unittest.main()
