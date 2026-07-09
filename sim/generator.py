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
RISK_RATINGS = [("low", 0.65), ("medium", 0.25), ("high", 0.10)]


class SimulatedClientSource(DataSource):
    """Dossiers KYC simulés des contreparties (+ fonds sans activité)."""

    origin = SIMULATED
    product_urn = "urn:fcc:client:kyc-profiles"

    EXTRA_CLIENTS = [
        ("549300H5DJ2KWQZM4V90", "Helvetia Capital SA"),
        ("969500FX2K3AB8CD1E22", "Fonds Lumière SICAV"),
        ("529900T8BM49AURSDO55", "Nordwind Asset GmbH"),
        ("213800ZBKL9BYSLXAB12", "Atlas Trade Finance Ltd"),
    ]

    def __init__(self, seed=42):
        self.seed = seed

    def fetch(self, business_date):
        rng = random.Random(f"{self.seed}:kyc:{business_date[:7]}")  # stable au mois
        records = []
        clients = list(COUNTERPARTY_NAMES.items()) + self.EXTRA_CLIENTS
        for i, (lei, name) in enumerate(clients):
            x, cumulative, rating = rng.random(), 0.0, "low"
            for r, w in RISK_RATINGS:
                cumulative += w
                if x < cumulative:
                    rating = r
                    break
            review_days = rng.randint(10, 360)
            records.append({
                "client_id": f"CLI-{i:04d}",
                "lei": lei,
                "name": name,
                "risk_rating": rating,
                "pep": rng.random() < 0.10,
                "residence_country": rng.choice(RESIDENCE_COUNTRIES),
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
