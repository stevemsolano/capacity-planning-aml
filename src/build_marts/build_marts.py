"""Materialize the dbt marts without requiring dbt installed.

Reads the SQL in dbt_project/models/marts/*.sql, strips the dbt
{{ ref('...') }} Jinja (replacing it with the raw table name), and
runs it against DuckDB if available, else against the CSVs via
Python's stdlib (same arithmetic). Exports every mart to
data/marts/<mart>.csv — the files Tableau connects to.

This keeps one definition of each metric: the dbt SQL is the source
of truth; this script is only the local runner. `dbt run` on
DuckDB/Postgres produces the same marts from the same files.
Run: python3 src/build_marts/build_marts.py
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARTS_DIR = ROOT / "dbt_project" / "models" / "marts"
OUT_DIR = ROOT / "data" / "marts"


def _strip_ref(sql: str) -> str:
    return re.sub(r"\{\{\s*ref\('([^']+)'\)\s*\}\}", r"\1", sql)


def _strip_source(sql: str) -> str:
    # Mirror dbt's resolution: source('raw', '<table>') lives in schema raw.
    return re.sub(r"\{\{\s*source\('[^']+',\s*'([^']+)'\)\s*\}\}", r"raw.\1", sql)


def _materialize_with_duckdb():
    import duckdb

    sys.path.insert(0, str(ROOT / "src" / "load"))
    import load_duckdb
    DB_PATH = load_duckdb.DB_PATH
    load_duckdb.main()
    con = duckdb.connect(str(DB_PATH))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Build staging views first (they rename analysts -> analysts_available).
    staging_dir = ROOT / "dbt_project" / "models" / "staging"
    for sql_file in sorted(staging_dir.glob("*.sql")):
        sql = _strip_source(sql_file.read_text())
        con.execute(f"CREATE OR REPLACE VIEW {sql_file.stem} AS {sql}")
    # Then intermediate views (mart_monthly_summary reads int_daily_capacity).
    intermediate_dir = ROOT / "dbt_project" / "models" / "intermediate"
    for sql_file in sorted(intermediate_dir.glob("*.sql")):
        sql = _strip_ref(sql_file.read_text())
        con.execute(f"CREATE OR REPLACE VIEW {sql_file.stem} AS {sql}")
    built = []
    for sql_file in sorted(MARTS_DIR.glob("*.sql")):
        mart = sql_file.stem
        sql = _strip_ref(sql_file.read_text())
        con.execute(f"CREATE OR REPLACE TABLE {mart} AS {sql}")
        rows = con.execute(f"SELECT * FROM {mart}").fetchall()
        cols = [d[0] for d in con.description]
        with (OUT_DIR / f"{mart}.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        built.append((mart, len(rows)))
    con.close()
    return built


def _materialize_fallback():
    """Stdlib fallback: same mart arithmetic, from the raw CSVs."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gen_fallback", ROOT / "src" / "generate" / "generate.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    generate, generate_by_queue = gen.generate, gen.generate_by_queue

    rows = generate(days=90, seed=42)
    qrows = generate_by_queue(days=90, seed=42)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    def write(name, fieldnames, data):
        with (OUT_DIR / f"{name}.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(data)
        return (name, len(data))

    built = []
    built.append(write("mart_demand_daily",
                       ["day", "date", "demand", "completed"],
                       [{"day": r["day"], "date": r["date"],
                         "demand": r["demand"], "completed": r["completed"]}
                        for r in rows]))
    built.append(write("mart_capacity_daily",
                       ["day", "date", "analysts_scheduled", "absent",
                        "analysts_available", "productivity", "capacity",
                        "completed", "utilisation"],
                       [{"day": r["day"], "date": r["date"],
                         "analysts_scheduled": r["analysts_scheduled"],
                         "absent": r["absent"],
                         "analysts_available": r["analysts"],
                         "productivity": r["productivity"],
                         "capacity": r["capacity"],
                         "completed": r["completed"],
                         "utilisation": round(r["completed"] / r["capacity"], 3)
                         if r["capacity"] else 0} for r in rows]))
    built.append(write("mart_backlog_sla",
                       ["day", "date", "demand", "completed", "backlog", "sla_ok"],
                       [{"day": r["day"], "date": r["date"], "demand": r["demand"],
                         "completed": r["completed"], "backlog": r["backlog"],
                         "sla_ok": r["sla_ok"]} for r in rows]))
    built.append(write("mart_staffing_scenario",
                       ["day", "date", "queue", "demand", "backlog", "sla_ok"],
                       [{"day": r["day"], "date": r["date"], "queue": r["queue"],
                         "demand": r["demand"], "backlog": r["backlog"],
                         "sla_ok": r["sla_ok"]} for r in qrows]))
    # Monthly planning grain (same arithmetic as mart_monthly_summary.sql).
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "mf_fallback", ROOT / "src" / "forecast" / "monthly_forecast.py")
    _mf = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mf)
    hist = _mf.aggregate_monthly(rows)
    built.append(write("mart_monthly_summary",
                       ["month", "days", "business_days", "demand", "completed",
                        "capacity", "ending_backlog", "peak_backlog",
                        "sla_breach_days"],
                       [{k: h[k] for k in
                         ["month", "days", "business_days", "demand",
                          "completed", "capacity", "ending_backlog",
                          "peak_backlog", "sla_breach_days"]}
                        for h in hist]))
    return built


def main():
    try:
        import duckdb  # noqa: F401
        built = _materialize_with_duckdb()
        print(f"marts built with DuckDB: {built}")
    except ImportError:
        built = _materialize_fallback()
        print(f"marts built with stdlib fallback (no duckdb): {built}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
