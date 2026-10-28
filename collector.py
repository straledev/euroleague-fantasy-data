import argparse
import re
from pathlib import Path

import pandas as pd
from euroleague_api.boxscore_data import BoxScoreData

COMPETITION = "E"

COL = {
    "Season": "season",
    "Phase": "phase",
    "Round": "round",
    "Gamecode": "game_code",
    "Player_ID": "player_id",
    "Player": "player",
    "Team": "team",
    "Home": "home",
    "IsStarter": "starter",
    "Minutes": "minutes",
    "Points": "pts",
    "FieldGoalsMade2": "fg2m",
    "FieldGoalsAttempted2": "fg2a",
    "FieldGoalsMade3": "fg3m",
    "FieldGoalsAttempted3": "fg3a",
    "FreeThrowsMade": "ftm",
    "FreeThrowsAttempted": "fta",
    "OffensiveRebounds": "oreb",
    "DefensiveRebounds": "dreb",
    "TotalRebounds": "reb",
    "Assistances": "ast",
    "Steals": "stl",
    "Turnovers": "tov",
    "BlocksFavour": "blk",
    "BlocksAgainst": "blk_against",
    "FoulsCommited": "pf",
    "FoulsReceived": "fd",
    "Valuation": "pir",
    "Plusminus": "plus_minus",
}
TEXT_COLS = {"season", "phase", "player_id", "player", "team", "minutes"}


def season_label(season: int) -> str:
    return f"{season}-{str(season + 1)[-2:]}"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def minutes_to_float(m) -> float:
    if isinstance(m, str) and ":" in m:
        mm, ss = m.split(":")[:2]
        return int(mm) + int(ss) / 60
    try:
        return float(m)
    except (TypeError, ValueError):
        return 0.0


def compute_pir(df: pd.DataFrame) -> pd.Series:
    missed_fg = (df.fg2a - df.fg2m) + (df.fg3a - df.fg3m)
    missed_ft = df.fta - df.ftm
    plus = df.pts + df.reb + df.ast + df.stl + df.blk + df.fd
    minus = missed_fg + missed_ft + df.tov + df.blk_against + df.pf
    return plus - minus


def collect(season: int, out_dir: Path) -> None:
    print(f"Preuzimam box score za sezonu {season_label(season)} ...")
    raw = BoxScoreData(COMPETITION).get_players_boxscore_stats_single_season(season)

    df = raw.rename(columns=COL)
    df = df[[c for c in COL.values() if c in df.columns]]
    for c in ["player_id", "player", "team", "phase"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
    df = df[~df["player_id"].str.upper().isin(["TOTAL", "TEAM", ""])].copy()
    df["minutes"] = df["minutes"].apply(minutes_to_float)

    num_cols = [c for c in COL.values() if c not in TEXT_COLS]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    df["pir_calc"] = compute_pir(df)
    mismatch = (df["pir_calc"] != df["pir"]).mean()
    print(f"  Redova: {len(df)} | razlika PIR vs Valuation: {mismatch:.1%}")

    base = out_dir / season_label(season)
    (base / "rounds").mkdir(parents=True, exist_ok=True)
    (base / "players").mkdir(parents=True, exist_ok=True)

    df = df.sort_values(["round", "game_code", "team", "player"])
    df.to_csv(base / "rounds" / "merged_rounds.csv", index=False)
    for rnd, g in df.groupby("round"):
        g.to_csv(base / "rounds" / f"round_{int(rnd)}.csv", index=False)
    for (pid, name), g in df.groupby(["player_id", "player"]):
        p_dir = base / "players" / f"{slug(name)}_{pid}"
        p_dir.mkdir(exist_ok=True)
        g.to_csv(p_dir / "rounds.csv", index=False)

    played = df[df["minutes"] > 0]
    summary = (
        played.groupby(["player_id", "player", "team"])
        .agg(games=("game_code", "nunique"), min_avg=("minutes", "mean"),
             pts_avg=("pts", "mean"), reb_avg=("reb", "mean"),
             ast_avg=("ast", "mean"), pir_avg=("pir", "mean"),
             pir_std=("pir", "std"), pir_total=("pir", "sum"))
        .round(2).reset_index()
        .sort_values("pir_avg", ascending=False)
    )
    summary.to_csv(base / "cleaned_players.csv", index=False)
    print(f"  Sačuvano u {base}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, action="append", required=True,
                    help="početna godina sezone, npr. 2026 za 2026-27")
    ap.add_argument("--out", default="data")
    args = ap.parse_args()
    for s in args.season:
        collect(s, Path(args.out))