"""
Data refresh for a running server (the daily job in Docker).

Builds both datasets into a new release folder, checks them, and only then points the
`current` link at it and asks the server to reload. A release that fails a check is
deleted and the live data stays as it was.

    <data root>/releases/20261029-050000/{nba,euroleague}_data.json
    <data root>/current -> releases/20261029-050000

Usage:
    python backend/scripts/refresh_data.py [--data-root /data] [--keep 7] [--app-url URL] [--no-reload]

The admin token for the reload call comes from HOOPGRID_ADMIN_TOKEN.
"""

import argparse
import json
import os
import random
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))  # builder
sys.path.insert(0, str(ROOT))                            # backend

from backend.catalog.criteria import TEAM, build_index  # noqa: E402
from backend.catalog.players import LEAGUE_FILES, PlayerCatalog  # noqa: E402
from backend.game.board import BoardGenerator  # noqa: E402
from builder.euroleague import build_euroleague_database  # noqa: E402
from builder.nba import build_nba_database  # noqa: E402

# A new dataset may not shrink by more than this against the live one
MAX_SHRINK = 0.10
# Fewest players a criterion team may have before the release counts as broken
MIN_TEAM_PLAYERS = {"nba": 100, "euroleague": 15}
MIN_PLAYERS = {"nba": 4000, "euroleague": 2000}


def validate(release: Path, current: Path) -> list:
    """Problems with a freshly built release; empty when it is fit to go live."""
    problems = []
    for league in LEAGUE_FILES:
        new = PlayerCatalog.load(league, release)
        old = PlayerCatalog.load(league, current) if current.exists() else None
        if len(new.players) < MIN_PLAYERS[league]:
            problems.append(f"{league}: only {len(new.players)} players (need {MIN_PLAYERS[league]})")
            continue
        if old and old.players and len(new.players) < (1 - MAX_SHRINK) * len(old.players):
            problems.append(f"{league}: {len(new.players)} players, down from {len(old.players)}")
        index = build_index(new)
        for spec in index.of_kind(TEAM):
            members = sum(1 for p in new.players if spec.matches(p))
            if members < MIN_TEAM_PLAYERS[league]:
                problems.append(f"{league}: {spec.label} has only {members} players")
        generator = BoardGenerator(index, rng=random.Random(0))
        for style in ("classic", "mixed"):
            for _ in range(10):
                rows, cols = generator.generate(style, min_answers=2)
                if not generator.is_solvable(rows, cols, 1):
                    problems.append(f"{league}: an unsolvable {style} grid")
                    break
    return problems


def switch_current(root: Path, release: Path) -> None:
    """Points root/current at the release in one rename, so readers never see a gap."""
    tmp = root / ".current-new"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(release.relative_to(root), tmp)
    os.replace(tmp, root / "current")


def prune(releases: Path, keep: int, live: Path) -> None:
    old = sorted((p for p in releases.iterdir() if p.is_dir()), reverse=True)[keep:]
    for path in old:
        if path.resolve() != live.resolve():
            shutil.rmtree(path)


def reload_server(app_url: str) -> None:
    token = os.environ.get("HOOPGRID_ADMIN_TOKEN", "")
    if not token:
        print("No HOOPGRID_ADMIN_TOKEN: the server picks up the new data on its next restart.")
        return
    req = urllib.request.Request(f"{app_url}/admin/reload", method="POST", headers={"X-Admin-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"Server reloaded: {json.loads(r.read())['players']}")
    except Exception as e:  # the data is switched either way
        print(f"Reload call failed ({e}); the server picks up the new data on its next restart.")


def main():
    parser = argparse.ArgumentParser(description="Build, check and publish fresh player data.")
    parser.add_argument("--data-root", type=Path, default=Path(os.environ.get("HOOPGRID_DATA_ROOT", "/data")))
    parser.add_argument("--keep", type=int, default=7, help="releases to keep for rollback")
    parser.add_argument("--app-url", default=os.environ.get("HOOPGRID_APP_URL", "http://app:8000"))
    parser.add_argument("--no-reload", action="store_true")
    args = parser.parse_args()

    root = args.data_root
    releases = root / "releases"
    current = root / "current"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    release = releases / stamp
    release.mkdir(parents=True)

    try:
        build_nba_database(release)
        build_euroleague_database(release)
    except Exception as e:
        shutil.rmtree(release)
        print(f"Build failed: {e}. The live data is unchanged.")
        return 1

    problems = validate(release, current)
    if problems:
        shutil.rmtree(release)
        print("Release rejected, the live data is unchanged:\n  " + "\n  ".join(problems))
        return 1

    switch_current(root, release)
    prune(releases, args.keep, release)
    print(f"Live data is now {release.name}")
    if not args.no_reload:
        reload_server(args.app_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
