# Revue qualité des rapports — Financial Command Center

Revue du **rendu réel** des 12 templates de `templates/reporting/*.json`
(générés via `reporting/generator.py`, formats CSV/XLSX/PDF/XBRL), sur les six
critères C1–C6. Chaque livrable est réellement généré puis examiné — pas une
lecture du seul JSON. Date : 10/07/2026.

## 1. Grille de revue (verdicts)

Légende : ✅ Conforme · 🟡 Réserve · ⛔ Rejet (bloquant).

| Rapport | C1 Pertinence | C2 Complétude | C3 Exactitude | C4 Langue | C5 Design | C6 Traçabilité |
|---|---|---|---|---|---|---|
| `bilan_economique` | ✅ | ✅ (2 côtés, CP ventilés) | ✅ (bouclage + CP=Cap+Rés+Rés.exercice) | 🟡 synthèse ASCII | ✅ | ✅ |
| `pnl_v1` | ✅ | ✅ (SIG v1, charges n/d) | ✅ (comparatif N-1) | 🟡 synthèse ASCII | ✅ | ✅ |
| `treasury` | ✅ | ✅ | ✅ | 🟡 | ✅ | ✅ |
| `finrep_f0101_fr` | 🟡 titres nets négatifs | 🟡 sous-ensemble Annexe III | ✅ (bilan boucle vs F0103) | 🟡 | ✅ | ✅ |
| `finrep_f0101_en` | 🟡 idem | 🟡 idem | ✅ | 🟡 | ✅ | ✅ |
| `finrep_f0103_fr` | ✅ | 🟡 réserves absentes | ✅ (bouclage F0101 vrai) | ✅ | ✅ | ✅ |
| `corep_c0700` | ✅ | ✅ (pondérations SA v1) | ✅ (RWA recalculé) | 🟡 typo « reguels » | ✅ | ✅ |
| `emir` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `mifid2` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `finfrag` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `regulatory` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `investor_relations` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## 2. Corrections appliquées cette revue (avec preuve)

| # | Sévérité | Défaut | Correction | Preuve |
|---|---|---|---|---|
| R1 | **1 — chiffre mensonger** | F 01.01 (actifs) dérivait un grand livre SANS commissions, F 01.03 AVEC : bilan déséquilibré de 388 762,24 € et affirmation « bouclage F 01.03 = F 01.01 au centime » **fausse**. | `_finrep_f0101` inclut les commissions (`fees_batch`) — une seule dérivation par date. Actif = Passif au centime. | `test_report_quality.test_finrep_balance_sheet_balances_across_statements` (mutation vérifiée : grand livre sans commissions → écart 388 k€ → le test crie). Commit corrigeant `_finrep_f0101`. |
| R2 | **2 — présentation comptable** | Bilan économique : « Capitaux propres (C) » libellé « solde 5000 » alors que le montant incluait le résultat (compte de produit 7000). | Ventilation Capital / Réserves / **Résultat de l'exercice** + contrôle bloquant `CP = Capital + Réserves + Résultat`. | Rendu vérifié ; contrôle vert. |
| R3 | 4 — clarté | « Le bilan boucle ✓ » affiché à côté d'un compte d'attente ≠ 0 (868 k USD) : contradiction apparente. | Tuile « Équilibre partie double : Débits = Crédits » + avertissement explicite sur le 9990 (« l'équilibre tient car 9990 absorbe, montants à apurer »). | Capture d'écran page Comptabilité. |
| R4 | — (fonctionnel) | Page Comptabilité sans compte de résultat ni hors-bilan. | Ajout PnL (SIG) + Hors-bilan (notionnels dérivés, **non valorisés**), fonctions pures `pnl_summary` / `off_balance_sheet` testées. | 2 tests ; rendu vérifié. |

## 3. Non-conformités résiduelles (backlog priorisé)

- **F1 (Réserve, C2) — complétude FINREP vs maquette officielle.** F 01.01 et
  F 01.03 exposent un **sous-ensemble** documenté des lignes de l'Annexe III
  (mapping v1, `docs/corep-finrep.md`). Cible mandat : chaque ligne officielle
  présente, renseignée ou `n/d`. **Décision requise** : périmètre des lignes à
  matérialiser (la plupart `n/d` sur ce modèle salle de marchés) + ajout d'une
  ligne Réserves à F 01.03.
- **F2 (Réserve, C1/C3) — F 01.01 ligne « Titres de créance » négative.** Le
  compte titres (3010) est net vendeur → valeur d'actif négative. En norme, une
  position nette courte relève du **passif de négociation (F 01.02)**, non d'un
  actif négatif. **Décision requise** : modéliser F 01.02 (passifs) — hors
  périmètre actuel. Le bilan boucle malgré cela (partie double).
- **F3 (Réserve, C4) — texte généré sans accents + typo.** Les lignes de
  synthèse/dérivation sont écrites en ASCII (« Synthese », « tresorerie »,
  « Ponderation ») et COREP contient « etablissements bancaires **reguels** »
  (→ « régulés »). Cause racine : sur-prudence PDF. **Sûr à corriger** : le
  rendu PDF encode en latin-1 qui supporte les accents français (vérifié : les
  titres accentués rendent 0 caractère de substitution). Restaurer les accents
  + corriger la typo. Non bloquant, non encore fait.
- **F4 (dette technique) — `reporting/generator.py` = 490 lignes** (> 400).
  À scinder (extraire les builders de datasets comptables/FINREP dans un module
  dédié) avant d'ajouter d'autres états.

## 4. Ce qui est déjà conforme (vérifié, pas supposé)

- **C5 Design / PDF** : aucun caractère de substitution (`?`/tofu) dans les 12
  PDF — `_pdf_escape` translittère `—`/`–`/`↔`/`⇒` avant l'encodage latin-1
  (vérifié en décompressant les flux PDF réels).
- **C6 Traçabilité** : Annexe de Preuve (UTC, provenance, SHA-256, assertions
  certifiées) + sidecar `.proof.json` cohérent, sur les 12 rapports.
- **C3 Exactitude** : contrôles de restitution bloquants présents et verts sur
  les états comptables/FINREP ; bilan équilibré Actif = Passif après R1.
