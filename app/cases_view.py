"""Orchestration présentation des cas de conformité (file, décisions, SAR).

Le calcul vit dans le mesh (`mesh.cases`, `mesh.sar`, `mesh.aml`) ; ce module
assemble le payload de la page, applique les transitions journalisées et fait
respecter la double validation G11. Il reçoit ses dépendances (registre,
journal d'audit, registre 4-yeux) en paramètre : testable sans lever de serveur.
"""

from mesh import cases, sar
from mesh.aml import screen
from mesh.lineage import Lineage
from sim.generator import SimulatedClientSource, SimulatedTradingSource

_FILTER_KEYS = ("assignee", "status", "case_type", "priority")


def _context(registry, date, seed, n_trades, feedback=None):
    """Candidats du jour + index (profils, alertes) pour détail et SAR."""
    trades = SimulatedTradingSource(seed=seed, n_trades=n_trades).fetch(date)
    kyc = SimulatedClientSource(seed=seed).fetch(date)
    alerts = screen(trades, kyc, Lineage(registry),
                    feedback=feedback)["output"]["alerts"]
    candidates = (cases.derive_kyc_review_candidates(kyc, date)
                  + cases.derive_aml_candidates(alerts, date))
    profiles = {p["client_id"]: p for p in kyc["records"]}
    alerts_by_trade = {a["trade_id"]: a for a in alerts}
    return candidates, profiles, alerts_by_trade


def _folded(registry, audit_log, date, seed, n_trades, feedback=None):
    candidates, profiles, alerts_by_trade = _context(
        registry, date, seed, n_trades, feedback)
    folded = cases.fold_events(candidates, audit_log.entries())
    return folded, profiles, alerts_by_trade


def payload(registry, audit_log, date, seed=42, n_trades=250,
            feedback=None, filters=None):
    """Payload de la page file : queue filtrée, compteurs, liste d'assignés."""
    folded, _, _ = _folded(registry, audit_log, date, seed, n_trades, feedback)
    clean = {k: v for k, v in (filters or {}).items() if k in _FILTER_KEYS and v}
    queue = cases.build_queue(folded, date, **clean)
    return {
        "seed": seed,
        "assignees": sorted({c["assignee"] for c in folded if c["assignee"]}),
        "counts": {
            "kyc_review": sum(1 for c in folded if c["case_type"] == "kyc_review"),
            "aml_alert": sum(1 for c in folded if c["case_type"] == "aml_alert"),
        },
        "filters": clean,
        **queue,
    }


def _current(registry, audit_log, body, feedback=None):
    date, seed = body["date"], int(body.get("seed", 42))
    n_trades = int(body.get("n_trades", 250))
    folded, profiles, alerts_by_trade = _folded(
        registry, audit_log, date, seed, n_trades, feedback)
    by_id = {c["case_id"]: c for c in folded}
    case = by_id.get(body["case_id"])
    if case is None:
        raise KeyError(f"cas inconnu : {body['case_id']!r}")
    return case, profiles, alerts_by_trade


def decide(registry, audit_log, four_eyes, body, feedback=None):
    """Applique une transition : assign / review_started (acteur unique,
    journalisé) ou escalated / cleared (double validation G11)."""
    case, _, _ = _current(registry, audit_log, body, feedback)
    action = body["action"]
    actor, ts = body.get("actor", "webapp"), body.get("timestamp", "")
    cid = case["case_id"]
    if action == "assign":
        if case["status"] in cases.TERMINAL_STATUSES:
            raise ValueError(f"cas {case['status']} : assignation impossible")
        assignee = body["assignee"]
        audit_log.append(actor=actor, action="case.assigned", subject_urn=cases.CASE_URN,
                         details={"case_id": cid, "assignee": assignee}, timestamp=ts)
        return _ok(audit_log, cid, assignee=assignee)
    if action == "review_started":
        cases.next_status(case["status"], cases.IN_REVIEW)
        audit_log.append(actor=actor, action="case.review_started",
                         subject_urn=cases.CASE_URN,
                         details={"case_id": cid}, timestamp=ts)
        return _ok(audit_log, cid, status=cases.IN_REVIEW)
    if action in cases.FOUR_EYES_TRANSITIONS:
        cases.next_status(case["status"], action)  # légalité AVANT de proposer
        result = four_eyes.submit(cid, action, actor)
        if result["status"] == "pending":
            audit_log.append(actor=actor, action="case.proposed",
                             subject_urn=cases.CASE_URN,
                             details={"case_id": cid, "decision": action,
                                      "awaiting": "second-validator"}, timestamp=ts)
            return {"pending": True, "proposed_by": actor, "decision": action}
        audit_log.append(actor=actor, action=f"case.{action}",
                         subject_urn=cases.CASE_URN,
                         details={"case_id": cid, "validators": result["validators"]},
                         timestamp=ts)
        return _ok(audit_log, cid, status=action, validated_by=result["validators"])
    raise ValueError(f"action inconnue : {action!r}")


def _ok(audit_log, case_id, **extra):
    return {"ok": True, "case_id": case_id,
            "audit_chain_intact": audit_log.verify_chain() is None, **extra}


def sar_document(registry, audit_log, body, feedback=None):
    """SAR/MROS pré-remplie pour un cas, avec vérification des champs sourcés."""
    case, profiles, alerts_by_trade = _current(registry, audit_log, body, feedback)
    alert = (alerts_by_trade.get(case["source_ref"])
             if case["case_type"] == "aml_alert" else None)
    document = sar.build_sar(case, profiles[case["subject_client_id"]],
                             alert, body["date"])
    document["unsourced"] = sar.unsourced_fields(document)
    return document
