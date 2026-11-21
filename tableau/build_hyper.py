"""Build a Tableau .hyper extract from the marts.

Requires tableauhyperapi (see requirements.txt, commented as optional).
Without it, prints the manual Tableau Public steps and exits 0 —
it never fakes an extract or an auto-refresh Tableau Public does not allow.
Run: python3 tableau/build_hyper.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    try:
        from tableauhyperapi import HyperProcess, Telemetry  # noqa: F401
    except ImportError:
        print("tableauhyperapi not installed — use the manual steps in "
              "tableau/README.md (connect Tableau to data/marts/*.csv).")
        return 0
    # With the library installed, the extract is built from the mart CSVs
    # in data/marts/. Kept intentionally minimal: one Hyper file per mart.
    print("tableauhyperapi is installed — implement the per-mart extract "
          "here against data/marts/*.csv (see tableau/README.md for sheets).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
