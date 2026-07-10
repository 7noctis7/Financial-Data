# Plan de catégorie — SaaS IA KYC/AML
## Rapport du comité des huit sièges (exécution de `docs/prompts/licorne-kyc-aml.md`)

> Étiquetage : `[FAIT]` sourçable · `[ESTIMATION]` méthode + fourchette ·
> `[HYPOTHÈSE]` à tester (test fourni) · `[RECO]` décision proposée.
> Date d'exécution : 10/07/2026. Les valorisations et chiffres de marché
> sont à re-vérifier au jour de toute utilisation externe.

---

# PHASE 1 — L1–L3, soumis aux huit vetos

## L1 — Thèse & wedge

**Mission.** Rendre la conformité LCB-FT opérable par des équipes 10× plus
petites, avec une piste d'audit que les régulateurs préfèrent à celle des
processus manuels qu'elle remplace.

**Pourquoi maintenant — trois forces datées, pas une de plus :**
1. **AMLR/AMLA (application 2027)** `[FAIT]` : le paquet AML européen
   harmonise et durcit les obligations ; l'AMLA supervisera directement les
   assujettis les plus risqués. Des milliers d'EMI/PI/CASP doivent
   industrialiser en < 24 mois ce qu'ils font aujourd'hui sous Excel.
2. **Le coût du triage intelligent s'est effondré** `[FAIT]` : ce qui
   exigeait une équipe data science interne (NLP d'adverse media, synthèse
   de dossier, scoring explicable) est devenu un coût d'inférence
   marginal — MAIS les incumbents (Actimize, SAS) ne peuvent pas le
   rétrofitter sans cannibaliser leurs services professionnels.
3. **La pénurie d'analystes conformité** `[FAIT, constaté par le marché]` :
   les salaires montent, le turnover épuise les MLRO ; la productivité par
   analyste est LE poste de coût attaquable.

**LE wedge choisi `[RECO]` : le poste de travail de l'analyste AML —
triage d'alertes assisté + case management + SAR sourcée — pour les
EMI, PI, néobanques et CASP européens (50–5 000 alertes/mois).**

Ce que le pilote livre en semaine 1 : la file d'alertes de l'établissement,
priorisée et expliquée, chaque décision journalisée en chaîne immuable,
la SAR pré-remplie champ par champ avec sa source. (C'est exactement le
périmètre déjà prototypé dans ce dépôt : criblage explicable, typologies
citées, cas SLA, 4-yeux, SAR sourcée — le démonstrateur est le germe.)

**Deux alternatives rejetées (et pourquoi) :**
- *IDV/biométrie d'onboarding* : guerre des prix installée
  (Sumsub/Veriff/Onfido/Jumio), différenciation par le coût unitaire,
  CAPEX modèles vision élevé, AI Act haut risque maximal → wedge rejeté,
  intégration partenaire à la place.
- *Remplacement frontal d'Actimize/SAS en banque tier-1* : cycles 18–36
  mois, migration de règles legacy, risque d'exécution mortel pour une
  équipe pre-seed → segment reporté (année 4+, tiré par les références).

