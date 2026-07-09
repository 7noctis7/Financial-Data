"""CLI de la plateforme self-service.

    python3 -m mesh catalog    # catalogue des Data Products
    python3 -m mesh validate   # valide tous les contrats de domaines
"""

import json
import sys

from .registry import ContractError, Registry


def main(argv):
    command = argv[0] if argv else "catalog"
    try:
        registry = Registry()
    except ContractError as exc:
        print(f"CONTRAT INVALIDE — {exc.path}", file=sys.stderr)
        for error in exc.errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if command == "validate":
        print(f"OK — {len(registry.products)} contrats valides, "
              f"{len(registry.ontology_terms)} termes d'ontologie chargés")
        return 0
    if command == "catalog":
        print(json.dumps(registry.catalog(), indent=2, ensure_ascii=False))
        return 0
    print(f"commande inconnue : {command!r} (attendu : catalog | validate)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
