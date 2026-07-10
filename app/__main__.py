"""Application Financial Command Center.

    python3 -m app                          # serveur local sur http://localhost:8787
    python3 -m app export [date] [seed]     # site statique autonome dans dist/
                                            # (publié gratuitement via GitHub Pages)

Le serveur et l'export utilisent exactement le même payload et la même
page : la version en ligne est un instantané figé de la version locale.
"""

import datetime
import json
import logging
import re
import shutil
import sys
import threading
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mesh import warehouse
from mesh.audit import AuditLog
from mesh.feedback import FeedbackStore
from mesh.four_eyes import FourEyesRegister
from mesh.lineage import Lineage
from mesh.reconciliation import decide, suggest, unmatched
from mesh.registry import REPO_ROOT, Registry

from . import cases_view
from .data import build_payload

STATIC_DIR = Path(__file__).resolve().parent / "static"
DIST_DIR = Path(__file__).resolve().parent.parent / "dist"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PORT = 8787
MAX_BODY_BYTES = 5 * 1024 * 1024  # plafond anti-DoS mémoire sur les corps POST (S3)

logging.basicConfig(level=logging.INFO, format="[fcc] %(asctime)s %(levelname)s %(message)s")
_LOG = logging.getLogger("fcc")

_AUDIT = AuditLog(REPO_ROOT / "data" / "audit-server.jsonl")  # persistant, chaîné
_FEEDBACK = FeedbackStore(REPO_ROOT / "data" / "feedback.jsonl")
_REGISTRY = Registry()  # invariant du processus : chargé une fois, pas par requête (C2)


class BadRequest(Exception):
    """Erreur ATTENDUE (validation, IAM, contrôle) : son message est sûr à
    renvoyer au client. Les autres exceptions sont masquées (S2)."""


_PENDING_AML = {}  # trade_id -> proposition en attente de 2e validation (G11)
_PENDING_LOCK = threading.Lock()  # ThreadingHTTPServer est multi-thread (C3)

# Registre 4-yeux (G11) des décisions de cas : propositions en attente,
# protégé par son propre verrou (état de processus, comme _PENDING_AML).
_CASES_FOUR_EYES = FourEyesRegister()

# Cache du payload /api/summary (constat C1) : le pipeline d'un jour est
# déterministe par (date, seed, n_trades) ; inutile de le rejouer à chaque
# rafraîchissement. Borné, protégé par verrou, sérialisé une seule fois.
_SUMMARY_CACHE = {}
_SUMMARY_LOCK = threading.Lock()
_SUMMARY_CACHE_MAX = 32


def _summary_bytes(date, seed, n_trades, date_from=None):
    key = (date, seed, n_trades, date_from)
    with _SUMMARY_LOCK:
        cached = _SUMMARY_CACHE.get(key)
        if cached is not None:
            return cached
    body = json.dumps(build_payload(date, seed, n_trades,
                                    date_from=date_from)).encode("utf-8")
    with _SUMMARY_LOCK:
        if len(_SUMMARY_CACHE) >= _SUMMARY_CACHE_MAX:
            _SUMMARY_CACHE.pop(next(iter(_SUMMARY_CACHE)))  # évince la plus ancienne
        _SUMMARY_CACHE[key] = body
    return body


def _aml_four_eyes(body):
    """Contrôle 4 yeux (G11) : une décision AML exige DEUX acteurs distincts.

    1er appel : la décision est PROPOSÉE (journalisée aml.proposed).
    2e appel par un acteur différent : elle devient effective (journal +
    feedback). Le même acteur qui tente de confirmer est refusé.
    """
    from mesh import aml
    alert, actor = body["alert"], body.get("actor", "webapp")
    escalated = bool(body["escalated"])
    timestamp = body.get("timestamp", "")
    key = alert["trade_id"]
    # Section critique : deux requêtes concurrentes sur le même trade ne
    # doivent pas créer deux propositions ni valider deux fois (C3).
    with _PENDING_LOCK:
        pending = _PENDING_AML.get(key)
        if pending is None:
            _PENDING_AML[key] = {"actor": actor, "escalated": escalated}
            _AUDIT.append(actor=actor, action="aml.proposed",
                          subject_urn="urn:fcc:client:kyc-profiles",
                          details={"trade_id": key, "escalated": escalated,
                                   "awaiting": "second-validator"},
                          timestamp=timestamp)
            return {"pending": True, "proposed_by": actor}
        if pending["actor"] == actor:
            raise PermissionError(
                "contrôle 4 yeux (G11) : un second validateur DISTINCT est requis "
                f"(proposé par {actor!r})")
        del _PENDING_AML[key]  # réservé sous verrou avant de valider hors section
    feedback = _aml_feedback()
    aml.decide(alert, escalated=pending["escalated"], actor=f"{pending['actor']}+{actor}",
               audit_log=_AUDIT, timestamp=timestamp, feedback=feedback)
    return {"ok": True, "validated_by": [pending["actor"], actor],
            "feedback_entries": len(feedback),
            "audit_chain_intact": _AUDIT.verify_chain() is None}


