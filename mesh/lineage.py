"""Lineage et XAI : toute sortie IA doit être explicable par ses sources.

Règle G6 : une prédiction sans lien de preuve résoluble vers des Data
Products du catalogue est rejetée. Le graphe produit→produit vient des
champs `sources` des contrats ; il n'y a pas de seconde source de vérité.
"""


class LineageError(ValueError):
    """Sortie IA non explicable : rejetée par la gouvernance (G6)."""


class Lineage:
    def __init__(self, registry):
        self.registry = registry

    def upstream(self, urn):
        """Tous les produits amont (transitifs) d'un produit du catalogue."""
        seen = []
        stack = list(self.registry.get(urn)["sources"])
        while stack:
            current = stack.pop()
            if current not in seen:
                seen.append(current)
                stack.extend(self.registry.get(current)["sources"])
        return seen

    def explain(self, prediction):
        """Valide et enrichit une sortie IA avec sa preuve de lineage.

        `prediction` doit porter `model`, `output` et `input_urns`. Le
        résultat référence chaque source avec la version de contrat
        consommée : c'est le lien de preuve montré à l'utilisateur.
        """
        for key in ("model", "output", "input_urns"):
            if key not in prediction:
                raise LineageError(f"champ requis manquant : {key!r}")
        if not prediction["input_urns"]:
            raise LineageError("aucune source déclarée : prédiction inexplicable (G6)")

        proof = []
        for urn in prediction["input_urns"]:
            if urn not in self.registry.products:
                raise LineageError(f"source hors catalogue : {urn} (G6)")
            contract = self.registry.get(urn)
            proof.append(
                {
                    "urn": urn,
                    "domain": contract["domain"],
                    "contract_version": contract["version"],
                    "upstream": self.upstream(urn),
                }
            )
        return dict(prediction, lineage_proof=proof)
