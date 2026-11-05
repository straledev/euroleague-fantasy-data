# EuroLeague Fantasy Data

![Update data](https://github.com/straledev/euroleague-fantasy-data/actions/workflows/update-stats.yml/badge.svg)
![Fantasy snapshot](https://github.com/straledev/euroleague-fantasy-data/actions/workflows/fantasy-snapshot.yml/badge.svg)

An open, automatically updated dataset for **EuroLeague Fantasy Challenge** analysis and modelling: player box scores game by game, PIR, opponents and results, fantasy points, credits (prices), price history and fantasy positions.

Inspired by [vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League), which does the same for FPL. No comparable public, structured dataset existed for EuroLeague Fantasy, so this repo aims to be one.

## What's inside

| Source | What | Updated |
|---|---|---|
| Official EuroLeague API (via [`euroleague-api`](https://github.com/giasemidis/euroleague_api)) | Box score for every player in every game (minutes, points, shooting splits, rebounds, assists, steals, turnovers, blocks, fouls, PIR, +/-), plus opponent, final score and result | Every day at 06:37 UTC |
| EuroLeague Fantasy Challenge (run by Fantaking / Dunkest) | Fantasy points (FPT), credits, credit change, position, coach stats | Every day at 10:17 UTC, saved only when something changed |
| This repo | Player map linking box-score players to fantasy IDs and positions | With every update |

Current season: **2026-27**. Historical seasons from 2016-17 are being added (box scores only).

## Accuracy

Every game is checked before it is saved:

- the players' points add up **exactly** to the official final score;
- both teams are present, no player appears twice;
- PIR from the API equals PIR recomputed from the box score.

A game that fails is not saved and is retried on the next run. Games already stored are never deleted. [`collection_status.json`](data/2026-27/collection_status.json) shows how many games are played, stored and verified, and lists anything missing. When a game is missing, or less than 99% of minutes played can be linked to a fantasy position, the daily update fails visibly instead of publishing incomplete data.

## Data structure

```
data/
└── 2026-27/
    ├── cleaned_players.csv              # season averages per player (games, minutes, PIR avg/std/total...)
    ├── schedule.csv                     # every played game: round, date, teams, final score
    ├── collection_status.json           # is the dataset complete? (games played vs stored and verified)
    ├── player_map.csv                   # box score player ↔ fantasy ID and position
    ├── rounds/
    │   ├── round_<n>.csv                # all players in regular-season round n
    │   ├── <phase>_round_<n>.csv        # play-in, playoffs, Final Four (po_round_1.csv...)
    │   └── merged_rounds.csv            # every player, every game, one file
    ├── players/
    │   └── <name>_<player_id>/rounds.csv  # game-by-game log for one player
    └── fantasy/
        ├── players_latest.csv           # most recent fantasy snapshot
        └── snapshots/
            └── players_<YYYY-MM-DD_HHMM>.csv  # every snapshot, timestamped (UTC)
config/
└── player_overrides.csv                 # positions set by hand for players the matcher can't link
```

Column descriptions are in [DATA_DICTIONARY.md](DATA_DICTIONARY.md).

## Using the data directly

No need to clone the repo. Read any file straight from GitHub:

```python
import pandas as pd

base = "https://raw.githubusercontent.com/straledev/euroleague-fantasy-data/main/data/2026-27"

games = pd.read_csv(f"{base}/rounds/merged_rounds.csv")
pmap = pd.read_csv(f"{base}/player_map.csv")
fantasy = pd.read_csv(f"{base}/fantasy/players_latest.csv")

# add fantasy positions to every game
games = games.merge(pmap[["player_id", "team", "position", "dunkest_id"]],
                    on=["player_id", "team"], how="left")

# points each team allows to opposing guards, per game
guards = games[(games.position == "Guard") & (games.minutes > 0)]
allowed = guards.groupby(["opponent", "game_code"]).pts.sum().groupby("opponent").mean()
print(allowed.sort_values(ascending=False).round(1))
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

The collector is incremental: it downloads only games that are missing, retries failed requests and keeps everything already stored.

**Player map:**

```bash
python merger.py --season 2026
```

It prints the players it could not link. Add them to `config/player_overrides.csv` with their position.

**Fantasy data** requires your own EuroLeague Fantasy Challenge login token:

1. Log in to the Fantasy Challenge in your browser and open DevTools → Network.
2. Open the *Stats* page and find the `table?...` request.
3. Copy the value of its `Authorization` request header.
4. Create a `.env` file in the project root (it is git-ignored, never commit it):
   ```
   DUNKEST_TOKEN=Bearer <your token>
   ```
5. Run:
   ```bash
   python fantasy_scraper.py                   # averages (default)
   python fantasy_scraper.py --stats-type tot  # season totals
   python fantasy_scraper.py --force           # save a snapshot even if nothing changed
   ```

The token expires after a while; if you get a `401`, copy a fresh one.

## Automation

Three GitHub Actions workflows keep the data current:

| Workflow | When | What |
|---|---|---|
| [Update EuroLeague box score data](.github/workflows/update-stats.yml) | Daily, 06:37 UTC | New games, checks, player map |
| [Fantasy prices snapshot](.github/workflows/fantasy-snapshot.yml) | Daily, 10:17 UTC | New fantasy snapshot when prices or points changed |
| [Backfill historical seasons](.github/workflows/backfill.yml) | Manually | Downloads past seasons, one commit per season |

The fantasy workflow reads the token from the repository secret `DUNKEST_TOKEN`.

## Notes for modelling

- **Use pre-deadline prices.** Credits change after every round. When modelling round *N*, use the snapshot taken *before* the round *N* deadline. A snapshot taken afterwards already reflects round *N* performance and leaks the target into your features.
- **FPT ≈ PIR.** Fantasy points for players follow PIR plus a 10% bonus when the team wins. `fpt_est` in the box score files applies that rule per game; it is an estimate, since the game publishes FPT only as averages and totals. Coaches are scored by game results (win/loss margin columns).
- **Fantasy data starts in 2026-27.** Historical seasons contain box scores only.
- **Team codes differ between sources.** The EuroLeague API and the Fantasy game use different team abbreviations (e.g. `MAD` vs `RMB`, `IST` vs `EFS`). `player_map.csv` already does the matching.
- **Small samples.** Early in the season or after injuries, averages rest on few games. Filter on the `games` column.
- `IsPlaying` from the API is **not** "did the player play". Use `minutes > 0` instead.

## Roadmap

- [x] Box score collector + daily automation
- [x] Fantasy prices / points snapshots, automated daily
- [x] Verification of every game against the official final score
- [x] Opponent, score and result columns; season schedule
- [x] `merger.py`: join box scores with fantasy data (team & player mapping)
- [ ] Historical seasons (2016-17 onwards)
- [ ] Data tests in `tests/`
- [ ] EDA notebook
- [ ] Defense vs position analysis
- [ ] FPT prediction model and lineup optimizer (100 credits, 4G / 4F / 2C + coach)

## Disclaimer

This is an unofficial, non-commercial project for education and analysis. It is not affiliated with or endorsed by Euroleague Basketball, Fantaking Interactive or Dunkest. All data belongs to its respective owners.

## Acknowledgements

- [giasemidis/euroleague_api](https://github.com/giasemidis/euroleague_api): Python wrapper for the EuroLeague API
- [vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League): the inspiration for the structure of this dataset

## License

[MIT](LICENSE)
