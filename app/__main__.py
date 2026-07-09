"""Application Financial Command Center.

    python3 -m app                          # serveur local sur http://localhost:8787
    python3 -m app export [date] [seed]     # site statique autonome dans dist/
                                            # (publié gratuitement via GitHub Pages)

Le serveur et l'export utilisent exactement le même payload et la même
page : la version en ligne est un instantané figé de la version locale.
"""

import datetime
import json
import re
import shutil
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mesh import warehouse
from mesh.audit import AuditLog
from mesh.feedback import FeedbackStore
from mesh.lineage import Lineage
from mesh.reconciliation import decide, suggest, unmatched
from mesh.registry import REPO_ROOT, Registry

from .data import build_payload

STATIC_DIR = Path(__file__).resolve().parent / "static"
DIST_DIR = Path(__file__).resolve().parent.parent / "dist"
DATA_PLACEHOLDER = '<script id="fcc-data" type="application/json">null</script>'
EXPLORER_PLACEHOLDER = '<script id="fcc-explorer-config" type="application/json">null</script>'
REPORTS_PLACEHOLDER = '<script id="fcc-reports-config" type="application/json">null</script>'
RECON_PLACEHOLDER = '<script id="fcc-recon-config" type="application/json">null</script>'
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PORT = 8787

_AUDIT = AuditLog()          # journal chaîné de la session serveur
_FEEDBACK = FeedbackStore(REPO_ROOT / "data" / "feedback.jsonl")


