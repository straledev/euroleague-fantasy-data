"""Box score collector for the EuroLeague Fantasy dataset.

Works incrementally: it reads the season schedule once, keeps every game already
stored, and downloads only played games that are missing. Each new game is
checked against the official final score before it is saved, so a partial or
broken response never reaches the dataset.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xmltodict
from euroleague_api.boxscore_data import BoxScoreData
from euroleague_api.utils import get_requests

COMPETITION = "E"
MAX_TRIES = 4          # pokusaja po utakmici
FIRST_WAIT = 5         # sekundi pre drugog pokusaja (5, 15, 45)
PAUSE = 1.0            # pauza izmedju utakmica, da API ne uspori zahteve

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
OUT_COLS = list(COL.values()) + ["pir_calc"]
CONTEXT_COLS = ["opponent", "team_score", "opp_score", "win", "fpt_est"]
WIN_BONUS = 0.10       # EuroLeague Fantasy: +10% poena kad tim pobedi


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


# ---------------------------------------------------------------- schedule

def get_schedule(api: BoxScoreData, season: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Raspored sezone sa konacnim rezultatima: (nase kolone, ceo odgovor API-ja).

    Citamo ga sami: biblioteka `played` pretvara u bool preko astype(bool),
    pa i tekst "false" postaje True i ne odigrane utakmice izgledaju odigrano.
    """
    r = get_requests(api.url_v1, params={"seasonCode": f"{COMPETITION}{season}"})
    games = xmltodict.parse(r.content)["results"]["game"]
    df = pd.DataFrame(games if isinstance(games, list) else [games])
    # polja sa XML atributima stizu kao recnici; cuvamo ih kao tekst
    df = df.apply(lambda col: col.map(lambda v: json.dumps(v, ensure_ascii=False)
                                      if isinstance(v, (dict, list)) else v))
    df = df.rename(columns={
        "gamenumber": "game_code", "round": "phase", "gameday": "round",
        "homescore": "home_score", "awayscore": "away_score",
    })
    df["played"] = df["played"].astype(str).str.strip().str.lower().eq("true")
    for c in ["game_code", "round", "home_score", "away_score"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    core = ["game_code", "phase", "round", "played", "home_score", "away_score"]
    full = df[core + [c for c in df.columns if c not in core]].sort_values("game_code")
    return df[core], full


# ---------------------------------------------------------------- one game

def clean_game(raw: pd.DataFrame, game) -> pd.DataFrame:
    df = raw.rename(columns=COL)
    df["phase"] = game.phase
    df["round"] = game.round
    df = df[[c for c in COL.values() if c in df.columns]].copy()
    for c in ["player_id", "player", "team", "phase"]:
        df[c] = df[c].astype(str).str.strip()
    df = df[~df["player_id"].str.upper().isin(["TOTAL", "TEAM", ""])].copy()
    df["minutes"] = df["minutes"].apply(minutes_to_float)
    for c in [c for c in COL.values() if c not in TEXT_COLS]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["pir_calc"] = compute_pir(df)
    return df


def check_game(df: pd.DataFrame, game) -> list[str]:
    """Razlozi zasto utakmica nije ispravna; prazna lista znaci da je sve u redu."""
    problems = []
    if df["team"].nunique() != 2:
        problems.append(f"{df['team'].nunique()} ekipa umesto 2")
        return problems
    if set(df["home"].astype(int)) != {0, 1}:
        problems.append("nema jasnog domacina i gosta")
        return problems
    pts = df.groupby(df["home"].astype(int))["pts"].sum()
    if int(pts.get(1, -1)) != int(game.home_score) or int(pts.get(0, -1)) != int(game.away_score):
        problems.append(
            f"poeni igraca {int(pts.get(1, 0))}-{int(pts.get(0, 0))}, "
            f"zvanican rezultat {int(game.home_score)}-{int(game.away_score)}"
        )
    if df.duplicated(["player_id", "team"]).any():
        problems.append("isti igrac dva puta")
    if (df["pir"] != df["pir_calc"]).any():
        problems.append("PIR se ne slaze sa statistikom")
    return problems


def fetch_game(api: BoxScoreData, season: int, game) -> pd.DataFrame | None:
    wait = FIRST_WAIT
    for attempt in range(1, MAX_TRIES + 1):
        try:
            raw = api.get_players_boxscore_stats(season, int(game.game_code))
            df = clean_game(raw, game)
            problems = check_game(df, game)
            if not problems:
                return df
            reason = "; ".join(problems)
        except Exception as e:  # mreza, prazan odgovor, los JSON...
            reason = f"{type(e).__name__}: {e}"
        print(f"    utakmica {int(game.game_code)}, pokusaj {attempt}/{MAX_TRIES}: {reason}")
        if attempt < MAX_TRIES:
            time.sleep(wait)
            wait *= 3
    return None


# ---------------------------------------------------------------- context

def add_game_context(df: pd.DataFrame) -> pd.DataFrame:
    """Protivnik, rezultat, pobeda i procena fantasy poena za svaki red."""
    df = df.drop(columns=[c for c in CONTEXT_COLS if c in df.columns])
    score = (df.groupby(["game_code", "team"], as_index=False)["pts"].sum()
               .rename(columns={"pts": "team_score"}))
    opp = score.rename(columns={"team": "opponent", "team_score": "opp_score"})
    ctx = score.merge(opp, on="game_code")
    ctx = ctx[ctx["team"] != ctx["opponent"]]
    df = df.merge(ctx, on=["game_code", "team"], how="left")
    df["win"] = (df["team_score"] > df["opp_score"]).astype(int)
    df["fpt_est"] = (df["pir"] * np.where(df["win"] == 1, 1 + WIN_BONUS, 1.0)).round(1)
    first = list(COL.values())
    first.insert(first.index("team") + 1, "opponent")
    order = first + ["team_score", "opp_score", "win", "pir_calc", "fpt_est"]
    return df[[c for c in order if c in df.columns]]


# ---------------------------------------------------------------- outputs

def write_outputs(df: pd.DataFrame, base: Path) -> None:
    df = add_game_context(df)
    rounds_dir = base / "rounds"
    players_dir = base / "players"
    rounds_dir.mkdir(parents=True, exist_ok=True)
    players_dir.mkdir(parents=True, exist_ok=True)

    df = df.sort_values(["game_code", "team", "player"])
    df.to_csv(rounds_dir / "merged_rounds.csv", index=False)

    # fajlovi po kolu uvek iz celog skupa, da nijedan ne ostane zastareo
    for old in rounds_dir.glob("*round_*.csv"):
        old.unlink()
    for (phase, rnd), g in df.groupby(["phase", "round"]):
        # regularni deo: round_5.csv; doigravanje i plej-of: po_round_2.csv, ff_round_1.csv...
        prefix = "" if phase == "RS" else f"{str(phase).lower()}_"
        g.to_csv(rounds_dir / f"{prefix}round_{int(rnd)}.csv", index=False)

    for (pid, name), g in df.groupby(["player_id", "player"]):
        p_dir = players_dir / f"{slug(name)}_{pid}"
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


# ---------------------------------------------------------------- season

def rounds_complete(played: pd.DataFrame, ok_codes: set, data: pd.DataFrame) -> list:
    """Kola u kojima su odigrane i proverene SVE utakmice.

    Raspored sadrzi samo odigrane utakmice, pa kolo u toku inace izgleda zavrseno.
    Zato kolo regularnog dela mora imati i pun broj utakmica (broj timova / 2).
    """
    full_round = data["team"].nunique() // 2 if not data.empty else 0
    out = []
    for (phase, rnd), g in played.sort_values("game_code").groupby(["phase", "round"], sort=False):
        codes = set(g["game_code"].astype(int))
        if not codes <= ok_codes:
            continue
        if phase == "RS":
            if len(codes) == full_round:
                out.append(int(rnd))
        else:
            out.append(f"{phase} {int(rnd)}")
    return out

def collect(season: int, out_dir: Path, api: BoxScoreData | None = None) -> bool:
    """Vraca True ako dataset sadrzi sve odigrane utakmice."""
    api = api or BoxScoreData(COMPETITION)
    base = out_dir / season_label(season)
    merged_path = base / "rounds" / "merged_rounds.csv"
    print(f"Sezona {season_label(season)}")

    schedule, schedule_full = get_schedule(api, season)
    base.mkdir(parents=True, exist_ok=True)
    schedule_full.to_csv(base / "schedule.csv", index=False)
    played = schedule[schedule["played"]]

    if merged_path.exists():
        existing = pd.read_csv(merged_path, dtype={"player_id": str})
    else:
        existing = pd.DataFrame(columns=OUT_COLS)

    # postojece utakmice proveravamo prema zvanicnom rezultatu
    have, bad = set(), set()
    for game in played.itertuples():
        g = existing[existing["game_code"] == game.game_code]
        if g.empty:
            continue
        if check_game(g, game):
            bad.add(int(game.game_code))
        else:
            have.add(int(game.game_code))

    todo = played[~played["game_code"].isin(have)]
    print(f"  Odigrano: {len(played)} | vec ispravno sacuvano: {len(have)} | "
          f"neispravno sacuvano: {len(bad)} | preuzimam: {len(todo)}")

    fresh = []
    for game in todo.itertuples():
        df = fetch_game(api, season, game)
        if df is not None:
            fresh.append(df)
            print(f"    utakmica {int(game.game_code)} (kolo {int(game.round)}): OK")
        time.sleep(PAUSE)

    fresh_codes = {int(c) for df in fresh for c in df["game_code"].unique()}
    # stara verzija utakmice ostaje dok ne stigne ispravna nova
    kept = existing[~existing["game_code"].isin(fresh_codes)]
    data = pd.concat([kept, *fresh], ignore_index=True) if fresh else kept
    data = data[[c for c in OUT_COLS if c in data.columns]]

    stored = set(data["game_code"].astype(int))
    ok_codes = have | fresh_codes
    missing = sorted(set(played["game_code"].astype(int)) - ok_codes)

    if fresh or not merged_path.exists() or "opponent" not in existing.columns:
        write_outputs(data, base)

    status = {
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "played_games": int(len(played)),
        "stored_games": len(stored),
        "verified_games": len(ok_codes),
        "rounds_complete": rounds_complete(played, ok_codes, data),
        "missing_or_unverified": missing,
    }
    (base / "collection_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")

    print(f"  Sacuvano utakmica: {len(stored)} od {len(played)} odigranih, "
          f"provereno prema rezultatu: {len(ok_codes)}")
    if missing:
        print(f"  NEDOSTAJE ILI NIJE PROVERENO: {missing}")
    return not missing


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, action="append", required=True,
                    help="pocetna godina sezone, npr. 2026 za 2026-27")
    ap.add_argument("--out", default="data")
    args = ap.parse_args()
    complete = [collect(s, Path(args.out)) for s in args.season]
    sys.exit(0 if all(complete) else 1)