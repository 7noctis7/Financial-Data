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
> **Trois voix invitées** siègent aussi au comité ; chacune impose un standard
> non négociable et un veto sur le résultat :
> - **Elon Musk — l'efficience par les premiers principes.** Applique
>   *l'algorithme* à chaque flux d'outils : (1) mets en cause chaque exigence
>   (nommer l'humain qui la porte), (2) **supprime** toute étape, tout champ,
>   tout outil qui ne se justifie pas — « le meilleur composant est celui qu'on
>   retire », (3) simplifie ce qui reste, (4) accélère le cycle, (5) automatise
>   en DERNIER (jamais un processus faux plus vite). Veto : toute étape manuelle
>   récurrente qu'une intégration MCP/CI supprimerait, tout doublon d'outil, tout
>   délai entre « décidé » et « fait ». Cible la **vitesse de boucle** :
>   idée → code → preuve → décision en minutes, pas en jours.
> - **Steve Jobs — l'expérience et le goût.** « Design is not how it looks, it's
>   how it works. » Le système multi-outils doit **paraître un seul produit** :
>   un utilisateur ne doit jamais sentir la couture entre Claude, Notion, GitHub,
>   Obsidian, Gemini. « It just works » : zéro configuration exposée, un seul
>   point d'entrée par intention. Dis **non à mille choses** — chaque outil,
>   chaque écran, chaque bouton de trop est retiré jusqu'à l'essentiel. Veto :
>   toute friction visible, tout jargon montré à l'utilisateur, toute étape qui
>   demande de « savoir quel outil ». La qualité se voit dans les détails que
>   personne ne remarque consciemment.
> - **Alex Karp (Palantir) — la maîtrise des données et l'ontologie
>   décisionnelle.** La valeur n'est pas dans la donnée mais dans **la décision
>   qu'elle permet**. Impose une **ontologie** qui relie chaque donnée à une
>   entité du monde réel et à l'action qu'elle déclenche ; casse les silos
>   (intégration) sans jamais laisser une IA décider seule sur un sujet sensible
>   (**human-in-the-loop**, décision journalisée). Veto : toute donnée orpheline
>   (sans propriétaire, sans lignage, sans usage décisionnel), toute
>   « intelligence » non traçable, toute exploitation de données sans piste
>   d'audit. La confiance institutionnelle est le produit, pas un supplément.
>
> **Objectif.** Produire un **modèle opérationnel de collaboration** entre ces
> cinq outils, applicable à tout projet, qui maximise la valeur de chacun,
> élimine les doublons, **maîtrise le cycle de vie complet de la donnée** et
> livre une **expérience utilisateur d'un seul tenant**. Interdits : le jargon
> marketing, les généralités (« ils se complètent bien »), et toute proposition
> non réalisable avec les intégrations réelles (MCP, API, git, fichiers
> Markdown).
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
> **Principe imposé n°2 — l'excellence architecturale, en permanence.** Chaque
> projet doit maintenir une architecture *maîtrisée de bout en bout*, jamais
> subie. Standards non négociables : séparation stricte des responsabilités
> (une couche = une raison de changer) ; frontières explicites (une couche
> anti-corruption à chaque entrée externe, le dialecte du fournisseur ne
> franchit jamais le cœur) ; dépendances minimales et orientées vers le stable ;
> contrats versionnés entre modules ; invariants exprimés *en code* et testés,
> pas dans des conventions humaines ; documentation d'architecture vivante
> (`docs/`) tenue à jour dans le même commit que le code. Toute décision
> structurante s'écrit en **ADR** (contexte / options / choix / conséquences).
> Règle de lisibilité : `< 400 lignes/fichier`, `< 50 lignes/fonction`, un nom
> qui dit l'intention. La dette technique se déclare et se planifie ; elle ne
> se cache pas. Test : un nouvel agent doit pouvoir recharger le modèle mental
> du système en lisant seulement `README` + `docs/` + les contrats.
>
> **Principe imposé n°3 — l'efficience absolue des tokens et des agents.** Le
> budget de tokens est une ressource à optimiser à chaque tâche, jamais à
> gaspiller. Impose, pour chaque tâche confiée à un agent IA :
> - **Lire avant de générer** — auditer l'existant (grep, lecture ciblée) évite
>   de régénérer ce qui existe déjà : la moitié des demandes sont déjà faites.
> - **Le bon outil au bon coût** — Gemini pour avaler un gros corpus une fois et
>   en rendre une synthèse *courte et citée* ; Claude raisonne et agit sur cette
>   synthèse, pas sur le corpus brut ; on ne recharge pas un contexte massif à
>   chaque tour.
> - **Contexte ciblé, pas exhaustif** — ne charger que les fichiers/sections
>   nécessaires ; préférer un lien vers la source unique à une recopie ;
>   s'appuyer sur la mémoire externe (Notion/`docs/`) plutôt que ré-expliquer.
> - **Découpe en tranches vérifiables** — une tâche = un incrément prouvable ;
>   on ne relance pas un raisonnement long sur une cible floue (tokens brûlés
>   pour rien).
> - **Sorties structurées et réutilisables** — un résultat (schéma, ADR, table)
>   écrit une fois dans la source canonique sert tous les agents suivants sans
>   le recalculer.
> - **Mesurer** — donner un ordre de grandeur du coût (tokens/appels) d'une
>   approche avant de la lancer, et préférer la moins coûteuse à valeur égale.
> Objectif : **valeur maximale par token**, jamais le token dépensé par confort.
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
> 5. **Maîtrise du cycle de vie de la donnée (regard Karp)** — pour chaque
>    étape, dis quel outil est propriétaire et quel canal la porte :
>    | Étape | Question à trancher | Outil moteur |
>    |---|---|---|
>    | **Création / ingestion** | d'où vient la donnée, quelle provenance ? | connecteur (code GitHub) ; Gemini pour l'extraction multimodale |
>    | **Traitement / dérivation** | quelle transformation, quel lignage ? | code + tests (GitHub) |
>    | **Exploitation / analyse** | quelle décision cette donnée permet ? | Claude (raisonnement) ancré sur la source |
>    | **Investigation** | comment remonter d'un chiffre à sa cause ? | requête + journal d'audit (drill-down) |
>    | **Restitution** | comment prouver un chiffre 6 mois plus tard ? | Annexe de Preuve + hash (GitHub) |
>    Exige une **ontologie** reliant chaque champ à une entité réelle et à son
>    usage ; aucune donnée orpheline ; human-in-the-loop sur toute décision
>    sensible, journalisée.
>
> 6. **Expérience utilisateur unifiée (regards Jobs & Musk)** — décris comment
>    les cinq outils se présentent comme **un seul produit** : un point d'entrée
>    par intention, zéro couture visible, zéro jargon exposé. Pour le visuel et
>    l'UI/UX : hiérarchie claire, un seul système de design (thème clair/sombre,
>    typographie, dates lisibles), interactions directes (survol = détail au
>    temps réel, clic = fenêtre de contexte), et **le retrait comme méthode**
>    (chaque écran/bouton de trop est supprimé). Nomme les 3 frictions
>    utilisateur les plus probables dans un montage multi-outils et comment les
>    faire disparaître.
>
> 7. **Boucle quotidienne type** — décris une journée de travail concrète en
>    8 à 12 étapes, du réveil de l'agent (lecture mémoire) à la clôture
>    (cochage + journal), en montrant les cinq outils à l'œuvre au bon moment,
>    et en visant la **vitesse de boucle** minimale (regard Musk).
>
> 8. **Gouvernance de l'architecture** — comment garder l'architecture excellente
>    dans la durée, pas seulement au départ : où vivent les ADR (Notion) et le
>    schéma d'architecture vivant (`docs/`) ; quels invariants sont vérifiés *en
>    code/CI* (contrats, lint, tests de frontière) plutôt que par discipline ;
>    comment la dette est déclarée et priorisée ; le seuil de découpage
>    (`< 400 lignes/fichier`, `< 50 lignes/fonction`) ; et le test du nouvel
>    arrivant : recharger le modèle mental via `README` + `docs/` + contrats.
>
> 9. **Playbook d'efficience des tokens et des agents** — le protocole concret
>    pour tirer la valeur maximale de chaque token dépensé :
>    | Levier | Règle | Effet |
>    |---|---|---|
>    | Lire avant de générer | auditer l'existant d'abord | ne pas régénérer le déjà-fait |
>    | Bon modèle, bon coût | Gemini avale le corpus → synthèse courte citée ; Claude agit dessus | pas de gros contexte rechargé à chaque tour |
>    | Contexte ciblé | charger sections utiles + liens vers la source unique | moins de tokens d'entrée |
>    | Tranches vérifiables | 1 tâche = 1 incrément prouvable | pas de raisonnement long sur cible floue |
>    | Sorties réutilisables | écrire une fois dans la source canonique | tout agent suivant réutilise sans recalcul |
>    | Mesurer d'abord | estimer coût (tokens/appels) avant de lancer | choisir la voie la moins chère à valeur égale |
>    Donne aussi la règle d'arbitrage : *à valeur égale, l'approche la moins
>    coûteuse gagne ; à coût égal, la plus vérifiable gagne.*
>
> 10. **Matrice de maturité** — 3 niveaux (manuel → semi-automatisé → orchestré)
>     décrivant l'état d'intégration, pour que l'utilisateur situe son projet et
>     voie la prochaine marche concrète à franchir.
>
> **Quintuple veto final.** Avant de conclure, passe le modèle au crible :
> *Musk* — « quelle étape/quel outil/quel token puis-je encore supprimer ? » ;
> *Jobs* — « où l'utilisateur sent-il encore la couture ou le jargon ? » ;
> *Karp* — « quelle donnée reste orpheline ou quelle décision n'est pas
> traçable ? » ; *Architecte* — « quel invariant repose sur la discipline
> humaine au lieu du code ? » ; *FinOps des tokens* — « quel appel IA dépense
> plus qu'il ne crée de valeur ? ». Corrige jusqu'à ce que les cinq vetos
> tombent.
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

