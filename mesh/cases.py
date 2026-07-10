"""Gestion de cas de conformité : revues KYC échues et alertes AML.

Un `Case` n'est jamais saisi : son existence et sa priorité sont DÉRIVÉES de
la donnée (une revue dont l'ancienneté dépasse le cycle, une alerte au-dessus
du seuil). Son état courant est le REPLI des transitions journalisées dans la
chaîne d'audit — le journal est la vérité, pas un champ mutable en base. Les
transitions sont validées par une machine à états ; escalade et classement
passent par la double validation (G11, `mesh/four_eyes.py`).

Politiques déclaratives (v1, révisables par la conformité) citées sous chaque
constante : cycle de revue, seuils de priorité, délais SLA.
"""

import datetime

# Cycle de revue périodique KYC : au-delà, la revue est échue et ouvre un cas.
# Réf. : obligation de mise à jour des données client (LBA art. 7 al. 1bis ;
# OBA-FINMA — revue périodique selon le risque). 365 j = cycle annuel v1.
KYC_REVIEW_CYCLE_DAYS = 365

# Délais SLA de traitement par priorité, en jours calendaires (politique
# interne LCB-FT v1 ; l'affinage en jours ouvrés est une évolution notée).
SLA_DAYS_BY_PRIORITY = {"high": 2, "medium": 7, "low": 30}

# Typologies AML de sévérité haute : leur seule présence porte le cas en
# priorité « high » quel que soit le score (PEP significatif, structuring).
HIGH_SEVERITY_TYPOLOGIES = {"T1-PEP-SIGNIFICATIF", "T3-FRACTIONNEMENT"}

OPEN, IN_REVIEW, ESCALATED, CLEARED = "open", "in_review", "escalated", "cleared"
TERMINAL_STATUSES = {ESCALATED, CLEARED}
# Transitions légales de la machine à états (l'assignation est orthogonale).
VALID_TRANSITIONS = {OPEN: {IN_REVIEW}, IN_REVIEW: {ESCALATED, CLEARED}}
# Décisions sensibles soumises à double validation (G11).
FOUR_EYES_TRANSITIONS = {ESCALATED, CLEARED}

CASE_URN = "urn:fcc:client:cases"


class CaseTransitionError(ValueError):
    """Transition d'état illégale au regard de la machine à états."""


def _date(iso):
    return datetime.date.fromisoformat(iso[:10])


def _iso(date):
    return f"{date.isoformat()}T00:00:00Z"


def _aml_priority(alert):
    """Priorité d'un cas d'alerte : score borné, relevé par une typologie
    de sévérité haute. Déclaratif, jamais tiré au sort."""
    if any(t["id"] in HIGH_SEVERITY_TYPOLOGIES for t in alert.get("typologies", [])):
        return "high"
    if alert["score"] >= 0.65:
        return "high"
    if alert["score"] >= 0.45:
        return "medium"
    return "low"


def _case(case_type, client_id, lei, priority, opened_on, source_ref, rationale):
    due = opened_on + datetime.timedelta(days=SLA_DAYS_BY_PRIORITY[priority])
    return {
        "case_id": None, "case_type": case_type,
        "subject_client_id": client_id, "subject_lei": lei,
        "status": OPEN, "priority": priority, "assignee": "",
        "opened_at": _iso(opened_on), "due_date": _iso(due),
        "source_ref": source_ref, "rationale": rationale,
    }


def derive_kyc_review_candidates(kyc_batch, business_date):
    """Cas ouverts par les revues KYC échues (ancienneté > cycle).

    `case_id` déterministe sur (client, date de revue lapsée) : rejouer la
    même journée ne duplique aucun cas (idempotence)."""
    as_of = _date(business_date)
    cases = []
    for profile in kyc_batch["records"]:
        last_review = _date(profile["last_review"])
        overdue_on = last_review + datetime.timedelta(days=KYC_REVIEW_CYCLE_DAYS)
        if overdue_on > as_of:
            continue  # revue encore dans le cycle
        age = (as_of - last_review).days
        case = _case("kyc_review", profile["client_id"], profile["lei"],
                     profile["risk_rating"], overdue_on,
                     source_ref=profile["last_review"],
                     rationale=(f"Revue KYC échue : dernière revue le "
                                f"{last_review.strftime('%d/%m/%Y')} "
                                f"({age} j > cycle {KYC_REVIEW_CYCLE_DAYS} j). "
                                f"Priorité = notation KYC ({profile['risk_rating']})."))
        case["case_id"] = f"CASE-KYC-{profile['client_id']}-{last_review.isoformat()}"
        cases.append(case)
    return cases


