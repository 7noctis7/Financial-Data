# Alignement « Manuel suisse d'audit » — SCI, prudentiel FINMA, KPI/KRI

Analyse d'écart entre le Financial Command Center et les exigences du
référentiel suisse (Manuel suisse d'audit, LFINMA, LIMF/FinfraG, circulaires
FINMA sur la gouvernance). Trois volets : fonctionnalités de conformité,
structure de reporting, méthodologie de contrôle interne.

## 1. Fonctionnalités prudentielles — acquis et écarts

| Exigence (référentiel) | État dans le projet | Écart / action |
|---|---|---|
| Piste d'audit inviolable (traçabilité des opérations) | ✅ journal chaîné SHA-256 (G3), génération de rapports et décisions humaines journalisées | Ancrage d'horodatage externe (durcissement) |
| Assertions d'audit ISA (existence, exhaustivité, droits, évaluation, exactitude, présentation) | ✅ exigées et vérifiées à chaque livrable (G10) | — |
| Séparation des fonctions / habilitations | ✅ IAM contextuel G9 (deny-by-default, refus journalisés) | Double validation (« 4 yeux ») sur les actions sensibles |
| Déclaration dérivés LIMF/FinfraG | 🟡 gabarit EMIR équivalent ; FinfraG partage le socle | Gabarit `finfrag.json` dédié (seuils suisses) |
| LCB-FT (OBA-FINMA) | ✅ v1 : criblage AML explicable, décision humaine, feedback | Scénarios OBA formalisés (seuils, pays GAFI versionnés en RegulatoryRule) |
| Gouvernance des données personnelles (LPD/RGPD) | ✅ KYC classé `restricted`, accès conformité/audit uniquement | Registre des traitements + durée de conservation |
| Continuité et re-jouabilité | ✅ pipeline déterministe (seed + date), entrepôt reconstructible | — |

## 2. Reporting & dashboard d'audit — KPI / KRI

Structure cible : **un indicateur = une source certifiable** (produit du
catalogue + assertion), sinon il n'entre pas au tableau de bord.

**KPI (santé opérationnelle)** — déjà affichés : volumes de trades,
notionnel, expositions, réconciliation, intégrité de la chaîne d'audit.

**KRI (risque & conformité) à afficher — prochaine itération UI :**

| KRI | Source | Seuil d'alerte proposé |
|---|---|---|
| Taux de violation de schéma (qualité) | disjoncteurs | > 0,5 % → orange, > SLO → rouge |
| Comptes non réconciliés / âge du plus vieil écart | `treasury:cash-positions` | > 0 pendant > 2 jours ouvrés |
| Utilisation maximale de limite de contrepartie | `risk:exposures` | > 75 % orange, > 90 % rouge |
| Alertes AML ouvertes / délai moyen de traitement | `client:kyc-profiles` + décisions | > 5 jours ouvrés |
| Dossiers KYC en retard de revue | `client:kyc-profiles` | revue > 12 mois |
| Refus IAM (tentatives d'accès) | journal `iam.denied` | pic anormal = revue |
| Rapports générés sans soumission / dry-runs | `regulatory:filings` | suivi mensuel |

## 3. Méthodologie SCI — trois lignes de défense

1. **Première ligne (métier)** : les contrôles sont DANS les Data Products —
   validation de contrat à l'ingestion (DataTransformer), disjoncteurs,
   rejets motivés. Un contrôle non codé n'existe pas (principe G-rules).
2. **Deuxième ligne (conformité/risque)** : criblage AML, règle G8
   (provenance), G9 (habilitations), gabarits réglementaires mappés aux
   normes (`regulatory-mapping.md`).
3. **Troisième ligne (audit)** : le domaine Audit consomme, ne modifie
   jamais ; assertions ancrées dans le journal chaîné ; toute la chaîne est
   re-vérifiable a posteriori (`verify_chain`, hash des livrables).

**Détection d'anomalies — approche proposée** (roadmap, par ordre de valeur) :
1. Contrôles de bouclage comptable : somme des mouvements = variation des
   soldes nostro (écart = anomalie de premier rang) → nécessite le futur
   domaine Comptabilité (grand livre en partie double dérivé des trades
   et règlements).
2. Analyses de population sur l'entrepôt SQL : doublons d'UTI, trades hors
   séance, montants ronds répétés, bénéficiaires inhabituels (loi de
   Benford sur les notionnels).
3. Échantillonnage dirigé par le risque : l'IA choisit QUOI contrôler
   (scores), l'auditeur conclut — jamais l'inverse.

## Priorités dérivées (à arbitrer dans la To-Do List)

1. **Domaine Comptabilité** : écritures en partie double dérivées des
   trades/règlements + contrôle de bouclage quotidien (le KRI n°1 d'un
   auditeur suisse).
2. **Panneau KRI** sur le dashboard (tableau ci-dessus, seuils codés).
3. Gabarit **FinfraG** + scénarios OBA-FINMA versionnés en RegulatoryRule.
4. Double validation (4 yeux) sur escalades AML et filings.
