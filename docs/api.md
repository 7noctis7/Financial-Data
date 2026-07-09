# API locale — référence

Serveur `python3 -m app` sur `http://localhost:8787`. Toutes les réponses
sont JSON ; les erreurs renvoient `{"error": "..."}` avec un statut 400.

| Méthode | Endpoint | Rôle |
|---|---|---|
| GET | `/api/health` | état du service : produits, DuckDB, intégrité de la chaîne d'audit |
| GET | `/api/summary?date&seed&trades` | payload complet du dashboard (KPI, KRI, tendance J-1, ancre d'audit) |
| GET | `/api/schema` | tables de l'entrepôt SQL (construit à la demande) |
| POST | `/api/query` `{sql}` | SQL lecture seule (SELECT/WITH/DESCRIBE…), 500 lignes max |
| GET | `/api/reports/templates` | catalogue des templates de rapports |
| POST | `/api/reports/generate` `{template, format, role, date}` | livrable certifié (csv/xlsx/pdf/xbrl) — G9/G10 + contrôles bloquants |
| GET | `/reports/<fichier>` | téléchargement d'un livrable généré |
| GET | `/api/recon?date&seed` | suggestions IA de réconciliation (lineage G6) |
| POST | `/api/recon/decide` `{suggestion, accepted, actor}` | décision humaine journalisée + feedback |
| GET | `/api/aml?date&seed` | dossiers KYC + alertes AML scorées |
| POST | `/api/aml/decide` `{alert, escalated, actor}` | **4 yeux (G11)** : 1er appel = proposition ; 2e appel par un acteur distinct = décision |
| GET | `/api/accounting?date&seed` | grand livre : balance générale + contrôle de bouclage |
| POST | `/api/ingest` `{csv, origin, control_totals?}` | ingestion CSV : mapping ontologique, rejets motivés, totaux de contrôle |

Connecteurs hors HTTP : `python3 -m connectors.mcp_server` (MCP stdio,
rôle via `FCC_ROLE`) ; `connectors/camt053.py` (relevés SWIFT camt.053,
`origin=production`) ; `connectors/fix_trading.py` (FIX 4.4).
