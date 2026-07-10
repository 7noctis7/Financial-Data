# Revue d'écart SaaS — du démonstrateur au produit quotidien

Grille d'écart par section : **existant** (audité, app lancée) vs **cible §4**
du prompt `docs/prompts/transformation-saas.md`. Effort indicatif (S/M/L),
ordre de livraison par valeur métier. Date : 10/07/2026.

## Transverse (§3) — fondations avant les features de section

| Item | Existant | Écart | Effort |
|---|---|---|---|
| §8 Identité (équipe + question du matin par écran) | **livré** (bande persona sur 10 sections) | — | ✅ |
| §3.1 Filtres globaux persistants (URL+localStorage) | filtres par page (marchés, cas, ingest) | barre unique partagée + persistance + « arrêté au … UTC » + badge origine partout | L |
| §3.2 Multi-entité (`entity_id`) | mono-entité | ajouter `entity_id` aux contrats + filtre | M |
| §3.3 RBAC app (rôle en session) | IAM sur rapports/MCP (G9) ; app mono-utilisateur | sélecteur de rôle, refus visibles, KYC `restricted` gardé | M |
| §3.4 Médaillon bronze/silver/gold | couches existent de fait (`data/<date>`, Parquet, payloads) | les NOMMER + doc + contrat de vue gold | S |
| §3.5 Observabilité (`/api/health` enrichi) | health basique | fraîcheur/SLO par produit, latence, hash git | S |
| §3.6 API documentée par tableau | endpoints JSON existants | page catalogue d'API | S |

## Sections (§4)

| Section | Existant | Écart principal vers la cible | Effort | Priorité |
|---|---|---|---|---|
| **index** cockpit | KPIs, MtM, expositions, concentration HHI, KRI, étude de cas | tuiles « top risques » consolidées (suspens>7j, revues échues, contrôles échoués) cliquables ; variation J/J-1 & M/M-1 ; mini-stress FX±10 %/taux±100 bp | M | **haute** |
| **1·KYC/AML** | criblage scoré, typologies, PEP, débordement corrigé | recherche client → dossier détaillé ; import Excel template versionné + saisie manuelle ; entonnoir criblage + taux de faux positifs mesuré ; aging revues ; OSINT (connecteur — décision humaine) | L | **haute** |
| **Cas** | file SLA, 4-yeux, SAR | charge par analyste ; lien croisé cas↔client↔trade | S | moyenne |
| **2·Ingestion** | transformer, totaux de contrôle, mappings multi-métiers | dashboard connecteurs (statut, volumes, rejets ligne à ligne, fraîcheur vs SLO) ; rejeu idempotent depuis l'écran | M | moyenne |
| **3·Marchés** | flux intraday, MtM, expositions, HHI (livré) | positions vives par axe ; P&L réalisé vs latent par desk ; sensibilités (duration, delta FX) ; prix aberrants ; limites à seuils non permanents ; filtres croisés | L | **haute** |
| **4·Réconciliation** | suggestions IA, décision | aging des suspens (0-1/2-7/>7/>30 j cliquable) ; drill-down 2 jambes ; précision matcher affichée ; lien →9990 | M | **haute** |
| **5·Comptabilité** | balance, SIG, hors-bilan, équilibre clarifié | clôture mensuelle M/M-1 (backfill existe) ; worklist apurement 9990 ; pont compta↔F 01.01 | M | **haute** |
| **6·Explorateur** | SQL sécurisé (S1), filtres sans SQL | 5 requêtes d'exemple cliquables + mode d'emploi ; drill-down par ligne (origine, contrat, audit) ; requêtes sauvegardées | M | **haute** |
| **7·Rapports** | génération certifiée, Annexe, contrôles | statut contrôles par rapport ; historique + re-vérif hash↔journal ; liasse groupée ; sélecteur période ; (F1/F2/F3 qualité) | M | moyenne |
| **8·Audit** | journal chaîné, vérif intégrité | explorateur filtrable (action/acteur/URN/période) ; export signé d'une période ; refus IAM visibles | M | moyenne |
| **9·FAQ** | présente | réécriture C4, une entrée par section avec limites épistémiques | S | basse |

## Ordre de livraison recommandé (valeur métier ÷ effort)

1. **§3.4 + §3.5** (nommer médaillon, health/SLO) — fondation cheap, débloque l'observabilité vendable. **S**
2. **5·Comptabilité — clôture mensuelle M/M-1 + worklist 9990** — CFO office, backfill déjà là. **M**
3. **4·Réconciliation — aging + drill-down** — back-office quotidien, data déjà là. **M**
4. **index — top risques consolidés + variations** — cockpit direction, agrège l'existant. **M**
5. **6·Explorateur — exemples + drill-down** — self-service, forte valeur perçue. **M**
6. **3·Marchés — positions + P&L réalisé/latent + sensibilités** — desk/risque. **L**
7. **§3.1 filtres globaux + §3.3 RBAC** — transverse, à faire quand 2-3 sections stables. **L**
8. **1·KYC/AML — recherche/import/OSINT** — gros, connecteur OSINT = décision humaine. **L**

## Décisions humaines (dossier préparé, non tranché seul)

Multi-tenant (isolation/facturation), SSO/OIDC, connecteur OSINT/World-Check
réel, connecteur production (FIX/CAMT.053), pricing, exposition réseau
au-delà de localhost. Chacune deviendra une entrée To-Do datée.
