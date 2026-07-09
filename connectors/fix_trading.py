"""Connecteur d'exemple : rapports d'exécution FIX → produit Trading.

Sous-ensemble de FIX 4.4 (ExecutionReport, MsgType 35=8) : le dialecte
du fournisseur reste ici, l'ontologie sort d'ici. Une salle réelle
brancherait le même connecteur sur sa gateway FIX en ne changeant que
`origin = PRODUCTION` (la provenance fait le reste — G8).
"""

from mesh.sources import SIMULATED

from .base import ExternalConnector, TranslationError

_STATUS = {"0": "pending", "2": "executed", "4": "cancelled", "B": "settled"}


class FixExecutionConnector(ExternalConnector):
    product_urn = "urn:fcc:trading:executed-trades"
    origin = SIMULATED  # une gateway réelle : origin = PRODUCTION

    def translate(self, message):
        if message.get("35") != "8":
            raise TranslationError(f"MsgType {message.get('35')!r} ≠ ExecutionReport")
        try:
            status = _STATUS[message["39"]]  # OrdStatus
            return {
                "trade_id": message["17"],                    # ExecID
                "instrument_id": message["48"],               # SecurityID (ISIN)
                "counterparty_lei": message["452"],           # PartyID (LEI)
                "notional": {
                    "amount": round(float(message["31"]) * float(message["32"]), 2),
                    "currency": message["15"],                # Currency
                },
                "status": status,
                "executed_at": message["60"],                 # TransactTime
            }
        except KeyError as exc:
            raise TranslationError(f"tag FIX manquant : {exc}") from exc