**Kill-list (on ne construit PAS avant l'année 3) :** analytics
blockchain (Chainalysis/TRM gagnent), fraude paiement temps réel <100 ms
(Feedzai/Sardine), IDV biométrique propriétaire, marché US (NYDFS 504 et
BSA = produit dédié), core screening sanctions propriétaire (on consomme
des listes sous licence — Dow Jones/OpenSanctions —, on ne les fabrique
pas), mobile natif.

## L2 — Marché

**TAM/SAM/SOM — double méthode croisée.**
- *Top-down* : marché mondial des logiciels AML/conformité financière
  ~3–5 Md$/an, croissance ~15 %/an `[ESTIMATION, fourchette des analystes
  sectoriels]`.
- *Bottom-up (méthode retenue, plus honnête)* :
  - EMI + établissements de paiement agréés UE/EEE+UK : ~2 500–3 000
    `[ESTIMATION, registres EBA/FCA]` ;
  - néobanques/banques digitales Europe : ~300–450 `[ESTIMATION]` ;
  - CASP/PSAN enregistrés (MiCA) : ~1 500–2 500 `[ESTIMATION]` ;
  - banques UE de taille moyenne (cible année 3+) : ~2 000 `[ESTIMATION]`.
  - ACV wedge : 30–90 k€/an selon volume d'alertes `[HYPOTHÈSE H1]`.
  - **SAM wedge Europe ≈ 6 000 comptes × ACV moyen 50 k€ ≈ 300 M€/an**
    `[ESTIMATION]` ; SOM à 5 ans : 2–4 % du SAM = 6–12 M€ ARR (cohérent
    avec le scénario base L8, ce qui valide la boucle).

**Tableau concurrents (obligatoire) :**

| Acteur | Position | Pricing (public/estimé) | Faille exploitable |
|---|---|---|---|
| ComplyAdvantage | screening + monitoring API-first | consommation, opaque `[ESTIMATION]` | case management faible ; l'enquête reste chez le client |
| Unit21 | no-code monitoring/case mgmt US | plateforme `[ESTIMATION]` | présence UE mince, pas AMLA-native |
| Napier AI / Hawk AI | monitoring IA banques mid | licence + volume | cycle enterprise ; peu adapté EMI 5–50 personnes |
| Lucinity | copilote enquêteur | plateforme | proche de nous : à battre sur l'audit-trail opposable et le prix d'entrée |
| Salv | monitoring baltique, collaboration | abordable | profondeur IA limitée `[ESTIMATION]` |
| Sumsub/Veriff | IDV dominant, s'étendent vers l'AML | par vérification | l'AML "ajouté" n'est pas leur cœur ; partenariat possible puis rivalité |
| Actimize/SAS/Oracle | incumbents banques | 7 chiffres + intégration | coût, faux positifs, 18 mois de déploiement — notre argumentaire |
| LSEG World-Check / Dow Jones | données de screening | licence données | fournisseurs, pas concurrents : on s'intègre |

**Comps de calibrage** `[ESTIMATION, à vérifier]` : Onfido→Entrust
(~650 M$, 2024) ; Socure (~4,5 Md$, 2021) ; Alloy (~1,55 Md$, 2022) ;
Chainalysis (~8,6 Md$, 2022) ; Feedzai licorne (2021). Multiples RegTech
croissance : ARR × 8–15. Une sortie 300–600 M€ exige ~30–50 M€ ARR — le
plan L8 vise ce couloir, pas « la licorne en 3 ans ».

**Fenêtre** : 2025–2028. Avant : pas de contrainte AMLA chiffrée. Après :
les gagnants du wedge seront installés et l'AMLA aura sacré des standards
de facto.

## L3 — Personas & problèmes

| Persona | Job-to-be-done | Verbatim (plausible, recueilli en discovery à valider H2) | Métrique défendue |
|---|---|---|---|
| **Analyste AML** (utilisateur quotidien) | vider la file d'alertes sans rien rater | « Je passe 80 % de mon temps à fermer des alertes dont je sais en 30 secondes qu'elles ne valent rien — mais je dois le documenter pendant 15 minutes. » | alertes traitées/jour ; qualité de documentation |
| **MLRO / Head of FinCrime** (acheteur) | dormir avant l'inspection | « Mon cauchemar n'est pas de rater un blanchisseur, c'est de ne pas pouvoir PROUVER que mon dispositif est cohérent. » | backlog d'alertes ; délais SAR ; findings d'audit |
| **DPO** (droit de veto interne) | minimisation, bases légales | « Où vont les données, qui y touche, combien de temps ? » | registres, DPIA |
| **COO fintech** (payeur) | coût de conformité par client onboardé | « La conformité est mon 2ᵉ poste de coût après l'acquisition. » | coût/dossier ; headcount évité |
| **Auditeur externe / superviseur** (utilisateur indirect) | reconstituer les décisions | « Montrez-moi POURQUOI cette alerte a été classée, par qui, sous quelle règle. » | complétude de la piste d'audit |

**Problèmes classés (fréquence × coût × urgence) :**

| # | Problème | Fréq. | Coût | Urgence | Score |
|---|---|---|---|---|---|
| P1 | 90–98 % de faux positifs au monitoring `[FAIT, littérature]`, 20–50 €/revue `[ESTIMATION]` | quotidienne | massif | AMLA | ★★★★★ |
| P2 | documentation de décision manuelle, hétérogène, indéfendable en audit | quotidienne | élevé | inspections | ★★★★★ |
| P3 | SAR/STR : rédaction 2–6 h/dossier, qualité variable | hebdo | élevé | légal | ★★★★ |
| P4 | revues KYC périodiques en retard (backlogs de milliers de dossiers) | mensuelle | moyen | findings | ★★★★ |
| P5 | outillage fragmenté (screening ici, cas là, Excel partout) | quotidienne | moyen | opérationnel | ★★★ |

---

## PASSAGE DES HUIT VETOS (L1–L3)

| Siège | Verdict | Objection → révision imposée |
|---|---|---|
| CEO catégorie | ✅ | wedge = catégorie « FinCrime Operations » naissante, pas une feature |
| CPO wedge | ✅ | exiger la métrique semaine-1 du pilote : « −50 % de temps de documentation par alerte » — ajoutée en L4 |
| **MLRO** | ⚠️ levé après révision | « Le triage IA qui CLASSE tout seul est invendable en inspection. » → **décision D1 modifiée : l'IA suggère et pré-documente, elle ne clôt JAMAIS seule** (répercuté L5/L6) |
| Chief AI | ✅ | sous condition : harnais d'éval avec dataset gelé dès le pilote 1 (L6) |
| CISO/DPO | ⚠️ levé après révision | hébergement UE + isolation par tenant dès le MVP, pas « plus tard » → coût MVP +1 mois (L7, L10) |
| CRO | ✅ | pilotes PAYANTS (10–20 k€) sinon signal de valeur nul (L9) |
| VC | ⚠️ levé après révision | « per-alert pricing » gameable et anti-scalable → **décision D2 modifiée : plateforme + paliers de volume, jamais du pur à-l'acte** (L8) |
| Régulateur | ⚠️ levé après révision | interdiction du mot « conformité automatique » dans tout le matériau ; l'humain signe chaque décision réglementée → **décision D3 : positionnement « augmentation », charte d'usage IA publique** (L9) |

Quatre vetos ont modifié le plan (D1, D2, D3 + hébergement UE MVP) — la
suite L4–L10 intègre ces révisions.

---

# PHASE 2 — L4–L10

## L4 — Produit

**Le flux wedge, écran par écran (semaine 1 du pilote) :**
1. **File de travail** : alertes + cas priorisés (risque × SLA), filtres
   sauvegardés, recherche globale, charge par analyste. KPI de tête :
   backlog, retards SLA, taux de faux positifs mesuré (décisions
   « classé » / alertes — affiché, avec sa dérive).
2. **Dossier 360°** : client (KYC, notation JUSTIFIÉE par règle),
   transactions liées, historique d'alertes et décisions, documents
   versionnés, graphe de contreparties (v1 : liens directs).
3. **Décision assistée** : l'IA pré-documente (résumé, typologies
   candidates AVEC références réglementaires citées, éléments à charge/
   décharge sourcés) ; l'analyste décide ; la justification est générée,
   éditable, et signée par lui (D1). Escalade/classement sous 4-yeux
   configurable.
