# Chaîne de confiance : exhaustivité, exactitude du mapping, automatisation

Réponse à la problématique : « comment s'assurer que les données insérées
dans l'application sont complètes, puis CORRECTEMENT mappées dans chaque
template (comptable, IR, réglementaire) — et automatiser en confiance ? »

Principe directeur : **on ne fait pas confiance à une étape, on vérifie
chaque frontière**. La confiance globale est le produit de cinq maillons,
chacun contrôlé par du code (jamais par une convention).

## Maillon 1 — Entrée : rien n'entre sans compter (exhaustivité amont)

| Garantie | Mécanisme (existant) |
|---|---|
| Chaque ligne reçue est acceptée OU rejetée avec motif — jamais perdue | `DataTransformer` : `reçues = acceptées + rejetées`, motifs conservés |
| L'entrée est rejouable et prouvable | SHA-256 du fichier source scellé dans le journal chaîné (G3) |
| L'intraduisible ne devient jamais une devinette | couche anti-corruption des connecteurs : rejet explicite |
| Une source qui dérive est isolée, pas ignorée | disjoncteurs (fraîcheur + taux de violation, G5) |

**Contrôle d'exhaustivité à exiger de toute source réelle** : le fichier
d'entrée doit porter (ou être accompagné de) ses **totaux de contrôle**
(nombre de lignes, somme des montants par devise). Le transformer compare
et refuse en cas d'écart — c'est l'extension n°1 à faire (voir plan).

## Maillon 2 — Traversée : la partie double comme détecteur universel

Le grand livre est le filet de sécurité central : tout flux financier
finit en écriture équilibrée, et **tout inexpliqué atterrit au compte
d'attente 9990** — visible en rouge, jamais absorbé. Le contrôle de
bouclage (débits = crédits par devise) est structurel : si une donnée se
perd en route, le bilan ne boucle plus ou l'attente gonfle. S'ajoutent la
réconciliation trades ↔ relevés (écarts exhibés) et la provenance
transitive (G8).

## Maillon 3 — Certification : les six assertions ISA par produit

Chaque jour ouvré, chaque Data Product reçoit une assertion
(`certified` / `qualified`) ancrée dans le journal chaîné — dont
**Exhaustivité** est littéralement l'une des six. Un rapport dont une
assertion exigée n'est pas `certified` **ne se génère pas** (G10).
L'exhaustivité n'est donc pas une intention : c'est une condition de
compilation du rapport.

## Maillon 4 — Restitution : le mapping est du code versionné + contrôlé

Le risque « mal mappé dans le template » se traite en trois couches :

1. **Mapping déclaratif et versionné** : compte 1010 → « Disponible »,
   nostros → ligne 040 FINREP… vivent dans le code/les templates JSON,
   revus en PR — jamais dans un copier-coller manuel.
2. **Cohérence par construction** : les totaux du template sont calculés
   depuis les lignes filles (F 01.01 : 380 = 010+050+360), pas saisis.
3. **Contrôles de restitution** (le maillon à généraliser) : pour chaque
   rapport généré, vérifier automatiquement :
   - *bouclage de périmètre* : total du rapport = total de la requête
     source, au centime ;
   - *recalcul des agrégations* (règles de validation EBA pour
     FINREP/COREP) ;
   - *cohérence inter-états* : F 01.01 ↔ grand livre ; PnL/Flux ↔ Δ bilan ;
     chiffres IR ↔ états certifiés dont ils proviennent ;
   - échec d'un contrôle ⇒ le rapport sort en `qualified`, jamais en
     silence.

## Maillon 5 — Preuve : tout est re-vérifiable après coup

Annexe de Preuve inséparable (norme, horodatage, demandeur, SHA-256,
hash des assertions), journal chaîné re-vérifiable (`verify_chain`),
refus IAM tracés. Si un chiffre est contesté six mois plus tard, on
remonte du PDF au hash, du hash à l'assertion, de l'assertion à la
requête, de la requête à la donnée source — sans intervention humaine.

## Plan d'implémentation (ordre de valeur)

1. **Totaux de contrôle à l'ingestion** : le transformer exige
   `expected_rows` / `expected_sum` par devise, refuse l'écart (maillon 1).
2. **Moteur de contrôles de restitution** : bloc `controls` déclaratif
   dans chaque template JSON (`sum_equals`, `recompute_totals`,
   `cross_report`), exécuté par le ReportGenerator, résultat écrit dans
   l'Annexe de Preuve (maillon 4.3).
3. **Panneau KRI** sur le dashboard : compte d'attente, écarts de recon,
   assertions `qualified`, rejets d'ingestion — la confiance devient
   visible en un coup d'œil.
4. Règles de validation EBA codées pour F 01.01 puis C 07.00.

La réponse courte à « comment avoir confiance ? » : **parce qu'à chaque
frontière, un contrôle codé compte, boucle ou refuse — et que chaque
refus laisse une trace chaînée.** L'automatisation n'est sûre que parce
qu'elle sait dire non.
