"""
Step 2: Scrape MoveInSync Play Store data (app snapshot + reviews).

Setup:   pip install google-play-scraper pandas
Run:     python scrape_playstore.py
Output:  data/<name>_snapshot.json   (rating, histogram, version, capture date)
         data/<name>_reviews.csv     (one row per review, last ~24 months)
"""
import json
import time
import datetime as dt
from pathlib import Path

import pandas as pd
from google_play_scraper import app, reviews, Sort

APPS = {
    "employee": "com.moveinsync.ets",
    "driver_partner": "com.moveinsync.driver.dco",
}
LANG, COUNTRY = "en", "in"
MONTHS_BACK = 24          # how far back to go
MAX_REVIEWS = 30000       # safety cap per app
BATCH = 200
OUT = Path("data")
OUT.mkdir(exist_ok=True)

NOW = dt.datetime.now()
CUTOFF = NOW - dt.timedelta(days=30 * MONTHS_BACK)

KEEP = [
    "reviewId", "at", "score", "content", "thumbsUpCount",
    "reviewCreatedVersion", "appVersion", "replyContent", "repliedAt",
]


def snapshot(pkg: str) -> dict:
    """Official numbers from the app page (the Step 1 baseline)."""
    info = app(pkg, lang=LANG, country=COUNTRY)
    snap = {
        "captured_on": NOW.strftime("%Y-%m-%d %H:%M"),
        "package": pkg,
        "title": info.get("title"),
        "developer": info.get("developer"),
        "score": info.get("score"),
        "ratings": info.get("ratings"),
        "reviews": info.get("reviews"),
        "histogram_1_to_5": info.get("histogram"),  # [1*, 2*, 3*, 4*, 5*]
        "installs": info.get("installs"),
        "version": info.get("version"),
        "updated": info.get("updated"),
    }
    return snap


def scrape_reviews(pkg: str) -> pd.DataFrame:
    rows, token = [], None
    while len(rows) < MAX_REVIEWS:
        batch, token = reviews(
            pkg,
            lang=LANG,
            country=COUNTRY,
            sort=Sort.NEWEST,
            count=BATCH,
            continuation_token=token,
        )
        if not batch:
            break
        rows.extend(batch)
        print(f"   {len(rows):>6} reviews | oldest so far: {batch[-1]['at']:%Y-%m-%d}")
        if batch[-1]["at"] < CUTOFF:
            break
        time.sleep(1)  # be polite

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates("reviewId")
    df = df[df["at"] >= CUTOFF]
    cols = [c for c in KEEP if c in df.columns]   # userName dropped on purpose (privacy)
    return df[cols].sort_values("at", ascending=False).reset_index(drop=True)


def quick_summary(name: str, snap: dict, df: pd.DataFrame) -> None:
    print(f"\n=== {name} ({snap['package']}) ===")
    print("Captured on :", snap["captured_on"])
    print("Score       :", snap["score"])
    print("Ratings     :", snap["ratings"], "| written reviews:", snap["reviews"])
    hist = snap["histogram_1_to_5"]
    if hist and sum(hist):
        tot = sum(hist)
        for star, n in zip([1, 2, 3, 4, 5], hist):
            print(f"  {star}*: {n:>8}  ({n / tot:.1%})")
    print("Version     :", snap["version"])
    if df.empty:
        print("No reviews scraped.")
        return
    print("Scraped     :", len(df), "reviews,", df["at"].min().date(), "->", df["at"].max().date())
    print("Mean score of scraped reviews:", round(df["score"].mean(), 2))
    print("Developer reply rate :", f"{df['replyContent'].notna().mean():.1%}")
    ver = "reviewCreatedVersion" if "reviewCreatedVersion" in df else "appVersion"
    print("Reviews with version :", f"{df[ver].notna().mean():.1%}")


if __name__ == "__main__":
    for name, pkg in APPS.items():
        print(f"\n>>> {name}: {pkg}")
        snap = snapshot(pkg)
        (OUT / f"{name}_snapshot.json").write_text(json.dumps(snap, indent=2, default=str))
        df = scrape_reviews(pkg)
        df.to_csv(OUT / f"{name}_reviews.csv", index=False)
        quick_summary(name, snap, df)
    print("\nDone. Files are in the data/ folder.")
