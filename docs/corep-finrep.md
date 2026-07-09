# COREP / FINREP — Exploration des maquettes et implémentation

Périmètre analysé : maquettes officielles des actes d'exécution UE
déposées dans `templates/reporting/` (FR + EN). Base réglementaire :
Règlement d'exécution (UE) 2021/451 (reporting prudentiel CRR).

## 1. Inventaire des fichiers (phase d'exploration)

| Fichier | Onglets | Contenu identifié |
|---|---|---|
| `FINREP-FR/EN — Annex III` (.xls) | 34 : Index, 1.1–1.3, 2…22, 30, 31, 40… | Maquettes FINREP IFRS : **1.1 = F 01.01 Actifs**, 1.2 = Passifs, 1.3 = Capitaux propres, 2 = F 02.00 Résultat |
| `FINREP-FR/EN — Annex IV` (.xls) | 34 (mêmes états) | Variante GAAP nationaux |
| `FINREP-FR/EN — Annex V / ACT` (.docx) | — | Instructions de remplissage + acte modificatif |
| `COREP_1` (.xlsx) | 33 : 1, 2, 3, 4, 5.1…34 | Fonds propres & exigences : **1 = C 01.00**, 2 = C 02.00, 7 = C 07.00 (risque de crédit SA) |
| `COREP_7` (.xls) | 67–70 | Liquidité ALMM (C 67–C 70) |
| `COREP_9` (.xls) | 71 | **C 71.00** — concentration de la capacité de rééquilibrage |
| `COREP_11` (.xls/.xlsx) | 66 | C 66 — échéancier de maturité |
| `COREP_2–6, 8, 10, 12` (.docx) | — | Instructions (annexes des actes) |

Points de contrôle critiques relevés dans F 01.01 : hiérarchie
d'agrégation (010 = 020+030+040 ; 050 = 060+070+080+090 ; 380 = somme
des postes de niveau 1) et références croisées IAS/IFRS par ligne
(colonne « Références » de la maquette).

## 2. Implémenté : F 01.01 dérivé du grand livre (FR + EN)

```bash
python3 -m reporting finrep_f0101_fr pdf 2026-07-09 --role regulatory-officer
python3 -m reporting finrep_f0101_en xlsx 2026-07-09 --role regulatory-officer
```

Mapping v1 (comptes du grand livre → lignes F 01.01) :

| Ligne | Poste (Annexe III) | Source grand livre | Approximation assumée |
|---|---|---|---|
| 040 (→010) | Autres dépôts à vue | 1010/1011/1012 Nostro (convertis EUR) | comptes chez correspondants = dépôts à vue |
| 060 | Dérivés | 3020 + 3021 | valorisation au notionnel réglé (pas de MtM v1) |
| 080 | Titres de créance | 3010 Titres | poste mixte obligations/actions non ventilé (070 à venir) |
| 360 | Autres actifs | 9990 Compte d'attente | flux inexpliqués en cours d'apurement |
| 380 | TOTAL ACTIFS | somme | = 010 + 050 + 360, **cohérence EBA par construction** |

Les soldes d'ouverture des nostros sont comptabilisés au grand livre
contre le compte 5000 Capitaux propres (sinon un bilan de pur flux
netterait à zéro — la partie double y veille). Contrôle vérifié :
TOTAL ACTIFS = capitaux d'ouverture convertis EUR, au centime.

Limites v1, à lever avec les instructions de l'Annexe V : solde net
négatif d'un compte de négociation à reclasser en F 01.02 (passifs
détenus à des fins de négociation) ; ventilation 070/080 exigerait le
détail par classe d'actifs du grand livre ; périmètre = journée simulée
(G8 : DRYRUN tant que la provenance n'est pas production).

## 3. Roadmap COREP

| État | Prérequis | Statut |
|---|---|---|
| C 07.00 (risque de crédit SA) | pondérations par contrepartie sur `risk:exposures` | 🟡 données présentes, pondérations à modéliser |
| C 01.00 / C 02.00 (fonds propres) | domaine Capital (inexistant) | 🔜 |
| C 66 / C 71 (liquidité) | échéancier des flux (dates de règlement) | 🟡 partiellement dérivable des trades |
