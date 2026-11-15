# Anatta × Shopify — partner triangulation for CT's book (Nov 2026)

Scores every account in CT's book of business against two ICPs — Shopify's enterprise/Plus sales motion and
Anatta's services motion — blends them into a triangle score, gates and tiers them. Same rubric, weights, thresholds
and gates as the October 2026 Anatta × Shopify build (`dashboards/anatta-shopify-triangulation`), so the two books
compare directly.

The deliverable is a single self-contained HTML file in two variants: an internal copy and a copy that is safe to
share with Shopify, each with a CSV of the scored book. It has two views (Overview, Account Dashboard), plus a Hub
Map view and named people on every account when a contacts export is supplied. Data files, the book config and the
generated HTML are **not** committed here; the code needed to regenerate them is in `pipeline/`.

## Result (11 Nov 2026)

79 accounts, 73 companies once shared rows are grouped: 8 golden-triangle rows across 5 companies (T1), 13 strong
(T2), 13 develop (T3), 31 watch (T4), 14 disqualified (X), none already on Shopify Plus. 27 accounts got a second
look and 9 records carry a documented adjustment.

Contacts (added 15 Nov 2026): 656 people in the export, 643 kept, 590 placed in 73 metro hubs of 120 km. 240 of them
sit at Tier 1 and Tier 2 accounts and 222 at disqualified accounts (184 at the four universities), so the hub map
opens filtered to the top two tiers.

## Inputs

| File | What it is |
|---|---|
| Apollo accounts export (79 rows) | Account name, website and the FIRE fields Anatta maintains |
| BuiltWith export of the book (78 domains) | Detected commerce platform and stack, with first/last-detected dates for tracked apps |
| Apollo contacts export (optional, 656 rows) | Name, title, company, email, LinkedIn address, city, state, country |

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
| 7 | `build_hubs.py` (optional) | Contacts layer: dedupes the contacts export, joins each person to an account row, reads seniority and function off the title, geocodes against GeoNames places of 500+ people and clusters them into 120 km hubs. Drops CRM record IDs and leaves out people exported under a wrong-company match. Needs the `geonamescache` package. |
| 8 | `assemble.py` | Embeds the scored book (and the contacts layer, if built) into `dashboard.html`. Writes the internal and shareable copies, each as a standalone file, as a page fragment for publishing and as a CSV; removes the internal-only section from the shareable copy and asserts it carries no internal-only field, CRM note or record ID. Contact emails are shown in full only in the internal standalone file; every other output masks them, and the build asserts the exact masked count. |

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

# with a contacts export: hub map and people on each account
pip install geonamescache
npm install d3@7.9.0 topojson-client@3.1.0 topojson-server@3.0.1 us-atlas@3.0.1 world-atlas@2.0.2      # in <libs>
TRI_LIBS=<libs>/node_modules node pipeline/prune_countries.js <libs>/node_modules/world-atlas/countries-50m.json <libs>/na-countries-50m.json
python3 pipeline/build_hubs.py <apollo_contacts.csv> <build>/scored.json <build>/book.json <build>/hubs.json
python3 pipeline/assemble.py <build>/scored.json <out> <build>/hubs.json <libs>
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
- **One documented whitespace cap.** One account went live on a competitor's enterprise platform inside the last
  two years and is that vendor's showcase. The rubric's top whitespace band is for legacy platforms, so its platform
  whitespace is capped at 15 of 25 (`whitespace_cap` in `book.json`), the same cap the October build used for
  platforms Shopify cannot convert in a quarter. The uncapped score stays on the record.
- **Second look was a consistency check.** The research pass used the whole web-search budget for the run (200
  searches), so the two verifiers checked each top-tier record and each judgment-call gate against its own sourced
  evidence and the rubric's wording instead of searching again (`"verification": "consistency"` in `book.json`).
  They pulled five Shopify scores down and removed three distress gates that did not meet the rubric's test.
- **Internal vs shareable.** The internal copy shows which accounts are in Salesforce and a section on how far to
  trust our own signal. The shareable copy drops both from the data and the page, along with notes that correct our
  own earlier review of the book.
- **Contacts under the wrong company.** The people Apollo exported under the misattributed account belong to other
  companies of the same name, so they are left out and counted (`contacts_wrong_company` in `book.json`). Four
  company names in the contacts export needed a manual match to an account row (`contact_company_alias`).
- **Emails.** Full addresses appear only in the internal standalone file. The shareable copy and both published
  page fragments show first initial and domain.
