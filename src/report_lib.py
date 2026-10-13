"""Metrics + HTML rendering for the MoveInSync Play Store rating report.
Used by weekly_dashboard.py (dashboard only) and make_report.py (dashboard + recommendations).
"""
import html
import json
import math

import numpy as np
import pandas as pd

from tagger import tag_text

TAG_LABEL = {
    "CRASH": "Crash / slow / hang", "LATE": "Cab late / driver / ops", "LOGIN": "Login / OTP / access",
    "BOOKING": "Booking / roster / cancel", "SESSION": "Forced logout / re-login", "ETA": "ETA / live tracking",
    "SUPPORT": "Support / helpdesk", "UI": "UI / redesign", "ROUTING": "Routing / pooling / pickup",
    "REQUEST": "Feature request", "NOTIF": "Notifications", "RATEPROMPT": "Rating prompt",
    "SAFETY": "Safety", "OTP": "Boarding OTP", "OTHER": "Other", "UNCLEAR": "No usable detail",
}
GROUPS = {
    "Reliability & access": ["CRASH", "LOGIN", "SESSION"],
    "Tracking, cab ops & routing": ["ETA", "LATE", "ROUTING"],
    "Booking / roster": ["BOOKING"],
    "Support": ["SUPPORT"],
    "UI & feature requests": ["UI", "REQUEST"],
    "Notifications": ["NOTIF"],
    "Rating prompt": ["RATEPROMPT"],
}
MICRO = {
    "OTP / code not received": r"otp.{0,40}(not|never|n.?t|delay)|(not|never|n.?t|no).{0,25}otp",
    "Tracking wrong / not updating": r"track|live location|location (is |was )?(not|wrong|inaccura|incorrect)|(wrong|incorrect|inaccurate) location",
    "Slow / lag / hang / crash": r"\bslow|\blag|laggy|hang|freez|loading|stuck|not opening|not open|won.?t open|crash",
    "Helpdesk unreachable / no reply": r"help ?desk|helpline|customer (care|support|service)|no (response|reply)|not (respond|reply|answer)",
    "Forced to reinstall / clear data": r"re-?install|uninstall|clear (the )?(data|cache)",
    "Call / chat with driver": r"(call|chat|contact|talk|speak|communicat|phone).{0,30}(driver|cab|bus|chauffeur)|(driver|cab|bus).{0,30}(call|chat|contact|phone)|call (button|option|feature)|calling feature",
    "No-show disputes": r"no[- ]?show",
    "Mentions an update / new version": r"updat|new version|new feature|latest version",
    "QR scan problems": r"\bqr\b|scan",
    "Map auto-zoom": r"zoom",
    "Terms / agreement pop-up": r"terms|agreement|consent|t ?& ?c\b",
}


# ----------------------------------------------------------------- data prep
def load_snapshot(path):
    return json.load(open(path))


def tag_frame(emp):
    neg = emp[emp.score <= 3].copy()
    res = neg.content.fillna("").astype(str).apply(tag_text)
    neg[["tag1", "tag2", "trigger", "owner"]] = pd.DataFrame(res.tolist(), index=neg.index)
    return neg


def _any(df, tags):
    return df.apply(lambda r: (r.tag1 in tags) or (r.tag2 in tags), axis=1)


