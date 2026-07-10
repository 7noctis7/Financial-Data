# Brouillon — modules mis en pause (réactivables)

Le produit en ligne ne surface volontairement que la partie **KYC / AML**
(`app/static/index.html` → accueil, `aml.html` → criblage, `cases.html` →
file de cas). Les autres écrans ont été **archivés ici** — rien n'est
supprimé, l'historique git est préservé (`git mv`).

## Ce qui est parké (front)

`drafts/static/` :

| Page | Rôle |
|---|---|
| `index.html` | Cockpit Marchés (KPIs, positions, concentration HHI, MtM, période N/N-1) |
| `ingest.html` | Ingestion CSV + mappings ontologiques |
| `recon.html` | Réconciliation IA (matching scoré) |
| `accounting.html` | Comptabilité (balance, SIG, hors-bilan, worklist 9990, clôture M/M-1) |
| `explorer.html` | Explorateur SQL (DuckDB) |
| `reports.html` | Rapports certifiés (EMIR, MiFID II, FINREP, COREP…) |
| `audit.html` | Journal d'audit chaîné |
| `faq.html` | FAQ |

## Ce qui reste en place (intentionnel)

Le **backend n'a pas été touché** : les Data Products (`domains/`), le mesh
(`mesh/`), le moteur de reporting (`reporting/`) et les endpoints API
correspondants (`/api/summary`, `/api/recon`, `/api/accounting`,
`/api/reports/*`, `/api/audit`, `/api/query`, `/api/ingest`) existent
toujours et restent testés (suite verte). Ils ne sont simplement plus
surfacés par une page ni publiés sur le site. C'est ce qui rend la
réactivation triviale et sûre.

## Réactiver un module

1. `git mv drafts/static/<page>.html app/static/<page>.html`
2. Rebrancher sa génération dans `app/__main__.py::export()` (pour la
   version statique) : ré-ajouter l'appel `_export_embedded(...)`
   correspondant (voir l'historique git de ce fichier), et le lien de
   navigation dans les pages conservées.
3. `python3 -m unittest discover -s tests` doit rester vert.

L'historique complet de chaque écran (y compris `_export_reports` /
`_export_explorer`, retirés de `export()`) est récupérable via
`git log --follow`.
