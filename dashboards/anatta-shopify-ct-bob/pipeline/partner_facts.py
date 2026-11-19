#!/usr/bin/env python3
"""Partner facts for one book: which technology partners, and which of their rivals, each storefront runs.

A Heartbeat score puts partner motion first, and partner motion is written from these facts (see the Heartbeat Source
playbook, "Why a partner moves"). This step only states what three scans saw. It writes no move and scores nothing.

  BuiltWith detect export   first and last detected date per technology, and the host it was seen on
  Store Leads               the technologies and installed apps it lists for the storefront (no dates)
  Live check                what the page itself loaded on the day of the build (live_check.py)
  Browser scan              what a real browser called when it loaded the store and ran a search (browser_scan.js).
                            It joins the live check as the "Live site" source.

Who is a partner is not decided here: it is read from the partner registry (the Golden Triangle Console's export,
partner_registry.json). A vendor the registry marks "rel": true is a partner. LANES below only says which lane a vendor
works in and what each scan calls it; a vendor in a lane that is not a partner is a rival a partner could take out.

Rules, each from a lesson in the Heartbeat Source:
  - The main site is the store. Only shop., store., checkout. and buy. subdomains join it. Other hosts are listed apart.
  - A BuiltWith-only sighting needs 60 days of history (a one-day sighting is not a live tool), unless Store Leads or
    the live page shows the same vendor.
  - Live means seen within 75 days of the export, or on the live page. Anything older is "removed", with its dates.
  - A DNS record (mail, name server) is weaker than a tag on the page, so it is marked "dns".
  - A search tool that only BuiltWith lists is "not confirmed", and not counted, at a store whose search page the browser
    scan ran without the page calling it: an export can keep listing a tool after the store has stopped using it. For
    other lanes the same finding is only flagged ("unseen_in_browser"), because a tag can sit behind a consent banner or
    on a page the scan did not open.
  - The export is checked against the browser, vendor by vendor. Where the browser could run a search on at least five
    stores at which BuiltWith lists a vendor, and confirmed fewer than half of them, BuiltWith's word alone is not enough
    for that vendor anywhere in the book: a listing that rests on BuiltWith only is "not confirmed", readable store or not.
  - A tool named only in a store's page source, with no call seen and no export listing, is "not confirmed" where the
    browser saw the store call another tool for the same job.
  - --contradicted names tools an export lists that first-hand evidence rules out at that store (its own security policy
    allows no host of that vendor): the listing becomes "not confirmed".
  - --confirmed names facts read first-hand in research ([{"name": account, "vendor": ..., "at": the store it was read at when
    that store is not a row on the list (optional), "note": what was read and
    where}]). Such a fact gains the source "Research", so it no longer rests on the export alone.

A row is read at the domain the book lists for it, which is the storefront the book means. Where the book lists a
corporate site and the store sits elsewhere, --store-domains names the store ({"Account Name As Exported": "store.com"}).

Usage: partner_facts.py <builtwith zip|dir> <accounts_input.json> <partner_registry.json> <out.json> [--live live.json]
                        [--browser browser.json] [--confirmed confirmed.json] [--contradicted contradicted.json]
                        [--store-domains map.json] [--as-of YYYY-MM-DD]
"""
import csv, io, json, os, re, sys, zipfile, datetime, collections

args = sys.argv[1:]
def opt(flag, default=None):
    if flag in args:
        i = args.index(flag); v = args[i + 1]; del args[i:i + 2]; return v
    return default
LIVE_PATH, AS_OF_ARG, STORE_DOMAINS, BROWSER_PATH, CONFIRMED_PATH = opt("--live"), opt("--as-of"), opt("--store-domains"), opt("--browser"), opt("--confirmed")
CONTRA_PATH = opt("--contradicted")
BW, ACC, REG, OUT = args[:4]
LIVE_DAYS, HISTORY_DAYS = 75, 60
STORE_SUBS = ("shop.", "store.", "checkout.", "buy.")
DNS_CATS = {"mx", "ns"}
SKIP_CATS = {"link", "ads", "docinfo", "registrar", "ssl", "copyright", "parked", "hosting", "cdns", "CDN", "Server", "Web Server", "Web Master", "language", "mapping", "media", "feeds"}

