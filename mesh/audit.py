"""Moteur de preuve d'audit : journal chaîné par hachage + assertions.

Règles de gouvernance G3 (immuabilité prouvable) et G4 (une assertion
`certified` référence une entrée de preuve du journal).
"""

import hashlib
import json

from .sources import ORIGINS

GENESIS = "0" * 64

CERTIFIED = "certified"
QUALIFIED = "qualified"
FAILED = "failed"
STATUSES = (CERTIFIED, QUALIFIED, FAILED)


def _hash_entry(prev_hash, payload):
    material = prev_hash + json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class AuditLog:
    """Journal append-only : chaque entrée scelle la précédente.

    Modifier, supprimer ou insérer une entrée passée casse tous les hashs
    en aval — `verify_chain` le détecte sans état externe.
    """

    def __init__(self, path=None):
        """`path` optionnel : persistance JSONL append-only. À l'ouverture,
        le journal existant est rechargé et sa chaîne re-vérifiée — un
        fichier falsifié refuse de s'ouvrir."""
        self._entries = []
        self._path = None
        if path is not None:
            from pathlib import Path
            self._path = Path(path)
            if self._path.exists():
                with self._path.open(encoding="utf-8") as fh:
                    self._entries = [json.loads(line) for line in fh if line.strip()]
                broken = self.verify_chain()
                if broken is not None:
                    raise ValueError(
                        f"journal d'audit corrompu à l'entrée {broken} : {self._path}")

    def append(self, actor, action, subject_urn, details, timestamp):
        payload = {
            "index": len(self._entries),
            "actor": actor,
            "action": action,
            "subject_urn": subject_urn,
            "details": details,
            "timestamp": timestamp,
        }
        prev_hash = self._entries[-1]["hash"] if self._entries else GENESIS
        entry = dict(payload, prev_hash=prev_hash, hash=_hash_entry(prev_hash, payload))
        self._entries.append(entry)
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry["hash"]

    def entries(self):
        return list(self._entries)

    def verify_chain(self):
        """Recalcule toute la chaîne ; retourne l'index de la première
        entrée falsifiée, ou None si le journal est intègre."""
        prev_hash = GENESIS
        for i, entry in enumerate(self._entries):
            payload = {k: v for k, v in entry.items() if k not in ("prev_hash", "hash")}
            if entry["prev_hash"] != prev_hash or entry["hash"] != _hash_entry(prev_hash, payload):
                return i
            prev_hash = entry["hash"]
        return None


class AssertionError_(ValueError):
    """Assertion d'audit invalide (nom suffixé pour ne pas masquer le builtin)."""


def make_assertion(log, auditor, product_urn, scope, status, evidence, timestamp, origin):
    """Publie une AuditAssertion et journalise sa preuve.

    Retourne l'assertion, dont `proof_hash` pointe l'entrée du journal —
    c'est ce hash que Regulatory/IR citent pour publier un chiffre (G4).
    `origin` est la provenance des données certifiées (simulated /
    production) : elle est scellée dans la preuve et vérifiée à la
    publication réglementaire (G8).
    """
    if status not in STATUSES:
        raise AssertionError_(f"statut inconnu : {status!r}")
    if origin not in ORIGINS:
        raise AssertionError_(f"provenance inconnue : {origin!r}")
    if status == CERTIFIED and not evidence:
        raise AssertionError_("une assertion 'certified' exige une preuve (G4)")
    proof_hash = log.append(
        actor=auditor,
        action="audit.assertion",
        subject_urn=product_urn,
        details={"scope": scope, "status": status, "evidence": evidence, "origin": origin},
        timestamp=timestamp,
    )
    return {
        "product_urn": product_urn,
        "scope": scope,
        "status": status,
        "origin": origin,
        "proof_hash": proof_hash,
        "timestamp": timestamp,
    }


def verify_assertion(log, assertion):
    """Vérifie qu'une assertion est ancrée dans un journal intègre."""
    if log.verify_chain() is not None:
        return False
    return any(
        e["hash"] == assertion["proof_hash"]
        and e["subject_urn"] == assertion["product_urn"]
        and e["details"]["status"] == assertion["status"]
        and e["details"]["origin"] == assertion["origin"]
        for e in log.entries()
    )
