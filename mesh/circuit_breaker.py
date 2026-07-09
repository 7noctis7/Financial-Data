"""Disjoncteur par Data Product : isole un domaine en dérive (règle G5).

Deux signaux, tous deux définis dans le contrat du produit :
- fraîcheur : dernière publication plus vieille que le SLO ;
- qualité : taux de violation de schéma sur fenêtre glissante.

Le temps est injecté par l'appelant (pas d'horloge interne) : le moteur
reste déterministe et testable, et fonctionne en rejeu historique.
"""

from collections import deque

CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half-open"

WINDOW = 100  # publications observées pour le taux de violation


class CircuitBreaker:
    def __init__(self, contract, audit_log=None):
        self.urn = contract["urn"]
        self.freshness_slo = contract["slo"]["freshness_seconds"]
        self.max_violation_rate = contract["slo"]["max_violation_rate"]
        self.cooldown = contract["slo"]["cooldown_seconds"]
        self.audit_log = audit_log
        self.state = CLOSED
        self.last_publication = None
        self.opened_at = None
        self._violations = deque(maxlen=WINDOW)

    def record_publication(self, timestamp, schema_valid):
        """Un événement publié par le domaine ; `schema_valid` vient du
        contrôle du payload contre le contrat."""
        self.last_publication = timestamp
        self._violations.append(0 if schema_valid else 1)
        self._evaluate(timestamp)

    def check(self, timestamp):
        """État consommable du produit à l'instant donné."""
        self._evaluate(timestamp)
        return self.state

    def is_consumable(self, timestamp):
        return self.check(timestamp) != OPEN

    def violation_rate(self):
        if not self._violations:
            return 0.0
        return sum(self._violations) / len(self._violations)

    def _evaluate(self, now):
        stale = (
            self.last_publication is not None
            and now - self.last_publication > self.freshness_slo
        )
        drifting = self.violation_rate() > self.max_violation_rate

        if self.state == CLOSED and (stale or drifting):
            self._open(now, stale=stale, drifting=drifting)
        elif self.state == OPEN and now - self.opened_at >= self.cooldown:
            self.state = HALF_OPEN
        elif self.state == HALF_OPEN:
            if stale or drifting:
                self._open(now, stale=stale, drifting=drifting)
            else:
                self.state = CLOSED
                self.opened_at = None

    def _open(self, now, stale, drifting):
        self.state = OPEN
        self.opened_at = now
        self._violations.clear()  # la fenêtre repart pour le réessai half-open
        if self.audit_log is not None:
            self.audit_log.append(
                actor="platform.circuit-breaker",
                action="circuit.open",
                subject_urn=self.urn,
                details={"stale": stale, "drifting": drifting},
                timestamp=now,
            )