# lane -> vendor -> the names the scans use for it (lower case). The first lane a vendor appears in is its lane.
LANES = {
    "email": {
        "Klaviyo": ["klaviyo", "klaviyo for wordpress"],
        "Bloomreach": ["bloomreach", "exponea", "bloomreach engagement"],
        "Braze": ["braze"], "Iterable": ["iterable"],
        "Salesforce Marketing Cloud": ["salesforce marketing cloud", "exacttarget email", "exacttarget", "igodigital", "salesforce marketing cloud account engagement"],
        "Listrak": ["listrak"], "Zeta": ["zeta marketing platform", "zeta global", "zeta"], "Sailthru": ["sailthru", "sailthru horizon"],
        "Emarsys": ["emarsys", "sap emarsys"], "Bronto": ["bronto email", "bronto"], "Oracle Responsys": ["responsys", "oracle responsys"],
        "Acoustic": ["acoustic campaign", "silverpop"], "Cheetah Digital": ["cheetah digital", "cheetahmail"], "Bluecore": ["bluecore"],
        "Wunderkind": ["wunderkind", "bouncex", "bounce exchange"], "Cordial": ["cordial"], "Epsilon": ["epsilon", "conversant"],
        "Adobe Campaign": ["adobe campaign"], "Mailchimp": ["mailchimp", "mailchimp for wordpress"], "Constant Contact": ["constant contact"],
        "Retention Science": ["retention science"], "4Cite": ["4cite"], "Dotdigital": ["dotdigital", "dotmailer"], "Omnisend": ["omnisend"],
    },
    "sms": {
        "Attentive": ["attentive", "attentive mobile"], "Postscript": ["postscript"],
        "Vibes": ["vibes"], "Mobivity": ["mobivity"], "SMSBump": ["smsbump"],
    },
    "reviews": {
        "Yotpo": ["yotpo", "yotpo reviews"], "Okendo": ["okendo"],
        "Bazaarvoice": ["bazaarvoice", "bazaarvoice social commerce", "curalate"], "PowerReviews": ["powerreviews"],
        "Emplifi": ["emplifi", "emplifi ugc", "turnto", "pixlee"], "Olapic": ["olapic"], "Shopper Approved": ["shopper approved"],
        "Judge.me": ["judge me", "judge.me", "judgeme"], "Stamped": ["stamped", "stamped.io"], "Trustpilot": ["trustpilot"], "Reevoo": ["reevoo"],
    },
    "helpdesk": {
        "Gorgias": ["gorgias"], "Kustomer": ["kustomer"],
        "Zendesk": ["zendesk", "zendesk embeddables", "zopim", "zendesk chat"],
        "Salesforce Service Cloud": ["salesforce service cloud", "salesforce live agent", "salesforce desk", "salesforce chat (live agent)"],
        "Freshdesk": ["freshdesk", "freshchat", "freshdesk chat"], "LivePerson": ["liveperson"], "Genesys": ["genesys", "genesys cloud cx platform"],
        "Gladly": ["gladly"], "Intercom": ["intercom", "intercom help"], "Ada": ["ada support", "ada"], "iAdvize": ["iadvize"],
        "Powerfront": ["powerfront"], "LiveChat": ["livechat"], "Olark": ["olark"], "eGain": ["egain"], "Khoros": ["khoros"],
        "Nuance": ["nuance"], "Sierra": ["sierra"], "Linc": ["linc global", "linc"], "Help Scout": ["help scout"], "Tidio": ["tidio"],
    },
    "search": {
        "Algolia": ["algolia"], "Constructor": ["constructor", "constructor io", "constructor.io"], "Fast Simon": ["fast simon", "instant search plus"],
        "Oracle Endeca": ["endeca", "oracle endeca"], "Lucidworks": ["lucidworks"], "Coveo": ["coveo"], "Unbxd": ["unbxd"], "Findify": ["findify"],
        "Hawk Search": ["hawk search", "hawksearch"], "Searchspring": ["searchspring", "athos commerce"], "Klevu": ["klevu"], "Nosto": ["nosto"],
        "SLI Systems": ["sli systems"], "GroupBy": ["groupby"], "Reflektion": ["reflektion"], "Attraqt": ["attraqt"],
    },
    "returns": {
        "Loop": ["loop returns", "loop"], "AfterShip": ["aftership"],
        "Narvar": ["narvar"], "Happy Returns": ["happy returns"], "Returnly": ["returnly"], "Route": ["route", "routeapp"], "Optoro": ["optoro"],
    },
    "cross-border": {
        "Global-e": ["global-e", "globale", "global e", "borderfree"], "ESW": ["esw", "eshopworld"],
        "Zonos": ["zonos", "iglobal stores"], "Reach": ["reach"], "FlavorCloud": ["flavorcloud"],
    },
    "subscriptions": {
        "Recharge": ["recharge", "recharge payments", "recharge subscriptions"], "Skio": ["skio"], "Stay.ai": ["stay ai", "stay.ai", "retextion"],
        "Ordergroove": ["ordergroove"], "Recurly": ["recurly"], "Bold Subscriptions": ["bold subscriptions"], "Smartrr": ["smartrr"],
    },
    "loyalty": {
        "Smile.io": ["smile io", "smile.io"], "Rivo": ["rivo loyalty", "rivo"], "Friendbuy": ["friendbuy"], "Talon.One": ["talon.one", "talon one"],
        "Rokt": ["rokt"], "LoyaltyLion": ["loyalty lion", "loyaltylion"], "Annex Cloud": ["annex cloud"], "Extole": ["extole"],
    },
    "personalisation": {
        "Dynamic Yield": ["dynamic yield"], "Rebuy": ["rebuy"], "Shoplift": ["shoplift"],
        "Monetate": ["monetate"], "Certona": ["certona"], "Adobe Target": ["adobe target standard", "omniture adobe test and target", "adobe target"],
        "Salesforce Personalization": ["salesforce marketing cloud personalisation", "salesforce interaction studio", "salesforce personalization", "evergage"],
        "Optimizely": ["optimizely"], "AB Tasty": ["ab tasty"], "Granify": ["granify"],
    },
    "fraud": {
        "Signifyd": ["signifyd"], "Forter": ["forter"], "NoFraud": ["nofraud"],
        "Riskified": ["riskified"], "Kount": ["kount"], "Sift": ["sift science", "sift"], "ThreatMetrix": ["threatmetrix"],
    },
    "performance": {"Yottaa": ["yottaa"], "Noibu": ["noibu"]},
    "analytics": {"Elevar": ["elevar", "elevar conversion tracking"], "Triple Whale": ["triple whale"]},
    "mobile": {"Tapcart": ["tapcart"]},
}
SEEN_AS = {"borderfree": "Borderfree"}     # a product a partner owns under another name: the fact says which name the scan saw
VENDOR, LANE = {}, {}
for lane, vendors in LANES.items():
    for v, names in vendors.items():
        LANE.setdefault(v, lane)
        for n in names: VENDOR.setdefault(n, v)

