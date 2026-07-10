"""Produits dérivés : Trésorerie et Risque calculés depuis les trades.

Fonctions pures : elles ne savent pas si l'amont est simulé ou réel.
La provenance se propage — un dérivé est `simulated` dès qu'UN de ses
amonts l'est (`combine_origin`). C'est ce qui garantit qu'aucun reliquat
simulé ne peut se blanchir en traversant le mesh.
"""

from .sources import PRODUCTION, SIMULATED, make_batch

# Table de conversion figée pour la valorisation d'exposition (en réel :
# produit de données Marché ; hors périmètre v1).
FX_TO_EUR = {"EUR": 1.0, "USD": 0.92, "GBP": 1.17}

OPENING_BALANCES_EUR_ACCOUNTS = {
    "NOSTRO-EUR-001": ("EUR", 250_000_000.0),
    "NOSTRO-USD-001": ("USD", 180_000_000.0),
    "NOSTRO-GBP-001": ("GBP", 60_000_000.0),
}

COUNTERPARTY_LIMIT_EUR = 1_500_000_000.0


def combine_origin(*batches):
    return SIMULATED if any(b["origin"] == SIMULATED for b in batches) else PRODUCTION


def _account_for(currency):
    for account_id, (ccy, _) in OPENING_BALANCES_EUR_ACCOUNTS.items():
        if ccy == currency:
            return account_id
    raise ValueError(f"aucun compte nostro pour la devise {currency!r}")


def derive_cash_positions(trades_batch, statements_batch, business_date):
    """Réconciliation : flux attendus (trades réglés) vs relevés bancaires.

    Un compte est `reconciled` si chaque flux attendu a sa ligne de relevé
    (match par référence de règlement) et réciproquement. Le solde vient du
    relevé — la banque est la vérité du cash, pas le front-office.
    """
    expected = {f"STL-{t['trade_id']}": t for t in trades_batch["records"]
                if t["status"] == "settled"}
    statements = {s["reference"]: s for s in statements_batch["records"]}

    accounts = {aid: {"balance": opening, "currency": ccy, "matched": 0, "unmatched": 0}
                for aid, (ccy, opening) in OPENING_BALANCES_EUR_ACCOUNTS.items()}

    for ref, line in statements.items():
        account = accounts[_account_for(line["amount"]["currency"])]
        account["balance"] += line["amount"]["amount"]
        if ref in expected:
            account["matched"] += 1
        else:
            account["unmatched"] += 1
    for ref, trade in expected.items():
        if ref not in statements:
            accounts[_account_for(trade["notional"]["currency"])]["unmatched"] += 1

    records = [
        {
            "account_id": account_id,
            "balance": {"amount": round(state["balance"], 2), "currency": state["currency"]},
            "value_date": f"{business_date}T00:00:00Z",
            "reconciled": state["unmatched"] == 0,
            "settlement_ref": f"STL-BATCH-{business_date}",
        }
        for account_id, state in accounts.items()
    ]
    return make_batch(
        "urn:fcc:treasury:cash-positions",
        combine_origin(trades_batch, statements_batch),
        f"{business_date}T18:15:00Z",
        records,
    )


def derive_valuations(trades_batch, prices_batch, business_date):
    """Mark-to-market v1 : variation de valeur du jour par instrument.

    Méthode assumée et documentée dans le contrat : rendement du jour
    (close / prev_close − 1) appliqué au notionnel vivant (trades
    `executed`) de l'instrument, converti en EUR. Une valorisation full-
    reval (courbes, sensibilités) remplacera cette fonction sans toucher
    au contrat `urn:fcc:risk:valuations`.
    """
    prices = {p["instrument_id"]: p for p in prices_batch["records"]}
    live_notional = {}
    for trade in trades_batch["records"]:
        if trade["status"] != "executed":
            continue
        notional = trade["notional"]
        eur = notional["amount"] * FX_TO_EUR[notional["currency"]]
        live_notional[trade["instrument_id"]] = (
            live_notional.get(trade["instrument_id"], 0.0) + eur)

    records = []
    for instrument_id, position_eur in sorted(live_notional.items()):
        price = prices.get(instrument_id)
        if price is None:  # pas de cours → pas de valorisation, jamais d'invention
            continue
        daily_return = price["close"]["amount"] / price["prev_close"]["amount"] - 1.0
        records.append({
            "instrument_id": instrument_id,
            "position_notional": {"amount": round(position_eur, 2), "currency": "EUR"},
            "close": price["close"],
            "daily_return": round(daily_return, 6),
            "mtm_pnl": {"amount": round(position_eur * daily_return, 2),
                        "currency": "EUR"},
            "computed_at": f"{business_date}T18:45:00Z",
        })
    return make_batch(
        "urn:fcc:risk:valuations",
        combine_origin(trades_batch, prices_batch),
        f"{business_date}T18:45:00Z",
        records,
    )


def derive_exposures(trades_batch, business_date):
    """Exposition brute par contrepartie, valorisée en EUR.

    Méthode v1 assumée : somme des notionnels des trades vivants (ni
    réglés ni annulés). Une vraie mesure (netting, collatéral, add-ons)
    remplacera cette fonction sans toucher au contrat.
    """
    by_counterparty = {}
    for trade in trades_batch["records"]:
        if trade["status"] != "executed":
            continue
        notional = trade["notional"]
        eur = notional["amount"] * FX_TO_EUR[notional["currency"]]
        by_counterparty[trade["counterparty_lei"]] = (
            by_counterparty.get(trade["counterparty_lei"], 0.0) + eur
        )

    records = [
        {
            "counterparty_lei": lei,
            "exposure": {"amount": round(exposure, 2), "currency": "EUR"},
            "position_ref": f"POS-{lei[:6]}-{business_date}",
            "limit_utilisation": round(exposure / COUNTERPARTY_LIMIT_EUR, 4),
            "computed_at": f"{business_date}T18:30:00Z",
        }
        for lei, exposure in sorted(by_counterparty.items())
    ]
    return make_batch(
        "urn:fcc:risk:exposures",
        combine_origin(trades_batch),
        f"{business_date}T18:30:00Z",
        records,
    )
