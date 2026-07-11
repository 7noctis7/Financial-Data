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
| `ScreeningHit` | Client Lifecycle | Correspondance potentielle entre un `Client` et une entrée de liste de surveillance (sanctions, PEP, médias défavorables), portant un score de similarité explicable, la version de la liste et les identifiants secondaires comparés. Toujours dérivée (matching flou), jamais saisie ; sa résolution (vrai match / faux positif) est humaine, journalisée, et un faux positif résolu est supprimé des criblages suivants tant que la liste ne change pas de version. |
| `Case` | Client Lifecycle | Dossier de traitement d'une diligence : revue KYC échue (`kyc_review`) ou alerte AML (`aml_alert`). Porte un statut (`open` → `in_review` → `escalated` \| `cleared`), un responsable, une échéance SLA et une priorité **dérivée** du risque (notation KYC ou score/typologies de l'alerte). Son existence et sa priorité sont dérivées de la donnée (jamais saisies) ; ses transitions sont journalisées, l'escalade et le classement sous double validation (G11). |
| `JournalEntry` | Comptabilité | Ligne d'écriture en **partie double** (compte, sens débit/crédit, montant, référence), toujours dérivée d'un `Settlement` ou d'un `Trade` — jamais saisie. L'équilibre débits = crédits par devise est un invariant contrôlé quotidiennement ; tout flux inexpliqué passe par le compte d'attente. |
| `Fee` | Client Lifecycle | Commission ou frais facturé à un `Client` (courtage, tenue de compte, droits de garde), toujours dérivé d'un `Trade` ou d'un service tarifé — barème versionné, jamais saisi. |
| `MarketPrice` | Marché | Prix de clôture (`close`) d'un `Instrument` à une date donnée, accompagné du cours de clôture précédent (`prev_close`) et de la source du cours. Un prix sans source ni horodatage n'existe pas pour le mesh. |
| `Valuation` | Risque | Valorisation **mark-to-market** d'une `Position` : variation de valeur du jour, dérivée d'un `MarketPrice` (close vs prev_close) appliquée au notionnel vivant, avec méthode de calcul référencée. Toujours dérivée, jamais saisie. |
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
