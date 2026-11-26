# Golden Triangle Console: readout

*Reviewed 2026-11-26 against the live artifact (data built 2026-08-26, refreshed 2026-09-09).*

## The short version

The console answers one question for a Shopify AE book: **which accounts can we actually get into, through whom, and where are the people?**

It scores 308 accounts (222 corporate families) on three legs and calls an account a *golden triangle* when all three hold:

| Leg | Meaning | Source |
|---|---|---|
| **Shopify heat** | The account is a priority for Shopify now | FIRE score, intent, in-market flags from the AE book |
| **Partner door** | A co-sell partner is already live in the brand's stack and can make a warm intro | Tech-stack detections, classified against a partner registry |
| **Mapped committee** | Real buyers are identified and located | 3,764 contacts across 180 metro hubs |

Twelve accounts clear all three. The rest are tiered so the team knows what is missing on each.

## What it does

A single-page app with seven views:

| View | What you get |
|---|---|
| **Overview** | KPIs, tier distribution, fit × door scatter, doors by partner, opportunity angles, research alerts, per-AE rollup, full methodology |
| **Hub Map** | North America map of contacts by metro, overlaid with H2 event cities; click a hub for its accounts and people |
| **Accounts** | Sortable table with a rule-based filter builder (34 fields, ALL/ANY) and 9 presets |
| **Partners** | Per-partner rollup of live accounts, plus every detected tech across the book |
| **Play Builder** | Pick a moment (event, metro, region), a door partner, and accounts; it assembles the invite list, room, venue and a copy/print play sheet. One-click variants: auto-build, sports, subscription, displacement, better-together |
| **Calendar** | H2 2026 industry events and sports moments |
| **Deep dives** | Evidence-level stack teardowns and entry strategy for 12 accounts |

Every account opens a side panel with its score breakdown, stack, doors, committee by lens, flags and research snapshot.

## The problems it solves

| Problem | How the console handles it |
|---|---|
| Partner co-sell is run on anecdote: "who do we both know?" | Every partner overlap is computed, counted and ranked |
| AE priority, partner presence and contacts live in three separate files | Joined into one record per account |
| A hot account with no way in looks identical to one with a warm path | Door strength is half the score; T1 requires a real A-tier door |
| Subscription platforms and stale pipeline tags get mistaken for access | Tracked as intel and explicitly excluded from scoring |
| Sibling brands inflate counts and create unsafe intros | Families counted once at their best member; six unsafe sibling paths suppressed |
| Event planning starts from a blank page | Play Builder produces a targeted room and a shareable sheet in minutes |
| Source data is wrong in ways nobody sees | A data-health section states coverage gaps; a family audit found and corrected 26 workbook errors |

## How scoring works

```
triangle = 0.55 × shopify_fit + 0.45 × door_strength + bonuses   (cap 100)
```

- **Shopify fit**: the FIRE score as given. Where missing, Opp Tier stands in and the account is flagged.
- **Door strength**: first A-tier door 40 points, each additional A door +15, B doors +8, single-source detections discounted ×0.8.
- **Bonuses**: in-market, intent, signal recency, committee completeness, Shopify products already in the stack.
- **T1** needs triangle ≥ 62, an A-door, at least 3 mapped contacts, and a live heat signal. T2 ≥ 48, T3 ≥ 36, T4 below. Accounts already on Shopify sit in a separate Expand lane.

Current distribution by account: T1 12 · T2 47 · T3 58 · T4 153 · Expand 38.

## What it takes to build

**Inputs**

1. AE tech-stack workbook: accounts, FIRE and intent signals, platform, detected stack by category.
2. Buying-committee contact export (Apollo): name, title, city, email.
3. Partner registry: 324 technologies classified by role (door, co-sell, incumbent, subscription, integration, neutral) and door tier.
4. Partner events guide and attendee target lists; a sports calendar; a venue shortlist.

**Pipeline**

1. Clean and join: normalize account names, merge case variants, match contacts to accounts by company and domain.
2. Resolve families: group brands under their CRM parent, then audit the groupings.
3. Classify the stack: map each detected tech to the registry to find doors.
4. Enrich contacts: assign function lens, seniority, key-stakeholder flag, metro hub and coordinates.
5. Score and tier, keeping the reasons on each account.
6. Research sweep: open-web check of ownership, platform and retail footprint for all 308 accounts, fact-checked; 188 produced a material alert.
7. Deep dives on selected accounts.
8. Emit one JSON payload and inline it into the page.

**Front end**

One self-contained HTML file, about 4 MB, of which 3.6 MB is data. Roughly 2,300 lines of vanilla JavaScript, hand-drawn SVG charts and map, no framework, no backend, no build step. State lives in the browser.

**Where the effort goes**

Most of it is steps 1 to 3 and 6. Entity resolution, the partner registry and the research sweep are judgment-heavy and are what make the output trustworthy. The scoring is a few dozen lines. The UI is the visible part, and the Play Builder is the bulk of it.

**To repeat it for a new book**: the registry and UI carry over. The join, family audit and research are redone per book. The `triangulation-dashboard` skill packages this method.

## Review: what holds up and what to fix

**Holds up**

- The methodology is fully disclosed and every score is explainable on the account.
- The door doctrine (subscription platform ≠ access, pipeline tag ≠ door) prevents the most common overcounting.
- Data limits are stated in the product rather than hidden.

**Fix or flag**

| # | Issue | Why it matters |
|---|---|---|
| 1 | **The data is 11 weeks old.** | "Signal in last 7 days" bonuses and in-market flags reflect early September. Most of the 22 H2 events have passed. Tiers should not be trusted for current outreach without a refresh. |
| 2 | **No source of record.** | The console exists only as a published artifact. The build pipeline and source data are not in this repo, so a refresh depends on re-deriving the process. |
| 3 | **Contact emails are unmasked in the page.** | 3,764 people's details travel with any share of the link. Keep it private or ship a masked variant. |
| 4 | **FIRE covers 130 of 308 accounts.** | 58% of fit scores are proxies or a baseline. |
| 5 | **Platform is "Unknown" for 93 accounts.** | Replatform angle and motion labels are weakest exactly where coverage is thin. |
| 6 | **Weights are hand-set.** | 0.55 / 0.45 and the tier cut-offs have not been checked against meetings booked or pipeline created. |
| 7 | **Half the book is T4.** | 153 accounts get little from the tool beyond "watch." |
| 8 | **Source workbook still carries the 26 audited errors.** | The console corrects them downstream; the next export will reintroduce them. |
| 9 | **Feature weight.** | Seven views and five play types is a lot for a tool whose core output is a list of 12. |

## Recommended next steps

1. Refresh the data and roll the calendar to H1 2027 before the console is used again.
2. Move the pipeline and a masked data sample into this repo so a refresh is a rerun.
3. Record outcomes on the 12 T1 accounts and use them to test the weights.
4. Fix the source workbook so corrections stop living only in the console.