4. **SAR/STR** : pré-remplie champ par champ, chaque champ portant sa
   source ; goAML/formats nationaux en export ; jamais transmise sans
   double validation humaine.
5. **Vue MLRO** : entonnoir (criblés→alertes→cas→SAR), retards, qualité
   de documentation, registre des décisions — l'écran qu'il montre à
   l'inspecteur.

**Socle transverse (exigences, pas features)** — audit trail immuable
(qui/quoi/avant/après/justification/approbateur, horodaté, exportable,
signé), versionnage avec diff/restauration sous droits, 4-yeux
configurable (N niveaux, délégations, SLA, escalades), RBAC granulaire
(rôles, équipes, géos, fenêtres temporelles), imports validés-normalisés-
dédoublonnés-journalisés (CSV/Excel/JSON/XML/API/SFTP/webhooks), exports
planifiables-signés-historisés, édition directe sous permissions +
4-yeux + réversibilité, moteur de workflow no-code (conditions, branches,
SLA, notifications, tâches IA), recherche globale.

**Tableau capacités (extrait décisionnel) :**

| Capacité | Valeur métier | Exigence couverte | Coût | MoSCoW |
|---|---|---|---|---|
| File + triage assisté | −50 % temps/alerte `[HYPOTHÈSE H3]` | dispositif « adéquat » AMLD/AMLR | L | **Must** |
| Audit trail immuable | inspection sans sueur | AMLR, NYDFS 504 (futur) | M | **Must** |
| SAR sourcée + goAML | −70 % temps de rédaction `[HYPOTHÈSE H4]` | art. 9 LBA/équiv. UE | M | **Must** |
| 4-yeux configurable | contrôle interne opposable | gouvernance interne, Wolfsberg | M | **Must** |
| Workflow no-code | zéro dev pour changer un process | — | L | Should |
| Graphe réseaux avancé | détection structuration | FATF typologies | L | Should (V2) |
| Screening propriétaire | — | — | XL | **Won't** (données sous licence) |
| Mobile natif | — | — | M | **Won't** (an 1–2) |