def compute(emp, tagged, snap):
    emp = emp.copy()
    emp["at"] = pd.to_datetime(emp["at"])
    tagged = tagged.copy()
    tagged["at"] = pd.to_datetime(tagged["at"])
    n2 = tagged[tagged.score <= 2]
    N = len(n2)
    hist = np.array(snap["histogram_1_to_5"], dtype=float)
    T = hist.sum()
    stars = np.arange(1, 6)
    mean = float((hist * stars).sum() / T)
    negr = hist[0] + hist[1]
    old = float((hist[0] * 1 + hist[1] * 2) / negr)

    m = {"snap": snap, "T": int(T), "mean": mean, "hist_share": (hist / T).tolist(), "negr": int(negr), "old": old,
         "N": N, "n_written": len(emp), "neg_share_written": float((emp.score <= 2).mean()),
         "end": emp["at"].max().strftime("%d %b %Y"), "start": emp["at"].min().strftime("%d %b %Y")}

    # theme any-mention
    anym = pd.concat([n2.tag1, n2.tag2.dropna()]).value_counts()
    m["tags"] = {t: {"n": int(anym.get(t, 0)), "pct": float(anym.get(t, 0) / N * 100)} for t in TAG_LABEL}
    m["nodetail"] = float(n2.tag1.isin(["UNCLEAR", "OTHER"]).mean() * 100)
    m["groups"] = {}
    for g, tags in GROUPS.items():
        s = float(_any(n2, tags).mean())
        c = s * negr
        m["groups"][g] = {
            "pct": s * 100, "ratings": int(c),
            "lift50": c * 0.5 * (4 - old) / T, "lift100_4": c * (4 - old) / T, "lift100_5": c * (5 - old) / T}
    top = ["CRASH", "LOGIN", "SESSION", "ETA", "LATE", "ROUTING", "BOOKING", "SUPPORT"]
    su = float(_any(n2, top).mean())
    m["union_top"] = {"pct": su * 100, "lift50": su * negr * 0.5 * (4 - old) / T, "lift100_4": su * negr * (4 - old) / T}
    m["owner"] = (n2.owner.value_counts(normalize=True) * 100).to_dict()

    # monthly
    emp["m"] = emp["at"].dt.to_period("M").astype(str)
    mo = emp.groupby("m").agg(n=("score", "size"), mean=("score", "mean"), neg=("score", lambda s: float((s <= 2).mean() * 100)))
    mo = mo[mo.n >= 100]          # drop partial first/last months
    m["monthly"] = [{"m": i, **r} for i, r in mo.iterrows()]
    m["best_months_neg"] = float(mo.neg.nsmallest(4).mean())

    # recent vs prior 90d, per theme (primary tag)
    end = emp["at"].max()
    a = n2[n2["at"] > end - pd.Timedelta(days=90)]
    b = n2[(n2["at"] <= end - pd.Timedelta(days=90)) & (n2["at"] > end - pd.Timedelta(days=180))]
    rows = []
    for t in TAG_LABEL:
        pa = float((a.tag1 == t).mean() * 100) if len(a) else 0.0
        pb = float((b.tag1 == t).mean() * 100) if len(b) else 0.0
        p = ((a.tag1 == t).sum() + (b.tag1 == t).sum()) / max(len(a) + len(b), 1)
        se = math.sqrt(max(p * (1 - p) * (1 / max(len(a), 1) + 1 / max(len(b), 1)), 1e-9))
        rows.append({"tag": t, "recent": pa, "prior": pb, "delta": pa - pb, "z": (pa - pb) / 100 / se})
    m["trend"] = sorted(rows, key=lambda r: -r["delta"])
    m["n_recent"], m["n_prior"] = len(a), len(b)

    # update watch
    t2 = tagged[tagged.score <= 2].copy()
    t2["m"] = t2["at"].dt.to_period("M").astype(str)
    um = t2.groupby("m").trigger.apply(lambda s: float((s == "after_update").mean() * 100))
    cm = t2.groupby("m").size()
    m["update_month"] = {k: {"pct": float(um[k]), "n": int(cm[k]), "k": int(round(um[k] * cm[k] / 100))} for k in um.index}
    m["update_overall"] = float((n2.trigger == "after_update").mean() * 100)

    # replies
    m["reply_all"] = float(emp.replyContent.notna().mean() * 100)
    m["reply_neg"] = float(n2.replyContent.notna().mean() * 100)
    m["replies_n"] = int(emp.replyContent.notna().sum())

    # micro themes (keyword counts among 1-2 star)
    low = n2.content.str.lower()
    m["micro"] = {k: int(low.str.contains(v, regex=True).sum()) for k, v in MICRO.items()}

    # version table (last 180 days)
    rec = emp[emp["at"] > end - pd.Timedelta(days=180)]
    vt = rec.groupby("reviewCreatedVersion").agg(n=("score", "size"), mean=("score", "mean"),
                                                  neg=("score", lambda s: float((s <= 2).mean() * 100)))
    vt = vt[vt.n >= 25].sort_values("n", ascending=False).head(8)
    m["versions"] = [{"v": i, **r} for i, r in vt.iterrows()]

    # modelled rating mix-shift lever: +10% more 5-star ratings
    add = 0.10 * T
    m["mix_shift_10"] = float(((hist * stars).sum() + 5 * add) / (T + add) - mean)
    need = (4.8 * T - (hist * stars).sum()) / 4
    m["need_conv_48"] = float(need)
    m["need_conv_48_share"] = float(need / hist[0])
    m["ceiling_4"] = mean + negr * (4 - old) / T
    m["ceiling_5"] = mean + negr * (5 - old) / T
    return m


