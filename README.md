# 🏀 Hoop-Tac-Toe

A competitive 2-player basketball trivia game blending **Tic-Tac-Toe (XOX)** with **Grid Trivia** (Immaculate Grid style).

Two players compete head-to-head on a 3x3 board. Each box is determined by the intersection of a **Row Criterion** and a **Column Criterion** (e.g. *Los Angeles Lakers* + *Miami Heat*, *France* + *Dallas Mavericks*, or *MVP* + *Boston Celtics*).

---

## 🎮 Game Rules
1. **The Grid:** 3 rows and 3 columns (9 boxes total).
2. **Turn-based 1v1:** Player 1 (`X`) vs Player 2 (`O`), on one device or in an online room. The first move alternates between grids.
3. **Drafting a Player:** To claim a box, you must pick a basketball player who matches **BOTH** the row and column criteria. Country criteria use the player's country of birth (Kyrie Irving counts for Australia).
4. **Fouls / Turnovers:** If you make an invalid guess or name a player that was already picked, you commit a turnover and forfeit your turn to your opponent!
5. **No Re-use:** Each basketball player can only be picked once per match.
6. **Winning:** The first player to get 3 claimed boxes in a row (horizontally, vertically, or diagonally) wins the game! If all 9 boxes are claimed without 3-in-a-row, it's a draw.
7. **Series:** a match is best of 1, 3, 5 or 7 grids (chosen in the menu). The first to win more than half takes it; drawn grids don't count.
8. **Skip & draw:** *Skip turn* passes the ball to your opponent. *Draw this grid* writes the current grid off and deals a new one, with the series score unchanged: online the other player must accept the offer (Yes / No under the button); on one device, press it twice to confirm.

---

## 🌟 Features
- **Two League Modes:** 
  - 🏀 **NBA Mode:** Star players, historic franchises, and international NBA talents.
  - 🏆 **EuroLeague Mode:** Continental giants (Real Madrid, Panathinaikos, Fenerbahçe, Olympiacos, Barcelona, etc.) and European legends.