## L5 — Pipelines (métriques cibles chiffrées)

**KYC (revue et remédiation — l'onboarding IDV reste partenaire) :**

| Étape | Cible | Dégradation | Norme |
|---|---|---|---|
| Création/import dossier | 100 % validé contre schéma, rejets motivés ligne à ligne | import refusé EN TOTALITÉ si totaux de contrôle faux | CDD |
| OCR/extraction (partenaire) | ≥ 98 % champs critiques `[ESTIMATION]` | file de saisie manuelle | — |
| Screening sanctions/PEP/adverse media (listes sous licence) | rappel ≈ 100 % sur listes, précision réglée par seuils | si fournisseur down : blocage des décisions, jamais de « pas de hit » silencieux | OFAC/UE/ONU, FATF R.12 |
| Notation risque | 100 % justifiée par règles versionnées (jamais de score nu) | — | approche par les risques |
| Revue périodique | event-driven (déclencheurs) + cycle par risque ; backlog visible | alarme MLRO à seuil | AMLR |

**AML :**

| Étape | Cible | Contre-mesure adverse |
|---|---|---|
| Ingestion transactions | temps quasi réel, contrôles de complétude | replay idempotent |
| Règles + ML | rappel maintenu, **faux positifs −40 à −60 % vs règles seules** `[HYPOTHÈSE H5, LA promesse à prouver]` | champion/challenger, dataset gelé |
| Triage IA | 100 % des alertes pré-documentées ; l'IA ne clôt jamais (D1) | taux d'acceptation humaine suivi ; < 70 % = revue du modèle |
| Graphe/réseaux | v1 liens directs ; V2 communautés | smurfing adaptatif : fenêtres et seuils randomisés |
| SAR | délai médian rédaction 6 h → < 1 h `[HYPOTHÈSE H4]` | qualité relue : échantillonnage 4-yeux |
| Feedback loop | chaque décision réentraîne le tri (avec validation humaine des labels) | poisoning : labels pondérés par ancienneté/rôle |

Attaques adverses couvertes : deepfake liveness (délégué au partenaire
IDV certifié), identités synthétiques (recoupement bureaux + graphe),
documents génératifs (partenaire + hash registres), structuring adaptatif
(cf. supra).

## L6 — IA & gouvernance des modèles

**Doctrine (quand quoi) :**
- **Règles déterministes** : seuils réglementaires, listes, invariants —
  tout ce qu'un inspecteur veut relire ligne à ligne.
- **ML classique explicable** (gradient boosting + SHAP) : scoring
  d'alerte, priorisation — performance mesurable, explication par
  facteurs.
- **LLM** : langage uniquement — synthèse de dossier, adverse media,
  pré-rédaction SAR, Q&A d'enquête. TOUJOURS avec sources citées,
  température basse, sortie contrainte.
- **Pas d'IA** : décision réglementée finale (classement, SAR, sortie de
  relation) = humaine, signée (D1).

