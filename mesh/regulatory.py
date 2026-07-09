"""Publication réglementaire : le point où la provenance devient bloquante.

Règle G8 : un filing n'est généré que depuis une assertion `certified`
portant `origin=production`. Les données simulées peuvent traverser tout
le mesh (c'est voulu, pour tester la chaîne de bout en bout) mais ne
peuvent pas en sortir — sauf en mode `dry_run`, explicitement marqué et
jamais soumissible.
"""

from .audit import CERTIFIED
from .sources import PRODUCTION


class FilingError(ValueError):
    """Assertion inapte à couvrir un filing (invariant n°3)."""


class OriginError(FilingError):
    """Provenance non-production refusée à la publication (G8)."""


def generate_filing(rule_ref, assertion, timestamp, dry_run=False):
    if assertion["status"] != CERTIFIED:
        raise FilingError(
            f"assertion {assertion['status']!r} : un filing exige 'certified' (invariant n°3)"
        )
    if assertion["origin"] != PRODUCTION and not dry_run:
        raise OriginError(
            f"origine {assertion['origin']!r} refusée à la publication réglementaire (G8) ; "
            "utiliser dry_run=True pour une répétition explicitement marquée"
        )
    prefix = "DRYRUN" if (dry_run or assertion["origin"] != PRODUCTION) else "FIL"
    return {
        "filing_id": f"{prefix}-{rule_ref}-{timestamp[:10]}",
        "rule_ref": rule_ref,
        "assertion_proof_hash": assertion["proof_hash"],
        "submitted_at": timestamp,
        "dry_run": prefix == "DRYRUN",
    }
