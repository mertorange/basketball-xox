# 🏀 Basketball XOX (Hoops Grid Tic-Tac-Toe)

A competitive 2-player basketball trivia game blending **Tic-Tac-Toe (XOX)** with **Grid Trivia** (Immaculate Grid style).

Two players compete head-to-head on a 3x3 board. Each box is determined by the intersection of a **Row Criterion** and a **Column Criterion** (e.g. *Los Angeles Lakers* + *Miami Heat*, or *France* + *Dallas Mavericks*).

---

## 🎮 Game Rules
1. **The Grid:** 3 rows and 3 columns (9 boxes total).
2. **Turn-based 1v1:** Player 1 (`X`) vs Player 2 (`O`).
3. **Drafting a Player:** To claim a box, you must pick a basketball player who matches **BOTH** the row and column criteria.
4. **Fouls / Turnovers:** If you make an invalid guess or name a player that was already picked, you commit a turnover and forfeit your turn to your opponent!
5. **No Re-use:** Each basketball player can only be picked once per match.
6. **Winning:** The first player to get 3 claimed boxes in a row (horizontally, vertically, or diagonally) wins the game! If all 9 boxes are claimed without 3-in-a-row, it's a draw.

---

## 🌟 Features
- **Two League Modes:** 
  - 🏀 **NBA Mode:** Star players, historic franchises, and international NBA talents.
  - 🏆 **EuroLeague Mode:** Continental giants (Real Madrid, Panathinaikos, Fenerbahçe, Olympiacos, Barcelona, etc.) and European legends.
- **Smart Balanced Board Generation:** Ensures every generated 3x3 grid is 100% solvable with valid players for each box.
- **Real-Time Autocomplete Search:** Search player names smoothly with keyboard navigation and typo-free selection.
- **Sound Effects:** Dynamic audio cues (swish on correct answers, referee buzzer on fouls, and victory fanfares) synthesized via Web Audio API with zero external audio assets.
- **Modular Data Architecture:** Separated JSON datasets ready to be upgraded to SQLite, PostgreSQL, or live basketball APIs (NBA/EuroLeague data).

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+ (works seamlessly with Anaconda or standard Python)
- Packages listed in `requirements.txt` (`fastapi`, `uvicorn`, `pydantic`)

### 2. Launching the Game
Simply run:
```bash
python run.py
```
This will launch the backend server and automatically open **http://localhost:8000** in your default web browser.

Alternatively, run manually with uvicorn:
```bash
uvicorn backend.app:app --reload --port 8000
```

---

## 📁 Project Structure
```
basketball-xox/
├── backend/
│   ├── app.py                # FastAPI endpoints and static file serving
│   ├── game_engine.py        # Board generation, rules, turns, Tic-Tac-Toe checks
│   ├── models.py             # Pydantic models for GameState, Criteria, Cell, Moves
│   └── data/
│       ├── nba_data.json     # Curated NBA players, teams, and nationalities
│       └── euroleague_data.json # Curated EuroLeague players, clubs, and nationalities
├── frontend/
│   ├── index.html            # Game board interface, scoreboard, turn indicators
│   ├── style.css             # Stadium court dark mode styling and animations
│   └── app.js                # Game client controller, sound effects, API calls
├── requirements.txt          # Python dependencies
├── run.py                    # One-click launcher script
└── README.md
```

---

## 🛠️ Upcoming Roadmap / Future Extensions
- [ ] Connect SQLite / PostgreSQL database for full career player stats.
- [ ] Stat & award criteria (e.g. *NBA Champion*, *EuroLeague MVP*, *50+ Pt Game*, *Drafted 1st overall*).
- [ ] Online multiplayer room codes via WebSockets.
