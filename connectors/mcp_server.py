"""Serveur MCP du mesh : les outils des domaines exposés à une IA hôte.

    python3 -m connectors.mcp_server        # transport stdio (JSON-RPC,
                                            # messages délimités par \\n)

Architecture : chaque domaine déclare ses outils dans TOOLS avec son
`domain` et sa `classification` — le serveur n'est qu'un aiguillage.
La sécurité est contextuelle (G9) : le rôle de la session vient de la
variable d'environnement FCC_ROLE (défaut : viewer) et chaque appel est
contrôlé par mesh/iam AVANT exécution, puis journalisé. L'IA hôte
n'orchestre donc jamais plus que ce que son rôle permet.

Déclaration côté client MCP (ex. Claude Desktop / Claude Code) :
    {"command": "python3", "args": ["-m", "connectors.mcp_server"],
     "cwd": "<repo>", "env": {"FCC_ROLE": "risk-analyst"}}
"""

import json
import os
import sys

from mesh import iam
from mesh.audit import AuditLog
from mesh.lineage import Lineage
from mesh.registry import Registry

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "financial-command-center", "version": "1.0.0"}


def _tool_catalog(_args):
    return Registry().catalog()


def _tool_query(args):
    from mesh import warehouse
    con = warehouse.connect()
    try:
        return warehouse.query(con, args["sql"])
    finally:
        con.close()


def _tool_simulate(args):
    from mesh.pipeline import run_business_day
    from sim.generator import SimulatedTradingSource, simulate_bank_statements
    seed = int(args.get("seed", 42))
    return run_business_day(
        args["date"], SimulatedTradingSource(seed=seed, n_trades=int(args.get("trades", 250))),
        lambda t: simulate_bank_statements(t, seed=seed))


def _tool_reconcile(args):
    from mesh.reconciliation import suggest
    from sim.generator import SimulatedTradingSource, simulate_bank_statements
    seed = int(args.get("seed", 42))
    trades = SimulatedTradingSource(seed=seed, n_trades=int(args.get("trades", 2000))).fetch(args["date"])
    statements = simulate_bank_statements(trades, seed=seed, drop_rate=float(args.get("drop_rate", 0.005)))
    return suggest(trades, statements, Lineage(Registry()))


def _tool_report(args):
    from reporting.generator import ReportGenerator, demo_assertions
    generator = ReportGenerator(audit_log=_LOG)
    return generator.demo(template_name=args["template"], fmt=args.get("format", "csv"),
                          requester=args.get("requester", "mcp-session"),
                          role=os.environ.get("FCC_ROLE", "viewer"),
                          business_date=args["date"])


def _schema(props, required):
    return {"type": "object",
            "properties": {k: {"type": t, "description": d} for k, (t, d) in props.items()},
            "required": required}


# Chaque domaine déclare ici ses outils (name, domain, classification,
# description, inputSchema, handler). Ajouter un domaine = ajouter des
# entrées, le serveur ne change pas.
TOOLS = {
    "catalog_list": {
        "domain": "platform", "classification": iam.PUBLIC,
        "description": "Catalogue des Data Products du mesh (URN, SLO, lineage).",
        "inputSchema": _schema({}, []), "handler": _tool_catalog,
    },
    "sql_query": {
        "domain": "platform", "classification": iam.INTERNAL,
        "description": "Requête SQL lecture seule sur l'entrepôt Parquet (DuckDB).",
        "inputSchema": _schema({"sql": ("string", "SELECT/WITH/DESCRIBE uniquement")}, ["sql"]),
        "handler": _tool_query,
    },
    "simulate_business_day": {
        "domain": "platform", "classification": iam.INTERNAL,
        "description": "Rejoue un jour ouvré complet (pipeline + assertions d'audit).",
        "inputSchema": _schema({"date": ("string", "AAAA-MM-JJ"),
                                "seed": ("integer", "graine"),
                                "trades": ("integer", "nombre de trades")}, ["date"]),
        "handler": _tool_simulate,
    },
    "reconciliation_suggest": {
        "domain": "treasury", "classification": iam.INTERNAL,
        "description": "Suggestions IA de rapprochement des flux non appariés "
                       "(scores explicables, lineage XAI, décision humaine requise).",
        "inputSchema": _schema({"date": ("string", "AAAA-MM-JJ")}, ["date"]),
        "handler": _tool_reconcile,
    },
    "report_generate": {
        "domain": "regulatory", "classification": iam.RESTRICTED,
        "description": "Génère un livrable certifié (CSV/XLSX/PDF) avec annexe de preuve.",
        "inputSchema": _schema({"template": ("string", "regulatory | investor_relations | treasury"),
                                "format": ("string", "csv | xlsx | pdf"),
                                "date": ("string", "AAAA-MM-JJ")}, ["template", "date"]),
        "handler": _tool_report,
    },
}

_LOG = AuditLog()  # journal de la session MCP (chaîné, vérifiable)


def handle(message, role):
    """Traite un message JSON-RPC ; retourne la réponse (ou None)."""
    method, msg_id = message.get("method"), message.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO}}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        tools = [{"name": name,
                  "description": f"[{t['domain']} · {t['classification']}] {t['description']}",
                  "inputSchema": t["inputSchema"]}
                 for name, t in TOOLS.items()]
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}}
    if method == "tools/call":
        name = message["params"]["name"]
        args = message["params"].get("arguments", {})
        tool = TOOLS.get(name)
        if tool is None:
            return {"jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32602, "message": f"outil inconnu : {name}"}}
        try:
            iam.check_access(role, tool["classification"], audit_log=_LOG,
                             actor=f"mcp:{role}", resource=f"urn:fcc:{tool['domain']}:tool:{name}")
            result = tool["handler"](args)
            _LOG.append(actor=f"mcp:{role}", action="mcp.tool_call",
                        subject_urn=f"urn:fcc:{tool['domain']}:tool:{name}",
                        details={"arguments": args}, timestamp="")
            payload, is_error = result, False
        except Exception as exc:  # le message d'erreur EST la réponse outil
            payload, is_error = {"error": str(exc)}, True
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "content": [{"type": "text",
                         "text": json.dumps(payload, ensure_ascii=False, default=str)}],
            "isError": is_error}}
    if msg_id is not None:
        return {"jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32601, "message": f"méthode inconnue : {method}"}}
    return None


def main():
    role = os.environ.get("FCC_ROLE", "viewer")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = handle(json.loads(line), role)
        except (json.JSONDecodeError, KeyError) as exc:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": str(exc)}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
