#!/usr/bin/env python3
"""Build the per-account research input set for one rep's book.

Always: the Apollo accounts export (the FIRE fields) + a BuiltWith export of the book.
Optionally: a Store Leads export of the book's domains and the live storefront check (live_check.py).
With more than one read on a storefront, each account also gets a `platform_read`: what every source says the
store runs on, side by side, and whether they agree. Nothing is averaged or voted on: research settles it.

Everything that names an account (domain aliases etc.) comes from book.json, which lives with the data, not in the repo.

BuiltWith comes in two shapes and both are read:
  - one wide CSV, a row per domain ("Root Domain", "eCommerce Platform", "<App> Last Detected", ...)
  - a "detect" export: a .zip or folder of per-category CSVs (shop.csv, analytics.csv, ...), each with
    Domain, Location on Website, Technology Name, First Detected, Last Detected

Usage: build_inputs.py <builtwith csv|zip|dir> <accounts_csv> <book_json> <out_json> [--storeleads <csv>] [--live <json>]"""
import csv, sys, json, re, collections, os, io, zipfile, datetime

args = sys.argv[1:]
def opt(flag):
    if flag in args:
        i = args.index(flag); v = args[i + 1]; del args[i:i + 2]; return v
    return None
SL_PATH, LIVE_PATH = opt("--storeleads"), opt("--live")
bw_path, ac_path, book_path, out = args[:4]

g = lambda r, k: (r.get(k) or "").strip()
book = json.load(open(book_path))
AS_OF = datetime.date.fromisoformat(book["as_of"])
ac = list(csv.DictReader(open(ac_path, newline='', encoding='utf-8-sig')))

def dom(u): return re.sub(r"^https?://(www\.)?", "", (u or "").strip().lower()).split("/")[0]
def lines(v): return [x.strip() for x in v.split("\n") if x.strip()]
def parents(d):
    """shop.brand.co.uk -> shop.brand.co.uk, brand.co.uk, co.uk (the caller stops at the first one it knows)."""
    parts = d.split(".")
    return [".".join(parts[i:]) for i in range(len(parts) - 1)]

# ---------- platform families: one vocabulary for every source ----------
FAMILIES = [
    ("Shopify Plus", r"shopify plus"),
    ("Shopify", r"shopify"),
    ("Salesforce Commerce Cloud", r"salesforce commerce|demandware|site ?genesis|\bsfra\b|\bsfcc\b"),
    ("Adobe Commerce / Magento", r"magento|adobe commerce"),
    ("SAP Commerce Cloud", r"sap commerce|hybris"),
    ("HCL Commerce", r"hcl commerce|websphere commerce"),
    ("Oracle Commerce", r"oracle commerce|\batg\b"),
    ("BigCommerce", r"bigcommerce"),
    ("WooCommerce", r"woocommerce"),
    ("commercetools", r"commercetools"),
    ("VTEX", r"\bvtex\b"),
    ("Kibo", r"\bkibo\b|mozu"),
    ("NetSuite SuiteCommerce", r"netsuite|suitecommerce"),
    ("Miva Merchant", r"\bmiva\b"),
    ("Optimizely Commerce", r"optimizely commerce|episerver"),
    ("Znode", r"\bznode\b"),
    ("Shopware", r"shopware"),
    ("PrestaShop", r"prestashop"),
    ("osCommerce", r"oscommerce"),
    ("Instacart Storefront", r"instacart"),
    ("Fanatics platform", r"fanatics platform"),
    ("Winery platform (WineDirect / vinSUITE / Commerce7)", r"winedirect|vinsuite|commerce7"),
    ("Squarespace Commerce", r"squarespace"),
    ("Webflow Ecommerce", r"webflow ecommerce"),
]
# what a detector prints when it sees a cart but cannot name the platform: a custom or unidentified build
GENERIC = re.compile(r"^(custom cart|cart functionality|pixels|unknown)$", re.I)
def family(text):
    t = (text or "").strip().lower()
    if not t: return ""
    if GENERIC.match(t): return "Custom / unidentified"
    for fam, pat in FAMILIES:
        if re.search(pat, t): return fam
    return ""
