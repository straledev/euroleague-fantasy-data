# EuroLeague Fantasy Data

![Update data](https://github.com/straledev/euroleague-fantasy-data/actions/workflows/update-stats.yml/badge.svg)

An open, regularly updated dataset for **EuroLeague Fantasy Challenge** analysis and modelling — player box scores game by game, PIR, fantasy points, credits (prices) and price changes.

Inspired by [vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League), which does the same for FPL. No comparable public, structured dataset existed for EuroLeague Fantasy, so this repo aims to be one.

## What's inside

| Source | What | Updated |
|---|---|---|
| Official EuroLeague API (via [`euroleague-api`](https://github.com/giasemidis/euroleague_api)) | Box score for every player in every game: minutes, points, shooting splits, rebounds, assists, steals, turnovers, blocks, fouls, PIR, +/- | Automatically every day (GitHub Actions) |
| EuroLeague Fantasy Challenge | Fantasy points (FPT), credits, credit change, position, coach stats | Snapshots taken manually before each round |

Current season: **2026-27**.

## Data structure

```
data/
└── 2026-27/
    ├── cleaned_players.csv              # season averages per player (games, minutes, PIR avg/std/total...)
    ├── rounds/
    │   ├── round_<n>.csv                # all players in round n
    │   └── merged_rounds.csv            # every player, every game, one file
    ├── players/
    │   └── <name>_<player_id>/rounds.csv  # game-by-game log for one player
    └── fantasy/
        ├── players_latest.csv           # most recent fantasy snapshot
        └── snapshots/
            └── players_<YYYY-MM-DD_HHMM>.csv  # every snapshot, timestamped (UTC)
```

Column descriptions are in [DATA_DICTIONARY.md](DATA_DICTIONARY.md).

## Using the data directly

No need to clone the repo — read any file straight from GitHub:

```python
import pandas as pd

base = "https://raw.githubusercontent.com/straledev/euroleague-fantasy-data/main/data/2026-27"

games = pd.read_csv(f"{base}/rounds/merged_rounds.csv")
fantasy = pd.read_csv(f"{base}/fantasy/players_latest.csv")

# top 10 players by average PIR (min. 4 games)
season = pd.read_csv(f"{base}/cleaned_players.csv")
print(season[season.games >= 4].head(10))
```

## Running it yourself

```bash
git clone https://github.com/straledev/euroleague-fantasy-data.git
cd euroleague-fantasy-data
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
```

**Box score data** (public API, no login):

```bash
python collector.py --season 2026                 # 2026 = the 2026-27 season
python collector.py --season 2025 --season 2024   # several seasons at once
```

**Fantasy data** requires your own EuroLeague Fantasy Challenge login token:

1. Log in to the Fantasy Challenge in your browser and open DevTools → Network.
2. Open the *Stats* page and find the `table?...` request.
3. Copy the value of its `Authorization` request header.
4. Create a `.env` file in the project root (it is git-ignored — never commit it):
   ```
   DUNKEST_TOKEN=Bearer <your token>
   ```
5. Run:
   ```bash
   python fantasy_scraper.py                 # averages (default)
   python fantasy_scraper.py --stats-type tot  # season totals
   ```

The token expires after a while; if you get a `401`, copy a fresh one.

## Notes for modelling

- **Use pre-deadline prices.** Credits change after every round. When modelling round *N*, use the snapshot taken *before* the round *N* deadline — a snapshot taken afterwards already reflects round *N* performance and leaks the target into your features.
- **FPT ≠ PIR.** Fantasy points for players follow a formula related to, but not identical to, PIR. Coaches are scored by game results (win/loss margin columns).
- **Team codes differ between sources.** The EuroLeague API and the Fantasy game use different team abbreviations (e.g. `MAD` vs `RMB`, `IST` vs `EFS`) and different name formats (`VEZENKOV, SASHA` vs `S. Vezenkov`). Joining the two requires a mapping — planned as `merger.py`.
- **Small samples.** Early in the season or after injuries, averages rest on few games. Filter on the `games` column.
- `IsPlaying` from the API is **not** "did the player play" — use `minutes > 0` instead.

## Roadmap

- [x] Box score collector + daily automation
- [x] Fantasy prices / points snapshots
- [ ] `merger.py` — join box scores with fantasy data (team & player mapping)
- [ ] Historical seasons (2016-17 onwards)
- [ ] EDA notebook
- [ ] FPT prediction model and lineup optimizer (100 credits, 4G / 4F / 2C + coach)

## Disclaimer

This is an unofficial, non-commercial project for education and analysis. It is not affiliated with or endorsed by Euroleague Basketball or Dunkest. All data belongs to its respective owners.

## Acknowledgements

- [giasemidis/euroleague_api](https://github.com/giasemidis/euroleague_api) — Python wrapper for the EuroLeague API
- [vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League) — the inspiration for the structure of this dataset

## License

[MIT](LICENSE)
