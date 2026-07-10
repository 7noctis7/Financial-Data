"""Prépare le payload du dashboard depuis le pipeline du mesh.

Les agrégations vivent ici, côté plateforme : le front ne reçoit que des
séries prêtes à tracer. Même payload pour le serveur local et l'export
statique — c'est ce qui garantit que les deux vues sont identiques.
"""

from collections import Counter

from mesh.derivations import (FX_TO_EUR, derive_cash_positions, derive_exposures,
                              derive_valuations)
from mesh.pipeline import run_business_day
from mesh.registry import Registry
from sim.generator import (INSTRUMENTS, SimulatedMarketDataSource,
                           SimulatedTradingSource, demo_statements)

CLASS_LABELS = {
    "govt_bond": "Obligations souveraines",
    "equity": "Actions",
    "irs": "Swaps de taux",
    "fx_forward": "Change à terme",
}
CLASS_BY_INSTRUMENT = {ident: cls for ident, cls, _ccy, _median in INSTRUMENTS}
COUNTERPARTY_NAMES = {
    "R0MUWSFPU8MPRO8K5P83": "BNP Paribas",
    "F3JS33DEI6XQ4ZBPTN86": "Société Générale",
    "7LTWFZYICNSX8D621K86": "Deutsche Bank",
    "8I5DZWZKVSZI1NUHU748": "JPMorgan Chase",
    "G5GSEF7VJP5I7OUK5573": "Barclays",
    "549300ZK53CNGEEI6A29": "Nomura",
}


def _eur(money):
    return money["amount"] * FX_TO_EUR[money["currency"]]


def _market_source(seed):
    """FCC_MARKET=yahoo → cours réels (gratuits) ; défaut → simulés.

    Le choix est celui de l'utilisateur, jamais deviné — et l'origine
    (production/simulated) suit la source, donc G8 reste appliqué."""
    import os
    if os.environ.get("FCC_MARKET", "").lower() == "yahoo":
        from connectors.yahoo_finance import YahooFinanceSource
        return YahooFinanceSource(), ("Cours réels Yahoo Finance (actions + spot FX) ; "
                                      "obligations/IRS non cotés : hors valorisation.")
    return SimulatedMarketDataSource(seed=seed), None


