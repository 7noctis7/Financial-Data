"""CLI de la plateforme self-service.

    python3 -m mesh catalog                       # catalogue des Data Products
    python3 -m mesh validate                      # valide tous les contrats
    python3 -m mesh simulate 2026-07-09 [seed] [n_trades]
                                                  # rejoue un jour ouvré simulé
    python3 -m mesh backfill 2026-06-01 2026-07-09 [seed] [n_trades]
                                                  # rejoue une plage (jours ouvrés)
"""

import json
import sys

from .registry import ContractError, Registry


def _simulate(argv):
    from sim.generator import (SimulatedMarketDataSource, SimulatedTradingSource,
                               simulate_bank_statements)

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
        market_source=SimulatedMarketDataSource(seed=seed),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _backfill(argv):
    import datetime

    from sim.generator import (SimulatedMarketDataSource, SimulatedTradingSource,
                               simulate_bank_statements)

    from .pipeline import run_business_day

    if len(argv) < 2:
        print("usage : python3 -m mesh backfill <début> <fin> [seed] [n_trades]",
              file=sys.stderr)
        return 2
    start = datetime.date.fromisoformat(argv[0])
    end = datetime.date.fromisoformat(argv[1])
    seed = int(argv[2]) if len(argv) > 2 else 42
    n_trades = int(argv[3]) if len(argv) > 3 else 250
    day, count = start, 0
    while day <= end:
        if day.weekday() < 5:  # jours ouvrés uniquement
            run_business_day(
                day.isoformat(),
                trading_source=SimulatedTradingSource(seed=seed, n_trades=n_trades),
                statements_source=lambda t: simulate_bank_statements(t, seed=seed),
                market_source=SimulatedMarketDataSource(seed=seed),
            )
            count += 1
        day += datetime.timedelta(days=1)
    print(f"{count} jours ouvrés simulés ({start} → {end})")
    return 0


def main(argv):
    command = argv[0] if argv else "catalog"
    if command == "simulate":
        return _simulate(argv[1:])
    if command == "backfill":
        return _backfill(argv[1:])
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
