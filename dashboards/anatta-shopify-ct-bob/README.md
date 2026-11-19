# Anatta × Shopify — partner triangulation for one book of accounts

Scores every account in a book of business against two ICPs — Shopify's enterprise/Plus sales motion and
Anatta's services motion — blends them into a triangle score, gates and tiers them. Same rubric, weights, thresholds
and gates as the October 2026 Anatta × Shopify build (`dashboards/anatta-shopify-triangulation`), so books compare
directly.

The pipeline was built for CT's book (11 Nov 2026), which is why the folder carries that name, and was run again
for a second, larger book (19 Nov 2026). Everything that names an account lives in that book's `book.json`, next to
its data, never here.

The deliverable is a single self-contained HTML file in two variants: an internal copy and a copy that is safe to
share with Shopify, each with a CSV of the scored book. It has two views (Overview, Account Dashboard), plus a Hub
Map view and named people on every account when a contacts export is supplied. Data files, the book config and the
generated HTML are **not** committed here; the code needed to regenerate them is in `pipeline/`.

## CT's book (11 Nov 2026)

79 accounts, 73 companies once shared rows are grouped: 8 golden-triangle rows across 5 companies (T1), 13 strong
(T2), 13 develop (T3), 31 watch (T4), 14 disqualified (X), none already on Shopify Plus. 27 accounts got a second
look and 9 records carry a documented adjustment.

Update 15 Nov 2026: one Tier 1 account was set aside because Anatta no longer pursues it. The book now reads 7
golden-triangle rows across 4 companies (T1), 13 strong, 13 develop, 31 watch and 15 set aside (X).

Contacts (added 15 Nov 2026): 656 people in the export, 643 kept, 590 placed in 73 metro hubs of 120 km. 195 of them
sit at Tier 1 and Tier 2 accounts and 267 at accounts that are set aside (184 at the four universities, 45 at the
account we no longer pursue), so the hub map opens filtered to the top two tiers.

## The second book (19 Nov 2026)

195 accounts, built from three inputs and a live check: the Apollo accounts export, a BuiltWith detect export (192
domains), a Store Leads export of the 204 rows the book lists, and 226 storefront hosts loaded on the day. The 9
listed rows with no Apollo account are a second storefront of an account that is in Apollo and are attached to it.

- **Platform read.** All three independent reads agree for 44 accounts and two agree for 12; 14 rest on one read,
  1 has reads that disagree, and for 124 no source names a platform (owners, non-merchants, in-house builds).
- **Research.** 12 accounts were gated by rule (3 universities, 9 owner or holding entities). The other 183 were
  researched in 17 batches, 172 on a full pass and 11 on a one-source pass, with about 130 web searches.
- **Second look.** 127 accounts got 186 verdicts from 14 verifiers, each with its own searches: 163 confirmed,
  23 adjusted, none refuted. For 9 rows (3 in T1, 6 in T2) the verifiers' own figures would give a lower tier than
  the average the method uses; the page labels each one.
- **Result.** 51 golden-triangle rows across 36 companies (T1), 50 strong (T2), 26 develop (T3), 12 watch (T4),
  11 already on Shopify Plus (EXP) and 45 set aside (X). 109 rows sit in 32 shared decisions and 99 rows under 19
  owners.
- **Can move, hard to move.** 70 records carry the documented whitespace cap. Of the 36 golden-triangle companies,
  20 have an uncapped golden row and 16 do not: the page leads with the 20 and lists the 16 apart.
- **Heartbeat ranking (19 Nov 2026).** The page now leads with the Heartbeat score, run by the Heartbeat Source's
  own `rescore.py`. Of 118 companies, 69 sit inside Anatta's ICP and are ranked (55 core, 14 adjacent), 10 are
  outside it and 39 are gated out. 15 have recurring purchase live and 43 can add Shop Pay to the checkout they run.
  The inputs came from a second research pass (10 batches) and three scans of each store. A browser scan read 118
  of 159 store sites and ran a search on 85. It confirmed the export for most partners, and only 4 of 11 of its
  listings of one search tool, so a listing of that tool resting on the export alone is not counted. For 5 ranked
  companies no scan could read a store the company runs itself: their partner motion is unknown and counts as 0.
