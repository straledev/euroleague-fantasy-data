# Data Dictionary

Column reference for every file in `data/<season>/`.

---

## 1. Box score files

**Files:**
- `rounds/merged_rounds.csv`: every player in every game of the season
- `rounds/round_<n>.csv`: same columns, only round *n*
- `players/<name>_<player_id>/rounds.csv`: same columns, only one player

**Source:** official EuroLeague API, via [`euroleague-api`](https://github.com/giasemidis/euroleague_api). Created by `collector.py`.

**One row =** one player in one game. Players who were on the roster but did not play are included with `minutes = 0`. Team total rows are removed.

**Accuracy:** a game is saved only when its players' points add up exactly to the official final score, both teams are present, no player appears twice and `pir` equals `pir_calc`. Games that fail the check are retried on the next run.

| Column | Type | Description |
|---|---|---|
| `season` | int | Start year of the season (`2026` = 2026-27) |
| `phase` | str | Competition phase: `RS` regular season, `PI` play-in, `PO` playoffs, `FF` Final Four |
| `round` | int | Round number within the phase |
| `game_code` | int | Game ID within the season (unique per season, not across seasons) |
| `player_id` | str | EuroLeague player ID, e.g. `P003469`. Stable across seasons |
| `player` | str | Player name as `LASTNAME, FIRSTNAME` |
| `team` | str | EuroLeague team code (e.g. `OLY`, `MAD`, `PAN`) |
| `opponent` | str | EuroLeague code of the opposing team in this game |
| `home` | int | `1` home team, `0` away team |
| `starter` | int | `1` started the game, `0` came off the bench |
| `minutes` | float | Minutes played in decimal form (`25:30` → `25.5`) |
| `pts` | int | Points |
| `fg2m` / `fg2a` | int | 2-point field goals made / attempted |
| `fg3m` / `fg3a` | int | 3-point field goals made / attempted |
| `ftm` / `fta` | int | Free throws made / attempted |
| `oreb` / `dreb` / `reb` | int | Offensive / defensive / total rebounds |
| `ast` | int | Assists |
| `stl` | int | Steals |
| `tov` | int | Turnovers |
| `blk` | int | Blocks made |
| `blk_against` | int | Own shots that were blocked |
| `pf` | int | Personal fouls committed |
| `fd` | int | Fouls drawn |
| `pir` | int | Performance Index Rating, as reported by the API (`Valuation`) |
| `plus_minus` | float | Point differential while on court |
| `team_score` | int | Points scored by the player's team in this game |
| `opp_score` | int | Points scored by the opponent in this game |
| `win` | int | `1` if the player's team won, `0` if it lost |
| `pir_calc` | int | PIR recomputed from the columns above. Used as a check and always equals `pir` |
| `fpt_est` | float | **Estimated** fantasy points: `pir × 1.1` when the team won, otherwise `pir`, following the EuroLeague Fantasy Challenge win bonus. Not an official per-game value; season averages of `fpt_est` are within 0.15 of the game's own FPT for most players |

**PIR formula:**

```
PIR = (pts + reb + ast + stl + blk + fd)
    - (missed 2PT + missed 3PT + missed FT + tov + blk_against + pf)
```

---

## 2. Schedule

**File:** `schedule.csv`

**Source:** official EuroLeague API (season results feed). Written by `collector.py` on every run.

**One row =** one **played** game. The results feed lists a game only once it has been played, so upcoming games are not in this file.

| Column | Type | Description |
|---|---|---|
| `game_code` | int | Game ID within the season, same as in the box score files |
| `phase` | str | Competition phase (`RS`, `PI`, `PO`, `FF`) |
| `round` | int | Round number |
| `played` | bool | `True` once the game is finished |
| `home_score` / `away_score` | int | Final score |
| `date` | str | Game date as published by the API, e.g. `Sep 24, 2026` |
| `time` | str | Tip-off time as published by the API, e.g. `20:00` (time zone not stated by the feed) |
| `gamecode` | str | Season and game in one ID, e.g. `E2026_1` |
| `group` | str | Competition stage name, e.g. `Regular Season` |
| `hometeam` / `awayteam` | str | Full team names, e.g. `CRVENA ZVEZDA MERIDIANBET BELGRADE` |
| `homecode` / `awaycode` | str | EuroLeague team codes, the same codes as `team` in the box score files |

---

## 3. Collection status

**File:** `collection_status.json`

Written on every run, so you can see at a glance whether the dataset is complete.

| Field | Description |
|---|---|
| `updated_utc` | When the collector last ran |
| `played_games` | Games the schedule marks as played |
| `stored_games` | Games in `merged_rounds.csv` |
| `verified_games` | Stored games that passed the final-score check |
| `rounds_complete` | Rounds where every game is stored and verified |
| `missing_or_unverified` | `game_code`s still missing; empty when the dataset is complete |

---

## 4. Season summary

**File:** `cleaned_players.csv`

**One row =** one player for one team. A player who changed teams during the season appears once per team. Only games with `minutes > 0` are counted. Sorted by `pir_avg` descending.

| Column | Type | Description |
|---|---|---|
| `player_id` | str | EuroLeague player ID |
| `player` | str | Player name (`LASTNAME, FIRSTNAME`) |
| `team` | str | EuroLeague team code |
| `games` | int | Games played (`minutes > 0`) |
| `min_avg` | float | Average minutes per game |
| `pts_avg` | float | Average points per game |
| `reb_avg` | float | Average rebounds per game |
| `ast_avg` | float | Average assists per game |
| `pir_avg` | float | Average PIR per game |
| `pir_std` | float | Standard deviation of PIR, a measure of consistency. Empty when `games = 1` |
| `pir_total` | int | Total PIR for the season |

Averages based on few games are unreliable, so filter on `games` before ranking.

---

## 5. Fantasy files

**Files:**
- `fantasy/players_latest.csv`: most recent snapshot
- `fantasy/snapshots/players_<YYYY-MM-DD_HHMM>.csv`: every snapshot, timestamp in UTC
- Files with a `_tot` suffix are season totals instead of averages

**Source:** EuroLeague Fantasy Challenge (Stats page). Created by `fantasy_scraper.py`.

**One row =** one player or head coach at the moment of the snapshot. Stat columns are **per-game averages** (`stats_type = avg`) or **season totals** (`stats_type = tot`).

| Column | Type | Description |
|---|---|---|
| `scraped_at_utc` | str | When the snapshot was taken (`YYYY-MM-DD HH:MM`, UTC) |
| `stats_type` | str | `avg` per-game averages, or `tot` season totals |
| `dunkest_id` | int | Player or coach ID in the Fantasy game. Not the same as `player_id` |
| `player` | str | Name as shown in the game, e.g. `S. Vezenkov` |
| `position` | str | `Guard`, `Forward`, `Center` or `Head Coach` |
| `team` | str | Fantasy game team code. **Differs from EuroLeague codes** for some teams (e.g. `RMB` vs `MAD`) |
| `fpt` | float | Fantasy points |
| `credits` | float | Current price in credits (a team has 100 credits in total) |
| `credits_change` | float | Price change shown in the game's `PLUS` column |
| `pts` | float | Points |
| `reb` | float | Rebounds |
| `ast` | float | Assists |
| `stl` | float | Steals |
| `tov` | float | Turnovers |
| `blk` | float | Blocks made |
| `blk_against` | float | Own shots that were blocked |
| `fd` | float | Fouls drawn |
| `pf` | float | Fouls committed |
| `fg_missed` | float | Missed field goals (2PT + 3PT) |
| `ft_missed` | float | Missed free throws |
| `coach_win_1_10` | float | Coach only: wins by 1-10 points |
| `coach_win_11_20` | float | Coach only: wins by 11-20 points |
| `coach_win_20plus` | float | Coach only: wins by more than 20 points |
| `coach_win_ot` | float | Coach only: wins in overtime |
| `coach_loss_1_10` | float | Coach only: losses by 1-10 points |
| `coach_loss_11_20` | float | Coach only: losses by 11-20 points |
| `coach_loss_20plus` | float | Coach only: losses by more than 20 points |
| `coach_loss_ot` | float | Coach only: losses in overtime |
| `is_coach` | bool | `True` for head coaches |

**Notes:**
- Player stat columns are empty for coaches, and coach columns are empty for players.
- In `avg` mode the coach columns are the share of games with that result (e.g. `0.3` = 30% of games); in `tot` mode they are counts.
- `fpt` for players is related to PIR but is not identical to it. Coaches score only through game results.
- Prices change after every round. For modelling round *N*, use the snapshot taken before the round *N* deadline.

---

## 6. Player map (joining the two sources)

**File:** `player_map.csv`

The box score and fantasy files share no ID, and use different name formats and partly different team codes:

| | Box score | Fantasy |
|---|---|---|
| Player ID | `player_id` (`P003469`) | `dunkest_id` (`3766`) |
| Name | `VEZENKOV, SASHA` | `S. Vezenkov` |
| Team | `MAD`, `IST`, `PAM`... | `RMB`, `EFS`, `VBC`... |

`merger.py` links them: it maps the 20 team codes, then matches each box-score player to a fantasy player of the same team by last name (accents and suffixes such as *Jr.* or *III* removed) and first initial. Only unambiguous matches are kept. A player not found in his team (for example after a transfer) is matched league-wide only if the name is a unique, exact match. Players that still cannot be matched can be added by hand in `config/player_overrides.csv`.

**One row =** one box-score player for one team, with at least one minute played this season.

| Column | Type | Description |
|---|---|---|
| `player_id` | str | EuroLeague player ID, as in the box score files |
| `player` | str | Name as in the box score files |
| `team` | str | EuroLeague team code |
| `dunkest_id` | int | Fantasy game ID. Empty when the player is not in any fantasy snapshot |
| `fantasy_name` / `fantasy_team` | str | Name and team code as shown in the fantasy game |
| `position` | str | `Guard`, `Forward` or `Center`, from the fantasy game |
| `match_method` | str | `team_and_name`, `name_only`, `manual` (from the overrides file) or `unmatched` |
| `games` / `minutes` | int / float | Games and minutes played, to judge how much an unmatched player matters |

The daily update fails, and sends a notification, when less than 99% of minutes played have a position.

**Example: add positions to the box score**

```python
import pandas as pd

base = "https://raw.githubusercontent.com/straledev/euroleague-fantasy-data/main/data/2026-27"

games = pd.read_csv(f"{base}/rounds/merged_rounds.csv")
pmap = pd.read_csv(f"{base}/player_map.csv")
games = games.merge(pmap[["player_id", "team", "position", "dunkest_id"]],
                    on=["player_id", "team"], how="left")
```