"""Simulateur de flux bancaires réalistes pour le produit Trading.

Ordres de grandeur calibrés sur une salle de marchés de banque de taille
moyenne : mix obligations souveraines / actions / swaps de taux / change à
terme, notionnels log-normaux par classe d'actifs, contreparties
interbancaires identifiées par LEI, horaires de séance UTC.

Déterministe : (seed, business_date, n_trades) identiques → batch
identique. Aucune horloge interne — la date vient de l'appelant.

Ce module est le SEUL endroit du dépôt qui fabrique de la donnée. Il ne
produit que des batches `origin=SIMULATED` ; la gouvernance (G8) empêche
ces batches d'atteindre une publication réglementaire.
"""

import random

from mesh.sources import SIMULATED, DataSource, make_batch

# (identifiant, classe d'actifs, devise, notionnel médian)
INSTRUMENTS = [
    ("FR0014007L00", "govt_bond", "EUR", 10_000_000),
    ("DE0001102580", "govt_bond", "EUR", 10_000_000),
    ("US91282CJK15", "govt_bond", "USD", 8_000_000),
    ("FR0000120271", "equity", "EUR", 400_000),
    ("NL0011794037", "equity", "EUR", 350_000),
    ("US0378331005", "equity", "USD", 500_000),
    ("INT:IRS-EUR-5Y", "irs", "EUR", 25_000_000),
    ("INT:IRS-USD-10Y", "irs", "USD", 30_000_000),
    ("INT:FXF-EURUSD-3M", "fx_forward", "USD", 5_000_000),
    ("INT:FXF-EURGBP-1M", "fx_forward", "GBP", 3_000_000),
]

# Contreparties interbancaires (LEI au format réel, 20 caractères)
COUNTERPARTIES = [
    "R0MUWSFPU8MPRO8K5P83",  # BNP Paribas
    "F3JS33DEI6XQ4ZBPTN86",  # Société Générale
    "7LTWFZYICNSX8D621K86",  # Deutsche Bank
    "8I5DZWZKVSZI1NUHU748",  # JPMorgan Chase
    "G5GSEF7VJP5I7OUK5573",  # Barclays
    "549300ZK53CNGEEI6A29",  # Nomura (Europe)
]

# Cycle de vie intra-journée : la plupart des trades du jour sont exécutés,
# le règlement (T+2) ne dénoue le jour même que le change court.
STATUS_WEIGHTS = [("executed", 0.85), ("settled", 0.12), ("cancelled", 0.03)]

TRADING_OPEN_S = 7 * 3600          # 07:00 UTC
TRADING_CLOSE_S = 17 * 3600 + 1800  # 17:30 UTC


def _pick_status(rng):
    x = rng.random()
    cumulative = 0.0
    for status, weight in STATUS_WEIGHTS:
        cumulative += weight
        if x < cumulative:
            return status
    return STATUS_WEIGHTS[-1][0]


class SimulatedTradingSource(DataSource):
    origin = SIMULATED
    product_urn = "urn:fcc:trading:executed-trades"

    def __init__(self, seed=42, n_trades=250):
        self.seed = seed
        self.n_trades = n_trades

    def fetch(self, business_date):
        # La graine mêle seed et date : chaque jour ouvré diffère, mais
        # chaque rejeu du même jour est identique.
        rng = random.Random(f"{self.seed}:{business_date}")
        records = []
        for i in range(self.n_trades):
            instrument_id, _asset_class, currency, median = rng.choice(INSTRUMENTS)
            # Log-normale autour du notionnel médian de la classe d'actifs
            notional = round(median * rng.lognormvariate(0, 0.6), 2)
            second = rng.randint(TRADING_OPEN_S, TRADING_CLOSE_S)
            executed_at = (f"{business_date}T{second // 3600:02d}:"
                           f"{second % 3600 // 60:02d}:{second % 60:02d}Z")
            records.append({
                "trade_id": f"TRD-{business_date.replace('-', '')}-{i:05d}",
                "instrument_id": instrument_id,
                "counterparty_lei": rng.choice(COUNTERPARTIES),
                "notional": {"amount": notional, "currency": currency},
                "status": _pick_status(rng),
                "executed_at": executed_at,
            })
        records.sort(key=lambda r: r["executed_at"])
        return make_batch(self.product_urn, self.origin,
                          f"{business_date}T18:00:00Z", records)


