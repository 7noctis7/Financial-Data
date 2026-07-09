"""Abstraction d'ingestion : la frontière entre données simulées et réelles.

Chaque Data Product consomme des *batches* produits par une `DataSource`.
La provenance (`origin`) est une propriété du batch, propagée jusqu'aux
assertions d'audit et vérifiée à la publication réglementaire (règle G8).

Passage en production : implémenter une `DataSource` avec
`origin = PRODUCTION` (connecteur FIX, SWIFT, base comptable...) et la
brancher dans le pipeline à la place du simulateur. Rien d'autre ne
change, et un batch simulé ne peut jamais aboutir à un filing — le
blocage est dans le code, pas dans une convention.
"""

SIMULATED = "simulated"
PRODUCTION = "production"
ORIGINS = (SIMULATED, PRODUCTION)


def make_batch(product_urn, origin, produced_at, records):
    if origin not in ORIGINS:
        raise ValueError(f"origine inconnue : {origin!r} (attendu {ORIGINS})")
    return {
        "product_urn": product_urn,
        "origin": origin,
        "produced_at": produced_at,
        "records": records,
    }


class DataSource:
    """Interface d'une source alimentant un Data Product."""

    origin = None
    product_urn = None

    def fetch(self, business_date):
        """Retourne le batch du jour ouvré demandé (via `make_batch`)."""
        raise NotImplementedError
