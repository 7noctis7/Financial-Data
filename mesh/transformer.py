"""DataTransformer : ingestion + mapping ontologique, audit trail natif.

Le point d'entrée unique pour faire entrer de la donnée tabulaire
(CSV/Excel exporté en CSV, dicts d'une API) dans un Data Product :

    transformer = DataTransformer(
        product_urn="urn:fcc:trading:executed-trades",
        mapping={
            "trade_id": "Deal Id",                       # renommage simple
            "instrument_id": "ISIN",
            "counterparty_lei": "LEI",
            "notional": {"amount": "Nominal", "currency": "Ccy"},  # money
            "status": lambda row: row["State"].lower(),  # transformation
            "executed_at": "Timestamp",
        },
        audit_log=log, actor="ops@fcc")
    batch, rejects = transformer.transform_rows(rows, origin, produced_at)

Garanties tenues ICI, donc valables pour toute source présente et future :
- chaque champ produit est un terme du contrat (validation quality.py) ;
- l'intraduisible est rejeté avec sa raison, jamais deviné ;
- la piste d'audit est injectée au niveau de la classe : chaque
  ingestion journalise acteur, horodatage, produit, volumes et
  SHA-256 de l'entrée — impossible d'ingérer sans tracer (G3) ;
- la couche de simulation s'injecte par `from_source(...)` : n'importe
  quelle `DataSource` (le générateur `sim/` — notre FactIQ — ou un
  connecteur de production) passe par le même chemin audité.
"""

import csv
import hashlib
import io
import json

from .quality import validate_record
from .registry import Registry
from .sources import make_batch


class MappingError(ValueError):
    """Ligne intraduisible : rejetée avec sa raison, jamais devinée."""


def _apply(spec, row):
    if callable(spec):
        return spec(row)
    if isinstance(spec, dict):  # composition money {amount, currency}
        try:
            return {"amount": float(row[spec["amount"]]), "currency": row[spec["currency"]]}
        except KeyError as exc:
            raise MappingError(f"colonne source manquante : {exc}") from exc
        except ValueError as exc:
            raise MappingError(f"montant non numérique : {row[spec['amount']]!r}") from exc
    if spec not in row:
        raise MappingError(f"colonne source manquante : {spec!r}")
    return row[spec]


class DataTransformer:
    def __init__(self, product_urn, mapping, audit_log, actor, registry=None):
        self.registry = registry or Registry()
        self.contract = self.registry.get(product_urn)
        self.product_urn = product_urn
        self.mapping = mapping
        self.audit_log = audit_log
        self.actor = actor

    def _record(self, row):
        record = {}
        for field, spec in self.mapping.items():
            try:
                record[field] = _apply(spec, row)
            except MappingError:
                raise
            except Exception as exc:  # une lambda de mapping qui casse = rejet
                raise MappingError(f"champ {field!r}: {exc}") from exc
        return record

    def transform_rows(self, rows, origin, produced_at, source_name="rows"):
        rows = list(rows)
        records, rejects = [], []
        for i, row in enumerate(rows):
            try:
                record = self._record(row)
            except MappingError as exc:
                rejects.append({"index": i, "reason": str(exc)})
                continue
            errors = validate_record(self.contract, record)
            if errors:
                rejects.append({"index": i, "reason": "; ".join(errors)})
            else:
                records.append(record)
        batch = make_batch(self.product_urn, origin, produced_at, records)
        # Piste d'audit injectée au niveau de la classe : User + Time + Hash.
        input_hash = hashlib.sha256(
            json.dumps(rows, sort_keys=True, ensure_ascii=False, default=str)
            .encode("utf-8")).hexdigest()
        self.audit_log.append(
            actor=self.actor, action="transform.ingested",
            subject_urn=self.product_urn,
            details={"source": source_name, "origin": origin,
                     "input_rows": len(rows), "accepted": len(records),
                     "rejected": len(rejects), "input_sha256": input_hash},
            timestamp=produced_at,
        )
        return batch, rejects

    def transform_csv(self, text_or_file, origin, produced_at, delimiter=";",
                      source_name="csv"):
        stream = io.StringIO(text_or_file) if isinstance(text_or_file, str) else text_or_file
        return self.transform_rows(csv.DictReader(stream, delimiter=delimiter),
                                   origin, produced_at, source_name=source_name)

    def from_source(self, source, business_date):
        """Couche de simulation / connecteur : même chemin, même audit.

        La `DataSource` (simulateur `sim/`, connecteur FIX...) produit déjà
        des records ontologiques : ici on re-valide et on re-trace — la
        confiance ne se propage pas, elle se vérifie à chaque frontière.
        """
        batch = source.fetch(business_date)
        identity = lambda field: (lambda row, f=field: row[f])  # noqa: E731
        passthrough = {f["name"]: identity(f["name"])
                       for f in self.contract["output_schema"]["fields"]}
        original_mapping, self.mapping = self.mapping, passthrough
        try:
            return self.transform_rows(batch["records"], batch["origin"],
                                       batch["produced_at"],
                                       source_name=type(source).__name__)
        finally:
            self.mapping = original_mapping
