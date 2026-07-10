import json
import unittest

from mesh.audit import AuditLog
from reporting.generator import ReportGenerator

DATE = "2026-07-09"


class TestReportQuality(unittest.TestCase):
    def setUp(self):
        self.gen = ReportGenerator(audit_log=AuditLog())

    def _controls(self, name, role="regulatory-officer"):
        meta = self.gen.demo(name, "csv", requester="qa", role=role, business_date=DATE)
        return json.load(open(meta["path"] + ".proof.json"))["controls"]

    def test_finrep_balance_sheet_balances_across_statements(self):
        """Actif (F 01.01) = Capitaux propres (F 01.03) au centime.

        Invariant comptable : le bilan boucle. Avant correction, F 01.01
        dérivait un grand livre SANS commissions (actif 485,8 M€) tandis que
        F 01.03 les incluait (capitaux propres 486,19 M€) : écart de 388 k€
        (le résultat), et l'affirmation de bouclage publiée était fausse.
        Ce test crie si l'une des deux moitiés repart sur un grand livre
        incohérent avec l'autre — les contrôles par rapport ne le voient pas.
        """
        assets = [c for c in self._controls("finrep_f0101_fr")
                  if "380" in c["control"]][0]["actual"]
        equity = [c for c in self._controls("finrep_f0103_fr")
                  if c["control"].startswith("F0103: total")][0]["actual"]
        self.assertIsNotNone(assets)
        self.assertIsNotNone(equity)
        self.assertLessEqual(abs(assets - equity), 0.01,
                             f"bilan déséquilibré : actif {assets} ≠ passif {equity}")

    def test_all_restitution_controls_pass_on_accounting_reports(self):
        for name in ("finrep_f0101_fr", "finrep_f0101_en", "finrep_f0103_fr",
                     "bilan_economique"):
            role = "treasury-ops" if name == "bilan_economique" else "regulatory-officer"
            controls = self._controls(name, role)
            self.assertTrue(controls, f"{name} devrait porter des contrôles")
            for c in controls:
                self.assertTrue(c["ok"], f"{name} : contrôle en échec {c['control']}")


if __name__ == "__main__":
    unittest.main()


class TestYearOverYearComparison(unittest.TestCase):
    """N-1 = même date de l'EXERCICE précédent (01.01.N ↔ 01.01.N-1),
    jamais la veille — convention comptable exigée par l'utilisateur."""

    def test_same_day_previous_year_shifts_a_full_year(self):
        from sim.generator import same_day_previous_year
        self.assertEqual(same_day_previous_year("2026-07-09"), "2025-07-09")
        # 29 février -> 28 février de l'année précédente
        self.assertEqual(same_day_previous_year("2024-02-29"), "2023-02-28")
        # 12/07/2025 est un samedi -> replié au vendredi ouvré 11/07/2025
        self.assertEqual(same_day_previous_year("2026-07-12"), "2025-07-11")

    def test_pnl_report_compares_to_previous_year_not_previous_day(self):
        gen = ReportGenerator(audit_log=AuditLog())
        meta = gen.demo("pnl_v1", "csv", requester="qa", role="treasury-ops",
                        business_date=DATE)
        content = open(meta["path"], encoding="utf-8").read()
        self.assertIn("09/07/2025", content)       # même date exercice précédent
        self.assertNotIn("08/07/2026", content)    # PAS la veille

    def test_dashboard_comparison_is_year_shifted_and_recomputable(self):
        from app.data import build_comparison
        cmp_ = build_comparison("2026-07-01", "2026-07-09", 42, 250)
        self.assertEqual(cmp_["prev_period"], {"from": "2025-07-01", "to": "2025-07-09"})
        # variation recalculable au centime depuis les deux périodes
        for key in ("trades", "notional_eur", "fees_eur"):
            delta = round(cmp_["current"][key] - cmp_["previous"][key], 2)
            self.assertEqual(cmp_["variation"][key]["delta"], delta)

    def test_period_aggregates_business_days(self):
        from app.data import build_comparison
        single = build_comparison("2026-07-09", "2026-07-09", 42, 250)
        period = build_comparison("2026-07-06", "2026-07-09", 42, 250)  # lun→jeu
        self.assertGreater(period["current"]["trades"], single["current"]["trades"])
