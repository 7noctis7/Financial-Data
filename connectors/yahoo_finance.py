"""Connecteur Yahoo Finance : cours de clôture réels, gratuits, sans clé.

Alimente `urn:fcc:market:eod-prices` avec `origin=PRODUCTION` depuis
l'API chart publique (query1.finance.yahoo.com). Couche anti-corruption :
le JSON Yahoo ne franchit jamais la frontière du mesh — `_parse_chart`
le traduit vers l'entité `MarketPrice` de l'ontologie, et tout instrument
sans cotation Yahoo est simplement ABSENT du batch (jamais inventé) :
`derive_valuations` ne valorise que ce qui a un cours.

Couverture honnête du portefeuille de démonstration :
- actions (ISIN → ticker Yahoo) : cours de clôture réels ;
- change à terme : le SPOT Yahoo sert de proxy déclaré (`price_source`
  le dit) — sur un terme court, la variation quotidienne du spot domine
  celle des points de terme ;
- obligations souveraines et swaps de taux : non cotés sur Yahoo → hors
  batch, valorisation impossible tant qu'un fournisseur obligataire
  n'est pas branché.

Réseau : stdlib uniquement (urllib). Toute erreur (HTTP, format, date
absente) lève YahooError — l'appelant choisit son repli, le connecteur
ne dégrade jamais silencieusement.
"""

import json
import urllib.request

from mesh.sources import PRODUCTION, DataSource, make_batch

# ISIN / identifiant interne → (ticker Yahoo, devise attendue, nature du cours)
TICKERS = {
    "FR0000120271": ("AI.PA", "EUR", "close"),        # Air Liquide
    "NL0011794037": ("ASML.AS", "EUR", "close"),      # ASML Holding
    "US0378331005": ("AAPL", "USD", "close"),         # Apple
    "INT:FXF-EURUSD-3M": ("EURUSD=X", "USD", "spot-proxy"),
    "INT:FXF-EURGBP-1M": ("EURGBP=X", "GBP", "spot-proxy"),
}

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1mo&interval=1d"
USER_AGENT = "Mozilla/5.0 (FinancialCommandCenter/1.0)"


class YahooError(RuntimeError):
    """Réponse Yahoo inexploitable : le connecteur refuse, il ne devine pas."""


def _parse_chart(payload, business_date):
    """JSON chart Yahoo → (close, prev_close, devise) pour une date.

    Prend la clôture du dernier jour de cotation <= business_date et la
    clôture non nulle qui la précède. Fonction pure : testable hors ligne
    sur une fixture, sans réseau.
    """
    try:
        result = payload["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
        currency = result["meta"]["currency"]
    except (KeyError, IndexError, TypeError) as exc:
        raise YahooError(f"format chart inattendu : {exc!r}") from exc

    import datetime
    days = []  # [(date_iso, close)] cotations effectives, ordre chronologique
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        day = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).date().isoformat()
        days.append((day, round(float(close), 4)))
    eligible = [d for d in days if d[0] <= business_date]
    if len(eligible) < 2:
        raise YahooError(
            f"moins de deux cotations disponibles jusqu'au {business_date}")
    (_, prev_close), (close_date, close) = eligible[-2], eligible[-1]
    return close, prev_close, currency, close_date


class YahooFinanceSource(DataSource):
    """Source de production pour `market:eod-prices` (instruments couverts)."""

    origin = PRODUCTION
    product_urn = "urn:fcc:market:eod-prices"

    def __init__(self, tickers=None, timeout=10):
        self.tickers = tickers or TICKERS
        self.timeout = timeout

    def _get(self, ticker):
        request = urllib.request.Request(
            CHART_URL.format(ticker=ticker), headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # réseau, HTTP, JSON — même refus explicite
            raise YahooError(f"{ticker}: {exc}") from exc

    def fetch(self, business_date):
        records = []
        for instrument_id, (ticker, expected_ccy, nature) in sorted(self.tickers.items()):
            close, prev_close, currency, close_date = _parse_chart(
                self._get(ticker), business_date)
            if currency != expected_ccy:
                raise YahooError(
                    f"{ticker}: devise {currency!r} au lieu de {expected_ccy!r}")
            records.append({
                "instrument_id": instrument_id,
                "close": {"amount": close, "currency": currency},
                "prev_close": {"amount": prev_close, "currency": currency},
                "price_date": f"{close_date}T00:00:00Z",
                "price_source": ("YAHOO-FINANCE" if nature == "close"
                                 else "YAHOO-FINANCE (proxy spot pour un terme court)"),
            })
        return make_batch(self.product_urn, self.origin,
                          f"{business_date}T18:00:00Z", records)
