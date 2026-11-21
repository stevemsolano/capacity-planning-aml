"""Load generated CSVs into DuckDB (local warehouse).

DuckDB is optional: if it is not installed this script prints a clear
message and exits 0 — the pipeline still runs on CSVs + the simulator.
With DuckDB installed (requirements.txt), it creates
warehouse/capacity.duckdb with raw_demand_daily / raw_demand_by_queue.

Run: python3 src/load/load_duckdb.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "warehouse" / "capacity.duckdb"


def main():
    try:
        import duckdb
    except ImportError:
        print("duckdb not installed — skipping warehouse load "
              "(pip install -r requirements.txt to enable it).")
        return 0
    raw = ROOT / "data" / "raw"
    daily = raw / "demand_daily.csv"
    by_queue = raw / "demand_by_queue.csv"
    if not daily.exists():
        print(f"missing {daily} — run python3 src/generate/generate.py first")
        return 1
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(f"CREATE OR REPLACE TABLE raw_demand_daily AS "
                f"SELECT * FROM read_csv_auto('{daily}')")
    if by_queue.exists():
        con.execute(f"CREATE OR REPLACE TABLE raw_demand_by_queue AS "
                    f"SELECT * FROM read_csv_auto('{by_queue}')")
    n = con.execute("SELECT count(*) FROM raw_demand_daily").fetchone()[0]
    print(f"loaded {n} daily rows into {DB_PATH}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