def same_family(a, b): return a == b or {a, b} == {"Shopify", "Shopify Plus"}

# ---------- BuiltWith, wide CSV (one row per domain) ----------
WIDE_KEYS = ["eCommerce Platform", "CMS Platform", "CRM Platform", "Marketing Automation Platform", "Payment Platforms",
             "CRuX Rank", "Cloudflare Rank", "Agency", "AI", "Compliance"]
def load_wide(path):
    rows = [r for r in csv.DictReader(open(path, newline='', encoding='utf-8-sig'))
            if "." in g(r, "Root Domain") and not g(r, "Root Domain").lower().startswith("compliance")]
    # every tracked technology in the export has "<X>", "<X> First Detected", "<X> Last Detected" columns
    apps = [h[:-len(" Last Detected")] for h in (rows[0].keys() if rows else []) if h.endswith(" Last Detected")]
    out = {}
    for b in rows:
        s = {k: g(b, k) for k in WIDE_KEYS if g(b, k)}
        det = []
        for a in apps:
            last, first = g(b, a + " Last Detected"), g(b, a + " First Detected")
            if g(b, a) == "Yes" or last:
                det.append(f"{a} ({'live' if g(b, a) == 'Yes' else 'seen'}; first {first or '?'}, last {last or '?'})")
        if det: s["Detected apps"] = "; ".join(det)
        out[g(b, "Root Domain").lower()] = {"stack": s, "entries": [{"family": family(x), "text": x.strip(), "host": "", "live": True, "blip": False}
                                                                   for x in re.split(r"[;,]", g(b, "eCommerce Platform")) if family(x)]}
    return out

# ---------- BuiltWith, "detect" export (per-category CSVs) ----------
# Technologies in shop.csv that are a commerce platform rather than an app that runs on one.
PLATFORM_TECH = re.compile(r"^(Shopify|Shopify Plus( Inferred)?|Salesforce Commerce Cloud( Storefront Reference Architecture)?|Site Genesis Salesforce Commerce Cloud|Demandware|"
                           r"Magento( 2| Enterprise| PWA Studio)?|Adobe Commerce.*|BigCommerce.*|WooCommerce|Oracle Commerce.*|SAP Commerce.*|SAP Hybris.*|HCL Commerce|"
                           r"IBM WebSphere Commerce.*|VTEX.*|commercetools|Kibo.*|Znode|Miva Merchant|osCommerce|Shopware.*|NetSuite.*|SuiteCommerce.*|PrestaShop.*|"
                           r"Optimizely Commerce.*|Episerver Commerce.*|Squarespace Add to Cart|Webflow Ecommerce|vinSUITE|WineDirect|Commerce7|Cart Functionality)$")
# Shopify's ecosystem (the rubric's "ecosystem pull") and the suites that weld a merchant to a competitor.
TRACKED = ["Klaviyo", "Yotpo", "Recharge", "Gorgias", "Okendo", "Attentive", "Global-e", "Loop Returns", "Rebuy", "Nosto", "Postscript", "Elevar", "Northbeam", "Triple Whale",
           "Shopify Pay", "Shop Pay Installments", "Shopify POS", "Shopify Markets Pro", "Klarna", "Afterpay", "Affirm", "Narvar", "Bazaarvoice", "PowerReviews",
           "Dynamic Yield", "BloomReach", "Algolia", "Braze", "Salesforce Marketing Cloud Personalisation", "ExactTarget", "Salesforce Service Cloud",
           "Adobe Experience Manager", "Adobe Marketing Cloud", "Contentful", "Contentstack", "Amplience", "Sitecore CMS", "Next.js", "Nuxt.js", "Oracle Cloud", "SAP Business Technology Platform"]
