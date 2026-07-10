"""Pré-remplissage d'une communication de soupçon (SAR / MROS).

Une SAR n'invente rien. Chaque champ porte sa SOURCE (dossier KYC, alerte
AML, catalogue de typologies versionné, chaîne d'audit, ou paramètre
d'établissement déclaré). Une information absente est rendue `n/d` avec une
source qui l'explique — jamais un chiffre ou un fait plausible fabriqué.

Réf. : communication de soupçon au bureau de communication (MROS) selon
l'art. 9 LBA ; contenu structuré aligné sur les rubriques usuelles d'une
déclaration d'opération suspecte.
"""

# Identité de l'intermédiaire financier déclarant : paramètre de l'installation
# (pas une donnée du mesh), sourcé comme tel. À renseigner à la mise en service.
DECLARING_INSTITUTION = {
    "name": "Financial Command Center (établissement de démonstration)",
    "role": "intermédiaire financier déclarant",
}


def _f(value, source):
    """Champ SAR : une valeur ET sa source, toujours toutes deux présentes."""
    return {"value": value, "source": source}


def _nd(source):
    """Champ absent : valeur `n/d`, source explicitant l'absence (jamais vide)."""
    return {"value": "n/d", "source": source}


def build_sar(case, profile, alert, business_date):
    """Assemble une SAR pré-remplie. `alert` peut être None (cas KYC pur) :
    les rubriques transaction/typologies deviennent `n/d` sourcées."""
    fields = {
        "declaring_institution": _f(DECLARING_INSTITUTION["name"],
                                    "paramètre d'établissement déclaré (mesh/sar.py)"),
        "report_reference": _f(f"SAR-{case['case_id']}",
                               "identifiant de cas (urn:fcc:client:cases)"),
        "report_date": _f(business_date, "date de traitement du cas"),
        "case_reference": _f(case["case_id"], "cas (urn:fcc:client:cases)"),
        "case_opened_at": _f(case["opened_at"], "ouverture du cas (dérivée)"),
        "subject_client_id": _f(profile["client_id"],
                                "dossier KYC (urn:fcc:client:kyc-profiles)"),
        "subject_name": _f(profile["name"], "dossier KYC"),
        "subject_lei": _f(profile["lei"], "dossier KYC (Counterparty)"),
        "subject_residence": _f(profile["residence_country"], "dossier KYC"),
        "subject_pep": _f(profile["pep"], "dossier KYC (statut PEP)"),
        "subject_risk_rating": _f(profile["risk_rating"],
                                  "notation KYC dérivée par règle"),
        "risk_rationale": _f(profile["rating_rationale"],
                             "justification de notation KYC (règle déclarative)"),
    }
    fields.update(_transaction_fields(alert))
    fields["grounds_for_suspicion"] = _grounds(alert)
    return {"case_id": case["case_id"], "case_type": case["case_type"],
            "fields": fields}


def _transaction_fields(alert):
    if alert is None:
        src = "aucune transaction : cas de revue KYC (pas d'alerte AML)"
        return {"transaction_ref": _nd(src), "transaction_amount_eur": _nd(src),
                "screening_score": _nd(src)}
    return {
        "transaction_ref": _f(alert["trade_id"],
                              "alerte AML (urn:fcc:trading:executed-trades)"),
        "transaction_amount_eur": _f(alert["amount_eur"],
                                     "alerte AML (notionnel converti EUR)"),
        "screening_score": _f(alert["score"],
                              "score de criblage AML (dérivé, modèle aml-screen-v1)"),
    }


def _grounds(alert):
    """Motifs de soupçon = typologies déclenchées, chacune citant sa norme.
    Jamais un motif libre : uniquement des typologies du catalogue versionné."""
    if not alert or not alert.get("typologies"):
        return _nd("aucune typologie déclenchée sur cette alerte")
    grounds = [{"id": t["id"], "label": t["label"], "norm_ref": t["norm_ref"]}
               for t in alert["typologies"]]
    return _f(grounds, "catalogue de typologies AML versionné (aml-typologies-v1)")


def unsourced_fields(sar):
    """Champs sans source exploitable — doit être vide pour une SAR livrable.

    Un champ (ou un motif de soupçon) dont la `source` est absente ou vide est
    une information non traçable : la SAR ne peut pas partir."""
    bad = []
    for name, field in sar["fields"].items():
        if not isinstance(field, dict) or not field.get("source"):
            bad.append(name)
            continue
        value = field.get("value")
        if isinstance(value, list):  # motifs de soupçon : chaque item cite sa norme
            for i, item in enumerate(value):
                if not item.get("norm_ref"):
                    bad.append(f"{name}[{i}].norm_ref")
    return bad
