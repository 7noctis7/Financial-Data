"""Comptabilité : grand livre en partie double dérivé, bouclage quotidien.

Principes (alignés Manuel suisse d'audit, docs/audit-suisse.md §3) :
- une écriture n'est JAMAIS saisie : elle est dérivée d'un règlement
  constaté (relevé bancaire = vérité du cash) ou d'un trade réglé ;
- partie double par construction : chaque événement produit exactement
  un débit et un crédit de même montant et même devise ;
- tout flux inexpliqué (règlement sans relevé, relevé orphelin) passe
  par le compte d'attente 9990 — il ne disparaît pas, il s'exhibe ;
- le contrôle de bouclage (`trial_balance`) vérifie débits = crédits
  par devise et expose le solde du compte d'attente : ce sont les deux
  premiers KRI d'un auditeur.
"""

from .derivations import OPENING_BALANCES_EUR_ACCOUNTS, combine_origin
from .sources import make_batch

NOSTRO_ACCOUNTS = {"EUR": ("1010", "Nostro EUR"), "USD": ("1011", "Nostro USD"),
                   "GBP": ("1012", "Nostro GBP")}
EQUITY = ("5000", "Capitaux propres")
FEE_INCOME = ("7000", "Commissions perçues")
SUSPENSE = ("9990", "Compte d'attente")


def _asset_account(instrument_id):
    if instrument_id.startswith("INT:IRS"):
        return ("3020", "Dérivés de taux")
    if instrument_id.startswith("INT:FXF"):
        return ("3021", "Change à terme")
    return ("3010", "Titres")


def derive_ledger(trades_batch, statements_batch, business_date, fees_batch=None):
    """Écritures du jour : trades réglés ↔ relevés, en partie double."""
    statements = {s["reference"]: s for s in statements_batch["records"]}
    matched_refs = set()
    entries, n = [], 0

    def book(debit, credit, amount, currency, reference):
        nonlocal n
        for side, (code, label) in (("debit", debit), ("credit", credit)):
            entries.append({
                "entry_id": f"JE-{business_date.replace('-', '')}-{n:05d}",
                "reference": reference,
                "account_code": code,
                "account_label": label,
                "side": side,
                "amount": {"amount": round(amount, 2), "currency": currency},
                "booked_at": f"{business_date}T18:45:00Z",
            })
        n += 1

    # Soldes d'ouverture : les nostros existent avant les flux du jour —
    # contrepartie en capitaux propres (sinon un bilan de flux net à zéro).
    for _account_id, (currency, opening) in OPENING_BALANCES_EUR_ACCOUNTS.items():
        book(NOSTRO_ACCOUNTS[currency], EQUITY, opening, currency, "OPENING")

    for trade in trades_batch["records"]:
        if trade["status"] != "settled":
            continue
        reference = f"STL-{trade['trade_id']}"
        currency = trade["notional"]["currency"]
        asset = _asset_account(trade["instrument_id"])
        statement = statements.get(reference)
        if statement is not None:
            matched_refs.add(reference)
            cash = statement["amount"]["amount"]
            cash_ccy = statement["amount"]["currency"]  # la banque fait foi
            nostro = NOSTRO_ACCOUNTS[cash_ccy]
            if cash >= 0:  # encaissement : débit nostro / crédit titres
                book(nostro, asset, cash, cash_ccy, reference)
            else:          # décaissement : débit titres / crédit nostro
                book(asset, nostro, -cash, cash_ccy, reference)
        else:
            # règlement sans cash constaté → attente (signal d'audit)
            book(SUSPENSE, asset, trade["notional"]["amount"], currency, reference)

    for fee in (fees_batch["records"] if fees_batch else []):
        currency = fee["amount"]["currency"]
        # encaissement de la commission : débit nostro / crédit produits
        book(NOSTRO_ACCOUNTS[currency], FEE_INCOME, fee["amount"]["amount"],
             currency, fee["fee_id"])

    for reference, statement in statements.items():
        if reference in matched_refs:
            continue
        # cash constaté sans trade connu (référence mutilée...) → attente
        cash = statement["amount"]["amount"]
        currency = statement["amount"]["currency"]
        nostro = NOSTRO_ACCOUNTS[currency]
        if cash >= 0:
            book(nostro, SUSPENSE, cash, currency, reference)
        else:
            book(SUSPENSE, nostro, -cash, currency, reference)

    return make_batch("urn:fcc:accounting:general-ledger",
                      combine_origin(trades_batch, statements_batch),
                      f"{business_date}T18:45:00Z", entries)