TRACKED_L = {t.lower(): t for t in TRACKED}
LIVE_DAYS = 75     # a technology last detected within this many days of the export counts as live
BLIP_DAYS = 30     # a platform seen for less than this long in total is a one-off detection

def read_detect(path):
    """Yield (category, row dict) for the top-level category files of a detect export (the sub-category files repeat them)."""
    def rows(name, fh):
        cat = os.path.basename(name)[:-4]
        if "_" in cat: return
        for r in csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8-sig", newline="")): yield cat, r
    if os.path.isdir(path):
        for f in sorted(os.listdir(path)):
            if f.endswith(".csv"):
                with open(os.path.join(path, f), "rb") as fh: yield from rows(f, fh)
    else:
        with zipfile.ZipFile(path) as z:
            for f in sorted(z.namelist()):
                if f.endswith(".csv") and "/" not in f.strip("/"):
                    with z.open(f) as fh: yield from rows(f, fh)

def load_detect(path):
    plats = collections.defaultdict(dict)   # domain -> (family, tech, host) -> [first, last]
    apps = collections.defaultdict(dict)    # domain -> tracked tech -> [first, last]
    agency = collections.defaultdict(set); n = collections.Counter()
    def span(d, k, first, last):
        if k in d: d[k] = [min(d[k][0], first or d[k][0]), max(d[k][1], last or d[k][1])]
        else: d[k] = [first, last]
    for cat, r in read_detect(path):
        d, tech = g(r, "Domain").lower(), g(r, "Technology Name")
        host = re.sub(r"/\*?$", "", g(r, "Location on Website").lower())
        first, last = g(r, "First Detected"), g(r, "Last Detected")
        if not d or not tech: continue
        n[d] += 1
        if cat == "shop" and PLATFORM_TECH.match(tech): span(plats[d], (family(tech), tech, "" if host in (d, "www." + d) else host), first, last)
        if cat == "agency": agency[d].add(tech)
        t = TRACKED_L.get(tech.lower())
        if t and cat not in ("mx", "ns", "link", "ads"): span(apps[d], t, first, last)
    def live(last):
        try: return (AS_OF - datetime.date.fromisoformat(last)).days <= LIVE_DAYS
        except Exception: return False
    out = {}
    for d in n:
        fams = collections.defaultdict(lambda: {"first": "9999", "last": "", "flavours": set()})   # (family, host)
        for (fam, tech, host), (first, last) in plats[d].items():
            e = fams[(fam, host)]; e["first"], e["last"] = min(e["first"], first or e["first"]), max(e["last"], last)
            if re.search(r"site genesis", tech, re.I): e["flavours"].add("SiteGenesis")
            if re.search(r"storefront reference", tech, re.I): e["flavours"].add("SFRA")
            if re.search(r"inferred", tech, re.I): e["flavours"].add("inferred")
            if re.search(r"pwa studio", tech, re.I): e["flavours"].add("PWA Studio")
        def blip(e):        # seen for under a month in total: a one-off detection, not a platform the site runs on
            try: return (datetime.date.fromisoformat(e["last"]) - datetime.date.fromisoformat(e["first"])).days < BLIP_DAYS
            except Exception: return False
        def state(e): return "one-off detection" if blip(e) else "live" if live(e["last"]) else "not seen recently"
        def show(fam, e): return f"{fam}{' [' + ', '.join(sorted(e['flavours'])) + ']' if e['flavours'] else ''} ({state(e)}; first {e['first'][:7]}, last {e['last'][:7]})"
        main = sorted(((fam, e) for (fam, host), e in fams.items() if not host), key=lambda kv: (not blip(kv[1]), kv[1]["first"]), reverse=True)
        other = sorted(((host, fam, e) for (fam, host), e in fams.items() if host), key=lambda kv: kv[2]["last"], reverse=True)
        s = {}
        if main: s["eCommerce Platform"] = "; ".join(show(f, e) for f, e in main)
        if other:
            s["Commerce on other hosts"] = "; ".join(f"{h}: {show(f, e)}" for h, f, e in other[:6]) + (f"; and {len(other) - 6} more" if len(other) > 6 else "")
        liveapps = sorted(a for a, (f, l) in apps[d].items() if live(l)); gone = sorted(a for a, (f, l) in apps[d].items() if not live(l))
        if liveapps: s["Detected apps"] = "; ".join(f"{a} (live; first {apps[d][a][0][:7]}, last {apps[d][a][1][:7]})" for a in liveapps)
        if gone: s["Seen earlier, not recently"] = "; ".join(f"{a} (last {apps[d][a][1][:7]})" for a in gone)
        if agency[d]: s["Agency"] = ", ".join(sorted(agency[d]))
        s["Technologies in the export"] = str(n[d])
        out[d] = {"stack": s, "entries": [{"family": fam, "text": show(fam, e), "host": host, "live": live(e["last"]), "blip": blip(e), "first": e["first"]}
                                          for host, fam, e in [("", f, e) for f, e in main] + other]}
    return out