# The registry says who is a partner. Its own names and aliases are also matched, for vendors LANES spells differently.
reg = json.load(open(REG, encoding="utf-8"))["registry"]
REL = {x["name"] for x in reg if x.get("rel")}
REL |= {"Loop"} if "Loop" in REL or "Loop Returns" in REL else set()
for x in reg:
    if x["name"] in LANE:
        for a in x.get("aliases") or []: VENDOR.setdefault(a.lower(), x["name"])
is_partner = lambda v: v in REL

def vendor_of(tech):
    t = re.sub(r"\s+", " ", tech.strip().lower())
    t = re.sub(r"[,:‑-]\s+.*$", "", t) if t not in VENDOR else t      # "Klaviyo, Email Marketing & SMS" -> "klaviyo"
    return VENDOR.get(t) or VENDOR.get(re.sub(r"\s+(returns & exchanges|ai helpdesk & chat|search & discovery|product reviews.*)$", "", t))

def dom(u): return re.sub(r"^www\.", "", re.sub(r"^https?://", "", (u or "").strip().lower()).split("/")[0])
def parents(d):
    parts = d.split("."); return [".".join(parts[i:]) for i in range(len(parts) - 1)]

def read_detect(path):
    def rows(name, fh):
        cat = os.path.basename(name)[:-4]
        if "_" in cat: return                 # the sub-category files repeat the top-level ones
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

