"""Links box-score players to the EuroLeague Fantasy game.

The two sources share no ID: the box score uses EuroLeague player IDs
(`P003469`, `VEZENKOV, SASHA`, team `OLY`), the fantasy game its own IDs
(`3766`, `S. Vezenkov`) and partly different team codes (`MAD` vs `RMB`).
This script matches them by team and name and writes
`data/<season>/player_map.csv`: one row per box-score player and team, with
`dunkest_id` and the fantasy position.
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

# EuroLeague (box score) -> EuroLeague Fantasy team codes
TEAM_MAP = {
    "ASV": "ASV", "BAR": "BAR", "BAS": "KBA", "BES": "BJK", "DUB": "DUB",
    "HTA": "HTA", "IST": "EFS", "MAD": "RMB", "MIL": "MIL", "MUN": "BAY",
    "OLY": "OLY", "PAM": "VBC", "PAN": "PAO", "PAR": "PAR", "PRS": "PBB",
    "RED": "CZV", "TEL": "MTA", "ULK": "FBT", "VIR": "VIR", "ZAL": "ZAL",
}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}
OVERRIDES = Path("config") / "player_overrides.csv"
MIN_COVERAGE = 0.99  # udeo odigranih minuta koji mora imati poziciju


def season_label(season: int) -> str:
    return f"{season}-{str(season + 1)[-2:]}"


def tokens(text: str) -> list[str]:
    """'Ðorđević-Šarić Jr.' -> ['djordjevic', 'saric']"""
    text = str(text).replace("Đ", "Dj").replace("đ", "dj")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return [t for t in re.sub(r"[^a-z ]", " ", text).split() if t not in SUFFIXES]


def load_fantasy(base: Path) -> pd.DataFrame:
    """Svi fantasy igraci iz svih snimaka; za svakog vazi poslednji snimak."""
    files = sorted((base / "fantasy" / "snapshots").glob("players_*.csv"))
    files = [f for f in files if not f.stem.endswith("_tot")]
    latest = base / "fantasy" / "players_latest.csv"
    if not files and latest.exists():
        files = [latest]
    if not files:
        raise SystemExit("Nema fantasy snimka. Prvo pokreni fantasy_scraper.py.")
    f = pd.concat([pd.read_csv(p) for p in files], ignore_index=True)
    f = f[~f["is_coach"].astype(bool)]
    f = (f.sort_values("scraped_at_utc")
           .drop_duplicates(["dunkest_id"], keep="last")
           .reset_index(drop=True))
    f["last"] = f["player"].str.split(". ", n=1).str[-1].map(tokens)
    f["initial"] = f["player"].map(lambda s: (tokens(s) or [""])[0][:1])
    return f


def score(box_last: list[str], box_first: list[str], fan) -> int:
    """3 = isto prezime, 2 = deo prezimena, 1 = imena zamenjena; +1 za prvo slovo imena."""
    if fan.last == box_last:
        s = 3
    elif set(fan.last) & set(box_last):
        s = 2
    elif set(fan.last) & set(box_first):
        s = 1
    else:
        return 0
    return s + (1 if box_first and fan.initial == box_first[0][:1] else 0)


def best_match(candidates: pd.DataFrame, box_last, box_first, min_score: int):
    if candidates.empty:
        return None
    sc = candidates.apply(lambda c: score(box_last, box_first, c), axis=1)
    top = sc.max()
    if top >= min_score and (sc == top).sum() == 1:
        return candidates.loc[sc.idxmax()]
    return None


def build_map(box: pd.DataFrame, fantasy: pd.DataFrame) -> pd.DataFrame:
    players = (box.groupby(["player_id", "player", "team"], as_index=False)
                  .agg(games=("game_code", "nunique"), minutes=("minutes", "sum")))
    rows = []
    for p in players.itertuples():
        last, _, first = p.player.partition(",")
        box_last, box_first = tokens(last), tokens(first)
        fteam = TEAM_MAP.get(p.team)

        # 1. isti tim; 2. bilo koji tim, ali samo ako je potpuno jednoznacno (transferi)
        match = best_match(fantasy[fantasy["team"] == fteam], box_last, box_first, 3)
        method = "team_and_name"
        if match is None:
            match = best_match(fantasy, box_last, box_first, 4)
            method = "name_only"
        rows.append({
            "player_id": p.player_id, "player": p.player, "team": p.team,
            "dunkest_id": None if match is None else int(match.dunkest_id),
            "fantasy_name": None if match is None else match.player,
            "fantasy_team": None if match is None else match.team,
            "position": None if match is None else match.position,
            "match_method": "unmatched" if match is None else method,
            "games": p.games, "minutes": round(p.minutes, 1),
        })
    return pd.DataFrame(rows)


def apply_overrides(m: pd.DataFrame, season: int) -> pd.DataFrame:
    """Rucne ispravke iz config/player_overrides.csv imaju prednost."""
    if not OVERRIDES.exists():
        return m
    o = pd.read_csv(OVERRIDES, dtype={"player_id": str})
    o = o[o["season"] == season]
    for r in o.itertuples():
        hit = m["player_id"] == r.player_id
        if pd.notna(getattr(r, "team", None)) and str(r.team).strip():
            hit &= m["team"] == r.team
        if not hit.any():
            print(f"  Upozorenje: ispravka za {r.player_id} ne odgovara nijednom igracu")
            continue
        m.loc[hit, "position"] = r.position
        if pd.notna(r.dunkest_id):
            m.loc[hit, "dunkest_id"] = int(r.dunkest_id)
        m.loc[hit, "match_method"] = "manual"
    return m


def merge(season: int, out_dir: Path) -> bool:
    base = out_dir / season_label(season)
    box = pd.read_csv(base / "rounds" / "merged_rounds.csv", dtype={"player_id": str})
    box = box[box["minutes"] > 0]
    fantasy = load_fantasy(base)

    unknown = sorted(set(box["team"]) - set(TEAM_MAP))
    if unknown:
        raise SystemExit(f"Timovi bez para u TEAM_MAP: {unknown}")

    m = apply_overrides(build_map(box, fantasy), season)
    m["dunkest_id"] = m["dunkest_id"].astype("Int64")

    # isti fantasy igrac ne sme biti dodeljen dvojici razlicitih igraca
    dup = m.dropna(subset=["dunkest_id"]).groupby("dunkest_id")["player_id"].nunique()
    for d in dup[dup > 1].index:
        names = m.loc[m["dunkest_id"] == d, "player"].tolist()
        print(f"  Dvosmisleno, ponisteno: dunkest_id {d} -> {names}")
        m.loc[m["dunkest_id"] == d, ["dunkest_id", "fantasy_name", "fantasy_team", "position"]] = None
        m.loc[m["dunkest_id"] == d, "match_method"] = "unmatched"

    m = m.sort_values(["team", "player"])
    m.to_csv(base / "player_map.csv", index=False)

    coverage = m.loc[m["position"].notna(), "minutes"].sum() / m["minutes"].sum()
    left = m[m["position"].isna()].sort_values("minutes", ascending=False)
    print(f"Sezona {season_label(season)}: {len(m)} igraca, "
          f"{m['position'].notna().sum()} sa pozicijom, "
          f"{coverage:.2%} odigranih minuta pokriveno")
    print("  " + m["match_method"].value_counts().to_string().replace("\n", "\n  "))
    if not left.empty:
        print("  Bez pozicije (dodaj u config/player_overrides.csv):")
        print(left[["player_id", "player", "team", "games", "minutes"]].to_string(index=False))
    return coverage >= MIN_COVERAGE


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, action="append", required=True)
    ap.add_argument("--out", default="data")
    args = ap.parse_args()
    ok = [merge(s, Path(args.out)) for s in args.season]
    sys.exit(0 if all(ok) else 1)