# Cours de référence par instrument (ordre de grandeur réaliste : prix pied
# de coupon pour les obligations, cours action, taux/points pour dérivés).
REFERENCE_PRICES = {
    "FR0014007L00": 98.42,
    "DE0001102580": 101.15,
    "US91282CJK15": 96.88,
    "FR0000120271": 62.34,
    "NL0011794037": 741.20,
    "US0378331005": 227.48,
    "INT:IRS-EUR-5Y": 100.00,
    "INT:IRS-USD-10Y": 100.00,
    "INT:FXF-EURUSD-3M": 1.0872,
    "INT:FXF-EURGBP-1M": 0.8547,
}

# Volatilité journalière par classe d'actifs (écart-type du rendement log)
DAILY_VOL = {"govt_bond": 0.003, "equity": 0.015, "irs": 0.002, "fx_forward": 0.006}


def _prev_business_day(business_date):
    import datetime
    day = datetime.date.fromisoformat(business_date) - datetime.timedelta(days=1)
    while day.weekday() >= 5:
        day -= datetime.timedelta(days=1)
    return day.isoformat()


class SimulatedMarketDataSource(DataSource):
    """Prix de clôture simulés, déterministes par (seed, instrument, date).

    Chaque clôture est le cours de référence de l'instrument affecté d'un
    rendement log-normal tiré de la graine `seed:px:instrument:date` — le
    même jour rejoué donne le même prix, et `prev_close` est recalculé par
    la même formule sur le jour ouvré précédent : les deux champs sont
    cohérents entre eux et entre exécutions. En production, un connecteur
    fournisseur remplace cette classe sans toucher au contrat.
    """

    origin = SIMULATED
    product_urn = "urn:fcc:market:eod-prices"

    def __init__(self, seed=42):
        self.seed = seed

    def _close(self, instrument_id, asset_class, date):
        rng = random.Random(f"{self.seed}:px:{instrument_id}:{date}")
        factor = rng.lognormvariate(0, DAILY_VOL[asset_class])
        ref = REFERENCE_PRICES[instrument_id]
        return round(ref * factor, 4 if ref < 10 else 2)

    def fetch(self, business_date):
        prev_day = _prev_business_day(business_date)
        records = []
        for instrument_id, asset_class, currency, _median in INSTRUMENTS:
            records.append({
                "instrument_id": instrument_id,
                "close": {"amount": self._close(instrument_id, asset_class, business_date),
                          "currency": currency},
                "prev_close": {"amount": self._close(instrument_id, asset_class, prev_day),
                               "currency": currency},
                "price_date": f"{business_date}T17:30:00Z",
                "price_source": "SIMULATED-EOD",
            })
        return make_batch(self.product_urn, self.origin,
                          f"{business_date}T17:35:00Z", records)


COUNTERPARTY_NAMES = {
    "R0MUWSFPU8MPRO8K5P83": "BNP Paribas",
    "F3JS33DEI6XQ4ZBPTN86": "Société Générale",
    "7LTWFZYICNSX8D621K86": "Deutsche Bank",
    "8I5DZWZKVSZI1NUHU748": "JPMorgan Chase",
    "G5GSEF7VJP5I7OUK5573": "Barclays",
    "549300ZK53CNGEEI6A29": "Nomura",
}

# Pays de résidence possibles ; les derniers sont à vigilance renforcée
RESIDENCE_COUNTRIES = ["FR", "DE", "GB", "US", "JP", "CH", "LU", "KY", "PA"]
ENHANCED_DILIGENCE_COUNTRIES = {"KY", "PA"}