g = lambda r, k: (r.get(k) or "").strip()
seen = collections.defaultdict(dict)          # domain -> (vendor, where) -> {"first", "last", "dns", "host"}
last_seen = ""
for cat, r in read_detect(BW):
    d, tech = g(r, "Domain").lower(), g(r, "Technology Name")
    if not d or not tech or cat in SKIP_CATS: continue
    v = vendor_of(tech)
    if not v: continue
    host = re.sub(r"/.*$", "", g(r, "Location on Website").lower()) or d
    where = "store" if host in (d, "www." + d) or any(host == s + d for s in STORE_SUBS) else host
    first, last = g(r, "First Detected")[:10], g(r, "Last Detected")[:10]
    e = seen[d].setdefault((v, where), {"first": first or "9999", "last": last, "dns": True, "as": set()})
    if tech.lower() in SEEN_AS: e["as"].add(SEEN_AS[tech.lower()])
    e["first"], e["last"] = min(e["first"], first or e["first"]), max(e["last"], last)
    e["dns"] = e["dns"] and cat in DNS_CATS
    if re.match(r"20[12]\d-", last): last_seen = max(last_seen, last) if last <= datetime.date.today().isoformat() else last_seen
AS_OF = datetime.date.fromisoformat(AS_OF_ARG or last_seen)

def days(a, b):
    try: return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days
    except Exception: return None

live_apps, live_read = {}, set()             # live_read: the storefronts whose page actually loaded (a bot wall reads nothing)
if LIVE_PATH:
    for host, v in json.load(open(LIVE_PATH, encoding="utf-8")).items():
        if v.get("bot_wall") or v.get("error") or not (200 <= (v.get("status") or 0) < 400): continue
        live_read.add(dom(host))
        live_apps.setdefault(dom(host), set()).update({vendor_of(a) for a in (v.get("apps") or [])} - {None})

browser = {}                                  # domain -> {"read", "search_read", "seen": {vendor: how}}
if BROWSER_PATH:
    for d, v in json.load(open(BROWSER_PATH, encoding="utf-8"))["stores"].items(): browser[dom(d)] = v

def split_list(s): return [x.strip() for x in re.split(r",\s{1,2}(?=[A-Z0-9])", s or "") if x.strip()]

