"""Builds backend/data/euroleague_data.json.

Season years follow the NBA convention in the dataset: a season is named after the year it
ends, so the API's E2024 (2024-25) is season 2025.
"""

from .aliases import apply_aliases
from .common import clean_player_name, load_previous_players, name_key, write_dataset
from .euroleague_clubs import STANDARD_EUROLEAGUE_CLUBS, normalize_euroleague_club
from .sources.euroleague_api import (fetch_career_stats, fetch_champions, fetch_euroleague_people,
                                     fetch_final_four_clubs)


EUROLEAGUE_POSITIONS = {"Guard": "G", "Forward": "F", "Center": "C"}


def build_euroleague_database(out_dir):
    print("\nBuilding EuroLeague database...")
    criteria = set(STANDARD_EUROLEAGUE_CLUBS)
    champions = fetch_champions()
    final_four = fetch_final_four_clubs()
    career = fetch_career_stats()

    players = []
    for entry in fetch_euroleague_people().values():
        if not entry["clubs"] & criteria:
            continue
        player = {
            "name": max(entry["names"])[1],
            "country": max(entry["countries"])[1] if entry["countries"] else "",
            "teams": sorted(entry["clubs"]),
        }
        seasons = [season for season, _ in entry["seasons"]]
        if seasons:
            player["seasons"] = [min(seasons) + 1, max(seasons) + 1]
        awards = set()
        for season, club in entry["seasons"]:
            if champions.get(season) == club:
                awards.add("champion")
            if club in final_four.get(season, ()):
                awards.add("final_four")
        if awards:
            player["awards"] = sorted(awards)
        stats = [career[code] for code in entry["codes"] if code in career]
        if stats:
            player["stats"] = {key: sum(s[key] for s in stats) for key in stats[0]}
        # Kept only when another player has the same name (see common.mark_shared_names)
        player["_born"] = entry["dob"]
        player["_pos"] = EUROLEAGUE_POSITIONS.get(max(entry["positions"])[1]) if entry["positions"] else None
        players.append(player)

    # Carry over previous entries (hand-curated legends from before 2000-01)
    by_key = {name_key(p["name"]): p for p in players}
    carried = 0
    for old in load_previous_players("euroleague_data.json"):
        clubs = {normalize_euroleague_club(t) for t in old.get("teams", [])}
        current = by_key.get(name_key(old["name"]))
        if current:
            # Pre-2000 stints only exist in the curated data
            current["teams"] = sorted(set(current["teams"]) | clubs)
            if not current["country"]:
                current["country"] = old.get("country", "")
            continue
        if clubs & criteria:
            carried += 1
            entry = {"name": clean_player_name(old["name"]), "country": old.get("country", ""),
                     "teams": sorted(clubs)}
            players.append(entry)
            by_key[name_key(entry["name"])] = entry
    print(f"  {carried} players carried over from the previous dataset")

    write_dataset(out_dir, "euroleague_data.json", "EuroLeague", STANDARD_EUROLEAGUE_CLUBS,
                  apply_aliases("euroleague", players))
