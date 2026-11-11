#!/usr/bin/env python3
"""Authoritative scoring for one rep's book: merge research batch files + verifier verdicts with the account inputs,
compute both fit scores, blend, gate, tier. Single source of truth for every number on the dashboard.
The formula, weights, thresholds and gates are the Oct 2026 Anatta x Shopify build's, unchanged.

Everything that names an account (shared buying centres, display names, the misattributed-signal list, platform-family
overrides) comes from book.json, which lives with the data, not in the repo.

Usage: score.py <build_dir> <accounts_csv> <book_json> <out_json>
"""
import csv, json, sys, glob, os, re, collections, datetime

B, ACCOUNTS_CSV, BOOK, OUT = sys.argv[1:5]
book = json.load(open(BOOK))
AS_OF = datetime.date.fromisoformat(book["as_of"])   # the day both exports were pulled
inputs = {a["name"]: a for a in json.load(open(f"{B}/accounts_input.json"))}

# ---------- load research (precedence: triage < research batches < rework) ----------
records, sources = {}, {}
for f in sorted(glob.glob(f"{B}/results/triage.json")) + sorted(glob.glob(f"{B}/results/batch_*.json")) + sorted(glob.glob(f"{B}/results/rework_*.json")):
    try:
        d = json.load(open(f))
    except Exception as e:
        print("BAD JSON", f, e); continue
    for r in d.get("accounts", []):
        if r.get("name") in inputs:
            records[r["name"]] = r; sources[r["name"]] = os.path.basename(f)
        else:
            print("unknown account name in", os.path.basename(f), "->", r.get("name"))

verdicts = collections.defaultdict(list)
for f in sorted(glob.glob(f"{B}/verify/*.json")):
    try:
        d = json.load(open(f))
    except Exception as e:
        print("BAD JSON", f, e); continue
    lens = "platform" if f.endswith("__platform.json") else "model"
    for v in (d.get("verdicts") if isinstance(d, dict) and "verdicts" in d else [d]):
        if v.get("name") not in inputs:
            print("unknown account name in", os.path.basename(f), "->", v.get("name")); continue
        v["lens"] = lens
        verdicts[v["name"]].append(v)

# ---------- deterministic pieces (identical to the Oct 2026 build) ----------
def fire_intent(f):
    p = {"High": 10, "Medium": 7, "Low": 3}.get(f["intent"], 2)
    if f["in_market"]: p += 5
    s = None if f["score"] == "" else float(f["score"])
    if s is not None: p += 5 if s >= 50 else 3 if s >= 35 else 1 if s > 0 else 0
    if f["signals"]: p += 3
    return min(20, p)

def bonus(f):
    b = 0
    if f["in_market"]: b += 3
    if f["intent"] == "High": b += 3
    if re.search(r"shopify", f["signals"] or "", re.I): b += 4
    return b

GATE_TEXT = {
    "already_plus": "Already on Shopify Plus — expansion / reference, not a replatform prospect",
    "gov": "Government or military — not a Shopify merchant",
    "distress": "Financial distress, wound down or absorbed",
    "non_merchant": "No plausible commerce surface",
    "bad_record": "Not a real account record",
    "restricted": "Category Shopify cannot host",
}
clamp = lambda v, lo, hi: max(lo, min(hi, v))
BLANK_FIRE = {"intent": "", "score": "", "in_market": False, "signals": "", "recency": "", "engagement": "", "last_signal": ""}

# ---------- documented, book-specific handling (each one is shown on the record) ----------
# The Apollo row for this account is a different company from the one in the book, so its FIRE fields are not this
# account's signal. They stay visible, exactly as exported, but do not score.
SIGNAL_MISATTRIBUTED = book.get("signal_misattributed", {})   # account name -> why
# Documented whitespace cap, as in the Oct 2026 build: where Shopify cannot convert the platform in a quarter (there: national
# retailers on proprietary platforms; here: a competitor platform that went live inside the last two years), platform whitespace
# is capped. The rubric's top band is for LEGACY platforms. The uncapped score stays on the record.
WHITESPACE_CAP = book.get("whitespace_cap", {})               # account name -> {"cap": n, "reason": "..."}
ACCOUNT_NOTES = book.get("account_notes", {})                 # account name -> a caveat added to the record's flags
# Rows that roll up to one buying centre: one decision covers all of them.
GROUPS = book.get("groups", {})                               # centre -> [account names]
group_of = {n: g for g, names in GROUPS.items() for n in names}
assert all(n in inputs for n in group_of), [n for n in group_of if n not in inputs]
assert all(n in inputs for n in list(WHITESPACE_CAP) + list(ACCOUNT_NOTES) + list(SIGNAL_MISATTRIBUTED)), "book.json names an account that is not in the book"