_PENDING_AML = {}  # trade_id -> proposition en attente de 2e validation (G11)


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
    feedback = _aml_feedback()
    aml.decide(alert, escalated=pending["escalated"], actor=f"{pending['actor']}+{actor}",
               audit_log=_AUDIT, timestamp=timestamp, feedback=feedback)
    del _PENDING_AML[key]
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
    prediction = screen(trades, kyc, Lineage(Registry()), feedback=_aml_feedback())
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
    from mesh.accounting import derive_ledger, trial_balance
    from sim.generator import SimulatedTradingSource, simulate_bank_statements
    trades = SimulatedTradingSource(seed=seed, n_trades=n_trades).fetch(date)
    statements = simulate_bank_statements(trades, seed=seed,
                                          drop_rate=0.01, mutate_rate=0.02)
    ledger = derive_ledger(trades, statements, date)
    balance = trial_balance(ledger)
    return {
        "business_date": date, "seed": seed, "origin": ledger["origin"],
        "entries": ledger["records"][-14:][::-1],
        "trial_balance": balance,
    }


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
    from sim.generator import SimulatedTradingSource, simulate_bank_statements
    trades = SimulatedTradingSource(seed=seed, n_trades=n_trades).fetch(date)
    statements = simulate_bank_statements(trades, seed=seed,
                                          drop_rate=0.01, mutate_rate=0.02)
    missing, unknown = unmatched(trades, statements)
    prediction = suggest(trades, statements, Lineage(Registry()),
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
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length))

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
            elif path == "/api/ingest":
                self._send_json(_ingest(self._read_body()))
            else:
                self.send_error(404)
        except Exception as exc:  # le message d'erreur EST la réponse (G9, G10...)
            self._send_json({"error": str(exc)}, status=400)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            from mesh import warehouse as _wh
            self._send_json({
                "status": "ok",
                "time_utc": datetime.datetime.now(datetime.timezone.utc)
                            .isoformat(timespec="seconds"),
                "products": len(Registry().catalog()),
                "duckdb": _wh.HAS_DUCKDB,
                "audit_entries": len(_AUDIT.entries()),
                "audit_chain_intact": _AUDIT.verify_chain() is None,
            })
            return
        if parsed.path == "/api/reports/templates":
            self._send_json({"templates": _templates_listing()})
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
                self._send_json({"error": str(exc)}, status=400)
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
                self._send_json({"error": str(exc)}, status=400)
            return
        if parsed.path != "/api/summary":
            return super().do_GET()
        query = parse_qs(parsed.query)
        date = query.get("date", [_default_date()])[0]
        if not DATE_RE.match(date):
            self.send_error(400, "date attendue au format AAAA-MM-JJ")
            return
        try:
            seed = int(query.get("seed", ["42"])[0])
            n_trades = min(max(int(query.get("trades", ["250"])[0]), 1), 20_000)
        except ValueError:
            self.send_error(400, "seed et trades doivent être des entiers")
            return
        body = json.dumps(build_payload(date, seed, n_trades)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[fcc] {fmt % args}\n")


def export(business_date, seed=42, n_trades=250):
    payload = build_payload(business_date, seed, n_trades)
    page = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    if DATA_PLACEHOLDER not in page:
        raise RuntimeError("placeholder de données introuvable dans index.html")
    page = page.replace(
        DATA_PLACEHOLDER,
        '<script id="fcc-data" type="application/json">'
        + json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
        + "</script>",
    )
    DIST_DIR.mkdir(exist_ok=True)
    (DIST_DIR / "index.html").write_text(page, encoding="utf-8")
    print(f"export statique : {DIST_DIR / 'index.html'} ({business_date}, seed={seed})")
    _export_explorer()
    _export_reports(business_date)
    _export_embedded("recon.html", RECON_PLACEHOLDER, _recon_payload(business_date, seed))
    _export_embedded("aml.html",
                     '<script id="fcc-aml-config" type="application/json">null</script>',
                     _aml_payload(business_date, seed))
    _export_embedded("ingest.html",
                     '<script id="fcc-ingest-config" type="application/json">null</script>',
                     {"mode": "static"})
    _export_embedded("accounting.html",
                     '<script id="fcc-accounting-config" type="application/json">null</script>',
                     _accounting_payload(business_date, seed))
    shutil.copy(STATIC_DIR / "faq.html", DIST_DIR / "faq.html")
    print("export faq.html")


def _export_reports(business_date):
    """Rapports pré-générés pour la version en ligne (CSV + PDF chacun)."""
    generator = _report_generator()
    dest = DIST_DIR / "reports"
    dest.mkdir(parents=True, exist_ok=True)
    files = {}
    for template in _templates_listing():
        role = (template["roles"] or ["auditor"])[0]
        files[template["id"]] = {}
        for fmt in ("csv", "pdf"):
            meta = generator.demo(template["id"], fmt, requester="ci-export",
                                  role=role, business_date=business_date)
            shutil.copy(meta["path"], dest / Path(meta["path"]).name)
            files[template["id"]][fmt] = f"reports/{Path(meta['path']).name}"
    page = (STATIC_DIR / "reports.html").read_text(encoding="utf-8")
    config = {"templates": _templates_listing(), "files": files}
    page = page.replace(REPORTS_PLACEHOLDER,
                        '<script id="fcc-reports-config" type="application/json">'
                        + json.dumps(config, ensure_ascii=False).replace("</", "<\\/")
                        + "</script>")
    (DIST_DIR / "reports.html").write_text(page, encoding="utf-8")
    print(f"export rapports : {sum(len(v) for v in files.values())} livrables → dist/reports/")


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


def _export_explorer():
    """Explorateur en ligne : Parquet copiés dans dist/, SQL via DuckDB-WASM."""
    if not warehouse.HAS_DUCKDB:
        print("duckdb absent : explorateur non exporté (pip install duckdb)")
        return
    shutil.rmtree(warehouse.WAREHOUSE_DIR, ignore_errors=True)
    warehouse.build_warehouse()
    dest = DIST_DIR / "data"
    dest.mkdir(parents=True, exist_ok=True)
    tables = {}
    for parquet in sorted(warehouse.WAREHOUSE_DIR.glob("*.parquet")):
        shutil.copy(parquet, dest / parquet.name)
        tables[parquet.stem] = f"data/{parquet.name}"
    page = (STATIC_DIR / "explorer.html").read_text(encoding="utf-8")
    if EXPLORER_PLACEHOLDER not in page:
        raise RuntimeError("placeholder de configuration introuvable dans explorer.html")
    config = {"mode": "wasm", "tables": tables}
    page = page.replace(
        EXPLORER_PLACEHOLDER,
        '<script id="fcc-explorer-config" type="application/json">'
        + json.dumps(config) + "</script>",
    )
    (DIST_DIR / "explorer.html").write_text(page, encoding="utf-8")
    print(f"export explorateur : {len(tables)} tables Parquet → dist/data/")


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
