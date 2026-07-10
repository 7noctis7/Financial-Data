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
