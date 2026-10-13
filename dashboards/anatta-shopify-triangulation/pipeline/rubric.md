# Anatta × Shopify — account fit rubrics (Oct 2026)

Context. Anatta (anatta.io) is a Shopify Platinum Partner systems integrator that builds and optimises high-performance
Shopify Plus and headless (Hydrogen) storefronts for DTC and omnichannel brands on a retainer model (clients: Rothy's,
AG1, Dollar Shave Club, Mack Weldon, Molekule). The partner is Shopify's enterprise/Plus sales organisation (our contact:
an account executive). A "triangle" account is one where Shopify has a real reason to want the merchant on Shopify
(or deeper on Shopify) AND Anatta has a real services engagement to deliver — so the two sides can make one warm,
coherent approach instead of two cold ones.

Score every account on BOTH legs. Use web search for evidence (company site, press, LinkedIn, store locators,
funding/ownership, BuiltWith-style stack confirmations). "No meaningful evidence found" is an acceptable,
score-suppressing answer — lower the subscore AND confidence; never invent. Be sceptical of the BuiltWith row: it is
a signal, not truth (e.g. an empty "eCommerce Platform" may mean a custom build, a headless storefront, a separate
shop subdomain, or genuinely no online store). Confirm what the storefront actually runs on.

## Leg 1 — SHOPIFY FIT (100 points, then penalties)

1. Platform whitespace (25). How much Shopify has to gain from this merchant moving or expanding.
   - 22–25: legacy enterprise platform with a real online store — Salesforce Commerce Cloud/Demandware, Adobe Commerce/Magento, Oracle Commerce/ATG, SAP Hybris, VTEX, HCL, Amplience, or a bespoke/custom build.
   - 15–21: mid-market or open-source stack — BigCommerce, WooCommerce, CS-Cart, VirtueMart, Zoho, EvolutionX, or a Wix/Squarespace store that has clearly outgrown it.
   - 10–18: no detectable online store but an obvious need — a retailer/brand with physical stores, wholesale or a catalogue that should transact online (score by how obvious and how large the gap is).
   - 8–12: already on Shopify (non-Plus) — the play is a Plus/Enterprise upgrade or POS/B2B/Markets expansion.
   - 0–6: no commerce surface at all (pure services, government, media, education, a dealership that only lists inventory).
   - Already on Shopify Plus: score 0 here and set gate = "already_plus" (it becomes the expansion/reference tier, not a prospect).
2. Commerce scale (20). Online revenue/GMV, web traffic (CRuX: Top 100k ≈ 17–20; Top 500k ≈ 13–17; Top 1m ≈ 10–13; Top 5m ≈ 6–10; Top 10m ≈ 3–6; Top 50m ≈ 0–3 — adjust with revenue/store-count evidence), store count, headcount, company revenue. Shopify Plus starts making sense around $1M+ online; Enterprise at $50M+ total revenue.
3. Business-model fit (20). Consumer product brand, specialty retailer, multi-location retailer or grocer with online shopping = 15–20. Distributor/manufacturer with a real wholesale catalogue (Shopify B2B) = 10–15. Restaurant/hospitality/franchise (gift cards, merch, online ordering) = 5–10. Services (salons, fitness, dental, remodelling, repair, car dealers) = 2–7. Universities, government, nonprofits, media, trade associations = 0–4. Direct-selling/MLM = 3–6 (comp-plan platforms dominate).
4. Unified-commerce surface (15). Count the channels Shopify would unify: physical stores (POS), wholesale/B2B, international markets, multiple brands/storefronts, marketplaces, subscriptions. None = 0–3; one = 5–8; two = 9–12; three or more = 13–15.
5. Timing & intent (10). Live FIRE signals (explicit "Intent: Shopify", Replatform, Agency Search), In-market flag, a new agency detected, leadership change (new CDO/CMO/CIO/head of ecommerce), recent funding or acquisition, a platform end-of-life or announced replatform, recent modernisation of the marketing stack. Nothing = 0–2; one soft signal = 3–5; a hard signal = 6–8; hard signal plus in-market = 9–10.
6. Ecosystem pull (10). Stack already speaks Shopify's ecosystem (Klaviyo, Yotpo, Recharge, Gorgias, Okendo, Shop Pay, Global-e, Affirm/Klarna, Attentive) = 7–10. Neutral stack = 4–6. Deeply welded to Salesforce/Oracle/SAP suites, or ERP-driven custom commerce = 0–3.

Penalties (subtract; state the reason):
- Government / military / public sector: −40 → gate "gov".
- Financial distress, insolvency, wound down, acquired and absorbed into a parent's store: −30 → gate "distress".
- Not a merchant at all (technology vendor, support portal, news/media, trade association, university): −20 to −30 → gate "non_merchant" if the Shopify score ends below 20.
- Bad/placeholder record (person's name as company, a news domain standing in for a brand, a duplicate): −40 → gate "bad_record".
- Services-only with no product catalogue: −15. Direct-selling/MLM: −10. Regulated category Shopify restricts or complicates (firearms/ammo, tobacco/vape, cannabis outside legal Canadian/US-state frameworks): −10 to −25 → gate "restricted" only if Shopify cannot host it at all.

## Leg 2 — ANATTA FIT (80 research points; a 20-point intent subscore is added by code from the FIRE fields — do NOT score intent here)

1. Consumer brand & storefront surface (20). A brand or retailer that owns a product catalogue and a storefront Anatta would build/optimise. Retailer with stores + online = 15–20. Wholesale-first with a growing DTC line = 8–14. Restaurants/services/gov/edu/media = 0–5.
2. Storefront modernisation need (20). Legacy or underperforming platform, dated theme, poor mobile performance, no headless/composable path, obvious conversion problems, an agency gap. A dated Shopify Plus store still scores (Anatta runs CRO/optimisation retainers): 8–14. A modern, well-run store = 2–6.
3. Scale to sustain a retainer (20). Anatta's engagements suit brands with roughly $20M+ revenue or $2M+ online, a real marketing/ecommerce team (the contact list helps here), multi-location or multi-brand complexity. Tiny single-location businesses = 0–5.
4. LTV & subscription complexity (20). Subscription, replenishment, memberships, loyalty, bundles, gifting calendars — the levers Anatta optimises. Pure one-off purchases with no repeat mechanic = 3–8.

## Gates (override the score; always give a plain-English reason)
- already_plus — BuiltWith or your research shows Shopify Plus live: expansion/reference, not a prospect.
- gov — government or military.
- distress — insolvency / shut down / absorbed.
- non_merchant — no plausible commerce surface (tech vendor, media, university, association) when Shopify fit < 20.
- bad_record — not a real account record.
- restricted — Shopify cannot host the category.
Leave gate empty for everything else, including weak accounts (they tier as T4 Watch, which is still information).

## What to write
- story: 2–3 sentences, the actual pitch — why this account, why now, what the joint angle is. Not a description of the company.
- shopify_angle: what Shopify leads with (replatform from X, Plus upgrade, POS unification across N stores, B2B catalogue, Markets/international, Hydrogen headless).
- anatta_angle: what Anatta leads with (migration/build, headless, CRO/subscription optimisation, retainer scope).
- flags: anything a human must know before calling (parent-company procurement, franchise structure, distress, contract timing, that the BuiltWith row looks stale, etc.).
- evidence: 3–6 claims each with the URL you found it at. Confidence high only when platform, scale and model are all sourced.
