# Audit institutionnel complet — Financial Command Center

Revue à 360° de l'architecture, du code et du produit, par fonction de
direction. Pour chaque axe : **acquis vérifiables** (dans le code, testés),
**écarts** face au niveau attendu d'une banque privée / family office, et
**actions à coût 0 €** (code et organisation uniquement). Les écarts qui
exigent un budget (licences, infrastructures, certifications) sont
explicitement marqués 💰 — pas de promesse gratuite sur du payant.

## Synthèse exécutive

Le socle est rare pour un projet à coût nul : **gouvernance exécutée par
le code** (G1–G11), preuve d'audit chaînée, provenance structurelle
simulé/production, 85 tests, zéro dépendance obligatoire. Ce qui sépare
l'outil d'un usage production : identités d'entreprise, données de marché
réelles, taxonomie DPM officielle, et durcissement opérationnel
(supervision, sauvegardes, revue de sécurité externe).

## CEO — gouvernance & confiance
- **Acquis** : 11 règles vérifiées par code ; KRI temps réel ; ancre
  d'audit publique quotidienne (tête de chaîne publiée sur le site) ;
  étude de cas traçable de bout en bout.
- **Écarts / actions 0 €** : formaliser un *comité produit* mensuel sur la
  To-Do Notion (rituel, pas du code) ; matrice de responsabilité par
  domaine (owner déjà dans chaque contrat — la publier sur le site).

## CFO — finance & comptabilité
- **Acquis** : grand livre partie double dérivé, bilan/PnL/FINREP d'une
  même source, bouclages croisés au centime, tendance J-1.
- **Écarts / actions 0 €** : clôture mensuelle (agrégation des journées —
  le backfill le permet déjà) ; états comparatifs N/N-1 dans les rapports ;
  charges d'exploitation modélisées (barème de coûts comme fees).
- 💰 : rapprochement avec une vraie comptabilité générale (core banking).

## CRO — risques
- **Acquis** : expositions/limites avec jauges, C 07.00 RWA, disjoncteurs
  de qualité, criblage AML explicable avec 4 yeux.
- **Écarts / actions 0 €** : ~~**valorisation MtM** des dérivés~~ — FAIT :
  produit `market:eod-prices` + `risk:valuations` (méthode v1 : rendement du
  jour × notionnel vif, contrat versionné, certifié par le pipeline). Restait la plus grosse limite
  déclarée) ; stress-tests simples (choc FX ±10 % sur l'entrepôt SQL) ;
  VaR historique quand l'historique multi-jours sera systématique.
- 💰 : données de marché réelles (Bloomberg/Refinitiv).

## CAO — audit interne
- **Acquis** : assertions ISA quotidiennes, journal chaîné re-vérifiable,
  refus tous tracés, contrôles de restitution scellés dans les livrables,
  ancre publique (nouvelle : la tête de chaîne publiée sur GitHub Pages
  rend la falsification rétroactive détectable publiquement).
- **Écarts / actions 0 €** : page « Journal d'audit » dans l'app (le
  journal est en SQL mais mérite son écran) ; échantillonnage dirigé
  outillé (l'IA choisit quoi contrôler).
- 💰 : horodatage qualifié eIDAS/RFC 3161 (autorité tierce).

## CDO — données
- **Acquis** : 10 Data Products sous contrat versionné (dont Marché EOD et valorisation MtM), ontologie
  contraignante, lineage XAI, entrepôt SQL, totaux de contrôle.
- **Écarts / actions 0 €** : SLO mesurés en continu (les contrats les
  déclarent, `/api/health` doit les évaluer par produit) ; dictionnaire de
  données publié sur le site (générable depuis les contrats).

## CIO / CTO — technologie
- **Acquis** : stdlib pur, déterministe et rejouable, CI verte, même code
  local/en ligne, API documentée (`docs/api.md`), `/api/health`,
  connecteurs FIX + **camt.053 production** (nouveau).
- **Écarts / actions 0 €** : authentification locale par utilisateurs
  nommés (fichier de rôles) en attendant le SSO ; journalisation d'accès
  HTTP ; sauvegarde du journal d'audit (il est en mémoire par session
  serveur — le persister en JSONL chaîné).
- 💰 : SSO/SAML d'entreprise, hébergement souverain, pentest externe.

## CMO / Marketing & Communication
- **Acquis** : étude de cas concrète, FAQ, site public auto-déployé,
  navigation métier — un démonstrateur qui se visite seul.
- **Actions 0 €** : page « À propos / méthode » racontant les 11 règles en
  langage client ; captures et PDF d'exemple téléchargeables mis en avant ;
  README anglais (les acheteurs institutionnels lisent en anglais) ;
  vidéo de 3 min du parcours (enregistrable gratuitement).

## Webdesign / UX
- **Acquis** : design system cohérent (jetons clair/sombre, palette
  validée accessibilité), filtres, mini-fenêtres, thème persistant.
- **Actions 0 €** : état de chargement (squelettes) sur les pages à
  calcul ; raccourcis clavier documentés ; version mobile des tableaux
  (cartes empilées) ; impression CSS propre des pages.

## Priorisation proposée (tout à 0 €)

1. Persistance du journal d'audit serveur (risque d'intégrité) — CIO.
2. ~~Produit Marché simulé + MtM~~ — FAIT (contrats `market:eod-prices` + `risk:valuations`, panneau MtM au dashboard) — CRO.
3. Page Journal d'audit + dictionnaire de données auto-généré — CAO/CDO.
4. Clôture mensuelle + comparatifs N/N-1 — CFO.
5. README/landing bilingue + page méthode — CMO.