# Record names that are a domain string or a label artefact get a readable display name; the record name is always shown beside it.
DISPLAY = book.get("display", {})                             # account name -> readable name
assert all(n in inputs for n in DISPLAY), [n for n in DISPLAY if n not in inputs]

# Platform family for filters and the breakdown, read off the researcher's free-text platform line. Order matters: a store
# that research could not find outranks a platform BuiltWith last saw years ago. PLAT_OVERRIDE settles the rows the rules get wrong.
PLAT_RULES = [
    ("Shopify Plus", r"shopify plus"),
    ("No online store", r"^(unconfirmed[:;,]?\s*)?(no |none\b)|no (?:[a-z-]+ ){0,3}(?:store|storefront|shop|commerce|e-?commerce|cart|ordering)|not a (?:store|merchant)|brochure|marketing site|informational"),
    ("Salesforce Commerce Cloud", r"salesforce commerce|demandware|sfcc|sfra|sitegenesis"),
    ("Shopify", r"shopify"),
    ("Adobe Commerce / Magento", r"magento|adobe commerce"),
    ("BigCommerce", r"bigcommerce"),
    ("WooCommerce", r"woocommerce"),
    ("Other enterprise", r"oracle|sap\b|hybris|vtex|hcl|optimizely|episerver|netsuite|suitecommerce|commercetools|kibo|znode|sitecore"),
    ("Custom build", r"custom|bespoke|in-house|proprietary|headless"),
]
PLAT_OVERRIDE = book.get("plat_override", {})                 # account name -> platform family
def plat_family(name, text):
    if name in PLAT_OVERRIDE: return PLAT_OVERRIDE[name]
    t = (text or "").lower()
    for fam, pat in PLAT_RULES:
        if re.search(pat, t): return fam
    return "Other / unclear"

# In card and table text, "Other enterprise" is replaced by the platform's own name where the researcher gave one.
ENTERPRISE_NAMES = [("vtex", "VTEX"), ("oracle", "Oracle Commerce"), ("hcl", "HCL Commerce"), ("optimizely", "Optimizely"), ("episerver", "Optimizely"),
                    ("hybris", "SAP Commerce"), ("sap", "SAP Commerce"), ("netsuite", "NetSuite"), ("suitecommerce", "NetSuite"),
                    ("commercetools", "commercetools"), ("kibo", "Kibo"), ("znode", "Znode"), ("sitecore", "Sitecore")]
def plat_label(family, text):
    if family != "Other enterprise": return family
    t = (text or "").lower()
    hits = sorted((t.index(k), n) for k, n in ENTERPRISE_NAMES if k in t)
    return hits[0][1] if hits else family

def recency_window(rows):
    """The scoring-run dates for which every (last signal date, recency label) pair in the export is consistent."""
    span = {"<7d": (0, 7), "8-30d": (8, 30), "31-90d": (31, 90)}
    lo, hi = datetime.date.min, datetime.date.max
    for last, label in rows:
        m = re.match(r"([A-Za-z]{3})\w* (\d+)\w* (\d{4})$", last or "")
        if not m or label not in span: continue
        d = datetime.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y").date()
        lo, hi = max(lo, d + datetime.timedelta(days=span[label][0])), min(hi, d + datetime.timedelta(days=span[label][1]))
    return [lo.strftime("%b %-d"), hi.strftime("%b %-d, %Y")] if datetime.date.min < lo <= hi < datetime.date.max else None

CRM_PRESENCE = re.compile(r"\bin salesforce\b|\bSFDC\b", re.I)   # stated once, in the internal-only in_sfdc field
def plain(text):
    """Researchers sometimes name the input field `prior_review`; readers know it as the earlier review of this book."""
    t = re.sub(r"\bprior_review'?s?\b", "the earlier review", text or "")
    return t[:1].upper() + t[1:] if t.startswith("the earlier review") else t
