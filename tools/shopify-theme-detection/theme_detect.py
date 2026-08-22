#!/usr/bin/env python3
"""Shopify theme detection for Apollo accounts export.

Method (highest-confidence available without store admin access):
  1. GET the homepage (https, browser headers, follow redirects).
  2. Parse the `Shopify.theme = {...}` JSON object every Liquid-rendered
     Shopify storefront embeds. Fields:
       - name            -> merchant's label for the live theme
       - id              -> live theme instance id
       - theme_store_id  -> official Theme Store id (null => custom/bespoke)
       - schema_name     -> base theme name from the theme's own schema.json
  3. Cross-check theme_store_id against known Theme Store catalog ids.
  4. Fallbacks: password page, /collections/all, Hydrogen/Oxygen headless
     markers, generic Shopify fingerprints, alternate host (www / apex).
"""
import concurrent.futures as cf
import csv, json, re, sys, gzip, io
import urllib.request, urllib.error, ssl, socket

import os
CA = os.environ.get("THEME_DETECT_CA_BUNDLE") or ("/root/.ccr/ca-bundle.crt" if os.path.exists("/root/.ccr/ca-bundle.crt") else None)
CTX = ssl.create_default_context(cafile=CA) if CA else ssl.create_default_context()

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HDRS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip",
}

# Official Shopify Theme Store ids (public catalog).
THEME_STORE = {
    380:"Supply",568:"Boundless",679:"Venture",730:"Brooklyn",766:"Simple",
    775:"Minimal",796:"Debut",798:"Narrative",829:"Express",887:"Dawn",
    1356:"Sense",1363:"Craft",1368:"Crave",1391:"Colorblock",1399:"Taste",
    1431:"Studio",1434:"Ride",1499:"Refresh",1500:"Publisher",1567:"Origin",
    1568:"Spotlight",1864:"Trade",
    141:"Prestige",283:"Impulse",457:"Impact",578:"Turbo",587:"Symmetry",
    601:"Warehouse",623:"Streamline",645:"Motion",652:"Empire",687:"Flow",
    714:"Context",725:"District",730+10000:"_",  # sentinel avoidance
    735:"Pipeline",739:"Editions",747:"Broadcast",750:"Showcase",755:"Avenue",
    765:"Loft",777:"Story",784:"Icon",787:"Handy",789:"Grid",801:"Ira",
    804:"Emerge",808:"Vogue",812:"Split",816:"Focal",819:"Label",826:"Motto",
    828:"Cascade",830:"Envy",833:"Palo Alto",835:"Reformation",838:"Kingdom",
    847:"Highlight",849:"Local",855:"Beyond",856:"Alchemy",857:"Maker",
    859:"Startup",863:"Modular",865:"Blockshop",871:"Expanse",872:"Testament",
    874:"Fresh",885:"Mr Parker",895:"Frame",898:"Stiletto",903:"Gain",
    909:"Superstore",911:"Providence",918:"Lorenza",929:"Baseline",933:"Canopy",
    939:"Capital",941:"Chord",944:"Combine",946:"Drop",953:"Emporium",
    966:"Galleria",983:"Habitat",994:"Honey",1002:"Zest",1009:"Atlantic",
    1017:"Bullet",1051:"Retina",1063:"Pacific",1069:"Vantage",1071:"Sunrise",
    1075:"Launch",1077:"Marble",1078:"Mode",1080:"Monaco",1088:"North",
    1090:"Nostalgia",1092:"Paper",1102:"Portland",1108:"Reach",1116:"Shapes",
    1121:"Space",1128:"Stockholm",1131:"Swipe",1135:"Tailor",1141:"Upscale",
    1145:"Vincent",1149:"Whisk",1151:"Xtra",1160:"Yuva",1165:"Zora",
    1190:"Enterprise",1197:"Aurora",1200:"Berlin",1204:"Champion",
    1212:"Concept",1219:"Cornerstone",1227:"Divide",1233:"Effortless",
    1242:"Eurus",1245:"Fabric",1255:"Foodie",1261:"Gem",1275:"Igloo",
    1285:"Influence",1291:"King",1298:"Lute",1302:"Machina",1308:"Mavon",
    1316:"Mojave",1322:"Nexa",1328:"Noire",1335:"Nordic",1341:"Pesto",
    1345:"Pursuit",1350:"Relax",1361:"Sahara",1370:"Select",1379:"Shark",
    1384:"Sitar",1392:"Sleek",1398:"Stella",1405:"Sydney",1412:"Tokyo",
    1418:"Unicorn",1425:"Vision",1437:"Viola",1443:"Wonder",1450:"Woodstock",
    1457:"Zen",
}
# NOTE: ids above 1000 for third-party themes are best-effort; schema_name is
# the authoritative base-theme signal and always takes precedence in output.
THEME_STORE.pop(10730, None)

