# Financial Command Center — Data Mesh Edition

Système de pilotage du cycle de vie financier organisé en **Data Mesh** :
chaque domaine métier (Trésorerie, Risque, Trading, Audit, Regulatory)
possède et publie son **Data Product**, sous une gouvernance fédérée et
une ontologie commune.

## Structure du dépôt

```
docs/
  architecture.md      Frontières de domaines, catalogue des Data Products, décisions
  ontology.md          Ontologie fédérée (Transaction, Position, AuditAssertion, ...)
  governance.md        Gouvernance fédérée, Regulatory-as-Code, disjoncteurs
mesh/                  Plateforme self-service (code exécutable, stdlib Python uniquement)
  contracts/           Schéma de contrat d'un Data Product
  registry.py          Registre / catalogue : découverte + validation des contrats
  audit.py             Journal d'audit immuable (chaîne de hachage) + assertions
  circuit_breaker.py   Isolation automatique d'un domaine en cas de dérive
  lineage.py           Graphe de lineage — preuve XAI pour chaque sortie IA
domains/
  treasury/ risk/ trading/ audit/ regulatory/
                       Un descripteur product.json par domaine (Data-as-a-Product)
tests/                 Tests unitaires du noyau plateforme
```

## Démarrage rapide

```bash
python3 -m unittest discover -s tests -v   # tests du noyau
python3 -m mesh catalog                    # liste le catalogue des Data Products
python3 -m mesh validate                   # valide tous les contrats de domaines
```

## Principes appliqués

- **Data-as-a-Product** : chaque domaine expose un contrat versionné
  (`product.json`) — découvrable, adressable, auto-descriptif, sécurisé.
- **Ontologie fédérée** : les termes des schémas de sortie doivent exister
  dans `docs/ontology.md` ; le registre rejette tout terme inconnu.
- **Gouvernance fédérée** : assertions d'audit vérifiées uniformément,
  journal de preuve immuable (chaîne de hachage).
- **Résilience** : disjoncteur par domaine (fraîcheur + taux de violation
  de schéma) ; un domaine en dérive est isolé, pas tout le mesh.
- **XAI** : toute prédiction IA porte un lien de lineage vers les Data
  Products sources et leurs versions de contrat.

## Décisions (Test de Réduction Radicale)

Reportés tant qu'ils n'apportent pas de valeur sans données réelles :
dashboards fédérés, FinOps par domaine, sandbox de stress-testing.
Voir `docs/architecture.md` § Roadmap.
