# Connectivité, Reporting certifié & Gouvernance augmentée

Le pont entre l'ontologie interne et le monde extérieur : entrées
(connecteurs, MCP) et sorties (livrables certifiés), sous G9/G10.

## 1. Serveur MCP (`connectors/mcp_server.py`)

Le mesh s'expose à une IA hôte (Claude Desktop, Claude Code...) via le
Model Context Protocol, transport stdio (JSON-RPC délimité par `\n`).

- **Décentralisé** : chaque domaine déclare ses outils dans `TOOLS` avec
  `domain` et `classification` ; le serveur n'est qu'un aiguillage —
  ajouter un domaine n'ajoute que des entrées.
- **Sécurité contextuelle (G9)** : le rôle de la session vient de
  `FCC_ROLE` ; chaque appel passe par `iam.check_access` AVANT exécution
  et chaque refus/appel est journalisé dans la chaîne d'audit.
- Outils v1 : `catalog_list` (public), `sql_query`,
  `simulate_business_day`, `reconciliation_suggest` (internal),
  `report_generate` (restricted).

Déclaration côté client :
```json
{"command": "python3", "args": ["-m", "connectors.mcp_server"],
 "cwd": "<repo>", "env": {"FCC_ROLE": "risk-analyst"}}
```

## 2. Connecteurs externes (`connectors/base.py`)

Un connecteur est une **couche anti-corruption** : le dialecte du
fournisseur (FIX, SWIFT, Bloomberg...) ne franchit jamais la frontière.
`translate()` produit des records aux termes de l'ontologie, validés
contre le contrat du produit cible ; l'intraduisible part en rejet
explicite (matière du signal de dérive). Le batch publié porte sa
provenance — un connecteur de production met `origin = PRODUCTION` et
G8 fait le reste. Exemple fourni : `fix_trading.py` (ExecutionReport
FIX 4.4 → `urn:fcc:trading:executed-trades`).

Ajout d'une source = une sous-classe. Le cœur du Data Product ne change
pas (contrainte de flexibilité).

## 3. Reporting certifié (`reporting/`)

`ReportGenerator.generate()` tient quatre garanties au niveau du
générateur — donc valables pour tout format présent et futur :

1. **G9** : contrôle d'accès avant tout rendu (classification + rôles du
   template) ; refus journalisé, aucun contenu produit.
2. **Certification** : les assertions exigées par le template (parmi
   existence, exhaustivité, droits/obligations, évaluation, exactitude,
   présentation) doivent être `certified` ET vérifiables dans le journal.
3. **Annexe de Preuve (G10)**, injectée DANS le fichier + sidecar
   `.proof.json` : horodatage UTC, demandeur + rôle, provenance des
   données, SHA-256 du contenu, hash de preuve de chaque assertion.
4. **Traçabilité** : la génération elle-même est une entrée du journal
   chaîné (hash du fichier ↔ journal, re-vérifiable après coup).

Formats : CSV, XLSX, PDF — stdlib pur (`renderers.py`), signature
commune `render(title, columns, rows, annex_lines)`. Un format de plus =
une fonction de plus ; du plus sophistiqué = XlsxWriter/FPDF derrière la
même signature. Templates par département dans `templates/reporting/`
(`regulatory`, `investor_relations`, `treasury`) : titre, colonnes,
classification, rôles, assertions exigées.

CLI : `python3 -m reporting regulatory pdf 2026-07-09 --role regulatory-officer`

## 4. Data Contracts versionnés

Déjà au cœur du mesh : chaque produit publie `product.json` (semver)
validé par le registre (G1/G2). Règle d'évolution : changement de schéma
de sortie ⇒ bump de version majeure + revue des consommateurs (même
procédure que l'ontologie). L'interopérabilité sans rupture vient du
contrat, pas d'un middleware.

## 5. Boucle de feedback (`mesh/feedback.py` + `mesh/reconciliation.py`)

Les corrections humaines optimisent les prédictions futures :

1. l'IA de réconciliation propose des matchs **scorés et décomposés**
   (devise, proximité de montant, similarité de référence, date) —
   sortie validée par le lineage XAI (G6) ;
2. un humain accepte/rejette (`decide`) → entrée du journal chaîné ;
3. la décision + son vecteur de features entrent dans la base de
   connaissances (`FeedbackStore`, JSONL append-only sous `data/`) ;
4. les prédictions suivantes sont ajustées par les k décisions les plus
   similaires (cosinus), influence bornée pour que le signal métier
   reste dominant.

Version volontairement minimale d'un RLHF local : quand un vrai modèle
vectoriel s'imposera, seule `FeedbackStore` change (même interface).

## 6. DataTransformer (`mesh/transformer.py`)

Point d'entrée unique de la donnée tabulaire (CSV/Excel/API) dans un
Data Product : mapping ontologique **déclaratif** (renommage, lambda de
transformation, composition `money`), validation contre le contrat,
rejets explicites, et **piste d'audit injectée au niveau de la classe**
— chaque ingestion journalise acteur + horodatage + SHA-256 de l'entrée
dans la chaîne (G3) ; impossible d'ingérer sans tracer. La couche de
simulation (le générateur `sim/`, notre « FactIQ » interne : données
synthétiques bancaires réalistes et déterministes) s'injecte par
`from_source(...)` — même chemin, même audit, mêmes validations que la
production. Mapping des rapports aux normes : `docs/regulatory-mapping.md`.

## 7. Correspondance avec la structure demandée

| Demandé | Ici | Pourquoi |
|---|---|---|
| `/src/connectors` | `connectors/` | le dépôt n'a pas de `/src` ; packages à la racine comme `mesh/`, `app/` |
| `/src/reporting` | `reporting/` + `templates/reporting/` | idem |
| `/src/audit_trail` | `mesh/audit.py` (journal chaîné, assertions) | l'audit-trail préexiste au module — on l'étend, on ne le duplique pas |
| `/src/governance` | `mesh/iam.py`, `mesh/registry.py`, règles G1–G10 | la gouvernance est la plateforme elle-même |
| Polars/XlsxWriter/FPDF | stdlib pur | plus léger que léger ; interfaces prêtes à les accueillir |
