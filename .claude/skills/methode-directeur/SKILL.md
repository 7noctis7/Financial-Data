---
name: methode-directeur
description: >
  Méthode de travail pour le Financial Command Center (Data Mesh Edition) —
  comment décomposer une tâche, vérifier son propre travail et décider quoi
  faire ensuite sur un système qui produit des chiffres réglementaires. À
  charger par tout agent IA (Claude, Gemini, GPT…) travaillant sur ce dépôt.
  Chaque règle a été payée par un bug réel de CE projet : les exemples sont
  les cicatrices.
---

# La méthode — travailler sur un système qui produit des chiffres opposables

Tu hérites d'un système dont les sorties peuvent finir dans un rapport
réglementaire (FINREP, COREP, EMIR) ou devant un auditeur. La compétence qui
compte ici n'est pas d'écrire du code vite — c'est de **ne jamais te mentir à
toi-même**, parce qu'un chiffre faux qui a l'air juste est pire qu'une panne
bruyante. Tout le reste en découle.

## 0. Avant d'agir : lis la mémoire, pas ton intuition

- Lis, dans l'ordre : `README.md` (architecture, squelette) → `docs/ontology.md`
  (le vocabulaire contraignant) → `docs/governance.md` (les règles G1–G11) →
  `docs/revue-architecture.md` (dette connue) → la **To-Do Notion** (source de
  priorité). L'Obsidian vault miroite `docs/` (`scripts/link-obsidian.sh`).
- Reformule en 3 lignes : état du projet, prochaine priorité, ce qui te bloque.
- **Audite avant de coder. La moitié de ce qu'on te demande existe déjà.**
  Cicatrice : le durcissement du broker de règlement (camt.053) était déjà
  livré comme connecteur de production ; refaire une couche « ingestion réelle »
  aurait doublonné du code testé. Une recherche de dix minutes (`grep`, lecture
  des `domains/*/product.json`) évite un jour de doublon.

## 1. Décomposer une tâche difficile

**Le test de décomposition :** si tu ne peux pas nommer le PREMIER incrément
testable en une phrase, tu n'as pas compris la tâche — retourne lire, pas coder.

- **Coupe par vérifiabilité, pas par module.** Chaque tranche se termine par une
  preuve exécutable : un test qui passe, une commande qui affiche le bon
  chiffre, un endpoint qui refuse ce qu'il doit refuser. « J'ai avancé sur les
  rapports » n'est pas une tranche.
- **Ordre des tranches : d'abord ce qui invalide le reste.** Une donnée fausse
  (P0) passe avant un écran. Cicatrice : le grand livre de flux purs du jour
  **boucle à zéro** en partie double (débits = crédits), donc le TOTAL ACTIFS de
  FINREP F 01.01 sortait à `0,00 €`. Construire l'UI du rapport avant d'avoir
  compris cet invariant, c'était décorer un faux. Le fix (booker les soldes
  d'ouverture des nostros contre les capitaux propres) a rendu tout l'aval vrai.
- **Plan avant code pour tout ce qui a une surface** (page, endpoint, contrat de
  Data Product, template de rapport) : 5–10 lignes, identifie ce que le backend
  expose **déjà** (souvent tout : `app/data.py` prépare le payload, le front ne
  fait que tracer), puis code.
- **Gros chantier = plusieurs commits/PR courts, CI verte entre chaque.** Jamais
  une PR cathédrale. La revue d'architecture s'est appliquée en tranches (S1,
  puis C2/D1, puis C1/S2/C3), chacune avec sa preuve — pas d'un bloc.

## 2. Vérifier ton propre travail (hiérarchie des preuves)

Du plus fort au plus faible — ne t'arrête jamais au niveau le plus faible que
tu peux t'offrir :

1. **Exécution réelle du chemin réel.** Lance le serveur, appelle l'endpoint,
   regarde la réponse. Cicatrice : un ancien processus `python3 -m app` gardait
   le port et **servait encore l'ancien code** — les nouveaux endpoints
   répondaient 404 alors que le fichier était juste. « Serveur relancé » ≠
   « nouveau code servi » : tue par motif exact (`pgrep -f "python3 -m app$"`),
   relance, puis `curl`.
2. **Test automatisé avec du mordant.** Un test qui ne peut pas échouer ne
   prouve rien. Le test S1 vérifie que `read_csv_auto('/etc/hostname')` est
   **refusé** ET qu'un `SELECT count(*)` normal **passe** — sinon on prouverait
   juste que tout est cassé. Casse le code, vérifie que le test crie.