- **Online Rooms:** Create a room, send the four-letter code or the invite link, and play from two devices. The server runs the shot clock, shows which box your opponent has open, keeps the series score, and holds your seat if you reload (two minutes to come back before a forfeit). A separate watch link lets up to 20 spectators follow the game live.
- **Answers After the Game:** Once a grid is over, see every player who fit each box, the best known first, next to the ones you picked. The answer key never leaves the server while a game is running.
- **Grid Styles:** *Mixed* (default) crosses teams with awards (champion, MVP, Finals MVP, All-NBA, ROY, DPOY, 6MOY, MIP; EuroLeague title, Final Four), draft slots (#1 pick, top 10, second round, undrafted), colleges, eras and career marks (5+ franchises; 1,000+ EuroLeague points…). *Classic* keeps to teams and countries of birth. *Custom* lets you tick the categories yourself (birth country, college, draft slot, awards, career marks, eras); teams are always in, and the picker only shows the categories the league has.
- **Difficulty levels:** *Easy*, *Medium* and *Hard* set how many **well-known** players fit each box, not just how many answers exist: a box whose forty answers are all bench players is hard. Fame comes from Wikipedia reach, minutes and awards in the NBA, and from EuroLeague games, points and titles in the EuroLeague (see DATA.md §3.1). Among the grids that fit, the most even one is dealt, so a grid never mixes a giveaway with a box nobody can fill.
- **Real-Time Autocomplete Search:** Search player names smoothly with keyboard navigation and typo-free selection.
- **Sound Effects:** Dynamic audio cues (swish on correct answers, referee buzzer on fouls, and victory fanfares) synthesized via Web Audio API with zero external audio assets.
- **Modular Architecture:** A criteria registry, board generator, rules and game manager on the backend; one ES module per screen part on the frontend; one builder module per data source.

---

## 🚀 Quick Start

### 1. With Docker (recommended)
```bash
cp .env.example .env        # set HOOPGRID_ADMIN_TOKEN at least
docker compose up -d --build
```
The game runs at **http://localhost:8000** (`HOOPGRID_PORT` changes the port). The image build runs the test suite and stops if a test fails. On first start the datasets baked into the image are copied to the `hoopgrid-data` volume.

Refresh the player data (new signings, trades) without stopping the game:
```bash
docker compose run --rm builder
```
It builds into a new release on the volume, checks it (player counts, team sizes, solvable grids), switches the `current` link only if every check passes, keeps the last 7 releases and tells the server to reload. Open rooms and running games are not interrupted.

### 2. Without Docker
Python 3.10+ and the packages in `requirements.txt` (`fastapi`, `uvicorn`, `pydantic`, `websockets`):
```bash
python run.py
```
This launches the server and opens **http://localhost:8000**. Or run uvicorn directly: `uvicorn backend.app:app --port 8000`.

### 3. On a server
On a VPS with Docker and a domain pointing at it:
```bash
git clone https://github.com/mertorange/basketball-xox.git && cd basketball-xox
cp .env.example .env        # HOOPGRID_DOMAIN, HOOPGRID_ADMIN_TOKEN, HOOPGRID_ALLOWED_ORIGINS
docker compose --profile server up -d --build
```
The `server` profile adds Caddy, which gets the HTTPS certificate and forwards WebSockets. For a daily data refresh add a cron line such as:
```
0 5 * * * cd /path/to/basketball-xox && docker compose run --rm builder >> refresh.log 2>&1
```
Rooms live in the app container's memory: keep a single `app` container with one worker (as configured), and expect a restart or redeploy to end open rooms. `GET /health` reports players, rooms and games.

### 4. Tests
```bash
pip install pytest httpx
python -m pytest tests
```
`HOOPGRID_DATA_DIR=/some/dir` points the server (and the real-data tests) at another set of dataset files.

### Settings (environment)
| Variable | Purpose |
|---|---|
| `HOOPGRID_ADMIN_TOKEN` | Secret for `POST /admin/reload` (used by the data refresh); empty disables it |
| `HOOPGRID_ALLOWED_ORIGINS` | CORS origins, comma separated (default `*`) |
| `HOOPGRID_DOMAIN` | Public host name for Caddy (server profile) |
| `HOOPGRID_PORT` | Host port of the app container (bound to 127.0.0.1) |
| `HOOPGRID_RATE_LIMIT` | `0` turns off the per-IP limits on room creation, new games and search |
| `HOOPGRID_DATA_DIR` | Where the server reads the datasets (Docker: `/data/current`) |

---

## 📁 Project Structure
```
basketball-xox/
├── backend/
│   ├── app.py                # App factory: loads catalogs, mounts API and frontend
│   ├── api.py                # HTTP routes
│   ├── models.py             # Pydantic request/response models
│   ├── catalog/
│   │   ├── players.py        # Dataset loading, name lookup, autocomplete
│   │   └── criteria.py       # Criterion registry: team, country, college, draft, award, career, era
│   ├── game/
│   │   ├── board.py          # Grid generation (classic / mixed) with answer checks
│   │   ├── rules.py          # Lines, draws, turns
│   │   └── manager.py        # Running games, moves, turnovers
│   ├── online/
│   │   ├── rooms.py          # Rooms, seats, server-side shot clock, reconnects, rematches
│   │   ├── protocol.py       # WebSocket message types
│   │   └── ws.py             # /api/rooms and /ws/rooms/{code}
│   ├── config.py, ratelimit.py  # Settings from the environment, per-IP request limits
│   ├── data/                 # Generated datasets (see DATA.md)
│   └── scripts/
│       ├── build_databases.py   # CLI
│       ├── refresh_data.py      # Build -> check -> switch release -> reload the server
│       └── builder/             # common.py, nba.py, euroleague.py, sources/<one per source>
├── frontend/
│   ├── index.html            # Scoresheet layout
│   ├── style.css             # Paper-and-ink styling
│   └── js/                   # main.js (menu, screens), hotseat.js / onlinegame.js (controllers),
│                             # online.js (room socket), api, board, clock, slip, scoresheet, sound, dom
├── tests/                    # pytest: criteria, board, game, API, online rooms, builder helpers
├── DATA.md                   # Data sources, pipeline, rules, gaps, licensing
├── Dockerfile                # Test stage + app image (non-root, one worker, healthcheck)
├── docker-compose.yml        # app, builder (data refresh), caddy (server profile)
├── docker/                   # entrypoint (seeds the data volume), Caddyfile
├── .env.example
├── requirements.txt
└── run.py                    # One-click launcher
```

---

## 📊 Data Sources
The datasets in `backend/data/` are generated by `python backend/scripts/build_databases.py` (standard library only):
- **NBA:** [Basketball GM community rosters](https://github.com/alexnoob/BasketBall-GM-Rosters) (recent seasons), ESPN's public roster feed (the current season), [FiveThirtyEight NBA player data](https://github.com/fivethirtyeight/nba-player-advanced-metrics) (1977–2020 team histories, CC BY 4.0) and [Wikidata](https://www.wikidata.org) (historical players and birthplaces, CC0).
- **EuroLeague:** the official EuroLeague API (season registrations since 2000-01).

Full details (pipeline, merge rules, known gaps, licensing) are in [DATA.md](DATA.md).

---

## 🛠️ Roadmap

### Done
- [x] Stat & award criteria: NBA champion, MVP, Finals MVP, All-NBA, ROY, DPOY, 6MOY, MIP, draft slots, colleges, eras; EuroLeague champion, Final Four, career totals.
- [x] Online rooms over WebSockets: room codes, invite and watch links, server-side shot clock, reconnects, spectators.
- [x] Post-game "all answers" view, most famous players first.
- [x] Docker image and compose setup with a checked, zero-downtime data refresh.
- [x] Best-of-1/3/5/7 series; *Skip turn*, and *Draw this grid* (both players agree; a new grid is dealt).
- [x] Difficulty levels (Easy / Medium / Hard) counted in well-known answers per box, with a fame score per league.
- [x] *Custom* grids: pick the categories mixed with teams.
- [x] Autocomplete that only sends names from the list, so a typo never costs the turn.
- [x] Basketball look (hardwood, scoreboard, varsity type), mute button, everything fits on one screen.
- [x] Online games can't be played or skipped through the same-device HTTP routes.

### Before a public launch
- [ ] **Data licensing**: get written permission for the Basketball GM roster data (ZenGM's licence is not open source) or move awards, championships and recent rosters to open sources (Wikidata, Wikipedia); replace the unofficial ESPN roster feed; check the EuroLeague API terms. See DATA.md §8.
- [ ] Run it on a VPS with a daily refresh cron.
- [ ] Rate-limit room lookups, WebSocket joins and messages; let the rate limiter forget old IPs.
- [ ] Pin dependency versions.
- [ ] "Unofficial fan game, not affiliated with the NBA, EuroLeague or any club" notice; drop "Official" from the menu.

### Gameplay fixes
- [ ] Merge EuroLeague players stored under two spellings (Edy / Walter Tavares, Theo / Theodoros Papaloukas, Gigi / Luigi Datome, Bobby Dixon / Ali Muhammed), who can currently be used twice.
- [ ] Tell same-named players apart (Mike James) in the search list and in the used-player check.
- [ ] Accent-insensitive search ("Dončić") and nicknames ("KD", "Penny", "Melo").
- [ ] Free a lobby seat when its player leaves before tip-off.

### If ads go in
- [ ] Privacy policy page and a cookie consent banner (GDPR / KVKK).
- [ ] Ad slots on the menu, lobby and result screens only, never during a turn.
- [ ] A donation link as a lighter alternative.

### Quality and data
- [ ] Frontend smoke tests in a real browser.
- [ ] Skip the release-switch test on Windows when symlinks aren't allowed.
- [ ] Count awards (seven All-NBA teams, not one) and fix Wikidata matches for a few stars (Durant, McGrady, Dwight Howard).
- [ ] EuroLeague MVP and *50+ point game* criteria (no source yet; see DATA.md).
- [ ] Keep generated datasets out of git, or write one player per line.

### Ideas
- [ ] Rarity points: rarer correct answers score more, as a tiebreak.
- [ ] Steal mode: take an opponent's box with a rarer player.
- [ ] Make the centre box (it sits on four lines) the hardest.
- [ ] Daily shared grid; play against a bot.
- [ ] Show a claimed player's teams on the box.
- [ ] Quick match queue, then accounts and ratings.
- [ ] SQLite / PostgreSQL for full career stats.
