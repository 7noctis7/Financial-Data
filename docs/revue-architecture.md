# Revue d'architecture — comité technique (4 experts)

Revue du code **réel** du dépôt (serveur `app/__main__.py`, garde SQL
`mesh/warehouse.py`, IAM `reporting/generator.py` + `mesh/iam.py`, journal
`mesh/audit.py`, CI `.github/workflows/pages.yml`), et non d'une description.
Date : 10/07/2026. Chaque constat cite un fichier et une ligne.

---

## 1. CTO — viabilité, dette technique, scalabilité

**Points forts.** Cœur en stdlib pur (déploiement trivial, zéro CVE de
dépendances) ; séparation nette plateforme (`mesh/`) / présentation
(`app/`) ; gouvernance exprimée en code et testée (102 tests).

**Constats.**

- **C1 — Aucun cache de payload (chaud).** `GET /api/summary`
  (`app/__main__.py:343`) appelle `build_payload`, qui rejoue tout le
  pipeline du jour (`SimulatedTradingSource.fetch`, `simulate_bank_statements`,
  `run_business_day`, `derive_valuations`) à **chaque** requête. Un simple
  rafraîchissement de page recalcule 250 à 20 000 trades. Aucune
  mémoïsation par `(date, seed, n_trades)`.
- **C2 — `Registry()` reconstruit à chaque appel.** `/api/audit`
  (`:261`), `/api/health` (`:282`), `_ingest`, `_aml_payload` (via
  `Lineage(Registry())`) relisent et revalident **10 fichiers JSON** du
  disque à chaque requête. Le registre est un invariant du processus :
  il devrait être chargé une fois.
- **C3 — État en mémoire non thread-safe.** `_PENDING_AML`
  (`:42`) est un `dict` module-level muté sans verrou sous
  `ThreadingHTTPServer` (multi-thread) ; deux requêtes 4-yeux
  concurrentes sur le même `trade_id` peuvent s'écraser. Il est aussi
  **perdu au redémarrage** (une proposition en attente disparaît) et non
  partagé entre processus.
- **C4 — Coût du journal croissant sans borne.** cf. D1/D2 côté Data —
  impact CTO : le temps de réponse de `/api/health` et `/api/audit`
  croît linéairement avec l'historique, sans rotation.

**Dette prioritaire :** C1 et C2 (chemin chaud, gain immédiat), puis C3
(correction de justesse sous charge concurrente).

---

## 2. Lead Data Architect — structure, intégrité, flux

**Points forts.** Contrats versionnés + ontologie contraignante
(un terme absent fait échouer le chargement) ; provenance transitive
(`combine_origin`) scellée jusqu'aux filings (G8) ; partie double comme
détecteur universel ; journal chaîné re-vérifiable.

**Constats.**

- **D1 — `entries()` relit tout le fichier à chaque appel.**
  `AuditLog.entries()` (`mesh/audit.py`) déclenche un `reload()` complet
  (relecture JSONL + `json.loads` ligne à ligne). Or `/api/health` et
  `/api/audit` appellent `entries()` **et** `verify_chain()` : double
  lecture + recalcul de **tous** les hashes depuis genesis, à chaque
  requête. O(n) non borné.
- **D2 — Pas de segmentation / d'ancrage incrémental du journal.**
  `verify_chain()` repart toujours de genesis. Au-delà de ~10⁵ entrées,
  chaque vérification devient coûteuse. Il manque un point d'ancrage
  périodique (hash de tête daté) permettant une vérification partielle.
- **D3 — Incohérence des paramètres de simulation entre vues.**
  `_accounting_payload` et `_recon_payload` (`:119`, `:176`) forcent
  `drop_rate=0.01, mutate_rate=0.02`, alors que `build_payload`
  (`app/data.py`) utilise les défauts. Deux pages affichent donc des
  relevés bancaires **différents pour la même date** — surprenant pour
  un utilisateur qui recoupe. À centraliser dans un profil de scénario
  unique.
- **D4 — `verify_chain()` recalculé plusieurs fois par requête.** Dans
  `_ingest` puis la réponse, ou dans `_aml_four_eyes`, la chaîne est
  re-vérifiée à chaque étape ; combiné à D1, c'est le principal coût
  caché.

**Priorité :** D1 (mémoïser la tête + longueur, ne relire que le delta),
puis D3 (source de scénario unique).

---

## 3. Sécurité offensive — vecteurs d'attaque

**Points forts.** Bind sur `127.0.0.1` (`:468`) — pas d'exposition
réseau par défaut ; `/reports/<name>` neutralise la traversée via
`Path(...).name` (`:306`) ; `n_trades` borné (`:339`) ; aucun secret en
dépôt (scan négatif) ; SQL en lecture seule par allow-list de verbes.

**Constats — par sévérité.**

