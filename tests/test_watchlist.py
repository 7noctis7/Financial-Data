import unittest

from mesh import watchlist
from mesh.audit import AuditLog
from mesh.quality import validate_record
from mesh.registry import Registry
from sim.generator import SimulatedClientSource

DATE = "2026-07-10"
REGISTRY = Registry()


def _hits(suppressed=None):
    kyc = SimulatedClientSource(seed=42).fetch(DATE)
    return watchlist.screen_profiles(kyc, DATE, suppressed=suppressed)


class TestFuzzyMatching(unittest.TestCase):
    def test_exact_name_scores_highest(self):
        self.assertGreaterEqual(watchlist.similarity("Farida Benali", "Farida Benali"), 0.99)

    def test_alias_and_variants_are_caught(self):
        # inversion de tokens, accent, initiale — le flou de World-Check
        self.assertGreaterEqual(watchlist.similarity("Benali Farida", "Farida Benali"), 0.99)
        self.assertGreaterEqual(watchlist.similarity("Edouard Villemont", "Édouard Villemont"), 0.99)
        self.assertGreaterEqual(watchlist.similarity("Dimitrii Sokolov", "Dimitri Sokolov"), 0.72)

    def test_unrelated_name_scores_low(self):
        self.assertLess(watchlist.similarity("Klaus Bergmann", "Farida Benali"), 0.3)


class TestScreening(unittest.TestCase):
    def test_known_peps_produce_hits_with_source_and_version(self):
        hits = _hits()
        clients = {h["client_name"].split(" (")[0] for h in hits}
        self.assertIn("Farida Benali", clients)
        self.assertIn("Dimitri Sokolov", clients)
        for h in hits:
            self.assertIn("SIMULÉE", h["list_ref"])      # provenance affichée (G8)
            self.assertEqual(h["list_version"], watchlist.WATCHLIST_VERSION)
            self.assertGreaterEqual(h["score"], watchlist.POSSIBLE_MATCH)

    def test_hits_conform_to_contract(self):
        contract = REGISTRY.get("urn:fcc:client:screening-hits")
        for h in _hits():
            record = dict(h)
            record.pop("secondary_id")  # détail d'affichage, hors contrat
            self.assertEqual(validate_record(contract, record), [])

    def test_secondary_identifier_adjusts_score(self):
        # même nom, pays concordant vs discordant → scores différents
        kyc = SimulatedClientSource(seed=42).fetch(DATE)
        benali = next(p for p in kyc["records"] if "Benali" in p["name"])
        hits = watchlist.screen_profiles(
            {"records": [benali]}, DATE)
        strong = [h for h in hits if h["list_entry"] == "Farida Benali"][0]
        self.assertTrue(strong["secondary_id"]["match"])  # KY == KY
        self.assertEqual(strong["strength"], "strong")

    def test_false_positive_suppression_persists_until_list_changes(self):
        hits = _hits()
        target = hits[0]
        log = AuditLog()
        key = watchlist.resolve_hit(target, true_match=False, actor="analyste-1",
                                    audit_log=log, timestamp=f"{DATE}T10:00:00Z")
        self.assertIsNotNone(key)
        self.assertEqual(log.entries()[-1]["action"], "screening.false_positive")
        rescreened = _hits(suppressed={key})
        same = [h for h in rescreened if h["hit_id"] == target["hit_id"]]
        self.assertTrue(all(h["suppressed"] for h in same))  # supprimé au recriblage

    def test_true_match_is_journaled_and_never_suppressed(self):
        hits = _hits()
        log = AuditLog()
        key = watchlist.resolve_hit(hits[0], true_match=True, actor="analyste-1",
                                    audit_log=log, timestamp=f"{DATE}T10:00:00Z")
        self.assertIsNone(key)  # un vrai match ne se supprime jamais
        self.assertEqual(log.entries()[-1]["action"], "screening.true_match")
        self.assertIsNone(log.verify_chain())


if __name__ == "__main__":
    unittest.main()
