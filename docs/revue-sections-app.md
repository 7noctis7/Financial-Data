# Revue produit des sections de l'application — Comité de Direction

Revue des neuf sections de l'app, application **réellement lancée**
(`python3 -m app`) et chaque écran exercé (chargement, endpoints, détection
d'overflow via navigateur headless). Grille : V (visuel), P (précision),
R (rigueur), D (pertinence data), I/O (entrées/sorties). Date : 10/07/2026.

## 1. Grille (verdicts) — ✅ Conforme · 🟡 Réserve · ⛔ Rejet

| Section | V | P | R | D | I/O | Note |
|---|---|---|---|---|---|---|
| index (accueil/Marchés) | ✅ | 🟡 | ✅ | ✅ | 🟡 | Marchés limité aux flux de trades (backlog §3) |
| 1·KYC/AML | ✅ *(corrigé)* | ✅ | ✅ | ✅ | ✅ | Débordement corrigé ; recherche client + OSINT à venir |
| 2·Ingestion | ✅ | ✅ | ✅ | ✅ | ✅ | Mappings multi-métiers ajoutés ; dashboard connecteurs à venir |
| 3·Marchés | 🟡 | 🟡 | ✅ | ✅ | 🟡 | Trop light : positions/P&L/risque à ajouter (backlog §3) |
| 4·Réconciliation | ✅ | ✅ | ✅ | ✅ | ✅ | Aging + drill-down par écart à enrichir |
| 5·Comptabilité | ✅ | ✅ | ✅ | ✅ | ✅ | PnL + hors-bilan + équilibre clarifié (livré) |
| 6·Explorateur | ✅ | ✅ | ✅ | ✅ | ✅ | Requêtes d'exemple + drill-down par ligne à venir |
| 7·Rapports | ✅ | 🟡 | ✅ | ✅ | ✅ | cf. docs/revue-qualite-rapports.md (F1–F4) |
| 8·Audit | ✅ | ✅ | ✅ | ✅ | ✅ | Filtres + re-vérif chaîne à confirmer |
| 9·FAQ | 🟡 | — | — | ✅ | — | Réécriture C4 (une entrée par section) à faire |

Contrôle overflow automatisé (Playwright, viewport 1180 & 390 px) : index,
recon, explorer, comptabilité, ingestion, cas → `docScrollW == largeur`, 0
débordement. KYC/AML était en débordement (1186 > 1180) → **corrigé**.

## 2. Corrections appliquées (cette revue + tours précédents, avec preuve)

| Section | Amélioration | Preuve |
|---|---|---|
| 1·KYC/AML | Débordement d'affichage corrigé (tableaux empilés pleine largeur, `.tscroll`, `overflow-wrap`, tuile date). | Playwright : 0 overflow à 1180 & 390 px ; capture. |
| 1·KYC/AML | Clients particuliers + PEP (politiques) ajoutés au portefeuille. | `test_aml` vert ; notations dérivées. |
| 5·Comptabilité | Compte de résultat (SIG) + hors-bilan (notionnels non valorisés) ; équilibre partie double vs compte d'attente clarifié ; capitaux propres ventilés (Capital/Réserves/Résultat). | 2 tests ; capture ; contrôle bloquant. |
| 2·Ingestion | Mappings ontologiques par métier (compta, finance, réglementaire, reporting, contrôle de gestion). | Rendu vérifié, 0 erreur JS. |
| 7·Rapports | Bilan FINREP qui boucle (Actif = Passif) ; cf. `revue-qualite-rapports.md`. | `test_report_quality` (mutation). |

## 3. Backlog d'extension (par valeur métier décroissante — consigné en To-Do)

**Priorité haute.**
- **3·Marchés** : positions & expositions (concentration top-N, HHI), P&L
  jour/cumulé réalisé vs latent (MtM *dérivé* étiqueté), sensibilités
  (duration, delta FX), flux enrichis (volumes horaires, notionnel/devise,
  top contreparties, taux d'annulation, frais), cours externes avec
  instruments **non valorisés** listés. Chaque bloc = un Data Product ou une
  vue contractée, pas une requête ad hoc dans le front.
- **6·Explorateur** : 3–5 requêtes d'exemple cliquables + mode d'emploi ;
  drill-down par ligne (champs, provenance/origine, lignage, journal lié).
- **1·KYC/AML** : barre de recherche client → profil détaillé (dossier,
  règle de notation, historique d'alertes, transactions liées) ; import
  Excel via template versionné + saisie manuelle (validation ligne à ligne,
  journal chaîné) ; panneau OSINT (source+URL+date, étiqueté
  `open-source intelligence`) — **décision humaine** : brancher un vrai
  connecteur OSINT ; sans lui, écran `n/d — connecteur non branché`.

**Priorité moyenne.**
- **2·Ingestion** : dashboard connecteurs (statut, dernier run, volumes,
  rejets anti-corruption par ligne, rejeu idempotent, badge prod/simulated).
- **4·Réconciliation** : aging des suspens, drill-down deux jambes,
  statut de résolution journalisé.
- **8·Audit** : filtres type/acteur/période, re-vérif chaîne à la demande,
  tête de chaîne affichée, refus IAM visibles.
- **9·FAQ** : réécriture C4, une entrée par section (rôle, source des
  données, limites épistémiques).

**Transverse.** Barre de recherche globale ; horodatage « arrêté au … UTC »
par écran ; badge d'origine par section ; export CSV systématique ; liens
croisés entre sections (alerte AML → client ; écart recon → écriture).

## 4. Garde-fous respectés

- Aucune donnée inventée : données absentes → `n/d` ; pas de connecteur →
  état « non branché » explicite (jamais un faux résultat).
- Version publique GitHub Pages : lecture seule, aucune mutation, aucune
  donnée personnelle réelle (les PEP affichés sont fictifs, `simulated`).
- Décisions humaines consignées, non tranchées seul : connecteur OSINT/
  production, publication de données sensibles, élargissement de surface.