- **Second look at the Heartbeat inputs (19 Nov 2026).** `subscription_scan.js` loaded 209 stores in a browser and
  read 156; the rest refused it. A second research round (11 batches, 87 companies, ranked or not)
  then settled recurring purchase program by program: 197 programs recorded, 46 counted and live, each with its
  terms, the engine where one was seen, the page and the date it was read. 18 ranked companies now carry the bonus.
  The round also filed 69 sourced corrections to the inputs, re-verified 54 dated events and added 19.
  First-hand evidence overruled the exports in two ways: a rebuilt store whose security policy allows none of a
  vendor's hosts, and a name sitting in a page's source while the store calls another tool for the same job.
  18 of the 69 scores changed. The page gained the insight layer (8 findings, a one-line read on all 69 ranked
  companies, the full set of lines and proof stories on 31) and a table of every program in rank order.
- **Release QA.** `qa.py` on the released files: 27,109 checks passed, 0 failed. Its first run, on the
  page as first published, found 2 email addresses inside research notes, "AE" in 4, em dashes in 7, and a firm
  that builds for an account named at 7 companies. `assemble.py` now applies the house wording to every note, and
  the list is labelled "the enterprise account list" (title "Enterprise Accounts Triangulation").

## Inputs

| File | What it is |
|---|---|
| Apollo accounts export | Account name, website and the FIRE fields Anatta maintains |
| BuiltWith export of the book | Detected commerce platform and stack with first/last-detected dates. Either one wide CSV (a row per domain) or a "detect" export (a zip or folder of per-category CSVs) |
| Store Leads export of the book's domains (optional) | Platform, an online-sales estimate, theme, installed apps and the last platform change, per storefront |
| Live storefront check (optional, made by `live_check.py`) | What answered at each address on the day of the build, and the platform fingerprints on the page |
| Apollo contacts export (optional) | Name, title, company, email, LinkedIn address, city, state, country |

With Store Leads or the live check in the build, every account carries a **platform read**: what each source says
the storefront runs on, side by side. BuiltWith's export, Store Leads and the live site are three independent reads.
A read counts only for the account's own main storefront, so a detection on a side host, on another site the address
redirects to, a one-off detection or one not seen recently is listed with the reason it is not counted. Apollo's own
BuiltWith column is the same vendor with no host and no last-seen date: it is shown as context and never counted.
Nothing is voted on or averaged. Research settles the platform; the read tells it where to look.

## Pipeline (run in this order)

| Step | Script | What it does |
|---|---|---|
| 0 | `book.json` | Not a script: the one file that names accounts (domain aliases, extra storefronts, shared buying centres, owner families, display names, the misattributed-signal list, rule triage, the batch plan). It lives with the data and is not committed; `book.example.json` documents the shape. |
| 0.5 | `live_check.py` (optional) | Loads each storefront once and reads the platform off the page: final address after redirects, platform fingerprints in the HTML, headers and cookies, the Shopify theme object. A bot wall or a failed fetch is recorded as such, never as "no store". Standard library only. |
| 1 | `build_inputs.py` | Joins the exports into one research input per account and, with Store Leads or the live check, builds each account's platform read. Where the book and Apollo disagree on a domain, `book.json` records each one and why. Asserts that every BuiltWith domain and every Store Leads row is attached to an account. Salesforce record IDs never leave the export (only an in-Salesforce yes/no is kept). |
| 2 | `triage.py` | Gates the universities by rule, plus any owner or holding entity `book.json` names (a private-equity firm, a holding company: it runs no storefront, and its companies sit on their own rows). Every other account is researched. |
| 3 | `make_batches.py` | Splits the rest into research batches, keeping rows that share a buying centre together. "Full" batches get 2–4 searches per account; "light" batches (no visible commerce surface) get one. |
| 4 | research agents + `validate_batch.py` | One agent per batch scores both legs per `rubric.md` with sourced web evidence and writes `results/batch_NN.json`; the validator enforces names, schema and ranges. |
| 5 | `make_verify.py`, verifier agents + `validate_verify.py` | Provisional T1 accounts get two adversarial lenses (platform & scale; business model & gates), T2 gets the platform lens, and every judgment-call gate (distress, gov, already_plus) gets the model lens. Each job carries the platform read, so a verifier checks the record against the sources and not only against itself. A third argument splits a long lens into parts, keeping one owner's rows together. |
| 6 | `score.py` | **Single source of truth** for every number: merges research, triage and verifier verdicts; computes Shopify fit, Anatta fit (with the deterministic FIRE intent subscore), triangle, gates and tiers; asserts subscore sums, source-exact FIRE values, a written play for every T1 and that no Salesforce ID is present. |
| 7 | `build_hubs.py` (optional) | Contacts layer: dedupes the contacts export, joins each person to an account row, reads seniority and function off the title, geocodes against GeoNames places of 500+ people and clusters them into 120 km hubs. Drops CRM record IDs and leaves out people exported under a wrong-company match. Needs the `geonamescache` package. |
| 8 | `assemble.py` | Embeds the scored book (and the contacts layer, if built) into `dashboard.html`. Writes the internal and shareable copies, each as a standalone file, as a page fragment for publishing and as a CSV; removes the internal-only section from the shareable copy and asserts it carries no internal-only field, CRM note or record ID. Contact emails are shown in full only in the internal standalone file; every other output masks them, and the build asserts the exact masked count. |

