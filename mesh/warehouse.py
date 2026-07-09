"""Entrepôt analytique : Data Products publiés en Parquet, requêtés en SQL.

Couche optionnelle (seule du projet à dépendre d'un paquet : `duckdb`).
Le mesh fonctionne sans elle ; avec elle, chaque produit devient une table
SQL explorable — par l'explorateur intégré de l'app, ou par n'importe quel
client se connectant à DuckDB (DBeaver, CLI duckdb, pandas...).

Les fichiers Parquet vivent dans data/warehouse/ (gitignoré, comme tout
data/) : l'entrepôt est un artefact reconstructible, jamais une source.
"""

import json
import re
import tempfile
import time
from pathlib import Path

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:  # le noyau du mesh reste utilisable sans duckdb
    HAS_DUCKDB = False

from .registry import REPO_ROOT

DATA_DIR = REPO_ROOT / "data"
WAREHOUSE_DIR = DATA_DIR / "warehouse"

# table SQL -> fichier produit par le pipeline (par jour ouvré)
TABLES = {
    "trades": "trades.json",
    "bank_statements": "bank-statements.json",
    "cash_positions": "cash-positions.json",
    "exposures": "exposures.json",
    "ledger": "ledger.json",
    "fees": "fees.json",
    "audit_journal": "audit-journal.json",
}

MAX_ROWS = 500
_READONLY = re.compile(r"^\s*(select|with|describe|show|explain|summarize)\b", re.IGNORECASE)


def build_warehouse(data_dir=DATA_DIR, warehouse_dir=WAREHOUSE_DIR):
    """Consolide tous les jours ouvrés de data/ en un Parquet par table.

    Chaque ligne est enrichie de `business_date` (et `origin` quand le
    fichier source est un batch) : la provenance reste visible en SQL.
    """
    if not HAS_DUCKDB:
        raise RuntimeError("duckdb n'est pas installé : pip install duckdb")
    warehouse_dir = Path(warehouse_dir)
    warehouse_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    built = []
    for table, filename in TABLES.items():
        rows = []
        for day_dir in sorted(Path(data_dir).glob("????-??-??")):
            path = day_dir / filename
            if not path.exists():
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
            records = doc if isinstance(doc, list) else doc["records"]
            origin = None if isinstance(doc, list) else doc["origin"]
            for record in records:
                row = {"business_date": day_dir.name}
                if origin is not None:
                    row["origin"] = origin
                row.update(record)
                rows.append(row)
        if not rows:
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                         encoding="utf-8") as tmp:
            for row in rows:
                tmp.write(json.dumps(row, ensure_ascii=False) + "\n")
        target = warehouse_dir / f"{table}.parquet"
        con.execute(
            "COPY (SELECT * FROM read_json_auto(?)) TO "
            f"'{target.as_posix()}' (FORMAT PARQUET)",
            [tmp.name],
        )
        Path(tmp.name).unlink()
        built.append(table)
    con.close()
    return built


def connect(warehouse_dir=WAREHOUSE_DIR):
    """Connexion mémoire avec une vue par table Parquet de l'entrepôt."""
    if not HAS_DUCKDB:
        raise RuntimeError("duckdb n'est pas installé : pip install duckdb")
    con = duckdb.connect()
    for parquet in sorted(Path(warehouse_dir).glob("*.parquet")):
        path = parquet.as_posix().replace("'", "''")
        con.execute(
            f'CREATE VIEW "{parquet.stem}" AS SELECT * FROM read_parquet(\'{path}\')')
    return con


def _jsonable(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)  # Decimal, datetime, UUID...


def query(con, sql, max_rows=MAX_ROWS):
    """Exécute une requête en lecture seule, résultat JSON-sérialisable."""
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        raise ValueError("une seule instruction SQL à la fois")
    if not _READONLY.match(stripped):
        raise ValueError(
            "lecture seule : SELECT, WITH, DESCRIBE, SHOW, SUMMARIZE ou EXPLAIN")
    start = time.perf_counter()
    cursor = con.execute(stripped)
    rows = cursor.fetchmany(max_rows + 1)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    return {
        "columns": [d[0] for d in cursor.description],
        "rows": [[_jsonable(v) for v in row] for row in rows[:max_rows]],
        "truncated": len(rows) > max_rows,
        "elapsed_ms": elapsed_ms,
    }


def schema(con):
    """Tables, colonnes et volumétrie — ce que l'explorateur affiche."""
    tables = []
    for (name,) in con.execute(
            "SELECT view_name FROM duckdb_views() WHERE NOT internal ORDER BY view_name"
    ).fetchall():
        columns = [
            {"name": c[0], "type": c[1]}
            for c in con.execute(f'DESCRIBE "{name}"').fetchall()
        ]
        (count,) = con.execute(f'SELECT count(*) FROM "{name}"').fetchone()
        tables.append({"name": name, "columns": columns, "rows": count})
    return tables