**Agents (extrait) :**

| Agent | Automatisation | Harnais d'éval | Coût inférence/dossier |
|---|---|---|---|
| Triage d'alertes | pré-classe + documente, ne clôt pas | AUC, précision@rappel≥95 %, dérive mensuelle | ~0,01–0,05 € `[ESTIMATION]` |
| Copilote d'enquête | répond sourcé sur le dossier | exactitude factuelle sur dataset gelé ; hallucination = défaut bloquant | ~0,05–0,20 € |
| Rédacteur SAR | pré-remplit, chaque champ sourcé | % champs acceptés sans édition | ~0,10–0,30 € |
| QA de dossier | signale incohérences/incomplétudes | précision des signalements | ~0,02 € |
| Gouvernance interne | goulets, anomalies d'usage, risques de non-conformité opérationnelle | adoption des recommandations | négligeable |

Total inférence < 2 % du prix client `[ESTIMATION]` → marge brute > 75 %
tenable. Gouvernance : registre de modèles, validation indépendante
(esprit SR 11-7), documentation AI Act (système à haut risque assumé pour
le scoring), monitoring de dérive, kill-switch par modèle, explicabilité
en langage d'auditeur.

## L7 — Architecture & sécurité du SaaS

Multi-tenant à isolation forte (schéma-par-tenant en V1 — plus coûteux
mais vendable aux banques ; mutualisation fine plus tard), **hébergement
UE dès le MVP** (veto CISO), résidence UK/CH en option, API-first (REST +
webhooks ; GraphQL non — complexité non justifiée), event bus, stockage
chiffré champ-niveau pour PII, gestion de secrets avec rotation,
SSO/OIDC + MFA, Zero Trust interne, observabilité complète, CI/CD avec
SBOM et scans, SLA 99,95 %, RTO 4 h / RPO 15 min, DR testé
semestriellement. Journal d'audit : append-only chaîné par hachage,
ancrage externe quotidien, export signé (le prototype FCC valide déjà ce
pattern). Certifications : SOC 2 Type II (mois 9–15, ~60–100 k€
`[ESTIMATION]`) → ISO 27001 (an 2) → ISO 42001 (an 3, différenciant IA).
DORA nous concerne comme prestataire TIC : registre de sous-traitance,
tests de résilience, clauses contractuelles types.

```
[Clients web] ──> [API Gateway + WAF] ──> [Services : cas | triage | screening-proxy | workflow | audit]
                                   │                │
                             [Event bus] ── [Moteur IA (registre de modèles, éval, HITL)]
                                   │                │
        [PostgreSQL par tenant + coffre PII chiffré]   [Data lake anonymisé + vector store]
                                   │
                    [Journal d'audit chaîné + ancrage externe + exports signés]
```

**Tableau norme → produit → preuve (extrait) :**

| Exigence | Réponse produit | Preuve générée |
|---|---|---|
| AMLR dispositif documenté | règles versionnées + registre décisions | export « dispositif » horodaté |
| Art. 9 LBA / SAR UE | SAR sourcée champ à champ, 4-yeux | dossier de déclaration + trace |
| AI Act haut risque | doc technique modèle, surveillance humaine, logs | dossier de conformité IA |
| DORA (client ET nous) | SLA, DR testé, registre sous-traitants | rapports de tests |
| RGPD | minimisation, DPIA, rétention paramétrable, droit d'accès | registre de traitements |

## L8 — Business model & finance

**Pricing (D2 : jamais de pur à-l'acte)** : plateforme par palier de
volume d'alertes/entités surveillées (Starter 24 k€/an ; Growth 60 k€/an ;
Scale 120 k€+/an `[HYPOTHÈSE H1]`) + modules (workflow avancé, graphe,
API premium) + Enterprise (SSO, résidence dédiée, SLA renforcé, audit
sur site). Positionnement : 30–50 % sous Napier/Hawk à périmètre wedge
`[ESTIMATION]`, 3–5× au-dessus des outils « listes seules ».

