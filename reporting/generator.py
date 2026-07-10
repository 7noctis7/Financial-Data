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


def run_controls(template, rows, context=None):
    """Contrôles de restitution déclaratifs (bloc `controls` du template).

    - recompute_total : une ligne de total doit être exactement la somme
      de ses lignes filles (règle de validation type EBA) ;
    - sum_equals : un agrégat du rapport doit égaler, au centime, une
      valeur de la source fournie via `context` (bouclage de périmètre).

    Retourne la liste des résultats — l'appelant décide de bloquer.
    """
    context = context or {}
    results = []
    for control in template.get("controls", []):
        key, amount = control["key"], control["amount_key"]
        by_key = {str(r[key]): float(r[amount]) for r in rows}
        if control["type"] == "recompute_total":
            actual = by_key.get(str(control["total"]))
            expected = round(sum(by_key.get(str(k), 0.0) for k in control["sum_of"]), 2)
        elif control["type"] == "sum_equals":
            actual = round(sum(by_key.get(str(k), 0.0) for k in control["keys"]), 2)
            expected = context.get(control["expected_context"])
        else:
            raise ReportError(f"type de contrôle inconnu : {control['type']!r}")
        ok = (actual is not None and expected is not None
              and abs(actual - float(expected)) <= 0.01)
        results.append({"control": control.get("name", control["type"]),
                        "ok": ok, "actual": actual, "expected": expected})
    return results


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
                 fmt="csv", timestamp=None, business_date=None,
                 control_context=None, summary_lines=None):
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

        # 2 bis. Contrôles de restitution : un écart bloque la livraison
        controls = run_controls(template, rows, control_context)
        failed = [c for c in controls if not c["ok"]]
        if failed:
            self.audit_log.append(
                actor=requester, action="report.control_failed",
                subject_urn=resource,
                details={"template": template_name, "failed": failed},
                timestamp=timestamp)
            raise ReportError(
                "contrôle de restitution en échec — " + " ; ".join(
                    f"{c['control']}: obtenu {c['actual']}, attendu {c['expected']}"
                    for c in failed))

        # 3. Annexe de Preuve
        origins = {assertions[c]["origin"] for c in template["required_assertions"]}
        content_hash = hashlib.sha256(json.dumps(
            {"columns": template["columns"], "rows": rows,
             "summary": summary_lines or []},
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
        ] + ([f"Controles de restitution : {len(controls)}/{len(controls)} OK"] + [
            f"  {c['control']} : {c['actual']} = {c['expected']} (au centime)"
            for c in controls
        ] if controls else [])

        content = RENDERERS[fmt](template["title"], template["columns"], rows, annex,
                                 summary_lines=summary_lines)
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
            "controls": controls,
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
        control_context, summary = None, []
        if dataset == "exposures":
            batch = derive_exposures(trades, business_date)
            rows = [{"counterparty_lei": r["counterparty_lei"],
                     "exposure_eur": r["exposure"]["amount"],
                     "limit_utilisation": r["limit_utilisation"],
                     "computed_at": _fr(r["computed_at"])} for r in batch["records"]]
            urn = "urn:fcc:risk:exposures"
            total = round(sum(r["exposure_eur"] for r in rows), 2)
            peak = max(rows, key=lambda r: r["limit_utilisation"], default=None)
            summary = [f"Synthese : {len(rows)} contreparties ; exposition brute "
                       f"totale {total:,.2f} EUR.".replace(",", " ")]
            if peak:
                summary.append(
                    f"Utilisation maximale de limite : {peak['limit_utilisation']:.1%} "
                    f"(LEI {peak['counterparty_lei']}).")
        elif dataset == "cash_positions":
            statements = simulate_bank_statements(trades, seed=seed)
            batch = derive_cash_positions(trades, statements, business_date)
            rows = [{"account_id": r["account_id"],
                     "balance": r["balance"]["amount"],
                     "currency": r["balance"]["currency"],
                     "reconciled": "oui" if r["reconciled"] else "non",
                     "value_date": _fr(r["value_date"])} for r in batch["records"]]
            urn = "urn:fcc:treasury:cash-positions"
            ok = sum(1 for r in rows if r["reconciled"] == "oui")
            summary = [f"Synthese : {len(rows)} comptes nostro ; {ok}/{len(rows)} "
                       "reconcilies trades vs releves bancaires."]
        elif dataset in ("derivative_trades", "transactions"):
            batch = trades
            keep = (lambda t: asset_class.get(t["instrument_id"]) in ("irs", "fx_forward")
                    ) if dataset == "derivative_trades" else (lambda t: True)
            rows = [_trade_row(t) for t in trades["records"]
                    if t["status"] != "cancelled" and keep(t)]
            urn = "urn:fcc:trading:executed-trades"
            by_ccy = {}
            for r in rows:
                by_ccy[r["currency"]] = by_ccy.get(r["currency"], 0.0) + r["notional"]
            summary = [f"Synthese : {len(rows)} transactions declarees ; notionnel par "
                       "devise : " + " ; ".join(
                           f"{v:,.0f} {c}".replace(",", " ")
                           for c, v in sorted(by_ccy.items())) + "."]
        elif dataset == "finrep_f0101":
            batch, rows, control_context = _finrep_f0101(
                trades, business_date, seed, template.get("lang", "fr"))
            urn = "urn:fcc:accounting:general-ledger"
            total = next(r["amount_eur"] for r in rows if r["row_ref"] == "380")
            summary = [f"Synthese : total actifs {total:,.2f} EUR ; bouclage "
                       "bilan/grand livre verifie au centime (voir annexe)."
                       .replace(",", " ")]
        elif dataset == "corep_c0700":
            from mesh.derivations import derive_exposures as _dx
            from sim.generator import COUNTERPARTY_NAMES
            batch = _dx(trades, business_date)
            urn = "urn:fcc:risk:exposures"
            rows, total_rwa = [], 0.0
            for i, r in enumerate(sorted(batch["records"],
                                         key=lambda x: -x["exposure"]["amount"])):
                # CRR SA v1 : etablissement bancaire regule => 20 %, sinon 100 %
                weight = 0.20 if r["counterparty_lei"] in COUNTERPARTY_NAMES else 1.00
                rwa = round(r["exposure"]["amount"] * weight, 2)
                total_rwa = round(total_rwa + rwa, 2)
                rows.append({"k": f"E{i}", "exposure_class":
                             COUNTERPARTY_NAMES.get(r["counterparty_lei"],
                                                    r["counterparty_lei"])
                             + " (etablissement)",
                             "exposure_eur": r["exposure"]["amount"],
                             "risk_weight": f"{weight:.0%}",
                             "rwa_eur": rwa,
                             "own_funds_req_eur": round(rwa * 0.08, 2)})
            rows.append({"k": "TOTAL", "exposure_class": "TOTAL",
                         "exposure_eur": round(sum(x["exposure_eur"] for x in rows), 2),
                         "risk_weight": "", "rwa_eur": total_rwa,
                         "own_funds_req_eur": round(total_rwa * 0.08, 2)})
            summary = [f"Synthese : RWA total {total_rwa:,.2f} EUR ; exigence de fonds".replace(",", " "),
                       f"propres (8 %) : {total_rwa * 0.08:,.2f} EUR. Ponderation v1 :".replace(",", " "),
                       "20 % etablissements bancaires reguels, 100 % autres (CRR art. 120-121)."]
        elif dataset == "finrep_f0103":
            ledger, balances = _ledger_balances_eur(trades, business_date, seed)
            batch = ledger
            urn = "urn:fcc:accounting:general-ledger"
            capital = round(-balances.get("5000", 0.0), 2)
            resultat = round(-balances.get("7000", 0.0), 2)
            rows = [
                {"row_ref": "010", "item": "Capital", "amount_eur": capital},
                {"row_ref": "250", "item": "Resultat de l'exercice en cours "
                 "(commissions percues, compte 7000)", "amount_eur": resultat},
                {"row_ref": "300", "item": "TOTAL CAPITAUX PROPRES",
                 "amount_eur": round(capital + resultat, 2)},
            ]
            control_context = {"ledger_equity_eur": round(capital + resultat, 2)}
            summary = [f"Synthese : capitaux propres {capital + resultat:,.2f} EUR".replace(",", " "),
                       f"dont resultat du jour {resultat:,.2f} EUR (commissions).".replace(",", " "),
                       "Bouclage F 01.03 = F 01.01 TOTAL ACTIFS, au centime."]
        elif dataset in ("balance_sheet_econ", "pnl_v1"):
            batch, rows, control_context, summary = _accounting_statement(
                trades, business_date, seed, dataset)
            urn = "urn:fcc:accounting:general-ledger"
        else:
            raise ReportError(f"dataset inconnu dans le template : {dataset!r}")
        assertions = demo_assertions(self.audit_log, urn, business_date, batch["origin"])
        return self.generate(template_name, rows, assertions, requester, role,
                             fmt=fmt, business_date=business_date,
                             control_context=control_context, summary_lines=summary)


# Libellés F 01.01 (Annexe III, Règlement d'exécution (UE) 2021/451)
_F0101_LABELS = {
    "fr": {
        "010": "Trésorerie, comptes à vue auprès de banques centrales et autres dépôts à vue",
        "040": "Autres dépôts à vue",
        "050": "Actifs financiers détenus à des fins de négociation",
        "060": "Dérivés",
        "080": "Titres de créance",
        "360": "Autres actifs",
        "380": "TOTAL ACTIFS",
    },
    "en": {
        "010": "Cash, cash balances at central banks and other demand deposits",
        "040": "Other demand deposits",
        "050": "Financial assets held for trading",
        "060": "Derivatives",
        "080": "Debt securities",
        "360": "Other assets",
        "380": "TOTAL ASSETS",
    },
}
_F0101_REFS = {"010": "IAS 1.54 (i)", "040": "Annexe V. Partie 2.3",
               "050": "IFRS 9. Annexe A", "060": "IFRS 9. Annexe A",
               "080": "Annexe V. Partie 1.31", "360": "Annexe V. Partie 2",
               "380": ""}


def _finrep_f0101(trades, business_date, seed, lang):
    """F 01.01 dérivé du grand livre — mapping v1 documenté dans
    docs/corep-finrep.md (nostro → 040 ; dérivés → 060 ; titres → 080 ;
    compte d'attente → 360). Cohérence EBA par construction :
    010 = 040, 050 = 060 + 080, 380 = 010 + 050 + 360."""
    from mesh.accounting import derive_ledger, trial_balance
    from mesh.derivations import FX_TO_EUR
    from sim.generator import simulate_bank_statements

    statements = simulate_bank_statements(trades, seed=seed)
    ledger = derive_ledger(trades, statements, business_date)
    balances = {}
    for account in trial_balance(ledger)["accounts"]:
        eur = account["balance"] * FX_TO_EUR[account["currency"]]
        balances[account["account_code"]] = balances.get(account["account_code"], 0.0) + eur

    demand_deposits = round(sum(balances.get(c, 0.0) for c in ("1010", "1011", "1012")), 2)
    derivatives = round(balances.get("3020", 0.0) + balances.get("3021", 0.0), 2)
    debt_securities = round(balances.get("3010", 0.0), 2)
    other_assets = round(balances.get("9990", 0.0), 2)
    held_for_trading = round(derivatives + debt_securities, 2)
    total = round(demand_deposits + held_for_trading + other_assets, 2)

    labels = _F0101_LABELS[lang]
    amounts = {"010": demand_deposits, "040": demand_deposits,
               "050": held_for_trading, "060": derivatives,
               "080": debt_securities, "360": other_assets, "380": total}
    rows = [{"row_ref": ref, "item": labels[ref], "reference": _F0101_REFS[ref],
             "amount_eur": amounts[ref]} for ref in
            ("010", "040", "050", "060", "080", "360", "380")]
    # Bouclage de périmètre : le total actif doit égaler, au centime, les
    # capitaux propres du grand livre (solde créditeur du compte 5000).
    control_context = {"ledger_equity_eur":
                       round(-balances.get("5000", 0.0) - balances.get("7000", 0.0), 2)}
    return ledger, rows, control_context


def _ledger_balances_eur(trades, business_date, seed):
    from mesh.accounting import derive_ledger, trial_balance
    from mesh.derivations import FX_TO_EUR
    from mesh.fees import derive_fees
    from sim.generator import simulate_bank_statements
    statements = simulate_bank_statements(trades, seed=seed)
    ledger = derive_ledger(trades, statements, business_date,
                           fees_batch=derive_fees(trades, business_date))
    balances = {}
    for account in trial_balance(ledger)["accounts"]:
        eur = account["balance"] * FX_TO_EUR[account["currency"]]
        balances[account["account_code"]] = balances.get(account["account_code"], 0.0) + eur
    return ledger, balances


def _accounting_statement(trades, business_date, seed, dataset):
    """Bilan économique / PnL v1 — chaque poste dérivé du grand livre,
    postes hors périmètre à zéro et déclarés (jamais estimés)."""
    ledger, balances = _ledger_balances_eur(trades, business_date, seed)
    disponible = round(sum(balances.get(c, 0.0) for c in ("1010", "1011", "1012")), 2)
    placements = round(balances.get("3010", 0.0) + balances.get("3020", 0.0)
                       + balances.get("3021", 0.0), 2)
    attente = round(balances.get("9990", 0.0), 2)
    fee_income = round(-balances.get("7000", 0.0), 2)
    equity = round(-balances.get("5000", 0.0) + fee_income, 2)
    if dataset == "balance_sheet_econ":
        endettement_net = round(0.0 - placements - disponible, 2)
        actif_eco = round(0.0 + attente, 2)  # immobilisations 0 + BFR HE
        rows = [
            {"k": "IMMO", "poste": "Immobilisations nettes (A)", "montant_eur": 0.0,
             "source": "hors perimetre v1 (aucun actif immobilise au grand livre)"},
            {"k": "BFRHE", "poste": "Besoin en fonds de roulement hors exploitation",
             "montant_eur": attente, "source": "solde 9990 Compte d'attente"},
            {"k": "ACTIF_ECO", "poste": "Actif economique (A+B)", "montant_eur": actif_eco,
             "source": "somme des lignes ci-dessus"},
            {"k": "CP", "poste": "Capitaux propres (C)", "montant_eur": equity,
             "source": "solde crediteur 5000"},
            {"k": "PLACEMENTS", "poste": "(-) Placements financiers",
             "montant_eur": -placements, "source": "soldes 3010+3020+3021"},
            {"k": "DISPO", "poste": "(-) Disponible", "montant_eur": -disponible,
             "source": "soldes nostro 1010/1011/1012"},
            {"k": "DETTE_NETTE", "poste": "Endettement net (D)",
             "montant_eur": endettement_net,
             "source": "dettes financieres (0) - placements - disponible"},
            {"k": "CAP_INV", "poste": "Capitaux investis (C+D) = Actif economique",
             "montant_eur": round(equity + endettement_net, 2),
             "source": "controle de bouclage"},
        ]
        context = {"actif_economique": actif_eco}
        summary = [
            f"Synthese : tresorerie disponible {disponible:,.2f} EUR ; placements "
            f"financiers {placements:,.2f} EUR ; capitaux propres {equity:,.2f} EUR."
            .replace(",", " "),
            "Controle : Capitaux investis (C+D) = Actif economique, au centime.",
        ]
        if attente:
            summary.append(f"Point d'attention : compte d'attente {attente:,.2f} EUR "
                           "a apurer (flux inexpliques).".replace(",", " "))
        return ledger, rows, context, summary
    # PnL v1 : seuls les flux reellement au grand livre — etat honnete,
    # avec comparatif N-1 (jour ouvre precedent, meme derivation).
    from sim.generator import SimulatedTradingSource, _prev_business_day
    prev_date = _prev_business_day(business_date)
    prev_trades = SimulatedTradingSource(seed=seed).fetch(prev_date)
    _, prev_balances = _ledger_balances_eur(prev_trades, prev_date, seed)
    prev_fee = round(-prev_balances.get("7000", 0.0), 2)
    delta = round(fee_income - prev_fee, 2)
    rows = [
        {"k": "CA", "poste": "CHIFFRE D'AFFAIRES (commissions percues)",
         "montant_eur": fee_income,
         "source": "solde crediteur 7000 - courtage derive des trades (bareme mesh/fees.py)"},
        {"k": "CA_N1", "poste": f"  rappel N-1 ({_fr(prev_date + 'T00:00:00Z')})",
         "montant_eur": prev_fee,
         "source": "meme derivation, jour ouvre precedent"},
        {"k": "CA_VAR", "poste": "  variation N / N-1",
         "montant_eur": delta,
         "source": (f"{delta / prev_fee:+.1%} vs jour ouvre precedent"
                    if prev_fee else "N-1 nul : variation non significative")},
        {"k": "CHARGES", "poste": "Charges d'exploitation", "montant_eur": 0.0,
         "source": "hors perimetre v1 (salaires, frais generaux non modelises)"},
        {"k": "EBE", "poste": "EXCEDENT BRUT D'EXPLOITATION",
         "montant_eur": fee_income, "source": "= CA - charges"},
    ]
    context = {"fee_income": fee_income}
    summary = [
        f"Synthese : commissions de courtage {fee_income:,.2f} EUR (bareme en points".replace(",", " "),
        "de base par classe d'instrument, derive de chaque trade non annule).",
        (f"Comparatif : {prev_fee:,.2f} EUR au jour ouvre precedent, variation "
         f"{delta:+,.2f} EUR.").replace(",", " "),
        "Charges d'exploitation hors perimetre v1 : EBE = CA.",
    ]
    return ledger, rows, context, summary


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
