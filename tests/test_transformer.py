import unittest

from mesh.audit import AuditLog
from mesh.sources import SIMULATED
from mesh.transformer import DataTransformer
from sim.generator import SimulatedTradingSource

DATE = "2026-07-09"
CSV = """Deal Id;ISIN;LEI;Nominal;Ccy;State;Timestamp
D-1;FR0000120271;R0MUWSFPU8MPRO8K5P83;1000000;EUR;EXECUTED;2026-07-09T10:00:00Z
D-2;US0378331005;G5GSEF7VJP5I7OUK5573;pas-un-nombre;USD;EXECUTED;2026-07-09T11:00:00Z
D-3;DE0001102580;7LTWFZYICNSX8D621K86;2500000;EUR;SETTLED;2026-07-09T12:00:00Z
"""

MAPPING = {
    "trade_id": "Deal Id",
    "instrument_id": "ISIN",
    "counterparty_lei": "LEI",
    "notional": {"amount": "Nominal", "currency": "Ccy"},
    "status": lambda row: row["State"].lower(),
    "executed_at": "Timestamp",
}


class TestDataTransformer(unittest.TestCase):
    def setUp(self):
        self.log = AuditLog()
        self.transformer = DataTransformer(
            "urn:fcc:trading:executed-trades", MAPPING,
            audit_log=self.log, actor="ops@fcc")

    def test_csv_ingestion_maps_to_ontology(self):
        batch, rejects = self.transformer.transform_csv(
            CSV, SIMULATED, f"{DATE}T18:00:00Z")
        self.assertEqual(len(batch["records"]), 2)
        self.assertEqual(len(rejects), 1)  # montant non numérique
        self.assertIn("non numérique", rejects[0]["reason"])
        record = batch["records"][0]
        self.assertEqual(record["notional"], {"amount": 1000000.0, "currency": "EUR"})
        self.assertEqual(record["status"], "executed")  # lambda appliquée

    def test_audit_trail_is_injected_at_class_level(self):
        self.transformer.transform_csv(CSV, SIMULATED, f"{DATE}T18:00:00Z")
        entry = self.log.entries()[-1]
        self.assertEqual(entry["action"], "transform.ingested")
        self.assertEqual(entry["actor"], "ops@fcc")
        self.assertEqual(entry["details"]["accepted"], 2)
        self.assertEqual(entry["details"]["rejected"], 1)
        self.assertEqual(len(entry["details"]["input_sha256"]), 64)
        self.assertIsNone(self.log.verify_chain())

    def test_simulation_layer_plugs_via_from_source(self):
        batch, rejects = self.transformer.from_source(
            SimulatedTradingSource(seed=42, n_trades=50), DATE)
        self.assertEqual(len(batch["records"]), 50)
        self.assertEqual(rejects, [])
        self.assertEqual(batch["origin"], SIMULATED)
        self.assertEqual(self.log.entries()[-1]["details"]["source"],
                         "SimulatedTradingSource")

    def test_unknown_source_column_rejected_not_guessed(self):
        _, rejects = self.transformer.transform_csv(
            "WrongHeader\nx\n", SIMULATED, f"{DATE}T18:00:00Z", delimiter=",")
        self.assertEqual(len(rejects), 1)
        self.assertIn("colonne source manquante", rejects[0]["reason"])


if __name__ == "__main__":
    unittest.main()