# ------------------------------------------------------------------ SVG bits
def esc(s):
    return html.escape(str(s))


def bar_svg(items, vmax=None, width=760, row=26):
    """items: list of (label, value_pct, n, kind) kind in {'main','muted'}"""
    vmax = vmax or max(v for _, v, _, _ in items) * 1.12
    lab_w, right = 230, 90
    h = row * len(items) + 8
    plot = width - lab_w - right
    out = [f'<svg viewBox="0 0 {width} {h}" role="img" aria-label="Theme share chart" style="width:100%;height:auto">']
    for i, (lab, v, n, kind) in enumerate(items):
        y = i * row + 4
        w = max(v / vmax * plot, 1)
        fill = "var(--accent)" if kind == "main" else "var(--muted-fill)"
        out.append(f'<text x="{lab_w - 8}" y="{y + 15}" text-anchor="end" style="fill:var(--text)" font-size="13">{esc(lab)}</text>')
        out.append(f'<rect x="{lab_w}" y="{y + 3}" width="{w:.1f}" height="16" rx="3" style="fill:{fill}"/>')
        out.append(f'<text x="{lab_w + w + 6}" y="{y + 16}" style="fill:var(--muted)" font-size="12">{v:.1f}% ({n})</text>')
    out.append("</svg>")
    return "".join(out)


