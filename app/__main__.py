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
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .data import build_payload

STATIC_DIR = Path(__file__).resolve().parent / "static"
DIST_DIR = Path(__file__).resolve().parent.parent / "dist"
DATA_PLACEHOLDER = '<script id="fcc-data" type="application/json">null</script>'
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PORT = 8787


def _default_date():
    return datetime.date.today().isoformat()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
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
