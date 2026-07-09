# Ontologie fédérée

Vocabulaire commun du mesh. Gestion **fédérée** : chaque terme a un domaine
steward ; toute évolution passe par une PR touchant ce fichier, revue par les
domaines consommateurs. Le registre (`mesh/registry.py`) **rejette** tout
contrat dont le schéma de sortie utilise un terme absent d'ici — c'est ce qui
rend l'ontologie contraignante et non décorative.

## Entités

| Terme | Steward | Définition contraignante |
|---|---|---|
| `Transaction` | Trading | Mouvement économique atomique et daté entre deux `Counterparty`, portant un `Instrument`, un montant et une devise. Une transaction est immuable ; une correction est une nouvelle transaction de contre-passation. |
| `Trade` | Trading | Spécialisation de `Transaction` : accord d'échange d'un `Instrument` avec état de cycle de vie (`pending` → `executed` → `settled` \| `cancelled`). |
| `Instrument` | Trading | Actif ou contrat négociable identifié par un identifiant public (ISIN prioritaire, sinon identifiant interne préfixé `INT:`). |
| `Counterparty` | Risque | Entité juridique face à laquelle une exposition existe. Identifiée par LEI si disponible. |
| `Position` | Risque | Agrégat net des `Trade` sur un `Instrument` pour un périmètre donné, à un instant donné. Toujours dérivée, jamais saisie. |
| `Exposure` | Risque | Perte potentielle face à une `Counterparty` ou un facteur de risque, avec méthode de calcul référencée. |
| `CashPosition` | Trésorerie | Solde d'un compte bancaire réel à une date de valeur, réconcilié ou non (`reconciled: bool`). |
| `Settlement` | Trésorerie | Mouvement de cash ou de titres dénouant un `Trade`. |
| `AuditAssertion` | Audit | Affirmation vérifiable sur un Data Product (ex. « les CashPosition du 2026-06-30 sont réconciliées à 100 % »), avec statut `certified` \| `qualified` \| `failed`, horodatage et référence de preuve dans le journal chaîné. |
| `Client` | Client Lifecycle | Personne morale (ou physique) en relation d'affaires, identifiée par un identifiant client unique — et par LEI quand elle est aussi `Counterparty`. |
| `KycProfile` | Client Lifecycle | Dossier de connaissance d'un `Client` : notation de risque (`low` \| `medium` \| `high`), statut PEP, pays de résidence, date de dernière revue. Donnée personnelle (RGPD) : classification `restricted` obligatoire. |
| `AmlAlert` | Client Lifecycle | Signal de vigilance LCB-FT sur l'activité d'un `Client`, avec score explicable et statut de traitement. Toujours dérivée, jamais saisie ; la décision (escalade / classement) est humaine et journalisée. |
| `JournalEntry` | Comptabilité | Ligne d'écriture en **partie double** (compte, sens débit/crédit, montant, référence), toujours dérivée d'un `Settlement` ou d'un `Trade` — jamais saisie. L'équilibre débits = crédits par devise est un invariant contrôlé quotidiennement ; tout flux inexpliqué passe par le compte d'attente. |
| `RegulatoryRule` | Regulatory | Règle de conformité versionnée, exprimée en code, référençant la norme source (texte + article). |
| `Filing` | Regulatory | Rapport réglementaire généré, référençant les `AuditAssertion` qui certifient ses données sources. |

## Invariants transverses

1. Tout montant est un couple `(amount, currency)` — jamais un nombre nu.
   Devise en ISO 4217.
2. Tout horodatage est UTC, ISO 8601.
3. Toute donnée publiée vers l'extérieur (Regulatory, IR) doit référencer au
   moins une `AuditAssertion` de statut `certified`.
4. `Position` et `Exposure` sont dérivées : leur contrat doit déclarer leurs
   produits sources (lineage obligatoire).

## Procédure d'évolution

1. PR modifiant ce fichier + les contrats impactés dans le même commit.
2. Revue obligatoire du steward et d'au moins un consommateur.
3. Un terme ne se supprime jamais : il se déprécie (`deprecated:` + terme de
   remplacement), le registre avertit pendant une version puis rejette.