def _aml_feedback():
    from mesh.aml import AML_FEATURES
    return FeedbackStore(REPO_ROOT / "data" / "feedback-aml.jsonl",
                         feature_order=AML_FEATURES)


def _aml_payload(date, seed=42, n_trades=250):
    from mesh.aml import screen
    from sim.generator import SimulatedClientSource, SimulatedTradingSource
    trades = SimulatedTradingSource(seed=seed, n_trades=n_trades).fetch(date)
    kyc = SimulatedClientSource(seed=seed).fetch(date)
    prediction = screen(trades, kyc, Lineage(_REGISTRY), feedback=_aml_feedback())
    profiles = kyc["records"]
    return {
        "business_date": date, "seed": seed,
        "profiles": profiles,
        "pep_count": sum(1 for p in profiles if p["pep"]),
        "high_risk_count": sum(1 for p in profiles if p["risk_rating"] == "high"),
        "screened_trades": prediction["output"]["screened_trades"],
        "alerts": prediction["output"]["alerts"],
        "lineage_proof": prediction["lineage_proof"],
        "model": prediction["model"],
    }


# Mapping de démonstration pour l'ingestion CSV (colonnes ↔ ontologie)
INGEST_MAPPING = {
    "trade_id": "Deal Id",
    "instrument_id": "ISIN",
    "counterparty_lei": "LEI",
    "notional": {"amount": "Nominal", "currency": "Ccy"},
    "status": lambda row: row["State"].lower(),
    "executed_at": "Timestamp",
}


def _accounting_payload(date, seed=42, n_trades=250):
    from mesh.accounting import (derive_ledger, off_balance_sheet, pnl_summary,
                                 suspense_worklist, trial_balance)
    from mesh.fees import derive_fees
    from sim.generator import SimulatedTradingSource, demo_statements
    trades = SimulatedTradingSource(seed=seed, n_trades=n_trades).fetch(date)
    statements = demo_statements(trades, seed=seed)
    # Grand livre AVEC commissions : cohérent avec le bilan/PnL certifiés (D3).
    ledger = derive_ledger(trades, statements, date,
                           fees_batch=derive_fees(trades, date))
    balance = trial_balance(ledger)
    return {
        "business_date": date, "seed": seed, "origin": ledger["origin"],
        "entries": ledger["records"][-14:][::-1],
        "trial_balance": balance,
        "pnl": pnl_summary(balance),
        "off_balance_sheet": off_balance_sheet(trades),
        "suspense_worklist": suspense_worklist(ledger, as_of=date),
        "monthly_close": _monthly_close(date, seed, n_trades),
    }


