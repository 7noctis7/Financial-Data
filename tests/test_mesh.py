import copy
import json
import unittest
from pathlib import Path

from mesh import audit, schema
from mesh.circuit_breaker import CLOSED, HALF_OPEN, OPEN, CircuitBreaker
from mesh.lineage import Lineage, LineageError
from mesh.registry import CONTRACT_SCHEMA_PATH, Registry, load_ontology_terms, validate_contract
from mesh.sources import PRODUCTION, SIMULATED

REGISTRY = Registry()
CONTRACT_SCHEMA = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
ONTOLOGY = load_ontology_terms()


class TestOntology(unittest.TestCase):
    def test_terms_loaded_from_markdown(self):
        self.assertIn("Transaction", ONTOLOGY)
        self.assertIn("AuditAssertion", ONTOLOGY)
        self.assertGreaterEqual(len(ONTOLOGY), 10)


class TestRegistry(unittest.TestCase):
    def test_all_domain_contracts_are_valid(self):
        self.assertEqual(len(REGISTRY.products), 6)
        self.assertEqual(
            {c["domain"] for c in REGISTRY.products.values()},
            {"trading", "treasury", "risk", "audit", "regulatory", "client"},
        )

    def test_catalog_is_discoverable(self):
        entry = next(e for e in REGISTRY.catalog() if e["urn"] == "urn:fcc:risk:exposures")
        self.assertEqual(entry["entity"], "Exposure")
        self.assertIn("urn:fcc:trading:executed-trades", entry["sources"])

    def _contract(self):
        return copy.deepcopy(REGISTRY.get("urn:fcc:trading:executed-trades"))

    def test_unknown_ontology_term_rejected(self):
        contract = self._contract()
        contract["output_schema"]["entity"] = "Blockchain"
        errors = validate_contract(contract, ONTOLOGY, CONTRACT_SCHEMA)
        self.assertTrue(any("G2" in e for e in errors))

    def test_restricted_without_roles_rejected(self):
        contract = self._contract()
        contract["access"] = {"classification": "restricted"}
        errors = validate_contract(contract, ONTOLOGY, CONTRACT_SCHEMA)
        self.assertTrue(any("G7" in e for e in errors))

    def test_malformed_urn_rejected(self):
        contract = self._contract()
        contract["urn"] = "trades"
        self.assertTrue(validate_contract(contract, ONTOLOGY, CONTRACT_SCHEMA))

    def test_missing_slo_rejected(self):
        contract = self._contract()
        del contract["slo"]
        self.assertTrue(validate_contract(contract, ONTOLOGY, CONTRACT_SCHEMA))


class TestSchemaValidator(unittest.TestCase):
    def test_type_and_enum(self):
        s = {"type": "object", "required": ["x"], "properties": {"x": {"type": "string", "enum": ["a"]}}}
        self.assertEqual(schema.validate({"x": "a"}, s), [])
        self.assertTrue(schema.validate({"x": "b"}, s))
        self.assertTrue(schema.validate({}, s))

    def test_bool_is_not_a_number(self):
        self.assertTrue(schema.validate(True, {"type": "integer"}))