- **S1 (ÉLEVÉ) — Lecture de fichiers arbitraires via DuckDB.**
  `POST /api/query` (`:224`) n'autorise que `SELECT/WITH/...`
  (`mesh/warehouse.py:113`), mais DuckDB peut lire le système de
  fichiers **dans un SELECT** : `SELECT * FROM read_csv('/etc/passwd')`,
  `read_text('...')`, `glob('/**')` sont des lectures valides. La garde
  par verbe ne suffit pas. Vecteur réel dès que l'endpoint est
  atteignable (et catastrophique si l'app était un jour exposée hors
  localhost). **Vérifié :** `SELECT * FROM read_csv_auto('/etc/hostname')`
  passe la garde actuelle et lit le fichier.
  **Correctif validé (testé) :** l'entrepôt crée aujourd'hui des *vues*
  paresseuses (`CREATE VIEW ... read_parquet`), donc couper l'accès
  disque après coup casserait aussi les requêtes légitimes. La parade
  qui fonctionne : **matérialiser les Parquet en tables** (`CREATE TABLE
  AS SELECT * FROM read_parquet(...)`, données chargées une fois en
  mémoire), puis `SET enable_external_access=false` +
  `SET lock_configuration=true`. Résultat mesuré : un `SELECT` normal
  passe, `read_csv_auto('/etc/hostname')` est refusé, et l'attaquant ne
  peut pas réactiver l'option (`SET enable_external_access=true` est
  verrouillé).