def _monthly_close(date, seed, n_trades):
    """Clôture mensuelle M / M-1 : mois en cours (du 1er au jour d'arrêté) vs
    même période du mois précédent. Recalculé, jamais estimé."""
    from app.data import build_comparison
    month_start = date[:8] + "01"
    cmp = build_comparison(month_start, date, seed, n_trades)
    cmp["label"] = "M (mois en cours à date) vs M-1 (même période, mois précédent)"
    # M-1 = même période décalée d'un an dans build_comparison ; ici on veut le
    # MOIS précédent : on recadre prev_period sur le mois M-1.
    import datetime
    d = datetime.date.fromisoformat(date)
    prev_month_end = datetime.date(d.year, d.month, 1) - datetime.timedelta(days=1)
    prev_start = prev_month_end.replace(day=1).isoformat()
    prev_end = min(prev_month_end,
                   prev_month_end.replace(day=min(d.day, prev_month_end.day))).isoformat()
    from app.data import _period_flux
    previous = _period_flux(prev_start, prev_end, seed, n_trades)
    cmp["prev_period"] = {"from": prev_start, "to": prev_end}
    cmp["previous"] = previous
    for k in ("trades", "notional_eur", "fees_eur"):
        delta = round(cmp["current"][k] - previous[k], 2)
        pct = round(delta / previous[k], 4) if previous[k] else None
        cmp["variation"][k] = {"delta": delta, "pct": pct}
    return cmp


def _ingest(body):
    from mesh.transformer import DataTransformer
    origin = body.get("origin", "simulated")
    transformer = DataTransformer("urn:fcc:trading:executed-trades",
                                  INGEST_MAPPING, audit_log=_AUDIT,
                                  actor=body.get("actor", "webapp"))
    batch, rejects = transformer.transform_csv(
        body["csv"], origin, datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds"), delimiter=body.get("delimiter", ";"),
        source_name=body.get("filename", "upload"),
        control_totals=body.get("control_totals"))
    entry = _AUDIT.entries()[-1]
    return {
        "accepted": len(batch["records"]),
        "rejected": len(rejects),
        "rejects": rejects[:20],
        "origin": batch["origin"],
        "sample": batch["records"][:5],
        "audit": {"action": entry["action"], "hash": entry["hash"],
                  "input_sha256": entry["details"]["input_sha256"]},
        "audit_chain_intact": _AUDIT.verify_chain() is None,
    }


def _report_generator():
    from reporting.generator import ReportGenerator
    return ReportGenerator(audit_log=_AUDIT)


def _templates_listing():
    from reporting.generator import TEMPLATES_DIR
    listing = []
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        t = json.loads(path.read_text(encoding="utf-8"))
        listing.append({"id": path.stem, "name": t["name"],
                        "department": t["department"],
                        "norm_ref": t.get("norm_ref"),
                        "classification": t["classification"],
                        "roles": t.get("roles", []),
                        "required_assertions": t["required_assertions"]})
    return listing


def _recon_payload(date, seed=42, n_trades=2000):
    from sim.generator import SimulatedTradingSource, demo_statements
    trades = SimulatedTradingSource(seed=seed, n_trades=n_trades).fetch(date)
    statements = demo_statements(trades, seed=seed)
    missing, unknown = unmatched(trades, statements)
    prediction = suggest(trades, statements, Lineage(_REGISTRY),
                         feedback=_FEEDBACK, min_score=0.4)
    return {
        "business_date": date, "seed": seed,
        "missing_statement": len(missing), "unknown_statement": len(unknown),
        "feedback_entries": len(_FEEDBACK),
        "model": prediction["model"],
        "suggestions": prediction["output"]["suggestions"][:40],
        "lineage_proof": prediction["lineage_proof"],
    }


def _default_date():
    return datetime.date.today().isoformat()


