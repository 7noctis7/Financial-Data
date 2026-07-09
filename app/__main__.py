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
            else:
                self.send_error(404)
        except Exception as exc:  # le message d'erreur EST la réponse (G9, G10...)
            self._send_json({"error": str(exc)}, status=400)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/reports/templates":
            self._send_json({"templates": _templates_listing()})
            return
        if parsed.path == "/api/recon":
            query = parse_qs(parsed.query)
            date = query.get("date", [_default_date()])[0]
            if not DATE_RE.match(date):
                self._send_json({"error": "date attendue au format AAAA-MM-JJ"}, 400)
                return
            try:
                seed = int(query.get("seed", ["42"])[0])
                self._send_json(_recon_payload(date, seed))
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
    _export_recon(business_date, seed)


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


def _export_recon(business_date, seed):
    payload = _recon_payload(business_date, seed)
    page = (STATIC_DIR / "recon.html").read_text(encoding="utf-8")
    page = page.replace(RECON_PLACEHOLDER,
                        '<script id="fcc-recon-config" type="application/json">'
                        + json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
                        + "</script>")
    (DIST_DIR / "recon.html").write_text(page, encoding="utf-8")
    print(f"export réconciliation : {len(payload['suggestions'])} suggestions embarquées")


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
