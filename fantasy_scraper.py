import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://fantaking-api.dunkest.com/api/v1/competitions/{competition}/stats/players/table"
COMPETITION_ID = 49
SEASON_LABEL = "2026-27"
PER_PAGE = 25
PAUSE_SEC = 1.0

HEADERS = {
    "User-Agent": "euroleague-fantasy-data (github.com/<tvoj-username>/euroleague-fantasy-data)",
    "Accept": "application/json",
}

RENAME = {
    "name": "player",
    "quotation": "credits",
    "plus": "credits_change",
    "tov": "tov",
    "blka": "blk_against",
    "pf": "pf",
    "win_1-10": "coach_win_1_10",
    "win_11-20": "coach_win_11_20",
    "win_20": "coach_win_20plus",
    "win_ot": "coach_win_ot",
    "loss_1-10": "coach_loss_1_10",
    "loss_11-20": "coach_loss_11_20",
    "loss_20": "coach_loss_20plus",
    "loss_ot": "coach_loss_ot",
}
TEXT_COLS = {"player", "position", "team"}


def load_token() -> str:
    token = os.environ.get("DUNKEST_TOKEN", "").strip()
    env_file = Path(".env")
    if not token and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DUNKEST_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not token:
        sys.exit("Nema tokena. Napravi .env fajl sa redom DUNKEST_TOKEN=<vrednost Authorization headera>")
    return token if token.lower().startswith("bearer ") else f"Bearer {token}"


def fetch_page(session: requests.Session, page: int, stats_type: str) -> dict:
    params = {
        "stats_type": stats_type,
        "positions": "",
        "matchdays": "",
        "search": "",
        "teams": "",
        "quotations": "0,30",
        "page": page,
        "per_page": PER_PAGE,
        "sort_by": "fpt",
        "sort_order": "desc",
        "active_players": "true",
    }
    r = session.get(BASE_URL.format(competition=COMPETITION_ID), params=params, timeout=30)
    if r.status_code == 401:
        sys.exit("401 Unauthorized: token je pogrešan ili je istekao. "
                 "Uzmi novi iz Firefoxa (Network -> zahtev 'table' -> Request Headers -> Authorization).")
    r.raise_for_status()
    return r.json()


def parse_page(payload: dict) -> pd.DataFrame:
    cols = payload["data"]["columns"]
    rows = [[p["id"], *p["row"]] for p in payload["data"]["players"]]
    return pd.DataFrame(rows, columns=["dunkest_id", *cols])


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=RENAME).drop(columns=["rank"], errors="ignore")
    for c in df.columns:
        if c in TEXT_COLS or c == "dunkest_id":
            continue
        df[c] = pd.to_numeric(df[c].replace("-", None), errors="coerce")
    df["is_coach"] = df["position"].eq("Head Coach")
    return df


def scrape(stats_type: str) -> pd.DataFrame:
    frames = []
    with requests.Session() as s:
        s.headers.update(HEADERS)
        s.headers["Authorization"] = load_token()
        first = fetch_page(s, 1, stats_type)
        last_page = first["meta"]["last_page"]
        total = first["meta"]["total"]
        print(f"Ukupno {total} igrača/trenera na {last_page} stranica")
        frames.append(parse_page(first))
        for page in range(2, last_page + 1):
            time.sleep(PAUSE_SEC)
            frames.append(parse_page(fetch_page(s, page, stats_type)))
            print(f"  stranica {page}/{last_page}", end="\r")
    df = clean(pd.concat(frames, ignore_index=True))
    if len(df) != total:
        print(f"\nUPOZORENJE: očekivano {total} redova, dobijeno {len(df)}")
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats-type", choices=["avg", "tot"], default="avg")
    ap.add_argument("--out", default="data")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    df = scrape(args.stats_type)
    df.insert(0, "scraped_at_utc", now.strftime("%Y-%m-%d %H:%M"))
    df.insert(1, "stats_type", args.stats_type)

    base = Path(args.out) / SEASON_LABEL / "fantasy"
    (base / "snapshots").mkdir(parents=True, exist_ok=True)
    suffix = "" if args.stats_type == "avg" else f"_{args.stats_type}"
    snap = base / "snapshots" / f"players{suffix}_{now:%Y-%m-%d_%H%M}.csv"
    df.to_csv(snap, index=False)
    df.to_csv(base / f"players{suffix}_latest.csv", index=False)
    print(f"\nSačuvano: {snap}")
    print(df[["player", "position", "team", "credits", "fpt"]].head(10).to_string(index=False))