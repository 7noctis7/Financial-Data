"""CLI de la plateforme self-service.

    python3 -m mesh catalog                       # catalogue des Data Products
    python3 -m mesh validate                      # valide tous les contrats
    python3 -m mesh simulate 2026-07-09 [seed] [n_trades]
                                                  # rejoue un jour ouvré simulé
"""

import json
import sys

from .registry import ContractError, Registry


def _simulate(argv):
    from sim.generator import SimulatedTradingSource, simulate_bank_statements

    from .pipeline import run_business_day

    if not argv:
        print("usage : python3 -m mesh simulate <AAAA-MM-JJ> [seed] [n_trades]",
              file=sys.stderr)
        return 2
    business_date = argv[0]
    seed = int(argv[1]) if len(argv) > 1 else 42
    n_trades = int(argv[2]) if len(argv) > 2 else 250
    summary = run_business_day(
        business_date,
        trading_source=SimulatedTradingSource(seed=seed, n_trades=n_trades),
        statements_source=lambda trades: simulate_bank_statements(trades, seed=seed),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def main(argv):
    command = argv[0] if argv else "catalog"
    if command == "simulate":
        return _simulate(argv[1:])
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
    print(f"commande inconnue : {command!r} (attendu : catalog | validate | simulate)",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