bwd = load_detect(bw_path) if (os.path.isdir(bw_path) or bw_path.lower().endswith(".zip")) else load_wide(bw_path)
def bw_for(d):
    return next(((p, bwd[p]) for p in parents(d) if p in bwd), ("", None))

# ---------- Store Leads export of the book's domains (optional) ----------
sld = {}
if SL_PATH:
    rd = list(csv.reader(open(SL_PATH, newline="", encoding="utf-8-sig")))
    hdr = ["account", "domain"] + rd[0][2:]       # the export's first two columns are the uploaded list: account name, domain
    for row in rd[1:]:
        r = dict(zip(hdr, row + [""] * (len(hdr) - len(row))))
        d = dom(r["domain"])
        if "." not in d: continue                 # the uploaded list's own header row
        sld[d] = r
def sl_summary(r):
    if not r or not g(r, "platform"): return {}
    s = {"Store": g(r, "domain_url"), "Platform": g(r, "platform"), "Estimated yearly sales": g(r, "estimated_yearly_sales"),
         "Merchant name": g(r, "merchant_name"), "Headless": "yes" if g(r, "headless") == "true" else "",
         "Previous platform": f'{g(r, "last_platform")} (changed {g(r, "last_platform_changed")})' if g(r, "last_platform") else "",
         "Theme": " / ".join(x for x in [g(r, "theme"), g(r, "theme_vendor")] if x and x != "Unknown"),
         "Theme last changed": g(r, "last_theme_changed"),
         "Apps": ", ".join(g(r, "installed_apps_names").split(":")[:14]), "Features": ", ".join(g(r, "features").split(":")),
         "Technologies": ", ".join(g(r, "technologies").split(":")[:24])}
    return {k: v for k, v in s.items() if v}

# ---------- live storefront check (optional) ----------
live = json.load(open(LIVE_PATH)) if LIVE_PATH else {}
live_by = {re.sub(r"^www\.", "", h): r for h, r in live.items()}
NOT_COMMERCE = {"WordPress", "Drupal", "Sitecore", "Adobe Experience Manager", "Contentful", "Contentstack", "Amplience", "Squarespace", "Webflow", "Wix",
                "Salesforce B2B / Experience Cloud", "Next.js (custom / headless front end)", "Nuxt (custom / headless front end)", "Angular (custom front end)"}