3. **Suite complète verte avant tout commit** :
   `python3 -m unittest discover -s tests`. Pas « les tests de mon module » : la
   suite. Chaque nouveau Data Product a cassé un compte ailleurs
   (catalogue 8→10, bouclage FINREP) — les régressions vivent loin de leur cause.
4. **Relecture adverse de ton propre diff.** Relis-le en cherchant à le refuser.
   Les `except Exception: pass` sont des mensonges différés. Cicatrice
   inverse à cultiver : le serveur renvoyait `str(exc)` brut au client (fuite de
   chemins internes) — le correctif distingue erreur *attendue* (message métier)
   d'erreur *inattendue* (message générique + `correlation_id` + log serveur).
5. **Lint / typage / bandit : nécessaires, jamais suffisants.** `ruff` et
   `bandit -ll` doivent rester verts ; un `# nosec` sans justification écrite
   est une alarme qu'on a débranchée.

**Règle des alarmes :** une alarme qui sonne en permanence est morte. Si un KRI
du dashboard clignote rouge en continu, corrige le **seuil** ou le
**classifieur**, jamais en masquant l'alarme.

## 3. Diagnostiquer une panne : la preuve d'abord, l'hypothèse ensuite

- **Lis la trace avant de théoriser.** Cicatrice : « le PDF affiche des `?` » —
  trois hypothèses plausibles (police, encodage front, données). La vraie : les
  tirets cadratins `—` et flèches `↔` non encodables en latin-1 dans le
  générateur PDF. Aucune théorie « données » ne l'aurait trouvée ; l'octet fautif
  si.
- **Distingue « voulu » de « cassé » avant de corriger.** Le grand livre qui
  boucle à zéro sur des flux purs est *correct* (partie double) — le bug était
  l'absence de soldes d'ouverture, pas l'équilibre. « Réparer » l'équilibre
  aurait été un accident.
- **Cherche la cause racine systémique.** L'ontologie pouvait diverger du code →
  le fix n'est pas « corriger un contrat », c'est « le registre **rejette** tout
  terme absent de `docs/ontology.md` » (contrainte en CI, pas discipline
  humaine).
- **Quand une commande utilisateur échoue bizarrement, suspecte d'abord tes
  propres instructions.** Cicatrice : `pkill -f "python3 -m app"` a tué le shell
  appelant parce que le motif matchait sa propre ligne de commande. Et un
  `git commit --amend` a réécrit un commit déjà poussé (résolu par
  `git reset --hard origin/<branche>`). Écris des blocs copiables, motif exact,
  et n'amende jamais du public.

## 4. Décider quoi faire ensuite

Ordre de priorité sur un système qui produit des chiffres opposables :

1. **Ce qui rend les résultats FAUX** — reliquat de données simulées publié en
   réglementaire (G8), mapping incorrect vers un template, chiffre halluciné.
2. **Ce qui échoue en silence** — exception avalée, refus IAM non journalisé,
   contrôle de restitution contourné.
3. **Ce qui débloque la preuve** — journal d'audit chaîné, Annexe de Preuve,
   ancrage public de la tête de chaîne. Sans preuve accumulée, la conformité
   future est une opinion.
4. **Les features.** Elles attendent très bien.

- **Rends les grandes décisions mécaniques à l'avance.** Un rapport ne part que
  si ses contrôles de restitution passent et si une `AuditAssertion certified`
  l'ancre (G4/G10). Le verdict est dans le code, pas dans l'humeur du jour.
- **Sache ce qui n'est PAS ta décision.** Passer une origine en `production`,
  activer un vrai filing réglementaire, réécrire l'historique git public,
  committer quoi que ce soit sous `data/` : tu prépares le dossier (options,
  coûts, reco) et tu consignes la décision humaine — tu ne tranches pas seul.
- **« Je peux » ≠ « c'est le moment ».** Un chantier profond entamé avec 5 % de
  contexte restant produit un chantier béant. Livrer moins, fini, bat livrer
  plus, à moitié.

## 5. Honnêteté épistémique (le wedge du projet)

- **Jamais de chiffre inventé.** Donnée absente → n/d. Pas de cours de marché
  pour un instrument → il n'est **pas valorisé** (le connecteur Yahoo laisse les
  obligations/IRS hors batch plutôt que d'inventer un prix). Une notation KYC est
  `low/medium/high` **par règle déclarative justifiée** affichée sous le dossier,
  jamais tirée au sort. Cicatrice fondatrice : « je ne veux pas de conclusion
  fictive ni d'hallucination, je veux que ce soit correctement justifié. »
