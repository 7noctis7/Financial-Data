"""Contrôle qualité des enregistrements contre le contrat de leur produit.

C'est ce contrôle qui alimente le signal « taux de violation de schéma »
du disjoncteur : un record invalide n'est pas une exception, c'est une
mesure de dérive.
"""

import re

_ISO_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
_ISO_CCY = re.compile(r"^[A-Z]{3}$")


def _check_money(value):
    if not isinstance(value, dict):
        return "un montant est un couple (amount, currency), pas un nombre nu"
    amount = value.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return "money.amount doit être numérique"
    currency = value.get("currency")
    if not isinstance(currency, str) or not _ISO_CCY.match(currency):
        return f"money.currency doit être un code ISO 4217, reçu {currency!r}"
    return None


def _check_type(value, field_type):
    if field_type == "string":
        return None if isinstance(value, str) else "attendu string"
    if field_type == "boolean":
        return None if isinstance(value, bool) else "attendu boolean"
    if field_type == "integer":
        return None if isinstance(value, int) and not isinstance(value, bool) else "attendu integer"
    if field_type == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        return None if ok else "attendu number"
    if field_type == "timestamp":
        ok = isinstance(value, str) and _ISO_TS.match(value)
        return None if ok else "attendu timestamp ISO 8601 UTC"
    if field_type == "money":
        return _check_money(value)
    return f"type de contrat inconnu : {field_type!r}"


def validate_record(contract, record):
    """Retourne la liste des violations d'un record contre son contrat."""
    errors = []
    for field in contract["output_schema"]["fields"]:
        name = field["name"]
        if name not in record:
            errors.append(f"champ manquant : {name!r}")
            continue
        problem = _check_type(record[name], field["type"])
        if problem:
            errors.append(f"champ {name!r}: {problem}")
    return errors


def validate_batch(contract, batch):
    """Valide tous les records d'un batch ; retourne (valides, violations).

    `violations` liste (index, erreurs) — c'est l'entrée du disjoncteur.
    """
    valid, violations = [], []
    for i, record in enumerate(batch["records"]):
        errors = validate_record(contract, record)
        if errors:
            violations.append((i, errors))
        else:
            valid.append(record)
    return valid, violations
