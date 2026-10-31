"""
Data refresh for a running server (the daily job in Docker).

Builds both datasets into a new release folder, checks them, and only then points the
`current` link at it and asks the server to reload. A release that fails a check is
deleted and the live data stays as it was.

    <data root>/releases/20261029-050000/{nba,euroleague}_data.json
    <data root>/current -> releases/20261029-050000

The datasets shipped inside the Docker image are published the same way when a container
starts (see docker/entrypoint.sh), but only when the volume has not seen them yet: on the
first start and after an image update, whose code may expect new fields. Restarting the
same image keeps whatever the last refresh published.

    <data root>/releases/image-1a2b3c4d5e6f/   datasets from the image, by content
    <data root>/.image-data                    fingerprint of the last image data published

Usage:
    python backend/scripts/refresh_data.py [--data-root /data] [--keep 7] [--app-url URL] [--no-reload]
    python backend/scripts/refresh_data.py --publish-image-data /app/backend/data

The admin token for the reload call comes from HOOPGRID_ADMIN_TOKEN.
"""

import argparse
import hashlib
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
from backend.catalog.fame import is_well_known  # noqa: E402
from backend.catalog.players import LEAGUE_FILES, PlayerCatalog  # noqa: E402
from backend.game.board import BoardGenerator  # noqa: E402
from builder.euroleague import build_euroleague_database  # noqa: E402
from builder.nba import build_nba_database  # noqa: E402

# A new dataset may not shrink by more than this against the live one
MAX_SHRINK = 0.10
# Fewest players a criterion team may have before the release counts as broken
MIN_TEAM_PLAYERS = {"nba": 100, "euroleague": 15}
MIN_PLAYERS = {"nba": 4000, "euroleague": 2000}

# Grid difficulty rests on fame (backend/catalog/fame.py): these must rank as well known,
# and these must not. A source that drops page counts or stats shows up here first.
FAME_CHECKS = {
    "nba": {
        "famous": ["LeBron James", "Michael Jordan", "Stephen Curry", "Kevin Durant", "Victor Wembanyama",
                   "Pete Maravich", "Bill Russell", "Wilt Chamberlain", "Steve Nash", "Yao Ming",
                   "Jeremy Lin", "Dennis Rodman"],
        "unknown": ["Reggie Jordan", "Gary Grant"],
    },
    "euroleague": {
        "famous": ["Vassilis Spanoulis", "Sergio Llull", "Dimitris Diamantidis", "Milos Teodosic", "Shane Larkin",
                   "Mike James", "Walter Tavares", "Keith Langford", "Kostas Sloukas", "Nando De Colo"],
        "unknown": ["Onuralp Bitim"],
    },
}
# Share of NBA players with a Wikimedia page count; it falls if the Wikidata match breaks
MIN_NBA_PAGE_SHARE = 0.7


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
        problems += fame_problems(league, new)
        generator = BoardGenerator(index, rng=random.Random(0))
        for style in ("classic", "mixed"):
            for _ in range(10):
                rows, cols = generator.generate(style, "medium")
                if not generator.is_solvable(rows, cols, 1):
                    problems.append(f"{league}: an unsolvable {style} grid")
                    break
    return problems


def fame_problems(league: str, catalog: PlayerCatalog) -> list:
    problems = []
    for expect, names in FAME_CHECKS[league].items():
        for name in names:
            players = catalog.find(name)
            if not players:
                problems.append(f"{league}: {name} is missing")
            elif any(is_well_known(league, p) for p in players) != (expect == "famous"):
                problems.append(f"{league}: {name} should {'' if expect == 'famous' else 'not '}rank as well known "
                                f"(fame {max(p['fame'] for p in players)})")
    if league == "nba":
        share = sum("wiki_pages" in p for p in catalog.players) / max(len(catalog.players), 1)
        if share < MIN_NBA_PAGE_SHARE:
            problems.append(f"nba: only {share:.0%} of players have a Wikimedia page count")
    return problems


def switch_current(root: Path, release: Path) -> None:
    """Points root/current at the release in one rename, so readers never see a gap."""
    tmp = root / ".current-new"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(release.relative_to(root), tmp)
    os.replace(tmp, root / "current")


def prune(releases: Path, keep: int, live: Path) -> None:
    """Keeps the `keep` newest releases (and the live one). Newest by creation time, not by
    name: image releases ('image-…') would otherwise always sort after dated ones."""
    old = sorted((p for p in releases.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime,
                 reverse=True)[keep:]
    for path in old:
        if path.resolve() != live.resolve():
            shutil.rmtree(path)


IMAGE_MARKER = ".image-data"


def data_fingerprint(folder: Path) -> str:
    """Short hash of a folder's dataset files, names and contents."""
    digest = hashlib.sha256()
    for path in sorted(folder.glob("*.json")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def publish_image_data(root: Path, image_data: Path, keep: int = 7):
    """Publishes the image's datasets unless this volume already took these exact files.

    Returns the release name when it switched `current`, None when nothing changed.
    """
    fingerprint = data_fingerprint(image_data)
    marker = root / IMAGE_MARKER
    seen = marker.read_text().strip() if marker.exists() else None
    if (root / "current").exists() and seen == fingerprint:
        return None
    release = root / "releases" / f"image-{fingerprint}"
    if not release.exists():
        release.mkdir(parents=True)
        for path in image_data.glob("*.json"):
            shutil.copy2(path, release / path.name)
        os.utime(release)  # newest for prune(), whatever the copied files' dates
    switch_current(root, release)
    marker.write_text(fingerprint)
    prune(root / "releases", keep, release)
    return release.name


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
    parser.add_argument("--publish-image-data", type=Path, metavar="DIR",
                        help="publish the datasets in DIR if the volume has not seen them, then stop")
    args = parser.parse_args()

    root = args.data_root
    if args.publish_image_data:
        published = publish_image_data(root, args.publish_image_data, args.keep)
        print(f"Live data is now {published} (from the image)." if published
              else "Image data already published; keeping the live data.")
        return 0

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