def clean_flags(flags):
    """Drop flags that only restate CRM presence, and take the shouting out of an all-caps lead-in."""
    out = []
    for f in flags:
        if CRM_PRESENCE.search(f): continue
        out.append(plain(re.sub(r"^([A-Z][A-Z ]{6,}):", lambda m: m.group(1).capitalize().replace("apollo", "Apollo") + ":", f)))
    return out

def days_since(s):
    m = re.match(r"([A-Za-z]{3})\w* (\d+)\w* (\d{4})$", s or "")
    if not m: return None
    d = datetime.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y").date()
    return (AS_OF - d).days

out = []
for name, a in inputs.items():
    r = records.get(name)
    f = a["fire"]
    f_scored = BLANK_FIRE if name in SIGNAL_MISATTRIBUTED else f
    common = {"name": name, "display": DISPLAY.get(name, name), "domain": a["domain"], "website": a["website"], "linkedin": a["linkedin"], "book_domain": a["book_domain"],
              "domain_note": a["domain_note"], "group": group_of.get(name, ""), "fire": f, "signals_raw": a["signals_raw"],
              "fire_days_since_signal": days_since(f["last_signal"]), "in_sfdc": a["in_sfdc"]}
    if not r:
        out.append({**common, "missing": True, "tier": "NA", "shopify_fit": None, "anatta_fit": None, "triangle": None, "gate": "", "gate_reason": ""})
        continue
    s, an = dict(r["shopify"]), r["anatta"]
    adj_notes = []
    if name in SIGNAL_MISATTRIBUTED: adj_notes.append("FIRE not scored: " + SIGNAL_MISATTRIBUTED[name])
    sf_uncapped = clamp(sum(s[k] for k in ("whitespace", "scale", "model_fit", "unified", "timing", "ecosystem")) + s["penalties"], 0, 100)
    cap = WHITESPACE_CAP.get(name)
    if cap and s["whitespace"] > cap["cap"]:
        adj_notes.append(f"Platform whitespace capped {s['whitespace']}→{cap['cap']} (Shopify fit {sf_uncapped} before the cap): {cap['reason']}")
        s["whitespace"] = cap["cap"]
    sf_raw = s["whitespace"] + s["scale"] + s["model_fit"] + s["unified"] + s["timing"] + s["ecosystem"]
    sf = clamp(sf_raw + s["penalties"], 0, 100)
    sf_research = sf
    intent_pts = fire_intent(f_scored)
    af = clamp(an["brand_surface"] + an["modernization"] + an["scale"] + an["ltv"] + intent_pts, 0, 100)
    af_research = af
    gate = r.get("gate", "") or ""
    gate_reason = r.get("gate_reason", "")
    # ---------- apply verifier verdicts ----------
    vs = verdicts.get(name, [])
    sf_sugg = [v["shopify_fit_suggested"] for v in vs if v["verdict"] in ("adjust", "refute") and v.get("shopify_fit_suggested") is not None]
    af_sugg = [v["anatta_fit_suggested"] for v in vs if v["verdict"] in ("adjust", "refute") and v.get("anatta_fit_suggested") is not None]
    if sf_sugg:
        new = round((sf + sum(sf_sugg) / len(sf_sugg)) / 2)  # conservative: average of research and verifier views
        if new != sf: adj_notes.append(f"Shopify fit {sf}→{new} after verification")
        sf = new
    if af_sugg:
        new = round((af + sum(af_sugg) / len(af_sugg)) / 2)
        if new != af: adj_notes.append(f"Anatta fit {af}→{new} after verification")
        af = new
    gate_sugg = [v["gate_suggested"] for v in vs if v["verdict"] == "refute" and v.get("gate_suggested") not in (None, "keep")]
    if gate_sugg:
        newg = gate_sugg[0]  # a refuting verifier can add or remove a gate; take the first and record why
        if newg != gate:
            adj_notes.append(f"Gate '{gate or 'none'}'→'{newg or 'none'}' after verification")
            gate = newg
            gate_reason = next(v["reason"] for v in vs if v["verdict"] == "refute" and v.get("gate_suggested") == newg)
    if gate == "non_merchant" and sf >= 20:  # the non_merchant gate only bites when the Shopify score is genuinely low
        adj_notes.append(f"non_merchant gate ignored: Shopify fit {sf} ≥ 20"); gate = ""; gate_reason = ""
    bon = bonus(f_scored)
    tri = min(100, round(0.55 * sf + 0.45 * af + bon))
    if gate == "already_plus": tier = "EXP"
    elif gate: tier = "X"
    elif tri >= 62 and sf >= 63: tier = "T1"
    elif tri >= 48: tier = "T2"
    elif tri >= 36: tier = "T3"
    else: tier = "T4"
    bw = a["builtwith"]
    out.append({
        **common, "missing": False,
        "category": r["category"], "model": r["model"], "size_est": r["size_est"], "platform": r["platform_confirmed"],
        "plat": plat_family(name, r["platform_confirmed"]),
        "plat_label": plat_label(plat_family(name, r["platform_confirmed"]), r["platform_confirmed"]),
        "hq": r["hq"], "ownership": r["ownership"],
        "shopify_sub": {k: s[k] for k in ["whitespace", "scale", "model_fit", "unified", "timing", "ecosystem", "penalties"]},
        "shopify_fit_research": sf_research, "shopify_fit_uncapped": sf_uncapped, "whitespace_capped": sf_uncapped != sf_research,
        "penalty_reason": s["penalty_reason"],
        "anatta_sub": {"brand_surface": an["brand_surface"], "modernization": an["modernization"], "scale": an["scale"], "ltv": an["ltv"], "intent": intent_pts},
        "anatta_fit_research": af_research,
        "shopify_fit": sf, "anatta_fit": af, "bonus": bon, "triangle": tri, "tier": tier,
        "gate": gate, "gate_reason": plain(gate_reason or GATE_TEXT.get(gate, "")) if gate else "",
        "story": plain(r["story"]), "shopify_angle": plain(r["shopify_angle"]), "anatta_angle": plain(r["anatta_angle"]),
        "evidence": [{"claim": plain(e["claim"]), "source": e["source"]} for e in r["evidence"]], "flags": clean_flags(r["flags"]) + ([ACCOUNT_NOTES[name]] if name in ACCOUNT_NOTES else []), "confidence": r["confidence"],
        "verification": [{"lens": v["lens"], "verdict": v["verdict"], "reason": v["reason"], "evidence": v.get("evidence", [])} for v in vs],
        "adjustments": adj_notes, "signal_misattributed": name in SIGNAL_MISATTRIBUTED,
        "storeleads": a["storeleads"], "builtwith": {k: v for k, v in bw.items() if k != "note"},
        "source": sources.get(name),
    })

