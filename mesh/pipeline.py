"""Pipeline d'un jour ouvré : source → dérivations → qualité → audit → G8.

La source est injectée : le simulateur aujourd'hui, un connecteur
`origin=production` demain — le pipeline ne fait pas la différence.
Les sorties vont dans `data/<date>/` (gitignoré) : la donnée simulée est
un artefact d'exécution, jamais un contenu du dépôt.
"""

import json
from pathlib import Path

from .accounting import derive_ledger
from .audit import CERTIFIED, QUALIFIED, AuditLog, make_assertion
from .circuit_breaker import CircuitBreaker
from .derivations import derive_cash_positions, derive_exposures
from .quality import validate_batch
from .regulatory import OriginError, generate_filing
from .registry import REPO_ROOT, Registry

DATA_DIR = REPO_ROOT / "data"


def _process_product(registry, log, batch):
    """Qualité + disjoncteur pour un batch ; retourne l'état du produit."""
    contract = registry.get(batch["product_urn"])
    valid, violations = validate_batch(contract, batch)
    breaker = CircuitBreaker(contract, audit_log=log)
    for i, record in enumerate(batch["records"]):
        breaker.record_publication(i, schema_valid=i not in {v[0] for v in violations})
    return {
        "batch": batch,
        "valid_records": len(valid),
        "violations": violations,
        "breaker_state": breaker.check(len(batch["records"])),
    }


def run_business_day(business_date, trading_source, statements_source,
                     out_dir=None, auditor="continuous-audit@fcc"):
    """Exécute la journée et retourne le résumé (également écrit sur disque)."""
    registry = Registry()
    log = AuditLog()
    out_dir = Path(out_dir) if out_dir else DATA_DIR / business_date
    out_dir.mkdir(parents=True, exist_ok=True)

    trades = trading_source.fetch(business_date)
    statements = statements_source(trades)
    cash = derive_cash_positions(trades, statements, business_date)
    exposures = derive_exposures(trades, business_date)
    ledger = derive_ledger(trades, statements, business_date)

    states = {b["product_urn"]: _process_product(registry, log, b)
              for b in (trades, cash, exposures, ledger)}

    assertions = {}
    for urn, state in states.items():
        batch = state["batch"]
        clean = not state["violations"] and state["breaker_state"] == "closed"
        if urn == "urn:fcc:treasury:cash-positions":
            clean = clean and all(r["reconciled"] for r in batch["records"])
        assertions[urn] = make_assertion(
            log, auditor, urn,
            scope=business_date,
            status=CERTIFIED if clean else QUALIFIED,
            evidence={
                "records": len(batch["records"]),
                "schema_violations": len(state["violations"]),
                "breaker_state": state["breaker_state"],
            },
            timestamp=f"{business_date}T19:00:00Z",
            origin=batch["origin"],
        )

    # Publication réglementaire : G8 doit refuser toute origine non-production.
    filings, refusals = [], []
    for urn, assertion in assertions.items():
        if assertion["status"] != CERTIFIED:
            continue
        rule_ref = f"RULE-DAILY-{urn.split(':')[2].upper()}"
        try:
            filings.append(generate_filing(rule_ref, assertion, f"{business_date}T20:00:00Z"))
        except OriginError as exc:
            refusals.append({"rule_ref": rule_ref, "reason": str(exc)})
            filings.append(generate_filing(rule_ref, assertion,
                                           f"{business_date}T20:00:00Z", dry_run=True))

    for name, batch in (("trades", trades), ("bank-statements", statements),
                        ("cash-positions", cash), ("exposures", exposures),
                        ("ledger", ledger)):
        (out_dir / f"{name}.json").write_text(
            json.dumps(batch, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "audit-journal.json").write_text(
        json.dumps(log.entries(), indent=2, ensure_ascii=False), encoding="utf-8")

    summary = {
        "business_date": business_date,
        "origin": trades["origin"],
        "products": {
            urn: {
                "records": len(state["batch"]["records"]),
                "schema_violations": len(state["violations"]),
                "breaker_state": state["breaker_state"],
                "assertion": assertions[urn]["status"],
            }
            for urn, state in states.items()
        },
        "reconciliation": {
            "accounts": len(cash["records"]),
            "unreconciled_accounts": sum(1 for r in cash["records"] if not r["reconciled"]),
        },
        "filings": filings,
        "g8_refusals": refusals,
        "audit_chain_intact": log.verify_chain() is None,
        "output_dir": str(out_dir),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary
