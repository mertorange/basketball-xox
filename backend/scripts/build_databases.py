"""
Database Builder for Hoop Grid
Rebuilds the NBA and EuroLeague player datasets in backend/data from public sources.

The work lives in the `builder` package next to this file: one module per external
source (builder/sources/), one per league (builder/nba.py, builder/euroleague.py) and the
shared name/country helpers (builder/common.py). DATA.md describes the pipeline and rules.

Usage:
    python backend/scripts/build_databases.py [--league nba|euroleague|all] [--out DIR]

Only the Python standard library is needed.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # also under `python -I`

from builder.common import DATA_DIR  # noqa: E402
from builder.euroleague import build_euroleague_database  # noqa: E402
from builder.nba import build_nba_database  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Rebuild Hoop Grid player datasets.")
    parser.add_argument("--league", choices=["nba", "euroleague", "all"], default="all")
    parser.add_argument("--out", type=Path, default=DATA_DIR,
                        help="output directory (default: backend/data, overwriting the current datasets)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    if args.league in ("nba", "all"):
        build_nba_database(args.out)
    if args.league in ("euroleague", "all"):
        build_euroleague_database(args.out)


if __name__ == "__main__":
    sys.exit(main())