out.sort(key=lambda x: (x["triangle"] is None, -(x["triangle"] or 0), x["name"]))

# ---------- assertions: the quality bar, enforced ----------
SH_MAX = {"whitespace": 25, "scale": 20, "model_fit": 20, "unified": 15, "timing": 10, "ecosystem": 10}
AN_MAX = {"brand_surface": 20, "modernization": 20, "scale": 20, "ltv": 20, "intent": 20}
src = {r["Company Name"].strip(): r for r in csv.DictReader(open(ACCOUNTS_CSV, newline="", encoding="utf-8-sig"))}
g = lambda r, k: (r.get(k) or "").strip()
for x in out:
    row = src[x["name"]]   # every FIRE value shown matches the export exactly
    assert x["fire"] == {"intent": g(row, "FIRE_Intent"), "score": g(row, "FIRE_Score_Total"), "in_market": g(row, "In-market") == "true",
                         "signals": g(row, "FIRE_Signals"), "recency": g(row, "FIRE_Recency"), "engagement": g(row, "FIRE_Engagement"),
                         "last_signal": g(row, "FIRE_Last_Signal_At")}, x["name"]
    if x["missing"]: continue
    ss, aa = x["shopify_sub"], x["anatta_sub"]
    assert all(0 <= ss[k] <= m for k, m in SH_MAX.items()) and ss["penalties"] <= 0, x["name"]
    assert all(0 <= aa[k] <= m for k, m in AN_MAX.items()), x["name"]
    assert x["shopify_fit_research"] == clamp(sum(ss[k] for k in SH_MAX) + ss["penalties"], 0, 100), x["name"]
    assert x["anatta_fit_research"] == clamp(sum(aa.values()), 0, 100), x["name"]
    assert x["triangle"] == min(100, round(0.55 * x["shopify_fit"] + 0.45 * x["anatta_fit"] + x["bonus"])), x["name"]
    if x["tier"] in ("X", "EXP"): assert x["gate"] and x["gate_reason"].strip(), f'{x["name"]}: gate without a reason'
    else: assert not x["gate"], x["name"]
    if x["tier"] == "T1": assert all(x[k].strip() for k in ("story", "shopify_angle", "anatta_angle")), f'{x["name"]}: T1 without a written play'