def kyc_rating(client_type, residence_country, pep):
    """Notation KYC dérivée de RÈGLES déclaratives — chaque notation est
    justifiable par ses facteurs, jamais tirée au sort.

    Règles (v1, à réviser par la conformité) :
    - PEP déclaré  OU  juridiction à vigilance renforcée  → high
    - établissement non bancaire (fonds, société de gestion, trade
      finance : surveillance prudentielle moindre)          → medium
    - banque régulée en juridiction standard                → low
    """
    factors = []
    if pep:
        factors.append("statut PEP déclaré à l'entrée en relation "
                       "(personne politiquement exposée — vigilance renforcée LBC-FT)")
    if residence_country in ENHANCED_DILIGENCE_COUNTRIES:
        factors.append(f"résidence {residence_country} : juridiction à vigilance "
                       "renforcée (liste interne alignée GAFI)")
    if pep or residence_country in ENHANCED_DILIGENCE_COUNTRIES:
        return "high", " ; ".join(factors)
    if client_type != "bank":
        factors.append("établissement non bancaire (fonds / société de gestion / "
                       "trade finance) : surveillance prudentielle moindre qu'une banque")
        return "medium", " ; ".join(factors)
    factors.append("banque régulée (surveillance prudentielle) en juridiction standard")
    return "low", " ; ".join(factors)


class SimulatedClientSource(DataSource):
    """Dossiers KYC simulés des contreparties (+ fonds sans activité).

    Seuls les ATTRIBUTS (résidence, PEP) sont simulés ; la notation est
    DÉRIVÉE par `kyc_rating` — règles déclaratives, jamais d'aléa.
    """

    origin = SIMULATED
    product_urn = "urn:fcc:client:kyc-profiles"

    EXTRA_CLIENTS = [
        ("549300H5DJ2KWQZM4V90", "Helvetia Capital SA", "asset-manager"),
        ("969500FX2K3AB8CD1E22", "Fonds Lumière SICAV", "fund"),
        ("529900T8BM49AURSDO55", "Nordwind Asset GmbH", "asset-manager"),
        ("213800ZBKL9BYSLXAB12", "Atlas Trade Finance Ltd", "trade-finance"),
    ]

    def __init__(self, seed=42):
        self.seed = seed

    def fetch(self, business_date):
        rng = random.Random(f"{self.seed}:kyc:{business_date[:7]}")  # stable au mois
        records = []
        clients = ([(lei, name, "bank") for lei, name in COUNTERPARTY_NAMES.items()]
                   + self.EXTRA_CLIENTS)
        for i, (lei, name, client_type) in enumerate(clients):
            pep = rng.random() < 0.10
            residence = rng.choice(RESIDENCE_COUNTRIES)
            rating, rationale = kyc_rating(client_type, residence, pep)
            review_days = rng.randint(10, 360)
            records.append({
                "client_id": f"CLI-{i:04d}",
                "lei": lei,
                "name": name,
                "risk_rating": rating,
                "rating_rationale": rationale,
                "pep": pep,
                "residence_country": residence,
                "last_review": f"{business_date[:4]}-01-01T00:00:00Z"
                               if review_days > 300 else f"{business_date}T00:00:00Z",
            })
        return make_batch(self.product_urn, self.origin,
                          f"{business_date}T06:00:00Z", records)


def simulate_bank_statements(trades_batch, seed=42, drop_rate=0.005, mutate_rate=0.0):
    """Relevés bancaires miroirs des trades réglés, imparfaits comme en vrai.

    ~0,5 % des flux manquent au relevé (retard de correspondant), et
    `mutate_rate` corrompt une fraction des références (troncature côté
    banque) : c'est ce qui donne au moteur de réconciliation — et à l'IA
    de matching — un vrai travail. En production, cette fonction est
    remplacée par le flux SWIFT/CAMT.053.
    """
    business_date = trades_batch["produced_at"][:10]
    rng = random.Random(f"{seed}:statements:{business_date}")
    records = []
    for trade in trades_batch["records"]:
        if trade["status"] != "settled" or rng.random() < drop_rate:
            continue
        reference = f"STL-{trade['trade_id']}"
        if rng.random() < mutate_rate:  # référence mutilée par la banque
            reference = reference.replace("STL-TRD-", "STL/TRD") + "/1"
        direction = 1 if rng.random() < 0.5 else -1
        records.append({
            "reference": reference,
            "amount": {
                "amount": round(direction * trade["notional"]["amount"], 2),
                "currency": trade["notional"]["currency"],
            },
            "value_date": f"{business_date}T00:00:00Z",
        })
    return make_batch("urn:fcc:treasury:cash-positions", SIMULATED,
                      f"{business_date}T17:45:00Z", records)