def live_summary(d):
    r = live_by.get(d)
    if not r: return {}
    s = {"host": r["host"], "checked": r["checked"], "status": r["status"], "final_url": r["final_url"], "title": r["title"]}
    if not r["status"]: s["result"] = "did not answer: " + r["error"]
    elif r["bot_wall"]: s["result"] = f"a bot wall answered ({r['bot_wall']}), not the site: no read"
    elif r["status"] == 402: s["result"] = "Shopify answered \"store unavailable\" (HTTP 402): the store is closed or frozen"
    else: s["result"] = "page loaded"
    com = [p for p in r["platforms"] if p not in NOT_COMMERCE]
    if com: s["commerce_fingerprints"] = {p: r["evidence"][p] for p in com}
    oth = [p for p in r["platforms"] if p in NOT_COMMERCE]
    if oth: s["other_fingerprints"] = oth
    if r["shopify"]: s["shopify"] = r["shopify"]
    if r["apps"]: s["apps_on_page"] = r["apps"]
    moved = dom(r["final_url"])
    if r["status"] and moved and moved != d and not moved.endswith("." + d) and not d.endswith("." + moved): s["redirects_to"] = moved
    return s

def platform_read(a, book_dom, bw, sl, lv, lv_ap=None):
    """Every source's answer to "what does this storefront run on", in one vocabulary, and whether they agree.

    Up to three independent reads count: the BuiltWith export, Store Leads and the live site. A read counts only for the
    account's own main storefront: a detection on a side host, on another site the address redirects to, a one-off
    detection or one not seen recently is listed with the reason it does not count. Apollo's own BuiltWith column is the
    same vendor as the export and carries no host and no last-seen date, so it is shown as context and never counted."""
    src = []
    def add(source, fam, detail, why=""): src.append({"source": source, "family": fam, "detail": detail, "counts": not why, **({"not_counted": why} if why else {})})
    ap = a["apollo_builtwith"]["ecomm"]
    if ap:
        fams = [family(re.sub(r"\s+-\s+\d{4}-\d\d-\d\d$", "", x)) for x in ap]
        fam = next((f for f in fams if f and f != "Custom / unidentified"), next((f for f in fams if f), ""))
        if fam: add("Apollo's BuiltWith column", fam, "; ".join(ap[:4]), "context only: no host and no last-seen date")
    for e in (bw["entries"] if bw else []):
        why = f"side host {e['host']}" if e["host"] else "one-off detection" if e["blip"] else "" if e["live"] else "not seen recently"
        add("BuiltWith export", e["family"], e["text"], why)
    if sl and g(sl, "platform"):
        store = dom(g(sl, "domain_url"))
        why = "" if not store or store == book_dom or book_dom.endswith("." + store) else f"side host {store}" if store.endswith("." + book_dom) else f"another site, {store}"
        add("Store Leads", family(g(sl, "platform")) or g(sl, "platform"),
            g(sl, "platform") + (f", was {g(sl, 'last_platform')} until {g(sl, 'last_platform_changed')}" if g(sl, "last_platform") else "") + (f" (store read at {store})" if store and store != book_dom else ""), why)
    for p, ev in (lv.get("commerce_fingerprints") or {}).items():
        add("Live site", family(p) or p, ev, f"the address redirects to another site, {lv['redirects_to']}" if lv.get("redirects_to") else "")
    if lv_ap and lv_ap.get("commerce_fingerprints"):      # the Apollo view's domain, when the book lists another one
        h = dom(lv_ap["host"]); rel = book_dom.endswith("." + h) or h.endswith("." + book_dom)
        for p, ev in lv_ap["commerce_fingerprints"].items():
            add("Live site", family(p) or p, f"{ev} (read at {h}, the domain Apollo lists)", "" if rel else f"another site, {h}")
    votes = collections.OrderedDict()                     # source -> families it names on the main storefront
    for x in src:
        if x["counts"] and x["family"] != "Custom / unidentified": votes.setdefault(x["source"], []).append(x["family"])
    plus = any(f == "Shopify Plus" for fs in votes.values() for f in fs)
    norm = lambda f: "Shopify" if f == "Shopify Plus" else f
    sets = [set(map(norm, fs)) for fs in votes.values()]
    common = set.intersection(*sets) if sets else set()
    cart = any(x["family"] == "Custom / unidentified" for x in src)
    if not sets:
        verdict, fams = ("No source names a platform; a cart is detected, so the build is custom or unidentified" if cart else "No source names a platform"), []
    elif common:
        # where one source lists two platforms (an old one it still sees, a new one), the one all sources share is the read
        fam = sorted(common, key=lambda f: -sum(f in st for st in sets))[0]
        fams = ["Shopify Plus" if plus and fam == "Shopify" else fam]
        extra = sorted({f for st in sets for f in st} - {fam})
        n = len(sets)
        verdict = (f"{n} sources agree: {fams[0]}" if n > 1 else f"1 source ({list(votes)[0]}): {fams[0]}") + (f"; also detected: {', '.join(extra)}" if extra else "")
        if plus and n > 1 and sum("Shopify Plus" in fs for fs in votes.values()) < n: verdict += " (Plus per BuiltWith)"
    else:
        fams = sorted({f for st in sets for f in st})
        verdict = "Sources disagree: " + "; ".join(f"{k} says {' and '.join(sorted(set(v)))}" for k, v in votes.items())
    return {"verdict": verdict, "families": fams, "sources": src}