**Unit economics cibles (an 3)** : ACV 50 k€ ; CAC 25–35 k€ (vente
assistée par contenu réglementaire) ; marge brute 75–80 % (inférence
comprise) ; NRR > 120 % (expansion par volume + modules) ; LTV/CAC > 4 ;
magic number > 0,7 ; **Rule of 40 atteint an 4** (croissance 60 % +
marge −15 % → 45).

**Projections 5 ans (trois scénarios, ARR fin d'année, M€) :**

| Scénario | A1 | A2 | A3 | A4 | A5 | Hypothèse pivot |
|---|---|---|---|---|---|---|
| Bear | 0,15 | 0,6 | 1,5 | 3 | 5,5 | H5 échoue partiellement (−25 % FP seulement) ; cycles 12 mois |
| **Base** | 0,25 | 1,2 | 3,5 | 8 | 16 | H1/H3/H5 tiennent ; 10 logos an 1→ ~90 comptes an 5 ; churn logo < 8 % |
| Bull | 0,4 | 2 | 6,5 | 15 | 30 | AMLA accélère ; partenariat distribution IDV signé an 2 |

Sensibilités dominantes : H5 (réduction faux positifs), durée de cycle de
vente, churn précoce des design partners, coût d'inférence (×3 = −6 pts
de marge), calendrier AMLA. **Financement** : pre-seed 0,8 M€ (MVP + 3
pilotes payants) → seed 3–4 M€ (10 clients, SOC 2, H5 prouvée sur données
réelles) → série A 12–15 M€ (2 M€ ARR, NRR démontré). Chaque tour achète
un dérisquage nommé, pas « de la croissance ».

## L9 — GTM & moat

**ICP initial** : EMI/PI/néobanque/CASP UE, 20–300 employés, 1–15
analystes conformité, 200–5 000 alertes/mois, stack actuel = screening
API + Excel/Jira ; déclencheurs d'achat : agrément récent, remédiation
demandée par le superviseur, croissance des volumes, audit raté.

**Séquence** : 3–5 design partners payants (10–20 k€ le pilote de 12
semaines, veto CRO) recrutés via le réseau conformité → beachhead
France/Benelux/Baltics-Nordics (superviseurs actifs, densité fintech) →
DACH/UK an 2–3 → banques mid an 3–4 sur références → US an 4+ (produit
NYDFS/BSA dédié).

**Canaux** : contenu réglementaire d'autorité (« le guide AMLA que les
Big 4 facturent 50 k€ », gratuit — machine à leads MLRO), cabinets
conformité et anciens superviseurs comme prescripteurs, intégrations
core-banking/BaaS (Mambu et équivalents), ACAMS/événements sectoriels,
analystes (Chartis, Celent). **Positionnement public (D3)** :
« augmentation de l'analyste », charte d'usage IA publiée — jamais
« conformité automatique ».

**Moat cumulatif (honnête)** : (1) coûts de changement — l'historique
d'audit et les workflows du client vivent chez nous ; (2) **données de
feedback** — chaque décision humaine améliore le triage ; personne ne
peut acheter ce dataset ; (3) typologies consortium inter-clients
(anonymisées, opt-in) — cold-start résolu en semant avec les typologies
publiques FATF/UIF puis en enrichissant ; (4) confiance certifiée
(SOC 2 → ISO 42001 + dossier AI Act = 18 mois qu'un entrant doit brûler) ;
(5) ce qui N'est PAS un moat : « notre LLM » — les modèles sont des
commodités, le harnais d'éval et les données ne le sont pas.

## L10 — Roadmap, risques, red-team

**Roadmap :**

| Phase | Contenu | Critère de passage | Kill criterion |
|---|---|---|---|
| MVP (m1–6) | file+triage suggéré+cas+4-yeux+audit trail+SAR sourcée, UE-hébergé | 3 pilotes payants ; −40 % temps/alerte mesuré | < 2 pilotes signés en 6 mois → pivot segment |
| V1 (m7–14) | workflow no-code, imports/exports complets, goAML, SOC 2 engagé | 10 clients ; NRR>100 % ; H5 prouvée | churn pilote > 30 % → revoir wedge |
| V2 (m15–24) | graphe réseaux, revues KYC event-driven, consortium v1 | 2 M€ ARR ; 1 banque mid signée | CAC payback > 24 mois |
| Enterprise (an 3) | ISO 27001/42001, multi-entité, résidence dédiée | 1er tier-2 bancaire | — |
| International (an 4+) | UK pack, US NYDFS/BSA | série A déployée | — |

**Pré-mortem — « morts en 2029 parce que… » (5 récits) :**
1. *Réglementaire* : l'AMLA a publié des standards techniques qui ont
   commoditisé le triage ; nous n'avions pas de moat au-delà. (Parade :
   consortium + workflow, pas le triage seul.)