def line_svg(months, target=None, width=760, height=240):
    xs = [r["m"] for r in months]
    ys = [r["neg"] for r in months]
    lo, hi = 15, max(40, math.ceil(max(ys) / 5) * 5)
    L, R, Tp, B = 42, 14, 14, 30
    pw, ph = width - L - R, height - Tp - B
    X = lambda i: L + pw * i / max(len(xs) - 1, 1)
    Y = lambda v: Tp + ph * (1 - (v - lo) / (hi - lo))
    o = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Monthly share of 1-2 star reviews" style="width:100%;height:auto">']
    for g in range(lo, hi + 1, 5):
        o.append(f'<line x1="{L}" x2="{width - R}" y1="{Y(g):.1f}" y2="{Y(g):.1f}" style="stroke:var(--line)"/>')
        o.append(f'<text x="{L - 6}" y="{Y(g) + 4:.1f}" text-anchor="end" font-size="11" style="fill:var(--muted)">{g}%</text>')
    if target:
        o.append(f'<line x1="{L}" x2="{width - R}" y1="{Y(target):.1f}" y2="{Y(target):.1f}" stroke-dasharray="5 4" style="stroke:var(--good)"/>')
        o.append(f'<text x="{width - R}" y="{Y(target) - 5:.1f}" text-anchor="end" font-size="11" style="fill:var(--good)">target {target}%</text>')
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(ys))
    o.append(f'<polyline points="{pts}" fill="none" stroke-width="2.2" style="stroke:var(--accent)"/>')
    for i, v in enumerate(ys):
        flag = v >= 32
        o.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="{4 if flag else 2.6}" style="fill:{"var(--bad)" if flag else "var(--accent)"}"><title>{xs[i]}: {v:.1f}% of written reviews were 1-2 star</title></circle>')
    step = max(1, len(xs) // 8)
    for i in range(0, len(xs), step):
        o.append(f'<text x="{X(i):.1f}" y="{height - 8}" text-anchor="middle" font-size="11" style="fill:var(--muted)">{xs[i][2:]}</text>')
    o.append("</svg>")
    return "".join(o)


def hist_svg(share, counts, width=360):
    labels = ["1", "2", "3", "4", "5"]
    row = 28
    h = row * 5 + 6
    o = [f'<svg viewBox="0 0 {width} {h}" role="img" aria-label="Star histogram" style="width:100%;height:auto">']
    plot = width - 130
    for i in range(4, -1, -1):
        y = (4 - i) * row + 4
        w = max(share[i] * plot / 0.9, 1)
        o.append(f'<text x="14" y="{y + 16}" font-size="13" style="fill:var(--text)">{labels[i]}★</text>')
        o.append(f'<rect x="34" y="{y + 3}" width="{w:.1f}" height="16" rx="3" style="fill:{"var(--bad)" if i == 0 else "var(--accent)"}"/>')
        o.append(f'<text x="{34 + w + 6:.1f}" y="{y + 16}" font-size="12" style="fill:var(--muted)">{share[i] * 100:.1f}% ({int(counts[i]):,})</text>')
    o.append("</svg>")
    return "".join(o)


# ------------------------------------------------------------------ HTML
CSS = """
:root{--bg:#ffffff;--surface:#f5f7fa;--text:#14181f;--muted:#5b6472;--line:#e2e6ec;--accent:#1f6feb;--bad:#d1453b;--good:#168a57;--warn:#b86e00;--muted-fill:#aab3c0;
box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#10141a;--surface:#181e27;--text:#e8ecf2;--muted:#9aa5b5;--line:#2a3340;--accent:#5b9bff;--bad:#ff7a70;--good:#4cc58b;--warn:#e0a040;--muted-fill:#566174}}
:root[data-theme="dark"]{--bg:#10141a;--surface:#181e27;--text:#e8ecf2;--muted:#9aa5b5;--line:#2a3340;--accent:#5b9bff;--bad:#ff7a70;--good:#4cc58b;--warn:#e0a040;--muted-fill:#566174}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
main{max-width:920px;margin:0 auto;padding:20px 16px 56px}
h1{font-size:1.65rem;line-height:1.25;margin:.2em 0 .3em}
h2{font-size:1.25rem;margin:2em 0 .5em;padding-top:.6em;border-top:1px solid var(--line)}
h3{font-size:1.02rem;margin:1.2em 0 .3em}
p{margin:.5em 0}
.muted{color:var(--muted)} .small{font-size:.86rem}
.lead{font-size:1.06rem}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin:14px 0}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi b{display:block;font-size:1.5rem;line-height:1.2}
.kpi span{color:var(--muted);font-size:.84rem}
.callout{background:var(--surface);border-left:4px solid var(--accent);border-radius:6px;padding:10px 14px;margin:14px 0}
.callout.warn{border-left-color:var(--warn)} .callout.bad{border-left-color:var(--bad)}
.wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.9rem;min-width:560px}
th,td{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}
th{background:var(--surface);font-weight:600}
td.num,th.num{text-align:right;white-space:nowrap}
.rec{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:14px 0;background:var(--bg)}
.rec h3{margin-top:0}
.rec dl{margin:.4em 0;display:grid;grid-template-columns:96px 1fr;gap:4px 10px}
.rec dt{color:var(--muted);font-size:.84rem;padding-top:2px} .rec dd{margin:0}
.tag{display:inline-block;font-size:.74rem;border-radius:999px;padding:1px 9px;border:1px solid var(--line);color:var(--muted);margin-right:4px}
.tag.first{background:var(--accent);border-color:var(--accent);color:#fff}
ul{padding-left:1.15em;margin:.4em 0} li{margin:.2em 0}
footer{margin-top:40px;color:var(--muted);font-size:.84rem}
"""


def _f(x, d=1):
    return f"{x:,.{d}f}"


def snap_ratings(m):
    return m["snap"]["ratings"]


def kpis(m):
    s = m["snap"]
    k = [
        (f'{s["score"]:.2f}', "Play Store rating"),
        (f'{snap_ratings(m):,}', "total ratings"),
        (_f(m["hist_share"][0] * 100) + "%", f'1★ ratings ({int(s["histogram_1_to_5"][0]):,})'),
        (_f(m["neg_share_written"] * 100) + "%", "of written reviews are 1-2★"),
        (_f(m["reply_neg"]) + "%", "of 1-2★ reviews got a reply"),
    ]
    return '<div class="grid">' + "".join(f'<div class="kpi"><b>{a}</b><span>{b}</span></div>' for a, b in k) + "</div>"


def themes_block(m):
    items = []
    for t, v in sorted(m["tags"].items(), key=lambda kv: -kv[1]["pct"]):
        if t in ("UNCLEAR", "OTHER") or v["n"] == 0:
            continue
        items.append((TAG_LABEL[t], v["pct"], v["n"], "main"))
    items.append(("No usable detail", m["nodetail"], int(m["nodetail"] * m["N"] / 100), "muted"))
    return bar_svg(items)


def trend_table(m):
    rows = []
    for r in m["trend"][:4]:
        if r["tag"] in ("UNCLEAR", "OTHER"):
            continue
        flag = "rising" if r["delta"] > 0 else "falling"
        sig = " (borderline signal)" if abs(r["z"]) >= 1.6 else " (within noise)"
        rows.append(f'<tr><td>{TAG_LABEL[r["tag"]]}</td><td class="num">{r["prior"]:.1f}%</td><td class="num">{r["recent"]:.1f}%</td>'
                    f'<td class="num">{r["delta"]:+.1f} pp</td><td>{flag}{sig}</td></tr>')
    return ('<div class="wrap"><table><tr><th>Theme (primary tag)</th><th class="num">Prior 90d</th><th class="num">Last 90d</th>'
            '<th class="num">Change</th><th>Read</th></tr>' + "".join(rows) + "</table></div>")


def version_table(m):
    rows = "".join(f'<tr><td>{esc(r["v"])}</td><td class="num">{int(r["n"])}</td><td class="num">{r["mean"]:.2f}</td><td class="num">{r["neg"]:.0f}%</td></tr>'
                   for r in m["versions"])
    return ('<div class="wrap"><table><tr><th>App version (last 180 days)</th><th class="num">Reviews</th><th class="num">Avg ★</th>'
            '<th class="num">% 1-2★</th></tr>' + rows + "</table></div>")


def dashboard_html(m):
    s = m["snap"]
    best = m["best_months_neg"]
    target = int(round(best))
    out = [f'<p class="muted small">Snapshot captured {esc(s["captured_on"])} · app version {esc(s["version"])} · review window {m["start"]} to {m["end"]} · {m["n_written"]:,} written reviews</p>',
           kpis(m),
           "<h3>Rating distribution (all ratings)</h3>", '<div style="max-width:440px">' + hist_svg(m["hist_share"], s["histogram_1_to_5"]) + "</div>",
           f'<h3>Share of written reviews that are 1-2★, by month</h3>{line_svg(m["monthly"], target=target)}'
           f'<p class="small muted">Red dots = months at or above 32%; partial months are left out. The dashed line is the average of the four best months in this window ({best:.1f}%), a level the app has already reached.</p>',
           f'<h3>What the 1-2★ reviews are about (n = {m["N"]:,}; a review can carry two themes)</h3>', themes_block(m),
           f'<h3>Emerging: last 90 days ({m["n_recent"]} negative reviews) vs prior 90 days ({m["n_prior"]})</h3>', trend_table(m),
           "<h3>Versions</h3>", version_table(m)]
    return "\n".join(out)


def page(title, body, favicon="📈"):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f'<title>{esc(title)}</title><link rel="icon" href="data:image/svg+xml,'
            f'%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22%3E%3Ctext y=%22.9em%22 font-size=%2290%22%3E{favicon}%3C/text%3E%3C/svg%3E">'
            f'<style>{CSS}</style></head><body><main>{body}</main></body></html>')