blob = json.dumps(out, ensure_ascii=False)
assert not re.search(r"\b001[A-Za-z0-9]{12,15}\b", blob), "a Salesforce record ID leaked into the scored book"

tiers = collections.Counter(x["tier"] for x in out)
scored = [x for x in out if not x["missing"]]
centres = {x["group"] or x["name"] for x in out}
summary = {"accounts": len(out), "scored": len(scored), "missing": [x["name"] for x in out if x["missing"]], "tiers": dict(tiers),
           "buying_centres": len(centres), "grouped_rows": sum(1 for x in out if x["group"]),
           "verified": sum(1 for x in scored if x["verification"]), "adjusted": sum(1 for x in scored if x["adjustments"]),
           "confidence": dict(collections.Counter(x["confidence"] for x in scored)),
           "triaged": sum(1 for x in scored if x["source"] == "triage.json"),
           "reworked": sum(1 for x in scored if (x["source"] or "").startswith("rework_")),
           "domain_mismatches": sum(1 for x in out if x["domain_note"]), "not_in_sfdc": sum(1 for x in out if not x["in_sfdc"]),
           "fire": {"with_score": sum(1 for x in out if x["fire"]["score"] != ""), "in_market": sum(1 for x in out if x["fire"]["in_market"]),
                    "with_signal": sum(1 for x in out if x["fire"]["signals"]),
                    "intent": dict(collections.Counter(x["fire"]["intent"] or "(blank)" for x in out)),
                    "newest_signal_days": min((x["fire_days_since_signal"] for x in out if x["fire_days_since_signal"] is not None), default=None)},
           "as_of": AS_OF.isoformat(), "book_label": book["label"], "title": book["title"], "slug": book["slug"],
           "verification": book.get("verification", "web")}   # "web" = verifiers searched; "consistency" = checked each record against its own evidence
no_bw = [a["name"] for a in inputs.values() if "note" in a["builtwith"]]
summary["no_builtwith"], summary["no_builtwith_names"] = len(no_bw), [DISPLAY.get(n, n) for n in no_bw]
summary["fire"]["recency_window"] = recency_window([(x["fire"]["last_signal"], x["fire"]["recency"]) for x in out])
if os.path.exists(f"{B}/batches/index.json"):
    depth = collections.Counter()
    for b in json.load(open(f"{B}/batches/index.json")): depth[b["depth"]] += len(b["names"])
    summary["research_depth"] = dict(depth)
json.dump({"summary": summary, "accounts": out}, open(OUT, "w"), indent=0, ensure_ascii=False)
print(json.dumps(summary, indent=1))
print("\nTOP 30:")
for x in scored[:30]:
    print(f'{x["tier"]:3s} tri={x["triangle"]:3} sf={x["shopify_fit"]:3} af={x["anatta_fit"]:3} conf={x["confidence"]:4s} {x["name"][:34]:34s} | {x["platform"][:34]:34s} | {x["model"]}')
print("\nPLATFORM FAMILY (check by eye):")
for fam, rows in sorted(collections.Counter(x["plat"] for x in scored).items(), key=lambda kv: -kv[1]): print(f"  {rows:2d} {fam}")
for x in sorted(scored, key=lambda x: x["plat"]): print(f'  {x["plat"][:24]:24s} | {x["name"][:30]:30s} | {x["platform"][:110]}')
print("\nGATED:")
for x in scored:
    if x["tier"] in ("X", "EXP"): print(f'{x["tier"]:3s} {x["name"][:34]:34s} gate={x["gate"]:13s} {x["gate_reason"][:90]}')
