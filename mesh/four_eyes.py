"""Double validation « 4 yeux » (G11), réutilisable et testable hors HTTP.

Une décision sensible (escalade/classement AML, clôture d'un cas) exige une
PROPOSITION par un premier acteur puis une CONFIRMATION par un second acteur
DISTINCT. Le même acteur ne peut jamais se confirmer lui-même. Les deux pas
sont journalisés par l'appelant ; ce module ne tient que l'état des
propositions en attente, protégé par un verrou (le serveur est multi-thread).

Séparé de `app/` pour que l'invariant « pas de clôture sans second validateur
distinct » se prouve par un test unitaire, sans lever un serveur.
"""

import threading


class FourEyesError(PermissionError):
    """Violation du contrôle 4 yeux (G11) — refus AVANT effet, à journaliser."""


class FourEyesRegister:
    """Registre des propositions en attente, clé = (sujet, action).

    `submit` renvoie soit un état `pending` (première proposition), soit un
    état `committed` (confirmation par un acteur distinct) contenant les deux
    validateurs. Une seconde proposition par le MÊME acteur est refusée.
    """

    def __init__(self):
        self._pending = {}
        self._lock = threading.Lock()

    def submit(self, subject, action, actor):
        if not actor:
            raise FourEyesError("acteur requis pour une décision 4 yeux (G11)")
        key = (subject, action)
        with self._lock:
            pending = self._pending.get(key)
            if pending is None:
                self._pending[key] = actor
                return {"status": "pending", "subject": subject,
                        "action": action, "proposed_by": actor}
            if pending == actor:
                raise FourEyesError(
                    "contrôle 4 yeux (G11) : un second validateur DISTINCT est "
                    f"requis (décision {action!r} proposée par {actor!r})")
            del self._pending[key]  # réservé sous verrou avant l'effet
            return {"status": "committed", "subject": subject, "action": action,
                    "validators": [pending, actor]}

    def pending(self, subject, action):
        """Acteur ayant proposé cette décision, ou None (lecture seule)."""
        with self._lock:
            return self._pending.get((subject, action))

    def cancel(self, subject, action):
        """Retire une proposition en attente (ex. cas résolu autrement)."""
        with self._lock:
            self._pending.pop((subject, action), None)
