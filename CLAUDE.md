# CLAUDE.md — contexte auto-chargé à chaque session

Ce fichier est lu automatiquement par Claude Code au démarrage de **chaque**
session sur ce dépôt. Il est volontairement court (efficience des tokens) : il
ne réexplique rien, il **pointe** vers la source unique de chaque règle.

## À faire en tout début de session

1. **Charge le skill `methode-directeur`** (méthode de travail, cicatrices
   réelles, garde-fous). Il est dans `.claude/skills/methode-directeur/SKILL.md`.
2. **Lis la mémoire, pas ton intuition** — dans l'ordre : `README.md` →
   `docs/ontology.md` → `docs/governance.md` → `docs/revue-architecture.md` →
   la **To-Do Notion** (source de priorité).
3. Reformule en 3 lignes : état, prochaine priorité, ce qui te bloque.

## Règles permanentes (résumé ; le détail est dans les fichiers cités)

- **Source unique** : GitHub = code exécutable ; Notion = documentation +
  décisions + to-do (JAMAIS le projet lui-même) ; Obsidian miroite `docs/` ;
  `data/` et `dist/` sont gitignorés (reconstructibles, jamais versionnés).
- **Honnêteté épistémique** : jamais de chiffre inventé (donnée absente → n/d ;
  pas de cours → non valorisé ; notation par règle justifiée). Provenance G8 :
  le `simulated` ne se promeut jamais en `production` sans vrai connecteur.
- **Excellence architecturale** : séparation `mesh/` (plateforme) / `app/`
  (présentation) ; couche anti-corruption à chaque entrée externe ; contrats
  versionnés ; invariants **en code** ; `< 400 lignes/fichier`, `< 50/fonction`.
- **Preuve avant tout** : suite verte (`python3 -m unittest discover -s tests`)
  avant chaque commit ; `ruff` + `bandit -ll` verts ; exécution réelle du chemin
  réel, pas seulement un test.
- **Présentation** : dates en `JJ/MM/AAAA`, horodatages UTC, montants
  `(amount, currency)`. Un seul système de design (thème clair/sombre).
- **Développe** sur la branche de travail, **merge** sur `main` CI verte.

## Prompts réutilisables (à donner explicitement à un agent)

- `docs/prompts/orchestration-outils.md` — orchestrer Claude + Gemini + Notion +
  GitHub + Obsidian (comité 7 voix, règle de la source unique, veto quintuple).
- `docs/prompts/expert-ir.md`, `docs/prompts/expert-accounting.md` — agents
  experts métier.

## En fin de session (clôture — fait partie de la tâche)

Coche la To-Do Notion **avec la preuve** (commit, chiffre, test) ; mets à jour la
doc concernée ; commit + push + merge ; termine ta réponse par :
**« Quelle est la prochaine priorité dans Notion ? »**