def build_payload(business_date, seed=42, n_trades=250):
    source = SimulatedTradingSource(seed=seed, n_trades=n_trades)
    trades = source.fetch(business_date)
    statements = demo_statements(trades, seed=seed)
    cash = derive_cash_positions(trades, statements, business_date)
    exposures = derive_exposures(trades, business_date)
    market, market_note = _market_source(seed)
    try:
        prices = market.fetch(business_date)
    except Exception as exc:  # réseau/format : repli EXPLICITE, jamais silencieux
        market = SimulatedMarketDataSource(seed=seed)
        market_note = f"Yahoo Finance indisponible ({exc}) — repli sur cours simulés."
        prices = market.fetch(business_date)
    valuations = derive_valuations(trades, prices, business_date)

    class _Fetched:  # le pipeline revalide le batch déjà téléchargé (1 seul appel réseau)
        origin = prices["origin"]

        @staticmethod
        def fetch(_date):
            return prices

    summary = run_business_day(
        business_date, source, lambda t: demo_statements(t, seed=seed),
        market_source=_Fetched)

    by_hour = Counter(int(t["executed_at"][11:13]) for t in trades["records"])
    by_class = Counter()
    total_notional = 0.0
    for trade in trades["records"]:
        if trade["status"] == "cancelled":
            continue
        eur = _eur(trade["notional"])
        by_class[CLASS_BY_INSTRUMENT[trade["instrument_id"]]] += eur
        total_notional += eur

    return {
        "business_date": business_date,
        "origin": trades["origin"],
        "params": {"seed": seed, "n_trades": n_trades},
        "kpis": {
            "trades": len(trades["records"]),
            "notional_eur": round(total_notional, 2),
            "exposure_eur": round(sum(_eur(r["exposure"]) for r in exposures["records"]), 2),
            "accounts": len(cash["records"]),
            "reconciled_accounts": sum(1 for r in cash["records"] if r["reconciled"]),
            "audit_chain_intact": summary["audit_chain_intact"],
        },
        "trades_by_hour": [
            {"hour": f"{h:02d}h", "count": by_hour.get(h, 0)} for h in range(7, 18)
        ],
        "notional_by_class": sorted(
            ({"label": CLASS_LABELS[cls], "eur": round(v, 2)} for cls, v in by_class.items()),
            key=lambda x: -x["eur"]),
        "exposures": sorted(
            ({
                "counterparty": COUNTERPARTY_NAMES.get(r["counterparty_lei"],
                                                       r["counterparty_lei"]),
                "lei": r["counterparty_lei"],
                "eur": r["exposure"]["amount"],
                "limit_utilisation": r["limit_utilisation"],
            } for r in exposures["records"]),
            key=lambda x: -x["eur"]),
        "cash": cash["records"],
        "products": summary["products"],
        "filings": summary["filings"],
        "g8_refusals": summary["g8_refusals"],
        "recent_trades": trades["records"][-10:][::-1],
        "trades": trades["records"],  # détail complet pour les mini-fenêtres
        "instrument_classes": {i: CLASS_LABELS[c] for i, c in CLASS_BY_INSTRUMENT.items()},
        "counterparty_names": COUNTERPARTY_NAMES,
        "fx_to_eur": FX_TO_EUR,
        "valuations": [
            {
                "instrument_id": r["instrument_id"],
                "asset_class": CLASS_LABELS[CLASS_BY_INSTRUMENT[r["instrument_id"]]],
                "position_eur": r["position_notional"]["amount"],
                "close": r["close"],
                "daily_return": r["daily_return"],
                "mtm_eur": r["mtm_pnl"]["amount"],
                "price_source": r["price_source"],
            }
            for r in sorted(valuations["records"],
                            key=lambda r: -abs(r["mtm_pnl"]["amount"]))
        ],
        "market_origin": prices["origin"],
        "market_note": market_note,
        "mtm_total_eur": round(sum(r["mtm_pnl"]["amount"]
                                   for r in valuations["records"]), 2),
        "audit_anchor": summary.get("audit_head_hash"),
        "catalog": Registry().catalog(),
        "kris": _kris(summary, cash, exposures, trades, statements, business_date),
        "trend": _trend(business_date, seed, n_trades),
    }


def _trend(business_date, seed, n_trades):
    """Comparaison avec le jour ouvré précédent (même simulateur)."""
    import datetime
    day = datetime.date.fromisoformat(business_date) - datetime.timedelta(days=1)
    while day.weekday() >= 5:
        day -= datetime.timedelta(days=1)
    prev = SimulatedTradingSource(seed=seed, n_trades=n_trades).fetch(day.isoformat())
    notional = sum(t["notional"]["amount"] * FX_TO_EUR[t["notional"]["currency"]]
                   for t in prev["records"] if t["status"] != "cancelled")
    return {"date": day.isoformat(), "trades": len(prev["records"]),
            "notional_eur": round(notional, 2)}


def _kris(summary, cash, exposures, trades, statements, business_date):
    """Indicateurs de risque (SCI) — seuils de docs/audit-suisse.md §2."""
    from mesh.accounting import derive_ledger, trial_balance
    from mesh.fees import derive_fees
    ledger = derive_ledger(trades, statements, business_date,
                           fees_batch=derive_fees(trades, business_date))
    balance = trial_balance(ledger)
    max_util = max((r["limit_utilisation"] for r in exposures["records"]), default=0.0)
    return {
        "max_limit_utilisation": max_util,
        "unreconciled_accounts": sum(1 for r in cash["records"] if not r["reconciled"]),
        "schema_violations": sum(p["schema_violations"] for p in summary["products"].values()),
        "suspense_eur": round(sum(abs(v) for v in balance["suspense"].values()), 2),
        "balanced": balance["balanced"],
        "qualified_assertions": sum(1 for p in summary["products"].values()
                                    if p["assertion"] != "certified"),
    }
