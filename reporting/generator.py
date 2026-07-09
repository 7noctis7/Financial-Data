"""ReportGenerator : livrables certifiés avec Annexe de Preuve obligatoire.

Contraintes tenues au niveau du générateur (pas dans les templates ni
les rendus, donc impossibles à contourner en ajoutant un format) :

1. Contrôle d'accès AVANT génération (G9, mesh/iam) — classification du
   template + liste de rôles ; un refus est journalisé, rien n'est rendu.
2. Assertions d'audit requises par le template (parmi les six :
   existence, exhaustivité, droits/obligations, évaluation, exactitude,
   présentation), toutes `certified` et vérifiables dans le journal.
3. Annexe de Preuve injectée dans le fichier ET en sidecar .proof.json :
   horodatage UTC, identité du demandeur, provenance des données,
   empreinte SHA-256 du contenu, référence de chaque preuve d'assertion.
4. La génération elle-même est une entrée du journal chaîné : le rapport
   est re-vérifiable après coup (hash du fichier ↔ journal).
"""

import datetime
import hashlib
import json
from pathlib import Path

from mesh import audit, iam
from mesh.registry import REPO_ROOT

from .renderers import RENDERERS

TEMPLATES_DIR = REPO_ROOT / "templates" / "reporting"
REPORTS_DIR = REPO_ROOT / "data" / "reports"

ASSERTION_CATEGORIES = ("existence", "completeness", "rights_obligations",
                        "valuation", "accuracy", "presentation")
CATEGORY_LABELS = {
    "existence": "Existence", "completeness": "Exhaustivité",
    "rights_obligations": "Droits et obligations", "valuation": "Évaluation",
    "accuracy": "Exactitude", "presentation": "Présentation",
}


class ReportError(ValueError):
    """Livrable refusé : assertion manquante, format inconnu, template absent."""


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _fr(iso):
    """Affichage JJ/MM/AAAA [HH:MM] — le stockage reste ISO 8601 UTC."""
    date = f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}"
    return date + (f" {iso[11:16]}" if len(iso) > 10 else "")