def trial_balance(ledger_batch):
    """Balance générale + contrôle de bouclage (débits = crédits par devise)."""
    accounts = {}
    totals = {}
    for entry in ledger_batch["records"]:
        currency = entry["amount"]["currency"]
        key = (entry["account_code"], currency)
        account = accounts.setdefault(key, {
            "account_code": entry["account_code"],
            "account_label": entry["account_label"],
            "currency": currency, "debit": 0.0, "credit": 0.0,
        })
        account[entry["side"]] += entry["amount"]["amount"]
        side_totals = totals.setdefault(currency, {"debit": 0.0, "credit": 0.0})
        side_totals[entry["side"]] += entry["amount"]["amount"]

    rows = []
    for account in accounts.values():
        account["debit"] = round(account["debit"], 2)
        account["credit"] = round(account["credit"], 2)
        account["balance"] = round(account["debit"] - account["credit"], 2)
        rows.append(account)
    rows.sort(key=lambda a: (a["account_code"], a["currency"]))

    balanced_by_currency = {
        ccy: round(t["debit"] - t["credit"], 2) == 0.0 for ccy, t in totals.items()
    }
    suspense = {r["currency"]: r["balance"] for r in rows
                if r["account_code"] == SUSPENSE[0] and r["balance"] != 0.0}
    return {
        "accounts": rows,
        "entries": len(ledger_batch["records"]),
        "balanced_by_currency": balanced_by_currency,
        "balanced": all(balanced_by_currency.values()) if balanced_by_currency else True,
        "suspense": suspense,
    }


def pnl_summary(balance):
    """Compte de résultat condensé dérivé de la balance (SIG v1).

    Produit = commissions perçues (compte 7000, solde créditeur), converties
    EUR. Charges d'exploitation hors périmètre v1 (salaires, frais généraux
    non modélisés) → EBE = résultat = CA. Aucun chiffre inventé."""
    from .derivations import FX_TO_EUR
    revenue = round(sum(-a["balance"] * FX_TO_EUR[a["currency"]]
                        for a in balance["accounts"]
                        if a["account_code"] == FEE_INCOME[0]), 2)
    return {
        "chiffre_affaires": revenue,
        "charges_exploitation": 0.0,
        "excedent_brut": revenue,
        "resultat_net": revenue,
        "note": "produits = commissions (7000) ; charges hors périmètre v1 → EBE = CA",
    }


def off_balance_sheet(trades_batch):
    """Engagements HORS BILAN : notionnels des dérivés vivants (IRS, change à
    terme). Un notionnel est un engagement de référence, PAS une valeur au
    bilan — jamais confondu avec une valorisation (honnêteté épistémique)."""
    from .derivations import FX_TO_EUR
    by_class = {}
    for trade in trades_batch["records"]:
        if trade["status"] == "cancelled":
            continue
        iid = trade["instrument_id"]
        if iid.startswith("INT:IRS"):
            label = "Swaps de taux (IRS)"
        elif iid.startswith("INT:FXF"):
            label = "Change à terme (FX forward)"
        else:
            continue
        eur = trade["notional"]["amount"] * FX_TO_EUR[trade["notional"]["currency"]]
        by_class[label] = by_class.get(label, 0.0) + eur
    lines = [{"engagement": k, "notionnel_eur": round(v, 2)}
             for k, v in sorted(by_class.items())]
    return {
        "lines": lines,
        "total_notionnel_eur": round(sum(by_class.values()), 2),
        "note": "notionnel de référence (engagement) — non valorisé au bilan",
    }
