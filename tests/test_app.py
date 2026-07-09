import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import __main__ as app_main
from app.data import build_payload

DATE = "2026-07-09"


class TestPayload(unittest.TestCase):
    def test_payload_shape(self):
        payload = build_payload(DATE, seed=42, n_trades=100)
        self.assertEqual(payload["origin"], "simulated")
        self.assertEqual(payload["kpis"]["trades"], 100)
        self.assertTrue(payload["kpis"]["audit_chain_intact"])
        self.assertEqual(len(payload["trades_by_hour"]), 11)  # 07h → 17h
        self.assertEqual(sum(r["count"] for r in payload["trades_by_hour"]), 100)
        self.assertLessEqual(len(payload["recent_trades"]), 10)
        self.assertEqual(len(payload["catalog"]), 7)
        json.dumps(payload)  # sérialisable tel quel


class TestExport(unittest.TestCase):
    def test_static_export_embeds_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(app_main, "DIST_DIR", Path(tmp)):
                app_main.export(DATE, seed=42, n_trades=50)
            page = (Path(tmp) / "index.html").read_text(encoding="utf-8")
        self.assertNotIn(app_main.DATA_PLACEHOLDER, page)
        self.assertIn('"business_date": "2026-07-09"', page)
        self.assertIn("Financial Command Center", page)


if __name__ == "__main__":
    unittest.main()
