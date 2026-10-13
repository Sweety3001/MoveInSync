# Submission cheat-sheet (fill in the form with these)

## Before you submit (about 15 minutes)
1. Create a **public** GitHub repo and upload everything in `moveinsync_submission_pack.zip` (unzipped, keep the folder structure, including the hidden `.github` folder).
2. In the repo: Settings, Pages, deploy from branch `main`, folder `/docs`. Then Actions, run the weekly workflow once.
3. Open the published report page and use its Share control so **anyone with the link** can view it. Open the links in a private browser window to check. The form says links that are not public will not be counted.
4. Fill in your registration number, name, contact number, email, LinkedIn and CV link yourself.

## Form field 5: Submission link(s)
`<your GitHub repo URL>`, `<report link from the published page>`

## Form field 6: Demo / dashboard links
`<GitHub Pages URL, e.g. https://YOURNAME.github.io/REPO/>` (live dashboard), optional 2-3 minute screen recording walking through the report headline and the three "do first" items.

## Form field 7: Short note (paste this)
I scoped the Play Store apps first: the employee app is at 4.64 on 114,879 ratings, while Driver Partner is 3.5 but has only 46 ratings, so I focused on the employee app. I scraped the app snapshot and 5,712 written reviews (Oct 2024 to Oct 2026) with google-play-scraper, tagged each review against a 16-theme taxonomy mapped to the rider journey, and used the exact star histogram to size how much each theme could move the rating. The tagger is rule-based so it is free and repeatable. I validated it on 100 hand-labelled reviews (50 for tuning, 50 held out): 64% exact main theme and 78% within the top two on the held-out set, so I treat single-theme shares as approximate and lean on grouped numbers. Findings: the lost points are the 6.4% of 1★ ratings; reliability and access issues (38% of 1-2★ reviews) and tracking/cab operations (25%) come first, then a release safety net and replying to reviews (only 4.2% of 1-2★ reviews get a reply). The report has 7 ticket-style recommendations with owner, success metric and modelled impact. A GitHub Action rebuilds a dashboard every Monday, so "How are our ratings?" is answered by one link. Tools: Python, pandas, google-play-scraper, scikit-learn, GitHub Actions and Pages, and Claude for planning, code and drafting (it also gave a second opinion on 36 of my 100 labels). Limits: written reviews skew negative, 29% of negative reviews have no usable detail, and the lift numbers assume written themes represent all 1-2★ ratings.

## Be ready to explain in the interview
- Why the taxonomy follows the employee journey, and why `SESSION` (forced logout) is separate from `LOGIN`.
- How the tagger was validated, and why the held-out number (64%) is the one to quote.
- Where the rating-lift numbers come from: exact histogram, assumption that written 1-2★ themes represent all 1-2★ ratings, and the 4.8 maths (about 4,629 of the 7,317 one-star ratings must become 5★).
- What you would do with a week of access to ops: match themes to tickets, get the release calendar, interview riders and transport desk staff.