# ----------------------------------------------------------- recommendations
def recommendations_html(m):
    g = m["groups"]
    mi = m["micro"]
    um = m["update_month"]
    last_m = sorted(um)[-1]
    tr = {r["tag"]: r for r in m["trend"]}
    crash = tr["CRASH"]
    G1, G2, G3, G4 = g["Reliability & access"], g["Tracking, cab ops & routing"], g["Booking / roster"], g["Support"]
    s = m["snap"]
    best = m["best_months_neg"]

    def lift(x):
        return f'+{x["lift50"]:.2f} to +{x["lift100_5"]:.2f}'

    html_ = f"""
<h2>What to do first</h2>
<div class="callout"><b>Do these three first, in this order.</b>
<ol>
<li><b>Make the app stay logged in and stop failing.</b> Reliability and access problems (crashes, slowness, login or OTP failures, forced logouts) appear in {G1["pct"]:.0f}% of 1-2★ reviews. This is the biggest and most fixable block, and it is all Engineering.</li>
<li><b>Fix live tracking and tell people what is happening to their cab.</b> Tracking, late cabs and routing appear in {G2["pct"]:.0f}% of 1-2★ reviews. Part of this is operations, but the app can still show a reason and a new ETA.</li>
<li><b>Put a safety net around releases and answer the reviews.</b> Staged rollouts are normally a small engineering change, and weekly review replies need no engineering at all; only {m["reply_neg"]:.1f}% of 1-2★ reviews get a reply today.</li>
</ol></div>

<div class="callout warn"><b>Be realistic about the number.</b> The app is already at {s["score"]:.2f} from {s["ratings"]:,} ratings, because {m["hist_share"][4]*100:.1f}% of ratings are 5★.
The gap is the {m["hist_share"][0]*100:.1f}% of ratings that are 1★ ({int(s["histogram_1_to_5"][0]):,} people). Reaching 4.8 would need about {m["need_conv_48"]:,.0f} of them ({m["need_conv_48_share"]*100:.0f}%) to become 5★.
Even if <i>every</i> 1-2★ rating became 4★ the score would be {m["ceiling_4"]:.2f}. Fixing the main areas (reliability, tracking and cab ops, booking, support) for half of the affected people is worth roughly +{m["union_top"]["lift50"]:.2f} on the lifetime score, if they then rate 4★.
Because the lifetime number moves slowly, track the <b>share of written reviews that are 1-2★</b> as the leading indicator. It is {m["neg_share_written"]*100:.1f}% overall and was already about {best:.0f}% in the app's four best months, so {int(round(best))}-{int(round(best))+1}% is a credible target.</div>

<h2>Prioritised recommendations</h2>
<p class="muted small">Ranked by modelled impact against effort. "Lift" is the modelled change in the lifetime rating if half of the affected users moved to 4★, up to all of them moving to 5★. Themes overlap, so lifts are not additive.</p>

<article class="rec"><h3><span class="tag first">P1 · do first</span> Keep people logged in; stop crashes, hangs and blank screens</h3>
<dl>
<dt>Problem</dt><dd>Users are logged out repeatedly, cannot get a login OTP, or hit slow, frozen or blank screens that only a reinstall fixes.</dd>
<dt>Evidence</dt><dd>{G1["pct"]:.0f}% of 1-2★ reviews ({G1["ratings"]:,} ratings if representative). Forced logout/re-login: {m["tags"]["SESSION"]["n"]} reviews. Slow/lag/hang/crash words: {mi["Slow / lag / hang / crash"]}. Login OTP or code not received: {mi["OTP / code not received"]}. Reviewers say they had to reinstall or clear data: {mi["Forced to reinstall / clear data"]}. Crash-type complaints rose from {crash["prior"]:.1f}% to {crash["recent"]:.1f}% of negatives in the last 90 days (borderline signal, z≈{crash["z"]:.1f}).</dd>
<dt>Fix</dt><dd>(a) Keep sessions alive with refresh tokens and no forced re-auth within a set period (e.g. 30 days) unless security requires it. (b) Add a second OTP channel (email or WhatsApp), a resend timer and delivery-failure monitoring on the SMS route. (c) On app start, detect corrupted local state and self-reset instead of asking users to reinstall. (d) Review the top 10 crash and ANR clusters in Play Console / Crashlytics and fix them in order of affected users.</dd>
<dt>Owner</dt><dd>Engineering (mobile + auth backend)</dd>
<dt>Success</dt><dd>Reliability-and-access share of 1-2★ reviews from {G1["pct"]:.0f}% to under 25% in 8 weeks; "logged out" and "OTP not received" reviews halved; crash-free sessions above 99.5%.</dd>
<dt>Modelled lift</dt><dd>{lift(G1)} on the rating</dd>
</dl></article>

<article class="rec"><h3><span class="tag first">P2 · do first</span> Make live tracking reliable and explain delays in the app</h3>
<dl>
<dt>Problem</dt><dd>Location updates lag or jump, the map keeps resetting, and when a cab is late or changes, the user is not told why. Users blame the app even when the cause is operational.</dd>
<dt>Evidence</dt><dd>{G2["pct"]:.0f}% of 1-2★ reviews mention tracking, late or no-show cabs, or routing. Tracking words appear in {mi["Tracking wrong / not updating"]} reviews, calling or chatting with the driver in {mi["Call / chat with driver"]}, no-show disputes in {mi["No-show disputes"]}, map auto-zoom resets in {mi["Map auto-zoom"]}. One of the most up-voted reviews says calling the driver is blocked by a "company policy" message, and the reviewer missed a bus.</dd>
<dt>Fix</dt><dd>(a) Raise the location refresh rate during the last 15 minutes before pickup, and show "last updated Xs ago". (b) Stop the map from resetting the zoom every 30 seconds; focus on the cab until pickup, then the destination. (c) When a cab is delayed or reassigned, show the reason and a new ETA. (d) Fix in-app call/chat with the driver, including the policy-blocked case. (e) Show proof of waiting and a one-tap dispute for no-shows.</dd>
<dt>Owner</dt><dd>Engineering + Product; Ops for the cab-delay reasons</dd>
<dt>Success</dt><dd>Tracking and late-cab share of 1-2★ reviews from {G2["pct"]:.0f}% to under 18%; no-show dispute reviews halved; call-failure tickets down.</dd>
<dt>Modelled lift</dt><dd>{lift(G2)} on the rating</dd>
</dl></article>

<article class="rec"><h3><span class="tag first">P3 · do first</span> Release safety net</h3>
<dl>
<dt>Problem</dt><dd>Negative reviews cluster around specific releases, and changes arrive without notice.</dd>
<dt>Evidence</dt><dd>In {last_m}, {um[last_m]["k"]} of {um[last_m]["n"]} negative reviews ({um[last_m]["pct"]:.0f}%) mention an update, against {m["update_overall"]:.0f}% over the whole period (an early signal on a small number, coinciding with the latest build, v{esc(s["version"])}). Two 2026 dips (June and August) reached 32-34% negative, against about 22% in March-May and July. They fall on builds 12.13-12.14 and 12.16-12.17, but release dates are needed to confirm a link.</dd>
<dt>Fix</dt><dd>(a) Staged rollout: 5% → 20% → 50% → 100% with automatic halt if the crash rate or the 1-2★ share rises. (b) Show a short "what's new" note for behaviour changes (for example the seat-belt prompt before the boarding OTP, or the tracking-window change). (c) Put risky changes behind remote flags so they can be switched off. (d) Share the release calendar with the ratings dashboard so each dip can be tied to a build.</dd>
<dt>Owner</dt><dd>Engineering + Product</dd>
<dt>Success</dt><dd>No month above 30% 1-2★; update-mentioning share of negatives under 8% in the month after each release.</dd>
</dl></article>

<article class="rec"><h3><span class="tag">P4</span> Booking and cancellation integrity</h3>
<dl>
<dt>Problem</dt><dd>Schedules do not show, bookings are cancelled or moved to a waitlist without notice, and users are marked no-show when they were not at fault.</dd>
<dt>Evidence</dt><dd>{G3["pct"]:.0f}% of 1-2★ reviews ({m["tags"]["BOOKING"]["n"]} reviews).</dd>
<dt>Fix</dt><dd>Send a push notification and an in-app banner for every automatic status change (cancellation, waitlist, reassignment), with the reason. Add an appeal path for no-show marks. Fix desk/seat selection bugs.</dd>
<dt>Owner</dt><dd>Product + Engineering; Ops for no-show policy</dd>
<dt>Success</dt><dd>Booking share of 1-2★ reviews from {G3["pct"]:.0f}% to under 8%.</dd>
<dt>Modelled lift</dt><dd>{lift(G3)} on the rating</dd>
</dl></article>

<article class="rec"><h3><span class="tag first">P5 · quick win</span> Answer the reviews that matter</h3>
<dl>
<dt>Problem</dt><dd>Almost no replies, and the ones that exist are generic thanks to happy users.</dd>
<dt>Evidence</dt><dd>{m["replies_n"]} replies across {m["n_written"]:,} reviews ({m["reply_all"]:.1f}%); only {m["reply_neg"]:.1f}% of 1-2★ reviews got one. Helpdesk unreachable or no response is raised in {mi["Helpdesk unreachable / no reply"]} negative reviews.</dd>
<dt>Fix</dt><dd>Reply to every 1-2★ review within 48 hours using theme-specific templates (login help, tracking, booking) that give the next step and an in-app support route. Do not ask users to change their rating. Review the replies weekly.</dd>
<dt>Owner</dt><dd>Support / Product (no engineering needed)</dd>
<dt>Success</dt><dd>At least 60% of 1-2★ reviews replied within 48 hours; support-themed share of negatives falls from {G4["pct"]:.0f}%.</dd>
<dt>Modelled lift</dt><dd>{lift(G4)} on the rating, plus some users edit their review after a reply</dd>
</dl></article>

<article class="rec"><h3><span class="tag">P6</span> Rating prompt policy</h3>
<dl>
<dt>Problem</dt><dd>Some users are asked to rate or give feedback after every ride, with no way to skip.</dd>
<dt>Evidence</dt><dd>{m["tags"]["RATEPROMPT"]["n"]} negative reviews complain about it (small but irritating). Written reviews run far more negative than the rating base ({m["neg_share_written"]*100:.0f}% vs {m["hist_share"][0]*100+m["hist_share"][1]*100:.1f}%), so happy riders are under-represented.</dd>
<dt>Fix</dt><dd>Ask for a Play Store rating only after a successful trip, not on every ride and at most once per 90 days, with a clear "Not now". Keep a separate in-app trip feedback form and a "Report a problem" button on the trip-end screen. Do not hide the store review option from unhappy users, because steering unhappy users away from the store can conflict with Google Play's review guidelines.</dd>
<dt>Owner</dt><dd>Product</dd>
<dt>Success</dt><dd>Rating-prompt complaints near zero; more 5★ ratings from happy riders. As an illustration, 10% more 5★ ratings would add about +{m["mix_shift_10"]:.2f} (assumption, not forecast).</dd>
</dl></article>

<article class="rec"><h3><span class="tag">P7</span> Small fixes that users keep raising</h3>
<dl>
<dt>Backlog</dt><dd>
<ul>
<li>Terms and agreement pop-up shown again on every open ({mi["Terms / agreement pop-up"]} reviews).</li>
<li>QR scan problems: trip not marked as started, blurry camera, torch left on ({mi["QR scan problems"]} reviews).</li>
<li>Clearer "Login" and "Logout" labelling for shift times, which night-shift users find confusing.</li>
<li>Dark mode, a clearer feedback form, and chat or call with the driver (requests).</li>
</ul></dd>
<dt>Owner</dt><dd>Product + Engineering</dd>
</dl></article>

<h2>How this is tracked every week</h2>
<p>The repository includes a scheduled GitHub Action. Every Monday it re-scrapes the Play Store, re-tags the reviews, and rebuilds the dashboard page: current rating and histogram, 1-2★ share by month, theme shares, which themes are rising in the last 90 days, and a version table. The question "How are our ratings?" is answered by one link.</p>
"""
    return html_