- **Étiquette la nature de chaque nombre** : mesuré / dérivé / simulé /
  proxy-déclaré. Un MtM v1 est *dérivé* (rendement du jour × notionnel vif), pas
  une valorisation full-reval — le confondre au reporting serait un mensonge par
  raccourci.
- **La provenance ne se blanchit jamais.** `combine_origin` propage `simulated`
  dès qu'un amont l'est ; G8 refuse la publication réglementaire d'une origine
  non `production` (`OriginError`). Le préfixe `DRYRUN-` marque un filing bloqué.
- **Rapporte fidèlement.** Si un test échoue, dis-le avec la sortie. Si tu as
  sauté une étape, dis-le. Le rapport optimiste coûte 10× au prochain qui te lit.

## 6. Garde-fous d'exécution (non négociables ici)

- **Origine par défaut : `simulated`.** Le `production` exige un vrai connecteur
  (FIX, camt.053, Yahoo) — jamais un flag qui « promeut » du simulé.
- **La version en ligne (GitHub Pages / DuckDB-WASM) est publique et en lecture
  seule POUR TOUJOURS** : aucune décision mutante, aucun secret, aucune clé.
- **`data/` et `dist/` sont gitignorés** : l'entrepôt et l'export sont
  reconstructibles, jamais des sources versionnées. Ne committe pas un artefact.
- **Idempotence** : rejouer un jour ouvré ne doublonne rien (simulateur
  déterministe par `seed:date`, journal append-only chaîné).
- **Sécurité d'abord sur toute entrée externe** : une garde par verbe SQL n'est
  pas une garde (DuckDB lit des fichiers dans un `SELECT`) ; un XML de banque
  tierce se parse DOCTYPE/ENTITY refusés. La surface d'attaque ne s'élargit
  jamais « pour la commodité ».
- **Toutes les dates affichées en `JJ/MM/AAAA`**, tous les horodatages internes
  en UTC ISO 8601. Tout montant est un couple `(amount, currency)`, jamais un
  nombre nu.
- **`< 400 lignes/fichier, < 50 lignes/fonction`** : c'est ce qui permet au
  prochain agent (toi dans trois semaines) de recharger le contexte.

## 7. Clôturer (sinon tu n'as pas travaillé, tu as juste tapé)

À chaque fin de session :
- **Coche la To-Do Notion avec la PREUVE dans la ligne** (commit, chiffre, nom du
  test). Cicatrice répétée : des blocs livrés et jamais cochés — le prochain
  agent paie un audit complet pour redécouvrir ce qui existe déjà.
- **Notion = documentation uniquement** (fonctionnement, ontologie, architecture,
  to-do). Le projet vit dans le dépôt et en ligne, jamais « dans Notion ».
- **Mets à jour la doc concernée** (`docs/…`) et l'Obsidian vault s'il est lié —
  la doc fait partie de la tâche, pas d'un « après ».
- **Commit descriptif, push sur la branche de travail, merge sur `main`** une
  fois la CI verte (l'export Pages se redéploie seul).
- **Termine ta réponse par : « Quelle est la prochaine priorité dans Notion ? »**

## 8. Anti-patterns — si tu te surprends à…

| Réflexe | Correction |
|---|---|
| Coder dès la demande reçue | Audite l'existant (`domains/`, `mesh/`, `docs/`) d'abord |
| « Le test passe » sans l'avoir vu échouer | Casse le code, vérifie que le test crie |
| `except Exception: pass` « pour la robustesse » | Logge la cause (avec `correlation_id`) ou laisse planter |
| Renvoyer `str(exc)` brut au client | Message métier si attendu, générique + log si inattendu |
| Inventer un cours / une notation plausible | Hors batch / n/d / règle justifiée — jamais d'aléa |
| Promouvoir du simulé en production « pour tester » | Vrai connecteur, `origin=production`, ou rien |
| Une PR qui grossit « tant qu'on y est » | Coupe, merge le fini, ouvre la suite |
| Committer un fichier sous `data/` ou `dist/` | Ils sont gitignorés : reconstruis, ne versionne pas |
| Amender / forcer un commit déjà poussé | Nouveau commit ; l'historique public ne se réécrit pas |
| Corriger un KRI en masquant l'alarme | Corrige le seuil ou le classifieur |
| Reporter la doc et le cochage Notion « après » | La clôture FAIT partie de la tâche |
| Trancher à la place de l'humain (origine réelle, filing, anonymat) | Dossier + reco + consignation de SA décision |

---

Le système est honnête aujourd'hui parce que chaque règle ci-dessus a coûté un
bug. Il ne le restera que si l'agent qui te succède refuse, comme toi, le
chiffre plausible qui arrange.