```bash
# book.json (see pipeline/book.example.json) holds everything that names an account; it lives with the data
python3 pipeline/build_inputs.py <builtwith.csv> <apollo_accounts.csv> <build>/book.json <build>/accounts_input.json
#   with a detect export, Store Leads and the live check:
#   python3 pipeline/live_check.py <hosts.txt> <build>/live.json
#   python3 pipeline/build_inputs.py <detect.zip> <apollo_accounts.csv> <build>/book.json <build>/accounts_input.json \
#       --storeleads <domains_export.csv> --live <build>/live.json
python3 pipeline/triage.py <build> [<build>/book.json]
python3 pipeline/make_batches.py <build> <build>/book.json [prior_review.json]
# research agents write <build>/results/batch_NN.json; check each with validate_batch.py <build> batch_NN
python3 pipeline/score.py <build> <apollo_accounts.csv> <build>/book.json <build>/scored.json
python3 pipeline/make_verify.py <build> <build>/scored.json [max_accounts_per_verifier]
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

## Ranking the Heartbeat way

The triangle score and its tiers are the research layer. The ranking a seller sees is the Heartbeat score, and its
model lives in the Heartbeat Source, not here: `tools/rescore.py`, `tools/icp.py` and `tools/potential.py` there are
the only place a Heartbeat score is computed. This pipeline prepares the one input that can be read off the scans,
hands the book over, and shows the result.

| Step | Script | What it does |
|---|---|---|
| H0 | `browser_scan.js` (optional, recommended) | Loads each store in a real browser, runs a search through the page's own search box, and records which vendors the page calls. A bot wall or a failed load is recorded as not read. An export can keep listing a tool after a store has stopped using it; this is the scan that says what a shopper's browser talks to today. |
| H1 | `partner_facts.py` | For every storefront: which technology partners and which of their rivals run on it, from the BuiltWith detect export (first and last detected), Store Leads, the live check and the browser scan. Who is a partner is read from the partner registry (the Golden Triangle Console's export). A tool counts as live after 60 days of history and when seen in the last 75 days, or when a second scan shows it. Only the store's own site counts. The export is checked against the browser vendor by vendor: where the browser confirmed fewer than half of a vendor's listings (five or more tested), a listing of that vendor resting on the export alone is "not confirmed" and not counted. `--confirmed` adds facts research read first-hand. |
| H2 | research agents | Per company (one buying centre): its entry in Anatta's ICP model, its potential (online sales, company-run stores, transactional stores, share), the Shop Pay fit, the subscription signal, and two judgment inputs for partner motion: dated events and whether a subscription tool has a play. Evidence rules are the Heartbeat Source's. |
| H3 | `partner_moves.py` | Writes each company's partner moves from the facts, by the rules of the playbook's "Why a partner moves", in the shape the Heartbeat Source keeps (`book_extras.json`). A corporate site, a row with no store and a store someone else operates are not the company's stores. |
| H4 | Heartbeat Source `tools/extract_book.py`, `tools/rescore.py` | Run unchanged: the first reads the book out of the triangulation page, the second scores and ranks it. |
| H5 | `assemble.py --heartbeat` | Joins the ranking to the book. The page then leads with the Heartbeat ranking and keeps the triangulation underneath; the CSVs gain the Heartbeat columns. The build asserts that every score recomputes from its four measures and that the ranking and the book list the same companies. |

```bash
node pipeline/browser_scan.js <stores.json> <build>/browser.json [concurrency]      # stores.json: [{"name": ..., "domain": ...}]
python3 pipeline/partner_facts.py <detect.zip> <build>/accounts_input.json <partner_registry.json> <build>/partner_facts.json \
    --live <build>/live.json --browser <build>/browser.json [--confirmed <confirmed.json>] [--store-domains <map.json>]
# in a copy of the Heartbeat Source, with HB_SELLER=<seller>:
python3 tools/extract_book.py <out>/<slug>-internal.html <seller>
# research writes data/<seller>/icp.json, potential.json and research.json
python3 pipeline/partner_moves.py data/<seller>/book.json <build>/partner_facts.json <partner_registry.json> data/<seller>/research.json \
    data/<seller>/book_extras.json --month "November 2026"
