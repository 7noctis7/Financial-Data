"""IA de réconciliation : suggestions de matching scorées, jamais d'écriture.

Principe (docs/architecture.md §4) : le modèle PROPOSE, l'humain DISPOSE.
- une suggestion est un score explicable (chaque composante visible) ;
- toute sortie passe par le lineage XAI (G6) : sources = produits Trading
  et Trésorerie du catalogue ;
- accepter ou rejeter une suggestion est un acte humain, journalisé dans
  la chaîne d'audit et versé à la base de feedback (mesh/feedback.py)
  qui ajuste les scores des prédictions futures.
"""

from difflib import SequenceMatcher


def unmatched(trades_batch, statements_batch):
    """Écarts de réconciliation : flux attendus sans relevé, et l'inverse."""
    expected = {f"STL-{t['trade_id']}": t for t in trades_batch["records"]
                if t["status"] == "settled"}
    statements = {s["reference"]: s for s in statements_batch["records"]}
    missing_statement = [t for ref, t in expected.items() if ref not in statements]
    unknown_statement = [s for ref, s in statements.items() if ref not in expected]
    return missing_statement, unknown_statement


def _score(trade, statement):
    """Score de matching [0..1], décomposé pour rester explicable (XAI)."""
    t_money, s_money = trade["notional"], statement["amount"]
    if t_money["currency"] != s_money["currency"]:
        return 0.0, {"currency_match": 0.0}
    t_amt, s_amt = abs(t_money["amount"]), abs(s_money["amount"])
    amount = max(0.0, 1.0 - abs(t_amt - s_amt) / max(t_amt, s_amt, 1.0))
    reference = SequenceMatcher(
        None, f"STL-{trade['trade_id']}", statement["reference"]).ratio()
    same_day = 1.0 if trade["executed_at"][:10] == statement["value_date"][:10] else 0.5
    features = {"currency_match": 1.0, "amount_proximity": round(amount, 4),
                "reference_similarity": round(reference, 4), "same_day": same_day}
    return round(0.6 * amount + 0.3 * reference + 0.1 * same_day, 4), features


def suggest(trades_batch, statements_batch, lineage, feedback=None,
            min_score=0.5, model="recon-matcher-v1"):
    """Suggestions de rapprochement pour les écarts, triées par score.

    Retourne une prédiction validée par `lineage.explain` (G6) — sans
    lineage résoluble, la fonction lève et rien n'est proposé.
    """
    missing, unknown = unmatched(trades_batch, statements_batch)
    suggestions = []
    for trade in missing:
        for statement in unknown:
            score, features = _score(trade, statement)
            if feedback is not None:
                score = feedback.adjust(score, features)
            if score >= min_score:
                suggestions.append({
                    "trade_id": trade["trade_id"],
                    "statement_reference": statement["reference"],
                    "score": round(score, 4),
                    "features": features,
                })
    suggestions.sort(key=lambda s: -s["score"])
    return lineage.explain({
        "model": model,
        "output": {"suggestions": suggestions,
                   "unmatched_trades": len(missing),
                   "unknown_statements": len(unknown)},
        "input_urns": ["urn:fcc:trading:executed-trades",
                       "urn:fcc:treasury:cash-positions"],
    })


def decide(suggestion, accepted, actor, audit_log, timestamp, feedback=None):
    """Décision HUMAINE sur une suggestion : journalisée puis apprise.

    C'est le seul chemin qui change l'état de réconciliation — le modèle
    n'écrit jamais lui-même.
    """
    audit_log.append(
        actor=actor,
        action="reconciliation." + ("accepted" if accepted else "rejected"),
        subject_urn="urn:fcc:treasury:cash-positions",
        details={"trade_id": suggestion["trade_id"],
                 "statement_reference": suggestion["statement_reference"],
                 "score": suggestion["score"]},
        timestamp=timestamp,
    )
    if feedback is not None:
        feedback.record(suggestion["features"], accepted, actor, timestamp)