# The book (the rep's list, as uploaded to BuiltWith / Store Leads) and the Apollo view can disagree on an account's domain.
# book.json maps the Apollo website domain -> {book_domain, note}; `account_domain` does the same per account name, for
# the case where several Apollo rows share one website but the book gives each its own. The note is for a human.
DOMAIN_ALIAS = {k: (v["book_domain"], v["note"]) for k, v in book.get("domain_alias", {}).items()}
ACCOUNT_DOMAIN = {k: (v["book_domain"], v["note"]) for k, v in book.get("account_domain", {}).items()}
# Book rows that are a second storefront of an account already in the Apollo view (a shop subdomain, an alternate domain).
EXTRA = book.get("extra_surfaces", {})          # account name -> [{"label": ..., "domain": ...}]
names = {a["Company Name"].strip() for a in ac}
assert all(n in names for n in list(ACCOUNT_DOMAIN) + list(EXTRA)), [n for n in list(ACCOUNT_DOMAIN) + list(EXTRA) if n not in names]

accounts, used_bw, used_sl = [], set(), set()
for a in ac:
    name, d = a["Company Name"].strip(), dom(a["Website"])
    book_dom, note = ACCOUNT_DOMAIN.get(name) or DOMAIN_ALIAS.get(d, (d, ""))
    bw_key, bw = bw_for(book_dom)
    if bw: used_bw.add(bw_key)
    sl = sld.get(book_dom)
    if sl: used_sl.add(book_dom)
    rec = {
        "name": name, "domain": d, "website": g(a, "Website"), "linkedin": g(a, "Company Linkedin Url"),
        "book_domain": "", "domain_note": note,
        "book_name": g(sl, "account") if sl else "",
        "apollo_parent": g(a, "Apollo Parent Org Name"),
        "fire": {"intent": g(a, "FIRE_Intent"), "score": g(a, "FIRE_Score_Total"), "in_market": g(a, "In-market") == "true",
                 "signals": g(a, "FIRE_Signals"), "recency": g(a, "FIRE_Recency"), "engagement": g(a, "FIRE_Engagement"),
                 "last_signal": g(a, "FIRE_Last_Signal_At")},
        # raw booleans exactly as exported ("" = blank in the export, not false)
        "signals_raw": {"in_market": g(a, "In-market"), "website_visit": g(a, "Website visit"), "key_page_visit": g(a, "Key page visit"),
                        "linkedin_engagement": g(a, "LinkedIn engagement")},
        "storeleads": {k: g(a, k) for k in ["Est. GMV (storeleads)", "CMS (storeleads)", "Headless (storeleads)"] if g(a, k)},
        "mobile_score": g(a, "Mobile Score (PSI)"),
        "apollo_builtwith": {"ecomm": lines(g(a, "BuiltWith (ecomm)")), "payments": lines(g(a, "BuiltWith (payments)"))},
        "in_sfdc": bool(g(a, "Account Salesforce ID")),   # the ID itself never leaves the export
        "builtwith": bw["stack"] if bw else {"note": "no BuiltWith row"},
        "contacts": {"count": 0, "sample_titles": [], "countries": {}}, "in_accounts_export": True,
    }
    if not SL_PATH and not LIVE_PATH:       # the first book's shape, unchanged: book_domain is the BuiltWith domain when there is a row
        rec["book_domain"] = book_dom if bw else ""
        rec.pop("book_name"); rec.pop("apollo_parent")
    else:
        rec["book_domain"] = book_dom
        rec["storeleads"].update(sl_summary(sl))
        lv = live_summary(book_dom)
        rec["live"] = lv
        lv_ap = live_summary(d) if book_dom != d else {}
        if lv_ap: rec["live_apollo_domain"] = lv_ap
        rec["platform_read"] = platform_read(rec, book_dom, bw, sl, lv, lv_ap)
        others = []
        for x in EXTRA.get(name, []):
            xd = dom(x["domain"]); xk, xbw = bw_for(xd); xsl = sld.get(xd)
            if xbw and xk != bw_key: used_bw.add(xk)
            if xsl: used_sl.add(xd)
            xl = live_summary(xd)
            others.append({"label": x["label"], "domain": xd, "storeleads": sl_summary(xsl),
                           "builtwith": xbw["stack"] if xbw and xk != bw_key else {}, "live": xl,
                           "platform_read": platform_read({"apollo_builtwith": {"ecomm": []}}, xd, xbw if xbw and xk != bw_key else None, xsl, xl)})
            others[-1]["platform_read"].pop("families")
        if others: rec["other_storefronts"] = others
    accounts.append(rec)
