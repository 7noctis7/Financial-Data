# Architecture Data Mesh — Financial Command Center

## 1. Frontières de domaines

Une frontière de domaine suit la **propriété métier de la donnée**, pas
l'organigramme. Règle de décision : le domaine qui peut corriger une donnée
à la source en est le propriétaire.

| Domaine | Propriétaire de | Ne possède PAS |
|---|---|---|
| **Trading (Front)** | Trades au fil de l'eau, ordres, exécutions | Positions agrégées (→ Risque), règlements (→ Trésorerie) |
| **Trésorerie (Back)** | Cash, règlements, réconciliation bancaire, liquidité | Valorisation des trades (→ Trading), limites (→ Risque) |
| **Risque (Middle)** | Positions consolidées, expositions, limites, VaR | Données brutes de trades (consomme le produit Trading) |
| **Audit** | Assertions d'audit, journal de preuve, certifications | Les données métier elles-mêmes (il les certifie, ne les modifie pas) |
| **Regulatory** | Rapports réglementaires, règles de conformité versionnées | Les données sources (consomme des produits certifiés par Audit) |

**Investor Relations** n'est pas un domaine propriétaire : c'est un
*consommateur* qui n'a le droit de publier que des chiffres portant une
assertion d'audit `certified`. Le lui donner un Data Product violerait la
règle de propriété (il ne peut rien corriger à la source).

## 2. Catalogue des Data Products

Chaque produit est décrit par un contrat `domains/<domaine>/product.json`
conforme à `mesh/contracts/data-product.schema.json`. Le contrat rend le
produit **découvrable** (registre), **adressable** (`urn:fcc:<domaine>:<produit>`),
**fiable** (SLO de fraîcheur + qualité), **auto-descriptif** (schéma de sortie
lié à l'ontologie) et **sécurisé** (classification + rôles d'accès).

| URN | Sortie principale | SLO fraîcheur | Consommateurs |
|---|---|---|---|
| `urn:fcc:trading:executed-trades` | Trades exécutés (événements) | 5 min | Risque, Trésorerie, Audit |
| `urn:fcc:treasury:cash-positions` | Soldes cash réconciliés | 1 h | Risque, Regulatory, IR |
| `urn:fcc:risk:exposures` | Expositions + utilisation de limites | 15 min | Trading, Regulatory |
| `urn:fcc:audit:assertions` | Assertions d'audit signées | 24 h | Regulatory, IR |
| `urn:fcc:regulatory:filings` | Rapports réglementaires générés | 24 h | Externe (régulateur) |

Flux : Trading → (Risque, Trésorerie) → Audit (certifie) → Regulatory / IR.
L'audit est **continu** : il consomme les produits des autres domaines et
publie des assertions, jamais l'inverse.

## 3. Plateforme self-service

Le noyau (`mesh/`) est ce qu'un domaine reçoit gratuitement :

- **Registre** (`registry.py`) : charge et valide les contrats ; un contrat
  invalide n'entre pas au catalogue — la validation est le déploiement.
- **Preuve d'audit** (`audit.py`) : journal chaîné par hachage (append-only),
  vérification des assertions. Toute écriture est prouvable, aucune n'est
  réécrivable.
- **Disjoncteur** (`circuit_breaker.py`) : par produit, sur deux signaux —
  fraîcheur dépassée et taux de violation de schéma. Ouvert = le produit est
  marqué non consommable ; le reste du mesh continue.
- **Lineage / XAI** (`lineage.py`) : graphe produit→produit ; chaque sortie
  IA référence les URN sources et la version de contrat consommée.

Stack volontairement minimale : Python stdlib, zéro dépendance. Le contrat
et la gouvernance sont la valeur ; l'infrastructure d'exécution (Kafka,
object store, orchestrateur) se branche derrière ces interfaces quand un
volume réel l'exige.

## 4. Couche IA par domaine

L'IA vit **dans** le domaine, pas au centre :

- Trésorerie : matching de réconciliation (suggestions scorées, jamais
  d'écriture automatique — un humain valide, l'audit journalise).
- Risque : détection d'anomalies d'exposition.
- Audit : échantillonnage dirigé (l'IA choisit quoi contrôler, pas le verdict).

Contrainte XAI transverse : une sortie IA sans `lineage_ref` valide est
rejetée par la gouvernance (voir `governance.md` §3).

## 5. Roadmap (décisions de réduction)

Supprimés du périmètre initial — réintroduits seulement quand la valeur est
démontrable :

1. **Dashboards fédérés** : sans flux de données réel, un dashboard est un
   mock. Prérequis : ≥ 2 produits alimentés.
2. **FinOps par domaine** : pertinent quand il y a du compute à mesurer.
3. **Sandbox de stress-testing** : nécessite les produits Risque et Trading
   opérationnels ; un moteur de simulation avant cela testerait du vide.
4. **Regulatory-as-Code complet** : la v1 se limite au mécanisme (règles
   versionnées dans le contrat Regulatory + vérification d'assertions) ;
   la traduction automatique de normes viendra norme par norme.
