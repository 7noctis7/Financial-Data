"""Boucle de feedback : les corrections humaines calibrent les scores.

Version délibérément minimale d'un « RLHF » local : chaque décision
humaine (acceptée / rejetée) est stockée avec le vecteur de features de
la suggestion. Au moment de prédire, les k décisions les plus proches
(similarité cosinus) tirent le score vers leur taux d'acceptation
historique. Pas de réseau de neurones tant qu'un plus proche voisin
lisible suffit — quand un vrai modèle vectoriel s'imposera, seule cette
classe changera (même interface `adjust`/`record`).

Le store est un JSONL append-only sous data/ (gitignoré) : les
corrections sont des données d'exécution, auditables via le journal
(chaque `record` correspond à une entrée reconciliation.* chaînée).
"""

import json
import math
from pathlib import Path

FEATURE_ORDER = ("currency_match", "amount_proximity", "reference_similarity", "same_day")


def _vector(features, order):
    return [float(features.get(k, 0.0)) for k in order]


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class FeedbackStore:
    def __init__(self, path, feature_order=FEATURE_ORDER):
        self.path = Path(path)
        self.feature_order = feature_order
        self._entries = []
        if self.path.exists():
            with self.path.open(encoding="utf-8") as fh:
                self._entries = [json.loads(line) for line in fh if line.strip()]

    def __len__(self):
        return len(self._entries)

    def record(self, features, accepted, actor, timestamp):
        entry = {"features": features, "accepted": bool(accepted),
                 "actor": actor, "timestamp": timestamp}
        self._entries.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def adjust(self, score, features, k=5, weight=0.3, min_similarity=0.9):
        """Score ajusté par les k décisions humaines les plus similaires.

        `weight` borne l'influence du feedback : le signal métier
        (montant, référence) reste dominant, l'historique corrige.
        """
        if not self._entries:
            return score
        target = _vector(features, self.feature_order)
        neighbours = sorted(
            ((_cosine(target, _vector(e["features"], self.feature_order)), e)
             for e in self._entries),
            key=lambda pair: -pair[0],
        )[:k]
        relevant = [e for sim, e in neighbours if sim >= min_similarity]
        if not relevant:
            return score
        acceptance = sum(1 for e in relevant if e["accepted"]) / len(relevant)
        return round(min(1.0, max(0.0, score + weight * (acceptance - 0.5) * 2)), 4)
