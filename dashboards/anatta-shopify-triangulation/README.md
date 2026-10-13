# Anatta × Shopify — partner triangulation dashboard (Oct 2026)

Scores every account in the Apollo book against two ICPs — Shopify's enterprise/Plus sales motion and
Anatta's services motion — blends them into a triangle score, tiers them, and maps every contact into
metro hubs. Built for the Shopify account sync with Nicole Smelzer.

The deliverable is a single self-contained HTML file (three views: Overview, Account Dashboard, Hub Map)
produced in two variants: a shareable copy with masked emails and an internal copy with full emails.
Data files and the generated HTML are **not** committed here because they contain contact PII; they are
delivered directly to the team. Everything needed to regenerate them is in `pipeline/`.

## Pipeline (run in this order)

| Step | Script | What it does |
|---|---|---|
| 1 | `build_inputs.py` | Joins the Apollo accounts export, the BuiltWith technology export and all contact exports (deduped on email → LinkedIn URL → name+company) into one research input per account. Adds companies that appear only in contact exports. |
| 2 | `triage.py` | Rule-based triage of obvious non-fits (government, universities, dealerships, placeholder records, zero-contact long tail) so agent time goes to accounts that could matter. |
| 3 | `wf_research.js` | Workflow script: batch research agents score both legs per `rubric.md` with sourced web evidence; adversarial verifiers challenge provisional T1 (two lenses), T2 (one lens) and gated-but-engaged accounts. |
| 4 | `score.py` | **Single source of truth** for every number: merges research + triage + verifier verdicts, computes Shopify fit, Anatta fit (with the deterministic FIRE intent subscore), triangle, gates and tiers. |
| 5 | `build_hubs2.py` | Geocodes contacts (GeoNames cities15000 → cities1000 → override table) and clusters them into 120 km hubs with nearest-seed assignment; worldwide, with region tags. |
| 6 | `assemble2.py` | Embeds the scored book, hubs, contacts, D3/TopoJSON and pruned Natural Earth boundaries into `dashboard.html`; asserts the masked build leaks no raw email. |

## Scoring in one paragraph

Shopify fit = platform whitespace 25 + commerce scale 20 + business-model fit 20 + unified-commerce surface 15 +
timing 10 + ecosystem pull 10, plus explicit penalties, clamped 0–100. Anatta fit = brand/storefront surface 20 +
modernisation need 20 + scale for a retainer 20 + LTV/subscription complexity 20 + FIRE intent 20 (computed
straight from the export). Triangle = round(0.55 × Shopify + 0.45 × Anatta + small intent bonuses). T1 needs
triangle ≥ 62 and Shopify fit ≥ 63; T2 ≥ 48; T3 ≥ 36; T4 otherwise. Gates: Shopify Plus already live → EXP;
government, distress, no commerce surface (only when Shopify fit < 20), bad record, restricted → X.