unused = sorted(set(bwd) - used_bw)
assert not unused, f"BuiltWith domains with no Apollo account: {unused}"
unused_sl = sorted(set(sld) - used_sl)
assert not unused_sl, f"Store Leads rows with no Apollo account: {unused_sl}"
assert len({a["name"] for a in accounts}) == len(accounts), "duplicate account names"
accounts.sort(key=lambda a: a["name"].lower())
json.dump(accounts, open(out, "w"), indent=0, ensure_ascii=False)
c = collections.Counter
print("accounts", len(accounts), "| with BuiltWith row", sum(1 for a in accounts if "note" not in a["builtwith"]),
      "| domain mismatches reconciled", sum(1 for a in accounts if a["domain_note"]),
      "| no BuiltWith row:", [a["name"] for a in accounts if "note" in a["builtwith"]])
print("FIRE score present", sum(1 for a in accounts if a["fire"]["score"] != ""), "| intent", dict(c(a["fire"]["intent"] or "(blank)" for a in accounts)),
      "| in-market true", sum(1 for a in accounts if a["fire"]["in_market"]), "| signals", sum(1 for a in accounts if a["fire"]["signals"]),
      "| in SFDC", sum(1 for a in accounts if a["in_sfdc"]))
if SL_PATH or LIVE_PATH:
    print("Store Leads rows", len(sld), "| accounts with a Store Leads platform", sum(1 for a in accounts if a["storeleads"].get("Platform")),
          "| live check: page loaded", sum(1 for a in accounts if a["live"].get("result") == "page loaded"),
          "| bot wall", sum(1 for a in accounts if "bot wall" in a["live"].get("result", "")),
          "| extra storefronts attached", sum(len(a.get("other_storefronts", [])) for a in accounts))
    print("platform read:", dict(c(re.sub(r"^1 source \(.*", "1 source", a["platform_read"]["verdict"]).split(":")[0].split(";")[0] for a in accounts)))
