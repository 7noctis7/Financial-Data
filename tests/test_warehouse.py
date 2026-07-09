import tempfile
import unittest
from pathlib import Path

from mesh import warehouse
from mesh.pipeline import run_business_day
from sim.generator import SimulatedTradingSource, simulate_bank_statements

DATE = "2026-07-09"


@unittest.skipUnless(warehouse.HAS_DUCKDB, "duckdb non installé (couche optionnelle)")
class TestWarehouse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        data_dir = Path(cls._tmp.name)
        run_business_day(
            DATE,
            trading_source=SimulatedTradingSource(seed=42, n_trades=120),
            statements_source=lambda t: simulate_bank_statements(t, seed=42),
            out_dir=data_dir / DATE,
        )
        cls.warehouse_dir = data_dir / "warehouse"
        cls.built = warehouse.build_warehouse(data_dir, cls.warehouse_dir)
        cls.con = warehouse.connect(cls.warehouse_dir)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()
        cls._tmp.cleanup()

    def test_all_tables_built(self):
        self.assertEqual(sorted(self.built),
                         ["audit_journal", "bank_statements", "cash_positions",
                          "exposures", "ledger", "trades"])

    def test_schema_reports_tables_and_counts(self):
        tables = {t["name"]: t for t in warehouse.schema(self.con)}
        self.assertEqual(tables["trades"]["rows"], 120)
        names = [c["name"] for c in tables["trades"]["columns"]]
        self.assertIn("business_date", names)
        self.assertIn("origin", names)  # la provenance reste visible en SQL

    def test_query_returns_rows(self):
        result = warehouse.query(
            self.con,
            "SELECT notional.currency AS ccy, count(*) AS n FROM trades GROUP BY 1 ORDER BY 2 DESC")
        self.assertEqual(result["columns"], ["ccy", "n"])
        self.assertEqual(sum(r[1] for r in result["rows"]), 120)

    def test_query_is_read_only(self):
        for sql in ("DROP VIEW trades", "DELETE FROM trades",
                    "SELECT 1; SELECT 2", "CREATE TABLE x(i INT)"):
            with self.assertRaises(ValueError):
                warehouse.query(self.con, sql)

    def test_query_truncates(self):
        result = warehouse.query(self.con, "SELECT * FROM trades", max_rows=10)
        self.assertEqual(len(result["rows"]), 10)
        self.assertTrue(result["truncated"])


if __name__ == "__main__":
    unittest.main()
