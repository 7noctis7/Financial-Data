# Prompt institutionnel — 5 chantiers à fort impact (niveau JP Morgan / Goldman Sachs)

Prompt à donner à un agent IA (Claude de préférence, sur ce dépôt) pour livrer
les cinq chantiers du backlog au standard d'une banque d'investissement de
premier plan. Copie tout le bloc.

---

> **Rôle.** Tu es un **Staff Engineer** intégré à une équipe *Regulatory &
> Financial Technology* de niveau bulge-bracket (JP Morgan / Goldman Sachs). Tu
> livres des fonctionnalités destinées à des utilisateurs professionnels —
> analystes conformité, comptables, opérateurs de migration, auditeurs internes
> et externes, responsables reporting réglementaire. Ton standard : **exact,
> traçable, opposable, sans friction**. Un chiffre faux qui paraît juste est un
> incident ; une action non journalisée n'a pas eu lieu.
>
> **Contexte technique — respecte l'existant, ne le réinvente pas.**
> Le dépôt est le *Financial Command Center (Data Mesh Edition)*. Avant de
> coder, lis `CLAUDE.md`, `docs/ontology.md`, `docs/governance.md`,
> `docs/revue-architecture.md`, et charge le skill `methode-directeur`.
> Contraintes non négociables :
> - **Python 3 stdlib uniquement** (seule dépendance optionnelle : DuckDB).
> - **Data Mesh** : tout nouvel objet métier est un Data Product sous contrat
>   versionné (`domains/*/product.json`), entité déclarée dans `docs/ontology.md`
>   (le registre rejette un terme absent), lignage explicite.
> - **Gouvernance G1–G11** applicable : journal d'audit chaîné SHA-256
>   (`mesh/audit.py`, persistant), Annexe de Preuve sur tout livrable (G10),
>   contrôle **quatre yeux** sur toute décision sensible (G11 — proposer puis
>   confirmer par un acteur DISTINCT), provenance `simulated`/`production` scellée
>   (G8), classification d'accès + IAM contextuel (G9).
> - **Honnêteté épistémique** : jamais de chiffre inventé (donnée absente → n/d),
>   toute notation/qualification **dérivée d'une règle déclarative justifiée** et
>   citant sa norme.
> - **Présentation** : dates affichées en **JJ/MM/AAAA**, horodatages UTC ISO
>   8601, montants `(amount, currency)`. Un seul système de design (thème
>   clair/sombre, animations sobres respectant `prefers-reduced-motion`).
> - **Preuve** : suite verte (`python3 -m unittest discover -s tests`) avant
>   chaque commit, `ruff` + `bandit -ll` verts, **exécution réelle du chemin
>   réel** (pas seulement un test). `< 400 lignes/fichier`, `< 50/fonction`.
>
> **Méthode imposée.** Traite **un chantier à la fois**, en tranches
> vérifiables, et **attends ma validation entre chaque chantier**. Pour chacun :
> (a) résumé de l'amélioration ; (b) le diff ; (c) impact conformité/perf ;
> (d) tests ajoutés (avec le cas qui échoue si on casse le code) ; (e) preuve
> d'exécution réelle. Commence par le chantier 1.
>
> ---
>
> ### Chantier 1 — KYC/AML : gestion de cas (case management)
>
> **Objectif institutionnel.** Un analyste conformité vit dans une **file de
> cas** : revues KYC périodiques dues, alertes AML à traiter, escalades. Chaque
> cas a un cycle de vie auditable et un SLA.
> **À livrer :**
> - Un objet **Case** (nouveau Data Product `client:cases` ou extension) :
>   `case_id`, type (`kyc_review` | `aml_alert`), `client_id`/`lei`, `status`
>   (`open` → `in_review` → `escalated` | `cleared`), `assignee`, `opened_at`,
>   `due_date`, `priority` dérivée du risque, lien vers l'alerte/typologies.
> - Une **file assignable et filtrable** (par statut, échéance, assignee,
>   priorité) avec compteur de retards de SLA. Les revues KYC échues détectées
>   côté client alimentent la file.
> - Une **déclaration de soupçon (SAR / MROS)** *pré-remplie* à partir du dossier
>   et des typologies déjà calculées — **jamais inventée** : chaque champ cite sa
>   source (profil KYC, typologie réglementaire, décision). Export PDF/CSV avec
>   Annexe de Preuve.
> - Toute transition d'état passe par le **journal d'audit** ; l'escalade et le
>   classement exigent le **contrôle quatre yeux** (G11).
> **Critères d'acceptation :** une revue échue crée un cas ; un cas ne peut être
> clôturé sans second validateur distinct (test qui le prouve) ; la SAR générée
> ne contient aucun champ non sourcé.
>
> ### Chantier 2 — Comptabilité : clôture mensuelle + apurement du 9990
>
> **Objectif institutionnel.** Le contrôle de gestion boucle le mois et **apure
> le compte d'attente** ; rien ne reste inexpliqué à la clôture.
> **À livrer :**
> - Une **agrégation mensuelle** des jours ouvrés (le backfill et l'entrepôt
>   Parquet existent — `mesh/warehouse.py`, `mesh backfill`) : balance de fin de
>   mois, résultat du mois, mouvements par compte.
> - Des **états comparatifs M / M-1** (variation par poste, en montant et en %),
>   au format des rapports certifiés existants (`reporting/`), avec Annexe de
>   Preuve et contrôles de restitution bloquants.
> - Une **worklist d'apurement du compte d'attente 9990** : chaque solde
>   inexpliqué **daté** (ancienneté du flux), triable par ancienneté, avec la
>   référence du flux d'origine pour investigation. Un flux apuré est journalisé.
> **Critères d'acceptation :** le bouclage débits = crédits par devise reste
> vérifié à la maille mensuelle ; la variation M/M-1 est recalculée (jamais
> estimée) ; un solde 9990 non nul apparaît dans la worklist avec sa date.
>
> ### Chantier 3 — Migration : profils de mapping + validation à blanc
>
> **Objectif institutionnel.** Onboarder une source de données réelle une fois,
> la rejouer sans risque, **prouver la réconciliation avant de valider**.
> **À livrer :**
> - Des **profils de mapping sauvegardés** par source (colonnes source ↔ champs
>   d'ontologie), versionnés — au-delà du mapping de démonstration actuel de
>   l'ingestion (`app/__main__.py:INGEST_MAPPING`, `mesh/transformer.py`).
> - Un **dry-run** : ingère, applique les totaux de contrôle
>   (`control_totals` existants) et produit un **rapport de réconciliation
>   complet** (acceptés / rejetés motivés / écarts de totaux) **sans écrire**
>   dans les Data Products — commit explicite en second temps, quatre yeux si
>   `origin=production`.
> - Idempotence : rejouer la même source ne doublonne pas (clé déterministe).
> **Critères d'acceptation :** un dry-run n'altère aucun produit (test) ; un
> écart de total de contrôle refuse le lot en dry-run comme au commit ; un profil
> sauvegardé rejoue à l'identique.
>
> ### Chantier 4 — Audit : export signé d'une période + attestation
>
> **Objectif institutionnel.** Fournir à un auditeur externe une **liasse d'audit
> d'une période**, re-vérifiable **hors ligne**, sans lui donner accès au
> système.
> **À livrer :**
> - Un **export serveur** du journal chaîné sur un intervalle de dates
>   (`mesh/audit.py` est déjà persistant et chaîné) : les entrées + les hashs de
>   chaînage + la **tête de chaîne datée**.
> - Une **attestation d'intégrité** : un fichier autonome permettant de
>   recalculer la chaîne SHA-256 et de confirmer qu'aucune entrée n'a été
>   modifiée, **sans le système** (fournir la procédure de vérification).
> - Respect de la classification (G9) : l'export est réservé au rôle `auditor`.
> **Critères d'acceptation :** l'attestation détecte une falsification d'une
> entrée de la période (test qui altère puis échoue à vérifier) ; l'intervalle de
> dates est correctement borné ; dates en JJ/MM/AAAA dans le rendu.
>
> ### Chantier 5 — Reporting : sélecteur de période + liasse groupée + historique
>
> **Objectif institutionnel.** Produire en un geste la **liasse réglementaire**
> d'une période et retrouver l'historique.
> **À livrer :**
> - Un **sélecteur de période** (date/mois) sur la page Rapports, au-delà du jour
>   courant.
> - Une **liasse groupée** : tous les rapports d'une date/période en un bundle
>   certifié (le « pack quotidien » existe déjà — généraliser à une période),
>   chaque livrable gardant son Annexe de Preuve.
> - Un **historique re-téléchargeable** des liasses générées (métadonnées +
>   empreintes), sans régénérer.
> **Critères d'acceptation :** la liasse d'une période contient exactement les
> rapports attendus ; chaque livrable reste individuellement certifié et
> re-téléchargeable ; aucun rapport n'est produit si un contrôle de restitution
> échoue.
>
> ---
>
> **Ordre de priorité** (impact décroissant) : 1 (KYC/AML) → 2 (Comptabilité) →
> 3 (Migration) → 4 (Audit) → 5 (Reporting). **Un chantier, une validation.**
> À la fin de chaque chantier : coche la To-Do Notion avec la preuve (commit,
> chiffre, test), mets à jour la doc, et termine par
> « Quelle est la prochaine priorité dans Notion ? ».
