# Étude de cas — « Banque Test SA » : une journée de bout en bout

Fil rouge de démonstration de l'outil, revu sous l'angle de chaque
fonction de direction d'une banque privée. **Établissement fictif ;
toutes les valeurs sont produites par le simulateur déterministe
(seed 42, journée du 09/07/2026) et recalculables à l'identique** —
aucun chiffre de ce document n'est rédigé à la main.

## Le scénario

La Banque Test SA, banque privée genevoise fictive, traite une
journée de marché ordinaire : **250 opérations** (obligations
souveraines, actions, swaps de taux, change à terme) face à **6
contreparties interbancaires** (LEI réels : BNP Paribas, Société
Générale, Deutsche Bank, JPMorgan, Barclays, Nomura), règlement via
3 comptes nostro (EUR/USD/GBP), avec les imperfections du réel :
relevés bancaires incomplets, références mutilées, un client PEP.

## Le parcours — chaque étape sur une page de l'outil

| # | Étape (page) | Entrées | Traitement | Sorties |
|---|---|---|---|---|
| 1 | **KYC/AML** | 10 dossiers clients (résidence, statut PEP, type d'établissement) + les trades du jour | notation par règles déclaratives (PEP/juridiction ⇒ high…) ; criblage AML scoré (montant, fractionnement, notation) | alertes priorisées, escalade/classement humain journalisé, feedback appris |
| 2 | **Ingestion** | CSV externe (export core banking) + totaux de contrôle | mapping ontologique, validation de contrat, rejets motivés | batch certifiable, SHA-256 scellé ; fichier refusé en totalité si les totaux ne bouclent pas |
| 3 | **Marchés** | trades exécutés (produit Trading) | KPI, activité horaire, expositions, panneau KRI (seuils SCI) | vision temps réel + mini-fenêtres de détail par contrepartie/heure/produit |
| 4 | **Réconciliation** | trades réglés ↔ relevés bancaires | matching IA scoré et explicable (montant/référence/date) | suggestions ; décisions humaines journalisées + apprises |
| 5 | **Comptabilité** | trades réglés, relevés, commissions | grand livre en partie double dérivé ; flux inexpliqués → compte d'attente 9990 | « le bilan boucle ✓ », balance générale, exports Bilan/PnL certifiés |
| 6 | **Explorateur** | les 7 tables de l'entrepôt SQL | filtres sans code ou SQL DuckDB | investigation libre, export CSV |
| 7 | **Rapports** | produits certifiés + assertions ISA | moteur de certification : contrôles de restitution bloquants, Annexe de Preuve | EMIR, MiFID II, FinFrag, FINREP F 01.01/01.03, COREP C 07.00, Bilan, PnL |
| 8 | **FAQ** | — | — | compréhension du dispositif |

## La journée en chiffres (seed 42, 09/07/2026 — tous recalculables)

- Notionnel traité : **1,98 Md€** ; exposition vive : **1,85 Md€** ;
  utilisation maximale de limite : **30,6 %** (BNP Paribas).
- Bilan : **TOTAL ACTIFS 485 800 000,00 €** = capitaux d'ouverture
  convertis, bouclé au centime (contrôle scellé dans l'Annexe de Preuve).
- Produit net de commissions : **388 762,24 €** (barème en points de
  base, dérivé trade par trade — compte 7000).
- Réconciliation : 3/3 comptes nostro bouclés en conditions nominales ;
  en conditions dégradées (flux manquants + références mutilées), les
  écarts alimentent le compte d'attente et l'IA propose ses
  rapprochements scorés.
- Conformité : déclaration EMIR = **75 dérivés** ; MiFID II ≈ 243
  exécutions ; C 07.00 : RWA pondérés 20 % (établissements) et exigence
  de fonds propres 8 %.

## Lecture par fonction de direction

- **CEO** — une seule question : « puis-je faire confiance à ces
  chiffres ? » Réponse outillée : panneau KRI vert/orange/rouge, bilan
  qui boucle, chaîne d'audit intègre — la confiance est un état affiché,
  pas une opinion.
- **CFO** — bilan, PnL et FINREP dérivés du même grand livre : un seul
  chiffre de vérité, trois présentations, bouclages croisés au centime.
- **CRO** — expositions par contrepartie avec jauges de limite, RWA
  C 07.00, disjoncteurs de qualité de données par produit.
- **CAO (audit)** — six assertions ISA par produit et par jour, journal
  chaîné SHA-256, tout refus/décision journalisé, re-vérifiable a
  posteriori sans intervention humaine.
- **CDO** — catalogue de 10 Data Products sous contrat versionné,
  ontologie contraignante, provenance G8 transitive, lineage XAI.
- **CIO/CTO** — zéro dépendance (stdlib), une seule optionnelle
  (DuckDB) ; pipeline déterministe rejouable ; même code en local et en
  ligne ; brancher la production = une DataSource `origin=production`.

## Limites déclarées (pas de fiction)

Données simulées (G8 : aucune publication réelle possible) ; valorisation
des dérivés au notionnel (pas de MtM) ; charges d'exploitation non
modélisées (EBE = CA) ; pondérations COREP simplifiées 20/100 %. Chaque
limite est répétée dans les rapports concernés.