def _ensure_warehouse():
    """Construit l'entrepôt Parquet ; simule une journée si data/ est vide."""
    if not warehouse.HAS_DUCKDB:
        raise RuntimeError("duckdb n'est pas installé : pip install duckdb")
    if not any(warehouse.DATA_DIR.glob("????-??-??")):
        build_payload(_default_date())  # exécute le pipeline, remplit data/
    if not any(warehouse.WAREHOUSE_DIR.glob("*.parquet")):
        warehouse.build_warehouse()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            raise BadRequest("en-tête Content-Length invalide")
        if length < 0 or length > MAX_BODY_BYTES:
            raise BadRequest(f"corps trop volumineux (max {MAX_BODY_BYTES} octets)")
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            raise BadRequest("corps JSON invalide")

    # Erreurs dont le message est sûr à renvoyer (validation métier, IAM,
    # contrôles de gouvernance G9/G10). Tout le reste est masqué (S2).
    _EXPECTED_ERRORS = (BadRequest, ValueError, PermissionError, KeyError)

    def _fail(self, exc):
        """Réponse d'erreur : message métier si l'erreur est attendue,
        sinon message générique + trace serveur avec identifiant de
        corrélation (l'utilisateur ne voit jamais l'interne — S2)."""
        if isinstance(exc, self._EXPECTED_ERRORS):
            self._send_json({"error": str(exc)}, status=400)
        else:
            ref = uuid.uuid4().hex[:12]
            _LOG.exception("erreur inattendue [ref=%s] sur %s", ref, self.path)
            self._send_json({"error": "erreur interne du serveur",
                             "correlation_id": ref}, status=500)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/query":
                body = self._read_body()
                _ensure_warehouse()
                con = warehouse.connect()
                try:
                    self._send_json(warehouse.query(con, body["sql"]))
                finally:
                    con.close()
            elif path == "/api/reports/generate":
                body = self._read_body()
                metadata = _report_generator().demo(
                    template_name=body["template"], fmt=body.get("format", "csv"),
                    requester=body.get("requester", "webapp"),
                    role=body.get("role", "viewer"),
                    business_date=body.get("date", _default_date()))
                metadata["download"] = "/reports/" + Path(metadata["path"]).name
                self._send_json(metadata)
            elif path == "/api/recon/decide":
                body = self._read_body()
                decide(body["suggestion"], accepted=bool(body["accepted"]),
                       actor=body.get("actor", "webapp"), audit_log=_AUDIT,
                       timestamp=body.get("timestamp", ""), feedback=_FEEDBACK)
                self._send_json({"ok": True, "feedback_entries": len(_FEEDBACK),
                                 "audit_chain_intact": _AUDIT.verify_chain() is None})
            elif path == "/api/aml/decide":
                self._send_json(_aml_four_eyes(self._read_body()))
            elif path == "/api/cases/decide":
                self._send_json(cases_view.decide(
                    _REGISTRY, _AUDIT, _CASES_FOUR_EYES, self._read_body(),
                    feedback=_aml_feedback()))
            elif path == "/api/cases/sar":
                self._send_json(cases_view.sar_document(
                    _REGISTRY, _AUDIT, self._read_body(), feedback=_aml_feedback()))
            elif path == "/api/ingest":
                self._send_json(_ingest(self._read_body()))
            else:
                self.send_error(404)
        except Exception as exc:  # attendue → message métier ; sinon masquée (S2)
            self._fail(exc)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/audit":
            entries = _AUDIT.entries()
            dictionary = [{
                "urn": c["urn"], "domain": c["domain"], "name": c["name"],
                "version": c["version"], "entity": c["output_schema"]["entity"],
                "classification": c["access"]["classification"],
                "owner": c["owner"], "sources": c["sources"],
                "fields": c["output_schema"]["fields"],
            } for c in _REGISTRY.products.values()]
            self._send_json({
                "total": len(entries),
                "chain_intact": _AUDIT.verify_chain() is None,
                "entries": entries[-200:][::-1],
                "dictionary": sorted(dictionary, key=lambda d: d["urn"]),
            })
            return
        if parsed.path == "/api/health":
            from mesh import warehouse as _wh
            self._send_json({
                "status": "ok",
                "time_utc": datetime.datetime.now(datetime.timezone.utc)
                            .isoformat(timespec="seconds"),
                "products": len(_REGISTRY.catalog()),
                "duckdb": _wh.HAS_DUCKDB,
                "audit_entries": len(_AUDIT.entries()),
                "audit_chain_intact": _AUDIT.verify_chain() is None,
            })
            return
        if parsed.path == "/api/reports/templates":
            self._send_json({"templates": _templates_listing()})
            return
        if parsed.path == "/api/cases":
            query = parse_qs(parsed.query)
            date = query.get("date", [_default_date()])[0]
            if not DATE_RE.match(date):
                self._send_json({"error": "date attendue au format AAAA-MM-JJ"}, 400)
                return
            try:
                seed = int(query.get("seed", ["42"])[0])
                filters = {k: query[k][0] for k in
                           ("assignee", "status", "case_type", "priority")
                           if k in query}
                self._send_json(cases_view.payload(
                    _REGISTRY, _AUDIT, date, seed,
                    feedback=_aml_feedback(), filters=filters))
            except Exception as exc:
                self._fail(exc)
            return
        if parsed.path in ("/api/recon", "/api/aml", "/api/accounting"):
            query = parse_qs(parsed.query)
            date = query.get("date", [_default_date()])[0]
            if not DATE_RE.match(date):
                self._send_json({"error": "date attendue au format AAAA-MM-JJ"}, 400)
                return
            try:
                seed = int(query.get("seed", ["42"])[0])
                builder = {"/api/recon": _recon_payload, "/api/aml": _aml_payload,
                           "/api/accounting": _accounting_payload}[parsed.path]
                self._send_json(builder(date, seed))
            except Exception as exc:
                self._fail(exc)
            return
        if parsed.path.startswith("/reports/"):
            name = Path(parsed.path).name  # neutralise toute traversée de chemin
            target = REPO_ROOT / "data" / "reports" / name
            if not target.is_file():
                self.send_error(404)
                return
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/schema":
            try:
                _ensure_warehouse()
                con = warehouse.connect()
                try:
                    self._send_json({"tables": warehouse.schema(con)})
                finally:
                    con.close()
            except Exception as exc:
                self._fail(exc)
            return
        if parsed.path != "/api/summary":
            return super().do_GET()
        query = parse_qs(parsed.query)
        date = query.get("date", [_default_date()])[0]
        if not DATE_RE.match(date):
            self.send_error(400, "date attendue au format AAAA-MM-JJ")
            return
        # Période optionnelle [du..au] : `from` <= date d'arrêté, bornée à
        # 366 jours (le comparatif N-1 double le calcul — pas de DoS).
        date_from = query.get("from", [None])[0]
        if date_from is not None:
            if not DATE_RE.match(date_from) or date_from > date:
                self.send_error(400, "période invalide : from <= date, AAAA-MM-JJ")
                return
            import datetime as _dt
            span = (_dt.date.fromisoformat(date)
                    - _dt.date.fromisoformat(date_from)).days
            if span > 366:
                self.send_error(400, "période trop longue (maximum 366 jours)")
                return
        try:
            seed = int(query.get("seed", ["42"])[0])
            n_trades = min(max(int(query.get("trades", ["250"])[0]), 1), 20_000)
        except ValueError:
            self.send_error(400, "seed et trades doivent être des entiers")
            return
        body = _summary_bytes(date, seed, n_trades, date_from=date_from)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[fcc] {fmt % args}\n")