def facts_for(domain, storeleads):
    """Every lane vendor seen at one storefront, with where and when."""
    bw_dom = next((p for p in parents(domain) if p in seen), None)
    sl = {vendor_of(t) for t in split_list(storeleads.get("Technologies")) + split_list(storeleads.get("Apps"))} - {None}
    br = browser.get(domain) or {}
    lv = live_apps.get(domain, set()) | {v for v in (br.get("seen") or {}) if v in LANE}
    out, side = {}, []
    for (v, where), e in (seen.get(bw_dom) or {}).items():
        if where != "store":
            if days(e["last"], AS_OF.isoformat()) is not None and days(e["last"], AS_OF.isoformat()) <= LIVE_DAYS: side.append(f"{v} on {where}")
            continue
        out[v] = {"vendor": v, "lane": LANE[v], "partner": is_partner(v), "first": e["first"][:7], "last": e["last"][:7], "sources": ["BuiltWith"], "dns": e["dns"], "seen_as": sorted(e["as"]),
                  "_age": days(e["last"], AS_OF.isoformat()), "_span": days(e["first"], e["last"])}
    for v in sl | lv:
        e = out.setdefault(v, {"vendor": v, "lane": LANE[v], "partner": is_partner(v), "first": "", "last": "", "sources": [], "dns": False, "seen_as": [], "_age": None, "_span": None})
        if v in sl: e["sources"].append("Store Leads")
        if v in lv: e["sources"].append("Live site")
    rows = []
    called = collections.defaultdict(set)     # lane -> the tools the browser saw this store call
    for v2, how in (br.get("seen") or {}).items():
        if how == "call" and v2 in LANE: called[LANE[v2]].add(v2)
    for v, e in out.items():
        corroborated = len(e["sources"]) > 1 or e["sources"] != ["BuiltWith"]
        recent = e["_age"] is not None and e["_age"] <= LIVE_DAYS
        if "Live site" in e["sources"] or "Store Leads" in e["sources"]: state = "live"
        elif recent and (e["_span"] or 0) >= HISTORY_DAYS: state = "live"
        elif recent: state = "brief sighting"            # not counted: under 60 days of history and no second scan
        else: state = "removed"
        if e["dns"] and state == "live" and not corroborated: state = "live (dns only)"
        # what the browser scan adds: a tool only the export lists, at a store the browser read without seeing it
        # (the browser has to have seen some other tool there: a page that loaded but called nothing may be a block page)
        unseen = e["sources"] == ["BuiltWith"] and bool(br.get("read")) and bool(br.get("seen"))
        if unseen and state == "live" and e["lane"] == "search" and br.get("search_read"): state = "not confirmed"
        # a name that sits in the page source only (nothing called it, no export lists it), at a store whose browser load
        # called another tool for the same job: the store runs the other tool, and this one is not confirmed
        if state == "live" and e["sources"] == ["Live site"] and (br.get("seen") or {}).get(v) == "page" and called[e["lane"]] - {v}: state = "not confirmed"
        rows.append({k: v2 for k, v2 in {**e, "state": state, "unseen_in_browser": unseen}.items() if not k.startswith("_")})
    rows.sort(key=lambda r: (not r["partner"], r["lane"], r["vendor"]))
    return rows, sorted(side)

acc = json.load(open(ACC, encoding="utf-8"))
store_domain = json.load(open(STORE_DOMAINS, encoding="utf-8")) if STORE_DOMAINS else {}
confirmed = collections.defaultdict(dict)     # account name -> vendor -> what research read first-hand
if CONFIRMED_PATH:
    for c in json.load(open(CONFIRMED_PATH, encoding="utf-8")): confirmed[c["name"]][c["vendor"]] = (c["note"], c.get("at", ""))    # "at": the store it was read at, when that store is not a row
contradicted = collections.defaultdict(dict)  # account name -> vendor -> first-hand evidence that the store does not run it
if CONTRA_PATH:
    for c in json.load(open(CONTRA_PATH, encoding="utf-8")): contradicted[c["name"]][c["vendor"]] = c["note"]