- **S2 (MOYEN) — Fuite de messages d'exception bruts.** Le `except
  Exception as exc: self._send_json({"error": str(exc)})` (`:254`,
  `:302`, `:327`) renvoie au client des messages internes (chemins
  absolus, structure des données, traces de bibliothèques). Utile en
  local, mais c'est de la divulgation d'information. **Correctif :**
  distinguer erreurs *attendues* (validation, IAM, contrôles → message
  métier) des erreurs *inattendues* (→ message générique + log serveur
  détaillé + identifiant de corrélation).
- **S3 (MOYEN) — Pas de borne sur la taille du corps.** `_read_body`
  (`:217`) fait `int(Content-Length)` puis `rfile.read(length)` sans
  plafond : un `Content-Length` énorme fait allouer/lire sans limite
  (DoS mémoire). **Correctif :** refuser au-delà d'un seuil (ex. 5 Mo)
  avant lecture.
- **S4 (FAIBLE, contextuel) — Endpoints mutateurs sans CSRF ni
  authentification.** `/api/ingest`, `/api/recon/decide`,
  `/api/aml/decide` modifient le journal/feedback sans jeton. Acceptable
  tant que le bind reste local et mono-utilisateur ; à traiter **avant**
  toute exposition multi-utilisateurs (lié à l'item SSO/IAM du backlog).

**Priorité absolue : S1.** C'est le seul constat qui transforme un
lecteur SQL en lecteur de système de fichiers.

---

## 4. Automatisation / DevSecOps — friction CI/CD

**Points forts.** CI simple et lisible ; permissions GitHub minimales
(`contents: read`, `pages: write`) ; tests exécutés avant publication ;
`concurrency` anti-collision.

**Constats.**

- **A1 — Dépendance non épinglée.** `pip install duckdb`
  (`pages.yml:23`) sans version → build non reproductible, cassable par
  une release amont. **Correctif :** `duckdb==<x.y.z>` (ou
  `requirements.txt` + `pip install -r`).
- **A2 — Aucun garde-fou qualité/sécurité dans la CI.** Ni lint (`ruff`),
  ni scan de vulnérabilités statique (`bandit`), ni `pip-audit`. Le
  constat S1 aurait pu être signalé par `bandit`. **Correctif :** un job
  `quality` (ruff + bandit + pip-audit), non bloquant d'abord puis
  bloquant.
- **A3 — Export non déterministe.** `python3 -m app export` sans date
  (`pages.yml:31`) utilise `date.today()` : le site publié change de
  contenu selon le jour du run, sans qu'un commit l'explique. **À
  décider :** figer une date de démo ou assumer explicitement le
  glissement.
- **A4 — Pas de cache pip ni de matrice Python.** Chaque run réinstalle
  tout ; testé sur une seule version implicite. **Correctif :**
  `actions/setup-python` avec `cache: pip` et matrice 3.11/3.12/3.13.

---

## Matrice de priorité (Impact / Effort)

| # | Constat | Impact | Effort | Quadrant |
|---|---|---|---|---|
| **S1** | Lecture fichiers arbitraires (DuckDB) | Élevé | Faible | **Quick win — à faire en premier** |
| **C2** | `Registry()` par requête | Moyen-Élevé | Faible | **Quick win** |
| **D1** | `entries()`/`verify_chain()` O(n) par requête | Moyen-Élevé | Faible | **Quick win** |
| **S3** | Pas de borne sur le corps | Moyen | Faible | **Quick win** |
| **A1** | Dépendance non épinglée | Moyen | Très faible | **Quick win** |
| **C1** | Pas de cache de payload | Élevé | Moyen | **Chantier prioritaire** |
| **S2** | Fuite d'exceptions | Moyen | Moyen | **Chantier prioritaire** |
| **C3** | `_PENDING_AML` non thread-safe / volatile | Moyen | Moyen | **Chantier prioritaire** |
| **D3** | Scénarios de simulation incohérents | Moyen | Moyen | Planifié |
| **A2** | Pas de lint/bandit/pip-audit | Moyen | Moyen | Planifié |
| **D2** | Journal sans segmentation | Faible (aujourd'hui) | Élevé | Différé |
| **S4** | CSRF/auth sur mutateurs | Faible (local) / Élevé (exposé) | Élevé | Différé (bloquant avant exposition) |
| **A3/A4** | Export non déterministe, CI sans cache/matrice | Faible | Faible-Moyen | Planifié |

**Séquence recommandée :** les cinq quick wins d'abord (S1, C2, D1, S3,
A1 — impact réel, effort faible, sans risque de régression), puis les
chantiers C1 / S2 / C3.

---

## État des correctifs (10/07/2026) — tous appliqués et prouvés

| # | Correctif | Preuve exécutable |
|---|---|---|
| **S1** | DuckDB : tables matérialisées + `enable_external_access=false` + `lock_configuration=true` | `test_arbitrary_file_read_is_blocked`, `test_config_cannot_be_reenabled`, `test_legitimate_query_still_works_after_lockdown` ; vérifié en direct : `read_csv_auto('/etc/hostname')` refusé, `SELECT count(*)` OK |
| **S2** | Erreurs attendues (message métier) vs inattendues (message générique + `correlation_id` + log serveur) | Vérifié en direct : template inconnu → message ; lecture fichier → `{"error":"erreur interne","correlation_id":...}` |
| **S3** | Plafond 5 Mo sur les corps POST | Vérifié en direct : `Content-Length: 99999999` → refusé avant lecture |
| **S+** | camt.053 : rejet DOCTYPE/ENTITY (XXE) + borne 20 Mo ; Yahoo : schéma https imposé | `test_camt053_rejects_xxe_doctype` (constat bandit B314/B310) |
| **C1** | Cache borné du payload `/api/summary` par `(date, seed, n_trades)` | Vérifié en direct : 2ᵉ appel ~20× plus rapide (0,001 s vs 0,030 s) |
| **C2** | `Registry()` chargé une fois (`_REGISTRY`), plus par requête | `Registry()` restant : 1 (le singleton) |
| **C3** | `_PENDING_AML` sous `threading.Lock` (section critique 4-yeux) | Relecture adverse : réservation `del` sous verrou avant validation |
| **D1** | `reload()` conditionné au `mtime` ; `verify_chain()` mémoïsé | `test_reload_skips_unchanged_file`, `test_reload_detects_external_append`, `test_verify_still_catches_tamper_after_memo` |
| **D3** | Scénario de simulation unique (`DEMO_SCENARIO`) partagé par toutes les pages | Toutes les vues d'une même date décrivent les mêmes relevés |
| **A1** | `requirements.txt` avec `duckdb==1.5.4` ; CI `setup-python` + cache pip | `pip install -r requirements.txt` |
| **A2** | Job CI `quality` : ruff + bandit (bloquants, verts) + pip-audit (informatif) | `ruff check` : All checks passed ; `bandit -ll` : No issues identified |

Suite : **109 tests verts** (86 → 109 sur cette revue). Restent
volontairement différés (non régressions, dépendants d'une exposition
future) : **S4** (CSRF/auth, bloquant seulement avant multi-utilisateurs)
et **D2** (segmentation du journal, sans impact aux volumes actuels).

---

## Prompt d'itération optimisé (Étape 2)

> Tu es un Staff Engineer. Applique les correctifs de la revue
> d'architecture `docs/revue-architecture.md`, **un constat à la fois**,
> en attendant ma validation entre chaque.
>
> Règles :
> 1. **Sécurité d'abord.** Ne jamais élargir la surface d'attaque. Pour
>    S1, restreindre DuckDB (`enable_external_access=false`,
>    `lock_configuration=true`) sans casser les requêtes légitimes sur
>    les Parquet de l'entrepôt — le prouver par un test qui montre que
>    `read_csv('/etc/passwd')` est refusé ET qu'un `SELECT` normal passe.
> 2. **Responsabilité unique.** Si un correctif alourdit une fonction du
>    serveur, extraire la logique dans `mesh/` ou un module dédié.
> 3. **Observabilité.** Ajouter un log serveur structuré là où une
>    erreur inattendue est désormais masquée au client (S2), avec
>    identifiant de corrélation.
> 4. **Format de réponse** par constat : (a) résumé de l'amélioration ;
>    (b) diff ; (c) impact perf/sécurité ; (d) tests unitaires ajoutés.
> 5. **Non-régression :** `python3 -m unittest discover -s tests` doit
>    rester vert, et le nombre de tests augmenter.
>
> Commence par **S1**. Montre-moi le diff et les tests, puis attends mon
> feu vert avant C2.