class ReportGenerator:
    def __init__(self, audit_log, templates_dir=TEMPLATES_DIR, reports_dir=REPORTS_DIR):
        self.audit_log = audit_log
        self.templates_dir = Path(templates_dir)
        self.reports_dir = Path(reports_dir)

    def _template(self, name):
        path = self.templates_dir / f"{name}.json"
        if not path.exists():
            available = sorted(p.stem for p in self.templates_dir.glob("*.json"))
            raise ReportError(f"template inconnu : {name!r} (disponibles : {available})")
        return json.loads(path.read_text(encoding="utf-8"))

    def generate(self, template_name, rows, assertions, requester, role,
                 fmt="csv", timestamp=None, business_date=None):
        """Génère le livrable ; retourne ses métadonnées de certification."""
        template = self._template(template_name)
        resource = f"urn:fcc:{template['department']}:report:{template_name}"
        timestamp = timestamp or _utc_now()

        # 1. Sécurité contextuelle — avant tout rendu (G9)
        iam.check_access(role, template["classification"], template.get("roles"),
                         audit_log=self.audit_log, actor=requester,
                         resource=resource, timestamp=timestamp)

        # 2. Certification : les assertions exigées, toutes certified + ancrées
        problems = []
        for category in template["required_assertions"]:
            assertion = assertions.get(category)
            if assertion is None:
                problems.append(f"{category} : assertion absente")
            elif assertion["status"] != audit.CERTIFIED:
                problems.append(f"{category} : statut {assertion['status']!r}")
            elif not audit.verify_assertion(self.audit_log, assertion):
                problems.append(f"{category} : preuve introuvable dans le journal")
        if problems:
            raise ReportError("certification incomplète — " + " ; ".join(problems))

        if fmt not in RENDERERS:
            raise ReportError(f"format inconnu : {fmt!r} (attendu {sorted(RENDERERS)})")

        # 3. Annexe de Preuve
        origins = {assertions[c]["origin"] for c in template["required_assertions"]}
        content_hash = hashlib.sha256(json.dumps(
            {"columns": template["columns"], "rows": rows},
            sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()
        annex = [
            f"Rapport : {template['name']} ({template['department']})",
        ] + ([f"Norme source : {template['norm_ref']}"] if template.get("norm_ref") else []) + [
            f"Genere le : {_fr(timestamp)} UTC ({timestamp})",
            f"Demandeur : {requester} (role : {role})",
            f"Provenance des donnees : {', '.join(sorted(origins))}",
            f"Empreinte SHA-256 du contenu : {content_hash}",
            "Assertions d'audit :",
        ] + [
            f"  {CATEGORY_LABELS[c]} : {assertions[c]['status']} — preuve "
            f"{assertions[c]['proof_hash']}"
            for c in template["required_assertions"]
        ]

        content = RENDERERS[fmt](template["title"], template["columns"], rows, annex)
        file_hash = hashlib.sha256(content).hexdigest()

        # 4. La génération entre dans la chaîne d'audit
        proof_hash = self.audit_log.append(
            actor=requester, action="report.generated", subject_urn=resource,
            details={"template": template_name, "format": fmt, "role": role,
                     "rows": len(rows), "content_hash": content_hash,
                     "file_hash": file_hash,
                     "assertions": {c: assertions[c]["proof_hash"]
                                    for c in template["required_assertions"]}},
            timestamp=timestamp,
        )

        stem = f"{template_name}-{(business_date or timestamp[:10])}"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        path = self.reports_dir / f"{stem}.{fmt}"
        path.write_bytes(content)
        metadata = {
            "path": str(path), "template": template_name, "format": fmt,
            "norm_ref": template.get("norm_ref"),
            "generated_at": timestamp, "requester": requester, "role": role,
            "origins": sorted(origins), "rows": len(rows),
            "content_hash": content_hash, "file_hash": file_hash,
            "audit_proof_hash": proof_hash,
        }
        (self.reports_dir / f"{stem}.{fmt}.proof.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        return metadata

    # ---------------- démo bout en bout (CLI + outil MCP) ----------------

    def demo(self, template_name, fmt, requester, role, business_date, seed=42):
        """Journée simulée → assertions certifiées → livrable certifié."""
        from mesh.derivations import derive_cash_positions, derive_exposures
        from sim.generator import (INSTRUMENTS, SimulatedTradingSource,
                                   simulate_bank_statements)

        template = self._template(template_name)
        trades = SimulatedTradingSource(seed=seed).fetch(business_date)
        asset_class = {ident: cls for ident, cls, _c, _m in INSTRUMENTS}

        def _trade_row(t):
            return {"trade_id": t["trade_id"], "instrument_id": t["instrument_id"],
                    "asset_class": asset_class.get(t["instrument_id"], "other"),
                    "counterparty_lei": t["counterparty_lei"],
                    "notional": t["notional"]["amount"],
                    "currency": t["notional"]["currency"],
                    "status": t["status"], "executed_at": _fr(t["executed_at"])}

        dataset = template["dataset"]
        if dataset == "exposures":
            batch = derive_exposures(trades, business_date)
            rows = [{"counterparty_lei": r["counterparty_lei"],
                     "exposure_eur": r["exposure"]["amount"],
                     "limit_utilisation": r["limit_utilisation"],
                     "computed_at": _fr(r["computed_at"])} for r in batch["records"]]
            urn = "urn:fcc:risk:exposures"
        elif dataset == "cash_positions":
            statements = simulate_bank_statements(trades, seed=seed)
            batch = derive_cash_positions(trades, statements, business_date)
            rows = [{"account_id": r["account_id"],
                     "balance": r["balance"]["amount"],
                     "currency": r["balance"]["currency"],
                     "reconciled": "oui" if r["reconciled"] else "non",
                     "value_date": _fr(r["value_date"])} for r in batch["records"]]
            urn = "urn:fcc:treasury:cash-positions"
        elif dataset == "derivative_trades":  # EMIR : IRS + change à terme
            batch = trades
            rows = [_trade_row(t) for t in trades["records"]
                    if asset_class.get(t["instrument_id"]) in ("irs", "fx_forward")
                    and t["status"] != "cancelled"]
            urn = "urn:fcc:trading:executed-trades"
        elif dataset == "transactions":  # MiFID II : toutes les exécutions
            batch = trades
            rows = [_trade_row(t) for t in trades["records"]
                    if t["status"] != "cancelled"]
            urn = "urn:fcc:trading:executed-trades"
        else:
            raise ReportError(f"dataset inconnu dans le template : {dataset!r}")
        assertions = demo_assertions(self.audit_log, urn, business_date, batch["origin"])
        return self.generate(template_name, rows, assertions, requester, role,
                             fmt=fmt, business_date=business_date)


def demo_assertions(log, product_urn, business_date, origin,
                    auditor="continuous-audit@fcc"):
    """Une assertion certifiée par catégorie, ancrée dans le journal."""
    return {
        category: audit.make_assertion(
            log, auditor, product_urn,
            scope=f"{business_date}:{category}", status=audit.CERTIFIED,
            evidence={"category": category, "method": "controle-automatique-v1"},
            timestamp=f"{business_date}T19:00:00Z", origin=origin)
        for category in ASSERTION_CATEGORIES
    }
