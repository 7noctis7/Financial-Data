# Gouvernance fédérée

Principe : les **règles** sont globales, leur **exécution** est locale au
domaine, leur **vérification** est automatique dans la plateforme. Une règle
qui ne peut pas être vérifiée par du code n'entre pas ici.

## 1. Règles appliquées par la plateforme (v1)

| # | Règle | Point d'application |
|---|---|---|
| G1 | Un Data Product sans contrat valide n'existe pas au catalogue. | `registry.py` — validation au chargement |
| G2 | Tout terme de schéma de sortie doit exister dans l'ontologie. | `registry.py` — contrôle contre `docs/ontology.md` |
| G3 | Toute écriture d'audit est chaînée par hachage ; la falsification d'une entrée invalide toute la chaîne en aval. | `audit.py` — `AuditLog.verify_chain()` |
| G4 | Une assertion `certified` exige une entrée de preuve dans le journal. | `audit.py` — `make_assertion()` |
| G5 | Un produit dont le disjoncteur est ouvert est non consommable ; les consommateurs le voient via le catalogue. | `circuit_breaker.py` |
| G6 | Une sortie IA sans lineage résoluble vers des URN du catalogue est rejetée. | `lineage.py` — `explain()` |
| G7 | Chaque contrat déclare sa classification (`public` / `internal` / `restricted`) et les rôles autorisés ; le registre refuse un contrat `restricted` sans liste de rôles. | `registry.py` |

## 2. Assertions d'audit

Cycle : le domaine Audit consomme un produit, exécute ses contrôles, publie
une `AuditAssertion` (statut + périmètre + horodatage) et journalise la
preuve dans le journal chaîné. Regulatory et Investor Relations ne peuvent
publier que des chiffres couverts par une assertion `certified` (invariant
n°3 de l'ontologie).

Le journal est **append-only** : chaque entrée contient le hash de la
précédente (SHA-256). La vérification recalcule la chaîne complète —
aucune entrée ne peut être modifiée ou insérée rétroactivement sans
détection. C'est le « moteur de preuve d'audit immuable » v1 ; l'ancrage
externe (horodatage tiers) est un durcissement ultérieur, pas un prérequis.

## 3. Disjoncteurs (dérive de données)

Deux signaux par produit, définis dans son contrat :

- **Fraîcheur** : dernière publication plus vieille que `freshness_slo`.
- **Qualité** : taux de violation de schéma sur une fenêtre glissante
  au-dessus de `max_violation_rate`.

États : `closed` (nominal) → `open` (isolé) → `half-open` (réessai après
`cooldown`). L'ouverture est journalisée dans le journal d'audit — une
indisponibilité est un événement auditable, pas un incident silencieux.

## 4. Regulatory-as-Code (périmètre v1)

Une `RegulatoryRule` est une fonction versionnée dans le domaine Regulatory :
`rule(data_product_snapshot) -> pass | fail + evidence`. Le contrat
Regulatory liste les règles actives avec leur référence normative. La
« traduction automatique des normes » est explicitement hors périmètre v1 :
on traduit norme par norme, à la main, avec revue — l'automatisation
viendra quand le corpus de règles manuelles donnera un étalon de qualité.

## 5. Ce que la gouvernance ne fait pas (réduction)

- Pas de workflow d'approbation humain outillé (une PR Git suffit).
- Pas de moteur de policies générique (OPA, etc.) tant que les 7 règles
  ci-dessus tiennent dans du Python lisible.
- Pas de chiffrement/IAM propre : la plateforme déclare les besoins d'accès
  dans les contrats ; l'application revient à l'infrastructure d'accueil.