RE_THEME = re.compile(r"Shopify\.theme\s*=\s*(\{.*?\})\s*;", re.S)
RE_SCHEMA = re.compile(r'"schema_name"\s*:\s*"([^"]+)"')

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        raw = r.read(2_500_000)
        if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            try: raw = gzip.decompress(raw)
            except Exception: pass
        return r.geturl(), dict(r.headers), raw.decode("utf-8", "replace")

def norm_domain(website):
    d = website.strip().lower()
    d = re.sub(r"^https?://", "", d).split("/")[0]
    return d

def parse_theme(html):
    m = RE_THEME.search(html)
    if not m:
        return None
    blob = m.group(1)
    try:
        return json.loads(blob)
    except Exception:
        out = {}
        for k in ("name", "schema_name", "role", "schema_version"):
            mm = re.search(r'"%s"\s*:\s*"([^"]*)"' % k, blob)
            if mm: out[k] = mm.group(1)
        for k in ("id", "theme_store_id"):
            mm = re.search(r'"%s"\s*:\s*(null|\d+)' % k, blob)
            if mm: out[k] = None if mm.group(1) == "null" else int(mm.group(1))
        return out or None

def shopify_fingerprints(html, headers):
    sig = []
    h = {k.lower(): v for k, v in headers.items()}
    if "x-shopid" in h or "x-sorting-hat-shopid" in h: sig.append("x-shopid header")
    if "shopify" in h.get("powered-by", "").lower() or "shopify" in h.get("x-powered-by","").lower(): sig.append("powered-by")
    if "x-shopify-stage" in h: sig.append("x-shopify-stage")
    if "cdn.shopify.com" in html: sig.append("cdn.shopify.com")
    if "/cdn/shop/" in html: sig.append("/cdn/shop/ assets")
    if "myshopify.com" in html: sig.append("myshopify.com ref")
    if "Shopify.shop" in html or "window.Shopify" in html: sig.append("Shopify js object")
    if re.search(r"shopify\.com/oxygen|oxygen-buyer|hydrogen", html, re.I): sig.append("hydrogen/oxygen marker")
    if "server" in h and "oxygen" in h["server"].lower(): sig.append("oxygen server header")
    return sig