2. *Concurrentiel* : Sumsub a bundlé un case management « suffisant »
   gratuit avec l'IDV ; notre wedge s'est fait absorber par le bas.
   (Parade : profondeur MLRO/audit que le bundle ne fait pas ; alliance
   IDV précoce.)
3. *Technique* : H5 n'a pas tenu sur données réelles hétérogènes ; la
   promesse chiffrée s'est dégonflée en « ça aide un peu ». (Parade :
   dataset gelé dès pilote 1, publication honnête des résultats.)
4. *Commercial* : cycles de 14 mois même chez les EMI ; le pre-seed est
   mort avant la preuve. (Parade : pilotes payants courts, 12 semaines max.)
5. *Financier* : pricing sous-évalué par peur, NRR 95 %, série A
   impossible. (Parade : paliers de volume dès le jour 1, D2.)

**Top faiblesses (20 identifiées, les 8 critiques ici)** : dépendance aux
fournisseurs de listes (risque de squeeze) ; cold-start du consortium ;
fondateurs sans marque conformité personnelle (recruter un advisor MLRO
reconnu = mois 1) ; « IA + conformité » = scepticisme des superviseurs
(charte + transparence) ; concentration early sur 3 pilotes (diversifier
dès V1) ; goAML hétérogène par pays (coût sous-estimé ×2 probable) ;
guerre des talents IA ; risque de sur-construction du socle gouvernance
avant la preuve de valeur (séquencer : audit trail d'abord, workflow
no-code après les 10 premiers clients).

**Expériences de validation (< 10 k€, < 4 semaines chacune) :**
- **H1 (ACV 30–90 k€)** : 15 entretiens MLRO avec 3 pages de pricing à
  réaction — coût ≈ 0 €, 3 semaines.
- **H2 (verbatims douleur)** : 10 shadowing d'analystes (NDA) — 2 sem.
- **H3 (−50 % temps/alerte)** : prototype sur 200 alertes anonymisées
  d'un partenaire, chrono avant/après — 4 sem., < 5 k€ d'inférence.
- **H4 (SAR < 1 h)** : 20 SAR historiques rejouées, % champs acceptés —
  2 sem.
- **H5 (FP −40/60 %)** : backtest champion/challenger sur 12 mois
  d'alertes d'un design partner, dataset gelé, protocole pré-enregistré —
  4 sem. **C'est L'expérience : tout le plan repose dessus.**

**Décisions modifiées par le red-team (preuve qu'il a mordu)** :
- D1 (veto MLRO) : l'IA ne clôt jamais seule → repositionne L5/L6 ;
- D2 (veto VC) : abandon du per-alert pur → pricing paliers L8 ;
- D3 (veto régulateur) : « augmentation », charte IA publique → L9 ;
- (+) hébergement UE avancé au MVP (veto CISO) → +1 mois, L10 ajusté ;
- (+) faiblesse n°8 : le socle gouvernance complet est SÉQUENCÉ après la
  preuve de valeur — correction directe de l'ambition initiale du
  prompt v1 qui voulait tout, tout de suite.

---

*Done-check (§8 du prompt) : L1–L3+L8 pitchables en seed ✓ ; L4–L5 reconnaissables par un MLRO ✓ ; L7 sans veto CISO rédhibitoire ✓ ; 5 hypothèses critiques → 5 expériences < 10 k€ ✓ ; red-team a modifié 5 décisions (> 3 requis) ✓.*
