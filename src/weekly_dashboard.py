"""Weekly job: scrape -> tag -> rebuild docs/index.html (the 'How are our ratings?' page).

  python src/weekly_dashboard.py            # live: scrapes Google Play
  python src/weekly_dashboard.py --offline  # rebuild from data/ files (no network)
"""
import json, os, sys, datetime as dt
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import report_lib as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = f"{ROOT}/data"
PKG = "com.moveinsync.ets"
offline = "--offline" in sys.argv

if not offline:
    import scrape_playstore as S
    snap = S.snapshot(PKG)
    json.dump(snap, open(f"{DATA}/employee_snapshot.json", "w"), indent=2, default=str)
    emp = S.scrape_reviews(PKG)
    emp.to_csv(f"{DATA}/employee_reviews.csv", index=False)
else:
    snap = R.load_snapshot(f"{DATA}/employee_snapshot.json")
    emp = pd.read_csv(f"{DATA}/employee_reviews.csv", parse_dates=["at"])

emp["content"] = emp["content"].fillna("").astype(str)
tagged = R.tag_frame(emp)
tagged.to_csv(f"{DATA}/employee_tagged.csv", index=False)
m = R.compute(emp, tagged, snap)

# history of weekly snapshots (rating, ratings, 1-2* share) for a long-run trend
hist_path = f"{DATA}/weekly_history.csv"
row = {"date": dt.date.today().isoformat(), "score": snap["score"], "ratings": snap["ratings"],
       "neg_share_written": round(m["neg_share_written"] * 100, 2), "version": snap.get("version")}
h = pd.read_csv(hist_path) if os.path.exists(hist_path) else pd.DataFrame()
h = pd.concat([h, pd.DataFrame([row])]).drop_duplicates("date", keep="last")
h.to_csv(hist_path, index=False)

body = ('<p class="muted small">MoveInSync employee app · weekly rating dashboard</p><h1>How are our Play Store ratings?</h1>'
        + R.dashboard_html(m)
        + '<h3>Rating history (weekly snapshots)</h3><div class="wrap"><table><tr><th>Date</th><th class="num">Rating</th><th class="num">Ratings</th>'
          '<th class="num">% 1-2★ of written</th><th>Version</th></tr>'
        + "".join(f'<tr><td>{r.date}</td><td class="num">{r.score:.3f}</td><td class="num">{int(r.ratings):,}</td>'
                  f'<td class="num">{r.neg_share_written:.1f}%</td><td>{r.version}</td></tr>' for r in h.tail(12).itertuples())
        + "</table></div>")
os.makedirs(f"{ROOT}/docs", exist_ok=True)
open(f"{ROOT}/docs/index.html", "w", encoding="utf-8").write(R.page("MoveInSync ratings dashboard", body))
print("dashboard rebuilt:", snap["score"], "| reviews:", len(emp))
