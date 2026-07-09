"""Frais & Commissions : revenus dérivés des trades, barème versionné.

Le chiffre d'affaires de la banque de marché v1 = commissions de
courtage, calculées en points de base du notionnel par classe
d'instrument. Rien n'est saisi : changer le barème = changer BPS ici,
en PR. Les commissions s'enregistrent au compte 7000 du grand livre
(crédit = produit) et alimentent le CA du PnL.
"""

from .derivations import combine_origin
from .sources import make_batch

# points de base par famille d'instrument (barème v1)
BPS_IRS, BPS_FX, BPS_SECURITIES = 1.0, 1.0, 3.0


def _bps(instrument_id):
    if instrument_id.startswith("INT:IRS"):
        return BPS_IRS
    if instrument_id.startswith("INT:FXF"):
        return BPS_FX
    return BPS_SECURITIES


def derive_fees(trades_batch, business_date):
    """Une commission de courtage par trade non annulé."""
    records = []
    for trade in trades_batch["records"]:
        if trade["status"] == "cancelled":
            continue
        amount = round(trade["notional"]["amount"] * _bps(trade["instrument_id"]) / 10_000, 2)
        records.append({
            "fee_id": f"FEE-{trade['trade_id']}",
            "trade_id": trade["trade_id"],
            "fee_type": "brokerage",
            "amount": {"amount": amount, "currency": trade["notional"]["currency"]},
            "booked_at": trade["executed_at"],
        })
    return make_batch("urn:fcc:fees:revenues", combine_origin(trades_batch),
                      f"{business_date}T18:10:00Z", records)
