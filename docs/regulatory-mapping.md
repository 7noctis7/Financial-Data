# Regulatory Mapping — Rapport ↔ Régulateur / Norme source

Compliance-by-Design : chaque rapport du Reporting Engine est mappé à sa
norme source et aux Data Products qui l'alimentent. Un rapport sans ligne
dans ce tableau n'existe pas ; une ligne sans produits alimentants est un
objectif de roadmap, pas une promesse.

## Tableau de correspondance

| Rapport | Régulateur / Émetteur | Norme source | Data Products sources | Statut |
|---|---|---|---|---|
| **AnaCredit** | BCE | Règlement (UE) 2016/867 | `trading:executed-trades` + *credit:loans* (roadmap) | 🔜 nécessite le domaine Crédits |
| **EMIR** (déclaration dérivés) | ESMA | Règlement (UE) 648/2012, RTS/ITS 2017 | `trading:executed-trades` (IRS, FX forwards) | ✅ gabarit implémenté (`python3 -m reporting emir ...`) — soumission réelle sous G8 |
| **MiFID II / MiFIR** (transaction reporting) | ESMA / AMF | Directive 2014/65/UE, RTS 22 | `trading:executed-trades` | ✅ gabarit implémenté (`python3 -m reporting mifid2 ...`) — soumission réelle sous G8 |
| **FinFrag** (dérivés suisses) | FINMA | LIMF/FinfraG RS 958.1, Circ. FINMA 2018/... | `trading:executed-trades` | 🟡 équivalent EMIR suisse — même socle |
| **LSFin / FIDLEG** (conduite, information client) | FINMA | LSFin RS 950.1 | *client:kyc* (roadmap), `audit:assertions` | 🔜 nécessite le domaine Client Lifecycle |
| **CRS** (échange automatique) | OCDE / AFC | Norme commune de déclaration OCDE | *client:kyc* (roadmap), `treasury:cash-positions` | 🔜 nécessite le domaine Client Lifecycle |
| **FATCA** | IRS (US) / accords IGA | 26 U.S.C. §1471–1474 | *client:kyc* (roadmap), `treasury:cash-positions` | 🔜 idem CRS |
| **IFRS 9** (provisionnement ECL) | IASB / arrêté des comptes | Norme IFRS 9 | `risk:exposures`, *credit:loans* (roadmap) | 🔜 nécessite historique + défauts |
| **Bâle IV** (fonds propres, ratios) | BCBS / BCE / FINMA | Bâle III finalisé (« IV »), CRR III | `risk:exposures`, `treasury:cash-positions` | 🟡 expositions v1 = brutes ; netting/pondérations à modéliser |
| **Rapport quotidien interne** | — | Politique interne (template `regulatory`) | `risk:exposures` certifié par `audit:assertions` | ✅ implémenté (`python3 -m reporting regulatory ...`) |

## Règles d'implémentation

1. **Un rapport = un template** dans `templates/reporting/` portant :
   la référence normative (`norm_ref`), la classification d'accès (G9)
   et les assertions ISA exigées (G10). Le `ReportGenerator` refuse tout
   livrable dont les assertions ne sont pas `certified` et ancrées.
2. **Un rapport réglementaire réel exige `origin=production`** (G8) :
   sur données simulées, seul un `DRYRUN-` est possible — c'est le mode
   de validation des pipelines (stress-test du rapport sans risque).
3. **La traduction d'une norme est manuelle et revue** (une `RegulatoryRule`
   versionnée par exigence), jamais générée automatiquement — le RAG
   réglementaire (roadmap) aide à la rédaction, il ne publie pas.

## Domaines cibles (extension du catalogue)

Le catalogue v1 (Trading, Trésorerie, Risque, Audit, Regulatory) s'étend
vers la chaîne de valeur complète — chaque domaine n'est créé que
lorsqu'il a un flux et un propriétaire :

| Domaine cible | Data Products envisagés | Débloque |
|---|---|---|
| **Crédits (Core Banking)** | `credit:loans`, `credit:collateral` | AnaCredit, IFRS 9 |
| **Client Lifecycle** | `client:kyc`, `client:aml-alerts`, `client:fees` | CRS, FATCA, LSFin, pré-diagnostic AML |
| **Titres & PMS** | `securities:positions`, `pms:portfolios`, `pms:custody-fees` | MiFID II coûts/frais, droits de garde |
| **Paiements** | `payments:transactions` | LCB-FT, monitoring fraude |
