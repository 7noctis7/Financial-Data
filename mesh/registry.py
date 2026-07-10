"""Registre du mesh : découverte et validation des contrats de Data Products.

Applique les règles de gouvernance G1 (contrat valide obligatoire),
G2 (termes d'ontologie), G7 (classification d'accès) et vérifie que le
lineage déclaré (`sources`) pointe vers des produits du catalogue.
"""

import json
import re
from pathlib import Path

from . import schema

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_SCHEMA_PATH = Path(__file__).resolve().parent / "contracts" / "data-product.schema.json"
ONTOLOGY_PATH = REPO_ROOT / "docs" / "ontology.md"
DOMAINS_DIR = REPO_ROOT / "domains"


def load_ontology_terms(path=ONTOLOGY_PATH):
    """Extrait les termes du tableau « Entités » de l'ontologie.

    Le fichier markdown EST la source de vérité fédérée : un terme absent
    du tableau n'existe pas pour le registre.
    """
    terms = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*`([A-Za-z]+)`\s*\|", line)
        if m:
            terms.add(m.group(1))
    return terms


class ContractError(Exception):
    """Contrat invalide : le produit n'entre pas au catalogue (règle G1)."""

    def __init__(self, path, errors):
        self.path = path
        self.errors = errors
        super().__init__(f"{path}: {len(errors)} erreur(s) de contrat")


def validate_contract(contract, ontology_terms, contract_schema):
    errors = schema.validate(contract, contract_schema)
    if errors:
        return errors  # inutile d'aller plus loin sur un contrat mal formé

    output = contract["output_schema"]
    if output["entity"] not in ontology_terms:
        errors.append(f"entité {output['entity']!r} absente de l'ontologie (G2)")
    for field in output["fields"]:
        term = field.get("ontology_term")
        if term and term not in ontology_terms:
            errors.append(f"champ {field['name']!r}: terme {term!r} absent de l'ontologie (G2)")

    access = contract["access"]
    if access["classification"] == "restricted" and not access.get("roles"):
        errors.append("classification 'restricted' sans liste de rôles (G7)")

    urn_domain = contract["urn"].split(":")[2]
    if urn_domain != contract["domain"]:
        errors.append(f"URN dans le domaine {urn_domain!r} mais contrat déclaré {contract['domain']!r}")

    return errors


class Registry:
    """Catalogue des Data Products valides du mesh."""

    def __init__(self, domains_dir=DOMAINS_DIR, ontology_path=ONTOLOGY_PATH):
        self.contract_schema = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.ontology_terms = load_ontology_terms(ontology_path)
        self.products = {}
        self._load(Path(domains_dir))
        self._check_lineage()

    def _load(self, domains_dir):
        for path in sorted(domains_dir.glob("*/product*.json")):
            contract = json.loads(path.read_text(encoding="utf-8"))
            errors = validate_contract(contract, self.ontology_terms, self.contract_schema)
            if errors:
                raise ContractError(path, errors)
            self.products[contract["urn"]] = contract

    def _check_lineage(self):
        for contract in self.products.values():
            for source in contract["sources"]:
                if source not in self.products:
                    raise ContractError(
                        contract["urn"], [f"source de lineage inconnue au catalogue : {source}"]
                    )

    def get(self, urn):
        return self.products[urn]

    def catalog(self):
        """Vue de découverte : ce qu'un consommateur voit du mesh."""
        return [
            {
                "urn": c["urn"],
                "domain": c["domain"],
                "name": c["name"],
                "version": c["version"],
                "entity": c["output_schema"]["entity"],
                "classification": c["access"]["classification"],
                "freshness_slo_seconds": c["slo"]["freshness_seconds"],
                "sources": c["sources"],
            }
            for c in self.products.values()
        ]