python3 tools/rescore.py issues/<issue>.json
python3 pipeline/assemble.py <build>/scored.json <out> --heartbeat data/<seller>/rescored.json --potential data/<seller>/potential.json \
    --heartbeat-extras data/<seller>/book_extras.json --heartbeat-notes <notes.json>
```

The Heartbeat score has no measure for how hard a platform is to leave, so the page shows the triangulation's
"hard to move" mark beside a rank as context. It never changes the rank.

### The second look, the insight layer and release QA

A ranking is only as good as its weakest input, and the subscription bonus is the largest single input a company can
carry (a flat 10). So before a ranking is released it gets a second round, subscription first:

| Step | Script | What it does |
|---|---|---|
| H6 | `subscription_scan.js` | Looks for recurring purchase at every store in a real browser: links that read like a program, the addresses programs usually live at, the sitemap, the store's own search for "subscription", Shopify selling plans, the three most promising pages, and every subscription engine the store calls. It reports leads with the words found, not verdicts: "subscribe" is also what a newsletter box says. A blocked store is "not read", never "no program". |
| H7 | research agents, with `read_page.js` | A second look per company: settle recurring purchase first-hand, program by program (store, terms, renewal, the engine that runs it, the page and date it was read), resolve the weak inputs the first round left (store-count floors, conflicting estimates, unverified events) from sources, and write the lines a seller reads. `read_page.js` reads one page in a real browser for stores that refuse a plain fetch. What counts as recurring purchase is the Heartbeat Source's rule; a rental, a free loyalty program and another company's subscription sold on the store are recorded and do not count. |
| H8 | `assemble.py --heartbeat-insights insights.json --proof <Heartbeat Source>/shared/anatta.json` | Adds the insight layer: findings counted from the ranked list, the one-line read on every ranked row, the why, play, watch, fit, move and three proof stories on a record, and the subscription view (every program with its terms, engine and source, in rank order). Proof totals stay `{proof.x}` tokens in the data and are filled on the page, so a total cannot go stale. |
| H9 | `qa.py` (with `qa_page.js`) | Release QA, after the Heartbeat Source's own `tools/qa.py`. Data: every Heartbeat number is recomputed from the inputs (fit from the ICP entry, potential from the research, timing with the Shop Pay lift, partner motion from the moves, the bonus, the score, the order); every partner a move calls live is live in the partner facts; every proof number traces to its client's Proof Genome entry and no unpublished client is named unless `naming.json` clears it; the two editions and the two CSVs agree; no email address, deal size, CRM record id or outside script is in a file. Page: both editions at 390x844 and 1440x900, no script errors, nothing wider than the screen, the ranking in score order, every ranked company opens with its score, links open safely, and the Heartbeat wording rules hold everywhere the Heartbeat layer shows. Exit code 1 on any failure. |

`insights.json` is `{"intro": ..., "findings": [{"k", "unit", "title", "text", "accounts"}], "accounts": {company: {"read", "next", "why", "play",
"watch", "q", "fitt", "leadt", "stories"}}, "subscriptions": {"intro", "note", "rows": [{"group", "state", "note", "programs": [...]}]}}`.
The build joins each subscription row to its rank and stops if the view and the bonus disagree.

**House wording.** `assemble.py` applies the Heartbeat wording rules to every research note a reader can see: an email
address is masked to its domain, an em dash becomes a comma, "AE" becomes "seller", and BuiltWith's Agency field is
left out. `--scrub scrub.json` adds a book's own list, for the name of a firm that builds for an account: it is never
shown, and the source link stays. The Heartbeat inputs are held to the rules at the source: the build stops if any of
them would need rewording. The triangulation template itself calls the account list "the book"; QA counts that phrase
in the triangulation layer and fails it in the Heartbeat layer and the navigation.

```bash
node pipeline/subscription_scan.js <stores.json> <build>/sub_scan.json [concurrency]   # stores.json: [{"name", "domain", "groups": [company]}]
node pipeline/read_page.js <url> --find "subscri|auto.?(ship|deliver|replen|renew)|member"   # one page, as a browser sees it
python3 pipeline/assemble.py <build>/scored.json <out> --heartbeat ... --heartbeat-insights <insights.json> \
    --proof <Heartbeat Source>/shared/anatta.json [--scrub <scrub.json>] [--title "..."] [--label "..."] [--slug ...]