class TestAuditLog(unittest.TestCase):
    def _log(self):
        log = audit.AuditLog()
        log.append("auditor@fcc", "audit.check", "urn:fcc:treasury:cash-positions",
                   {"result": "ok"}, "2026-07-09T10:00:00Z")
        log.append("auditor@fcc", "audit.check", "urn:fcc:risk:exposures",
                   {"result": "ok"}, "2026-07-09T11:00:00Z")
        return log

    def test_chain_is_valid(self):
        self.assertIsNone(self._log().verify_chain())

    def test_tampering_is_detected(self):
        log = self._log()
        log._entries[0]["details"]["result"] = "falsified"
        self.assertEqual(log.verify_chain(), 0)

    def test_certified_assertion_requires_evidence(self):
        log = self._log()
        with self.assertRaises(audit.AssertionError_):
            audit.make_assertion(log, "auditor@fcc", "urn:fcc:treasury:cash-positions",
                                 "2026-06", audit.CERTIFIED, evidence=None,
                                 timestamp="2026-07-09T12:00:00Z", origin=PRODUCTION)

    def test_unknown_origin_rejected(self):
        with self.assertRaises(audit.AssertionError_):
            audit.make_assertion(self._log(), "auditor@fcc", "urn:fcc:risk:exposures",
                                 "2026-06", audit.QUALIFIED, evidence={},
                                 timestamp="2026-07-09T12:00:00Z", origin="staging")

    def test_assertion_roundtrip(self):
        log = self._log()
        assertion = audit.make_assertion(
            log, "auditor@fcc", "urn:fcc:treasury:cash-positions", "2026-06",
            audit.CERTIFIED, evidence={"reconciled_pct": 100.0},
            timestamp="2026-07-09T12:00:00Z", origin=PRODUCTION)
        self.assertTrue(audit.verify_assertion(log, assertion))
        log._entries[-1]["details"]["status"] = audit.FAILED
        self.assertFalse(audit.verify_assertion(log, assertion))


class TestCircuitBreaker(unittest.TestCase):
    def _breaker(self, audit_log=None):
        contract = {"urn": "urn:fcc:trading:executed-trades",
                    "slo": {"freshness_seconds": 300, "max_violation_rate": 0.2,
                            "cooldown_seconds": 600}}
        return CircuitBreaker(contract, audit_log=audit_log)

    def test_nominal_stays_closed(self):
        cb = self._breaker()
        for t in range(0, 1000, 100):
            cb.record_publication(t, schema_valid=True)
        self.assertEqual(cb.check(1000), CLOSED)

    def test_staleness_opens(self):
        cb = self._breaker()
        cb.record_publication(0, schema_valid=True)
        self.assertEqual(cb.check(301), OPEN)

    def test_drift_opens_and_logs(self):
        log = audit.AuditLog()
        cb = self._breaker(audit_log=log)
        for t in range(10):
            cb.record_publication(t, schema_valid=(t % 2 == 0))  # 50 % > 20 %
        self.assertEqual(cb.state, OPEN)
        self.assertEqual(log.entries()[-1]["action"], "circuit.open")
        self.assertIsNone(log.verify_chain())

    def test_recovery_via_half_open(self):
        cb = self._breaker()
        cb.record_publication(0, schema_valid=True)
        self.assertEqual(cb.check(301), OPEN)
        cb.record_publication(901, schema_valid=True)  # après cooldown
        self.assertEqual(cb.check(902), CLOSED)

    def test_half_open_reopens_if_still_stale(self):
        cb = self._breaker()
        cb.record_publication(0, schema_valid=True)
        self.assertEqual(cb.check(301), OPEN)
        self.assertEqual(cb.check(901), HALF_OPEN)
        self.assertEqual(cb.check(902), OPEN)  # toujours aucune publication


class TestLineage(unittest.TestCase):
    def setUp(self):
        self.lineage = Lineage(REGISTRY)

    def test_transitive_upstream(self):
        upstream = self.lineage.upstream("urn:fcc:regulatory:filings")
        self.assertIn("urn:fcc:trading:executed-trades", upstream)

    def test_explain_attaches_proof(self):
        explained = self.lineage.explain({
            "model": "recon-matcher-v1",
            "output": {"match_score": 0.97},
            "input_urns": ["urn:fcc:treasury:cash-positions"],
        })
        proof = explained["lineage_proof"][0]
        self.assertEqual(proof["contract_version"], "1.0.0")
        self.assertIn("urn:fcc:trading:executed-trades", proof["upstream"])

    def test_prediction_without_sources_rejected(self):
        with self.assertRaises(LineageError):
            self.lineage.explain({"model": "m", "output": {}, "input_urns": []})

    def test_prediction_with_unknown_source_rejected(self):
        with self.assertRaises(LineageError):
            self.lineage.explain({"model": "m", "output": {},
                                  "input_urns": ["urn:fcc:shadow:feed"]})


if __name__ == "__main__":
    unittest.main()