def derive_aml_candidates(alerts, business_date):
    """Cas ouverts par les alertes AML du jour (`case_id` = trade)."""
    opened_on = _date(business_date)
    cases = []
    for alert in alerts:
        priority = _aml_priority(alert)
        typ = ", ".join(t["id"] for t in alert.get("typologies", [])) or "aucune"
        case = _case("aml_alert", alert["client_id"], alert["lei"], priority,
                     opened_on, source_ref=alert["trade_id"],
                     rationale=(f"Alerte AML score {alert['score']} sur le trade "
                                f"{alert['trade_id']} ; typologies : {typ}. "
                                f"Priorité dérivée du score et des typologies."))
        case["case_id"] = f"CASE-AML-{alert['trade_id']}"
        cases.append(case)
    return cases


def next_status(current, action):
    """Statut cible d'une transition, ou lève si elle est illégale."""
    if action not in VALID_TRANSITIONS.get(current, set()):
        raise CaseTransitionError(
            f"transition illégale : {current!r} -> {action!r} "
            f"(autorisées depuis {current!r} : "
            f"{sorted(VALID_TRANSITIONS.get(current, set())) or 'aucune'})")
    return action


def fold_events(candidates, audit_entries):
    """État courant des cas = candidats + repli des transitions journalisées.

    Ne considère que les actions `case.*` ; ignore une transition portant sur
    un `case_id` inconnu (un cas fermé peut disparaître des candidats du jour
    suivant sans invalider l'historique)."""
    by_id = {c["case_id"]: dict(c) for c in candidates}
    for entry in audit_entries:
        action = entry.get("action", "")
        if not action.startswith("case."):
            continue
        case_id = entry.get("details", {}).get("case_id")
        case = by_id.get(case_id)
        if case is None:
            continue
        if action == "case.assigned":
            case["assignee"] = entry["details"].get("assignee", case["assignee"])
        elif action == "case.review_started" and case["status"] == OPEN:
            case["status"] = IN_REVIEW
        elif action == "case.escalated" and case["status"] == IN_REVIEW:
            case["status"] = ESCALATED
        elif action == "case.cleared" and case["status"] == IN_REVIEW:
            case["status"] = CLEARED
    return list(by_id.values())


def build_queue(cases, business_date, assignee=None, status=None,
                case_type=None, priority=None):
    """File filtrable + tri (retards puis priorité) + compteur SLA.

    Un cas est en retard si son échéance est dépassée et qu'il n'est pas
    clôturé. Le compteur de retards est un KRI, pas une alarme décorative."""
    as_of = _date(business_date)
    order = {"high": 0, "medium": 1, "low": 2}
    rows, overdue = [], 0
    for case in cases:
        if assignee is not None and case["assignee"] != assignee:
            continue
        if status is not None and case["status"] != status:
            continue
        if case_type is not None and case["case_type"] != case_type:
            continue
        if priority is not None and case["priority"] != priority:
            continue
        is_overdue = (case["status"] not in TERMINAL_STATUSES
                      and _date(case["due_date"]) < as_of)
        row = dict(case, overdue=is_overdue,
                   days_to_due=(_date(case["due_date"]) - as_of).days)
        rows.append(row)
        overdue += 1 if is_overdue else 0
    rows.sort(key=lambda r: (not r["overdue"], order.get(r["priority"], 9),
                             r["due_date"]))
    return {"business_date": business_date, "cases": rows,
            "total": len(rows), "overdue": overdue}
