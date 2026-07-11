"""Criblage nominatif contre listes de surveillance (sanctions / PEP / médias).

Transposition des patterns de référence du marché (LSEG World-Check One,
ComplyAdvantage) dans la doctrine du mesh :
- matching FLOU (variations d'orthographe, alias, inversions) avec un score
  explicable — jamais un oui/non opaque ;
- identifiants secondaires (pays) pour réduire les faux positifs ;
- seuils déclaratifs : correspondance forte / possible / hors champ ;
- chaque hit exige une RÉSOLUTION humaine (true match / false positive),
  journalisée ; un faux positif résolu est SUPPRIMÉ des criblages suivants
  (whitelist) tant que l'entrée de liste ne change pas de version ;
- la liste embarquée est SIMULÉE et étiquetée comme telle (G8) — un vrai
  connecteur de listes (UE/OFAC/ONU sous licence) est une décision humaine.
"""

import difflib
import unicodedata

WATCHLIST_VERSION = "watchlist-sim-v1"

# Liste de surveillance simulée : personnes/entités fictives dont certaines
# entrent en collision (exacte, alias, translittération) avec les clients
# simulés du mesh — et des leurres proches pour exercer les seuils.
# (name, entry_type, list_ref, aliases, country)
WATCHLIST = [
    ("Farida Benali", "pep", "SIM-PEP-LIST (registre PEP simulé)",
     ["F. Benali", "Farida Ben Ali"], "KY"),
    ("Edouard Villemont", "pep", "SIM-PEP-LIST (registre PEP simulé)",
     ["Édouard Villemont", "E. Villemont"], "FR"),
    ("Dimitri Sokolov", "sanction", "SIM-SANCTIONS (liste consolidée simulée)",
     ["Dimitrii Sokolov", "D. Sokolov"], "JP"),
    ("Atlas Trade Finance Ltd", "adverse_media", "SIM-MEDIA (presse simulée)",
     ["Atlas Trade Finance", "Atlas TF Ltd"], "PA"),
    # Leurres : proches mais PAS nos clients — exercent les faux positifs
    ("Farid Benal", "sanction", "SIM-SANCTIONS (liste consolidée simulée)",
     [], "IR"),
    ("Nordwind Asset Management SA", "adverse_media", "SIM-MEDIA (presse simulée)",
     ["Nordwind AM"], "LU"),
    ("Sofia Marchetti-Blanc", "pep", "SIM-PEP-LIST (registre PEP simulé)",
     [], "FR"),
]

STRONG_MATCH = 0.88   # correspondance forte : cas ouvert d'office
POSSIBLE_MATCH = 0.72  # correspondance possible : résolution analyste requise


def normalize(name):
    """Minuscules, sans accents ni ponctuation, tokens triés (inversions)."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    tokens = "".join(c if c.isalnum() or c.isspace() else " " for c in text).split()
    return " ".join(sorted(tokens))


def similarity(candidate, reference):
    """Score 0..1 : séquence normalisée + recouvrement de tokens (moyenne).

    Deux signaux valent mieux qu'un : SequenceMatcher capte les fautes de
    frappe, le Jaccard de tokens capte initiales/mots manquants."""
    a, b = normalize(candidate), normalize(reference)
    if not a or not b:
        return 0.0
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    # Jaccard de tokens FLOU : deux tokens s'apparient si leur similarité de
    # séquence ≥ 0,85 (« dimitrii » ≈ « dimitri ») — c'est ce qui capte les
    # translittérations que le Jaccard strict pénalise à tort.
    ta, tb = a.split(), b.split()
    matched = 0
    remaining = list(tb)
    for token in ta:
        best = max(remaining, key=lambda t: difflib.SequenceMatcher(None, token, t).ratio(),
                   default=None)
        if best and difflib.SequenceMatcher(None, token, best).ratio() >= 0.85:
            matched += 1
            remaining.remove(best)
    jac = matched / (len(ta) + len(tb) - matched)
    return round((seq + jac) / 2, 4)


def best_match(profile_name, entry):
    """Meilleur score contre le nom principal ET chaque alias."""
    name, _type, _ref, aliases, _country = entry
    scores = [(similarity(profile_name, name), name)]
    scores += [(similarity(profile_name, alias), alias) for alias in aliases]
    return max(scores)


def screen_profiles(kyc_batch, business_date, suppressed=None):
    """Crible chaque dossier KYC contre la liste ; retourne les hits scorés.

    `suppressed` : ensemble de clés (client_id, list_ref, version) déjà
    résolues « faux positif » — supprimées tant que la liste ne change pas
    (pattern World-Check : auto-résolution des récurrences)."""
    suppressed = suppressed or set()
    hits = []
    for profile in kyc_batch["records"]:
        # le nom seul (sans le descriptif entre parenthèses) est criblé
        clean = profile["name"].split("(")[0].strip()
        for entry in WATCHLIST:
            score, matched = best_match(clean, entry)
            if score < POSSIBLE_MATCH:
                continue
            name, entry_type, list_ref, _aliases, country = entry
            # identifiant secondaire : le pays concorde-t-il ?
            country_match = profile["residence_country"] == country
            adjusted = round(min(1.0, score + (0.04 if country_match else -0.03)), 4)
            if adjusted < POSSIBLE_MATCH:
                continue
            key = (profile["client_id"], list_ref + ":" + name, WATCHLIST_VERSION)
            hits.append({
                "hit_id": f"HIT-{profile['client_id']}-{normalize(name).replace(' ', '-')[:24]}",
                "client_id": profile["client_id"],
                "client_name": profile["name"],
                "list_entry": name,
                "matched_alias": matched,
                "entry_type": entry_type,
                "list_ref": list_ref + " — SIMULÉE",
                "score": adjusted,
                "strength": "strong" if adjusted >= STRONG_MATCH else "possible",
                "secondary_id": {"country_profile": profile["residence_country"],
                                 "country_list": country, "match": country_match},
                "suppressed": key in suppressed,
                "list_version": WATCHLIST_VERSION,
                "screened_at": f"{business_date}T07:30:00Z",
            })
    hits.sort(key=lambda h: (-h["score"], h["client_id"]))
    return hits


def resolve_hit(hit, true_match, actor, audit_log, timestamp):
    """Résolution humaine d'un hit : true match ou faux positif, journalisée.

    Retourne la clé de suppression si faux positif (à persister par
    l'appelant) — un vrai match reste visible et alimente un cas."""
    audit_log.append(
        actor=actor,
        action="screening." + ("true_match" if true_match else "false_positive"),
        subject_urn="urn:fcc:client:screening-hits",
        details={"hit_id": hit["hit_id"], "client_id": hit["client_id"],
                 "list_entry": hit["list_entry"], "score": hit["score"],
                 "list_version": hit["list_version"]},
        timestamp=timestamp,
    )
    if not true_match:
        return (hit["client_id"], hit["list_ref"].replace(" — SIMULÉE", "")
                + ":" + hit["list_entry"], hit["list_version"])
    return None