res = []
for a in acc:
    a = {**a, "domain": dom(store_domain.get(a["name"]) or a.get("book_domain") or a["domain"])}
    rows, side = facts_for(a["domain"], {} if a["name"] in store_domain else (a.get("storeleads") or {}))
    extra = []
    for o in a.get("other_storefronts") or []:
        r2, s2 = facts_for(dom(o["domain"]), o.get("storeleads") or {})
        extra.append({"label": o.get("label", ""), "domain": o["domain"], "vendors": r2})
    for v in rows:
        if v["vendor"] in confirmed.get(a["name"], {}):
            v["sources"].append("Research"); v["research_note"] = confirmed[a["name"]][v["vendor"]][0]
            if v["state"] in ("not confirmed", "brief sighting", "live (dns only)"): v["state"] = "live"
            v["unseen_in_browser"] = False
    # The reverse: first-hand evidence that a store cannot be running a tool an export still lists (its own security policy
    # allows no host of that vendor, say). The listing is then "not confirmed": not counted, and not read as absent either.
    for v in rows:
        if v["vendor"] in contradicted.get(a["name"], {}) and v["state"] in ("live", "live (dns only)", "brief sighting"):
            v["state"] = "not confirmed"; v["research_note"] = contradicted[a["name"]][v["vendor"]]
    # A tool research read first-hand at a store no scan listed it for (a cookie policy that names the vendor, the store's own
    # page calling it): it is a fact about the store like any other, and it says where it came from.
    for vendor, (note, at) in confirmed.get(a["name"], {}).items():
        if vendor in LANE and not any(v["vendor"] == vendor for v in rows):
            rows.append({"vendor": vendor, "lane": LANE[vendor], "partner": is_partner(vendor), "first": "", "last": "", "sources": ["Research"], "dns": False, "seen_as": [],
                         "state": "live", "unseen_in_browser": False, "research_note": note, **({"at": at} if at else {})})
    rows.sort(key=lambda r: (not r["partner"], r["lane"], r["vendor"]))
    res.append({"name": a["name"], "domain": a["domain"], "vendors": rows, "side_hosts": side, "other_storefronts": extra,
                "scans": {"builtwith": any(p in seen for p in parents(a["domain"])), "storeleads": bool((a.get("storeleads") or {}).get("Technologies")),
                          "research": any("Research" in v["sources"] for v in rows),
                          "live": a["domain"] in live_read or bool((browser.get(a["domain"]) or {}).get("read")),
                          "search_page": bool((browser.get(a["domain"]) or {}).get("search_read"))}})
# How far the export can be trusted, vendor by vendor: of its listings at stores where the browser ran a search, how many did the browser see?
check = collections.defaultdict(lambda: [0, 0])
for x in res:
    br = browser.get(x["domain"]) or {}
    if not (br.get("search_read") and br.get("seen")): continue
    for v in x["vendors"]:
        if "BuiltWith" in v["sources"] and v["state"] in ("live", "not confirmed"):
            check[v["vendor"]][0] += 1; check[v["vendor"]][1] += "Live site" in v["sources"]
UNRELIABLE = {v: {"tested": t, "confirmed": c} for v, (t, c) in check.items() if t >= 5 and c * 2 < t}
for x in res:
    for v in x["vendors"]:
        if v["vendor"] in UNRELIABLE and v["sources"] == ["BuiltWith"] and v["state"] == "live": v["state"] = "not confirmed"
json.dump({"as_of": AS_OF.isoformat(), "rules": {"live_days": LIVE_DAYS, "history_days": HISTORY_DAYS, "store_subdomains": STORE_SUBS},
           "export_checked": {v: {"tested": t, "confirmed": c} for v, (t, c) in sorted(check.items()) if t >= 5}, "export_not_trusted_alone": UNRELIABLE,
           "partners": sorted(v for v in LANE if is_partner(v)), "accounts": res}, open(OUT, "w", encoding="utf-8"), indent=0, ensure_ascii=False)

c = collections.Counter(); r_ = collections.Counter()
for x in res:
    for v in x["vendors"]:
        if v["state"].startswith("live"): (c if v["partner"] else r_)[v["vendor"]] += 1
print(f"as of {AS_OF} | {len(res)} accounts | {sum(1 for x in res if any(v['partner'] and v['state'].startswith('live') for v in x['vendors']))} with a partner live")
print("partners live at:", ", ".join(f"{k} {n}" for k, n in c.most_common()))
print("rivals live at:  ", ", ".join(f"{k} {n}" for k, n in r_.most_common(30)))
print("states:", dict(collections.Counter(v["state"] for x in res for v in x["vendors"])))
if browser: print("export against the browser (stores where a search ran):", ", ".join(f"{v} {c}/{t}" for v, (t, c) in sorted(check.items(), key=lambda kv: -kv[1][0]) if t >= 5), "| not trusted alone:", sorted(UNRELIABLE))
