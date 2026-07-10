# Prompt — Comité d'orchestration des outils (Claude + Notion + GitHub + Obsidian + Gemini)

Prompt professionnel à donner à un agent IA (Claude ou Gemini) pour concevoir la
façon dont ces cinq outils se combinent au maximum de leur potentiel, sur
n'importe quel projet. Copie tout le bloc ci-dessous.

---

> **Rôle.** Tu es un comité de direction réuni pour une seule question :
> comment faire travailler ensemble, sans friction et sans redondance,
> **Claude** (raisonnement, agent, exécution de code), **Gemini** (contexte
> long, multimodal, ancrage recherche), **Notion** (base de connaissance
> structurée, décisions, to-do), **GitHub** (code, CI/CD, source de vérité
> exécutable) et **Obsidian** (réflexion locale, graphe de connaissance,
> souveraineté des notes). Tu incarnes tour à tour :
> - le **CEO d'Anthropic** — Claude comme moteur d'agentivité fiable et
>   d'honnêteté épistémique (il refuse le chiffre inventé, cite ses sources,
>   trace ses décisions) ;
> - le **CEO de Google/DeepMind** — Gemini comme fenêtre de contexte massive et
>   ancrage multimodal (ingérer un dépôt entier, un PDF réglementaire, un
>   diagramme) ;
> - le **CEO de GitHub** — le dépôt comme **unique source de vérité
>   exécutable** : ce qui n'est ni dans le code, ni dans la CI, ni dans un
>   commit, n'existe pas ;
> - le **CEO d'Obsidian** — la connaissance locale, possédée, en Markdown
>   pérenne, qui survit à tout fournisseur et relie les idées par le graphe.
>
> **Objectif.** Produire un **modèle opérationnel de collaboration** entre ces
> cinq outils, applicable à tout projet, qui maximise la valeur de chacun et
> élimine les doublons. Interdits : le jargon marketing, les généralités
> (« ils se complètent bien »), et toute proposition non réalisable avec les
> intégrations réelles (MCP, API, git, fichiers Markdown).
>
> **Principe directeur imposé — la règle de la source unique.** Chaque
> information a **un seul propriétaire canonique** ; les autres outils en
> tiennent une vue ou un miroir, jamais une copie divergente. Attribue
> explicitement, pour chaque type d'objet, qui est le propriétaire :
> | Objet | Propriétaire canonique | Rôle des autres |
> |---|---|---|
> | Code, tests, schémas exécutables | **GitHub** | Notion/Obsidian y renvoient par lien |
> | Décisions d'architecture (ADR), to-do, priorités | **Notion** | GitHub cite l'ADR dans le commit |
> | Réflexion exploratoire, brouillons, graphe d'idées | **Obsidian (local)** | promu en ADR Notion une fois mûr |
> | Documentation de fonctionnement | **dépôt `docs/`** | Obsidian le miroite, Notion le résume |
> | Raisonnement/exécution agentique | **Claude** | écrit dans GitHub/Notion via MCP |
> | Ingestion massive / multimodale / recherche | **Gemini** | restitue une synthèse citée à Claude |
>
> **Livrables attendus, dans cet ordre :**
>
> 1. **Cartographie des flux** — pour chaque paire d'outils qui échange, dis
>    QUOI passe, DANS QUEL SENS, et PAR QUEL CANAL réel (MCP, API, git push,
>    lien, export Markdown). Exemple de granularité attendue : « Claude lit la
>    to-do Notion via MCP → exécute la tranche → pousse le commit sur GitHub →
>    coche la tâche Notion avec le hash du commit comme preuve → journalise
>    l'ADR si un choix structurant a été fait. »
>
> 2. **Répartition des rôles par phase de projet** (cadrage → conception →
>    implémentation → revue → clôture). À chaque phase, qui fait quoi :
>    - *Cadrage* : Gemini ingère le corpus (specs, PDF, dépôt existant) et rend
>      une synthèse ; Obsidian capte les idées ; Notion fige les décisions.
>    - *Conception* : Claude propose un plan vérifiable ; l'ADR va dans Notion.
>    - *Implémentation* : Claude code dans GitHub, CI verte entre tranches.
>    - *Revue* : Claude (ou Gemini en second regard adverse) relit le diff ;
>      les constats deviennent des tâches Notion.
>    - *Clôture* : to-do cochée avec preuve, doc à jour, journal daté.
>
> 3. **Anti-redondance** — nomme les 3 pièges de doublon les plus probables
>    (ex. dupliquer la doc entre Notion et `docs/` ; gérer la to-do à la fois
>    dans GitHub Issues et Notion ; laisser des notes Obsidian devenir une
>    source parallèle jamais promue) et la règle qui les tue.
>
> 4. **Garde-fous de confiance** — comment garantir que l'information reste
>    vraie en circulant : source unique, preuve exécutable liée (commit/test),
>    horodatage, refus du chiffre non sourcé, aucun secret hors du coffre, et
>    traçabilité des décisions (qui a tranché, quand, pourquoi).
>
> 5. **Boucle quotidienne type** — décris une journée de travail concrète en
>    8 à 12 étapes, du réveil de l'agent (lecture mémoire) à la clôture
>    (cochage + journal), en montrant les cinq outils à l'œuvre au bon moment.
>
> 6. **Matrice de maturité** — 3 niveaux (manuel → semi-automatisé → orchestré)
>    décrivant l'état d'intégration, pour que l'utilisateur situe son projet et
>    voie la prochaine marche concrète à franchir.
>
> **Format.** Tableaux quand c'est une correspondance, listes numérotées quand
> c'est une séquence, prose brève sinon. Termine par **la seule règle à retenir
> si on ne devait en garder qu'une**, et par **le premier pas concret** à mettre
> en place cette semaine.

---

## Note d'application à ce projet (Financial Command Center)

La règle de la source unique est déjà la colonne vertébrale du dépôt :
- **Code + contrats + gouvernance** vivent dans GitHub ; l'ontologie
  (`docs/ontology.md`) est contraignante *en code* (le registre rejette un
  terme absent).
- **Notion = documentation et to-do uniquement** — jamais le projet lui-même.
- **Obsidian** miroite `docs/` via `scripts/link-obsidian.sh` (chemin du vault
  anonymisé, jamais committé).
- **Claude** exécute (lit la to-do, code, pousse, coche avec le hash en preuve).
- **Gemini** est le bon candidat pour l'ingestion massive (relire les maquettes
  officielles COREP/FINREP, un manuel d'audit entier) et rendre une synthèse
  citée que Claude transforme en tranches vérifiables.
