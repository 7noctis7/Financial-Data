"""Sécurité contextuelle : droits fondés sur la classification des données.

Règle G9 : toute sortie (export, outil MCP, requête) porte une
classification (`public` / `internal` / `restricted`) et l'appelant un
rôle ; si l'habilitation ne couvre pas la classification — ou si une
liste de rôles explicite est déclarée et n'inclut pas l'appelant —
l'opération est refusée AVANT toute génération de contenu.

Le refus est journalisé : un accès bloqué est un événement d'audit,
pas un échec silencieux.
"""

PUBLIC, INTERNAL, RESTRICTED = "public", "internal", "restricted"
CLEARANCE = {PUBLIC: 0, INTERNAL: 1, RESTRICTED: 2}

# Habilitation maximale par rôle. Un rôle inconnu n'a AUCUN accès
# (deny by default), pas même au public : on ne devine pas une identité.
ROLE_CLEARANCE = {
    "viewer": PUBLIC,
    "investor-relations": INTERNAL,
    "trader": RESTRICTED,
    "treasury-ops": INTERNAL,
    "risk-analyst": INTERNAL,
    "auditor": RESTRICTED,
    "regulatory-officer": RESTRICTED,
    "platform-admin": RESTRICTED,
}


class AccessError(PermissionError):
    """Accès refusé (G9) — le message est montrable à l'appelant."""


def check_access(role, classification, allowed_roles=None, audit_log=None,
                 actor=None, resource=None, timestamp=None):
    """Lève AccessError si `role` ne peut pas lire `classification`.

    `allowed_roles` (venant d'un contrat ou d'un template) restreint
    encore : la classification donne le plancher, la liste donne le mur.
    """
    if classification not in CLEARANCE:
        raise ValueError(f"classification inconnue : {classification!r}")
    granted = ROLE_CLEARANCE.get(role)
    denied = None
    if granted is None:
        denied = f"rôle inconnu : {role!r}"
    elif CLEARANCE[granted] < CLEARANCE[classification]:
        denied = (f"habilitation {granted!r} insuffisante pour une donnée "
                  f"{classification!r}")
    elif allowed_roles and role not in allowed_roles:
        denied = f"rôle {role!r} absent de la liste autorisée {sorted(allowed_roles)}"
    if denied:
        if audit_log is not None:
            audit_log.append(
                actor=actor or role, action="iam.denied",
                subject_urn=resource or "urn:fcc:platform:iam",
                details={"role": role, "classification": classification,
                         "reason": denied},
                timestamp=timestamp or "",
            )
        raise AccessError(f"export bloqué (G9) : {denied}")
