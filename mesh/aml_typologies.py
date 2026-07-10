"""Typologies AML déclaratives et versionnées.

Une alerte de criblage ne doit pas être qu'un score : elle doit dire, en
termes réglementaires, POURQUOI elle mérite une revue. Chaque typologie
est une RÈGLE déclarative — un prédicat sur les caractéristiques déjà
calculées, une étiquette, et une référence de norme citable. Aucune
n'invente de fait : elle nomme un motif que la donnée présente déjà.

Ajouter/réviser une typologie = éditer cette table (revue conformité),
jamais du code de scoring. Les références citent des normes stables
(LBA, OBA-FINMA, recommandations GAFI) au niveau où elles sont sûres —
pas de numéro d'article inventé.
"""

TYPOLOGY_VERSION = "aml-typologies-v1"

# (id, libellé, référence de norme, prédicat(features, profile, eur))
TYPOLOGIES = [
    ("T1-PEP-SIGNIFICATIF",
     "PEP réalisant une opération significative",
     "Recommandation GAFI 12 (PEP) ; OBA-FINMA — relations d'affaires à risques accrus",
     lambda f, p, eur: f["pep"] >= 1.0 and f["large_amount"] >= 0.5),
    ("T2-JURIDICTION-RISQUE",
     "Contrepartie résidente d'une juridiction à risque plus élevé",
     "Recommandation GAFI 19 (pays présentant un risque plus élevé)",
     lambda f, p, eur: f["high_risk_country"] >= 1.0),
    ("T3-FRACTIONNEMENT",
     "Fractionnement présumé (structuring) — répétition rapprochée",
     "Typologie GAFI de structuring ; obligation de clarification art. 6 LBA",
     lambda f, p, eur: f["velocity"] >= 0.7),
    ("T4-MONTANT-INHABITUEL",
     "Transaction de montant inhabituellement élevé",
     "OBA-FINMA — transactions présentant un risque accru",
     lambda f, p, eur: f["large_amount"] >= 0.8),
    ("T5-CLIENT-RISQUE-ELEVE",
     "Client noté à risque élevé menant une activité",
     "Obligation de clarification particulière art. 6 LBA",
     lambda f, p, eur: f["risk_rating"] >= 1.0),
]


def match_typologies(features, profile, eur):
    """Liste des typologies déclenchées pour une alerte (ordre du catalogue).

    Retourne des dicts {id, label, norm_ref} — jamais un score : la
    typologie qualifie, elle ne pondère pas (le score reste séparé et
    explicable)."""
    fired = []
    for typ_id, label, norm_ref, predicate in TYPOLOGIES:
        if predicate(features, profile, eur):
            fired.append({"id": typ_id, "label": label, "norm_ref": norm_ref})
    return fired