def method_html(m, val):
    v = val
    return f"""
<h2>How I got here, and the limits</h2>
<ul>
<li><b>Scope.</b> Employee app <code>com.moveinsync.ets</code> ({m["snap"]["score"]:.2f}, {m["snap"]["ratings"]:,} ratings). Driver Partner (3.5) has only 46 ratings and 7 written reviews, too few to analyse; it is a footnote.</li>
<li><b>Data.</b> Public Play Store data via google-play-scraper: the app snapshot (rating, exact histogram, version) and {m["n_written"]:,} written reviews from {m["start"]} to {m["end"]}. Written reviews are about {m["neg_share_written"]*100/ (m["hist_share"][0]*100+m["hist_share"][1]*100):.1f}x more negative than the full rating base, so they show what unhappy users say, not what the average user feels.</li>
<li><b>Tagging.</b> A rule-based tagger (keyword rules, free, repeatable) assigns up to two themes per review from a 16-tag taxonomy built around the employee journey. I hand-labelled 100 reviews (36 labels were revised after a second-opinion pass with Claude), then split them 50 for tuning and 50 held out. On the held-out 50: main theme exactly right {v["test"]["tag1_exact"]*100:.0f}%, right within the top two themes {v["test"]["top2"]*100:.0f}%, agreement (kappa) {v["test"]["kappa"]:.2f}. On the tuning set it reached {v["dev"]["tag1_exact"]*100:.0f}%, which is optimistic. Spot checks: forced-logout tag {v["spot_check"]["SESSION"]}, cab-ops tag {v["spot_check"]["LATE"]}. Treat theme shares as roughly ±10 percentage points and rely on the grouped numbers.</li>
<li><b>{m["nodetail"]:.0f}% of negative reviews say nothing usable</b> (for example "worst app"), and are shown as "No usable detail".</li>
<li><b>Modelled lift</b> assumes the themes in written 1-2★ reviews are representative of all 1-2★ ratings. That is an assumption, not a measurement.</li>
<li><b>Tools.</b> Python (pandas, google-play-scraper, scikit-learn), regular-expression tagging, GitHub Actions for the weekly run, and Claude as an assistant for planning, code and drafting. An LLM tagger notebook is also included and can replace the rules.</li>
<li><b>With a week of access to the ops team I would</b> match each theme to ticket data, get the release calendar and crash dashboards, and interview five riders and two transport desk staff to see which complaints are app problems and which are operations.</li>
</ul>
"""
