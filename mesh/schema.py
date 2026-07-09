"""Validateur du sous-ensemble de JSON Schema utilisé par les contrats.

Volontairement minimal (type, required, properties, items, enum, pattern,
minimum) : assez pour rendre les contrats contraignants, sans dépendance
externe. Si un contrat a besoin d'un mot-clé absent d'ici, la question à
poser est d'abord « le contrat est-il trop compliqué ? ».
"""

import re

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


def validate(instance, schema, path="$"):
    """Retourne la liste des erreurs (vide si l'instance est conforme)."""
    errors = []

    expected = schema.get("type")
    if expected:
        pytype = _TYPES[expected]
        if isinstance(instance, bool) and expected in ("integer", "number"):
            errors.append(f"{path}: attendu {expected}, reçu boolean")
            return errors
        if not isinstance(instance, pytype):
            errors.append(f"{path}: attendu {expected}, reçu {type(instance).__name__}")
            return errors

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} hors de l'énumération {schema['enum']}")

    if "pattern" in schema and isinstance(instance, str):
        if not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} ne respecte pas le motif {schema['pattern']!r}")

    if "minimum" in schema and isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if instance < schema["minimum"]:
            errors.append(f"{path}: {instance} < minimum {schema['minimum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: propriété requise manquante {key!r}")
        for key, subschema in schema.get("properties", {}).items():
            if key in instance:
                errors.extend(validate(instance[key], subschema, f"{path}.{key}"))

    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            errors.extend(validate(item, schema["items"], f"{path}[{i}]"))

    return errors
