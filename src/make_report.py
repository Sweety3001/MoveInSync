"""Build the full recommendation report (dashboard + recommendations) as one self-contained HTML file.
Usage: python src/make_report.py
"""
import json, os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import report_lib as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
emp = pd.read_csv(f"{ROOT}/data/employee_reviews.csv", parse_dates=["at"])
tagged = pd.read_csv(f"{ROOT}/data/employee_tagged.csv", parse_dates=["at"])
snap = R.load_snapshot(f"{ROOT}/data/employee_snapshot.json")
val = json.load(open(f"{ROOT}/data/validation.json"))
m = R.compute(emp, tagged, snap)

head = f"""
<p class="muted small">MoveInSync · Forward Deployed Engineer case study · employee app (Play Store)</p>
<h1>Why the Play Store rating is {snap["score"]:.2f}, and what to fix first</h1>
<p class="lead">The app is already well rated, so the lost points sit in a small group of unhappy users:
{m["hist_share"][0]*100:.1f}% of ratings are 1★. Their written reviews point to <b>reliability and access</b> ({m["groups"]["Reliability & access"]["pct"]:.0f}%),
<b>tracking and cab operations</b> ({m["groups"]["Tracking, cab ops & routing"]["pct"]:.0f}%) and <b>booking</b> ({m["groups"]["Booking / roster"]["pct"]:.0f}%).
Fix the first two, add a release safety net, and start answering reviews.</p>
"""
body = head + R.recommendations_html(m) + "<h2>The data</h2>" + R.dashboard_html(m) + R.method_html(m, val)
body += '<footer>Numbers are computed from public Play Store data; see the repository README for how to rerun them.</footer>'
out = R.page("MoveInSync Play Store rating: findings and recommendations", body)
os.makedirs(f"{ROOT}/docs", exist_ok=True)
open(f"{ROOT}/report.html", "w", encoding="utf-8").write(out)
print("wrote report.html", len(out) // 1024, "KB")