def export(business_date, seed=42, n_trades=250):
    """Export statique du produit KYC/AML seul : accueil + criblage + cas.

    Les autres modules sont archivés en brouillon (drafts/) et ne sont ni
    servis ni publiés. Pour les réactiver, voir drafts/README.md."""
    shutil.rmtree(DIST_DIR, ignore_errors=True)  # publication déterministe : aucune page archivée résiduelle
    DIST_DIR.mkdir(exist_ok=True)
    shutil.copy(STATIC_DIR / "index.html", DIST_DIR / "index.html")
    print(f"export statique KYC/AML : {DIST_DIR / 'index.html'} ({business_date}, seed={seed})")
    _export_embedded("aml.html",
                     '<script id="fcc-aml-config" type="application/json">null</script>',
                     _aml_payload(business_date, seed))
    _export_embedded("cases.html",
                     '<script id="fcc-cases-config" type="application/json">null</script>',
                     cases_view.payload(_REGISTRY, _AUDIT, business_date, seed))



def _export_embedded(name, placeholder, payload):
    """Exporte une page en remplaçant son placeholder de config/données."""
    page = (STATIC_DIR / name).read_text(encoding="utf-8")
    if placeholder not in page:
        raise RuntimeError(f"placeholder introuvable dans {name}")
    marker_id = placeholder.split('id="')[1].split('"')[0]
    page = page.replace(placeholder,
                        f'<script id="{marker_id}" type="application/json">'
                        + json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
                        + "</script>")
    (DIST_DIR / name).write_text(page, encoding="utf-8")
    print(f"export {name}")



def main(argv):
    if argv and argv[0] == "export":
        date = argv[1] if len(argv) > 1 else _default_date()
        seed = int(argv[2]) if len(argv) > 2 else 42
        export(date, seed)
        return 0
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Financial Command Center : http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
