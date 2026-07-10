"""Pré-diagnostic AML : criblage LCB-FT des trades contre les dossiers KYC.

Même philosophie que la réconciliation : le modèle PROPOSE un score
explicable (chaque composante visible), l'humain DISPOSE — escalade ou
classement sans suite, journalisé dans la chaîne d'audit et versé au
feedback. Une alerte n'est jamais une accusation : c'est une priorité
de revue.
"""

from .aml_typologies import match_typologies
from .derivations import FX_TO_EUR

HIGH_RISK_COUNTRIES = {"KY", "PA", "VG", "IR", "KP"}
LARGE_AMOUNT_EUR = 25_000_000.0   # seuil de vigilance sur un trade unitaire
VELOCITY_WINDOW = 10              # trades même contrepartie / même heure

AML_FEATURES = ("pep", "high_risk_country", "risk_rating", "large_amount", "velocity")


def _velocity(trades):
    """Nombre de trades par (contrepartie, heure) — motif de fractionnement."""
    counts = {}
    for t in trades:
        key = (t["counterparty_lei"], t["executed_at"][:13])
        counts[key] = counts.get(key, 0) + 1
    return counts


def screen(trades_batch, kyc_batch, lineage, feedback=None,
           min_score=0.35, max_alerts=40, model="aml-screen-v1"):
    """Alertes scorées sur l'activité du jour, enveloppées de lineage (G6)."""
    profiles = {p["lei"]: p for p in kyc_batch["records"]}
    live = [t for t in trades_batch["records"] if t["status"] != "cancelled"]
    velocity = _velocity(live)
    alerts = []
    for t in live:
        profile = profiles.get(t["counterparty_lei"])
        if profile is None:
            continue
        eur = t["notional"]["amount"] * FX_TO_EUR[t["notional"]["currency"]]
        features = {
            "pep": 1.0 if profile["pep"] else 0.0,
            "high_risk_country": 1.0 if profile["residence_country"] in HIGH_RISK_COUNTRIES else 0.0,
            "risk_rating": {"low": 0.0, "medium": 0.5, "high": 1.0}[profile["risk_rating"]],
            "large_amount": round(min(1.0, eur / (2 * LARGE_AMOUNT_EUR)), 4),
            "velocity": round(min(1.0, velocity[(t["counterparty_lei"], t["executed_at"][:13])]
                                  / VELOCITY_WINDOW), 4),
        }
        score = round(0.30 * features["pep"] + 0.20 * features["high_risk_country"]
                      + 0.15 * features["risk_rating"] + 0.25 * features["large_amount"]
                      + 0.10 * features["velocity"], 4)
        if feedback is not None:
            score = feedback.adjust(score, features)
        if score >= min_score:
            alerts.append({
                "trade_id": t["trade_id"],
                "client_id": profile["client_id"],
                "lei": t["counterparty_lei"],
                "client_name": profile["name"],
                "amount_eur": round(eur, 2),
                "score": round(score, 4),
                "features": features,
                "typologies": match_typologies(features, profile, eur),
            })
    alerts.sort(key=lambda a: -a["score"])
    return lineage.explain({
        "model": model,
        "output": {"alerts": alerts[:max_alerts],
                   "screened_trades": len(live),
                   "profiles": len(profiles)},
        "input_urns": ["urn:fcc:trading:executed-trades",
                       "urn:fcc:client:kyc-profiles"],
    })


def decide(alert, escalated, actor, audit_log, timestamp, feedback=None):
    """Décision humaine sur une alerte : escalade ou classement, journalisé."""
    audit_log.append(
        actor=actor,
        action="aml." + ("escalated" if escalated else "dismissed"),
        subject_urn="urn:fcc:client:kyc-profiles",
        details={"trade_id": alert["trade_id"], "client_id": alert["client_id"],
                 "score": alert["score"]},
        timestamp=timestamp,
    )
    if feedback is not None:
        feedback.record(alert["features"], escalated, actor, timestamp)