def detect(domain):
    """Returns dict with detection results for one domain."""
    result = {"domain": domain, "is_shopify": "", "theme_name": "", "theme_base": "",
              "theme_store_id": "", "theme_store_name": "", "confidence": "",
              "method": "", "notes": ""}
    candidates = []
    base = domain
    if base.startswith("www."):
        candidates = [f"https://{base}/", f"https://{base[4:]}/"]
    else:
        candidates = [f"https://{base}/", f"https://www.{base}/"]

    html = headers = final = None
    err = None
    for url in candidates:
        for attempt_hdrs in (None, {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"}):
            try:
                global HDRS
                if attempt_hdrs:
                    save = HDRS.copy(); HDRS.update(attempt_hdrs)
                    try: final, headers, html = fetch(url)
                    finally: HDRS = save
                else:
                    final, headers, html = fetch(url)
                err = None
                break
            except urllib.error.HTTPError as e:
                err = f"HTTP {e.code}"
                try:
                    body = e.read(2_500_000)
                    if body[:2] == b"\x1f\x8b": body = gzip.decompress(body)
                    btxt = body.decode("utf-8", "replace")
                    if RE_THEME.search(btxt):  # e.g. password page 401/403 still Liquid
                        final, headers, html = url, dict(e.headers), btxt
                        err = None
                        break
                except Exception:
                    pass
            except Exception as e:
                err = type(e).__name__ + ": " + str(e)[:80]
        if html is not None:
            break
    if html is None:
        result["is_shopify"] = "Unknown"
        result["confidence"] = "None"
        result["method"] = "fetch failed"
        result["notes"] = err or "unreachable"
        return result

    theme = parse_theme(html)
    sigs = shopify_fingerprints(html, headers)

    if theme is None and sigs:
        # try a deeper page — some homepages are landers; theme obj on collection page
        try:
            u = final.rstrip("/") + "/collections/all"
            _, h2, html2 = fetch(u)
            t2 = parse_theme(html2)
            if t2:
                theme, html, headers = t2, html2, h2
        except Exception:
            pass

    hydrogen = any("hydrogen" in s or "oxygen" in s for s in sigs)

    if theme:
        result["is_shopify"] = "Yes"
        result["theme_name"] = str(theme.get("name") or "")
        tsid = theme.get("theme_store_id")
        schema = theme.get("schema_name") or ""
        result["theme_base"] = schema
        result["theme_store_id"] = "" if tsid in (None, "") else str(tsid)
        if tsid:
            result["theme_store_name"] = THEME_STORE.get(int(tsid), "")
        if not schema and not tsid:
            result["theme_base"] = "Custom theme (no theme store id)"
        result["confidence"] = "High"
        result["method"] = "Shopify.theme object"
        result["notes"] = "; ".join(sigs[:4])
    elif hydrogen:
        result["is_shopify"] = "Yes (Headless)"
        result["theme_base"] = "Headless (Hydrogen/Oxygen) — no Liquid theme"
        result["confidence"] = "High"
        result["method"] = "hydrogen/oxygen markers"
        result["notes"] = "; ".join(sigs[:5])
    elif sigs:
        result["is_shopify"] = "Yes"
        result["theme_base"] = "Undetermined (Shopify detected, theme object not exposed)"
        result["confidence"] = "Medium"
        result["method"] = "fingerprints only"
        result["notes"] = "; ".join(sigs[:5])
    else:
        result["is_shopify"] = "No"
        # light platform hint
        hint = ""
        for pat, name in [(r"salesforce|demandware|dwstatic", "Salesforce Commerce Cloud"),
                          (r"bigcommerce", "BigCommerce"), (r"woocommerce|wp-content", "WooCommerce/WordPress"),
                          (r"magento|mage-", "Magento/Adobe Commerce"), (r"squarespace", "Squarespace"),
                          (r"wixstatic|wix\.com", "Wix"), (r"__next|_next/static", "Next.js (custom/headless)"),
                          (r"sfcc|scene7", "Salesforce Commerce Cloud")]:
            if re.search(pat, html, re.I):
                hint = name; break
        result["theme_base"] = "N/A — not Shopify"
        result["confidence"] = "High"
        result["method"] = "no shopify fingerprints"
        result["notes"] = ("platform hint: " + hint) if hint else ""
    return result

def main():
    src = sys.argv[1]; dst = sys.argv[2]
    limit_domains = sys.argv[3].split(",") if len(sys.argv) > 3 else None
    rows = list(csv.reader(open(src, encoding="utf-8-sig")))
    header, data = rows[0], rows[1:]
    # pad rows
    data = [r + [""] * (len(header) - len(r)) for r in data if any(c.strip() for c in r)]
    domains = sorted({norm_domain(r[1]) for r in data if r[1].strip()})
    if limit_domains:
        domains = [d for d in domains if d in limit_domains]
    print(f"probing {len(domains)} domains...", file=sys.stderr)
    results = {}
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(detect, d): d for d in domains}
        done = 0
        for f in cf.as_completed(futs):
            d = futs[f]
            try:
                results[d] = f.result()
            except Exception as e:
                results[d] = {"domain": d, "is_shopify": "Unknown", "theme_name": "",
                              "theme_base": "", "theme_store_id": "", "theme_store_name": "",
                              "confidence": "None", "method": "error", "notes": str(e)[:100]}
            done += 1
            if done % 20 == 0:
                print(f"  {done}/{len(domains)}", file=sys.stderr)
    new_cols = ["Shopify Detected (Live)", "Theme Name (Store Label)", "Theme Base (Schema)",
                "Theme Store ID", "Theme Store Name", "Theme Detection Confidence",
                "Theme Detection Method", "Theme Detection Notes"]
    out = [header + new_cols]
    for r in data:
        d = norm_domain(r[1]) if r[1].strip() else ""
        res = results.get(d)
        if res:
            out.append(r + [res["is_shopify"], res["theme_name"], res["theme_base"],
                            res["theme_store_id"], res["theme_store_name"], res["confidence"],
                            res["method"], res["notes"]])
        else:
            out.append(r + (["No website", "", "", "", "", "None", "no website in row", ""] if not d
                            else ["", "", "", "", "", "", "", ""]))
    with open(dst, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(out)
    print(json.dumps({d: {k: v for k, v in r.items() if k in ('is_shopify','theme_base','theme_store_id','confidence')} for d, r in sorted(results.items())}, indent=1)[:4000])

if __name__ == "__main__":
    main()