python3 pipeline/qa.py --internal <out>/<slug>-internal.html --shareable <out>/<slug>-shareable.html \
    --source <Heartbeat Source> --seller <seller> --issue <Heartbeat Source>/issues/<issue>.json \
    --facts <build>/partner_facts.json --csv-internal <out>/<slug>-accounts-internal.csv --csv-shareable <out>/<slug>-accounts-shareable.csv \
    --ids-from <the CRM export>.csv [--scrub <scrub.json>]
```

## Scoring in one paragraph

Shopify fit = platform whitespace 25 + commerce scale 20 + business-model fit 20 + unified-commerce surface 15 +
timing 10 + ecosystem pull 10, plus explicit penalties, clamped 0–100. Anatta fit = brand/storefront surface 20 +
modernisation need 20 + scale for a retainer 20 + LTV/subscription complexity 20 + FIRE intent 20 (computed
straight from the export). Triangle = round(0.55 × Shopify + 0.45 × Anatta + small intent bonuses). T1 needs
triangle ≥ 62 and Shopify fit ≥ 63; T2 ≥ 48; T3 ≥ 36; T4 otherwise. Gates: Shopify Plus already live → EXP;
government, distress, no commerce surface (only when Shopify fit < 20), bad record, restricted → X.

Where a verifier suggests a different fit, the final fit is the average of the research figure and the verifier's.
That is deliberately conservative, and it can leave a row in a tier the verifier would not have given it. `score.py`
therefore records two more views of every verified row (`second_look`): the tier before the second look, which is
what the verifiers' notes were written against, and the tier on the verifiers' own figures. The page says both on
the record and tags a row "second look: T2" when the second view differs from the tier shown; the CSV carries it as
`second_look_would_be`.

## Groups and families

`groups` in `book.json` are rows that share one decision: one conversation covers all of them. `families` are rows
that share an owner but buy separately (a holding company's subsidiaries, a licensor's brands). Both are context:
every row is scored on its own storefront. Where a sister row already runs Shopify, the record says so and the page
lists it under "Where Shopify is already inside"; it is never part of the score.

## What was specific to the second book

- **Three reads on every storefront.** See "platform read" above. Store Leads' sales figure is a model estimate and
  was used as an order of magnitude only; scale is scored from public revenue, store counts and headcount.
- **Two lists, 22 domain differences.** Where several Apollo rows share one website and the book gives each its own,
  `account_domain` in `book.json` maps them by account name. Apollo matched two rows to a different company from the
  one the book lists; their FIRE fields are shown as exported and not scored.
- **Owners.** Most of the book is holding companies, brand groups and the companies they own, so `families` carries
  the ownership and `groups` only the rows that share one decision. Research corrected several of Apollo's parent
  fields (ownership had changed during 2025 and 2026), and both lists were redrawn from what it sourced.
- **Caps.** The cap from the October build (whitespace 15 of 25) is applied in two cases, each with the researcher's
  sourced reason: an in-house platform at national scale, and a platform that went live within about two years.
  A roll-out still in progress counts for every row that shares the decision.
- **Hard to move.** On a book of national retailers an account can clear both bars on scale and signal alone, cap
  included. The tiers are unchanged; the overview counts the companies with an uncapped golden row as the ones to
  walk into, and lists the rest apart with the reason and the play that is left.
- **Old signal.** The newest FIRE signal is 57 days older than the exports. Researchers and verifiers treated a FIRE
  signal or an In-market flag as soft unless public evidence backed it.
- **No contacts export**, so no hub map and no named people.

## What was specific to CT's book

- **Its two book-specific sentences** now come from `book.json`: `lede_note` ("Most of those are manufacturers,
  distributors and processors with no storefront to move.") and `method_notes` (the CRuX note below). Add both to
  regenerate that book's page word for word.
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
- **An account we no longer pursue.** `not_pursued` in `book.json` names it with the reason. It is our decision, not
  a judgment on fit: the row keeps its scores for the record, moves to tier X, and is not counted in the tiers, the
  plays or the top-tier people on the hub map. It is applied last, so no score or verifier verdict can undo it.
- **Internal vs shareable.** The internal copy shows which accounts are in Salesforce and a section on how far to
  trust our own signal. The shareable copy drops both from the data and the page, along with notes that correct our
  own earlier review of the book.
- **Contacts under the wrong company.** The people Apollo exported under the misattributed account belong to other
  companies of the same name, so they are left out and counted (`contacts_wrong_company` in `book.json`). Four
  company names in the contacts export needed a manual match to an account row (`contact_company_alias`).
- **Emails.** Full addresses appear only in the internal standalone file. The shareable copy and both published
  page fragments show first initial and domain.
