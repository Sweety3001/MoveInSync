# MoveInSync Play Store ratings: why they are where they are, and what to fix

Case study for the MoveInSync Forward Deployed Engineer (intern to FTE) role.

**Main deliverable:** `report.html` (findings, 7 ticket-style recommendations, method and limits).
**Recurring answer to "How are our ratings?":** `docs/index.html`, rebuilt every Monday by a GitHub Action.

## Headline
The employee app is rated 4.64 on 114,879 ratings. The lost points are the 6.4% of ratings that are 1★.
Their written reviews point to reliability and access (38% of 1-2★ reviews), tracking and cab operations (25%) and booking (12%).
Do first: (1) stop forced logouts, login/OTP failures and crashes, (2) make live tracking reliable and explain delays, (3) add a release safety net and answer reviews.

## Folder map
| Path | What it is |
|---|---|
| `report.html` | Full report (open in a browser) |
| `docs/index.html` | Weekly dashboard (publish with GitHub Pages) |
| `src/scrape_playstore.py` | Pulls app snapshot (rating, exact histogram) and reviews |
| `src/tagger.py` | Rule-based review tagger (16-tag taxonomy, free, deterministic) |
| `src/report_lib.py` | Metrics, SVG charts, recommendation text |
| `src/make_report.py` | Builds `report.html` |
| `src/weekly_dashboard.py` | Scrape, tag, rebuild `docs/index.html` |
| `.github/workflows/weekly.yml` | Monday 03:30 UTC schedule (plus manual run) |
| `notebooks/step4_tagger_free.ipynb` | Optional LLM tagger (Gemini free tier) to replace the rules |
| `data/` | Snapshots, reviews, tagged reviews, 100-review gold labels, validation numbers |

## Run it
```bash
pip install -r requirements.txt
python src/weekly_dashboard.py --offline   # rebuild from the files in data/ (no network)
python src/weekly_dashboard.py             # live: scrape Google Play, re-tag, rebuild
python src/make_report.py                  # rebuild report.html
```

## Make the weekly page live
1. Push this folder to a public GitHub repo.
2. Settings, Pages, deploy from branch `main`, folder `/docs`.
3. Actions tab, run "Weekly Play Store rating dashboard" once to test. After that it runs every Monday.

## Taxonomy (v2)
LOGIN, SESSION, CRASH, BOOKING, ROUTING, ETA, LATE, OTP (boarding), SAFETY, SUPPORT, NOTIF, UI, RATEPROMPT, REQUEST, OTHER, UNCLEAR.
Each review gets up to two themes, a trigger (for example `after_update`) and an owner (Eng / Product / Ops).
Key rules: a failing feature gets the feature's tag, a global failure (will not open, slow, server error) is CRASH; a late cab is LATE with owner Ops even if the user blames the app.

## Validation (100 hand-labelled reviews, split 50 tune / 50 held out)
| Set | Main theme exact | Within top two | Kappa | Owner | Trigger |
|---|---|---|---|---|---|
| Tuning (50) | 84% | 92% | 0.82 | 90% | 70% |
| Held out (50) | 64% | 78% | 0.60 | 72% | 52% |

Spot checks: forced-logout tag about 78% precise, cab-ops tag about 60%. Treat single-theme shares as roughly ±10 points and rely on grouped numbers.
36 of the 100 gold labels were revised after a second-opinion pass with Claude, so the gold set is not fully independent of AI.

## Limits
- Written reviews are about 4x more negative than the full rating base (28.6% vs 7.1% at 1-2★). They show what unhappy users say.
- 29% of negative reviews have no usable detail.
- Modelled rating lift assumes written 1-2★ themes represent all 1-2★ ratings.
- Dips in June and August 2026 line up with specific builds, but release dates are needed to confirm.
- Driver Partner (3.5) has only 46 ratings and 7 written reviews, so it was not analysed.
