# Anatta × Shopify — partner triangulation for CT's book (Nov 2026)

Scores every account in CT's book of business against two ICPs — Shopify's enterprise/Plus sales motion and
Anatta's services motion — blends them into a triangle score, gates and tiers them. Same rubric, weights, thresholds
and gates as the October 2026 Anatta × Shopify build (`dashboards/anatta-shopify-triangulation`), so the two books
compare directly.

The deliverable is a single self-contained HTML file with two views (Overview, Account Dashboard) in two variants:
an internal copy and a copy that is safe to share with Shopify. No contacts export was in scope, so there is no hub
map. Data files and the generated HTML are **not** committed here; everything needed to regenerate them is in
`pipeline/`.

## Inputs

| File | What it is |
|---|---|
| Apollo accounts export (79 rows) | Account name, website and the FIRE fields Anatta maintains |
| BuiltWith export of the book (78 domains) | Detected commerce platform and stack, with first/last-detected dates for tracked apps |

## Pipeline (run in this order)

| Step | Script | What it does |
|---|---|---|
| 0 | `book.json` | Not a script: the one file that names accounts (domain aliases, shared buying centres, display names, the misattributed-signal list, the batch plan). It lives with the data and is not committed; `book.example.json` documents the shape. |
| 1 | `build_inputs.py` | Joins the two exports into one research input per account. Nine accounts carry a different domain in the two files; `book.json` records each one and why. Salesforce record IDs never leave the export (only an in-Salesforce yes/no is kept). |
| 2 | `triage.py` | Gates the universities by rule. With 79 accounts and an unreliable CRuX column, every other account is researched. |
| 3 | `make_batches.py` | Splits the rest into research batches, keeping rows that share a buying centre together. "Full" batches get 2–4 searches per account; "light" batches (no visible commerce surface) get one. |
| 4 | research agents + `validate_batch.py` | One agent per batch scores both legs per `rubric.md` with sourced web evidence and writes `results/batch_NN.json`; the validator enforces names, schema and ranges. |
| 5 | `make_verify.py`, verifier agents + `validate_verify.py` | Provisional T1 accounts get two adversarial lenses (platform & scale; business model & gates), T2 gets the platform lens, and every judgment-call gate (distress, gov, already_plus) gets the model lens. |
| 6 | `score.py` | **Single source of truth** for every number: merges research, triage and verifier verdicts; computes Shopify fit, Anatta fit (with the deterministic FIRE intent subscore), triangle, gates and tiers; asserts subscore sums, source-exact FIRE values, a written play for every T1 and that no Salesforce ID is present. |
| 7 | `assemble.py` | Embeds the scored book into `dashboard.html`. Writes the internal and shareable copies, each as a standalone file and as a page fragment for publishing; asserts the shareable copy carries no internal-only field or CRM note. |

```bash
# book.json (see pipeline/book.example.json) holds everything that names an account; it lives with the data
python3 pipeline/build_inputs.py <builtwith.csv> <apollo_accounts.csv> <build>/book.json <build>/accounts_input.json
python3 pipeline/triage.py <build>
python3 pipeline/make_batches.py <build> <build>/book.json [prior_review.json]
# research agents write <build>/results/batch_NN.json; check each with validate_batch.py <build> batch_NN
python3 pipeline/score.py <build> <apollo_accounts.csv> <build>/book.json <build>/scored.json
python3 pipeline/make_verify.py <build> <build>/scored.json
# verifier agents write <build>/verify/<part>__<lens>.json; check each with validate_verify.py
python3 pipeline/score.py <build> <apollo_accounts.csv> <build>/book.json <build>/scored.json
python3 pipeline/assemble.py <build>/scored.json <out>
```

## Scoring in one paragraph

Shopify fit = platform whitespace 25 + commerce scale 20 + business-model fit 20 + unified-commerce surface 15 +
timing 10 + ecosystem pull 10, plus explicit penalties, clamped 0–100. Anatta fit = brand/storefront surface 20 +
modernisation need 20 + scale for a retainer 20 + LTV/subscription complexity 20 + FIRE intent 20 (computed
straight from the export). Triangle = round(0.55 × Shopify + 0.45 × Anatta + small intent bonuses). T1 needs
triangle ≥ 62 and Shopify fit ≥ 63; T2 ≥ 48; T3 ≥ 36; T4 otherwise. Gates: Shopify Plus already live → EXP;
government, distress, no commerce surface (only when Shopify fit < 20), bad record, restricted → X.

## What is specific to this book

- **Signal attached to the wrong company.** Apollo matched one account to a different company from the one in the
  book. Its FIRE fields are shown exactly as exported but are not scored (`signal_misattributed` in `book.json`).
- **Shared buying centres.** Ten rows roll up to four companies (`groups` in `book.json`). Each row is scored on its
  own storefront and marked as a shared decision.
- **Old signal.** The newest FIRE signal is 53 days older than the build, and the recency labels were computed about
  seven weeks earlier. Researchers treated a FIRE signal or an In-market flag as soft unless public evidence backed
  it; the 20-point intent subscore is still computed from the export exactly as written.
- **CRuX is unreliable here.** Several national retailers show the lowest traffic band, so commerce scale is scored
  from revenue, store counts and headcount.
- **Internal vs shareable.** The internal copy shows which accounts are in Salesforce and a section on how far to
  trust our own signal. The shareable copy drops both from the data, not just from the page.