Les trois voix invitées cadrent déjà des choix du projet :
- **Musk (efficience)** — un seul payload sert le serveur ET l'export statique ;
  le cache `/api/summary` évite de rejouer le pipeline ; l'origine ne se
  « promeut » pas, elle vient d'un vrai connecteur : aucune étape inutile.
- **Jobs (expérience)** — navigation dans l'ordre du cycle de vie bancaire, un
  seul système de design (thème clair/sombre, dates `JJ/MM/AAAA`), survol =
  détail temps réel, clic = mini-fenêtre ; l'utilisateur ne voit jamais l'outil,
  seulement la tâche.
- **Karp (ontologie décisionnelle)** — `docs/ontology.md` relie chaque champ à
  une entité réelle ; le journal chaîné et l'Annexe de Preuve rendent chaque
  chiffre investigable et opposable ; l'IA propose, l'humain tranche sous
  contrôle 4 yeux (G11), toujours journalisé.
- **Excellence architecturale** — séparation plateforme (`mesh/`) / présentation
  (`app/`) ; couche anti-corruption à chaque entrée externe (connecteurs FIX,
  camt.053, Yahoo) ; contrats versionnés (`domains/*/product.json`) ; invariants
  en code (registre qui rejette un terme hors ontologie, contrôles de
  restitution bloquants) ; dette suivie dans `docs/revue-architecture.md`.
- **Efficience des tokens** — un payload unique sert serveur et export ; le cache
  `/api/summary` évite de rejouer le pipeline ; Gemini résume les gros corpus
  réglementaires une fois, Claude agit sur la synthèse ; la mémoire externe
  (Notion + `docs/`) évite de ré-expliquer le contexte à chaque session.
