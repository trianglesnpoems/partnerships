# Shopify Theme Detection

Enriches an Apollo accounts export CSV with the live Shopify theme for each account's website.

## Method (near-100% for Shopify storefronts)

Every Liquid-rendered Shopify storefront embeds a JavaScript object in its HTML:

```js
Shopify.theme = {"name":"Impulse v7.2","id":123456789,"schema_name":"Impulse","schema_version":"7.2.0","theme_store_id":283,"role":"main"}
```

This is first-party data from the store itself, not an inference:

- **`schema_name`** — the base theme's true name from the theme's own `schema.json` (authoritative).
- **`theme_store_id`** — the official Shopify Theme Store catalog id; `null` means a fully custom/bespoke theme.
- **`name`** — the merchant's label for the live theme (often includes version).

Fallback chain, in order:
1. Homepage fetch (desktop UA, then mobile UA; `www`/apex variants; gzip; redirects).
2. Password/401/403 pages are still Liquid-rendered — the theme object is parsed from error bodies too.
3. `/collections/all` probe when the homepage is a non-Liquid lander.
4. Headless detection: Hydrogen/Oxygen markers → "Headless — no Liquid theme" (there is genuinely no theme to name).
5. Generic Shopify fingerprints (`X-ShopId` header, `cdn.shopify.com`, `/cdn/shop/` assets) → Shopify confirmed, theme undetermined.
6. No fingerprints → "Not Shopify" with a platform hint (SFCC, Magento, Next.js, etc.).

Each row gets a confidence level (High / Medium / None) and the exact method + evidence used, so nothing is silently guessed.

## Usage

```bash
python3 theme_detect.py <input.csv> <output.csv>
# optional 3rd arg: comma-separated domain filter for a pilot run
python3 theme_detect.py input.csv pilot.csv "www.huel.com,www.brooklinen.com"
```

- Python 3.8+, stdlib only (no pip installs).
- Assumes the input CSV's second column is `Website`. All original columns are preserved; eight columns are appended:
  `Shopify Detected (Live)`, `Theme Name (Store Label)`, `Theme Base (Schema)`, `Theme Store ID`, `Theme Store Name`, `Theme Detection Confidence`, `Theme Detection Method`, `Theme Detection Notes`.
- Deduplicates by domain (fetches each domain once), runs 16 fetches in parallel; ~190 domains complete in a couple of minutes.
- Behind a TLS-intercepting proxy, set `THEME_DETECT_CA_BUNDLE=/path/to/ca.pem`.

## Note on Claude Code remote sessions

This session's network egress policy blocks outbound requests to arbitrary storefront domains, so the sweep must run either (a) in a Claude Code environment whose network policy allows all domains (claude.ai/code → environment settings → network policy), or (b) locally with the command above.
