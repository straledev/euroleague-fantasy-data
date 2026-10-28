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

| Column | Type | Description |
|---|---|---|
| `season` | int | Start year of the season (`2026` = 2026-27) |
| `phase` | str | Competition phase: `RS` regular season, `PI` play-in, `PO` playoffs, `FF` Final Four |
| `round` | int | Round number within the phase |
| `game_code` | int | Game ID within the season (unique per season, not across seasons) |
| `player_id` | str | EuroLeague player ID, e.g. `P003469`. Stable across seasons |
| `player` | str | Player name as `LASTNAME, FIRSTNAME` |
| `team` | str | EuroLeague team code (e.g. `OLY`, `MAD`, `PAN`) |
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
| `pir_calc` | int | PIR recomputed from the columns above. Used as a check and should always equal `pir` |

**PIR formula:**

```
PIR = (pts + reb + ast + stl + blk + fd)
    - (missed 2PT + missed 3PT + missed FT + tov + blk_against + pf)
```

---

## 2. Season summary

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

## 3. Fantasy files

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

## Joining the two sources

The box score and fantasy files do not share an ID. To join them you need to match:

| | Box score | Fantasy |
|---|---|---|
| Player ID | `player_id` (`P003469`) | `dunkest_id` (`3766`) |
| Name | `VEZENKOV, SASHA` | `S. Vezenkov` |
| Team | `MAD`, `IST`, `PAM`... | `RMB`, `EFS`, `VBC`... |

A merge script (`merger.py`) that builds this mapping is planned. See the roadmap in the [README](README.md).