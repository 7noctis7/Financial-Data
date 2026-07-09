"""Pattern connecteur : le pont entre un flux externe et l'ontologie.

Un connecteur est une **couche anti-corruption** : le format du
fournisseur (Bloomberg, core banking, SWIFT...) ne franchit jamais la
frontière du mesh. Le connecteur traduit chaque message vers les termes
de l'ontologie, valide le résultat contre le contrat du produit cible
(mesh/quality.py) et publie un batch porteur de provenance.

Ajouter une source = écrire UNE sous-classe (translate + origin), sans
toucher au cœur du Data Product — c'est la contrainte de flexibilité.
Les messages intraduisibles partent en rejet explicite : un connecteur
ne devine jamais, il refuse.
"""

from mesh.quality import validate_record
from mesh.registry import Registry
from mesh.sources import make_batch


class TranslationError(ValueError):
    """Message externe intraduisible vers l'ontologie : rejeté, tracé."""


class ExternalConnector:
    """Sous-classer : définir product_urn, origin et translate()."""

    product_urn = None   # produit du catalogue alimenté par ce connecteur
    origin = None        # mesh.sources.SIMULATED ou PRODUCTION

    def __init__(self, registry=None):
        self.registry = registry or Registry()
        self.contract = self.registry.get(self.product_urn)

    def translate(self, message):
        """Un message externe → un record aux termes de l'ontologie."""
        raise NotImplementedError

    def ingest(self, messages, produced_at):
        """Traduit, valide contre le contrat, publie ; retourne (batch, rejets).

        Les rejets contiennent la raison — c'est l'entrée du signal de
        dérive du disjoncteur ET la matière du support de niveau 1.
        """
        records, rejects = [], []
        for i, message in enumerate(messages):
            try:
                record = self.translate(message)
            except TranslationError as exc:
                rejects.append({"index": i, "reason": str(exc)})
                continue
            errors = validate_record(self.contract, record)
            if errors:
                rejects.append({"index": i, "reason": "; ".join(errors)})
            else:
                records.append(record)
        batch = make_batch(self.product_urn, self.origin, produced_at, records)
        return batch, rejects
